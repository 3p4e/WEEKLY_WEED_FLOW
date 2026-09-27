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

    # The date of cloning initiation has no default: the initiator sets it
    # (owner, 2026-09-05; review AD-19).
    r = await client.post("/cultivation/clone-runs",
                          json={"cultivar_id": cv["id"], "planned_count": 10}, headers=cu_h)
    assert r.status_code == 422, r.text
    assert len((await client.get("/cultivation/clone-runs", headers=qc_h)).json()["runs"]) == 2


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
    # The STRAIN's history is what the owner asked for: the same lot, counted
    # once, labelled by its source.
    assert body["strain"]["n"] == 1 and body["strain"]["values"][0]["source"] == "coq_product"
    assert body["sources"]["coq_product"]["n"] == 1
    assert body["sources"]["coq_cultivar"]["n"] == 0 and body["sources"]["certificate"]["n"] == 0
    # Nothing links this lot to THIS plant, so the traced figure stays empty
    # rather than borrowing the strain's number.
    assert body["traced"] == {"n": 0, "avg": None, "min": None, "max": None, "values": []}

    # The bank row carries the same strain-level figure.
    row = next(x for x in (await client.get("/cultivation/mothers", headers=cu_h)).json()["mothers"]
               if x["id"] == m["id"])
    assert row["tested"]["n"] == 1 and round(row["tested"]["avg"], 2) == 23.98


async def test_a_mother_counts_its_strains_certificates_by_batch_code_head(client, admin_headers):
    """Review 2026-09-27b, INV-09: the mother bank's certificate source is the
    catalogue's own (qc/products.py certificate_total_thc). Its private copy
    joined stored Total THC rows, which QC-10 refuses, so a released
    certificate never reached a mother. Now the total is derived from the
    components and the lot is attributed by the batch-code head."""
    from tests.test_qc import _computed_spec, _release_with_components
    _, qp = await _actor(client, admin_headers, "QP")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m = await _mother(client, cu_h, prod["id"], camp["id"])
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="MOTHER-CERT")
    # 2.0 + 0.877 × 25.06 = 23.98, on a GP-headed lot, certificate only (no CoQ)
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "GP092601",
                                   a_val=2.0, b_val=25.06)
    # another strain's lot is not this mother's evidence
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "OPM092601",
                                   a_val=1.0, b_val=20.0)

    body = (await client.get(f"/cultivation/mothers/{m['id']}/potency", headers=cu_h)).json()
    cert = body["sources"]["certificate"]
    assert cert["n"] == 1 and round(cert["avg"], 2) == 23.98, cert
    assert cert["values"][0]["lot_code"] == "GP092601"
    assert body["strain"]["n"] == 1 and body["strain"]["values"][0]["source"] == "certificate"
    # The catalogue reports the same certificate from the same function.
    hist = (await client.get(f"/qc/products/{prod['id']}/potency-history",
                             headers=admin_headers)).json()
    assert hist["certificate_level"]["n"] == 1
    assert round(hist["certificate_level"]["avg"], 2) == round(cert["avg"], 2)


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
        "cultivar_id": gp["id"], "planned_count": 2000, "batch_id": opm_batch["id"],
        "started_on": "2026-09-06"})
    assert r.status_code == 422 and "OPM092601" in r.text
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": gp["id"], "planned_count": 2000, "batch_id": gp_batch["id"],
        "started_on": "2026-09-06"})
    assert r.status_code == 201, r.text
    assert r.json()["batch_code"] == "GP092601"

    r2 = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": gp["id"], "planned_count": 10, "started_on": "2026-09-06"})
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
        "cultivar_id": cv["id"], "planned_count": 100, "code": "CR_001",
        "started_on": "2026-09-06"})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    r = await client.post("/cultivation/clone-runs", headers=qa_h, json={
        "cultivar_id": cv["id"], "planned_count": 5, "code": "CR_001",
        "started_on": "2026-09-06"})
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


# ── the 2026-09-27 review: CS-03, CS-04, CS-05, CS-10, CS-12, CS-14, CS-15 ───

