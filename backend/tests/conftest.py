"""Shared fixtures.

Runs against two real Postgres databases (RLS is the app's actual security
model — it can't be meaningfully exercised against a mock or SQLite).
Identity data (organizations/profiles) lives in the users DB, work data in
the tasks DB — same split as production's two containers. Each test that
needs data gets its own fresh organization via the `org` fixture; teardown
deletes the org from the users DB (cascades profiles there) and explicitly
purges the org's rows from the tasks DB (no cross-database cascade exists).

Requires USERS_/TASKS_DATABASE_URL (+ _ADMIN_ variants) to point at real
(test-only!) databases with the schema loaded — see
backend/scripts/load_schema.sh and backend/README.md.
"""
import os
import uuid

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "pytest-test-secret-not-for-production")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import close_pools, init_pools, tasks_admin_pool, users_admin_pool
from app.security import hash_password


def pytest_configure(config):
    """Fail loudly if pytest's logging plugin has been disabled.

    `-p no:logging` is a tempting way to quieten this suite (it is very chatty:
    every request is logged as JSON). But that plugin is what provides the
    `caplog` fixture, and test_notifications.py uses `caplog` to prove a failed
    notification recipient is LOGGED rather than silently swallowed. With the
    plugin off, that test does not fail — it ERRORS with "fixture 'caplog' not
    found", which in a 600-test run reads exactly like a real regression and
    sends you hunting through unrelated code.

    That misdiagnosis has happened twice. Use `-q`, `--tb=short`, or
    `--log-cli-level=CRITICAL` to reduce noise; never `-p no:logging`."""
    if not config.pluginmanager.hasplugin("logging"):
        raise pytest.UsageError(
            "pytest's logging plugin is disabled (-p no:logging), which removes the "
            "`caplog` fixture and makes test_notifications.py ERROR in a way that "
            "looks like a code regression. Drop the flag; use -q or "
            "--log-cli-level=CRITICAL to reduce output instead."
        )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _pools():
    await init_pools()
    # test_audit.py's tamper tests deliberately break the hash chain (delete/
    # rewrite audit rows) and per-test purges never touch audit_log — so on a
    # REUSED local database the next session starts with a poisoned chain and
    # the intact-chain tests fail for reasons that have nothing to do with the
    # code under test. Start every session from an empty chain instead. (CI is
    # unaffected — its databases are always fresh.)
    for pool in (users_admin_pool(), tasks_admin_pool()):
        # DELETE, not TRUNCATE — app_admin's grants are S/I/U/D only.
        await pool.execute("DELETE FROM audit_log")
    yield
    await close_pools()


@pytest_asyncio.fixture
async def client():
    from app.main import app as fastapi_app
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def _reset_login_rate_limit():
    # ASGITransport gives every request the same fake client IP, so
    # auth.py's in-process rate limiter would otherwise accumulate failed
    # attempts across unrelated tests and eventually 429 a legitimate one.
    from app.api import auth
    auth._failed_attempts.clear()
    yield
    auth._failed_attempts.clear()


