"""Cultivation — cultivar master, coded batches, per-plant identity (migration
0045 + app/api/cultivation.py).

Pins the access model (read: every role above USER; write: CU_MGR + executives
+ ADMIN), the identity scheme the owner confirmed (batch code, plant id
`<clone-date>_<cultivar>_<seq>`), the resumable chunked plant fill, and the
audit-lock-safe phase move (batch-level, not per plant).
"""
import uuid
from datetime import date, timedelta

from app.db import tasks_admin_pool, users_admin_pool
from app.security import hash_password
from tests.conftest import create_user, login_and_set_password, purge_org


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


# ── Phase 3: tasks reference the batch they act on (migration 0054) ──────────

async def _seed_cultivation_week(org, on=None):
    """_generate_phase_tasks (app/api/cultivation.py) only fires when the org
    has a code='cultivation' department AND a calendar_weeks row covering the
    transition date — neither exists by default (the `org` fixture seeds only
    the admin profile), same precondition test_tasks.py's own week/department
    tests seed by hand (test_patch_week_id_moves_task_to_a_different_week,
    test_patch_null_clears_department)."""
    on = on or date.today()
    monday = on - timedelta(days=on.weekday())
    sunday = monday + timedelta(days=6)
    await tasks_admin_pool().execute(
        "INSERT INTO departments(org_id, code, name) VALUES ($1,'cultivation','Cultivation')",
        org["org_id"])
    iso = monday.isocalendar()
    await tasks_admin_pool().execute(
        "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on) VALUES"
        " ($1,$2,$3,$4,$5)", org["org_id"], iso[0], iso[1], monday, sunday)