async def test_a_later_generation_keeps_its_parents_campaign_and_mother_number(client, admin_headers):
    """CS-03. "all clones made from this -2 (second) cloning generation of
    motherplant selection S1M03 will have codes like GP26_S1M03-2_020": the
    line is inherited from the parent, and a body that says otherwise is
    refused rather than quietly registering M05."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    s1 = await _campaign(client, cu_h)
    s2 = await _campaign(client, cu_h, "clones")
    for _ in range(2):
        await _mother(client, cu_h, prod["id"], s1["id"])
    m3 = await _mother(client, cu_h, prod["id"], s1["id"])
    assert m3["code"] == "GP26_S1M03-1_001"

    # Campaign and mother number left out: taken from the parent.
    gen2 = await client.post("/cultivation/mothers",
                             json={"product_id": prod["id"], "parent_id": m3["id"]}, headers=cu_h)
    assert gen2.status_code == 201, gen2.text
    assert gen2.json()["code"] == "GP26_S1M03-2_001"
    assert gen2.json()["campaign_id"] == s1["id"] and gen2.json()["mother_no"] == 3
    # Stated and agreeing: fine, and the stock number counts on within -2.
    r = await client.post("/cultivation/mothers", json={
        "product_id": prod["id"], "campaign_id": s1["id"], "mother_no": 3,
        "parent_id": m3["id"]}, headers=cu_h)
    assert r.status_code == 201 and r.json()["code"] == "GP26_S1M03-2_002"
    # Contradicting the parent: refused.
    r = await client.post("/cultivation/mothers", json={
        "product_id": prod["id"], "campaign_id": s2["id"], "parent_id": m3["id"]}, headers=cu_h)
    assert r.status_code == 422 and "campaign" in r.text
    r = await client.post("/cultivation/mothers", json={
        "product_id": prod["id"], "mother_no": 5, "parent_id": m3["id"]}, headers=cu_h)
    assert r.status_code == 422 and "M03" in r.text
    # No parent and no campaign is nothing to number from.
    r = await client.post("/cultivation/mothers", json={"product_id": prod["id"]}, headers=cu_h)
    assert r.status_code == 422 and "campaign_id" in r.text


async def test_a_mother_number_names_one_line_per_campaign(client, admin_headers):
    """CS-04. M01 of S1 is a Grape Pie 26 line: an OPM mother cannot take the
    number, and an auto-numbered OPM mother takes the campaign's NEXT number.
    A campaign opened for one strain refuses another strain's mothers."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    gp = await _cultivar(client, cu_h, "GP", "Grape Pie")
    opm = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    gp_prod = await _approved_product(client, admin_headers, gp["id"])
    opm_prod = await _approved_product(client, admin_headers, opm["id"], "OPM_THC22:CBD1", 22)
    camp = await _campaign(client, cu_h)
    m1 = await _mother(client, cu_h, gp_prod["id"], camp["id"])
    assert m1["code"] == "GP26_S1M01-1_001"

    r = await client.post("/cultivation/mothers", json={
        "product_id": opm_prod["id"], "campaign_id": camp["id"], "mother_no": 1}, headers=cu_h)
    assert r.status_code == 422 and "GP_THC26:CBD1" in r.text
    r = await client.get(f"/cultivation/mothers/next-code?product_id={opm_prod['id']}"
                         f"&campaign_id={camp['id']}&mother_no=1", headers=cu_h)
    assert r.status_code == 422, "the suggestion refuses the same line the save would"
    other = await _mother(client, cu_h, opm_prod["id"], camp["id"])
    assert other["code"] == "OPM22_S1M02-1_001"
    # The same line, a second stock plant: still GP's, still fine.
    assert (await _mother(client, cu_h, gp_prod["id"], camp["id"], mother_no=1))["code"] == "GP26_S1M01-1_002"

    gp_only = await _campaign(client, cu_h, "phenotypes", cultivar_id=gp["id"])
    r = await client.post("/cultivation/mothers", json={
        "product_id": opm_prod["id"], "campaign_id": gp_only["id"]}, headers=cu_h)
    assert r.status_code == 422 and "another strain" in r.text


