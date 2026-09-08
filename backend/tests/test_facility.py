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


async def test_read_gating_and_a_departmentless_manager_opens_no_room(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/facility", headers=user_h)).status_code == 403
    assert (await client.get("/facility", headers=qc_h)).status_code == 200
    # rooms belong to the department that runs them — and this cultivation
    # manager has no department, so there is nothing for a room to belong to.
    # (A manager WITH a department opens their own rooms: see the tests below.)
    r = await client.post("/facility/rooms", json={"code": "x1", "name": "X", "kind": "veg"},
                          headers=cu_h)
    assert r.status_code == 403
    assert "department" in r.json()["detail"].lower()
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


# ── rooms belong to the department that runs them (migration 0064) ────────────

async def _department(org, code, name, parent_id=None):
    from app.db import tasks_admin_pool
    return str(await tasks_admin_pool().fetchval(
        "INSERT INTO departments(org_id, code, name, parent_id) VALUES ($1,$2,$3,$4) RETURNING id",
        org["org_id"], code, name, parent_id))


async def _dept_actor(client, admin_headers, role, dept_id):
    u, otp = await create_user(client, admin_headers, role=role, department_id=dept_id)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def test_a_department_manager_opens_the_rooms_their_department_runs(client, admin_headers, org):
    """The gate that made the cultivation manager unable to place a batch: a
    batch REQUIRES a room and only ADMIN could open one. Now cultivation opens
    the rooms it grows in and production opens its dry rooms — each within its
    own kinds, and the room is theirs."""
    cu_d = await _department(org, "cultivation", "Cultivation")
    pr_d = await _department(org, "production", "Production")
    _, cu_h = await _dept_actor(client, admin_headers, "CU_MGR", cu_d)
    _, pr_h = await _dept_actor(client, admin_headers, "PR_MGR", pr_d)

    r = await client.post("/facility/rooms", json={"code": "clone_1", "name": "Clone 1", "kind": "clone"},
                          headers=cu_h)
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "clone"
    assert r.json()["department_id"] == cu_d, "a room a manager opens is their department's"
    # …but a dry room is production's, whoever asks
    assert (await client.post("/facility/rooms", json={"code": "dry_x", "name": "Dry X", "kind": "dry"},
                              headers=cu_h)).status_code == 403

    ok = await client.post("/facility/rooms", json={"code": "dry_1", "name": "Dry 1", "kind": "dry"},
                           headers=pr_h)
    assert ok.status_code == 201, ok.text
    assert ok.json()["department_id"] == pr_d
    assert (await client.post("/facility/rooms", json={"code": "veg_x", "name": "Veg X", "kind": "veg"},
                              headers=pr_h)).status_code == 403


async def test_a_manager_cannot_place_a_room_in_another_department(client, admin_headers, org):
    cu_d = await _department(org, "cultivation", "Cultivation")
    pr_d = await _department(org, "production", "Production")
    _, cu_h = await _dept_actor(client, admin_headers, "CU_MGR", cu_d)
    r = await client.post("/facility/rooms", json={"code": "veg_2", "name": "Veg 2", "kind": "veg",
                                                   "department_id": pr_d}, headers=cu_h)
    assert r.status_code == 403


async def test_a_manager_may_place_a_room_in_a_sub_department_they_run(client, admin_headers, org):
    """Cloning is a sub-department of Cultivation; its clone rooms are the
    cultivation manager's to open."""
    cu_d = await _department(org, "cultivation", "Cultivation")
    cl_d = await _department(org, "cloning", "Cloning", parent_id=cu_d)
    _, cu_h = await _dept_actor(client, admin_headers, "CU_MGR", cu_d)
    r = await client.post("/facility/rooms", json={"code": "clone_2", "name": "Clone 2", "kind": "clone",
                                                   "department_id": cl_d}, headers=cu_h)
    assert r.status_code == 201, r.text
    assert r.json()["department_id"] == cl_d


async def test_executives_open_any_room_and_may_leave_it_unassigned(client, admin_headers):
    _, owner_h = await _actor(client, admin_headers, "OWNER")
    r = await client.post("/facility/rooms", json={"code": "dry_o", "name": "Dry O", "kind": "dry"},
                          headers=owner_h)
    assert r.status_code == 201, r.text
    assert r.json()["department_id"] is None


async def test_editing_keeps_a_room_within_its_department_and_kind(client, admin_headers, org):
    cu_d = await _department(org, "cultivation", "Cultivation")
    _, cu_h = await _dept_actor(client, admin_headers, "CU_MGR", cu_d)

    # Every room that predates 0064 is unassigned. One of the manager's own
    # KIND stays editable by them — the alternative is that nobody but ADMIN
    # can touch any existing room — but editing it does not claim it…
    legacy = await _room(client, admin_headers, "legacy_veg", "Legacy Veg", kind="veg")
    assert legacy["department_id"] is None
    assert (await client.patch(f"/facility/rooms/{legacy['id']}", json={"name": "Veg A"},
                               headers=cu_h)).status_code == 200
    rooms = {r["code"]: r for r in (await client.get("/facility", headers=cu_h)).json()["rooms"]}
    assert rooms["legacy_veg"]["department_id"] is None
    # …and it cannot be retyped into another department's kind
    assert (await client.patch(f"/facility/rooms/{legacy['id']}", json={"kind": "dry"},
                               headers=cu_h)).status_code == 403
    # a room of another department's kind is not theirs to touch at all
    dry = await _room(client, admin_headers, "dry_l", "Dry L", kind="dry")
    assert (await client.patch(f"/facility/rooms/{dry['id']}", json={"name": "x"},
                               headers=cu_h)).status_code == 403
    # and a manager cannot unassign their own room so that anyone of that
    # kind could edit it next — only an administrator may
    mine = (await client.post("/facility/rooms", json={"code": "veg_m", "name": "Veg M", "kind": "veg"},
                              headers=cu_h)).json()
    assert (await client.patch(f"/facility/rooms/{mine['id']}", json={"department_id": None},
                               headers=cu_h)).status_code == 403
    assert (await client.patch(f"/facility/rooms/{mine['id']}", json={"department_id": None},
                               headers=admin_headers)).status_code == 200


async def test_managers_outside_the_floor_are_refused_at_the_route(client, admin_headers):
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post("/facility/rooms", json={"code": "qc_room", "name": "QC"},
                              headers=qc_h)).status_code == 403


async def test_the_board_carries_each_rooms_department(client, admin_headers, org):
    cu_d = await _department(org, "cultivation", "Cultivation")
    _, cu_h = await _dept_actor(client, admin_headers, "CU_MGR", cu_d)
    assert (await client.post("/facility/rooms", json={"code": "veg_b", "name": "Veg B", "kind": "veg"},
                              headers=cu_h)).status_code == 201
    rooms = (await client.get("/facility", headers=cu_h)).json()["rooms"]
    assert {r["code"]: r["department_id"] for r in rooms}["veg_b"] == cu_d
