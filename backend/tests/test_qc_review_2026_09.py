"""Regression tests for the 2026-09-27 QC review fixes (docs/review-2026-09-27/
backend-qc.md, QC-01 … QC-31 except the product-catalogue items).

Each test names the finding it pins. They reuse the fixtures and helpers of
test_qc.py; a few reach into the tasks DB through the admin pool to stage a
state the API itself now refuses to create (the defence-in-depth gates are
only reachable that way).
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.api.qc.common import _evaluate, derived_total, parse_lab_number
from app.api.qc.coq_docx import _coq_cell
from app.worktime import facility_today
from tests.test_qc import (_FakeDE, _accept_checklist, _actor, _approved_coa, _closed_oos, _coa,
                           _computed_spec, _coq_spec_two_params, _ecoa_doc,
                           _ecoa_spec_with_param, _hoqc_walk, _lab, _oos, _param,
                           _release_with_components, _released_coa, _rqs, _rqs_registered,
                           _RQS_COMPLETE, _sample, _spec, _stub_de)


PW = {"password": "TestPassword123456"}           # the org admin (conftest)
PW2 = {"password": "NewPassword123456"}           # every _actor-created user


async def _admin_pool():
    from app.db import tasks_admin_pool
    return tasks_admin_pool()


# ── QC-05 / QC-20 / QC-10: numeric core ─────────────────────────────────────

def test_qc05_evaluate_compares_as_decimal():
    """A value exactly on its limit conforms whatever type each side arrived as."""
    assert _evaluate(23.4, Decimal("23.40"), None) == (True, "pass")
    assert _evaluate(0.1, None, Decimal("0.1")) == (True, "pass")
    assert _evaluate(Decimal("0.05"), None, 0.05) == (True, "pass")
    assert _evaluate(23.39, Decimal("23.40"), None) == (False, "fail")
    assert _evaluate(None, 1, 2) == (None, "unknown")


def test_qc20_derived_total_rounds_half_up():
    """Ph. Eur. 3028: neutral + 0.877 × acid, two places, half-up — the binary
    float round() gave 23.39 and 13.19 for these two, each across a window bound."""
    assert derived_total(1.47, 25.00) == Decimal("23.40")
    assert derived_total(0.04, 15.00) == Decimal("13.20")
    assert derived_total(Decimal("2.0"), Decimal("25.06")) == Decimal("23.98")


def test_qc03_parse_lab_number_follows_the_lab_separator():
    assert parse_lab_number("0,6", ",") == Decimal("0.6")
    assert parse_lab_number("1.234,5", ",") == Decimal("1234.5")
    assert parse_lab_number("22,61 %", ",") == Decimal("22.61")
    assert parse_lab_number("1,234.5", ".") == Decimal("1234.5")
    assert parse_lab_number("< 0,5", ",") is None          # a bound, not a point value
    assert parse_lab_number("Complies", ".") is None
    for bad in ("0,6", "12,5", "1,2,3"):
        try:
            parse_lab_number(bad, ".")
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} must not parse under '.'")


async def test_qc05_ecoa_value_on_the_limit_passes_and_promote_recomputes(client, admin_headers):
    """The eCoA path graded 30.0 against an upper limit of numeric 30.0 as FAIL
    (float vs Decimal); promote then copied that stale verdict beside a freshly
    computed status. Both paths now agree, on the limit and through promote."""
    spec, p = await _ecoa_spec_with_param(client, admin_headers, material="QC05-ECOA")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QC05", report_date="2026-07-01")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "Total THC", "raw_value": "30.0", "unit": "%"}]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    ext = r.json()["extractions"][0]
    assert ext["numeric_value"] == 30.0 and ext["complies"] is True, ext
    await _accept_checklist(client, admin_headers, doc["id"])
    pr = await client.post(f"/qc/coa-documents/{doc['id']}/promote", headers=admin_headers)
    assert pr.status_code == 201, pr.text
    res = (await client.get(f"/qc/certificates/{pr.json()['coa_id']}", headers=admin_headers)).json()["results"]
    assert res[0]["complies"] is True and res[0]["status"] == "pass"
    assert res[0]["result_date"] == "2026-07-01"           # QC-09: the eCoA's report date


async def test_qc20_coq_total_line_is_half_up(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="QC20-SPEC")
    await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-QC20",
                                   a_val=1.47, b_val=25.00)
    r = await client.post("/qc/coq", json={"batch_id": "B-QC20", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    d = (await client.get(f"/qc/coq/{r.json()['id']}", headers=admin_headers)).json()
    total = next(ln for ln in d["lines"] if ln["parameter_name"] == "Total THC")
    assert total["result_numeric"] == 23.4                 # 23.395 → 23.40, not 23.39


async def test_qc10_derived_total_is_never_a_mapping_target(client, admin_headers):
    """A lab line 'Total THC' must not map onto the computed total_thc parameter
    — by name, by reviewer PATCH, or by placeholder mapping."""
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="QC10-SPEC")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QC10", report_date="2026-07-01")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "Total THC", "raw_value": "22.5", "unit": "%"},
                                          {"raw_label": "Delta-9-THC", "raw_value": "1.5", "unit": "%"}]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    by_label = {e["raw_label"]: e for e in r.json()["extractions"]}
    assert by_label["Total THC"]["parameter_id"] is None and by_label["Total THC"]["grade_status"] == "unmapped"
    assert by_label["Delta-9-THC"]["parameter_id"] == pa["id"]
    r = await client.patch(f"/qc/coa-documents/{doc['id']}/extractions/{by_label['Total THC']['id']}",
                           json={"parameter_id": pt["id"]}, headers=admin_headers)
    assert r.status_code == 422 and "computed" in r.json()["detail"], r.text
    ph = next(p for p in (await client.get("/qc/coa-placeholders", headers=admin_headers)).json()
              if p["normalized_label"] == "total thc")
    r = await client.patch(f"/qc/coa-placeholders/{ph['id']}",
                           json={"status": "MAPPED", "mapped_parameter_id": pt["id"]}, headers=admin_headers)
    assert r.status_code == 422 and "computed" in r.json()["detail"], r.text


async def test_qc10_single_certificate_coq_refuses_a_transcribed_total(client, admin_headers, monkeypatch):
    """A certificate that carries a transcribed row for the computed total (a
    row from before the never-transcribed rule) is named, not certified."""
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="QC10-LEG")
    coa = await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-QC10L")
    pool = await _admin_pool()
    await pool.execute(
        "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_numeric, unit,"
        " lower_limit, upper_limit, complies, status)"
        " SELECT org_id, id, $2, 'Total THC', 19.0, '%', 10, 30, true, 'pass' FROM qc_certificates WHERE id=$1",
        coa["id"], pt["id"])
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409 and "never transcribed" in r.json()["detail"], r.text


async def test_inv09_aggregation_coq_refuses_a_transcribed_total_too(client, admin_headers):
    """Review 2026-09-27b INV-09: the aggregation CoQ used to ignore a legacy
    transcribed total and compute from the components, while the
    single-certificate CoQ refused the same certificate. One rule: both refuse,
    and the message names the certificate."""
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="INV09-LEG")
    coa = await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-INV09")
    pool = await _admin_pool()
    await pool.execute(
        "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_numeric, unit,"
        " lower_limit, upper_limit, complies, status)"
        " SELECT org_id, id, $2, 'Total THC', 19.0, '%', 10, 30, true, 'pass' FROM qc_certificates WHERE id=$1",
        coa["id"], pt["id"])
    r = await client.post("/qc/coq", json={"batch_id": "B-INV09", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 409 and "never transcribed" in r.json()["detail"], r.text
    assert coa["coa_number"] in r.json()["detail"]


# ── QC-03 / QC-17: parsing and units ────────────────────────────────────────

async def test_qc03_comma_decimal_is_read_under_the_lab_separator(client, admin_headers):
    lab = await _lab(client, admin_headers, name="Skopje Lab", decimal_separator=",")
    spec = await _spec(client, admin_headers, material="QC03-MAT")
    lead = await _param(client, admin_headers, spec["id"], name="Lead", lo=None, hi=0.5, unit="mg/kg")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QC03", laboratory_id=lab["id"],
                          report_date="2026-07-01")
    # the old client sent parseFloat("0,6") == 0 — refused, not graded as 0
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "Lead", "raw_value": "0,6", "numeric_value": 0,
                                           "unit": "mg/kg"}]}, headers=admin_headers)
    assert r.status_code == 422 and "disagrees" in r.json()["detail"], r.text
    # the server reads 0,6 itself → 0.6 → FAIL against ≤ 0.5
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "Lead", "raw_value": "0,6", "unit": "mg/kg"}]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    ext = r.json()["extractions"][0]
    assert ext["parameter_id"] == lead["id"] and ext["numeric_value"] == 0.6 and ext["complies"] is False
    # a '.' laboratory: "0,6" is malformed, never truncated
    dot = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QC03D", report_date="2026-07-01")
    r = await client.post(f"/qc/coa-documents/{dot['id']}/extractions",
                          json={"items": [{"raw_label": "Lead", "raw_value": "0,6", "unit": "mg/kg"}]},
                          headers=admin_headers)
    assert r.status_code == 422 and "decimal separator" in r.json()["detail"], r.text
    # the iCoA "numeric" box: the text and the number must agree
    coa = await _coa(client, admin_headers, spec["id"], batch="B-QC03I")
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"parameter_id": lead["id"], "test_name": "Lead",
                                "result_value": "0.6", "result_numeric": 0.0},
                          headers=admin_headers)
    assert r.status_code == 422, r.text
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"parameter_id": lead["id"], "test_name": "Lead", "result_value": "0.6"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["result_numeric"] == 0.6 and r.json()["complies"] is False


async def test_qr01_extraction_patch_takes_the_text_and_derives_the_number(client, admin_headers):
    """QR-01 (QC-03 residual): the eCoA edit box sends the transcribed TEXT
    (`raw_value`); the server derives the numeric under the laboratory's
    decimal separator. A comma value on a ',' laboratory is read, on a '.'
    laboratory refused; a cleared text leaves the line unmeasured."""
    lab = await _lab(client, admin_headers, name="Comma Lab", decimal_separator=",")
    spec = await _spec(client, admin_headers, material="QR01-MAT")
    lead = await _param(client, admin_headers, spec["id"], name="Lead", lo=None, hi=0.5, unit="mg/kg")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QR01", laboratory_id=lab["id"],
                          report_date="2026-07-01")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "Lead", "raw_value": "0,4", "unit": "mg/kg"}]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    ext = r.json()["extractions"][0]
    assert ext["numeric_value"] == 0.4 and ext["complies"] is True
    r = await client.patch(f"/qc/coa-documents/{doc['id']}/extractions/{ext['id']}",
                           json={"raw_value": "0,6"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["raw_value"] == "0,6" and r.json()["numeric_value"] == 0.6
    assert r.json()["complies"] is False
    # text and a disagreeing number → refused
    r = await client.patch(f"/qc/coa-documents/{doc['id']}/extractions/{ext['id']}",
                           json={"raw_value": "0,6", "numeric_value": 0}, headers=admin_headers)
    assert r.status_code == 422 and "disagrees" in r.json()["detail"], r.text
    # cleared text → unmeasured, nothing invented
    r = await client.patch(f"/qc/coa-documents/{doc['id']}/extractions/{ext['id']}",
                           json={"raw_value": ""}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["numeric_value"] is None and r.json()["complies"] is None
    # a '.' laboratory: the comma is malformed, never truncated to 0
    dot = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QR01D", report_date="2026-07-01")
    r = await client.post(f"/qc/coa-documents/{dot['id']}/extractions",
                          json={"items": [{"raw_label": "Lead", "raw_value": "0.4", "unit": "mg/kg"}]},
                          headers=admin_headers)
    e2 = r.json()["extractions"][0]
    r = await client.patch(f"/qc/coa-documents/{dot['id']}/extractions/{e2['id']}",
                           json={"raw_value": "0,6"}, headers=admin_headers)
    assert r.status_code == 422 and "decimal separator" in r.json()["detail"], r.text


async def test_qc17_result_unit_must_match_the_parameter_unit(client, admin_headers):
    spec = await _spec(client, admin_headers, material="QC17-MAT")
    afla = await _param(client, admin_headers, spec["id"], name="Aflatoxin B1", lo=None, hi=2.0, unit="µg/kg")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-QC17")
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"parameter_id": afla["id"], "test_name": "Aflatoxin B1",
                                "result_numeric": 0.004, "unit": "mg/kg"}, headers=admin_headers)
    assert r.status_code == 422 and "µg/kg" in r.json()["detail"], r.text
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"parameter_id": afla["id"], "test_name": "Aflatoxin B1", "result_numeric": 4.0},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["unit"] == "µg/kg" and r.json()["complies"] is False
    # eCoA path
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QC17E", report_date="2026-07-01")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "Aflatoxin B1", "raw_value": "0.004", "unit": "mg/kg"}]},
                          headers=admin_headers)
    assert r.status_code == 422 and "µg/kg" in r.json()["detail"], r.text


# ── QC-01 / QC-13: investigation outcomes ───────────────────────────────────

async def test_qc01_retest_does_not_overturn_a_confirmed_oos(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC01-MAT")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC01", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 9.0,
         "result_date": "2026-07-01"}], decision="FAIL")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC01", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0,
         "result_date": "2026-07-05"},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0,
         "result_date": "2026-07-05"}])
    body = {"batch_id": "B-QC01", "specification_id": spec["id"]}
    # Phase II attributed the failure to the batch (not invalidated), batch RELEASED
    # after reprocessing: the failure stands, the re-test does not replace it.
    await _closed_oos(client, admin_headers, qp, batch="B-QC01", test_name="Total THC",
                      invalidated=False, disposition="RELEASE")
    r = await client.post("/qc/coq", json=body, headers=admin_headers)
    assert r.status_code == 409 and "CONFIRMED" in r.json()["detail"], r.text
    # a REJECT disposition on the batch refuses the compile outright
    await _closed_oos(client, admin_headers, qp, batch="B-QC01", test_name="Total THC",
                      invalidated=True, disposition="REJECT")
    r = await client.post("/qc/coq", json=body, headers=admin_headers)
    assert r.status_code == 409 and "REJECT" in r.json()["detail"], r.text


async def test_qr03_single_certificate_coq_refuses_a_rejected_or_confirmed_batch(
        client, admin_headers, monkeypatch):
    """QR-03 (QC-01 residual): POST /qc/certificates/{id}/coq issued a
    "Conforms to Specification" document for a batch whose investigation
    closed with the QP disposition REJECT, and over a test a closed,
    non-invalidated OOS on the batch had CONFIRMED; only an OPEN OOS was
    checked. Same gates as the aggregation path now."""
    _stub_de(monkeypatch, {"document_id": "DE-QR03", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="QR03-A", batch="B-QR03-A")
    # a CLOSED OOS on the batch (raised on another test) with disposition REJECT
    await _closed_oos(client, admin_headers, qp, batch="B-QR03-A", test_name="Water content",
                      invalidated=False, disposition="REJECT")
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409 and "REJECT" in r.json()["detail"], r.text
    # a CLOSED, non-invalidated OOS naming a test of this certificate → CONFIRMED
    coa_b = await _released_coa(client, admin_headers, qp, material="QR03-B", batch="B-QR03-B")
    await _closed_oos(client, admin_headers, qp, batch="B-QR03-B", test_name="total thc",
                      invalidated=False, disposition="RELEASE")
    r = await client.post(f"/qc/certificates/{coa_b['id']}/coq", headers=admin_headers)
    assert r.status_code == 409 and "CONFIRMED" in r.json()["detail"], r.text
    # an INVALIDATED one (laboratory error) covers it: the certificate issues
    coa_c = await _released_coa(client, admin_headers, qp, material="QR03-C", batch="B-QR03-C")
    await _closed_oos(client, admin_headers, qp, batch="B-QR03-C", test_name="Total THC",
                      invalidated=True, disposition="RELEASE")
    r = await client.post(f"/qc/certificates/{coa_c['id']}/coq", headers=admin_headers)
    assert r.status_code == 201, r.text
    # a closed OOS on ANOTHER test of the batch does not touch this certificate
    coa_d = await _released_coa(client, admin_headers, qp, material="QR03-D", batch="B-QR03-D")
    await _closed_oos(client, admin_headers, qp, batch="B-QR03-D", test_name="Moisture",
                      invalidated=False, disposition="RELEASE")
    r = await client.post(f"/qc/certificates/{coa_d['id']}/coq", headers=admin_headers)
    assert r.status_code == 201, r.text


async def test_qc01_only_an_invalidating_oos_covers_a_masked_failure(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC01-OK")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC01B", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 9.0,
         "result_date": "2026-07-01"}], decision="FAIL")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC01B", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0,
         "result_date": "2026-07-05"},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0,
         "result_date": "2026-07-05"}])
    oos = await _closed_oos(client, admin_headers, qp, batch="B-QC01B", test_name="Total THC",
                            invalidated=True, lab_error=True, disposition="RELEASE")
    r = await client.post("/qc/coq", json={"batch_id": "B-QC01B", "specification_id": spec["id"],
                                           "oos_reference": oos["oos_number"]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["overall_conform"] is True


async def test_qc13_closed_oos_is_frozen(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    oos = await _closed_oos(client, admin_headers, qp, batch="B-QC13", test_name="Total THC")
    for who, patch in ((admin_headers, {"invalidated": True}),
                       (admin_headers, {"root_cause_description": "rewritten"}),
                       (qp, {"disposition": "RELEASE"})):
        r = await client.patch(f"/qc/oos/{oos['id']}", json=patch, headers=who)
        assert r.status_code == 409 and "CLOSED" in r.json()["detail"], (patch, r.text)
    r = await client.patch(f"/qc/oos/{oos['id']}", json={"notes": "follow-up opened as PP-OOS-…"},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["invalidated"] is oos["invalidated"]


# ── QC-02: source certificates re-validated ─────────────────────────────────

async def test_qc02_void_and_revision_release_refuse_while_a_live_coq_cites(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC02-MAT")
    coa = await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC02", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    coq = (await client.post("/qc/coq", json={"batch_id": "B-QC02", "specification_id": spec["id"]},
                             headers=admin_headers)).json()
    r = await client.post(f"/qc/certificates/{coa['id']}/void", json={"reason": "wrong sample"}, headers=qc)
    assert r.status_code == 409 and coq["coq_number"] in r.json()["detail"], r.text
    # a revision of the (APPROVED) source can be opened, but not released over the live CoQ
    rev = await client.post(f"/qc/certificates/{coa['id']}/revise", json={"reason": "typo fix"}, headers=admin_headers)
    assert rev.status_code == 201, rev.text
    await _hoqc_walk(client, admin_headers, qp, rev.json()["id"], targets=("REVIEWED", "APPROVED"))
    _, hoqc = await _actor(client, admin_headers, "QC_MGR")
    r = await client.patch(f"/qc/certificates/{rev.json()['id']}", json={"status": "RELEASED"}, headers=hoqc)
    assert r.status_code == 409 and coq["coq_number"] in r.json()["detail"], r.text
    # once the CoQ is voided, both proceed
    assert (await client.post(f"/qc/coq/{coq['id']}/void", json={"reason": "source superseded"},
                              headers=qc)).status_code == 200
    r = await client.patch(f"/qc/certificates/{rev.json()['id']}", json={"status": "RELEASED"}, headers=hoqc)
    assert r.status_code == 200, r.text
    assert (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()["coa"]["status"] == "SUPERSEDED"


async def test_qc02_review_and_render_check_source_status(client, admin_headers, monkeypatch):
    """Defence in depth: a CoQ whose source died through a path this rule did
    not exist for is neither approved nor printed, and its sources show it."""
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC02-DEEP")
    coa = await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC02D", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    coq = (await client.post("/qc/coq", json={"batch_id": "B-QC02D", "specification_id": spec["id"]},
                             headers=admin_headers)).json()
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_certificates SET status='VOIDED' WHERE id=$1", coa["id"])
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert d["sources"][0]["coa_status"] == "VOIDED"
    r = await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)
    assert r.status_code == 409 and "VOIDED" in r.json()["detail"], r.text
    await pool.execute("UPDATE qc_certificates SET status='APPROVED' WHERE id=$1", coa["id"])
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)).status_code == 200
    await pool.execute("UPDATE qc_certificates SET status='SUPERSEDED' WHERE id=$1", coa["id"])
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 409 and "SUPERSEDED" in r.json()["detail"], r.text


# ── QC-06: disposition reconciled with results ──────────────────────────────

async def test_qc06_pass_disposition_needs_conforming_results(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="QC06-MAT")
    p = await _param(client, admin_headers, spec["id"])
    empty = await _coa(client, admin_headers, spec["id"], batch="B-QC06E")
    r = await client.patch(f"/qc/certificates/{empty['id']}", json={"decision": "PASS"}, headers=admin_headers)
    assert r.status_code == 409 and "no results" in r.json()["detail"], r.text
    coa = await _coa(client, admin_headers, spec["id"], batch="B-QC06F")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": p["id"], "test_name": "Total THC", "result_numeric": 99.0},
                              headers=admin_headers)).status_code == 201
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"decision": "PASS"}, headers=admin_headers)
    assert r.status_code == 409 and "do not comply" in r.json()["detail"], r.text
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"decision": "FAIL"},
                               headers=admin_headers)).status_code == 200
    # PASS recorded first, failing result added afterwards → approval refused
    late = await _coa(client, admin_headers, spec["id"], batch="B-QC06L")
    assert (await client.post(f"/qc/certificates/{late['id']}/results",
                              json={"parameter_id": p["id"], "test_name": "Total THC", "result_numeric": 22.0},
                              headers=admin_headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{late['id']}", json={"decision": "PASS"},
                               headers=admin_headers)).status_code == 200
    assert (await client.post(f"/qc/certificates/{late['id']}/results",
                              json={"test_name": "Total THC (repeat)", "parameter_id": p["id"],
                                    "result_numeric": 5.0},
                              headers=admin_headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{late['id']}", json={"status": "REVIEWED"},
                               headers=qp)).status_code == 200
    _, hoqc = await _actor(client, admin_headers, "QC_MGR")
    r = await client.patch(f"/qc/certificates/{late['id']}", json={"status": "APPROVED"}, headers=hoqc)
    assert r.status_code == 409 and "PASS" in r.json()["detail"], r.text


async def test_qc06_fail_dispositioned_source_never_feeds_a_conforming_coq(client, admin_headers,
                                                                             monkeypatch):
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC06-COQ")
    # every line complies numerically, but the HoQC failed the certificate
    coa = await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC06C", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}], decision="FAIL")
    r = await client.post("/qc/coq", json={"batch_id": "B-QC06C", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    coq = r.json()
    assert coq["overall_conform"] is False              # recorded for the QP, never conforming
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert all(ln["complies"] is True for ln in d["lines"])      # the measurements stand as they are
    assert d["sources"][0]["coa_number"] == coa["coa_number"] and d["sources"][0]["coa_decision"] == "FAIL"
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)).status_code == 200
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 409 and "not conform" in r.json()["detail"]


async def test_qc06_icoa_page_flags_an_inconsistent_pass(client, admin_headers):
    spec = await _spec(client, admin_headers, material="QC06-HTML")
    p = await _param(client, admin_headers, spec["id"])
    coa = await _coa(client, admin_headers, spec["id"], batch="B-QC06H", report_date="2026-07-01")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": p["id"], "test_name": "Total THC", "result_numeric": 99.0},
                              headers=admin_headers)).status_code == 201
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_certificates SET decision='PASS' WHERE id=$1", coa["id"])   # legacy state
    doc = (await client.get(f"/qc/certificates/{coa['id']}/icoa-html?parameter_id={p['id']}",
                            headers=admin_headers)).text
    assert "inconsistent with results" in doc and "Conforms to Specification" not in doc


# ── QC-07: the COQ certificate type ─────────────────────────────────────────

async def test_qc07_coq_certificate_type_is_retired_and_hoqc_gated(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="QC07-MAT")
    p = await _param(client, admin_headers, spec["id"])
    r = await client.post("/qc/certificates", json={"batch_id": "B-QC07", "specification_id": spec["id"],
                                                    "cert_type": "COQ"}, headers=admin_headers)
    assert r.status_code == 422 and "/qc/coq" in r.json()["detail"], r.text
    # a COQ-type row that predates the rule walks its lifecycle under the HoQC, not the QP
    coa = await _coa(client, admin_headers, spec["id"], batch="B-QC07L", report_date="2026-07-01")
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_certificates SET cert_type='COQ' WHERE id=$1", coa["id"])
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": p["id"], "test_name": "Total THC", "result_numeric": 22.0},
                              headers=admin_headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"decision": "PASS"},
                               headers=admin_headers)).status_code == 200
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "REVIEWED"},
                               headers=qp)).status_code == 200
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "APPROVED"},
                               headers=qp)).status_code == 403
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "APPROVED"},
                               headers=qc)).status_code == 200
    # the register still lists the legacy type
    assert (await client.get("/qc/register?cert_type=COQ", headers=admin_headers)).status_code == 200


async def test_qc07_coq_document_omits_the_qp_release_signature(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="QC07-SIG", batch="B-QC07S")
    # the eCoA/other release is the QP's; RELEASED is signed by the releasing role
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_certificates SET cert_type='OTHER' WHERE id=$1", coa["id"])
    r = await client.post(f"/qc/certificates/{coa['id']}/sign", json={**PW2, "meaning": "RELEASED"}, headers=qp)
    assert r.status_code == 201, r.text
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq", headers=qc)).status_code == 201
    md = _FakeDE.last_markdown
    assert "Released by" not in md and "Пуштил" not in md


# ── QC-08: the header THC window ────────────────────────────────────────────

async def test_qc08_header_window_must_match_the_total_thc_parameter(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, approver = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="QC08-SPEC", lo=10.0, hi=30.0)
    assert (await client.patch(f"/qc/specifications/{spec['id']}",
                               json={"thc_acceptance_min": 23.4, "thc_acceptance_max": 28.59,
                                     "thc_grade": "GRADE_II"}, headers=admin_headers)).status_code == 200
    # a partial patch cannot invert the stored window
    r = await client.patch(f"/qc/specifications/{spec['id']}", json={"thc_acceptance_max": 20.0},
                           headers=admin_headers)
    assert r.status_code == 422, r.text
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "QC_REVIEW"},
                               headers=admin_headers)).status_code == 200
    r = await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "QA_APPROVED"}, headers=approver)
    assert r.status_code == 409 and "differs" in r.json()["detail"], r.text
    assert (await client.patch(f"/qc/specifications/{spec['id']}",
                               json={"thc_acceptance_min": 10.0, "thc_acceptance_max": 30.0},
                               headers=admin_headers)).status_code == 200
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "QA_APPROVED"},
                               headers=approver)).status_code == 200
    # the CoQ prints the graded window, not a header of its own
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-QC08")
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)).status_code == 201
    # the limits print at two decimals (QR-06), as the catalogue prints a window
    assert "THC 10.00–30.00%" in _FakeDE.last_markdown and "Grade II" in _FakeDE.last_markdown


async def test_qr06_a_float_bound_limit_prints_at_two_decimals(client, admin_headers, monkeypatch):
    """QR-06: a total_thc parameter whose limits were bound as Python floats
    (every one created before 04b83ee) holds the float's binary expansion in
    its numeric column — 23.4 reads back as 23.399999999999998578… — and the
    CoQ Potency row printed the whole tail. Staged through the admin pool the
    way asyncpg wrote such rows; the row prints "THC 23.40–28.59%"."""
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="QR06-SPEC")
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_spec_parameters SET lower_limit=$1, upper_limit=$2 WHERE id=$3",
                       23.4, 28.59, pt["id"])
    stored = await pool.fetchval("SELECT lower_limit::text FROM qc_spec_parameters WHERE id=$1", pt["id"])
    assert len(stored) > 15, f"the fixture must hold a binary tail, got {stored}"
    # 2.0 + 0.877 × 25.06 = 23.98 — inside the window
    coa = await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-QR06",
                                         a_val=2.0, b_val=25.06)
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 201, r.text
    md = _FakeDE.last_markdown
    assert "THC 23.40–28.59%" in md, md
    assert "23.39999" not in md and "28.5899" not in md


# ── QC-09: latest result = latest measurement ───────────────────────────────

async def test_qc09_latest_result_is_by_measurement_date(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC09-MAT")
    # entered FIRST but measured LATER
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC09", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0, "result_date": "2026-07-10"},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0, "result_date": "2026-07-10"}])
    # entered LATER (a lab report transcribed late) but measured EARLIER
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC09", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 25.0, "result_date": "2026-07-01"}])
    r = await client.post("/qc/coq", json={"batch_id": "B-QC09", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    d = (await client.get(f"/qc/coq/{r.json()['id']}", headers=admin_headers)).json()
    assert next(ln for ln in d["lines"] if ln["parameter_name"] == "Total THC")["result_numeric"] == 22.0
    # add_result stamps the facility day when no date is given
    coa = await _coa(client, admin_headers, spec["id"], batch="B-QC09D")
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 20.0},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["result_date"] == facility_today().isoformat()
    # promote needs the eCoA's report date to carry
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QC09P", report_date=None)
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                              json={"items": [{"raw_label": "Total THC", "raw_value": "21.0", "unit": "%"}]},
                              headers=admin_headers)).status_code == 201
    await _accept_checklist(client, admin_headers, doc["id"])
    r = await client.post(f"/qc/coa-documents/{doc['id']}/promote", headers=admin_headers)
    assert r.status_code == 409 and "report_date" in r.json()["detail"], r.text


# ── QC-11 / QC-12: segregation and e-signatures ─────────────────────────────

async def test_qc11_checklist_decider_must_not_have_transcribed(client, admin_headers):
    _, hoqc = await _actor(client, admin_headers, "QC_MGR")
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="QC11-ECOA")
    doc = await _ecoa_doc(client, hoqc, spec["id"], batch="B-QC11", report_date="2026-07-01")
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                              json={"items": [{"raw_label": "Total THC", "raw_value": "22.0", "unit": "%"}]},
                              headers=hoqc)).status_code == 201
    assert (await client.put(f"/qc/coa-documents/{doc['id']}/checklist",
                             json={"sample_id_match": True, "method_per_tqa": True,
                                   "units_per_spec": True, "conformance_by_pp": True},
                             headers=admin_headers)).status_code == 200
    r = await client.post(f"/qc/coa-documents/{doc['id']}/checklist/decide",
                          json={"outcome": "ACCEPTED"}, headers=hoqc)
    assert r.status_code == 403 and "transcribed" in r.json()["detail"], r.text
    _, other = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/checklist/decide",
                              json={"outcome": "ACCEPTED"}, headers=other)).status_code == 200


async def test_qc11_spec_approver_must_not_have_authored_a_parameter(client, admin_headers):
    _, author = await _actor(client, admin_headers, "QC_MGR")
    _, co = await _actor(client, admin_headers, "QC_MGR")
    spec = await _spec(client, author, material="QC11-SPEC")
    await _param(client, co, spec["id"])                       # co-author adds the criterion
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "QC_REVIEW"},
                               headers=author)).status_code == 200
    r = await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "QA_APPROVED"}, headers=co)
    assert r.status_code == 403 and "parameters" in r.json()["detail"], r.text
    _, third = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "QA_APPROVED"},
                               headers=third)).status_code == 200


async def test_qc12_signature_is_tied_to_the_role_of_record(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="QC12-MAT", batch="B-QC12")
    d = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()["coa"]
    # admin is the analyst of record: AUTHORED yes, APPROVED (someone else's act) no
    assert (await client.post(f"/qc/certificates/{coa['id']}/sign", json={**PW, "meaning": "AUTHORED"},
                              headers=admin_headers)).status_code == 201
    r = await client.post(f"/qc/certificates/{coa['id']}/sign", json={**PW, "meaning": "APPROVED"},
                          headers=admin_headers)
    assert r.status_code == 403 and "of record" in r.json()["detail"], r.text
    # the QP reviewed it: REVIEWED yes; COQ_ISSUED never (QP does not issue CoQs)
    assert d["reviewer_id"] and (await client.post(f"/qc/certificates/{coa['id']}/sign",
                                                   json={**PW2, "meaning": "REVIEWED"},
                                                   headers=qp)).status_code == 201
    r = await client.post(f"/qc/certificates/{coa['id']}/sign", json={**PW2, "meaning": "COQ_ISSUED"}, headers=qp)
    assert r.status_code == 403, r.text
    # an unrelated QC_MGR cannot sign RELEASED on an iCoA it did not release … but a
    # QC_MGR (the releasing role for iCoA) can; the approver of record signs APPROVED
    _, other = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/certificates/{coa['id']}/sign", json={**PW2, "meaning": "APPROVED"},
                              headers=other)).status_code == 403


async def test_qc12_aggregation_coq_carries_and_prints_esignatures(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "DE-SIG", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC12-COQ")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC12C", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    coq = (await client.post("/qc/coq", json={"batch_id": "B-QC12C", "specification_id": spec["id"]},
                             headers=admin_headers)).json()
    # APPROVED before approval → 409; COMPILED by someone other than the compiler → 403
    assert (await client.post(f"/qc/coq/{coq['id']}/sign", json={**PW2, "meaning": "APPROVED"},
                              headers=qc)).status_code == 409
    assert (await client.post(f"/qc/coq/{coq['id']}/sign", json={**PW2, "meaning": "COMPILED"},
                              headers=qc)).status_code == 403
    assert (await client.post(f"/qc/coq/{coq['id']}/sign", json={**PW, "meaning": "COMPILED"},
                              headers=admin_headers)).status_code == 201
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)).status_code == 200
    assert (await client.post(f"/qc/coq/{coq['id']}/sign", json={**PW2, "meaning": "APPROVED"},
                              headers=qc)).status_code == 201
    sigs = (await client.get(f"/qc/coq/{coq['id']}/signatures", headers=admin_headers)).json()
    assert [s["meaning"] for s in sigs] == ["COMPILED", "APPROVED"]
    assert (await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "Compiled by" in md and "Approved by" in md and "Test Admin" in md
    assert "carries no electronic signature" not in md


# ── QC-15: initial and re-test CoQs coexist ─────────────────────────────────

async def test_qc15_initial_and_retest_coqs_coexist(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC15-MAT")
    initial = await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC15", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 24.0, "result_date": "2026-01-10"},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0, "result_date": "2026-01-10"}])
    coq1 = (await client.post("/qc/coq", json={"batch_id": "B-QC15", "specification_id": spec["id"]},
                              headers=admin_headers)).json()
    assert coq1["purpose"] == "INITIAL" and coq1["timepoint"] is None
    assert (await client.post(f"/qc/coq/{coq1['id']}/review", headers=qc)).status_code == 200
    # six months on: a re-test certificate
    retest = await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC15", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.5, "result_date": "2026-07-10"},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 9.0, "result_date": "2026-07-10"}])
    r = await client.post("/qc/coq", json={"batch_id": "B-QC15", "specification_id": spec["id"],
                                           "purpose": "RETEST"}, headers=admin_headers)
    assert r.status_code == 422 and "timepoint" in r.json()["detail"]
    r = await client.post("/qc/coq", json={"batch_id": "B-QC15", "specification_id": spec["id"],
                                           "purpose": "RETEST", "timepoint": "6M",
                                           "source_coa_ids": [retest["id"]]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    coq2 = r.json()
    d = (await client.get(f"/qc/coq/{coq2['id']}", headers=admin_headers)).json()
    assert [s["coa_number"] for s in d["sources"]] == [retest["coa_number"]]
    assert next(ln for ln in d["lines"] if ln["parameter_name"] == "Total THC")["result_numeric"] == 22.5
    # both APPROVED at once — no void of the valid initial-release CoQ
    assert (await client.post(f"/qc/coq/{coq2['id']}/review", headers=qc)).status_code == 200
    assert (await client.get(f"/qc/coq/{coq1['id']}", headers=admin_headers)).json()["coq"]["status"] == "APPROVED"
    # the initial-release CoQ stays recompilable from the release-time set
    r = await client.post("/qc/coq", json={"batch_id": "B-QC15", "specification_id": spec["id"],
                                           "source_coa_ids": [initial["id"]]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    d = (await client.get(f"/qc/coq/{r.json()['id']}", headers=admin_headers)).json()
    assert next(ln for ln in d["lines"] if ln["parameter_name"] == "Total THC")["result_numeric"] == 24.0
    # but a second APPROVED for the same period is still refused
    assert (await client.post(f"/qc/coq/{r.json()['id']}/review", headers=qc)).status_code == 409
    # a foreign certificate id is refused
    r = await client.post("/qc/coq", json={"batch_id": "B-QC15", "specification_id": spec["id"],
                                           "source_coa_ids": [coq1["id"]]}, headers=admin_headers)
    assert r.status_code == 422


async def test_qr04_a_retest_coq_prints_its_period_and_the_register_shows_it(
        client, admin_headers, monkeypatch):
    """QR-04 (QC-15 seam): the INITIAL and the 6-month RETEST CoQ of one batch
    are both live; the document and the register must say which is which."""
    _stub_de(monkeypatch, {"document_id": "DE-QR04", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QR04-MAT")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QR04", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 24.0, "result_date": "2026-01-10"},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0, "result_date": "2026-01-10"}])
    coq1 = (await client.post("/qc/coq", json={"batch_id": "B-QR04", "specification_id": spec["id"]},
                              headers=admin_headers)).json()
    assert (await client.post(f"/qc/coq/{coq1['id']}/review", headers=qc)).status_code == 200
    assert (await client.post(f"/qc/coq/{coq1['id']}/render", headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "# Сертификат за квалитет|Certificate of Quality\n" in md, "an INITIAL CoQ keeps the plain title"
    assert "Период на тестирање~~Testing period ||| Првично пуштање / Initial release" in md
    retest = await _approved_coa(client, admin_headers, qp, spec["id"], "B-QR04", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.5, "result_date": "2026-07-10"},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 9.0, "result_date": "2026-07-10"}])
    coq2 = (await client.post("/qc/coq", json={"batch_id": "B-QR04", "specification_id": spec["id"],
                                               "purpose": "RETEST", "timepoint": "6M",
                                               "source_coa_ids": [retest["id"]]},
                              headers=admin_headers)).json()
    assert (await client.post(f"/qc/coq/{coq2['id']}/review", headers=qc)).status_code == 200
    assert (await client.post(f"/qc/coq/{coq2['id']}/render", headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "en_title: Certificate of Quality — Re-test 6M" in md
    assert "# Сертификат за квалитет — Ретест 6M|Certificate of Quality — Re-test 6M\n" in md
    assert "Период на тестирање~~Testing period ||| Ретест 6M / Re-test 6M" in md
    rows = {r["coa_number"]: r for r in
            (await client.get("/qc/register", headers=admin_headers)).json()
            if r["record"] == "coq"}
    assert rows[coq1["coq_number"]]["purpose"] == "INITIAL" and rows[coq1["coq_number"]]["timepoint"] is None
    assert rows[coq2["coq_number"]]["purpose"] == "RETEST" and rows[coq2["coq_number"]]["timepoint"] == "6M"


# ── QC-18 / QC-19 / QC-21 ───────────────────────────────────────────────────

async def test_qc18_revise_carries_template_metadata_and_works_from_approved(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC18-MAT")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-QC18", report_date="2026-07-01")
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"cultivation_batch": "GP072501", "product_code": "GP_THC24:CBD1",
                                     "packaging": "50 g jar", "packaging_date": "2026-07-02",
                                     "manufacture_date": "2026-06-30", "expiry_date": "2027-06-30",
                                     "retest_date": "2027-01-30", "botanical_type": "Cannabis sativa L.",
                                     "chemotype": "I", "analysis_start_date": "2026-06-25",
                                     "analysis_end_date": "2026-06-28", "sampling_location": "Dry room 2",
                                     "issue_language": "EN"}, headers=admin_headers)).status_code == 200
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
                              headers=admin_headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"decision": "PASS"},
                               headers=admin_headers)).status_code == 200
    await _hoqc_walk(client, admin_headers, qp, coa["id"], targets=("REVIEWED", "APPROVED"))
    r = await client.post(f"/qc/certificates/{coa['id']}/revise", json={"reason": "wrong jar size"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    rev = r.json()
    for k in ("cultivation_batch", "product_code", "packaging", "packaging_date", "manufacture_date",
              "expiry_date", "retest_date", "botanical_type", "chemotype", "analysis_start_date",
              "analysis_end_date", "sampling_location", "issue_language"):
        assert rev[k] is not None, k
    assert rev["packaging"] == "50 g jar" and rev["supersedes_id"] == coa["id"]


async def test_qc19_rebinding_identity_invalidates_the_checklist(client, admin_headers):
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="QC19-ECOA")
    lab = await _lab(client, admin_headers, name="Lab A")
    lab2 = await _lab(client, admin_headers, name="Lab B")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QC19", laboratory_id=lab["id"],
                          report_date="2026-07-01")
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                              json={"items": [{"raw_label": "Total THC", "raw_value": "22.0", "unit": "%"}]},
                              headers=admin_headers)).status_code == 201
    await _accept_checklist(client, admin_headers, doc["id"])
    for patch in ({"laboratory_id": lab2["id"]}, {"report_date": "2026-07-09"},
                  {"source_institution": "Someone else"}, {"material_code": "OTHER"}):
        await _accept_checklist(client, admin_headers, doc["id"]) if (
            await client.get(f"/qc/coa-documents/{doc['id']}/checklist", headers=admin_headers)
        ).json()["outcome"] != "ACCEPTED" else None
        assert (await client.patch(f"/qc/coa-documents/{doc['id']}", json=patch,
                                   headers=admin_headers)).status_code == 200, patch
        cl = (await client.get(f"/qc/coa-documents/{doc['id']}/checklist", headers=admin_headers)).json()
        assert cl["outcome"] == "PENDING" and cl["reviewed_by"] is None, patch
    # an echo of the same value is not a change
    await _accept_checklist(client, admin_headers, doc["id"])
    assert (await client.patch(f"/qc/coa-documents/{doc['id']}", json={"report_date": "2026-07-09"},
                               headers=admin_headers)).status_code == 200
    assert (await client.get(f"/qc/coa-documents/{doc['id']}/checklist",
                             headers=admin_headers)).json()["outcome"] == "ACCEPTED"


async def test_qc21_coq_report_date_is_the_facility_day(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC21-MAT")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC21", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    coq = (await client.post("/qc/coq", json={"batch_id": "B-QC21", "specification_id": spec["id"]},
                             headers=admin_headers)).json()
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)).status_code == 200
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_coq SET compiled_at=$2 WHERE id=$1", coq["id"],
                       datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc))   # 00:30 on 1 Jan in Skopje
    assert (await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)).status_code == 201
    assert "2027-01-01" in _FakeDE.last_markdown and "2026-12-31" not in _FakeDE.last_markdown


# ── QC-23 / QC-24 / QC-29 ───────────────────────────────────────────────────

async def test_qc23_registered_rqs_and_completed_sfr_are_frozen(client, admin_headers):
    rqs = await _rqs_registered(client, admin_headers, batch_id="B-QC23")
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"storage_location": None},
                           headers=admin_headers)
    assert r.status_code == 409 and "storage_location" in r.json()["detail"], r.text
    assert (await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"num_samples": 99},
                               headers=admin_headers)).status_code == 409
    # workflow fields and an echo of the registered value still pass
    assert (await client.patch(f"/qc/sampling-requests/{rqs['id']}",
                               json={"num_samples": _RQS_COMPLETE["num_samples"], "notes": "ok"},
                               headers=admin_headers)).status_code == 200
    sfr = (await client.post("/qc/field-records", json={"rqs_id": rqs["id"], "sampling_location": "Barrel 3",
                                                        "destination_facility": "QC lab"},
                             headers=admin_headers)).json()
    for tgt in ("IN_FIELD", "COMPLETED"):
        assert (await client.patch(f"/qc/field-records/{sfr['id']}", json={"status": tgt},
                                   headers=admin_headers)).status_code == 200
    r = await client.patch(f"/qc/field-records/{sfr['id']}", json={"actual_arrival": "2026-07-01T10:00:00Z"},
                           headers=admin_headers)
    assert r.status_code == 409 and "COMPLETED" in r.json()["detail"], r.text
    assert (await client.patch(f"/qc/field-records/{sfr['id']}", json={"notes": "late note"},
                               headers=admin_headers)).status_code == 200


async def test_qc24_water_verdict_is_required_and_set_once(client, admin_headers):
    r = await client.post("/qc/water-tests", json={"location": "RO-1", "grade": "RO",
                                                   "parameters": {"pH": 6.8}}, headers=admin_headers)
    assert r.status_code == 422
    wt = (await client.post("/qc/water-tests", json={"location": "RO-1", "grade": "RO",
                                                     "parameters": {"pH": 6.8}, "passed": False,
                                                     "ooe": "TOC high"}, headers=admin_headers)).json()
    assert wt["passed"] is False
    r = await client.patch(f"/qc/water-tests/{wt['id']}", json={"passed": True}, headers=admin_headers)
    assert r.status_code == 200 and r.json().get("noop") is True        # the field is not accepted
    assert (await client.get("/qc/water-tests?location=RO-1", headers=admin_headers)).json()[0]["passed"] is False


async def test_qc29_custody_is_recorded_by_a_party(client, admin_headers):
    sample = await _sample(client, admin_headers, batch="B-QC29")
    a, _ = await _actor(client, admin_headers, "USER")
    b, _ = await _actor(client, admin_headers, "USER")
    r = await client.post(f"/qc/samples/{sample['id']}/custody",
                          json={"from_user_id": a["id"], "to_user_id": b["id"], "transfer_type": "FIELD_TO_LAB"},
                          headers=admin_headers)
    assert r.status_code == 403 and "third" in r.json()["detail"], r.text
    r = await client.post(f"/qc/samples/{sample['id']}/custody",
                          json={"to_user_id": b["id"], "transfer_type": "FIELD_TO_LAB"}, headers=admin_headers)
    assert r.status_code == 201, r.text


# ── QC-25 / QC-26 / QC-27 / QC-28 ───────────────────────────────────────────

async def test_qc25_coq_footnotes_and_claims_derive_from_the_data(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="QC25-SPEC")
    coa = await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-QC25")
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "Foreign Matter" not in md                      # no invented Q footnote content
    assert "Delta-9-THC" in md and "in-house Purely Plant QC Department" in md
    assert "3028" in md and "2.2.29" not in md              # the ∑ note cites the monograph
    assert "ISO/IEC 17025 accredited" not in md            # nothing external, nothing claimed
    # an external source with a registered but unaccredited lab: named, not called accredited
    lab = await _lab(client, admin_headers, name="Plain Lab")
    coa2 = await _released_coa(client, admin_headers, qp, material="QC25-EXT", batch="B-QC25X",
                               results=None)
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_certificates SET laboratory_id=$2 WHERE id=$1", coa2["id"], lab["id"])
    await pool.execute("UPDATE qc_results SET source_institution='Plain Lab' WHERE coa_id=$1", coa2["id"])
    assert (await client.post(f"/qc/certificates/{coa2['id']}/coq", headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "ISO/IEC 17025 accredited" not in md and "cross-referenced in section 02" in md
    await pool.execute("UPDATE qc_laboratories SET accreditation_number='LT-045' WHERE id=$1", lab["id"])
    assert (await client.post(f"/qc/certificates/{coa2['id']}/coq", headers=admin_headers)).status_code == 201
    assert "ISO/IEC 17025 accredited" in _FakeDE.last_markdown


def test_qc26_coq_cell_neutralises_newlines_and_block_markers():
    assert _coq_cell("50 g\njar") == "50 g jar"
    assert _coq_cell("a\r\n[[/TABLE]]\n# heading") == "a [ [/TABLE] ] # heading"
    assert _coq_cell("# heading").startswith("​#")
    assert _coq_cell("[[FORM:grid]]") == "[ [FORM:grid] ]"
    assert _coq_cell("a|b|||c~~d") == "a/b/c-d"


async def test_qc27_batch_ids_are_normalised_and_gates_are_case_insensitive(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC27-MAT")
    coa = await _approved_coa(client, admin_headers, qp, spec["id"], " p050022 ", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    assert coa["batch_id"] == "P050022"
    # an OOS filed in the OCR variant blocks the CoQ (rows written lower-case
    # before normalisation are matched case-insensitively too)
    oos = await _oos(client, admin_headers, batch="P050022")
    pool = await _admin_pool()
    await pool.execute("UPDATE qc_oos_records SET batch_id='p050022' WHERE id=$1", oos["id"])
    r = await client.post("/qc/coq", json={"batch_id": "P050022", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 409 and "open OOS" in r.json()["detail"], r.text


async def test_qc28_qc_identifiers_are_per_org_per_year(client, admin_headers):
    """A fresh org's first spec / sample / lab / water test is 0001 of the
    facility year — not wherever a shared cross-tenant sequence happened to be."""
    yr = str(facility_today().year)
    spec = await _spec(client, admin_headers, material="QC28-MAT")
    assert spec["spec_id"] == f"PP-SPEC-{yr}-0001", spec["spec_id"]
    spec2 = await _spec(client, admin_headers, material="QC28-MAT2")
    assert spec2["spec_id"] == f"PP-SPEC-{yr}-0002"
    sample = await _sample(client, admin_headers, batch="B-QC28")
    assert sample["sample_id"] == f"PP-SMP-{yr}-0001"
    lab = await _lab(client, admin_headers, name="Numbered Lab")
    assert lab["lab_code"] == f"PP-LAB-{yr}-0001"
    wt = (await client.post("/qc/water-tests", json={"location": "L", "grade": "RO", "passed": True},
                            headers=admin_headers)).json()
    assert wt["water_test_id"] == f"PP-WT-{yr}-0001"
    rqs = await _rqs_registered(client, admin_headers, batch_id="B-QC28R")
    sfr = (await client.post("/qc/field-records", json={"rqs_id": rqs["id"], "sampling_location": "x",
                                                        "destination_facility": "y"},
                             headers=admin_headers)).json()
    assert sfr["sfr_number"] == f"PP-SFR-{yr}-0001"


# ── QC-31: the leftovers ────────────────────────────────────────────────────

async def test_qc31_one_transcribed_line_per_parameter(client, admin_headers):
    spec, p = await _ecoa_spec_with_param(client, admin_headers, material="QC31-DUP")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-QC31", report_date="2026-07-01")
    body = {"items": [{"raw_label": "Total THC", "raw_value": "22.0", "unit": "%"}]}
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/extractions", json=body,
                              headers=admin_headers)).status_code == 201
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions", json=body, headers=admin_headers)
    assert r.status_code == 409 and "one transcribed line" in r.json()["detail"], r.text
    exts = (await client.get(f"/qc/coa-documents/{doc['id']}", headers=admin_headers)).json()["extractions"]
    assert len(exts) == 1


async def test_qc31_oos_reference_is_always_validated(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC31-REF")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC31R", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    r = await client.post("/qc/coq", json={"batch_id": "B-QC31R", "specification_id": spec["id"],
                                           "oos_reference": "PP-OOS-2026-0099"}, headers=admin_headers)
    assert r.status_code == 409 and "does not match a CLOSED OOS" in r.json()["detail"], r.text


async def test_qc31_register_lists_aggregation_coqs(client, admin_headers):
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="QC31-REG")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-QC31G", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    coq = (await client.post("/qc/coq", json={"batch_id": "B-QC31G", "specification_id": spec["id"]},
                             headers=admin_headers)).json()
    reg = (await client.get("/qc/register", headers=admin_headers)).json()
    row = next(x for x in reg if x["coa_number"] == coq["coq_number"])
    assert row["cert_type"] == "COQ" and row["record"] == "coq" and row["decision"] == "PASS"
    assert any(x["coa_number"] == coq["coq_number"]
               for x in (await client.get("/qc/register?cert_type=COQ", headers=admin_headers)).json())


async def test_qc31_retention_window_must_be_ordered(client, admin_headers):
    spec = await _spec(client, admin_headers, material="QC31-RET")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-QC31T")
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"retention_start": "2026-07-01"},
                               headers=admin_headers)).status_code == 200
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"retention_expiry": "2026-06-01"},
                           headers=admin_headers)
    assert r.status_code == 422 and "precedes" in r.json()["detail"], r.text


async def test_qc31_oos_register_is_append_only_at_the_db(client, admin_headers, org):
    oos = await _oos(client, admin_headers, batch="B-QC31A")
    from app.db import rls
    me = {"id": org["admin_id"], "org_id": org["org_id"], "role": "ADMIN"}
    async with rls(me) as c:
        tag = await c.execute("UPDATE qc_oos_register SET action='tampered' WHERE oos_id=$1", oos["id"])
        assert tag == "UPDATE 0"
        tag = await c.execute("DELETE FROM qc_oos_register WHERE oos_id=$1", oos["id"])
        assert tag == "DELETE 0"
    reg = (await client.get(f"/qc/oos/{oos['id']}", headers=admin_headers)).json()["register"]
    assert reg and reg[0]["action"] == "opened"


# ── QR-12 / INV-10: the 0071 downgrade preserves records ───────────────────

def test_qr12_the_0071_downgrade_preserves_records_and_refuses_what_it_cannot_hold():
    """The downgrade must not delete COMPILED e-signatures (Annex 11
    evidence), must not recreate the retired sequences at 1 (the pre-0071
    minting would collide with numbers already issued), and must refuse —
    before touching anything — data the old schema cannot hold (RETEST CoQs,
    two APPROVED CoQs of one batch/spec across periods)."""
    import importlib.util
    import pathlib
    import re as _re
    path = pathlib.Path(__file__).resolve().parents[1] / "alembic_tasks" / "versions" / "0071_qc_review_fixes.py"
    src = path.read_text(encoding="utf-8")
    assert "DELETE FROM public.qc_signatures" not in src
    assert not _re.search(r"START WITH 1\b", src), "sequences are seeded past the series max"
    assert "NOT VALID" in src and "RuntimeError" in src
    spec = importlib.util.spec_from_file_location("mig0071", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # every retired sequence maps to the series it fed, and those columns exist
    schema = (path.parents[2] / "schema.tasks.sql").read_text(encoding="utf-8")
    assert set(mod.SERIES) == set(mod._DEAD_SEQUENCES)
    for table, column in mod.SERIES.values():
        block = schema[schema.index(f"CREATE TABLE public.{table} ("):]
        block = block[:block.index("\n);")]
        assert f"    {column} " in block, f"{table}.{column}"
    assert mod.recreate_sequence_sql("qc_spec_id_seq", 17) == (
        "CREATE SEQUENCE public.qc_spec_id_seq AS integer START WITH 18 INCREMENT BY 1")
    assert mod.recreate_sequence_sql("qc_wt_id_seq", 0).endswith("START WITH 1 INCREMENT BY 1")
    assert "regexp_match(spec_id, '-([0-9]+)$')" in mod.series_max_sql("qc_specifications", "spec_id")
    assert mod.unrepresentable(0, 0) == []
    msgs = mod.unrepresentable(2, 1)
    assert len(msgs) == 2 and "RETEST" in msgs[0] and "qc_coq_one_approved_idx" in msgs[1]
