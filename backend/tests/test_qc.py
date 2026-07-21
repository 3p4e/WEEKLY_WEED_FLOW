"""QC LIMS U1 — specifications master data: role gating, the one-ACTIVE-per-
material constraint, guarded lifecycle transitions, and parameter authoring."""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role):
    user, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, user["username"], otp)
    return user, {"Authorization": f"Bearer {token}"}


async def _spec(client, headers, material="CANN-FLOS-D", version=1, **extra):
    body = {"material_code": material, "material_name_en": "Cannabis flos",
            "material_name_mk": "Каннабис цвет", "version": version, **extra}
    r = await client.post("/qc/specifications", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_list_get_specification(client, admin_headers):
    spec = await _spec(client, admin_headers)
    assert spec["spec_id"].startswith("PP-SPEC-") and spec["status"] == "DRAFT"
    r = await client.get("/qc/specifications", headers=admin_headers)
    assert r.status_code == 200 and any(s["id"] == spec["id"] for s in r.json())
    r = await client.get(f"/qc/specifications/{spec['id']}", headers=admin_headers)
    assert r.status_code == 200 and r.json()["spec"]["id"] == spec["id"]
    assert r.json()["parameters"] == []


async def test_date_fields_accept_real_iso_dates(client, admin_headers):
    """effective_date/sampling_date/report_date/result_date are bound with an
    explicit ::date cast — asyncpg rejects that cast unless given a real date
    object, so a Pydantic field typed str (rather than date) 500s the moment
    a real value is supplied. Every creation path is exercised here with an
    actual ISO date, not just the all-null defaults the other tests use."""
    spec = await _spec(client, admin_headers, material="DATE-MAT", effective_date="2026-07-01")
    assert spec["effective_date"] == "2026-07-01"
    r = await client.patch(f"/qc/specifications/{spec['id']}", json={"effective_date": "2026-08-01"},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["effective_date"] == "2026-08-01"

    sample = await _sample(client, admin_headers, batch="B-DATE", sampling_date="2026-07-02")
    assert sample["sampling_date"] == "2026-07-02"

    coa = await _coa(client, admin_headers, spec["id"], report_date="2026-07-03")
    assert coa["report_date"] == "2026-07-03"
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"report_date": "2026-08-03"},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["report_date"] == "2026-08-03"

    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Moisture", "result_numeric": 8.0,
                                "lower_limit": 5.0, "upper_limit": 12.0, "result_date": "2026-07-04"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["result_date"] == "2026-07-04"


async def test_role_gating(client, admin_headers):
    spec = await _spec(client, admin_headers, material="ROLE-MAT")
    # base USER: no read
    _, user_h = await _actor(client, admin_headers, "USER")
    assert (await client.get("/qc/specifications", headers=user_h)).status_code == 403
    # QC_MGR: reads AND writes (owns the domain)
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.get("/qc/specifications", headers=qc_h)).status_code == 200
    r = await client.post("/qc/specifications",
                          json={"material_code": "QCM-MAT", "material_name_en": "x"}, headers=qc_h)
    assert r.status_code == 201, r.text
    # a non-QC manager (CU_MGR) may READ (elevated) but NOT write
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/qc/specifications", headers=cu_h)).status_code == 200
    r = await client.post("/qc/specifications",
                          json={"material_code": "CU-MAT", "material_name_en": "x"}, headers=cu_h)
    assert r.status_code == 403


async def test_only_one_active_spec_per_material(client, admin_headers):
    """The partial unique index guards dual-activation. Walk one spec to ACTIVE,
    then a second version of the SAME material must not also go ACTIVE."""
    async def _to_active(sid):
        for tgt in ("QC_REVIEW", "QA_APPROVED", "NUMBERED", "TRAINED", "ACTIVE"):
            r = await client.patch(f"/qc/specifications/{sid}", json={"status": tgt}, headers=admin_headers)
            assert r.status_code == 200, (tgt, r.text)
    a = await _spec(client, admin_headers, material="DUP-MAT", version=1)
    await _to_active(a["id"])
    b = await _spec(client, admin_headers, material="DUP-MAT", version=2)
    # drive b to TRAINED, then the ACTIVE step must 409 (index conflict)
    for tgt in ("QC_REVIEW", "QA_APPROVED", "NUMBERED", "TRAINED"):
        assert (await client.patch(f"/qc/specifications/{b['id']}", json={"status": tgt},
                                   headers=admin_headers)).status_code == 200
    r = await client.patch(f"/qc/specifications/{b['id']}", json={"status": "ACTIVE"}, headers=admin_headers)
    assert r.status_code == 409, r.text


async def test_illegal_lifecycle_transition_rejected(client, admin_headers):
    spec = await _spec(client, admin_headers, material="LC-MAT")  # DRAFT
    # DRAFT -> ACTIVE is not a legal single step
    r = await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "ACTIVE"}, headers=admin_headers)
    assert r.status_code == 409
    # DRAFT -> QC_REVIEW is legal; QC_REVIEW -> DRAFT (reject) is legal
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "QC_REVIEW"},
                               headers=admin_headers)).status_code == 200
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "DRAFT"},
                               headers=admin_headers)).status_code == 200
    # unknown status is 422
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "BOGUS"},
                               headers=admin_headers)).status_code == 422


async def test_duplicate_material_version_conflicts(client, admin_headers):
    await _spec(client, admin_headers, material="UNIQ-MAT", version=1)
    r = await client.post("/qc/specifications",
                          json={"material_code": "UNIQ-MAT", "material_name_en": "y", "version": 1},
                          headers=admin_headers)
    assert r.status_code == 409, r.text


async def test_bad_thc_grade_rejected(client, admin_headers):
    r = await client.post("/qc/specifications",
                          json={"material_code": "G-MAT", "material_name_en": "x", "thc_grade": "GRADE_IX"},
                          headers=admin_headers)
    assert r.status_code == 422


async def test_parameters_add_and_lock_after_authoring(client, admin_headers):
    spec = await _spec(client, admin_headers, material="PARAM-MAT")
    # add a parameter while DRAFT (authoring) — limits may be null (never fabricated)
    r = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                                "unit": "%", "lower_limit": None, "upper_limit": 30.0,
                                "pharmacopoeia_ref": "Ph.Eur. 3028"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    param_id = r.json()["id"]
    assert r.json()["lower_limit"] is None and r.json()["upper_limit"] == 30.0
    detail = (await client.get(f"/qc/specifications/{spec['id']}", headers=admin_headers)).json()
    assert len(detail["parameters"]) == 1
    # move past authoring → parameters lock
    for tgt in ("QC_REVIEW", "QA_APPROVED"):
        assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": tgt},
                                   headers=admin_headers)).status_code == 200
    r = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Water"}, headers=admin_headers)
    assert r.status_code == 409
    r = await client.delete(f"/qc/specifications/{spec['id']}/parameters/{param_id}", headers=admin_headers)
    assert r.status_code == 409


# ── QC LIMS U2 — samples + lifecycle ────────────────────────────────────────
async def _sample(client, headers, batch="B-2026-001", **extra):
    body = {"batch_id": batch, "material_code": "CANN-FLOS-D", "sample_type": "flos", **extra}
    r = await client.post("/qc/samples", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_and_list_sample(client, admin_headers):
    s = await _sample(client, admin_headers)
    assert s["sample_id"].startswith("PP-SMP-") and s["status"] == "COLLECTED"
    r = await client.get("/qc/samples", headers=admin_headers)
    assert r.status_code == 200 and any(x["id"] == s["id"] for x in r.json())
    r = await client.get(f"/qc/samples?batch_id={s['batch_id']}", headers=admin_headers)
    assert r.status_code == 200 and len(r.json()) >= 1


async def test_sample_lifecycle_happy_path(client, admin_headers):
    s = await _sample(client, admin_headers, batch="B-LC")
    chain = ["RECEIVED", "IN_TEST", "TESTED", "REVIEWED", "APPROVED", "RELEASED"]
    for tgt in chain:
        r = await client.patch(f"/qc/samples/{s['id']}", json={"status": tgt}, headers=admin_headers)
        assert r.status_code == 200, (tgt, r.text)
        assert r.json()["status"] == tgt


async def test_sample_illegal_transition_rejected(client, admin_headers):
    s = await _sample(client, admin_headers, batch="B-ILL")
    # COLLECTED -> RELEASED is not legal
    r = await client.patch(f"/qc/samples/{s['id']}", json={"status": "RELEASED"}, headers=admin_headers)
    assert r.status_code == 409
    # out-of-spec branch: IN_TEST -> QUARANTINE, then QUARANTINE -> IN_TEST (retest)
    for tgt in ("RECEIVED", "IN_TEST", "QUARANTINE", "IN_TEST"):
        assert (await client.patch(f"/qc/samples/{s['id']}", json={"status": tgt},
                                   headers=admin_headers)).status_code == 200
    # unknown status 422
    assert (await client.patch(f"/qc/samples/{s['id']}", json={"status": "NOPE"},
                               headers=admin_headers)).status_code == 422


async def test_release_reject_is_qp_gated(client, admin_headers):
    """RELEASED/REJECTED are QP-level; a QC_MGR can drive the sample up to
    APPROVED but not RELEASE it — that's the Qualified Person's call."""
    s = await _sample(client, admin_headers, batch="B-QP")
    for tgt in ("RECEIVED", "IN_TEST", "TESTED", "REVIEWED", "APPROVED"):
        assert (await client.patch(f"/qc/samples/{s['id']}", json={"status": tgt},
                                   headers=admin_headers)).status_code == 200
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    r = await client.patch(f"/qc/samples/{s['id']}", json={"status": "RELEASED"}, headers=qc_h)
    assert r.status_code == 403, r.text          # QC_MGR may not release
    _, qp_h = await _actor(client, admin_headers, "QP")
    r = await client.patch(f"/qc/samples/{s['id']}", json={"status": "RELEASED"}, headers=qp_h)
    assert r.status_code == 200, r.text          # QP may


async def test_sample_genealogy(client, admin_headers):
    parent = await _sample(client, admin_headers, batch="B-GEN")
    child = await _sample(client, admin_headers, batch="B-GEN", parent_id=parent["id"], retention_sample=True)
    assert child["parent_id"] == parent["id"]
    detail = (await client.get(f"/qc/samples/{parent['id']}", headers=admin_headers)).json()
    assert [k["id"] for k in detail["children"]] == [child["id"]]
    # unknown parent rejected. Flip the last hex digit to a guaranteed-
    # different, still-valid UUID (don't just append "0" — if the real id
    # already ends in "0" that reproduces the existing parent and the create
    # wrongly succeeds).
    missing_parent = parent["id"][:-1] + ("1" if parent["id"][-1] == "0" else "0")
    r = await client.post("/qc/samples",
                          json={"batch_id": "B-X", "material_code": "M", "parent_id": missing_parent},
                          headers=admin_headers)
    assert r.status_code in (422, 404)


async def test_sample_role_gating(client, admin_headers):
    s = await _sample(client, admin_headers, batch="B-ROLE")
    _, user_h = await _actor(client, admin_headers, "USER")
    assert (await client.get("/qc/samples", headers=user_h)).status_code == 403
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/qc/samples", headers=cu_h)).status_code == 200   # elevated read
    r = await client.post("/qc/samples", json={"batch_id": "B-CU", "material_code": "M"}, headers=cu_h)
    assert r.status_code == 403                                                 # non-QC manager can't write


async def test_sample_kind_taxonomy_and_retention(client, admin_headers):
    """QCSOP 011 §6.2.1 sample-type taxonomy + §7.0 retention expiry."""
    s = await _sample(client, admin_headers, batch="B-KIND-1",
                      sample_kind="RET", retention_expiry="2027-12-31")
    assert s["sample_kind"] == "RET" and s["retention_expiry"] == "2027-12-31"
    # a bad kind is rejected on create and on patch
    r = await client.post("/qc/samples",
                          json={"batch_id": "B-KIND-2", "material_code": "M", "sample_kind": "ZZ"},
                          headers=admin_headers)
    assert r.status_code == 422 and "6.2.1" in r.text
    r = await client.patch(f"/qc/samples/{s['id']}", json={"sample_kind": "ZZ"}, headers=admin_headers)
    assert r.status_code == 422
    # a valid kind updates
    r = await client.patch(f"/qc/samples/{s['id']}", json={"sample_kind": "STAB"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["sample_kind"] == "STAB"


async def test_sample_non_conforming_flag(client, admin_headers):
    """§6.7 — a sample can be flagged non-conforming with a reason and cleared."""
    s = await _sample(client, admin_headers, batch="B-NC-1")
    assert s["non_conforming"] is False
    r = await client.patch(f"/qc/samples/{s['id']}",
                           json={"non_conforming": True, "non_conforming_reason": "seal breach in transit"},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["non_conforming"] is True
    assert r.json()["non_conforming_reason"] == "seal breach in transit"
    # clearing sets it back and nulls the reason
    r = await client.patch(f"/qc/samples/{s['id']}",
                           json={"non_conforming": False, "non_conforming_reason": None}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["non_conforming"] is False and r.json()["non_conforming_reason"] is None


async def test_sampling_plan_create_and_list(client, admin_headers):
    r = await client.post("/qc/sampling-plans",
                          json={"material_code": "CANN-FLOS-D", "sampling_frequency": "EVERY_BATCH"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["plan_id"].startswith("PP-SPL-")
    r = await client.get("/qc/sampling-plans", headers=admin_headers)
    assert r.status_code == 200 and len(r.json()) >= 1
    # bad frequency 422
    r = await client.post("/qc/sampling-plans",
                          json={"material_code": "X", "sampling_frequency": "HOURLY"}, headers=admin_headers)
    assert r.status_code == 422


# ── QC LIMS U3 — certificates of analysis + test results ────────────────────
async def _coa(client, headers, spec_id, batch="B-COA-1", **extra):
    body = {"batch_id": batch, "specification_id": spec_id, **extra}
    r = await client.post("/qc/certificates", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_and_get_coa(client, admin_headers):
    spec = await _spec(client, admin_headers, material="COA-MAT")
    coa = await _coa(client, admin_headers, spec["id"])
    assert coa["coa_number"].startswith("iCoA-PP-") and coa["status"] == "DRAFT"
    assert coa["cert_type"] == "ICOA" and coa["specification_id"] == spec["id"]
    r = await client.get("/qc/certificates", headers=admin_headers)
    assert r.status_code == 200 and any(x["id"] == coa["id"] for x in r.json())
    detail = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()
    assert detail["coa"]["id"] == coa["id"] and detail["results"] == []


async def test_result_auto_evaluates_complies(client, admin_headers):
    spec = await _spec(client, admin_headers, material="EVAL-MAT")
    coa = await _coa(client, admin_headers, spec["id"])
    # in-spec numeric → complies True, status pass
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Total THC", "result_numeric": 22.0,
                                "lower_limit": 18.0, "upper_limit": 30.0, "unit": "%"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["complies"] is True and r.json()["status"] == "pass"
    # out-of-spec numeric → complies False, status fail
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Water", "result_numeric": 15.0, "upper_limit": 10.0},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["complies"] is False and r.json()["status"] == "fail"
    # no numeric measurement → complies null, status unknown (never fabricated)
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Appearance", "result_value": "Compliant"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["complies"] is None and r.json()["status"] == "unknown"
    detail = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()
    assert len(detail["results"]) == 3


async def test_result_snapshots_parameter_limits(client, admin_headers):
    """When a result cites a spec parameter and supplies no limits, it snapshots
    the parameter's limits — the specification is the single source of truth."""
    spec = await _spec(client, admin_headers, material="SNAP-MAT")
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Total THC", "unit": "%",
                                "lower_limit": 18.0, "upper_limit": 30.0}, headers=admin_headers)
    param_id = p.json()["id"]
    coa = await _coa(client, admin_headers, spec["id"])
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Total THC", "parameter_id": param_id,
                                "result_numeric": 40.0}, headers=admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["lower_limit"] == 18.0 and body["upper_limit"] == 30.0
    assert body["complies"] is False   # 40 > 30


async def test_failing_result_quarantines_linked_sample(client, admin_headers):
    """OOS hook: a failing result on a CoA that links a still-testable sample
    flags that sample QUARANTINE."""
    spec = await _spec(client, admin_headers, material="OOS-MAT")
    s = await _sample(client, admin_headers, batch="B-OOS")
    for tgt in ("RECEIVED", "IN_TEST"):
        assert (await client.patch(f"/qc/samples/{s['id']}", json={"status": tgt},
                                   headers=admin_headers)).status_code == 200
    coa = await _coa(client, admin_headers, spec["id"], batch="B-OOS", sample_id=s["id"])
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Total Aerobic Count", "result_numeric": 5000.0,
                                "upper_limit": 1000.0}, headers=admin_headers)
    assert r.status_code == 201 and r.json()["complies"] is False
    detail = (await client.get(f"/qc/samples/{s['id']}", headers=admin_headers)).json()
    assert detail["sample"]["status"] == "QUARANTINE"


async def test_passing_result_leaves_sample_untouched(client, admin_headers):
    spec = await _spec(client, admin_headers, material="OK-MAT")
    s = await _sample(client, admin_headers, batch="B-OK")
    assert (await client.patch(f"/qc/samples/{s['id']}", json={"status": "RECEIVED"},
                               headers=admin_headers)).status_code == 200
    coa = await _coa(client, admin_headers, spec["id"], batch="B-OK", sample_id=s["id"])
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Water", "result_numeric": 5.0, "upper_limit": 10.0},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["complies"] is True
    detail = (await client.get(f"/qc/samples/{s['id']}", headers=admin_headers)).json()
    assert detail["sample"]["status"] == "RECEIVED"   # untouched


async def test_coa_reviewer_must_differ_from_analyst(client, admin_headers):
    spec = await _spec(client, admin_headers, material="REV-MAT")
    coa = await _coa(client, admin_headers, spec["id"])   # analyst = admin
    # same person cannot review their own CoA (GxP second-person review)
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "REVIEWED"},
                           headers=admin_headers)
    assert r.status_code == 403, r.text
    # a different qualified person may
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "REVIEWED"}, headers=qc_h)
    assert r.status_code == 200 and r.json()["status"] == "REVIEWED"
    assert r.json()["reviewer_id"] is not None


