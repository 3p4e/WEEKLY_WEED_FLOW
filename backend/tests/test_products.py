"""The official ImB product catalogue — qc_products + app/api/qc/products.py.

The owner confirmed on 2026-09-05 that the two ImB Specification documents are
official "regarding the strains and potency ranges and grades and codes". Those
pages are per product (one strain at one nominal Total Δ9-THC, window ± 10 %
relative), which the per-cultivar tier ladder cannot express. These tests pin
what the catalogue is allowed to do that the ladder was not, what it inherits
from the ladder unchanged (authoring, segregation of duties, one live version),
and what "tested so far" counts.
"""
from tests.conftest import create_user, login_and_set_password
from tests.test_qc import _actor, _computed_spec, _release_with_components


async def _cultivar(client, headers, code="GP", name="Grape Pie"):
    r = await client.post("/cultivation/cultivars", json={"code": code, "name": name},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _product(client, headers, cultivar_id, code="GP_THC26:CBD1", grade=26, **extra):
    r = await client.post("/qc/products", json={"cultivar_id": cultivar_id,
                                                "product_code": code, "grade": grade, **extra},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _approved(client, admin_headers, cultivar_id, code="GP_THC26:CBD1", grade=26):
    """Author as admin, approve as a QC manager — the approver must differ."""
    p = await _product(client, admin_headers, cultivar_id, code, grade)
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/products/{p['id']}/approve", headers=qc2)
    assert r.status_code == 200, r.text
    return r.json()


async def test_a_product_carries_the_page_verbatim_and_defaults_its_window(client, admin_headers):
    cv = await _cultivar(client, admin_headers)
    p = await _product(client, admin_headers, cv["id"])
    assert p["product_code"] == "GP_THC26:CBD1" and p["grade"] == 26.0
    assert p["nominal_pct"] == 26.0
    # ± 10 % relative, exactly as the page prints it.
    assert p["window_min"] == 23.40 and p["window_max"] == 28.59
    assert p["doc_code"] == "QCSP 001" and p["doc_version"] == "v.03"
    assert p["status"] == "DRAFT" and p["cultivar_code"] == "GP"
    # "tested so far" is a read-side aggregate; the write echoes the row only.
    assert "tested" not in p
    row = next(r for r in (await client.get("/qc/products", headers=admin_headers)).json()
               if r["id"] == p["id"])
    assert row["tested"] == {"n": 0, "avg": None, "min": None, "max": None}


async def test_a_window_may_reach_above_thirty_percent(client, admin_headers):
    """CJ_THC28's window tops at 30.79. The ladder validator refused anything
    over 30.00 — the catalogue must not, or the official page is unrecordable."""
    cv = await _cultivar(client, admin_headers, code="CJ", name="Cap Junky")
    p = await _product(client, admin_headers, cv["id"], "CJ_THC28:CBD1", 28)
    assert p["window_min"] == 25.20 and p["window_max"] == 30.79


async def test_a_product_code_must_name_its_own_strain(client, admin_headers):
    """The mother-plant ID is built from the product code's head (GP26…), so a
    product filed under the wrong cultivar would print a wrong plant id
    forever."""
    gp = await _cultivar(client, admin_headers)
    r = await client.post("/qc/products", json={"cultivar_id": gp["id"],
                                                "product_code": "OPM_THC22:CBD1", "grade": 22},
                          headers=admin_headers)
    assert r.status_code == 422 and "does not belong to GP" in r.text
    r = await client.post("/qc/products", json={"cultivar_id": gp["id"],
                                                "product_code": "not a code", "grade": 26},
                          headers=admin_headers)
    assert r.status_code == 422 and "GP_THC26:CBD1" in r.text


async def test_several_products_of_one_strain_coexist_with_overlapping_windows(client, admin_headers):
    """The ladder allowed ONE approved row per cultivar and forbade overlap.
    A strain sells as several products at once and their windows overlap
    (GP26 23.40–28.59 and GP24 21.60–26.39) — both must be approved together."""
    cv = await _cultivar(client, admin_headers)
    a = await _approved(client, admin_headers, cv["id"], "GP_THC26:CBD1", 26)
    b = await _approved(client, admin_headers, cv["id"], "GP_THC24:CBD1", 24)
    rows = (await client.get(f"/qc/products?cultivar_id={cv['id']}&status=APPROVED",
                             headers=admin_headers)).json()
    assert {r["product_code"] for r in rows} == {a["product_code"], b["product_code"]}
    assert b["window_min"] < a["window_max"], "the two windows genuinely overlap"


async def test_approval_needs_a_second_person_and_retires_the_previous_version(client, admin_headers):
    cv = await _cultivar(client, admin_headers)
    p = await _product(client, admin_headers, cv["id"])
    r = await client.post(f"/qc/products/{p['id']}/approve", headers=admin_headers)
    assert r.status_code == 403 and "segregation of duties" in r.text.lower()
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/products/{p['id']}/approve", headers=qc2)
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    assert r.json()["effective_date"] is not None
    assert (await client.post(f"/qc/products/{p['id']}/approve", headers=qc2)).status_code == 409
    # An approved page is superseded by a new version, never edited in place.
    assert (await client.patch(f"/qc/products/{p['id']}", json={"notes": "x"},
                               headers=admin_headers)).status_code == 409
    v4 = await _product(client, admin_headers, cv["id"], "GP_THC26:CBD1", 26, doc_version="v.04")
    assert (await client.post(f"/qc/products/{v4['id']}/approve", headers=qc2)).status_code == 200
    old = (await client.get(f"/qc/products/{p['id']}", headers=admin_headers)).json()["product"]
    assert old["status"] == "SUPERSEDED"


async def test_approving_a_product_retires_the_cultivars_ladder(client, admin_headers):
    """Two live grade schemes would be two answers to one question. The first
    approved product for a strain takes grading over from its ladder."""
    from tests.test_potency import _cultivar as _cv, _ladder
    cv = await _cv(client, admin_headers, code="GP", name="Grape Pie")
    ladder = await _ladder(client, admin_headers, cv["id"], version="v5.2")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/potency-specs/{ladder['id']}/approve",
                              headers=qc2)).status_code == 200
    p = await _product(client, admin_headers, cv["id"])
    r = await client.post(f"/qc/products/{p['id']}/approve", headers=qc2)
    assert r.status_code == 200
    after = (await client.get(f"/qc/potency-specs/{ladder['id']}", headers=admin_headers)).json()
    assert after["spec"]["status"] == "SUPERSEDED"


