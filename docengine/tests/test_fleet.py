# Fleet unit surface: model-handle resolution is pure and worth pinning
# (the create/attach/delete round-trips are exercised on the wwf_mass stack,
# same convention as test_pipeline.py).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fleet import _resolve_model, _scope_block, agent_datasets, load_fleet  # noqa: E402


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
