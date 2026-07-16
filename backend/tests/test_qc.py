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
    analyst; qp_headers reviews (must differ from analyst) → approves → releases."""
    spec = await _spec(client, headers, material=material)
    await client.post(f"/qc/specifications/{spec['id']}/parameters",
                      json={"test_name_en": "Total THC", "test_name_mk": "Вкупен ТХЦ",
                            "test_method": "HPLC", "unit": "%", "lower_limit": 10.0,
                            "upper_limit": 30.0}, headers=headers)
    coa = await _coa(client, headers, spec["id"], batch="B-COQ")
    for r in (results or [{"test_name": "Total THC", "result_numeric": 22.0,
                           "lower_limit": 10.0, "upper_limit": 30.0, "unit": "%",
                           "source_document_code": "ECOA-LAB-001"}]):
        assert (await client.post(f"/qc/certificates/{coa['id']}/results",
                                  json=r, headers=headers)).status_code == 201
    for tgt in ("REVIEWED", "APPROVED", "RELEASED"):
        assert (await client.patch(f"/qc/certificates/{coa['id']}",
                                   json={"status": tgt}, headers=qp_headers)).status_code == 200, tgt
    return coa


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


async def test_coq_is_qp_gated(client, admin_headers, monkeypatch):
    _stub_de(monkeypatch, {"document_id": "DE-COQ-2", "verify": "RESULT: PASS"})
    _, qp = await _actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="COQ-ROLE")
    _, qc_mgr = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=qc_mgr)).status_code == 403   # QC mgr cannot certify
    assert (await client.post(f"/qc/certificates/{coa['id']}/coq",
                              headers=qp)).status_code == 201        # QP can


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


async def test_ecoa_is_write_gated(client, admin_headers):
    _, user_headers = await _actor(client, admin_headers, "USER")
    r = await client.post("/qc/coa-documents", json={"batch_id": "B-X"}, headers=user_headers)
    assert r.status_code == 403
