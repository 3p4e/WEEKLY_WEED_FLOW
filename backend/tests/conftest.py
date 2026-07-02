"""Shared fixtures.

Runs against a real Postgres database (RLS is the app's actual security
model — it can't be meaningfully exercised against a mock or SQLite). Each
test that needs data gets its own fresh organization via the `org` fixture;
deleting that org at teardown cascades to every row it owns, so tests never
share or leak state despite running against one shared database.

Requires DATABASE_URL / ADMIN_DATABASE_URL to point at a real (test-only!)
Postgres database with schema.sql already loaded — see
backend/scripts/load_schema.sh and backend/README.md.
"""
import os
import uuid

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "pytest-test-secret-not-for-production")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import admin_pool, close_pools, init_pools
from app.security import hash_password


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _pools():
    await init_pools()
    yield
    await close_pools()


@pytest_asyncio.fixture
async def client():
    from app.main import app as fastapi_app
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def org():
    """A fresh org + one ADMIN profile with a known password (must_change_password
    already cleared). This app has no self-signup — the very first admin in any
    org is always seeded directly, same as this fixture does."""
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    suffix = uuid.uuid4().hex[:8]
    username = f"admin_{suffix}"
    email = f"admin_{suffix}@test.invalid"
    password = "TestPassword123456"
    pool = admin_pool()
    await pool.execute(
        "INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
        org_id, f"Test Org {suffix}", f"test-{suffix}")
    await pool.execute(
        "INSERT INTO profiles(id, org_id, username, email, password_hash, full_name, role, must_change_password)"
        " VALUES ($1,$2,$3,$4,$5,$6,'ADMIN',false)",
        admin_id, org_id, username, email, hash_password(password), "Test Admin")
    yield {
        "org_id": str(org_id), "admin_id": str(admin_id),
        "username": username, "email": email, "password": password,
    }
    await pool.execute("DELETE FROM organizations WHERE id=$1", org_id)  # cascades everywhere


@pytest_asyncio.fixture
async def admin_token(client, org):
    r = await client.post("/auth/login", json={"email": org["username"], "password": org["password"]})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


async def create_user(client, admin_headers, *, role="USER", full_name="Test User"):
    """Provision a user via the real API (as an admin would) and return
    (profile, otp) — the OTP is a real one-time password from a real
    /auth/users call, not a shortcut."""
    r = await client.post("/auth/users", json={
        "username": f"user_{uuid.uuid4().hex[:8]}", "full_name": full_name, "role": role,
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    return body["user"], body["otp"]


async def login_and_set_password(client, username, otp, new_password="NewPassword123456"):
    """First-login flow: OTP login -> forced change-password -> real session."""
    r = await client.post("/auth/login", json={"email": username, "password": otp})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["must_change_password"] is True
    tmp_token = r.json()["access_token"]
    r = await client.post("/auth/change-password", json={"new_password": new_password},
                           headers={"Authorization": f"Bearer {tmp_token}"})
    assert r.status_code == 200, r.text
    r = await client.post("/auth/login", json={"email": username, "password": new_password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
