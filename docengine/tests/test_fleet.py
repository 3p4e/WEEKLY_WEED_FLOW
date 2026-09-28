# Fleet unit surface: model-handle resolution is pure and worth pinning
# (the create/attach/delete round-trips are exercised on the wwf_mass stack,
# same convention as test_pipeline.py).
import ast
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import fleet  # noqa: E402
from app.letta import LettaError  # noqa: E402
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
    assert "DB01_REG" in agent_datasets("gf_reg_checker")


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
    assert "eCOA_DB" in agent_datasets("gf_app_assistant")


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
    documents. `persona` stays writable for a conversational agent (Letta
    owns that block) — but NOT for a verbatim author: its reply is spliced
    straight into a controlled document, so a persona it could be talked
    into rewriting would steer every later section with no human stop
    (review 2026-09-27, DI-14)."""
    spec = load_fleet()
    for ag in spec["agents"]:
        for block in fleet._blocks_for(ag, spec):
            if block["label"] == fleet.PERSONA_BLOCK:
                expected = bool(ag.get("verbatim_output"))
            else:
                expected = True
            assert block["read_only"] is expected, (ag["name"], block["label"])
    assert fleet.PERSONA_BLOCK not in fleet.GOVERNANCE_BLOCKS
    verbatim = {a["name"] for a in spec["agents"] if a.get("verbatim_output")}
    assert verbatim == {"gf_sop_author", "gf_annex_author", "gf_raci_specialist"}


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
    """_qa_audit_passed accepts exactly ONE line that is nothing but the
    verdict, and fails a PASS verdict that has a FIX token anywhere else.
    The persona has to describe THAT parser, not a looser one: 'Verdict:
    PASS, no fixes needed' fails because the line carries extra text, and the
    persona must say so for that reason (the earlier text blamed 'both
    tokens', which was not what the code checked — review 2026-09-27, DI-15).
    """
    persona = next(a for a in load_fleet()["agents"] if a["name"] == "gf_qa_auditor")["persona"]
    assert "Verdict: PASS" in persona
    assert "Nothing else on that line" in persona
    assert "NOT a verdict line and FAILS the document" in persona
    assert "NEVER write the token FIX anywhere in a passing reply" in persona


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


# ── Serialisation: agent locks + cached ensure pass (DI-08) ─────────────────


@pytest.fixture
def _clean_fleet_cache():
    fleet.invalidate_fleet_cache()
    yield
    fleet.invalidate_fleet_cache()


def test_agent_lock_is_one_lock_per_persistent_agent():
    assert fleet.agent_lock("gf_qa_auditor") is fleet.agent_lock("gf_qa_auditor")
    assert fleet.agent_lock("gf_qa_auditor") is not fleet.agent_lock("gf_sop_author")


@pytest.mark.asyncio
async def test_ensure_fleet_ctx_reuses_a_recent_pass_and_force_repeats_it(monkeypatch, _clean_fleet_cache):
    """Every job and every chat question used to run the full reconcile —
    and a reconcile can reset a persistent agent's buffer under another
    job's turn. A pass younger than FLEET_CACHE_S is reused instead."""
    passes = []

    async def fake_pass(client):
        passes.append(client)
        return fleet.FleetContext({"gf_x": "a-1"}, [], "m", "e", "tool-1", [], fleet.FleetReport())
    monkeypatch.setattr(fleet, "_ensure_fleet_pass", fake_pass)

    assert fleet.fleet_ctx_cached() is None
    first = await fleet.ensure_fleet_ctx(object())
    second = await fleet.ensure_fleet_ctx(object())
    assert first is second and len(passes) == 1
    assert fleet.fleet_ctx_cached() is first
    third = await fleet.ensure_fleet_ctx(object(), force=True)
    assert third is not first and len(passes) == 2
    fleet.invalidate_fleet_cache()
    assert fleet.fleet_ctx_cached() is None
    await fleet.ensure_fleet_ctx(object())
    assert len(passes) == 3


@pytest.mark.asyncio
async def test_a_cached_pass_expires_after_the_window(monkeypatch, _clean_fleet_cache):
    async def fake_pass(client):
        return fleet.FleetContext({}, [], "m", "e", "t", [], fleet.FleetReport())
    monkeypatch.setattr(fleet, "_ensure_fleet_pass", fake_pass)
    await fleet.ensure_fleet_ctx(object())
    assert fleet.fleet_ctx_cached() is not None
    monkeypatch.setattr(fleet, "FLEET_CACHE_S", 0)
    assert fleet.fleet_ctx_cached() is None


@pytest.mark.asyncio
async def test_concurrent_callers_share_one_pass(monkeypatch, _clean_fleet_cache):
    """Two jobs starting at once run ONE reconcile, not two interleaved."""
    started = asyncio.Event()
    release = asyncio.Event()
    passes = []

    async def slow_pass(client):
        passes.append(1)
        started.set()
        await release.wait()
        return fleet.FleetContext({}, [], "m", "e", "t", [], fleet.FleetReport())
    monkeypatch.setattr(fleet, "_ensure_fleet_pass", slow_pass)
    a = asyncio.create_task(fleet.ensure_fleet_ctx(object()))
    await started.wait()
    b = asyncio.create_task(fleet.ensure_fleet_ctx(object()))
    await asyncio.sleep(0)
    release.set()
    ra, rb = await asyncio.gather(a, b)
    assert ra is rb and passes == [1]


@pytest.mark.asyncio
async def test_reconcile_config_waits_for_the_agents_turn_before_resetting_its_buffer():
    """The race the review found: job B mid-turn on gf_qa_auditor, job A's
    reconcile sees a stale buffer and resets it under B. The reconciler now
    takes the agent's lock — the same lock the pipeline holds around every
    send to a persistent agent — so the reset waits for B's turn to end."""
    spec = load_fleet()
    client = _ConfigClient()
    agent = {"id": "agent-1", "message_buffer_autoclear": True,
             "message_ids": ["m1", "m2", "m3"],
             "llm_config": {"context_window": spec["defaults"]["context_window"],
                            "max_tokens": spec["defaults"]["max_tokens"]}}
    ag = {"name": "gf_qa_auditor", "autoclear": True}
    lock = fleet.agent_lock("gf_qa_auditor")
    await lock.acquire()                      # "job B" is mid-turn
    task = asyncio.create_task(
        fleet._reconcile_config(client, agent, ag, spec, "gf_qa_auditor"))
    for _ in range(5):
        await asyncio.sleep(0)
    assert client.resets == []                # nothing reset under B
    assert not task.done()
    lock.release()                            # B's turn ends
    assert await task is True
    assert client.resets == ["agent-1"]


@pytest.mark.asyncio
async def test_the_pipeline_sends_to_a_persistent_author_under_its_lock(monkeypatch):
    """With the author's lock held by someone else, the section draft waits;
    once released, the job proceeds. No second job can share an author's
    turn."""
    from app import builder, db, pipeline

    updates = []

    async def fake_job_get(jid):
        return {"id": "job-1", "payload": {"questionnaire": "annex_form", "answers": {},
                                          "meta": {"title_mk": "МК", "title_en": "EN", "code": "C-1"}}}

    async def fake_job_update(jid, **fields):
        updates.append(fields)

    async def fake_document_create(job_id, meta):
        return "doc-1"

    agents = {a["name"]: f"agent-{a['name']}" for a in load_fleet()["agents"]}

    async def fake_ctx(client):
        return fleet.FleetContext(agents, [], "m", "e", "tool-1", [], fleet.FleetReport())

    async def fake_spawn(client, agent_name, name_suffix, ctx=None, autoclear=None):
        return "tmp-1"
    monkeypatch.setattr(db, "job_get", fake_job_get)
    monkeypatch.setattr(db, "job_update", fake_job_update)
    monkeypatch.setattr(db, "document_create", fake_document_create)
    monkeypatch.setattr(fleet, "ensure_fleet_ctx", fake_ctx)
    monkeypatch.setattr(fleet, "spawn_ephemeral", fake_spawn)
    monkeypatch.setattr(builder, "build", lambda *a, **k: builder.BuildResult(
        path=Path("/tmp/x.docx"), bytes=1, verify_report="RESULT: PASS", doctype="FORM"))

    sent = []

    class Client:
        async def send_message_full(self, agent_id, prompt):
            sent.append(agent_id)
            text = "Verdict: PASS" if "§6A" in prompt else \
                "# Образец|Form\n[[FORM:grid]]\nДатум~~Date|||\n[[/FORM]]\nТекст со букви.|Text with letters."
            return {"text": text, "tool_calls": [], "tool_returns": []}

        async def send_message(self, agent_id, prompt):
            return "NO-FINDING"

        async def delete_agent(self, agent_id):
            pass

        async def aclose(self):
            pass

    lock = fleet.agent_lock(pipeline.ANNEX_AUTHOR)
    await lock.acquire()
    task = asyncio.create_task(pipeline.run_workflow("job-1", client=Client()))
    for _ in range(10):
        await asyncio.sleep(0)
    assert sent == []                         # the author's turn is someone else's
    lock.release()
    await task
    assert sent[0] == agents[pipeline.ANNEX_AUTHOR]
    assert updates[-1]["status"] == "done"
    assert not lock.locked()                  # released after the turn


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

    async def get_agent(self, agent_id: str) -> dict:
        # The churn guard re-reads after a push. This stub is a server that
        # honours what it was sent.
        d = load_fleet()["defaults"]
        return {"id": agent_id, "name": "gf_x",
                "llm_config": {"context_window": d["context_window"], "max_tokens": d["max_tokens"]}}


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
    # Granted but not yet ingested: this test is about what an unresolvable
    # name DISCLOSES, so the caller has to clear the allowlist to reach it.
    monkeypatch.setenv("RAGFLOW_ALLOWED_DATASETS", "DB1_REGULATORY,DB3_PP_CURRENT_unified")
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


@pytest.mark.asyncio
async def test_ensure_tool_adopts_rather_than_rewrites_when_source_code_is_absent():
    """This server's tool listing does return source_code, so this is latent.
    But `(None or "").strip() != source.strip()` is ALWAYS true, so a Letta
    that dropped the field would rewrite the tool on every document job — a
    silent write loop whose only symptom is churn nobody is looking for."""
    client = _ToolClient({"id": "tool-1", "name": TOOL_NAME})  # no source_code key
    assert await fleet.ensure_tool(client) == "tool-1"
    assert client.updates == []
    assert client.creates == []


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


def test_tool_refuses_to_search_at_all_when_no_allowlist_is_set(monkeypatch):
    """FAIL CLOSED. `if allowed:` meant an unset or empty
    RAGFLOW_ALLOWED_DATASETS disabled enforcement entirely and the agent
    reached every dataset in the tenant — the exact bypass the variable exists
    to prevent, arriving silently and looking like an ordinary success.

    Nothing can produce that state today (both write paths in fleet.py gate on
    a non-empty `ag["datasets"]`), which is why it is worth closing now, while
    it is still unreachable rather than after a fourth caller forgets."""
    monkeypatch.setenv("RAGFLOW_BASE_URL", "http://ragflow.invalid")
    monkeypatch.setenv("RAGFLOW_API_KEY", "k")
    monkeypatch.delenv("RAGFLOW_ALLOWED_DATASETS", raising=False)
    # No urlopen stub on purpose: reaching the network would blow up the test
    # rather than quietly pass it.
    out = json.loads(_load_tool_callable()("stability at 9 months", "STABILITY_PROGRAMME"))
    assert out["ok"] is False
    assert "RAGFLOW_ALLOWED_DATASETS is not set" in out["err"]
    # and it must not hand back a scope it does not have
    assert "your_scope" not in out


def test_tool_refuses_to_search_when_the_allowlist_is_present_but_empty(monkeypatch):
    monkeypatch.setenv("RAGFLOW_BASE_URL", "http://ragflow.invalid")
    monkeypatch.setenv("RAGFLOW_API_KEY", "k")
    monkeypatch.setenv("RAGFLOW_ALLOWED_DATASETS", "  ,  ")
    out = json.loads(_load_tool_callable()("anything", "eCoA_DATABASE"))
    assert out["ok"] is False
    assert "RAGFLOW_ALLOWED_DATASETS is not set" in out["err"]


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
async def test_reconcile_tool_env_leaves_a_foreign_only_env_alone(monkeypatch):
    """A datasetless agent carrying ONLY someone else's variables is not this
    module's business — gf_doc_orchestrator holds secrets for a different tool.
    No RAGflow key present, nothing to revoke, no PATCH."""
    client = _EnvClient()
    agent = {"id": "a", "tool_exec_environment_variables": [{"key": "KVM4_RUNNER_URL", "value": "x"}]}
    assert await fleet._reconcile_tool_env(client, agent, {"name": "gf_x"}, "gf_x") is False
    assert client.patches == []


@pytest.mark.asyncio
async def test_revoking_datasets_strips_the_credentials_and_keeps_foreign_keys(monkeypatch):
    """The gap the loop had: remove `datasets:` from an agent and its scope
    block said "you have no corpus" while RAGFLOW_ALLOWED_DATASETS, the base
    URL and the tenant key all stayed in its sandbox. Narrowing a list
    reconciled; revoking it did not."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    client = _EnvClient()
    env = _live_env("eCoA_DATABASE") + [{"key": "OTHER_TOOL_TOKEN", "value": "keep"}]
    agent = {"id": "a", "tool_exec_environment_variables": env}
    assert await fleet._reconcile_tool_env(client, agent, {"name": "gf_x"}, "gf_x") is True
    body = client.patches[0][1]["tool_exec_environment_variables"]
    assert body == {"OTHER_TOOL_TOKEN": "keep"}
    for k in fleet.OWNED_ENV:
        assert k not in body


@pytest.mark.asyncio
async def test_an_unknown_custom_tool_revokes_the_credentials_even_with_datasets(monkeypatch):
    """The key is per-agent, the allowlist is per-one-tool. An agent that has
    picked up a custom tool fleet.yaml did not declare must not hold the key."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    client = _EnvClient()
    agent = {"id": "a", "tool_exec_environment_variables": _live_env("eCoA_DATABASE")}
    ag = {"name": "gf_x", "datasets": ["eCoA_DATABASE"]}
    assert await fleet._reconcile_tool_env(client, agent, ag, "gf_x", revoke=True) is True
    assert client.patches[0][1]["tool_exec_environment_variables"] == {}


@pytest.mark.asyncio
async def test_a_failed_tool_env_push_raises_instead_of_running_on(monkeypatch):
    """The old handler continued on the grounds that "the memory-block scope
    still applies" — a block the same file describes as asking, and asking was
    all it was. An allowlist that could not be brought to the declaration may
    be wider than it; that is not a state to run a job on."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)

    class _Failing(_EnvClient):
        async def update_agent_config(self, agent_id, body):
            raise LettaError("nope", status=500)

    agent = {"id": "a", "tool_exec_environment_variables": _live_env("eCoA_DATABASE", key="old")}
    with pytest.raises(LettaError):
        await fleet._reconcile_tool_env(_Failing(), agent, {"name": "gf_x", "datasets": ["eCoA_DATABASE"]}, "gf_x")


def _live_env(scope: str, key: str = "k", base: str = "http://r") -> list[dict]:
    """The shape Letta actually returns: all three values echoed back."""
    return [
        {"key": "RAGFLOW_BASE_URL", "value": base},
        {"key": "RAGFLOW_API_KEY", "value": key},
        {"key": "RAGFLOW_ALLOWED_DATASETS", "value": scope},
    ]


@pytest.mark.asyncio
async def test_reconcile_tool_env_is_a_no_op_once_the_whole_env_matches(monkeypatch):
    """ensure_fleet runs on every document job, so an agent that already has
    the right environment must not be PATCHed again."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    client = _EnvClient()
    agent = {"id": "a", "tool_exec_environment_variables": _live_env("eCoA_DATABASE")}
    ag = {"name": "gf_x", "datasets": ["eCoA_DATABASE"]}
    assert await fleet._reconcile_tool_env(client, agent, ag, "gf_x") is False
    assert client.patches == []


@pytest.mark.asyncio
async def test_reconcile_tool_env_pushes_a_rotated_credential(monkeypatch):
    """This short-circuited on RAGFLOW_ALLOWED_DATASETS alone, so a rotated
    RAGFLOW_API_KEY reached no agent whose dataset list was unchanged — i.e.
    every agent — and retrieval would fail with no reconcile ever trying."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "rotated-key", raising=False)
    client = _EnvClient()
    agent = {"id": "a", "tool_exec_environment_variables": _live_env("eCoA_DATABASE", key="old-key")}
    ag = {"name": "gf_x", "datasets": ["eCoA_DATABASE"]}
    assert await fleet._reconcile_tool_env(client, agent, ag, "gf_x") is True
    body = client.patches[0][1]["tool_exec_environment_variables"]
    assert body["RAGFLOW_API_KEY"] == "rotated-key"
    # and the scope it was already carrying survives the push
    assert body["RAGFLOW_ALLOWED_DATASETS"] == "eCoA_DATABASE"


@pytest.mark.asyncio
async def test_reconcile_tool_env_pushes_a_moved_base_url(monkeypatch):
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://moved", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    client = _EnvClient()
    agent = {"id": "a", "tool_exec_environment_variables": _live_env("eCoA_DATABASE")}
    ag = {"name": "gf_x", "datasets": ["eCoA_DATABASE"]}
    assert await fleet._reconcile_tool_env(client, agent, ag, "gf_x") is True
    assert client.patches[0][1]["tool_exec_environment_variables"]["RAGFLOW_BASE_URL"] == "http://moved"


@pytest.mark.asyncio
async def test_reconcile_tool_env_keeps_variables_this_module_does_not_own(monkeypatch):
    """A PATCH replaces the whole set. The docstring's reason for leaving a
    datasetless agent alone applies just as much to an agent that has datasets
    AND something else — pushing only the three RAGflow keys would delete it."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "rotated", raising=False)
    client = _EnvClient()
    env = _live_env("eCoA_DATABASE", key="old")
    env.append({"key": "SOME_OTHER_TOOL_TOKEN", "value": "keep-me"})
    agent = {"id": "a", "tool_exec_environment_variables": env}
    ag = {"name": "gf_x", "datasets": ["eCoA_DATABASE"]}
    assert await fleet._reconcile_tool_env(client, agent, ag, "gf_x") is True
    body = client.patches[0][1]["tool_exec_environment_variables"]
    assert body["SOME_OTHER_TOOL_TOKEN"] == "keep-me"
    assert body["RAGFLOW_API_KEY"] == "rotated"


@pytest.mark.asyncio
async def test_reconcile_tool_env_ignores_a_foreign_variable_when_deciding(monkeypatch):
    """An unrelated variable is not this module's business, so its presence
    must not trigger a PATCH on every document job."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    client = _EnvClient()
    env = _live_env("eCoA_DATABASE")
    env.append({"key": "SOME_OTHER_TOOL_TOKEN", "value": "x"})
    agent = {"id": "a", "tool_exec_environment_variables": env}
    ag = {"name": "gf_x", "datasets": ["eCoA_DATABASE"]}
    assert await fleet._reconcile_tool_env(client, agent, ag, "gf_x") is False
    assert client.patches == []


@pytest.mark.asyncio
async def test_reconcile_tool_env_does_not_churn_when_a_value_is_withheld(monkeypatch):
    """This Letta echoes every value back, but a stricter server might blank
    the secret. A withheld value must not read as a mismatch, or the whole set
    would be re-pushed on every single document job."""
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    client = _EnvClient()
    env = _live_env("eCoA_DATABASE")
    env[1]["value"] = ""  # server declines to show RAGFLOW_API_KEY
    agent = {"id": "a", "tool_exec_environment_variables": env}
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


def test_the_conversational_agent_keeps_its_history():
    """Clearing this would break the thing it exists to do — gf_app_assistant
    holds a real back-and-forth with staff."""
    by_name = {a["name"]: a for a in load_fleet()["agents"]}
    assert by_name["gf_app_assistant"].get("autoclear") is False


def test_only_agents_something_drives_are_declared():
    """Review 2026-09-27, DI2-15. gf_doc_orchestrator and gf_translator_mk_en
    were created and reconciled on every pass (the translator holding the
    RAGflow key) while their own personas said the pipeline never called
    them. fleet.yaml declares the agents pipeline.py drives plus the one
    staff assistant, and nothing else; the drift report lists a removed
    agent as "live on the server, not declared" until an operator deletes it."""
    from app.pipeline import DRIVEN_AGENTS
    declared = {a["name"] for a in load_fleet()["agents"]}
    assert declared == set(DRIVEN_AGENTS) | {"gf_app_assistant"}, declared


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


# ── verbatim_output: whose reply BECOMES the document ───────────────────────
# The ungrounded branch of the scope block used to tell every agent to "say so
# plainly in your output". For three of them the output IS the document, so the
# instruction put a note about corpus availability inside a controlled document
# (seen in a direct probe: a section opening with a bilingual sentence about the
# facility corpus not being ingested). A blank field is how a document says a
# value is unknown.


def test_the_three_verbatim_authors_declare_it():
    """Exactly the agents whose reply pipeline.py inserts into the document."""
    by_name = {a["name"]: a for a in load_fleet()["agents"]}
    for name in ("gf_sop_author", "gf_annex_author", "gf_raci_specialist"):
        assert by_name[name].get("verbatim_output") is True, name


def test_reporting_and_conversational_agents_are_not_verbatim():
    """gf_reg_checker returns findings and gf_app_assistant talks to a person —
    both SHOULD say when a corpus is missing."""
    by_name = {a["name"]: a for a in load_fleet()["agents"]}
    for name in ("gf_reg_checker", "gf_app_assistant", "gf_qa_auditor"):
        assert not by_name[name].get("verbatim_output"), name


def test_ungrounded_verbatim_author_is_told_to_leave_blanks_not_to_narrate():
    block = _scope_block(["DB3_PP_CURRENT_unified"], ["DB3_PP_CURRENT_unified"], True)
    assert "BLANK write-in field" in block
    assert "The blank" in block
    assert "say so plainly" not in block


def test_ungrounded_reporter_still_says_so():
    """The original wording is right for anything that is not document text."""
    block = _scope_block(["DB1_REGULATORY"], ["DB1_REGULATORY"], False)
    assert "say so plainly" in block   # wraps across lines in the block


def test_the_verbatim_flag_reaches_the_generated_scope_block():
    """_blocks_for is what the reconciler diffs against the live agent, so the
    flag has to survive the trip from fleet.yaml into the block value."""
    spec = load_fleet()
    by_name = {a["name"]: a for a in spec["agents"]}
    author = next(b for b in fleet._blocks_for(by_name["gf_sop_author"], spec)
                  if b["label"] == fleet.SCOPE_BLOCK)["value"]
    checker = next(b for b in fleet._blocks_for(by_name["gf_reg_checker"], spec)
                   if b["label"] == fleet.SCOPE_BLOCK)["value"]
    assert "BLANK write-in field" in author and "say so plainly" not in author
    assert "say so plainly" in checker


def test_the_corpus_guide_does_not_order_document_text_to_narrate():
    """The shared corpus block carried the same instruction and would have
    re-introduced it regardless of the scope block."""
    guide = load_fleet()["corpus_guide"]
    assert "never document text" in guide
    assert "blank write-in fields instead" in guide


def test_no_persona_still_references_the_host_exec_tool():
    """gf_doc_orchestrator's persona described how to use an unrestricted host
    shell. The tool is detached from the live agent; the file must not invite
    it back."""
    for ag in load_fleet()["agents"]:
        assert "kvm4_runner_exec" not in ag["persona"], ag["name"]


def test_the_auditor_is_told_to_raise_every_issue_at_once():
    """A real job died with the auditor's second-round issue unaddressed
    because the first round had not mentioned it."""
    persona = next(a for a in load_fleet()["agents"]
                   if a["name"] == "gf_qa_auditor")["persona"]
    assert "List EVERY issue you have, in that one verdict." in persona


def test_the_annex_author_is_taught_the_engine_s_actual_row_grammar():
    """It was told rows must share a column count and that short rows should be
    padded. Both are wrong against the engine, and the second is worse than
    wrong: padding rows out to a common width produces a UNIFORM block that
    loses cells 4+ of every row and looks consistent doing it. emit_form reads
    exactly three cells and never a fourth."""
    persona = next(a for a in load_fleet()["agents"]
                   if a["name"] == "gf_annex_author")["persona"]
    assert "ONE FIELD PER ROW" in persona
    assert "EXACTLY three cells" in persona
    assert "padded with empty cells" not in persona
    assert "same number of" not in persona


def test_the_house_rules_state_the_three_cell_form_row():
    """The shared block is what every author reads, so the grammar belongs
    there too and not only in one persona."""
    assert "exactly three cells" in load_fleet()["house_rules"]


# ── _reconcile_blocks ───────────────────────────────────────────────────────
# It rewrites the persona and four governance blocks on every live agent on
# every document job, and had no test at all — the largest behavioural change
# in this work, uncovered, while its two siblings each had half a dozen.


class _BlockClient:
    """Serves a fixed set of blocks and records what was written."""

    def __init__(self, existing: dict, missing_raises: Exception | None = None):
        self.existing = existing          # label -> {"value","read_only"}
        self.missing_raises = missing_raises
        self.updates: list[tuple] = []
        self.created: list[tuple] = []
        self.attached: list[tuple] = []

    async def get_block(self, agent_id, label):
        if label in self.existing:
            return dict(self.existing[label])
        if self.missing_raises:
            raise self.missing_raises
        return None

    async def update_block(self, agent_id, label, value=None, read_only=None):
        self.updates.append((label, value, read_only))

    async def create_block(self, label, value, read_only=False, limit=100_000):
        self.created.append((label, value, read_only))
        return {"id": "block-" + label}

    async def attach_block(self, agent_id, block_id):
        self.attached.append((agent_id, block_id))


def _agent_and_spec():
    spec = load_fleet()
    ag = next(a for a in spec["agents"] if a["name"] == "gf_sop_author")
    return ag, spec


@pytest.mark.asyncio
async def test_reconcile_blocks_is_silent_when_everything_already_matches():
    """ensure_fleet runs many times per job; a matching agent must cost no
    writes at all."""
    ag, spec = _agent_and_spec()
    want = {b["label"]: {"value": b["value"], "read_only": b["read_only"]}
            for b in fleet._blocks_for(ag, spec)}
    client = _BlockClient(want)
    assert await fleet._reconcile_blocks(client, "a", ag, spec, "gf_sop_author") == []
    assert client.updates == [] and client.created == []


@pytest.mark.asyncio
async def test_reconcile_blocks_rewrites_a_drifted_value():
    ag, spec = _agent_and_spec()
    want = {b["label"]: {"value": b["value"], "read_only": b["read_only"]}
            for b in fleet._blocks_for(ag, spec)}
    want["persona"]["value"] = "something an agent wrote over its own brief"
    client = _BlockClient(want)
    changed = await fleet._reconcile_blocks(client, "a", ag, spec, "gf_sop_author")
    assert changed == ["persona"]
    assert client.updates[0][0] == "persona"
    assert client.updates[0][1] == ag["persona"].strip()


@pytest.mark.asyncio
async def test_reconcile_blocks_repairs_a_read_only_flag_without_touching_the_value():
    """The flag is the guardrail — an agent that can edit its own scope is not
    scoped. Repairing it must not rewrite a value that is already correct."""
    ag, spec = _agent_and_spec()
    want = {b["label"]: {"value": b["value"], "read_only": b["read_only"]}
            for b in fleet._blocks_for(ag, spec)}
    want[fleet.SCOPE_BLOCK]["read_only"] = False
    client = _BlockClient(want)
    changed = await fleet._reconcile_blocks(client, "a", ag, spec, "gf_sop_author")
    assert changed == [fleet.SCOPE_BLOCK]
    label, value, read_only = client.updates[0]
    assert label == fleet.SCOPE_BLOCK and value is None and read_only is True


@pytest.mark.asyncio
async def test_reconcile_blocks_creates_and_attaches_a_block_the_agent_predates():
    """How gf_mission and gf_corpus reached eight agents that were created
    before either existed."""
    ag, spec = _agent_and_spec()
    want = {b["label"]: {"value": b["value"], "read_only": b["read_only"]}
            for b in fleet._blocks_for(ag, spec)}
    del want[fleet.MISSION_BLOCK]
    client = _BlockClient(want)
    changed = await fleet._reconcile_blocks(client, "a", ag, spec, "gf_sop_author")
    assert changed == [fleet.MISSION_BLOCK + " (added)"]
    assert client.created[0][0] == fleet.MISSION_BLOCK
    assert client.created[0][2] is True          # governance blocks are read-only
    assert client.attached == [("a", "block-" + fleet.MISSION_BLOCK)]


@pytest.mark.asyncio
async def test_a_transient_error_does_not_manufacture_a_duplicate_block():
    """get_block re-raises anything that is not a 404, and the per-block
    handler logs it — the agent is left alone rather than given a second block
    with the same label."""
    ag, spec = _agent_and_spec()
    client = _BlockClient({}, missing_raises=LettaError("boom", status=503))
    changed = await fleet._reconcile_blocks(client, "a", ag, spec, "gf_sop_author")
    assert changed == []
    assert client.created == [] and client.attached == []


# ── The loop converges now: it revokes, prunes and reports ───────────────────
# Every reconciler below used to be additive. Each test here fails on the
# code as it was before 2026-08-31.


def _tool(name: str, kind: str = "custom", tid: str | None = None) -> dict:
    return {"name": name, "tool_type": kind, "id": tid or f"tool-{name}"}


_BUILTINS = [_tool("memory_insert", "letta_sleeptime_core"),
             _tool("memory_replace", "letta_sleeptime_core"),
             _tool("conversation_search", "letta_core")]


def test_unknown_tools_ignores_lettas_own_core_tools_and_the_declared_ones():
    """The exact tool set observed on every live gf_ agent: three Letta
    built-ins plus (on retrievers) ragflow_search. None of those is unknown."""
    agent = {"tools": _BUILTINS + [_tool(TOOL_NAME)]}
    assert fleet._unknown_tools(agent, {"name": "gf_x", "datasets": ["d"]}) == []
    agent = {"tools": _BUILTINS + [_tool(TOOL_NAME), _tool("host_exec")]}
    assert fleet._unknown_tools(agent, {"name": "gf_x", "extra_tools": ["host_exec"]}) == []


def test_unknown_tools_names_a_custom_tool_fleet_yaml_did_not_declare():
    agent = {"tools": _BUILTINS + [_tool(TOOL_NAME), _tool("host_exec")]}
    assert fleet._unknown_tools(agent, {"name": "gf_x", "datasets": ["d"]}) == ["host_exec"]


class _AttachClient:
    def __init__(self):
        self.attached: list[tuple] = []
        self.detached: list[tuple] = []

    async def attach_tool(self, agent_id, tool_id):
        self.attached.append((agent_id, tool_id))

    async def detach_tool(self, agent_id, tool_id):
        self.detached.append((agent_id, tool_id))


@pytest.mark.asyncio
async def test_retrieval_tool_is_detached_from_an_agent_that_lost_its_datasets():
    """There was no detach at all — not in the reconciler, not in the client.
    An agent whose corpus was revoked kept the search button forever."""
    c = _AttachClient()
    have = {TOOL_NAME: "tool-live"}
    did = await fleet._reconcile_retrieval_tool(c, "a", {"name": "gf_x"}, "tool-1", have, "gf_x")
    assert did == "tool detached"
    assert c.detached == [("a", "tool-live")] and c.attached == []


@pytest.mark.asyncio
async def test_retrieval_tool_is_detached_when_an_unknown_tool_forces_revoke():
    c = _AttachClient()
    ag = {"name": "gf_x", "datasets": ["d"]}
    did = await fleet._reconcile_retrieval_tool(c, "a", ag, "tool-1", {TOOL_NAME: "t"}, "gf_x", revoke=True)
    assert did == "tool detached" and c.detached == [("a", "t")]


@pytest.mark.asyncio
async def test_retrieval_tool_attach_and_no_op_still_work():
    c = _AttachClient()
    ag = {"name": "gf_x", "datasets": ["d"]}
    assert await fleet._reconcile_retrieval_tool(c, "a", ag, "tool-1", {}, "gf_x") == "tool attached"
    assert c.attached == [("a", "tool-1")]
    assert await fleet._reconcile_retrieval_tool(c, "a", ag, "tool-1", {TOOL_NAME: "t"}, "gf_x") is None
    assert await fleet._reconcile_retrieval_tool(c, "a", {"name": "gf_y"}, "tool-1", {}, "gf_y") is None


@pytest.mark.asyncio
async def test_ensure_tool_raises_when_it_cannot_bring_the_tool_to_the_committed_source():
    """It used to return the id anyway, and every agent was then wired to an
    unverified server object with the tenant key in hand. The pre-hardening
    tool searched everything when `datasets` was omitted; a swallowed update
    failure rolled back to exactly that, with one warning line."""
    class _Refusing(_ToolClient):
        async def update_tool(self, tool_id, source_code, description=""):
            raise LettaError("forbidden", status=403)

    client = _Refusing({"id": "tool-1", "name": TOOL_NAME, "source_code": "def old(): pass"})
    with pytest.raises(LettaError):
        await fleet.ensure_tool(client)


@pytest.mark.asyncio
async def test_ensure_tool_raises_when_registration_fails():
    class _Refusing(_ToolClient):
        async def create_tool(self, source_code, description=""):
            raise LettaError("rejected", status=422)

    with pytest.raises(LettaError):
        await fleet.ensure_tool(_Refusing(None))


class _ProbingConfigClient(_ConfigClient):
    """Reports whatever llm_config the test says the server kept."""

    def __init__(self, kept: dict):
        super().__init__()
        self.kept = kept

    async def get_agent(self, agent_id):
        return {"id": agent_id, "name": "gf_x", "llm_config": self.kept}


@pytest.mark.asyncio
async def test_a_context_window_the_server_does_not_honour_is_pushed_once_then_reported(monkeypatch):
    """Read `context_window`, write `context_window_limit`. If the server
    normalises the value, the two never agree and the old code PATCHed on
    every document job forever with no symptom but churn — the same trap
    ensure_tool guards against for source_code."""
    monkeypatch.setattr(fleet, "_UNHONOURED", set())
    spec = load_fleet()
    want = spec["defaults"]["context_window"]
    client = _ProbingConfigClient({"context_window": 32000, "max_tokens": spec["defaults"]["max_tokens"]})
    agent = {"id": "agent-1", "llm_config": dict(client.kept), "message_buffer_autoclear": True}
    ag = {"name": "gf_x", "autoclear": True}
    report = fleet.FleetReport()
    assert await fleet._reconcile_config(client, agent, ag, spec, "gf_x", report) is True
    assert client.patches == [("agent-1", {"context_window_limit": want})]
    assert any("not re-pushing" in d for d in report.drift)
    # second pass, same agent, server still at 32000: no second PATCH
    assert await fleet._reconcile_config(client, agent, ag, spec, "gf_x", fleet.FleetReport()) is False
    assert len(client.patches) == 1


@pytest.mark.asyncio
async def test_model_handle_drift_is_reported_and_never_patched():
    """fleet.yaml's `model:` governed only from-scratch agents while being
    written, tested and read as a declaration. Still not patched — the server
    rejects that write — but no longer silent."""
    spec = load_fleet()
    client = _ConfigClient()
    agent = {"id": "a", "llm_config": {"context_window": spec["defaults"]["context_window"],
                                       "max_tokens": spec["defaults"]["max_tokens"],
                                       "handle": "some/other-model"},
             "message_buffer_autoclear": True}
    report = fleet.FleetReport()
    await fleet._reconcile_config(client, agent, {"name": "gf_x", "autoclear": True}, spec, "gf_x", report)
    assert client.patches == []
    assert any("some/other-model" in d and "not reconciled" in d for d in report.drift)


class _LeakyBlockClient(_BlockClient):
    def __init__(self, want):
        super().__init__(want)
        self.deleted: list[str] = []

    async def attach_block(self, agent_id, block_id):
        raise LettaError("attach failed", status=500)

    async def delete_block(self, block_id):
        self.deleted.append(block_id)


@pytest.mark.asyncio
async def test_a_block_whose_attach_fails_is_deleted_rather_than_leaked():
    """create-then-attach: a failure between the two leaked one unattached
    block per pass, and the next pass (no block under that label on the agent)
    created another. Unbounded on a flapping server."""
    ag, spec = _agent_and_spec()
    want = {b["label"]: {"value": b["value"], "read_only": b["read_only"]}
            for b in fleet._blocks_for(ag, spec)}
    del want[fleet.MISSION_BLOCK]
    client = _LeakyBlockClient(want)
    changed = await fleet._reconcile_blocks(client, "a", ag, spec, "gf_sop_author")
    assert changed == []
    assert client.deleted == ["block-" + fleet.MISSION_BLOCK]


class _SweepClient:
    def __init__(self):
        self.deleted: list[str] = []

    async def delete_agent(self, agent_id):
        self.deleted.append(agent_id)


@pytest.mark.asyncio
async def test_orphan_sweep_deletes_old_tmp_clones_and_keeps_young_ones_and_the_fleet(monkeypatch):
    """pipeline.py said "the next fleet audit sweeps _tmp_ leftovers"; nothing
    did, and an orphan kept the RAGflow key. Age-gated because a clone younger
    than a job's longest exchange may belong to the other worker."""
    from datetime import datetime, timedelta, timezone
    monkeypatch.setattr(fleet.settings, "letta_read_timeout", 100.0, raising=False)
    now = datetime.now(timezone.utc)
    old = (now - timedelta(seconds=1000)).isoformat()
    young = (now - timedelta(seconds=10)).isoformat()
    existing = [
        {"id": "1", "name": "gf_reg_checker_tmp_abc", "created_at": old},
        {"id": "2", "name": "gf_reg_checker_tmp_def", "created_at": young},
        {"id": "3", "name": "gf_reg_checker", "created_at": old},
        {"id": "4", "name": "planner_tmp_x", "created_at": old},   # not gf_: not ours
    ]
    c = _SweepClient()
    report = fleet.FleetReport()
    kept = await fleet._sweep_orphans(c, existing, report)
    assert c.deleted == ["1"]
    assert report.swept == ["gf_reg_checker_tmp_abc"]
    assert [a["id"] for a in kept] == ["2", "3", "4"]


@pytest.mark.asyncio
async def test_pending_is_what_ragflow_says_not_what_the_yaml_says(monkeypatch):
    """The test written after 2026-08-27 compared fleet.yaml to fleet.yaml and
    was green through the identical 2026-08-29 rename. Pending must come from
    the tenant: a dataset the YAML calls ingested but RAGflow does not have is
    pending, and one the YAML calls pending but RAGflow now has is not."""
    spec = load_fleet()
    yaml_pending = fleet.declared_pending(spec)
    assert "eCOA_DB" not in yaml_pending and "DB01_REG" in yaml_pending

    async def fake_live(*a, **k):
        return {"DB01_REG", "something_else"}   # eCOA_DB renamed away
    monkeypatch.setattr(fleet, "list_dataset_names", fake_live)
    report = fleet.FleetReport()
    pending = await fleet.resolve_pending(spec, report)
    assert "eCOA_DB" in pending
    assert "DB01_REG" not in pending
    assert report.datasets_unresolved == pending and report.datasets_live is not None
    # and it reaches the block the agent actually reads
    ag = next(a for a in spec["agents"] if a["name"] == "gf_app_assistant")
    scope = next(b for b in fleet._blocks_for(ag, spec, pending) if b["label"] == fleet.SCOPE_BLOCK)
    assert "eCOA_DB" in scope["value"] and "NOT YET INGESTED" in scope["value"]


@pytest.mark.asyncio
async def test_pending_falls_back_to_the_yaml_when_ragflow_is_unreachable(monkeypatch):
    from app.ragflow_api import RagflowUnreachable
    spec = load_fleet()

    async def down(*a, **k):
        raise RagflowUnreachable("connection refused")
    monkeypatch.setattr(fleet, "list_dataset_names", down)
    report = fleet.FleetReport()
    assert await fleet.resolve_pending(spec, report) == fleet.declared_pending(spec)
    assert report.datasets_live is None
    assert any("unreachable" in w for w in report.warnings)


def test_every_block_this_module_makes_carries_one_limit_and_derives_read_only():
    """The create path used to take Letta's default limit while the reconcile
    path set 100000, and read_only was written out per entry rather than
    derived — so GOVERNANCE_BLOCKS named an invariant nothing consulted."""
    ag, spec = _agent_and_spec()
    for b in fleet._blocks_for(ag, spec):
        assert b["limit"] == fleet.BLOCK_LIMIT
        expected = (b["label"] in fleet.GOVERNANCE_BLOCKS
                    or (b["label"] == fleet.PERSONA_BLOCK and bool(ag.get("verbatim_output"))))
        assert b["read_only"] == expected


@pytest.mark.asyncio
async def test_spawn_ephemeral_with_a_context_lists_nothing(monkeypatch):
    """Per section it re-listed agents, models, embeddings and tools — ~54
    round-trips on a nine-section SOP for data the same job had just fetched."""
    calls: list[str] = []

    class _C:
        async def list_agents(self):
            calls.append("list_agents"); return []
        async def list_models(self):
            calls.append("list_models"); return []
        async def list_embedding_models(self):
            calls.append("list_embedding_models"); return []
        async def list_tools(self):
            calls.append("list_tools"); return []
        async def create_agent(self, body):
            calls.append("create"); return {"id": "tmp-1", "name": body["name"], "tools": []}
        async def attach_tool(self, agent_id, tool_id):
            calls.append("attach")

    spec = load_fleet()
    base = {"name": "gf_reg_checker", "llm_config": {"handle": "p/m"}, "embedding_config": {"handle": "p/e"}}
    ctx = fleet.FleetContext({}, [base], "p/m", "p/e", "tool-1", [], fleet.FleetReport())
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)
    tid = await fleet.spawn_ephemeral(_C(), "gf_reg_checker", "x", ctx=ctx)
    assert tid == "tmp-1"
    assert calls == ["create", "attach"]


