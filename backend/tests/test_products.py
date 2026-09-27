"""The official product catalogue — qc_products + app/api/qc/products.py.

The owner confirmed on 2026-09-05 that the two ImB Specification documents are
official "regarding the strains and potency ranges and grades and codes". Those
pages are per product (one strain at one nominal Total Δ9-THC), which the
per-cultivar tier ladder cannot express. On 2026-09-06 he set the rules a
window must obey (at most ±10 % of the nominal, grades that do not overlap,
an out-of-window value falls to the next grade) and on 2026-09-18 retired the
flat ±10 % rule in favour of the fitted tolerances "everywhere". These tests
pin what the catalogue is allowed to do that the ladder was not, what it
inherits from the ladder unchanged (authoring, segregation of duties, one live
version), the window rules, the two importers, and what "tested so far" counts.
"""
from app.plantids import window_for
from tests.test_qc import _actor, _computed_spec, _release_with_components


async def _cultivar(client, headers, code="GP", name="Grape Pie"):
    r = await client.post("/cultivation/cultivars", json={"code": code, "name": name},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _product(client, headers, cultivar_id, code="GP_THC26:CBD1", grade=26, window=None,
                   **extra):
    """Author a product with an EXPLICIT window — by default the one the v.03
    page prints (window_for is reference-only; the API derives nothing)."""
    wmin, wmax = window or window_for(grade)
    r = await client.post("/qc/products", json={"cultivar_id": cultivar_id, "product_code": code,
                                                "grade": grade, "window_min": wmin,
                                                "window_max": wmax, **extra},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _approved(client, admin_headers, cultivar_id, code="GP_THC26:CBD1", grade=26,
                    window=None, **extra):
    """Author as admin, approve as a QC manager — the approver must differ."""
    p = await _product(client, admin_headers, cultivar_id, code, grade, window, **extra)
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/products/{p['id']}/approve", headers=qc2)
    assert r.status_code == 200, r.text
    return r.json()


# The owner's fitted Cap Junky ladder (Potency Spec Service, 2026-09-15 form):
# nominal ± tolerance → lo = N − t, hi = N + t − 0.01. Five grades, no overlap.
CJ_FITTED = [(14, 1.4), (17, 1.4), (20, 1.6), (24, 2.4), (28, 1.6)]


def _fitted_window(nominal, tol):
    return round(nominal - tol, 2), round(nominal + tol - 0.01, 2)


async def test_a_product_stores_the_window_it_is_given_and_derives_nothing(client, admin_headers):
    cv = await _cultivar(client, admin_headers)
    p = await _product(client, admin_headers, cv["id"])
    assert p["product_code"] == "GP_THC26:CBD1" and p["grade"] == 26.0
    assert p["nominal_pct"] == 26.0
    assert p["window_min"] == 23.40 and p["window_max"] == 28.59
    assert p["doc_code"] == "QCSP 001" and p["doc_version"] == "v.03"
    assert p["status"] == "DRAFT" and p["cultivar_code"] == "GP"
    # "tested so far" is a read-side aggregate; the write echoes the row only.
    assert "tested" not in p
    row = next(r for r in (await client.get("/qc/products", headers=admin_headers)).json()
               if r["id"] == p["id"])
    assert row["tested"] == {"n": 0, "avg": None, "min": None, "max": None}
    # Owner 2026-09-18: the window is explicit, never a ±10 % rule applied to
    # the nominal — a page without its window is not recordable.
    r = await client.post("/qc/products", json={"cultivar_id": cv["id"],
                                                "product_code": "GP_THC24:CBD1", "grade": 24},
                          headers=admin_headers)
    assert r.status_code == 422, r.text
    # A fitted window narrower than ±10 % is stored exactly as given.
    q = await _product(client, admin_headers, cv["id"], "GP_THC24:CBD1", 24, window=(22.0, 25.99))
    assert q["window_min"] == 22.0 and q["window_max"] == 25.99


async def test_a_window_may_reach_above_thirty_percent(client, admin_headers):
    """CJ_THC28's page window tops at 30.79. The ladder validator refused
    anything over 30.00 — the catalogue must not, or the official page is
    unrecordable."""
    cv = await _cultivar(client, admin_headers, code="CJ", name="Cap Junky")
    p = await _product(client, admin_headers, cv["id"], "CJ_THC28:CBD1", 28)
    assert p["window_min"] == 25.20 and p["window_max"] == 30.79


async def test_a_product_code_must_name_its_own_strain(client, admin_headers):
    """The mother-plant ID is built from the product code's head (GP26…), so a
    product filed under the wrong cultivar would print a wrong plant id
    forever."""
    gp = await _cultivar(client, admin_headers)
    r = await client.post("/qc/products", json={"cultivar_id": gp["id"], "grade": 22,
                                                "product_code": "OPM_THC22:CBD1",
                                                "window_min": 19.8, "window_max": 24.19},
                          headers=admin_headers)
    assert r.status_code == 422 and "does not belong to GP" in r.text
    r = await client.post("/qc/products", json={"cultivar_id": gp["id"], "grade": 26,
                                                "product_code": "not a code",
                                                "window_min": 23.4, "window_max": 28.59},
                          headers=admin_headers)
    assert r.status_code == 422 and "GP_THC26:CBD1" in r.text


async def test_code_grade_and_nominal_are_one_number(client, admin_headers):
    """QC-30: GP_THC26 → grade 26 → nominal 26.00 → mother id GP26…; a row where
    they disagree would print two different potencies for one product."""
    gp = await _cultivar(client, admin_headers)
    body = {"cultivar_id": gp["id"], "product_code": "GP_THC26:CBD1",
            "window_min": 23.4, "window_max": 28.59}
    r = await client.post("/qc/products", json={**body, "grade": 18}, headers=admin_headers)
    assert r.status_code == 422 and "THC number" in r.text
    r = await client.post("/qc/products", json={**body, "grade": 26, "nominal_pct": 24},
                          headers=admin_headers)
    assert r.status_code == 422 and "nominal" in r.text
    # The code is stored in its canonical spelling: 26.0 and 26 are one product.
    p = await _product(client, admin_headers, gp["id"], "GP_THC26.0:CBD1.0", 26)
    assert p["product_code"] == "GP_THC26:CBD1"
    r = await client.post("/qc/products", json={**body, "grade": 26}, headers=admin_headers)
    assert r.status_code == 409, "the canonical code is already on file"


async def test_a_window_may_not_exceed_ten_percent_of_the_nominal(client, admin_headers):
    """Owner 2026-09-06: the tolerance "can be a maximum of ±10 % of the nominal"
    (INS-13). The page's own form (nominal × 1.10 − 0.01) sits inside it."""
    gp = await _cultivar(client, admin_headers)
    body = {"cultivar_id": gp["id"], "product_code": "GP_THC26:CBD1", "grade": 26}
    r = await client.post("/qc/products", json={**body, "window_min": 10, "window_max": 40},
                          headers=admin_headers)
    assert r.status_code == 422 and "±10 %" in r.text
    r = await client.post("/qc/products", json={**body, "window_min": 23.39, "window_max": 28.59},
                          headers=admin_headers)
    assert r.status_code == 422, "2.61 below the nominal is over the ceiling of 2.60"
    p = await _product(client, admin_headers, gp["id"], window=(23.40, 28.60))
    assert p["window_max"] == 28.60, "exactly ±10 % is the ceiling, and allowed"


async def test_patch_is_validated_before_the_update(client, admin_headers):
    """QC-30: an inverted window used to hit the table's CHECK constraint and
    surface as a 500; a grade that no longer matches the code was stored."""
    gp = await _cultivar(client, admin_headers)
    p = await _product(client, admin_headers, gp["id"])
    r = await client.patch(f"/qc/products/{p['id']}", json={"window_max": 20.0}, headers=admin_headers)
    assert r.status_code == 422, r.text
    r = await client.patch(f"/qc/products/{p['id']}", json={"grade": 18}, headers=admin_headers)
    assert r.status_code == 422 and "THC number" in r.text
    r = await client.patch(f"/qc/products/{p['id']}", json={"window_min": 10.0}, headers=admin_headers)
    assert r.status_code == 422 and "±10 %" in r.text
    r = await client.patch(f"/qc/products/{p['id']}", json={"window_min": 24.0, "notes": "narrowed"},
                          headers=admin_headers)
    assert r.status_code == 200 and r.json()["window_min"] == 24.0 and r.json()["notes"] == "narrowed"


async def test_several_products_of_one_strain_coexist_with_overlapping_windows(client, admin_headers):
    """The ladder allowed ONE approved row per cultivar and forbade overlap.
    The issued v.03 pages sell a strain as several products at once and their
    windows overlap (GP26 23.40–28.59 and GP24 21.60–26.39) — both must be
    recordable and approved together, because that is what the document says."""
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


async def test_approving_a_new_document_version_retires_the_strains_old_version(client, admin_headers):
    """One specification version is live per strain. The fitted set (2026-09-18)
    has grades the ImB pages do not (GP16 next to no GP26): approving its first
    product must retire the cultivar's products of the old version, or two
    schemes would grade one strain."""
    cv = await _cultivar(client, admin_headers)
    a = await _approved(client, admin_headers, cv["id"], "GP_THC26:CBD1", 26)
    b = await _approved(client, admin_headers, cv["id"], "GP_THC24:CBD1", 24)
    fitted = await _approved(client, admin_headers, cv["id"], "GP_THC16:CBD1", 16,
                             window=(14.4, 17.59), doc_version="fitted 2026-09-15")
    assert fitted["status"] == "APPROVED"
    rows = {r["product_code"]: r["status"] for r in
            (await client.get(f"/qc/products?cultivar_id={cv['id']}", headers=admin_headers)).json()}
    assert rows[a["product_code"]] == "SUPERSEDED" and rows[b["product_code"]] == "SUPERSEDED"
    # A second product of the SAME new version joins it rather than retiring it.
    g20 = await _approved(client, admin_headers, cv["id"], "GP_THC20:CBD1", 20,
                          window=(18.0, 21.99), doc_version="fitted 2026-09-15")
    live = {r["product_code"] for r in
            (await client.get(f"/qc/products?cultivar_id={cv['id']}&status=APPROVED",
                              headers=admin_headers)).json()}
    assert live == {fitted["product_code"], g20["product_code"]}


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


async def test_a_live_product_closes_every_ladder_route(client, admin_headers):
    """QC-04: once a cultivar is graded from the catalogue, no ladder may be
    authored, approved or imported for it again — a later ladder would silently
    take grading back from the official page."""
    from tests.test_potency import _ladder
    cv = await _cultivar(client, admin_headers)
    draft = await _ladder(client, admin_headers, cv["id"], version="v5.2")
    await _approved(client, admin_headers, cv["id"])
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/potency-specs/{draft['id']}/approve", headers=qc2)
    assert r.status_code == 409 and "retired" in r.text
    r = await client.post("/qc/potency-specs", json={
        "cultivar_id": cv["id"], "version": "v6", "floor_pct": 13.83, "n_batches": 0,
        "ranges": [{"tier": 1, "range_min": 13.83, "range_max": 30, "nominal": 20}]},
        headers=admin_headers)
    assert r.status_code == 409 and "retired" in r.text
    r = await client.post("/qc/potency-specs/import", json={"dry_run": True}, headers=admin_headers)
    assert r.status_code == 409 and "retired" in r.text


async def test_role_gating(client, admin_headers):
    cv = await _cultivar(client, admin_headers)
    p = await _product(client, admin_headers, cv["id"])
    _, user_h = await _actor(client, admin_headers, "USER")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.get("/qc/products", headers=user_h)).status_code == 403
    assert (await client.get("/qc/products", headers=cu_h)).status_code == 200
    assert (await client.post("/qc/products", json={"cultivar_id": cv["id"],
                                                    "product_code": "GP_THC20:CBD1", "grade": 20,
                                                    "window_min": 18, "window_max": 21.99},
                              headers=cu_h)).status_code == 403
    assert (await client.post("/qc/products/ladder", json={
        "cultivar_id": cv["id"], "doc_version": "x",
        "grades": [{"grade": 20, "window_min": 18, "window_max": 21.99}]},
        headers=cu_h)).status_code == 403
    assert (await client.post(f"/qc/products/{p['id']}/approve", headers=cu_h)).status_code == 403
    assert (await client.post("/qc/products/import", json={"dry_run": True},
                              headers=cu_h)).status_code == 403
    assert (await client.post("/qc/products/import-fitted", json={
        "dry_run": True, "doc_version": "x", "specs": [{"id": "GP", "name": "Grape Pie"}]},
        headers=cu_h)).status_code == 403
    assert (await client.get("/qc/products", headers=qc_h)).status_code == 200


async def test_conformance_names_the_product_a_value_belongs_to(client, admin_headers):
    """The ladder answered "which tier?" — exactly one. The v.03 windows
    overlap, so `matching` is a list; `nearest` is ONE product under the
    owner's rule (2026-09-06, AD-12): the window that contains the value —
    closest nominal when several do, the lower on a tie — else the nearest
    window above or below. Never the highest nominal the value happens to
    satisfy, which over-labelled potency."""
    cv = await _cultivar(client, admin_headers)
    await _approved(client, admin_headers, cv["id"], "GP_THC28:CBD1", 28)
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

    # 25.3 sits inside GP28 (25.20–30.79), GP26 (23.40–28.59) and GP24 (21.60–26.39);
    # it is 0.7 from 26, 1.3 from 24 and 2.7 from 28.
    body = await ask(25.3)
    assert body["matching"] == ["GP_THC28:CBD1", "GP_THC26:CBD1", "GP_THC24:CBD1"]
    assert body["nearest"] == "GP_THC26:CBD1"
    # 25.0 is 1.0 from both 26 and 24: the lower nominal wins (never over-label).
    assert (await ask(25.0))["nearest"] == "GP_THC24:CBD1"
    # The bounds are inclusive, to the decimal the page prints.
    assert "GP_THC26:CBD1" in (await ask(23.40))["matching"]
    assert "GP_THC26:CBD1" not in (await ask(23.39))["matching"]
    assert (await ask(30.80))["matching"] == []
    # Below every window: nothing matches; the nearest is the lowest window.
    out = await ask(5.0)
    assert out["matching"] == [] and out["nearest"] == "GP_THC18:CBD1"
    # In the dead band between GP18 (…19.79) and GP24 (21.60…): nearest by edge.
    assert (await ask(20.5))["nearest"] == "GP_THC18:CBD1"
    # Asked about one product, it answers about that product — and where the
    # value falls when it does not conform.
    out = await ask(24.0, p26["id"])
    assert out["product"]["conforms"] is True and out["product"]["regrade_to"] is None
    out = await ask(22.0, p26["id"])
    assert out["product"]["conforms"] is False and out["product"]["regrade_to"] == "GP_THC24:CBD1"
    out = await ask(20.5, p26["id"])
    assert out["product"]["conforms"] is False and out["product"]["regrade_to"] is None, \
        "a value no grade holds is not regraded to a grade that does not hold it"


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


async def test_a_ladder_is_written_whole_or_not_at_all(client, admin_headers):
    """INS-03: a strain's grades enter in one transaction with explicit
    windows, validated as a set — no overlap, ceiling, distinct grades — so a
    refused ladder leaves nothing behind."""
    cj = await _cultivar(client, admin_headers, code="CJ", name="Cap Junky")
    grades = [{"grade": n, "window_min": _fitted_window(n, t)[0], "window_max": _fitted_window(n, t)[1]}
              for n, t in CJ_FITTED]
    r = await client.post("/qc/products/ladder", json={
        "cultivar_id": cj["id"], "doc_version": "fitted 2026-09-15",
        "source": "Potency Spec Service · CJ finished 2026-09-16",
        "notes": "fitted, non-overlapping", "grades": grades}, headers=admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert [p["product_code"] for p in body["products"]] == [
        "CJ_THC14:CBD1", "CJ_THC17:CBD1", "CJ_THC20:CBD1", "CJ_THC24:CBD1", "CJ_THC28:CBD1"]
    assert all(p["status"] == "DRAFT" and p["doc_version"] == "fitted 2026-09-15"
               and p["source"].startswith("Potency Spec Service") for p in body["products"])
    assert body["products"][-1]["window_max"] == 29.59
    assert body["overlaps_existing"] == []
    # The same version again is refused as a whole.
    r = await client.post("/qc/products/ladder", json={
        "cultivar_id": cj["id"], "doc_version": "fitted 2026-09-15", "grades": grades[:1]},
        headers=admin_headers)
    assert r.status_code == 409 and "nothing was written" in r.text
    # Overlapping grades are refused before anything is written.
    gp = await _cultivar(client, admin_headers)
    r = await client.post("/qc/products/ladder", json={
        "cultivar_id": gp["id"], "doc_version": "v.03",
        "grades": [{"grade": 26, "window_min": 23.4, "window_max": 28.59},
                   {"grade": 24, "window_min": 21.6, "window_max": 26.39}]}, headers=admin_headers)
    assert r.status_code == 422 and "overlap" in r.text
    assert (await client.get(f"/qc/products?cultivar_id={gp['id']}", headers=admin_headers)).json() == []
    # A grade without its window is not a grade (no ±10 % default, 2026-09-18).
    r = await client.post("/qc/products/ladder", json={
        "cultivar_id": gp["id"], "doc_version": "v.03", "grades": [{"grade": 26}]},
        headers=admin_headers)
    assert r.status_code == 422
    # Overlaps with the strain's products of ANOTHER version are reported, not
    # refused: they are what approving the new version supersedes.
    await _product(client, admin_headers, gp["id"], "GP_THC26:CBD1", 26)
    r = await client.post("/qc/products/ladder", json={
        "cultivar_id": gp["id"], "doc_version": "fitted 2026-09-15",
        "grades": [{"grade": 24, "window_min": 22.0, "window_max": 25.99},
                   {"grade": 28, "window_min": 26.0, "window_max": 29.99}]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert {(o["product_code"], o["with"]) for o in r.json()["overlaps_existing"]} == {
        ("GP_THC26:CBD1", "GP_THC24:CBD1"), ("GP_THC26:CBD1", "GP_THC28:CBD1")}


def _service_export(*specs):
    """The shape GET /api/specs?status=finished returns from the Potency Spec
    Service, ranges in the service's own arithmetic (hi = N + t − 0.01)."""
    out = []
    for sid, name, status, pairs in specs:
        ranges = [{"nominal": n, "tol": t, "lo": _fitted_window(n, t)[0],
                   "hi": _fitted_window(n, t)[1]} for n, t in pairs]
        out.append({"id": sid, "name": name, "custom": False, "status": status,
                    "tol": {str(int(n)): t for n, t in pairs}, "ranges": ranges,
                    "results_entered": [13.8, 14.2], "results_excluded": [21.29],
                    "created_at": "2026-09-11T14:47:47.401884+00:00",
                    "updated_at": "2026-09-16T09:28:00+00:00",
                    "finished_at": "2026-09-16T09:28:00+00:00" if status == "finished" else None})
    return {"specs": out}


async def test_import_fitted_loads_the_service_export_as_draft_products(client, admin_headers):
    """The owner's FINISHED fitted specs (2026-09-18) enter from the Potency
    Spec Service's export, each range one DRAFT product with the window the
    service prints and the fit's provenance in source/notes. Drafts and empty
    specs are skipped; a second run is idempotent."""
    export = _service_export(
        ("GP", "Grape Pie", "finished", [(16, 1.6), (20, 2.0), (24, 2.0), (28, 2.0)]),
        ("SJ", "Sleepy Joe", "draft", [(10, 1.0), (12, 1.0)]),
        ("WED", "Wedding Cake", "finished", []),
        # The service also holds the partner's Versa catalogue (V_*): not this
        # facility's strains, and not a valid acronym for a plant id.
        ("V_BG", "Blue Gelato", "finished", [(26, 2.6)]))
    r = await client.post("/qc/products/import-fitted", json={**export, "dry_run": True},
                          headers=admin_headers)
    assert r.status_code == 422, "the document version is stated by the importer, never invented"
    body = {**export, "doc_version": "fitted 2026-09-15"}
    r = await client.post("/qc/products/import-fitted", json={**body, "dry_run": True},
                          headers=admin_headers)
    assert r.status_code == 200, r.text
    dry = r.json()
    assert [c["product_code"] for c in dry["created"]] == [
        "GP_THC16:CBD1", "GP_THC20:CBD1", "GP_THC24:CBD1", "GP_THC28:CBD1"]
    assert {s["id"]: s["reason"] for s in dry["skipped"]} == {
        "SJ": "draft — not finished in the service", "WED": "no grades",
        "V_BG": "id is not a strain acronym (letters and digits only)"}
    assert dry["cultivars_created"] == [{"code": "GP", "name": "Grape Pie"}]
    assert (await client.get("/qc/products", headers=admin_headers)).json() == []

    r = await client.post("/qc/products/import-fitted", json=body, headers=admin_headers)
    assert r.status_code == 200, r.text
    rows = (await client.get("/qc/products", headers=admin_headers)).json()
    assert len(rows) == 4 and all(p["status"] == "DRAFT" for p in rows)
    gp24 = next(p for p in rows if p["product_code"] == "GP_THC24:CBD1")
    assert gp24["window_min"] == 22.0 and gp24["window_max"] == 25.99
    assert gp24["doc_version"] == "fitted 2026-09-15" and gp24["cultivar_name"] == "Grape Pie"
    assert "Potency Spec Service" in gp24["source"] and "finished 2026-09-16" in gp24["source"]
    assert "2 result(s) entered" in gp24["source"]
    assert "±2" in gp24["notes"] and "2026-09-18" in gp24["notes"] and "1 source result(s) excluded" in gp24["notes"]
    again = (await client.post("/qc/products/import-fitted", json=body, headers=admin_headers)).json()
    assert again["created"] == [] and len(again["skipped"]) == 7
    # A window that is not the spec's own arithmetic is a hand edit — refused.
    bad = _service_export(("BG", "Blue Gelato", "finished", [(22, 2.2)]))
    bad["specs"][0]["ranges"][0]["hi"] = 25.0
    r = await client.post("/qc/products/import-fitted",
                          json={**bad, "doc_version": "fitted 2026-09-15"}, headers=admin_headers)
    assert r.status_code == 422 and "arithmetic" in r.text
    # …and so is a tolerance over the owner's ceiling.
    wide = _service_export(("BG", "Blue Gelato", "finished", [(26, 3.0)]))
    r = await client.post("/qc/products/import-fitted",
                          json={**wide, "doc_version": "fitted 2026-09-15"}, headers=admin_headers)
    assert r.status_code == 422 and "±10 %" in r.text


async def test_import_fitted_resolves_a_disputed_spelling_to_the_one_cultivar(client, admin_headers):
    """The service spells four strains the merged master's way (Jelly Donuts)
    while the cultivar master has the August spelling (Jelly Donutz). Both are
    one strain: the import must attach to it, never create a second JD."""
    jd = await _cultivar(client, admin_headers, code="JD", name="Jelly Donutz")
    export = _service_export(("JD", "Jelly Donuts", "finished", [(15, 1.2), (18, 1.8), (22, 2.2)]))
    r = await client.post("/qc/products/import-fitted",
                          json={**export, "doc_version": "fitted 2026-09-15"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["conflicts"] == [] and r.json()["cultivars_created"] == []
    rows = (await client.get(f"/qc/products?cultivar_id={jd['id']}", headers=admin_headers)).json()
    assert len(rows) == 3 and all(p["cultivar_name"] == "Jelly Donutz" for p in rows)
    # A genuinely different strain under a taken code is still a conflict.
    export = _service_export(("JD", "Just Different", "finished", [(15, 1.2)]))
    r = await client.post("/qc/products/import-fitted",
                          json={**export, "doc_version": "fitted 2026-09-15"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["conflicts"] == [
        {"strain": "Just Different", "code": "JD", "taken_by": "Jelly Donutz"}]


async def test_the_packaged_catalogue_imports_the_owners_pages_once(client, admin_headers):
    r = await client.post("/qc/products/import", json={"dry_run": True}, headers=admin_headers)
    assert r.status_code == 200, r.text
    dry = r.json()
    assert dry["dry_run"] is True and dry["doc_version"] == "v.03"
    assert len(dry["created"]) == 42, "42 distinct products across the 48 pages"
    strains = {c["strain"] for c in dry["created"]}
    assert len(strains) == 22
    # INS-05: the two spellings both controlled sources agree on are canonical.
    assert "Pure Michigen" in strains and "Clemosa A Bud" in strains
    assert "Pure Michigan" not in strains and "Clemosa" not in strains
    assert dry["conflicts"] == [] and dry["cultivars_renamed"] == []
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
    jd = next(p for p in rows if p["product_code"] == "JD_THC22:CBD1")
    assert "Jelly Donuts" in jd["notes"] and "disagree" in jd["notes"]
    # Every imported window is the page's ± 10 % rule (what v.03 prints).
    for p in rows:
        assert (p["window_min"], p["window_max"]) == window_for(p["nominal_pct"])

    again = (await client.post("/qc/products/import", json={}, headers=admin_headers)).json()
    assert again["created"] == [] and len(again["skipped"]) == 42
    assert len((await client.get("/qc/products", headers=admin_headers)).json()) == 42


async def test_import_renames_a_cultivar_still_carrying_a_retired_spelling(client, admin_headers):
    """INS-05 (owner 2026-09-06: "correct as in the specifications for every
    strain"). PURE MICHIGEN is the spelling in both controlled sources; an org
    whose cultivar was created as "Pure Michigan" by the earlier import is
    corrected on the next one, with the old spelling kept in the note, and a
    disputed spelling ("Jelly Donuts") is attached to, not renamed."""
    pum = await _cultivar(client, admin_headers, code="PUM", name="Pure Michigan")
    jd = await _cultivar(client, admin_headers, code="JD", name="Jelly Donuts")
    dry = (await client.post("/qc/products/import", json={"dry_run": True},
                             headers=admin_headers)).json()
    assert dry["cultivars_renamed"] == [{"code": "PUM", "from": "Pure Michigan", "to": "Pure Michigen"}]
    assert dry["conflicts"] == []
    cvs = {c["code"]: c for c in (await client.get("/cultivation/cultivars",
                                                    headers=admin_headers)).json()["cultivars"]}
    assert cvs["PUM"]["name"] == "Pure Michigan", "a dry run renames nothing"

    real = (await client.post("/qc/products/import", json={}, headers=admin_headers)).json()
    assert real["cultivars_renamed"] == [{"code": "PUM", "from": "Pure Michigan", "to": "Pure Michigen"}]
    assert real["conflicts"] == [] and len(real["created"]) == 42
    cvs = {c["code"]: c for c in (await client.get("/cultivation/cultivars",
                                                    headers=admin_headers)).json()["cultivars"]}
    assert cvs["PUM"]["name"] == "Pure Michigen" and "Pure Michigan" in (cvs["PUM"]["note"] or "")
    assert cvs["JD"]["name"] == "Jelly Donuts", "a disputed spelling is left for the owner"
    rows = (await client.get("/qc/products", headers=admin_headers)).json()
    assert next(p for p in rows if p["product_code"] == "PUM_THC14:CBD1")["cultivar_id"] == pum["id"]
    assert all(p["cultivar_id"] == jd["id"] for p in rows if p["product_code"].startswith("JD_"))
    assert len({p["cultivar_id"] for p in rows}) == 22


# ── Fix round 2 (review 2026-09-27): the version rule, single-product overlap,
#    the SJ alias and the certificate-level history ───────────────────────────

async def test_an_older_version_is_never_approved_over_the_live_set(client, admin_headers):
    """QR-02 (owner 2026-09-18): once a strain's fitted set is APPROVED, a
    retired v.03 ImB page for that strain cannot be approved — it would have
    superseded the whole fitted set — and the packaged v.03 import is refused
    for that strain (a dry run reports it). Same and newer versions still go."""
    cj = await _cultivar(client, admin_headers, code="CJ", name="Cap Junky")
    fitted = {}
    for n, t in CJ_FITTED:
        fitted[n] = await _approved(client, admin_headers, cj["id"], f"CJ_THC{n}:CBD1", n,
                                    window=_fitted_window(n, t), doc_version="v.04")
    old = await _product(client, admin_headers, cj["id"], "CJ_THC28:CBD1", 28)   # v.03 page
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/products/{old['id']}/approve", headers=qc2)
    assert r.status_code == 409 and "v.04" in r.json()["detail"], r.text
    live = {p["product_code"] for p in
            (await client.get(f"/qc/products?cultivar_id={cj['id']}&status=APPROVED",
                              headers=admin_headers)).json()}
    assert live == {f"CJ_THC{n}:CBD1" for n, _ in CJ_FITTED}, "the fitted set is untouched"
    # the same version joins; a newer version supersedes
    v4b = await _approved(client, admin_headers, cj["id"], "CJ_THC30:CBD1", 30,
                          window=(29.61, 30.5), doc_version="v.04")
    assert v4b["status"] == "APPROVED"
    v5 = await _approved(client, admin_headers, cj["id"], "CJ_THC20:CBD1", 20,
                         window=(18.4, 21.59), doc_version="v.05")
    assert v5["status"] == "APPROVED"
    live = {p["product_code"] for p in
            (await client.get(f"/qc/products?cultivar_id={cj['id']}&status=APPROVED",
                              headers=admin_headers)).json()}
    assert live == {"CJ_THC20:CBD1"}
    # the v.03 pages: reported on a dry run, refused for real
    r = await client.post("/qc/products/import", json={"dry_run": True}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert "CJ (v.05)" in r.json()["refused"] and "CJ (v.04)" in r.json()["refused"]
    r = await client.post("/qc/products/import", json={"dry_run": False}, headers=admin_headers)
    assert r.status_code == 409 and "CJ (v.05)" in r.json()["detail"], r.text
    assert not [p for p in (await client.get(f"/qc/products?cultivar_id={cj['id']}",
                                             headers=admin_headers)).json()
                if p["doc_version"] == "v.03" and p["id"] != old["id"]], "nothing was written"


async def test_a_single_product_may_not_overlap_its_siblings_of_the_same_version(client, admin_headers):
    """QR-09 / INS2-06 (owner 2026-09-06 "ranges not overlapping"): POST and
    PATCH check the product as a set with the strain's DRAFT/APPROVED siblings
    of the same doc_version, as /ladder does. The issued v.03 pages are exempt
    (they overlap as printed — test_several_products_of_one_strain_coexist_…)."""
    cv = await _cultivar(client, admin_headers)
    a = await _approved(client, admin_headers, cv["id"], "GP_THC26:CBD1", 26,
                        window=(23.40, 28.59), doc_version="v.04")
    r = await client.post("/qc/products", json={
        "cultivar_id": cv["id"], "product_code": "GP_THC24:CBD1", "grade": 24,
        "window_min": 21.60, "window_max": 26.39, "doc_version": "v.04"}, headers=admin_headers)
    assert r.status_code == 422 and "overlap" in r.json()["detail"], r.text
    b = await _product(client, admin_headers, cv["id"], "GP_THC22:CBD1", 22,
                       window=(20.0, 23.39), doc_version="v.04")
    assert b["window_max"] == 23.39
    r = await client.patch(f"/qc/products/{b['id']}", json={"window_max": 24.0}, headers=admin_headers)
    assert r.status_code == 422 and "overlap" in r.json()["detail"], r.text
    r = await client.patch(f"/qc/products/{b['id']}", json={"window_max": 23.0}, headers=admin_headers)
    assert r.status_code == 200, r.text
    # a ladder body for the same version is checked against the singles too
    r = await client.post("/qc/products/ladder", json={
        "cultivar_id": cv["id"], "doc_version": "v.04",
        "grades": [{"grade": 20, "window_min": 18.0, "window_max": 21.0}]}, headers=admin_headers)
    assert r.status_code == 422 and "overlap" in r.json()["detail"], r.text
    # another version is not this version's business
    c = await _product(client, admin_headers, cv["id"], "GP_THC24:CBD1", 24,
                       window=(21.60, 26.39), doc_version="v.05")
    assert c["status"] == "DRAFT"
    assert a["status"] == "APPROVED"


async def test_import_fitted_resolves_sleepy_joy_to_sleepy_joe(client, admin_headers):
    """INS2-03: the per-strain folder spells SJ "Sleepy Joy", the merged
    master (and the cultivar master) "Sleepy Joe". A fitted export naming
    "Sleepy Joy" must land on the one SJ cultivar, not report a conflict."""
    sj = await _cultivar(client, admin_headers, code="SJ", name="Sleepy Joe")
    export = _service_export(("SJ", "Sleepy Joy", "finished", [(8, 0.8), (10, 1.0)]))
    r = await client.post("/qc/products/import-fitted",
                          json={**export, "doc_version": "fitted 2026-09-15"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["conflicts"] == [] and r.json()["cultivars_created"] == []
    rows = (await client.get(f"/qc/products?cultivar_id={sj['id']}", headers=admin_headers)).json()
    assert {p["product_code"] for p in rows} == {"SJ_THC8:CBD1", "SJ_THC10:CBD1"}
    assert all(p["cultivar_name"] == "Sleepy Joe" for p in rows), "an alias, never a rename"


async def test_certificate_level_history_is_derived_by_the_batch_code_head(client, admin_headers):
    """QR-11 (QC-10 residual): the certificate-level "tested so far" source
    derives each certificate's Total Δ9-THC from its component results (a
    transcribed total is refused everywhere) and attributes the certificate
    to the strain by the batch code's head (^GP[0-9]), case-insensitively —
    GPX… is another strain, and a code with no head is not attributed."""
    _, qp = await _actor(client, admin_headers, "QP")
    cv = await _cultivar(client, admin_headers)
    await _cultivar(client, admin_headers, code="GPX", name="Grape Pie X")
    prod = await _approved(client, admin_headers, cv["id"])
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-CERTH")
    # 2.0 + 0.877 × 25.06 = 23.98 on a GP-headed lot; 1.0 + 0.877 × 20.0 = 18.54 on a GPX lot
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "gp092601",
                                   a_val=2.0, b_val=25.06)
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "GPX092601",
                                   a_val=1.0, b_val=20.0)
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "L-NOHEAD",
                                   a_val=1.0, b_val=22.0)
    # owner 2026-09-16: an experiment (＊) lot is not used — it certifies nothing here
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "GP092602＊",
                                   a_val=3.0, b_val=25.06)
    hist = (await client.get(f"/qc/products/{prod['id']}/potency-history", headers=admin_headers)).json()
    lvl = hist["certificate_level"]
    assert lvl["n"] == 1 and round(lvl["avg"], 2) == 23.98, lvl
    assert lvl["values"][0]["lot_code"] == "GP092601" and lvl["values"][0]["conforms"] is True
    # A registered batch always carries the head (create_batch refuses any
    # other code), so the exact plant_batches match serves legacy rows only;
    # a head-less lot is never attributed by guesswork.
    assert "L-NOHEAD" not in {v["lot_code"] for v in lvl["values"]}
    assert not [v for v in lvl["values"] if "＊" in (v["lot_code"] or "")], "an experiment lot is not evidence"
