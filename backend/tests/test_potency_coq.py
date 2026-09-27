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
    """The owner's out-of-grade rule (2026-09-06): a Total Δ9-THC outside the
    chosen product's window (1) falls to the product whose window holds it,
    (2) is flagged on the CoQ and printed as REGRADED on the document, (3) is
    approved only with a formal OOS naming Total Δ9-THC on that batch, and
    (4) is handed to the Cultivation and Production managers as a deviation.
    The certificate is NOT blocked (owner 2026-09-06: "NO for now")."""
    _stub_de(monkeypatch, {"document_id": "DE-REGRADE-1", "verify": "RESULT: PASS", "bytes": 2048})
    from tests.test_qc import _closed_oos
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
    pot = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()["potency"]
    assert pot["conforms"] is False and pot["regrade_to"] == "GP_THC24:CBD1"
    assert round(pot["total_d9_thc"], 2) == 22.10

    # (4) the deviation reached both department managers, and nobody else.
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

    # (3) approval needs a formal OOS naming Total Δ9-THC on the batch — an
    # investigation into something else does not count.
    r = await client.post(f"/qc/coq/{coq['id']}/review", headers=qc2)
    assert r.status_code == 409 and "formal OOS" in r.text and "GP_THC24:CBD1" in r.text, r.text
    await _closed_oos(client, admin_headers, qp, "B-REGRADE", test_name="Water content")
    r = await client.post(f"/qc/coq/{coq['id']}/review", headers=qc2)
    assert r.status_code == 409 and "formal OOS" in r.text
    await _closed_oos(client, admin_headers, qp, "B-REGRADE", test_name="Total Δ9-THC",
                      specification_value="23.40 – 28.59 %", obtained_value="22.10 %")
    r = await client.post(f"/qc/coq/{coq['id']}/review", headers=qc2)
    assert r.status_code == 200, r.text

    # (2) the document prints the verdict and the regrade, and still issues.
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 201, r.text
    md = _FakeDE.last_markdown
    assert "Оцена~~Grade" in md
    assert "GP_THC26:CBD1 · nominal 26.00 % · window 23.40–28.59 %" in md
    assert "does NOT conform (Total Δ9-THC 22.10 %)" in md
    assert "REGRADED from GP_THC26:CBD1 to GP_THC24:CBD1" in md
    assert "QCSP 001 v.03" in md and "PP-QC-SPEC-001" not in md


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