@pytest.mark.asyncio
async def test_spawn_ephemeral_autoclear_override_lets_a_clone_take_a_second_turn(monkeypatch):
    """gf_reg_checker declares autoclear: true for its normal one-shot use.
    A caller that will send this clone a SECOND turn (a repair's nudge) needs
    the first turn still in the buffer when the second is composed — autoclear
    left on wipes it in between, and the second turn runs with no memory of
    the first (observed live: a repair nudge ran at 5.8k tokens right after a
    34k-token first turn, and returned nothing). spawn_ephemeral(autoclear=False)
    must override the base agent's own flag for this one clone."""
    bodies: list[dict] = []

    class _C:
        async def list_agents(self):
            return []
        async def list_models(self):
            return []
        async def list_embedding_models(self):
            return []
        async def list_tools(self):
            return []
        async def create_agent(self, body):
            bodies.append(body)
            return {"id": "tmp-1", "name": body["name"], "tools": []}
        async def attach_tool(self, agent_id, tool_id):
            pass

    spec = load_fleet()
    ag = next(a for a in spec["agents"] if a["name"] == "gf_reg_checker")
    assert ag.get("autoclear") is True  # the premise: the base agent IS autoclear:true
    base = {"name": "gf_reg_checker", "llm_config": {"handle": "p/m"}, "embedding_config": {"handle": "p/e"}}
    ctx = fleet.FleetContext({}, [base], "p/m", "p/e", "tool-1", [], fleet.FleetReport())
    monkeypatch.setattr(fleet.settings, "ragflow_base", "http://r", raising=False)
    monkeypatch.setattr(fleet.settings, "ragflow_key", "k", raising=False)

    await fleet.spawn_ephemeral(_C(), "gf_reg_checker", "x", ctx=ctx, autoclear=False)
    assert bodies[-1]["message_buffer_autoclear"] is False

    bodies.clear()
    await fleet.spawn_ephemeral(_C(), "gf_reg_checker", "y", ctx=ctx)
    assert bodies[-1]["message_buffer_autoclear"] is True  # unchanged when no override is given


