"""P1 — org isolation. The RLS model is the app's actual security boundary
(every table is FORCE ROW LEVEL SECURITY); this pins that a user in one org
can never see or touch another org's data through the API, regardless of
role.

Covers every table with a real API read path: tasks, profiles (via
directory), departments, calendar_weeks, handoffs (collab.py) and
ai_agent_bindings (ai.py).

The previous version of this docstring claimed handoffs / ai_pins /
ai_agent_bindings / password_reset_codes had "no API routes at all" and were
out of scope. That went stale: handoffs gained POST/GET /tasks/{id}/handoffs
and POST /handoffs/{id}/resolve, ai_agent_bindings gained GET/PUT/DELETE
/ai/bindings, and ai_pins gained GET /ai/pins — all reachable over HTTP, all
relying on RLS with nothing pinning it. password_reset_codes was dead schema
and has been dropped (users migration 0008)."""
import uuid

from app.db import tasks_admin_pool, users_admin_pool
from app.security import hash_password
from tests.conftest import purge_org


async def _make_org_admin(username_prefix="admin"):
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    suffix = uuid.uuid4().hex[:8]
    pool = users_admin_pool()
    await pool.execute("INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
                        org_id, f"Org {suffix}", f"org-{suffix}")
    await pool.execute(
        "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,'ADMIN',false)",
        admin_id, org_id, f"{username_prefix}_{suffix}", hash_password("TestPassword123456"), "Admin")
    return {"org_id": org_id, "admin_id": admin_id, "username": f"{username_prefix}_{suffix}"}


async def test_task_not_visible_or_writable_across_orgs(client):
    org_a = await _make_org_admin("a")
    org_b = await _make_org_admin("b")
    try:
        r = await client.post("/auth/login", json={"email": org_a["username"], "password": "TestPassword123456"})
        token_a = r.json()["access_token"]
        r = await client.post("/auth/login", json={"email": org_b["username"], "password": "TestPassword123456"})
        token_b = r.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        r = await client.post("/tasks", json={"title": "Org A secret task", "status": "pending"},
                               headers=headers_a)
        task_id = r.json()["id"]

        # Org B can't see it in a list...
        r = await client.get("/tasks?parents_only=true", headers=headers_b)
        assert not any(t["id"] == task_id for t in r.json())

        # ...can't fetch it directly...
        r = await client.get(f"/tasks/{task_id}", headers=headers_b)
        assert r.status_code == 404

        # ...and can't write to it, even as an ADMIN of their own org.
        r = await client.patch(f"/tasks/{task_id}", json={"status": "ongoing"}, headers=headers_b)
        assert r.status_code == 404
    finally:
        await purge_org(org_a["org_id"])
        await purge_org(org_b["org_id"])


async def test_directory_scoped_to_own_org(client):
    org_a = await _make_org_admin("dira")
    org_b = await _make_org_admin("dirb")
    try:
        r = await client.post("/auth/login", json={"email": org_a["username"], "password": "TestPassword123456"})
        token_a = r.json()["access_token"]
        r = await client.get("/auth/directory", headers={"Authorization": f"Bearer {token_a}"})
        usernames = [u["username"] for u in r.json()]
        assert org_a["username"] in usernames
        assert org_b["username"] not in usernames
    finally:
        await purge_org(org_a["org_id"])
        await purge_org(org_b["org_id"])


async def test_departments_scoped_to_own_org(client):
    """departments has a real API read path (GET /departments) but no
    existing test proves org isolation on it specifically."""
    org_a = await _make_org_admin("depta")
    org_b = await _make_org_admin("deptb")
    try:
        await tasks_admin_pool().execute(
            "INSERT INTO departments(org_id, code, name) VALUES ($1,'secret','Org A Secret Dept')",
            org_a["org_id"])
        r = await client.post("/auth/login", json={"email": org_b["username"], "password": "TestPassword123456"})
        token_b = r.json()["access_token"]
        r = await client.get("/departments", headers={"Authorization": f"Bearer {token_b}"})
        assert r.status_code == 200
        names = [d["name"] for d in r.json()]
        assert "Org A Secret Dept" not in names
    finally:
        await purge_org(org_a["org_id"])
        await purge_org(org_b["org_id"])


