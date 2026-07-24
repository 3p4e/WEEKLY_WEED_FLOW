# Pipeline unit surface: questionnaire defaulting + Markdown assembly, plus
# run_workflow's error-path coverage (the Letta round-trips are otherwise
# exercised live on the wwf_mass stack, not here).
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import builder, db, fleet  # noqa: E402
from app.letta import LettaError  # noqa: E402
from app.pipeline import (  # noqa: E402
    assemble_markdown, run_workflow, _strip_fences, _clean_section,
)
from app.questionnaires import apply_defaults  # noqa: E402


def test_apply_defaults_fills_compliant_options():
    out = apply_defaults("sop_qc", {"focus": "Potency"})
    assert out["focus"] == "Potency"                       # explicit answer kept
    assert out["method_source"] == "Ph. Eur. (preferred)"  # default filled
    assert out["review_chain"].startswith("Two-tier")
    # multi-select default
    assert "Doc ID (EU GMP 4.2)" in apply_defaults("annex_form", {})["id_fields"]


def test_assemble_markdown_headerdata_and_sections():
    md = assemble_markdown(
        {"title_mk": "МК", "title_en": "EN", "code": "C-1", "doctype": "SOP"},
        [{"num": "1.0", "mk": "ЦЕЛ", "en": "PURPOSE", "content": "Текст.|Text."}],
    )
    assert md.startswith("<!--HEADERDATA")
    assert "doctype: SOP" in md and "code: C-1" in md
    assert "# 1.0 ЦЕЛ|PURPOSE" in md and "Текст.|Text." in md


def test_assemble_markdown_rejects_embedded_comment_terminator():
    # B2: a meta field value containing '-->' would corrupt the HEADERDATA
    # block boundary downstream — reject at assembly time, don't ship it.
    with pytest.raises(ValueError):
        assemble_markdown(
            {"title_mk": "Опис --> на процедура", "title_en": "EN", "code": "C-1", "doctype": "SOP"},
            [{"num": "1.0", "mk": "ЦЕЛ", "en": "PURPOSE", "content": "Текст.|Text."}],
        )


def test_strip_fences():
    assert _strip_fences("```markdown\nhello\n```") == "hello"
    assert _strip_fences("plain") == "plain"


def test_clean_section_structured_drops_preamble_before_marker():
    # the exact failure observed on the live wwf_mass smoke
    raw = (
        "Looking at the persona description more carefully — it explicitly "
        "describes the structure of QCT-SMOKE-01 (my earlier work). Let me align "
        "to that specification precisely.\n\n"
        "# Барање | Material Transfer Request\n\n"
        "[[FORM:grid]]\nИме ~~ Name ||| _____\n[[FORM:grid]]"
    )
    out = _clean_section(raw, structured=True)
    assert out.startswith("# Барање | Material Transfer Request")
    assert "Looking at the persona" not in out
    assert "[[FORM:grid]]" in out


def test_clean_section_prose_peels_leading_commentary_only():
    raw = "Here is the section body:\n\nThe purpose of this SOP is to define X."
    out = _clean_section(raw, structured=False)
    assert out == "The purpose of this SOP is to define X."


def test_clean_section_keeps_legitimate_prose():
    # a real SOP prose body must never be eaten, even with no heading
    raw = "The purpose of this procedure is to describe the sampling of water."
    assert _clean_section(raw, structured=False) == raw
    # a body that is ALL commentary falls back to the original (never empty)
    only = "Let me think about this."
    assert _clean_section(only, structured=False) == only


# ── run_workflow error-path coverage ────────────────────────────────────────
# Every branch below drives run_workflow end-to-end with fakes for db/fleet/
# the Letta client, asserting on the job row run_workflow itself writes —
# run_workflow "never raises: every failure lands in the job row as
# status=failed" (its own docstring), and this is what pins that promise.
_AGENT_NAMES = ("gf_sop_author", "gf_raci_specialist", "gf_annex_author",
                "gf_reg_checker", "gf_qa_auditor")


def _job(qkey="annex_form"):
    return {
        "id": "job-1",
        "payload": {
            "questionnaire": qkey, "answers": {},
            "meta": {"title_mk": "МК наслов", "title_en": "EN title", "code": "C-1"},
        },
    }


class FakeClient:
    """Replies NO-FINDING to regulatory checks and PASS to the §6A audit by
    default; subclasses override send_message/delete_agent for specific
    failure modes."""

    async def send_message(self, agent_id, prompt):
        if "§6A" in prompt:
            return "PASS"
        return "NO-FINDING"

    async def delete_agent(self, agent_id):
        pass


