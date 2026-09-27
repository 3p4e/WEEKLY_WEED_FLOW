"""Cultivation — cultivar master, coded batches, per-plant identity (migration
0045 + app/api/cultivation.py).

Pins the access model (read: every role above USER; write: CU_MGR + QA +
executives + ADMIN), the identity scheme the owner confirmed (batch code
<cultivar><MMYY><nn>, legacy plant id `<clone-date>_<batch code>_<seq>`, clone
id `<mother>-<cutting>.<clone>`), the resumable chunked plant fill, the
audit-lock-safe phase move (batch-level, not per plant), the phase path and
who may leave it, and the facility-clock bounds on every recorded date
(review 2026-09-27, CS-01 … CS-18).
"""
import asyncio
import uuid
from datetime import timedelta

from app.db import tasks_admin_pool, users_admin_pool
from app.security import hash_password
from app.worktime import facility_today
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
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")

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
    # plant id shape: <clone-date>_<batch code>_<seq4>, seq starting at 1. The
    # BATCH code, not the cultivar: two batches of one cultivar cloned on the
    # same day must not compute the same ids (CS-02, pinned below).
    assert lst["plants"][0]["plant_code"] == "20260701_GP072501_0001"
    assert lst["plants"][0]["seq"] == 1
    # status_since is the FACILITY day, bound explicitly rather than left to
    # the column's UTC CURRENT_DATE default (CS-14).
    assert lst["plants"][0]["status_since"] == facility_today().isoformat()


async def test_plant_fill_is_resumable_and_idempotent(client, admin_headers):
    """Calling generate again after a complete fill creates nothing, and a fill
    always tops up to the target rather than restarting — the property that
    makes an interrupted chunked fill safe to retry."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "flower_c181", "Flowering 1.2")
    cv = await _cultivar(client, cu_h, "GG", "Gorilla Glue")
    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GG072502",
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
    payload = {"room_id": room["id"], "cultivar_id": cv["id"], "code": "FB072503",
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
        "room_id": veg["id"], "cultivar_id": cv["id"], "code": "FB072504",
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

    # flower -> harvested: terminal, closes the batch and settles active plants.
    # A terminal move needs a stated reason, server-side and not only in the UI
    # (CS-17): a direct call with none — or a blank one — is refused.
    assert (await client.post(f"/cultivation/batches/{bid}/move", json={
        "to_phase": "harvested"}, headers=cu_h)).status_code == 422
    assert (await client.post(f"/cultivation/batches/{bid}/move", json={
        "to_phase": "harvested", "reason": ""}, headers=cu_h)).status_code == 422
    hv = await client.post(f"/cultivation/batches/{bid}/move", json={
        "to_phase": "harvested", "reason": "final pull"}, headers=cu_h)
    assert hv.status_code == 200, hv.text
    assert hv.json()["phase"] == "harvested" and hv.json()["is_active"] is False
    assert hv.json()["plants_settled"] == {"harvested": 30, "destroyed": 0}
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
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "FB072505",
        "plant_count": 10, "phase": "harvested"}, headers=cu_h)
    assert r.status_code == 422


# ── Phase 3: tasks reference the batch they act on (migration 0054) ──────────

async def _seed_cultivation_week(org, on=None):
    """_generate_phase_tasks (app/api/cultivation.py) only fires when the org
    has a code='cultivation' department AND a calendar_weeks row covering the
    transition date — neither exists by default (the `org` fixture seeds only
    the admin profile), same precondition test_tasks.py's own week/department
    tests seed by hand (test_patch_week_id_moves_task_to_a_different_week,
    test_patch_null_clears_department).

    The week MUST be built from facility_today(), never date.today(). The move
    endpoint stamps `body.occurred_on or facility_today()`, so seeding at the
    process zone (UTC in CI and in every container) puts the calendar_weeks row
    in a different week from the one the endpoint then looks up — every night
    between facility-midnight and UTC-midnight. Within a week that is harmless;
    across the Sunday->Monday boundary the two land in entirely different
    weeks, `_generate_phase_tasks` finds no covering row, and correctly
    generates nothing. Failed exactly so at 22:33 UTC on Sunday 2026-08-30 —
    00:33 Monday in Europe/Skopje — seeding Aug 24-30 while the endpoint asked
    for Aug 31. Same defect as CI run 356 (see app/worktime.py and
    tests/test_documents.py); this was the last site of it left in the suite."""
    on = on or facility_today()
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
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "FB072506",
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
    """veg and flower transitions each generate their template — 3 tasks for
    veg, 4 for flower since the trichome maturation check joined it — linked to
    the batch, in the org's cultivation department and the calendar week
    covering the move; revisiting a phase already generated (a correction, not
    the common case) must not duplicate its set."""
    await _seed_cultivation_week(org)
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    veg = await _room(client, admin_headers, "veg_c190", "Vegetation 2", "veg")
    flower = await _room(client, admin_headers, "flower_c190", "Flowering 2.0")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    b = await client.post("/cultivation/batches", json={
        "room_id": veg["id"], "cultivar_id": cv["id"], "code": "FB072510",
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
    assert len(mv2.json()["generated_task_ids"]) == 4
    tl2 = await client.get(f"/cultivation/batches/{bid}/tasks", headers=cu_h)
    flower_tasks = [x for x in tl2.json()["tasks"] if x["phase_gen"] == "flower"]
    assert len(tl2.json()["tasks"]) == 7
    # The owner's rule that the cut is decided by trichome maturation, tracked
    # under a microscope with documented records, is prompted by the template.
    assert any("Trichome maturation check" in x["title"] for x in flower_tasks)

    # a correction back to veg then forward to flower again must NOT generate
    # a second flower set — idempotent per (batch, phase), not per visit. A
    # backward move is a correction of the record: QA authority, with a reason.
    r = await client.post(f"/cultivation/batches/{bid}/move",
                          json={"to_phase": "veg", "reason": "moved a day early"}, headers=qa_h)
    assert r.status_code == 200, r.text
    mv3 = await client.post(f"/cultivation/batches/{bid}/move", json={"to_phase": "flower"}, headers=cu_h)
    assert mv3.status_code == 200, mv3.text
    assert mv3.json()["generated_task_ids"] == []
    tl3 = await client.get(f"/cultivation/batches/{bid}/tasks", headers=cu_h)
    assert len(tl3.json()["tasks"]) == 7


async def test_phase_with_no_template_generates_nothing(client, admin_headers, org):
    await _seed_cultivation_week(org)
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "nursery_c191", "Nursery 1", "nursery")
    cv = await _cultivar(client, cu_h, "FB", "Fat Bastard")
    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "FB072511",
        "plant_count": 5, "phase": "clone"}, headers=cu_h)
    bid = b.json()["id"]

    mv = await client.post(f"/cultivation/batches/{bid}/move",
                           json={"to_phase": "nursery"}, headers=cu_h)
    assert mv.status_code == 200, mv.text
    assert mv.json()["generated_task_ids"] == []
    tl = await client.get(f"/cultivation/batches/{bid}/tasks", headers=cu_h)
    assert tl.json()["tasks"] == []


# ── registering from the product specification (owner, 2026-09-05) ───────────

async def test_qa_registers_a_batch_generates_its_ids_and_moves_it(client, admin_headers):
    """The owner's model, as amended on 2026-09-05: "the QA manager, the CEO
    and COO as well as the cultivation manager can register a batch", and "QA
    should be able to move a batch through its phases or edit the cultivar
    master". QC still registers nothing — it is not a floor role."""
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, ceo_h = await _actor(client, admin_headers, "CEO")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_q", "Clone Q", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    body = {"room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092601",
            "plant_count": 3, "phase": "clone"}
    assert (await client.post("/cultivation/batches", json=body, headers=qc_h)).status_code == 403
    r = await client.post("/cultivation/batches", json=body, headers=qa_h)
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    g = await client.post(f"/cultivation/batches/{bid}/plants", headers=qa_h)
    assert g.status_code == 200 and g.json()["complete"] is True
    r = await client.post(f"/cultivation/batches/{bid}/move", json={"to_phase": "veg"},
                          headers=qa_h)
    assert r.status_code == 200, r.text
    assert r.json()["phase"] == "veg"
    # …and authors the cultivar master, which QC still may not.
    assert (await client.post("/cultivation/cultivars", json={"code": "QA1", "name": "QA Strain"},
                              headers=qa_h)).status_code == 201
    assert (await client.post("/cultivation/cultivars", json={"code": "QC1", "name": "QC Strain"},
                              headers=qc_h)).status_code == 403
    r = await client.post("/cultivation/batches", json={**body, "code": "GP092602"}, headers=ceo_h)
    assert r.status_code == 201, r.text


