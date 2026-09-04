# docengine.app.pipeline — the merged content workflow (DOCENGINE-CANON §5):
# questionnaire answers -> section generation by the gf_ fleet -> per-section
# regulatory RAG check -> §6A audit -> bilingual Markdown assembly -> the
# formatting core (builder.py, hard PASS gate) -> registry row.
#
# Runs as an asyncio background task; ALL state transitions go through
# Postgres (db.jobs) so any worker can serve the poll.
from __future__ import annotations

import asyncio
import logging
import re

from . import builder, db
from .config import settings
from .letta import LettaClient, LettaError
from .questionnaires import QUESTIONNAIRES, apply_defaults

log = logging.getLogger("docengine.pipeline")

SOP_SECTIONS = [
    ("1.0", "ЦЕЛ", "PURPOSE"),
    ("2.0", "ПОДРАЧЈЕ НА ПРИМЕНА", "SCOPE"),
    ("3.0", "ОДГОВОРНОСТИ", "RESPONSIBILITIES"),
    ("4.0", "РЕФЕРЕНТНИ ДОКУМЕНТИ", "REFERENCE DOCUMENTS"),
    ("5.0", "ДЕФИНИЦИИ", "DEFINITIONS"),
    ("6.0", "ПОСТАПКА", "PROCEDURE"),
    ("7.0", "ЗАПИСИ", "RECORDS"),
    ("8.0", "ПОВРЗАНИ ДОКУМЕНТИ", "RELATED DOCUMENTS"),
    ("9.0", "РЕВИЗИЈА", "REVISION"),
]

_MD_FENCE = re.compile(r"^```[a-zA-Z]*\n|\n```$", re.M)

# The agents THIS module drives, and how. This is the single place that knows
# whether an agent's reply is spliced into the document (verbatim) and whether
# it is sent one prompt and read for one reply (one_shot). Both facts used to
# be declared only in fleet.yaml as `verbatim_output` / `autoclear` — a file
# that cannot see how the pipeline uses an agent — and the tests restated
# today's answer by name. A new verbatim author wired in here without the flag
# would have silently reintroduced the "note about corpus availability inside
# a controlled document" failure; a new one-shot worker without autoclear, the
# 78k-token qa-auditor timeout. test_fleet now checks fleet.yaml against this.
SOP_AUTHOR = "gf_sop_author"
ANNEX_AUTHOR = "gf_annex_author"
RACI_SPECIALIST = "gf_raci_specialist"
REG_CHECKER = "gf_reg_checker"
QA_AUDITOR = "gf_qa_auditor"
DRIVEN_AGENTS: dict[str, dict[str, bool]] = {
    SOP_AUTHOR: {"verbatim": True, "one_shot": True},
    ANNEX_AUTHOR: {"verbatim": True, "one_shot": True},
    RACI_SPECIALIST: {"verbatim": True, "one_shot": True},
    REG_CHECKER: {"verbatim": False, "one_shot": True},
    QA_AUDITOR: {"verbatim": False, "one_shot": True},
}

# Conversational lead-ins a stateful agent sometimes emits BEFORE the document
# body despite being told "body only" (observed live: "Looking at the persona
# description more carefully... Let me align..."). These must never reach the
# .docx. Matched case-insensitively at the very start of a line.
# Narrowed deliberately. These five alternatives were removed because they
# open legitimate SOP prose at least as often as agent chatter, and the strip
# is silent: "note:", "based on( the)?", "the following", "this is (my|the)",
# "below is". "Note: samples are stored at 2-8 C." and "The following
# equipment is required:" are ordinary procedure text, and losing either is a
# content-integrity defect in a controlled document. What is left is
# first-person / meta phrasing that has no place in an SOP body at all.
_PREAMBLE = re.compile(
    r"^(looking at|let me|here('s| is)|here are|i'll|i will|i have|i've|"
    r"as (requested|instructed|per)|sure[,!]|certainly|okay|alright|"
    r"understood|of course|great[,!]|let's|now,? (let|i))\b",
    re.I,
)
# A conversational lead-in is SHORT — a sentence or two. Anything bigger is
# the agent's actual output, so the stripper must not be what decides to drop
# it. Absolute cap only, deliberately: a proportional cap misfires on short
# sections, where a single legitimate lead-in line is a large share of the
# body and would be wrongly kept.
_MAX_PREAMBLE_CHARS = 400
# The first structural token of a real document body: a Markdown heading or a
# form/table marker. Everything an annex author says before this is commentary.
_STRUCT = re.compile(r"^\s*(#{1,6}\s|\[\[(FORM|TABLE))", re.M)
# A HEADERDATA block emitted by an agent inside its section body. Document
# metadata belongs to assemble_markdown alone, which prepends the authoritative
# block; build_from_md.py's parser is line-anchored on the FIRST "<!--HEADERDATA"
# it sees, so a second one either declares a conflicting version or leaks its
# remaining fields into the body as literal text. Observed live: DeepSeek
# v4-flash put one mid-body and the §6A auditor caught the version conflict.
# Line-anchored to mirror that parser exactly — and deliberately not a fail:
# the agent is answering the brief, it just doesn't own the header.
_AGENT_HEADERDATA = re.compile(r"^[ \t]*<!--HEADERDATA\b.*?-->[ \t]*$", re.M | re.S)


class QaAuditFailed(Exception):
    """The §6A auditor returned a FIX verdict (or something other than a
    clear PASS) — the document must not proceed to formatting/registration
    until the issues are addressed. Consistent with pp_verify's own hard
    PASS/FAIL gate elsewhere in this pipeline: never fabricate, fail loud."""

    def __init__(self, verdict: str, history: list[str] | None = None,
                 markdown: str = ""):
        super().__init__("§6A audit did not PASS")
        self.verdict = verdict
        # every verdict in order, so a failed job shows what repair was tried
        self.history = history or [verdict]
        # the assembled document the verdict was passed on
        self.markdown = markdown


class BilingualGap(Exception):
    """One or more sections carry only ONE language.

    pp_verify's `--require-bilingual` asks whether the WHOLE .docx contains
    Cyrillic and Latin anywhere, which a single Macedonian word in a
    forty-page English document satisfies. Every real bilingual failure this
    pipeline can produce is per-SECTION — an agent drafts section 5 in English
    only while sections 1-4 carry both — and the document-wide check passes it
    without comment. Checked here, where sections are still separate.
    """

    def __init__(self, gaps: list[str]):
        super().__init__("sections are not bilingual: " + ", ".join(gaps))
        self.gaps = gaps


