# docengine.app.db — workflow state in Postgres (own schema `docengine`).
# This fixes the qms-creator per-worker in-memory bug class: any uvicorn
# worker can serve any poll because state lives in the database.
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Iterable

import asyncpg

from .config import settings

log = logging.getLogger("docengine.db")

_pool: asyncpg.Pool | None = None

# One id per process boot. Every job is stamped with the worker that owns it
# (the background task lives in that process). Whether that worker is still
# alive is answered by its HEARTBEAT row (docengine.workers, touched every
# main.HEARTBEAT_INTERVAL_S): a job whose worker has no fresh heartbeat
# belongs to a process that is gone — a redeploy, an OOM kill, a hung loop —
# and is failed. The first version treated "not THIS process" as "gone",
# which was exact under --workers 1 and mutually destructive the moment a
# second process shared the database: each failed the other's live jobs
# every sweep (review 2026-09-27, DI-04 / DI2-02). Overridable for tests.
WORKER_ID = os.environ.get("DOCENGINE_WORKER_ID") or uuid.uuid4().hex
# A worker whose heartbeat is older than this is gone. main.py beats every
# 60 s; five missed beats is a dead process, not a busy one.
WORKER_STALE_S = 300

_SCHEMA = """
CREATE TABLE IF NOT EXISTS docengine.jobs (
  id          uuid PRIMARY KEY,
  kind        text NOT NULL,                 -- 'workflow' | 'revise'
  status      text NOT NULL DEFAULT 'queued',-- queued|running|done|failed
                                             -- (awaiting_review is reserved for
                                             --  the canvas design; nothing
                                             --  writes it yet, and the reaper
                                             --  must never touch it)
  stage       text NOT NULL DEFAULT '',
  payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
  result      jsonb NOT NULL DEFAULT '{}'::jsonb,
  error       text,
  created_by  text NOT NULL DEFAULT '',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
-- Additive, like the canvas design prescribes: the schema is created by the
-- service itself, so every later column is an ADD COLUMN IF NOT EXISTS here.
ALTER TABLE docengine.jobs ADD COLUMN IF NOT EXISTS worker_id text;
ALTER TABLE docengine.jobs ADD COLUMN IF NOT EXISTS org_id text;
CREATE TABLE IF NOT EXISTS docengine.documents (
  id          uuid PRIMARY KEY,
  job_id      uuid REFERENCES docengine.jobs(id),
  code        text NOT NULL,
  doctype     text NOT NULL,
  title_mk    text NOT NULL DEFAULT '',
  title_en    text NOT NULL DEFAULT '',
  version     text NOT NULL DEFAULT '1.0',
  path        text NOT NULL,
  bytes       int  NOT NULL,
  verify      text NOT NULL,                 -- full pp_verify PASS report
  created_at  timestamptz NOT NULL DEFAULT now()
);
-- The jobs row's status/stage/error are overwritten on every job_update()
-- call, so once a job finishes there is no way to see the path it took to
-- get there — only where it ended up. That is exactly the information a
-- failed run needs to be debugged without re-running it (the agents do not
-- reproduce the same draft twice, per pipeline.py). job_events is the
-- append-only history job_update() writes alongside the row it updates.
CREATE TABLE IF NOT EXISTS docengine.job_events (
  id          bigserial PRIMARY KEY,
  job_id      uuid NOT NULL REFERENCES docengine.jobs(id) ON DELETE CASCADE,
  status      text,
  stage       text,
  error       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
-- Review 2026-09-27 (DI-06 / DI-07 / DI-13 / DI-14): who registered it, for
-- which organisation, by which path, what it supersedes, what the §6A
-- auditor said (NULL = never audited: the /build path), what fed each
-- section, and who reviewed it (NULL = no human has; the canvas design's
-- approval gate is what will set it).
ALTER TABLE docengine.documents ADD COLUMN IF NOT EXISTS created_by  text NOT NULL DEFAULT '';
ALTER TABLE docengine.documents ADD COLUMN IF NOT EXISTS org_id      text;
ALTER TABLE docengine.documents ADD COLUMN IF NOT EXISTS source      text NOT NULL DEFAULT 'workflow';
ALTER TABLE docengine.documents ADD COLUMN IF NOT EXISTS supersedes_id uuid REFERENCES docengine.documents(id);
ALTER TABLE docengine.documents ADD COLUMN IF NOT EXISTS qa_audit    text;
ALTER TABLE docengine.documents ADD COLUMN IF NOT EXISTS provenance  jsonb;
ALTER TABLE docengine.documents ADD COLUMN IF NOT EXISTS reviewed_by text;
ALTER TABLE docengine.documents ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;
CREATE INDEX IF NOT EXISTS de_jobs_status ON docengine.jobs(status);
CREATE INDEX IF NOT EXISTS de_jobs_org ON docengine.jobs(org_id);
CREATE INDEX IF NOT EXISTS de_docs_code ON docengine.documents(code);
CREATE INDEX IF NOT EXISTS de_job_events_job ON docengine.job_events(job_id, created_at);
CREATE INDEX IF NOT EXISTS de_docs_org_created ON docengine.documents(org_id, created_at DESC);
-- Liveness of every process that owns jobs (DI2-02): the reaper trusts a
-- worker that beat recently, whatever process is asking.
CREATE TABLE IF NOT EXISTS docengine.workers (
  worker_id    text PRIMARY KEY,
  started_at   timestamptz NOT NULL DEFAULT now(),
  heartbeat_at timestamptz NOT NULL DEFAULT now()
);
"""