async def test_coa_approve_release_qp_gated(client, admin_headers):
    spec = await _spec(client, admin_headers, material="QPG-MAT")
    coa = await _coa(client, admin_headers, spec["id"])   # analyst = admin
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "REVIEWED"},
                               headers=qc_h)).status_code == 200
    # QC_MGR cannot APPROVE (Qualified-Person decision)
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "APPROVED"}, headers=qc_h)
    assert r.status_code == 403, r.text
    _, qp_h = await _actor(client, admin_headers, "QP")
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "APPROVED"},
                               headers=qp_h)).status_code == 200
    # QC_MGR cannot RELEASE; QP can
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "RELEASED"},
                               headers=qc_h)).status_code == 403
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "RELEASED"}, headers=qp_h)
    assert r.status_code == 200 and r.json()["status"] == "RELEASED" and r.json()["approver_id"] is not None


async def test_results_only_in_draft(client, admin_headers):
    spec = await _spec(client, admin_headers, material="LOCK-MAT")
    coa = await _coa(client, admin_headers, spec["id"])
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "REVIEWED"},
                               headers=qc_h)).status_code == 200
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Late", "result_numeric": 1.0}, headers=admin_headers)
    assert r.status_code == 409, r.text


async def test_coa_bad_refs_and_illegal_transition(client, admin_headers):
    _ZERO = "00000000-0000-0000-0000-000000000000"
    # unknown specification → 422
    r = await client.post("/qc/certificates",
                          json={"batch_id": "B", "specification_id": _ZERO}, headers=admin_headers)
    assert r.status_code == 422
    spec = await _spec(client, admin_headers, material="BADREF-MAT")
    # unknown sample → 422
    r = await client.post("/qc/certificates",
                          json={"batch_id": "B", "specification_id": spec["id"], "sample_id": _ZERO},
                          headers=admin_headers)
    assert r.status_code == 422
    # bad cert_type → 422
    r = await client.post("/qc/certificates",
                          json={"batch_id": "B", "specification_id": spec["id"], "cert_type": "BOGUS"},
                          headers=admin_headers)
    assert r.status_code == 422
    # illegal lifecycle jump DRAFT -> APPROVED → 409 (transition guard beats role check)
    coa = await _coa(client, admin_headers, spec["id"], batch="B-JUMP")
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "APPROVED"}, headers=admin_headers)
    assert r.status_code == 409


async def test_coa_role_gating(client, admin_headers):
    spec = await _spec(client, admin_headers, material="COAROLE-MAT")
    await _coa(client, admin_headers, spec["id"])
    _, user_h = await _actor(client, admin_headers, "USER")
    assert (await client.get("/qc/certificates", headers=user_h)).status_code == 403
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/qc/certificates", headers=cu_h)).status_code == 200   # elevated read
    r = await client.post("/qc/certificates",
                          json={"batch_id": "B", "specification_id": spec["id"]}, headers=cu_h)
    assert r.status_code == 403   # non-QC manager cannot write


# ── QC LIMS U4 — OOS investigations + CAPA ──────────────────────────────────
async def _oos(client, headers, batch="B-OOS-1", **extra):
    body = {"batch_id": batch, "oos_type": "OOS", "test_name": "Total THC", **extra}
    r = await client.post("/qc/oos", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_list_get_oos(client, admin_headers):
    oos = await _oos(client, admin_headers)
    assert oos["oos_number"].startswith("PP-OOS-") and oos["status"] == "OPEN" and oos["phase"] == "I"
    r = await client.get("/qc/oos", headers=admin_headers)
    assert r.status_code == 200 and any(x["id"] == oos["id"] for x in r.json())
    detail = (await client.get(f"/qc/oos/{oos['id']}", headers=admin_headers)).json()
    assert detail["oos"]["id"] == oos["id"]
    # the create stamps an append-only "opened" register event
    assert [e["action"] for e in detail["register"]] == ["opened"]
    assert detail["notifications"] == []


async def test_oos_lifecycle_and_qp_close_gate(client, admin_headers):
    oos = await _oos(client, admin_headers, batch="B-LC")
    # OPEN -> PHASE_I -> PHASE_II by the QC manager
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    oos = (await client.post("/qc/oos", json={"batch_id": "B-LC2", "test_name": "Water"},
                             headers=qc_h)).json()
    for tgt in ("PHASE_I", "PHASE_II"):
        r = await client.patch(f"/qc/oos/{oos['id']}", json={"status": tgt}, headers=qc_h)
        assert r.status_code == 200 and r.json()["status"] == tgt
    # CLOSE is a QP decision — QC manager is refused, QP allowed
    assert (await client.patch(f"/qc/oos/{oos['id']}", json={"status": "CLOSED"},
                               headers=qc_h)).status_code == 403
    _, qp_h = await _actor(client, admin_headers, "QP")
    r = await client.patch(f"/qc/oos/{oos['id']}", json={"status": "CLOSED"}, headers=qp_h)
    assert r.status_code == 200 and r.json()["status"] == "CLOSED"
    assert r.json()["closed_at"] is not None
    # register recorded each transition
    detail = (await client.get(f"/qc/oos/{oos['id']}", headers=qp_h)).json()
    actions = [e["action"] for e in detail["register"]]
    assert "opened" in actions and any(a.startswith("status:PHASE_II->CLOSED") for a in actions)


async def test_oos_illegal_transition_and_bad_enums(client, admin_headers):
    oos = await _oos(client, admin_headers, batch="B-BAD")
    # OPEN -> PHASE_II skips Phase I
    assert (await client.patch(f"/qc/oos/{oos['id']}", json={"status": "PHASE_II"},
                               headers=admin_headers)).status_code == 409
    # unknown enum values
    assert (await client.patch(f"/qc/oos/{oos['id']}", json={"status": "BOGUS"},
                               headers=admin_headers)).status_code == 422
    assert (await client.patch(f"/qc/oos/{oos['id']}", json={"risk_level": "SEVERE"},
                               headers=admin_headers)).status_code == 422
    assert (await client.post("/qc/oos", json={"batch_id": "B", "oos_type": "NOPE"},
                              headers=admin_headers)).status_code == 422


async def test_oos_disposition_is_qp_gated(client, admin_headers):
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    oos = (await client.post("/qc/oos", json={"batch_id": "B-DISP"}, headers=qc_h)).json()
    # QC manager cannot set a batch disposition
    assert (await client.patch(f"/qc/oos/{oos['id']}", json={"disposition": "REJECT",
            "disposition_reason": "confirmed OOS"}, headers=qc_h)).status_code == 403
    _, qp_h = await _actor(client, admin_headers, "QP")
    r = await client.patch(f"/qc/oos/{oos['id']}", json={"disposition": "REJECT",
                           "disposition_reason": "confirmed OOS"}, headers=qp_h)
    assert r.status_code == 200 and r.json()["disposition"] == "REJECT"


async def test_oos_register_is_append_only_endpoint(client, admin_headers):
    oos = await _oos(client, admin_headers, batch="B-REG")
    r = await client.post(f"/qc/oos/{oos['id']}/register",
                          json={"action": "sample_retested", "details": "retest within spec"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["action"] == "sample_retested"
    detail = (await client.get(f"/qc/oos/{oos['id']}", headers=admin_headers)).json()
    assert [e["action"] for e in detail["register"]] == ["opened", "sample_retested"]


async def test_oos_notifications_and_ack(client, admin_headers):
    oos = await _oos(client, admin_headers, batch="B-NOTIF")
    r = await client.post(f"/qc/oos/{oos['id']}/notifications",
                          json={"part": "A", "recipients": ["qa@x", "qp@x"], "message": "OOS Part A"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["acknowledged"] is False
    assert r.json()["recipients"] == ["qa@x", "qp@x"]
    notif_id = r.json()["id"]
    assert (await client.post("/qc/oos/%s/notifications" % oos["id"], json={"part": "Z"},
                              headers=admin_headers)).status_code == 422   # bad part
    r = await client.post(f"/qc/oos/{oos['id']}/notifications/{notif_id}/ack", headers=admin_headers)
    assert r.status_code == 200 and r.json()["acknowledged"] is True and r.json()["acknowledged_at"]


async def test_capa_derived_from_oos(client, admin_headers):
    # fresh OOS → CAPA OPEN
    oos = await _oos(client, admin_headers, batch="B-CAPA")
    capa = (await client.get("/qc/capa", headers=admin_headers)).json()
    mine = next(x for x in capa if x["oos_id"] == oos["id"])
    assert mine["status"] == "OPEN" and mine["id"] == f"CAPA-{oos['oos_number']}"
    # add a root cause → IN_PROGRESS
    await client.patch(f"/qc/oos/{oos['id']}",
                       json={"root_cause_description": "miscalibrated balance"}, headers=admin_headers)
    mine = next(x for x in (await client.get("/qc/capa", headers=admin_headers)).json()
                if x["oos_id"] == oos["id"])
    assert mine["status"] == "IN_PROGRESS" and mine["title"] == "miscalibrated balance"
    # effectiveness check recorded → EFFECTIVE; status filter works
    await client.patch(f"/qc/oos/{oos['id']}",
                       json={"effectiveness_check_date": "2026-07-10",
                             "effectiveness_check_result": "verified"}, headers=admin_headers)
    eff = (await client.get("/qc/capa?status=EFFECTIVE", headers=admin_headers)).json()
    assert any(x["oos_id"] == oos["id"] for x in eff)


async def test_oos_bad_refs_and_date_fields(client, admin_headers):
    _ZERO = "00000000-0000-0000-0000-000000000000"
    assert (await client.post("/qc/oos", json={"batch_id": "B", "result_id": _ZERO},
                              headers=admin_headers)).status_code == 422
    assert (await client.post("/qc/oos", json={"batch_id": "B", "sample_id": _ZERO},
                              headers=admin_headers)).status_code == 422
    # real ISO dates on every date field (guards the ::date/str asyncpg class of bug)
    oos = await _oos(client, admin_headers, batch="B-DATES",
                     detection_date="2026-07-01", timeline_deadline="2026-07-08")
    assert oos["detection_date"] == "2026-07-01" and oos["timeline_deadline"] == "2026-07-08"
    r = await client.patch(f"/qc/oos/{oos['id']}",
                           json={"effectiveness_check_date": "2026-07-20"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["effectiveness_check_date"] == "2026-07-20"


async def test_oos_role_gating(client, admin_headers):
    await _oos(client, admin_headers, batch="B-ROLE")
    _, user_h = await _actor(client, admin_headers, "USER")
    assert (await client.get("/qc/oos", headers=user_h)).status_code == 403
    assert (await client.get("/qc/capa", headers=user_h)).status_code == 403
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/qc/oos", headers=cu_h)).status_code == 200          # elevated read
    assert (await client.post("/qc/oos", json={"batch_id": "B"}, headers=cu_h)).status_code == 403


# ── Phase 3 U1 — Certificate of Quality (COQ) generation ────────────────────
from app.api import qc as _qc_mod          # noqa: E402
from app.config import settings as _settings  # noqa: E402


class _FakeDE:
    """Stands in for the DocEngine httpx client — records the markdown it was
    asked to build so the assembler can be asserted, returns a canned build."""
    last_markdown = None

    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def request(self, method, path, json=None, **kw):
        _FakeDE.last_markdown = (json or {}).get("markdown")

        class _R:
            status_code = 200

            def __init__(self, d):
                self._d = d

            def json(self):
                return self._d
        if isinstance(self._resp, Exception):
            raise self._resp
        return _R(self._resp)


def _stub_de(monkeypatch, resp):
    monkeypatch.setattr(_settings, "docengine_api_key", "test-de-key")
    monkeypatch.setattr(_qc_mod, "_coq_client", lambda timeout=20.0: _FakeDE(resp))


async def _released_coa(client, headers, qp_headers, material="COQ-MAT", results=None):
    """A CoA driven to RELEASED with the given results. Header user is the
    analyst; qp_headers reviews (must differ from analyst) → approves → releases.
    The default result CITES the spec parameter — the COQ completeness gate
    counts only parameter-cited results as coverage."""
    spec = await _spec(client, headers, material=material)
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                                "test_method": "HPLC", "unit": "%", "lower_limit": 10.0,
                                "upper_limit": 30.0}, headers=headers)
    assert p.status_code == 201, p.text
    # report_date + PASS disposition are WHO/Annex-16 mandatory COQ content
    coa = await _coa(client, headers, spec["id"], batch="B-COQ", report_date="2026-07-01")
    for r in (results or [{"parameter_id": p.json()["id"], "test_name": "Total THC",
                           "result_numeric": 22.0,
                           "lower_limit": 10.0, "upper_limit": 30.0, "unit": "%",
                           "source_document_code": "ECOA-LAB-001"}]):
        assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                                  json=r, headers=headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": "PASS"}, headers=headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp_headers)).status_code == 200, tgt
    return coa


# ── QCSOP 012 v3 — Tier 1 (Void + External CoA Review Checklist + register) ──
async def test_void_certificate(client, admin_headers):
    """§6.6 — a fundamentally-invalid certificate is VOIDED with a written reason
    by the Head of QC; the record is retained; it cannot be voided twice, and a
    non-QC writer may not void."""
    spec = await _spec(client, admin_headers, material="VOID-MAT")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-VOID")
    # a reason is mandatory (min length) → 422
    r = await client.post(f"/qc/certificates/{coa['id']}/void", json={"reason": ""}, headers=admin_headers)
    assert r.status_code == 422
    # a non-QC writer (executive) cannot void
    _, ceo = await _actor(client, admin_headers, "CEO")
    r = await client.post(f"/qc/certificates/{coa['id']}/void",
                          json={"reason": "wrong batch identified"}, headers=ceo)
    assert r.status_code == 403
    # the QC Manager voids it
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/certificates/{coa['id']}/void",
                          json={"reason": "wrong sample tested"}, headers=qc)
    assert r.status_code == 200 and r.json()["status"] == "VOIDED"
    assert r.json()["void_reason"] == "wrong sample tested" and r.json()["voided_by"]
    assert r.json()["sop_status"] == "Voided"
    # a voided certificate cannot be voided again, revised, or generate a CoQ
    assert (await client.post(f"/qc/certificates/{coa['id']}/void",
                              json={"reason": "again"}, headers=qc)).status_code == 409
    assert (await client.post(f"/qc/certificates/{coa['id']}/revise",
                              json={"reason": "cannot revise a voided certificate"}, headers=qc)).status_code == 409
    # it is still retained/readable (never deleted)
    assert (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).status_code == 200
    # §6.6 immutability — a voided record's substantive fields are frozen, but the
    # retention/archive register fields may still be maintained.
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 409
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"archive_ref": "SHELF-A-12"}, headers=admin_headers)).status_code == 200


async def test_ecoa_review_checklist(client, admin_headers):
    """§6.3.2 — the External CoA Review Checklist (QCT 018): the reviewer fills the
    affirmations, the Head of QC signs ACCEPTED only when all are affirmed with no
    open discrepancies, and a decided checklist is locked."""
    doc = await _ecoa_doc(client, admin_headers, batch="B-CL-1")
    # no checklist yet
    assert (await client.get(f"/qc/coa-documents/{doc['id']}/checklist", headers=admin_headers)).json() is None
    # fill it, but with a discrepancy + one affirmation missing
    r = await client.put(f"/qc/coa-documents/{doc['id']}/checklist",
                         json={"sample_id_match": True, "method_per_tqa": True,
                               "units_per_spec": True, "conformance_by_pp": False,
                               "discrepancies": "Pb units differ"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["outcome"] == "PENDING"
    # cannot ACCEPT while an affirmation is false / a discrepancy is open
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/checklist/decide",
                          json={"outcome": "ACCEPTED"}, headers=qc)
    assert r.status_code == 422
    # a plain writer cannot decide (HoQC act)
    _, ceo = await _actor(client, admin_headers, "CEO")
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/checklist/decide",
                              json={"outcome": "ACCEPTED"}, headers=ceo)).status_code == 403
    # clear the discrepancy + affirm all, then accept
    r = await client.put(f"/qc/coa-documents/{doc['id']}/checklist",
                         json={"conformance_by_pp": True, "discrepancies": ""}, headers=admin_headers)
    assert r.status_code == 200
    r = await client.post(f"/qc/coa-documents/{doc['id']}/checklist/decide",
                          json={"outcome": "ACCEPTED"}, headers=qc)
    assert r.status_code == 200 and r.json()["outcome"] == "ACCEPTED" and r.json()["reviewed_by"]
    # locked: no further edits, no re-decide
    assert (await client.put(f"/qc/coa-documents/{doc['id']}/checklist",
                             json={"notes": "x"}, headers=admin_headers)).status_code == 409
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/checklist/decide",
                              json={"outcome": "REJECTED"}, headers=qc)).status_code == 409


