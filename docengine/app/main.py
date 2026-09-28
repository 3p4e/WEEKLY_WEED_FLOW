# docengine.app.main — GrowFlow DocEngine: dedicated FastAPI service.
#
# Internal-only container (no published ports); the WWF backend's /qms proxy
# is the sole caller (X-API-Key). Endpoints:
#   GET  /health                          liveness (+ letta/db readiness)
#   GET  /questionnaires                  index of Mode-A question banks
#   GET  /questionnaires/{key}            full question bank
#   POST /workflows                       start questionnaire->SOP pipeline
#   GET  /workflows/{id}                  poll job state (any worker)
#   POST /workflows/{id}/chat             ask about a finished document — read-only
#   POST /workflows/{id}/revise           direct-edit a finished document (chat/preset)
#   GET  /presets                         one-click revise instructions for the UI
#   POST /build                           direct Markdown -> verified .docx
#   GET  /documents                       registry list
#   GET  /documents/{id}                  registry row (verify report incl.)
#   GET  /documents/{id}/download         the .docx (only ever PASS docs)
#   GET  /documents/{id}/pdf              Gotenberg-rendered PDF
import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator

from . import builder, db, fleet
from .config import ENGINE_SCRIPTS, settings
from .letta import LettaClient, LettaError
from .pipeline import (
    ANNEX_AUTHOR, SOP_AUTHOR, run_revision, run_workflow, section_gate_failures,
    split_markdown_sections,
)
from .presets import PRESETS, PRESETS_BY_KEY
from .ragflow_api import RagflowUnreachable, list_dataset_names
from .questionnaires import QUESTIONNAIRES, InvalidAnswer, questionnaire_index, validate_answers
from .security import require_api_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("docengine")


# How often the periodic sweep runs. Startup-only reaping missed every job a
# hung (not killed) worker leaves behind, and every job a redeploy killed
# that was younger than the age threshold (review 2026-09-27, DI-04).
REAPER_INTERVAL_S = 300
# How often this process records that it is alive (docengine.workers). The
# orphan sweep — in this process or any other on the same database — fails
# only jobs whose worker has not beaten for db.WORKER_STALE_S (DI2-02).
HEARTBEAT_INTERVAL_S = 60


async def _sweep_jobs(where: str) -> None:
    """Both reapers, never raising: the service must come up and stay up
    whatever the sweep finds. Jobs this process still has a task for are
    excluded from the age sweep, so a slow-but-alive job is never failed
    under its own task."""
    try:
        orphaned = await db.reap_orphaned_jobs()
        if orphaned:
            log.warning("%s: reaped %d job(s) owned by a worker that is gone", where, orphaned)
        stale = await db.reap_stale_jobs(exclude=list(_running_jobs))
        if stale:
            log.warning("%s: reaped %d job(s) with no progress for %d min",
                        where, stale, db.STALE_JOB_MINUTES)
    except Exception:  # noqa: BLE001
        log.warning("%s: job sweep failed", where, exc_info=True)


async def _heartbeat(where: str) -> None:
    try:
        await db.heartbeat()
    except Exception:  # noqa: BLE001 — a missed beat is logged, never fatal
        log.warning("%s: worker heartbeat failed", where, exc_info=True)


async def _reaper_loop() -> None:
    """Beat every HEARTBEAT_INTERVAL_S; sweep every REAPER_INTERVAL_S."""
    ticks_per_sweep = max(1, REAPER_INTERVAL_S // HEARTBEAT_INTERVAL_S)
    tick = 0
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)
        await _heartbeat("periodic")
        tick += 1
        if tick % ticks_per_sweep == 0:
            await _sweep_jobs("periodic sweep")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    # Sweep jobs abandoned by a previously-killed worker. Startup is exactly
    # when those rows appear (a redeploy kills the worker mid-run), and without
    # this they sit at 'running' forever with a poller waiting on them.
    if db.ready():
        await _heartbeat("startup")
        await _sweep_jobs("startup")
    reaper = asyncio.create_task(_reaper_loop()) if db.ready() else None
    try:
        yield
    finally:
        if reaper is not None:
            reaper.cancel()
            try:
                await reaper
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
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
# job id -> its task, for as long as the task lives. The periodic reaper reads
# the keys: a job with a live task here is alive by definition.
_running_jobs: dict[str, asyncio.Task] = {}