# One identity per controlled document (review 2026-09-27, DI2-03): a second
# revision of the same source, or the same questionnaire run twice under one
# code, registered the same code+version again with different bytes — two
# documents with one identity, which a GMP registry may not hold. Partial:
# the /build path re-registers a certificate's COQ on every regeneration by
# design and is not a controlled-document identity. Created separately from
# _SCHEMA so a registry that ALREADY holds duplicates still boots (the
# statement fails, loudly, and /health reports it) instead of taking the
# service down; docs/DEPLOY.md says how to find and resolve them first.
_IDENTITY_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS de_docs_identity"
    " ON docengine.documents(org_id, code, version) WHERE source <> 'build'"
)
_identity_index_ok: bool | None = None


def identity_index_ok() -> bool | None:
    """True once the identity index exists, False when init() could not create
    it over existing duplicates, None before init() ran."""
    return _identity_index_ok

# The columns a registry LIST row carries. The verify report and provenance
# are per-document reads (document_get), not list payload.
_DOC_LIST_COLS = (
    "id, code, doctype, title_mk, title_en, version, bytes, created_at,"
    " created_by, org_id, source, supersedes_id, reviewed_by, reviewed_at,"
    " (qa_audit IS NOT NULL) AS audited"
)


async def init() -> None:
    global _pool
    if not settings.database_url:
        return  # tests / degraded mode: endpoints depending on DB 503
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    async with _pool.acquire() as c:
        # The schema is created only when it is absent. `CREATE SCHEMA IF NOT
        # EXISTS` checks CREATE ON DATABASE before it checks existence, and
        # that privilege is exactly what the service's own role must not hold
        # (docengine/sql/docengine_role.sql creates the schema and hands it
        # over; review 2026-09-27, DI-09). Under a role that may create
        # schemas — a test cluster, a first boot as superuser — this still
        # creates it.
        if not await c.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = 'docengine'"):
            await c.execute("CREATE SCHEMA docengine")
        await c.execute(_SCHEMA)
        global _identity_index_ok
        try:
            await c.execute(_IDENTITY_INDEX)
            _identity_index_ok = True
        except asyncpg.UniqueViolationError as e:
            _identity_index_ok = False
            log.error("registry identity index NOT created: existing rows share one "
                      "(org_id, code, version) — %s. Resolve the duplicates (docs/DEPLOY.md, "
                      "\"Registry identity\") and restart; until then a revision may register a "
                      "second document under an existing identity.", e)


