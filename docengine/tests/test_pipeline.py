# Pipeline unit surface: questionnaire defaulting + Markdown assembly, plus
# run_workflow's error-path coverage (the Letta round-trips are otherwise
# exercised live on the wwf_mass stack, not here).
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import builder, db, fleet  # noqa: E402
from app.config import settings  # noqa: E402
from app.letta import LettaError  # noqa: E402
from app.pipeline import (  # noqa: E402
    assemble_markdown, run_workflow, _strip_fences, _clean_section, _bilingual_gaps,
    _brief, _qa_audit_passed, _split_repaired, _section_body, _repair_sections,
    _drop_echoed_heading,
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


def test_assemble_markdown_rejects_embedded_newline_in_orient():
    # HIGH: a meta.orient value with an embedded newline could smuggle a
    # forged `code:`/`version:` HEADERDATA line in AFTER the real ones.
    # build_from_md.py's parser is line-anchored key:value with last-line-
    # wins, so the forged fields would win when the document is built —
    # diverging the .docx's printed code/version from the registry row this
    # same pipeline records from the caller's original, unmodified metadata.
    # Must be rejected at assembly time, same as the existing '-->' guard.
    with pytest.raises(ValueError):
        assemble_markdown(
            {
                "title_mk": "МК", "title_en": "EN", "code": "SOP-REAL",
                "doctype": "SOP", "version": "1.0",
                "orient": "portrait\ncode: SOP-FORGED\nversion: 9.9",
            },
            [{"num": "1.0", "mk": "ЦЕЛ", "en": "PURPOSE", "content": "Текст.|Text."}],
        )


def test_assemble_markdown_rejects_bare_carriage_return():
    # \r alone (no \n) is just as capable of confusing a line-oriented
    # parser/renderer as \n — reject both.
    with pytest.raises(ValueError):
        assemble_markdown(
            {"title_mk": "МК", "title_en": "EN", "code": "C-1", "doctype": "SOP",
             "orient": "portrait\rcode: SOP-FORGED"},
            [{"num": "1.0", "mk": "ЦЕЛ", "en": "PURPOSE", "content": "Текст.|Text."}],
        )


def test_assemble_markdown_rejects_embedded_newline_in_any_headerdata_field():
    # Not just orient — every field written into the block is guarded the
    # same way (title_mk here, arbitrarily chosen among the rest).
    with pytest.raises(ValueError):
        assemble_markdown(
            {"title_mk": "МК\ncode: SOP-FORGED", "title_en": "EN", "code": "C-1", "doctype": "SOP"},
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


def test_clean_section_keeps_sop_prose_openers():
    """M — the stripper used to match "note:", "based on", "the following",
    "this is the" and "below is" at the start of a line. Those open ordinary
    procedure text at least as often as agent chatter, and the strip is silent:
    the §5A fidelity check compares the built .docx against this ALREADY-CLEANED
    text, so anything lost here is invisible to the one safeguard meant to catch
    content impoverishment."""
    for raw in (
        "Note: samples must be stored at 2-8 °C until tested.",
        "Based on the risk assessment, sampling is performed per QCSOP-011.",
        "The following equipment is required for this procedure.",
        "This is the reference method for water conductivity.",
        "Below is the acceptance criteria table.",
    ):
        assert _clean_section(raw, structured=False) == raw, raw


def test_clean_section_refuses_an_oversized_strip():
    """M — a conversational lead-in is short. A large removal is the agent's
    real output, so the stripper keeps the original rather than being the thing
    that silently drops procedure text."""
    big = ("Let me explain. " + "This sentence is real procedure content. " * 40).strip()
    out = _clean_section(big, structured=False)
    assert out == big                      # refused, nothing lost
    # …while a genuinely short lead-in is still peeled
    small = "Let me explain.\n\nThe purpose of this SOP is to define X."
    assert _clean_section(small, structured=False) == "The purpose of this SOP is to define X."


# --- per-section bilingual gate -------------------------------------------
# M — pp_verify's --require-bilingual asks whether the WHOLE .docx contains
# Cyrillic and Latin ANYWHERE, so one Macedonian word in a forty-page English
# document passes it. Every realistic failure is per-section, which is where
# _bilingual_gaps looks.

_MK = ("Оваа постапка ја опишува постапката за земање, обележување и чување на "
       "примероци од секоја произведена серија до крајот на рокот на употреба.")
_EN = ("This procedure describes the sampling, labelling and retention of samples "
       "from every manufactured batch until the end of its shelf life.")


def test_bilingual_gaps_flags_a_monolingual_section():
    gaps = _bilingual_gaps([
        {"num": "1.0", "content": f"{_MK}|{_EN}"},
        {"num": "2.0", "content": _EN * 2},      # English only
        {"num": "3.0", "content": _MK * 2},      # Macedonian only
    ])
    assert gaps == ["2.0 (no MK)", "3.0 (no EN)"]


def test_bilingual_gaps_passes_a_document_that_is_bilingual_throughout():
    assert _bilingual_gaps([
        {"num": "1.0", "content": f"{_MK}|{_EN}"},
        {"num": "2.0", "content": f"{_MK}|{_EN}"},
    ]) == []


def test_bilingual_gaps_ignores_sections_with_too_little_text_to_judge():
    """A bare form marker, a formula or a short code reference is legitimately
    language-neutral. Failing those would make the gate unusable."""
    assert _bilingual_gaps([
        {"num": "4.0", "content": "[[FORM:grid]]"},
        {"num": "5.0", "content": "QCSOP-011 v2.0"},
        {"num": "6.0", "content": "C = (A - B) / V * 100"},
        {"num": "7.0", "content": ""},
    ]) == []


def test_bilingual_gaps_is_what_the_whole_document_check_would_miss():
    """The regression this exists for, stated directly: a document whose
    sections are overwhelmingly English but that carries Macedonian in ONE
    section satisfies pp_verify's document-wide check, and must not satisfy
    this one."""
    sections = [{"num": "1.0", "content": f"{_MK}|{_EN}"}] + [
        {"num": f"{n}.0", "content": _EN * 3} for n in range(2, 8)
    ]
    whole_doc = " ".join(s["content"] for s in sections)
    import re as _re
    assert _re.search(r"[Ѐ-ӿ]", whole_doc) and _re.search(r"[A-Za-z]", whole_doc)
    assert _bilingual_gaps(sections) == [f"{n}.0 (no MK)" for n in range(2, 8)]


@pytest.mark.asyncio
async def test_monolingual_section_fails_the_job_before_the_build(monkeypatch):
    """The gate wired end-to-end: an English-only section must fail the job,
    and must do so BEFORE builder.build runs — the whole point is catching it
    while the sections are still separable, not after pp_verify's
    document-wide check has waved it through."""
    updates = _patch_common(monkeypatch)
    built = []
    monkeypatch.setattr(builder, "build", lambda *a, **k: built.append(1) or _fake_build_result())

    class EnglishOnlyClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            if "§6A" in prompt:
                return "PASS"
            if "Check this drafted section" in prompt:
                return "NO-FINDING"
            return _EN * 3          # the drafted section body — no Macedonian

    await run_workflow("job-1", client=EnglishOnlyClient())
    assert updates[-1]["status"] == "failed"
    assert "not bilingual" in updates[-1]["error"]
    assert updates[-1]["result"]["bilingual_gaps"] == ["1.0 (no MK)"]
    assert not built, "the build must not run once a section is known monolingual"


@pytest.mark.asyncio
async def test_bilingual_sections_still_reach_the_build(monkeypatch):
    """The other direction — the gate must not block a legitimate document."""
    updates = _patch_common(monkeypatch)
    built = []
    monkeypatch.setattr(builder, "build", lambda *a, **k: built.append(1) or _fake_build_result())

    class BilingualClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            if "§6A" in prompt:
                return "PASS"
            if "Check this drafted section" in prompt:
                return "NO-FINDING"
            return f"{_MK}|{_EN}"

    await run_workflow("job-1", client=BilingualClient())
    assert updates[-1]["status"] == "done"
    assert built


def test_bilingual_gaps_does_not_fail_a_short_bilingual_section():
    """The regression that the code check caught before this shipped.

    Macedonian renders longer than its English equivalent, so an ordinary short
    bilingual section sits around 52 Cyrillic / 31 Latin letters. Judged against
    a single shared floor that reads as "missing English" and FAILS a perfectly
    good job — worse than the gap the check exists to close. Hence the split
    into _MIN_TOTAL_TO_JUDGE (is there enough text to have an opinion?) and
    _MIN_PRESENCE (is this language present at all?)."""
    mk = "Опсегот на оваа постапка ги опфаќа сите серии од производство"
    en = "Scope covers all production batches"
    assert _bilingual_gaps([{"num": "2.0", "content": f"{mk}|{en}"}]) == []
    # ...and a longer section with the same lopsided ratio is still fine
    assert _bilingual_gaps([{"num": "3.0", "content": f"{mk * 3}|{en * 3}"}]) == []


def test_clean_section_strips_an_agent_emitted_headerdata_block():
    """assemble_markdown owns document metadata and prepends the authoritative
    block; build_from_md.py's parser is line-anchored on the FIRST
    "<!--HEADERDATA" it sees. A second block therefore either declares a
    conflicting version or leaks its fields into the body as literal text.
    Observed live: DeepSeek v4-flash emitted one mid-body and the §6A auditor
    flagged the version conflict."""
    body = (
        "## 1. Наслов|Title\n"
        "<!--HEADERDATA\n"
        "doc_id: X\n"
        "version: 4.3\n"
        "-->\n"
        "[[TABLE]]\n"
        "Бр.|||No.\n"
    )
    out = _clean_section(body, structured=True)
    assert "HEADERDATA" not in out
    assert "version: 4.3" not in out
    # the real content survives on both sides of where the block was
    assert "## 1. Наслов|Title" in out
    assert "[[TABLE]]" in out
    assert "Бр.|||No." in out


def test_clean_section_strips_headerdata_placed_before_any_heading():
    out = _clean_section(
        "<!--HEADERDATA\nversion: 9\n-->\n## 1. A|B\ntext\n", structured=True
    )
    assert "HEADERDATA" not in out and "## 1. A|B" in out


def test_clean_section_leaves_an_ordinary_html_comment_alone():
    """Only HEADERDATA is the assembler's property."""
    out = _clean_section("## 1. A|B\n<!-- a note -->\ntext\n", structured=True)
    assert "<!-- a note -->" in out


def test_brief_says_parenthesised_numbers_are_clause_refs_not_values():
    """Several questionnaire options read "Version (4.3)", where 4.3 is the EU
    GMP clause requiring the field. A model that took it as the value produced a
    form stamped version 4.3 against a document at 1.0 — the §6A auditor's
    objection was that someone could sign off on the wrong revision."""
    b = _brief(
        "annex_form",
        {"id_fields": ["Doc ID (EU GMP 4.2)", "Version (4.3)", "Date (4.8)"]},
        {"code": "QASOP_031", "version": "2.0"},
    )
    assert "NEVER the field's value" in b
    assert "clause" in b
    # and the real identity is stated so the agent has no reason to infer one
    assert "QASOP_031" in b and "version: 2.0" in b


def test_brief_without_meta_still_renders_the_answers():
    b = _brief("annex_form", {"purpose": "Recording"})
    assert "purpose: Recording" in b


# ---- §6A verdict parsing ----
# The live auditor prefixes a line of preamble and announces "**Verdict: PASS**".
# Requiring the reply to START with PASS rejected a genuinely passing audit and
# the document was never built, so these pin the real reply shapes.
@pytest.mark.parametrize(
    "reply",
    [
        "PASS",
        "PASS — no issues found",
        "I'll run the §6A review on this FORM.\n\n**Verdict: PASS**\n\nChecks: ...",
        "Verdict: PASS",
        "verdict:  pass\nall six checks cleared",
    ],
)
def test_qa_audit_accepts_a_real_pass_reply(reply):
    assert _qa_audit_passed(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "   ",
        "FIX: section 2.0 references the wrong regulation",
        "**Verdict: FIX**\n\n1. Version conflict ...",
        # no recognisable verdict at all -> fail closed
        "The document looks broadly reasonable to me.",
        # both tokens present -> ambiguous -> fail closed
        "**Verdict: FIX**\nlater corrected to Verdict: PASS",
        # must not be fooled by prose containing the word
        "The document did not PASS the bilingual check.",
    ],
)
def test_qa_audit_rejects_anything_short_of_a_clear_pass(reply):
    assert not _qa_audit_passed(reply)


@pytest.mark.asyncio
async def test_a_pass_with_preamble_reaches_the_builder(monkeypatch):
    """End-to-end shape of the live failure: the auditor passed the document and
    the build still never ran."""
    updates = _patch_common(monkeypatch)
    built = []
    monkeypatch.setattr(builder, "build", lambda *a, **k: built.append(1) or _fake_build_result())

    class PreambleAuditClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            if "§6A" in prompt:
                return "I'll run the §6A review.\n\n**Verdict: PASS**\n\nAll checks cleared."
            return await super().send_message(agent_id, prompt)

    await run_workflow("job-1", client=PreambleAuditClient())
    assert built, "a PASS announced after preamble must still reach builder.build"
    assert updates[-1]["status"] == "done"


# ---- §6A repair loop ----
def _blk(num, mk, en, content):
    """Build one repair-protocol section block."""
    return f"<<<PP-SECTION {num}|{mk}|{en}>>>\n{content}\n<<<PP-END {num}>>>"


_ORIG = [
    {"num": "1.0", "mk": "СОДРЖИНА", "en": "CONTENT", "content": "тело|body one"},
    {"num": "2.0", "mk": "ПОТВРДА", "en": "SIGN-OFF", "content": "тело|body two"},
]


def test_split_repaired_accepts_a_faithful_rewrite():
    body = _blk("1.0", "СОДРЖИНА", "CONTENT", "нов|new one") + "\n\n" + \
        _blk("2.0", "ПОТВРДА", "SIGN-OFF", "нов|new two")
    out, reason = _split_repaired(body, _ORIG)
    assert reason.startswith("ok")
    assert [s["content"] for s in out] == ["нов|new one", "нов|new two"]
    # titles are carried from the originals, never taken from the reply
    assert [(s["num"], s["mk"], s["en"]) for s in out] == [
        ("1.0", "СОДРЖИНА", "CONTENT"), ("2.0", "ПОТВРДА", "SIGN-OFF")]


def test_split_repaired_ignores_a_retitled_section():
    """The agent may rewrite bodies, not rename sections — but the title it
    supplies is discarded rather than trusted."""
    body = _blk("1.0", "SOMETHING ELSE", "WHATEVER", "нов|new one") + "\n\n" + \
        _blk("2.0", "X", "Y", "нов|new two")
    out, _ = _split_repaired(body, _ORIG)
    assert [s["mk"] for s in out] == ["СОДРЖИНА", "ПОТВРДА"]


@pytest.mark.parametrize(
    "body",
    [
        "",                                                   # nothing back
        "Sure! Here is the fixed document.",                  # no headings
        _blk("1.0", "A", "B", "x") + _blk("2.0", "C", "D", "y") + _blk("3.0", "E", "F", "z"),
        _blk("1.0", "A", "B", "x") + _blk("2.9", "C", "D", "y"),          # renumbered
        _blk("1.0", "A", "B", "") + _blk("2.0", "C", "D", "y"),           # emptied a section
        # opened but never closed — the whole point of the end marker
        "<<<PP-SECTION 1.0|A|B>>>\nx" + _blk("2.0", "C", "D", "y"),
    ],
)
def test_split_repaired_refuses_anything_that_does_not_line_up(body):
    """A repair that cannot be parsed with confidence is not a repair. The job
    must fail on the auditor's verdict rather than build a guess."""
    out, reason = _split_repaired(body, _ORIG)
    assert out is None and reason


def test_section_body_never_exposes_the_document_header():
    """Agents own no document metadata — the one defect this pipeline already
    had to strip. The repair input must not hand it back to them."""
    body = _section_body(_ORIG)
    assert "HEADERDATA" not in body
    assert body.startswith("<<<PP-SECTION 1.0|СОДРЖИНА|CONTENT>>>")


@pytest.mark.asyncio
async def test_a_fix_verdict_is_repaired_and_the_document_builds(monkeypatch):
    updates = _patch_common(monkeypatch)
    built = []
    monkeypatch.setattr(builder, "build", lambda *a, **k: built.append(1) or _fake_build_result())
    monkeypatch.setattr(settings, "max_repair_rounds", 1)

    class RepairingClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.audits = 0

        async def send_message(self, agent_id, prompt):
            if "corrected sections and NOTHING" in prompt:
                return _blk("1.0", "СОДРЖИНА", "CONTENT", "поправено|repaired")
            if "§6A" in prompt:
                self.audits += 1
                return ("**Verdict: FIX**\n1. missing Code row" if self.audits == 1
                        else "**Verdict: PASS**")
            return await super().send_message(agent_id, prompt)

    await run_workflow("job-1", client=RepairingClient())
    assert built, "a repaired document must reach the builder"
    res = updates[-1]["result"]
    assert updates[-1]["status"] == "done"
    # trap 2: the record must not read as a first-pass PASS
    assert res["qa_repair_rounds"] == 1
    assert len(res["qa_audit_history"]) == 2
    assert "FIX" in res["qa_audit_history"][0]
    assert _qa_audit_passed(res["qa_audit"])


@pytest.mark.asyncio
async def test_an_unusable_repair_fails_the_job_on_the_original_verdict(monkeypatch):
    updates = _patch_common(monkeypatch)
    built = []
    monkeypatch.setattr(builder, "build", lambda *a, **k: built.append(1) or _fake_build_result())
    monkeypatch.setattr(settings, "max_repair_rounds", 1)

    class GarbageRepairClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            if "corrected sections and NOTHING" in prompt:
                return "Sure! I've fixed everything for you."   # unparseable
            if "§6A" in prompt:
                return "**Verdict: FIX**\n1. missing Code row"
            return await super().send_message(agent_id, prompt)

    await run_workflow("job-1", client=GarbageRepairClient())
    assert not built, "an unparseable repair must never reach the builder"
    assert updates[-1]["status"] == "failed"
    assert updates[-1]["error"] == "§6A audit did not pass"


@pytest.mark.asyncio
async def test_repair_is_disabled_when_max_repair_rounds_is_zero(monkeypatch):
    """The knob restores the old fail-on-first-FIX behaviour exactly."""
    updates = _patch_common(monkeypatch)
    monkeypatch.setattr(builder, "build", lambda *a, **k: _fake_build_result())
    monkeypatch.setattr(settings, "max_repair_rounds", 0)
    repairs = []

    class FixClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            if "corrected sections and NOTHING" in prompt:
                repairs.append(1)
                return _blk("1.0", "A", "B", "x")
            if "§6A" in prompt:
                return "**Verdict: FIX**\n1. something"
            return await super().send_message(agent_id, prompt)

    await run_workflow("job-1", client=FixClient())
    assert not repairs, "no repair may be attempted when the knob is 0"
    assert updates[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_a_repair_that_breaks_bilingual_parity_is_discarded(monkeypatch):
    """A reworded cell can drop one language. The per-section gate re-runs on the
    repair rather than trusting it."""
    updates = _patch_common(monkeypatch)
    built = []
    monkeypatch.setattr(builder, "build", lambda *a, **k: built.append(1) or _fake_build_result())
    monkeypatch.setattr(settings, "max_repair_rounds", 1)

    class MonolingualRepairClient(FakeClient):
        async def send_message(self, agent_id, prompt):
            if "corrected sections and NOTHING" in prompt:
                return _blk("1.0", "СОДРЖИНА", "CONTENT", "English only text. " * 20)
            if "§6A" in prompt:
                return "**Verdict: FIX**\n1. something"
            return await super().send_message(agent_id, prompt)

    await run_workflow("job-1", client=MonolingualRepairClient())
    assert not built
    assert updates[-1]["status"] == "failed"


def test_repair_prompt_forbids_inventing_data_to_satisfy_an_issue():
    """Trap 1: a repair loop IS fabrication pressure. Told an issue is blocking,
    the cheapest way to satisfy "field X is empty" is to fill X in — the one
    failure the house rules forbid outright. Pinned so no future edit of the
    prompt quietly drops it."""
    src = inspect.getsource(_repair_sections)
    assert "NEVER invent data" in src
    assert "BLANK write-ins" in src
    assert "leave that" in src and "unfixed" in src


def test_split_repaired_tolerates_chatter_around_a_correct_document():
    """A model that wraps the right document in a sentence has still done the
    work; throwing the round away over packaging wastes it."""
    body = ("Sure — here is the corrected document.\n\n"
            + _blk("1.0", "СОДРЖИНА", "CONTENT", "нов|new one") + "\n\n"
            + _blk("2.0", "ПОТВРДА", "SIGN-OFF", "нов|new two"))
    out, reason = _split_repaired(body, _ORIG)
    assert reason.startswith("ok")
    assert out[0]["content"] == "нов|new one"


def test_split_repaired_reason_names_what_came_back():
    out, reason = _split_repaired(_blk("9.9", "X", "Y", "z"), _ORIG)
    assert out is None
    assert "9.9" in reason and "1.0" in reason


def test_text_after_the_final_end_marker_never_enters_the_document():
    """The defect this protocol exists to stop. The prompt invites the agent to
    declare an issue it could not fix, and a live repair duly appended
    "Corrected as required: added the missing Шифра | Code row ..." — which was
    built into the .docx, and the §6A auditor passed it without comment. Only
    text between a matching pair is document content."""
    body = (_blk("1.0", "A", "B", "x") + "\n\n" + _blk("2.0", "C", "D", "y")
            + "\n\n---\nCorrected as required: added the missing row. "
              "No issues remain unfixed.")
    out, reason = _split_repaired(body, _ORIG)
    assert reason.startswith("ok")
    assert [s["content"] for s in out] == ["x", "y"]
    assert not any("Corrected as required" in s["content"] for s in out)


def test_text_between_sections_is_discarded_too():
    body = (_blk("1.0", "A", "B", "x")
            + "\n\nlet me now do the second section\n\n"
            + _blk("2.0", "C", "D", "y"))
    out, reason = _split_repaired(body, _ORIG)
    assert reason.startswith("ok")
    assert [s["content"] for s in out] == ["x", "y"]


def test_section_content_may_contain_markdown_headings():
    """The delimiter must not collide with the payload. Section content
    legitimately carries Markdown headings — an annex body has its own title
    line — and a heading-based delimiter rejected a correct repair over it."""
    orig = [{"num": "1.0", "mk": "СОДРЖИНА", "en": "CONTENT",
             "content": "# Образец | Form\n[[FORM:grid]]\n~~Шифра | Code~~ ||| X"}]
    body = _section_body(orig)
    out, reason = _split_repaired(body, orig)
    assert reason.startswith("ok"), reason
    assert out[0]["content"] == orig[0]["content"]
    assert "# Образец | Form" in out[0]["content"]


# ---- partial repair ----
def test_repair_may_return_only_the_sections_it_changed():
    """Asked to fix two issues in a nine-section SOP, the model rewrote the
    sections it needed and stopped. Requiring the whole document back rejected
    that outright — and echoing nine sections invites truncation besides."""
    out, reason = _split_repaired(_blk("2.0", "ПОТВРДА", "SIGN-OFF", "поправено"), _ORIG)
    assert out is not None, reason
    assert out[0]["content"] == "тело|body one"        # untouched, kept as-is
    assert out[1]["content"] == "поправено"            # rewritten
    assert "1 of 2" in reason


def test_repair_may_return_sections_out_of_order():
    body = _blk("2.0", "X", "Y", "two") + "\n\n" + _blk("1.0", "X", "Y", "one")
    out, reason = _split_repaired(body, _ORIG)
    assert [s["content"] for s in out] == ["one", "two"], reason


def test_repair_returning_nothing_is_not_a_repair():
    out, reason = _split_repaired("I could not fix anything, sorry.", _ORIG)
    assert out is None and "no closed sections" in reason


def test_repair_may_not_return_the_same_section_twice():
    body = _blk("1.0", "X", "Y", "a") + "\n\n" + _blk("1.0", "X", "Y", "b")
    out, reason = _split_repaired(body, _ORIG)
    assert out is None and "more than once" in reason


# ---- echoed heading ----
@pytest.mark.parametrize(
    "head",
    ["# 1.0 ЦЕЛ|PURPOSE", "## 1.0 ЦЕЛ | PURPOSE", "### ЦЕЛ | PURPOSE", "## PURPOSE"],
)
def test_echoed_section_heading_is_dropped(head):
    """assemble_markdown emits the heading; the author writes one too, so every
    section came out with a doubled title — the §6A auditor flagged it on all
    nine SOP sections at once."""
    out = _drop_echoed_heading(f"{head}\nтекст|text", "1.0", "ЦЕЛ", "PURPOSE")
    assert out == "текст|text"


@pytest.mark.parametrize(
    "first",
    [
        "## 6.1 Подготовка | Preparation",   # a real subsection, not an echo
        "## Опрема | Equipment",
        "текст|text",                        # not a heading at all
    ],
)
def test_a_real_opening_heading_is_left_alone(first):
    body = f"{first}\nостаток|rest"
    assert _drop_echoed_heading(body, "6.0", "ПОСТАПКА", "PROCEDURE") == body


def test_echoed_heading_strip_only_touches_the_first_line():
    body = "текст|text\n## 1.0 ЦЕЛ | PURPOSE\nповеќе|more"
    assert _drop_echoed_heading(body, "1.0", "ЦЕЛ", "PURPOSE") == body


@pytest.mark.asyncio
async def test_a_deliberating_repair_is_nudged_once_and_still_lands(monkeypatch):
    """A stateful agent handed a long prompt sometimes spends its turn planning
    and stops — a whole nine-section SOP run died on exactly that, with no
    markers emitted. The clone still holds the context, so one nudge recovers it."""
    updates = _patch_common(monkeypatch)
    built = []
    monkeypatch.setattr(builder, "build", lambda *a, **k: built.append(1) or _fake_build_result())
    monkeypatch.setattr(settings, "max_repair_rounds", 1)
    prompts = []

    class DeliberatingClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.audits = 0

        async def send_message(self, agent_id, prompt):
            prompts.append(prompt)
            if "Output the corrected sections NOW" in prompt:
                return _blk("1.0", "СОДРЖИНА", "CONTENT", "поправено|repaired")
            if "CORRECTED document body" in prompt or "corrected sections and NOTHING" in prompt:
                return "I need to apply the fixes. Let me review the issues first."
            if "§6A" in prompt:
                self.audits += 1
                return "**Verdict: FIX**\n1. x" if self.audits == 1 else "**Verdict: PASS**"
            return await super().send_message(agent_id, prompt)

    await run_workflow("job-1", client=DeliberatingClient())
    assert any("Output the corrected sections NOW" in p for p in prompts), "nudge not sent"
    assert built, "the nudged repair must still reach the builder"
    assert updates[-1]["status"] == "done"


@pytest.mark.asyncio
async def test_a_repair_that_already_has_markers_is_not_nudged(monkeypatch):
    _patch_common(monkeypatch)
    monkeypatch.setattr(builder, "build", lambda *a, **k: _fake_build_result())
    monkeypatch.setattr(settings, "max_repair_rounds", 1)
    prompts = []

    class GoodClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.audits = 0

        async def send_message(self, agent_id, prompt):
            prompts.append(prompt)
            if "corrected sections and NOTHING" in prompt:
                return _blk("1.0", "СОДРЖИНА", "CONTENT", "поправено")
            if "§6A" in prompt:
                self.audits += 1
                return "**Verdict: FIX**\n1. x" if self.audits == 1 else "**Verdict: PASS**"
            return await super().send_message(agent_id, prompt)

    await run_workflow("job-1", client=GoodClient())
    assert not any("Output the corrected sections NOW" in p for p in prompts)
