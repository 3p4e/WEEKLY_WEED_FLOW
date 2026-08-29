# Fleet unit surface: model-handle resolution is pure and worth pinning
# (the create/attach/delete round-trips are exercised on the wwf_mass stack,
# same convention as test_pipeline.py).
import ast
import json
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import fleet  # noqa: E402
from app.fleet import (  # noqa: E402
    TOOL_NAME,
    _resolve_model,
    _scope_block,
    agent_datasets,
    load_fleet,
    load_tool_source,
)


@pytest.fixture
def _fresh_fleet_cache(monkeypatch):
    """Force the module-level memoization in load_fleet() back to "never
    loaded" so a test can observe the FIRST load, independent of whatever
    earlier tests in this session already cached."""
    monkeypatch.setattr(fleet, "_FLEET_SPEC", None)
    yield


def test_resolve_model_falls_back_to_yaml_defaults_when_no_agents_exist():
    spec = load_fleet()
    model, embedding = _resolve_model(spec, [])
    assert model == spec["defaults"]["model"]
    assert embedding == spec["defaults"]["embedding"]


def test_resolve_model_adopts_an_existing_agent_handle_over_the_yaml_default():
    spec = {"defaults": {"model": "yaml/default-model", "embedding": "yaml/default-embed"}}
    existing = [
        {"llm_config": {}, "embedding_config": {}},  # no handle — skipped
        {"llm_config": {"handle": "deepseek/deepseek-chat"},
         "embedding_config": {"handle": "letta/letta-free"}},
        {"llm_config": {"handle": "should-never-be-picked"}},
    ]
    model, embedding = _resolve_model(spec, existing)
    assert model == "deepseek/deepseek-chat"
    assert embedding == "letta/letta-free"


def test_reg_checker_is_declared_with_its_regulatory_datasets():
    assert "DB1_REGULATORY" in agent_datasets("gf_reg_checker")


def test_no_agent_still_declares_a_letta_source():
    """Retrieval moved to RAGflow: a leftover `sources:` key would be silently
    ignored by fleet.py, so the agent would look grounded and not be."""
    spec = load_fleet()
    assert [a["name"] for a in spec["agents"] if "sources" in a] == []


def test_no_document_agent_may_reach_the_stability_corpus():
    """The stability/release boundary is enforced as a data boundary — no
    document agent may name the stability dataset, so it cannot surface a
    stability figure as a release value."""
    spec = load_fleet()
    for ag in spec["agents"]:
        assert not any("STABILITY" in d.upper() for d in ag.get("datasets", [])), ag["name"]


def test_scope_block_tells_an_ungranted_agent_not_to_search():
    assert "no document corpus" in _scope_block([], [])


def test_scope_block_flags_a_dataset_that_is_not_ingested_yet():
    block = _scope_block(["DB1_REGULATORY", "eCoA_DATABASE"], ["DB1_REGULATORY"])
    assert "NOT YET INGESTED (DB1_REGULATORY)" in block
    assert "They are not a corpus you have." in block
    # the granted-and-present dataset is still named as searchable
    assert "eCoA_DATABASE" in block


def test_every_agent_with_datasets_gets_a_scope_block_naming_them():
    spec = load_fleet()
    pending = (spec.get("ragflow") or {}).get("pending_ingest", [])
    for ag in spec["agents"]:
        block = _scope_block(ag.get("datasets", []), pending)
        for d in ag.get("datasets", []):
            assert d in block, (ag["name"], d)


def test_tool_source_defines_the_tool_and_nothing_runs_at_module_level():
    """The file is uploaded verbatim as the tool's source_code and executed in
    Letta's sandbox, so it must define exactly the one function and carry no
    module-level statements that would run there."""
    tree = ast.parse(load_tool_source())
    funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert funcs == [TOOL_NAME]
    assert [n for n in tree.body if not isinstance(n, ast.FunctionDef)] == []


