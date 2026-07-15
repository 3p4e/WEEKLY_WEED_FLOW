"""Tests for the Letta SOP workflow orchestrator.

Exercises the pure logic (gap detection, passage enrichment, prompt
builders) and the execute() orchestration loop against a fake
LettaService — no Letta server or letta_client SDK required.
"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# letta_service imports the letta_client SDK at module level; stub it when
# absent so the workflow module (which never touches the SDK directly in
# these tests) can be imported without it.
if "letta_client" not in sys.modules:
    try:
        import letta_client  # noqa: F401
    except ImportError:
        stub = types.ModuleType("letta_client")
        stub.Letta = object
        sys.modules["letta_client"] = stub

import CONTENT_CREATOR_FRAMEWORK.letta_workflow as lw
from CONTENT_CREATOR_FRAMEWORK.agent_definitions import SECTION_ORDER
from CONTENT_CREATOR_FRAMEWORK.letta_workflow import LettaSOPWorkflow


class FakeLetta:
    """Stand-in for LettaService that records calls and returns canned text."""

    def __init__(self, responses=None, fail_roles=(), empty_roles=(),
                 external_responses=None, db_results=None):
        self.responses = responses or {}
        self.fail_roles = set(fail_roles)
        self.empty_roles = set(empty_roles)
        self.messages = []  # (role, prompt) pairs
        self.context_updates = []  # (role, text, block_label)
        self.resets = []
        self.external_calls = []  # (name, prompt) pairs
        self.external_responses = external_responses or {}
        self.db_results = db_results  # override dual_db_search return

    def send_message(self, role, prompt):
        self.messages.append((role, prompt))
        if role in self.fail_roles:
            raise RuntimeError(f"agent {role} unavailable")
        if role in self.empty_roles:
            return ""
        return self.responses.get(role, f"Generated content for {role} section.")

    def send_to_external(self, name, prompt):
        self.external_calls.append((name, prompt))
        return self.external_responses.get(name, "")

    def reset_agent_messages(self, role):
        self.resets.append(role)

    def update_agent_context(self, role, text, block_label="human"):
        self.context_updates.append((role, text, block_label))

    def dual_db_search(self, query, db1_top_k=3, db2_top_k=3):
        self.last_search = {"query": query, "db1": db1_top_k, "db2": db2_top_k}
        if self.db_results is not None:
            return self.db_results
        return {"db1_results": [], "db2_results": []}


# ─── Gap detection ──────────────────────────────────────────────


def test_detect_gap_topic_by_keyword(monkeypatch):
    monkeypatch.setattr(lw, "KB_METADATA", {
        "databases": {"db2_entity_qms": {"gaps": [
            {"topic": "Product Recall", "skill_fallback": "recall-skill",
             "description": "No recall examples", "status": "high"},
        ]}},
        "gap_detection": {"keywords": {"product_recall": ["recall", "market withdrawal"]}},
    })
    gap = lw._detect_gap_topic("procedure for market withdrawal", "Recall Handling")
    assert gap is not None
    assert gap["topic"] == "Product Recall"
    assert gap["skill_fallback"] == "recall-skill"
    assert gap["severity"] == "high"


def test_detect_gap_topic_none_for_unrelated_query(monkeypatch):
    monkeypatch.setattr(lw, "KB_METADATA", {
        "databases": {"db2_entity_qms": {"gaps": [
            {"topic": "Product Recall", "skill_fallback": "recall-skill"},
        ]}},
        "gap_detection": {"keywords": {"product_recall": ["recall"]}},
    })
    assert lw._detect_gap_topic("cleaning validation", "Cleaning") is None


def test_detect_gap_topic_direct_topic_match(monkeypatch):
    monkeypatch.setattr(lw, "KB_METADATA", {
        "databases": {"db2_entity_qms": {"gaps": [
            {"topic": "Change Control", "skill_fallback": "cc-skill"},
        ]}},
        "gap_detection": {"keywords": {}},
    })
    gap = lw._detect_gap_topic("how to run change control", "Some SOP")
    assert gap is not None and gap["topic"] == "Change Control"


# ─── Passage enrichment ─────────────────────────────────────────


def test_enrich_passage_metadata_quality_and_authority(monkeypatch):
    monkeypatch.setattr(lw, "CLASSIFICATION_RULES", {
        "classification_rules": {"filename_patterns": {}, "content_keywords": {}},
        "quality_scoring": {"structure_indicators": {
            "has_headers": {"points": 1.5},
            "has_numbering": {"points": 1.0},
            "has_tables": {"points": 1.0},
        }},
    })
    text = "# Header\n1. Step one\n| a | b |\n---\n"
    meta = lw._enrich_passage_metadata(text, ["db1", "file:annex11.pdf"])
    assert meta["quality"] == 8.5  # 5.0 base + 1.5 + 1.0 + 1.0
    assert meta["source_authority"] == "official_regulatory"

    plain = lw._enrich_passage_metadata("plain text", ["file:example.docx"])
    assert plain["quality"] == 5.0
    assert plain["source_authority"] == "operational_example"


def test_enrich_passage_metadata_filename_classification(monkeypatch):
    monkeypatch.setattr(lw, "CLASSIFICATION_RULES", {
        "classification_rules": {
            "filename_patterns": {"Validation": {"patterns": ["valid"]}},
            "content_keywords": {},
        },
        "quality_scoring": {},
    })
    meta = lw._enrich_passage_metadata("text", ["file:Cleaning_Validation.docx"])
    assert meta["category"] == "Validation"


# ─── Prompt builders ────────────────────────────────────────────


def _workflow(fake=None, tmp_path=None):
    return LettaSOPWorkflow(fake or FakeLetta(), project_root=str(tmp_path) if tmp_path else None)


def test_build_context_string_includes_selections():
    wf = _workflow()
    ctx = wf._build_context_string(
        "Document Control", "QA_00.02", "QA", "Cannabis EU GMP", "SOP",
        {"annexes": ["Transport Form"]},
    )
    assert "QA_00.02 - Document Control" in ctx
    assert "Department: QA" in ctx
    assert "Transport Form" in ctx


def test_build_section_prompt_injects_mapped_user_inputs(monkeypatch):
    monkeypatch.setattr(lw, "USER_INPUT_MAPPING", {"equipment_list": ["procedure"]})
    wf = _workflow()
    prompt = wf._build_section_prompt(
        "procedure", "Cleaning", "PR_01.01", "Production",
        {"equipment_list": "HPLC-01, Scale-02"},
        rag_context="context snippet",
        prev_sections={"purpose": "The purpose is cleanliness." * 20},
    )
    assert "Equipment List:" in prompt and "HPLC-01" in prompt
    assert "context snippet" in prompt
    assert "COHERENCE CONTEXT" in prompt
    # unmapped section must not receive the input
    other = wf._build_section_prompt(
        "scope", "Cleaning", "PR_01.01", "Production",
        {"equipment_list": "HPLC-01"}, rag_context="", prev_sections={},
    )
    assert "HPLC-01" not in other


def test_build_assembly_prompt_metrics():
    wf = _workflow()
    sections = {"purpose": "## Heading\n1. one\nEU GMP cannabis text | --- |"}
    prompt = wf._build_assembly_prompt(sections, "Cleaning", "PR_01.01")
    assert "Has headings (##): True" in prompt
    assert "Has numbered lists: True" in prompt
    assert "Mentions EU GMP: True" in prompt
    assert "Cannabis-specific: True" in prompt


def test_build_annex_prompt():
    wf = _workflow()
    prompt = wf._build_annex_prompt(
        "Transport Form", "Annex A", "Transport", "LG_02.01", "summary text"
    )
    assert "Annex A: Transport Form" in prompt
    assert "LG_02.01 - Transport" in prompt
    assert "summary text" in prompt


# ─── Gap-aware search weighting ─────────────────────────────────


def test_search_for_section_boosts_db1_on_gap(monkeypatch):
    monkeypatch.setattr(lw, "KB_METADATA", {
        "databases": {"db2_entity_qms": {"gaps": [
            {"topic": "Product Recall", "skill_fallback": "recall-skill"},
        ]}},
        "gap_detection": {"keywords": {"product_recall": ["recall"]}},
    })
    monkeypatch.setattr(lw, "RAG_QUERY_TEMPLATES", {"procedure": "EU GMP {sop_name}"})
    fake = FakeLetta()
    wf = _workflow(fake)
    out = wf._search_for_section("procedure", "Product Recall")
    # procedure default weights are db1=2/db2=5; gap boosts db1 and trims db2
    assert fake.last_search["db1"] == 5
    assert fake.last_search["db2"] == 4
    assert "KNOWLEDGE GAP NOTICE" in out
    assert "recall-skill" in out


# ─── execute() orchestration ────────────────────────────────────


def test_execute_happy_path(tmp_path):
    fake = FakeLetta()
    wf = _workflow(fake, tmp_path)
    result = asyncio.run(wf.execute(sop_name="Document Control", sop_code="QA_00.02", department="QA"))

    assert set(result["sections"]) == set(SECTION_ORDER)
    assert result["errors"] == []
    assert result["metadata"]["section_count"] == len(SECTION_ORDER)
    assert result["quality_report"]
    # DOCX generated under the provided project root
    assert result["docx_path"].startswith(str(tmp_path))
    assert Path(result["docx_path"]).exists()
    # researcher + one message per section + assembler
    roles_messaged = [r for r, _ in fake.messages]
    assert roles_messaged[0] == "researcher"
    assert roles_messaged[-1] == "assembler"


def test_execute_records_section_failures(tmp_path):
    fake = FakeLetta(fail_roles={"procedure"}, empty_roles={"scope"})
    wf = _workflow(fake, tmp_path)
    result = asyncio.run(wf.execute(sop_name="Cleaning", sop_code="PR_01.01"))

    assert any(e["section"] == "procedure" for e in result["errors"])
    assert any(e["section"] == "scope" and e["error"] == "Empty response" for e in result["errors"])
    assert result["sections"]["procedure"].startswith("[Error generating")
    # failures must not abort the run: other sections still generated
    assert result["sections"]["purpose"].startswith("Generated content")
    assert result["metadata"]["section_count"] == len(SECTION_ORDER) - 2


def test_execute_survives_researcher_failure(tmp_path):
    fake = FakeLetta(fail_roles={"researcher"})
    wf = _workflow(fake, tmp_path)
    result = asyncio.run(wf.execute(sop_name="Sampling", sop_code="QC_03.01"))
    assert result["errors"] == []
    assert result["metadata"]["section_count"] == len(SECTION_ORDER)
    # fallback research brief propagated to agent memory blocks
    research_blocks = [t for _, t, label in fake.context_updates if label == "research"]
    assert research_blocks and all("unavailable" in t for t in research_blocks)


def test_generate_annexes_labels_and_error_isolation():
    fake = FakeLetta(responses={"annex": "| Field | Value |\n| --- | --- |"})
    wf = _workflow(fake)
    result = asyncio.run(wf.generate_annexes(
        annexes=["Transport Form", "Checklist"],
        sections={"procedure": "steps"},
        sop_name="Transport",
        sop_code="LG_02.01",
    ))
    assert list(result) == ["Annex A", "Annex B"]
    assert all(v.startswith("|") for v in result.values())

    failing = FakeLetta(fail_roles={"annex"})
    wf2 = _workflow(failing)
    result2 = asyncio.run(wf2.generate_annexes(
        annexes=["Form"], sections={}, sop_name="X", sop_code="Y",
    ))
    assert result2["Annex A"].startswith("[Error generating Annex A")


def test_execute_with_annexes_appends_to_docx(tmp_path):
    fake = FakeLetta(responses={"annex": "Annex body content"})
    wf = _workflow(fake, tmp_path)
    result = asyncio.run(wf.execute(
        sop_name="Transport",
        sop_code="LG_02.01",
        user_selections={"annexes": ["Transport Form"]},
    ))
    assert result["annexes"] == {"Annex A": "Annex body content"}
    assert result["metadata"]["annex_count"] == 1
    assert Path(result["docx_path"]).exists()


# ─── Hybrid specialist wiring (D1c) ─────────────────────────────


def test_research_prefers_compliance_specialist(tmp_path):
    """Research brief comes from the external compliance specialist when available."""
    fake = FakeLetta(external_responses={
        "eu_gmp_compliance_expert": "AUTHORITATIVE EU GMP BRIEF with citations."
    })
    wf = _workflow(fake, tmp_path)
    asyncio.run(wf.execute(sop_name="Document Control", sop_code="QA_00.02"))
    # the compliance specialist was consulted...
    assert any(n == "eu_gmp_compliance_expert" for n, _ in fake.external_calls)
    # ...and its brief was propagated to agents' research memory block
    research_blocks = [t for _, t, label in fake.context_updates if label == "research"]
    assert research_blocks and all("AUTHORITATIVE EU GMP BRIEF" in t for t in research_blocks)
    # the internal researcher agent was NOT needed as a fallback
    assert "researcher" not in [r for r, _ in fake.messages]


def test_research_falls_back_to_internal_researcher(tmp_path):
    """When the specialist is absent (returns ''), fall back to the app's researcher."""
    fake = FakeLetta()  # no external_responses -> send_to_external returns ""
    wf = _workflow(fake, tmp_path)
    asyncio.run(wf.execute(sop_name="Cleaning", sop_code="PR_01.01"))
    assert any(n == "eu_gmp_compliance_expert" for n, _ in fake.external_calls)
    assert "researcher" in [r for r, _ in fake.messages]


