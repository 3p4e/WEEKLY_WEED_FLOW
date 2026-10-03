"""P1 — task assignment, and direct regression tests for three bugs fixed
this session:
  1. assign() used to accept a user_id from any org (no cross-org check).
  2. a malformed (non-UUID) user_id crashed with an unhandled 500.
  3. tasks_write RLS had no assignee clause, so a legitimately assigned
     user could never persist a status/field change on their own task —
     silently rejected forever, no matter who assigned them.
"""
import uuid

from tests.conftest import create_user, login_and_set_password


async def test_assign_same_org_user_succeeds(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Assign me", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers)
    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text

    r = await client.get("/tasks?parents_only=true", headers=admin_headers)
    listed = next(t for t in r.json() if t["id"] == task_id)
    assert user["id"] in listed["assignee_ids"]


async def test_assign_cross_org_user_rejected(client, admin_headers, org):
    """org A's admin tries to assign a real profile that belongs to org B."""
    r = await client.post("/tasks", json={"title": "Cross-org assign attempt", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]

    # A second, independent org with its own admin.
    other_org_id = uuid.uuid4()
    other_admin_id = uuid.uuid4()
    from app.db import users_admin_pool
    from app.security import hash_password
    pool = users_admin_pool()
    await pool.execute("INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
                        other_org_id, "Other Org", f"other-{other_org_id.hex[:8]}")
    await pool.execute(
        "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,'ADMIN',false)",
        other_admin_id, other_org_id, f"other_admin_{other_org_id.hex[:6]}",
        hash_password("whatever"), "Other Admin")
    try:
        r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": str(other_admin_id)},
                               headers=admin_headers)
        assert r.status_code == 404, r.text
        assert "organization" in r.json()["detail"].lower()
    finally:
        from tests.conftest import purge_org
        await purge_org(other_org_id)


async def test_assign_malformed_uuid_returns_422_not_500(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Malformed assignee", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]
    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": "not-a-uuid"}, headers=admin_headers)
    assert r.status_code == 422


async def test_reassigning_the_same_pair_upserts_cleanly(client, admin_headers):
    """assign() relies on ON CONFLICT (task_id, user_id) DO UPDATE for a
    repeat assignment — no exception path should be reachable there, so
    posting the same pair twice (e.g. to change role) must succeed both
    times, not surface a masked/misleading error."""
    r = await client.post("/tasks", json={"title": "Reassign me", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers)
    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"], "role": "assignee"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"], "role": "reviewer"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    lst = (await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)).json()
    assert next(a for a in lst if a["user_id"] == user["id"])["role"] == "reviewer"


async def test_assignee_can_write_task_they_are_assigned_to(client, admin_headers):
    """The core RLS regression test: a plain USER who is assigned to a task
    (but doesn't own it and has no elevated role) must be able to persist a
    status change on it — this is what tasks_write's new assignee clause
    fixes, and what GF.ownsTask on the frontend already assumed."""
    r = await client.post("/tasks", json={"title": "Assignee write test", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]

    user, otp = await create_user(client, admin_headers, role="USER")
    op_token = await login_and_set_password(client, user["username"], otp)
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # Before assignment: invisible and unwritable.
    r = await client.get("/tasks?parents_only=true", headers=op_headers)
    assert not any(t["id"] == task_id for t in r.json())
    r = await client.patch(f"/tasks/{task_id}", json={"status": "ongoing"}, headers=op_headers)
    assert r.status_code == 404

    # Admin assigns them.
    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)
    assert r.status_code == 201

    # After assignment: visible and writable, without being the owner or elevated.
    r = await client.get("/tasks?parents_only=true", headers=op_headers)
    assert any(t["id"] == task_id for t in r.json())
    r = await client.patch(f"/tasks/{task_id}", json={"status": "ongoing"}, headers=op_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ongoing"


async def test_non_owner_non_assignee_cannot_assign_others(client, admin_headers):
    """A plain USER who isn't the task's owner or elevated can't manage
    assignment on it, even if they can see it as an assignee themselves."""
    r = await client.post("/tasks", json={"title": "Assign permission check", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]

    assignee, otp1 = await create_user(client, admin_headers, role="USER")
    bystander, otp2 = await create_user(client, admin_headers, role="USER")
    assignee_token = await login_and_set_password(client, assignee["username"], otp1)

    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": assignee["id"]}, headers=admin_headers)

    r = await client.post(f"/tasks/{task_id}/assignees", json={"user_id": bystander["id"]},
                           headers={"Authorization": f"Bearer {assignee_token}"})
    assert r.status_code == 403


async def test_comment_and_ack_flow(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Comment/ack test", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)

    r = await client.post(f"/tasks/{task_id}/comments", json={"content": "On it"}, headers=headers)
    assert r.status_code == 201, r.text

    r = await client.post(f"/tasks/{task_id}/ack", json={"accepted": True}, headers=headers)
    assert r.status_code == 200, r.text

    r = await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)
    assignee_row = next(a for a in r.json() if a["user_id"] == user["id"])
    assert assignee_row["accepted"] is True


async def test_ack_decline_records_reason_as_a_comment(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Decline test", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, user["username"], otp)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)

    r = await client.post(f"/tasks/{task_id}/ack", json={"accepted": False, "reason": "Overloaded this week"},
                           headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is False

    r = await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)
    assignee_row = next(a for a in r.json() if a["user_id"] == user["id"])
    assert assignee_row["accepted"] is False

    r = await client.get(f"/tasks/{task_id}/comments", headers=admin_headers)
    comments = [c["content"] for c in r.json()]
    assert any("Declined" in c and "Overloaded this week" in c for c in comments)


async def test_ack_by_someone_not_assigned_returns_404(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Not your task", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    bystander, otp = await create_user(client, admin_headers, role="USER")
    token = await login_and_set_password(client, bystander["username"], otp)
    r = await client.post(f"/tasks/{task_id}/ack", json={"accepted": True},
                           headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


async def test_owner_can_unassign(client, admin_headers):
    r = await client.post("/tasks", json={"title": "Unassign test", "status": "pending"}, headers=admin_headers)
    task_id = r.json()["id"]
    user, otp = await create_user(client, admin_headers, role="USER")
    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": user["id"]}, headers=admin_headers)

    r = await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)
    assert any(a["user_id"] == user["id"] for a in r.json())

    r = await client.delete(f"/tasks/{task_id}/assignees/{user['id']}", headers=admin_headers)
    assert r.status_code == 200, r.text

    r = await client.get(f"/tasks/{task_id}/assignees", headers=admin_headers)
    assert not any(a["user_id"] == user["id"] for a in r.json())


async def test_non_owner_non_assignee_cannot_unassign_others(client, admin_headers):
    """Mirrors test_non_owner_non_assignee_cannot_assign_others for the
    DELETE side — _can_manage_task gates both the same way. Uses a second
    assignee (not a bystander) as the actor: a true bystander can't see the
    task at all via tasks_read RLS and would 404 before ever reaching the
    _can_manage_task check, which would prove the wrong thing."""
    r = await client.post("/tasks", json={"title": "Unassign permission check", "status": "pending"},
                           headers=admin_headers)
    task_id = r.json()["id"]

    assignee1, otp1 = await create_user(client, admin_headers, role="USER")
    assignee2, otp2 = await create_user(client, admin_headers, role="USER")
    assignee1_token = await login_and_set_password(client, assignee1["username"], otp1)

    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": assignee1["id"]}, headers=admin_headers)
    await client.post(f"/tasks/{task_id}/assignees", json={"user_id": assignee2["id"]}, headers=admin_headers)

    r = await client.delete(f"/tasks/{task_id}/assignees/{assignee2['id']}",
                             headers={"Authorization": f"Bearer {assignee1_token}"})
    assert r.status_code == 403


# ── TMS T1: cross-department handoff lifecycle ──────────────────────────────
async def test_handoff_propose_and_accept_moves_department(client, admin_headers):
    d_from = (await client.post("/departments", json={"code": "ho_from", "name": "HO From"},
                                headers=admin_headers)).json()
    d_to = (await client.post("/departments", json={"code": "ho_to", "name": "HO To"},
                              headers=admin_headers)).json()
    task = (await client.post("/tasks", json={"title": "Transfer me", "department_id": d_from["id"]},
                              headers=admin_headers)).json()
    tid = task["id"]
    # propose a handoff to the other department
    r = await client.post(f"/tasks/{tid}/handoffs",
                          json={"to_dept_id": d_to["id"], "note": "please take over"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    handoff = r.json()
    assert handoff["status"] == "proposed" and str(handoff["to_dept_id"]) == d_to["id"]
    # it shows up in the task's handoff list
    lst = (await client.get(f"/tasks/{tid}/handoffs", headers=admin_headers)).json()
    assert len(lst) == 1 and lst[0]["id"] == handoff["id"]
    # the PROPOSER may not accept their own handoff — the target department
    # never consented (second-person rule); org-wide authority doesn't waive it
    r = await client.post(f"/handoffs/{handoff['id']}/resolve", json={"status": "accepted"},
                          headers=admin_headers)
    assert r.status_code == 403, r.text
    # the target department's manager accepts → the task re-homes there
    to_mgr_user, to_otp = await create_user(client, admin_headers, role="PR_MGR",
                                            department_id=d_to["id"])
    to_mgr_token = await login_and_set_password(client, to_mgr_user["username"], to_otp)
    to_mgr = {"Authorization": f"Bearer {to_mgr_token}"}
    r = await client.post(f"/handoffs/{handoff['id']}/resolve", json={"status": "accepted"},
                          headers=to_mgr)
    assert r.status_code == 200, r.text
    moved = (await client.get(f"/tasks/{tid}", headers=admin_headers)).json()["task"]
    assert str(moved["department_id"]) == d_to["id"]
    # a resolved handoff cannot be resolved again
    r = await client.post(f"/handoffs/{handoff['id']}/resolve", json={"status": "rejected"},
                          headers=admin_headers)
    assert r.status_code == 409


async def _mgr(client, admin_headers, role, dept_id):
    prof, otp = await create_user(client, admin_headers, role=role, department_id=dept_id)
    tok = await login_and_set_password(client, prof["username"], otp)
    return prof, {"Authorization": f"Bearer {tok}"}


async def test_handoff_reaches_the_receiving_manager_who_can_open_the_task_while_it_is_pending(
        client, admin_headers):
    """Review 2026-09-27, BC-04. departments.head_user_id was never written, so
    propose_handoff pinged nobody on the receiving side; and the receiving
    manager could not open the task or its handoff list (404 from the scope
    guard — the task still sits in the SOURCE department), so the Accept
    button never rendered for the one person meant to press it.

    Now: the manager provisioned into the target department becomes its head
    (departments.head_user_id), the proposal notifies the target department's
    managers AND those of its parent (Cultivation's manager receives a handoff
    addressed to Cloning), and the task is in their scope while the proposal
    is pending — and out of it again once it is rejected."""
    src = (await client.post("/departments", json={"code": "ho_src", "name": "Source"},
                             headers=admin_headers)).json()
    cult = (await client.post("/departments", json={"code": "ho_cult", "name": "Cultivation"},
                              headers=admin_headers)).json()
    clone = (await client.post("/departments", json={"code": "ho_clone", "name": "Cloning",
                                                     "parent_id": cult["id"]},
                               headers=admin_headers)).json()
    _, src_mgr_h = await _mgr(client, admin_headers, "QC_MGR", src["id"])
    cu, cu_h = await _mgr(client, admin_headers, "CU_MGR", cult["id"])
    # provisioning the manager set them as the department's head (BC-04 backend half)
    depts = {d["code"]: d for d in (await client.get("/departments", headers=admin_headers)).json()}
    assert str(depts["ho_cult"]["head_user_id"]) == cu["id"]

    task = (await client.post("/tasks", json={"title": "Clones needed", "department_id": src["id"]},
                              headers=src_mgr_h)).json()
    tid = task["id"]
    # before the proposal the cultivation manager cannot see it at all
    assert (await client.get(f"/tasks/{tid}", headers=cu_h)).status_code == 404

    r = await client.post(f"/tasks/{tid}/handoffs", json={"to_dept_id": clone["id"]}, headers=src_mgr_h)
    assert r.status_code == 201, r.text
    hid = r.json()["id"]

    # notified — through the parent department, not only an exact match
    inbox = (await client.get("/notifications", headers=cu_h)).json()
    assert any(n["verb"] == "handoff" and n["task_id"] == tid for n in inbox), inbox
    # …and the task, its handoff list and the board now show it
    assert (await client.get(f"/tasks/{tid}", headers=cu_h)).status_code == 200
    hl = (await client.get(f"/tasks/{tid}/handoffs", headers=cu_h)).json()
    assert [h["id"] for h in hl] == [hid]
    assert tid in {t["id"] for t in (await client.get("/tasks", headers=cu_h)).json()}

    # the receiving manager rejects it → the task leaves their scope again
    r = await client.post(f"/handoffs/{hid}/resolve", json={"status": "rejected"}, headers=cu_h)
    assert r.status_code == 200, r.text
    assert (await client.get(f"/tasks/{tid}", headers=cu_h)).status_code == 404


async def test_pending_handoffs_lists_what_the_caller_may_decide_until_it_is_resolved(
        client, admin_headers):
    """Review 2026-09-27b, R2-FE-09. The Approvals list was rebuilt from
    `handoff` notifications, so marking the notification Done dropped the
    proposal from the only list that showed it. GET /handoffs/pending reads
    the handoffs themselves: the receiving side (here through the parent
    department) sees the proposal after the notification is done; the
    proposing department-scoped manager does not; an org-wide role sees it as
    an arbiter; nobody sees it once it is resolved."""
    src = (await client.post("/departments", json={"code": "hp_src", "name": "Source"},
                             headers=admin_headers)).json()
    cult = (await client.post("/departments", json={"code": "hp_cult", "name": "Cultivation"},
                              headers=admin_headers)).json()
    clone = (await client.post("/departments", json={"code": "hp_clone", "name": "Cloning",
                                                     "parent_id": cult["id"]},
                               headers=admin_headers)).json()
    _, src_h = await _mgr(client, admin_headers, "QC_MGR", src["id"])
    _, cu_h = await _mgr(client, admin_headers, "CU_MGR", cult["id"])
    tid = (await client.post("/tasks", json={"title": "Cuttings for GP", "department_id": src["id"]},
                             headers=src_h)).json()["id"]
    hid = (await client.post(f"/tasks/{tid}/handoffs", json={"to_dept_id": clone["id"]},
                             headers=src_h)).json()["id"]

    # the recipient marks the notification done — the proposal must stay listed
    for n in (await client.get("/notifications", headers=cu_h)).json():
        if n["verb"] == "handoff" and n["task_id"] == tid:
            assert (await client.post(f"/notifications/{n['id']}/done", headers=cu_h)).status_code in (200, 204)
    assert not [n for n in (await client.get("/notifications", headers=cu_h)).json()
                if n["verb"] == "handoff" and n["task_id"] == tid]
    rows = (await client.get("/handoffs/pending", headers=cu_h)).json()
    assert [(r["id"], r["task_title"], r["target_side"]) for r in rows] == [(hid, "Cuttings for GP", True)]
    # the proposer's department is not the receiving side
    assert (await client.get("/handoffs/pending", headers=src_h)).json() == []
    # an org-wide role may arbitrate it, and is told it is not the target side
    arb = [r for r in (await client.get("/handoffs/pending", headers=admin_headers)).json() if r["id"] == hid]
    assert len(arb) == 1 and arb[0]["target_side"] is False

    assert (await client.post(f"/handoffs/{hid}/resolve", json={"status": "accepted"},
                              headers=cu_h)).status_code == 200
    assert (await client.get("/handoffs/pending", headers=cu_h)).json() == []


async def test_a_pending_handoff_opens_the_task_to_the_receiving_manager_for_reading_only(
        client, admin_headers):
    """Review 2026-09-27, R2-BC-04. A proposal addressed to my department lets
    me OPEN the task to accept or reject it — it does not make the task mine
    to edit. The receiving manager could retitle it, log sessions on it, move
    its status and sign it off while it still sat in the source department,
    and attach a subtask of their own to it, which kept the parent in their
    scope through the "child in my family" arm after the proposal was
    rejected. Reads and the comment thread keep the pending-handoff arm;
    every write is refused (404, the guard's usual answer) until the handoff
    is accepted and the task actually moves."""
    src = (await client.post("/departments", json={"code": "hr_src", "name": "Source"},
                             headers=admin_headers)).json()
    cult = (await client.post("/departments", json={"code": "hr_cult", "name": "Cultivation"},
                              headers=admin_headers)).json()
    _, src_mgr_h = await _mgr(client, admin_headers, "QC_MGR", src["id"])
    _, cu_h = await _mgr(client, admin_headers, "CU_MGR", cult["id"])
    tid = (await client.post("/tasks", json={"title": "Clones needed", "department_id": src["id"]},
                             headers=src_mgr_h)).json()["id"]
    r = await client.post(f"/tasks/{tid}/handoffs", json={"to_dept_id": cult["id"]}, headers=src_mgr_h)
    assert r.status_code == 201, r.text
    hid = r.json()["id"]

    # reads and the discussion around the proposal
    assert (await client.get(f"/tasks/{tid}", headers=cu_h)).status_code == 200
    assert (await client.get(f"/tasks/{tid}/handoffs", headers=cu_h)).status_code == 200
    assert (await client.get(f"/tasks/{tid}/comments", headers=cu_h)).status_code == 200
    assert (await client.post(f"/tasks/{tid}/comments", json={"content": "can we make it Nursery?"},
                              headers=cu_h)).status_code == 201
    # …but nothing that changes the task or hangs new records off it
    writes = [
        ("patch", f"/tasks/{tid}", {"title": "Renamed by the receiver"}),
        ("patch", f"/tasks/{tid}", {"status": "completed"}),
        ("post", f"/tasks/{tid}/workflow", {"action": "SUBMIT"}),
        ("post", f"/tasks/{tid}/sessions", {"started_at": "2026-07-06T09:00:00", "hours": 1}),
        ("post", f"/tasks/{tid}/progress", {"day_label": "Mon", "note": "x"}),
        ("post", f"/tasks/{tid}/links", {"url": "https://example.invalid/x", "label": "x"}),
        ("post", f"/tasks/{tid}/assignees", {"user_id": str(uuid.uuid4())}),
        ("post", f"/tasks/{tid}/handoffs", {"to_dept_id": src["id"]}),
    ]
    for method, path, body in writes:
        r = await getattr(client, method)(path, json=body, headers=cu_h)
        assert r.status_code == 404, (method, path, r.status_code, r.text)
    # a subtask under the pending task is a write on it too: refused, so the
    # parent cannot be pinned into the receiver's scope through a child
    r = await client.post("/tasks", json={"title": "child", "parent_id": tid,
                                          "department_id": cult["id"]}, headers=cu_h)
    assert r.status_code == 404, r.text
    t = (await client.get(f"/tasks/{tid}", headers=src_mgr_h)).json()["task"]
    assert t["title"] == "Clones needed" and t["status"] != "completed"

    # rejected → out of scope again, with no child left behind to keep it
    r = await client.post(f"/handoffs/{hid}/resolve", json={"status": "rejected"}, headers=cu_h)
    assert r.status_code == 200, r.text
    assert (await client.get(f"/tasks/{tid}", headers=cu_h)).status_code == 404
    assert tid not in {x["id"] for x in (await client.get("/tasks", headers=cu_h)).json()}

    # accepted → the task moves, and only then does the receiver edit it
    hid = (await client.post(f"/tasks/{tid}/handoffs", json={"to_dept_id": cult["id"]},
                             headers=src_mgr_h)).json()["id"]
    assert (await client.post(f"/handoffs/{hid}/resolve", json={"status": "accepted"},
                              headers=cu_h)).status_code == 200
    r = await client.patch(f"/tasks/{tid}", json={"title": "Now ours"}, headers=cu_h)
    assert r.status_code == 200, r.text
    r = await client.post("/tasks", json={"title": "child", "parent_id": tid}, headers=cu_h)
    assert r.status_code == 201, r.text


async def test_department_head_is_maintained_by_the_roster_and_editable_by_admin(client, admin_headers):
    """The head follows the roster (first scoped manager in, out again on
    move/demotion/delete; an existing head is never displaced automatically)
    and ADMIN can set it explicitly on create or via PATCH /departments/{id}."""
    d = (await client.post("/departments", json={"code": "head_d", "name": "Head Dept"},
                           headers=admin_headers)).json()
    first, _ = await _mgr(client, admin_headers, "PR_MGR", d["id"])
    second, _ = await _mgr(client, admin_headers, "PR_MGR", d["id"])

    async def head():
        rows = (await client.get("/departments", headers=admin_headers)).json()
        return next(x for x in rows if x["code"] == "head_d")["head_user_id"]

    assert str(await head()) == first["id"], "the first manager in becomes head; the second does not displace them"
    # moving the head out of the department clears it, and the vacancy is
    # filled by the next manager who is (re)assigned there
    other = (await client.post("/departments", json={"code": "head_o", "name": "Other"},
                               headers=admin_headers)).json()
    r = await client.patch(f"/auth/users/{first['id']}", json={"department_id": other["id"]},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    assert await head() is None
    r = await client.patch(f"/auth/users/{second['id']}", json={"department_id": d["id"]},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    assert str(await head()) == second["id"]
    # deleting the head clears it
    assert (await client.delete(f"/auth/users/{second['id']}", headers=admin_headers)).status_code == 200
    assert await head() is None
    # ADMIN sets it explicitly; a base USER is refused as head; null clears
    op, _ = await create_user(client, admin_headers, role="USER", department_id=d["id"])
    r = await client.patch(f"/departments/{d['id']}", json={"head_user_id": op["id"]}, headers=admin_headers)
    assert r.status_code == 422
    r = await client.patch(f"/departments/{d['id']}", json={"head_user_id": first["id"]}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert str(await head()) == first["id"]
    r = await client.patch(f"/departments/{d['id']}", json={"head_user_id": None}, headers=admin_headers)
    assert r.status_code == 200 and await head() is None
    # and on create
    r = await client.post("/departments", json={"code": "head_c", "name": "Created With Head",
                                                "head_user_id": first["id"]}, headers=admin_headers)
    assert r.status_code == 201 and str(r.json()["head_user_id"]) == first["id"]
    # managers may not edit departments
    _, pr_h = await _mgr(client, admin_headers, "WH_MGR", d["id"])
    assert (await client.patch(f"/departments/{d['id']}", json={"name": "x"}, headers=pr_h)).status_code == 403


async def test_handoff_to_same_department_rejected(client, admin_headers):
    d = (await client.post("/departments", json={"code": "ho_same", "name": "HO Same"},
                           headers=admin_headers)).json()
    task = (await client.post("/tasks", json={"title": "x", "department_id": d["id"]},
                              headers=admin_headers)).json()
    r = await client.post(f"/tasks/{task['id']}/handoffs", json={"to_dept_id": d["id"]},
                          headers=admin_headers)
    assert r.status_code == 422


async def test_malformed_ids_return_404_not_500(client, admin_headers):
    """H11: a garbage (non-uuid) task_id/handoff_id/assignee_id used to reach
    asyncpg raw and 500 instead of the clean 'not found' every sibling
    genuinely-missing-row path already returns."""
    garbage = "not-a-uuid"
    task = (await client.post("/tasks", json={"title": "id-guard subject"}, headers=admin_headers)).json()
    tid = task["id"]

    assert (await client.get(f"/tasks/{garbage}/comments", headers=admin_headers)).status_code == 404
    assert (await client.post(f"/tasks/{garbage}/comments", json={"content": "hi"},
                              headers=admin_headers)).status_code == 404
    assert (await client.get(f"/tasks/{garbage}/assignees", headers=admin_headers)).status_code == 404
    assert (await client.delete(f"/tasks/{tid}/assignees/{garbage}", headers=admin_headers)).status_code == 404
    assert (await client.post(f"/tasks/{garbage}/ack", json={"accepted": True},
                              headers=admin_headers)).status_code == 404
    assert (await client.post(f"/tasks/{garbage}/handoffs", json={"to_dept_id": str(uuid.uuid4())},
                              headers=admin_headers)).status_code == 404
    assert (await client.get(f"/tasks/{garbage}/handoffs", headers=admin_headers)).status_code == 404
    assert (await client.post(f"/handoffs/{garbage}/resolve", json={"status": "accepted"},
                              headers=admin_headers)).status_code == 404