async def test_register_sop_status_labels(client, admin_headers):
    """§6.13 — the register presents the SOP status vocabulary. A released cert is
    'Issued'; a released revision is 'Revised'."""
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="REG-SOP")
    reg = (await client.get("/qc/register", headers=admin_headers)).json()
    row = next(x for x in reg if x["id"] == coa["id"])
    assert row["sop_status"] == "Issued"
    rev = (await client.post(f"/qc/certificates/{coa['id']}/revise",
                             json={"reason": "typo in units"}, headers=admin_headers)).json()
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{rev['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    reg = (await client.get("/qc/register", headers=admin_headers)).json()
    assert next(x for x in reg if x["id"] == rev["id"])["sop_status"] == "Revised"
    assert next(x for x in reg if x["id"] == coa["id"])["sop_status"] == "Superseded"


async def test_coq_generates_from_released_cert(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "DE-COQ-1", "verify": "RESULT: PASS", "bytes": 4096})
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp)
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["document_id"] == "DE-COQ-1" and r.json()["verify"] == "RESULT: PASS"
    # the doc id is persisted on the cert for re-download/audit
    detail = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()
    assert detail["coa"]["coq_document_id"] == "DE-COQ-1" and detail["coa"]["coq_generated_at"]
    # the assembled markdown is bilingual, GMP-worded, and never says "EU GMP"
    md = _FakeDE.last_markdown
    assert "Certificate of Quality" in md and "Сертификат за квалитет" in md
    assert "MK GMP Certified Facility" in md and "EU GMP" not in md
    assert "ECOA-LAB-001" in md          # every line maps back to its source doc


async def test_coq_layout_has_house_template_sections(client, admin_headers, monkeypatch):
    """D1 layout parity: the assembled CoQ carries the approved house-template
    structure — the identity meta grid, the §01/§02 navy section banners, the
    batch disposition, the QC compliance statement, and the signatures block."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-L", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="COQ-LAYOUT")
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    for token in ("Certificate №", "01 Analytical Results", "02 Laboratory",
                  "Overall Batch Disposition", "QC Compliance Statement", "Signatures",
                  "Manufacturer", "Purely Plant DOOEL", "№~~№"):
        assert token in md, token
    # numbers are labelled with the numero sign, never the "No." abbreviation
    assert "№" in md and "No." not in md


async def test_coq_metadata_roundtrips_and_renders(client, admin_headers, monkeypatch):
    """The CoQ house-template metadata (mig 0038) round-trips through the
    certificate and surfaces on the rendered CoQ; an unset field is simply
    absent — never fabricated."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-M", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="COQ-META")
    meta = {"cultivation_batch": "AB092501", "product_code": "PP-sFP-THC15:CBD1",
            "packaging": "400.0 g ±3% · Triplex Alu Bag", "manufacture_date": "2025-12-01",
            "expiry_date": "2026-12-01", "botanical_type": "Hybrid · Indica-dominant",
            "chemotype": "THC-dominant chemotype"}
    # metadata is editable on a released cert (it's descriptive, not a result)
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json=meta, headers=admin_headers)).status_code == 200
    got = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()["coa"]
    for k, v in meta.items():
        assert got[k] == v, k
    assert got["retest_date"] is None                     # unset stays null
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "AB092501" in md and "Hybrid · Indica-dominant" in md
    assert "Triplex Alu Bag" in md and "THC-dominant chemotype" in md


async def test_coq_source_crossref_derived_from_provenance(client, admin_headers, monkeypatch):
    """§02 lab cross-reference is derived from the results' cited provenance —
    each distinct external source lettered A, B…, in-house 'Q' — with no new
    schema and nothing fabricated."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-X", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="COQ-XREF")
    params = []
    for nm in ("Assay", "Heavy Metals", "Foreign Matter"):
        p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                              json={"test_name_en": nm, "test_method": "Ph. Eur.",
                                    "unit": "%", "lower_limit": 0.0, "upper_limit": 100.0},
                              headers=admin_headers)
        params.append(p.json()["id"])
    coa = await _coa(client, admin_headers, spec["id"], batch="B-XREF", report_date="2026-07-01")
    rows = [  # two external sources + one measured in-house (no cited source)
        {"parameter_id": params[0], "test_name": "Assay", "result_numeric": 22.0,
         "unit": "%", "source_document_code": "PPK26005", "source_institution": "UKIM Pharmacy"},
        {"parameter_id": params[1], "test_name": "Heavy Metals", "result_numeric": 1.0,
         "unit": "%", "source_document_code": "84/2026", "source_institution": "JZU IJZ"},
        {"parameter_id": params[2], "test_name": "Foreign Matter", "result_numeric": 0.1,
         "unit": "%"},
    ]
    for r in rows:
        assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                                  json=r, headers=admin_headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "UKIM Pharmacy" in md and "JZU IJZ" in md      # both external labs traced
    assert "PPK26005" in md and "84/2026" in md           # each source's CoA code
    assert "internal release control" in md               # the in-house 'Q' row


async def test_coq_crossref_sanitizes_source_separators(client, admin_headers, monkeypatch):
    """A free-text source_institution containing raw DSL separators (~~, |||)
    must be sanitized in the §02 table — never split into a fabricated bilingual
    pair or an injected column. Only the fixed internal-QC row is bilingual."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-SEP", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="COQ-SEP")
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Assay", "test_method": "Ph. Eur.",
                                "unit": "%", "lower_limit": 0.0, "upper_limit": 100.0},
                          headers=admin_headers)
    coa = await _coa(client, admin_headers, spec["id"], batch="B-SEP", report_date="2026-07-01")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": p.json()["id"], "test_name": "Assay",
                                    "result_numeric": 22.0, "unit": "%",
                                    "source_document_code": "AB|||CD",
                                    "source_institution": "Alfa~~Beta ||| Labs"},
                              headers=admin_headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=admin_headers)).status_code == 201
    # find the §02 rows in the assembled markdown; the external row must have the
    # canonical 6 columns (Src · Lab · Accreditation · Code · Issued · Params №)
    md = _FakeDE.last_markdown
    sec = md.split("02 Laboratory")[1]
    ext = [ln for ln in sec.splitlines() if ln.startswith("A ||| ")]
    assert ext and ext[0].count("|||") == 5, ext        # not shifted by injection
    assert "Alfa~~Beta" not in md and "Alfa-Beta" in md  # ~~ neutralised, not split


async def test_coq_water_cert_omits_cannabis_species_and_monograph(client, admin_headers, monkeypatch):
    """A non-cannabis-flower certificate (cert_type WATER/OTHER) must NOT assert
    the Cannabis flos species or Ph. Eur. 3028 conformance — that identity would
    be fabricated for a product that doesn't have it."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-W", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="COQ-WATER")
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Conductivity", "test_method": "Ph. Eur. 2.2.38",
                                "unit": "µS/cm", "upper_limit": 5.1}, headers=admin_headers)
    coa = await _coa(client, admin_headers, spec["id"], batch="B-WATER",
                     report_date="2026-07-01", cert_type="WATER")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": p.json()["id"], "test_name": "Conductivity",
                                    "result_numeric": 1.2, "upper_limit": 5.1, "unit": "µS/cm"},
                              headers=admin_headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=admin_headers)).status_code == 201
    md = _FakeDE.last_markdown
    assert "Cannabis Sativae" not in md and "3028" not in md   # no fabricated identity
    assert "Certificate of Quality" in md                      # still a valid CoQ


async def test_coq_only_from_released(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "X"})
    spec = await _spec(client, admin_headers, material="COQ-DRAFT")
    coa = await _coa(client, admin_headers, spec["id"])
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409          # DRAFT cert cannot be certified


async def test_coq_blocks_on_noncompliant_result(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "X"})
    _, qp = await _actor(client, admin_headers, "QP")
    # a failing result → the batch does not conform → COQ refused (never fabricated)
    coa = await _released_coa(client, admin_headers, qp, material="COQ-FAIL",
                              results=[{"test_name": "Water", "result_numeric": 15.0,
                                        "upper_limit": 10.0}])
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409 and "comply" in r.json()["detail"]


async def test_coq_is_qc_mgr_gated(client, admin_headers, monkeypatch):
    """Issuing the COQ is a QC act (compiled and approved within QC, QCSOP 012
    §6.4). The Qualified Person RECEIVES the approved COQ as an input to the
    separate Annex 16 release decision — the QP does not issue it, and neither
    does a non-QC manager or an executive."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-2", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="COQ-ROLE")
    _, cu_mgr = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=cu_mgr)).status_code == 403   # non-QC manager cannot
    _, ceo = await _actor(client, admin_headers, "CEO")
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=ceo)).status_code == 403      # executive is not a GMP quality role
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=qp)).status_code == 403       # QP receives, never issues
    _, qc_mgr = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=qc_mgr)).status_code == 201   # QC Manager issues the COQ


async def test_coq_blocked_by_open_oos(client, admin_headers, monkeypatch):
    """QCSOP 012 §6.4.1: no COQ for a batch with an open OOS investigation —
    only the investigation-confirmed result set may be certified."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-OOS", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="COQ-OOS")
    oos = await _oos(client, admin_headers, batch="B-COQ")   # same batch as _released_coa
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409 and "OOS" in r.json()["detail"]
    # QP closes the investigation → the COQ may now be issued
    assert (await client.patch(f"/qc/oos/{oos['id']}", json={"status": "CLOSED"},
                               headers=qp)).status_code == 200
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=admin_headers)).status_code == 201


async def test_coq_surfaces_verify_fail(client, admin_headers, monkeypatch):
    """A DocEngine pp_verify FAIL must reach the caller as 422 — never a
    silently-shipped certificate."""
    import httpx as _httpx
    _stub_de(monkeypatch, None)
    # make the fake DE raise a 4xx by returning a 422-shaped response
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="COQ-VF")

    class _Fail(_FakeDE):
        async def request(self, method, path, json=None, **kw):
            class _R:
                status_code = 422
                def json(self):
                    return {"detail": {"verify": "RESULT: FAIL", "error": "verify FAILED"}}
            return _R()
    monkeypatch.setattr(_qc_mod, "_coq_client", lambda timeout=20.0: _Fail(None))
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 422 and r.json()["detail"]["verify"] == "RESULT: FAIL"


async def test_coq_blocks_when_spec_not_fully_tested(client, admin_headers, monkeypatch):
    """Every spec parameter must be covered by a parameter-cited result before a
    COQ can be issued — passing results for HALF the spec is not a conforming
    batch, it is an incompletely-tested one."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-INC", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="COQ-INCOMPLETE")
    p1 = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                           json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                                 "test_method": "HPLC", "unit": "%", "lower_limit": 10.0,
                                 "upper_limit": 30.0}, headers=admin_headers)
    await client.post(f"/qc/specifications/{spec['id']}/parameters",
                      json={"test_name_en": "Moisture", "test_name_mk": "Влага",
                            "test_method": "LOD", "unit": "%", "upper_limit": 12.0},
                      headers=admin_headers)
    coa = await _coa(client, admin_headers, spec["id"], batch="B-COQ-INC")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": p1.json()["id"], "test_name": "Total THC",
                                    "result_numeric": 22.0, "lower_limit": 10.0,
                                    "upper_limit": 30.0, "unit": "%"},
                              headers=admin_headers)).status_code == 201
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409 and "not fully tested" in r.json()["detail"]


# ── URS increment 6 — CoQ mandatory-content manifest (WHO TRS 1010 / Annex 16 §9.3)
async def test_coq_manifest_blocks_missing_content(client, admin_headers, monkeypatch):
    """A RELEASED certificate whose results all comply and whose spec is fully
    tested still cannot be issued as a CoQ if it is missing mandatory certificate
    CONTENT — here the report date and the recorded PASS disposition. The gate
    names each absent element and fabricates none; supplying them lets the same
    certificate issue."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-MAN", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="COQ-MANIFEST")
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                                "test_method": "HPLC", "unit": "%",
                                "lower_limit": 10.0, "upper_limit": 30.0},
                          headers=admin_headers)
    assert p.status_code == 201
    # deliberately created with NO report_date and the disposition left unset
    coa = await _coa(client, admin_headers, spec["id"], batch="B-COQ-MAN")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": p.json()["id"], "test_name": "Total THC",
                                    "result_numeric": 22.0, "lower_limit": 10.0,
                                    "upper_limit": 30.0, "unit": "%",
                                    "source_document_code": "ECOA-LAB-9"},
                              headers=admin_headers)).status_code == 201
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert "mandatory content" in detail
    assert "report date" in detail and "PASS disposition" in detail
    # the CoQ is refused because content is absent, not because the batch failed —
    # recording the report date + disposition lifts the gate (nothing invented)
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"report_date": "2026-07-02", "decision": "PASS"},
                               headers=admin_headers)).status_code == 200
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=admin_headers)).status_code == 201


async def test_coq_manifest_requires_method(client, admin_headers, monkeypatch):
    """WHO TRS 1010: every reported test on the CoQ must cite an analytical
    method. A spec parameter carrying neither a test_method nor a pharmacopoeia
    reference blocks issuance and the gate names the offending test."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-NM", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="COQ-NOMETHOD")
    # parameter with no method and no pharmacopoeia reference
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Assay", "test_name_mk": "Анализа",
                                "unit": "%", "lower_limit": 90.0, "upper_limit": 110.0},
                          headers=admin_headers)
    assert p.status_code == 201
    coa = await _coa(client, admin_headers, spec["id"], batch="B-COQ-NM",
                     report_date="2026-07-01")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": p.json()["id"], "test_name": "Assay",
                                    "result_numeric": 99.0, "lower_limit": 90.0,
                                    "upper_limit": 110.0, "unit": "%",
                                    "source_document_code": "ECOA-LAB-10"},
                              headers=admin_headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409, r.text
    assert "analytical method" in r.json()["detail"] and "Assay" in r.json()["detail"]