def _fire_and_forget(coro, job_id: str | None = None) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    if job_id:
        _running_jobs[job_id] = task
        task.add_done_callback(lambda t, jid=job_id: _running_jobs.pop(jid, None))
    return task


def _valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


# ---------- organisation scope (review 2026-09-27, DI-13) ----------
# The registry and the job table hold every organisation's controlled
# documents, and the backend proxy's role gate alone let any elevated user of
# any organisation — including an anonymous visitor holding the public demo's
# ADMIN token — list, download, revise and register documents in the one
# shared registry. Every read and write is now for exactly one organisation:
# the backend sends the signed-in user's org id as X-Org-Id (app/docengine.py
# de_forward), jobs and documents are stamped with it, and every read filters
# on it. A missing header is refused, never defaulted — an unscoped read is
# the defect, not a convenience.
_ORG_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


async def require_org(x_org_id: str = Header(default="", alias="X-Org-Id")) -> str:
    org = (x_org_id or "").strip()
    if not _ORG_ID.match(org):
        raise HTTPException(
            400, "X-Org-Id required: DocEngine reads and writes are scoped to one organisation")
    return org


async def _job_or_404(jid: str, org: str) -> dict:
    """The job, only if it is this organisation's. Another organisation's
    job reads as absent — the id must not leak existence across tenants."""
    if not _valid_uuid(jid):
        raise HTTPException(404, "no such job")
    if not db.ready():
        raise HTTPException(503, "DocEngine storage unavailable")
    job = await db.job_get(jid)
    if not job or (job.get("org_id") or "") != org:
        raise HTTPException(404, "no such job")
    return job


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
        # False when init() could not create the (org, code, version) identity
        # index over existing duplicate rows (DI2-03; docs/DEPLOY.md)
        "registry_identity_unique": db.identity_index_ok(),
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
async def start_workflow(body: WorkflowIn, org: str = Depends(require_org)):
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
        raise HTTPException(422, f"invalid answer for '{e.qkey}': {e.reason}") from e
    if not db.ready():
        raise HTTPException(503, "DocEngine storage unavailable")
    if not LettaClient().configured:
        raise HTTPException(503, "Letta unavailable")
    jid = await db.job_create("workflow", body.model_dump(), body.requested_by, org_id=org)
    _fire_and_forget(run_workflow(jid), job_id=jid)
    return {"job_id": jid, "status": "queued"}


@app.get("/workflows/{jid}", dependencies=[Depends(require_api_key)])
async def get_workflow(jid: str, org: str = Depends(require_org)):
    return await _job_or_404(jid, org)


def _chat_ready_doc(job: dict) -> tuple[list[dict], dict]:
    """(sections, meta) off a finished job's result, or raise 404/409.

    Both chat and revise need the SAME structured pair run_workflow's "done"
    result stores — a job built before that field existed (or one that
    failed) has no `sections`/`meta` to work from, and there is nothing to
    fall back to that would not risk re-deriving section boundaries by
    re-parsing rendered Markdown."""
    if job["status"] != "done":
        raise HTTPException(404, "no finished document for this job")
    result = job.get("result") or {}
    sections, meta = result.get("sections"), result.get("meta")
    if not sections or not meta:
        raise HTTPException(
            409, "this job has no chat/revise-ready document (built before this feature shipped)"
        )
    return sections, meta


def _section_context(sections: list[dict], section_num: str | None) -> str:
    """Sections joined for an agent to READ, never to parse back — chat
    answers a question and is told not to emit the '<<<PP-SECTION' markers
    _direct_edit_sections relies on, so this join carries no marker syntax
    for it to echo by mistake."""
    target = [s for s in sections if not section_num or s["num"] == section_num]
    return "\n\n".join(f"# {s['num']} {s['mk']}|{s['en']}\n{s['content'].strip()}" for s in target)


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    section_num: str | None = None


# Chat turns in flight and recently finished, keyed by (job, organisation,
# question, section). The backend proxy gives a turn 170 s and then answers
# 504 "still answering"; the person retries, and the retry used to start a
# second full turn while the first one's answer — which lands a moment later
# — was thrown away at the return statement nobody was waiting on (review
# 2026-09-27, DI2-09). Now the turn runs as its own task, a retry of the same
# question attaches to that task instead of starting another, and a finished
# answer is replayed for CHAT_RESULT_TTL_S. Nothing here is a document
# mutation: no job row, no build.
_CHAT_INFLIGHT: dict[str, asyncio.Task] = {}
_CHAT_DONE: dict[str, tuple[float, str]] = {}
CHAT_RESULT_TTL_S = 600