async def test_task_batch_id_round_trips_and_clears(client, admin_headers, org):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_c185", "Flowering 1.6")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP072506",
        "plant_count": 10, "phase": "veg"}, headers=cu_h)
    bid = b.json()["id"]

    r = await client.post("/tasks", json={"title": "Check batch", "status": "pending",
                                          "batch_id": bid}, headers=admin_headers)
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]
    assert r.json()["batch_id"] == bid

    r = await client.get(f"/tasks/{task_id}", headers=admin_headers)
    assert r.json()["task"]["batch_id"] == bid

    # explicit null clears the link (same shape as department_id)
    r = await client.patch(f"/tasks/{task_id}", json={"batch_id": None}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["batch_id"] is None


async def test_task_batch_id_cross_org_rejected_on_create_and_patch(client, admin_headers, org):
    """A real batch id belonging to ANOTHER org must be refused. The bare FK
    alone would accept it — Postgres validates a foreign key against the
    referenced TABLE, not through this session's RLS — so create_task/
    update_task run their own RLS-scoped existence check (see the comment
    beside it in app/api/tasks.py)."""
    other_org_id = uuid.uuid4()
    other_admin_id = uuid.uuid4()
    other_password = "OtherOrgPassword123456"
    other_username = f"other_admin_{other_org_id.hex[:8]}"
    pool = users_admin_pool()
    await pool.execute("INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
                       other_org_id, "Other Org", f"other-{other_org_id.hex[:8]}")
    await pool.execute(
        "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,'ADMIN',false)",
        other_admin_id, other_org_id, other_username, hash_password(other_password), "Other Admin")
    try:
        r = await client.post("/auth/login", json={"email": other_username, "password": other_password})
        assert r.status_code == 200, r.text
        other_h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        room = await _room(client, other_h, "flower_other1", "Other Org Flower")
        cv = await _cultivar(client, other_h, "OO", "Other Org Strain")
        b = await client.post("/cultivation/batches", json={
            "room_id": room["id"], "cultivar_id": cv["id"], "code": "OO072501",
            "plant_count": 5, "phase": "veg"}, headers=other_h)
        assert b.status_code == 201, b.text
        other_batch_id = b.json()["id"]

        r = await client.post("/tasks", json={"title": "Cross-org batch attempt", "status": "pending",
                                              "batch_id": other_batch_id}, headers=admin_headers)
        assert r.status_code == 422, r.text
        assert "batch" in r.json()["detail"].lower()

        mine = await client.post("/tasks", json={"title": "Patch target", "status": "pending"},
                                 headers=admin_headers)
        task_id = mine.json()["id"]
        r = await client.patch(f"/tasks/{task_id}", json={"batch_id": other_batch_id}, headers=admin_headers)
        assert r.status_code == 422, r.text
        assert "batch" in r.json()["detail"].lower()
    finally:
        await purge_org(other_org_id)


async def test_phase_move_generates_task_set_and_is_idempotent(client, admin_headers, org):
    """veg/flower transitions each generate their 3-task template, linked to
    the batch, in the org's cultivation department and the calendar week
    covering the move; revisiting a phase already generated (a correction,
    not the common case) must not duplicate its set."""
    await _seed_cultivation_week(org)
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    veg = await _room(client, admin_headers, "veg_c190", "Vegetation 2", "veg")
    flower = await _room(client, admin_headers, "flower_c190", "Flowering 2.0")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    b = await client.post("/cultivation/batches", json={
        "room_id": veg["id"], "cultivar_id": cv["id"], "code": "GP072510",
        "plant_count": 20, "phase": "clone"}, headers=cu_h)
    bid = b.json()["id"]

    # clone -> veg: generates the veg template
    mv = await client.post(f"/cultivation/batches/{bid}/move",
                           json={"to_phase": "veg"}, headers=cu_h)
    assert mv.status_code == 200, mv.text
    assert len(mv.json()["generated_task_ids"]) == 3

    tl = await client.get(f"/cultivation/batches/{bid}/tasks", headers=cu_h)
    assert tl.status_code == 200, tl.text
    veg_tasks = tl.json()["tasks"]
    assert len(veg_tasks) == 3
    assert {t["phase_gen"] for t in veg_tasks} == {"veg"}
    assert {t["status"] for t in veg_tasks} == {"pending"}
    # each generated task is a real task, reachable and batch-linked through
    # the ordinary task API — not a side record only cultivation.py can see
    one = await client.get(f"/tasks/{veg_tasks[0]['id']}", headers=admin_headers)
    assert one.json()["task"]["batch_id"] == bid

    # veg -> flower: generates the flower template ON TOP of the veg set
    mv2 = await client.post(f"/cultivation/batches/{bid}/move",
                            json={"to_phase": "flower", "to_room_id": flower["id"]}, headers=cu_h)
    assert len(mv2.json()["generated_task_ids"]) == 3
    tl2 = await client.get(f"/cultivation/batches/{bid}/tasks", headers=cu_h)
    assert len(tl2.json()["tasks"]) == 6

    # a correction back to veg then forward to flower again must NOT generate
    # a second flower set — idempotent per (batch, phase), not per visit
    await client.post(f"/cultivation/batches/{bid}/move", json={"to_phase": "veg"}, headers=cu_h)
    mv3 = await client.post(f"/cultivation/batches/{bid}/move", json={"to_phase": "flower"}, headers=cu_h)
    assert mv3.status_code == 200, mv3.text
    assert mv3.json()["generated_task_ids"] == []
    tl3 = await client.get(f"/cultivation/batches/{bid}/tasks", headers=cu_h)
    assert len(tl3.json()["tasks"]) == 6


async def test_phase_with_no_template_generates_nothing(client, admin_headers, org):
    await _seed_cultivation_week(org)
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "nursery_c191", "Nursery 1", "nursery")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP072511",
        "plant_count": 5, "phase": "clone"}, headers=cu_h)
    bid = b.json()["id"]

    mv = await client.post(f"/cultivation/batches/{bid}/move",
                           json={"to_phase": "nursery"}, headers=cu_h)
    assert mv.status_code == 200, mv.text
    assert mv.json()["generated_task_ids"] == []
    tl = await client.get(f"/cultivation/batches/{bid}/tasks", headers=cu_h)
    assert tl.json()["tasks"] == []
