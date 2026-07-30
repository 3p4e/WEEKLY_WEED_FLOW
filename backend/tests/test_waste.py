"""Destruction / waste manifests — the reconciliation record (migration 0048 +
app/api/waste.py).

Pins the four gates and the reconciliation invariant, because destruction is the
one phase transition where the material stops being auditable afterwards: an
empty seal, a post-seal edit, a self-witnessed load, a disposal recorded on an
unwitnessed load, and an over-declared batch each produce a record that looks
complete and is not. Every one of them is a refusal here, not a warning.

Org isolation is NOT re-tested here on purpose: test_rls_coverage enumerates
every public table and fails on any without RLS enabled, so the two new tables
are covered the moment the migration lands, and test_rls pins the cross-org API
behaviour once for the whole app. A third copy of that scaffolding would drift.
"""
import asyncio

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


async def _cultivar(client, headers, code, name):
    r = await client.post("/cultivation/cultivars", json={"code": code, "name": name},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _batch(client, headers, room_id, cultivar_id, code, plant_count):
    r = await client.post("/cultivation/batches", json={
        "room_id": room_id, "cultivar_id": cultivar_id, "code": code,
        "plant_count": plant_count, "phase": "flower"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _manifest(client, headers, code, **over):
    body = {"manifest_code": code, "waste_type": "plant_material",
            "reason": "hlvd_eradication", "campaign": "hlvd-2026-07"}
    body.update(over)
    r = await client.post("/waste/manifests", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_read_gating_and_writer_roles(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")

    assert (await client.get("/waste/manifests", headers=user_h)).status_code == 403
    assert (await client.get("/waste/manifests", headers=qc_h)).status_code == 200

    # Recording a manifest is a cultivation-crew action; QC is a different manager.
    assert (await client.post("/waste/manifests", json={
        "manifest_code": "WM-QC", "waste_type": "plant_material",
        "reason": "hlvd_eradication"}, headers=qc_h)).status_code == 403
    m = await _manifest(client, cu_h, "WM-001")
    assert m["status"] == "draft"


async def test_duplicate_manifest_code_is_a_clean_409(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    await _manifest(client, cu_h, "WM-DUP")
    again = await client.post("/waste/manifests", json={
        "manifest_code": "WM-DUP", "waste_type": "trim",
        "reason": "routine_cull"}, headers=cu_h)
    assert again.status_code == 409
    assert "already exists" in again.json()["detail"]


async def test_an_empty_manifest_cannot_be_sealed(client, admin_headers):
    """Gate 1 — a sealed manifest with no lines asserts nothing while looking
    complete."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    m = await _manifest(client, cu_h, "WM-EMPTY")
    seal = await client.post(f"/waste/manifests/{m['id']}/seal",
                             json={"gross_weight_kg": 1200.5}, headers=cu_h)
    assert seal.status_code == 409
    assert "empty manifest" in seal.json()["detail"]


async def test_a_line_must_quantify_something(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    m = await _manifest(client, cu_h, "WM-NOQTY")
    r = await client.post(f"/waste/manifests/{m['id']}/lines",
                          json={"note": "some material"}, headers=cu_h)
    assert r.status_code == 422
    assert "plant count or a weight" in r.json()["detail"]


async def test_sealed_manifest_refuses_line_add_and_delete(client, admin_headers):
    """Gate 2 — sealing is what makes the witness's signature mean something."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    m = await _manifest(client, cu_h, "WM-FROZEN")
    add = await client.post(f"/waste/manifests/{m['id']}/lines",
                            json={"weight_kg": 800}, headers=cu_h)
    assert add.status_code == 201
    line_id = add.json()["id"]

    seal = await client.post(f"/waste/manifests/{m['id']}/seal",
                             json={"gross_weight_kg": 800}, headers=cu_h)
    assert seal.status_code == 200
    assert seal.json()["status"] == "sealed"

    after = await client.post(f"/waste/manifests/{m['id']}/lines",
                              json={"weight_kg": 5}, headers=cu_h)
    assert after.status_code == 409
    assert "sealed" in after.json()["detail"]

    rm = await client.delete(f"/waste/manifests/{m['id']}/lines/{line_id}", headers=cu_h)
    assert rm.status_code == 409

    # And the line is still there — the refusal was not a silent partial delete.
    detail = (await client.get(f"/waste/manifests/{m['id']}", headers=cu_h)).json()
    assert len(detail["lines"]) == 1


async def test_a_draft_line_can_be_removed(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    m = await _manifest(client, cu_h, "WM-DRAFTEDIT")
    add = await client.post(f"/waste/manifests/{m['id']}/lines",
                            json={"weight_kg": 40}, headers=cu_h)
    line_id = add.json()["id"]
    rm = await client.delete(f"/waste/manifests/{m['id']}/lines/{line_id}", headers=cu_h)
    assert rm.status_code == 200
    detail = (await client.get(f"/waste/manifests/{m['id']}", headers=cu_h)).json()
    assert detail["lines"] == []


async def test_the_weigher_cannot_witness_their_own_load(client, admin_headers):
    """Gate 3 — the two-person rule is the entire point of a witness, so it holds
    even for a role that is allowed to do both."""
    # An executive is in BOTH the recorder and the witness set, which is exactly
    # the case a role check alone would wave through.
    _, coo_h = await _actor(client, admin_headers, "COO")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    m = await _manifest(client, coo_h, "WM-SELF")
    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"weight_kg": 950}, headers=coo_h)
    await client.post(f"/waste/manifests/{m['id']}/seal",
                      json={"gross_weight_kg": 950}, headers=coo_h)

    self_witness = await client.post(f"/waste/manifests/{m['id']}/witness",
                                     json={}, headers=coo_h)
    assert self_witness.status_code == 409
    assert "cannot also witness" in self_witness.json()["detail"]

    other = await client.post(f"/waste/manifests/{m['id']}/witness", json={}, headers=qa_h)
    assert other.status_code == 200
    assert other.json()["status"] == "witnessed"


async def test_a_draft_load_cannot_be_witnessed_and_witnessing_is_once(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    m = await _manifest(client, cu_h, "WM-ORDER")

    early = await client.post(f"/waste/manifests/{m['id']}/witness", json={}, headers=qa_h)
    assert early.status_code == 409
    assert "not sealed" in early.json()["detail"]

    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"weight_kg": 10}, headers=cu_h)
    await client.post(f"/waste/manifests/{m['id']}/seal",
                      json={"gross_weight_kg": 10}, headers=cu_h)
    assert (await client.post(f"/waste/manifests/{m['id']}/witness",
                              json={}, headers=qa_h)).status_code == 200
    twice = await client.post(f"/waste/manifests/{m['id']}/witness", json={}, headers=qa_h)
    assert twice.status_code == 409
    assert "already witnessed" in twice.json()["detail"]


async def test_the_cultivation_crew_cannot_witness(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    m = await _manifest(client, cu_h, "WM-NOTQA")
    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"weight_kg": 10}, headers=cu_h)
    await client.post(f"/waste/manifests/{m['id']}/seal",
                      json={"gross_weight_kg": 10}, headers=cu_h)
    assert (await client.post(f"/waste/manifests/{m['id']}/witness",
                              json={}, headers=cu_h)).status_code == 403


async def test_disposal_requires_a_witnessed_load(client, admin_headers):
    """Gate 4 — the carrier reference closes a chain that has to exist first."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    m = await _manifest(client, cu_h, "WM-CHAIN")
    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"weight_kg": 2100}, headers=cu_h)

    on_draft = await client.post(f"/waste/manifests/{m['id']}/dispose",
                                 json={"carrier_ref": "X-1"}, headers=cu_h)
    assert on_draft.status_code == 409
    assert "must be witnessed" in on_draft.json()["detail"]

    await client.post(f"/waste/manifests/{m['id']}/seal",
                      json={"gross_weight_kg": 2100}, headers=cu_h)
    on_sealed = await client.post(f"/waste/manifests/{m['id']}/dispose",
                                  json={"carrier_ref": "X-1"}, headers=cu_h)
    assert on_sealed.status_code == 409

    await client.post(f"/waste/manifests/{m['id']}/witness", json={}, headers=qa_h)
    done = await client.post(f"/waste/manifests/{m['id']}/dispose",
                             json={"carrier_ref": "CARRIER-2026-0731-004",
                                   "carrier_name": "Licensed incinerator"}, headers=cu_h)
    assert done.status_code == 200
    assert done.json()["status"] == "disposed"
    assert done.json()["carrier_ref"] == "CARRIER-2026-0731-004"

    detail = (await client.get(f"/waste/manifests/{m['id']}", headers=cu_h)).json()
    assert detail["carrier_name"] == "Licensed incinerator"
    # Every rung of the ladder carries its own evidence.
    for field in ("sealed_at", "weighed_at", "witnessed_at", "disposed_at"):
        assert detail[field] is not None, field
    assert detail["weighed_by"] != detail["witnessed_by"]


async def test_a_blank_carrier_reference_is_refused_server_side(client, admin_headers):
    """The UI blocks this too, but the UI is never the gate: Pydantic accepts ""
    for a plain str, so without min_length a 'disposed' manifest could assert
    nothing at all."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    m = await _manifest(client, cu_h, "WM-BLANKREF")
    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"weight_kg": 5}, headers=cu_h)
    await client.post(f"/waste/manifests/{m['id']}/seal",
                      json={"gross_weight_kg": 5}, headers=cu_h)
    await client.post(f"/waste/manifests/{m['id']}/witness", json={}, headers=qa_h)

    empty = await client.post(f"/waste/manifests/{m['id']}/dispose",
                              json={"carrier_ref": ""}, headers=cu_h)
    assert empty.status_code == 422
    blank = await client.post(f"/waste/manifests/{m['id']}/dispose",
                              json={"carrier_ref": "   "}, headers=cu_h)
    assert blank.status_code == 422, "whitespace-only asserts as little as empty"

    ok = await client.post(f"/waste/manifests/{m['id']}/dispose",
                           json={"carrier_ref": "  C-77  "}, headers=cu_h)
    assert ok.status_code == 200
    assert ok.json()["carrier_ref"] == "C-77", "the stored reference is stripped"


async def test_over_declaring_a_batch_is_refused_across_manifests(client, admin_headers):
    """The reconciliation invariant. Over-declaring is not a harmless typo — it is
    the arithmetic that stops the register balancing."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c180_w", "Flowering 1.1")
    cv = await _cultivar(client, cu_h, "Bisamber", "Bisamber")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP072501", 100)

    m1 = await _manifest(client, cu_h, "WM-R1")
    first = await client.post(f"/waste/manifests/{m1['id']}/lines",
                              json={"batch_id": b["id"], "plant_qty": 60}, headers=cu_h)
    assert first.status_code == 201

    # A single line that alone exceeds what is left.
    too_many = await client.post(f"/waste/manifests/{m1['id']}/lines",
                                 json={"batch_id": b["id"], "plant_qty": 50}, headers=cu_h)
    assert too_many.status_code == 409
    assert "over-declare" in too_many.json()["detail"]

    # And the sum is counted across manifests, not just within one.
    m2 = await _manifest(client, cu_h, "WM-R2")
    across = await client.post(f"/waste/manifests/{m2['id']}/lines",
                               json={"batch_id": b["id"], "plant_qty": 41}, headers=cu_h)
    assert across.status_code == 409
    exact = await client.post(f"/waste/manifests/{m2['id']}/lines",
                              json={"batch_id": b["id"], "plant_qty": 40}, headers=cu_h)
    assert exact.status_code == 201, "declaring exactly the remainder must be allowed"


async def test_concurrent_lines_on_different_manifests_do_not_jointly_over_declare(
        client, admin_headers):
    """The reconciliation invariant is checked per add_line call, so two lines
    for the SAME batch on two DIFFERENT manifests never see each other's write
    unless something serializes them — add_line took no lock at all before this
    fix. Sequential calls (the test above) only prove the arithmetic; this
    fires two real concurrent requests (asyncio.gather) against a batch that
    only has room for one of the two lines to be accepted."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c183_w", "Flowering 1.4")
    cv = await _cultivar(client, cu_h, "RaceLines", "Race Lines")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP072503", 10)
    m1 = await _manifest(client, cu_h, "WM-RACEL1")
    m2 = await _manifest(client, cu_h, "WM-RACEL2")

    r1, r2 = await asyncio.gather(
        client.post(f"/waste/manifests/{m1['id']}/lines",
                    json={"batch_id": b["id"], "plant_qty": 6}, headers=cu_h),
        client.post(f"/waste/manifests/{m2['id']}/lines",
                    json={"batch_id": b["id"], "plant_qty": 6}, headers=cu_h))

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 409], (
        "two concurrent lines that jointly exceed the batch (6+6 > 10) on"
        f" DIFFERENT manifests must resolve to exactly one success, got {statuses}")

    total = 0
    for man in (m1, m2):
        detail = (await client.get(f"/waste/manifests/{man['id']}", headers=cu_h)).json()
        total += sum(l["plant_qty"] or 0 for l in detail["lines"])
    assert total == 6, "exactly the winning request's 6 plants may be recorded"


