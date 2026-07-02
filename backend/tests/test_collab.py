"""P1 — task assignment, and direct regression tests for three bugs fixed
this session:
  1. assign() used to accept a user_id from any org (no cross-org check).
  2. a malformed (non-UUID) user_id crashed with an unhandled 500.
  3. tasks_write RLS had no assignee clause, so a legitimately assigned
     user could never persist a status/field change on their own task —
     silently rejected forever, no matter who assigned them.
"""
import uuid

from tests.conftest import create_user, login_and_set_password


async def test_assign_same_org_user_succeeds(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Assign me", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers)
    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text

    r = await client.get("/tasks?parents_only=true", headers=admin_headers)
    listed = next(t for t in r.json() if t["id"] == task_id)
    assert user["id"] in listed["assignee_ids"]


async def test_assign_cross_org_user_rejected(client, admin_headers, org):
    """org A's admin tries to assign a real profile that belongs to org B."""
    r = await client.post("/tasks", json={"title": "Cross-org assign attempt", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]

    # A second, independent org with its own admin.
    other_org_id = uuid.uuid4()
    other_admin_id = uuid.uuid4()
    from app.db import admin_pool
    from app.security import hash_password
    pool = admin_pool()
    await pool.execute("INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
                        other_org_id, "Other Org", f"other-{other_org_id.hex[:8]}")
    await pool.execute(
        "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,'ADMIN',false)",
        other_admin_id, other_org_id, f"other_admin_{other_org_id.hex[:6]}",
        hash_password("whatever"), "Other Admin")
    try:
        r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": str(other_admin_id)},
                               headers=admin_headers)
        assert r.status_code == 404, r.text
        assert "organization" in r.json()["detail"].lower()
    finally:
        await pool.execute("DELETE FROM organizations WHERE id=$1", other_org_id)


async def test_assign_malformed_uuid_returns_422_not_500(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Malformed assignee", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": "not-a-uuid"}, headers=admin_headers)
    assert r.status_code == 422


async def test_assignee_can_write_task_they_are_assigned_to(client, admin_headers):
    """The core RLS regression test: a plain USER who is assigned to a task
    (but doesn't own it and has no elevated role) must be able to persist a
    status change on it — this is what tasks_write's new assignee clause
    fixes, and what GF.ownsTask on the frontend already assumed."""
    r = await client.post("/tasks", json={"title": "Assignee write test", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]

    user, otp = await create_user(client, admin_headers, role="USER")
    op_token = await login_and_set_password(client, user["username"], otp)
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # Before assignment: invisible and unwritable.
    r = await client.get("/tasks?parents_only=true", headers=op_headers)
    assert not any(t["id"] == task_id for t in r.json())
    r = await client.patch(f"/tasks/{task_id}", json={"status": "ongoing"}, headers=op_headers)
    assert r.status_code == 404

    # Admin assigns them.
    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)
    assert r.status_code == 201

    # After assignment: visible and writable, without being the owner or elevated.
    r = await client.get("/tasks?parents_only=true", headers=op_headers)
    assert any(t["id"] == task_id for t in r.json())
    r = await client.patch(f"/tasks/{task_id}", json={"status": "ongoing"}, headers=op_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ongoing"


async def test_non_owner_non_assignee_cannot_assign_others(client, admin_headers):
    """A plain USER who isn't the task's owner or elevated can't manage
    assignment on it, even if they can see it as an assignee themselves."""
    r = await client.post("/tasks", json={"title": "Assign permission check", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]

    assignee, otp1 = await create_user(client, admin_headers, role="USER")
    bystander, otp2 = await create_user(client, admin_headers, role="USER")
    assignee_token = await login_and_set_password(client, assignee["username"], otp1)

    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": assignee["id"]}, headers=admin_headers)

    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": bystander["id"]},
                           headers={"Authorization": f"Bearer {assignee_token}"})
    assert r.status_code == 403


async def test_comment_and_ack_flow(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Comment/ack test", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)

    r = await client.post(f"/tasks/{task_id}/comments", json={"content": "On it"}, headers=headers)
    assert r.status_code == 201, r.text

    r = await client.post(f"/tasks/{task_id}/ack", json={"accepted": True}, headers=headers)
    assert r.status_code == 200, r.text

    r = await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)
    assignee_row = next(a for a in r.json() if a["user_id"] == user["id"])
    assert assignee_row["accepted"] is True


async def test_ack_decline_records_reason_as_a_comment(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Decline test", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)

    r = await client.post(f"/tasks/{task_id}/ack", json={"accepted": False, "reason": "Overloaded this week"},
                           headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is False

    r = await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)
    assignee_row = next(a for a in r.json() if a["user_id"] == user["id"])
    assert assignee_row["accepted"] is False

    r = await client.get(f"/tasks/{task_id}/comments", headers=admin_headers)
    comments = [c["content"] for c in r.json()]
    assert any("Declined" in c and "Overloaded this week" in c for c in comments)


async def test_ack_by_someone_not_assigned_returns_404(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Not your task", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    bystander, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, bystander["username"], otp)
    r = await client.post(f"/tasks/{task_id}/ack", json={"accepted": True},
                           headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


async def test_owner_can_unassign(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Unassign test", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers, role="USER")
    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)

    r = await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)
    assert any(a["user_id"] == user["id"] for a in r.json())

    r = await client.delete(f"/tasks/{task_id}/assignees/{user['id']}", headers=admin_headers)
    assert r.status_code == 200, r.text

    r = await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)
    assert not any(a["user_id"] == user["id"] for a in r.json())


async def test_non_owner_non_assignee_cannot_unassign_others(client, admin_headers):
    """Mirrors test_non_owner_non_assignee_cannot_assign_others for the
    DELETE side — _can_manage_task gates both the same way. Uses a second
    assignee (not a bystander) as the actor: a true bystander can't see the
    task at all via tasks_read RLS and would 404 before ever reaching the
    _can_manage_task check, which would prove the wrong thing."""
    r = await client.post("/tasks", json={"title": "Unassign permission check", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]

    assignee1, otp1 = await create_user(client, admin_headers, role="USER")
    assignee2, otp2 = await create_user(client, admin_headers, role="USER")
    assignee1_token = await login_and_set_password(client, assignee1["username"], otp1)

    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": assignee1["id"]}, headers=admin_headers)
    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": assignee2["id"]}, headers=admin_headers)

    r = await client.delete(f"/tasks/{task_id}/assignees/{assignee2['id']}",
                             headers={"Authorization": f"Bearer {assignee1_token}"})
    assert r.status_code == 403
