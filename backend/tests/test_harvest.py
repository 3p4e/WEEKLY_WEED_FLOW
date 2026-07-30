"""Harvest / yield and the IPM applications it blocks on (migration 0051 +
app/api/harvest.py).

Pins the five gates, the genealogy edge, and the two things about the pre-harvest
interval that are easy to get subtly wrong and impossible to notice afterwards:

  - a PHI block is released by QA authority and NOT by the person recording the
    cut, so a recorder cannot clear their own block;
  - a room-scoped application is resolved against the batch's room ON THE
    APPLICATION DATE, so a batch that moved INTO a treated room afterwards is not
    retroactively restricted and one that moved OUT still carries the interval.

Org isolation is not re-tested here: test_rls_coverage enumerates every public
table and fails on any without RLS, so both new tables are covered the moment the
migration lands, and test_rls pins the cross-org API behaviour once for the app.
"""
from datetime import date, timedelta

from app.db import tasks_admin_pool
from tests.conftest import create_user, login_and_set_password


def _at(days_ago: int) -> str:
    """An application timestamp at 10:00 UTC `days_ago` days back.

    Midday-UTC on purpose: `(applied_at AT TIME ZONE <site>)::date` is what the
    PHI arithmetic counts from, and 10:00 UTC lands on the same calendar date in
    any plausible site timezone. A test that used `now()` would flip its own
    expected dates for a few hours every evening."""
    return (date.today() - timedelta(days=days_ago)).isoformat() + "T10:00:00+00:00"


