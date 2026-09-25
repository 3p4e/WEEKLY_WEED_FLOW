"""Irrigation / feeding record (migration 0052 + app/api/irrigation.py).

The last Phase 2 cultivation record. It carries no downstream gate, so what is
worth pinning is the record's own integrity, not an interlock:

  - the write surface (cultivation crew records; a different manager cannot);
  - room is REQUIRED and must exist (a feed with no room is a diary entry);
  - the method vocabulary and the physical ranges (pH 0-14, no negative volume
    or conductivity) are refused with a named 422, never surfaced as a 500;
  - a NULL reading ("not measured") is distinct from 0 and round-trips as null;
  - "today" is the SITE's day, so a feed logged just after local midnight is not
    filed under yesterday.

Org isolation is not re-tested here: test_rls_coverage enumerates every public
table and fails on any without RLS, so irrigation_events is covered the moment
the migration lands.
"""
from datetime import timedelta

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


async def _feed(client, headers, room_id, **over):
    body = {"room_id": room_id}
    body.update(over)
    return await client.post("/cultivation/irrigation", json=body, headers=headers)


# ── access ───────────────────────────────────────────────────────────────────

async def test_read_gating_and_writer_roles(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, ir_h = await _actor(client, admin_headers, "IR_MGR")
    room = await _room(client, admin_headers, "irr_a", "Flowering IA")

    # read: base USER is refused, an elevated manager is allowed
    assert (await client.get("/cultivation/irrigation", headers=user_h)).status_code == 403
    assert (await client.get("/cultivation/irrigation", headers=qc_h)).status_code == 200

    # record: a feed is the IRRIGATION department's record. QC is a different
    # manager — and so, now, is cultivation: irrigation runs the fertigation
    # plant and its distribution to every room as a department of its own,
    # and cultivation reads the record it used to hold the pen for.
    denied = await _feed(client, qc_h, room["id"], water_volume_l=12)
    assert denied.status_code == 403
    assert (await _feed(client, cu_h, room["id"], water_volume_l=12)).status_code == 403

    ok = await _feed(client, ir_h, room["id"], method="drip", water_volume_l=40,
                     feed_ec=1.8, feed_ph=6.1, nutrients="Base A+B, 2ml/L")
    assert ok.status_code == 201, ok.text
    assert ok.json()["feed_ph"] == 6.1
    assert ok.json()["room_name"] == "Flowering IA"


async def test_room_is_required_and_must_exist(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, ir_h = await _actor(client, admin_headers, "IR_MGR")

    # omitted room_id → 422 (Pydantic: no default)
    missing = await client.post("/cultivation/irrigation",
                                json={"water_volume_l": 10}, headers=ir_h)
    assert missing.status_code == 422

    # a well-formed uuid that is not a room → 422 with a named reason
    ghost = await _feed(client, ir_h, "00000000-0000-0000-0000-000000000000")
    assert ghost.status_code == 422
    assert "room" in ghost.json()["detail"].lower()


async def test_method_and_ranges_are_refused_with_a_named_422(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, ir_h = await _actor(client, admin_headers, "IR_MGR")
    room = await _room(client, admin_headers, "irr_r", "Flowering IR")

    bad_method = await _feed(client, ir_h, room["id"], method="sprinkle")
    assert bad_method.status_code == 422
    assert "method" in bad_method.json()["detail"].lower()

    # pH lives on the 0-14 scale; conductivity and volume cannot be negative.
    assert (await _feed(client, ir_h, room["id"], feed_ph=15)).status_code == 422
    assert (await _feed(client, ir_h, room["id"], runoff_ph=-1)).status_code == 422
    assert (await _feed(client, ir_h, room["id"], water_volume_l=-5)).status_code == 422
    assert (await _feed(client, ir_h, room["id"], feed_ec=-0.1)).status_code == 422


async def test_a_null_reading_is_not_zero(client, admin_headers):
    """A plain top-up records only a volume; its EC/pH are 'not measured', which
    must come back as null and never be coerced to 0 (a real, in-range reading)."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, ir_h = await _actor(client, admin_headers, "IR_MGR")
    room = await _room(client, admin_headers, "irr_n", "Flowering IN")
    r = await _feed(client, ir_h, room["id"], water_volume_l=25)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["water_volume_l"] == 25
    assert body["feed_ec"] is None and body["feed_ph"] is None
    assert body["runoff_ec"] is None and body["runoff_ph"] is None


async def test_defaults_to_today_at_the_site(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, ir_h = await _actor(client, admin_headers, "IR_MGR")
    room = await _room(client, admin_headers, "irr_t", "Flowering IT")
    r = await _feed(client, ir_h, room["id"], water_volume_l=10)
    assert r.status_code == 201, r.text
    # facility_today() is the same site-clock function the API resolves against.
    assert r.json()["applied_on"] == facility_today().isoformat()


async def test_batch_scope_is_optional_and_filters_the_list(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, ir_h = await _actor(client, admin_headers, "IR_MGR")
    room = await _room(client, admin_headers, "irr_b", "Flowering IB")
    cv = await _cultivar(client, cu_h, "IRRCV", "Irr cultivar")
    b = await _batch(client, cu_h, room["id"], cv["id"], "GP-IRRCV", 20)

    # one feed scoped to the batch, one room-only
    scoped = await _feed(client, ir_h, room["id"], batch_id=b["id"], water_volume_l=30)
    assert scoped.status_code == 201, scoped.text
    roomonly = await _feed(client, ir_h, room["id"], water_volume_l=5)
    assert roomonly.status_code == 201, roomonly.text

    by_batch = (await client.get(f"/cultivation/irrigation?batch_id={b['id']}",
                                 headers=cu_h)).json()["feeds"]
    assert len(by_batch) == 1
    assert by_batch[0]["batch_id"] == b["id"]
    assert by_batch[0]["batch_code"] == "GP-IRRCV"

    by_room = (await client.get(f"/cultivation/irrigation?room_id={room['id']}",
                                headers=cu_h)).json()["feeds"]
    assert len(by_room) == 2
