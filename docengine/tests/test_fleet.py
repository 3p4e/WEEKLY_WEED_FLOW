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