def _days(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


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


async def _batch(client, headers, room_id, cultivar_id, code, plant_count, **over):
    body = {"room_id": room_id, "cultivar_id": cultivar_id, "code": code,
            "plant_count": plant_count, "phase": "flower"}
    body.update(over)
    r = await client.post("/cultivation/batches", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _harvest(client, headers, batch_id, lot, plants, wet, **over):
    body = {"batch_id": batch_id, "lot_code": lot, "plants_harvested": plants,
            "wet_weight_g": wet}
    body.update(over)
    return await client.post("/cultivation/harvests", json=body, headers=headers)


# ── access ───────────────────────────────────────────────────────────────────

async def test_read_gating_and_writer_roles(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")

    assert (await client.get("/cultivation/harvests", headers=user_h)).status_code == 403
    assert (await client.get("/cultivation/harvests", headers=qc_h)).status_code == 200
    assert (await client.get("/cultivation/ipm", headers=qc_h)).status_code == 200

    # Recording a spray is a cultivation-crew action; QC is a different manager.
    denied = await client.post("/cultivation/ipm", json={
        "product": "Neem", "category": "botanical", "batch_id": None,
        "room_id": None}, headers=qc_h)
    assert denied.status_code == 403

    room = await _room(client, admin_headers, "c200_h", "Flowering H1")
    ok = await client.post("/cultivation/ipm", json={
        "product": "Neem oil", "category": "botanical", "room_id": room["id"],
        "method": "spray", "rei_hours": 12, "phi_days": 7}, headers=cu_h)
    assert ok.status_code == 201, ok.text
    assert ok.json()["phi_days"] == 7


async def test_qa_can_record_a_cut_but_not_a_yield(client, admin_headers):
    """QA's extra write is exactly one action — creating the harvest that carries
    their PHI release. Recording the yield and closing the lot stay with the
    cultivation crew, so the widened surface is the minimum the control needs."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    room = await _room(client, admin_headers, "c224_h", "Flowering H23")
    cv = await _cultivar(client, cu_h, "QASURF", "QA surface")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-QASURF", 10,
                     phase_since=_days(30))

    cut = await _harvest(client, qa_h, b["id"], "LOT-QASURF", 10, 4000)
    assert cut.status_code == 201, cut.text

    assert (await client.post(f"/cultivation/harvests/{cut.json()['id']}/dry",
                              json={"dry_flower_g": 900}, headers=qa_h)).status_code == 403
    assert (await client.post("/cultivation/ipm", json={
        "product": "Neem", "category": "botanical", "room_id": room["id"]},
        headers=qa_h)).status_code == 403
    assert (await client.post(f"/cultivation/harvests/{cut.json()['id']}/close",
                              json={}, headers=qa_h)).status_code == 403


# ── IPM record ───────────────────────────────────────────────────────────────

async def test_an_application_must_name_a_room_or_a_batch(client, admin_headers):
    """An application scoped to neither cannot feed either control it exists for —
    it would be a diary entry, not a record."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    r = await client.post("/cultivation/ipm", json={
        "product": "Sulphur", "category": "chemical"}, headers=cu_h)
    assert r.status_code == 422
    assert "room or the batch" in r.json()["detail"]


async def test_ipm_enumerations_are_rejected_with_a_named_list(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c201_h", "Flowering H2")
    bad_cat = await client.post("/cultivation/ipm", json={
        "product": "X", "category": "pesticide", "room_id": room["id"]}, headers=cu_h)
    assert bad_cat.status_code == 422
    assert "biological" in bad_cat.json()["detail"]

    bad_method = await client.post("/cultivation/ipm", json={
        "product": "X", "category": "chemical", "method": "sprinkle",
        "room_id": room["id"]}, headers=cu_h)
    assert bad_method.status_code == 422
    assert "drench" in bad_method.json()["detail"]


async def test_re_entry_interval_is_reported_in_hours_not_days(client, admin_headers):
    """REI is the reason applied_at is a timestamp: a room sprayed this morning
    with a 12-hour interval is enterable this evening, which a date column cannot
    express."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c202_h", "Flowering H3")
    await client.post("/cultivation/ipm", json={
        "product": "Spinosad", "category": "biological", "room_id": room["id"],
        "rei_hours": 48, "applied_at": _at(0)}, headers=cu_h)
    await client.post("/cultivation/ipm", json={
        "product": "Old spray", "category": "chemical", "room_id": room["id"],
        "rei_hours": 12, "applied_at": _at(9)}, headers=cu_h)

    apps = (await client.get(f"/cultivation/ipm?room_id={room['id']}",
                             headers=cu_h)).json()["applications"]
    by_product = {a["product"]: a for a in apps}
    assert by_product["Spinosad"]["rei_active"] is True
    assert by_product["Old spray"]["rei_active"] is False, \
        "an interval that elapsed nine days ago is not an active restriction"


# ── gate 1: the pre-harvest interval ─────────────────────────────────────────

async def test_a_batch_inside_a_pre_harvest_interval_cannot_be_cut(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c203_h", "Flowering H4")
    cv = await _cultivar(client, cu_h, "PHI1", "PHI One")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-PHI-1", 100,
                     phase_since=_days(20))

    await client.post("/cultivation/ipm", json={
        "product": "Sulphur dust", "category": "chemical", "room_id": room["id"],
        "phi_days": 14, "applied_at": _at(3)}, headers=cu_h)

    clearance = (await client.get(f"/cultivation/harvest-clearance/{b['id']}",
                                  headers=cu_h)).json()
    assert clearance["clear"] is False
    assert len(clearance["blocking"]) == 1
    block = clearance["blocking"][0]
    assert block["product"] == "Sulphur dust"
    assert block["scope"] == "room"
    assert block["days_remaining"] == 11
    assert block["phi_clear_on"] == (date.today() + timedelta(days=11)).isoformat()

    cut = await _harvest(client, cu_h, b["id"], "LOT-PHI-1", 100, 50000)
    assert cut.status_code == 409
    detail = cut.json()["detail"]
    assert "pre-harvest interval" in detail
    assert "14-day PHI" in detail
    assert "11 day(s)" in detail


async def test_an_elapsed_interval_does_not_block(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c204_h", "Flowering H5")
    cv = await _cultivar(client, cu_h, "PHI2", "PHI Two")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-PHI-2", 20,
                     phase_since=_days(30))
    await client.post("/cultivation/ipm", json={
        "product": "Neem", "category": "botanical", "room_id": room["id"],
        "phi_days": 7, "applied_at": _at(20)}, headers=cu_h)

    clearance = (await client.get(f"/cultivation/harvest-clearance/{b['id']}",
                                  headers=cu_h)).json()
    assert clearance["clear"] is True
    assert clearance["blocking"] == []

    cut = await _harvest(client, cu_h, b["id"], "LOT-PHI-2", 20, 9000)
    assert cut.status_code == 201, cut.text


async def test_the_interval_boundary_is_the_clear_date_itself(client, admin_headers):
    """An interval that clears TODAY is clear today — a 7-day PHI applied 7 days
    ago has elapsed, it does not run to the eighth. The off-by-one here is the
    kind that survives every test that only checks "long ago" and "just now", so
    it is pinned at exactly the boundary and one day either side.

    This also pins the site-zone arithmetic: the clear date is computed from
    `applied_at` rendered in the facility zone, and `today` is resolved by
    Postgres in the same zone, so the two cannot be a day apart."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c225_h", "Flowering H24")
    cv = await _cultivar(client, cu_h, "BOUND", "Boundary")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-BOUND", 30,
                     phase_since=_days(40))

    # Clears today: applied 7 days ago with a 7-day PHI.
    await client.post("/cultivation/ipm", json={
        "product": "Clears today", "category": "chemical", "room_id": room["id"],
        "phi_days": 7, "applied_at": _at(7)}, headers=cu_h)
    today = (await client.get(f"/cultivation/harvest-clearance/{b['id']}",
                              headers=cu_h)).json()
    assert today["clear"] is True, "a 7-day interval applied 7 days ago has elapsed"

    # Clears tomorrow: applied 7 days ago with an 8-day PHI.
    await client.post("/cultivation/ipm", json={
        "product": "Clears tomorrow", "category": "chemical", "room_id": room["id"],
        "phi_days": 8, "applied_at": _at(7)}, headers=cu_h)
    tomorrow = (await client.get(f"/cultivation/harvest-clearance/{b['id']}",
                                 headers=cu_h)).json()
    assert tomorrow["clear"] is False
    assert [x["product"] for x in tomorrow["blocking"]] == ["Clears tomorrow"], \
        "only the outstanding interval blocks; the elapsed one is not reported"
    assert tomorrow["blocking"][0]["days_remaining"] == 1

    # And the `on` parameter moves the question, not just the answer's label.
    ahead = (await client.get(
        f"/cultivation/harvest-clearance/{b['id']}"
        f"?on={(date.today() + timedelta(days=1)).isoformat()}", headers=cu_h)).json()
    assert ahead["clear"] is True, "asking about tomorrow must answer about tomorrow"


