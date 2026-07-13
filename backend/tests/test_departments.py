"""POST /departments — ADMIN-only, idempotent department creation.

Pins: creation returns the row; re-POSTing the same code is a safe no-op
returning the existing row (the provisioning script depends on this);
managers AND executives get 403 (org structure is system administration,
not delegated provisioning); bad codes are 422.
"""
import pytest

from tests.conftest import create_user, login_and_set_password


@pytest.mark.asyncio
async def test_create_department_idempotent(client, admin_headers, org):
    r = await client.post("/departments", json={
        "code": "cultivation", "name": "Cultivation", "name_mk": "Одгледување"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["code"] == "cultivation" and first["name_mk"] == "Одгледување"

    # Re-POST: same row back, nothing duplicated, different name ignored.
    r = await client.post("/departments", json={
        "code": "cultivation", "name": "Cultivation RENAMED"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == first["id"]
    assert r.json()["name"] == "Cultivation"

    r = await client.get("/departments", headers=admin_headers)
    codes = [d["code"] for d in r.json()]
    assert codes.count("cultivation") == 1


@pytest.mark.asyncio
async def test_create_department_forbidden_for_managers_and_owner(client, admin_headers, org):
    for role in ("QC_MGR", "OWNER"):
        user, otp = await create_user(client, admin_headers, role=role, full_name=f"{role} Person")
        token = await login_and_set_password(client, user["username"], otp)
        r = await client.post("/departments", json={"code": "sneaky", "name": "Sneaky"},
                              headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403, f"{role}: {r.status_code} {r.text}"


@pytest.mark.asyncio
async def test_create_department_validates_code(client, admin_headers, org):
    for bad in ("Warehouse", "ware house", "wh-1", ""):
        r = await client.post("/departments", json={"code": bad, "name": "X"}, headers=admin_headers)
        assert r.status_code == 422, f"{bad!r} accepted"