async def purge_org(org_id) -> None:
    """Remove every row the org owns, in both databases. The users DB
    cascades from organizations; the tasks DB has no organizations table
    (and no cross-database FK), so its tables are purged explicitly —
    children before parents. audit_log rows stay in both (the hash chain
    must never be edited)."""
    t = tasks_admin_pool()
    for table in ("ai_agent_bindings", "ai_pins", "weekly_documents", "handoffs",
                  "notifications", "events", "task_comments",
                  "task_workflow_events", "task_assignees", "task_links", "work_sessions",
                  "task_progress",
                  # QC LIMS — children before parents; the cert→spec FK is
                  # RESTRICT, so certificates (and their CASCADE results) must
                  # go before specifications. The CoQ aggregation cites certs
                  # (RESTRICT) and specs (RESTRICT), so it goes before both.
                  "qc_coq_lines", "qc_coq_sources", "qc_coq",
                  "qc_batch_genealogy", "qc_document_files", "qc_signatures",
                  # eCoA/CoA ingestion cluster — everything citing
                  # qc_coa_documents (CASCADE/SET NULL) goes before it.
                  "qc_field_placeholders", "qc_ecoa_checklist", "qc_coa_chunks",
                  "qc_coa_verifications", "qc_coa_extractions", "qc_coa_documents",
                  # OOS/CAPA cluster — cites qc_results (SET NULL) and
                  # qc_oos_records (CASCADE), so it goes before both.
                  "qc_oos_notifications", "qc_oos_register", "qc_oos_records",
                  "qc_results",
                  # custody cluster — chain cites samples (CASCADE) and SFRs
                  # (SET NULL); SFRs cite RQS (SET NULL) and samples (SET NULL).
                  "qc_chain_of_custody", "qc_sample_field_records", "qc_sampling_requests",
                  "qc_sample_transports", "qc_stability_studies", "qc_water_tests",
                  "qc_certificates", "qc_spec_parameters", "qc_samples", "qc_laboratories",
                  "qc_sampling_plans", "qc_specifications",
                  # cultivation — plants + phase events cite batches (RESTRICT),
                  # batches cite cultivars (RESTRICT) and rooms (RESTRICT), so the
                  # order is: leaves -> batches -> cultivars/rooms.
                  "decon_tool_log", "decon_positive_controls",
                  "decon_swabs", "decon_bleach_log", "decon_step_signoffs",
                  "decon_room_cycles",
                  # waste lines cite batches AND rooms (both RESTRICT), so they
                  # come before either. The lines->manifest edge is CASCADE, but
                  # both are listed: this is a per-org DELETE, not a DROP, and
                  # relying on the cascade would leave the intent implicit.
                  # corridor_cleanings cites rooms AND waste_manifests (both
                  # RESTRICT), so it precedes the manifests as well as the rooms.
                  "corridor_cleanings",
                  "waste_manifest_lines", "waste_manifests",
                  # harvests, ipm_applications and irrigation_events all cite
                  # batches AND rooms (RESTRICT), so they precede both — same
                  # reason as the waste lines above.
                  "harvests", "ipm_applications", "irrigation_events", "biosecurity_events",
                  "plant_phase_events", "plants", "plant_batches", "cultivars",
                  "rooms",
                  "task_dependencies", "tasks", "calendar_weeks", "departments"):
        await t.execute(f"DELETE FROM {table} WHERE org_id=$1", org_id)
    await users_admin_pool().execute("DELETE FROM organizations WHERE id=$1", org_id)


@pytest_asyncio.fixture
async def org():
    """A fresh org + one ADMIN profile with a known password (must_change_password
    already cleared). This app has no self-signup — the very first admin in any
    org is always seeded directly, same as this fixture does."""
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    suffix = uuid.uuid4().hex[:8]
    username = f"admin_{suffix}"
    email = f"admin_{suffix}@test.invalid"
    password = "TestPassword123456"
    pool = users_admin_pool()
    await pool.execute(
        "INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
        org_id, f"Test Org {suffix}", f"test-{suffix}")
    await pool.execute(
        "INSERT INTO profiles(id, org_id, username, email, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,$6,'ADMIN',false)",
        admin_id, org_id, username, email, hash_password(password), "Test Admin")
    yield {
        "org_id": str(org_id), "admin_id": str(admin_id),
        "username": username, "email": email, "password": password,
    }
    await purge_org(org_id)


@pytest_asyncio.fixture
async def admin_token(client, org):
    r = await client.post("/auth/login", json={"email": org["username"], "password": org["password"]})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


async def create_user(client, admin_headers, *, role="USER", full_name="Test User",
                      department_id=None):
    """Provision a user via the real API (as an admin would) and return
    (profile, otp) — the OTP is a real one-time password from a real
    /auth/users call, not a shortcut."""
    r = await client.post("/auth/users", json={
        "username": f"user_{uuid.uuid4().hex[:8]}", "full_name": full_name, "role": role,
        "department_id": department_id,
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    return body["user"], body["otp"]


async def login_and_set_password(client, username, otp, new_password="NewPassword123456"):
    """First-login flow: OTP login -> forced change-password -> real session."""
    r = await client.post("/auth/login", json={"email": username, "password": otp})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["must_change_password"] is True
    tmp_token = r.json()["access_token"]
    r = await client.post("/auth/change-password", json={"new_password": new_password},
                           headers={"Authorization": f"Bearer {tmp_token}"})
    assert r.status_code == 200, r.text
    r = await client.post("/auth/login", json={"email": username, "password": new_password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