# ── URS increment 2 — certificate supersession (QCSOP 012 §6.7) ─────────────
async def test_coa_revision_supersession_chain(client, admin_headers):
    """QCSOP 012 §6.7: an approved certificate is immutable — a correction is a
    NEW certificate (new number) carrying supersedes_id + revision_reason; when
    the revision is RELEASED the original flips to terminal SUPERSEDED (never
    deleted)."""
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="SUP-MAT")
    # direct SUPERSEDED is refused — only releasing a revision sets it
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "SUPERSEDED"},
                           headers=admin_headers)
    assert r.status_code == 409
    # a revision needs a real reason
    r = await client.post(f"/qc/certificates/{coa['id']}/revise", json={"reason": "typo"},
                          headers=admin_headers)
    assert r.status_code == 422
    r = await client.post(f"/qc/certificates/{coa['id']}/revise",
                          json={"reason": "Transcription error in THC result"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    rev = r.json()
    assert rev["status"] == "DRAFT" and rev["supersedes_id"] == coa["id"]
    assert rev["coa_number"].startswith("iCoA-PP-") and rev["coa_number"] != coa["coa_number"]
    assert rev["revision_reason"] == "Transcription error in THC result"
    # the result set is carried forward so the correction edits the real state
    detail = (await client.get(f"/qc/certificates/{rev['id']}", headers=admin_headers)).json()
    assert len(detail["results"]) == 1 and detail["results"][0]["test_name"] == "Total THC"
    # a second open revision of the same original is refused
    r = await client.post(f"/qc/certificates/{coa['id']}/revise",
                          json={"reason": "Second correction attempt"}, headers=admin_headers)
    assert r.status_code == 409 and "revision already exists" in r.json()["detail"]
    # release the revision → the original flips to SUPERSEDED
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{rev['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    orig = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()["coa"]
    assert orig["status"] == "SUPERSEDED"
    # SUPERSEDED is terminal — no further transitions
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "RELEASED"},
                           headers=admin_headers)
    assert r.status_code == 409
    # only a RELEASED certificate can be revised
    spec = await _spec(client, admin_headers, material="SUP-DRAFT")
    draft = await _coa(client, admin_headers, spec["id"], batch="B-SUP-D")
    r = await client.post(f"/qc/certificates/{draft['id']}/revise",
                          json={"reason": "Should not be possible"}, headers=admin_headers)
    assert r.status_code == 409


# ── URS increment 2 — computed total THC/CBD (Ph. Eur. 3028) ────────────────
async def _computed_spec(client, headers, material="PH3028", lo=10.0, hi=30.0):
    """A spec with two measured component parameters (Δ9-THC neutral + THCA
    acid) and one computed total_thc parameter derived from them."""
    spec = await _spec(client, headers, material=material)
    base = f"/qc/specifications/{spec['id']}/parameters"
    a = await client.post(base, json={"test_name_en": "Delta-9-THC", "test_method": "HPLC",
                                      "unit": "%"}, headers=headers)
    b = await client.post(base, json={"test_name_en": "THCA", "test_method": "HPLC",
                                      "unit": "%"}, headers=headers)
    assert a.status_code == 201 and b.status_code == 201
    t = await client.post(base, json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                                      "test_method": "Ph. Eur. 3028", "unit": "%",
                                      "lower_limit": lo, "upper_limit": hi,
                                      "computed_kind": "total_thc",
                                      "component_a_id": a.json()["id"],
                                      "component_b_id": b.json()["id"]}, headers=headers)
    assert t.status_code == 201, t.text
    assert t.json()["computed_kind"] == "total_thc"
    return spec, a.json(), b.json(), t.json()


async def _release_with_components(client, headers, qp, spec, pa, pb, batch,
                                   a_val=1.5, b_val=20.0):
    coa = await _coa(client, headers, spec["id"], batch=batch, report_date="2026-07-01")
    for pid, name, val in ((pa["id"], "Delta-9-THC", a_val), (pb["id"], "THCA", b_val)):
        assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                                  json={"parameter_id": pid, "test_name": name,
                                        "result_numeric": val, "unit": "%"},
                                  headers=headers)).status_code == 201
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": "PASS"}, headers=headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    return coa


async def test_coq_computes_total_thc(client, admin_headers, monkeypatch):
    """Ph. Eur. 3028: total THC = Δ9-THC + 0.877 × THCA, DERIVED by the engine
    from the component results at COQ time — never transcribed. The computed
    row covers its spec parameter and cites the monograph as its source."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-3028", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PH3028")
    coa = await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-3028")
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 201, r.text
    md = _FakeDE.last_markdown
    # 1.5 + 0.877 × 20.0 = 19.04 — in spec (10–30), cited to the monograph
    assert "19.04" in md and "Ph. Eur. 3028" in md and "Total THC" in md


async def test_coq_computed_total_fail_blocks(client, admin_headers, monkeypatch):
    """A computed total outside its limits is a non-conforming batch — the COQ
    is refused by the comply gate, exactly like a measured OOS result."""
    _stub_de(monkeypatch, {"document_id": "X"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PH3028-F", hi=15.0)
    coa = await _release_with_components(client, admin_headers, qp, spec, pa, pb, "B-3028-F")
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409 and "comply" in r.json()["detail"]


async def test_coq_computed_missing_component_blocks(client, admin_headers, monkeypatch):
    """A computed total with an unmeasured component is NOT covered — the
    completeness gate refuses the COQ (the batch is not fully tested); the
    engine never derives a value from a partial component set."""
    _stub_de(monkeypatch, {"document_id": "X"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb, pt = await _computed_spec(client, admin_headers, material="PH3028-M")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-3028-M")
    assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                              json={"parameter_id": pa["id"], "test_name": "Delta-9-THC",
                                    "result_numeric": 1.5, "unit": "%"},
                              headers=admin_headers)).status_code == 201
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 409 and "not fully tested" in r.json()["detail"]


async def test_computed_param_validation(client, admin_headers):
    spec = await _spec(client, admin_headers, material="COMP-VAL")
    base = f"/qc/specifications/{spec['id']}/parameters"
    a = (await client.post(base, json={"test_name_en": "Delta-9-THC"}, headers=admin_headers)).json()
    b = (await client.post(base, json={"test_name_en": "THCA"}, headers=admin_headers)).json()
    # unknown kind
    r = await client.post(base, json={"test_name_en": "T", "computed_kind": "total_cbg",
                                      "component_a_id": a["id"], "component_b_id": b["id"]},
                          headers=admin_headers)
    assert r.status_code == 422
    # computed without components
    r = await client.post(base, json={"test_name_en": "T", "computed_kind": "total_thc"},
                          headers=admin_headers)
    assert r.status_code == 422
    # the same component twice
    r = await client.post(base, json={"test_name_en": "T", "computed_kind": "total_thc",
                                      "component_a_id": a["id"], "component_b_id": a["id"]},
                          headers=admin_headers)
    assert r.status_code == 422
    # a component from a DIFFERENT spec
    other = await _spec(client, admin_headers, material="COMP-VAL-2")
    oa = (await client.post(f"/qc/specifications/{other['id']}/parameters",
                            json={"test_name_en": "Foreign"}, headers=admin_headers)).json()
    r = await client.post(base, json={"test_name_en": "T", "computed_kind": "total_thc",
                                      "component_a_id": oa["id"], "component_b_id": b["id"]},
                          headers=admin_headers)
    assert r.status_code == 422
    # component ids without computed_kind
    r = await client.post(base, json={"test_name_en": "T", "component_a_id": a["id"],
                                      "component_b_id": b["id"]}, headers=admin_headers)
    assert r.status_code == 422
    # a computed parameter cannot itself be a component
    t = await client.post(base, json={"test_name_en": "Total THC", "computed_kind": "total_thc",
                                      "component_a_id": a["id"], "component_b_id": b["id"]},
                          headers=admin_headers)
    assert t.status_code == 201, t.text
    r = await client.post(base, json={"test_name_en": "T2", "computed_kind": "total_cbd",
                                      "component_a_id": t.json()["id"], "component_b_id": b["id"]},
                          headers=admin_headers)
    assert r.status_code == 422
    # transcribing a result AGAINST the computed parameter is forbidden
    coa = await _coa(client, admin_headers, spec["id"], batch="B-COMP-VAL")
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"parameter_id": t.json()["id"], "test_name": "Total THC",
                                "result_numeric": 20.0}, headers=admin_headers)
    assert r.status_code == 422 and "computed" in r.json()["detail"]


# ── URS increment 3 — accredited laboratory entity (Chapter 7) ──────────────
async def _lab(client, headers, name="Contract Lab GmbH", **extra):
    body = {"name": name, **extra}
    r = await client.post("/qc/laboratories", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_laboratory_crud(client, admin_headers):
    lab = await _lab(client, admin_headers, name="Eurofins MK",
                     accreditation_body="IARM", accreditation_number="LT-045",
                     iso17025_scope=["HPLC", "GC-MS"], decimal_separator=",",
                     locale="mk-MK", quality_agreement_ref="QA-2026-07")
    assert lab["lab_code"].startswith("PP-LAB-") and lab["status"] == "ACTIVE"
    assert lab["iso17025_scope"] == ["HPLC", "GC-MS"] and lab["decimal_separator"] == ","
    assert lab["accreditation_body"] == "IARM"
    # list + get
    r = await client.get("/qc/laboratories", headers=admin_headers)
    assert r.status_code == 200 and any(x["id"] == lab["id"] for x in r.json())
    r = await client.get(f"/qc/laboratories/{lab['id']}", headers=admin_headers)
    assert r.status_code == 200 and r.json()["name"] == "Eurofins MK"
    # patch: deactivate + amend scope
    r = await client.patch(f"/qc/laboratories/{lab['id']}",
                           json={"status": "INACTIVE", "iso17025_scope": ["HPLC"]},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "INACTIVE"
    assert r.json()["iso17025_scope"] == ["HPLC"]
    # bad decimal separator + bad status → 422
    assert (await client.post("/qc/laboratories", json={"name": "X", "decimal_separator": ";"},
                              headers=admin_headers)).status_code == 422
    assert (await client.patch(f"/qc/laboratories/{lab['id']}", json={"status": "ARCHIVED"},
                               headers=admin_headers)).status_code == 422


async def test_laboratory_role_gating(client, admin_headers):
    lab = await _lab(client, admin_headers, name="Role Lab")
    _, user_h = await _actor(client, admin_headers, "USER")
    assert (await client.get("/qc/laboratories", headers=user_h)).status_code == 403
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/qc/laboratories", headers=cu_h)).status_code == 200   # elevated read
    assert (await client.post("/qc/laboratories", json={"name": "Nope"},
                              headers=cu_h)).status_code == 403
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post("/qc/laboratories", json={"name": "QC Lab"},
                              headers=qc_h)).status_code == 201


async def test_certificate_links_laboratory(client, admin_headers):
    lab = await _lab(client, admin_headers, name="Linked Lab")
    spec = await _spec(client, admin_headers, material="LAB-LINK")
    coa = await _coa(client, admin_headers, spec["id"], laboratory_id=lab["id"])
    assert coa["laboratory_id"] == lab["id"]
    # detail resolves the laboratory object
    detail = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()
    assert detail["laboratory"]["id"] == lab["id"] and detail["laboratory"]["name"] == "Linked Lab"
    # unknown laboratory → 422
    import uuid as _uuid
    r = await client.post("/qc/certificates",
                          json={"batch_id": "B-BAD-LAB", "specification_id": spec["id"],
                                "laboratory_id": str(_uuid.uuid4())}, headers=admin_headers)
    assert r.status_code == 422 and "laboratory" in r.json()["detail"].lower()


async def test_coq_flags_out_of_scope(client, admin_headers, monkeypatch):
    """URS Chapter 7: a result run on a method outside the lab's ISO 17025 scope
    is flagged on the COQ — advisory, never a block. In-scope results carry no
    flag."""
    _stub_de(monkeypatch, {"document_id": "DE-COQ-SCOPE", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    # lab accredited for HPLC only
    lab = await _lab(client, admin_headers, name="Scope Lab", iso17025_scope=["HPLC"])
    spec = await _spec(client, admin_headers, material="SCOPE-MAT")
    p_in = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                             json={"test_name_en": "Total THC", "test_method": "HPLC",
                                   "unit": "%", "lower_limit": 10.0, "upper_limit": 30.0},
                             headers=admin_headers)
    p_out = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                              json={"test_name_en": "Moisture", "test_method": "LOD",
                                    "unit": "%", "upper_limit": 12.0}, headers=admin_headers)
    coa = await _coa(client, admin_headers, spec["id"], batch="B-SCOPE",
                     laboratory_id=lab["id"], report_date="2026-07-01")
    for p, name, val in ((p_in, "Total THC", 22.0), (p_out, "Moisture", 8.0)):
        assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                                  json={"parameter_id": p.json()["id"], "test_name": name,
                                        "result_numeric": val}, headers=admin_headers)
                ).status_code == 201
    # detail flags the LOD result out of scope, the HPLC one in scope
    detail = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()
    by_name = {r["test_name"]: r for r in detail["results"]}
    assert by_name["Total THC"]["in_scope"] is True
    assert by_name["Moisture"]["in_scope"] is False
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200, tgt
    r = await client.post(f"/qc/certificates/{coa['id']}/coq", headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["out_of_scope"] == ["Moisture"]
    md = _FakeDE.last_markdown
    assert "ISO 17025" in md and "Moisture" in md
    # the structured lab (name + accreditation) shows in the grid, not source_lab
    assert "Scope Lab" in md


async def test_ecoa_doc_promote_carries_laboratory(client, admin_headers):
    lab = await _lab(client, admin_headers, name="Promote Lab")
    spec, param = await _ecoa_spec_with_param(client, admin_headers, material="LAB-PROMO")
    r = await client.post("/qc/coa-documents",
                          json={"batch_id": "B-LAB-PROMO", "specification_id": spec["id"],
                                "laboratory_id": lab["id"], "source_institution": "Promote Lab"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["laboratory_id"] == lab["id"]
    doc = r.json()
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [{"raw_label": "Total THC", "numeric_value": 20.0}]},
                      headers=admin_headers)
    prom = await client.post(f"/qc/coa-documents/{doc['id']}/promote", headers=admin_headers)
    assert prom.status_code == 201, prom.text
    cert = (await client.get(f"/qc/certificates/{prom.json()['coa_id']}",
                             headers=admin_headers)).json()
    assert cert["coa"]["laboratory_id"] == lab["id"]


# ── URS increment 4 — certificate register (QCLB 020 §6.13) ─────────────────
async def test_certificate_register_filters(client, admin_headers):
    lab = await _lab(client, admin_headers, name="Register Lab")
    spec = await _spec(client, admin_headers, material="REG-MAT")
    icoa = await _coa(client, admin_headers, spec["id"], batch="B-REG-A",
                      cert_type="ICOA", laboratory_id=lab["id"])
    ecoa = await _coa(client, admin_headers, spec["id"], batch="B-REG-B", cert_type="ECOA")
    year = int(icoa["coa_number"].split("-")[2])
    # set retention (expired) + archive ref on the ICOA
    r = await client.patch(f"/qc/certificates/{icoa['id']}",
                           json={"retention_start": "2020-01-01", "retention_expiry": "2021-01-01",
                                 "archive_ref": "BINDER-7"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["archive_ref"] == "BINDER-7"

    reg = (await client.get("/qc/register", headers=admin_headers)).json()
    codes = {x["coa_number"] for x in reg}
    assert icoa["coa_number"] in codes and ecoa["coa_number"] in codes
    row = next(x for x in reg if x["coa_number"] == icoa["coa_number"])
    assert row["laboratory"] == "Register Lab" and row["archive_ref"] == "BINDER-7"

    # cert_type filter
    only_icoa = (await client.get("/qc/register?cert_type=ICOA", headers=admin_headers)).json()
    assert all(x["cert_type"] == "ICOA" for x in only_icoa)
    assert icoa["coa_number"] in {x["coa_number"] for x in only_icoa}
    assert ecoa["coa_number"] not in {x["coa_number"] for x in only_icoa}

    # pending (both are DRAFT → in-progress)
    pend = (await client.get("/qc/register?pending=true", headers=admin_headers)).json()
    assert {icoa["coa_number"], ecoa["coa_number"]} <= {x["coa_number"] for x in pend}

    # retention=expired returns the ICOA (expiry in the past)
    exp = (await client.get("/qc/register?retention=expired", headers=admin_headers)).json()
    assert icoa["coa_number"] in {x["coa_number"] for x in exp}
    assert ecoa["coa_number"] not in {x["coa_number"] for x in exp}

    # year filter (the register year is the YYYY in the number)
    yr = (await client.get(f"/qc/register?year={year}", headers=admin_headers)).json()
    assert icoa["coa_number"] in {x["coa_number"] for x in yr}
    # prior year: our certs are absent from that register slice
    prev = (await client.get(f"/qc/register?year={year - 1}", headers=admin_headers)).json()
    assert icoa["coa_number"] not in {x["coa_number"] for x in prev}

    # bad enum → 422
    assert (await client.get("/qc/register?cert_type=NOPE", headers=admin_headers)).status_code == 422
    assert (await client.get("/qc/register?retention=maybe", headers=admin_headers)).status_code == 422
    assert (await client.get("/qc/register?quarter=5", headers=admin_headers)).status_code == 422


async def test_register_oos_linked(client, admin_headers):
    spec = await _spec(client, admin_headers, material="REG-OOS")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-REG-OOS")
    await _oos(client, admin_headers, batch="B-REG-OOS")   # open OOS on the same batch
    reg = (await client.get("/qc/register?oos_linked=true", headers=admin_headers)).json()
    row = next((x for x in reg if x["coa_number"] == coa["coa_number"]), None)
    assert row is not None and row["open_oos"] >= 1
    # a cert whose batch has no OOS is excluded from the oos_linked view
    clean = await _coa(client, admin_headers, spec["id"], batch="B-REG-CLEAN")
    assert clean["coa_number"] not in {x["coa_number"] for x in reg}


async def test_register_numbering_gaps(client, admin_headers):
    """The gap report lists absent numbers within a year's issued range. Our own
    issued numbers are never reported as gaps; the shared-sequence caveat is
    surfaced in the note (a gap may be another tenant's allocation)."""
    spec = await _spec(client, admin_headers, material="REG-GAP")
    made = [await _coa(client, admin_headers, spec["id"], batch=f"B-GAP-{i}") for i in range(3)]
    year = int(made[0]["coa_number"].split("-")[2])
    g = (await client.get(f"/qc/register/gaps?year={year}", headers=admin_headers)).json()
    assert g["year"] == year and g["issued"] >= 3
    assert g["min"] is not None and g["max"] >= g["min"]
    mine = {m["coa_number"] for m in made}
    assert not (mine & set(g["gaps"]))          # none of our own numbers are "gaps"
    assert "shared across tenants" in g["note"]


async def test_certificate_numbering_per_type_series(client, admin_headers):
    """QCSOP 012 §6.13 (C2) — new certificates mint under a per-cert-type prefix
    (iCoA-PP / CoQ-PP / …), each type keeping its own independent per-year
    counter, and the numbering-gap report never mixes two unrelated series."""
    spec = await _spec(client, admin_headers, material="NUM-MAT")
    icoa1 = await _coa(client, admin_headers, spec["id"], batch="B-NUM-I1")
    assert icoa1["coa_number"].startswith("iCoA-PP-")
    icoa2 = await _coa(client, admin_headers, spec["id"], batch="B-NUM-I2")
    seq1 = int(icoa1["coa_number"].rsplit("-", 1)[-1])
    seq2 = int(icoa2["coa_number"].rsplit("-", 1)[-1])
    assert seq2 == seq1 + 1                      # the ICOA series advances by exactly one
    r = await client.post("/qc/certificates",
                          json={"batch_id": "B-NUM-Q", "specification_id": spec["id"], "cert_type": "COQ"},
                          headers=admin_headers)
    coq = r.json()
    assert coq["coa_number"].startswith("CoQ-PP-")   # a distinct series, distinct prefix
    # scoping the gap report to a type keeps its series clean of the other type's numbers
    year = int(icoa1["coa_number"].split("-")[2])
    g = (await client.get(f"/qc/register/gaps?year={year}&cert_type=ICOA", headers=admin_headers)).json()
    assert g["min"] is not None and all(x.startswith("iCoA-PP-") for x in g["gaps"])
    assert {icoa1["coa_number"], icoa2["coa_number"]} & set(g["gaps"]) == set()
    assert coq["coa_number"] not in set(g["gaps"])
    r = await client.get(f"/qc/register/gaps?year={year}&cert_type=NOPE", headers=admin_headers)
    assert r.status_code == 422


# ── URS increment 5 — 5-working-day eCoA review clock (§6.3.1) ──────────────
async def test_ecoa_review_clock_met(client, admin_headers):
    """Registration stamps a 5-working-day review deadline; a review inside the
    window records review_window_met = True (and is not overdue)."""
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="CLOCK-MET")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-CLOCK-MET")
    assert doc["review_deadline"] is not None and doc["review_window_met"] is None
    assert doc["review_overdue"] is False
    # 5 working days is at least 7 calendar days ahead of today
    import datetime as _dt
    assert _dt.date.fromisoformat(doc["review_deadline"]) >= _dt.date.today() + _dt.timedelta(days=7)
    # walk to REVIEWED (on time) → window met, reviewed_at stamped
    assert (await client.patch(f"/qc/coa-documents/{doc['id']}", json={"status": "EXTRACTED"},
                               headers=admin_headers)).status_code == 200
    r = await client.patch(f"/qc/coa-documents/{doc['id']}", json={"status": "REVIEWED"},
                           headers=admin_headers)
    assert r.status_code == 200
    got = (await client.get(f"/qc/coa-documents/{doc['id']}", headers=admin_headers)).json()["document"]
    assert got["review_window_met"] is True and got["reviewed_at"] is not None
    assert got["review_overdue"] is False


