"""Phase B — the CoQ carries the batch's per-cultivar potency grade.

A Certificate of Quality that names a cultivar grades its batch on Total Δ9-THC
against that cultivar's APPROVED ladder (PP-QC-SPEC-001). The ladder VERSION is
frozen on the CoQ at compile time, so the printed grade stays stable and
traceable even after the ladder is superseded. These tests exercise the
aggregated CoQ path (POST /qc/coq → GET /qc/coq/{id}), reusing the QC and
potency helpers.
"""
import uuid

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
    assert "Cultivar · Grade" in md
    assert "Grape Pie" in md and "Spec II" in md and "nominal 24.0%" in md
    assert "PP-QC-SPEC-001 v5.2" in md
    assert "Total Δ9-THC 23.98%" in md


async def test_coq_rejects_unknown_cultivar(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="BADCV")
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-BADCV")
    r = await client.post("/qc/coq", json={"batch_id": "B-BADCV", "specification_id": spec["id"],
                                           "cultivar_id": str(uuid.uuid4())}, headers=admin_headers)
    assert r.status_code == 422, r.text