async def test_cultivars_carry_their_official_products(client, admin_headers):
    """GET /cultivars returns each strain with the official ImB products it is
    grown to — approved first, drafts flagged — so the batch form registers
    from the catalogue rather than from a tier ladder."""
    from tests.test_products import _approved, _product
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    gp = await _cultivar(client, cu_h, "GP", "Grape Pie")
    fb = await _cultivar(client, cu_h, "FB", "Fat Bastard")

    by_code = {c["code"]: c for c in
               (await client.get("/cultivation/cultivars", headers=cu_h)).json()["cultivars"]}
    assert by_code["GP"]["products"] == [] and by_code["FB"]["products"] == []

    await _approved(client, admin_headers, gp["id"], "GP_THC26:CBD1", 26)
    await _approved(client, admin_headers, gp["id"], "GP_THC18:CBD1", 18)
    await _product(client, admin_headers, fb["id"], "FB_THC18:CBD1", 18)   # DRAFT

    by_code = {c["code"]: c for c in
               (await client.get("/cultivation/cultivars", headers=cu_h)).json()["cultivars"]}
    gp_products = by_code["GP"]["products"]
    assert [p["product_code"] for p in gp_products] == ["GP_THC26:CBD1", "GP_THC18:CBD1"]
    assert gp_products[0]["window_min"] == 23.40 and gp_products[0]["window_max"] == 28.59
    assert gp_products[0]["grade"] == 26.0 and gp_products[0]["status"] == "APPROVED"
    assert by_code["FB"]["products"][0]["status"] == "DRAFT"


