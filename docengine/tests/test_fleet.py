# Fleet unit surface: model-handle resolution is pure and worth pinning
# (the create/attach/delete round-trips are exercised on the wwf_mass stack,
# same convention as test_pipeline.py).
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fleet import (  # noqa: E402
    TOOL_NAME,
    _resolve_model,
    _scope_block,
    agent_datasets,
    load_fleet,
    load_tool_source,
)


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
    block = _scope_block(["DB1_REGULATORY", "eCOA_INGEST"], ["DB1_REGULATORY"])
    assert "NOT YET INGESTED (DB1_REGULATORY)" in block
    assert "WITHOUT corpus" in block
    # the granted-and-present dataset is still named as searchable
    assert "eCOA_INGEST" in block


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


def test_context_window_and_max_tokens_are_declared_and_sane():
    """Letta sizes an unknown model from its DEFAULT of 30000, which truncated a
    real 9-section repair mid-reply. Both are declared so the model gets what it
    can actually take."""
    d = load_fleet()["defaults"]
    assert d["context_window"] >= 100_000
    assert d["max_tokens"] >= 8_000
    assert d["max_tokens"] < d["context_window"]