async def test_ecoa_review_clock_missed_and_overdue(client, admin_headers):
    """A document whose deadline has passed reads as overdue while awaiting
    review; reviewing it after the deadline records review_window_met = False."""
    from app.db import tasks_admin_pool
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="CLOCK-MISS")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-CLOCK-MISS")
    # backdate the deadline to yesterday (as if 5 working days have elapsed)
    await tasks_admin_pool().execute(
        "UPDATE qc_coa_documents SET review_deadline = CURRENT_DATE - 1 WHERE id=$1", doc["id"])
    got = (await client.get(f"/qc/coa-documents/{doc['id']}", headers=admin_headers)).json()["document"]
    assert got["review_overdue"] is True and got["review_window_met"] is None
    # reviewing now (after the deadline) records the missed window, not overdue
    await client.patch(f"/qc/coa-documents/{doc['id']}", json={"status": "EXTRACTED"}, headers=admin_headers)
    await client.patch(f"/qc/coa-documents/{doc['id']}", json={"status": "REVIEWED"}, headers=admin_headers)
    got = (await client.get(f"/qc/coa-documents/{doc['id']}", headers=admin_headers)).json()["document"]
    assert got["review_window_met"] is False and got["review_overdue"] is False


# ── Phase 3 U2 — eCOA ingestion ─────────────────────────────────────────────
async def _ecoa_spec_with_param(client, headers, material="ECOA-MAT"):
    spec = await _spec(client, headers, material=material)
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                                "test_method": "HPLC", "unit": "%", "lower_limit": 10.0,
                                "upper_limit": 30.0}, headers=headers)
    assert p.status_code == 201, p.text
    return spec, p.json()


async def _ecoa_doc(client, headers, spec_id=None, batch="B-ECOA-1", **extra):
    body = {"batch_id": batch, "source_institution": "Contract Lab GmbH", **extra}
    if spec_id:
        body["specification_id"] = spec_id
    r = await client.post("/qc/coa-documents", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_ecoa_register_grades_and_discovers(client, admin_headers):
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="ECOA-GRADE")
    doc = await _ecoa_doc(client, admin_headers, spec["id"])
    assert doc["doc_number"].startswith("PP-ECOA-") and doc["status"] == "UPLOADED"
    # one matching field (graded) + one unknown label (queued for a human)
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [
                              {"raw_label": "Total THC", "numeric_value": 22.0, "unit": "%"},
                              {"raw_label": "Mystery Assay", "raw_value": "42", "numeric_value": 42.0},
                          ]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["count"] == 2 and body["unmapped"] == 1
    ex = {e["raw_label"]: e for e in body["extractions"]}
    assert ex["Total THC"]["grade_status"] == "graded" and ex["Total THC"]["complies"] is True
    assert ex["Mystery Assay"]["grade_status"] == "unmapped" and ex["Mystery Assay"]["complies"] is None
    # the document advanced to EXTRACTED
    d = (await client.get(f"/qc/coa-documents/{doc['id']}", headers=admin_headers)).json()
    assert d["document"]["status"] == "EXTRACTED"
    # the unknown label is now in the discovery queue
    ph = (await client.get("/qc/coa-placeholders", headers=admin_headers)).json()
    assert any(p["raw_label"] == "Mystery Assay" and p["status"] == "OPEN" for p in ph)


async def test_ecoa_lab_verdict_reference_only(client, admin_headers):
    """QCSOP 012 §6.3.2: the lab's stated verdict is captured verbatim as
    reference, never as the conformance of record — and a disagreement with
    the in-house determination is surfaced as a mismatch flag."""
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="ECOA-LABV")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-LABV")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [
                              # out of the 10-30 range → OUR verdict False; lab claims Pass
                              {"raw_label": "Total THC", "numeric_value": 99.0,
                               "unit": "%", "lab_verdict": "Pass"},
                          ]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    e = r.json()["extractions"][0]
    assert e["complies"] is False                 # in-house determination wins
    assert e["lab_verdict"] == "Pass"             # lab's claim kept verbatim
    assert e["lab_verdict_mismatch"] is True      # disagreement surfaced
    # reviewer corrects the value into range → verdicts now agree, flag clears
    r = await client.patch(f"/qc/coa-documents/{doc['id']}/extractions/{e['id']}",
                           json={"numeric_value": 22.0}, headers=admin_headers)
    assert r.status_code == 200
    e2 = r.json()
    assert e2["complies"] is True and e2["lab_verdict_mismatch"] is False
    # an extraction with no stated lab verdict never computes a mismatch
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "Total THC", "numeric_value": 99.0}]},
                          headers=admin_headers)
    e3 = r.json()["extractions"][0]
    assert e3["lab_verdict"] is None and e3["lab_verdict_mismatch"] is False


async def test_ecoa_unmeasured_is_unknown_not_fabricated(client, admin_headers):
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="ECOA-UNK")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-UNK")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "Total THC", "raw_value": "not reported"}]},
                          headers=admin_headers)
    e = r.json()["extractions"][0]
    # mapped to the parameter, but no numeric value → unknown, never a verdict
    assert e["grade_status"] == "unknown" and e["complies"] is None


async def test_ecoa_placeholder_map_enables_auto_map(client, admin_headers):
    spec, param = await _ecoa_spec_with_param(client, admin_headers, material="ECOA-MAP")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-MAP-1")
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [{"raw_label": "THC (total)", "numeric_value": 20.0}]},
                      headers=admin_headers)
    ph = [p for p in (await client.get("/qc/coa-placeholders", headers=admin_headers)).json()
          if p["raw_label"] == "THC (total)"][0]
    # a human maps the discovered label to the Total-THC parameter
    m = await client.patch(f"/qc/coa-placeholders/{ph['id']}",
                           json={"status": "MAPPED", "mapped_parameter_id": param["id"]},
                           headers=admin_headers)
    assert m.status_code == 200 and m.json()["status"] == "MAPPED"
    # a NEW document with the same label now auto-maps + grades
    doc2 = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-MAP-2")
    r = await client.post(f"/qc/coa-documents/{doc2['id']}/extractions",
                          json={"items": [{"raw_label": "THC (total)", "numeric_value": 25.0}]},
                          headers=admin_headers)
    e = r.json()["extractions"][0]
    assert e["grade_status"] == "graded" and e["complies"] is True and e["parameter_id"] == param["id"]


async def test_ecoa_promote_creates_certificate_with_provenance(client, admin_headers):
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="ECOA-PROMO")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-PROMO")
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [
                          {"raw_label": "Total THC", "numeric_value": 22.0, "unit": "%"},
                          {"raw_label": "Unknown Field", "numeric_value": 1.0},
                      ]}, headers=admin_headers)
    r = await client.post(f"/qc/coa-documents/{doc['id']}/promote", headers=admin_headers)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["results_created"] == 1 and out["skipped_unmapped"] == 1
    # the minted certificate is a DRAFT ECOA carrying the source doc on its result
    coa = (await client.get(f"/qc/certificates/{out['coa_id']}", headers=admin_headers)).json()
    assert coa["coa"]["status"] == "DRAFT" and coa["coa"]["cert_type"] == "ECOA"
    assert coa["results"][0]["source_document_code"] == doc["doc_number"]
    assert coa["results"][0]["complies"] is True
    # the document is now PROMOTED and points at the certificate
    d = (await client.get(f"/qc/coa-documents/{doc['id']}", headers=admin_headers)).json()
    assert d["document"]["status"] == "PROMOTED" and d["document"]["promoted_coa_id"] == out["coa_id"]


# ── URS increment 7 — lab-verdict onto the permanent record (completes item 8)
async def test_promote_carries_lab_verdict_onto_result(client, admin_headers):
    """The lab's stated verdict captured at eCoA extraction (mig 0028) must
    survive onto the promoted qc_result, so the lab-vs-in-house reconciliation
    lives on the permanent certificate — not just in the intake queue. Here the
    lab claims Pass on an out-of-spec value: the certificate keeps our FAIL
    determination AND records the disagreement."""
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="ECOA-LABV-PROMO")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-LABV-PROMO")
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [
                          # out of the 10-30 range → our verdict FAIL; lab printed "Pass"
                          {"raw_label": "Total THC", "numeric_value": 99.0,
                           "unit": "%", "lab_verdict": "Pass"},
                      ]}, headers=admin_headers)
    out = (await client.post(f"/qc/coa-documents/{doc['id']}/promote",
                             headers=admin_headers)).json()
    res = (await client.get(f"/qc/certificates/{out['coa_id']}",
                            headers=admin_headers)).json()["results"][0]
    assert res["lab_verdict"] == "Pass"           # carried onto the permanent record
    assert res["complies"] is False               # our determination, unchanged
    assert res["lab_verdict_mismatch"] is True     # the disagreement is on the record


async def test_result_lab_verdict_manual_reference_only(client, admin_headers):
    """A manually-entered (iCoA) result can carry the lab's stated verdict; it is
    surfaced with a reconciliation flag and NEVER alters the in-house `complies`
    (QCSOP 012 §6.3.2 — conformance is determined by Purely Plant)."""
    spec, p = await _ecoa_spec_with_param(client, admin_headers, material="RES-LABV")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-RES-LABV")
    # lab claims Fail but the value is in the 10-30 range → we determine PASS
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"parameter_id": p["id"], "test_name": "Total THC",
                                "result_numeric": 22.0, "lab_verdict": "Fail"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["complies"] is True and body["status"] == "pass"   # value-driven, not lab-driven
    assert body["lab_verdict"] == "Fail" and body["lab_verdict_mismatch"] is True
    # a result with no stated lab verdict never computes a mismatch
    r2 = await client.post(f"/qc/certificates/{coa['id']}/results",
                           json={"parameter_id": p["id"], "test_name": "Total THC",
                                 "result_numeric": 25.0}, headers=admin_headers)
    assert r2.json()["lab_verdict"] is None and r2.json()["lab_verdict_mismatch"] is False


# ── URS increment 8 — Annex 11 electronic signatures (URS §14 / item 11) ────
async def test_certificate_esignature_records_and_lists(client, admin_headers):
    """A re-authenticated signature is recorded against the certificate carrying
    the signer's name, the meaning, and the time; it is listed on the cert and in
    the detail. The admin's account password is TestPassword123456 (conftest)."""
    spec = await _spec(client, admin_headers, material="SIG-MAT")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-SIG")
    r = await client.post(f"/qc/certificates/{coa['id']}/sign",
                          json={"password": "TestPassword123456", "meaning": "APPROVED",
                                "statement": "Reviewed and approved."}, headers=admin_headers)
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["meaning"] == "APPROVED" and s["signer_name"] == "Test Admin" and s["signed_at"]
    assert s["object_type"] == "qc_certificate" and s["object_id"] == coa["id"]
    # a second meaning appends a second signature (append-only attestation log)
    assert (await client.post(f"/qc/certificates/{coa['id']}/sign",
                              json={"password": "TestPassword123456", "meaning": "RELEASED"},
                              headers=admin_headers)).status_code == 201
    lst = (await client.get(f"/qc/certificates/{coa['id']}/signatures", headers=admin_headers)).json()
    assert [x["meaning"] for x in lst] == ["APPROVED", "RELEASED"]
    detail = (await client.get(f"/qc/certificates/{coa['id']}", headers=admin_headers)).json()
    assert len(detail["signatures"]) == 2


async def test_certificate_esignature_reauth_required(client, admin_headers):
    """Annex 11 §14 — the signature is only applied if the signer re-authenticates;
    a wrong password records nothing."""
    spec = await _spec(client, admin_headers, material="SIG-REAUTH")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-SIG-RA")
    r = await client.post(f"/qc/certificates/{coa['id']}/sign",
                          json={"password": "wrong-password", "meaning": "APPROVED"},
                          headers=admin_headers)
    assert r.status_code == 401
    lst = (await client.get(f"/qc/certificates/{coa['id']}/signatures", headers=admin_headers)).json()
    assert lst == []                              # nothing recorded on a failed re-auth


async def test_certificate_esignature_validates_meaning_and_gates(client, admin_headers):
    spec = await _spec(client, admin_headers, material="SIG-VAL")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-SIG-VAL")
    # an unknown meaning is rejected
    assert (await client.post(f"/qc/certificates/{coa['id']}/sign",
                              json={"password": "TestPassword123456", "meaning": "WHATEVER"},
                              headers=admin_headers)).status_code == 422
    # signing is a QC-writer act — a base USER cannot sign (nor read the domain)
    _, user = await _actor(client, admin_headers, "USER")
    assert (await client.post(f"/qc/certificates/{coa['id']}/sign",
                              json={"password": "NewPassword123456", "meaning": "APPROVED"},
                              headers=user)).status_code == 403
    # a bogus certificate id is a 404, not a 500
    assert (await client.post("/qc/certificates/not-a-uuid/sign",
                              json={"password": "TestPassword123456", "meaning": "APPROVED"},
                              headers=admin_headers)).status_code == 404


