"""TMS T5 — SUMA v2 workflow sign-off: draft → submitted → approved/rejected
(+ QP quality block). The lifecycle moves only through POST /tasks/{id}/workflow;
every transition lands in the append-only task_workflow_events record; the
approver must differ from the submitter; reject/block demand a remark."""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role):
    user, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, user["username"], otp)
    return user, {"Authorization": f"Bearer {token}"}


async def _task(client, headers, title="Sign-off subject"):
    r = await client.post("/tasks", json={"title": title, "status": "pending"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _wf(client, headers, task_id, action, remark=None):
    return await client.post(f"/tasks/{task_id}/workflow",
                             json={"action": action, **({"remark": remark} if remark else {})},
                             headers=headers)


async def test_workflow_submit_approve_happy_path(client, admin_headers):
    """Submit → approve by a second person; the state advances and every
    transition is on the events record with actor + role."""
    task = await _task(client, admin_headers)
    assert task["workflow_state"] == "draft"          # inert default, now live
    r = await _wf(client, admin_headers, task["id"], "submit")
    assert r.status_code == 201 and r.json()["workflow_state"] == "submitted"
    # the submitter cannot sign off their own submission
    r = await _wf(client, admin_headers, task["id"], "approve")
    assert r.status_code == 403
    _, mgr = await _actor(client, admin_headers, "QA_MGR")
    r = await _wf(client, mgr, task["id"], "approve", remark="Looks complete.")
    assert r.status_code == 201 and r.json()["workflow_state"] == "approved"
    wf = (await client.get(f"/tasks/{task['id']}/workflow", headers=admin_headers)).json()
    assert wf["workflow_state"] == "approved"
    assert [e["action"] for e in wf["events"]] == ["SUBMIT", "APPROVE"]
    assert wf["events"][1]["actor_role"] == "QA_MGR" and wf["events"][1]["remark"] == "Looks complete."


async def test_workflow_reject_requires_remark_and_resubmit(client, admin_headers):
    task = await _task(client, admin_headers, title="Rework loop")
    assert (await _wf(client, admin_headers, task["id"], "submit")).status_code == 201
    _, mgr = await _actor(client, admin_headers, "QA_MGR")
    # an unexplained rejection is not a record
    assert (await _wf(client, mgr, task["id"], "reject")).status_code == 422
    r = await _wf(client, mgr, task["id"], "reject", remark="Missing evidence.")
    assert r.status_code == 201 and r.json()["workflow_state"] == "rejected"
    # rejected is resubmittable; approving from rejected is illegal
    assert (await _wf(client, mgr, task["id"], "approve")).status_code == 409
    assert (await _wf(client, admin_headers, task["id"], "submit")).status_code == 201


async def test_workflow_qp_block_and_unblock(client, admin_headers):
    """A quality block is a QP/ADMIN act from any state; lifting it returns the
    task to draft for rework + resubmission."""
    task = await _task(client, admin_headers, title="Quality hold")
    _, mgr = await _actor(client, admin_headers, "QA_MGR")
    _, qp = await _actor(client, admin_headers, "QP")
    # a non-QP manager cannot block
    assert (await _wf(client, mgr, task["id"], "block", remark="hold")).status_code == 403
    # block demands a remark
    assert (await _wf(client, qp, task["id"], "block")).status_code == 422
    r = await _wf(client, qp, task["id"], "block", remark="Deviation under investigation.")
    assert r.status_code == 201 and r.json()["workflow_state"] == "qp_blocked"
    # nothing moves while blocked; only QP/ADMIN lifts
    assert (await _wf(client, admin_headers, task["id"], "submit")).status_code == 409
    assert (await _wf(client, mgr, task["id"], "unblock")).status_code == 403
    r = await _wf(client, qp, task["id"], "unblock")
    assert r.status_code == 201 and r.json()["workflow_state"] == "draft"


async def test_workflow_state_not_patchable_and_guards(client, admin_headers):
    """The raw workflow_state passthrough is gone — a PATCH silently ignores it
    (exclude_unset drops unknown fields is not enough: the field no longer
    exists on TaskPatch, so it cannot reach the UPDATE) — and the endpoint
    validates its inputs."""
    task = await _task(client, admin_headers, title="No bypass")
    r = await client.patch(f"/tasks/{task['id']}", json={"workflow_state": "approved"},
                           headers=admin_headers)
    assert r.status_code == 200
    wf = (await client.get(f"/tasks/{task['id']}/workflow", headers=admin_headers)).json()
    assert wf["workflow_state"] == "draft"            # unchanged — no bypass
    # unknown action → 422; malformed id → 422; USER cannot approve
    assert (await _wf(client, admin_headers, task["id"], "escalate")).status_code == 422
    assert (await _wf(client, admin_headers, "not-a-uuid", "submit")).status_code == 422
    assert (await _wf(client, admin_headers, task["id"], "submit")).status_code == 201
    # a plain USER — assigned so RLS lets them SEE the task — still cannot
    # sign off (the 403 proves the role gate, not mere invisibility)
    plain_user, plain = await _actor(client, admin_headers, "USER")
    assert (await client.post(f"/tasks/{task['id']}/assignees",
                              json={"user_id": plain_user["id"]},
                              headers=admin_headers)).status_code in (200, 201)
    assert (await _wf(client, plain, task["id"], "approve")).status_code == 403


async def test_workflow_transition_delivers_notification(client, admin_headers):
    """H4 (deep-review) — a workflow sign-off must reach participants' inboxes.
    The reason='workflow' notification was silently dropped by emit()'s savepoint
    because the CHECK constraint rejected it; migration 0042 permits it."""
    user, _otp = await create_user(client, admin_headers, role="USER")
    utoken = await login_and_set_password(client, user["username"], _otp)
    uh = {"Authorization": f"Bearer {utoken}"}
    task = await _task(client, admin_headers, title="Notify on submit")
    # assign the task to U, then submit as admin → U is a participant
    assert (await client.post(f"/tasks/{task['id']}/assignees", json={"user_id": user["id"]},
                              headers=admin_headers)).status_code == 201
    assert (await _wf(client, admin_headers, task["id"], "submit")).status_code == 201
    # U now has a workflow-reason notification (previously dropped → empty)
    notes = (await client.get("/notifications?reason=workflow", headers=uh)).json()
    items = notes if isinstance(notes, list) else notes.get("items", notes.get("notifications", []))
    assert any(n.get("reason") == "workflow" for n in items), items
