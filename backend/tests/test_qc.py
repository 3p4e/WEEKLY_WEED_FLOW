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