def test_fleet_yaml_flags_match_how_the_pipeline_actually_drives_each_agent():
    """`verbatim_output` and `autoclear` are properties of how pipeline.py USES
    an agent, declared in a file that cannot see the pipeline. The earlier
    tests restated today's answer by name; this derives it from the pipeline's
    own declaration, so a new verbatim author or one-shot worker wired in
    without the matching flag fails here instead of in a controlled document."""
    from app.pipeline import DRIVEN_AGENTS
    by_name = {a["name"]: a for a in load_fleet()["agents"]}
    for name, how in DRIVEN_AGENTS.items():
        assert name in by_name, f"pipeline drives {name}, fleet.yaml does not declare it"
        ag = by_name[name]
        assert bool(ag.get("verbatim_output")) == how["verbatim"], name
        assert bool(ag.get("autoclear")) == how["one_shot"], name
    # and the reverse for the output contract: a verbatim agent nobody drives
    # verbatim is a flag with no reader
    for name, ag in by_name.items():
        if ag.get("verbatim_output"):
            assert DRIVEN_AGENTS.get(name, {}).get("verbatim"), name


def test_the_tool_paginates_past_the_first_hundred_datasets(monkeypatch):
    """Page 1 only: on a tenant past 100 datasets a granted corpus resolved as
    "not ingested" — fail-closed, silent, permanent."""
    pages = {1: [{"name": f"ds{i}", "id": str(i)} for i in range(100)],
             2: [{"name": "eCoA_DATABASE", "id": "target"}]}
    seen: list[int] = []

    class _Resp:
        def __init__(self, payload):
            self.payload = payload
        def read(self):
            return json.dumps(self.payload).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        url = req.full_url
        if "/datasets" in url:
            page = int(url.split("page=")[1].split("&")[0])
            seen.append(page)
            return _Resp({"data": pages.get(page, [])})
        return _Resp({"data": {"chunks": []}})

    monkeypatch.setenv("RAGFLOW_BASE_URL", "http://ragflow.invalid")
    monkeypatch.setenv("RAGFLOW_API_KEY", "k")
    monkeypatch.setenv("RAGFLOW_ALLOWED_DATASETS", "eCoA_DATABASE")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = json.loads(_load_tool_callable()("q", "eCoA_DATABASE"))
    assert seen == [1, 2]
    assert out["ok"] is True and out["searched"] == ["eCoA_DATABASE"]


