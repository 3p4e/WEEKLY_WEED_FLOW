"""Propagation — the mother-plant bank and clone runs (migration 0065 +
app/api/propagation.py).

Pins the access model (read: every role above USER; the bank: CU_MGR +
executives + ADMIN; initiating a clone run: those PLUS QA_MGR — the same set
that registers a batch), the derived-not-stored facts on a mother (age, last
cut, generations), the same-cultivar rule between a run, its mothers and the
batch it feeds, the product-specification snapshot, and the run's one-way
lifecycle.
"""
from datetime import timedelta

from app.worktime import facility_today
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


async def _room(client, admin_headers, code, name, kind="mother"):
    r = await client.post("/facility/rooms",
                          json={"code": code, "name": name, "kind": kind},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _cultivar(client, headers, code="GP", name="Grape Pie"):
    r = await client.post("/cultivation/cultivars",
                          json={"code": code, "name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _mother(client, headers, cultivar_id, code, **extra):
    r = await client.post("/cultivation/mothers",
                          json={"cultivar_id": cultivar_id, "code": code, **extra},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


LADDER = [
    {"tier": 1, "range_min": 26, "range_max": 30, "nominal": 28.0},
    {"tier": 2, "range_min": 22, "range_max": 26, "nominal": 24.0},
    {"tier": 3, "range_min": 18, "range_max": 22, "nominal": 20.0},
    {"tier": 4, "range_min": 13.83, "range_max": 18, "nominal": 16.0},
]


async def _approved_ladder(client, admin_headers, cultivar_id, version="v5.2"):
    """An APPROVED ImB ladder: authored by admin, approved by a different
    person (segregation of duties is the potency module's own rule)."""
    r = await client.post("/qc/potency-specs", json={
        "cultivar_id": cultivar_id, "version": version, "variant": "A",
        "floor_pct": 13.83, "n_batches": 10, "ranges": LADDER}, headers=admin_headers)
    assert r.status_code == 201, r.text
    spec = r.json()
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/potency-specs/{spec['id']}/approve", headers=qc_h)
    assert r.status_code == 200, r.text
    return spec


# ── the bank ──────────────────────────────────────────────────────────────────

async def test_bank_read_gating_writers_and_derived_fields(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    room = await _room(client, admin_headers, "mother_1", "Mother room 1")

    assert (await client.get("/cultivation/mothers", headers=user_h)).status_code == 403
    assert (await client.get("/cultivation/mothers", headers=qc_h)).status_code == 200

    # The bank is floor master data: QC and QA do not register mothers; CU does.
    body = {"cultivar_id": cv["id"], "code": "GP_M01"}
    assert (await client.post("/cultivation/mothers", json=body, headers=qc_h)).status_code == 403
    assert (await client.post("/cultivation/mothers", json=body, headers=qa_h)).status_code == 403

    started = facility_today() - timedelta(days=40)
    m = await _mother(client, cu_h, cv["id"], "GP_M01", phenotype="Pheno A",
                      room_id=room["id"], position="pot 12", started_on=started.isoformat(),
                      source="seed selection 2026")
    assert m["cultivar_code"] == "GP" and m["room_name"] == "Mother room 1"
    assert m["position"] == "pot 12" and m["phenotype"] == "Pheno A"
    # Derived, never stored: age from the establishment date; a mother never
    # cut has no last cut and zero generations — not an invented first one.
    assert m["age_days"] == 40
    assert m["last_cut_on"] is None and m["generations"] == 0 and m["cuttings_total"] == 0

    # A second mother with no dates has no age rather than an age of zero.
    m2 = await _mother(client, cu_h, cv["id"], "GP_M02")
    assert m2["age_days"] is None

    # Unique ID: the same code again is a conflict, not a silent return.
    r = await client.post("/cultivation/mothers", json=body, headers=cu_h)
    assert r.status_code == 409

    # The per-strain count comes from the server.
    lst = (await client.get("/cultivation/mothers", headers=qc_h)).json()
    assert [x["code"] for x in lst["mothers"]] == ["GP_M01", "GP_M02"]
    strain = next(s for s in lst["by_cultivar"] if s["cultivar_id"] == cv["id"])
    assert strain["active"] == 2 and strain["total"] == 2
    assert strain["phenotypes"] == ["Pheno A"]


async def test_next_mother_code_is_the_cultivar_head_plus_the_next_number(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    r = await client.get(f"/cultivation/mothers/next-code?cultivar_id={cv['id']}", headers=cu_h)
    assert r.status_code == 200, r.text
    assert r.json() == {"prefix": "OPM_M", "seq": 1, "suggested": "OPM_M01"}
    await _mother(client, cu_h, cv["id"], "OPM_M01")
    r = await client.get(f"/cultivation/mothers/next-code?cultivar_id={cv['id']}", headers=cu_h)
    assert r.json()["suggested"] == "OPM_M02"
    # An unknown cultivar is a 422, not a suggestion for nothing.
    r = await client.get("/cultivation/mothers/next-code?cultivar_id=not-a-uuid", headers=cu_h)
    assert r.status_code == 422


async def test_mother_status_moves_and_a_destroyed_plant_stays_destroyed(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    cv = await _cultivar(client, cu_h)
    room = await _room(client, admin_headers, "mother_2", "Mother room 2")
    m = await _mother(client, cu_h, cv["id"], "GP_M01", room_id=room["id"], position="pot 3")

    # QA reads the bank; it does not edit it.
    r = await client.patch(f"/cultivation/mothers/{m['id']}", json={"position": "pot 4"}, headers=qa_h)
    assert r.status_code == 403

    r = await client.patch(f"/cultivation/mothers/{m['id']}", json={"status": "retired"}, headers=cu_h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "retired"
    assert r.json()["status_since"] == facility_today().isoformat()

    # Explicit null clears the location; an absent key leaves it alone.
    r = await client.patch(f"/cultivation/mothers/{m['id']}",
                           json={"room_id": None, "position": None}, headers=cu_h)
    assert r.json()["room_id"] is None and r.json()["position"] is None
    r = await client.patch(f"/cultivation/mothers/{m['id']}", json={"note": "kept for genetics"},
                           headers=cu_h)
    assert r.json()["status"] == "retired" and r.json()["note"] == "kept for genetics"

    # Retired excluded from the active list, present with active=false.
    active = (await client.get("/cultivation/mothers", headers=cu_h)).json()
    assert m["id"] not in [x["id"] for x in active["mothers"]]
    every = (await client.get("/cultivation/mothers?active=false", headers=cu_h)).json()
    assert m["id"] in [x["id"] for x in every["mothers"]]

    r = await client.patch(f"/cultivation/mothers/{m['id']}", json={"status": "destroyed"}, headers=cu_h)
    assert r.status_code == 200
    r = await client.patch(f"/cultivation/mothers/{m['id']}", json={"status": "active"}, headers=cu_h)
    assert r.status_code == 409
    r = await client.patch(f"/cultivation/mothers/{m['id']}", json={"status": "eaten"}, headers=cu_h)
    assert r.status_code == 422


# ── clone runs ────────────────────────────────────────────────────────────────

async def test_a_clone_run_is_initiated_by_cultivation_or_qa_and_snapshots_the_spec(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    clone_room = await _room(client, admin_headers, "clone_1", "Clone room 1", kind="clone")

    # Before any ladder exists the run says so with a null, not a refusal.
    body = {"cultivar_id": cv["id"], "planned_count": 2000, "room_id": clone_room["id"],
            "started_on": "2026-09-06"}
    assert (await client.post("/cultivation/clone-runs", json=body, headers=user_h)).status_code == 403
    assert (await client.post("/cultivation/clone-runs", json=body, headers=qc_h)).status_code == 403
    r = await client.post("/cultivation/clone-runs", json=body, headers=qa_h)
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["cultivar_code"] == "GP" and run["room_name"] == "Clone room 1"
    assert run["started_on"] == "2026-09-06" and run["planned_count"] == 2000
    assert run["status"] == "started" and run["mothers"] == [] and run["cuttings_total"] == 0
    assert run["potency_spec_id"] is None and run["spec_version"] is None

    # With an APPROVED ImB ladder, the run records which specification the
    # material was propagated against.
    spec = await _approved_ladder(client, admin_headers, cv["id"])
    r = await client.post("/cultivation/clone-runs", json=body, headers=cu_h)
    assert r.status_code == 201, r.text
    run2 = r.json()
    assert run2["potency_spec_id"] == spec["id"]
    assert run2["spec_version"] == "v5.2" and run2["spec_status"] == "APPROVED"
    assert run2["spec_code"] == "PP-QC-SPEC-001"

    # started_on defaults to the facility's today.
    r = await client.post("/cultivation/clone-runs",
                          json={"cultivar_id": cv["id"], "planned_count": 10}, headers=cu_h)
    assert r.json()["started_on"] == facility_today().isoformat()

    lst = (await client.get("/cultivation/clone-runs", headers=qc_h)).json()
    assert len(lst["runs"]) == 3


async def test_a_run_names_its_mothers_and_the_bank_derives_last_cut_and_generations(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    gp = await _cultivar(client, cu_h, "GP", "Grape Pie")
    opm = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    m1 = await _mother(client, cu_h, gp["id"], "GP_M01")
    m2 = await _mother(client, cu_h, gp["id"], "GP_M02")
    other = await _mother(client, cu_h, opm["id"], "OPM_M01")
    retired = await _mother(client, cu_h, gp["id"], "GP_M03")
    await client.patch(f"/cultivation/mothers/{retired['id']}", json={"status": "retired"}, headers=cu_h)

    base = {"cultivar_id": gp["id"], "planned_count": 100, "started_on": "2026-09-06"}
    # A mother of another strain, a retired mother, a mother listed twice —
    # each refused by name, before anything is written.
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        **base, "mothers": [{"mother_plant_id": other["id"], "cuttings": 5}]})
    assert r.status_code == 422 and "OPM_M01" in r.text
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        **base, "mothers": [{"mother_plant_id": retired["id"]}]})
    assert r.status_code == 422 and "retired" in r.text
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        **base, "mothers": [{"mother_plant_id": m1["id"]}, {"mother_plant_id": m1["id"]}]})
    assert r.status_code == 422
    assert (await client.get("/cultivation/clone-runs", headers=cu_h)).json()["runs"] == []

    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        **base, "mothers": [{"mother_plant_id": m1["id"], "cuttings": 60},
                            {"mother_plant_id": m2["id"], "cuttings": 40}]})
    assert r.status_code == 201, r.text
    run = r.json()
    assert [m["code"] for m in run["mothers"]] == ["GP_M01", "GP_M02"]
    assert run["cuttings_total"] == 100

    # The bank now shows the cut on both mothers — from the run, not a counter.
    bank = {m["code"]: m for m in (await client.get("/cultivation/mothers", headers=cu_h)).json()["mothers"]}
    assert bank["GP_M01"]["last_cut_on"] == "2026-09-06" and bank["GP_M01"]["generations"] == 1
    assert bank["GP_M01"]["cuttings_total"] == 60 and bank["GP_M02"]["cuttings_total"] == 40

    # A later run from one of them: generations 2, last cut moves forward.
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        **base, "started_on": "2026-09-20", "mothers": [{"mother_plant_id": m1["id"], "cuttings": 30}]})
    assert r.status_code == 201
    bank = {m["code"]: m for m in (await client.get("/cultivation/mothers", headers=cu_h)).json()["mothers"]}
    assert bank["GP_M01"]["generations"] == 2 and bank["GP_M01"]["last_cut_on"] == "2026-09-20"
    assert bank["GP_M02"]["generations"] == 1 and bank["GP_M02"]["last_cut_on"] == "2026-09-06"


