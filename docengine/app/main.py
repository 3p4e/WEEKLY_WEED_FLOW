# docengine.app.main — GrowFlow DocEngine: dedicated FastAPI service.
#
# Internal-only container (no published ports); the WWF backend's /qms proxy
# is the sole caller (X-API-Key). Endpoints:
#   GET  /health                          liveness (+ letta/db readiness)
#   GET  /questionnaires                  index of Mode-A question banks
#   GET  /questionnaires/{key}            full question bank
#   POST /workflows                       start questionnaire->SOP pipeline
#   GET  /workflows/{id}                  poll job state (any worker)
#   POST /build                           direct Markdown -> verified .docx
#   GET  /documents                       registry list
#   GET  /documents/{id}                  registry row (verify report incl.)
#   GET  /documents/{id}/download         the .docx (only ever PASS docs)
#   GET  /documents/{id}/pdf              Gotenberg-rendered PDF
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator

from . import builder, db, fleet
from .config import ENGINE_SCRIPTS, settings
from .letta import LettaClient, LettaError
from .pipeline import run_workflow
from .ragflow_api import RagflowUnreachable, list_dataset_names
from .questionnaires import QUESTIONNAIRES, InvalidAnswer, questionnaire_index, validate_answers
from .security import require_api_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("docengine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    # Sweep jobs abandoned by a previously-killed worker. Startup is exactly
    # when those rows appear (a redeploy kills the worker mid-run), and without
    # this they sit at 'running' forever with a poller waiting on them.
    try:
        reaped = await db.reap_stale_jobs()
        if reaped:
            log.warning("reaped %d stale job(s) left mid-flight by a killed worker", reaped)
    except Exception:
        # Never block startup on the sweep — the service must come up.
        log.warning("stale-job sweep failed at startup", exc_info=True)
    yield
    await db.close()


app = FastAPI(title="GrowFlow DocEngine", version="1.0.0", lifespan=lifespan)

# asyncio.create_task() only holds a WEAK reference to the task it returns —
# without also keeping a strong reference somewhere, the task can be silently
# garbage-collected mid-run before it completes (a documented asyncio footgun,
# not hypothetical: see "Important" note under
# https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task).
# A job that vanished mid-generation would sit "running" forever with no
# error recorded — worse than any exception run_workflow itself might raise.
_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def _valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


# ---------- health (unauthenticated: compose healthcheck) ----------
_PROBE_S = 4.0


async def _probe_letta() -> bool:
    """Reachable, not merely configured. `LettaClient().configured` only said
    a URL was SET, which was true through every outage."""
    c = LettaClient()
    if not c.configured:
        return False
    try:
        await asyncio.wait_for(c.list_tools(), _PROBE_S)
        return True
    except (LettaError, asyncio.TimeoutError, httpx.HTTPError):
        return False
    finally:
        try:
            await c.aclose()
        except Exception:  # noqa: BLE001
            pass


async def _probe_ragflow() -> dict:
    """Whether RAGflow answers, and whether every dataset fleet.yaml grants is
    actually on the tenant. This is the check that would have shown the fleet
    running against renamed datasets on 2026-08-27 and again on 2026-08-29,
    both times with /health reporting ok."""
    declared = sorted({d for a in fleet.load_fleet()["agents"] for d in a.get("datasets", [])})
    try:
        live = await asyncio.wait_for(list_dataset_names(timeout=_PROBE_S), _PROBE_S + 1)
    except (RagflowUnreachable, asyncio.TimeoutError):
        return {"reachable": False, "declared": declared, "unresolved": declared}
    return {"reachable": True, "declared": declared,
            "unresolved": [d for d in declared if d not in live]}


@app.get("/health")
async def health():
    letta_ok, rag = await asyncio.gather(_probe_letta(), _probe_ragflow())
    last = fleet.last_report()
    body = {
        "ok": True,
        "db": db.ready(),
        "letta": letta_ok,
        "ragflow": rag["reachable"],
        "datasets_unresolved": rag["unresolved"],
        # what the last ensure_fleet pass concluded; None until a job has run
        "fleet": last.summary() if last else None,
        # the tree the service actually imports (config.ENGINE_SCRIPTS), not a
        # string that named the OTHER copy — see DEPLOY-2026-08-31 review, R3
        "engine": ENGINE_SCRIPTS.parent.name,
    }
    # ok stays a liveness answer (the process is up and serving); the
    # readiness facts sit beside it so a dashboard, a person, or the compose
    # healthcheck can each take the view they need.
    body["ready"] = bool(body["db"] and letta_ok and rag["reachable"] and not rag["unresolved"])
    return body


@app.get("/fleet/status", dependencies=[Depends(require_api_key)])
async def fleet_status():
    """The last ensure_fleet report in full, plus a fresh dataset resolution.
    Read-only: it does not run a reconcile pass, because that mutates live
    agents and a status probe must not."""
    last = fleet.last_report()
    return {
        "last_pass": {
            "changed": last.changed, "drift": last.drift, "warnings": last.warnings,
            "unknown_tools": last.unknown_tools, "swept_orphans": last.swept,
            "created": last.created, "converged": last.summary()["converged"],
        } if last else None,
        "datasets": await _probe_ragflow(),
    }


# ---------- questionnaires ----------
@app.get("/questionnaires", dependencies=[Depends(require_api_key)])
async def list_questionnaires():
    return {"questionnaires": questionnaire_index()}


@app.get("/questionnaires/{key}", dependencies=[Depends(require_api_key)])
async def get_questionnaire(key: str):
    q = QUESTIONNAIRES.get(key)
    if not q:
        raise HTTPException(404, "unknown questionnaire")
    return q


# ---------- workflows ----------
# Unlike BuildIn's markdown/out_name below (Field(max_length=...)), a bare
# `dict` field can't carry a length bound directly — so this is a validator
# instead of a Field kwarg. Every value in answers/meta flows verbatim into
# every agent prompt for the job (see _brief() / assemble_markdown() in
# pipeline.py), so an unbounded payload is the same class of risk BuildIn's
# bounds already guard against, just on a dict-shaped field instead of a str
# one. The cap is generous (comfortably above any real questionnaire's
# answers or a normal meta block) while staying well below "clearly abusive".
_MAX_DICT_JSON_CHARS = 80_000


class WorkflowIn(BaseModel):
    questionnaire: str
    answers: dict = Field(default_factory=dict)
    meta: dict  # {title_mk, title_en, code, version?, orient?}
    requested_by: str = ""

    @field_validator("answers", "meta")
    @classmethod
    def _bound_json_size(cls, v: dict, info) -> dict:
        size = len(json.dumps(v, ensure_ascii=False))
        if size > _MAX_DICT_JSON_CHARS:
            raise ValueError(
                f"{info.field_name} is too large ({size} chars serialized JSON; "
                f"max {_MAX_DICT_JSON_CHARS})"
            )
        return v


@app.post("/workflows", dependencies=[Depends(require_api_key)])
async def start_workflow(body: WorkflowIn):
    if body.questionnaire not in QUESTIONNAIRES:
        raise HTTPException(400, "unknown questionnaire")
    for k in ("title_mk", "title_en", "code"):
        if not body.meta.get(k):
            raise HTTPException(400, f"meta.{k} required")
    # Pre-populated-answers gate (DOCENGINE-CANON §5): every value the caller
    # supplied must be a defined option for that question — never free text,
    # never an invented option. Unchecked answers flow verbatim into every
    # authoring/repair prompt sent to the Letta agents for this job, so this
    # must run BEFORE the job is created, not after.
    #
    # Residual, accepted gap (audit LOW companion to H8, not addressed here):
    # this closes off `answers` (closed option lists only), but `body.meta`
    # (title_mk, title_en, code, version, orient) stays free text — checked
    # only for HEADERDATA-breaking characters (see
    # _reject_headerdata_breakers in pipeline.py), not for general malformed
    # content — and flows into every downstream prompt just the same.
    # Malformed (non-injection) free text there can still degrade document
    # quality even absent malicious intent; that's inherent to accepting
    # free-text fields at all, not something this validator can close.
    try:
        validate_answers(body.questionnaire, body.answers)
    except InvalidAnswer as e:
        raise HTTPException(422, f"invalid answer for '{e.qkey}': not a defined option") from e
    if not db.ready():
        raise HTTPException(503, "DocEngine storage unavailable")
    if not LettaClient().configured:
        raise HTTPException(503, "Letta unavailable")
    jid = await db.job_create("workflow", body.model_dump(), body.requested_by)
    _fire_and_forget(run_workflow(jid))
    return {"job_id": jid, "status": "queued"}


@app.get("/workflows/{jid}", dependencies=[Depends(require_api_key)])
async def get_workflow(jid: str):
    if not _valid_uuid(jid):
        raise HTTPException(404, "no such job")
    if not db.ready():
        raise HTTPException(503, "DocEngine storage unavailable")
    job = await db.job_get(jid)
    if not job:
        raise HTTPException(404, "no such job")
    return job


# ---------- direct build (Mode B/C: caller supplies the Markdown) ----------
class BuildIn(BaseModel):
    markdown: str = Field(min_length=20, max_length=400_000)
    # Bounded: this becomes part of a filename via builder.safe_name(). That
    # helper truncates to 120 chars, but only AFTER the value has been accepted
    # — and every other field on this model already carries a bound, so the
    # omission was the odd one out rather than a decision.
    out_name: str = Field(default="document", min_length=1, max_length=80)
    meta: dict = Field(default_factory=dict)


@app.post("/build", dependencies=[Depends(require_api_key)])
async def direct_build(body: BuildIn):
    try:
        result = await asyncio.to_thread(
            builder.build, body.markdown, settings.out_dir, body.out_name
        )
    except builder.VerifyFailed as e:
        # the gate: FAILed docs are deleted and never returned
        raise HTTPException(422, detail={"verify": e.report, "error": "verify FAILED"})
    doc_id = None
    if db.ready():
        doc_id = await db.document_create(
            None,
            {
                "code": body.meta.get("code", body.out_name),
                "doctype": result.doctype,
                "title_mk": body.meta.get("title_mk", ""),
                "title_en": body.meta.get("title_en", ""),
                "version": body.meta.get("version", "1.0"),
                "path": str(result.path), "bytes": result.bytes,
                "verify": result.verify_report,
            },
        )
    return {
        "ok": True, "document_id": doc_id, "bytes": result.bytes,
        "verify": result.verify_report,
    }


# ---------- documents ----------
@app.get("/documents", dependencies=[Depends(require_api_key)])
async def list_documents():
    if not db.ready():
        raise HTTPException(503, "DocEngine storage unavailable")
    return {"documents": await db.documents_list()}


async def _doc_meta_or_404(did: str) -> dict:
    if not _valid_uuid(did):
        raise HTTPException(404, "no such document")
    if not db.ready():
        raise HTTPException(503, "DocEngine storage unavailable")
    d = await db.document_get(did)
    if not d:
        raise HTTPException(404, "no such document")
    return d


async def _doc_or_404(did: str) -> dict:
    d = await _doc_meta_or_404(did)
    if not Path(d["path"]).exists():
        raise HTTPException(410, "document artifact missing")
    return d


@app.get("/documents/{did}", dependencies=[Depends(require_api_key)])
async def get_document(did: str):
    return await _doc_meta_or_404(did)


@app.get("/documents/{did}/download", dependencies=[Depends(require_api_key)])
async def download_document(did: str):
    d = await _doc_or_404(did)
    return FileResponse(
        d["path"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(d["path"]).name,
    )


@app.get("/documents/{did}/pdf", dependencies=[Depends(require_api_key)])
async def document_pdf(did: str):
    d = await _doc_or_404(did)
    if not settings.gotenberg_url:
        raise HTTPException(503, "PDF renderer unavailable")
    # Read off the event loop. Passing the open file handle to httpx made it
    # do blocking disk reads while streaming the upload, stalling every other
    # request this worker was serving for the duration of a multi-megabyte
    # .docx — the same defect H14 fixed for builder.build, on a path that is
    # hit far more often.
    try:
        blob = await asyncio.to_thread(Path(d["path"]).read_bytes)
    except OSError as e:
        log.warning("PDF conversion: cannot read document %s: %s", did, e)
        raise HTTPException(404, "Document file missing") from e
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                settings.gotenberg_url + "/forms/libreoffice/convert",
                files={"files": (Path(d["path"]).name, blob,
                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
    except httpx.HTTPError as e:
        log.warning("Gotenberg PDF conversion failed for document %s: %s", did, e)
        raise HTTPException(502, "PDF conversion failed") from e
    if r.status_code != 200:
        raise HTTPException(502, "PDF conversion failed")
    return Response(
        content=r.content, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="{Path(d["path"]).stem}.pdf"'},
    )
