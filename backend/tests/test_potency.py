"""QC potency ladders — PP-QC-SPEC-001 per-cultivar THC grade ladders.

Covers the "stored, approved spec data" model (owner decision 2026-08-07): a
versioned DRAFT ladder authored as a contiguous tiling of [floor, 30 %], the
one-APPROVED-per-cultivar rule, segregation of duties on approval (approver ≠
author), and the pure disposition read a certificate uses to grade a batch.
"""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role):
    user, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, user["username"], otp)
    return user, {"Authorization": f"Bearer {token}"}


async def _cultivar(client, headers, code="GP", name="Grape Pie"):
    r = await client.post("/cultivation/cultivars", json={"code": code, "name": name},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# The Grape Pie ladder from PP-QC-SPEC-001 v5.2 (n=10, floor 13.83, 4 specs).
GRAPE_PIE = [
    {"tier": 1, "range_min": 26, "range_max": 30, "nominal": 28.0},
    {"tier": 2, "range_min": 22, "range_max": 26, "nominal": 24.0},
    {"tier": 3, "range_min": 18, "range_max": 22, "nominal": 20.0},
    {"tier": 4, "range_min": 13.83, "range_max": 18, "nominal": 16.0},
]


async def _ladder(client, headers, cultivar_id, version="v5.2", floor=13.83,
                  ranges=None, n_batches=10, **extra):
    body = {"cultivar_id": cultivar_id, "version": version, "variant": "A",
            "floor_pct": floor, "n_batches": n_batches,
            "ranges": ranges if ranges is not None else GRAPE_PIE, **extra}
    r = await client.post("/qc/potency-specs", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_list_get_ladder(client, admin_headers):
    cv = await _cultivar(client, admin_headers)
    spec = await _ladder(client, admin_headers, cv["id"])
    assert spec["status"] == "DRAFT"
    assert spec["spec_code"] == "PP-QC-SPEC-001"
    assert spec["basis"] == "total_d9_thc"
    assert spec["data_supported"] is True          # n=10 ≥ 3
    assert spec["floor_pct"] == 13.83

    r = await client.get("/qc/potency-specs", headers=admin_headers)
    assert r.status_code == 200
    row = next(s for s in r.json() if s["id"] == spec["id"])
    assert row["cultivar_code"] == "GP"

    r = await client.get(f"/qc/potency-specs/{spec['id']}", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["spec"]["id"] == spec["id"]
    ranges = body["ranges"]
    assert [x["tier"] for x in ranges] == [1, 2, 3, 4]
    assert ranges[0]["spec"] == "Spec I" and ranges[0]["range_max"] == 30.0
    assert ranges[-1]["range_min"] == 13.83


async def test_provisional_ladder_is_flagged(client, admin_headers):
    cv = await _cultivar(client, admin_headers, code="OPM", name="Orange Punch Mimosa")
    # floor 7.09, 4 specs — one observed batch → provisional (n<3).
    ranges = [
        {"tier": 1, "range_min": 25, "range_max": 30, "nominal": 28.0},
        {"tier": 2, "range_min": 19, "range_max": 25, "nominal": 22.0},
        {"tier": 3, "range_min": 13, "range_max": 19, "nominal": 16.0},
        {"tier": 4, "range_min": 7.09, "range_max": 13, "nominal": 10.0},
    ]
    spec = await _ladder(client, admin_headers, cv["id"], version="v5.2",
                         floor=7.09, ranges=ranges, n_batches=1)
    assert spec["data_supported"] is False


async def test_ladder_must_tile_floor_to_thirty(client, admin_headers):
    cv = await _cultivar(client, admin_headers, code="BAD", name="Bad Data")

    async def expect_422(ranges, floor=13.83, needle=None):
        body = {"cultivar_id": cv["id"], "version": "vx", "floor_pct": floor,
                "n_batches": 5, "ranges": ranges}
        r = await client.post("/qc/potency-specs", json=body, headers=admin_headers)
        assert r.status_code == 422, r.text
        if needle:
            assert needle in r.text.lower()

    # tiers not contiguous from 1
    await expect_422([{"tier": 1, "range_min": 20, "range_max": 30, "nominal": 25},
                      {"tier": 3, "range_min": 13.83, "range_max": 20, "nominal": 16}],
                     needle="contiguous")
    # Spec I does not reach 30
    await expect_422([{"tier": 1, "range_min": 20, "range_max": 28, "nominal": 24},
                      {"tier": 2, "range_min": 13.83, "range_max": 20, "nominal": 16}],
                     needle="top out")
    # a gap between tiers (they do not meet)
    await expect_422([{"tier": 1, "range_min": 24, "range_max": 30, "nominal": 27},
                      {"tier": 2, "range_min": 13.83, "range_max": 22, "nominal": 18}],
                     needle="do not meet")
    # bottom tier does not start at the floor
    await expect_422([{"tier": 1, "range_min": 26, "range_max": 30, "nominal": 28},
                      {"tier": 2, "range_min": 20, "range_max": 26, "nominal": 23}],
                     needle="floor")
    # nominal outside its range
    await expect_422([{"tier": 1, "range_min": 20, "range_max": 30, "nominal": 40},
                      {"tier": 2, "range_min": 13.83, "range_max": 20, "nominal": 16}])


async def test_version_collision_is_409(client, admin_headers):
    cv = await _cultivar(client, admin_headers, code="DUP", name="Dup")
    await _ladder(client, admin_headers, cv["id"], version="v1")
    body = {"cultivar_id": cv["id"], "version": "v1", "floor_pct": 13.83,
            "n_batches": 4, "ranges": GRAPE_PIE}
    r = await client.post("/qc/potency-specs", json=body, headers=admin_headers)
    assert r.status_code == 409, r.text


async def test_role_gating(client, admin_headers):
    cv = await _cultivar(client, admin_headers, code="ROLE", name="Role")
    # base USER: no read
    _, user_h = await _actor(client, admin_headers, "USER")
    assert (await client.get("/qc/potency-specs", headers=user_h)).status_code == 403
    # QC_MGR: reads AND writes (owns the domain)
    _, qc_h = await _actor(client, admin_headers, "QC_MGR")
    assert (await client.get("/qc/potency-specs", headers=qc_h)).status_code == 200
    r = await client.post("/qc/potency-specs",
                          json={"cultivar_id": cv["id"], "version": "vqc", "floor_pct": 13.83,
                                "n_batches": 4, "ranges": GRAPE_PIE}, headers=qc_h)
    assert r.status_code == 201, r.text
    # a non-QC manager (CU_MGR) may READ (elevated) but NOT write
    _, cu_h = await _actor(client, admin_headers, "CU_MGR")
    assert (await client.get("/qc/potency-specs", headers=cu_h)).status_code == 200
    r = await client.post("/qc/potency-specs",
                          json={"cultivar_id": cv["id"], "version": "vcu", "floor_pct": 13.83,
                                "n_batches": 4, "ranges": GRAPE_PIE}, headers=cu_h)
    assert r.status_code == 403


async def test_approval_requires_a_different_person(client, admin_headers):
    """Segregation of duties: the author cannot approve their own ladder."""
    cv = await _cultivar(client, admin_headers, code="SOD", name="Segregation")
    _, qc1 = await _actor(client, admin_headers, "QC_MGR")
    spec = await _ladder(client, qc1, cv["id"])
    # author (qc1) tries to approve → 403
    r = await client.post(f"/qc/potency-specs/{spec['id']}/approve", headers=qc1)
    assert r.status_code == 403, r.text
    assert "segregation of duties" in r.text.lower()
    # a different QC person approves → 200
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/potency-specs/{spec['id']}/approve", headers=qc2)
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["status"] == "APPROVED"
    assert approved["approved_by"] is not None
    assert approved["effective_date"] is not None
    # re-approving an already-APPROVED ladder → 409
    r = await client.post(f"/qc/potency-specs/{spec['id']}/approve", headers=admin_headers)
    assert r.status_code == 409


async def test_one_approved_per_cultivar_supersedes_prior(client, admin_headers):
    cv = await _cultivar(client, admin_headers, code="SUP", name="Supersede")
    _, qc1 = await _actor(client, admin_headers, "QC_MGR")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    v1 = await _ladder(client, qc1, cv["id"], version="v1")
    r = await client.post(f"/qc/potency-specs/{v1['id']}/approve", headers=qc2)
    assert r.status_code == 200
    # Author + approve a second ladder for the SAME cultivar.
    v2 = await _ladder(client, qc1, cv["id"], version="v2")
    r = await client.post(f"/qc/potency-specs/{v2['id']}/approve", headers=qc2)
    assert r.status_code == 200, r.text
    # v1 must have been auto-superseded; only v2 is APPROVED.
    r = await client.get(f"/qc/potency-specs?cultivar_id={cv['id']}", headers=admin_headers)
    by_id = {s["id"]: s for s in r.json()}
    assert by_id[v1["id"]]["status"] == "SUPERSEDED"
    assert by_id[v2["id"]]["status"] == "APPROVED"


async def test_approved_ladder_is_immutable_edit_goes_through_new_version(client, admin_headers):
    cv = await _cultivar(client, admin_headers, code="LOCK", name="Locked")
    _, qc1 = await _actor(client, admin_headers, "QC_MGR")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    spec = await _ladder(client, qc1, cv["id"])
    # DRAFT is editable — bump observed_max.
    r = await client.patch(f"/qc/potency-specs/{spec['id']}", json={"observed_max": 29.5},
                           headers=qc1)
    assert r.status_code == 200 and r.json()["observed_max"] == 29.5
    # Approve, then any edit must be refused.
    assert (await client.post(f"/qc/potency-specs/{spec['id']}/approve", headers=qc2)).status_code == 200
    r = await client.patch(f"/qc/potency-specs/{spec['id']}", json={"notes": "late"}, headers=qc1)
    assert r.status_code == 409, r.text


async def test_patch_ranges_revalidates(client, admin_headers):
    cv = await _cultivar(client, admin_headers, code="PR", name="PatchRanges")
    spec = await _ladder(client, admin_headers, cv["id"])
    # Replacing the ladder with a broken (non-meeting) one is rejected.
    r = await client.patch(f"/qc/potency-specs/{spec['id']}",
                           json={"ranges": [{"tier": 1, "range_min": 24, "range_max": 30, "nominal": 27},
                                            {"tier": 2, "range_min": 13.83, "range_max": 22, "nominal": 18}]},
                           headers=admin_headers)
    assert r.status_code == 422
    # A valid 2-tier replacement is accepted and stored.
    r = await client.patch(f"/qc/potency-specs/{spec['id']}",
                           json={"ranges": [{"tier": 1, "range_min": 20, "range_max": 30, "nominal": 25},
                                            {"tier": 2, "range_min": 13.83, "range_max": 20, "nominal": 17}]},
                           headers=admin_headers)
    assert r.status_code == 200, r.text
    r = await client.get(f"/qc/potency-specs/{spec['id']}", headers=admin_headers)
    assert [x["tier"] for x in r.json()["ranges"]] == [1, 2]


async def test_disposition_reads_the_approved_ladder(client, admin_headers):
    cv = await _cultivar(client, admin_headers, code="DISP", name="Disposition")
    _, qc1 = await _actor(client, admin_headers, "QC_MGR")
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    spec = await _ladder(client, qc1, cv["id"])

    # No APPROVED ladder yet → approved:false
    r = await client.get("/qc/potency-disposition",
                         params={"cultivar_id": cv["id"], "total_d9_thc": 24.0}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["approved"] is False

    assert (await client.post(f"/qc/potency-specs/{spec['id']}/approve", headers=qc2)).status_code == 200

    async def disp(v):
        r = await client.get("/qc/potency-disposition",
                             params={"cultivar_id": cv["id"], "total_d9_thc": v}, headers=admin_headers)
        assert r.status_code == 200, r.text
        return r.json()

    d = await disp(29.0)
    assert d["approved"] is True and d["below_spec"] is False
    assert d["disposition"]["spec"] == "Spec I" and d["disposition"]["nominal"] == 28.0
    # boundary 26.00 belongs to the UPPER tier (Spec I)
    assert (await disp(26.0))["disposition"]["spec"] == "Spec I"
    assert (await disp(25.9))["disposition"]["spec"] == "Spec II"
    assert (await disp(13.83))["disposition"]["spec"] == "Spec IV"
    # below the floor → below spec, no tier
    below = await disp(13.0)
    assert below["below_spec"] is True and below["disposition"] is None