async def test_calendar_weeks_scoped_to_own_org(client):
    """calendar_weeks has a real API read path (GET /weeks) but no existing
    test proves org isolation on it specifically."""
    org_a = await _make_org_admin("weeka")
    org_b = await _make_org_admin("weekb")
    try:
        await tasks_admin_pool().execute(
            "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on)"
            " VALUES ($1,2026,1,'2026-01-05','2026-01-11')",
            org_a["org_id"])
        r = await client.post("/auth/login", json={"email": org_b["username"], "password": "TestPassword123456"})
        token_b = r.json()["access_token"]
        r = await client.get("/weeks", headers={"Authorization": f"Bearer {token_b}"})
        assert r.status_code == 200
        assert r.json() == []
    finally:
        await purge_org(org_a["org_id"])
        await purge_org(org_b["org_id"])


async def test_handoffs_not_visible_across_orgs(client):
    """handoffs has live routes (collab.py) and org-scoped RLS, but nothing
    pinned the isolation — the docstring above used to assert it had no routes
    at all. Org B must not read, nor resolve, org A's handoff.

    The department + handoff rows are seeded through the admin pool rather than
    POST /departments: that route provisions AI agents and needs outbound
    network, which is unrelated to the RLS property under test here."""
    org_a = await _make_org_admin("hoa")
    org_b = await _make_org_admin("hob")
    try:
        r = await client.post("/auth/login", json={"email": org_a["username"], "password": "TestPassword123456"})
        headers_a = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.post("/auth/login", json={"email": org_b["username"], "password": "TestPassword123456"})
        headers_b = {"Authorization": f"Bearer {r.json()['access_token']}"}

        pool = tasks_admin_pool()
        dept_id = uuid.uuid4()
        await pool.execute(
            "INSERT INTO departments(id, org_id, code, name) VALUES ($1,$2,'qc','QC')",
            dept_id, org_a["org_id"])
        task = (await client.post("/tasks", json={"title": "Org A handoff task", "status": "pending"},
                                  headers=headers_a)).json()
        handoff_id = await pool.fetchval(
            "INSERT INTO handoffs(org_id, task_id, to_dept_id, requested_by, note)"
            " VALUES ($1,$2,$3,$4,'please take this') RETURNING id",
            org_a["org_id"], uuid.UUID(task["id"]), dept_id, org_a["admin_id"])

        # Org A sees its own handoff …
        r = await client.get(f"/tasks/{task['id']}/handoffs", headers=headers_a)
        assert r.status_code == 200 and len(r.json()) == 1, r.text
        # … org B cannot list it (the parent task is itself invisible) …
        assert (await client.get(f"/tasks/{task['id']}/handoffs", headers=headers_b)).status_code == 404
        # … and cannot resolve it, even as an ADMIN of their own org.
        r = await client.post(f"/handoffs/{handoff_id}/resolve",
                              json={"decision": "accepted"}, headers=headers_b)
        assert r.status_code in (403, 404, 422), r.text
    finally:
        await purge_org(org_a["org_id"])
        await purge_org(org_b["org_id"])


async def test_ai_bindings_not_visible_across_orgs(client):
    """ai_agent_bindings has live routes (ai.py GET/PUT/DELETE /ai/bindings)
    and org-scoped RLS. A binding written by org A must never appear in, or be
    deleted by, org B."""
    org_a = await _make_org_admin("aia")
    org_b = await _make_org_admin("aib")
    try:
        r = await client.post("/auth/login", json={"email": org_a["username"], "password": "TestPassword123456"})
        headers_a = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await client.post("/auth/login", json={"email": org_b["username"], "password": "TestPassword123456"})
        headers_b = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.put("/ai/bindings/weekly_summary",
                             json={"letta_agent_id": "agent-org-a"}, headers=headers_a)
        assert r.status_code == 200, r.text

        def _bound(rows):
            rows = rows if isinstance(rows, list) else rows.get("bindings", [])
            return any(x.get("letta_agent_id") == "agent-org-a" for x in rows)

        # Org B's list must not contain org A's binding …
        assert not _bound((await client.get("/ai/bindings", headers=headers_b)).json())
        # … and deleting "the same" function key must not touch org A's row.
        await client.delete("/ai/bindings/weekly_summary", headers=headers_b)
        assert _bound((await client.get("/ai/bindings", headers=headers_a)).json())
    finally:
        await purge_org(org_a["org_id"])
        await purge_org(org_b["org_id"])