async def test_next_batch_code_is_the_cultivar_head_plus_period_plus_sequence(client, admin_headers):
    """GP072501 = cultivar code + period + sequence. The head is the cultivar
    code; the period is MMYY of the facility's today; the sequence counts what
    the org already holds for that cultivar in that period."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    room = await _room(client, admin_headers, "clone_n", "Clone N", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    period = facility_today().strftime("%m%y")
    r = await client.get(f"/cultivation/batch-code?cultivar_id={cv['id']}", headers=qa_h)
    assert r.status_code == 200, r.text
    assert r.json() == {"prefix": "GP", "period": period, "seq": 1, "suggested": f"GP{period}01"}
    r = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": r.json()["suggested"],
        "plant_count": 1, "phase": "clone"}, headers=qa_h)
    assert r.status_code == 201, r.text
    r = await client.get(f"/cultivation/batch-code?cultivar_id={cv['id']}", headers=qa_h)
    assert r.json()["seq"] == 2 and r.json()["suggested"] == f"GP{period}02"
    assert (await client.get("/cultivation/batch-code?cultivar_id=nope", headers=qa_h)).status_code == 422


# ── the official product, the clone source and the plan's expected dates ─────

async def test_a_batch_is_registered_against_an_approved_product(client, admin_headers):
    """A batch names the ImB product it is grown to. It is a TARGET, not a
    verdict: what the lot turns out to be is settled by the Certificate of
    Quality against that product's window, not here."""
    from tests.test_products import _approved, _product
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_p", "Clone P", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    other = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    prod = await _approved(client, admin_headers, cv["id"], "GP_THC26:CBD1", 26)
    draft = await _product(client, admin_headers, cv["id"], "GP_THC24:CBD1", 24)
    foreign = await _approved(client, admin_headers, other["id"], "OPM_THC22:CBD1", 22)

    base = {"room_id": room["id"], "cultivar_id": cv["id"], "plant_count": 10, "phase": "clone"}
    r = await client.post("/cultivation/batches",
                          json={**base, "code": "GP092601", "product_id": draft["id"]},
                          headers=cu_h)
    assert r.status_code == 422 and "DRAFT" in r.text
    r = await client.post("/cultivation/batches",
                          json={**base, "code": "GP092602", "product_id": foreign["id"]},
                          headers=cu_h)
    assert r.status_code == 422 and "not this cultivar's product" in r.text
    r = await client.post("/cultivation/batches", json={
        **base, "code": "GP092603", "product_id": prod["id"], "clone_source": "imported"},
        headers=cu_h)
    assert r.status_code == 201, r.text
    assert r.json()["product_code"] == "GP_THC26:CBD1" and r.json()["clone_source"] == "imported"

    row = next(b for b in (await client.get("/cultivation/batches", headers=cu_h)).json()["batches"]
               if b["code"] == "GP092603")
    assert row["product_code"] == "GP_THC26:CBD1" and row["product_grade"] == 26.0
    assert row["product_window"] == [23.40, 28.59]

    # A batch registered before its strain's page existed names the product later.
    r = await client.post("/cultivation/batches", json={**base, "code": "GP092604"}, headers=cu_h)
    assert r.status_code == 201 and r.json()["product_id"] is None
    bid = r.json()["id"]
    assert (await client.patch(f"/cultivation/batches/{bid}",
                               json={"product_id": foreign["id"]}, headers=cu_h)).status_code == 422
    r = await client.patch(f"/cultivation/batches/{bid}",
                           json={"product_id": prod["id"], "clone_source": "own_stock"},
                           headers=cu_h)
    assert r.status_code == 200 and r.json()["product_code"] == "GP_THC26:CBD1"
    assert (await client.patch(f"/cultivation/batches/{bid}", json={"clone_source": "bought"},
                               headers=cu_h)).status_code == 422


async def test_the_board_computes_the_plans_expected_window_for_the_phase(client, admin_headers):
    """The owner's plan: cloning 7–14 days (imported clones may stay some days
    more for quarantine), vegetation 14–17, flowering 42–63. The server
    computes the window and the board renders it — one copy of the interval,
    the same discipline the pre-harvest interval keeps."""
    from datetime import timedelta
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "veg_p", "Veg P", kind="veg")
    froom = await _room(client, admin_headers, "flower_p", "Flower P")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    today = facility_today()

    async def _mk(code, phase, days_ago, **over):
        r = await client.post("/cultivation/batches", json={
            "room_id": froom["id"] if phase == "flower" else room["id"],
            "cultivar_id": cv["id"], "code": code, "plant_count": 5,
            "phase": phase, "phase_since": (today - timedelta(days=days_ago)).isoformat(),
            **over}, headers=cu_h)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    veg = await _mk("GP092610", "veg", 10)
    flower = await _mk("GP092611", "flower", 50)
    own = await _mk("GP092612", "clone", 3, clone_source="own_stock")
    imported = await _mk("GP092613", "clone", 3, clone_source="imported")
    mother = await _mk("GP092614", "mother", 3)

    board = {b["id"]: b for b in
             (await client.get("/cultivation/batches", headers=cu_h)).json()["batches"]}

    v = board[veg]
    assert v["days_in_phase"] == 10 and v["expected_next_phase"] == "flower"
    assert v["expected_from"] == (today + timedelta(days=4)).isoformat()   # 14 − 10
    assert v["expected_to"] == (today + timedelta(days=7)).isoformat()     # 17 − 10
    assert v["window_state"] == "early"

    f = board[flower]
    assert f["expected_next_phase"] == "harvest"
    assert f["harvest_window_from"] == (today - timedelta(days=8)).isoformat()   # 42 − 50
    assert f["harvest_window_to"] == (today + timedelta(days=13)).isoformat()    # 63 − 50
    assert f["window_state"] == "in_window", "the harvest window is open now"

    # Imported clones leave at roughly the same time but may stay longer for
    # quarantine and acclimatisation: same start, later end.
    assert board[own]["expected_from"] == board[imported]["expected_from"]
    assert board[own]["expected_to"] == (today + timedelta(days=11)).isoformat()      # 14 − 3
    assert board[imported]["expected_to"] == (today + timedelta(days=18)).isoformat()  # 21 − 3

    # Mother stock is not on the production path: no window is invented for it.
    m = board[mother]
    assert m["expected_from"] is None and m["window_state"] is None
    assert m["days_in_phase"] == 3