def _patch_common(monkeypatch, qkey="annex_form"):
    updates = []

    async def fake_job_get(jid):
        return _job(qkey)

    async def fake_job_update(jid, **fields):
        updates.append(fields)

    async def fake_document_create(job_id, meta):
        return "doc-1"

    async def fake_ensure_fleet(client):
        return {name: f"agent-{name}" for name in _AGENT_NAMES}

    async def fake_spawn_ephemeral(client, agent_name, name_suffix):
        return f"tmp-{agent_name}-{name_suffix}"

    monkeypatch.setattr(db, "job_get", fake_job_get)
    monkeypatch.setattr(db, "job_update", fake_job_update)
    monkeypatch.setattr(db, "document_create", fake_document_create)
    monkeypatch.setattr(fleet, "ensure_fleet", fake_ensure_fleet)
    monkeypatch.setattr(fleet, "spawn_ephemeral", fake_spawn_ephemeral)
    return updates


def _fake_build_result():
    return builder.BuildResult(path=Path("/tmp/x.docx"), bytes=10,
                               verify_report="RESULT: PASS", doctype="SOP")


@pytest.mark.asyncio
async def test_verify_failed_records_failed_status(monkeypatch):
    updates = _patch_common(monkeypatch)
    monkeypatch.setattr(builder, "build",
                        lambda *a, **k: (_ for _ in ()).throw(builder.VerifyFailed("bad report")))
    await run_workflow("job-1", client=FakeClient())
    assert updates[-1]["status"] == "failed"
    assert updates[-1]["error"] == "verify FAILED"
    assert updates[-1]["result"]["verify"] == "bad report"


@pytest.mark.asyncio
async def test_letta_error_records_failed_status(monkeypatch):
    updates = _patch_common(monkeypatch)

    class FailingClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            raise LettaError("letta down")

    await run_workflow("job-1", client=FailingClient())
    assert updates[-1]["status"] == "failed"
    assert updates[-1]["error"] == "letta: letta down"


@pytest.mark.asyncio
async def test_generic_exception_with_blank_str_still_records_a_useful_error(monkeypatch):
    # httpx.ReadTimeout and friends stringify to "" — the job's error must
    # never end up blank; it falls back to the exception's type name.
    updates = _patch_common(monkeypatch)

    class _Blank(Exception):
        def __str__(self):
            return ""

    class FailingClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            raise _Blank()

    await run_workflow("job-1", client=FailingClient())
    assert updates[-1]["status"] == "failed"
    assert updates[-1]["error"].startswith("_Blank:")


@pytest.mark.asyncio
async def test_qa_audit_fix_verdict_blocks_the_build(monkeypatch):
    updates = _patch_common(monkeypatch)
    built = []
    monkeypatch.setattr(builder, "build", lambda *a, **k: built.append(1) or _fake_build_result())

    class FixClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            if "§6A" in prompt:
                return "FIX: section 2.0 references the wrong regulation"
            return "NO-FINDING"

    await run_workflow("job-1", client=FixClient())
    assert not built, "builder.build must never run past a §6A FIX verdict"
    assert updates[-1]["status"] == "failed"
    assert updates[-1]["error"] == "§6A audit did not pass"
    assert updates[-1]["result"]["qa_audit"].startswith("FIX")


@pytest.mark.asyncio
async def test_qa_audit_pass_verdict_proceeds_to_build(monkeypatch):
    updates = _patch_common(monkeypatch)
    monkeypatch.setattr(builder, "build", lambda *a, **k: _fake_build_result())
    await run_workflow("job-1", client=FakeClient())
    assert updates[-1]["status"] == "done"


@pytest.mark.asyncio
async def test_ephemeral_regchecker_cleanup_failure_does_not_abort_the_job(monkeypatch):
    """The SOP path spawns + deletes a throwaway reg-checker per section; a
    failure deleting it (observed live: httpx transport errors) must not
    abort the whole job — it's logged and the job still completes."""
    updates = _patch_common(monkeypatch, qkey="sop_qc")
    monkeypatch.setattr(builder, "build", lambda *a, **k: _fake_build_result())

    class FlakyDeleteClient(FakeClient):
        async def delete_agent(self, agent_id):
            raise RuntimeError("delete failed")

    await run_workflow("job-1", client=FlakyDeleteClient())
    assert updates[-1]["status"] == "done"
