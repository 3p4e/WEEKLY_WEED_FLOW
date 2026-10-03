"""app/db.py against a real Postgres — the layer that had no executed coverage.

The stale-job reaper gets the most attention here because it is the piece with
the worst failure mode: it runs once at startup inside a broad `except
Exception: log.warning(...)`, so every way it can be wrong is silent. A job
wrongly reaped destroys a running build's record; a job wrongly SPARED sits at
'running' forever with a poller waiting on it. Both directions are pinned.
"""
import uuid

import pytest

from app import db

pytestmark = pytest.mark.asyncio


async def seed_job(pool, *, status: str, age_minutes: int = 0,
                   error: str | None = None, kind: str = "workflow") -> str:
    """Insert a job with a backdated updated_at — the only thing the reaper
    keys on. Bypasses job_create deliberately: the point is to control
    updated_at, which job_create never lets a caller set."""
    jid = str(uuid.uuid4())
    await pool.execute(
        "INSERT INTO docengine.jobs (id, kind, status, error, updated_at)"
        " VALUES ($1, $2, $3, $4, now() - make_interval(mins => $5))",
        jid, kind, status, error, age_minutes)
    return jid


async def status_of(pool, jid: str) -> str:
    return await pool.fetchval("SELECT status FROM docengine.jobs WHERE id = $1", jid)


async def test_reaper_fails_jobs_abandoned_by_a_killed_worker(dbpool):
    stale_running = await seed_job(dbpool, status="running", age_minutes=120)
    stale_queued = await seed_job(dbpool, status="queued", age_minutes=999)

    assert await db.reap_stale_jobs() == 2

    assert await status_of(dbpool, stale_running) == "failed"
    assert await status_of(dbpool, stale_queued) == "failed"
    err = await dbpool.fetchval(
        "SELECT error FROM docengine.jobs WHERE id = $1", stale_running)
    assert "abandoned" in err and "worker killed mid-run" in err


async def test_reaper_spares_everything_it_must(dbpool):
    """The dangerous direction. Three distinct reasons a job must survive:

    - `fresh`: still making progress. job_update() touches updated_at on every
      stage change, so an active build is continuously young.
    - `awaiting_review`: blocked on a HUMAN. Legitimately days old — reaping it
      would destroy the review gate, so it must never appear in the predicate.
    - `done`: terminal. Reaping it would rewrite finished history.
    """
    fresh = await seed_job(dbpool, status="running", age_minutes=5)
    review = await seed_job(dbpool, status="awaiting_review", age_minutes=5000)
    done = await seed_job(dbpool, status="done", age_minutes=5000)
    failed = await seed_job(dbpool, status="failed", age_minutes=5000)

    assert await db.reap_stale_jobs() == 0

    assert await status_of(dbpool, fresh) == "running"
    assert await status_of(dbpool, review) == "awaiting_review"
    assert await status_of(dbpool, done) == "done"
    assert await status_of(dbpool, failed) == "failed"


async def test_reaper_keeps_an_error_the_job_already_recorded(dbpool):
    """A job that recorded WHY it failed and then died before its status caught
    up must keep that message — it is the only diagnosis anyone has. The
    COALESCE(NULLIF(error,'')) only fills in a blank one."""
    jid = await seed_job(dbpool, status="running", age_minutes=300,
                         error="letta: connection reset")
    assert await db.reap_stale_jobs() == 1
    row = await dbpool.fetchrow(
        "SELECT status, error FROM docengine.jobs WHERE id = $1", jid)
    assert row["status"] == "failed"
    assert row["error"] == "letta: connection reset"


async def test_reaper_threshold_is_honoured(dbpool):
    """Just inside the window survives; just outside does not. Pins that the
    cutoff is really applied rather than the predicate matching everything."""
    inside = await seed_job(dbpool, status="running", age_minutes=59)
    outside = await seed_job(dbpool, status="running", age_minutes=61)
    assert await db.reap_stale_jobs(60) == 1
    assert await status_of(dbpool, inside) == "running"
    assert await status_of(dbpool, outside) == "failed"


async def test_reaper_is_a_no_op_without_a_pool():
    """Called before init() (or in degraded mode) it must return 0, not raise —
    main.py's lifespan calls it before the service is known to have a DB."""
    await db.close()
    assert not db.ready()
    assert await db.reap_stale_jobs() == 0


