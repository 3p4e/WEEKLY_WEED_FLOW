"""/reports/weekly — Fri->Thu window math, ref_date validation, plan mode,
department filtering, and the 'postponed' summary-bucket regression."""
from app.db import admin_pool


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
    rows = await admin_pool().fetch(
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