class RevisionFailed(Exception):
    """A direct-edit request (run_revision) could not be turned into a new
    document — the target section doesn't exist, or the editing agent's reply
    didn't parse (see _direct_edit_sections). Distinct from QaAuditFailed:
    there is no auditor verdict here, just a request that didn't land."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class GridOverflow(Exception):
    """A block contains cells the formatter will not put in the document.

    `emit_form` reads exactly three cells per [[FORM]] row — MK label, EN
    label, value — and never looks at a fourth. Anything beyond is dropped
    silently, so a form can lose a field a human was meant to fill and still
    look complete. In an SOP the same shape is worse: `build_sop` sizes the
    table from its first row and a wider data row raises IndexError inside the
    formatter, which reaches the job as a bare "IndexError: list index out of
    range".

    Both surfaced only as opaque late failures. Job VERIFY-ANNEX-003
    (2026-08-29) failed as `verify FAILED` with every pp_verify check printing
    PASS and only the §5A fidelity line short, by one word — §5A is the right
    backstop and is untouched, but "the output is smaller than the source" is a
    poor error when the answer is "row 2 of this block has a fourth cell and
    the formatter reads three". Checked here, before the audit and the build,
    where the block can still be named.
    """

    def __init__(self, gaps: list[str]):
        super().__init__("cells the formatter would discard: " + "; ".join(gaps))
        self.gaps = gaps


# What the vendored engine actually does with a block's cells — read from
# build_from_md.py and confirmed by building each shape and diffing the tokens
# in the produced .docx, because guessing this wrong is how the first version of
# this gate came to flag documents that build perfectly:
#
#   ANNEX  [[FORM]]/[[FORM:grid]]  emit_form() reads rd[0], rd[1], rd[2] and
#          nothing else. A cell at index 3 or beyond is NEVER read, whatever the
#          other rows look like. Uniform 5-cell rows lose cells 4-5 in EVERY row
#          (verified: ExtraFourA/ExtraFiveA/ExtraFourB/ExtraFiveB all absent).
#   ANNEX  [[TABLE]]  emit_table() sizes to max(len(r)) — tolerant, loses nothing.
#   SOP    both  build_sop() takes ncol from row 0 and does not clamp, so a data
#          row WIDER than the header raises IndexError inside pp_format
#          (verified: widths 4,6,6 crash the build).
#
# So the rule is per doctype, and it is never "this row differs from its
# siblings" — that comparison flags `A ||| B` next to `C ||| D ||| E`, which
# builds with nothing lost.
_BLOCK_OPEN = re.compile(r"^\s*\[\[(FORM|TABLE)\b([^\]]*)\]\]\s*$")
_BLOCK_CLOSE = re.compile(r"^\s*(\[\[/|\[\[(?:FORM|TABLE)\b|#)")
_FORM_CELLS_READ = 3


def _blocks_in(content: str):
    """Yield (kind, rows) for each [[FORM…]]/[[TABLE]] block in a section.

    A block ends at a blank line, the next block marker, a closing [[/…]] or a
    heading — the same set parse() closes on in build_from_md.py, so what is
    counted here is what the engine will actually be handed."""
    lines = (content or "").split("\n")
    i = 0
    while i < len(lines):
        m = _BLOCK_OPEN.match(lines[i])
        if not m:
            i += 1
            continue
        kind = m.group(1)
        i += 1
        rows = []
        while i < len(lines) and lines[i].strip() and not _BLOCK_CLOSE.match(lines[i]):
            rows.append(lines[i].split("|||"))
            i += 1
        yield kind, rows


def _grid_overflow(sections: list[dict], doctype: str) -> list[str]:
    """Cells the engine would silently discard, or a width that would crash it.

    Named for the failure, not the shape: the point is content that does not
    reach the document."""
    gaps: list[str] = []
    is_sop = (doctype or "").upper() == "SOP"
    for sec in sections:
        num = sec.get("num", "?")
        for bno, (kind, rows) in enumerate(_blocks_in(sec.get("content") or ""), 1):
            if not rows:
                continue
            label = f"section {num}, [[{kind}]] block {bno}"
            if is_sop:
                # ncol comes from row 0; a wider data row indexes past the table.
                width0 = len(rows[0])
                wide = [(n, len(r)) for n, r in enumerate(rows[1:], 2) if len(r) > width0]
                if wide:
                    detail = ", ".join(f"row {n} has {w}" for n, w in wide)
                    gaps.append(
                        f"{label}: the first row sets {width0} columns but {detail}"
                        f" — in an SOP that crashes the formatter"
                    )
            elif kind == "FORM":
                # Only a NON-EMPTY overflow cell is content actually lost; a
                # trailing `||| ` is idiomatic and costs nothing.
                bad = [
                    (n, [c.strip() for c in r[_FORM_CELLS_READ:] if c.strip()])
                    for n, r in enumerate(rows, 1)
                    if any(c.strip() for c in r[_FORM_CELLS_READ:])
                ]
                if bad:
                    detail = "; ".join(
                        f"row {n} would lose {', '.join(repr(c) for c in cells)}"
                        for n, cells in bad
                    )
                    gaps.append(
                        f"{label}: a [[FORM]] row is read as "
                        f"MK-label ||| EN-label ||| value and nothing after — {detail}"
                    )
    return gaps


# Letters only. Digits, punctuation and the [[FORM]]/[[TABLE]] markers say
# nothing about language.
_CYR = re.compile(r"[Ѐ-ӿ]")
_LAT = re.compile(r"[A-Za-z]")
# TWO thresholds, deliberately, because they answer different questions. A
# single one is wrong in a way that is easy to miss: Macedonian renders longer
# than its English equivalent, so an ordinary short bilingual section sits at
# something like 52 Cyrillic / 31 Latin letters. Judged against one shared
# floor, that section is "missing English" and FAILS a perfectly good job —
# worse than the gap the check exists to close.
#
# _MIN_TOTAL_TO_JUDGE: below this much text there is nothing to be confident
# about, and a bare [[FORM:grid]], a formula or a code reference is
# legitimately language-neutral. Skip the section entirely.
_MIN_TOTAL_TO_JUDGE = 120
# _MIN_PRESENCE: above the total floor, this much of a language counts as
# present. Low on purpose — a real heading or clause clears it easily, while a
# stray acronym or unit symbol ("pH", "HPLC", "mg") does not.
_MIN_PRESENCE = 15


def _bilingual_gaps(sections: list[dict]) -> list[str]:
    """Return the numbers of sections that carry substantial text in only one
    of the two languages. Sections too short to judge are skipped — see
    _MIN_TOTAL_TO_JUDGE."""
    gaps = []
    for s in sections:
        body = s.get("content") or ""
        cyr, lat = len(_CYR.findall(body)), len(_LAT.findall(body))
        if cyr + lat < _MIN_TOTAL_TO_JUDGE:
            continue
        if cyr < _MIN_PRESENCE:
            gaps.append(f"{s.get('num', '?')} (no MK)")
        elif lat < _MIN_PRESENCE:
            gaps.append(f"{s.get('num', '?')} (no EN)")
    return gaps


# The auditor is asked for "{verdict PASS|FIX, issues: [...]}" and in practice
# announces it as "**Verdict: PASS**" after a line of preamble. Matching only a
# reply that STARTS with PASS therefore rejected genuinely passing audits: seen
# live, an audit that cleared all six checks was recorded as
# "§6A audit did not pass" and the document was never built. Allowing a bare
# leading PASS as well keeps the simple form (and the existing fakes) working.
_QA_VERDICT = re.compile(r"\bverdict\b\W{0,12}?(PASS|FIX)\b", re.I)


def _norm_head(s: str) -> str:
    return re.sub(r"[\s|·—–-]+", " ", (s or "").lower()).strip()


def _drop_echoed_heading(content: str, num: str, mk: str, en: str) -> str:
    """Remove a leading heading that just repeats the section's own identity.

    assemble_markdown emits `# <num> <MK>|<EN>` for every section, and the author
    is told to return the body with no heading line — but it writes one anyway,
    so every section came out with a doubled title. The §6A auditor caught it on
    all nine SOP sections at once ("Every major section has a duplicated heading
    line ... This repeats for all 9 sections"). Asking is not enough; this
    enforces it.

    Deliberately narrow: only the FIRST line, only if it is a heading, and only
    if it echoes this section's number or one of its titles. A body that opens on
    a real subsection heading (`## 6.1 Подготовка | Preparation` under 6.0
    ПОСТАПКА) matches none of those and is left alone."""
    lines = (content or "").split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return content
    head = lines[i].strip()
    if not re.match(r"^#{1,6}\s", head):
        return content
    text = _norm_head(re.sub(r"^#{1,6}\s*", "", head))
    if any(t and t in text for t in (_norm_head(num), _norm_head(mk), _norm_head(en))):
        return "\n".join(lines[i + 1:]).strip()
    return content


# A reg-checker finding that is routine ("nothing applies") vs one that
# actually flagged something — used only to keep the §6A prompt from burying
# a real finding under a wall of NO-FINDING lines on a clean document. See
# _reg_findings_context() and the cross-referenced note at the regulatory-
# check loop in run_workflow().
_NO_FINDING = re.compile(r"^\s*NO-FINDING\b", re.I)


def _reg_findings_context(reg_findings: list[str]) -> str:
    """Render the per-section regulatory-checker findings as EXTRA CONTEXT for
    the §6A auditor prompt — informational only, not a gate (see the note at
    the regulatory-check loop in run_workflow() for why this stays advisory).
    Routine NO-FINDING sections are omitted so a long clean document doesn't
    bury the section(s) that actually flagged something; if every section
    came back clean, say that plainly instead of an empty/misleading block."""
    flagged = [f for f in reg_findings if not _NO_FINDING.search(f.split("]", 1)[-1])]
    if not flagged:
        return "REGULATORY CHECK: no section flagged a conflict or gap.\n\n"
    return (
        "REGULATORY CHECK (per-section, informational — use your own judgement "
        "on whether any of this should factor into your verdict):\n"
        + "\n".join(flagged) + "\n\n"
    )


def _qa_audit_passed(verdict: str) -> bool:
    """True only on an unambiguous PASS.

    Fail-closed on purpose, in three ways: an empty reply fails, a reply with no
    recognisable verdict fails, and a reply carrying BOTH tokens fails. This gate
    is what stands between a draft and a formatted controlled document, so
    "probably fine" has to count as not passing."""
    t = (verdict or "").strip()
    if not t:
        return False
    found = {m.group(1).upper() for m in _QA_VERDICT.finditer(t)}
    if found:
        return found == {"PASS"}
    return t.upper().startswith("PASS")


def _strip_fences(text: str) -> str:
    return _MD_FENCE.sub("", text or "").strip()


def _clean_section(text: str, structured: bool = False) -> str:
    """Strip code fences AND any leading agent commentary from a section body.

    structured=True (annex/form bodies, which always contain a heading or a
    [[FORM]]/[[TABLE]] marker): drop everything before the first structural
    token — anything prior is preamble. structured=False (SOP prose sections,
    legitimately plain text with no heading): only peel conversational lead-in
    lines off the top, so real prose is never lost."""
    t = _strip_fences(text)
    if not t:
        return t
    # Drop any agent-emitted HEADERDATA wherever it sits. Done before the
    # structural-token search because a block placed AFTER the first heading
    # survives that search untouched, which is exactly where it was seen.
    t = _AGENT_HEADERDATA.sub("", t).strip()
    if not t:
        return t
    if structured:
        m = _STRUCT.search(t)
        if m:
            return t[m.start():].strip()
    # peel leading conversational lines (and the blank lines between them)
    lines = t.split("\n")
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s == "" or _PREAMBLE.match(s):
            i += 1
            continue
        break
    cleaned = "\n".join(lines[i:]).strip() or t
    # Bound the strip, and SAY when it fires. The §5A fidelity check compares
    # the built .docx against this already-cleaned text, so anything removed
    # here is invisible to the one safeguard meant to catch content
    # impoverishment. A removal past the absolute cap is not a lead-in, so the
    # original is kept and the section goes through with the (harmless) chatter
    # rather than silently losing procedure text.
    #
    # Absolute cap ONLY — a proportional one was tried and dropped, because on
    # a short section a single legitimate lead-in line is a large share of the
    # body and would be wrongly kept. Note this path is not reached in
    # structured mode when a heading/[[FORM]] marker was found: there the
    # boundary is unambiguous and the strip returns above, uncapped.
    removed = len(t) - len(cleaned)
    if removed > 0:
        too_big = removed > _MAX_PREAMBLE_CHARS
        log.info("preamble strip removed %d/%d chars%s", removed, len(t),
                 " — REFUSED (too large to be a lead-in), keeping original" if too_big else "")
        if too_big:
            return t
    return cleaned


def _brief(questionnaire_key: str, answers: dict, meta: dict | None = None) -> str:
    """Render the questionnaire answers for an authoring agent.

    Two clarifications are not optional. Several option labels carry a
    parenthesised EU GMP clause — "Version (4.3)", "Doc ID (EU GMP 4.2)",
    "Date (4.8)" — and a model reading those as field VALUES writes a form whose
    version says 4.3. That happened live, and the §6A auditor's objection was the
    right one: someone could sign off against the wrong revision. So say what the
    parentheses are, and state the document's real identity instead of leaving
    the agent to infer it."""
    lines = [f"Questionnaire: {questionnaire_key}"]
    if meta:
        lines += [
            "Document identity (authoritative — use these, do not invent or "
            "copy numbers out of the field list below):",
            f"- code: {meta.get('code', '')}",
            f"- version: {meta.get('version', '1.0')}",
        ]
    for k, v in answers.items():
        lines.append(f"- {k}: {', '.join(v) if isinstance(v, list) else v}")
    lines.append(
        "NOTE: a number in parentheses after a field name is the EU GMP clause "
        "that requires the field (e.g. 'Version (4.3)' means clause 4.3). It is "
        "NEVER the field's value. Identification fields such as version, date "
        "and batch are blank write-ins unless given above."
    )
    return "\n".join(lines)


def _section_body(sections: list[dict]) -> str:
    """The document body an authoring agent is allowed to see and rewrite,
    WITHOUT the HEADERDATA block. Document metadata is never handed to an agent:
    it owns none of it, and an agent-emitted header is a defect this pipeline
    already had to strip once.

    Sections are delimited by an explicit sentinel rather than by the document's
    own `# num MK|EN` headings. That distinction matters: section CONTENT
    legitimately contains Markdown headings — an annex body carries its own
    title line — so a heading-based delimiter cannot tell the protocol from the
    payload. Seen live: a repair that correctly added the one row the auditor
    asked for was rejected because the body it faithfully reproduced contained
    `# Образец ...`. The sentinel cannot collide with document text."""
    return "\n\n".join(
        f"<<<PP-SECTION {s['num']}|{s['mk']}|{s['en']}>>>\n"
        f"{s['content'].strip()}\n"
        f"<<<PP-END {s['num']}>>>"
        for s in sections
    )


# Sections are OPENED and CLOSED. Only text between a matching pair becomes
# document content; everything outside is discarded. That is what keeps an
# agent's sign-off out of a controlled document — the previous version, which
# only opened sections, let a repair append "Corrected as required: added the
# missing Шифра | Code row ... All other content left byte for byte unchanged."
# to the end of the body, and it was built into the .docx (the §6A auditor
# passed it without comment). The prompt still invites the agent to declare an
# unfixable issue; it now does so outside the closing marker, where it can be
# logged without becoming part of the record.
MARK_OPEN = "<<<PP-SECTION"


_SECTION_BLOCK = re.compile(
    r"^<<<PP-SECTION[ \t]+([^|>\s]+)[^>\n]*>>>[ \t]*\n(.*?)^<<<PP-END[ \t]+\1[ \t]*>>>[ \t]*$",
    re.M | re.S,
)
_SECTION_OPEN = re.compile(r"^<<<PP-SECTION[ \t]+([^|>\s]+)[^>\n]*>>>[ \t]*$", re.M)


def _split_repaired(body: str, original: list[dict]) -> tuple[list[dict] | None, str]:
    """Merge a repair reply into the original sections. Returns (sections,
    reason); sections is None when the reply cannot be trusted.

    The agent returns ONLY the sections it changed. Anything it leaves out keeps
    its original content. Requiring the whole document back does not survive a
    real SOP: asked to fix two issues in a nine-section document, the model
    rewrote the sections it needed and stopped — reasonable behaviour that the
    all-or-nothing protocol rejected outright, and echoing nine full sections
    invites truncation on top of costing a fortune in tokens.

    Still strict about what a returned section may be: it must be one of the
    originals (no invented sections), closed by its end marker, non-empty, and
    sent at most once. Numbering and titles are carried from the originals, so a
    repair can only rewrite bodies. Text outside a marker pair — preamble,
    commentary, an unfixable-issue note — is discarded."""
    by_num = {s["num"]: i for i, s in enumerate(original)}
    blocks = [(m.group(1), m.group(2)) for m in _SECTION_BLOCK.finditer(body)]
    if not blocks:
        opened = [m.group(1) for m in _SECTION_OPEN.finditer(body)]
        return None, f"no closed sections in the reply (open markers seen: {opened[:12]})"

    seen: set[str] = set()
    out = [dict(s) for s in original]
    changed = []
    for num, content in blocks:
        if num not in by_num:
            return None, f"section {num!r} is not part of this document {sorted(by_num)}"
        if num in seen:
            return None, f"section {num} returned more than once"
        seen.add(num)
        content = content.strip()
        if not content:
            return None, f"section {num} came back empty"
        out[by_num[num]]["content"] = content
        changed.append(num)
    return out, f"ok ({len(changed)} of {len(original)} sections rewritten: {changed})"


async def _repair_sections(
    client: LettaClient, author: str, sections: list[dict], audit: str, job_id: str,
    ctx=None,
) -> list[dict] | None:
    """Hand the auditor's issues back to the authoring agent, once.

    Runs on an ephemeral clone for the same reason the reg-checker does: a
    persistent agent carries every prior turn into the next prompt.

    The no-invention clause is not boilerplate. A repair loop is fabrication
    pressure by construction — told an issue is blocking, the cheapest way for a
    model to satisfy "field X is empty" is to fill X in. In a GMP document that
    is the one failure that matters, so the instruction is explicit that a blank
    stays blank and an unresolvable issue stays unresolved. The §6A gate then
    fails the job honestly, which is the correct outcome."""
    from .fleet import spawn_ephemeral  # late import: fleet needs live Letta

    # autoclear=False: this clone gets a second turn (the nudge below) if the
    # first comes back with no section markers. The author's own fleet.yaml
    # flag is autoclear=true for its normal one-shot per-section use; left on
    # here it wipes the first turn's context (the whole document, the issues)
    # before the nudge is composed, so the nudge runs with nothing to act on.
    tmp_id = await spawn_ephemeral(client, author, f"fix_{job_id[:8]}", ctx=ctx, autoclear=False)
    try:
        reply = await client.send_message(
            tmp_id,
            "A §6A reviewer raised the issues below against this document. "
            "Reply with the corrected sections and NOTHING else — no plan, no "
            "commentary, no explanation of what you are about to do. Your reply "
            "is parsed by a machine, not read by a person.\n\n"
            "Rules:\n"
            "- Return ONLY the sections you actually changed. Leave every other "
            "section out entirely — it is kept exactly as it is. Do not echo the "
            "whole document.\n"
            "- Give each returned section in full, wrapped in its original "
            "'<<<PP-SECTION ...>>>' and '<<<PP-END <number>>>>' marker lines, "
            "reproduced unchanged. They delimit the document for reassembly and "
            "are not part of it.\n"
            "- ONLY text between a matching pair becomes the document. Put any "
            "remark, summary of what you changed, or issue you could not fix "
            "AFTER the final '<<<PP-END ...>>>' line — never inside a section.\n"
            "- Change only what the issues require; leave everything else byte "
            "for byte as it is.\n"
            "- NEVER invent data to satisfy an issue. Facility specifics, "
            "measured values, dates, names and signatures stay BLANK write-ins. "
            "If an issue cannot be fixed without inventing something, leave that "
            "one unfixed and say so after the final marker.\n"
            "- Do NOT emit a <!--HEADERDATA--> block; you do not own the header.\n"
            "- Output the document body first, with no preamble.\n\n"
            f"ISSUES:\n{audit.strip()}\n\n"
            f"DOCUMENT BODY:\n{_section_body(sections)}",
        )
        # A stateful agent handed a long prompt sometimes spends its turn
        # deliberating and stops: "I need to apply the fixes. Let me review the
        # issues and determine which sections I actually changed." — a whole
        # nine-section SOP run died on exactly that, with no markers emitted at
        # all. The clone still holds the context, so one blunt nudge is nearly
        # free and asks only for the output it already worked out.
        if MARK_OPEN not in (reply or ""):
            log.info("repair reply had no section markers — nudging once")
            reply = await client.send_message(
                tmp_id,
                "Output the corrected sections NOW: only the "
                f"{MARK_OPEN}...>>> / <<<PP-END n>>> blocks for the sections you "
                "changed, nothing before or after them. No commentary, no plan, "
                "no explanation.",
            )
    finally:
        # same rationale as the reg-checker clone: cleanup must never abort a job
        try:
            await client.delete_agent(tmp_id)
        except Exception as e:  # noqa: BLE001
            log.warning("failed to delete ephemeral repairer %s: %s", tmp_id, e)
    repaired, reason = _split_repaired(_strip_fences(reply), sections)
    if repaired is not None:
        log.info("repair accepted: %s", reason)
    if repaired is None:
        # Say what came back, not just that it was rejected — a silent "unusable"
        # is impossible to act on when it happens in production.
        log.warning("repair reply unusable (%s); first line: %r",
                    reason, (reply or "").strip().split("\n")[0][:160])
    return repaired


async def _direct_edit_sections(
    client: LettaClient, author: str, sections: list[dict], instruction: str, job_id: str,
    ctx=None, section_num: str | None = None,
) -> tuple[list[dict] | None, str]:
    """Apply a person's direct-edit request (chat instruction or a preset) to
    one section or the whole document, on an ephemeral clone of the section's
    own author — the same machinery _repair_sections uses for the §6A loop:
    autoclear off (this clone may get a second, nudge turn), the same
    never-invent instruction, the same marker protocol so a reply can only
    ever replace the sections it names.

    Unlike _repair_sections there is no reviewer verdict downstream — the
    caller (run_revision) asked for this change directly, and whatever comes
    back that parses is rebuilt and re-verified immediately. What this
    function still guards: an unparseable reply changes nothing; an invented
    fact is refused by the same rule that refuses one for an auditor's issue;
    and when the caller scoped the request to one section, a reply that also
    touches another is rejected rather than silently widened past what was
    asked."""
    from .fleet import spawn_ephemeral

    scope_line = (
        f"ONLY section {section_num} may change in your reply — every other "
        "section must be left out entirely, not merely unchanged.\n"
        if section_num else ""
    )
    tmp_id = await spawn_ephemeral(client, author, f"rev_{job_id[:8]}", ctx=ctx, autoclear=False)
    try:
        reply = await client.send_message(
            tmp_id,
            "A person reviewing this document asked for the change below. "
            "Reply with the corrected sections and NOTHING else — no plan, no "
            "commentary, no explanation of what you are about to do. Your reply "
            "is parsed by a machine, not read by a person.\n\n"
            f"{scope_line}"
            "Rules:\n"
            "- Return ONLY the sections you actually changed. Leave every other "
            "section out entirely — it is kept exactly as it is. Do not echo the "
            "whole document.\n"
            "- Give each returned section in full, wrapped in its original "
            "'<<<PP-SECTION ...>>>' and '<<<PP-END <number>>>>' marker lines, "
            "reproduced unchanged. They delimit the document for reassembly and "
            "are not part of it.\n"
            "- ONLY text between a matching pair becomes the document. Put any "
            "remark, summary of what you changed, or request you could not "
            "satisfy AFTER the final '<<<PP-END ...>>>' line — never inside a "
            "section.\n"
            "- Change only what the request below requires; leave everything "
            "else byte for byte as it is.\n"
            "- NEVER invent data to satisfy the request. Facility specifics, "
            "measured values, dates, names and signatures stay BLANK write-ins. "
            "If the request cannot be met without inventing something, leave "
            "that part unmet and say so after the final marker.\n"
            "- Do NOT emit a <!--HEADERDATA--> block; you do not own the header.\n"
            "- Output the document body first, with no preamble.\n\n"
            f"REQUEST:\n{instruction.strip()}\n\n"
            f"DOCUMENT BODY:\n{_section_body(sections)}",
        )
        if MARK_OPEN not in (reply or ""):
            log.info("direct-edit reply had no section markers — nudging once")
            reply = await client.send_message(
                tmp_id,
                "Output the corrected sections NOW: only the "
                f"{MARK_OPEN}...>>> / <<<PP-END n>>> blocks for the sections you "
                "changed, nothing before or after them. No commentary, no plan, "
                "no explanation.",
            )
    finally:
        try:
            await client.delete_agent(tmp_id)
        except Exception as e:  # noqa: BLE001
            log.warning("failed to delete ephemeral editor %s: %s", tmp_id, e)
    body = _strip_fences(reply)
    if section_num:
        # A reply naming a section outside the caller's scope is not "close
        # enough" — reject it rather than let the edit widen past what was
        # asked for.
        named = {m.group(1) for m in _SECTION_OPEN.finditer(body or "")}
        outside = sorted(named - {section_num})
        if outside:
            return None, f"reply touched section(s) outside the requested scope: {outside}"
    revised, reason = _split_repaired(body, sections)
    if revised is not None:
        log.info("direct edit accepted: %s", reason)
    else:
        log.warning("direct edit reply unusable (%s); first line: %r",
                    reason, (reply or "").strip().split("\n")[0][:160])
    return revised, reason


def _reject_headerdata_breakers(field: str, value) -> None:
    """A HEADERDATA field value must never contain the block terminator or a
    line break. A literal "-->" would be mistaken for the HEADERDATA block's
    own terminator by build_from_md.py's parser, truncating the header and
    leaking the remaining fields into the document body. An embedded
    newline/carriage-return is the same class of attack one level down:
    build_from_md.py's parse() reads every line between the markers as its
    own line-anchored "key: value" pair, so a value containing e.g.
    "portrait\ncode: SOP-FORGED\nversion: 9.9" injects forged fields that
    land AFTER (and therefore win over) the real ones — letting a single
    crafted request make the built .docx's printed code/version diverge from
    the registry row this same pipeline writes from the caller's original
    metadata. Reject rather than silently strip/sanitize — fail loud, never
    ship a corrupted controlled document.
    """
    if not value:
        return
    s = str(value)
    if "-->" in s:
        raise ValueError(f"meta.{field} may not contain '-->' (breaks the HEADERDATA block terminator)")
    if "\n" in s or "\r" in s:
        raise ValueError(f"meta.{field} may not contain a line break (would inject forged HEADERDATA fields)")


def assemble_markdown(meta: dict, sections: list[dict]) -> str:
    """Assemble the HEADERDATA block + section bodies into engine Markdown."""
    for _k in ("title_mk", "title_en", "code", "version", "doctype", "orient"):
        _reject_headerdata_breakers(_k, meta.get(_k))
    hd = (
        "<!--HEADERDATA\n"
        f"mk_title: {meta['title_mk']}\n"
        f"en_title: {meta['title_en']}\n"
        f"code: {meta['code']}\n"
        f"version: {meta.get('version', '1.0')}\n"
        f"doctype: {meta['doctype']}\n"
        f"orient: {meta.get('orient', 'portrait')}\n"
        "-->\n"
    )
    body = []
    for s in sections:
        body.append(f"# {s['num']} {s['mk']}|{s['en']}")
        body.append(s["content"].strip())
        body.append("")
    return hd + "\n".join(body)


async def run_workflow(job_id: str, client: LettaClient | None = None) -> None:
    """The full Mode-A + Mode-B pipeline for one job. Never raises: every
    failure lands in the job row as status=failed.

    KNOWN GAP (documented, not fixed here — audit LOW ITEM 3): this function
    makes roughly 20-40 sequential AI calls for a single job (one per SOP
    section, one per-section regulatory check, one §6A audit per repair
    round, plus repair calls) with no retry and no per-section checkpointing.
    A transient failure late in the run (a Letta timeout on section 8 of 9,
    say) is caught by the except clauses below and recorded as a normal
    job failure — correct, but it discards all the work already done, and a
    retry of the same job starts over from section 1. Real checkpointing
    (persisting completed sections/findings so a retry resumes instead of
    restarting) is a genuine feature — a job-resumption model, storage for
    partial state, etc. — not a mechanical fix, so it is intentionally left
    for a dedicated pass rather than attempted piecemeal here."""
    client = client or LettaClient()
    # Bound up front so every except clause below can persist whatever the job
    # had reached. They are the job's diagnostics, and a handler that raises
    # NameError while recording a failure loses exactly the evidence the
    # failure was worth having.
    reg_findings: list[str] = []
    audits: list[str] = []
    sections: list[dict] = []
    markdown = ""
    try:
        job = await db.job_get(job_id)
        p = job["payload"]
        qkey = p["questionnaire"]
        meta = p["meta"]
        answers = apply_defaults(qkey, p.get("answers", {}))
        doctype = QUESTIONNAIRES[qkey]["doctype"]
        meta["doctype"] = doctype
        brief = _brief(qkey, answers, meta)
        await db.job_update(job_id, status="running", stage="generate")

        # late import: fleet needs live Letta
        from .fleet import agent_datasets, ensure_fleet_ctx, spawn_ephemeral

        ctx = await ensure_fleet_ctx(client)
        agents = ctx.agents
        reg_corpora = agent_datasets(REG_CHECKER)

        # ---- section generation ----
        if doctype == "SOP":
            for num, mk, en in SOP_SECTIONS:
                author = agents[RACI_SPECIALIST] if num == "3.0" else agents[SOP_AUTHOR]
                text = await client.send_message(
                    author,
                    f"Draft ONLY section {num} {mk}|{en} of the SOP "
                    f"'{meta['title_mk']} | {meta['title_en']}' (code {meta['code']}). "
                    f"Content brief:\n{brief}\n\n"
                    "Return ONLY the bilingual Markdown body — no heading line, no code "
                    "fences, and NO commentary, preamble, or explanation of what you are "
                    "doing. Your entire reply is inserted verbatim into the document. "
                    "Unknown facility specifics stay as blank fields.",
                )
                sections.append({
                    "num": num, "mk": mk, "en": en,
                    "content": _drop_echoed_heading(_clean_section(text), num, mk, en),
                })
                await db.job_update(job_id, stage=f"generate {num}")
        else:
            text = await client.send_message(
                agents[ANNEX_AUTHOR],
                f"Design the {doctype} '{meta['title_mk']} | {meta['title_en']}' "
                f"(code {meta['code']}). Content brief:\n{brief}\n\n"
                "Return ONLY the bilingual Markdown body, using [[FORM:grid]] for the "
                "metadata block and [[TABLE]] for data grids. Blank write-in values. "
                "NO commentary, preamble, or explanation — your entire reply is inserted "
                "verbatim into the document.\n"
                "Do NOT emit a <!--HEADERDATA--> block: the document header is added "
                "around your output and a second one conflicts with it. Do NOT use the "
                "SOP 9-section numbers (1 ЦЕЛ, 6 ПОСТАПКА, ...) — that structure is for "
                "SOPs only; number any headings you need from 1 upward, or title them by "
                "intent. Keep every [[FORM:grid]] row to the same column count.",
            )
            sections.append(
                {"num": "1.0", "mk": "СОДРЖИНА", "en": "CONTENT",
                 "content": _drop_echoed_heading(
                     _clean_section(text, structured=True), "1.0", "СОДРЖИНА", "CONTENT")}
            )

        # ---- per-section regulatory check ----
        # Each section gets its OWN short-lived agent (spawn_ephemeral), used
        # for exactly one exchange then deleted. A single persistent agent
        # accumulates every prior section + retrieved passage into its next
        # turn's prompt, so a 9-section SOP reliably blows the model's context
        # window by the last section or two (observed live, twice, including
        # against a freshly-created agent) — isolating each check per-section
        # keeps the prompt size constant regardless of section count.
        #
        # NOTE on reg_findings and gating (cross-ref: the §6A audit prompt
        # below, where reg_findings is consumed): a per-section CONFLICT or
        # GAP finding here does NOT block the job and is not itself checked
        # against any pass/fail gate — it is folded into the §6A auditor's
        # prompt as additional context (below) so the AI auditor can decide
        # whether to raise it, but the auditor is free to PASS a document
        # despite an open regulatory finding. That is a real gap relative to
        # this pipeline's other gates (the §6A PASS gate itself, pp_verify's
        # PASS gate, the bilingual gate), all of which are hard-enforced.
        # Whether findings SHOULD hard-block is a product decision this
        # comment deliberately does not make — the regulatory-checker's
        # false-positive rate is unknown, and a hard gate here could break
        # legitimate document generation on a noisy checker. A future editor
        # who wants to change this should make it a deliberate call, not a
        # side effect of an unrelated change.
        await db.job_update(job_id, stage="regulatory-check")
        for s in sections:
            await db.job_update(job_id, stage=f"regulatory-check {s['num']}")
            tmp_id = await spawn_ephemeral(
                client, REG_CHECKER, f"{job_id[:8]}_{s['num'].replace('.', '')}", ctx=ctx
            )
            try:
                finding = await client.send_message(
                    tmp_id,
                    f"Check this drafted section {s['num']} of {meta['code']} against the "
                    f"regulatory corpus — call ragflow_search on the datasets "
                    f"{', '.join(reg_corpora)}. Cite only retrieved passages; say "
                    f"NO-FINDING if nothing applies.\n\n{s['content']}",
                )
            finally:
                # Broad catch on purpose: cleanup of a throwaway clone must
                # never abort the job — delete_agent can also raise plain
                # httpx transport errors (ReadTimeout etc.), not just
                # LettaError, and an orphan is recoverable while a failed job
                # isn't. Recoverable BECAUSE fleet._sweep_orphans now exists:
                # the next ensure_fleet pass deletes any gf_*_tmp_* clone older
                # than a job could legally be. This comment used to make that
                # claim when nothing implemented it.
                try:
                    await client.delete_agent(tmp_id)
                except Exception as e:  # noqa: BLE001
                    log.warning("failed to delete ephemeral reg-checker %s: %s", tmp_id, e)
            reg_findings.append(f"[{s['num']}] {finding.strip()}")

        # ---- per-section bilingual gate ----
        # Deliberately BEFORE the §6A audit and the build: both of those see
        # the assembled document, where pp_verify's document-wide
        # --require-bilingual is satisfied by any Cyrillic anywhere. Fail here,
        # while the sections are still separable and the message can name which
        # one is monolingual.
        await db.job_update(job_id, stage="bilingual-check")
        gaps = _bilingual_gaps(sections)
        if gaps:
            raise BilingualGap(gaps)

        # Structural gate, same reasoning and the same position as the
        # bilingual one: a ragged [[FORM:grid]] silently loses its overflow
        # cells in the packer, and the only thing downstream that notices is
        # §5A fidelity — which can only report that the document came out
        # smaller than its source. Caught here, the message names the block.
        await db.job_update(job_id, stage="structure-check")
        overflow = _grid_overflow(sections, doctype)
        if overflow:
            raise GridOverflow(overflow)

        # ---- §6A audit ----
        # A FIX verdict is not the end: the auditor returns concrete, actionable
        # issues ("add the ~~Шифра | Code~~ row ... after adding it the document
        # is PASS"), and before this loop the pipeline discarded them and failed
        # the job. Most first-pass failures are ordinary drafting variance, so
        # one hand-back converges them. The gate itself is NOT relaxed —
        # _qa_audit_passed still has to return True on the final verdict; repair
        # only buys more attempts at earning it.
        await db.job_update(job_id, stage="qa-audit")
        author = SOP_AUTHOR if doctype == "SOP" else ANNEX_AUTHOR
        markdown = assemble_markdown(meta, sections)
        # Cross-ref: the regulatory-check loop above computes reg_findings and
        # explains there why it is advisory context here rather than a hard
        # gate. Folded into the prompt (not the pass/fail mechanics) so the AI
        # auditor at least has visibility into what the regulatory-checker
        # found and can choose to raise it as an issue itself.
        reg_context = _reg_findings_context(reg_findings)
        for attempt in range(max(0, settings.max_repair_rounds) + 1):
            audit = await client.send_message(
                agents[QA_AUDITOR],
                "Run the §6A review on this assembled document Markdown. "
                "Return verdict PASS or FIX with issues.\n\n"
                "SCOPE: review the CONTENT. The `<!--HEADERDATA-->` block and the "
                "`# <number> <MK>|<EN>` section heading lines are emitted by the "
                "formatter in canonical form — they are not the author's and not "
                "yours to restyle. Do not raise issues about their spacing, level "
                "or punctuation; no author can act on those and the document "
                "cannot pass.\n\n" + reg_context + markdown,
            )
            audits.append(audit)
            if _qa_audit_passed(audit) or attempt >= settings.max_repair_rounds:
                break

            await db.job_update(job_id, stage=f"qa-repair {attempt + 1}")
            repaired = await _repair_sections(client, author, sections, audit, job_id, ctx=ctx)
            if repaired is None:
                log.warning("job %s repair %d unusable — failing on the audit", job_id, attempt + 1)
                break
            # A repair can break parity (dropping one language while rewording a
            # cell). Re-run the same per-section gate rather than trusting it.
            gaps = _bilingual_gaps(repaired)
            if gaps:
                log.warning("job %s repair %d broke bilingual parity %s — discarded",
                            job_id, attempt + 1, gaps)
                break
            sections = repaired
            markdown = assemble_markdown(meta, sections)

        if not _qa_audit_passed(audits[-1]):
            raise QaAuditFailed(audits[-1], audits, markdown)

        # ---- format + verify (hard gate) ----
        await db.job_update(job_id, stage="format")
        # H14 — builder.build is fully synchronous (docx render + verify, tens
        # of seconds). Called bare it blocked the event loop for the whole
        # build, stalling every other request this worker was serving,
        # including the /workflows/{jid} polls this very job depends on.
        # main.py's direct_build already did this correctly.
        result = await asyncio.to_thread(
            builder.build, markdown, settings.out_dir, meta["code"]
        )
        did = await db.document_create(
            job_id,
            {
                "code": meta["code"], "doctype": doctype,
                "title_mk": meta["title_mk"], "title_en": meta["title_en"],
                "version": meta.get("version", "1.0"),
                "path": str(result.path), "bytes": result.bytes,
                "verify": result.verify_report,
            },
        )
        await db.job_update(
            job_id, status="done", stage="done",
            result={
                "document_id": did,
                "markdown": markdown,
                # Structured, not just the assembled string — a later direct
                # edit (run_revision) targets one section by number and must
                # not re-derive section boundaries by re-parsing the rendered
                # Markdown. `meta` (with doctype filled in, unlike the raw
                # payload) travels with it for the same reason.
                "sections": sections,
                "meta": meta,
                "verify": result.verify_report,
                "regulatory": reg_findings,
                "qa_audit": audits[-1],
                # Never let a repaired document read as one that passed first
                # time. Every verdict in order, and how many hand-backs it took.
                "qa_audit_history": audits,
                "qa_repair_rounds": len(audits) - 1,
                "bytes": result.bytes,
            },
        )
    except builder.VerifyFailed as e:
        # The verify report alone is not enough to act on. §5A fidelity in
        # particular only says the document is smaller than its source, and
        # without the source there is nothing to compare it against — job
        # VERIFY-ANNEX-003 (2026-08-29) failed exactly this way and its input
        # could not be recovered afterwards. Persist what the auditor saw, the
        # same way QaAuditFailed already does.
        log.error("job %s verify FAILED", job_id)
        await db.job_update(job_id, status="failed", error="verify FAILED",
                            result={"verify": e.report, "markdown": markdown,
                                    "qa_audit_history": audits,
                                    "regulatory": reg_findings})
    except QaAuditFailed as e:
        log.error("job %s §6A audit did not pass", job_id)
        await db.job_update(job_id, status="failed", error="§6A audit did not pass",
                            result={"qa_audit": e.verdict,
                                    "qa_audit_history": e.history,
                                    "qa_repair_rounds": len(e.history) - 1,
                                    # the document the auditor actually judged —
                                    # without it a FIX verdict cannot be checked
                                    "markdown": e.markdown,
                                    "regulatory": reg_findings})
    except GridOverflow as e:
        log.error("job %s grid overflow: %s", job_id, e.gaps)
        await db.job_update(job_id, status="failed", error=str(e)[:500],
                            result={"grid_overflow": e.gaps, "sections": sections,
                                    "regulatory": reg_findings})
    except BilingualGap as e:
        log.error("job %s bilingual gap: %s", job_id, e.gaps)
        # Persist the sections, exactly as the structure gate above does. Both
        # gates fire at the same point for the same reason — the sections are
        # still separable — and both name a section the reader then wants to
        # look at. Without them the only way to see what the gate objected to
        # was to re-run the whole generation, which is not reproducible: the
        # agents do not produce the same draft twice.
        await db.job_update(job_id, status="failed",
                            error="sections are not bilingual: " + ", ".join(e.gaps),
                            result={"bilingual_gaps": e.gaps, "sections": sections,
                                    "regulatory": reg_findings})
    except LettaError as e:
        log.error("job %s letta error: %s", job_id, e)
        await db.job_update(job_id, status="failed", error=f"letta: {e}")
    except Exception as e:  # noqa: BLE001 — job must record any failure
        log.exception("job %s failed", job_id)
        # Some exceptions (notably httpx.ReadTimeout) stringify to "" — always
        # record the type name so the job row never shows a blank error.
        detail = str(e).strip() or repr(e)
        await db.job_update(job_id, status="failed", error=f"{type(e).__name__}: {detail}"[:500])
    finally:
        # This LettaClient (whether passed in or created above) is scoped to
        # this one job — nothing else holds a reference to it once
        # run_workflow returns. Its pooled httpx.AsyncClient (see letta.py)
        # must be closed here or the connection/file descriptor it holds
        # outlives the job that opened it, across every job this worker runs.
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001 — cleanup must never mask a job result
            log.warning("job %s: failed to close Letta client", job_id, exc_info=True)


async def run_revision(job_id: str, client: LettaClient | None = None) -> None:
    """A direct-edit follow-up on a document run_workflow already built — a
    chat instruction or a preset, scoped to one section or the whole
    document. `job.payload` for this kind of job is
    {source_document_id, sections, meta, instruction, section_num}: `sections`
    and `meta` are the exact structures run_workflow's own "done" result
    stored, carried forward by the caller rather than re-derived here by
    re-parsing rendered Markdown.

    Runs _direct_edit_sections (the same repair-clone machinery the §6A audit
    loop uses) then rebuilds and re-verifies exactly as run_workflow does.
    There is deliberately no accept/reject step in between: the request was
    for a direct edit, so a parseable, non-fabricating reply plus the hard
    pp_verify PASS gate together ARE the new document. What is not
    deliberate — every revision becomes a NEW row in db.documents, never an
    edit of the one it started from. That costs nothing to keep and it means
    the source document, the instruction that was given, and the document it
    produced all stay on the record, whether or not anyone downstream ever
    adds a review step of their own."""
    client = client or LettaClient()
    sections: list[dict] = []
    markdown = ""
    try:
        job = await db.job_get(job_id)
        p = job["payload"]
        meta = dict(p["meta"])
        sections = [dict(s) for s in p["sections"]]
        instruction = p["instruction"]
        section_num = p.get("section_num") or None
        doctype = meta["doctype"]
        await db.job_update(job_id, status="running", stage="revise")

        # late import: fleet needs live Letta
        from .fleet import ensure_fleet_ctx

        ctx = await ensure_fleet_ctx(client)
        author = SOP_AUTHOR if doctype == "SOP" else ANNEX_AUTHOR

        if section_num and not any(s["num"] == section_num for s in sections):
            raise RevisionFailed(f"no section {section_num} on this document")

        await db.job_update(job_id, stage="editing" + (f" {section_num}" if section_num else ""))
        revised, reason = await _direct_edit_sections(
            client, author, sections, instruction, job_id, ctx=ctx, section_num=section_num,
        )
        if revised is None:
            raise RevisionFailed(reason)

        # Same two structural gates run_workflow enforces before it will build
        # anything, for the same reason: a revision can drop a language out of
        # a section, or widen a [[FORM]]/[[TABLE]] row past what the packer
        # will place, just as easily as a first draft can.
        gaps = _bilingual_gaps(revised)
        if gaps:
            raise BilingualGap(gaps)
        overflow = _grid_overflow(revised, doctype)
        if overflow:
            raise GridOverflow(overflow)

        sections = revised
        markdown = assemble_markdown(meta, sections)

        await db.job_update(job_id, stage="format")
        result = await asyncio.to_thread(
            builder.build, markdown, settings.out_dir, meta["code"]
        )
        did = await db.document_create(
            job_id,
            {
                "code": meta["code"], "doctype": doctype,
                "title_mk": meta["title_mk"], "title_en": meta["title_en"],
                "version": meta.get("version", "1.0"),
                "path": str(result.path), "bytes": result.bytes,
                "verify": result.verify_report,
            },
        )
        await db.job_update(
            job_id, status="done", stage="done",
            result={
                "document_id": did,
                "markdown": markdown,
                "sections": sections,
                "meta": meta,
                "verify": result.verify_report,
                "instruction": instruction,
                "section_num": section_num,
                "source_document_id": p.get("source_document_id"),
                "bytes": result.bytes,
            },
        )
    except builder.VerifyFailed as e:
        log.error("job %s (revision) verify FAILED", job_id)
        await db.job_update(job_id, status="failed", error="verify FAILED",
                            result={"verify": e.report, "markdown": markdown, "sections": sections})
    except RevisionFailed as e:
        log.error("job %s (revision) could not be applied: %s", job_id, e.reason)
        await db.job_update(job_id, status="failed", error=str(e.reason)[:500])
    except BilingualGap as e:
        log.error("job %s (revision) bilingual gap: %s", job_id, e.gaps)
        await db.job_update(job_id, status="failed",
                            error="revision broke bilingual parity: " + ", ".join(e.gaps),
                            result={"bilingual_gaps": e.gaps, "sections": sections})
    except GridOverflow as e:
        log.error("job %s (revision) grid overflow: %s", job_id, e.gaps)
        await db.job_update(job_id, status="failed",
                            error="revision broke a table/form grid: " + str(e)[:400],
                            result={"grid_overflow": e.gaps, "sections": sections})
    except LettaError as e:
        log.error("job %s (revision) letta error: %s", job_id, e)
        await db.job_update(job_id, status="failed", error=f"letta: {e}")
    except Exception as e:  # noqa: BLE001 — job must record any failure
        log.exception("job %s (revision) failed", job_id)
        detail = str(e).strip() or repr(e)
        await db.job_update(job_id, status="failed", error=f"{type(e).__name__}: {detail}"[:500])
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001 — cleanup must never mask a job result
            log.warning("job %s: failed to close Letta client", job_id, exc_info=True)
