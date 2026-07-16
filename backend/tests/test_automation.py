"""Canned automation rules (app/automation.py) — a FIXED rule set, not a
user-configurable builder: CAPA work going stuck reaches QA + the Qualified
Person, validation work going stuck reaches the Qualified Person, regardless
of who is assigned. Pins: the rule only fires for its exact (task_type,
status) pair, uninvolved roles are never notified, and a canned recipient who
is ALSO a participant gets the more specific reason (first-reason-wins).
"""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role="USER"):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def test_capa_stuck_notifies_qa_and_qp_not_unrelated_managers(client, admin_headers):
    qa, qah = await _actor(client, admin_headers, role="QA_MGR")
    qp, qph = await _actor(client, admin_headers, role="QP")
    qc, qch = await _actor(client, admin_headers, role="QC_MGR")  # unrelated — must NOT hear
    worker, wh = await _actor(client, admin_headers)

    r = await client.post("/tasks", json={"title": "CAPA A", "task_type": "capa"},
                          headers=admin_headers)
    tid = r.json()["id"]
    await client.post(f"/tasks/{tid}/assignees", json={"user_id": worker["id"]}, headers=admin_headers)
    for h in (qah, qph, qch, wh):
        await client.post("/notifications/read-all", headers=h)

    assert (await client.patch(f"/tasks/{tid}", json={"status": "stuck"},
                               headers=admin_headers)).status_code == 200

    qa_inbox = (await client.get("/notifications", headers=qah)).json()
    assert any(n["task_id"] == tid and n["reason"] == "capa_stuck" for n in qa_inbox)
    qp_inbox = (await client.get("/notifications", headers=qph)).json()
    assert any(n["task_id"] == tid and n["reason"] == "capa_stuck" for n in qp_inbox)
    qc_inbox = (await client.get("/notifications", headers=qch)).json()
    assert not any(n["task_id"] == tid for n in qc_inbox)
    # the assigned worker still gets the ordinary participant notification
    w_inbox = (await client.get("/notifications", headers=wh)).json()
    assert any(n["task_id"] == tid and n["reason"] == "status" for n in w_inbox)


async def test_validation_stuck_notifies_qp_only(client, admin_headers):
    qa, qah = await _actor(client, admin_headers, role="QA_MGR")
    qp, qph = await _actor(client, admin_headers, role="QP")

    r = await client.post("/tasks", json={"title": "Validation A", "task_type": "validation"},
                          headers=admin_headers)
    tid = r.json()["id"]
    for h in (qah, qph):
        await client.post("/notifications/read-all", headers=h)

    assert (await client.patch(f"/tasks/{tid}", json={"status": "stuck"},
                               headers=admin_headers)).status_code == 200

    qp_inbox = (await client.get("/notifications", headers=qph)).json()
    assert any(n["task_id"] == tid and n["reason"] == "validation_stuck" for n in qp_inbox)
    qa_inbox = (await client.get("/notifications", headers=qah)).json()
    assert not any(n["task_id"] == tid for n in qa_inbox)


async def test_other_task_types_dont_trigger_canned_rules(client, admin_headers):
    qp, qph = await _actor(client, admin_headers, role="QP")
    r = await client.post("/tasks", json={"title": "Ordinary lab work", "task_type": "lab"},
                          headers=admin_headers)
    tid = r.json()["id"]
    await client.post("/notifications/read-all", headers=qph)
    assert (await client.patch(f"/tasks/{tid}", json={"status": "stuck"},
                               headers=admin_headers)).status_code == 200
    qp_inbox = (await client.get("/notifications", headers=qph)).json()
    assert not any(n["task_id"] == tid for n in qp_inbox)


async def test_capa_review_status_does_not_trigger_the_stuck_rule(client, admin_headers):
    qp, qph = await _actor(client, admin_headers, role="QP")
    r = await client.post("/tasks", json={"title": "CAPA B", "task_type": "capa"},
                          headers=admin_headers)
    tid = r.json()["id"]
    await client.post("/notifications/read-all", headers=qph)
    assert (await client.patch(f"/tasks/{tid}", json={"status": "review"},
                               headers=admin_headers)).status_code == 200
    qp_inbox = (await client.get("/notifications", headers=qph)).json()
    assert not any(n["task_id"] == tid for n in qp_inbox)


async def test_canned_reason_wins_when_recipient_is_also_a_participant(client, admin_headers):
    qp, qph = await _actor(client, admin_headers, role="QP")
    r = await client.post("/tasks", json={"title": "CAPA C", "task_type": "capa"},
                          headers=admin_headers)
    tid = r.json()["id"]
    # the QP is ALSO the assignee — a participant, not just a canned recipient
    assert (await client.post(f"/tasks/{tid}/assignees", json={"user_id": qp["id"]},
                              headers=admin_headers)).status_code == 201
    await client.post("/notifications/read-all", headers=qph)

    assert (await client.patch(f"/tasks/{tid}", json={"status": "stuck"},
                               headers=admin_headers)).status_code == 200

    # The assignment itself is a SEPARATE, earlier event (reason "assigned")
    # and legitimately still shows up — coalescing only collapses repeats of
    # the SAME event, not distinct events on the same task. What this test
    # pins is the status_changed event specifically: emit()'s per-recipient
    # dedup sees the QP once, and because canned recipients are listed first
    # in tasks.py, they get "capa_stuck" rather than the generic "status".
    status_rows = [n for n in (await client.get("/notifications", headers=qph)).json()
                   if n["task_id"] == tid and n["verb"] == "status_changed"]
    assert len(status_rows) == 1
    assert status_rows[0]["reason"] == "capa_stuck"