async def test_ecoa_promote_needs_spec_and_mapped_results(client, admin_headers):
    # no spec → cannot certify
    doc = await _ecoa_doc(client, admin_headers, batch="B-NOSPEC")
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [{"raw_label": "Whatever", "numeric_value": 1.0}]},
                      headers=admin_headers)
    r = await client.post(f"/qc/coa-documents/{doc['id']}/promote", headers=admin_headers)
    assert r.status_code == 409
    # spec but only unmapped fields → nothing to promote
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="ECOA-NOMAP")
    doc2 = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-NOMAP")
    await client.post(f"/qc/coa-documents/{doc2['id']}/extractions",
                      json={"items": [{"raw_label": "Alien Test", "numeric_value": 1.0}]},
                      headers=admin_headers)
    r = await client.post(f"/qc/coa-documents/{doc2['id']}/promote", headers=admin_headers)
    assert r.status_code == 409


async def test_ecoa_promote_via_patch_is_refused(client, admin_headers):
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="ECOA-PATCH")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-PATCH")
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [{"raw_label": "Total THC", "numeric_value": 22.0}]},
                      headers=admin_headers)
    # PROMOTED must go through the promote endpoint (it mints a certificate)
    r = await client.patch(f"/qc/coa-documents/{doc['id']}", json={"status": "PROMOTED"},
                           headers=admin_headers)
    assert r.status_code == 409
    # a legal transition is fine
    r = await client.patch(f"/qc/coa-documents/{doc['id']}", json={"status": "REVIEWED"},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "REVIEWED"


# ── URS increment 9 — source-document custody + SHA-256 (item 12) ────────────
async def test_coa_original_upload_download_and_integrity(client, admin_headers):
    """The original source PDF is stored with a server-computed SHA-256, listed
    on the eCoA, and downloadable with an integrity verdict re-hashed on read."""
    import base64 as _b64, hashlib as _hl
    doc = await _ecoa_doc(client, admin_headers, batch="B-ORIG")
    blob = b"%PDF-1.4 fake certificate bytes \x00\x01\x02 end"
    digest = _hl.sha256(blob).hexdigest()
    r = await client.post(f"/qc/coa-documents/{doc['id']}/originals",
                          json={"filename": "supplier_coa.pdf", "content_type": "application/pdf",
                                "content_b64": _b64.b64encode(blob).decode()}, headers=admin_headers)
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["sha256"] == digest and f["size_bytes"] == len(blob) and f["filename"] == "supplier_coa.pdf"
    # listed on the doc + folded into the detail
    lst = (await client.get(f"/qc/coa-documents/{doc['id']}/originals", headers=admin_headers)).json()
    assert len(lst) == 1 and lst[0]["sha256"] == digest
    detail = (await client.get(f"/qc/coa-documents/{doc['id']}", headers=admin_headers)).json()
    assert len(detail["originals"]) == 1
    # download returns the exact bytes + an integrity-OK header
    dl = await client.get(f"/qc/document-files/{f['id']}/download", headers=admin_headers)
    assert dl.status_code == 200 and dl.content == blob
    assert dl.headers["x-integrity"] == "OK" and dl.headers["x-content-sha256"] == digest


async def test_coa_original_rejects_bad_input_and_is_gated(client, admin_headers):
    doc = await _ecoa_doc(client, admin_headers, batch="B-ORIG-BAD")
    # not valid base64 → 422
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/originals",
                              json={"filename": "x.pdf", "content_b64": "!!!not base64!!!"},
                              headers=admin_headers)).status_code == 422
    # write-gated — a base USER cannot upload
    _, user = await _actor(client, admin_headers, "USER")
    import base64 as _b64
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/originals",
                              json={"filename": "x.pdf", "content_b64": _b64.b64encode(b"hi").decode()},
                              headers=user)).status_code == 403
    # a bogus file id download is a 404, not a 500
    assert (await client.get("/qc/document-files/not-a-uuid/download",
                             headers=admin_headers)).status_code == 404


# ── URS increment 10 — batch genealogy (item 5, D2 = blending / m:n) ─────────
async def _edge(client, headers, parent, child, relation="GENERIC"):
    r = await client.post("/qc/genealogy",
                          json={"parent_batch_id": parent, "child_batch_id": child, "relation": relation},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_genealogy_chain_and_inherited_results(client, admin_headers, monkeypatch):
    """variety → cultivation → processing → packaging: ancestors/descendants
    resolve recursively, and a finished-pack batch can see the RELEASED-cert
    results of its ancestor lots (QCSOP 012 D3 inheritance)."""
    V, AB, P, PACK = "VAR-KUSH", "AB-2026-01", "P-2026-09", "PACK-2026-77"
    await _edge(client, admin_headers, V, AB, "CULTIVATION")
    await _edge(client, admin_headers, AB, P, "PROCESSING")
    await _edge(client, admin_headers, P, PACK, "PACKAGING")
    g = (await client.get(f"/qc/genealogy/{PACK}", headers=admin_headers)).json()
    assert [e["parent_batch_id"] for e in g["parents"]] == [P]
    anc = {a["batch_id"]: a["depth"] for a in g["ancestors"]}
    assert anc == {P: 1, AB: 2, V: 3}
    gv = (await client.get(f"/qc/genealogy/{V}", headers=admin_headers)).json()
    assert {d["batch_id"] for d in gv["descendants"]} == {AB, P, PACK}
    # a RELEASED certificate on the AB ancestor → inheritable by PACK
    _stub_de(monkeypatch, {"document_id": "X"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec = await _spec(client, admin_headers, material="GEN-MAT")
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Total THC", "test_name_mk": "ТХЦ",
                                "test_method": "HPLC", "unit": "%", "lower_limit": 10.0,
                                "upper_limit": 30.0}, headers=admin_headers)
    coa = await _coa(client, admin_headers, spec["id"], batch=AB, report_date="2026-07-01")
    await client.post(f"/qc/certificates/{coa['id']}/results",
                      json={"parameter_id": p.json()["id"], "test_name": "Total THC",
                            "result_numeric": 22.0, "lower_limit": 10.0, "upper_limit": 30.0},
                      headers=admin_headers)
    await client.patch(f"/qc/certificates/{coa['id']}", json={"decision": "PASS"}, headers=admin_headers)
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}", json={"status": tgt},
                                   headers=qp)).status_code == 200
    inh = (await client.get(f"/qc/genealogy/{PACK}/inherited-results", headers=admin_headers)).json()
    assert AB in inh["ancestors"]
    assert any(b["from_batch_id"] == AB and b["coa_number"] == coa["coa_number"]
               and b["results"][0]["test_name"] == "Total THC" for b in inh["inherited"])


async def test_genealogy_blend_multiple_parents(client, admin_headers):
    """Decision D2 — a packaging lot BLENDED from two processing lots has both
    as parents (m:n), and both appear among its ancestors."""
    await _edge(client, admin_headers, "P-A", "PACK-BLEND", "BLEND")
    await _edge(client, admin_headers, "P-B", "PACK-BLEND", "BLEND")
    g = (await client.get("/qc/genealogy/PACK-BLEND", headers=admin_headers)).json()
    assert {e["parent_batch_id"] for e in g["parents"]} == {"P-A", "P-B"}
    assert {a["batch_id"] for a in g["ancestors"]} == {"P-A", "P-B"}


async def test_genealogy_cycle_and_validation_guards(client, admin_headers):
    await _edge(client, admin_headers, "C-A", "C-B")
    await _edge(client, admin_headers, "C-B", "C-C")
    # C-C → C-A would close a cycle (A is an ancestor of C)
    assert (await client.post("/qc/genealogy",
                              json={"parent_batch_id": "C-C", "child_batch_id": "C-A"},
                              headers=admin_headers)).status_code == 409
    # a self-edge is rejected
    assert (await client.post("/qc/genealogy",
                              json={"parent_batch_id": "C-A", "child_batch_id": "C-A"},
                              headers=admin_headers)).status_code == 422
    # a duplicate edge is rejected
    assert (await client.post("/qc/genealogy",
                              json={"parent_batch_id": "C-A", "child_batch_id": "C-B"},
                              headers=admin_headers)).status_code == 409
    # an unknown relation is rejected
    assert (await client.post("/qc/genealogy",
                              json={"parent_batch_id": "C-X", "child_batch_id": "C-Y", "relation": "NOPE"},
                              headers=admin_headers)).status_code == 422


async def test_genealogy_is_write_gated_and_deletable(client, admin_headers):
    _, user = await _actor(client, admin_headers, "USER")
    assert (await client.post("/qc/genealogy",
                              json={"parent_batch_id": "G-1", "child_batch_id": "G-2"},
                              headers=user)).status_code == 403
    edge = await _edge(client, admin_headers, "G-1", "G-2")
    assert (await client.delete(f"/qc/genealogy/{edge['id']}", headers=admin_headers)).status_code == 204
    g = (await client.get("/qc/genealogy/G-2", headers=admin_headers)).json()
    assert g["parents"] == []


async def test_ecoa_is_write_gated(client, admin_headers):
    _, user_headers = await _actor(client, admin_headers, "USER")
    r = await client.post("/qc/coa-documents", json={"batch_id": "B-X"}, headers=user_headers)
    assert r.status_code == 403


# ── Phase 3 U3 — certificate verify loop (source reconciliation) ────────────
async def _promoted_cert(client, headers, batch, thc=22.0):
    """Register an eCoA, grade one THC field, promote → returns (coa_id, doc_id)."""
    spec = await _spec(client, headers, material=f"VER-{batch}")
    await client.post(f"/qc/specifications/{spec['id']}/parameters",
                      json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                            "test_method": "HPLC", "unit": "%", "lower_limit": 10.0,
                            "upper_limit": 30.0}, headers=headers)
    doc = (await client.post("/qc/coa-documents",
                             json={"batch_id": batch, "specification_id": spec["id"],
                                   "source_institution": "Lab X"}, headers=headers)).json()
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [{"raw_label": "Total THC", "numeric_value": thc, "unit": "%"}]},
                      headers=headers)
    pr = (await client.post(f"/qc/coa-documents/{doc['id']}/promote", headers=headers)).json()
    return pr["coa_id"], doc["id"]


async def test_verify_matches_source(client, admin_headers):
    coa_id, _ = await _promoted_cert(client, admin_headers, "B-VER-OK")
    r = await client.post(f"/qc/certificates/{coa_id}/verify", headers=admin_headers)
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["verdict"] == "VERIFIED" and v["checked"] == 1 and v["mismatches"] == 0
    assert v["details"][0]["match"] is True
    # the run is recorded for audit
    hist = (await client.get(f"/qc/certificates/{coa_id}/verifications", headers=admin_headers)).json()
    assert len(hist) == 1 and hist[0]["verdict"] == "VERIFIED"


async def test_verify_flags_discrepancy(client, admin_headers):
    coa_id, doc_id = await _promoted_cert(client, admin_headers, "B-VER-DIFF")
    d = (await client.get(f"/qc/coa-documents/{doc_id}", headers=admin_headers)).json()
    eid = d["extractions"][0]["id"]
    # a PROMOTED document's extractions are locked — the API can no longer be
    # used to diverge source from certificate (that hole is closed)
    r = await client.patch(f"/qc/coa-documents/{doc_id}/extractions/{eid}",
                           json={"numeric_value": 99.0}, headers=admin_headers)
    assert r.status_code == 409
    # so simulate out-of-band source divergence (the scenario verify exists to
    # catch) by editing the extraction directly in the database
    from app.db import tasks_admin_pool
    async with tasks_admin_pool().acquire() as c:
        await c.execute("UPDATE qc_coa_extractions SET numeric_value=$1 WHERE id=$2",
                        99.0, eid)
    r = await client.post(f"/qc/certificates/{coa_id}/verify", headers=admin_headers)
    assert r.status_code == 201
    v = r.json()
    assert v["verdict"] == "DISCREPANCY" and v["mismatches"] == 1
    assert v["details"][0]["match"] is False and "value" in v["details"][0]["reason"]


async def test_verify_requires_promoted_cert(client, admin_headers):
    # a hand-built certificate (not promoted from an eCoA) has no source to check
    spec = await _spec(client, admin_headers, material="VER-NONE")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-VER-NONE")
    r = await client.post(f"/qc/certificates/{coa['id']}/verify", headers=admin_headers)
    assert r.status_code == 409


async def test_verify_is_write_gated(client, admin_headers):
    coa_id, _ = await _promoted_cert(client, admin_headers, "B-VER-GATE")
    _, user_headers = await _actor(client, admin_headers, "USER")
    r = await client.post(f"/qc/certificates/{coa_id}/verify", headers=user_headers)
    assert r.status_code == 403


# ── QC-U5 — custody cluster (RQS + SFR + chain of custody) ──────────────────
# QCSOP 011 §6.1.4 mandatory registration fields — an RQS must carry all of
# these before the QC Head may register it into the MLL (§6.1.6 completeness gate).
_RQS_COMPLETE = dict(num_samples=2, required_tests=["POTENCY"], storage_location="QC store",
                     material_status="QUARANTINE", spec_reference="SPEC-REF/2026")


async def _rqs(client, headers, **extra):
    body = {"material_code": "CANN-FLOS-D", "originating_department": "Production", **extra}
    r = await client.post("/qc/sampling-requests", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _rqs_registered(client, headers, **extra):
    """A §6.1.4-complete RQS advanced to REGISTERED — the precondition for an SFR."""
    body = {"batch_id": extra.pop("batch_id", "B-REG"), **_RQS_COMPLETE, **extra}
    rqs = await _rqs(client, headers, **body)
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_rqs_lifecycle_and_24h_window(client, admin_headers):
    # §6.1.3 Request Ordinal format PP-QC-F-001.A01/YYYY-NNN
    rqs = await _rqs(client, admin_headers, batch_id="B-RQS-1", **_RQS_COMPLETE)
    assert rqs["rqs_number"].startswith("PP-QC-F-001.A01/") and rqs["status"] == "OPEN"
    assert rqs["registration_deadline"] is not None  # requested_at + 24h
    # register within the window → REGISTERED, window met, control number minted
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "REGISTERED"
    assert r.json()["registration_window_met"] is True and r.json()["registered_at"]
    assert r.json()["qc_control_number"] and r.json()["qc_control_number"].endswith("_RQS")  # §6.1.6 MLL control №
    # assign → IN_PROGRESS (defaults assignee to the actor), then complete
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "IN_PROGRESS"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["assigned_to_id"] and r.json()["assigned_at"]
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "COMPLETED"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["completed_at"]


async def test_rqs_illegal_transition(client, admin_headers):
    rqs = await _rqs(client, admin_headers, batch_id="B-RQS-BAD")
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "COMPLETED"}, headers=admin_headers)
    assert r.status_code == 409  # OPEN -> COMPLETED not allowed


async def test_rqs_registration_requires_mandatory_fields(client, admin_headers):
    """§6.1.6 completeness gate — an incomplete RQS cannot be registered; the
    missing §6.1.4 fields are named, and filling them lets registration proceed."""
    rqs = await _rqs(client, admin_headers, batch_id="B-INC-1")   # batch only, else empty
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=admin_headers)
    assert r.status_code == 422 and "6.1.6" in r.text
    # fill the mandatory fields, then registration succeeds
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json=dict(_RQS_COMPLETE), headers=admin_headers)
    assert r.status_code == 200, r.text
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["qc_control_number"]


async def test_rqs_field_validation(client, admin_headers):
    """§6.1.4 enumerations are validated; an URGENT request needs a justification."""
    r = await client.post("/qc/sampling-requests",
                          json={"material_code": "M", "originating_department": "D", "required_tests": ["NOPE"]},
                          headers=admin_headers)
    assert r.status_code == 422 and "required_tests" in r.text
    r = await client.post("/qc/sampling-requests",
                          json={"material_code": "M", "originating_department": "D", "material_status": "BOGUS"},
                          headers=admin_headers)
    assert r.status_code == 422
    r = await client.post("/qc/sampling-requests",
                          json={"material_code": "M", "originating_department": "D", "priority": "URGENT"},
                          headers=admin_headers)
    assert r.status_code == 422 and "justification" in r.text
    r = await client.post("/qc/sampling-requests",
                          json={"material_code": "M", "originating_department": "D",
                                "priority": "URGENT", "priority_justification": "stability pull due"},
                          headers=admin_headers)
    assert r.status_code == 201 and r.json()["priority"] == "URGENT"


async def test_rqs_registration_is_qc_role_gated(client, admin_headers):
    """§3/§6.1.6 — registration into the MLL is a QC-Head act. A non-QC writer
    (executive) may raise an RQS but may not register it."""
    _, ceo_h = await _actor(client, admin_headers, "CEO")
    rqs = await _rqs(client, ceo_h, batch_id="B-CEO-1", **_RQS_COMPLETE)   # executive may create
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=ceo_h)
    assert r.status_code == 403 and "6.1.6" in r.text
    # the QC Manager may
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=qc_h)
    assert r.status_code == 200


