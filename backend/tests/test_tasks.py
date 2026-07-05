"""P1 — task lifecycle, and a direct regression test for the status-enum
bug: the frontend's S_OUT map used to collapse 'review'/'postponed' into
other values on save (fixed this session). The bug was entirely
client-side, but this pins the backend's side of that contract: every
status the frontend can send must round-trip through PATCH unchanged."""
import pytest

from app.db import tasks_admin_pool

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


async def test_patch_week_id_moves_task_to_a_different_week(client, admin_headers, org):
    """Regression test for GF.rollover: it used to mutate local state and
    call a no-op GF.store.save(), so 'rolled over' tasks silently reverted
    to their original week on reload. week_id/week_start must be real,
    persisted PATCH fields, same as status/priority/etc."""
    await tasks_admin_pool().execute(
        "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on) VALUES"
        " ($1,2026,1,'2026-01-05','2026-01-11'), ($1,2026,2,'2026-01-12','2026-01-18')", org["org_id"])
    r = await client.get("/weeks", headers=admin_headers)
    weeks = sorted(r.json(), key=lambda w: w["iso_week"])
    this_week, next_week = weeks[0], weeks[1]

    r = await client.post("/tasks", json={
        "title": "Roll me over", "status": "pending", "week_id": this_week["id"], "week_start": "2026-01-05",
    }, headers=admin_headers)
    task_id = r.json()["id"]

    r = await client.patch(f"/tasks/{task_id}",
                            json={"week_id": next_week["id"], "week_start": "2026-01-12"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["week_id"] == next_week["id"]
    assert r.json()["week_start"] == "2026-01-12"

    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert r.json()["task"]["week_id"] == next_week["id"]


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


async def test_get_nonexistent_task_returns_a_real_404(client, admin_headers):
    """Regression test: GET used to return HTTP 200 with {"error": "not_found"}
    instead of a real 404, inconsistent with PATCH on the same resource."""
    r = await client.get("/tasks/00000000-0000-0000-0000-000000000000", headers=admin_headers)
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


async def test_progress_notes_reflects_real_task_progress_rows(client, admin_headers):
    """Regression: tasks.progress_notes used to be its own jsonb column, set
    once at INSERT (DEFAULT '[]') and never updated by any write path — the
    only place progress is ever written is POST /tasks/{id}/progress, which
    inserts into the separate task_progress table and never touched
    tasks.progress_notes. Net effect: every task card in the live UI showed
    zero progress notes, always, no matter how many a user added. list_tasks
    now aggregates progress_notes live from task_progress instead of trusting
    a column that could never reflect it; this pins actual content, not just
    shape, so a regression back to a static/stale column fails loudly."""
    r = await client.post("/tasks", json={"title": "Progress notes shape check", "status": "pending"},
                           headers=admin_headers)
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]

    r = await client.get("/tasks?parents_only=true", headers=admin_headers)
    listed = next(t for t in r.json() if t["id"] == task_id)
    assert listed["progress_notes"] == []

    await client.post(f"/tasks/{task_id}/progress", json={"day_label": "Mon", "note": "watered"},
                       headers=admin_headers)
    r = await client.get("/tasks?parents_only=true", headers=admin_headers)
    listed = next(t for t in r.json() if t["id"] == task_id)
    assert len(listed["progress_notes"]) == 1
    assert listed["progress_notes"][0]["note"] == "watered"
    assert listed["progress_notes"][0]["day_label"] == "Mon"

    # progress_notes/deps were dropped as dead columns — get_task's `SELECT *`
    # must not resurrect them; task_progress rows still come back via `progress`.
    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert r.json()["progress"][0]["note"] == "watered"
    assert "progress_notes" not in r.json()["task"]
    assert "deps" not in r.json()["task"]


async def test_add_progress_rejects_task_caller_cannot_see(client, admin_headers):
    """Regression: add_progress used to insert straight into task_progress
    with no prior visibility check (unlike add_session/add_comment, which
    both look the task up under RLS first), so a non-elevated caller could
    POST notes onto a task they don't own, aren't assigned to, and can't
    even see — task_progress RLS is org-scoped only, not owner/assignee
    scoped, so the insert would silently succeed with no error at all."""
    from tests.conftest import create_user, login_and_set_password
    user, otp = await create_user(client, admin_headers)
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/tasks", json={"title": "Admin-only task", "status": "pending"},
                          headers=admin_headers)
    task_id = r.json()["id"]

    r = await client.post(f"/tasks/{task_id}/progress", json={"day_label": "Mon", "note": "sneaking in"},
                          headers=headers)
    assert r.status_code == 404, r.text

    r = await client.post("/tasks/00000000-0000-0000-0000-000000000000/progress",
                          json={"day_label": "Mon", "note": "x"}, headers=admin_headers)
    assert r.status_code == 404


