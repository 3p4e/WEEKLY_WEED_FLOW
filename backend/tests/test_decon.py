"""Decontamination campaign — per-room signed cycle, bleach log, swab gate
(migration 0046 + app/api/decon.py).

Pins the two gates the CEO's HLVd eradication plan insists on: steps must be
signed IN ORDER with rinse1_whitecloth passing before bleach is accepted (a
soiled cloth reopens the wash, it does not let bleach through), and a room is
released only against a complete signed cycle with every swab negative — a
pending or positive swab blocks it outright, and only QA may release.
"""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def _room(client, admin_headers, code, name, kind="flower"):
    r = await client.post("/facility/rooms",
                          json={"code": code, "name": name, "kind": kind},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _cycle(client, headers, room_id, campaign="hlvd-2026-07"):
    r = await client.post("/decon/cycles",
                          json={"room_id": room_id, "campaign": campaign}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_read_gating_and_writer_roles(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")

    assert (await client.get("/decon/cycles", headers=user_h)).status_code == 403
    assert (await client.get("/decon/cycles", headers=qc_h)).status_code == 200

    room = await _room(client, admin_headers, "c185_t", "Flowering 1.6")
    # cleaning-crew action gated to CU_MGR-and-up; QC (a different manager) is not one
    assert (await client.post("/decon/cycles", json={"room_id": room["id"], "campaign": "x"},
                              headers=qc_h)).status_code == 403
    cyc = await _cycle(client, cu_h, room["id"])
    assert cyc["status"] == "in_progress"

    # swab recording is a QA function; the cultivation manager may not record one
    assert (await client.post("/decon/swabs", json={
        "room_id": room["id"], "cycle_id": cyc["id"], "swab_code": "RR-01-001"},
        headers=cu_h)).status_code == 403
    assert (await client.post("/decon/swabs", json={
        "room_id": room["id"], "cycle_id": cyc["id"], "swab_code": "RR-01-001"},
        headers=qa_h)).status_code == 201


async def test_steps_must_be_signed_in_order(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c184_t", "Flowering 1.5")
    cyc = await _cycle(client, cu_h, room["id"])

    # bleach before dry_clean/wash/rinse1 is rejected
    skip = await client.post(f"/decon/cycles/{cyc['id']}/steps",
                             json={"step": "bleach"}, headers=cu_h)
    assert skip.status_code == 409

    ok1 = await client.post(f"/decon/cycles/{cyc['id']}/steps",
                            json={"step": "dry_clean"}, headers=cu_h)
    assert ok1.status_code == 201
    ok2 = await client.post(f"/decon/cycles/{cyc['id']}/steps",
                            json={"step": "detergent_wash"}, headers=cu_h)
    assert ok2.status_code == 201

    # bleach still rejected: rinse1_whitecloth has not been recorded at all
    still_skip = await client.post(f"/decon/cycles/{cyc['id']}/steps",
                                   json={"step": "bleach"}, headers=cu_h)
    assert still_skip.status_code == 409


async def test_soiled_white_cloth_blocks_bleach_until_re_washed(client, admin_headers):
    """The exact rule from the plan: "Soiled cloth -> wash again; the bleach
    does not go on." A failed white-cloth check must not be a dead end — it
    reopens detergent_wash, and only a PASSING rinse1 lets bleach through."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c183_t", "Flowering 1.4")
    cyc = await _cycle(client, cu_h, room["id"])
    cid = cyc["id"]

    await client.post(f"/decon/cycles/{cid}/steps", json={"step": "dry_clean"}, headers=cu_h)
    await client.post(f"/decon/cycles/{cid}/steps", json={"step": "detergent_wash"}, headers=cu_h)

    failed = await client.post(f"/decon/cycles/{cid}/steps",
                               json={"step": "rinse1_whitecloth", "passed": False,
                                     "note": "soiled, wash again"}, headers=cu_h)
    assert failed.status_code == 201 and failed.json()["passed"] is False

    # bleach must still be rejected — the gate has not passed
    blocked = await client.post(f"/decon/cycles/{cid}/steps",
                                json={"step": "bleach"}, headers=cu_h)
    assert blocked.status_code == 409
    assert "does not go on" in blocked.json()["detail"]

    # wash again, then a PASSING white-cloth check
    await client.post(f"/decon/cycles/{cid}/steps", json={"step": "detergent_wash"}, headers=cu_h)
    passed = await client.post(f"/decon/cycles/{cid}/steps",
                              json={"step": "rinse1_whitecloth", "passed": True}, headers=cu_h)
    assert passed.status_code == 201 and passed.json()["passed"] is True

    # now bleach + rinse2 are accepted, and the cycle completes
    ok = await client.post(f"/decon/cycles/{cid}/steps", json={"step": "bleach"}, headers=cu_h)
    assert ok.status_code == 201 and ok.json()["cycle_complete"] is False
    last = await client.post(f"/decon/cycles/{cid}/steps", json={"step": "rinse2"}, headers=cu_h)
    assert last.status_code == 201 and last.json()["cycle_complete"] is True

    cyc_after = (await client.get(f"/decon/cycles/{cid}", headers=cu_h)).json()
    assert cyc_after["status"] == "awaiting_verification"
    assert cyc_after["steps"]["rinse1_whitecloth"]["passed"] is True


async def _run_full_cycle(client, cu_h, room_id, campaign="hlvd-2026-07"):
    cyc = await _cycle(client, cu_h, room_id, campaign)
    cid = cyc["id"]
    for step in ("dry_clean", "detergent_wash"):
        await client.post(f"/decon/cycles/{cid}/steps", json={"step": step}, headers=cu_h)
    await client.post(f"/decon/cycles/{cid}/steps",
                      json={"step": "rinse1_whitecloth", "passed": True}, headers=cu_h)
    for step in ("bleach", "rinse2"):
        await client.post(f"/decon/cycles/{cid}/steps", json={"step": step}, headers=cu_h)
    return cid


async def test_release_requires_complete_cycle_and_all_negative_swabs(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    room = await _room(client, admin_headers, "c182_t", "Flowering 1.3")
    cid = await _run_full_cycle(client, cu_h, room["id"])

    # release with NO swabs on file at all is refused — never on zero verification
    none_yet = await client.post(f"/decon/cycles/{cid}/release", json={}, headers=qa_h)
    assert none_yet.status_code == 409
    assert "zero verification" in none_yet.json()["detail"]

    swab = await client.post("/decon/swabs", json={
        "room_id": room["id"], "cycle_id": cid, "swab_code": "RR-01-100"}, headers=qa_h)
    sid = swab.json()["id"]

    # a PENDING swab blocks release outright
    pending = await client.post(f"/decon/cycles/{cid}/release", json={}, headers=qa_h)
    assert pending.status_code == 409
    assert "pending=1" in pending.json()["detail"]

    # a POSITIVE result blocks release too — never on a pending or bad result
    await client.patch(f"/decon/swabs/{sid}/result",
                       json={"result": "positive", "ct_value": 28.4}, headers=qa_h)
    positive = await client.post(f"/decon/cycles/{cid}/release", json={}, headers=qa_h)
    assert positive.status_code == 409
    assert "positive=1" in positive.json()["detail"]

    # only once it comes back negative does release succeed
    await client.patch(f"/decon/swabs/{sid}/result", json={"result": "negative"}, headers=qa_h)
    released = await client.post(f"/decon/cycles/{cid}/release",
                                 json={"release_note": "signed off"}, headers=qa_h)
    assert released.status_code == 200
    assert released.json()["status"] == "released"

    # released is terminal — no further steps or a second release
    again = await client.post(f"/decon/cycles/{cid}/release", json={}, headers=qa_h)
    assert again.status_code == 409


async def test_only_qa_can_release_not_the_cleaning_crew(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c181_t", "Flowering 1.2")
    cid = await _run_full_cycle(client, cu_h, room["id"])
    denied = await client.post(f"/decon/cycles/{cid}/release", json={}, headers=cu_h)
    assert denied.status_code == 403


async def test_bleach_log_records_ppm_and_flags_below_spec(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c180_t", "Flowering 1.1")
    good = await client.post("/decon/bleach-log", json={
        "room_id": room["id"], "ppm_strip_reading": 5000}, headers=cu_h)
    assert good.status_code == 201 and good.json()["ppm_strip_reading"] == 5000

    weak = await client.post("/decon/bleach-log", json={
        "room_id": room["id"], "ppm_strip_reading": 400,
        "note": "unbriefed housekeeping strength"}, headers=cu_h)
    assert weak.status_code == 201   # logged, not rejected — the plan's #1 risk is
                                     # visible in the log, not silently blocked

    log = (await client.get("/decon/bleach-log", params={"room_id": room["id"]},
                            headers=cu_h)).json()
    assert len(log["entries"]) == 2
    readings = {e["ppm_strip_reading"] for e in log["entries"]}
    assert readings == {5000, 400}


async def test_duplicate_swab_code_rejected(client, admin_headers):
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    room = await _room(client, admin_headers, "c150_t", "Quarantine", "other")
    payload = {"room_id": room["id"], "swab_code": "RR-88-001"}
    assert (await client.post("/decon/swabs", json=payload, headers=qa_h)).status_code == 201
    dup = await client.post("/decon/swabs", json=payload, headers=qa_h)
    assert dup.status_code == 409


async def test_cannot_start_a_second_open_cycle_on_the_same_room_and_campaign(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c179_t", "Vegetation 2", "veg")
    await _cycle(client, cu_h, room["id"], campaign="hlvd-2026-07")
    dup = await client.post("/decon/cycles",
                            json={"room_id": room["id"], "campaign": "hlvd-2026-07"},
                            headers=cu_h)
    assert dup.status_code == 409
    # a DIFFERENT campaign is fine — the open-cycle guard is scoped per campaign
    other = await client.post("/decon/cycles",
                              json={"room_id": room["id"], "campaign": "hlvd-2026-08-restart"},
                              headers=cu_h)
    assert other.status_code == 201
