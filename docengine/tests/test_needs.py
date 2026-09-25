# The [NEEDS INPUT: …] contract (app/needs.py).
#
# The rule "never invent facility specifics" was, until now, enforced only by
# repeating it in every prompt: nothing in the pipeline could tell whether an
# agent had obeyed it, and an unknown value that was quietly omitted looked
# exactly like one that was never needed. The marker is what makes a gap
# legible — visible in the document AND lifted into the job result — so these
# tests cover the half that is now code: does the extractor find what the
# agents were told to write, and does it refuse to find things that aren't
# markers.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.needs import INSTRUCTION, extract_needs, needs_summary  # noqa: E402


def _sec(num, content):
    return {"num": num, "mk": "МК", "en": "EN", "content": content}


def test_extracts_the_marker_with_the_section_it_came_from():
    out = extract_needs([
        _sec("4.0", "Материјалот се чува во [NEEDS INPUT: cold room code].|"
                    "The material is stored in [NEEDS INPUT: cold room code]."),
        _sec("6.0", "Ништо не недостасува.|Nothing missing here."),
    ])
    assert out == [{"section": "4.0", "item": "cold room code"}]


def test_the_two_language_sides_of_one_gap_are_one_question():
    """The instruction asks for the SAME wording on both sides precisely so
    this collapses — otherwise every gap is reported twice and a reader has to
    work out that the pair is one fact, not two."""
    out = extract_needs([_sec("2.0", "[NEEDS INPUT: purity limit] ||| [NEEDS INPUT: purity limit]")])
    assert out == [{"section": "2.0", "item": "purity limit"}]


def test_distinct_gaps_in_one_section_are_all_reported_in_reading_order():
    out = extract_needs([_sec("6.0",
        "Step 1 in [NEEDS INPUT: room code]. Step 2 at [NEEDS INPUT: incubation temperature].")])
    assert [n["item"] for n in out] == ["room code", "incubation temperature"]


def test_whitespace_and_case_variants_normalise():
    out = extract_needs([_sec("1.0",
        "a [needs input:   spacing   and   case  ] b [NEEDS  INPUT: spacing and case]")])
    # one gap, tidied — not two near-duplicates for a human to reconcile
    assert out == [{"section": "1.0", "item": "spacing and case"}]


def test_a_document_with_nothing_missing_reports_nothing():
    assert extract_needs([_sec("1.0", "Целосно.|Complete.")]) == []
    assert extract_needs([]) == []


def test_the_engines_own_block_markers_are_not_mistaken_for_gaps():
    """[[FORM]] / [[TABLE]] / [[FORM:grid]] are the formatter's grammar and are
    doubled; the placeholder is single-bracketed. A collision here would either
    swallow a real block or report the document's own structure as a question."""
    out = extract_needs([_sec("3.0",
        "[[FORM:grid]]\nИме ~~ Name ||| _\n[[/FORM]]\n[[TABLE]]\nA ||| B\n[[/TABLE]]")])
    assert out == []


def test_ordinary_bracketed_prose_is_not_a_gap():
    # A Markdown link and a plain bracketed aside must not become questions.
    out = extract_needs([_sec("4.0",
        "See [EU GMP Annex 1](https://example.test) and [see note 3] below.")])
    assert out == []


def test_a_malformed_marker_does_not_swallow_the_rest_of_the_line():
    """An unclosed '[' must fail to match rather than consuming the paragraph
    and reporting a sentence as the missing fact."""
    out = extract_needs([_sec("5.0",
        "[NEEDS INPUT: unclosed and then a lot of ordinary procedure text follows "
        "for the rest of this line, which must not be captured as an item")])
    assert out == []


def test_summary_names_the_first_few_and_counts_the_rest():
    needs = [{"section": str(i), "item": f"item {i}"} for i in range(1, 8)]
    s = needs_summary(needs)
    assert s.startswith("7 open question(s):")
    assert "1 item 1" in s and "(+2 more)" in s
    assert needs_summary([]) == ""


def test_the_instruction_keeps_execution_time_blanks_out_of_scope():
    """Without this carve-out the marker spreads to every signature line and
    measured-result field in the house style — which are blank BY DESIGN, and
    burying the real questions among them defeats the point of collecting
    them."""
    low = INSTRUCTION.lower()
    assert "write-in" in low
    for word in ("signature", "measured", "dates of execution"):
        assert word in low
    # and it must actually name the marker it is asking for
    assert "[NEEDS INPUT:" in INSTRUCTION
