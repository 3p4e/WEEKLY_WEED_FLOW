"""GET /approvals/pending — the acknowledgment aggregate behind Approvals/My Day.

Pins: a fresh assignment is pending for the assignee (mine) and visible to
elevated follow-up (team); acknowledging clears it; base USERs get their own
list but never the team list; dept-scoped managers see only their department.
"""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role="USER", department_id=None):
    u, otp = await create_user(client, admin_headers, role=role, department_id=department_id)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def test_pending_lifecycle(client, admin_headers):
    worker, wh = await _actor(client, admin_headers)
    r = await client.post("/tasks", json={"title": "Ack me"}, headers=admin_headers)
    tid = r.json()["id"]
    assert (await client.post(f"/tasks/{tid}/assignees",
                              json={"user_id": worker["id"]}, headers=admin_headers)).status_code == 201
    # pending for the assignee...
    mine = (await client.get("/approvals/pending", headers=wh)).json()
    row = next(x for x in mine["mine"] if x["task_id"] == tid)
    assert row["title"] == "Ack me"
    assert mine["team"] == []                        # base USER never gets team
    # ...and on the admin's team follow-up list
    team = (await client.get("/approvals/pending", headers=admin_headers)).json()["team"]
    assert any(x["task_id"] == tid and x["user_id"] == worker["id"] for x in team)
    # acknowledging clears both
    assert (await client.post(f"/tasks/{tid}/ack", json={"accepted": True},
                              headers=wh)).status_code == 200
    mine = (await client.get("/approvals/pending", headers=wh)).json()["mine"]
    assert not any(x["task_id"] == tid for x in mine)
    team = (await client.get("/approvals/pending", headers=admin_headers)).json()["team"]
    assert not any(x["task_id"] == tid for x in team)


async def test_completed_and_archived_drop_out(client, admin_headers):
    worker, wh = await _actor(client, admin_headers)
    r = await client.post("/tasks", json={"title": "Finished before ack"}, headers=admin_headers)
    tid = r.json()["id"]
    await client.post(f"/tasks/{tid}/assignees", json={"user_id": worker["id"]}, headers=admin_headers)
    await client.patch(f"/tasks/{tid}", json={"status": "completed"}, headers=admin_headers)
    mine = (await client.get("/approvals/pending", headers=wh)).json()["mine"]
    assert not any(x["task_id"] == tid for x in mine)


async def test_team_is_department_scoped_for_managers(client, admin_headers):
    # two departments, one pending ack in each
    d1 = (await client.post("/departments", json={"code": "apv_d1", "name": "Apv D1"},
                            headers=admin_headers)).json()
    d2 = (await client.post("/departments", json={"code": "apv_d2", "name": "Apv D2"},
                            headers=admin_headers)).json()
    w1, _ = await _actor(client, admin_headers)
    w2, _ = await _actor(client, admin_headers)
    mgr, mh = await _actor(client, admin_headers, role="QC_MGR", department_id=d1["id"])
    for dep, w in ((d1, w1), (d2, w2)):
        r = await client.post("/tasks", json={"title": f"In {dep['code']}",
                                              "department_id": dep["id"]}, headers=admin_headers)
        await client.post(f"/tasks/{r.json()['id']}/assignees",
                          json={"user_id": w["id"]}, headers=admin_headers)
    team = (await client.get("/approvals/pending", headers=mh)).json()["team"]
    depts = {x["department_id"] for x in team}
    assert d1["id"] in depts and d2["id"] not in depts
    # org-wide (admin) sees both
    team = (await client.get("/approvals/pending", headers=admin_headers)).json()["team"]
    depts = {x["department_id"] for x in team}
    assert d1["id"] in depts and d2["id"] in depts