async def test_role_gating(client, admin_headers):
    cv = await _cultivar(client, admin_headers)
    p = await _product(client, admin_headers, cv["id"])
    _, user_h = await _actor(client, admin_headers, "USER")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.get("/qc/products", headers=user_h)).status_code == 403
    assert (await client.get("/qc/products", headers=cu_h)).status_code == 200
    assert (await client.post("/qc/products", json={"cultivar_id": cv["id"],
                                                    "product_code": "GP_THC20:CBD1", "grade": 20},
                              headers=cu_h)).status_code == 403
    assert (await client.post(f"/qc/products/{p['id']}/approve", headers=cu_h)).status_code == 403
    assert (await client.post("/qc/products/import", json={"dry_run": True},
                              headers=cu_h)).status_code == 403
    assert (await client.get("/qc/products", headers=qc_h)).status_code == 200


async def test_conformance_lists_every_product_a_value_satisfies(client, admin_headers):
    """The ladder answered "which tier?" — exactly one. The catalogue's windows
    overlap, so the honest answer is a list; which product a lot ships as is a
    packaging decision, not something a measurement settles."""
    cv = await _cultivar(client, admin_headers)
    p26 = await _approved(client, admin_headers, cv["id"], "GP_THC26:CBD1", 26)
    await _approved(client, admin_headers, cv["id"], "GP_THC24:CBD1", 24)
    await _approved(client, admin_headers, cv["id"], "GP_THC18:CBD1", 18)

    async def ask(v, product_id=None):
        q = f"/qc/products/conformance?cultivar_id={cv['id']}&total_d9_thc={v}"
        if product_id:
            q += f"&product_id={product_id}"
        r = await client.get(q, headers=admin_headers)
        assert r.status_code == 200, r.text
        return r.json()

    # 24.00 sits inside both GP26 (23.40–28.59) and GP24 (21.60–26.39).
    body = await ask(24.0)
    assert body["matching"] == ["GP_THC26:CBD1", "GP_THC24:CBD1"]
    assert body["nearest"] == "GP_THC26:CBD1"
    # The bounds are inclusive, to the decimal the page prints: 23.40 is GP26's
    # floor (and still inside GP24), 28.59 its ceiling, 28.60 outside everything.
    assert "GP_THC26:CBD1" in (await ask(23.40))["matching"]
    assert "GP_THC26:CBD1" not in (await ask(23.39))["matching"]
    assert (await ask(28.59))["matching"] == ["GP_THC26:CBD1"]
    assert (await ask(28.60))["matching"] == []
    # A value below every window conforms to nothing, and says so plainly.
    out = await ask(5.0)
    assert out["matching"] == [] and out["nearest"] is None
    # Asked about one product, it answers about that product.
    out = await ask(24.0, p26["id"])
    assert out["product"]["product_code"] == "GP_THC26:CBD1" and out["product"]["conforms"] is True
    out = await ask(19.0, p26["id"])
    assert out["product"]["conforms"] is False