async def test_a_run_feeds_a_batch_of_the_same_cultivar_only(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    gp = await _cultivar(client, cu_h, "GP", "Grape Pie")
    opm = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    room = await _room(client, admin_headers, "clone_2", "Clone room 2", kind="clone")
    gp_batch = (await client.post("/cultivation/batches", headers=cu_h, json={
        "room_id": room["id"], "cultivar_id": gp["id"], "code": "GP092601",
        "plant_count": 2000, "phase": "clone"})).json()
    opm_batch = (await client.post("/cultivation/batches", headers=cu_h, json={
        "room_id": room["id"], "cultivar_id": opm["id"], "code": "OPM092601",
        "plant_count": 500, "phase": "clone"})).json()

    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": gp["id"], "planned_count": 2000, "batch_id": opm_batch["id"]})
    assert r.status_code == 422 and "OPM092601" in r.text
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": gp["id"], "planned_count": 2000, "batch_id": gp_batch["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["batch_code"] == "GP092601"

    # Linking after the fact follows the same rule.
    r2 = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": gp["id"], "planned_count": 10})
    rid = r2.json()["id"]
    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"batch_id": opm_batch["id"]}, headers=cu_h)
    assert r.status_code == 422
    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"batch_id": gp_batch["id"]}, headers=cu_h)
    assert r.status_code == 200 and r.json()["batch_code"] == "GP092601"