async def test_an_application_with_no_declared_phi_does_not_block(client, admin_headers):
    """NULL phi_days means "no interval declared", which is a different statement
    from zero — and neither of them is a block."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c205_h", "Flowering H6")
    cv = await _cultivar(client, cu_h, "PHI3", "PHI Three")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-PHI-3", 10,
                     phase_since=_days(30))
    await client.post("/cultivation/ipm", json={
        "product": "Predatory mites", "category": "biological", "method": "release",
        "room_id": room["id"], "applied_at": _at(0)}, headers=cu_h)

    assert (await client.get(f"/cultivation/harvest-clearance/{b['id']}",
                             headers=cu_h)).json()["clear"] is True
    assert (await _harvest(client, cu_h, b["id"], "LOT-PHI-3", 10, 4000)).status_code == 201


async def test_the_recorder_cannot_clear_their_own_phi_block(client, admin_headers):
    """The override is a QA release. If the person recording the cut could wave
    away their own block, the gate would be decoration."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    room = await _room(client, admin_headers, "c206_h", "Flowering H7")
    cv = await _cultivar(client, cu_h, "PHI4", "PHI Four")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-PHI-4", 10,
                     phase_since=_days(30))
    await client.post("/cultivation/ipm", json={
        "product": "Sulphur", "category": "chemical", "room_id": room["id"],
        "phi_days": 21, "applied_at": _at(1)}, headers=cu_h)

    by_recorder = await _harvest(client, cu_h, b["id"], "LOT-PHI-4", 10, 4000,
                                 phi_override_reason="the plants look fine")
    assert by_recorder.status_code == 403
    assert "QA decision" in by_recorder.json()["detail"]

    by_qa = await _harvest(client, qa_h, b["id"], "LOT-PHI-4", 10, 4000,
                           phi_override_reason="residue screen clear, ref QA-2026-114")
    assert by_qa.status_code == 201, by_qa.text
    assert by_qa.json()["phi_override"] is True

    lot = (await client.get(f"/cultivation/harvests/{by_qa.json()['id']}",
                            headers=qa_h)).json()
    # The override is part of the record, not a note: a named person, a stated
    # reason and a time, all three or none (migration 0051's CHECK).
    assert lot["phi_override_at"] is not None
    assert lot["phi_override_by"] is not None
    assert lot["phi_override_reason"] == "residue screen clear, ref QA-2026-114"