async def test_the_cloning_leg_does_not_restart_when_a_batch_moves_to_nursery(client, admin_headers):
    """Nursery is a stop INSIDE the cloning leg, so the expected date is
    measured from the day the batch entered the clone rooms."""
    from datetime import timedelta
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_n2", "Clone N2", kind="clone")
    nursery = await _room(client, admin_headers, "nursery_n2", "Nursery N2", kind="nursery")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    today = facility_today()
    started = today - timedelta(days=6)
    r = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092620", "plant_count": 5,
        "phase": "clone", "phase_since": started.isoformat(),
        "clone_date": started.isoformat()}, headers=cu_h)
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    r = await client.post(f"/cultivation/batches/{bid}/move",
                          json={"to_phase": "nursery", "to_room_id": nursery["id"]}, headers=cu_h)
    assert r.status_code == 200, r.text

    row = next(b for b in (await client.get("/cultivation/batches", headers=cu_h)).json()["batches"]
               if b["id"] == bid)
    assert row["days_in_phase"] == 0, "it moved today"
    # …but the leg still ends 7–14 days after it entered cloning, not after the move.
    assert row["expected_from"] == (started + timedelta(days=7)).isoformat()
    assert row["expected_to"] == (started + timedelta(days=14)).isoformat()
    assert row["expected_next_phase"] == "veg"


async def test_clones_carry_their_mothers_id_and_the_fill_stays_resumable(client, admin_headers):
    """The owner's clone id: every plant cut from GP26_S1M01-1_001 in that
    mother's first cutting is GP26_S1M01-1_001-01.001 upward. A plant with no
    known mother keeps the legacy <date>_<cultivar>_<seq>, and the allocation is
    a pure function of the sequence number so an interrupted fill finishes
    correctly."""
    from tests.test_products import _approved
    from tests.test_propagation import _campaign, _mother
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_cl", "Clone CL", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    prod = await _approved(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m1 = await _mother(client, cu_h, prod["id"], camp["id"])
    m2 = await _mother(client, cu_h, prod["id"], camp["id"])
    assert (m1["code"], m2["code"]) == ("GP26_S1M01-1_001", "GP26_S1M02-1_001")

    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092630",
        "plant_count": 120, "phase": "clone", "clone_date": "2026-09-01",
        "product_id": prod["id"]}, headers=cu_h)
    assert b.status_code == 201, b.text
    bid = b.json()["id"]
    # 60 from the first mother, 40 from the second: 20 of the 120 planned have
    # no mother to name them.
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 120, "started_on": "2026-09-01", "batch_id": bid,
        "product_id": prod["id"],
        "mothers": [{"mother_plant_id": m1["id"], "cuttings": 60},
                    {"mother_plant_id": m2["id"], "cuttings": 40}]})
    assert r.status_code == 201, r.text

    g = await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)
    assert g.status_code == 200, g.text
    body = g.json()
    assert body["complete"] is True and body["materialised"] == 120
    assert body["per_mother"] == [{"mother_code": "GP26_S1M01-1_001", "cutting_no": 1, "count": 60},
                                  {"mother_code": "GP26_S1M02-1_001", "cutting_no": 1, "count": 40}]
    assert body["legacy"] == 20 and body["capped"] is False

    rows = (await client.get(f"/cultivation/batches/{bid}/plants?limit=200",
                             headers=cu_h)).json()["plants"]
    codes = [p["plant_code"] for p in rows]
    assert codes[0] == "GP26_S1M01-1_001-01.001"
    assert codes[59] == "GP26_S1M01-1_001-01.060"
    assert codes[60] == "GP26_S1M02-1_001-01.001"
    assert codes[99] == "GP26_S1M02-1_001-01.040"
    # the remainder falls back to the legacy id, and says nothing about a mother
    assert codes[100] == "20260901_GP092630_0101" and codes[119] == "20260901_GP092630_0120"
    assert rows[0]["mother_code"] == "GP26_S1M01-1_001" and rows[0]["clone_no"] == 1
    assert rows[100]["mother_plant_id"] is None and rows[100]["cutting_no"] is None

    # A second cutting from the same mother numbers itself 02, so its clones do too.
    b2 = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092631",
        "plant_count": 3, "phase": "clone", "clone_date": "2026-09-20"}, headers=cu_h)
    bid2 = b2.json()["id"]
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 3, "started_on": "2026-09-20", "batch_id": bid2,
        "mothers": [{"mother_plant_id": m1["id"], "cuttings": 3}]})
    assert r.status_code == 201 and r.json()["mothers"][0]["cutting_no"] == 2
    await client.post(f"/cultivation/batches/{bid2}/plants", headers=cu_h)
    rows2 = (await client.get(f"/cultivation/batches/{bid2}/plants", headers=cu_h)).json()["plants"]
    assert [p["plant_code"] for p in rows2] == ["GP26_S1M01-1_001-02.001",
                                                "GP26_S1M01-1_001-02.002",
                                                "GP26_S1M01-1_001-02.003"]


