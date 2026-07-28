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
_PREAMBLE = re.compile(
    r"^(looking at|let me|here('s| is)|here are|i'll|i will|i have|i've|based on( the)?|"
    r"as (requested|instructed|per)|sure[,!]|certainly|okay|alright|below is|the following|"
    r"this is (my|the)|note:|understood|of course|great[,!]|let's|now,? (let|i))\b",
    re.I,
)
# The first structural token of a real document body: a Markdown heading or a
# form/table marker. Everything an annex author says before this is commentary.
_STRUCT = re.compile(r"^\s*(#{1,6}\s|\[\[(FORM|TABLE))", re.M)


class QaAuditFailed(Exception):
    """The §6A auditor returned a FIX verdict (or something other than a
    clear PASS) — the document must not proceed to formatting/registration
    until the issues are addressed. Consistent with pp_verify's own hard
    PASS/FAIL gate elsewhere in this pipeline: never fabricate, fail loud."""

    def __init__(self, verdict: str):
        super().__init__("§6A audit did not PASS")
        self.verdict = verdict


def _qa_audit_passed(verdict: str) -> bool:
    return (verdict or "").strip().upper().startswith("PASS")


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
    return "\n".join(lines[i:]).strip() or t


def _brief(questionnaire_key: str, answers: dict) -> str:
    lines = [f"Questionnaire: {questionnaire_key}"]
    for k, v in answers.items():
        lines.append(f"- {k}: {', '.join(v) if isinstance(v, list) else v}")
    return "\n".join(lines)


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
        brief = _brief(qkey, answers)
        await db.job_update(job_id, status="running", stage="generate")

        from .fleet import ensure_fleet, spawn_ephemeral  # late import: fleet needs live Letta

        agents = await ensure_fleet(client)

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
                sections.append({"num": num, "mk": mk, "en": en, "content": _clean_section(text)})
                await db.job_update(job_id, stage=f"generate {num}")
        else:
            text = await client.send_message(
                agents["gf_annex_author"],
                f"Design the {doctype} '{meta['title_mk']} | {meta['title_en']}' "
                f"(code {meta['code']}). Content brief:\n{brief}\n\n"
                "Return ONLY the bilingual Markdown body, using [[FORM:grid]] for the "
                "metadata block and [[TABLE]] for data grids. Blank write-in values. "
                "NO commentary, preamble, or explanation — your entire reply is inserted "
                "verbatim into the document.",
            )
            sections.append(
                {"num": "1.0", "mk": "СОДРЖИНА", "en": "CONTENT",
                 "content": _clean_section(text, structured=True)}
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
                    f"regulatory corpus ({', '.join(settings.reg_sources)}). Cite only "
                    f"retrieved passages; say NO-FINDING if nothing applies.\n\n{s['content']}",
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

        # ---- §6A audit ----
        await db.job_update(job_id, stage="qa-audit")
        markdown = assemble_markdown(meta, sections)
        audit = await client.send_message(
            agents["gf_qa_auditor"],
            "Run the §6A review on this assembled document Markdown. "
            "Return verdict PASS or FIX with issues.\n\n" + markdown,
        )
        if not _qa_audit_passed(audit):
            raise QaAuditFailed(audit)

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
                "qa_audit": audit,
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
                            result={"qa_audit": e.verdict})
    except LettaError as e:
        log.error("job %s letta error: %s", job_id, e)
        await db.job_update(job_id, status="failed", error=f"letta: {e}")
    except Exception as e:  # noqa: BLE001 — job must record any failure
        log.exception("job %s failed", job_id)
        # Some exceptions (notably httpx.ReadTimeout) stringify to "" — always
        # record the type name so the job row never shows a blank error.
        detail = str(e).strip() or repr(e)
        await db.job_update(job_id, status="failed", error=f"{type(e).__name__}: {detail}"[:500])