async def test_a_blank_override_reason_is_not_an_override(client, admin_headers):
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c207_h", "Flowering H8")
    cv = await _cultivar(client, cu_h, "PHI5", "PHI Five")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-PHI-5", 10,
                     phase_since=_days(30))
    await client.post("/cultivation/ipm", json={
        "product": "Sulphur", "category": "chemical", "room_id": room["id"],
        "phi_days": 21, "applied_at": _at(1)}, headers=cu_h)

    empty = await _harvest(client, qa_h, b["id"], "LOT-PHI-5", 10, 4000,
                           phi_override_reason="")
    assert empty.status_code == 422, "Pydantic accepts '' for a plain str — min_length is the gate"


async def test_room_scope_is_resolved_as_of_the_application_date(client, admin_headers):
    """A room-scoped spray restricts whatever was standing in that room WHEN it
    was sprayed. A batch that moved in afterwards was never treated; one that
    moved out still carries the interval. Resolving against the CURRENT room gets
    both of these backwards."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    treated = await _room(client, admin_headers, "c208_h", "Flowering treated")
    clean = await _room(client, admin_headers, "c209_h", "Flowering clean")
    cv = await _cultivar(client, cu_h, "PHI6", "PHI Six")

    # `was_there` was in the treated room when it was sprayed and has since moved
    # out; `came_later` was elsewhere and has since moved in.
    was_there = await _batch(client, cu_h, treated["id"], cv["id"], "GP-WASTHERE", 10,
                             phase_since=_days(20))
    came_later = await _batch(client, cu_h, clean["id"], cv["id"], "GP-CAMELATER", 10,
                              phase_since=_days(20))

    await client.post("/cultivation/ipm", json={
        "product": "Sulphur", "category": "chemical", "room_id": treated["id"],
        "phi_days": 21, "applied_at": _at(5)}, headers=cu_h)

    # Swap the two rooms today, AFTER the application.
    for b, dest in ((was_there, clean), (came_later, treated)):
        moved = await client.post(f"/cultivation/batches/{b['id']}/move",
                                  json={"to_phase": "flower", "to_room_id": dest["id"]},
                                  headers=cu_h)
        assert moved.status_code == 200, moved.text

    left = (await client.get(f"/cultivation/harvest-clearance/{was_there['id']}",
                             headers=cu_h)).json()
    arrived = (await client.get(f"/cultivation/harvest-clearance/{came_later['id']}",
                                headers=cu_h)).json()

    assert left["clear"] is False, "the interval follows the plants out of the room"
    assert arrived["clear"] is True, \
        "moving into a treated room afterwards does not retroactively treat the batch"


async def test_a_batch_scoped_application_blocks_regardless_of_room(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c210_h", "Flowering H9")
    cv = await _cultivar(client, cu_h, "PHI7", "PHI Seven")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-PHI-7", 10,
                     phase_since=_days(20))
    other = await _batch(client, cu_h, room["id"], cv["id"], "GP-PHI-7B", 10,
                         phase_since=_days(20))

    await client.post("/cultivation/ipm", json={
        "product": "Drench", "category": "chemical", "batch_id": b["id"],
        "method": "drench", "phi_days": 10, "applied_at": _at(2)}, headers=cu_h)

    mine = (await client.get(f"/cultivation/harvest-clearance/{b['id']}",
                             headers=cu_h)).json()
    assert mine["clear"] is False
    assert mine["blocking"][0]["scope"] == "batch"
    # The neighbour shares the room but not the treatment.
    neighbour = (await client.get(f"/cultivation/harvest-clearance/{other['id']}",
                                  headers=cu_h)).json()
    assert neighbour["clear"] is True


# ── gate 2: the headcount invariant ──────────────────────────────────────────

async def test_harvesting_more_plants_than_the_batch_holds_is_refused(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c211_h", "Flowering H10")
    cv = await _cultivar(client, cu_h, "HC1", "Headcount One")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-HC-1", 100,
                     phase_since=_days(30))

    assert (await _harvest(client, cu_h, b["id"], "LOT-HC-1a", 60, 30000)).status_code == 201
    over = await _harvest(client, cu_h, b["id"], "LOT-HC-1b", 41, 20000)
    assert over.status_code == 409
    assert "over-declare" in over.json()["detail"]
    exact = await _harvest(client, cu_h, b["id"], "LOT-HC-1c", 40, 20000)
    assert exact.status_code == 201, "cutting exactly the remainder must be allowed"


async def test_harvest_and_destruction_are_counted_against_the_same_batch(client, admin_headers):
    """The two registers must be checked TOGETHER. Each is individually satisfiable
    while the pair is impossible: 100 plants cut into lots and the same 100
    declared destroyed."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c212_h", "Flowering H11")
    cv = await _cultivar(client, cu_h, "HC2", "Headcount Two")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-HC-2", 100,
                     phase_since=_days(30))

    m = await client.post("/waste/manifests", json={
        "manifest_code": "WM-HC-2", "waste_type": "plant_material",
        "reason": "routine_cull"}, headers=cu_h)
    assert m.status_code == 201
    culled = await client.post(f"/waste/manifests/{m.json()['id']}/lines",
                               json={"batch_id": b["id"], "plant_qty": 30}, headers=cu_h)
    assert culled.status_code == 201

    # 30 destroyed + 71 harvested > 100.
    too_many = await _harvest(client, cu_h, b["id"], "LOT-HC-2a", 71, 30000)
    assert too_many.status_code == 409
    assert "declared destroyed" in too_many.json()["detail"]
    ok = await _harvest(client, cu_h, b["id"], "LOT-HC-2b", 70, 30000)
    assert ok.status_code == 201

    # ...and the mirror: the destruction register now sees the harvested plants.
    more_waste = await client.post(f"/waste/manifests/{m.json()['id']}/lines",
                                   json={"batch_id": b["id"], "plant_qty": 1}, headers=cu_h)
    assert more_waste.status_code == 409
    assert "harvested" in more_waste.json()["detail"]