async def test_an_interrupted_fill_resumes_with_the_same_ids(client, admin_headers):
    from tests.test_products import _approved
    from tests.test_propagation import _campaign, _mother
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_rs", "Clone RS", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    prod = await _approved(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m = await _mother(client, cu_h, prod["id"], camp["id"])
    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092632",
        "plant_count": 10, "phase": "clone", "clone_date": "2026-09-01"}, headers=cu_h)
    bid = b.json()["id"]
    await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 10, "started_on": "2026-09-01", "batch_id": bid,
        "mothers": [{"mother_plant_id": m["id"], "cuttings": 10}]})

    # Simulate an interrupted fill: materialise, then delete the tail and
    # resume — the ids that come back must be the ones that were there.
    await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)
    from app.db import tasks_admin_pool
    await tasks_admin_pool().execute("DELETE FROM plants WHERE batch_id=$1 AND seq > 4", bid)
    g = await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)
    assert g.json()["complete"] is True
    rows = (await client.get(f"/cultivation/batches/{bid}/plants", headers=cu_h)).json()["plants"]
    assert [p["plant_code"] for p in rows] == [
        f"{m['code']}-01.{n:03d}" for n in range(1, 11)]


async def test_a_cutting_of_more_than_999_clones_cannot_be_numbered(client, admin_headers):
    """.nnn runs 001-999. A cutting bigger than that has to be split, and
    saying so is better than silently numbering 1000 plants wrongly."""
    from tests.test_products import _approved
    from tests.test_propagation import _campaign, _mother
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_big", "Clone BIG", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    prod = await _approved(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m = await _mother(client, cu_h, prod["id"], camp["id"])
    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092633",
        "plant_count": 1200, "phase": "clone"}, headers=cu_h)
    bid = b.json()["id"]
    await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 1200, "started_on": "2026-09-01", "batch_id": bid,
        "mothers": [{"mother_plant_id": m["id"], "cuttings": 1000}]})
    r = await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)
    assert r.status_code == 422 and "999" in r.text
    assert (await client.get(f"/cultivation/batches/{bid}/plants",
                             headers=cu_h)).json()["total"] == 0


async def test_a_mother_whose_cuttings_were_not_counted_names_no_clones(client, admin_headers):
    """Numbering clones 1..n needs an n. Blank cuttings mean "not counted", so
    those plants keep the legacy id rather than being given invented numbers."""
    from tests.test_products import _approved
    from tests.test_propagation import _campaign, _mother
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_unc", "Clone UNC", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    prod = await _approved(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m = await _mother(client, cu_h, prod["id"], camp["id"])
    b = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092634",
        "plant_count": 3, "phase": "clone", "clone_date": "2026-09-01"}, headers=cu_h)
    bid = b.json()["id"]
    await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 3, "started_on": "2026-09-01", "batch_id": bid,
        "mothers": [{"mother_plant_id": m["id"]}]})
    g = await client.post(f"/cultivation/batches/{bid}/plants", headers=cu_h)
    assert g.json()["per_mother"] == [] and g.json()["legacy"] == 3
    rows = (await client.get(f"/cultivation/batches/{bid}/plants", headers=cu_h)).json()["plants"]
    assert [p["plant_code"] for p in rows] == ["20260901_GP092634_0001", "20260901_GP092634_0002",
                                               "20260901_GP092634_0003"]


# ── the 2026-09-27 review: CS-01 … CS-18 ─────────────────────────────────────

