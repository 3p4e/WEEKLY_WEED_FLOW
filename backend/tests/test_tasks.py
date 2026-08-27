"""P1 — task lifecycle, and a direct regression test for the status-enum
bug: the frontend's S_OUT map used to collapse 'review'/'postponed' into
other values on save (fixed this session). The bug was entirely
client-side, but this pins the backend's side of that contract: every
status the frontend can send must round-trip through PATCH unchanged."""
import asyncio

import pytest

from app.db import tasks_admin_pool
from app.worktime import facility_today

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


async def test_patch_null_clears_department(client, admin_headers, org):
    """department_id is a nullable FK (ON DELETE SET NULL); an explicit
    {"department_id": null} PATCH must clear the assignment, not be silently
    dropped as 'field omitted' (department_id was missing from
    _NULLABLE_PATCH_COLS)."""
    from app.db import tasks_admin_pool
    dept = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'qc','QC') RETURNING id",
        org["org_id"])
    r = await client.post("/tasks", json={"title": "Dept task", "status": "pending",
                                          "department_id": str(dept["id"])}, headers=admin_headers)
    task_id = r.json()["id"]
    assert r.json()["department_id"] == str(dept["id"])

    r = await client.patch(f"/tasks/{task_id}", json={"department_id": None}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["department_id"] is None
    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert r.json()["task"]["department_id"] is None


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


async def test_malformed_ids_rejected_with_422_not_500(client, admin_headers):
    """H11: a garbage (non-uuid) path/body id used to reach asyncpg raw —
    a cast failure the driver reports as a 500, not a clean validation error.
    Every task sub-resource route that takes an id must 422 instead."""
    garbage = "not-a-uuid"
    r = await client.post("/tasks", json={"title": "id-guard subject"}, headers=admin_headers)
    task_id = r.json()["id"]

    assert (await client.patch(f"/tasks/{garbage}", json={"title": "x"}, headers=admin_headers)).status_code == 422
    assert (await client.post(f"/tasks/{garbage}/progress",
                              json={"day_label": "Mon", "note": "n"}, headers=admin_headers)).status_code == 422
    assert (await client.post(f"/tasks/{garbage}/sessions",
                              json={"started_at": "2026-07-06T09:00:00", "hours": 1},
                              headers=admin_headers)).status_code == 422
    assert (await client.get(f"/tasks/{garbage}/sessions", headers=admin_headers)).status_code == 422
    assert (await client.delete(f"/sessions/{garbage}", headers=admin_headers)).status_code == 422
    assert (await client.post(f"/tasks/{garbage}/links",
                              json={"url": "https://example.com"}, headers=admin_headers)).status_code == 422
    assert (await client.delete(f"/tasks/{garbage}/links/{garbage}", headers=admin_headers)).status_code == 422
    assert (await client.delete(f"/tasks/{task_id}/links/{garbage}", headers=admin_headers)).status_code == 422
    assert (await client.post(f"/tasks/{garbage}/dependencies",
                              json={"depends_on_task_id": task_id}, headers=admin_headers)).status_code == 422
    assert (await client.post(f"/tasks/{task_id}/dependencies",
                              json={"depends_on_task_id": garbage}, headers=admin_headers)).status_code == 422
    assert (await client.delete(f"/tasks/{garbage}/dependencies/{garbage}",
                                headers=admin_headers)).status_code == 422


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


async def test_recurring_next_instance_creates_missing_calendar_week(client, admin_headers, org):
    """A weekly recurrence can advance past however far calendar_weeks has
    been seeded — the next instance must still land in a real week
    (ensure_week upserts the row), not get silently orphaned with
    week_id=NULL the way a plain SELECT-miss used to leave it."""
    await tasks_admin_pool().execute(
        "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on) VALUES"
        " ($1,2026,20,'2026-05-11','2026-05-17')", org["org_id"])
    weeks = {w["iso_week"]: w for w in (await client.get("/weeks", headers=admin_headers)).json()}
    wk_a = weeks[20]
    assert 21 not in weeks, "test setup: iso_week 21 must not exist yet"

    r = await client.post("/tasks", json={
        "title": "Weekly line check 2", "status": "ongoing",
        "recurrence": {"freq": "weekly", "interval": 1},
        "week_id": wk_a["id"], "week_start": "2026-05-11", "due_date": "2026-05-15"},
        headers=admin_headers)
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]

    r = await client.patch(f"/tasks/{task_id}", json={"status": "completed"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    nxt = r.json().get("next_instance")
    assert nxt is not None
    assert nxt["week_id"] is not None, \
        "next instance was orphaned (week_id NULL) instead of upserting the missing week"
    assert str(nxt["week_start"]) == "2026-05-18"

    weeks_after = {w["iso_week"]: w for w in (await client.get("/weeks", headers=admin_headers)).json()}
    assert 21 in weeks_after and weeks_after[21]["id"] == nxt["week_id"]


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


async def test_link_url_and_label_bounds_rejected_with_422(client, admin_headers):
    """DoS hygiene (L5, same convention as every other free-text field in this
    file — see TaskIn's docstring): LinkIn.url/label had no max_length at all,
    unlike every comparable field (external_ref=200, blocker_reason=2000). An
    oversized url or label must be a clean 422, not accepted unbounded."""
    r = await client.post("/tasks", json={"title": "Link bounds check"}, headers=admin_headers)
    task_id = r.json()["id"]

    over_url = "https://example.com/" + "a" * 2000  # > 2000 chars total
    r = await client.post(f"/tasks/{task_id}/links",
                          json={"url": over_url, "label": "fine"}, headers=admin_headers)
    assert r.status_code == 422, r.text

    over_label = "x" * 201  # > 200 chars
    r = await client.post(f"/tasks/{task_id}/links",
                          json={"url": "https://example.com/sop", "label": over_label},
                          headers=admin_headers)
    assert r.status_code == 422, r.text

    # sanity: bounds-respecting values still succeed
    r = await client.post(f"/tasks/{task_id}/links",
                          json={"url": "https://example.com/sop", "label": "SOP-001"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text


async def test_negative_hours_rejected_with_422(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Bad estimate", "estimated_hours": -1}, headers=admin_headers)
    assert r.status_code == 422
    r = await client.post("/tasks", json={"title": "Real task", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.patch(f"/tasks/{task_id}", json={"actual_hours": -2}, headers=admin_headers)
    assert r.status_code == 422


async def test_recurrence_interval_upper_bound_rejected_with_422(client, admin_headers):
    """L3: a huge interval sails past the positive-int check but overflows date
    arithmetic at rollover — a 500 that rolls back (and blocks) the completion.
    Reject it at write time; a sane interval still works."""
    r = await client.post("/tasks", json={"title": "R", "recurrence": {"freq": "weekly", "interval": 100000}},
                          headers=admin_headers)
    assert r.status_code == 422, r.text
    r = await client.post("/tasks", json={"title": "R2", "recurrence": {"freq": "weekly", "interval": 2}},
                          headers=admin_headers)
    assert r.status_code == 201, r.text


async def test_tags_bounds_rejected_with_422(client, admin_headers):
    """L5: bound the free-form tag list (count + per-tag length); a normal
    list is accepted."""
    r = await client.post("/tasks", json={"title": "T", "tags": [f"t{i}" for i in range(100)]},
                          headers=admin_headers)
    assert r.status_code == 422, r.text
    r = await client.post("/tasks", json={"title": "T2", "tags": ["x" * 500]}, headers=admin_headers)
    assert r.status_code == 422, r.text
    r = await client.post("/tasks", json={"title": "T3", "tags": ["ok", "fine"]}, headers=admin_headers)
    assert r.status_code == 201, r.text


# ── TMS T1: node_kind, dependency graph, task tree ──────────────────────────
async def test_node_kind_defaults_and_roundtrips(client, admin_headers):
    r = await client.post("/tasks", json={"title": "plain"}, headers=admin_headers)
    assert r.status_code == 201 and r.json()["node_kind"] == "task"
    r = await client.post("/tasks", json={"title": "annex node", "node_kind": "annex"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["node_kind"] == "annex"
    tid = r.json()["id"]
    r = await client.patch(f"/tasks/{tid}", json={"node_kind": "step"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["node_kind"] == "step"
    # invalid node_kind is rejected by the enum
    r = await client.post("/tasks", json={"title": "bad", "node_kind": "bogus"}, headers=admin_headers)
    assert r.status_code == 422


async def test_dependency_add_list_and_cycle_guard(client, admin_headers):
    a = (await client.post("/tasks", json={"title": "A"}, headers=admin_headers)).json()["id"]
    b = (await client.post("/tasks", json={"title": "B"}, headers=admin_headers)).json()["id"]
    # A is blocked by B
    r = await client.post(f"/tasks/{a}/dependencies", json={"depends_on_task_id": b},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    detail = (await client.get(f"/tasks/{a}", headers=admin_headers)).json()
    assert [d["id"] for d in detail["blocked_by"]] == [b]
    # reverse view: B blocks A
    rev = (await client.get(f"/tasks/{b}", headers=admin_headers)).json()
    assert [d["id"] for d in rev["blocks"]] == [a]
    # a cycle (B depends on A) must be rejected
    r = await client.post(f"/tasks/{b}/dependencies", json={"depends_on_task_id": a},
                          headers=admin_headers)
    assert r.status_code == 422, r.text
    # self-dependency rejected
    r = await client.post(f"/tasks/{a}/dependencies", json={"depends_on_task_id": a},
                          headers=admin_headers)
    assert r.status_code == 422
    # delete the edge
    r = await client.delete(f"/tasks/{a}/dependencies/{b}", headers=admin_headers)
    assert r.status_code == 200
    detail = (await client.get(f"/tasks/{a}", headers=admin_headers)).json()
    assert detail["blocked_by"] == []


async def test_dependency_transitive_cycle_still_rejected_under_lock(client, admin_headers):
    """Regression for the concurrency hardening: add_dependency now takes an
    org-scoped pg_advisory_xact_lock as the first statement in its transaction,
    so two concurrent reverse-edge writes (A->B and B->A) serialize and can no
    longer both pass the cycle check. A true race is impractical to drive
    through the shared ASGI test client, so this pins the invariant the lock
    protects: cycle detection is not weakened. A transitive cycle A->B->C then
    C->A is still refused, and the graph is left untouched."""
    a = (await client.post("/tasks", json={"title": "CycA"}, headers=admin_headers)).json()["id"]
    b = (await client.post("/tasks", json={"title": "CycB"}, headers=admin_headers)).json()["id"]
    c = (await client.post("/tasks", json={"title": "CycC"}, headers=admin_headers)).json()["id"]
    assert (await client.post(f"/tasks/{a}/dependencies", json={"depends_on_task_id": b},
                              headers=admin_headers)).status_code == 201
    assert (await client.post(f"/tasks/{b}/dependencies", json={"depends_on_task_id": c},
                              headers=admin_headers)).status_code == 201
    # C -> A would close the loop A->B->C->A — rejected, not inserted
    r = await client.post(f"/tasks/{c}/dependencies", json={"depends_on_task_id": a},
                          headers=admin_headers)
    assert r.status_code == 422, r.text
    assert (await client.get(f"/tasks/{c}", headers=admin_headers)).json()["blocked_by"] == []


async def test_task_tree_returns_hierarchy(client, admin_headers):
    parent = (await client.post("/tasks", json={"title": "SOP", "node_kind": "task"},
                                headers=admin_headers)).json()["id"]
    child = (await client.post("/tasks", json={"title": "annex", "node_kind": "annex",
                                               "parent_id": parent}, headers=admin_headers)).json()["id"]
    tree = (await client.get("/tasks/tree", headers=admin_headers)).json()
    ids = {n["id"]: n for n in tree}
    assert parent in ids and child in ids
    assert ids[child]["parent_id"] == parent
    assert ids[child]["node_kind"] == "annex"
    # 'tree' must not be captured as a task id (route ordering)
    assert all(n["id"] != "tree" for n in tree)


async def test_parent_department_week_cross_org_rejected_on_create_and_patch(client, admin_headers, org):
    """Companion to test_cultivation.py's
    test_task_batch_id_cross_org_rejected_on_create_and_patch: parent_id,
    department_id and week_id need the exact same RLS-scoped existence check
    batch_id already had. That check used to run ONLY inside
    `if scope and body.parent_id` in create_task (and not at all, for any
    caller, for department_id/week_id in either create_task or update_task) —
    so a bare FK check was all that stood between a caller and another org's
    real parent-task/department/calendar-week id. dept_scope() returns None
    for every org-wide role (ADMIN/OWNER/CEO/COO/QP, a department-less
    manager) *and* for plain USER (not in DEPT_SCOPED_ROLES), so ALL of those
    callers skipped validation entirely — this pins both an org-wide caller
    (ADMIN) and a dept-scoped manager (QC_MGR)."""
    import uuid
    from app.security import hash_password
    from app.db import users_admin_pool
    from tests.conftest import create_user, login_and_set_password, purge_org

    other_org_id = uuid.uuid4()
    other_admin_id = uuid.uuid4()
    other_password = "OtherOrgPassword123456"
    other_username = f"other_admin_{other_org_id.hex[:8]}"
    upool = users_admin_pool()
    await upool.execute("INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
                        other_org_id, "Other Org", f"other-{other_org_id.hex[:8]}")
    await upool.execute(
        "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,'ADMIN',false)",
        other_admin_id, other_org_id, other_username, hash_password(other_password), "Other Admin")
    try:
        r = await client.post("/auth/login", json={"email": other_username, "password": other_password})
        assert r.status_code == 200, r.text
        other_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # A real parent task, department and calendar week — all in the OTHER org.
        other_parent = await client.post("/tasks", json={"title": "Other org parent"}, headers=other_h)
        assert other_parent.status_code == 201, other_parent.text
        other_parent_id = other_parent.json()["id"]

        other_dept = await tasks_admin_pool().fetchrow(
            "INSERT INTO departments(org_id, code, name) VALUES ($1,'qc','QC') RETURNING id", other_org_id)
        other_dept_id = str(other_dept["id"])

        other_week = await tasks_admin_pool().fetchrow(
            "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on) VALUES"
            " ($1,2026,30,'2026-07-20','2026-07-26') RETURNING id", other_org_id)
        other_week_id = str(other_week["id"])

        # ── org-wide caller (ADMIN): scope is None, so the old `if scope and
        # ...` gate used to skip validation entirely for parent_id, and
        # department_id/week_id were never checked for anyone. ──────────────
        for field, val in (("parent_id", other_parent_id), ("department_id", other_dept_id),
                           ("week_id", other_week_id)):
            r = await client.post("/tasks", json={"title": f"cross-org {field}", field: val},
                                  headers=admin_headers)
            assert r.status_code == 422, f"{field}: {r.status_code} {r.text}"

        mine = await client.post("/tasks", json={"title": "patch target admin"}, headers=admin_headers)
        assert mine.status_code == 201, mine.text
        tid = mine.json()["id"]
        for field, val in (("department_id", other_dept_id), ("week_id", other_week_id)):
            r = await client.patch(f"/tasks/{tid}", json={field: val}, headers=admin_headers)
            assert r.status_code == 422, f"{field}: {r.status_code} {r.text}"

        # ── dept-scoped caller (QC_MGR): same cross-org ids must still be
        # refused — either by the department-scoping rule (403) or, once past
        # it, by the same org-scoped existence check (422). Either way, never
        # a 201/200 that plants a cross-tenant reference. ──────────────────
        my_dept = await tasks_admin_pool().fetchrow(
            "INSERT INTO departments(org_id, code, name) VALUES ($1,'pr','Production') RETURNING id",
            org["org_id"])
        prof, otp = await create_user(client, admin_headers, role="QC_MGR",
                                      department_id=str(my_dept["id"]))
        token = await login_and_set_password(client, prof["username"], otp)
        mgr_h = {"Authorization": f"Bearer {token}"}

        for field, val in (("parent_id", other_parent_id), ("department_id", other_dept_id),
                           ("week_id", other_week_id)):
            r = await client.post("/tasks", json={"title": f"cross-org mgr {field}", field: val},
                                  headers=mgr_h)
            assert r.status_code in (403, 422), f"{field}: {r.status_code} {r.text}"

        mine2 = await client.post("/tasks", json={"title": "patch target mgr"}, headers=mgr_h)
        assert mine2.status_code == 201, mine2.text
        tid2 = mine2.json()["id"]
        for field, val in (("department_id", other_dept_id), ("week_id", other_week_id)):
            r = await client.patch(f"/tasks/{tid2}", json={field: val}, headers=mgr_h)
            assert r.status_code in (403, 422), f"{field}: {r.status_code} {r.text}"

        # Sanity: a SAME-org parent/department/week still work fine for both —
        # the fix must not break legitimate same-org references.
        same_org_child = await client.post("/tasks", json={
            "title": "same-org parent ok", "parent_id": tid}, headers=admin_headers)
        assert same_org_child.status_code == 201, same_org_child.text
    finally:
        await purge_org(other_org_id)


async def test_external_ref_duplicate_is_409_not_500(client, admin_headers):
    """M5: a repeated external_ref (an at-least-once integration retry) must map to
    409, not an uncaught 500 — the unique index is what signals idempotency."""
    r = await client.post("/tasks", json={"title": "Imported once", "status": "pending",
                                           "external_ref": "ext-dup-001"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    # a second create with the same external_ref collides on tasks_org_external_ref_key
    r = await client.post("/tasks", json={"title": "Imported again", "status": "pending",
                                          "external_ref": "ext-dup-001"}, headers=admin_headers)
    assert r.status_code == 409, r.text
    # PATCHing another task onto an already-used external_ref is also a 409
    other = (await client.post("/tasks", json={"title": "Another", "status": "pending"},
                               headers=admin_headers)).json()
    r = await client.patch(f"/tasks/{other['id']}", json={"external_ref": "ext-dup-001"},
                           headers=admin_headers)
    assert r.status_code == 409, r.text


async def test_delete_dependency_scope_checks_both_sides_of_the_edge(client, admin_headers, org):
    """Regression: delete_dependency only scope-checked task_id, unlike
    add_dependency (which checks both sides via `for tid in (task_id, dep):`).
    That made dep_id's visibility an existence oracle — a dept-scoped manager
    could learn whether a specific out-of-scope task id exists (and has a real
    edge to one of their own tasks) purely from whether the delete succeeded
    vs 404'd, without ever being able to see that task any other way."""
    from tests.conftest import create_user, login_and_set_password

    dept_a = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'da','Dept A') RETURNING id", org["org_id"])
    dept_b = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'db','Dept B') RETURNING id", org["org_id"])

    r = await client.post("/tasks", json={"title": "In dept A", "department_id": str(dept_a["id"])},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    task_a = r.json()["id"]
    r = await client.post("/tasks", json={"title": "In dept B", "department_id": str(dept_b["id"])},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    task_b = r.json()["id"]

    # Admin (org-wide) can create the edge: A is blocked by B.
    r = await client.post(f"/tasks/{task_a}/dependencies", json={"depends_on_task_id": task_b},
                          headers=admin_headers)
    assert r.status_code == 201, r.text

    # A manager scoped to Dept A can see task_a but not task_b.
    mgr, otp = await create_user(client, admin_headers, role="QC_MGR", department_id=str(dept_a["id"]))
    token = await login_and_set_password(client, mgr["username"], otp)
    mgr_h = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"/tasks/{task_a}", headers=mgr_h)).status_code == 200
    assert (await client.get(f"/tasks/{task_b}", headers=mgr_h)).status_code == 404

    # The manager must not be able to delete an edge whose OTHER side (dep_id)
    # they can't see — even though the edge is real and task_id is in scope.
    r = await client.delete(f"/tasks/{task_a}/dependencies/{task_b}", headers=mgr_h)
    assert r.status_code == 404, r.text

    # The edge must still be intact — the manager's request must not have
    # silently deleted it before/without the scope check applying.
    detail = (await client.get(f"/tasks/{task_a}", headers=admin_headers)).json()
    assert [d["id"] for d in detail["blocked_by"]] == [task_b]

    # Sanity: admin (org-wide) can still delete it.
    r = await client.delete(f"/tasks/{task_a}/dependencies/{task_b}", headers=admin_headers)
    assert r.status_code == 200, r.text


async def test_patch_noop_on_nonexistent_task_returns_404(client, admin_headers):
    """Regression: an empty-body PATCH to a nonexistent task id used to return
    200 {"noop": True} for org-wide callers — _assert_scope_visible no-ops
    when dept_scope() is None, so it never confirmed the row actually
    existed, inconsistent with a non-empty PATCH to the same id (which
    already 404's via UPDATE ... RETURNING NULL) and letting a caller infer
    task-id existence from the response shape alone."""
    r = await client.patch("/tasks/00000000-0000-0000-0000-000000000000", json={}, headers=admin_headers)
    assert r.status_code == 404
    assert "detail" in r.json()


async def test_department_move_permission_enforced_after_lock_reorder(client, admin_headers, org):
    """Companion to the FOR UPDATE reordering fix in update_task: the
    department-move permission check now reads department_id/user_id off the
    row locked by the same FOR UPDATE select prev_status uses (instead of a
    separate, earlier, unlocked read) — pin that the permission logic itself
    still behaves correctly off that row."""
    dept_a = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'ma','Move A') RETURNING id", org["org_id"])
    dept_b = await tasks_admin_pool().fetchrow(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'mb','Move B') RETURNING id", org["org_id"])
    from tests.conftest import create_user, login_and_set_password

    mgr, otp = await create_user(client, admin_headers, role="QC_MGR", department_id=str(dept_a["id"]))
    token = await login_and_set_password(client, mgr["username"], otp)
    mgr_h = {"Authorization": f"Bearer {token}"}

    r = await client.post("/tasks", json={"title": "In dept A"}, headers=mgr_h)
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]
    assert r.json()["department_id"] == str(dept_a["id"])

    # A manager may not move their own task out to a department they don't own.
    r = await client.patch(f"/tasks/{task_id}", json={"department_id": str(dept_b["id"])}, headers=mgr_h)
    assert r.status_code == 403, r.text

    # An org-wide caller can — the check isn't over-broad.
    r = await client.patch(f"/tasks/{task_id}", json={"department_id": str(dept_b["id"])}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["department_id"] == str(dept_b["id"])


async def test_update_task_concurrent_completions_materialize_once(client, admin_headers):
    """H8-style companion for update_task's own FOR UPDATE guard (relocated
    earlier in the function by the lock-reorder fix, ahead of the
    department-move permission check, but still covering prev_status the same
    way): two concurrent PATCHes completing the same recurring task must
    serialize on the row lock, not both read a pre-completion status and each
    materialize a duplicate 'next' recurring instance."""
    r = await client.post("/tasks", json={
        "title": "Concurrent completion", "status": "ongoing",
        "recurrence": {"freq": "daily", "interval": 1}, "due_date": "2026-07-06"},
        headers=admin_headers)
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]

    r1, r2 = await asyncio.gather(
        client.patch(f"/tasks/{task_id}", json={"status": "completed"}, headers=admin_headers),
        client.patch(f"/tasks/{task_id}", json={"status": "completed"}, headers=admin_headers),
    )
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    next_instances = [j.get("next_instance") for j in (r1.json(), r2.json()) if j.get("next_instance")]
    assert len(next_instances) == 1, "exactly one concurrent completion must materialize the next instance"


async def test_patch_completed_with_null_completed_date_autofills_today(client, admin_headers):
    """Regression: status='completed' + completed_date=null used to be
    accepted verbatim, leaving completed_date NULL on a 'completed' task and
    silently dropping it out of completion-rate analytics (which filters/
    aggregates on completed_date being non-null). An explicit null is now
    treated the same as an omitted completed_date: auto-filled to today,
    matching this codebase's existing auto-fill/auto-clear convention for
    status-driven side effects on this column."""
    r = await client.post("/tasks", json={"title": "Complete with null date", "status": "ongoing"},
                           headers=admin_headers)
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]

    r = await client.patch(f"/tasks/{task_id}",
                            json={"status": "completed", "completed_date": None}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["completed_date"] == facility_today().isoformat()

    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert r.json()["task"]["completed_date"] == facility_today().isoformat()

    # Sanity: an explicit, real completed_date is still respected verbatim.
    r = await client.post("/tasks", json={"title": "Complete with real date", "status": "ongoing"},
                           headers=admin_headers)
    task_id2 = r.json()["id"]
    r = await client.patch(f"/tasks/{task_id2}",
                            json={"status": "completed", "completed_date": "2026-01-15"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["completed_date"] == "2026-01-15"
