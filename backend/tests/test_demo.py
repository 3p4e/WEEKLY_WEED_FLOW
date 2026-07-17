"""Live demo mode (app/api/demo.py + app/demo_org.py).

The demo is a REAL session against the REAL backend, isolated from every
tenant by the same org_id RLS. These tests run against the two real test
databases like the rest of the suite. They exercise: the disabled-by-default
404, the start→token→seeded-data path through real endpoints, RLS isolation
from another org, reset wiping visitor rows while re-seeding, audit-chain
integrity across a wipe, exit invalidating the session, and the per-IP
start throttle.
"""
import uuid

import pytest
import pytest_asyncio

from app import demo_org
from app.config import settings
from app.db import tasks_admin_pool, users_admin_pool


@pytest_asyncio.fixture
async def demo_on():
    """Turn the feature on for the test and guarantee the shared demo org is
    torn down afterwards (rows + the organizations row itself), so a reused
    local database never leaks demo state between runs. Also clears the
    in-process start throttle so tests don't 429 each other."""
    from app.api import demo as demo_router
    prev = settings.demo_enabled
    settings.demo_enabled = True
    demo_router._starts.clear()
    try:
        yield
    finally:
        settings.demo_enabled = prev
        demo_router._starts.clear()
        org_id = await demo_org.get_demo_org_id()
        if org_id is not None:
            await demo_org.wipe_demo_org(org_id)
            await users_admin_pool().execute(
                "DELETE FROM organizations WHERE id=$1", org_id)


async def _start(client, cast="cartoon"):
    r = await client.post("/demo/start", json={"cast": cast})
    assert r.status_code == 200, r.text
    body = r.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


async def test_disabled_by_default(client):
    # Default settings.demo_enabled is False — the endpoint simply doesn't exist.
    r = await client.post("/demo/start", json={"cast": "cartoon"})
    assert r.status_code == 404
    r = await client.post("/demo/exit")
    assert r.status_code in (401, 404)  # 404 disabled OR 401 no token


async def test_start_mints_admin_token(client, demo_on):
    body, headers = await _start(client)
    assert body["cast"] == "cartoon"
    assert body["user"]["role"] == "ADMIN"
    assert body["user"]["username"].startswith("demo.")
    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "ADMIN"


async def test_start_seeds_every_surface(client, demo_on):
    _, headers = await _start(client)

    tasks = await client.get("/tasks", headers=headers)
    assert tasks.status_code == 200
    assert len(tasks.json()) > 10  # the ported cast dataset

    fac = await client.get("/facility", headers=headers)
    assert fac.status_code == 200
    assert len(fac.json()["rooms"]) == 6

    specs = await client.get("/qc/specifications", headers=headers)
    assert specs.status_code == 200
    assert any(s["status"] == "ACTIVE" for s in specs.json())

    samples = await client.get("/qc/samples", headers=headers)
    assert samples.status_code == 200
    assert any(s["status"] == "QUARANTINE" for s in samples.json())

    coas = await client.get("/qc/certificates", headers=headers)
    assert coas.status_code == 200
    assert len(coas.json()) >= 1

    oos = await client.get("/qc/oos", headers=headers)
    assert oos.status_code == 200
    assert any(o["phase"] == "I" for o in oos.json())


async def test_reset_wipes_visitor_rows_and_reseeds(client, demo_on):
    _, headers = await _start(client)
    before = await client.get("/tasks", headers=headers)
    seeded_count = len(before.json())
    assert seeded_count > 0

    # A visitor-created row: inject a marker task straight into the demo org.
    org_id = await demo_org.get_demo_org_id()
    row = await tasks_admin_pool().fetchrow(
        "SELECT user_id, department_id, week_id, week_start FROM tasks"
        " WHERE org_id=$1 LIMIT 1", org_id)
    marker = f"VISITOR-{uuid.uuid4().hex[:8]}"
    await tasks_admin_pool().execute(
        "INSERT INTO tasks(org_id, user_id, title, status, department_id, week_id,"
        " week_start, created_by, updated_by)"
        " VALUES ($1,$2,$3,'pending',$4,$5,$6,$2,$2)",
        org_id, row["user_id"], marker, row["department_id"], row["week_id"],
        row["week_start"])
    mid = await client.get("/tasks", headers=headers)
    assert any(t["title"] == marker for t in mid.json())

    # Second start re-seeds: marker gone, seeded dataset back.
    _, headers2 = await _start(client)
    after = await client.get("/tasks", headers=headers2)
    titles = [t["title"] for t in after.json()]
    assert marker not in titles
    assert len(titles) == seeded_count


async def test_wipe_introduces_no_audit_break(client, demo_on):
    # The wipe never deletes audit_log (the global hash chain), so a
    # wipe+seed cycle must not increase the break count. Measure the count
    # around a second start rather than asserting a globally-clean chain —
    # other tests in the same session deliberately tamper with the chain, so
    # an absolute "0 breaks" assertion would be order-dependent.
    _, headers = await _start(client)  # demo admin can walk the chain
    before = (await client.get("/audit/verify", headers=headers)).json()
    _, headers2 = await _start(client)  # another full wipe+seed
    after = (await client.get("/audit/verify", headers=headers2)).json()
    assert after["tasks"]["breaks"] == before["tasks"]["breaks"]
    assert after["users"]["breaks"] == before["users"]["breaks"]


async def test_exit_invalidates_session(client, demo_on):
    _, headers = await _start(client)
    ex = await client.post("/demo/exit", headers=headers)
    assert ex.status_code == 200
    # Profiles were deleted by the wipe — the token's subject no longer exists.
    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 401


async def test_exit_rejects_non_demo_token(client, demo_on, admin_headers):
    # A real tenant's admin token is not a demo session.
    r = await client.post("/demo/exit", headers=admin_headers)
    assert r.status_code == 403


async def test_reset_leaves_other_org_untouched(client, demo_on, org, admin_headers):
    # Seed a marker task in the real org via its admin pool.
    other_id = uuid.UUID(org["org_id"])
    dept = await tasks_admin_pool().fetchval(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'d','D') RETURNING id",
        other_id)
    marker = f"OTHER-{uuid.uuid4().hex[:8]}"
    await tasks_admin_pool().execute(
        "INSERT INTO tasks(org_id, user_id, title, status, department_id,"
        " week_start, created_by, updated_by)"
        " VALUES ($1,$2,$3,'pending',$4, current_date, $2,$2)",
        other_id, uuid.UUID(org["admin_id"]), marker, dept)

    await _start(client)  # runs a full demo wipe+seed

    # The other org's row survived.
    still = await tasks_admin_pool().fetchval(
        "SELECT count(*) FROM tasks WHERE org_id=$1 AND title=$2", other_id, marker)
    assert still == 1


async def test_start_throttled_after_limit(client, demo_on):
    from app.api import demo as demo_router
    for _ in range(demo_router._MAX_STARTS_PER_IP):
        r = await client.post("/demo/start", json={"cast": "cartoon"})
        assert r.status_code == 200, r.text
    r = await client.post("/demo/start", json={"cast": "cartoon"})
    assert r.status_code == 429
