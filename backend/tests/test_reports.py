"""/reports/weekly — Fri->Thu window math, ref_date validation, plan mode,
department filtering, and the 'postponed' summary-bucket regression."""
from app.db import tasks_admin_pool
from tests.conftest import create_user, login_and_set_password


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


async def test_invalid_ref_date_returns_422(client, admin_headers):
    r = await client.get("/reports/weekly", params={"ref_date": "not-a-date"}, headers=admin_headers)
    assert r.status_code == 422


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