async def test_job_round_trip(dbpool):
    """job_create -> job_get -> job_update, incl. the jsonb columns that
    job_update special-cases and the updated_at bump the reaper depends on."""
    jid = await db.job_create("workflow", {"questionnaire": "sop_qc"}, created_by="tester")
    job = await db.job_get(jid)
    assert job["status"] == "queued" and job["kind"] == "workflow"
    assert job["payload"]["questionnaire"] == "sop_qc"

    before = await dbpool.fetchval(
        "SELECT updated_at FROM docengine.jobs WHERE id = $1", jid)
    await db.job_update(jid, status="done", stage="done", result={"document_id": "x"})
    after = await db.job_get(jid)
    assert after["status"] == "done"
    assert after["result"]["document_id"] == "x"
    bumped = await dbpool.fetchval(
        "SELECT updated_at FROM docengine.jobs WHERE id = $1", jid)
    assert bumped >= before, "job_update must move updated_at — the reaper keys on it"

    assert await db.job_get("00000000-0000-0000-0000-000000000000") is None


async def test_document_create_and_read_back(dbpool):
    jid = await db.job_create("workflow", {}, org_id="org-a")
    did = await db.document_create(jid, {
        "code": "QCSOP-999", "doctype": "SOP", "title_mk": "МК", "title_en": "EN",
        "version": "1.0", "path": "/data/out/QCSOP-999.docx", "bytes": 4242,
        "verify": "RESULT: PASS", "org_id": "org-a", "created_by": "qa.one",
        "qa_audit": "Verdict: PASS", "provenance": {"sections": [{"section": "1.0"}]},
    })
    doc = await db.document_get(did, "org-a")
    assert doc["code"] == "QCSOP-999" and doc["bytes"] == 4242
    assert doc["verify"] == "RESULT: PASS"
    assert doc["created_by"] == "qa.one" and doc["source"] == "workflow"
    assert doc["qa_audit"] == "Verdict: PASS"
    assert doc["provenance"] == {"sections": [{"section": "1.0"}]}
    # registration is not review: nobody has reviewed it until someone does
    assert doc["reviewed_by"] is None and doc["reviewed_at"] is None
    page = await db.documents_list("org-a")
    assert page["total"] == 1 and page["documents"][0]["id"] == did
    assert page["documents"][0]["audited"] is True


# ── org scope (DI-13) ────────────────────────────────────────────────────────
async def _register(org, code, **extra):
    return await db.document_create(None, {
        "code": code, "doctype": "FORM", "title_mk": "МК", "title_en": "EN",
        "version": "1.0", "path": f"/data/out/{code}.docx", "bytes": 10,
        "verify": "RESULT: PASS", "org_id": org, **extra,
    })


async def test_documents_are_invisible_to_another_organisation(dbpool):
    """One shared registry, many tenants: another organisation's document
    must read as ABSENT (not forbidden — the id must not leak existence)."""
    mine = await _register("org-a", "A-1")
    theirs = await _register("org-b", "B-1")
    assert await db.document_get(theirs, "org-a") is None
    assert await db.document_get(mine, "org-a") is not None
    ids = {d["id"] for d in (await db.documents_list("org-a"))["documents"]}
    assert ids == {mine}
    assert (await db.documents_list("org-b"))["total"] == 1


async def test_a_document_with_no_org_is_listed_by_nobody(dbpool):
    """Rows registered before org scoping existed carry NULL and are
    reachable through no organisation until the owner backfills them (the
    rollout step in docs/DEPLOY.md). Fail closed rather than show them to
    whoever asks first."""
    orphan = await db.document_create(None, {
        "code": "OLD-1", "doctype": "SOP", "title_mk": "МК", "title_en": "EN",
        "version": "1.0", "path": "/data/out/OLD-1.docx", "bytes": 10,
        "verify": "RESULT: PASS",
    })
    assert await db.document_get(orphan, "org-a") is None
    assert (await db.documents_list("org-a"))["total"] == 0


# ── paging (DI-21) ───────────────────────────────────────────────────────────
async def test_documents_list_pages_past_the_old_100_row_cap(dbpool):
    for i in range(120):
        await _register("org-p", f"P-{i:03d}")
    first = await db.documents_list("org-p", limit=100, offset=0)
    second = await db.documents_list("org-p", limit=100, offset=100)
    assert first["total"] == 120 and second["total"] == 120
    assert len(first["documents"]) == 100 and len(second["documents"]) == 20
    seen = {d["id"] for d in first["documents"]} | {d["id"] for d in second["documents"]}
    assert len(seen) == 120
    # newest first, and the page is what the caller asked for
    assert first["limit"] == 100 and second["offset"] == 100


async def test_documents_list_clamps_an_abusive_limit(dbpool):
    await _register("org-p", "P-0")
    page = await db.documents_list("org-p", limit=100_000, offset=-5)
    assert page["limit"] == 500 and page["offset"] == 0


# ── lineage (DI-07) ──────────────────────────────────────────────────────────
async def test_a_revision_points_at_the_document_it_supersedes(dbpool):
    v1 = await _register("org-a", "SOP-X", version="1.0")
    v2 = await _register("org-a", "SOP-X", version="1.1", supersedes_id=v1, source="revise")
    doc = await db.document_get(v2, "org-a")
    assert doc["supersedes_id"] == v1 and doc["source"] == "revise"
    rows = {d["id"]: d for d in (await db.documents_list("org-a"))["documents"]}
    assert rows[v2]["supersedes_id"] == v1 and rows[v1]["supersedes_id"] is None