async def test_a_batch_line_inherits_the_batch_room(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c181_w", "Flowering 1.2")
    cv = await _cultivar(client, cu_h, "Bisamber2", "Bisamber 2")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP072502", 10)
    m = await _manifest(client, cu_h, "WM-ROOM")
    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"batch_id": b["id"], "plant_qty": 10}, headers=cu_h)
    detail = (await client.get(f"/waste/manifests/{m['id']}", headers=cu_h)).json()
    assert detail["lines"][0]["room_id"] == room["id"]
    assert detail["lines"][0]["batch_code"] == "GP072502"


async def test_reconciliation_reports_unaccounted_and_unmanifested_destruction(client, admin_headers):
    """The join neither module can see alone: a batch closed as destroyed in
    cultivation with nothing ever manifested."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    room = await _room(client, admin_headers, "c182_w", "Flowering 1.3")
    cv = await _cultivar(client, cu_h, "Recon", "Recon")

    partly = await _batch(client, cu_h, room["id"], cv["id"], "GP-PART", 100)
    ghost = await _batch(client, cu_h, room["id"], cv["id"], "GP-GHOST", 50)

    m = await _manifest(client, cu_h, "WM-RECON")
    await client.post(f"/waste/manifests/{m['id']}/lines",
                      json={"batch_id": partly["id"], "plant_qty": 30}, headers=cu_h)

    # The ghost batch is closed as destroyed in cultivation, with no manifest.
    closed = await client.post(f"/cultivation/batches/{ghost['id']}/move",
                               json={"to_phase": "destroyed", "reason": "HLVd cull"},
                               headers=cu_h)
    assert closed.status_code == 200

    rec = (await client.get("/waste/reconciliation", headers=qa_h)).json()["batches"]
    by_code = {r["code"]: r for r in rec}

    assert by_code["GP-PART"]["declared_destroyed"] == 30
    assert by_code["GP-PART"]["unaccounted"] == 70
    assert by_code["GP-PART"]["unmanifested_destruction"] is False
    assert by_code["GP-PART"]["over_declared"] is False
    # Declared but not yet disposed — the manifest is still a draft.
    assert by_code["GP-PART"]["disposed_destroyed"] == 0

    assert by_code["GP-GHOST"]["phase"] == "destroyed"
    assert by_code["GP-GHOST"]["declared_destroyed"] == 0
    assert by_code["GP-GHOST"]["unmanifested_destruction"] is True, \
        "a batch closed as destroyed with nothing manifested is the discrepancy this report exists for"

    # Once the manifest reaches 'disposed' the disposed column follows.
    await client.post(f"/waste/manifests/{m['id']}/seal",
                      json={"gross_weight_kg": 300}, headers=cu_h)
    await client.post(f"/waste/manifests/{m['id']}/witness", json={}, headers=qa_h)
    await client.post(f"/waste/manifests/{m['id']}/dispose",
                      json={"carrier_ref": "C-1"}, headers=cu_h)
    rec2 = (await client.get("/waste/reconciliation", headers=qa_h)).json()["batches"]
    assert {r["code"]: r for r in rec2}["GP-PART"]["disposed_destroyed"] == 30


async def test_enumerations_are_rejected_with_a_named_list(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    bad_type = await client.post("/waste/manifests", json={
        "manifest_code": "WM-BAD1", "waste_type": "sludge",
        "reason": "hlvd_eradication"}, headers=cu_h)
    assert bad_type.status_code == 422
    assert "plant_material" in bad_type.json()["detail"]

    bad_reason = await client.post("/waste/manifests", json={
        "manifest_code": "WM-BAD2", "waste_type": "trim",
        "reason": "because"}, headers=cu_h)
    assert bad_reason.status_code == 422
    assert "hlvd_eradication" in bad_reason.json()["detail"]

    bad_filter = await client.get("/waste/manifests?status=shredded", headers=cu_h)
    assert bad_filter.status_code == 422