async def test_a_partial_canopy_pull_retires_no_plants(client, admin_headers):
    """0 is a legitimate headcount: taking the tops and leaving the plants standing
    is a real harvest event that must not consume the batch."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c213_h", "Flowering H12")
    cv = await _cultivar(client, cu_h, "HC3", "Headcount Three")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-HC-3", 10,
                     phase_since=_days(30))
    assert (await _harvest(client, cu_h, b["id"], "LOT-HC-3a", 0, 2000)).status_code == 201
    assert (await _harvest(client, cu_h, b["id"], "LOT-HC-3b", 10, 6000)).status_code == 201


# ── gate 5 + identity ────────────────────────────────────────────────────────

async def test_a_closed_batch_cannot_be_harvested(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c214_h", "Flowering H13")
    cv = await _cultivar(client, cu_h, "TERM", "Terminal")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-TERM", 10,
                     phase_since=_days(30))
    await client.post(f"/cultivation/batches/{b['id']}/move",
                      json={"to_phase": "harvested"}, headers=cu_h)
    late = await _harvest(client, cu_h, b["id"], "LOT-TERM", 10, 4000)
    assert late.status_code == 409
    assert "after the final pull" in late.json()["detail"]


async def test_lot_code_collisions_are_refused(client, admin_headers):
    """A lot code that is already a node in the genealogy would fuse two different
    physical things into one traceability node."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c215_h", "Flowering H14")
    cv = await _cultivar(client, cu_h, "COL", "Collide")
    a = await _batch(client, cu_h, room["id"], cv["id"], "GP-COL-A", 50,
                     phase_since=_days(30))
    other = await _batch(client, cu_h, room["id"], cv["id"], "GP-COL-B", 50,
                         phase_since=_days(30))

    same_as_batch = await _harvest(client, cu_h, a["id"], "GP-COL-A", 10, 4000)
    assert same_as_batch.status_code == 422
    assert "differ from the batch code" in same_as_batch.json()["detail"]

    another_batch_code = await _harvest(client, cu_h, a["id"], "GP-COL-B", 10, 4000)
    assert another_batch_code.status_code == 409
    assert "already used" in another_batch_code.json()["detail"]

    assert (await _harvest(client, cu_h, a["id"], "LOT-COL", 10, 4000)).status_code == 201
    dup = await _harvest(client, cu_h, other["id"], "LOT-COL", 10, 4000)
    assert dup.status_code == 409
    assert "already exists" in dup.json()["detail"]