async def close() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("docengine db not configured")
    return _pool


def ready() -> bool:
    return _pool is not None


# ---- job helpers ----
async def job_create(kind: str, payload: dict, created_by: str = "",
                     org_id: str | None = None) -> str:
    jid = str(uuid.uuid4())
    await pool().execute(
        "INSERT INTO docengine.jobs (id, kind, payload, created_by, worker_id, org_id)"
        " VALUES ($1,$2,$3,$4,$5,$6)",
        jid, kind, json.dumps(payload), created_by, WORKER_ID, org_id,
    )
    return jid


async def job_update(jid: str, **fields: Any) -> None:
    sets, vals = ["updated_at = now()"], []
    for k, v in fields.items():
        if k in ("payload", "result"):
            v = json.dumps(v)
        vals.append(v)
        sets.append(f"{k} = ${len(vals)}")
    vals.append(jid)
    # B608 suppressed below: `sets` interpolates only CODE-controlled column
    # names (the **fields kwargs at this module's own call sites: status/
    # stage/error/result/payload). Every VALUE is a real asyncpg bind
    # parameter in *vals, never interpolated. Same parametrized-with-
    # code-controlled-columns pattern the backend documents in app/demo_org.py.
    row = await pool().fetchrow(
        f"UPDATE docengine.jobs SET {', '.join(sets)} WHERE id = ${len(vals)} "
        "RETURNING status, stage, error",  # nosec B608
        *vals,
    )
    # RETURNING (not the caller's **fields) so the event always reflects the
    # row's actual post-update state — a call that only touches `stage`
    # still logs the status/error that were already there, instead of two
    # blanks that would make the trace look like it reset.
    if row is not None and any(k in fields for k in ("status", "stage", "error")):
        await pool().execute(
            "INSERT INTO docengine.job_events (job_id, status, stage, error)"
            " VALUES ($1,$2,$3,$4)",
            jid, row["status"], row["stage"], row["error"],
        )


# A job is only ever advanced by the worker that owns it, so a worker killed
# mid-run (OOM, redeploy) leaves its row at 'running'/'queued' forever: the
# poller waits on it indefinitely and nothing ever cleans it up. Two sweeps
# cover the two ways that happens:
#
#   reap_orphaned_jobs — the worker is GONE: its heartbeat row is missing or
#     older than WORKER_STALE_S. Every unfinished job it owns is failed,
#     whatever the job's age. This is the redeploy case: the old process
#     closed its pool mid-job, the new one starts seconds later, and the row
#     is only minutes old — an age-based sweep alone left it 'running'
#     forever (review 2026-09-27, DI-04). The old process's last beat ages
#     past the threshold within WORKER_STALE_S, so the job is failed within
#     a few minutes of the restart rather than never. A worker that is still
#     beating is never reaped by another, however many processes share the
#     database (DI2-02); one sweep runs at a time, under a transaction-scoped
#     advisory lock, so two processes never race the same rows.
#   reap_stale_jobs — the worker is alive but the job stopped moving. Age is
#     the signal; 60 minutes sits above the longest legal silence between two
#     job_update() calls (one §6A audit turn + a two-turn repair at the 900 s
#     read timeout). Only THIS worker's own jobs (and legacy rows with no
#     owner) are judged — another live worker knows which of its jobs still
#     have a task — and jobs the live process still has a task for are
#     excluded by the caller, so a slow-but-alive job is never failed under
#     its task.
STALE_JOB_MINUTES = 60
_ABANDONED = "abandoned: worker %s is gone (restart or redeploy killed it mid-run)"
_REAPER_LOCK = "SELECT pg_try_advisory_xact_lock(hashtext('docengine.reaper'))"


