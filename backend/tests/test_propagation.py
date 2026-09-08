"""Propagation — selection campaigns, the mother-plant bank and clone runs
(migrations 0065/0067 + app/api/propagation.py).

Pins the owner's identity scheme (2026-09-05): a mother plant is
GP26_S1M03-2_020 — product, facility-wide selection campaign, mother number of
that campaign, its own generation, clone number in stock — composed by the
server from segments rather than typed; a cutting from that mother is numbered
so the clones it produced can be named; and the derived facts (age, last cut,
how many times cut, the strain's tested potency) are read from the record,
never stored as counters. Also pins the access model after QA joined the floor
writers.
"""
from datetime import timedelta

from app.worktime import facility_today
from tests.conftest import create_user, login_and_set_password
from tests.test_products import _approved as _approved_product


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


async def _campaign(client, headers, material="seeds", **extra):
    r = await client.post("/cultivation/campaigns", json={"material": material, **extra},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _mother(client, headers, product_id, campaign_id, **extra):
    r = await client.post("/cultivation/mothers",
                          json={"product_id": product_id, "campaign_id": campaign_id, **extra},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_the_bank_is_the_floors_and_a_mother_carries_its_derived_facts(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h, "seeds", description="first selection")
    room = await _room(client, admin_headers, "mother_1", "Mother room 1")

    assert (await client.get("/cultivation/mothers", headers=user_h)).status_code == 403
    assert (await client.get("/cultivation/mothers", headers=qc_h)).status_code == 200
    # The bank is floor master data. QC does not register mothers; QA does,
    # since the owner put it on the floor on 2026-09-05.
    body = {"product_id": prod["id"], "campaign_id": camp["id"]}
    assert (await client.post("/cultivation/mothers", json=body, headers=qc_h)).status_code == 403

    started = facility_today() - timedelta(days=40)
    m = await _mother(client, cu_h, prod["id"], camp["id"], phenotype="Pheno A",
                      room_id=room["id"], position="pot 12", started_on=started.isoformat(),
                      source="seed selection 2026")
    # The id is COMPOSED, not typed: product grade, campaign, mother, generation, stock.
    assert m["code"] == "GP26_S1M01-1_001"
    assert m["product_code"] == "GP_THC26:CBD1" and m["campaign_label"] == "S1"
    assert m["mother_no"] == 1 and m["generation"] == 1 and m["stock_no"] == 1
    assert m["room_name"] == "Mother room 1" and m["position"] == "pot 12"
    # Derived, never stored: age from the establishment date; a mother never cut
    # has no last cut and has been cut zero times — not an invented first one.
    assert m["age_days"] == 40
    assert m["last_cut_on"] is None and m["times_cut"] == 0 and m["cuttings_total"] == 0
    assert m["tested"] == {"n": 0, "avg": None, "min": None, "max": None}

    # QA registers too, and the next numbers follow on their own.
    m2 = await _mother(client, qa_h, prod["id"], camp["id"])
    assert m2["code"] == "GP26_S1M02-1_001", "a new mother takes the campaign's next M number"
    assert m2["age_days"] is None, "no date recorded is no age, not an age of zero"

    lst = (await client.get("/cultivation/mothers", headers=qc_h)).json()
    assert [x["code"] for x in lst["mothers"]] == ["GP26_S1M01-1_001", "GP26_S1M02-1_001"]
    strain = next(s for s in lst["by_cultivar"] if s["cultivar_id"] == cv["id"])
    assert strain["active"] == 2 and strain["total"] == 2
    assert strain["phenotypes"] == ["Pheno A"] and strain["products"] == ["GP_THC26:CBD1"]


async def test_a_campaign_is_numbered_facility_wide(client, admin_headers):
    """S3 is "the third such event" the facility ran, whatever the strain."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    gp = await _cultivar(client, cu_h, "GP", "Grape Pie")
    opm = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    a = await _campaign(client, cu_h, "seeds", cultivar_id=gp["id"])
    b = await _campaign(client, cu_h, "phenotypes", cultivar_id=opm["id"])
    c = await _campaign(client, cu_h, "clones")
    assert [x["seq"] for x in (a, b, c)] == [1, 2, 3]
    assert c["label"] == "S3" and c["started_on"] == facility_today().isoformat()
    assert (await client.post("/cultivation/campaigns", json={"material": "cuttings"},
                              headers=cu_h)).status_code == 422
    assert (await client.post("/cultivation/campaigns", json={"material": "seeds"},
                              headers=qc_h)).status_code == 403
    lst = (await client.get("/cultivation/campaigns", headers=qc_h)).json()["campaigns"]
    assert [x["label"] for x in lst] == ["S1", "S2", "S3"]
    assert lst[0]["cultivar_code"] == "GP" and lst[2]["cultivar_code"] is None
    assert all(x["mothers_count"] == 0 for x in lst)


async def test_the_id_segments_are_chosen_or_suggested(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    prod = await _approved_product(client, admin_headers, cv["id"], "OPM_THC8:CBD1", 8)
    camp = await _campaign(client, cu_h, "clones")

    r = await client.get(f"/cultivation/mothers/next-code?product_id={prod['id']}"
                         f"&campaign_id={camp['id']}", headers=cu_h)
    assert r.status_code == 200, r.text
    assert r.json()["suggested"] == "OPM8_S1M01-1_001"
    assert r.json()["head"] == "OPM8_S1M01-1_" and r.json()["next_mother_no"] == 1

    first = await _mother(client, cu_h, prod["id"], camp["id"])
    assert first["code"] == "OPM8_S1M01-1_001"
    # A second plant of the SAME line takes the next stock number.
    second = await _mother(client, cu_h, prod["id"], camp["id"], mother_no=1)
    assert second["code"] == "OPM8_S1M01-1_002"
    r = await client.get(f"/cultivation/mothers/next-code?product_id={prod['id']}"
                         f"&campaign_id={camp['id']}&mother_no=1", headers=cu_h)
    assert r.json()["next_stock_no"] == 3

    # A second-generation clone of a known mother: the generation follows from
    # the parent, and the parent must be of the same specification strain.
    gen2 = await _mother(client, cu_h, prod["id"], camp["id"], mother_no=1,
                         parent_id=first["id"])
    assert gen2["code"] == "OPM8_S1M01-2_001"
    assert gen2["generation"] == 2 and gen2["parent_code"] == "OPM8_S1M01-1_001"
    gp = await _cultivar(client, cu_h, "GP", "Grape Pie")
    gp_prod = await _approved_product(client, admin_headers, gp["id"])
    r = await client.post("/cultivation/mothers", json={
        "product_id": gp_prod["id"], "campaign_id": camp["id"], "parent_id": first["id"]},
        headers=cu_h)
    assert r.status_code == 422 and "specification strain" in r.text

    # An id names exactly one plant.
    r = await client.post("/cultivation/mothers", json={
        "product_id": prod["id"], "campaign_id": camp["id"], "mother_no": 1, "stock_no": 1},
        headers=cu_h)
    assert r.status_code == 409 and "OPM8_S1M01-1_001" in r.text
    # A draft page cannot name a plant: its nominal — the 8 in OPM8 — can change.
    from tests.test_products import _product
    draft = await _product(client, admin_headers, cv["id"], "OPM_THC10:CBD1", 10)
    r = await client.post("/cultivation/mothers",
                          json={"product_id": draft["id"], "campaign_id": camp["id"]},
                          headers=cu_h)
    assert r.status_code == 422 and "DRAFT" in r.text


async def test_mother_status_moves_and_a_destroyed_plant_stays_destroyed(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    room = await _room(client, admin_headers, "mother_2", "Mother room 2")
    m = await _mother(client, cu_h, prod["id"], camp["id"], room_id=room["id"], position="pot 3")

    assert (await client.patch(f"/cultivation/mothers/{m['id']}", json={"position": "pot 4"},
                               headers=qc_h)).status_code == 403
    r = await client.patch(f"/cultivation/mothers/{m['id']}", json={"status": "retired"},
                           headers=cu_h)
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

    active = (await client.get("/cultivation/mothers", headers=cu_h)).json()
    assert m["id"] not in [x["id"] for x in active["mothers"]]
    every = (await client.get("/cultivation/mothers?active=false", headers=cu_h)).json()
    assert m["id"] in [x["id"] for x in every["mothers"]]

    assert (await client.patch(f"/cultivation/mothers/{m['id']}", json={"status": "destroyed"},
                               headers=cu_h)).status_code == 200
    assert (await client.patch(f"/cultivation/mothers/{m['id']}", json={"status": "active"},
                               headers=cu_h)).status_code == 409
    assert (await client.patch(f"/cultivation/mothers/{m['id']}", json={"status": "eaten"},
                               headers=cu_h)).status_code == 422


async def test_a_clone_run_is_initiated_by_cultivation_or_qa_and_names_its_product(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    _, qa_h = await _actor(client, admin_headers, "QA_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    clone_room = await _room(client, admin_headers, "clone_1", "Clone room 1", kind="clone")

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
    # No product named is a fact the run states with null, not a refusal.
    assert run["product_id"] is None and run["product_code"] is None

    r = await client.post("/cultivation/clone-runs", json={**body, "product_id": prod["id"]},
                          headers=cu_h)
    assert r.status_code == 201, r.text
    assert r.json()["product_code"] == "GP_THC26:CBD1" and r.json()["product_status"] == "APPROVED"

    other = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    other_prod = await _approved_product(client, admin_headers, other["id"], "OPM_THC22:CBD1", 22)
    r = await client.post("/cultivation/clone-runs", json={**body, "product_id": other_prod["id"]},
                          headers=cu_h)
    assert r.status_code == 422 and "not this cultivar's product" in r.text

    r = await client.post("/cultivation/clone-runs",
                          json={"cultivar_id": cv["id"], "planned_count": 10}, headers=cu_h)
    assert r.json()["started_on"] == facility_today().isoformat()
    assert len((await client.get("/cultivation/clone-runs", headers=qc_h)).json()["runs"]) == 3


async def test_a_run_numbers_its_cuttings_and_the_bank_derives_last_cut_and_times_cut(client, admin_headers):
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    gp = await _cultivar(client, cu_h, "GP", "Grape Pie")
    opm = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    gp_prod = await _approved_product(client, admin_headers, gp["id"])
    opm_prod = await _approved_product(client, admin_headers, opm["id"], "OPM_THC22:CBD1", 22)
    camp = await _campaign(client, cu_h)
    m1 = await _mother(client, cu_h, gp_prod["id"], camp["id"])
    m2 = await _mother(client, cu_h, gp_prod["id"], camp["id"])
    other = await _mother(client, cu_h, opm_prod["id"], camp["id"])
    retired = await _mother(client, cu_h, gp_prod["id"], camp["id"])
    await client.patch(f"/cultivation/mothers/{retired['id']}", json={"status": "retired"},
                       headers=cu_h)

    base = {"cultivar_id": gp["id"], "planned_count": 100, "started_on": "2026-09-06"}
    # A mother of another strain, a retired mother, a mother listed twice —
    # each refused by name, before anything is written.
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        **base, "mothers": [{"mother_plant_id": other["id"], "cuttings": 5}]})
    assert r.status_code == 422 and other["code"] in r.text
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
    assert [m["code"] for m in run["mothers"]] == [m1["code"], m2["code"]]
    assert run["cuttings_total"] == 100
    # Each mother's FIRST cutting is 01 — the xx in every clone's own id.
    assert {m["code"]: m["cutting_no"] for m in run["mothers"]} == {m1["code"]: 1, m2["code"]: 1}

    bank = {m["code"]: m for m in
            (await client.get("/cultivation/mothers", headers=cu_h)).json()["mothers"]}
    assert bank[m1["code"]]["last_cut_on"] == "2026-09-06"
    assert bank[m1["code"]]["times_cut"] == 1 and bank[m1["code"]]["cuttings_total"] == 60
    assert bank[m2["code"]]["cuttings_total"] == 40

    # A later run from one of them: its SECOND cutting, last cut moves forward.
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        **base, "started_on": "2026-09-20",
        "mothers": [{"mother_plant_id": m1["id"], "cuttings": 30}]})
    assert r.status_code == 201
    assert r.json()["mothers"][0]["cutting_no"] == 2
    bank = {m["code"]: m for m in
            (await client.get("/cultivation/mothers", headers=cu_h)).json()["mothers"]}
    assert bank[m1["code"]]["times_cut"] == 2 and bank[m1["code"]]["last_cut_on"] == "2026-09-20"
    assert bank[m2["code"]]["times_cut"] == 1 and bank[m2["code"]]["last_cut_on"] == "2026-09-06"


async def test_a_mother_shows_what_its_specification_strain_has_tested(client, admin_headers):
    """The owner asked for the potency tested so far for the mother's strain —
    an average and the individual values — with the subset traceable to this
    plant reported separately, because that is a stronger and rarer claim."""
    from tests.test_qc import _computed_spec, _release_with_components
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m = await _mother(client, cu_h, prod["id"], camp["id"])

    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="MOTHER-POT")
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "L-M1",
                                   a_val=2.0, b_val=25.06)      # 23.98
    r = await client.post("/qc/coq", json={"batch_id": "L-M1", "specification_id": spec["id"],
                                           "product_id": prod["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert (await client.post(f"/qc/coq/{r.json()['id']}/review", headers=qc2)).status_code == 200

    body = (await client.get(f"/cultivation/mothers/{m['id']}/potency", headers=cu_h)).json()
    assert body["code"] == m["code"] and body["product_code"] == "GP_THC26:CBD1"
    assert body["window"] == [23.40, 28.59]
    assert body["product"]["n"] == 1 and round(body["product"]["avg"], 2) == 23.98
    assert body["product"]["values"][0]["lot_code"] == "L-M1"
    # Nothing links this lot to THIS plant, so the traced figure stays empty
    # rather than borrowing the strain's number.
    assert body["traced"] == {"n": 0, "avg": None, "min": None, "max": None, "values": []}

    # The bank row carries the same strain-level figure.
    row = next(x for x in (await client.get("/cultivation/mothers", headers=cu_h)).json()["mothers"]
               if x["id"] == m["id"])
    assert row["tested"]["n"] == 1 and round(row["tested"]["avg"], 2) == 23.98


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

    r2 = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": gp["id"], "planned_count": 10})
    rid = r2.json()["id"]
    assert (await client.patch(f"/cultivation/clone-runs/{rid}",
                               json={"batch_id": opm_batch["id"]}, headers=cu_h)).status_code == 422
    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"batch_id": gp_batch["id"]},
                           headers=cu_h)
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
    r = await client.post("/cultivation/clone-runs", headers=qa_h, json={
        "cultivar_id": cv["id"], "planned_count": 5, "code": "CR_001"})
    assert r.status_code == 409

    assert (await client.patch(f"/cultivation/clone-runs/{rid}", json={"note": "x"},
                               headers=qc_h)).status_code == 403
    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"planned_count": 120},
                           headers=cu_h)
    assert r.status_code == 200 and r.json()["planned_count"] == 120

    r = await client.patch(f"/cultivation/clone-runs/{rid}", json={"status": "transplanted"},
                           headers=cu_h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "transplanted"
    assert r.json()["finished_on"] == facility_today().isoformat()
    assert rid not in [x["id"] for x in
                       (await client.get("/cultivation/clone-runs", headers=cu_h)).json()["runs"]]
    assert rid in [x["id"] for x in
                   (await client.get("/cultivation/clone-runs?active=false",
                                     headers=cu_h)).json()["runs"]]
    assert (await client.patch(f"/cultivation/clone-runs/{rid}", json={"note": "late"},
                               headers=cu_h)).status_code == 409
    assert (await client.patch(f"/cultivation/clone-runs/{rid}", json={"status": "started"},
                               headers=cu_h)).status_code == 409
    assert (await client.patch("/cultivation/clone-runs/not-a-uuid", json={"note": "x"},
                               headers=cu_h)).status_code == 404
