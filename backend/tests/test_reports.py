"""/reports/weekly — Fri->Thu window math, ref_date validation, plan mode,
department filtering, and the 'postponed' summary-bucket regression."""
import uuid
from datetime import date, timedelta
from app.worktime import facility_today

from app.api.weekwindow import fri_thu
from app.db import tasks_admin_pool
from tests.conftest import create_user, login_and_set_password


async def test_report_endpoints_reject_non_uuid_department_id(client, admin_headers):
    """department_id is a query param bound straight into raw SQL against a uuid
    column, so a non-uuid value would surface as an asyncpg cast error -> 500.
    Both report endpoints that accept it (/reports/weekly and /reports/audit-prep)
    must return a clean 422 instead. A well-formed (if unmatched) uuid is fine."""
    for path in ("/reports/weekly", "/reports/audit-prep"):
        r = await client.get(path, params={"department_id": "not-a-uuid"}, headers=admin_headers)
        assert r.status_code == 422, f"{path}: {r.status_code} {r.text}"
        r = await client.get(path, params={"department_id": str(uuid.uuid4())}, headers=admin_headers)
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text}"


async def test_weekly_report_summary_counts_postponed_tasks(client, admin_headers):
    """Regression: the summary used to omit a 'postponed' bucket even though
    it's a valid, reachable status, so a postponed task counted toward
    summary.total but reconciled with no named bucket in the frontend's
    stat cards."""
    r = await client.post("/tasks", json={"title": "Postponed today", "status": "postponed"},
                           headers=admin_headers)
    assert r.status_code == 201, r.text

    r = await client.get("/reports/weekly", headers=admin_headers)
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert summary["postponed"] >= 1
    # Every bucket the summary reports must add up to (at most) the total —
    # the bug this test pins was postponed silently falling out of the sum.
    accounted = (
        summary["completed"] + summary["in_progress"] + summary["stuck"]
        + summary["pending"] + summary["review"] + summary["postponed"]
    )
    assert accounted == summary["total"]


async def test_report_overdue_excludes_tasks_due_later_this_same_week(client, admin_headers):
    """A task due LATER in a still-in-progress week is not overdue yet — the
    cutoff is real 'today', not the week's Thursday end boundary (a report
    viewed mid-week used to wrongly count it as already overdue). Uses a
    ref_date whose Fri->Thu window ends well after real 'today' so the
    assertion doesn't depend on which day of the week the suite happens to
    run on; the overdue query itself isn't week-bounded, so a genuinely
    past-due task is unaffected by which ref_date is passed."""
    today = facility_today()
    future_ref = today + timedelta(days=10)
    _fri, thu = fri_thu(future_ref)
    assert thu > today  # sanity: the window's end must actually be in the future

    r = await client.post("/tasks", json={
        "title": "Due later this week", "status": "pending", "due_date": thu.isoformat()},
        headers=admin_headers)
    assert r.status_code == 201, r.text
    not_yet_due_id = r.json()["id"]

    r = await client.post("/tasks", json={
        "title": "Actually overdue", "status": "pending",
        "due_date": (today - timedelta(days=1)).isoformat()}, headers=admin_headers)
    assert r.status_code == 201, r.text
    overdue_id = r.json()["id"]

    r = await client.get("/reports/weekly", params={"ref_date": future_ref.isoformat()}, headers=admin_headers)
    assert r.status_code == 200, r.text
    overdue_ids = {t["id"] for t in r.json()["overdue"]}
    assert overdue_id in overdue_ids
    assert not_yet_due_id not in overdue_ids, \
        "a task due later THIS SAME week must not be counted overdue before its due date arrives"


async def test_invalid_ref_date_returns_422(client, admin_headers):
    r = await client.get("/reports/weekly", params={"ref_date": "not-a-date"}, headers=admin_headers)
    assert r.status_code == 422