def test_section_search_falls_back_to_rag_specialist():
    """Empty archives -> consult gmp_rag_agent and embed its answer in context."""
    fake = FakeLetta(external_responses={
        "gmp_rag_agent": "Relevant Annex 15 cleaning-validation guidance."
    })
    wf = _workflow(fake)
    out = wf._search_for_section("procedure", "Cleaning Validation")
    assert any(n == "gmp_rag_agent" for n, _ in fake.external_calls)
    assert "GMP RAG SPECIALIST" in out
    assert "Annex 15 cleaning-validation" in out


def test_section_search_skips_rag_specialist_when_archives_hit():
    """If archives return results, do not call the external RAG specialist."""
    fake = FakeLetta(db_results={
        "db1_results": [{"text": "official guidance", "tags": ["db1"]}],
        "db2_results": [],
    })
    wf = _workflow(fake)
    wf._search_for_section("procedure", "Cleaning")
    assert not any(n == "gmp_rag_agent" for n, _ in fake.external_calls)


# ─── DOCX failure surfacing (bug #6) ────────────────────────────


def test_docx_failure_recorded_in_errors(tmp_path, monkeypatch):
    """A DOCX generation exception is recorded in errors, not hidden as success."""
    fake = FakeLetta()
    wf = _workflow(fake, tmp_path)

    def boom(*a, **k):
        raise RuntimeError("docx engine exploded")

    monkeypatch.setattr(wf, "_generate_docx", boom)
    result = asyncio.run(wf.execute(sop_name="X", sop_code="QA_00.09"))
    assert any(e["section"] == "docx_generation" for e in result["errors"])
    assert result["docx_path"] == ""
