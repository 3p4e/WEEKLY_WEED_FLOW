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

    # Review 2026-09-27, BC-01: the chain is client -> Traefik -> nginx ->
    # uvicorn, and uvicorn takes the RIGHTMOST forwarded address it does not
    # trust. nginx appending its own peer (Traefik) with
    # $proxy_add_x_forwarded_for therefore resolved every client to Traefik
    # and collapsed the per-IP limiter into one facility-wide bucket.
    #
    # R2-BC-03: the first fix trusted the header by the INTERFACE a request
    # arrived on, which every container on traefik_network can also reach.
    # Trust is now keyed on Traefik itself: the realip module rewrites
    # $remote_addr from X-Forwarded-For only when the direct peer is in
    # set_real_ip_from, and those lines are written at start from the
    # resolved Traefik container address (web/docker-entrypoint.d/
    # 05-wwf-realip.sh) — never a hard-coded subnet in nginx.conf. Every
    # proxied location forwards exactly one address, $remote_addr.
    nginx_conf = (root / "web" / "nginx.conf").read_text()
    directives = [ln for ln in nginx_conf.splitlines() if not ln.strip().startswith("#")]
    body = "\n".join(directives)
    assert "$proxy_add_x_forwarded_for" not in body, \
        "nginx must not append its own peer to X-Forwarded-For — that peer is Traefik"
    assert "$http_x_forwarded_for" not in body and "$wwf_client_xff" not in body, \
        "the raw X-Forwarded-For header must never be forwarded — trust is decided by realip"
    xff_lines = [ln for ln in directives if "X-Forwarded-For" in ln and "proxy_set_header" in ln]
    assert xff_lines and all(ln.split()[-1] == "$remote_addr;" for ln in xff_lines), \
        "every proxied location must forward the realip-resolved $remote_addr and nothing else"
    assert re.search(r"^\s*real_ip_header\s+X-Forwarded-For;", body, re.M)
    assert re.search(r"^\s*real_ip_recursive\s+on;", body, re.M)
    assert re.search(r"^\s*include\s+/etc/nginx/wwf-realip\.d/\*\.conf;", body, re.M), \
        "the trusted-proxy list is the snippet the entrypoint hook writes, included by wildcard"
    assert "set_real_ip_from" not in body, \
        "no hard-coded trusted proxy in nginx.conf: a subnet would trust every container on it"
    assert "map $server_addr" not in body, "interface-based trust is the R2-BC-03 hole"
    # the hook: shipped by the Dockerfile into /docker-entrypoint.d, resolves a
    # NAME (never a range) and writes set_real_ip_from lines; trusts nobody
    # when the name does not resolve
    hook = (root / "web" / "docker-entrypoint.d" / "05-wwf-realip.sh").read_text()
    assert "set_real_ip_from" in hook and "getent" in hook and "WWF_TRAEFIK_HOST" in hook
    assert "NO proxy is trusted" in hook, "the fail-safe direction must be loud"
    assert "0.0.0.0/0" not in hook
    web_dockerfile = (root / "web" / "Dockerfile").read_text()
    assert "docker-entrypoint.d/05-wwf-realip.sh /docker-entrypoint.d/05-wwf-realip.sh" in web_dockerfile
    assert "mkdir -p /etc/nginx/wwf-realip.d" in web_dockerfile
    # compose names the Traefik container for the hook (TRAEFIK_HOST, .env)
    assert re.search(r"WWF_TRAEFIK_HOST=\$\{TRAEFIK_HOST", compose), \
        "the frontend service must pass the Traefik container name to the hook"
    assert "TRAEFIK_HOST=" in (root / ".env.example").read_text()
    # R2-BC-09: the retired /qms/rag-query route must not linger in the
    # slow-path location (web/gf/api.js mirrors this list as _SLOW_PATHS)
    assert "rag-query" not in body, "/qms/rag-query was retired with the qms-api proxy (BC-19)"