async def test_an_unaudited_build_is_marked_as_such(dbpool):
    did = await _register("org-a", "PP-COA-1", source="build", qa_audit=None,
                          created_by="qp.one")
    row = (await db.documents_list("org-a"))["documents"][0]
    assert row["id"] == did and row["audited"] is False
    assert row["source"] == "build" and row["created_by"] == "qp.one"


# ── worker-aware reaping (DI-04) ─────────────────────────────────────────────
async def test_job_create_stamps_this_worker(dbpool):
    jid = await db.job_create("workflow", {}, org_id="org-a")
    assert await dbpool.fetchval(
        "SELECT worker_id FROM docengine.jobs WHERE id = $1", jid) == db.WORKER_ID


async def test_orphan_reaper_fails_another_workers_jobs_regardless_of_age(dbpool):
    """The redeploy case: a job at 'regulatory-check 4.0', updated two
    minutes ago, whose worker is gone. The age sweep alone leaves it
    'running' forever (it is younger than the threshold); the orphan sweep
    fails it at once because its worker id is not this process's."""
    gone = str(uuid.uuid4())
    await dbpool.execute(
        "INSERT INTO docengine.jobs (id, kind, status, stage, worker_id, updated_at)"
        " VALUES ($1, 'workflow', 'running', 'regulatory-check 4.0', $2,"
        "         now() - interval '2 minutes')", gone, "old-worker-boot")
    queued = str(uuid.uuid4())
    await dbpool.execute(
        "INSERT INTO docengine.jobs (id, kind, status, worker_id) VALUES ($1, 'revise', 'queued', $2)",
        queued, "old-worker-boot")
    legacy = await seed_job(dbpool, status="running", age_minutes=1)  # worker_id NULL

    assert await db.reap_orphaned_jobs() == 3
    for jid in (gone, queued, legacy):
        assert await status_of(dbpool, jid) == "failed"
    err = await dbpool.fetchval("SELECT error FROM docengine.jobs WHERE id = $1", gone)
    assert "old-worker-boot" in err and "gone" in err


async def test_orphan_reaper_spares_this_workers_own_jobs(dbpool):
    mine = await db.job_create("workflow", {}, org_id="org-a")
    await db.job_update(mine, status="running", stage="generate 3.0")
    done = await db.job_create("workflow", {}, org_id="org-a")
    await db.job_update(done, status="done")
    assert await db.reap_orphaned_jobs() == 0
    assert await status_of(dbpool, mine) == "running"


async def test_stale_reaper_skips_jobs_the_live_process_still_owns(dbpool):
    """A slow-but-alive job (its task still exists in this process) is never
    failed under its own task, however old its last update; a job with no
    task is."""
    alive = await seed_job(dbpool, status="running", age_minutes=500)
    dead = await seed_job(dbpool, status="running", age_minutes=500)
    assert await db.reap_stale_jobs(exclude=[alive]) == 1
    assert await status_of(dbpool, alive) == "running"
    assert await status_of(dbpool, dead) == "failed"


# ── heartbeat-aware reaping (DI2-02) ─────────────────────────────────────────
async def _worker_row(pool, worker_id: str, beat_age_s: int) -> None:
    await pool.execute(
        "INSERT INTO docengine.workers (worker_id, heartbeat_at)"
        " VALUES ($1, now() - make_interval(secs => $2))"
        " ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = EXCLUDED.heartbeat_at",
        worker_id, float(beat_age_s))


async def _owned_job(pool, worker_id: str, status: str = "running") -> str:
    jid = str(uuid.uuid4())
    await pool.execute(
        "INSERT INTO docengine.jobs (id, kind, status, worker_id) VALUES ($1, 'workflow', $2, $3)",
        jid, status, worker_id)
    return jid


async def test_heartbeat_records_this_worker_and_refreshes_it(dbpool):
    await db.heartbeat()
    first = await dbpool.fetchval(
        "SELECT heartbeat_at FROM docengine.workers WHERE worker_id = $1", db.WORKER_ID)
    assert first is not None
    await db.heartbeat()
    again = await dbpool.fetchval(
        "SELECT heartbeat_at FROM docengine.workers WHERE worker_id = $1", db.WORKER_ID)
    assert again >= first
    assert await dbpool.fetchval("SELECT count(*) FROM docengine.workers") == 1