async def _bt(client, headers, room_id, cultivar_id, code, phase="clone", **over):
    body = {"room_id": room_id, "cultivar_id": cultivar_id, "code": code,
            "plant_count": 10, "phase": phase, **over}
    r = await client.post("/cultivation/batches", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _mv(client, headers, bid, **body):
    return await client.post(f"/cultivation/batches/{bid}/move", json=body, headers=headers)


async def test_a_move_is_bounded_by_the_facility_clock_and_stays_in_order(client, admin_headers):
    """CS-01. A move dated after the facility's today, or before the batch's
    latest phase event, is refused: the PHI gate resolves the batch's room on
    the application date from these events, and a backdated room move used to
    lift a room-scoped spray block."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    f1 = await _room(client, admin_headers, "flower_b1", "Flowering B1")
    f2 = await _room(client, admin_headers, "flower_b2", "Flowering B2")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    today = facility_today()
    b = await _bt(client, cu_h, f1["id"], cv["id"], "GP092640", phase="flower",
                  phase_since=(today - timedelta(days=10)).isoformat())

    r = await _mv(client, cu_h, b["id"], to_phase="flower", to_room_id=f2["id"],
                  occurred_on=(today + timedelta(days=1)).isoformat())
    assert r.status_code == 422 and "future" in r.text
    r = await _mv(client, cu_h, b["id"], to_phase="flower", to_room_id=f2["id"],
                  occurred_on=(today - timedelta(days=11)).isoformat())
    assert r.status_code == 422 and "before" in r.text
    # Dated on the phase start itself is fine; the next move cannot predate it.
    r = await _mv(client, cu_h, b["id"], to_phase="flower", to_room_id=f2["id"],
                  occurred_on=(today - timedelta(days=3)).isoformat())
    assert r.status_code == 200, r.text
    r = await _mv(client, cu_h, b["id"], to_phase="flower", to_room_id=f1["id"],
                  occurred_on=(today - timedelta(days=5)).isoformat())
    assert r.status_code == 422 and "before" in r.text
    # A batch cannot be registered in the future either.
    r = await client.post("/cultivation/batches", json={
        "room_id": f1["id"], "cultivar_id": cv["id"], "code": "GP092641", "plant_count": 1,
        "phase": "clone", "clone_date": (today + timedelta(days=1)).isoformat()}, headers=cu_h)
    assert r.status_code == 422 and "future" in r.text


async def test_two_batches_of_one_cultivar_cloned_the_same_day_both_get_ids(client, admin_headers):
    """CS-02. Two flowering rooms of Grape Pie cloned together is the normal
    plan. The legacy id carries the batch code, so the second fill does not
    collide with the first on (org, plant_code)."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_two", "Clone Two", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    a = await _bt(client, cu_h, room["id"], cv["id"], "GP092601", clone_date="2026-09-27")
    b = await _bt(client, cu_h, room["id"], cv["id"], "GP092602", clone_date="2026-09-27")
    for x in (a, b):
        g = await client.post(f"/cultivation/batches/{x['id']}/plants", headers=cu_h)
        assert g.status_code == 200, g.text
        assert g.json()["complete"] is True
    pa = (await client.get(f"/cultivation/batches/{a['id']}/plants", headers=cu_h)).json()["plants"]
    pb = (await client.get(f"/cultivation/batches/{b['id']}/plants", headers=cu_h)).json()["plants"]
    assert pa[0]["plant_code"] == "20260927_GP092601_0001"
    assert pb[0]["plant_code"] == "20260927_GP092602_0001"
    assert not ({p["plant_code"] for p in pa} & {p["plant_code"] for p in pb})


async def test_a_room_change_keeps_the_phase_clock(client, admin_headers):
    """CS-06. A flowering batch moved F1 -> F2 on day 30 is still on day 30: a
    move to the SAME phase changes the room and nothing else, records one
    event, and generates no phase tasks."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    f1 = await _room(client, admin_headers, "flower_r1", "Flowering R1")
    f2 = await _room(client, admin_headers, "flower_r2", "Flowering R2")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    since = (facility_today() - timedelta(days=30)).isoformat()
    b = await _bt(client, cu_h, f1["id"], cv["id"], "GP092650", phase="flower", phase_since=since)

    # "Move to where you already are" with no room is not a move.
    assert (await _mv(client, cu_h, b["id"], to_phase="flower")).status_code == 422
    assert (await _mv(client, cu_h, b["id"], to_phase="flower",
                      to_room_id=f1["id"])).status_code == 422
    r = await _mv(client, cu_h, b["id"], to_phase="flower", to_room_id=f2["id"])
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "room" and r.json()["phase_since"] == since
    assert r.json()["room_id"] == f2["id"] and r.json()["generated_task_ids"] == []
    row = next(x for x in (await client.get("/cultivation/batches", headers=cu_h)).json()["batches"]
               if x["id"] == b["id"])
    assert row["days_in_phase"] == 30 and row["room_name"] == "Flowering R2"
    # …and the harvest window did not restart.
    assert row["harvest_window_from"] == (facility_today() + timedelta(days=12)).isoformat()


async def test_the_path_is_walked_one_stop_at_a_time_and_backwards_is_a_qa_correction(client, admin_headers):
    """CS-06. clone -> nursery -> veg -> flower -> drying -> harvested, nursery
    and drying optional, destroyed from anywhere. A backward move is a
    correction: QA authority with a reason, or nothing."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    clone = await _room(client, admin_headers, "clone_path", "Clone Path", kind="clone")
    flower = await _room(client, admin_headers, "flower_path", "Flowering Path")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    b = await _bt(client, cu_h, clone["id"], cv["id"], "GP092660")

    r = await _mv(client, cu_h, b["id"], to_phase="flower", to_room_id=flower["id"])
    assert r.status_code == 422 and "skips" in r.text
    assert (await _mv(client, cu_h, b["id"], to_phase="drying")).status_code == 422
    assert (await _mv(client, cu_h, b["id"], to_phase="harvested", reason="x")).status_code == 422
    assert (await _mv(client, cu_h, b["id"], to_phase="veg")).status_code == 200      # nursery skipped
    assert (await _mv(client, cu_h, b["id"], to_phase="flower",
                      to_room_id=flower["id"])).status_code == 200
    # Backwards: the floor may not; QA may, with a reason.
    r = await _mv(client, cu_h, b["id"], to_phase="veg", reason="wrong room")
    assert r.status_code == 403
    r = await _mv(client, qa_h, b["id"], to_phase="veg")
    assert r.status_code == 422 and "reason" in r.text
    r = await _mv(client, qa_h, b["id"], to_phase="veg", reason="moved a day early by mistake")
    assert r.status_code == 200 and r.json()["kind"] == "backward"
    assert (await _mv(client, cu_h, b["id"], to_phase="flower")).status_code == 200
    # flower -> harvested skips the optional drying stop; drying -> harvested too.
    assert (await _mv(client, cu_h, b["id"], to_phase="drying")).status_code == 200
    r = await _mv(client, cu_h, b["id"], to_phase="harvested", reason="final pull")
    assert r.status_code == 200 and r.json()["is_active"] is False
    # Destroyed is reachable from anywhere; mother stock is off the path.
    c2 = await _bt(client, cu_h, clone["id"], cv["id"], "GP092661")
    assert (await _mv(client, cu_h, c2["id"], to_phase="destroyed",
                      reason="damping off")).status_code == 200
    m = await _bt(client, cu_h, clone["id"], cv["id"], "GP092662", phase="mother")
    r = await _mv(client, cu_h, m["id"], to_phase="veg")
    assert r.status_code == 422 and "mother" in r.text
    assert (await _mv(client, cu_h, c2["id"], to_phase="mother")).status_code == 409


async def test_two_moves_at_once_serialise_on_the_batch_row(client, admin_headers):
    """CS-06. A forward move and a terminal move fired together: the row lock
    orders them, so the batch ends closed with every plant settled and never
    half-closed (phase moved on, is_active false)."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    flower = await _room(client, admin_headers, "flower_race", "Flowering Race")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    b = await _bt(client, cu_h, flower["id"], cv["id"], "GP092670", phase="flower")
    await client.post(f"/cultivation/batches/{b['id']}/plants", headers=cu_h)
    a, c = await asyncio.gather(
        _mv(client, cu_h, b["id"], to_phase="harvested", reason="final pull"),
        _mv(client, cu_h, b["id"], to_phase="drying"))
    assert sorted([a.status_code, c.status_code]) in ([200, 200], [200, 409]), (a.text, c.text)
    row = next(x for x in (await client.get("/cultivation/batches?active=false",
                                            headers=cu_h)).json()["batches"] if x["id"] == b["id"])
    assert row["phase"] == "harvested" and row["is_active"] is False
    assert (await client.get(f"/cultivation/batches/{b['id']}/plants?status=active",
                             headers=cu_h)).json()["total"] == 0


async def test_closing_after_a_waste_manifest_settles_the_destroyed_plants(client, admin_headers):
    """CS-07. 150 of 2000 declared destroyed on a manifest and the rest
    harvested: closing the batch marks 150 plants destroyed, not harvested,
    with the manifest named as the reason."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    flower = await _room(client, admin_headers, "flower_wm", "Flowering WM")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    b = await _bt(client, cu_h, flower["id"], cv["id"], "GP092680", phase="flower", plant_count=40)
    await client.post(f"/cultivation/batches/{b['id']}/plants", headers=cu_h)
    m = await client.post("/waste/manifests", json={
        "manifest_code": "WM-CS07", "waste_type": "plant_material",
        "reason": "hlvd_eradication", "campaign": "hlvd-2026-09"}, headers=cu_h)
    assert m.status_code == 201, m.text
    r = await client.post(f"/waste/manifests/{m.json()['id']}/lines",
                          json={"batch_id": b["id"], "plant_qty": 15}, headers=cu_h)
    assert r.status_code == 201, r.text

    r = await _mv(client, cu_h, b["id"], to_phase="harvested", reason="final pull")
    assert r.status_code == 200, r.text
    assert r.json()["plants_settled"] == {"harvested": 25, "destroyed": 15}
    plants = (await client.get(f"/cultivation/batches/{b['id']}/plants?limit=100",
                               headers=cu_h)).json()["plants"]
    assert sum(1 for p in plants if p["status"] == "destroyed") == 15
    assert sum(1 for p in plants if p["status"] == "harvested") == 25
    gone = [p for p in plants if p["status"] == "destroyed"]
    assert "WM-CS07" in gone[0]["reason"]
    assert all(p["status_since"] == facility_today().isoformat() for p in plants)


async def test_the_next_batch_number_is_max_plus_one_in_the_cloning_month(client, admin_headers):
    """CS-09. GP092601 and GP092603 on file suggest 04, not 03 (count); the
    month is the CLONING month, not the day the form is opened; 99 is the end."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_nn", "Clone NN", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    for code in ("GP082601", "GP082603", "GP0826X1", "GP-SUB"):
        await _bt(client, cu_h, room["id"], cv["id"], code, clone_date="2026-08-20")
    r = await client.get(f"/cultivation/batch-code?cultivar_id={cv['id']}&clone_date=2026-08-30",
                         headers=cu_h)
    assert r.status_code == 200, r.text
    assert r.json() == {"prefix": "GP", "period": "0826", "seq": 4, "suggested": "GP082604"}
    r = await client.get(f"/cultivation/batch-code?cultivar_id={cv['id']}&clone_date=2026-09-01",
                         headers=cu_h)
    assert r.json()["suggested"] == "GP092601", "September's first batch, whatever today is"
    await _bt(client, cu_h, room["id"], cv["id"], "GP092699", clone_date="2026-09-01")
    r = await client.get(f"/cultivation/batch-code?cultivar_id={cv['id']}&clone_date=2026-09-02",
                         headers=cu_h)
    assert r.status_code == 422 and "99" in r.text


async def test_a_batch_code_must_carry_its_cultivars_head(client, admin_headers):
    """CS-09. The strain of a tested lot is read off the batch code's head, so
    a GP batch cannot be filed as XYZ092601; a concurrent duplicate is a 409."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_hd", "Clone HD", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    r = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "XYZ092601",
        "plant_count": 1, "phase": "clone"}, headers=cu_h)
    assert r.status_code == 422 and "GP" in r.text
    body = {"room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092605",
            "plant_count": 1, "phase": "clone"}
    a, b = await asyncio.gather(client.post("/cultivation/batches", json=body, headers=cu_h),
                                client.post("/cultivation/batches", json=body, headers=cu_h))
    assert sorted([a.status_code, b.status_code]) == [201, 409], (a.text, b.text)


