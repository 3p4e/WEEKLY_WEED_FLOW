"""Regression tests for the 2026-07-12 audit-response hardening.

Pins: PyJWT migration behaviour (garbage/expired tokens still map to clean
401s), the count-every-call throttle on authenticated auth mutations, days[]
token validation, and the new max_length input bounds.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings


@pytest.mark.asyncio
async def test_garbage_and_expired_tokens_are_clean_401s(client):
    # Not-a-JWT at all
    r = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401
    # Structurally valid but signed with the wrong key
    forged = jwt.encode({"sub": "x", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                        "wrong-key", algorithm=settings.algorithm)
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
    # Correct key but expired
    expired = jwt.encode({"sub": "x", "role": "ADMIN", "org_id": "x", "pwv": None,
                          "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
                         settings.secret_key, algorithm=settings.algorithm)
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_change_password_is_throttled(client, admin_headers, org):
    # Too-short password fails BEFORE bcrypt (422), so each attempt is cheap —
    # but every call still counts against the throttle. 20 allowed, 21st → 429.
    for _ in range(20):
        r = await client.post("/auth/change-password", json={"new_password": "x"}, headers=admin_headers)
        assert r.status_code in (401, 422)
    r = await client.post("/auth/change-password", json={"new_password": "x"}, headers=admin_headers)
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_create_user_is_throttled(client, admin_headers, org):
    # Invalid role fails cheaply after the throttle records the call.
    for _ in range(20):
        r = await client.post("/auth/users", json={"username": "u", "full_name": "U",
                                                   "role": "NOT_A_ROLE"}, headers=admin_headers)
        assert r.status_code == 422
    r = await client.post("/auth/users", json={"username": "u", "full_name": "U",
                                               "role": "NOT_A_ROLE"}, headers=admin_headers)
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_days_tokens_validated_on_create_and_patch(client, admin_headers, org):
    r = await client.post("/tasks", json={"title": "bad days", "days": ["Monday"]}, headers=admin_headers)
    assert r.status_code == 422
    r = await client.post("/tasks", json={"title": "good days", "days": ["Mon", "Fri"]}, headers=admin_headers)
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["days"] == ["Mon", "Fri"]
    r = await client.patch(f"/tasks/{task['id']}", json={"days": ["Funday"]}, headers=admin_headers)
    assert r.status_code == 422
    r = await client.patch(f"/tasks/{task['id']}", json={"days": ["Sat"]}, headers=admin_headers)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_string_inputs_are_bounded(client, admin_headers, org):
    r = await client.post("/tasks", json={"title": "x" * 301}, headers=admin_headers)
    assert r.status_code == 422
    r = await client.post("/auth/users", json={"username": "u" * 65, "full_name": "U",
                                               "role": "USER"}, headers=admin_headers)
    assert r.status_code == 422
    r = await client.post("/auth/login", json={"email": "whoever", "password": "p" * 257})
    assert r.status_code == 422
