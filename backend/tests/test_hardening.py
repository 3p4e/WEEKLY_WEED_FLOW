"""Regression tests for the 2026-07-12 audit-response hardening.

Pins: PyJWT migration behaviour (garbage/expired tokens still map to clean
401s), the count-every-call throttle on authenticated auth mutations, days[]
token validation, and the new max_length input bounds.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def test_uvicorn_trusts_only_the_frontend_proxy_ip_not_wildcard():
    """The backend must honour X-Forwarded-For (so the login rate-limiter and
    forensic log see the real client, not the frontend container's IP), but
    trust it ONLY from the frontend's fixed IP — never '*', which would let a
    compromised sibling container (e.g. the internet-exposed capture-mcp on the
    same docker network) spoof its source IP and defeat the limiter. Pins the
    mechanism: --proxy-headers on, no wildcard in the image, and the compose
    wires a specific FORWARDED_ALLOW_IPS matching the frontend's static IP.
    The live proxy chain itself can't be exercised from a plain TestClient."""
    root = Path(__file__).parent.parent.parent
    dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
    # Check the actual CMD line, not the explanatory comments (which name the
    # wildcard on purpose to say why it's avoided).
    cmd_line = next((ln for ln in dockerfile.splitlines()
                     if ln.strip().startswith("CMD") and "uvicorn" in ln), "")
    assert "--proxy-headers" in cmd_line
    assert "--forwarded-allow-ips=*" not in cmd_line, "wildcard XFF trust is spoofable"

    compose = (root / "docker-compose.yml").read_text()
    import re
    m = re.search(r"FORWARDED_ALLOW_IPS=(\d+\.\d+\.\d+\.\d+)", compose)
    assert m, "compose must set FORWARDED_ALLOW_IPS to a specific frontend IP"
    trusted_ip = m.group(1)
    assert trusted_ip != "0.0.0.0"
    # the frontend must actually hold that IP statically, or the trust is dead
    assert f"ipv4_address: {trusted_ip}" in compose, \
        "frontend must have the static ipv4_address the backend trusts"