async def test_flowering_happens_in_a_flowering_room(client, admin_headers):
    """CS-16. The owner: flowering is "in one of the 6 available flowering
    rooms". A batch cannot be registered in, or moved to, flower in any other
    kind of room — with or without a room change on the move."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    veg = await _room(client, admin_headers, "veg_fl", "Veg FL", kind="veg")
    dry = await _room(client, admin_headers, "dry_fl", "Dry FL", kind="dry")
    flower = await _room(client, admin_headers, "flower_fl", "Flowering FL")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    r = await client.post("/cultivation/batches", json={
        "room_id": veg["id"], "cultivar_id": cv["id"], "code": "GP092690",
        "plant_count": 1, "phase": "flower"}, headers=cu_h)
    assert r.status_code == 422 and "flower" in r.text
    b = await _bt(client, cu_h, veg["id"], cv["id"], "GP092691", phase="veg")
    assert (await _mv(client, cu_h, b["id"], to_phase="flower")).status_code == 422
    assert (await _mv(client, cu_h, b["id"], to_phase="flower",
                      to_room_id=dry["id"])).status_code == 422
    assert (await _mv(client, cu_h, b["id"], to_phase="flower",
                      to_room_id=flower["id"])).status_code == 200
    # A flowering batch may not be shuffled into a veg room either.
    assert (await _mv(client, cu_h, b["id"], to_phase="flower",
                      to_room_id=veg["id"])).status_code == 422


async def test_cultivars_carry_no_legacy_ladder(client, admin_headers):
    """CS-18. The superseded potency ladder rode along as `spec`; nothing read it."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    await _cultivar(client, cu_h, "GP", "Grape Pie")
    cvs = (await client.get("/cultivation/cultivars", headers=cu_h)).json()["cultivars"]
    assert cvs and all("spec" not in c for c in cvs)
    assert all("products" in c for c in cvs)


