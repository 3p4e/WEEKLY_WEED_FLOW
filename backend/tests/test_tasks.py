"""P1 — task lifecycle, and a direct regression test for the status-enum
bug: the frontend's S_OUT map used to collapse 'review'/'postponed' into
other values on save (fixed this session). The bug was entirely
client-side, but this pins the backend's side of that contract: every
status the frontend can send must round-trip through PATCH unchanged."""
import pytest

ALL_STATUSES = ["pending", "ongoing", "review", "stuck", "postponed", "completed"]


async def test_create_and_list_task(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Water the clones", "status": "pending"},
                           headers=admin_headers)
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["title"] == "Water the clones"
    assert "user_id" in task

    r = await client.get("/tasks?parents_only=true", headers=admin_headers)
    assert r.status_code == 200
    listed = next(t for t in r.json() if t["id"] == task["id"])
    # Regression: list_tasks used to omit user_id entirely (every task's
    # frontend "owner" was hardcoded to the viewer regardless of who
    # actually created it) and never returned real assignee ids.
    assert listed["user_id"] == task["user_id"]
    assert listed["assignee_ids"] == []


@pytest.mark.parametrize("status", ALL_STATUSES)
async def test_status_round_trips_unchanged(client, admin_headers, status):
    r = await client.post("/tasks", json={"title": "Status round-trip", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.patch(f"/tasks/{task_id}", json={"status": status}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == status
    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert r.json()["task"]["status"] == status


async def test_patch_nonexistent_task_returns_404_with_detail(client, admin_headers):
    r = await client.patch("/tasks/00000000-0000-0000-0000-000000000000",
                            json={"status": "ongoing"}, headers=admin_headers)
    assert r.status_code == 404
    assert "detail" in r.json()


async def test_patch_noop_when_no_fields(client, admin_headers):
    r = await client.post("/tasks", json={"title": "No-op patch", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.patch(f"/tasks/{task_id}", json={}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json().get("noop") is True


async def test_departments_and_weeks_endpoints(client, admin_headers):
    r = await client.get("/departments", headers=admin_headers)
    assert r.status_code == 200
    r = await client.get("/weeks", headers=admin_headers)
    assert r.status_code == 200