async def test_rqs_release_related_escalates_to_qp(client, admin_headers):
    """§6.1.2 — a release-related RQS is registered by the Qualified Person, not
    the QC Manager."""
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    rqs = await _rqs(client, qc_h, batch_id="B-REL-1", release_related=True, **_RQS_COMPLETE)
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=qc_h)
    assert r.status_code == 403 and "6.1.2" in r.text
    _, qp_h = await _actor(client, admin_headers, "QP")
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=qp_h)
    assert r.status_code == 200 and r.json()["release_related"] is True


async def test_release_related_flag_cannot_be_dropped_to_dodge_qp(client, admin_headers):
    """§6.1.2 segregation of duties — a non-QP writer must not be able to clear
    the release-related flag, either in the register PATCH or beforehand, to
    register a QP-reserved request itself."""
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    rqs = await _rqs(client, qc_h, batch_id="B-DODGE", release_related=True, **_RQS_COMPLETE)
    # same-PATCH attempt: flip the flag false while registering → 403 (can't clear)
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}",
                           json={"status": "REGISTERED", "release_related": False}, headers=qc_h)
    assert r.status_code == 403
    # two-step attempt: clear the flag first → 403 (only QP may clear it)
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}",
                           json={"release_related": False}, headers=qc_h)
    assert r.status_code == 403 and "6.1.2" in r.text
    # the QP legitimately registers it
    _, qp_h = await _actor(client, admin_headers, "QP")
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=qp_h)
    assert r.status_code == 200


async def test_registration_rejects_blank_and_zero_fields(client, admin_headers):
    """§6.1.6 completeness — whitespace-only mandatory strings and a zero sample
    count do not satisfy the gate."""
    rqs = await _rqs(client, admin_headers, batch_id="   ", num_samples=0,
                     required_tests=["POTENCY"], storage_location="  ",
                     material_status="QUARANTINE", spec_reference="\t")
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}", json={"status": "REGISTERED"}, headers=admin_headers)
    assert r.status_code == 422
    body = r.text
    assert "batch_id" in body and "num_samples" in body and "storage_location" in body and "spec_reference" in body


async def test_sfr_requires_registered_rqs(client, admin_headers):
    """§6.1.1 (MAJOR) — no sampling may be recorded without a registered RQS.
    The rqs_id is required, must exist, and must be past OPEN."""
    # missing rqs_id → 422 (required field)
    r = await client.post("/qc/field-records",
                          json={"sampling_location": "GH", "destination_facility": "QC Lab"},
                          headers=admin_headers)
    assert r.status_code == 422
    # an OPEN (unregistered) RQS → 409
    rqs = await _rqs(client, admin_headers, batch_id="B-SFR-OPEN", **_RQS_COMPLETE)
    r = await client.post("/qc/field-records",
                          json={"rqs_id": rqs["id"], "sampling_location": "GH", "destination_facility": "QC Lab"},
                          headers=admin_headers)
    assert r.status_code == 409 and "6.1.1" in r.text
    # register it → the SFR is now accepted
    assert (await client.patch(f"/qc/sampling-requests/{rqs['id']}",
                               json={"status": "REGISTERED"}, headers=admin_headers)).status_code == 200
    r = await client.post("/qc/field-records",
                          json={"rqs_id": rqs["id"], "sampling_location": "GH", "destination_facility": "QC Lab"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text


async def test_sfr_create_and_lifecycle(client, admin_headers):
    rqs = await _rqs_registered(client, admin_headers, batch_id="B-SFR-1")
    r = await client.post("/qc/field-records", json={
        "rqs_id": rqs["id"], "sampling_location": "Greenhouse 3",
        "sampling_coordinates": "41.99,21.43", "barrel_numbers": ["B-01", "B-02"],
        "num_containers": 2, "destination_facility": "QC Lab",
        "sampling_equipment": "SS scoop / sterile bag",
        "planned_departure": "2026-07-16T08:00:00Z"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    sfr = r.json()
    assert sfr["sfr_number"].startswith("PP-SFR-") and sfr["status"] == "CREATED"
    assert sfr["barrel_numbers"] == ["B-01", "B-02"] and sfr["num_containers"] == 2
    assert sfr["rqs_id"] == rqs["id"] and sfr["sampling_equipment"] == "SS scoop / sterile bag"
    # §6.3.2 receipt fields round-trip on PATCH
    r = await client.patch(f"/qc/field-records/{sfr['id']}",
                           json={"ambient_conditions": "22°C / 45% RH", "received_condition": "intact, sealed"},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["ambient_conditions"] == "22°C / 45% RH"
    assert r.json()["received_condition"] == "intact, sealed"
    for tgt in ("IN_FIELD", "COMPLETED"):
        r = await client.patch(f"/qc/field-records/{sfr['id']}", json={"status": tgt}, headers=admin_headers)
        assert r.status_code == 200 and r.json()["status"] == tgt, tgt


async def test_chain_of_custody_append_and_list(client, admin_headers):
    sample = await _sample(client, admin_headers, batch="B-CUST-1")
    r = await client.post(f"/qc/samples/{sample['id']}/custody", json={
        "to_location": "QC Lab - Cabinet A", "transfer_reason": "Testing",
        "transfer_type": "FIELD_TO_LAB",
        "sample_condition": "seal intact", "condition_ok": True}, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["from_user_id"]  # defaults to the acting user
    # §6.3.1 condition confirmation round-trips
    assert r.json()["sample_condition"] == "seal intact" and r.json()["condition_ok"] is True
    lst = (await client.get(f"/qc/samples/{sample['id']}/custody", headers=admin_headers)).json()
    assert len(lst) == 1 and lst[0]["transfer_type"] == "FIELD_TO_LAB"
    # bad transfer_type rejected; missing sample 404
    r = await client.post(f"/qc/samples/{sample['id']}/custody", json={"transfer_type": "TELEPORT"}, headers=admin_headers)
    assert r.status_code == 422
    import uuid as _uuid
    r = await client.post(f"/qc/samples/{_uuid.uuid4()}/custody", json={}, headers=admin_headers)
    assert r.status_code == 404


async def test_custody_cluster_is_write_gated(client, admin_headers):
    _, user_headers = await _actor(client, admin_headers, "USER")
    r = await client.post("/qc/sampling-requests",
                          json={"material_code": "X", "originating_department": "Y"}, headers=user_headers)
    assert r.status_code == 403


# ── QC-U6 — water / stability / transport leaves ────────────────────────────
async def test_water_test_crud(client, admin_headers):
    r = await client.post("/qc/water-tests", json={
        "location": "RO_F97_001", "grade": "RO", "result_date": "2026-07-16",
        "parameters": {"pH": 6.8, "Conductivity": 1.1, "TOC": 0.3}, "passed": True}, headers=admin_headers)
    assert r.status_code == 201, r.text
    wt = r.json()
    assert wt["water_test_id"].startswith("PP-WT-") and wt["grade"] == "RO"
    assert wt["parameters"]["pH"] == 6.8 and wt["passed"] is True
    r = await client.patch(f"/qc/water-tests/{wt['id']}", json={"passed": False, "ooe": "TOC drift"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["passed"] is False and r.json()["ooe"] == "TOC drift"
    lst = (await client.get("/qc/water-tests?location=RO_F97_001", headers=admin_headers)).json()
    assert any(x["id"] == wt["id"] for x in lst)
    # bad grade rejected
    r = await client.post("/qc/water-tests", json={"location": "X", "grade": "ZZ"}, headers=admin_headers)
    assert r.status_code == 422


async def test_stability_study_lifecycle(client, admin_headers):
    r = await client.post("/qc/stability-studies", json={
        "study_type": "LT", "material_code": "TD1-DF400", "material_name_en": "Flos",
        "material_name_mk": "Цвет", "batches": ["B-1", "B-2"], "started": "2026-01-01"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    st = r.json()
    assert st["study_id"].startswith("PP-STB-") and st["study_type"] == "LT" and st["status"] == "IN_PROGRESS"
    assert st["batches"] == ["B-1", "B-2"]
    r = await client.patch(f"/qc/stability-studies/{st['id']}",
                           json={"status": "CLOSED", "shelf_life": "24 months", "report": "REP-01"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "CLOSED" and r.json()["shelf_life"] == "24 months"
    # bad type / status rejected
    assert (await client.post("/qc/stability-studies", json={"study_type": "XX", "material_code": "M"}, headers=admin_headers)).status_code == 422
    assert (await client.patch(f"/qc/stability-studies/{st['id']}", json={"status": "BOGUS"}, headers=admin_headers)).status_code == 422


async def test_sample_transport_forms(client, admin_headers):
    r = await client.post("/qc/transports", json={
        "sample_id": "PP-SMP-2026-0001", "batch_id": "B-9", "external_lab": "EuroLab",
        "tests": ["THC", "Pesticides"]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    tr = r.json()
    assert tr["transport_id"].startswith("PP-TRN-") and tr["status"] == "draft"
    assert tr["tests"] == ["THC", "Pesticides"] and tr["forms"]["sar"] is False
    r = await client.patch(f"/qc/transports/{tr['id']}",
                           json={"status": "in_transit", "form_sar": True, "form_tmcoc": True,
                                 "tracking": "DHL-123", "shipped_date": "2026-07-16"}, headers=admin_headers)
    assert r.status_code == 200
    tr2 = r.json()
    assert tr2["status"] == "in_transit" and tr2["forms"]["sar"] is True and tr2["forms"]["tmcoc"] is True
    assert tr2["tracking"] == "DHL-123"
    assert (await client.patch(f"/qc/transports/{tr['id']}", json={"status": "beamed"}, headers=admin_headers)).status_code == 422


async def test_qc_leaves_write_gated(client, admin_headers):
    _, user_headers = await _actor(client, admin_headers, "USER")
    assert (await client.post("/qc/water-tests", json={"location": "X", "grade": "RO"}, headers=user_headers)).status_code == 403
    assert (await client.post("/qc/stability-studies", json={"study_type": "LT", "material_code": "M"}, headers=user_headers)).status_code == 403
    assert (await client.post("/qc/transports", json={"sample_id": "S"}, headers=user_headers)).status_code == 403


# ── P3-U4 — RAG Q&A over ingested CoAs ──────────────────────────────────────
async def test_coa_chunks_index_and_qa(client, admin_headers):
    doc = await _ecoa_doc(client, admin_headers, batch="B-RAG")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/chunks", json={"chunks": [
        "Total THC content was determined by HPLC to be 22.4 percent.",
        "Heavy metals: lead below 0.5 ppm, cadmium not detected.",
        "Microbial limits: total aerobic count within pharmacopoeia specification."]}, headers=admin_headers)
    assert r.status_code == 201 and r.json()["indexed"] == 3
    # retrieval finds the relevant passage and cites it
    r = await client.post("/qc/coa-qa", json={"question": "what was the THC content?"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    qa = r.json()
    assert qa["grounded"] is True and qa["passages"]
    top = qa["passages"][0]
    assert "THC" in top["content"] and top["doc_number"] == doc["doc_number"]
    assert top["doc_number"] in qa["answer"]                # the answer cites its source
    # document-scoped retrieval
    r2 = await client.post("/qc/coa-qa", json={"question": "heavy metals lead", "document_id": doc["id"]}, headers=admin_headers)
    assert r2.json()["passages"][0]["content"].startswith("Heavy metals")
    # re-index is idempotent (replaces)
    r = await client.post(f"/qc/coa-documents/{doc['id']}/chunks", json={"chunks": ["Only one chunk now."]}, headers=admin_headers)
    assert r.json()["indexed"] == 1
    assert len((await client.get(f"/qc/coa-documents/{doc['id']}/chunks", headers=admin_headers)).json()) == 1


async def test_coa_qa_no_match_is_grounded_false(client, admin_headers):
    doc = await _ecoa_doc(client, admin_headers, batch="B-RAG-EMPTY")
    await client.post(f"/qc/coa-documents/{doc['id']}/chunks",
                      json={"chunks": ["Total THC content 22 percent."]}, headers=admin_headers)
    r = await client.post("/qc/coa-qa", json={"question": "xyzzy quux nonexistent term"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["grounded"] is False and r.json()["answer"] == ""


async def test_coa_qa_read_gated_index_write_gated(client, admin_headers):
    doc = await _ecoa_doc(client, admin_headers, batch="B-RAG-GATE")
    _, user_headers = await _actor(client, admin_headers, "USER")
    # a plain USER is below the elevated read gate
    assert (await client.post("/qc/coa-qa", json={"question": "thc"}, headers=user_headers)).status_code == 403
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/chunks", json={"chunks": ["x"]}, headers=user_headers)).status_code == 403


# ── Phase 4 hardening — write-side FK validation (422 not 500) + terminal locks ──
_FAKE_UUID = "00000000-0000-0000-0000-0000000000ff"


async def test_add_result_rejects_unknown_and_cross_spec_parameter(client, admin_headers):
    # unknown parameter id → 422 (not a raw FK 500)
    specA, paramA = await _ecoa_spec_with_param(client, admin_headers, material="HARD-A")
    coaA = await _coa(client, admin_headers, specA["id"], batch="B-HARD-A")
    r = await client.post(f"/qc/certificates/{coaA['id']}/results",
                          json={"test_name": "x", "parameter_id": _FAKE_UUID}, headers=admin_headers)
    assert r.status_code == 422, r.text
    # a parameter from ANOTHER spec → 422 (can't cite a cross-spec parameter)
    specB = await _spec(client, admin_headers, material="HARD-B")
    coaB = await _coa(client, admin_headers, specB["id"], batch="B-HARD-B")
    r = await client.post(f"/qc/certificates/{coaB['id']}/results",
                          json={"test_name": "Total THC", "parameter_id": paramA["id"]}, headers=admin_headers)
    assert r.status_code == 422 and "specification" in r.json()["detail"].lower(), r.text


async def test_placeholder_rejects_unknown_parameter_without_status(client, admin_headers):
    spec, _ = await _ecoa_spec_with_param(client, admin_headers, material="HARD-PH")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-HARD-PH")
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [{"raw_label": "Odd Label", "numeric_value": 1.0}]}, headers=admin_headers)
    ph = [p for p in (await client.get("/qc/coa-placeholders", headers=admin_headers)).json()
          if p["raw_label"] == "Odd Label"][0]
    # a bad mapped_parameter_id with NO status change must still 422 (was a 500)
    r = await client.patch(f"/qc/coa-placeholders/{ph['id']}",
                           json={"mapped_parameter_id": _FAKE_UUID}, headers=admin_headers)
    assert r.status_code == 422, r.text


async def test_sfr_rqs_reject_unknown_sample(client, admin_headers):
    # create_sfr against a registered RQS but a bad sample_id → 422 (not a raw FK 500)
    reg = await _rqs_registered(client, admin_headers, batch_id="B-HARD-REG")
    r = await client.post("/qc/field-records",
                          json={"rqs_id": reg["id"], "sampling_location": "GH",
                                "destination_facility": "QC Lab", "sample_id": _FAKE_UUID},
                          headers=admin_headers)
    assert r.status_code == 422, r.text
    # update_rqs / update_sfr with a bad sample_id → 422
    rqs = await _rqs(client, admin_headers, batch_id="B-HARD-RQS")
    r = await client.patch(f"/qc/sampling-requests/{rqs['id']}",
                           json={"sample_id": _FAKE_UUID}, headers=admin_headers)
    assert r.status_code == 422, r.text
    sfr = (await client.post("/qc/field-records",
                             json={"rqs_id": reg["id"], "sampling_location": "GH2",
                                   "destination_facility": "QC Lab"},
                             headers=admin_headers)).json()
    r = await client.patch(f"/qc/field-records/{sfr['id']}",
                           json={"sample_id": _FAKE_UUID}, headers=admin_headers)
    assert r.status_code == 422, r.text


async def test_batch_size_caps(client, admin_headers):
    doc = await _ecoa_doc(client, admin_headers, batch="B-HARD-CAP")
    r = await client.post(f"/qc/coa-documents/{doc['id']}/chunks",
                          json={"chunks": ["x"] * 2001}, headers=admin_headers)
    assert r.status_code == 422, r.text
    r = await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                          json={"items": [{"raw_label": "x"}] * 501}, headers=admin_headers)
    assert r.status_code == 422, r.text


# ── Regression: 2026-07-17 backend audit fixes ──────────────────────────────
async def test_result_partial_limit_inherits_spec_bound(client, admin_headers):
    """A cited parameter that supplies only ONE limit must still inherit the
    spec's other bound — a partial override must never silently disable it and
    grade an out-of-spec value as compliant (GxP: never fabricate conformance)."""
    spec = await _spec(client, admin_headers, material="PARTIAL-MAT")
    p = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                          json={"test_name_en": "Total THC", "unit": "%",
                                "lower_limit": 18.0, "upper_limit": 30.0}, headers=admin_headers)
    param_id = p.json()["id"]
    coa = await _coa(client, admin_headers, spec["id"], batch="B-PARTIAL")
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Total THC", "parameter_id": param_id,
                                "lower_limit": 18.0, "result_numeric": 40.0}, headers=admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["upper_limit"] == 30.0        # inherited from the spec
    assert body["complies"] is False          # 40 > 30 — not graded compliant


async def test_reviewer_cannot_be_a_result_analyst(client, admin_headers):
    """Second-person review: the reviewer must differ from ANYONE who entered a
    result, not only the CoA's analyst-of-record (each result stamps its own
    analyst_id)."""
    spec = await _spec(client, admin_headers, material="REV2-MAT")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-REV2")   # analyst-of-record = admin
    _, b_h = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/certificates/{coa['id']}/results",
                          json={"test_name": "Water", "result_numeric": 5.0, "upper_limit": 10.0},
                          headers=b_h)
    assert r.status_code == 201, r.text
    # B produced data on this CoA → B may not review it (even though B != creator)
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "REVIEWED"}, headers=b_h)
    assert r.status_code == 403, r.text
    # a third, uninvolved qualified person may
    _, c_h = await _actor(client, admin_headers, "QC_MGR")
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"status": "REVIEWED"}, headers=c_h)
    assert r.status_code == 200 and r.json()["status"] == "REVIEWED"


async def test_spec_acceptance_criteria_locked_after_authoring(client, admin_headers):
    """Acceptance criteria freeze once the spec leaves the authoring states — the
    same control the child parameters already enforce. notes + a lifecycle
    transition stay allowed."""
    spec = await _spec(client, admin_headers, material="LOCK-MAT")
    for tgt in ("QC_REVIEW", "QA_APPROVED", "NUMBERED", "TRAINED", "ACTIVE"):
        assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": tgt},
                                   headers=admin_headers)).status_code == 200, tgt
    r = await client.patch(f"/qc/specifications/{spec['id']}",
                           json={"thc_acceptance_max": 99.0}, headers=admin_headers)
    assert r.status_code == 409, r.text
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"notes": "audit note"},
                               headers=admin_headers)).status_code == 200
    assert (await client.patch(f"/qc/specifications/{spec['id']}", json={"status": "UNDER_CHANGE"},
                               headers=admin_headers)).status_code == 200


