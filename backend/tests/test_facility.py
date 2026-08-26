"""Facility board — rooms + a READ-ONLY view of plant batches (migration 0015).

Batch management (create/move/close) lives exclusively in cultivation.py —
POST/PATCH /facility/batches were removed (see app/api/facility.py's module
docstring): they were a second, independent write path over the same
`plant_batches` row cultivation.py owns, with a narrower phase vocabulary
that crashed GET /facility outright the moment a batch sat in a phase
(`nursery`) this file's own totals loop didn't know about.

Pins the access model (read: every role above USER; rooms: ADMIN-only,
idempotent), that batches created through cultivation.py show up correctly
on this board including the full phase vocabulary, and — the regression
this rewrite exists for — that GET /facility never 500s regardless of which
phase a live batch is in.
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


async def _cultivar(client, headers, code, name):
    r = await client.post("/cultivation/cultivars",
                          json={"code": code, "name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _batch(client, headers, room, cv, code, plant_count, phase):
    r = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": code,
        "plant_count": plant_count, "phase": phase}, headers=headers)
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


async def test_batches_created_via_cultivation_appear_on_the_board(client, admin_headers):
    """The board is read-only, but it must still reflect reality: a batch
    opened and moved through the real (cultivation.py) write path shows up
    here, with correct per-room and per-phase totals, and disappears once it
    reaches a terminal phase — exactly like the old facility-write-path
    tests asserted, just seeded through the endpoint that's now authoritative."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    nursery = await _room(client, admin_headers, "nursery_t", "Nursery T", "nursery")
    grow = await _room(client, admin_headers, "grow_t2", "Grow T2")
    cv = await _cultivar(client, cu_h, "GG", "Gorilla Glue")
    b = await _batch(client, cu_h, nursery, cv, "GP072501", 48, "clone")
    bid = b["id"]
    assert b["phase_since"] == facility_today().isoformat()

    board = (await client.get("/facility", headers=cu_h)).json()
    nroom = next(r for r in board["rooms"] if r["id"] == nursery["id"])
    assert nroom["plant_total"] == 48
    assert board["totals"]["clone"] >= 48

    # move to the grow room + flowering
    mv = await client.post(f"/cultivation/batches/{bid}/move", json={
        "to_phase": "flower", "to_room_id": grow["id"]}, headers=cu_h)
    assert mv.status_code == 200, mv.text
    board = (await client.get("/facility", headers=cu_h)).json()
    groom = next(r for r in board["rooms"] if r["id"] == grow["id"])
    assert groom["plant_total"] == 48
    assert next(r for r in board["rooms"] if r["id"] == nursery["id"])["plant_total"] == 0

    # a terminal move (harvested) removes it from the board entirely
    hv = await client.post(f"/cultivation/batches/{bid}/move",
                           json={"to_phase": "harvested"}, headers=cu_h)
    assert hv.status_code == 200 and hv.json()["is_active"] is False
    board = (await client.get("/facility", headers=cu_h)).json()
    assert next(r for r in board["rooms"] if r["id"] == grow["id"])["plant_total"] == 0


async def test_facility_totals_never_500_across_the_full_phase_vocabulary(client, admin_headers):
    """H-CRIT regression: GET /facility used to build its totals dict from a
    hardcoded 5-phase tuple narrower than cultivation.py's real 8-phase
    vocabulary — an active batch sitting in 'nursery' raised an unhandled
    KeyError and took the whole board down for every reader in the org.
    Seed a batch in every non-terminal phase (including nursery) plus one
    that reaches a terminal phase, and confirm the board still renders and
    totals correctly."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "allphase_room", "All-Phase Room", "nursery")
    cv = await _cultivar(client, cu_h, "AP", "All Phase")

    non_terminal = ["nursery", "clone", "veg", "flower", "mother", "drying"]
    batches = {}
    for i, phase in enumerate(non_terminal):
        b = await _batch(client, cu_h, room, cv, f"AP07250{i}", 10, "clone")
        if phase != "clone":
            mv = await client.post(f"/cultivation/batches/{b['id']}/move",
                                   json={"to_phase": phase}, headers=cu_h)
            assert mv.status_code == 200, mv.text
        batches[phase] = b["id"]

    # one more batch that actually reaches a terminal phase (harvested) — it
    # must be correctly excluded from the still-active board, not crash it.
    term = await _batch(client, cu_h, room, cv, "AP072509", 7, "clone")
    hv = await client.post(f"/cultivation/batches/{term['id']}/move",
                           json={"to_phase": "harvested"}, headers=cu_h)
    assert hv.status_code == 200, hv.text

    r = await client.get("/facility", headers=cu_h)
    assert r.status_code == 200, r.text
    totals = r.json()["totals"]
    for phase in non_terminal:
        assert totals.get(phase, 0) >= 10, f"phase {phase} missing/short in totals: {totals}"
    assert "harvested" not in totals   # terminal batch correctly excluded, not just zeroed
    assert totals["total"] >= 10 * len(non_terminal)


async def test_batch_write_endpoints_are_gone(client, admin_headers):
    """POST/PATCH /facility/batches were retired — batch management lives
    only at /cultivation/batches now. Lock the retirement in so it can't
    silently come back as an independent write path."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "grow_t3", "Grow T3")
    assert (await client.post("/facility/batches", json={
        "room_id": room["id"], "strain": "X", "plant_count": 1, "phase": "veg"},
        headers=cu_h)).status_code in (404, 405)
    assert (await client.patch("/facility/batches/00000000-0000-0000-0000-000000000000",
                               json={"plant_count": 2}, headers=cu_h)).status_code in (404, 405)


async def test_cultivation_batch_changes_feed_the_activity_stream(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "grow_t4", "Grow T4")
    cv = await _cultivar(client, cu_h, "NL", "Northern Lights")
    b = await _batch(client, cu_h, room, cv, "GP072504", 12, "veg")
    feed = (await client.get("/activity", headers=admin_headers)).json()
    ev = next(e for e in feed if e["verb"] == "batch_added" and e["object_id"] == b["id"])
    assert ev["params"]["cultivar"] == "NL"
    # ...and nobody was inbox-notified (feed-only by design)
    inbox = (await client.get("/notifications", headers=admin_headers)).json()
    assert not any(n.get("object_id") == b["id"] for n in inbox)


async def test_malformed_room_id_rejected_not_500(client, admin_headers):
    """H11: a garbage (non-uuid) room_id used to reach asyncpg raw and 500
    instead of the clean error every sibling bad-id path returns."""
    garbage = "not-a-uuid"
    assert (await client.patch(f"/facility/rooms/{garbage}", json={"name": "x"},
                               headers=admin_headers)).status_code == 404