def test_tool_source_contains_exactly_one_function_anywhere():
    """Letta derives a JSON schema from EVERY function it finds in the uploaded
    source and rejects the whole tool if any falls short. A nested helper was
    refused first for a missing docstring, then for an unannotated parameter
    (both observed live against letta-6ou3, where the tool silently failed to
    register while all 8 agents were created regardless). One function has no
    such surface, so keep it that way — inline instead of extracting."""
    funcs = [
        n.name
        for n in ast.walk(ast.parse(load_tool_source()))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert funcs == [TOOL_NAME], funcs


def test_the_tool_function_is_fully_annotated_and_documented():
    """The other half of what Letta's schema generation requires: a docstring,
    and a type annotation on every parameter."""
    fn = next(
        n for n in ast.parse(load_tool_source()).body if isinstance(n, ast.FunctionDef)
    )
    assert ast.get_docstring(fn)
    for arg in fn.args.args:
        assert arg.annotation is not None, arg.arg
    # every parameter is also described in the docstring, which is what the
    # model reads when choosing arguments
    doc = ast.get_docstring(fn)
    for arg in fn.args.args:
        assert arg.arg + " (" in doc, arg.arg


def test_tool_source_is_stdlib_only_and_imports_nothing_from_this_repo():
    """Letta's sandbox has no access to this repository."""
    tree = ast.parse(load_tool_source())
    names = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names += [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            assert n.level == 0, "no relative imports inside the tool"
            names.append((n.module or "").split(".")[0])
    assert set(names) <= {"json", "os", "urllib"}, names


def test_tool_has_a_description_for_the_model_to_select_on():
    assert len((load_fleet().get("ragflow") or {}).get("tool_description", "")) > 80


def test_declared_model_and_embedding_handles_are_provider_qualified():
    """A bare model name is rejected by POST /agents as a handle — the whole
    reason _resolve_model refuses to adopt one."""
    d = load_fleet()["defaults"]
    assert "/" in d["model"] and "/" in d["embedding"]


def test_declared_handles_win_when_the_server_serves_them():
    """The whole point of the declarative file: editing defaults must actually
    move the fleet. Before this, adoption from a live agent ran first and the
    old handle won forever."""
    spec = {"defaults": {"model": "yaml/wanted", "embedding": "yaml/wanted-embed"}}
    existing = [{"llm_config": {"handle": "live/other"},
                 "embedding_config": {"handle": "live/other-embed"}}]
    model, embedding = _resolve_model(
        spec, existing, {"yaml/wanted", "live/other"}, {"yaml/wanted-embed"}
    )
    assert (model, embedding) == ("yaml/wanted", "yaml/wanted-embed")


def test_unserved_declared_handle_falls_back_to_a_live_agents_handle():
    """A handle the server does not serve is the invented-handle case the
    handover warned about; a handle some agent already uses is proof it works."""
    spec = {"defaults": {"model": "yaml/retired", "embedding": "yaml/retired-embed"}}
    existing = [{"llm_config": {"handle": "live/works"},
                 "embedding_config": {"handle": "live/works-embed"}}]
    model, embedding = _resolve_model(spec, existing, {"live/works"}, {"live/works-embed"})
    assert (model, embedding) == ("live/works", "live/works-embed")


def test_unknown_served_set_keeps_the_old_adoption_behaviour():
    """If listing the server's handles fails we must not become stricter than
    before — _served_handles returns None and adoption still applies."""
    spec = {"defaults": {"model": "yaml/m", "embedding": "yaml/e"}}
    existing = [{"llm_config": {"handle": "live/m"}, "embedding_config": {"handle": "live/e"}}]
    assert _resolve_model(spec, existing, None, None) == ("live/m", "live/e")


def test_declared_defaults_are_not_an_out_of_credit_provider():
    """Guards the specific trap that cost a cutover: letta-6ou3 lists Anthropic
    and OpenAI handles it cannot bill."""
    model = load_fleet()["defaults"]["model"]
    assert not model.startswith(("anthropic/", "openai/")), model


def test_load_fleet_reads_the_file_only_once(_fresh_fleet_cache, monkeypatch):
    """MEDIUM: load_fleet() used to do a synchronous Path.read_text() +
    yaml.safe_load() on the event-loop thread on EVERY call. spawn_ephemeral
    (the fix's actual target) calls load_fleet() roughly a dozen times per
    single document job. Assert the read function itself is invoked at most
    once across many load_fleet() calls -- the caching, not just its result."""
    # Path is a slotted C type -- an instance attribute like FLEET_FILE can't
    # carry a monkeypatched method, so spy on yaml.safe_load instead (the
    # other half of load_fleet()'s read-and-parse work, and just as good a
    # proof that the file wasn't re-read-and-reparsed).
    calls = []
    real_safe_load = fleet.yaml.safe_load

    def counting_safe_load(*a, **k):
        calls.append(1)
        return real_safe_load(*a, **k)

    monkeypatch.setattr(fleet.yaml, "safe_load", counting_safe_load)

    first = load_fleet()
    for _ in range(11):  # mirrors "roughly a dozen times per job"
        again = load_fleet()
        assert again is first  # same cached object, not just equal content

    assert len(calls) == 1, f"fleet.yaml was read {len(calls)} times, expected 1"


def test_agent_datasets_reuses_the_cached_spec_too(_fresh_fleet_cache, monkeypatch):
    """agent_datasets() is the other unconditional load_fleet() caller named
    in the bug report -- same cache, same guarantee."""
    calls = []
    real_safe_load = fleet.yaml.safe_load

    def counting_safe_load(*a, **k):
        calls.append(1)
        return real_safe_load(*a, **k)

    monkeypatch.setattr(fleet.yaml, "safe_load", counting_safe_load)

    agent_datasets("gf_reg_checker")
    agent_datasets("gf_sop_author")
    load_fleet()
    assert len(calls) == 1


def test_context_window_and_max_tokens_are_declared_and_sane():
    """Letta sizes an unknown model from its DEFAULT of 30000, which truncated a
    real 9-section repair mid-reply. Both are declared so the model gets what it
    can actually take."""
    d = load_fleet()["defaults"]
    assert d["context_window"] >= 100_000
    assert d["max_tokens"] >= 8_000
    assert d["max_tokens"] < d["context_window"]


# ── The dataset map vs reality ──────────────────────────────────────────────
# These exist because of a live failure on 2026-08-27: RAGflow's eCOA_INGEST /
# eCOA_INGEST_SUMMA datasets had been deleted and replaced by a single
# eCoA_DATABASE re-ingest the day before, and nothing updated fleet.yaml. Five
# of eight agents were pointed at names that no longer resolved — including the
# one agent this file's own comment claimed had live grounding. Nothing caught
# it, because nothing checked the names against anything.


def test_every_declared_dataset_is_tracked_as_ingested_or_pending():
    """A dataset name in neither list is the exact failure above: an agent
    pointed at a corpus nobody is tracking the existence of."""
    spec = load_fleet()
    rag = spec["ragflow"]
    known = set(rag["ingested"]) | set(rag["pending_ingest"])
    for ag in spec["agents"]:
        for ds in ag.get("datasets", []):
            assert ds in known, f"{ag['name']} names untracked dataset {ds!r}"


def test_ingested_and_pending_are_disjoint():
    rag = load_fleet()["ragflow"]
    assert not (set(rag["ingested"]) & set(rag["pending_ingest"]))


def test_no_agent_is_granted_a_withheld_dataset():
    """The stability corpus is present in RAGflow and granted to nobody. This
    is the same guarantee as the STABILITY substring test above, asserted
    against the declared list rather than a name pattern."""
    spec = load_fleet()
    withheld = set(spec["ragflow"]["withheld"])
    for ag in spec["agents"]:
        assert not (set(ag.get("datasets", [])) & withheld), ag["name"]


def test_at_least_one_agent_can_actually_retrieve_something_today():
    """Guards the state this fix found the fleet in: every retrieval agent
    scoped exclusively to datasets that do not exist, so the entire fleet was
    ungrounded while presenting itself as grounded."""
    spec = load_fleet()
    live = set(spec["ragflow"]["ingested"])
    grounded = [a["name"] for a in spec["agents"] if set(a.get("datasets", [])) & live]
    assert grounded, "no agent is scoped to any dataset that exists"


def test_the_app_assistant_is_the_one_with_live_grounding():
    """Staff ask batch-QC questions in the app; the certificates answer them."""
    assert "eCoA_DATABASE" in agent_datasets("gf_app_assistant")


# ── Instruction blocks ──────────────────────────────────────────────────────


def _labels(blocks):
    return [b["label"] for b in blocks]


def test_every_agent_carries_the_mission_and_the_house_rules():
    """The mission block is what tells an agent WHY it is being asked — the
    thing that makes 'leave it blank' obviously right rather than unhelpful."""
    spec = load_fleet()
    for ag in spec["agents"]:
        labels = _labels(fleet._blocks_for(ag, spec))
        assert fleet.MISSION_BLOCK in labels, ag["name"]
        assert fleet.RULES_BLOCK in labels, ag["name"]
        assert fleet.PERSONA_BLOCK in labels, ag["name"]
        assert fleet.SCOPE_BLOCK in labels, ag["name"]


def test_the_corpus_guide_goes_only_to_agents_that_can_retrieve():
    """An agent with no datasets has no use for a description of corpora it
    cannot search, and is one nudge away from citing one."""
    spec = load_fleet()
    for ag in spec["agents"]:
        has_guide = fleet.CORPUS_BLOCK in _labels(fleet._blocks_for(ag, spec))
        assert has_guide == bool(ag.get("datasets")), ag["name"]


def test_governance_blocks_are_read_only_and_the_persona_is_not():
    """Every gf_ agent carries memory_replace/memory_insert, so without the
    flag an agent can rewrite its own house rules — or widen its own dataset
    scope, which is the guardrail keeping stability data out of release
    documents. `persona` stays writable: Letta owns that block."""
    spec = load_fleet()
    for ag in spec["agents"]:
        for block in fleet._blocks_for(ag, spec):
            expected = block["label"] != fleet.PERSONA_BLOCK
            assert block["read_only"] is expected, (ag["name"], block["label"])
    assert fleet.PERSONA_BLOCK not in fleet.GOVERNANCE_BLOCKS


def test_every_persona_is_a_brief_not_a_sentence():
    """The personas are the training. A one-line persona is what the fleet had
    before, and it left the model to guess its own output contract — which is
    how commentary and duplicated headings ended up inside controlled
    documents."""
    for ag in load_fleet()["agents"]:
        persona = ag["persona"]
        assert len(persona) > 600, ag["name"]
        for heading in ("ROLE", "NEVER"):
            assert heading in persona, (ag["name"], heading)


def test_the_authors_are_told_their_reply_is_used_verbatim():
    """The single fact that makes 'no preamble' a hard rule rather than a style
    note: nothing edits these replies before they reach the .docx."""
    spec = load_fleet()
    by_name = {a["name"]: a for a in spec["agents"]}
    for name in ("gf_sop_author", "gf_annex_author", "gf_raci_specialist"):
        assert "VERBATIM" in by_name[name]["persona"], name


def test_the_auditor_is_warned_off_the_both_tokens_verdict():
    """_qa_audit_passed fails a reply containing BOTH PASS and FIX, so a
    well-meant 'Verdict: PASS, no fixes needed' kills the document."""
    persona = next(a for a in load_fleet()["agents"] if a["name"] == "gf_qa_auditor")["persona"]
    assert "Verdict: PASS" in persona
    assert "NEVER write both tokens" in persona


# ── Scope block ─────────────────────────────────────────────────────────────


def test_scope_block_names_the_one_live_dataset_when_the_rest_are_pending():
    block = _scope_block(["eCoA_DATABASE", "DB1_REGULATORY"], ["DB1_REGULATORY"])
    assert "NOT YET INGESTED (DB1_REGULATORY)" in block
    assert "Only eCoA_DATABASE actually answers today." in block


def test_scope_block_says_there_is_no_corpus_at_all_when_every_grant_is_pending():
    """Five agents were in exactly this state and their scope block still read
    as though retrieval worked."""
    block = _scope_block(["DB1_REGULATORY"], ["DB1_REGULATORY"])
    assert "NO working corpus" in block


def test_scope_block_forbids_an_unscoped_search():
    """Omitting the tool's `datasets` argument searches every dataset the API
    key can reach — including the withheld one. The tool refuses it now; the
    block says so too."""
    assert "never omit the argument" in _scope_block(["eCoA_DATABASE"], [])


# ── Config reconciliation ───────────────────────────────────────────────────


class _ConfigClient:
    """Minimal stand-in: records the PATCH bodies _reconcile_config sends, and
    whether it went on to clear the agent's accumulated message buffer."""

    def __init__(self):
        self.patches: list[tuple[str, dict]] = []
        self.resets: list[str] = []

    async def update_agent_config(self, agent_id: str, body: dict) -> dict:
        self.patches.append((agent_id, body))
        return {}

    async def reset_messages(self, agent_id: str) -> None:
        self.resets.append(agent_id)


@pytest.mark.asyncio
async def test_reconcile_config_pushes_the_declared_window_onto_a_live_agent():
    """All eight live agents sat at Letta's LLM_MAX_CONTEXT_WINDOW['DEFAULT']
    of 30000 while fleet.yaml declared 128000, because both values are
    create-time only and the agents predate the declaration."""
    spec = load_fleet()
    client = _ConfigClient()
    agent = {"id": "agent-1", "llm_config": {"context_window": 30000, "max_tokens": 16384},
             "message_buffer_autoclear": True}
    ag = {"name": "gf_x", "autoclear": True}
    assert await fleet._reconcile_config(client, agent, ag, spec, "gf_x") is True
    assert client.patches == [("agent-1", {"context_window_limit": 128000})]


@pytest.mark.asyncio
async def test_reconcile_config_is_a_no_op_when_the_agent_already_matches():
    spec = load_fleet()
    client = _ConfigClient()
    agent = {
        "id": "agent-1",
        "llm_config": {
            "context_window": spec["defaults"]["context_window"],
            "max_tokens": spec["defaults"]["max_tokens"],
        },
        "message_buffer_autoclear": True,
    }
    ag = {"name": "gf_x", "autoclear": True}
    assert await fleet._reconcile_config(client, agent, ag, spec, "gf_x") is False
    assert client.patches == []
    assert client.resets == []


@pytest.mark.asyncio
async def test_reconcile_config_never_touches_the_model_handle():
    """fleet.yaml records leaving an existing agent's model alone as a standing
    decision; widening this reconciler would silently reverse it."""
    spec = load_fleet()
    client = _ConfigClient()
    agent = {"id": "a", "llm_config": {"context_window": 30000, "handle": "some/other-model"}}
    await fleet._reconcile_config(client, agent, {"name": "gf_x"}, spec, "gf_x")
    for _, body in client.patches:
        assert set(body) <= {"context_window_limit", "max_tokens", "message_buffer_autoclear"}
        assert "model" not in body and "handle" not in body


# ── The tool's own guardrails, executed rather than parsed ──────────────────


def _load_tool_callable():
    """Run the uploaded source the way Letta's sandbox does, and hand back the
    function itself so its behaviour can be tested, not just its shape."""
    ns: dict = {}
    exec(compile(load_tool_source(), TOOL_NAME + ".py", "exec"), ns)  # noqa: S102
    return ns[TOOL_NAME]


def test_tool_refuses_an_unscoped_search(monkeypatch):
    """Omitting `datasets` used to search every dataset the key could see —
    turning a forgotten argument into a full scope bypass, stability corpus
    included."""
    monkeypatch.setenv("RAGFLOW_BASE_URL", "http://ragflow.invalid")
    monkeypatch.setenv("RAGFLOW_API_KEY", "k")
    out = json.loads(_load_tool_callable()("what is the TAMC limit", ""))
    assert out["ok"] is False
    assert "datasets is required" in out["err"]


def test_tool_error_never_names_a_dataset_the_caller_was_not_granted(monkeypatch):
    """On an unresolvable scope the tool used to return the tenant's full
    dataset list — naming STABILITY_PROGRAMME to agents whose entire design is
    that they cannot know it exists, and handing them a name to try next."""
    listing = {"data": [{"name": "eCoA_DATABASE", "id": "1"},
                        {"name": "STABILITY_PROGRAMME", "id": "2"}]}

    class _Resp:
        def read(self):
            return json.dumps(listing).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setenv("RAGFLOW_BASE_URL", "http://ragflow.invalid")
    monkeypatch.setenv("RAGFLOW_API_KEY", "k")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())

    raw = _load_tool_callable()("any question", "DB1_REGULATORY,DB3_PP_CURRENT_unified")
    assert "STABILITY" not in raw
    out = json.loads(raw)
    assert out["ok"] is False
    assert out["unknown_datasets"] == ["DB1_REGULATORY", "DB3_PP_CURRENT_unified"]
    assert "available" not in out


# ── The tool is a shared server object, and nothing ever revisited it ───────


class _ToolClient:
    """Records what ensure_tool does to an already-registered tool."""

    def __init__(self, registered: dict | None):
        self.registered = registered
        self.updates: list[tuple] = []
        self.creates: list[tuple] = []

    async def list_tools(self):
        return [self.registered] if self.registered else []

    async def update_tool(self, tool_id, source_code, description=""):
        self.updates.append((tool_id, source_code, description))
        return {"id": tool_id}

    async def create_tool(self, source_code, description=""):
        self.creates.append((source_code, description))
        return {"id": "tool-new"}


@pytest.mark.asyncio
async def test_ensure_tool_rewrites_a_registered_tool_whose_source_has_drifted():
    """The tool is where dataset scoping is ENFORCED — it is what refuses an
    unscoped search and decides what an error discloses. Adopting it by name
    without checking its source meant a hardening edit could reach the repo,
    the tests and the image, and never the server."""
    client = _ToolClient({"id": "tool-1", "name": TOOL_NAME, "source_code": "def old(): pass"})
    assert await fleet.ensure_tool(client) == "tool-1"
    assert len(client.updates) == 1
    assert client.updates[0][1] == load_tool_source()
    assert not client.creates


@pytest.mark.asyncio
async def test_ensure_tool_leaves_an_up_to_date_tool_alone():
    """ensure_fleet runs on every document job; rewriting an unchanged tool on
    each one is pointless server churn."""
    client = _ToolClient({"id": "tool-1", "name": TOOL_NAME, "source_code": load_tool_source()})
    assert await fleet.ensure_tool(client) == "tool-1"
    assert client.updates == []


@pytest.mark.asyncio
async def test_ensure_tool_still_registers_when_nothing_is_there():
    client = _ToolClient(None)
    assert await fleet.ensure_tool(client) == "tool-new"
    assert client.creates[0][0] == load_tool_source()


# ── The scope as a control, not an instruction ──────────────────────────────
# Found by running the live fleet: asked for a stability result, gf_app_assistant
# correctly declined — but only because it had been told to. The tool cannot see
# which agent is calling it, so nothing would have stopped it had it decided
# otherwise. RAGFLOW_ALLOWED_DATASETS moves the limit into the tool's per-agent
# execution environment, where the model cannot reach it.


def test_the_tool_env_carries_the_agents_permitted_scope(monkeypatch):
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    env = fleet._tool_env(["eCoA_DATABASE", "DB1_REGULATORY"])
    assert env["RAGFLOW_ALLOWED_DATASETS"] == "eCoA_DATABASE,DB1_REGULATORY"


def test_the_tool_env_is_empty_when_ragflow_is_unconfigured(monkeypatch):
    """The tool then returns a clear 'not set' error rather than the agent
    quietly answering from its own memory."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "", raising=False)
    assert fleet._tool_env(["eCoA_DATABASE"]) == {}


def test_tool_refuses_a_dataset_outside_the_agents_allowlist(monkeypatch):
    monkeypatch.setenv("RAGFLOW_BASE_URL", "http://ragflow.invalid")
    monkeypatch.setenv("RAGFLOW_API_KEY", "k")
    monkeypatch.setenv("RAGFLOW_ALLOWED_DATASETS", "eCoA_DATABASE")
    # No urlopen stub: the refusal must happen BEFORE any network call, so a
    # real request here would blow up the test rather than pass it.
    out = json.loads(_load_tool_callable()("stability at 9 months", "STABILITY_PROGRAMME"))
    assert out["ok"] is False
    assert out["refused"] == ["STABILITY_PROGRAMME"]


def test_tool_allows_the_datasets_the_agent_is_granted(monkeypatch):
    """The allowlist must not break the one agent that can actually retrieve."""
    listing = {"data": [{"name": "eCoA_DATABASE", "id": "1"}]}
    chunks = {"data": {"chunks": [{"document_keyword": "BG1024, 752-2025, 27.02.2025, IJZ.pdf",
                                   "content": "олово 0,01 mg/kg"}]}}
    seq = [listing, chunks]

    class _Resp:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return json.dumps(self.payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setenv("RAGFLOW_BASE_URL", "http://ragflow.invalid")
    monkeypatch.setenv("RAGFLOW_API_KEY", "k")
    monkeypatch.setenv("RAGFLOW_ALLOWED_DATASETS", "eCoA_DATABASE,DB1_REGULATORY")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(seq.pop(0)))

    out = json.loads(_load_tool_callable()("heavy metals BG1024", "eCoA_DATABASE"))
    assert out["ok"] is True
    assert out["hits"][0]["document"] == "BG1024, 752-2025, 27.02.2025, IJZ.pdf"


def test_the_corpus_guide_does_not_name_the_withheld_dataset():
    """It used to, and the live agent then read the name straight back out in a
    refusal. Describing the boundary is the point; handing over the name is not."""
    spec = load_fleet()
    for withheld in spec["ragflow"]["withheld"]:
        assert withheld not in spec["corpus_guide"], withheld


class _EnvClient(_ConfigClient):
    pass


@pytest.mark.asyncio
async def test_reconcile_tool_env_leaves_an_agent_with_no_datasets_alone(monkeypatch):
    """A PATCH replaces the whole environment set, and gf_doc_orchestrator
    carries unrelated secrets for a different tool. An agent this module has no
    RAGflow env for must be left strictly alone, not reconciled to empty."""
    client = _EnvClient()
    agent = {"id": "a", "tool_exec_environment_variables": [{"key": "KVM4_RUNNER_URL"}]}
    assert await fleet._reconcile_tool_env(client, agent, {"name": "gf_x"}, "gf_x") is False
    assert client.patches == []


@pytest.mark.asyncio
async def test_reconcile_tool_env_is_a_no_op_once_the_scope_matches(monkeypatch):
    """Credentials are secrets the server may not echo back, so the comparison
    is on the scope alone — otherwise every ensure_fleet run looks like drift."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    client = _EnvClient()
    agent = {
        "id": "a",
        "tool_exec_environment_variables": [
            {"key": "RAGFLOW_ALLOWED_DATASETS", "value": "eCoA_DATABASE"}
        ],
    }
    ag = {"name": "gf_x", "datasets": ["eCoA_DATABASE"]}
    assert await fleet._reconcile_tool_env(client, agent, ag, "gf_x") is False
    assert client.patches == []


@pytest.mark.asyncio
async def test_reconcile_tool_env_pushes_a_missing_allowlist(monkeypatch):
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    client = _EnvClient()
    agent = {"id": "a", "tool_exec_environment_variables": [
        {"key": "RAGFLOW_BASE_URL", "value": "http://r"}]}
    ag = {"name": "gf_x", "datasets": ["eCoA_DATABASE", "DB1_REGULATORY"]}
    assert await fleet._reconcile_tool_env(client, agent, ag, "gf_x") is True
    body = client.patches[0][1]["tool_exec_environment_variables"]
    assert body["RAGFLOW_ALLOWED_DATASETS"] == "eCoA_DATABASE,DB1_REGULATORY"


# ── autoclear: the mandatory companion to a large context window ────────────
# Raising context_window_limit 30000 -> 128000 removed the trimming Letta had
# been doing to fit the smaller window, so a persistent one-shot worker started
# carrying every document it had ever seen into its next prompt. Measured live
# on 2026-08-27, the first time the declared window actually reached the fleet:
# gf_qa_auditor at 78,201 of 128,000 tokens after ten messages, and a real
# annex job dying on a 300s ReadTimeout at the qa-audit stage. The same audit
# on a clone with no history took 49.5s and passed, which is what ruled the
# instructions out as the cost.


def test_every_pipeline_worker_declares_autoclear():
    """These five are sent one prompt and read for one reply; none of them ever
    refers back to a previous turn, so none of them may keep one."""
    by_name = {a["name"]: a for a in load_fleet()["agents"]}
    for name in ("gf_sop_author", "gf_annex_author", "gf_raci_specialist",
                 "gf_qa_auditor", "gf_reg_checker"):
        assert by_name[name].get("autoclear") is True, name


def test_the_conversational_agents_keep_their_history():
    """Clearing these would break the thing they exist to do — gf_app_assistant
    holds a real back-and-forth with staff, and the orchestrator resolves
    TYPE/MODE across turns."""
    by_name = {a["name"]: a for a in load_fleet()["agents"]}
    for name in ("gf_app_assistant", "gf_doc_orchestrator"):
        assert by_name[name].get("autoclear") is False, name


def test_every_agent_states_its_autoclear_intent_explicitly():
    """`autoclear` reads as False when omitted, and False is the setting that
    caused the outage — so an agent added without thinking about it would
    silently inherit the broken behaviour. Make the file say which it is."""
    for ag in load_fleet()["agents"]:
        assert "autoclear" in ag, ag["name"]
        assert isinstance(ag["autoclear"], bool), ag["name"]


def test_created_agents_carry_their_autoclear_setting():
    spec = load_fleet()
    for ag in spec["agents"]:
        body = fleet._build_body(ag, spec, "m", "e", ag["name"], "")
        assert body["message_buffer_autoclear"] is ag["autoclear"], ag["name"]


@pytest.mark.asyncio
async def test_reconcile_turns_autoclear_on_and_clears_the_existing_buffer():
    """Setting the flag only bounds growth from here. gf_qa_auditor was already
    at 78k and would have stayed slow — so the accumulated buffer goes too."""
    client = _ConfigClient()
    agent = {"id": "a", "llm_config": {"context_window": 128000, "max_tokens": 16384},
             "message_buffer_autoclear": False, "message_ids": ["m"] * 9}
    ag = {"name": "gf_qa_auditor", "autoclear": True}
    assert await fleet._reconcile_config(client, agent, ag, load_fleet(), "gf_qa_auditor") is True
    assert client.patches == [("a", {"message_buffer_autoclear": True})]
    assert client.resets == ["a"]


@pytest.mark.asyncio
async def test_a_failed_clear_is_retried_on_the_next_pass():
    """The regression this replaced: the clear was keyed off the flag's
    TRANSITION, so the first live run set the flag, failed the clear (the route
    wants a body), and spent the edge. The next run saw the flag already on,
    concluded there was nothing to do, and left the agent at 78k. Keyed off the
    buffer, an agent whose flag is already set but whose history survived still
    gets cleared."""
    client = _ConfigClient()
    agent = {"id": "a", "llm_config": {"context_window": 128000, "max_tokens": 16384},
             "message_buffer_autoclear": True, "message_ids": ["m"] * 9}
    ag = {"name": "gf_qa_auditor", "autoclear": True}
    assert await fleet._reconcile_config(client, agent, ag, load_fleet(), "gf_qa_auditor") is True
    assert client.patches == []          # nothing left to configure
    assert client.resets == ["a"]        # but the stale buffer still goes


@pytest.mark.asyncio
async def test_reconcile_does_not_clear_the_buffer_of_a_conversational_agent():
    """A reset here would throw away a staff member's conversation."""
    client = _ConfigClient()
    agent = {"id": "a", "llm_config": {"context_window": 30000, "max_tokens": 16384},
             "message_buffer_autoclear": False}
    agent["message_ids"] = ["m"] * 16   # a real staff conversation
    ag = {"name": "gf_app_assistant", "autoclear": False}
    await fleet._reconcile_config(client, agent, ag, load_fleet(), "gf_app_assistant")
    assert client.resets == []
    for _, body in client.patches:
        assert "message_buffer_autoclear" not in body


@pytest.mark.asyncio
async def test_reconcile_does_not_re_clear_a_settled_agent():
    """ensure_fleet runs many times per document job. A reset leaves exactly one
    message behind (measured live, 41 -> 1 on the worst agent), so an
    autoclearing agent settles at 1 and must not be reset again and again."""
    client = _ConfigClient()
    agent = {"id": "a", "llm_config": {"context_window": 128000, "max_tokens": 16384},
             "message_buffer_autoclear": True, "message_ids": ["only-one"]}
    ag = {"name": "gf_qa_auditor", "autoclear": True}
    assert await fleet._reconcile_config(client, agent, ag, load_fleet(), "gf_qa_auditor") is False
    assert client.resets == []
    assert client.patches == []