async def heartbeat(worker: str | None = None) -> None:
    """Record that this process is alive. Called at startup and every
    HEARTBEAT_INTERVAL_S from main; the orphan sweep trusts a worker whose
    beat is younger than WORKER_STALE_S. Rows of workers silent for a day
    are dropped here, so the table does not grow with every redeploy."""
    if _pool is None:
        return
    me = worker or WORKER_ID
    async with pool().acquire() as c:
        await c.execute(
            "INSERT INTO docengine.workers (worker_id) VALUES ($1)"
            " ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = now()", me)
        await c.execute(
            "DELETE FROM docengine.workers WHERE heartbeat_at < now() - interval '1 day'")


async def reap_orphaned_jobs(current_worker: str | None = None,
                             stale_after_s: int = WORKER_STALE_S) -> int:
    """Fail every unfinished job whose owning worker has no fresh heartbeat
    (missing row, or last beat older than `stale_after_s`), regardless of the
    job's age. This worker's own jobs are never candidates. Returns how many,
    or 0 when another process's sweep holds the reaper lock right now."""
    if _pool is None:
        return 0
    me = current_worker or WORKER_ID
    async with pool().acquire() as c, c.transaction():
        if not await c.fetchval(_REAPER_LOCK):
            return 0
        rows = await c.fetch(
            "UPDATE docengine.jobs j SET status='failed', updated_at=now(),"
            "   error = COALESCE(NULLIF(error,''),"
            "                    format($2::text, COALESCE(worker_id, '<unknown>')))"
            " WHERE status IN ('queued','running')"
            "   AND worker_id IS DISTINCT FROM $1"
            "   AND NOT EXISTS (SELECT 1 FROM docengine.workers w"
            "                   WHERE w.worker_id = j.worker_id"
            "                     AND w.heartbeat_at > now() - make_interval(secs => $3))"
            " RETURNING id", me, _ABANDONED, float(stale_after_s))
    return len(rows)


async def reap_stale_jobs(older_than_minutes: int = STALE_JOB_MINUTES,
                          exclude: Iterable[str] = (),
                          current_worker: str | None = None) -> int:
    """Fail THIS worker's jobs (and ownerless legacy rows) that have made no
    progress for `older_than_minutes`. Returns how many. `exclude` names jobs
    the caller still has a live task for.

    Uses updated_at, which every job_update() touches, so a job still making
    progress is never reaped. Runs at startup and then periodically from
    main._reaper_loop — a hung worker is exactly the case a startup-only
    sweep cannot see. Another worker's silent job is that worker's to judge
    (it knows whether a task is still alive for it); if that worker is gone,
    the orphan sweep takes it."""
    if _pool is None:
        return 0
    me = current_worker or WORKER_ID
    keep = [uuid.UUID(x) for x in exclude]
    rows = await pool().fetch(
        "UPDATE docengine.jobs SET status='failed', updated_at=now(),"
        "   error = COALESCE(NULLIF(error,''), 'abandoned: no progress for '"
        "                    || $1::text || ' minutes (worker killed mid-run)')"
        " WHERE status IN ('queued','running')"
        "   AND updated_at < now() - ($1::text || ' minutes')::interval"
        "   AND (worker_id IS NULL OR worker_id = $3)"
        "   AND NOT (id = ANY($2::uuid[]))"
        " RETURNING id", str(older_than_minutes), keep, me)
    return len(rows)


async def job_get(jid: str) -> dict | None:
    r = await pool().fetchrow("SELECT * FROM docengine.jobs WHERE id = $1", jid)
    if not r:
        return None
    d = dict(r)
    for k in ("payload", "result"):
        if isinstance(d.get(k), str):
            d[k] = json.loads(d[k])
    d["id"] = str(d["id"])
    for k in ("created_at", "updated_at"):
        d[k] = d[k].isoformat()
    return d


async def job_events(jid: str) -> list[dict]:
    """Oldest-first, so a trace panel can render it top-to-bottom as the run
    actually happened. Returns [] for a job with no events (created before
    this table existed, or none of its job_update() calls touched
    status/stage/error) rather than raising — the caller already has job_get
    for the 404 case."""
    rows = await pool().fetch(
        "SELECT status, stage, error, created_at FROM docengine.job_events"
        " WHERE job_id = $1 ORDER BY id ASC", jid,
    )
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out