async def test_potency_history_separates_product_cultivar_and_certificate_evidence(client, admin_headers):
    """"Tested so far" is three different strengths of evidence and they are
    never merged: a CoQ that named the product, a CoQ that named only the
    strain, and a certificate reached through the batch code."""
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")   # reviews the CoQ
    cv = await _cultivar(client, admin_headers)
    prod = await _approved(client, admin_headers, cv["id"])
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-HIST")
    # Total Δ9-THC = 2.0 + 0.877 × 25.06 = 23.98 → inside GP26's window.
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "L-PROD",
                                   a_val=2.0, b_val=25.06)
    r = await client.post("/qc/coq", json={"batch_id": "L-PROD", "specification_id": spec["id"],
                                           "product_id": prod["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    coq = r.json()
    assert coq["product_id"] == prod["id"]
    # A DRAFT CoQ is not evidence yet.
    hist = (await client.get(f"/qc/products/{prod['id']}", headers=admin_headers)).json()
    assert hist["tested"]["n"] == 0
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc2)).status_code == 200

    hist = (await client.get(f"/qc/products/{prod['id']}/potency-history",
                             headers=admin_headers)).json()
    assert hist["tested"]["n"] == 1 and round(hist["tested"]["avg"], 2) == 23.98
    assert hist["tested"]["values"][0]["conforms"] is True
    assert hist["tested"]["values"][0]["lot_code"] == "L-PROD"
    # A CoQ that names only the cultivar is counted separately, never inside.
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "L-CV",
                                   a_val=1.0, b_val=20.0)
    r = await client.post("/qc/coq", json={"batch_id": "L-CV", "specification_id": spec["id"],
                                           "cultivar_id": cv["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert (await client.post(f"/qc/coq/{r.json()['id']}/review", headers=qc2)).status_code == 200
    hist = (await client.get(f"/qc/products/{prod['id']}", headers=admin_headers)).json()
    assert hist["tested"]["n"] == 1, "a cultivar-level CoQ is not product evidence"
    assert hist["cultivar_level"]["n"] == 1
    assert round(hist["cultivar_level"]["avg"], 2) == round(1.0 + 0.877 * 20.0, 2)


async def test_the_packaged_catalogue_imports_the_owners_pages_once(client, admin_headers):
    r = await client.post("/qc/products/import", json={"dry_run": True}, headers=admin_headers)
    assert r.status_code == 200, r.text
    dry = r.json()
    assert dry["dry_run"] is True and dry["doc_version"] == "v.03"
    assert len(dry["created"]) == 42, "42 distinct products across the 48 pages"
    assert len({c["strain"] for c in dry["created"]}) == 22
    assert dry["conflicts"] == []
    assert len(dry["cultivars_created"]) == 22
    # A dry run writes nothing.
    assert (await client.get("/qc/products", headers=admin_headers)).json() == []

    r = await client.post("/qc/products/import", json={}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["created"]) == 42 and body["conflicts"] == []
    rows = (await client.get("/qc/products", headers=admin_headers)).json()
    assert len(rows) == 42 and all(p["status"] == "DRAFT" for p in rows)
    gp26 = next(p for p in rows if p["product_code"] == "GP_THC26:CBD1")
    assert gp26["window_min"] == 23.40 and gp26["window_max"] == 28.59
    assert "Tran02" in gp26["source"] and "QCSP 001 v.03" in gp26["source"]
    # Every imported window is the page's ± 10 % rule.
    for p in rows:
        assert p["window_min"] == round(p["nominal_pct"] * 0.9, 2)
        assert p["window_max"] == round(round(p["nominal_pct"] * 1.1, 2) - 0.01, 2)

    again = (await client.post("/qc/products/import", json={}, headers=admin_headers)).json()
    assert again["created"] == [] and len(again["skipped"]) == 42
    assert len((await client.get("/qc/products", headers=admin_headers)).json()) == 42
