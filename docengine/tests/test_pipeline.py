# Pipeline unit surface: questionnaire defaulting + Markdown assembly
# (the Letta round-trips are exercised on the wwf_mass stack, not here).
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import assemble_markdown, _strip_fences, _clean_section  # noqa: E402
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