# ── read-only context for chat (DI2-09) and locks around every write (DI2-10) ─


class _ListingOnlyClient:
    """A Letta that can be LISTED and nothing else: any write is an
    AttributeError, which is the point — read_only_ctx must never need one."""

    def __init__(self, agents, tools):
        self._agents, self._tools = agents, tools

    async def list_agents(self, name=None):
        return list(self._agents)

    async def list_tools(self):
        return list(self._tools)

    async def list_models(self):
        return []

    async def list_embedding_models(self):
        return []


def _live_fleet(spec):
    return [{"id": f"id-{a['name']}", "name": a["name"], "tools": [],
             "llm_config": {"handle": spec["defaults"]["model"]},
             "embedding_config": {"handle": spec["defaults"]["embedding"]}}
            for a in spec["agents"]]


@pytest.mark.asyncio
async def test_read_only_ctx_resolves_from_listings_and_writes_nothing():
    spec = load_fleet()
    live = _live_fleet(spec) + [{"id": "tmp-1", "name": "gf_sop_author_tmp_chat_x", "tools": []}]
    ctx = await fleet.read_only_ctx(_ListingOnlyClient(live, [{"id": "tool-9", "name": fleet.TOOL_NAME}]))
    assert ctx.tool_id == "tool-9"
    assert ctx.agents == {a["name"]: f"id-{a['name']}" for a in spec["agents"]}
    assert "gf_sop_author_tmp_chat_x" not in ctx.agents
    assert ctx.existing == live
    assert ctx.model and ctx.embedding


