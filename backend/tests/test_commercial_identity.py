"""Batch commercial identities (migration 0059) — per-batch rename/brand/label.

The Portfolio Master renames strains per BATCH (same original → different
commercial names on different batches). The table is keyed by the free-text
batch code QC rows carry; the CoQ detail surfaces the identity read-only and
never lets it alter certificate content.
"""
from tests.conftest import create_user, login_and_set_password, purge_org


async def _actor(client, admin_headers, role):
    user, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, user["username"], otp)
    return user, {"Authorization": f"Bearer {token}"}


async def test_upsert_list_delete(client, admin_headers):
    body = {"tranche": 1, "original_name": "Cap Junkie", "neu_name": "Cookie Kush",
            "brand": "CAYN", "final_label": "CAYN CK XY/1", "thc_declared": 20.29,
            "thc_bracket": "19–22%", "volume_kg": 64.53}
    r = await client.put("/qc/commercial-identities/CJ052501%2F01", json=body,
                         headers=admin_headers)
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["batch_code"] == "CJ052501/01" and row["neu_name"] == "Cookie Kush"

    # upsert updates in place — same batch, new label
    body["final_label"] = "CAYN CK XY/2"
    r = await client.put("/qc/commercial-identities/CJ052501%2F01", json=body,
                         headers=admin_headers)
    assert r.status_code == 200 and r.json()["final_label"] == "CAYN CK XY/2"
    rows = (await client.get("/qc/commercial-identities", headers=admin_headers)).json()
    assert len(rows) == 1

    # filters
    rows = (await client.get("/qc/commercial-identities?brand=CAYN",
                             headers=admin_headers)).json()
    assert len(rows) == 1
    rows = (await client.get("/qc/commercial-identities?brand=STEADY",
                             headers=admin_headers)).json()
    assert rows == []

    r = await client.delete("/qc/commercial-identities/CJ052501%2F01", headers=admin_headers)
    assert r.status_code == 200
    r = await client.delete("/qc/commercial-identities/CJ052501%2F01", headers=admin_headers)
    assert r.status_code == 404


async def test_same_original_different_neu_per_batch(client, admin_headers):
    """The defining property of the model: renames are per batch, not per strain."""
    for batch, neu in (("CJ052501%2F01", "Cookie Kush"), ("CJ062501%2F2", "OG Banana's")):
        r = await client.put(f"/qc/commercial-identities/{batch}",
                             json={"original_name": "Cap Junkie", "neu_name": neu},
                             headers=admin_headers)
        assert r.status_code == 200, r.text
    rows = (await client.get("/qc/commercial-identities", headers=admin_headers)).json()
    assert {r["neu_name"] for r in rows} == {"Cookie Kush", "OG Banana's"}
    assert all(r["original_name"] == "Cap Junkie" for r in rows)


async def test_portfolio_import_is_idempotent(client, admin_headers):
    r = await client.post("/qc/commercial-identities/import", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 78
    # re-run refreshes, never duplicates
    r = await client.post("/qc/commercial-identities/import", headers=admin_headers)
    assert r.json()["imported"] == 78
    rows = (await client.get("/qc/commercial-identities", headers=admin_headers)).json()
    assert len(rows) == 78
    # THC arrives as percent, converted from the sheet's fraction
    bg = next(x for x in rows if x["batch_code"] == "BG1024")
    assert bg["thc_declared"] == 21.8 and bg["thc_bracket"] == "19–22%"
    assert bg["neu_name"] == "Blue Gelato" and bg["brand"] == "STEADY"
    # tranche filter
    t3 = (await client.get("/qc/commercial-identities?tranche=3",
                           headers=admin_headers)).json()
    assert len(t3) == 28   # tranche counts: T1=21, T2=29, T3=28


async def test_role_gates(client, admin_headers):
    _, user_h = await _actor(client, admin_headers, "USER")
    assert (await client.get("/qc/commercial-identities", headers=user_h)).status_code == 403
    _, cu = await _actor(client, admin_headers, "CU_MGR")
    # elevated read OK, write refused
    assert (await client.get("/qc/commercial-identities", headers=cu)).status_code == 200
    r = await client.put("/qc/commercial-identities/X1", json={"neu_name": "Y"}, headers=cu)
    assert r.status_code == 403
    r = await client.post("/qc/commercial-identities/import", headers=cu)
    assert r.status_code == 403


async def test_rls_isolation_between_orgs(client, admin_headers):
    """Org B must never see org A's identities (RLS org_isolation)."""
    import uuid as _uuid
    from app.db import users_admin_pool
    from app.security import hash_password
    org_b, admin_b = _uuid.uuid4(), _uuid.uuid4()
    suffix = _uuid.uuid4().hex[:8]
    pool = users_admin_pool()
    await pool.execute("INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
                       org_b, f"Other {suffix}", f"other-{suffix}")
    await pool.execute(
        "INSERT INTO profiles(id, org_id, username, email, password_hash, full_name, role,"
        " must_change_password) VALUES ($1,$2,$3,$4,$5,'B Admin','ADMIN',false)",
        admin_b, org_b, f"admin_{suffix}", f"admin_{suffix}@test.invalid",
        hash_password("TestPassword123456"))
    try:
        r = await client.post("/auth/login", json={"email": f"admin_{suffix}",
                                                   "password": "TestPassword123456"})
        hb = {"Authorization": f"Bearer {r.json()['access_token']}"}
        assert (await client.put("/qc/commercial-identities/SECRET-A",
                                 json={"neu_name": "Org A Name"},
                                 headers=admin_headers)).status_code == 200
        rows_b = (await client.get("/qc/commercial-identities", headers=hb)).json()
        assert rows_b == []
    finally:
        await purge_org(org_b)


async def test_coq_detail_surfaces_commercial_identity(client, admin_headers, monkeypatch):
    """A CoQ whose batch code has a commercial identity carries it read-only in
    the detail; a batch without one carries null — never fabricated."""
    from tests.test_qc import _released_coa, _actor as _qc_actor
    _, qp = await _qc_actor(client, admin_headers, "QP")
    coa = await _released_coa(client, admin_headers, qp, material="COMM-MAT",
                              batch="GP0824_02")
    r = await client.post("/qc/coq", json={"batch_id": "GP0824_02",
                                           "specification_id": coa["specification_id"]},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    coq_id = r.json()["id"]
    # no identity yet → null
    d = (await client.get(f"/qc/coq/{coq_id}", headers=admin_headers)).json()
    assert d["commercial"] is None
    # add the identity → surfaces
    assert (await client.put("/qc/commercial-identities/GP0824_02",
                             json={"neu_name": "Grape Pie", "brand": "STEADY",
                                   "final_label": "STEADY GP XY/1", "tranche": 1,
                                   "thc_bracket": "22–25%"},
                             headers=admin_headers)).status_code == 200
    d = (await client.get(f"/qc/coq/{coq_id}", headers=admin_headers)).json()
    assert d["commercial"]["neu_name"] == "Grape Pie"
    assert d["commercial"]["brand"] == "STEADY"