async def test_malformed_uuid_returns_4xx_not_500(client, admin_headers):
    """A garbage {id} path → clean 404; a garbage uuid BODY field → 422 — never a
    500 from asyncpg trying to cast the value."""
    assert (await client.get("/qc/specifications/not-a-uuid", headers=admin_headers)).status_code == 404
    assert (await client.get("/qc/samples/xyz", headers=admin_headers)).status_code == 404
    assert (await client.get("/qc/certificates/nope", headers=admin_headers)).status_code == 404
    reg = await _rqs_registered(client, admin_headers, batch_id="B-HARD-UUID")
    r = await client.post("/qc/field-records",
                          json={"rqs_id": reg["id"], "sampling_location": "Field A",
                                "destination_facility": "Lab", "sampled_by_id": "not-a-uuid"},
                          headers=admin_headers)
    assert r.status_code == 422, r.text


# ── QCSOP 012 §6.4 (C5) — per-batch CoQ aggregation + Tier 3 (C6/C7/C8) ──────
async def _coq_spec_two_params(client, headers, material="COQA-MAT"):
    """A spec with two parameters (Total THC 10–30 % and Moisture ≤ 12 %)."""
    spec = await _spec(client, headers, material=material)
    pa = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                           json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                                 "test_method": "HPLC", "unit": "%", "lower_limit": 10.0,
                                 "upper_limit": 30.0}, headers=headers)
    assert pa.status_code == 201, pa.text
    pb = await client.post(f"/qc/specifications/{spec['id']}/parameters",
                           json={"test_name_en": "Moisture", "test_name_mk": "Влага",
                                 "test_method": "LOD", "unit": "%", "upper_limit": 12.0},
                           headers=headers)
    assert pb.status_code == 201, pb.text
    return spec, pa.json(), pb.json()


async def _approved_coa(client, headers, qp_headers, spec_id, batch, results,
                        decision="PASS"):
    """A certificate driven to APPROVED — a usable §6.4.2 CoQ source."""
    coa = await _coa(client, headers, spec_id, batch=batch, report_date="2026-07-01")
    for res in results:
        assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                                  json=res, headers=headers)).status_code == 201, res
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"decision": decision}, headers=headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp_headers)).status_code == 200, tgt
    return coa


async def test_coq_compile_aggregates_batch(client, admin_headers):
    """§6.4.1/§6.4.2 — the CoQ consolidates every approved iCoA result for the
    batch against the spec: one line per parameter, each citing its source
    certificate; overall conformance derived, never typed; the CoQ-PP number
    series is SHARED with certificate-type-COQ records (§6.13, one register)."""
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers)
    coa_a = await _approved_coa(client, admin_headers, qp, spec["id"], "B-AGG", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0}])
    coa_b = await _approved_coa(client, admin_headers, qp, spec["id"], "B-AGG", [
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0,
         "source_institution": "Contract Lab GmbH"}])
    r = await client.post("/qc/coq", json={"batch_id": "B-AGG", "specification_id": spec["id"],
                                           "product_name": "Cannabis flos 22%"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    coq = r.json()
    assert coq["coq_number"].startswith("CoQ-PP-") and coq["status"] == "DRAFT"
    assert coq["overall_conform"] is True and coq["compiled_by"]
    assert spec["spec_id"] in (coq["spec_reference"] or "")
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert len(d["lines"]) == 2 and len(d["sources"]) == 2
    by_name = {ln["parameter_name"]: ln for ln in d["lines"]}
    assert by_name["Total THC"]["source_coa_number"] == coa_a["coa_number"]
    assert by_name["Moisture"]["source_coa_number"] == coa_b["coa_number"]
    assert by_name["Moisture"]["testing_lab"] == "Contract Lab GmbH"
    assert by_name["Total THC"]["complies"] is True
    assert "10" in by_name["Total THC"]["acceptance_criterion"]
    # §6.13 shared series — a certificate-type-COQ record mints the NEXT number
    # in the same CoQ-PP series (never a duplicate), and vice versa.
    seq = int(coq["coq_number"].rsplit("-", 1)[1])
    cert_coq = await _coa(client, admin_headers, spec["id"], batch="B-AGG",
                          cert_type="COQ")
    assert int(cert_coq["coa_number"].rsplit("-", 1)[1]) == seq + 1
    r2 = await client.post("/qc/coq", json={"batch_id": "B-AGG", "specification_id": spec["id"]},
                           headers=admin_headers)
    assert int(r2.json()["coq_number"].rsplit("-", 1)[1]) == seq + 2


async def test_coq_compile_prerequisites(client, admin_headers):
    """§6.4.1 — no sources → refused; incomplete parameter coverage → refused
    (a partially-tested batch never gets a CoQ)."""
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="COQA-PRE")
    r = await client.post("/qc/coq", json={"batch_id": "B-NOSRC", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 409 and "source certificate" in r.json()["detail"]
    # one param covered, one not → named in the refusal
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-PART", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0}])
    r = await client.post("/qc/coq", json={"batch_id": "B-PART", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 409 and "Moisture" in r.json()["detail"]


async def test_coq_compile_checklist_gate(client, admin_headers):
    """§6.3.2 — an eCoA source promoted from an ingested document feeds a CoQ
    only after its QCT 018 review checklist is ACCEPTED."""
    _, qp = await _actor(client, admin_headers, "QP")
    spec, param = await _ecoa_spec_with_param(client, admin_headers, material="COQA-CL")
    doc = await _ecoa_doc(client, admin_headers, spec["id"], batch="B-CLG")
    await client.post(f"/qc/coa-documents/{doc['id']}/extractions",
                      json={"items": [{"raw_label": "Total THC", "numeric_value": 22.0,
                                       "unit": "%"}]}, headers=admin_headers)
    out = (await client.post(f"/qc/coa-documents/{doc['id']}/promote",
                             headers=admin_headers)).json()
    assert (await client.patch(f"/qc/certificates/{out['coa_id']}",
                               json={"decision": "PASS"}, headers=admin_headers)).status_code == 200
    for tgt in ("REVIEWED", "APPROVED"):
        assert (await client.patch(f"/qc/certificates/{out['coa_id']}",
                                   json={"status": tgt}, headers=qp)).status_code == 200
    # no checklist yet → blocked, naming the document
    r = await client.post("/qc/coq", json={"batch_id": "B-CLG", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 409 and "QCT 018" in r.json()["detail"]
    assert doc["doc_number"] in r.json()["detail"]
    # fill + accept the checklist (HoQC) → compiles, citing the external lab
    assert (await client.put(f"/qc/coa-documents/{doc['id']}/checklist",
                             json={"sample_id_match": True, "method_per_tqa": True,
                                   "units_per_spec": True, "conformance_by_pp": True},
                             headers=admin_headers)).status_code == 200
    assert (await client.post(f"/qc/coa-documents/{doc['id']}/checklist/decide",
                              json={"outcome": "ACCEPTED"}, headers=admin_headers)).status_code == 200
    r = await client.post("/qc/coq", json={"batch_id": "B-CLG", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    d = (await client.get(f"/qc/coq/{r.json()['id']}", headers=admin_headers)).json()
    assert d["sources"][0]["cert_type"] == "ECOA"
    assert d["lines"][0]["testing_lab"] == "Contract Lab GmbH"


async def test_coq_second_person_review_and_void(client, admin_headers):
    """§6.4.3 — HoQC approves the CoQ, but never their own compilation (second
    person); §6.6 — voiding needs a written reason and is terminal."""
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="COQA-REV")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-REV", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    coq = (await client.post("/qc/coq", json={"batch_id": "B-REV", "specification_id": spec["id"]},
                             headers=admin_headers)).json()
    # the compiler (admin) cannot approve their own compilation
    r = await client.post(f"/qc/coq/{coq['id']}/review", headers=admin_headers)
    assert r.status_code == 403
    # a non-HoQC writer cannot review at all
    _, ceo = await _actor(client, admin_headers, "CEO")
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=ceo)).status_code == 403
    # a second HoQC person approves
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)
    assert r.status_code == 200 and r.json()["status"] == "APPROVED" and r.json()["reviewed_by"]
    # approve again → 409 (not DRAFT any more)
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)).status_code == 409
    # void: reason mandatory; non-HoQC 403; then terminal
    assert (await client.post(f"/qc/coq/{coq['id']}/void", json={"reason": ""},
                              headers=qc)).status_code == 422
    assert (await client.post(f"/qc/coq/{coq['id']}/void", json={"reason": "wrong batch"},
                              headers=ceo)).status_code == 403
    r = await client.post(f"/qc/coq/{coq['id']}/void", json={"reason": "wrong batch"}, headers=qc)
    assert r.status_code == 200 and r.json()["status"] == "VOIDED" and r.json()["void_reason"]
    assert (await client.post(f"/qc/coq/{coq['id']}/void", json={"reason": "again"},
                              headers=qc)).status_code == 409
    # retained, never deleted
    assert (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).status_code == 200


async def test_coq_render_document(client, admin_headers, monkeypatch):
    """The APPROVED, conforming CoQ renders to the house-style document via the
    DocEngine; a DRAFT one does not; the artifact pointer is persisted."""
    _stub_de(monkeypatch, {"document_id": "DE-COQAGG-1", "verify": "RESULT: PASS", "bytes": 2048})
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="COQA-RND")
    coa = await _approved_coa(client, admin_headers, qp, spec["id"], "B-RND", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    coq = (await client.post("/qc/coq", json={"batch_id": "B-RND", "specification_id": spec["id"]},
                             headers=admin_headers)).json()
    # DRAFT → no render
    assert (await client.post(f"/qc/coq/{coq['id']}/render",
                              headers=admin_headers)).status_code == 409
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)).status_code == 200
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["document_id"] == "DE-COQAGG-1"
    d = (await client.get(f"/qc/coq/{coq['id']}", headers=admin_headers)).json()
    assert d["coq"]["coq_document_id"] == "DE-COQAGG-1" and d["coq"]["coq_generated_at"]
    md = _FakeDE.last_markdown
    assert "Certificate of Quality" in md and coq["coq_number"] in md
    assert coa["coa_number"] in md            # every line cites its source cert
    assert "Total THC" in md and "Moisture" in md


async def test_coq_non_conforming_batch_never_renders(client, admin_headers, monkeypatch):
    """GxP — a failing line is RECORDED on the CoQ (overall_conform=false), and
    a conformance-asserting document is never rendered over it."""
    _stub_de(monkeypatch, {"document_id": "DE-NEVER", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="COQA-FAIL")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-FAILQ", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 99.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}],
        decision="FAIL")
    coq = (await client.post("/qc/coq", json={"batch_id": "B-FAILQ", "specification_id": spec["id"]},
                             headers=admin_headers)).json()
    assert coq["overall_conform"] is False
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/coq/{coq['id']}/review", headers=qc)).status_code == 200
    r = await client.post(f"/qc/coq/{coq['id']}/render", headers=admin_headers)
    assert r.status_code == 409 and "not conform" in r.json()["detail"]


async def test_coq_open_oos_blocks_compile_and_logs_deviation(client, admin_headers):
    """§6.4.1 + §6.16 (C8) — an open OOS on the batch blocks compilation, and the
    blocked attempt is itself recorded as a deviation."""
    _, qp = await _actor(client, admin_headers, "QP")
    spec, pa, pb = await _coq_spec_two_params(client, admin_headers, material="COQA-OOS")
    await _approved_coa(client, admin_headers, qp, spec["id"], "B-OOSQ", [
        {"parameter_id": pa["id"], "test_name": "Total THC", "result_numeric": 22.0},
        {"parameter_id": pb["id"], "test_name": "Moisture", "result_numeric": 8.0}])
    await _oos(client, admin_headers, batch="B-OOSQ")
    r = await client.post("/qc/coq", json={"batch_id": "B-OOSQ", "specification_id": spec["id"]},
                          headers=admin_headers)
    assert r.status_code == 409 and "§6.16" in r.json()["detail"]


async def test_certificate_c6_analysis_range_and_c7_language(client, admin_headers):
    """§6.2.2 (C6) — analysis date range + sampling location live on the
    certificate; §6.7 (C7) — issue language is controlled (EN / EN-MK) and the
    bilingual translation is verified by a SECOND person, never the analyst."""
    spec = await _spec(client, admin_headers, material="C6C7-MAT")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-C6")
    r = await client.patch(f"/qc/certificates/{coa['id']}",
                           json={"analysis_start_date": "2026-07-01",
                                 "analysis_end_date": "2026-07-03",
                                 "sampling_location": "Drying room 2"},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["analysis_start_date"] == "2026-07-01"
    assert r.json()["analysis_end_date"] == "2026-07-03"
    assert r.json()["sampling_location"] == "Drying room 2"
    # language is controlled — bad value 422; default is bilingual EN-MK
    assert r.json()["issue_language"] == "EN-MK"
    assert (await client.patch(f"/qc/certificates/{coa['id']}",
                               json={"issue_language": "DE"},
                               headers=admin_headers)).status_code == 422
    # the analyst-of-record cannot verify their own translation (second person)
    assert (await client.post(f"/qc/certificates/{coa['id']}/translation-verified",
                              headers=admin_headers)).status_code == 403
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/certificates/{coa['id']}/translation-verified", headers=qc)
    assert r.status_code == 200 and r.json()["translation_verified_by"] and r.json()["translation_verified_at"]
    # an English-only issue has no translation to verify
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"issue_language": "EN"},
                           headers=admin_headers)
    assert r.status_code == 200 and r.json()["issue_language"] == "EN"
    assert (await client.post(f"/qc/certificates/{coa['id']}/translation-verified",
                              headers=qc)).status_code == 409


async def test_edit_archived_certificate_records_deviation(client, admin_headers):
    """§6.16 (C8) — an attempted edit of an archived (voided) certificate is
    refused AND the attempt is recorded as a deviation (the 409 must not roll
    the deviation event back)."""
    spec = await _spec(client, admin_headers, material="C8-MAT")
    coa = await _coa(client, admin_headers, spec["id"], batch="B-C8")
    _, qc = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/certificates/{coa['id']}/void",
                              json={"reason": "wrong batch identified"},
                              headers=qc)).status_code == 200
    r = await client.patch(f"/qc/certificates/{coa['id']}", json={"decision": "PASS"},
                           headers=admin_headers)
    assert r.status_code == 409 and "§6.16" in r.json()["detail"]
