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
    # unknown parent rejected
    r = await client.post("/qc/samples",
                          json={"batch_id": "B-X", "material_code": "M", "parent_id": parent["id"][:-1] + "0"},
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
    assert coa["coa_number"].startswith("PP-COA-") and coa["status"] == "DRAFT"
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
