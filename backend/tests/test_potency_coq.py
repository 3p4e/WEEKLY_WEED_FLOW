"""Phase B — the CoQ carries the batch's per-cultivar potency grade.

A Certificate of Quality that names a cultivar grades its batch on Total Δ9-THC
against that cultivar's APPROVED ladder (PP-QC-SPEC-001). The ladder VERSION is
frozen on the CoQ at compile time, so the printed grade stays stable and
traceable even after the ladder is superseded. These tests exercise the
aggregated CoQ path (POST /qc/coq → GET /qc/coq/{id}), reusing the QC and
potency helpers.
"""
import uuid

from tests.conftest import create_user, login_and_set_password
from tests.test_qc import _actor, _computed_spec, _release_with_components, _stub_de, _FakeDE
from tests.test_potency import _cultivar, _ladder


async def test_coq_freezes_and_shows_cultivar_potency_grade(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="GRADE-SPEC")
    # Total Δ9-THC = 2.0 + 0.877 × 25.06 = 23.98 → Spec II (22–26) on Grape Pie.
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-GRADE",
                                   a_val=2.0, b_val=25.06)
    cv = await _cultivar(client, admin_headers, code="GP", name="Grape Pie")
    ladder = await _ladder(client, admin_headers, cv["id"], version="v5.2")
    assert (await client.post(f"/qc/potency-specs/{ladder['id']}/approve",
                              headers=qc2)).status_code == 200

    r = await client.post("/qc/coq", json={"batch_id": "B-GRADE", "specification_id": spec["id"],
                                           "cultivar_id": cv["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    coq = r.json()
    assert coq["cultivar_id"] == cv["id"]
    assert coq["potency_spec_id"] == ladder["id"]          # ladder version frozen at compile

    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    pot = d["potency"]
    assert pot is not None and pot["below_spec"] is False
    assert round(pot["total_d9_thc"], 2) == 23.98
    assert pot["disposition"]["spec"] == "Spec II" and pot["disposition"]["nominal"] == 24.0
    assert pot["cultivar_name"] == "Grape Pie" and pot["version"] == "v5.2"

    # FREEZE: approve a NEW ladder version (supersedes v5.2). The already-issued
    # CoQ must keep the v5.2 grade — it was frozen at compile.
    l2 = await _ladder(client, admin_headers, cv["id"], version="v6.0")
    assert (await client.post(f"/qc/potency-specs/{l2['id']}/approve",
                              headers=qc2)).status_code == 200
    d2 = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert d2["potency"]["potency_spec_id"] == ladder["id"]
    assert d2["potency"]["spec_status"] == "SUPERSEDED"    # the frozen ladder is now retired
    assert d2["potency"]["disposition"]["spec"] == "Spec II"


async def test_coq_without_cultivar_has_no_grade(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="NOGRADE")
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-NOGRADE")
    r = await client.post("/qc/coq", json={"batch_id": "B-NOGRADE", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    d = (await client.get(f"/qc/coq/{r.json()['id']}", headers=admin_headers)).json()
    assert d["potency"] is None
    assert d["coq"]["cultivar_id"] is None and d["coq"]["potency_spec_id"] is None


async def test_coq_cultivar_without_approved_ladder_carries_no_grade(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="NOLADDER")
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-NOLADDER")
    cv = await _cultivar(client, admin_headers, code="NL", name="No Ladder")
    await _ladder(client, admin_headers, cv["id"], version="v1")   # DRAFT only, never approved
    r = await client.post("/qc/coq", json={"batch_id": "B-NOLADDER", "specification_id": spec["id"],
                                           "cultivar_id": cv["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    coq = r.json()
    assert coq["cultivar_id"] == cv["id"] and coq["potency_spec_id"] is None
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert d["potency"] is None


async def test_coq_document_renders_cultivar_grade(client, admin_headers, monkeypatch):
    """Phase C — the rendered CoQ document carries the per-cultivar grade in its
    meta grid (Cultivar · Grade row), sourced from the frozen ladder disposition."""
    _stub_de(monkeypatch, {"document_id": "DE-GRADE-1", "verify": "RESULT: PASS", "bytes": 2048})
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="GRADE-DOC")
    # Total Δ9-THC = 2.0 + 0.877 × 25.06 = 23.98 → Spec II (nominal 24.0) on Grape Pie.
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-GRADE-DOC",
                                   a_val=2.0, b_val=25.06)
    cv = await _cultivar(client, admin_headers, code="GP", name="Grape Pie")
    ladder = await _ladder(client, admin_headers, cv["id"], version="v5.2")
    assert (await client.post(f"/qc/potency-specs/{ladder['id']}/approve",
                              headers=qc)).status_code == 200
    coq = (await client.post("/qc/coq", json={"batch_id": "B-GRADE-DOC",
                                              "specification_id": spec["id"],
                                              "cultivar_id": cv["id"]},
                             headers=admin_headers)).json()
    # review by a second QC person (compiler = admin), then render
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)).status_code == 200
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 201, r.text
    md = _FakeDE.last_markdown
    # dedicated Cultivar meta row + a grade-only row
    assert "Сорта~~Cultivar" in md and "Grape Pie" in md
    assert "Оцена~~Grade" in md
    assert "Spec II" in md and "nominal 24.0%" in md
    assert "PP-QC-SPEC-001 v5.2" in md
    assert "Total Δ9-THC 23.98%" in md


async def test_coq_rejects_unknown_cultivar(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="BADCV")
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-BADCV")
    r = await client.post("/qc/coq", json={"batch_id": "B-BADCV", "specification_id": spec["id"],
                                           "cultivar_id": str(uuid.uuid4())}, headers=admin_headers)
    assert r.status_code == 422, r.text


# ── The official product catalogue on the CoQ (plan commit 2; owner 2026-09-05/06) ──

async def _gp_products(client, admin_headers):
    """Grape Pie with three APPROVED v.03 products: GP26 23.40–28.59,
    GP24 21.60–26.39, GP18 16.20–19.79. Returns {code: product}."""
    from tests.test_products import _approved
    cv = await _cultivar(client, admin_headers, code="GP", name="Grape Pie")
    out = {}
    for code, grade in (("GP_THC26:CBD1", 26), ("GP_THC24:CBD1", 24), ("GP_THC18:CBD1", 18)):
        out[code] = await _approved(client, admin_headers, cv["id"], code, grade)
    return cv, out


async def _named_actor(client, admin_headers, role, full_name):
    user, otp = await create_user(client, admin_headers, role=role, full_name=full_name)
    token = await login_and_set_password(client, user["username"], otp)
    return user, {"Authorization": f"Bearer {token}"}


async def test_coq_graded_against_a_product_reports_conformance(client, admin_headers):
    """A CoQ compiled with product_id is judged against THAT product's window;
    the ladder stays out of it. Inside the window → conforms, no regrade."""
    _, qp = await _actor(client, admin_headers, "QP")
    cv, prods = await _gp_products(client, admin_headers)
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-OK")
    # Total Δ9-THC = 2.0 + 0.877 × 25.06 = 23.98 → inside GP26 (and GP24).
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-PROD-OK",
                                   a_val=2.0, b_val=25.06)
    r = await client.post("/qc/coq", json={"batch_id": "B-PROD-OK", "specification_id": spec["id"],
                                           "product_id": prods["GP_THC26:CBD1"]["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    coq = r.json()
    assert coq["product_code"] == "GP_THC26:CBD1" and coq["product_conforms"] is True
    assert coq["regrade_to"] is None and coq["potency_spec_id"] is None
    assert coq["cultivar_id"] == cv["id"]
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    pot = d["potency"]
    assert pot["kind"] == "product" and pot["product_code"] == "GP_THC26:CBD1"
    assert pot["nominal"] == 26.0 and (pot["window_min"], pot["window_max"]) == (23.40, 28.59)
    assert round(pot["total_d9_thc"], 2) == 23.98 and pot["conforms"] is True
    assert pot["matching"] == ["GP_THC26:CBD1", "GP_THC24:CBD1"]
    assert pot["nearest"] == "GP_THC24:CBD1" and pot["regrade_to"] is None
    assert pot["doc_code"] == "QCSP 001" and pot["doc_version"] == "v.03"
    assert d["coq"]["product_conforms"] is True and d["coq"]["product_code"] == "GP_THC26:CBD1"


async def test_out_of_window_coq_is_regraded_flagged_investigated_and_handed_over(
        client, admin_headers, monkeypatch):
    """The owner's out-of-grade rule (2026-09-06, "NO for now: a Total Δ9-THC
    outside the product's window does not block issuance … a formal OOS
    regarding the batch disposition should be opened and the value accepted
    and handed over as a deviation"; review 2026-09-27 INS2-01): a Total
    Δ9-THC outside the chosen product's window (1) falls to the product whose
    window holds it, (2) is flagged on the CoQ and printed as REGRADED on the
    document together with the state of the formal OOS, (3) is handed to the
    Cultivation and Production managers as a deviation, and (4) leaves the
    formal OOS on the batch disposition as a TRACKED FOLLOW-UP —
    `regrade_oos_pending` on the CoQ, `GET /qc/coq?regrade_oos_pending=true`
    for the register — that never gates approval or rendering. The
    certificate is NOT blocked; the regrade OOS itself, while open, does not
    block it either; any other open OOS on the batch still does."""
    _stub_de(monkeypatch, {"document_id": "DE-REGRADE-1", "verify": "RESULT: PASS", "bytes": 2048})
    from tests.test_qc import _closed_oos, _oos
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    cu, cu_h = await _named_actor(client, admin_headers, "CU_MGR", "Cultivation Lead")
    pr, pr_h = await _named_actor(client, admin_headers, "PR_MGR", "Production Lead")
    cv, prods = await _gp_products(client, admin_headers)
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-REGRADE")
    # Total Δ9-THC = 2.0 + 0.877 × 22.92 = 22.10 → outside GP26 (23.40–28.59),
    # inside GP24 (21.60–26.39): the lot falls to GP24.
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-REGRADE",
                                   a_val=2.0, b_val=22.92)
    r = await client.post("/qc/coq", json={"batch_id": "B-REGRADE", "specification_id": spec["id"],
                                           "product_id": prods["GP_THC26:CBD1"]["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    coq = r.json()
    assert coq["product_conforms"] is False and coq["regrade_to"] == "GP_THC24:CBD1"
    # (4) the follow-up is owed, and said so on the compile response and the detail
    assert coq["regrade_oos_pending"] is True and coq["regrade_oos"] is None
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    pot = d["potency"]
    assert pot["conforms"] is False and pot["regrade_to"] == "GP_THC24:CBD1"
    assert round(pot["total_d9_thc"], 2) == 22.10
    assert pot["regrade_oos_pending"] is True and pot["regrade_oos"] is None
    assert d["coq"]["regrade_oos_pending"] is True
    owed = (await client.get("/qc/coq?regrade_oos_pending=true", headers=admin_headers)).json()
    assert [q["id"] for q in owed] == [coq["id"]] and owed[0]["regrade_to"] == "GP_THC24:CBD1"
    assert (await client.get("/qc/coq?regrade_oos_pending=false", headers=admin_headers)).json() == []
    # a bare list stays bare (the verdict is resolved per row only on request)
    bare = next(q for q in (await client.get("/qc/coq", headers=admin_headers)).json() if q["id"] == coq["id"])
    assert bare["regrade_oos_pending"] is None and bare["product_conforms"] is None

    # (3) the deviation reached both department managers, and nobody else.
    for h in (cu_h, pr_h):
        inbox = (await client.get("/notifications", headers=h)).json()
        dev = [n for n in inbox if n["verb"] == "potency_deviation"]
        assert len(dev) == 1, inbox
        p = dev[0]["params"]
        assert p["batch_id"] == "B-REGRADE" and p["product_code"] == "GP_THC26:CBD1"
        assert p["regrade_to"] == "GP_THC24:CBD1" and round(p["total_d9_thc"], 2) == 22.10
        assert p["coq_number"] == coq["coq_number"]
    assert not [n for n in (await client.get("/notifications", headers=qc2)).json()
                if n["verb"] == "potency_deviation"]

    # NOT blocked: the HoQC approves with no OOS on the batch at all, and the
    # approval response still says the follow-up is owed.
    r = await client.post(f"/qc/coq/{coq['id']}/review", headers=qc2)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED" and r.json()["regrade_oos_pending"] is True

    # (2) the document issues and prints the regrade AND that the OOS is owed.
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 201, r.text
    md = _FakeDE.last_markdown
    assert "Оцена~~Grade" in md
    assert "GP_THC26:CBD1 · nominal 26.00 % · window 23.40–28.59 %" in md
    assert "does NOT conform (Total Δ9-THC 22.10 %)" in md
    assert ("REGRADED from GP_THC26:CBD1 to GP_THC24:CBD1 — formal OOS on the batch"
            " disposition: NOT YET OPENED") in md
    assert "QCSP 001 v.03" in md and "PP-QC-SPEC-001" not in md

    # An investigation into something else does not settle the follow-up …
    await _closed_oos(client, admin_headers, qp, "B-REGRADE", test_name="Water content")
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert d["coq"]["regrade_oos_pending"] is True
    # … nor does one that INVALIDATED a Total Δ9-THC result (a laboratory
    # error — the batch disposition was never investigated; QR-07).
    await _closed_oos(client, admin_headers, qp, "B-REGRADE", test_name="Total Δ9-THC",
                      invalidated=True, lab_error=True)
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert d["coq"]["regrade_oos_pending"] is True

    # The formal OOS on the batch disposition, OPENED (not closed) after the
    # CoQ was compiled: the follow-up is done, and the record names it.
    formal = await _oos(client, admin_headers, batch="B-REGRADE", test_name="Total Δ9-THC",
                        specification_value="23.40 – 28.59 %", obtained_value="22.10 %")
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert d["coq"]["regrade_oos_pending"] is False
    assert d["coq"]["regrade_oos"] == formal["oos_number"]
    assert (await client.get("/qc/coq?regrade_oos_pending=true", headers=admin_headers)).json() == []
    have = (await client.get("/qc/coq?regrade_oos_pending=false", headers=admin_headers)).json()
    assert [q["id"] for q in have] == [coq["id"]] and have[0]["regrade_oos"] == formal["oos_number"]
    # The open regrade OOS does NOT block issuance (it is the rule being
    # followed): the document re-renders and prints its number.
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 201, r.text
    md = _FakeDE.last_markdown
    assert ("REGRADED from GP_THC26:CBD1 to GP_THC24:CBD1 — formal OOS on the batch"
            f" disposition: {formal['oos_number']}") in md
    assert "NOT YET OPENED" not in md
    # Any OTHER open OOS on the batch still blocks under §6.4.1.
    other = await _oos(client, admin_headers, batch="B-REGRADE", test_name="Water content")
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 409 and "1 open OOS" in r.json()["detail"], r.text
    assert (await client.patch(f"/qc/oos/{other['id']}", json={"status": "CLOSED",
                                                               "disposition": "RELEASE",
                                                               "disposition_reason": "n/a",
                                                               "root_cause_description": "n/a"},
                               headers=qp)).status_code == 200, "the other OOS closes"
    assert (await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)).status_code == 201


async def test_regrade_oos_exemption_is_for_the_regraded_coq_only(client, admin_headers):
    """The §6.4.1 open-OOS gate exempts an open OOS naming Total Δ9-THC ONLY
    on a regraded CoQ (it is the out-of-grade follow-up). On a CoQ whose lot
    conforms to its product, the same open OOS is a genuine specification
    failure under investigation and still refuses the approval (INS2-01)."""
    from tests.test_qc import _oos
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    cv, prods = await _gp_products(client, admin_headers)
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-EXEMPT")
    # 23.98 → inside GP26: conforming.
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-EXEMPT-OK",
                                   a_val=2.0, b_val=25.06)
    ok = (await client.post("/qc/coq", json={"batch_id": "B-EXEMPT-OK", "specification_id": spec["id"],
                                             "product_id": prods["GP_THC26:CBD1"]["id"]},
                            headers=admin_headers)).json()
    assert ok["product_conforms"] is True and ok["regrade_oos_pending"] is None
    await _oos(client, admin_headers, batch="B-EXEMPT-OK", test_name="Total Δ9-THC")
    r = await client.post(f"/qc/coq/{ok['id']}/review", headers=qc2)
    assert r.status_code == 409 and "open OOS" in r.json()["detail"], r.text
    # 22.10 → regraded to GP24: the same open OOS is the follow-up and is exempt.
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-EXEMPT-RG",
                                   a_val=2.0, b_val=22.92)
    rg = (await client.post("/qc/coq", json={"batch_id": "B-EXEMPT-RG", "specification_id": spec["id"],
                                             "product_id": prods["GP_THC26:CBD1"]["id"]},
                            headers=admin_headers)).json()
    assert rg["product_conforms"] is False and rg["regrade_oos_pending"] is True
    formal = await _oos(client, admin_headers, batch="B-EXEMPT-RG", test_name="Total Δ9-THC")
    r = await client.post(f"/qc/coq/{rg['id']}/review", headers=qc2)
    assert r.status_code == 200, r.text
    assert r.json()["regrade_oos_pending"] is False and r.json()["regrade_oos"] == formal["oos_number"]


async def test_regrade_oos_match_is_case_insensitive_and_scoped_to_the_coq(client, admin_headers):
    """INS2-16 / QR-07: the follow-up match compares the batch id like every
    other OOS gate (upper()), and counts only an OOS that belongs to THIS
    CoQ — opened after its compile, raised on a result it aggregated, or
    cited as its oos_reference. An older investigation of the same batch
    (say, the initial period's) does not satisfy a later re-test CoQ."""
    from tests.test_qc import _closed_oos, _oos
    from tests.test_qc_review_2026_09 import _admin_pool
    _, qp = await _actor(client, admin_headers, "QP")
    cv, prods = await _gp_products(client, admin_headers)
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-SCOPE")
    # An earlier, CLOSED, non-invalidated investigation on the batch (before
    # any CoQ) — the initial period's, say.
    earlier = await _closed_oos(client, admin_headers, qp, "B-SCOPE", test_name="Total Δ9-THC",
                                invalidated=False, lab_error=False)
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-SCOPE",
                                   a_val=2.0, b_val=22.92)
    coq = (await client.post("/qc/coq", json={"batch_id": "B-SCOPE", "specification_id": spec["id"],
                                              "product_id": prods["GP_THC26:CBD1"]["id"]},
                             headers=admin_headers)).json()
    assert coq["regrade_oos_pending"] is True, "an OOS that predates the CoQ is not its follow-up"
    # … unless the CoQ cites it: compiled again naming it as oos_reference.
    cited = await client.post("/qc/coq", json={"batch_id": "B-SCOPE", "specification_id": spec["id"],
                                               "product_id": prods["GP_THC26:CBD1"]["id"],
                                               "oos_reference": earlier["oos_number"]},
                              headers=admin_headers)
    assert cited.status_code == 201, cited.text
    assert cited.json()["regrade_oos_pending"] is False
    assert cited.json()["regrade_oos"] == earlier["oos_number"]
    # A follow-up filed under the batch id in another case still counts.
    later = await _oos(client, admin_headers, batch="B-SCOPE", test_name="Total Δ9-THC")
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_oos_records SET batch_id='b-scope' WHERE id=$1", later["id"])
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert d["coq"]["regrade_oos_pending"] is False and d["coq"]["regrade_oos"] == later["oos_number"]


async def test_compile_refuses_a_product_of_another_strain_for_a_registered_batch(client, admin_headers):
    """INS2-12: a registered batch has a cultivar of record; a CoQ compiled
    against another strain's product would carry that strain's code and
    cultivar_id. Refused (422). An unregistered batch id is not checked."""
    from tests.test_cultivation import _room
    _, qp = await _actor(client, admin_headers, "QP")
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    cv, prods = await _gp_products(client, admin_headers)
    from tests.test_products import _approved
    cj = await _cultivar(client, admin_headers, code="CJ", name="Cap Junky")
    cj28 = await _approved(client, admin_headers, cj["id"], "CJ_THC28:CBD1", 28)
    room = await _room(client, admin_headers, "flower_ins212", "Flowering 2.1")
    r = await client.post("/cultivation/batches", json={
        "room_id": room["id"], "cultivar_id": cv["id"], "code": "GP092601",
        "plant_count": 10, "phase": "clone", "clone_date": "2026-07-01"}, headers=cu_h)
    assert r.status_code == 201, r.text
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-STRAIN")
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "GP092601",
                                   a_val=2.0, b_val=25.06)
    r = await client.post("/qc/coq", json={"batch_id": "GP092601", "specification_id": spec["id"],
                                           "product_id": cj28["id"]}, headers=admin_headers)
    assert r.status_code == 422 and "registered as cultivar GP" in r.json()["detail"], r.text
    r = await client.post("/qc/coq", json={"batch_id": "GP092601", "specification_id": spec["id"],
                                           "product_id": prods["GP_THC26:CBD1"]["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    # an unregistered lot is not checked against anything
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "L-UNREG",
                                   a_val=2.0, b_val=25.06)
    r = await client.post("/qc/coq", json={"batch_id": "L-UNREG", "specification_id": spec["id"],
                                           "product_id": cj28["id"]}, headers=admin_headers)
    assert r.status_code == 201, r.text


async def test_a_value_no_grade_holds_is_not_regraded(client, admin_headers):
    """Outside every window of the strain (the dead band between GP18's
    19.79 and GP24's 21.60): flagged, no regrade target — the OOS decides."""
    _, qp = await _actor(client, admin_headers, "QP")
    cv, prods = await _gp_products(client, admin_headers)
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-DEAD")
    # Total Δ9-THC = 1.0 + 0.877 × 22.0 = 20.29.
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-DEAD",
                                   a_val=1.0, b_val=22.0)
    r = await client.post("/qc/coq", json={"batch_id": "B-DEAD", "specification_id": spec["id"],
                                           "product_id": prods["GP_THC26:CBD1"]["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["product_conforms"] is False and r.json()["regrade_to"] is None
    pot = (await client.get(f"/qc/coq/{r.json()['id']}", headers=admin_headers)).json()["potency"]
    assert pot["matching"] == [] and pot["nearest"] == "GP_THC18:CBD1" and pot["regrade_to"] is None


async def test_a_conforming_product_coq_needs_no_oos_and_prints_conforms(client, admin_headers,
                                                                          monkeypatch):
    _stub_de(monkeypatch, {"document_id": "DE-PROD-OK", "verify": "RESULT: PASS", "bytes": 2048})
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    cv, prods = await _gp_products(client, admin_headers)
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PROD-DOC")
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-PROD-DOC",
                                   a_val=2.0, b_val=25.06)
    coq = (await client.post("/qc/coq", json={"batch_id": "B-PROD-DOC", "specification_id": spec["id"],
                                              "product_id": prods["GP_THC26:CBD1"]["id"]},
                             headers=admin_headers)).json()
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc2)).status_code == 200
    assert (await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "GP_THC26:CBD1 · nominal 26.00 % · window 23.40–28.59 % — conforms (Total Δ9-THC 23.98 %)" in md
    assert "REGRADED" not in md
    # No manager was disturbed for a conforming lot.
    inbox = (await client.get("/notifications", headers=qc2)).json()
    assert not [n for n in inbox if n["verb"] == "potency_deviation"]
