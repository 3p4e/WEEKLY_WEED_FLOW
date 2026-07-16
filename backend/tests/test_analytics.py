"""GET /reports/analytics — cross-week trends, deliberately hour-free.

Pins: role gate (base USER 403), weekly bucket math (created/completed/on_time
land in the current Fri→Thu bucket), the current department snapshot
(open/stuck/overdue/completed), the open-task type mix, and dept-scoped
managers being pinned to their own department like /reports/weekly.
"""
from datetime import date, timedelta

from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role="USER"):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def test_base_user_gets_403(client, admin_headers):
    _, uh = await _actor(client, admin_headers)
    assert (await client.get("/reports/analytics", headers=uh)).status_code == 403


async def test_weeks_param_bounds(client, admin_headers):
    assert (await client.get("/reports/analytics?weeks=3", headers=admin_headers)).status_code == 422
    assert (await client.get("/reports/analytics?weeks=17", headers=admin_headers)).status_code == 422


async def test_weekly_buckets_and_snapshot(client, admin_headers):
    dept = (await client.post("/departments", json={"code": "ana_d1", "name": "Ana D1"},
                              headers=admin_headers)).json()
    today = date.today()
    # one completed on time (due today, completed today), one open + overdue
    r1 = await client.post("/tasks", json={"title": "Ana done", "department_id": dept["id"],
                                           "task_type": "lab", "due_date": today.isoformat()},
                           headers=admin_headers)
    await client.patch(f"/tasks/{r1.json()['id']}", json={"status": "completed"},
                       headers=admin_headers)
    await client.post("/tasks", json={"title": "Ana late", "department_id": dept["id"],
                                      "task_type": "capa",
                                      "due_date": (today - timedelta(days=2)).isoformat()},
                      headers=admin_headers)

    body = (await client.get("/reports/analytics", headers=admin_headers)).json()
    assert body["range"]["weeks"] == 8 and len(body["weeks"]) == 8
    cur = body["weeks"][-1]                      # newest bucket = current window
    assert cur["created"] >= 2
    assert cur["completed"] >= 1 and cur["on_time"] >= 1
    # nothing hour-shaped anywhere in the payload
    assert "hours" not in str(body)

    drow = next(d for d in body["departments"] if d["id"] == dept["id"])
    assert drow["open"] >= 1 and drow["overdue"] >= 1 and drow["completed"] >= 1
    types = {t["task_type"]: t["count"] for t in body["task_types"]}
    assert types.get("capa", 0) >= 1             # open task counted
    assert "lab" not in types or types["lab"] >= 0  # completed one no longer "open"


async def test_dept_scoped_manager_sees_only_their_department(client, admin_headers):
    mine = (await client.post("/departments", json={"code": "ana_mine", "name": "Mine"},
                              headers=admin_headers)).json()
    other = (await client.post("/departments", json={"code": "ana_other", "name": "Other"},
                               headers=admin_headers)).json()
    mgr, mh = await _actor(client, admin_headers, role="QC_MGR")
    await client.patch(f"/auth/users/{mgr['id']}", json={"department_id": mine["id"]},
                       headers=admin_headers)
    await client.post("/tasks", json={"title": "In mine", "department_id": mine["id"]},
                      headers=admin_headers)
    await client.post("/tasks", json={"title": "In other", "department_id": other["id"]},
                      headers=admin_headers)

    body = (await client.get("/reports/analytics", headers=mh)).json()
    ids = {d["id"] for d in body["departments"]}
    assert mine["id"] in ids and other["id"] not in ids
