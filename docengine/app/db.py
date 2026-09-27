# docengine.app.db — workflow state in Postgres (own schema `docengine`).
# This fixes the qms-creator per-worker in-memory bug class: any uvicorn
# worker can serve any poll because state lives in the database.
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Iterable

import asyncpg

from .config import settings

_pool: asyncpg.Pool | None = None

# One id per process boot. Every job is stamped with the worker that owns it
# (the background task lives in that process), so a job whose worker is not
# THIS one belongs to a process that no longer exists — a redeploy, an OOM
# kill — and can be failed at once, whatever its age. With --workers 1 that
# is exact (review 2026-09-27, DI-04). Overridable for tests only.
WORKER_ID = os.environ.get("DOCENGINE_WORKER_ID") or uuid.uuid4().hex

_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS docengine;
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
CREATE INDEX IF NOT EXISTS de_docs_org_created ON docengine.documents(org_id, created_at DESC);
"""

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
        await c.execute(_SCHEMA)


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
    await pool().execute(
        f"UPDATE docengine.jobs SET {', '.join(sets)} WHERE id = ${len(vals)}", *vals  # nosec B608
    )


# A job is only ever advanced by the worker that owns it, so a worker killed
# mid-run (OOM, redeploy) leaves its row at 'running'/'queued' forever: the
# poller waits on it indefinitely and nothing ever cleans it up. Two sweeps
# cover the two ways that happens:
#
#   reap_orphaned_jobs — the worker is GONE. Every unfinished job stamped with
#     another worker id is failed at once, whatever its age. This is the
#     redeploy case: the old process closed its pool mid-job, the new one
#     starts seconds later, and the row is only minutes old — an age-based
#     sweep alone left it 'running' forever (review 2026-09-27, DI-04).
#   reap_stale_jobs — the worker is alive but the job stopped moving. Age is
#     the signal; 60 minutes sits above the longest legal silence between two
#     job_update() calls (one §6A audit turn + a two-turn repair at the 900 s
#     read timeout). Jobs the live process still has a task for are excluded
#     by the caller, so a slow-but-alive job is never failed under its task.
STALE_JOB_MINUTES = 60
_ABANDONED = "abandoned: worker %s is gone (restart or redeploy killed it mid-run)"


async def reap_orphaned_jobs(current_worker: str | None = None) -> int:
    """Fail every unfinished job that belongs to a worker other than this
    one, regardless of age. Returns how many."""
    if _pool is None:
        return 0
    me = current_worker or WORKER_ID
    rows = await pool().fetch(
        "UPDATE docengine.jobs SET status='failed', updated_at=now(),"
        "   error = COALESCE(NULLIF(error,''),"
        "                    format($2::text, COALESCE(worker_id, '<unknown>')))"
        " WHERE status IN ('queued','running')"
        "   AND worker_id IS DISTINCT FROM $1"
        " RETURNING id", me, _ABANDONED)
    return len(rows)


async def reap_stale_jobs(older_than_minutes: int = STALE_JOB_MINUTES,
                          exclude: Iterable[str] = ()) -> int:
    """Fail jobs that have made no progress for `older_than_minutes`. Returns
    how many. `exclude` names jobs the caller still has a live task for.

    Uses updated_at, which every job_update() touches, so a job still making
    progress is never reaped. Runs at startup and then periodically from
    main._reaper_loop — a hung worker is exactly the case a startup-only
    sweep cannot see."""
    if _pool is None:
        return 0
    keep = [uuid.UUID(x) for x in exclude]
    rows = await pool().fetch(
        "UPDATE docengine.jobs SET status='failed', updated_at=now(),"
        "   error = COALESCE(NULLIF(error,''), 'abandoned: no progress for '"
        "                    || $1::text || ' minutes (worker killed mid-run)')"
        " WHERE status IN ('queued','running')"
        "   AND updated_at < now() - ($1::text || ' minutes')::interval"
        "   AND NOT (id = ANY($2::uuid[]))"
        " RETURNING id", str(older_than_minutes), keep)
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


async def document_create(job_id: str | None, meta: dict) -> str:
    """Register one verified document. `meta` carries the registry identity
    (code/doctype/titles/version), the artefact (path/bytes/verify) and the
    record fields: created_by, org_id, source ('workflow'|'revise'|'build'),
    supersedes_id, qa_audit (None when the §6A auditor never saw it) and
    provenance. reviewed_by is never set here: registration is not review."""
    did = str(uuid.uuid4())
    prov = meta.get("provenance")
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
        f"SELECT {_DOC_LIST_COLS} FROM docengine.documents"  # nosec B608 — code-controlled column list
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