async def test_two_registrations_at_once_take_different_numbers(client, admin_headers):
    """CS-04. The next-number read runs under an advisory lock per campaign,
    so two mothers registered at the same moment become M01 and M02 — never
    both M01 with one of them a 500."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    gp = await _cultivar(client, cu_h, "GP", "Grape Pie")
    opm = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    gp_prod = await _approved_product(client, admin_headers, gp["id"])
    opm_prod = await _approved_product(client, admin_headers, opm["id"], "OPM_THC22:CBD1", 22)
    camp = await _campaign(client, cu_h)
    import asyncio
    a, b = await asyncio.gather(
        client.post("/cultivation/mothers", json={"product_id": gp_prod["id"],
                                                  "campaign_id": camp["id"]}, headers=cu_h),
        client.post("/cultivation/mothers", json={"product_id": opm_prod["id"],
                                                  "campaign_id": camp["id"]}, headers=cu_h))
    assert a.status_code == 201 and b.status_code == 201, (a.text, b.text)
    assert {a.json()["mother_no"], b.json()["mother_no"]} == {1, 2}


async def test_number_caps_are_refused_with_a_reason_not_a_500(client, admin_headers):
    """CS-10. Mother numbers stop at 99, stock numbers at 999, generations at
    9 — typed or derived from a parent — and each cap answers 422."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    last = await _mother(client, cu_h, prod["id"], camp["id"], mother_no=99)
    assert last["code"] == "GP26_S1M99-1_001"
    r = await client.post("/cultivation/mothers",
                          json={"product_id": prod["id"], "campaign_id": camp["id"]}, headers=cu_h)
    assert r.status_code == 422 and "M99" in r.text
    r = await client.get(f"/cultivation/mothers/next-code?product_id={prod['id']}"
                         f"&campaign_id={camp['id']}", headers=cu_h)
    assert r.status_code == 422
    await _mother(client, cu_h, prod["id"], camp["id"], mother_no=99, stock_no=999)
    r = await client.post("/cultivation/mothers", json={
        "product_id": prod["id"], "campaign_id": camp["id"], "mother_no": 99}, headers=cu_h)
    assert r.status_code == 422 and "999" in r.text
    g9 = await _mother(client, cu_h, prod["id"], camp["id"], mother_no=1, generation=9)
    r = await client.post("/cultivation/mothers", json={
        "product_id": prod["id"], "parent_id": g9["id"]}, headers=cu_h)
    assert r.status_code == 422 and "generation" in r.text
    assert (await client.post("/cultivation/mothers", json={
        "product_id": prod["id"], "campaign_id": camp["id"], "mother_no": 100},
        headers=cu_h)).status_code == 422


async def test_the_ids_head_is_the_products_acronym_on_both_sides(client, admin_headers):
    """CS-12. The server composes the id from the product code's acronym and
    tells the form what it used, so the preview and the saved id share one
    source."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h, "OPM", "Orange Punch Mimosa")
    prod = await _approved_product(client, admin_headers, cv["id"], "OPM_THC8:CBD1", 8)
    camp = await _campaign(client, cu_h)
    r = (await client.get(f"/cultivation/mothers/next-code?product_id={prod['id']}"
                          f"&campaign_id={camp['id']}", headers=cu_h)).json()
    assert r["acronym"] == "OPM" and r["head"] == "OPM8_S1M01-1_"
    m = await _mother(client, cu_h, prod["id"], camp["id"])
    assert m["code"] == r["suggested"] == "OPM8_S1M01-1_001"
    # status_since is the FACILITY day, bound explicitly, not the UTC default.
    assert m["status_since"] == facility_today().isoformat()


async def test_an_empty_id_is_refused_rather_than_crashing(client, admin_headers):
    """CS-15. `room_id: ""` and `batch_id: ""` are malformed ids, not "clear
    it": they answer 422, while an explicit null still clears."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    room = await _room(client, admin_headers, "mother_e", "Mother E")
    m = await _mother(client, cu_h, prod["id"], camp["id"], room_id=room["id"])
    assert (await client.patch(f"/cultivation/mothers/{m['id']}", json={"room_id": ""},
                               headers=cu_h)).status_code == 422
    r = await client.patch(f"/cultivation/mothers/{m['id']}", json={"room_id": None}, headers=cu_h)
    assert r.status_code == 200 and r.json()["room_id"] is None
    run = (await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 5, "started_on": "2026-09-06",
        "room_id": room["id"]})).json()
    for body in ({"batch_id": ""}, {"room_id": ""}):
        assert (await client.patch(f"/cultivation/clone-runs/{run['id']}", json=body,
                                   headers=cu_h)).status_code == 422, body
    r = await client.patch(f"/cultivation/clone-runs/{run['id']}", json={"room_id": None},
                           headers=cu_h)
    assert r.status_code == 200 and r.json()["room_id"] is None