async def test_orphan_reaper_spares_a_worker_that_still_beats_and_fails_one_that_stopped(dbpool):
    """Review 2026-09-27, DI2-02. Two processes on one database each failed
    the other's live jobs every sweep ("not THIS worker" read as "gone").
    A worker is gone when its heartbeat is stale or absent — never merely
    because it is a different process."""
    await _worker_row(dbpool, "alive-worker", beat_age_s=30)
    await _worker_row(dbpool, "dead-worker", beat_age_s=db.WORKER_STALE_S + 60)
    alive_job = await _owned_job(dbpool, "alive-worker")
    dead_job = await _owned_job(dbpool, "dead-worker")
    no_row_job = await _owned_job(dbpool, "never-beat")
    legacy = await seed_job(dbpool, status="running", age_minutes=1)  # worker_id NULL

    assert await db.reap_orphaned_jobs() == 3
    assert await status_of(dbpool, alive_job) == "running"
    for jid in (dead_job, no_row_job, legacy):
        assert await status_of(dbpool, jid) == "failed"
    err = await dbpool.fetchval("SELECT error FROM docengine.jobs WHERE id = $1", dead_job)
    assert "dead-worker" in err and "gone" in err
    # the beating worker's job is failed once its beats stop
    await _worker_row(dbpool, "alive-worker", beat_age_s=db.WORKER_STALE_S + 1)
    assert await db.reap_orphaned_jobs() == 1
    assert await status_of(dbpool, alive_job) == "failed"


async def test_orphan_reaper_yields_to_a_sweep_already_running_elsewhere(dbpool):
    """One sweep at a time, under a transaction-scoped advisory lock: two
    processes never race the same rows. While another connection holds the
    lock the sweep reports 0 and touches nothing; it reaps on the next pass."""
    gone = await _owned_job(dbpool, "gone-worker")
    async with dbpool.acquire() as other, other.transaction():
        assert await other.fetchval("SELECT pg_try_advisory_xact_lock(hashtext('docengine.reaper'))")
        assert await db.reap_orphaned_jobs() == 0
        assert await status_of(dbpool, gone) == "running"
    assert await db.reap_orphaned_jobs() == 1
    assert await status_of(dbpool, gone) == "failed"


async def test_stale_reaper_judges_only_this_workers_jobs(dbpool):
    """Another live worker knows which of its silent jobs still have a task;
    its rows are its own to judge (or the orphan sweep's, once it stops
    beating). Ownerless legacy rows are still this worker's to clean."""
    await _worker_row(dbpool, "other-worker", beat_age_s=10)
    theirs = await _owned_job(dbpool, "other-worker")
    await dbpool.execute("UPDATE docengine.jobs SET updated_at = now() - interval '500 minutes'"
                         " WHERE id = $1", theirs)
    mine = await db.job_create("workflow", {}, org_id="org-a")
    await dbpool.execute("UPDATE docengine.jobs SET status='running',"
                         " updated_at = now() - interval '500 minutes' WHERE id = $1", mine)
    legacy = await seed_job(dbpool, status="running", age_minutes=500)
    assert await db.reap_stale_jobs() == 2
    assert await status_of(dbpool, theirs) == "running"
    assert await status_of(dbpool, mine) == "failed"
    assert await status_of(dbpool, legacy) == "failed"


# ── one identity per controlled document (DI2-03) ────────────────────────────
async def test_the_identity_index_exists_after_init(dbpool):
    assert db.identity_index_ok() is True
    assert await dbpool.fetchval(
        "SELECT indexdef FROM pg_indexes WHERE schemaname='docengine' AND indexname='de_docs_identity'")


async def test_registry_refuses_a_second_document_under_an_existing_identity(dbpool):
    """Review 2026-09-27, DI2-03. A second revision of the same source, or the
    same questionnaire run twice under one code, registered the same
    code+version again with different bytes: two controlled documents with
    one identity. The registry now holds one row per (organisation, code,
    version) for everything but /build artefacts."""
    v1 = await _register("org-a", "SOP-X", version="1.0")
    await _register("org-a", "SOP-X", version="1.1", supersedes_id=v1, source="revise")
    with pytest.raises(db.DocumentIdentityTaken) as ei:
        await _register("org-a", "SOP-X", version="1.1", supersedes_id=v1, source="revise")
    assert "SOP-X" in str(ei.value) and "1.1" in str(ei.value)
    with pytest.raises(db.DocumentIdentityTaken):
        await _register("org-a", "SOP-X", version="1.0")  # a re-run of the first draft
    # another organisation may hold the same code+version; a /build artefact
    # (a certificate regenerated) is not a controlled-document identity
    await _register("org-b", "SOP-X", version="1.1")
    await _register("org-a", "PP-COA-1", version="01", source="build")
    await _register("org-a", "PP-COA-1", version="01", source="build")
    assert sorted(await db.registered_versions("org-a", "SOP-X")) == ["1.0", "1.1"]
    assert await db.registered_versions("org-a", "PP-COA-1") == []   # build rows carry no identity
    assert await db.registered_versions(None, "SOP-X") == []
