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
    client: LettaClient, author: str, sections: list[dict], audit: str, job_id: str
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

    tmp_id = await spawn_ephemeral(client, author, f"fix_{job_id[:8]}")
    try:
        reply = await client.send_message(
            tmp_id,
            "A §6A reviewer raised the issues below against this document. "
            "Return the CORRECTED document body.\n\n"
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


def assemble_markdown(meta: dict, sections: list[dict]) -> str:
    """Assemble the HEADERDATA block + section bodies into engine Markdown."""
    # A literal "-->" in a meta value would be mistaken for the HEADERDATA
    # block's own terminator by build_from_md.py's parser, truncating the
    # header and leaking the remaining fields into the document body. Reject
    # rather than silently strip/sanitize — fail loud, never ship a
    # corrupted controlled document.
    for _k in ("title_mk", "title_en", "code", "version", "doctype", "orient"):
        _v = meta.get(_k)
        if _v and "-->" in str(_v):
            raise ValueError(f"meta.{_k} may not contain '-->' (breaks the HEADERDATA block terminator)")
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
    failure lands in the job row as status=failed."""
    client = client or LettaClient()
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
        from .fleet import agent_datasets, ensure_fleet, spawn_ephemeral

        agents = await ensure_fleet(client)
        reg_corpora = agent_datasets("gf_reg_checker")

        # ---- section generation ----
        sections: list[dict] = []
        if doctype == "SOP":
            for num, mk, en in SOP_SECTIONS:
                author = agents["gf_raci_specialist"] if num == "3.0" else agents["gf_sop_author"]
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
                agents["gf_annex_author"],
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
        await db.job_update(job_id, stage="regulatory-check")
        reg_findings: list[str] = []
        for s in sections:
            await db.job_update(job_id, stage=f"regulatory-check {s['num']}")
            tmp_id = await spawn_ephemeral(
                client, "gf_reg_checker", f"{job_id[:8]}_{s['num'].replace('.', '')}"
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
                # LettaError, and an orphaned tmp agent is harmless (the next
                # fleet audit sweeps _tmp_ leftovers) while a failed job isn't.
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

        # ---- §6A audit ----
        # A FIX verdict is not the end: the auditor returns concrete, actionable
        # issues ("add the ~~Шифра | Code~~ row ... after adding it the document
        # is PASS"), and before this loop the pipeline discarded them and failed
        # the job. Most first-pass failures are ordinary drafting variance, so
        # one hand-back converges them. The gate itself is NOT relaxed —
        # _qa_audit_passed still has to return True on the final verdict; repair
        # only buys more attempts at earning it.
        await db.job_update(job_id, stage="qa-audit")
        author = "gf_sop_author" if doctype == "SOP" else "gf_annex_author"
        audits: list[str] = []
        markdown = assemble_markdown(meta, sections)
        for attempt in range(max(0, settings.max_repair_rounds) + 1):
            audit = await client.send_message(
                agents["gf_qa_auditor"],
                "Run the §6A review on this assembled document Markdown. "
                "Return verdict PASS or FIX with issues.\n\n"
                "SCOPE: review the CONTENT. The `<!--HEADERDATA-->` block and the "
                "`# <number> <MK>|<EN>` section heading lines are emitted by the "
                "formatter in canonical form — they are not the author's and not "
                "yours to restyle. Do not raise issues about their spacing, level "
                "or punctuation; no author can act on those and the document "
                "cannot pass.\n\n" + markdown,
            )
            audits.append(audit)
            if _qa_audit_passed(audit) or attempt >= settings.max_repair_rounds:
                break

            await db.job_update(job_id, stage=f"qa-repair {attempt + 1}")
            repaired = await _repair_sections(client, author, sections, audit, job_id)
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
        log.error("job %s verify FAILED", job_id)
        await db.job_update(job_id, status="failed", error="verify FAILED",
                            result={"verify": e.report})
    except QaAuditFailed as e:
        log.error("job %s §6A audit did not pass", job_id)
        await db.job_update(job_id, status="failed", error="§6A audit did not pass",
                            result={"qa_audit": e.verdict,
                                    "qa_audit_history": e.history,
                                    "qa_repair_rounds": len(e.history) - 1,
                                    # the document the auditor actually judged —
                                    # without it a FIX verdict cannot be checked
                                    "markdown": e.markdown})
    except BilingualGap as e:
        log.error("job %s bilingual gap: %s", job_id, e.gaps)
        await db.job_update(job_id, status="failed",
                            error="sections are not bilingual: " + ", ".join(e.gaps),
                            result={"bilingual_gaps": e.gaps})
    except LettaError as e:
        log.error("job %s letta error: %s", job_id, e)
        await db.job_update(job_id, status="failed", error=f"letta: {e}")
    except Exception as e:  # noqa: BLE001 — job must record any failure
        log.exception("job %s failed", job_id)
        # Some exceptions (notably httpx.ReadTimeout) stringify to "" — always
        # record the type name so the job row never shows a blank error.
        detail = str(e).strip() or repr(e)
        await db.job_update(job_id, status="failed", error=f"{type(e).__name__}: {detail}"[:500])
