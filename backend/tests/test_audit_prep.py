"""GET /reports/audit-prep — GMP audit-preparation readiness (assimilated from
the SUMA/ISO17verSUMA executive "GMP & SOP Preparation Tracker" + timeline).

Pins: role gate (base USER 403), per-program rollup + completion_rate over the
tasks.tags facet (incl. a zero-task program still returning a row), the
programs= override + its bounds, the due-date milestone timeline with the
overdue flag, the outcome-traceability sanity check, busiest-scheduled-day, and
dept-scoped managers being pinned to their own department like /analytics.

Every test uses UNIQUE tag names so counts are exact regardless of other tests'
data sharing the DB.
"""
from datetime import date, timedelta

from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role="USER"):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def _task(client, headers, title, tags, status="pending", days=None,
                due_date=None, outcome=None):
    body = {"title": title, "tags": tags, "status": status}
    if days is not None:
        body["days"] = days
    if due_date is not None:
        body["due_date"] = due_date
    r = await client.post("/tasks", json=body, headers=headers)
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    if outcome is not None:
        await client.patch(f"/tasks/{tid}", json={"outcome": outcome}, headers=headers)
    return tid


async def test_base_user_gets_403(client, admin_headers):
    _, uh = await _actor(client, admin_headers)
    assert (await client.get("/reports/audit-prep", headers=uh)).status_code == 403


async def test_programs_param_bounds(client, admin_headers):
    too_many = ",".join(f"p{i}" for i in range(13))
    assert (await client.get(f"/reports/audit-prep?programs={too_many}",
                             headers=admin_headers)).status_code == 422
    long_name = "x" * 65
    assert (await client.get(f"/reports/audit-prep?programs={long_name}",
                             headers=admin_headers)).status_code == 422


async def test_per_program_rollup_and_zero_task_program(client, admin_headers):
    past = (date.today() - timedelta(days=3)).isoformat()
    await _task(client, admin_headers, "mk done", ["AUD_MK"], status="completed")
    await _task(client, admin_headers, "mk ongoing", ["AUD_MK"], status="ongoing")
    # in both MK + EU, stuck and overdue
    await _task(client, admin_headers, "mk+eu stuck late", ["AUD_MK", "AUD_EU"],
                status="stuck", due_date=past)
    await _task(client, admin_headers, "eu pending", ["AUD_EU"], status="pending")

    body = (await client.get("/reports/audit-prep?programs=AUD_MK,AUD_EU,AUD_SOP",
                             headers=admin_headers)).json()
    progs = {p["program"]: p for p in body["programs"]}

    mk = progs["AUD_MK"]
    assert mk["total"] == 3 and mk["completed"] == 1 and mk["ongoing"] == 1
    assert mk["stuck"] == 1 and mk["overdue"] == 1
    assert round(mk["completion_rate"], 3) == 0.333

    eu = progs["AUD_EU"]
    assert eu["total"] == 2 and eu["stuck"] == 1 and eu["pending"] == 1 and eu["overdue"] == 1

    # a program with no matching tasks still appears, with a zero rollup
    assert progs["AUD_SOP"]["total"] == 0 and progs["AUD_SOP"]["completion_rate"] == 0.0


async def test_default_programs_when_unspecified(client, admin_headers):
    body = (await client.get("/reports/audit-prep", headers=admin_headers)).json()
    names = {p["program"] for p in body["programs"]}
    assert {"MK-GMP", "EU-GMP", "SOP-writing"} <= names


async def test_timeline_orders_by_due_and_flags_overdue(client, admin_headers):
    past = (date.today() - timedelta(days=2)).isoformat()
    future = (date.today() + timedelta(days=5)).isoformat()
    await _task(client, admin_headers, "tl late", ["AUD_TL"], status="ongoing", due_date=past)
    await _task(client, admin_headers, "tl upcoming", ["AUD_TL"], status="pending", due_date=future)
    # a task with no due_date must NOT appear on the timeline
    await _task(client, admin_headers, "tl no due", ["AUD_TL"], status="pending")

    body = (await client.get("/reports/audit-prep?programs=AUD_TL", headers=admin_headers)).json()
    tl = body["timeline"]
    assert len(tl) == 2                                   # the no-due task is excluded
    assert tl[0]["due_date"] == past and tl[1]["due_date"] == future   # soonest first
    assert tl[0]["overdue"] is True and tl[1]["overdue"] is False
    assert "AUD_TL" in tl[0]["programs"]


async def test_traceability_counts_completed_without_outcome(client, admin_headers):
    await _task(client, admin_headers, "tr with", ["AUD_TR"], status="completed",
                outcome="finished and documented")
    await _task(client, admin_headers, "tr without", ["AUD_TR"], status="completed")
    await _task(client, admin_headers, "tr ongoing", ["AUD_TR"], status="ongoing")

    body = (await client.get("/reports/audit-prep?programs=AUD_TR", headers=admin_headers)).json()
    tr = body["traceability"]
    assert tr["completed"] == 2 and tr["with_outcome"] == 1 and tr["without_outcome"] == 1
    assert tr["rate"] == 0.5


async def test_busiest_scheduled_day(client, admin_headers):
    await _task(client, admin_headers, "d1", ["AUD_DAY"], days=["Mon"])
    await _task(client, admin_headers, "d2", ["AUD_DAY"], days=["Mon", "Tue"])
    await _task(client, admin_headers, "d3", ["AUD_DAY"], days=["Mon"])

    body = (await client.get("/reports/audit-prep?programs=AUD_DAY", headers=admin_headers)).json()
    assert body["busiest_day"]["day"] == "Mon" and body["busiest_day"]["count"] == 3
    assert body["day_distribution"]["Mon"] == 3 and body["day_distribution"]["Tue"] == 1


async def test_dept_scoped_manager_pinned_to_own_department(client, admin_headers):
    mine = (await client.post("/departments", json={"code": "ap_mine", "name": "AP Mine"},
                              headers=admin_headers)).json()
    other = (await client.post("/departments", json={"code": "ap_other", "name": "AP Other"},
                               headers=admin_headers)).json()
    mgr, mh = await _actor(client, admin_headers, role="QC_MGR")
    await client.patch(f"/auth/users/{mgr['id']}", json={"department_id": mine["id"]},
                       headers=admin_headers)
    await client.post("/tasks", json={"title": "mine ap", "tags": ["AUD_DEP"],
                                       "department_id": mine["id"]}, headers=admin_headers)
    await client.post("/tasks", json={"title": "other ap", "tags": ["AUD_DEP"],
                                      "department_id": other["id"]}, headers=admin_headers)

    body = (await client.get("/reports/audit-prep?programs=AUD_DEP", headers=mh)).json()
    dep = next(p for p in body["programs"] if p["program"] == "AUD_DEP")
    assert dep["total"] == 1                 # only the manager's own department counted
    assert body["department_id"] == mine["id"]
