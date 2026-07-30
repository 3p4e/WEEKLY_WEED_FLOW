"""Facility board — rooms + plant batches (migration 0015).

Pins the access model (read: every role above USER; write: CU_MGR +
executives + ADMIN; rooms: ADMIN-only, idempotent) and the batch lifecycle
(phase-move stamps phase_since, closing removes from the board, totals math).
"""
from datetime import date
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


async def test_read_gating_and_room_admin_only(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/facility", headers=user_h)).status_code == 403
    assert (await client.get("/facility", headers=qc_h)).status_code == 200
    # rooms: ADMIN-only — even the cultivation manager may not alter the registry
    assert (await client.post("/facility/rooms", json={"code": "x1", "name": "X"},
                              headers=cu_h)).status_code == 403
    room = await _room(client, admin_headers, "grow_t1", "Grow T1")
    again = await _room(client, admin_headers, "grow_t1", "Grow T1 renamed")
    assert again["id"] == room["id"]          # idempotent, original untouched
    assert again["name"] == "Grow T1"


async def test_batch_lifecycle_and_totals(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    nursery = await _room(client, admin_headers, "nursery_t", "Nursery T", "nursery")
    grow = await _room(client, admin_headers, "grow_t2", "Grow T2")
    b = await client.post("/facility/batches", json={
        "room_id": nursery["id"], "strain": "Gorilla Glue", "plant_count": 48,
        "phase": "clone"}, headers=cu_h)
    assert b.status_code == 201, b.text
    bid = b.json()["id"]
    assert b.json()["phase_since"] == facility_today().isoformat()

    board = (await client.get("/facility", headers=cu_h)).json()
    nroom = next(r for r in board["rooms"] if r["id"] == nursery["id"])
    assert nroom["plant_total"] == 48
    assert board["totals"]["clone"] >= 48

    # move to the grow room + flowering: phase_since re-stamps automatically
    mv = await client.patch(f"/facility/batches/{bid}", json={
        "room_id": grow["id"], "phase": "flower", "plant_count": 44},
        headers=cu_h)
    assert mv.status_code == 200, mv.text
    assert mv.json()["phase"] == "flower"
    assert mv.json()["phase_since"] == facility_today().isoformat()
    board = (await client.get("/facility", headers=cu_h)).json()
    groom = next(r for r in board["rooms"] if r["id"] == grow["id"])
    assert groom["plant_total"] == 44
    assert next(r for r in board["rooms"] if r["id"] == nursery["id"])["plant_total"] == 0

    # closing removes it from the board
    cl = await client.patch(f"/facility/batches/{bid}", json={"is_active": False},
                            headers=cu_h)
    assert cl.status_code == 200 and cl.json()["is_active"] is False
    board = (await client.get("/facility", headers=cu_h)).json()
    assert next(r for r in board["rooms"] if r["id"] == grow["id"])["plant_total"] == 0


async def test_write_gating_and_validation(client, admin_headers):
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "grow_t3", "Grow T3")
    # a non-cultivation manager reads but may not write
    assert (await client.post("/facility/batches", json={
        "room_id": room["id"], "strain": "X", "plant_count": 1, "phase": "veg"},
        headers=qc_h)).status_code == 403
    # bounds + enums + FK
    assert (await client.post("/facility/batches", json={
        "room_id": room["id"], "strain": "X", "plant_count": -1, "phase": "veg"},
        headers=cu_h)).status_code == 422
    assert (await client.post("/facility/batches", json={
        "room_id": room["id"], "strain": "X", "plant_count": 1, "phase": "sprout"},
        headers=cu_h)).status_code == 422
    assert (await client.post("/facility/batches", json={
        "room_id": "00000000-0000-0000-0000-000000000000", "strain": "X",
        "plant_count": 1, "phase": "veg"}, headers=cu_h)).status_code == 422


async def test_batch_changes_feed_the_activity_stream(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "grow_t4", "Grow T4")
    b = (await client.post("/facility/batches", json={
        "room_id": room["id"], "strain": "Northern Lights", "plant_count": 12,
        "phase": "veg"}, headers=cu_h)).json()
    feed = (await client.get("/activity", headers=admin_headers)).json()
    ev = next(e for e in feed if e["verb"] == "batch_added" and e["object_id"] == b["id"])
    assert ev["params"]["strain"] == "Northern Lights"
    assert ev["params"]["room"] == "Grow T4"
    # ...and nobody was inbox-notified (feed-only by design)
    inbox = (await client.get("/notifications", headers=admin_headers)).json()
    assert not any(n.get("object_id") == b["id"] for n in inbox)


async def test_malformed_ids_rejected_not_500(client, admin_headers):
    """H11: a garbage (non-uuid) room_id/batch_id used to reach asyncpg raw
    and 500 instead of the clean error every sibling bad-id path returns."""
    garbage = "not-a-uuid"
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "grow_badid", "Grow BadId")

    assert (await client.patch(f"/facility/rooms/{garbage}", json={"name": "x"},
                               headers=admin_headers)).status_code == 404
    assert (await client.post("/facility/batches", json={
        "room_id": garbage, "strain": "X", "plant_count": 1, "phase": "veg"},
        headers=cu_h)).status_code == 422
    assert (await client.patch(f"/facility/batches/{garbage}", json={"plant_count": 2},
                               headers=cu_h)).status_code == 404
    b = await client.post("/facility/batches", json={
        "room_id": room["id"], "strain": "X", "plant_count": 1, "phase": "veg"}, headers=cu_h)
    bid = b.json()["id"]
    assert (await client.patch(f"/facility/batches/{bid}", json={"room_id": garbage},
                               headers=cu_h)).status_code == 422


async def test_batch_phase_since_patch_accepts_real_date(client, admin_headers):
    """PATCH /facility/batches/{id} with an explicit phase_since must bind via a
    ::date cast (backdating a phase), not 500 on asyncpg's str→date rejection."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "grow_ps", "Grow PS")
    b = await client.post("/facility/batches", json={
        "room_id": room["id"], "strain": "Backdate Kush", "plant_count": 12,
        "phase": "veg"}, headers=cu_h)
    assert b.status_code == 201, b.text
    bid = b.json()["id"]
    # explicit phase_since, phase unchanged → the value is used verbatim (cast)
    r = await client.patch(f"/facility/batches/{bid}", json={"phase_since": "2026-06-01"}, headers=cu_h)
    assert r.status_code == 200, r.text
    assert r.json()["phase_since"] == "2026-06-01"
