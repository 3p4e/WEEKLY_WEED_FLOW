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


async def test_progress_notes_is_a_real_list_not_a_json_string(client, admin_headers):
    """Regression: tasks.progress_notes is jsonb (DEFAULT '[]'::jsonb NOT
    NULL); without a jsonb codec on the asyncpg pools it comes back as the
    raw string "[]" instead of an empty list. The frontend's
    GF.WWF.transform does `(t.progress_notes || []).map(...)` — a non-empty
    string is truthy, so the `|| []` fallback never kicks in, and `.map` on
    a string throws for every task, every load. Caught by a real browser
    (e2e) hitting this exact path via GF.submitAdd; pinned here at the API
    layer so it can't regress silently again."""
    r = await client.post("/tasks", json={"title": "Progress notes shape check", "status": "pending"},
                           headers=admin_headers)
    assert r.status_code == 201, r.text
    assert isinstance(r.json()["progress_notes"], list)
    assert r.json()["progress_notes"] == []

    task_id = r.json()["id"]
    r = await client.get("/tasks?parents_only=true", headers=admin_headers)
    listed = next(t for t in r.json() if t["id"] == task_id)
    assert isinstance(listed["progress_notes"], list)

    await client.post(f"/tasks/{task_id}/progress", json={"day_label": "Mon", "note": "watered"},
                       headers=admin_headers)
    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert isinstance(r.json()["task"]["progress_notes"], list)