class DocumentIdentityTaken(Exception):
    """A controlled document with this (organisation, code, version) is
    already registered (DI2-03). The job records this as its failure; the
    author revises from the latest registered row or picks the next version."""

    def __init__(self, code: str, version: str):
        self.code, self.version = code, version
        super().__init__(f"a controlled document {code} version {version} is already "
                         "registered for this organisation — revise from the latest "
                         "registered version instead of registering a second one")


async def registered_versions(org_id: str | None, code: str) -> list[str]:
    """Every version registered under `code` for the organisation, excluding
    /build artefacts (which carry no controlled-document identity). Empty
    without a registry or an organisation."""
    if _pool is None or not org_id:
        return []
    rows = await pool().fetch(
        "SELECT DISTINCT version FROM docengine.documents"
        " WHERE org_id = $1 AND code = $2 AND source <> 'build'", org_id, code)
    return [r["version"] for r in rows]


async def document_create(job_id: str | None, meta: dict) -> str:
    """Register one verified document. `meta` carries the registry identity
    (code/doctype/titles/version), the artefact (path/bytes/verify) and the
    record fields: created_by, org_id, source ('workflow'|'revise'|'build'),
    supersedes_id, qa_audit (None when the §6A auditor never saw it) and
    provenance. reviewed_by is never set here: registration is not review.
    Raises DocumentIdentityTaken when the identity index refuses the row."""
    did = str(uuid.uuid4())
    prov = meta.get("provenance")
    try:
        await pool().execute(
            """INSERT INTO docengine.documents
               (id, job_id, code, doctype, title_mk, title_en, version, path, bytes, verify,
                created_by, org_id, source, supersedes_id, qa_audit, provenance)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)""",
            did, job_id, meta["code"], meta["doctype"], meta.get("title_mk", ""),
            meta.get("title_en", ""), meta.get("version", "1.0"), meta["path"],
            meta["bytes"], meta["verify"],
            meta.get("created_by") or "", meta.get("org_id"), meta.get("source") or "workflow",
            meta.get("supersedes_id"), meta.get("qa_audit"),
            None if prov is None else json.dumps(prov),
        )
    except asyncpg.UniqueViolationError as e:
        if "de_docs_identity" in str(e):
            raise DocumentIdentityTaken(meta["code"], str(meta.get("version", "1.0"))) from e
        raise
    return did


def _doc_row(r) -> dict:
    d = dict(r)
    for k in ("id", "job_id", "supersedes_id"):
        if k in d:
            d[k] = str(d[k]) if d[k] else None
    for k in ("created_at", "reviewed_at"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    if isinstance(d.get("provenance"), str):
        d["provenance"] = json.loads(d["provenance"])
    return d


async def documents_list(org_id: str, limit: int = 100, offset: int = 0) -> dict:
    """One page of the organisation's registry, newest first, with the total
    so a caller can page (review 2026-09-27, DI-21: the list was capped at
    100 with no way past it, and every COQ regeneration adds a row).

    org_id is REQUIRED (DI-13): the registry holds every organisation's
    controlled documents and a read is always for one of them."""
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    rows = await pool().fetch(
        f"SELECT {_DOC_LIST_COLS} FROM docengine.documents"  # nosec B608
        " WHERE org_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        org_id, limit, offset,
    )
    total = await pool().fetchval(
        "SELECT count(*) FROM docengine.documents WHERE org_id = $1", org_id)
    return {"documents": [_doc_row(r) for r in rows],
            "total": int(total or 0), "limit": limit, "offset": offset}


async def document_get(did: str, org_id: str) -> dict | None:
    """One registry row, only if it belongs to `org_id`. Another
    organisation's document reads as absent, not as forbidden — the id
    itself must not leak existence across tenants."""
    r = await pool().fetchrow(
        "SELECT * FROM docengine.documents WHERE id = $1 AND org_id = $2", did, org_id)
    if not r:
        return None
    return _doc_row(r)