async def test_estimated_hours_set_at_create_and_listed(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Trim batch", "status": "pending", "estimated_hours": 4},
                           headers=admin_headers)
    assert r.status_code == 201, r.text
    assert float(r.json()["estimated_hours"]) == 4.0
    task_id = r.json()["id"]

    # Surfaced in the list (the frontend transform reads it from here).
    r = await client.get("/tasks?parents_only=true", headers=admin_headers)
    listed = next(t for t in r.json() if t["id"] == task_id)
    assert float(listed["estimated_hours"]) == 4.0
    assert listed["actual_hours"] is None


async def test_actual_hours_patch_round_trips(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Log my hours", "status": "ongoing"}, headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.patch(f"/tasks/{task_id}", json={"actual_hours": 5.5}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert float(r.json()["actual_hours"]) == 5.5
    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert float(r.json()["task"]["actual_hours"]) == 5.5


async def test_patch_null_clears_actual_hours(client, admin_headers):
    """Regression: update_task used model_dump(exclude_none=True), which
    can't distinguish "field omitted" from "field explicitly null" — so
    blanking the hours input sent {actual_hours: null}, the backend silently
    dropped it, returned 200, and the stale value reappeared on reload."""
    r = await client.post("/tasks", json={"title": "Clear my hours", "status": "ongoing"},
                           headers=admin_headers)
    task_id = r.json()["id"]
    await client.patch(f"/tasks/{task_id}", json={"actual_hours": 5.5}, headers=admin_headers)

    r = await client.patch(f"/tasks/{task_id}", json={"actual_hours": None}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["actual_hours"] is None

    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert r.json()["task"]["actual_hours"] is None


async def test_patch_null_on_not_null_column_is_ignored_not_500(client, admin_headers):
    """An explicit null on a NOT NULL column (status) must be treated as
    not-provided — never forwarded to SQL as NULL."""
    r = await client.post("/tasks", json={"title": "Null status probe", "status": "ongoing"},
                           headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.patch(f"/tasks/{task_id}", json={"status": None}, headers=admin_headers)
    assert r.status_code == 200, r.text
    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert r.json()["task"]["status"] == "ongoing"


async def test_zero_estimate_is_a_value_not_missing(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Trivial task", "estimated_hours": 0},
                           headers=admin_headers)
    assert r.status_code == 201, r.text
    assert float(r.json()["estimated_hours"]) == 0.0


async def test_invalid_status_rejected_with_422(client, admin_headers):
    """Regression: tasks.status gained a DB CHECK constraint (migration 0004)
    restricting it to the six canonical values. Without matching Pydantic
    validation, a bad value would hit that constraint as an unhandled 500
    instead of a clean 422 — this pins the API-layer counterpart, same
    precedent as the existing hours ge=0 / DB CHECK pairing."""
    r = await client.post("/tasks", json={"title": "Bad status", "status": "bogus"}, headers=admin_headers)
    assert r.status_code == 422
    r = await client.post("/tasks", json={"title": "Real task", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.patch(f"/tasks/{task_id}", json={"status": "bogus"}, headers=admin_headers)
    assert r.status_code == 422


async def test_bad_priority_rejected_with_422(client, admin_headers):
    """priority gained API-layer validation (the wire set low/normal/medium/
    high/critical). Garbage would otherwise store silently and sort last in
    every priority-ordered view with no indication anything was wrong."""
    r = await client.post("/tasks", json={"title": "x", "priority": "URGENT!!"}, headers=admin_headers)
    assert r.status_code == 422
    # The value the GrowFlow UI actually sends for medium must stay accepted.
    r = await client.post("/tasks", json={"title": "ok", "priority": "normal"}, headers=admin_headers)
    assert r.status_code == 201, r.text


async def test_unknown_fk_fields_return_422_not_500(client, admin_headers):
    """A well-formed but non-existent week_id/department_id/parent_id must be a
    clean 422, not a raw 500 from an uncaught ForeignKeyViolation."""
    ghost = "00000000-0000-0000-0000-000000000000"
    for field in ("week_id", "department_id", "parent_id"):
        r = await client.post("/tasks", json={"title": "fk probe", field: ghost}, headers=admin_headers)
        assert r.status_code == 422, f"{field}: {r.status_code} {r.text}"
    # PATCH path too.
    r = await client.post("/tasks", json={"title": "real"}, headers=admin_headers)
    tid = r.json()["id"]
    r = await client.patch(f"/tasks/{tid}", json={"week_id": ghost}, headers=admin_headers)
    assert r.status_code == 422, r.text


async def test_recurrence_until_bad_date_rejected_at_create(client, admin_headers):
    """A malformed recurrence.until is validated up front (422) — otherwise it
    only blows up later, inside the completion transaction, permanently 500-ing
    (and rolling back) every attempt to complete that task."""
    r = await client.post("/tasks", json={
        "title": "bad recurrence", "recurrence": {"freq": "weekly", "interval": 1, "until": "not-a-date"}},
        headers=admin_headers)
    assert r.status_code == 422, r.text


async def test_recurring_next_instance_carries_week_id(client, admin_headers, org):
    """When a weekly-recurring task completes, its spawned next instance must
    resolve the next calendar week's id (not just week_start), or it vanishes
    from ?week_id= week views."""
    await tasks_admin_pool().execute(
        "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on) VALUES"
        " ($1,2026,10,'2026-03-02','2026-03-08'), ($1,2026,11,'2026-03-09','2026-03-15')", org["org_id"])
    weeks = {w["iso_week"]: w for w in (await client.get("/weeks", headers=admin_headers)).json()}
    wk_a, wk_b = weeks[10], weeks[11]

    r = await client.post("/tasks", json={
        "title": "Weekly line check", "status": "ongoing",
        "recurrence": {"freq": "weekly", "interval": 1},
        "week_id": wk_a["id"], "week_start": "2026-03-02", "due_date": "2026-03-06"},
        headers=admin_headers)
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]

    r = await client.patch(f"/tasks/{task_id}", json={"status": "completed"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    nxt = r.json().get("next_instance")
    assert nxt is not None, "completing a recurring task should spawn the next instance"
    assert nxt["week_id"] == wk_b["id"]
    assert str(nxt["week_start"]) == "2026-03-09"

    # And it actually shows up when listing next week.
    r = await client.get(f"/tasks?week_id={wk_b['id']}", headers=admin_headers)
    assert any(t["id"] == nxt["id"] for t in r.json())


async def test_delete_link_requires_task_visibility(client, admin_headers):
    """Regression (IDOR): task_links' only RLS policy is org_isolation, so
    delete_link must look the task up under RLS first — otherwise any org
    member who knows a link id could delete links on a task they can't see."""
    from tests.conftest import create_user, login_and_set_password
    # Admin creates a task and a link on it.
    r = await client.post("/tasks", json={"title": "Admin task with link"}, headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.post(f"/tasks/{task_id}/links", json={"url": "https://example.com/sop"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    link_id = r.json()["id"]

    # A plain USER who is not owner/assignee/elevated can't see the task...
    user, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.delete(f"/tasks/{task_id}/links/{link_id}", headers=headers)
    assert r.status_code == 404, r.text

    # ...and the link is still there for the admin.
    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert any(l["id"] == link_id for l in r.json()["links"])


async def test_negative_hours_rejected_with_422(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Bad estimate", "estimated_hours": -1}, headers=admin_headers)
    assert r.status_code == 422
    r = await client.post("/tasks", json={"title": "Real task", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.patch(f"/tasks/{task_id}", json={"actual_hours": -2}, headers=admin_headers)
    assert r.status_code == 422