async def test_an_uncoded_batch_cannot_produce_a_lot(client, admin_headers):
    """Silently skipping the genealogy edge would leave a harvest that looks linked
    and is not, which is worse than refusing."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c216_h", "Flowering H15")
    cv = await _cultivar(client, cu_h, "NOCODE", "No code")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-NOCODE", 10,
                     phase_since=_days(30))
    # Legacy shape: a batch predating migration 0045's `code` column.
    await tasks_admin_pool().execute(
        "UPDATE plant_batches SET code=NULL WHERE id=$1::uuid", b["id"])

    r = await _harvest(client, cu_h, b["id"], "LOT-NOCODE", 10, 4000)
    assert r.status_code == 422
    assert "no batch code" in r.json()["detail"]


async def test_a_harvest_writes_the_cultivation_genealogy_edge(client, admin_headers):
    """The whole reason this record exists: qc_batch_genealogy has carried a
    CULTIVATION relation since migration 0036 with nothing upstream producing the
    identifier for it."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    room = await _room(client, admin_headers, "c217_h", "Flowering H16")
    cv = await _cultivar(client, cu_h, "GEN", "Genealogy")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-GEN", 40,
                     phase_since=_days(30))

    r = await _harvest(client, cu_h, b["id"], "LOT-GEN-01", 40, 26000)
    assert r.status_code == 201, r.text
    assert r.json()["genealogy_edge"] == {
        "parent_batch_id": "GP-GEN", "child_batch_id": "LOT-GEN-01",
        "relation": "CULTIVATION"}

    lineage = (await client.get("/qc/genealogy/LOT-GEN-01", headers=qc_h)).json()
    assert [p["parent_batch_id"] for p in lineage["parents"]] == ["GP-GEN"]
    assert lineage["parents"][0]["relation"] == "CULTIVATION"
    assert lineage["parents"][0]["unit"] == "g"
    assert [a["batch_id"] for a in lineage["ancestors"]] == ["GP-GEN"]

    down = (await client.get("/qc/genealogy/GP-GEN", headers=qc_h)).json()
    assert [d["batch_id"] for d in down["descendants"]] == ["LOT-GEN-01"]


# ── gates 3 and 4: the yield itself ──────────────────────────────────────────