async def test_a_closed_batch_gets_no_plants_and_a_failed_run_names_none(client, admin_headers):
    """CS-05. Generating plants for a harvested or destroyed batch is refused;
    the mothers of a run that FAILED (its cuttings did not root) contribute no
    clone ids, so the fill numbers only the runs that produced plants."""
    from tests.test_products import _approved
    from tests.test_propagation import _campaign, _mother
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    room = await _room(client, admin_headers, "clone_fail", "Clone Fail", kind="clone")
    cv = await _cultivar(client, cu_h, "GP", "Grape Pie")
    prod = await _approved(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m1 = await _mother(client, cu_h, prod["id"], camp["id"])
    m2 = await _mother(client, cu_h, prod["id"], camp["id"])
    b = await _bt(client, cu_h, room["id"], cv["id"], "GP092695", plant_count=6,
                  clone_date="2026-09-01")
    failed = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 3, "started_on": "2026-09-01",
        "batch_id": b["id"], "mothers": [{"mother_plant_id": m1["id"], "cuttings": 3}]})
    assert failed.status_code == 201, failed.text
    ok = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 3, "started_on": "2026-09-02",
        "batch_id": b["id"], "mothers": [{"mother_plant_id": m2["id"], "cuttings": 3}]})
    assert ok.status_code == 201, ok.text
    assert (await client.patch(f"/cultivation/clone-runs/{failed.json()['id']}",
                               json={"status": "failed"}, headers=cu_h)).status_code == 200
    g = await client.post(f"/cultivation/batches/{b['id']}/plants", headers=cu_h)
    assert g.status_code == 200, g.text
    assert g.json()["per_mother"] == [{"mother_code": m2["code"], "cutting_no": 1, "count": 3}]
    codes = [p["plant_code"] for p in
             (await client.get(f"/cultivation/batches/{b['id']}/plants", headers=cu_h)).json()["plants"]]
    assert codes[:3] == [f"{m2['code']}-01.00{n}" for n in (1, 2, 3)]
    assert codes[3] == "20260901_GP092695_0004"

    closed = await _bt(client, cu_h, room["id"], cv["id"], "GP092696", plant_count=2)
    await _mv(client, cu_h, closed["id"], to_phase="destroyed", reason="damping off")
    r = await client.post(f"/cultivation/batches/{closed['id']}/plants", headers=cu_h)
    assert r.status_code == 409 and "closed" in r.text
