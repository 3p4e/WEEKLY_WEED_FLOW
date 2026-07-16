# docengine.app.pipeline — the merged content workflow (DOCENGINE-CANON §5):
# questionnaire answers -> section generation by the gf_ fleet -> per-section
# regulatory RAG check -> §6A audit -> bilingual Markdown assembly -> the
# formatting core (builder.py, hard PASS gate) -> registry row.
#
# Runs as an asyncio background task; ALL state transitions go through
# Postgres (db.jobs) so any worker can serve the poll.
from __future__ import annotations

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


def _strip_fences(text: str) -> str:
    return _MD_FENCE.sub("", text or "").strip()


def _brief(questionnaire_key: str, answers: dict) -> str:
    lines = [f"Questionnaire: {questionnaire_key}"]
    for k, v in answers.items():
        lines.append(f"- {k}: {', '.join(v) if isinstance(v, list) else v}")
    return "\n".join(lines)


def assemble_markdown(meta: dict, sections: list[dict]) -> str:
    """Assemble the HEADERDATA block + section bodies into engine Markdown."""
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

        from .fleet import ensure_fleet  # late import: fleet needs live Letta

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
                    "Return bilingual Markdown body only (no heading line, no fences). "
                    "Unknown facility specifics stay as blank fields.",
                )
                sections.append({"num": num, "mk": mk, "en": en, "content": _strip_fences(text)})
                await db.job_update(job_id, stage=f"generate {num}")
        else:
            text = await client.send_message(
                agents["gf_annex_author"],
                f"Design the {doctype} '{meta['title_mk']} | {meta['title_en']}' "
                f"(code {meta['code']}). Content brief:\n{brief}\n\n"
                "Return bilingual Markdown body only, using [[FORM:grid]] for the "
                "metadata block and [[TABLE]] for data grids. Blank write-in values.",
            )
            sections.append(
                {"num": "1.0", "mk": "СОДРЖИНА", "en": "CONTENT", "content": _strip_fences(text)}
            )

        # ---- per-section regulatory check ----
        await db.job_update(job_id, stage="regulatory-check")
        reg_findings: list[str] = []
        for s in sections:
            finding = await client.send_message(
                agents["gf_reg_checker"],
                f"Check this drafted section {s['num']} of {meta['code']} against the "
                f"regulatory corpus ({', '.join(settings.reg_sources)}). Cite only "
                f"retrieved passages; say NO-FINDING if nothing applies.\n\n{s['content']}",
            )
            reg_findings.append(f"[{s['num']}] {finding.strip()}")

        # ---- §6A audit ----
        await db.job_update(job_id, stage="qa-audit")
        markdown = assemble_markdown(meta, sections)
        audit = await client.send_message(
            agents["gf_qa_auditor"],
            "Run the §6A review on this assembled document Markdown. "
            "Return verdict PASS or FIX with issues.\n\n" + markdown,
        )

        # ---- format + verify (hard gate) ----
        await db.job_update(job_id, stage="format")
        result = builder.build(markdown, settings.out_dir, meta["code"])
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
    except LettaError as e:
        log.error("job %s letta error: %s", job_id, e)
        await db.job_update(job_id, status="failed", error=f"letta: {e}")
    except Exception as e:  # noqa: BLE001 — job must record any failure
        log.exception("job %s failed", job_id)
        await db.job_update(job_id, status="failed", error=str(e)[:500])