async def test_dry_weight_cannot_exceed_wet_weight(client, admin_headers):
    """Nothing gains mass in a dry room."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c218_h", "Flowering H17")
    cv = await _cultivar(client, cu_h, "DRY1", "Dry One")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-DRY-1", 10,
                     phase_since=_days(30))
    h = (await _harvest(client, cu_h, b["id"], "LOT-DRY-1", 10, 5000)).json()

    over = await client.post(f"/cultivation/harvests/{h['id']}/dry",
                             json={"dry_flower_g": 4000, "dry_trim_g": 900,
                                   "dry_waste_g": 200}, headers=cu_h)
    assert over.status_code == 409
    assert "gains mass" in over.json()["detail"]

    ok = await client.post(f"/cultivation/harvests/{h['id']}/dry",
                           json={"dry_flower_g": 900, "dry_trim_g": 150,
                                 "dry_waste_g": 50}, headers=cu_h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "dried"
    assert ok.json()["dry_total_g"] == 1100
    assert ok.json()["moisture_loss_pct"] == 78.0
    assert ok.json()["implausible_loss"] is False


async def test_an_implausible_loss_is_reported_and_not_refused(client, admin_headers):
    """Outside the band means "look at this number", not "this number is wrong".
    A report that cries wolf on ordinary variation gets ignored on the day it is
    right."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c219_h", "Flowering H18")
    cv = await _cultivar(client, cu_h, "DRY2", "Dry Two")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-DRY-2", 10,
                     phase_since=_days(30))
    h = (await _harvest(client, cu_h, b["id"], "LOT-DRY-2", 10, 5000)).json()
    r = await client.post(f"/cultivation/harvests/{h['id']}/dry",
                          json={"dry_flower_g": 4500}, headers=cu_h)
    assert r.status_code == 200, "a 10% loss is odd, not forbidden"
    assert r.json()["moisture_loss_pct"] == 10.0
    assert r.json()["implausible_loss"] is True


async def test_a_lot_cannot_be_closed_before_its_yield_is_recorded(client, admin_headers):
    """Gate 4 — a closed record with no yield in it looks finished, which is worse
    than an open one."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c220_h", "Flowering H19")
    cv = await _cultivar(client, cu_h, "CLOSE", "Close")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-CLOSE", 10,
                     phase_since=_days(30))
    h = (await _harvest(client, cu_h, b["id"], "LOT-CLOSE", 10, 5000)).json()

    early = await client.post(f"/cultivation/harvests/{h['id']}/close",
                              json={}, headers=cu_h)
    assert early.status_code == 409
    assert "no dry weight" in early.json()["detail"]

    await client.post(f"/cultivation/harvests/{h['id']}/dry",
                      json={"dry_flower_g": 1100}, headers=cu_h)
    done = await client.post(f"/cultivation/harvests/{h['id']}/close",
                             json={}, headers=cu_h)
    assert done.status_code == 200
    assert done.json()["status"] == "closed"
    assert done.json()["closed_at"] is not None

    twice = await client.post(f"/cultivation/harvests/{h['id']}/close",
                              json={}, headers=cu_h)
    assert twice.status_code == 409
    assert "already closed" in twice.json()["detail"]


async def test_dry_weights_are_correctable_until_the_lot_closes(client, admin_headers):
    """Correcting a mis-keyed weight before the lot closes is ordinary; the
    alternative is a permanent wrong number. After the close it is final."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c221_h", "Flowering H20")
    cv = await _cultivar(client, cu_h, "FIX", "Fix")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-FIX", 10,
                     phase_since=_days(30))
    h = (await _harvest(client, cu_h, b["id"], "LOT-FIX", 10, 5000)).json()

    await client.post(f"/cultivation/harvests/{h['id']}/dry",
                      json={"dry_flower_g": 110}, headers=cu_h)
    fixed = await client.post(f"/cultivation/harvests/{h['id']}/dry",
                              json={"dry_flower_g": 1100}, headers=cu_h)
    assert fixed.status_code == 200
    assert (await client.get(f"/cultivation/harvests/{h['id']}",
                             headers=cu_h)).json()["dry_flower_g"] == 1100

    await client.post(f"/cultivation/harvests/{h['id']}/close", json={}, headers=cu_h)
    after = await client.post(f"/cultivation/harvests/{h['id']}/dry",
                              json={"dry_flower_g": 1200}, headers=cu_h)
    assert after.status_code == 409
    assert "final" in after.json()["detail"]


# ── the yield report ─────────────────────────────────────────────────────────

