# Pipeline unit surface: questionnaire defaulting + Markdown assembly
# (the Letta round-trips are exercised on the wwf_mass stack, not here).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import assemble_markdown, _strip_fences  # noqa: E402
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


def test_strip_fences():
    assert _strip_fences("```markdown\nhello\n```") == "hello"
    assert _strip_fences("plain") == "plain"