def _chat_key(jid: str, org: str, body: "ChatIn") -> str:
    raw = json.dumps([jid, org, body.question.strip(), body.section_num or ""], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _forget_stale_chat_results(now: float) -> None:
    for k, (at, _) in list(_CHAT_DONE.items()):
        if now - at >= CHAT_RESULT_TTL_S:
            _CHAT_DONE.pop(k, None)


async def _chat_turn(jid: str, sections: list[dict], meta: dict, body: "ChatIn") -> str:
    """One question to an ephemeral clone of the document's author. Runs to
    completion whether or not the HTTP request that started it is still
    waiting (see _CHAT_INFLIGHT)."""
    client = LettaClient()
    try:
        # A question must not reconcile the fleet. It used to run the full
        # ~40-call ensure pass — block and config writes included — on every
        # question, which both blew the backend's timeout and reset persistent
        # agents' buffers under whatever job held them (review 2026-09-27,
        # DI-08 / DI-12); then only on a cold or expired cache, which is the
        # first question after ten idle minutes — inside the chat budget
        # (DI2-09). A cached pass is reused; otherwise the two ids a clone
        # needs are resolved from read-only listings and nothing is written.
        ctx = fleet.fleet_ctx_cached()
        if ctx is None:
            try:
                ctx = await fleet.read_only_ctx(client)
            except fleet.FleetNotReady as e:
                raise HTTPException(503, str(e))
        author = SOP_AUTHOR if meta.get("doctype") == "SOP" else ANNEX_AUTHOR
        tmp_id = await fleet.spawn_ephemeral(
            client, author, f"chat_{jid[:8]}", ctx=ctx, autoclear=False)
        try:
            reply = await client.send_message(
                tmp_id,
                "Answer the question below about this document. This is a "
                "question, not an edit request: do NOT rewrite any section and "
                "do NOT emit '<<<PP-SECTION' markers. If the answer is not in "
                "the document and you cannot verify it against your permitted "
                "corpus, say so rather than guessing.\n\n"
                f"QUESTION:\n{body.question.strip()}\n\n"
                f"DOCUMENT:\n{_section_context(sections, body.section_num)}",
            )
        finally:
            try:
                await client.delete_agent(tmp_id)
            except Exception:  # noqa: BLE001
                log.warning("failed to delete ephemeral chat clone %s", tmp_id, exc_info=True)
    finally:
        await client.aclose()
    return (reply or "").strip()


@app.post("/workflows/{jid}/chat", dependencies=[Depends(require_api_key)])
async def chat_about_document(jid: str, body: ChatIn, org: str = Depends(require_org)):
    """Answer a question about a finished document. Read-only: nothing this
    route does can change the document — that is what /revise is for. Runs
    on an ephemeral clone of the document's own author (autoclear off, in
    case a caller later wants a short back-and-forth on the same clone; today
    each call is one turn) so the answer comes from an agent that already
    understands this document's persona, corpus access and house rules,
    rather than a generic model call outside the fleet.

    The turn outlives the request: a retry of the same question while the
    first turn is still running attaches to it, and a finished answer is
    replayed for CHAT_RESULT_TTL_S (`replayed: true`) instead of being spent
    on a second Letta turn (DI2-09)."""
    job = await _job_or_404(jid, org)
    sections, meta = _chat_ready_doc(job)
    if body.section_num and not any(s["num"] == body.section_num for s in sections):
        raise HTTPException(404, f"no section {body.section_num} on this document")
    if not LettaClient().configured:
        raise HTTPException(503, "Letta unavailable")

    key = _chat_key(jid, org, body)
    now = time.monotonic()
    _forget_stale_chat_results(now)
    done = _CHAT_DONE.get(key)
    if done is not None:
        return {"answer": done[1], "replayed": True}
    task = _CHAT_INFLIGHT.get(key)
    if task is None:
        task = _fire_and_forget(_chat_turn(jid, sections, meta, body))
        _CHAT_INFLIGHT[key] = task

        def _settle(t: asyncio.Task, key: str = key) -> None:
            _CHAT_INFLIGHT.pop(key, None)
            if not t.cancelled() and t.exception() is None:
                _CHAT_DONE[key] = (time.monotonic(), t.result())
        task.add_done_callback(_settle)
    # shield: the request going away must not cancel the turn a retry will
    # want the answer of.
    answer = await asyncio.shield(task)
    return {"answer": answer}


@app.get("/presets", dependencies=[Depends(require_api_key)])
async def list_presets():
    # The full instruction text is included, not just the label — the UI can
    # drop it straight into an editable chat box so a preset is a starting
    # point a person can tweak, not a black box.
    return {"presets": PRESETS}


class ReviseIn(BaseModel):
    instruction: str | None = Field(default=None, max_length=4000)
    preset_key: str | None = None
    section_num: str | None = None
    requested_by: str = ""

    @field_validator("instruction")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v.strip() if v and v.strip() else None


@app.post("/workflows/{jid}/revise", dependencies=[Depends(require_api_key)])
async def revise_workflow(jid: str, body: ReviseIn, org: str = Depends(require_org)):
    """Start a direct-edit job on a finished document — a chat instruction or
    a preset, applied to one section or the whole document. Fires the same
    way /workflows does: a new job row, a background task, polled at
    /workflows/{new_id}. The revision clears the same §6A gate as a first
    draft, then run_revision registers a NEW db.documents row that
    supersedes the source (supersedes_id, next version, canon D5 content
    floor — see pipeline.run_revision). The source job and document are
    never touched, so the original stays downloadable exactly as built."""
    source = await _job_or_404(jid, org)
    sections, meta = _chat_ready_doc(source)
    if body.section_num and not any(s["num"] == body.section_num for s in sections):
        raise HTTPException(404, f"no section {body.section_num} on this document")
    instruction = body.instruction
    if not instruction and body.preset_key:
        preset = PRESETS_BY_KEY.get(body.preset_key)
        if not preset:
            raise HTTPException(422, f"unknown preset '{body.preset_key}'")
        instruction = preset["instruction"]
    if not instruction:
        raise HTTPException(422, "instruction or a known preset_key is required")
    if not LettaClient().configured:
        raise HTTPException(503, "Letta unavailable")
    payload = {
        "source_document_id": (source.get("result") or {}).get("document_id"),
        "sections": sections,
        "meta": meta,
        "instruction": instruction,
        "section_num": body.section_num,
    }
    rid = await db.job_create("revise", payload, body.requested_by, org_id=org)
    _fire_and_forget(run_revision(rid), job_id=rid)
    return {"job_id": rid, "status": "queued"}


# ---------- direct build (Mode B/C: caller supplies the Markdown) ----------
class BuildIn(BaseModel):
    markdown: str = Field(min_length=20, max_length=400_000)
    # Bounded: this becomes part of a filename via builder.safe_name(). That
    # helper truncates to 120 chars, but only AFTER the value has been accepted
    # — and every other field on this model already carries a bound, so the
    # omission was the odd one out rather than a decision.
    out_name: str = Field(default="document", min_length=1, max_length=80)
    meta: dict = Field(default_factory=dict)
    requested_by: str = Field(default="", max_length=120)


# meta key -> HEADERDATA field. The caller may repeat the document's identity
# in `meta`; it may not CONTRADICT it.
_META_TO_HEADER = {"code": "code", "version": "version", "title_mk": "mk_title",
                   "title_en": "en_title", "doctype": "doctype"}
_HEADER_REQUIRED = ("code", "version", "doctype", "mk_title", "en_title")


def _registry_identity(markdown: str, meta: dict) -> dict:
    """The registry row's identity, taken from the document itself.

    The printed HEADERDATA used to be whatever the markdown said while the
    registry row took code/title/version from `body.meta` with defaults of
    '' and '1.0' — so every Studio direct build registered with empty titles
    and version 1.0 whatever the document printed, under whatever code the
    user typed (review 2026-09-27, DI-06). The header is the identity; a
    `meta` value that disagrees with it is a 422, not a tie-break."""
    hd = builder.headerdata(markdown)
    missing = [k for k in _HEADER_REQUIRED if not hd.get(k)]
    if missing:
        raise HTTPException(
            422, detail={"error": "HEADERDATA incomplete",
                         "missing": missing,
                         "hint": "the registry identity (code, version, doctype, mk_title, "
                                 "en_title) is read from the document's HEADERDATA block"})
    conflicts = {}
    for mk, hk in _META_TO_HEADER.items():
        if mk in meta and meta[mk] not in (None, "") and str(meta[mk]).strip() != hd[hk]:
            conflicts[mk] = {"meta": meta[mk], "headerdata": hd[hk]}
    if conflicts:
        raise HTTPException(
            422, detail={"error": "meta contradicts HEADERDATA", "conflicts": conflicts})
    return {"code": hd["code"], "version": hd["version"], "doctype": hd["doctype"].upper(),
            "title_mk": hd["mk_title"], "title_en": hd["en_title"]}


@app.post("/build", dependencies=[Depends(require_api_key)])
async def direct_build(body: BuildIn, org: str = Depends(require_org)):
    """Direct Markdown -> verified .docx -> registry row.

    What this path enforces, and what it does not. It runs the same
    deterministic gates the questionnaire path runs before ITS build — the
    per-section bilingual check and the grid-overflow check — and the
    pp_verify hard gate. It does NOT run the §6A LLM audit: this route is
    synchronous (the backend proxy allows 120 s; one auditor turn is
    budgeted 900 s) and half of its callers are the certificate pipeline,
    whose markdown is generated from laboratory data rather than authored.
    The registry row therefore records `qa_audit = NULL` (`audited: false`
    on the list), `source = 'build'`, who requested it and for which
    organisation — a direct build is never presented as an audited
    document (review 2026-09-27, DI-06 / DI-16)."""
    if not db.ready():
        # A built file that is registered nowhere is not a controlled
        # document, and answering 200 with document_id=null let the
        # certificate pipeline record "generated" with no artefact (DI-16).
        raise HTTPException(503, "DocEngine storage unavailable")
    identity = _registry_identity(body.markdown, body.meta)
    sections = split_markdown_sections(body.markdown)
    failures = section_gate_failures(sections, identity["doctype"])
    if failures:
        raise HTTPException(422, detail={"error": "section gates failed", "gates": failures})
    try:
        result = await asyncio.to_thread(
            builder.build, body.markdown, settings.out_dir, body.out_name
        )
    except builder.VerifyFailed as e:
        # the gate: FAILed docs are deleted and never returned
        raise HTTPException(422, detail={"verify": e.report, "error": "verify FAILED"})
    doc_id = await db.document_create(
        None,
        {
            **identity,
            "path": str(result.path), "bytes": result.bytes,
            "verify": result.verify_report,
            "created_by": body.requested_by,
            "org_id": org,
            "source": "build",
            "qa_audit": None,
            "provenance": {"source": "build", "requested_by": body.requested_by,
                           "markdown_sha256": builder.sha256_text(body.markdown),
                           "sections": [s["num"] for s in sections]},
        },
    )
    return {
        "ok": True, "document_id": doc_id, "bytes": result.bytes,
        "verify": result.verify_report, "audited": False,
        "registered": {**identity, "created_by": body.requested_by},
    }


# ---------- documents ----------
@app.get("/documents", dependencies=[Depends(require_api_key)])
async def list_documents(org: str = Depends(require_org),
                         limit: int = Query(default=100, ge=1, le=500),
                         offset: int = Query(default=0, ge=0)):
    if not db.ready():
        raise HTTPException(503, "DocEngine storage unavailable")
    return await db.documents_list(org, limit=limit, offset=offset)


async def _doc_meta_or_404(did: str, org: str) -> dict:
    if not _valid_uuid(did):
        raise HTTPException(404, "no such document")
    if not db.ready():
        raise HTTPException(503, "DocEngine storage unavailable")
    d = await db.document_get(did, org)
    if not d:
        raise HTTPException(404, "no such document")
    return d


async def _doc_or_404(did: str, org: str) -> dict:
    d = await _doc_meta_or_404(did, org)
    if not Path(d["path"]).exists():
        raise HTTPException(410, "document artifact missing")
    return d


@app.get("/documents/{did}", dependencies=[Depends(require_api_key)])
async def get_document(did: str, org: str = Depends(require_org)):
    return await _doc_meta_or_404(did, org)


@app.get("/documents/{did}/download", dependencies=[Depends(require_api_key)])
async def download_document(did: str, org: str = Depends(require_org)):
    d = await _doc_or_404(did, org)
    return FileResponse(
        d["path"],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(d["path"]).name,
    )


@app.get("/documents/{did}/pdf", dependencies=[Depends(require_api_key)])
async def document_pdf(did: str, org: str = Depends(require_org)):
    d = await _doc_or_404(did, org)
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
