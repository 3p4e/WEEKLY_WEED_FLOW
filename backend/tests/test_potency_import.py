"""QCSP 001 potency-ladder catalogue import — the packaged 71-strain handoff.

The catalogue ships with the backend (app/data/imb_grade_ladders.json); the
import endpoint loads a family (or ALL) into qc_potency_specs as DRAFT rows,
auto-creating missing cultivars. Idempotent; approval stays a second-person
human act.
"""
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role):
    user, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, user["username"], otp)
    return user, {"Authorization": f"Bearer {token}"}


async def test_dry_run_reports_without_writing(client, admin_headers):
    r = await client.post("/qc/potency-specs/import",
                          json={"family": "BASE_SPCs", "dry_run": True}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    assert len(body["created"]) == 35            # the CULI-001 approved list
    assert body["conflicts"] == []
    # nothing written
    r = await client.get("/qc/potency-specs", headers=admin_headers)
    assert r.json() == []
    r = await client.get("/cultivation/cultivars", headers=admin_headers)
    assert r.json()["cultivars"] == []


async def test_import_base_family_creates_draft_ladders_and_cultivars(client, admin_headers):
    r = await client.post("/qc/potency-specs/import",
                          json={"family": "BASE_SPCs"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["created"]) == 35 and body["conflicts"] == []
    assert len(body["cultivars_created"]) == 35   # fresh org — all auto-created

    specs = (await client.get("/qc/potency-specs", headers=admin_headers)).json()
    assert len(specs) == 35
    assert all(s["status"] == "DRAFT" for s in specs)
    assert all(s["data_supported"] is False for s in specs)   # provisional
    assert all(s["variant"] == "BASE_SPCs" for s in specs)

    # Grape Pie keeps its own contiguous ladder from the handoff (not the
    # standard bracket): I 26-30 / II 22-26 / III 18-22 / IV 13.83-18.
    gp = next(s for s in specs if s["cultivar_code"] == "GP")
    assert gp["floor_pct"] == 13.83
    detail = (await client.get(f"/qc/potency-specs/{gp['id']}", headers=admin_headers)).json()
    tiers = {r["tier"]: r for r in detail["ranges"]}
    assert len(tiers) == 4
    assert tiers[1]["range_min"] == 26.0 and tiers[1]["range_max"] == 30.0
    assert tiers[3]["range_min"] == 18.0 and tiers[3]["range_max"] == 22.0
    assert tiers[3]["nominal"] == 20.0 and tiers[3]["width_pp"] == 2.0

    # Amsterdam Amnesia carries the standard bracket (0.10-pp gaps) — the
    # relaxed validator accepts it.
    aa = next(s for s in specs if s["cultivar_code"] == "AA")
    d2 = (await client.get(f"/qc/potency-specs/{aa['id']}", headers=admin_headers)).json()
    t2 = {r["tier"]: r for r in d2["ranges"]}
    assert t2[2]["range_max"] == 26.9 and t2[1]["range_min"] == 27.0


async def test_reimport_is_idempotent(client, admin_headers):
    first = (await client.post("/qc/potency-specs/import",
                               json={"family": "NEWs"}, headers=admin_headers)).json()
    assert len(first["created"]) > 0
    again = (await client.post("/qc/potency-specs/import",
                               json={"family": "NEWs"}, headers=admin_headers)).json()
    assert again["created"] == []
    assert len(again["skipped"]) == len(first["created"])
    assert all(s["reason"] == "version exists" for s in again["skipped"])


async def test_import_all_families(client, admin_headers):
    body = (await client.post("/qc/potency-specs/import",
                              json={"family": "ALL"}, headers=admin_headers)).json()
    assert len(body["created"]) == 71 and body["conflicts"] == []
    specs = (await client.get("/qc/potency-specs", headers=admin_headers)).json()
    assert len(specs) == 71


async def test_imported_ladder_needs_second_person_approval(client, admin_headers):
    """Importing never approves: the importer cannot approve what they imported
    (created_by = importer), a second QC person can."""
    _, qc1 = await _actor(client, admin_headers, "QC_MGR")
    body = (await client.post("/qc/potency-specs/import",
                              json={"family": "NEWs"}, headers=qc1)).json()
    assert len(body["created"]) > 0
    specs = (await client.get("/qc/potency-specs", headers=admin_headers)).json()
    spec = next(s for s in specs if s["variant"] == "NEWs")
    r = await client.post(f"/qc/potency-specs/{spec['id']}/approve", headers=qc1)
    assert r.status_code == 403
    _, qc2 = await _actor(client, admin_headers, "QC_MGR")
    r = await client.post(f"/qc/potency-specs/{spec['id']}/approve", headers=qc2)
    assert r.status_code == 200, r.text


async def test_import_role_gated_and_validated(client, admin_headers):
    _, cu = await _actor(client, admin_headers, "CU_MGR")
    r = await client.post("/qc/potency-specs/import", json={"family": "ALL"}, headers=cu)
    assert r.status_code == 403
    r = await client.post("/qc/potency-specs/import", json={"family": "NOPE"},
                          headers=admin_headers)
    assert r.status_code == 422