async def test_a_batch_with_plants_freezes_its_runs(client, admin_headers):
    """CS-05. Clone ids are numbered from the batch's runs laid end to end, so
    once any plant exists the run set is fixed: no new run may join the batch,
    and a run may not be moved away from or into it."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    prod = await _approved_product(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m = await _mother(client, cu_h, prod["id"], camp["id"])
    room = await _room(client, admin_headers, "clone_frz", "Clone FRZ", kind="clone")
    x = (await client.post("/cultivation/batches", headers=cu_h, json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092601",
        "plant_count": 4, "phase": "clone"})).json()
    y = (await client.post("/cultivation/batches", headers=cu_h, json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092602",
        "plant_count": 4, "phase": "clone"})).json()
    run = (await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 4, "started_on": "2026-09-01",
        "batch_id": x["id"], "mothers": [{"mother_plant_id": m["id"], "cuttings": 4}]})).json()
    loose = (await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 2, "started_on": "2026-08-30"})).json()
    g = await client.post(f"/cultivation/batches/{x['id']}/plants", headers=cu_h)
    assert g.status_code == 200 and g.json()["complete"]

    # Relink the fed run to another batch, or unlink it: 409.
    r = await client.patch(f"/cultivation/clone-runs/{run['id']}", json={"batch_id": y["id"]},
                           headers=cu_h)
    assert r.status_code == 409 and "GP092601" in r.text
    r = await client.patch(f"/cultivation/clone-runs/{run['id']}", json={"batch_id": None},
                           headers=cu_h)
    assert r.status_code == 409
    # An earlier-dated run joining the filled batch would shift every segment.
    r = await client.patch(f"/cultivation/clone-runs/{loose['id']}", json={"batch_id": x["id"]},
                           headers=cu_h)
    assert r.status_code == 409
    r = await client.post("/cultivation/clone-runs", headers=cu_h, json={
        "cultivar_id": cv["id"], "planned_count": 1, "started_on": "2026-09-05",
        "batch_id": x["id"]})
    assert r.status_code == 409
    # The unfilled batch still takes runs, and a note on the fed run is fine.
    assert (await client.patch(f"/cultivation/clone-runs/{loose['id']}", json={"batch_id": y["id"]},
                               headers=cu_h)).status_code == 200
    assert (await client.patch(f"/cultivation/clone-runs/{run['id']}", json={"note": "rooted"},
                               headers=cu_h)).status_code == 200
    codes = [p["plant_code"] for p in
             (await client.get(f"/cultivation/batches/{x['id']}/plants", headers=cu_h)).json()["plants"]]
    assert codes == [f"{m['code']}-01.00{n}" for n in (1, 2, 3, 4)]


# ── the second review (2026-09-27): CS2-01 ───────────────────────────────────

async def test_a_reissued_catalogue_page_does_not_freeze_the_line(client, admin_headers):
    """CS2-01. Approving the fitted GP_THC26:CBD1 retires the v.03 row the
    line was opened against (qc/products.py, C-3). The line is the product
    CODE, not the row: generation 2 from M01 and a second stock plant on M01
    both register against the live page, the parent's own row is moved onto
    it, and the next-code preview no longer refuses the line. Another code
    is still refused, whatever its version."""
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv = await _cultivar(client, cu_h)
    v03 = await _approved_product(client, admin_headers, cv["id"])
    camp = await _campaign(client, cu_h)
    m1 = await _mother(client, cu_h, v03["id"], camp["id"])
    assert m1["code"] == "GP26_S1M01-1_001" and m1["product_id"] == v03["id"]

    fitted = await _approved_product(client, admin_headers, cv["id"], "GP_THC26:CBD1", 26,
                                     window=(24.6, 27.59), doc_version="fitted 2026-09-15")
    old = (await client.get(f"/qc/products/{v03['id']}", headers=admin_headers)).json()["product"]
    assert old["status"] == "SUPERSEDED", "the premise: a new version retires the old row"

    # Generation 2 from M01, no product named: the line's code, resolved to the live page.
    r = await client.post("/cultivation/mothers", json={"parent_id": m1["id"]}, headers=cu_h)
    assert r.status_code == 201, r.text
    gen2 = r.json()
    assert gen2["code"] == "GP26_S1M01-2_001"
    assert gen2["product_id"] == fitted["id"] and gen2["product_status"] == "APPROVED"
    assert gen2["parent_code"] == "GP26_S1M01-1_001"
    # Naming the live page is the same registration; naming the retired row is not a live product.
    r = await client.post("/cultivation/mothers", json={"product_id": fitted["id"],
                                                        "parent_id": m1["id"]}, headers=cu_h)
    assert r.status_code == 201 and r.json()["code"] == "GP26_S1M01-2_002", r.text
    r = await client.post("/cultivation/mothers", json={"product_id": v03["id"],
                                                        "parent_id": m1["id"]}, headers=cu_h)
    assert r.status_code == 422 and "SUPERSEDED" in r.text

    # A second stock plant on line M01: the suggestion and the save both take it.
    r = await client.get(f"/cultivation/mothers/next-code?product_id={fitted['id']}"
                         f"&campaign_id={camp['id']}&mother_no=1", headers=cu_h)
    assert r.status_code == 200, r.text
    assert r.json()["suggested"] == "GP26_S1M01-1_002"
    s2 = await _mother(client, cu_h, fitted["id"], camp["id"], mother_no=1)
    assert s2["code"] == "GP26_S1M01-1_002" and s2["product_id"] == fitted["id"]

    # The line's first mother now names the live page too — same product, new version.
    bank = {x["code"]: x for x in
            (await client.get("/cultivation/mothers", headers=cu_h)).json()["mothers"]}
    assert bank["GP26_S1M01-1_001"]["product_id"] == fitted["id"]
    assert bank["GP26_S1M01-1_001"]["product_status"] == "APPROVED"
    assert all(x["product_code"] == "GP_THC26:CBD1" for x in bank.values())

    # Another CODE cannot take the line, and a clone cannot change its code.
    # Its window stops below GP_THC26's 24.60: a strain's grades never overlap
    # within one document version (owner 2026-09-06; QR-09 enforces it).
    gp24 = await _approved_product(client, admin_headers, cv["id"], "GP_THC24:CBD1", 24,
                                   window=(22.6, 24.59), doc_version="fitted 2026-09-15")
    r = await client.post("/cultivation/mothers", json={
        "product_id": gp24["id"], "campaign_id": camp["id"], "mother_no": 1}, headers=cu_h)
    assert r.status_code == 422 and "GP_THC26:CBD1" in r.text
    r = await client.post("/cultivation/mothers", json={"product_id": gp24["id"],
                                                        "parent_id": m1["id"]}, headers=cu_h)
    assert r.status_code == 422 and "cannot change its specification strain" in r.text
    # No parent and no product is nothing to register against.
    r = await client.post("/cultivation/mothers", json={"campaign_id": camp["id"]}, headers=cu_h)
    assert r.status_code == 422 and "product_id" in r.text
    # A parent whose code has no live page any more cannot grow a generation.
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/products/{fitted['id']}/supersede",
                              headers=qc2)).status_code == 200
    r = await client.post("/cultivation/mothers", json={"parent_id": m1["id"]}, headers=cu_h)
    assert r.status_code == 422 and "no APPROVED page" in r.text
