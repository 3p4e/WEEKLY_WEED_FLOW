"""P1 — org isolation. The RLS model is the app's actual security boundary
(every table is FORCE ROW LEVEL SECURITY); this pins that a user in one org
can never see or touch another org's data through the API, regardless of
role."""
import uuid

from app.db import admin_pool
from app.security import hash_password


async def _make_org_admin(username_prefix="admin"):
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    suffix = uuid.uuid4().hex[:8]
    pool = admin_pool()
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
        await admin_pool().execute("DELETE FROM organizations WHERE id=$1", org_a["org_id"])
        await admin_pool().execute("DELETE FROM organizations WHERE id=$1", org_b["org_id"])


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
        await admin_pool().execute("DELETE FROM organizations WHERE id=$1", org_a["org_id"])
        await admin_pool().execute("DELETE FROM organizations WHERE id=$1", org_b["org_id"])
