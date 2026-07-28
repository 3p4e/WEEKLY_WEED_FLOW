"""Real-Postgres fixture for the DocEngine persistence layer.

Until now every DocEngine test ran against fakes: `db.init()` returns early
when DOCENGINE_DATABASE_URL is empty ("tests / degraded mode"), so app/db.py —
job_create, job_update, document_create, reap_stale_jobs — had NO executed
coverage at all. That is how `reap_stale_jobs` shipped never having run once:
its only caller wraps it in `except Exception: log.warning(...)`, so a wrong
column name would have surfaced as a startup warning nobody reads while stale
jobs piled up forever — exactly the condition the function exists to prevent.

`db` is a module with a global pool, so the fixture is function-scoped and
opens/closes per test: cheap against a local Postgres and it keeps one test's
failure from poisoning the next. Tests SKIP rather than fail when no DSN is
configured, so `pytest` in a bare checkout still works; CI sets the variable,
which is what makes the coverage real.
"""
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.config import settings  # noqa: E402


@pytest_asyncio.fixture
async def dbpool():
    """An initialised, empty docengine schema. Skips when no DSN is set."""
    if not settings.database_url:
        pytest.skip("DOCENGINE_DATABASE_URL not set — DB-backed tests skipped")
    await db.init()
    assert db.ready(), "db.init() did not open a pool despite a DSN being set"
    # documents references jobs, so truncate together.
    await db.pool().execute(
        "TRUNCATE docengine.documents, docengine.jobs RESTART IDENTITY CASCADE")
    try:
        yield db.pool()
    finally:
        await db.close()


async def seed_job(pool, *, status: str, age_minutes: int = 0,
                   error: str | None = None, kind: str = "workflow") -> str:
    """Insert a job with a backdated updated_at, which is the only thing
    reap_stale_jobs keys on. Bypasses job_create deliberately: the point is to
    control updated_at, which job_create never lets a caller set."""
    import uuid
    jid = str(uuid.uuid4())
    await pool.execute(
        "INSERT INTO docengine.jobs (id, kind, status, error, updated_at)"
        " VALUES ($1, $2, $3, $4, now() - make_interval(mins => $5))",
        jid, kind, status, error, age_minutes)
    return jid


async def status_of(pool, jid: str) -> str:
    return await pool.fetchval("SELECT status FROM docengine.jobs WHERE id = $1", jid)