async def test_a_clone_run_finishes_once(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    cv = await _cultivar(client, cu_h)
    r = await client.post("/cultivation/clone-runs", headers=qa_h, json={
        "cultivar_id": cv["id"], "planned_count": 100, "code": "CR_001"})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    # A stated code is unique per org.
    r = await client.post("/cultivation/clone-runs", headers=qa_h, json={
        "cultivar_id": cv["id"], "planned_count": 5, "code": "CR_001"})
    assert r.status_code == 409

    assert (await client.patch(f"/cultivation/clone-runs/{rid}", json={"note": "x"},
                               headers=qc_h)).status_code == 403
    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"planned_count": 120}, headers=cu_h)
    assert r.status_code == 200 and r.json()["planned_count"] == 120

    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"status": "transplanted"}, headers=cu_h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "transplanted"
    assert r.json()["finished_on"] == facility_today().isoformat()
    # Finished runs leave the active list and do not change again.
    assert rid not in [x["id"] for x in (await client.get("/cultivation/clone-runs", headers=cu_h)).json()["runs"]]
    assert rid in [x["id"] for x in (await client.get("/cultivation/clone-runs?active=false", headers=cu_h)).json()["runs"]]
    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"note": "late"}, headers=cu_h)
    assert r.status_code == 409
    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"status": "started"}, headers=cu_h)
    assert r.status_code == 409

    r = await client.patch("/cultivation/clone-runs/not-a-uuid", json={"note": "x"}, headers=cu_h)
    assert r.status_code == 404