async def test_yield_report_flags_a_batch_harvested_with_no_lot(client, admin_headers):
    """The mirror of the destruction register's `unmanifested_destruction`:
    cultivation says the crop came off, the yield register says nothing did, and
    there is no lot for a CoA to be issued against."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    room = await _room(client, admin_headers, "c222_h", "Flowering H21")
    cv = await _cultivar(client, cu_h, "YR", "Yield report")

    recorded = await _batch(client, cu_h, room["id"], cv["id"], "GP-YR-OK", 100,
                            phase_since=_days(30))
    ghost = await _batch(client, cu_h, room["id"], cv["id"], "GP-YR-GHOST", 50,
                         phase_since=_days(30))
    live = await _batch(client, cu_h, room["id"], cv["id"], "GP-YR-LIVE", 30,
                        phase_since=_days(30))

    h = (await _harvest(client, cu_h, recorded["id"], "LOT-YR-1", 100, 50000)).json()
    await client.post(f"/cultivation/harvests/{h['id']}/dry",
                      json={"dry_flower_g": 10000, "dry_trim_g": 1500,
                            "dry_waste_g": 500}, headers=cu_h)
    await client.post(f"/cultivation/batches/{recorded['id']}/move",
                      json={"to_phase": "harvested"}, headers=cu_h)
    await client.post(f"/cultivation/batches/{ghost['id']}/move",
                      json={"to_phase": "harvested"}, headers=cu_h)

    rows = (await client.get("/cultivation/yield", headers=qa_h)).json()["batches"]
    by_code = {r["code"]: r for r in rows}

    ok = by_code["GP-YR-OK"]
    assert ok["harvested_without_record"] is False
    assert ok["plants_harvested"] == 100
    assert ok["unaccounted"] == 0
    assert ok["dry_total_g"] == 12000
    assert ok["moisture_loss_pct"] == 76.0
    assert ok["dry_flower_g_per_plant"] == 100.0
    assert ok["lot_count"] == 1 and ok["open_lots"] == 1
    assert ok["over_declared"] is False

    assert by_code["GP-YR-GHOST"]["phase"] == "harvested"
    assert by_code["GP-YR-GHOST"]["harvested_without_record"] is True, \
        "closed as harvested with no lot is the discrepancy this report exists for"

    # A live batch with nothing off it yet is not a discrepancy — its plants are
    # in the room, which is what `unaccounted` says on a non-terminal batch.
    assert by_code["GP-YR-LIVE"]["harvested_without_record"] is False
    assert by_code["GP-YR-LIVE"]["unaccounted"] == 30
    assert by_code["GP-YR-LIVE"]["moisture_loss_pct"] is None


async def test_a_lot_still_drying_does_not_distort_the_batch_loss(client, admin_headers):
    """Only DRIED lots enter the loss calculation. Dividing a partial dry weight by
    the whole wet weight would report a batch mid-dry-down as catastrophic loss."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "c223_h", "Flowering H22")
    cv = await _cultivar(client, cu_h, "MID", "Mid dry")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-MID", 20,
                     phase_since=_days(30))

    done = (await _harvest(client, cu_h, b["id"], "LOT-MID-1", 10, 5000)).json()
    await client.post(f"/cultivation/harvests/{done['id']}/dry",
                      json={"dry_flower_g": 1100}, headers=cu_h)
    # Still wet — its 5000 g must not be counted as a lot that lost everything.
    assert (await _harvest(client, cu_h, b["id"], "LOT-MID-2", 10, 5000)).status_code == 201

    row = {r["code"]: r for r in
           (await client.get("/cultivation/yield", headers=cu_h)).json()["batches"]}["GP-MID"]
    assert row["wet_g"] == 10000, "the wet total covers every lot"
    assert row["moisture_loss_pct"] == 78.0, "but the loss only covers the dried one"
    assert row["open_lots"] == 2


async def test_harvest_filters_are_validated(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/cultivation/harvests?status=soggy",
                             headers=cu_h)).status_code == 422
    assert (await client.get("/cultivation/harvests?batch_id=not-a-uuid",
                             headers=cu_h)).status_code == 422
    assert (await client.get("/cultivation/harvest-clearance/not-a-uuid",
                             headers=cu_h)).status_code == 422