@pytest.mark.asyncio
async def test_read_only_ctx_refuses_rather_than_creates_what_is_missing():
    spec = load_fleet()
    with pytest.raises(fleet.FleetNotReady, match="ragflow_search is not registered"):
        await fleet.read_only_ctx(_ListingOnlyClient(_live_fleet(spec), []))
    with pytest.raises(fleet.FleetNotReady, match="gf_qa_auditor"):
        live = [a for a in _live_fleet(spec) if a["name"] != "gf_qa_auditor"]
        await fleet.read_only_ctx(_ListingOnlyClient(live, [{"id": "t", "name": fleet.TOOL_NAME}]))


@pytest.mark.asyncio
async def test_the_ensure_pass_reconciles_every_write_under_the_agents_lock(monkeypatch):
    """Review 2026-09-27, DI2-10. Only the config reconciler took the agent's
    lock; a block rewrite or a sandbox-environment PATCH could land under a
    tool call a job had in flight on that agent. All four reconcilers now
    run inside agent_lock(name) in the ensure pass."""
    spec = load_fleet()
    live = _live_fleet(spec)
    held: dict[str, list[str]] = {}

    def saw(what):
        def _rec(label):
            held.setdefault(label, []).append(what if fleet.agent_lock(label).locked() else f"{what}:UNLOCKED")
        return _rec

    async def fake_tool(client, agent_id, ag, tool_id, have, label, revoke=False):
        saw("tool")(label)
        return None

    async def fake_blocks(client, agent_id, ag, spec, label, pending=None, report=None):
        saw("blocks")(label)
        return []

    async def fake_env(client, agent, ag, label, revoke=False):
        saw("env")(label)
        return False

    async def fake_config(client, agent, ag, spec, label, report=None, locked=False):
        saw("config")(label)
        assert locked is True, "the pass holds the lock; a re-take would deadlock"
        return False

    async def fake_sweep(client, existing, report):
        return existing

    async def fake_served(client):
        return None, None

    async def fake_tool_id(client, spec=None):
        return "tool-1"

    async def fake_pending(spec, report=None):
        return []
    monkeypatch.setattr(fleet, "_reconcile_retrieval_tool", fake_tool)
    monkeypatch.setattr(fleet, "_reconcile_blocks", fake_blocks)
    monkeypatch.setattr(fleet, "_reconcile_tool_env", fake_env)
    monkeypatch.setattr(fleet, "_reconcile_config", fake_config)
    monkeypatch.setattr(fleet, "_sweep_orphans", fake_sweep)
    monkeypatch.setattr(fleet, "_served_handles", fake_served)
    monkeypatch.setattr(fleet, "ensure_tool", fake_tool_id)
    monkeypatch.setattr(fleet, "resolve_pending", fake_pending)

    ctx = await fleet._ensure_fleet_pass(_ListingOnlyClient(live, [{"id": "tool-1", "name": fleet.TOOL_NAME}]))
    assert set(ctx.agents) == {a["name"] for a in spec["agents"]}
    for name in ctx.agents:
        assert held[name] == ["tool", "blocks", "env", "config"], (name, held[name])
    # and the pass released every lock
    assert not any(fleet.agent_lock(n).locked() for n in ctx.agents)
