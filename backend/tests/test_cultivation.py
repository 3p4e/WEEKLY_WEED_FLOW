"""Cultivation — cultivar master, coded batches, per-plant identity (migration
0045 + app/api/cultivation.py).

Pins the access model (read: every role above USER; write: CU_MGR + executives
+ ADMIN), the identity scheme the owner confirmed (batch code, plant id
`<clone-date>_<cultivar>_<seq>`), the resumable chunked plant fill, and the
audit-lock-safe phase move (batch-level, not per plant).
"""
from datetime import date

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
    r = await client.post("/cultivation/cultivars",
                          json={"code": code, "name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_read_gating_and_cultivar_writers(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")

    # read: base USER blocked, any elevated role allowed
    assert (await client.get("/cultivation/cultivars", headers=user_h)).status_code == 403
    assert (await client.get("/cultivation/cultivars", headers=qc_h)).status_code == 200

    # write: a non-cultivation manager (QC) may not author master data; CU may
    assert (await client.post("/cultivation/cultivars", json={"code": "FB", "name": "Fat Bastard"},
                              headers=qc_h)).status_code == 403
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    assert cv["code"] == "FB"

    # idempotent on (org, code): a second create returns the original untouched
    again = await client.post("/cultivation/cultivars",
                              json={"code": "FB", "name": "renamed"}, headers=cu_h)
    assert again.status_code == 201
    assert again.json()["id"] == cv["id"] and again.json()["name"] == "Fat Bastard"


async def test_batch_create_is_record_only_then_plants_are_materialised(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_c180", "Flowering 1.1")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")

    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP072501",
        "plant_count": 120, "phase": "clone", "clone_date": "2026-07-01"},
        headers=cu_h)
    assert b.status_code == 201, b.text
    bid = b.json()["id"]

    # create records the batch but materialises NO plant rows yet
    lst = (await client.get(f"/cultivation/batches/{bid}/plants", headers=cu_h)).json()
    assert lst["total"] == 0

    # generate: chunked fill brings it to the target
    g = await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)
    assert g.status_code == 200, g.text
    assert g.json()["materialised"] == 120 and g.json()["complete"] is True

    lst = (await client.get(f"/cultivation/batches/{bid}/plants",
                            params={"limit": 5}, headers=cu_h)).json()
    assert lst["total"] == 120
    # plant id shape: <clone-date>_<cultivar>_<seq4>, seq starting at 1
    assert lst["plants"][0]["plant_code"] == "20260701_FB_0001"
    assert lst["plants"][0]["seq"] == 1


async def test_plant_fill_is_resumable_and_idempotent(client, admin_headers):
    """Calling generate again after a complete fill creates nothing, and a fill
    always tops up to the target rather than restarting — the property that
    makes an interrupted chunked fill safe to retry."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_c181", "Flowering 1.2")
    cv = await _cultivar(client, cu_h, "GG", "Gorilla Glue")
    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP072502",
        "plant_count": 75, "phase": "clone"}, headers=cu_h)
    bid = b.json()["id"]

    first = (await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)).json()
    assert first["materialised"] == 75
    second = (await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)).json()
    assert second["created"] == 0 and second["materialised"] == 75 and second["complete"]

    # seqs are contiguous 1..75 with no duplicates (the ON CONFLICT + max(seq)
    # resume guarantees this even across calls)
    allp = (await client.get(f"/cultivation/batches/{bid}/plants",
                             params={"limit": 2000}, headers=cu_h)).json()
    seqs = sorted(p["seq"] for p in allp["plants"])
    assert seqs == list(range(1, 76))


async def test_duplicate_batch_code_rejected(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_c182", "Flowering 1.3")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    payload = {"room_id": room["id"], "cultivar_id": cv["id"], "code": "GP072503",
               "plant_count": 10, "phase": "clone"}
    assert (await client.post("/cultivation/batches", json=payload, headers=cu_h)).status_code == 201
    dup = await client.post("/cultivation/batches", json=payload, headers=cu_h)
    assert dup.status_code == 409


async def test_phase_move_is_batch_level_and_terminal_settles_plants(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    veg = await _room(client, admin_headers, "veg_c178", "Vegetation 1", "veg")
    flower = await _room(client, admin_headers, "flower_c183", "Flowering 1.4")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    b = await client.post("/cultivation/batches", json={
        "room_id": veg["id"], "cultivar_id": cv["id"], "code": "GP072504",
        "plant_count": 30, "phase": "veg"}, headers=cu_h)
    bid = b.json()["id"]
    await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)

    # veg -> flower, into the flowering room: one batch update, plants untouched
    mv = await client.post(f"/cultivation/batches/{bid}/move", json={
        "to_phase": "flower", "to_room_id": flower["id"]}, headers=cu_h)
    assert mv.status_code == 200, mv.text
    assert mv.json()["phase"] == "flower" and mv.json()["is_active"] is True
    active = (await client.get(f"/cultivation/batches/{bid}/plants",
                               params={"status": "active", "limit": 1}, headers=cu_h)).json()
    assert active["total"] == 30   # a move does NOT change plant status

    # flower -> harvested: terminal, closes the batch and settles active plants
    hv = await client.post(f"/cultivation/batches/{bid}/move", json={
        "to_phase": "harvested"}, headers=cu_h)
    assert hv.status_code == 200
    assert hv.json()["phase"] == "harvested" and hv.json()["is_active"] is False
    harv = (await client.get(f"/cultivation/batches/{bid}/plants",
                             params={"status": "harvested", "limit": 1}, headers=cu_h)).json()
    assert harv["total"] == 30

    # a terminal batch cannot move again
    again = await client.post(f"/cultivation/batches/{bid}/move",
                              json={"to_phase": "flower"}, headers=cu_h)
    assert again.status_code == 409


async def test_terminal_start_phase_rejected(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_c184", "Flowering 1.5")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    r = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP072505",
        "plant_count": 10, "phase": "harvested"}, headers=cu_h)
    assert r.status_code == 422
