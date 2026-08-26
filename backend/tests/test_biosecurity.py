"""Biosecurity events (migration 0053 + app/api/biosecurity.py) — the four §5c
record types (AHU filter, disinfection mat, contact plate/sentinel bioassay,
gowning), one table discriminated by `kind`.

Pins the one real invariant the migration header names: a `fail` or
`below_spec` result cannot be recorded without a stated `action_taken` — a
below-spec mat or a positive plate that nobody responded to is the exact §27
gap this record exists to close.

Org isolation is not re-tested here: test_rls_coverage enumerates every public
table and fails on any without RLS, so biosecurity_events is covered the moment
the migration lands.
"""
from app.worktime import facility_today
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


async def _event(client, headers, kind, **over):
    body = {"kind": kind}
    body.update(over)
    return await client.post("/decon/biosecurity", json=body, headers=headers)


# ── access ───────────────────────────────────────────────────────────────────

async def test_read_gating_and_both_writer_sets(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")

    assert (await client.get("/decon/biosecurity", headers=user_h)).status_code == 403
    assert (await client.get("/decon/biosecurity", headers=qc_h)).status_code == 200

    # a different manager (QC) is not a recorder for this board
    denied = await _event(client, qc_h, "ahu_filter", subject="AHU-3", result="pass")
    assert denied.status_code == 403

    # cultivation crew records a filter pull...
    ok_cu = await _event(client, cu_h, "ahu_filter", subject="AHU-3", result="pass")
    assert ok_cu.status_code == 201, ok_cu.text
    # ...and QA records a contact-plate read — both are recorders on this board.
    ok_qa = await _event(client, qa_h, "contact_plate", subject="Cure room bench",
                         measure_value=0, measure_unit="CFU", result="pass")
    assert ok_qa.status_code == 201, ok_qa.text


async def test_unknown_kind_and_result_are_refused_with_a_named_422(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    bad_kind = await _event(client, cu_h, "footbath")
    assert bad_kind.status_code == 422
    assert "kind" in bad_kind.json()["detail"].lower()

    bad_result = await _event(client, cu_h, "gowning", result="maybe")
    assert bad_result.status_code == 422
    assert "result" in bad_result.json()["detail"].lower()


# ── the one invariant ────────────────────────────────────────────────────────

async def test_a_failing_result_is_refused_without_a_stated_action(client, admin_headers):
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")

    no_action = await _event(client, qa_h, "contact_plate", subject="Dry room A",
                             result="fail")
    assert no_action.status_code == 422
    assert "action" in no_action.json()["detail"].lower()

    blank_action = await _event(client, qa_h, "disinfection_mat", subject="Mat 2",
                                result="below_spec", action_taken="   ")
    assert blank_action.status_code == 422

    ok = await _event(client, qa_h, "contact_plate", subject="Dry room A",
                      result="fail", action_taken="Re-swabbed, room quarantined pending recheck")
    assert ok.status_code == 201, ok.text
    assert ok.json()["result"] == "fail"
    assert "quarantined" in ok.json()["action_taken"]


async def test_pass_and_pending_need_no_action(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await _event(client, cu_h, "ahu_filter", subject="AHU-1",
                         result="pass")).status_code == 201
    assert (await _event(client, cu_h, "sentinel_bioassay", subject="Sentinel plate 4",
                         result="pending")).status_code == 201
    # no result at all (e.g. a plate placed but not yet read) is also fine
    assert (await _event(client, cu_h, "contact_plate",
                         subject="Cure bench 2")).status_code == 201


# ── resolving a pending result (PATCH .../result) ───────────────────────────

async def test_pending_event_can_be_resolved_and_fail_still_requires_action(
        client, admin_headers):
    """A contact plate is plated now, read days later after incubation — before
    this endpoint nothing could ever move a `pending` record to a final
    result. And resolving to fail/below_spec through this path must be gated
    exactly like POST is: no action_taken, no fail."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")

    plated = await _event(client, cu_h, "contact_plate", subject="Cure bench 3",
                          result="pending")
    assert plated.status_code == 201
    eid = plated.json()["id"]

    # a different manager (QC) is not a recorder on this board — same gate as POST
    denied = await client.patch(f"/decon/biosecurity/{eid}/result",
                                json={"result": "pass"}, headers=qc_h)
    assert denied.status_code == 403

    # resolving to fail with no action_taken is refused, same as POST
    no_action = await client.patch(f"/decon/biosecurity/{eid}/result",
                                   json={"result": "fail"}, headers=cu_h)
    assert no_action.status_code == 422
    assert "action" in no_action.json()["detail"].lower()

    # ...and below_spec with a blank action_taken is refused too
    blank_action = await client.patch(f"/decon/biosecurity/{eid}/result",
                                      json={"result": "below_spec", "action_taken": "   "},
                                      headers=cu_h)
    assert blank_action.status_code == 422

    # resolving back to "pending" is not a valid final result
    still_pending = await client.patch(f"/decon/biosecurity/{eid}/result",
                                       json={"result": "pending"}, headers=cu_h)
    assert still_pending.status_code == 422

    resolved = await client.patch(f"/decon/biosecurity/{eid}/result",
                                  json={"result": "fail",
                                        "action_taken": "Plate re-read, room flagged"},
                                  headers=cu_h)
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["result"] == "fail"
    assert "flagged" in resolved.json()["action_taken"]

    # a pass needs no action_taken and can resolve a different pending event
    plated2 = await _event(client, cu_h, "sentinel_bioassay", subject="Sentinel plate 9",
                           result="pending")
    eid2 = plated2.json()["id"]
    passed = await client.patch(f"/decon/biosecurity/{eid2}/result",
                                json={"result": "pass"}, headers=cu_h)
    assert passed.status_code == 200
    assert passed.json()["result"] == "pass"

    # an unknown event id is a clean 404
    missing = await client.patch(
        "/decon/biosecurity/00000000-0000-0000-0000-000000000000/result",
        json={"result": "pass"}, headers=cu_h)
    assert missing.status_code == 404


# ── room is optional but validated when given ───────────────────────────────

async def test_room_is_optional_but_must_exist_when_given(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")

    # gowning / zone-crossing has no natural room in every case — must succeed
    # without one.
    no_room = await _event(client, cu_h, "gowning", subject="J. Doe entering flower zone",
                           result="pass")
    assert no_room.status_code == 201, no_room.text
    assert no_room.json()["room_id"] is None

    ghost = await _event(client, cu_h, "ahu_filter",
                         room_id="00000000-0000-0000-0000-000000000000")
    assert ghost.status_code == 422


async def test_defaults_to_today_and_filters_by_kind_room_and_open(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "bio_r", "Flowering BR")

    with_default_date = await _event(client, cu_h, "ahu_filter", room_id=room["id"],
                                     subject="AHU-9", result="pass")
    assert with_default_date.status_code == 201, with_default_date.text
    assert with_default_date.json()["occurred_on"] == facility_today().isoformat()

    failing = await _event(client, cu_h, "disinfection_mat", room_id=room["id"],
                           subject="Mat entrance", result="below_spec",
                           action_taken="Bleach topped up and re-verified")
    assert failing.status_code == 201, failing.text

    by_kind = (await client.get("/decon/biosecurity?kind=ahu_filter",
                                headers=cu_h)).json()["events"]
    assert all(e["kind"] == "ahu_filter" for e in by_kind)
    assert any(e["subject"] == "AHU-9" for e in by_kind)

    by_room = (await client.get(f"/decon/biosecurity?room_id={room['id']}",
                                headers=cu_h)).json()["events"]
    assert len(by_room) == 2

    open_only = (await client.get("/decon/biosecurity?open_only=true",
                                  headers=cu_h)).json()["events"]
    assert all(e["result"] in ("fail", "below_spec") for e in open_only)
    assert any(e["subject"] == "Mat entrance" for e in open_only)