async def test_normal_priority_sorts_alongside_medium_not_last(client, admin_headers):
    """The GrowFlow UI stores 'normal' as its medium-priority wire value; the
    report's ORDER BY must rank it as medium (tier 2), not fall through to the
    ELSE tier below 'low' — otherwise every default-priority UI task sorts last."""
    # low sorts after medium/normal; normal must come before low.
    await client.post("/tasks", json={"title": "Z low task", "status": "pending",
                                       "priority": "low"}, headers=admin_headers)
    await client.post("/tasks", json={"title": "A normal task", "status": "pending",
                                       "priority": "normal"}, headers=admin_headers)
    r = await client.get("/reports/weekly", headers=admin_headers)
    assert r.status_code == 200, r.text
    titles = [t["title"] for t in r.json()["tasks"]]
    # Despite 'A' < 'Z' alphabetically, ordering is by priority rank first, so
    # the normal task (rank 2) must appear before the low task (rank 3).
    assert titles.index("A normal task") < titles.index("Z low task")


async def test_report_mode_window_is_the_friday_thursday_containing_ref_date(client, admin_headers):
    # 2026-06-24 is a Wednesday -> the containing Fri-Thu window is
    # 2026-06-19 (Fri) .. 2026-06-25 (Thu).
    r = await client.get("/reports/weekly", params={"ref_date": "2026-06-24"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    period = r.json()["period"]
    assert period["start"] == "2026-06-19"
    assert period["end"] == "2026-06-25"


async def test_plan_mode_window_is_shifted_one_week_forward(client, admin_headers):
    r = await client.get("/reports/weekly", params={"ref_date": "2026-06-24", "mode": "plan"},
                          headers=admin_headers)
    assert r.status_code == 200, r.text
    period = r.json()["period"]
    assert period["start"] == "2026-06-26"
    assert period["end"] == "2026-07-02"


async def test_plan_mode_excludes_completed_tasks(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Still open", "status": "pending"}, headers=admin_headers)
    open_id = r.json()["id"]
    r = await client.post("/tasks", json={"title": "Already done", "status": "completed"}, headers=admin_headers)
    done_id = r.json()["id"]

    r = await client.get("/reports/weekly", params={"mode": "plan"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    ids = [t["id"] for t in r.json()["tasks"]]
    assert open_id in ids
    assert done_id not in ids


async def test_report_mode_only_includes_tasks_with_activity_in_the_window(client, admin_headers):
    """A task with no created/updated/completed/progress activity inside
    the queried Fri-Thu window must not appear — report mode is meant to
    show what happened *that week*, not every task that happens to exist."""
    r = await client.post("/tasks", json={"title": "Created just now", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]

    # Query a window far in the past — created_at (now()) falls outside it.
    r = await client.get("/reports/weekly", params={"ref_date": "2020-01-08"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    ids = [t["id"] for t in r.json()["tasks"]]
    assert task_id not in ids

    # The current week's window (default ref_date=today) does include it.
    r = await client.get("/reports/weekly", headers=admin_headers)
    ids = [t["id"] for t in r.json()["tasks"]]
    assert task_id in ids


async def test_department_filter_excludes_other_departments(client, admin_headers, org):
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'cult','Cultivation'), ($1,'qc','QC')"
        " RETURNING id, code",
        org["org_id"],
    )
    dept_ids = {row["code"]: str(row["id"]) for row in rows}

    r = await client.post("/tasks", json={"title": "In Cultivation", "status": "pending",
                                           "department_id": dept_ids["cult"]}, headers=admin_headers)
    cult_task_id = r.json()["id"]
    r = await client.post("/tasks", json={"title": "In QC", "status": "pending",
                                           "department_id": dept_ids["qc"]}, headers=admin_headers)
    qc_task_id = r.json()["id"]

    r = await client.get("/reports/weekly", params={"department_id": dept_ids["cult"]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    ids = [t["id"] for t in r.json()["tasks"]]
    assert cult_task_id in ids
    assert qc_task_id not in ids


async def test_non_elevated_hours_by_person_scoped_to_self(client, admin_headers, org):
    """work_sessions/task_progress RLS is org-scoped only (no owner/assignee
    restriction like tasks_read), so without explicit scoping in the query a
    non-elevated caller would see every colleague's hours and activity here,
    even though their tasks list is correctly RLS-scoped to their own."""
    user, otp = await create_user(client, admin_headers)
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/tasks", json={"title": "Admin's work", "status": "ongoing"}, headers=admin_headers)
    admin_task = r.json()["id"]
    r = await client.post(f"/tasks/{admin_task}/sessions",
                          json={"started_at": "2026-07-04T10:00:00", "hours": 3}, headers=admin_headers)
    assert r.status_code == 201, r.text

    r = await client.post("/tasks", json={"title": "My work", "status": "ongoing"}, headers=headers)
    user_task = r.json()["id"]
    r = await client.post(f"/tasks/{user_task}/sessions",
                          json={"started_at": "2026-07-04T11:00:00", "hours": 2}, headers=headers)
    assert r.status_code == 201, r.text

    r = await client.get("/reports/weekly", params={"ref_date": "2026-07-04"}, headers=headers)
    assert r.status_code == 200, r.text
    hbp = r.json()["hours_by_person"]
    assert len(hbp) == 1
    assert hbp[0]["username"] == user["username"]
    assert hbp[0]["total"] == 2.0

    r = await client.get("/reports/weekly", params={"ref_date": "2026-07-04"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["hours_by_person"]) == 2


async def test_department_filter_scopes_hours_by_person(client, admin_headers, org):
    """Regression: department_id now scopes hours_by_person / the time-band too
    (work_sessions filtered by their task's department). It used to filter only
    the tasks list, so a dept-filtered report still mixed in other departments'
    hours."""
    rows = await tasks_admin_pool().fetch(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'cult','Cultivation'),($1,'qc','QC')"
        " RETURNING id, code", org["org_id"])
    dept = {r["code"]: str(r["id"]) for r in rows}

    r = await client.post("/tasks", json={"title": "Cult task", "status": "ongoing",
        "department_id": dept["cult"]}, headers=admin_headers)
    await client.post(f"/tasks/{r.json()['id']}/sessions",
        json={"started_at": "2026-07-04T10:00:00", "hours": 3}, headers=admin_headers)
    r = await client.post("/tasks", json={"title": "QC task", "status": "ongoing",
        "department_id": dept["qc"]}, headers=admin_headers)
    await client.post(f"/tasks/{r.json()['id']}/sessions",
        json={"started_at": "2026-07-04T12:00:00", "hours": 5}, headers=admin_headers)

    # Filtered to Cultivation → only the 3h cult session.
    r = await client.get("/reports/weekly", params={"ref_date": "2026-07-04", "department_id": dept["cult"]},
                         headers=admin_headers)
    assert r.status_code == 200, r.text
    hbp = r.json()["hours_by_person"]
    assert sum(p["total"] for p in hbp) == 3.0
    # Unfiltered → both sessions (8h).
    r = await client.get("/reports/weekly", params={"ref_date": "2026-07-04"}, headers=admin_headers)
    assert sum(p["total"] for p in r.json()["hours_by_person"]) == 8.0


async def test_summary_sums_estimated_and_actual_hours(client, admin_headers):
    """Effort capture flows through to the report: hours entered on tasks sum
    into summary.estimated_hours / actual_hours (drives the Hours stat card)."""
    await client.post("/tasks", json={"title": "Estimated 4 done 5.5", "status": "ongoing",
                                       "estimated_hours": 4}, headers=admin_headers)
    r = await client.post("/tasks", json={"title": "logged", "status": "ongoing",
                                          "estimated_hours": 2}, headers=admin_headers)
    tid = r.json()["id"]
    await client.patch(f"/tasks/{tid}", json={"actual_hours": 5.5}, headers=admin_headers)

    r = await client.get("/reports/weekly", headers=admin_headers)
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert s["estimated_hours"] == 6.0
    assert s["actual_hours"] == 5.5
