"""P0 — does the app come up and can anyone log in at all."""
import logging


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


async def test_login_by_username(client, org):
    r = await client.post("/auth/login", json={"email": org["username"], "password": org["password"]})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["username"] == org["username"]


async def test_login_by_email(client, org):
    r = await client.post("/auth/login", json={"email": org["email"], "password": org["password"]})
    assert r.status_code == 200, r.text


async def test_login_wrong_password(client, org):
    r = await client.post("/auth/login", json={"email": org["username"], "password": "wrong-password"})
    assert r.status_code == 401


async def test_login_unknown_user(client):
    r = await client.post("/auth/login", json={"email": "nobody-such-user", "password": "whatever"})
    assert r.status_code == 401


async def test_authenticated_endpoint_requires_token(client):
    r = await client.get("/tasks")
    assert r.status_code in (401, 403)


async def test_bad_token_rejected(client):
    r = await client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


async def test_oversized_request_body_is_rejected(client, monkeypatch):
    """M9 — a request whose declared Content-Length exceeds the ceiling is
    rejected (413) up front, before Starlette buffers the body into memory; a body
    under the ceiling passes the guard untouched. The ceiling is patched low here
    so the test needn't allocate the real 32 MB bound."""
    import app.main as _main
    monkeypatch.setattr(_main, "_MAX_REQUEST_BYTES", 100)
    # a body over the (patched) ceiling → 413 from the guard, before routing/parsing
    r = await client.post("/auth/login", content="x" * 200,
                          headers={"content-type": "application/json"})
    assert r.status_code == 413 and "too large" in r.json()["detail"]
    # a small body is unaffected (reaches the handler and fails auth, never 413)
    r = await client.post("/auth/login", json={"email": "nobody", "password": "x"})
    assert r.status_code != 413


async def test_chunked_oversized_request_body_is_rejected(client, monkeypatch):
    """M9 backstop — a body sent with NO Content-Length header (as with real
    `Transfer-Encoding: chunked` traffic) skips the fast Content-Length check
    in test_oversized_request_body_is_rejected entirely, so it must still be
    caught by the byte-counting fallback that reads request.stream() with a
    running total. httpx can't know a generator's length up front, so it
    omits Content-Length and sends `Transfer-Encoding: chunked` instead —
    reproducing that exact gap without needing a literal chunked-encoded wire
    request (ASGI has no wire framing to simulate one against)."""
    import app.main as _main
    monkeypatch.setattr(_main, "_MAX_REQUEST_BYTES", 100)

    async def oversized_body():
        for _ in range(30):
            yield b"x" * 10   # 300 bytes total, over the patched 100-byte cap

    req = client.build_request("POST", "/auth/login", content=oversized_body(),
                                headers={"content-type": "application/json"})
    assert "content-length" not in req.headers
    assert req.headers.get("transfer-encoding") == "chunked"
    r = await client.send(req)
    assert r.status_code == 413 and "too large" in r.json()["detail"]

    # a body under the cap, sent the same content-length-less way, is
    # unaffected: it reaches the handler and fails auth on bad credentials,
    # never 413 — proving the streamed-and-recounted body still arrives
    # intact downstream (the middleware's read doesn't swallow it).
    async def small_body():
        yield b'{"email": "nobody", "password": "x"}'

    req2 = client.build_request("POST", "/auth/login", content=small_body(),
                                 headers={"content-type": "application/json"})
    assert "content-length" not in req2.headers
    r2 = await client.send(req2)
    assert r2.status_code == 401


async def test_rejected_oversized_body_is_still_logged(client, monkeypatch, caplog):
    """Wave 3 audit (Low): limit_body_size's early-rejection responses (the
    plain Content-Length-declared-too-large 413 here — the path with NO log
    call of its own inside limit_body_size) must still produce a log line.
    They do: log_requests is registered AFTER limit_body_size, and Starlette's
    add_middleware inserts each new middleware at position 0 of the stack, so
    the LAST-registered middleware ends up OUTERMOST — log_requests wraps
    limit_body_size and logs whatever Response comes back from it, rejection
    or not. See the comments on limit_body_size/log_requests in app/main.py."""
    import app.main as _main
    monkeypatch.setattr(_main, "_MAX_REQUEST_BYTES", 100)
    caplog.set_level(logging.INFO, logger="app.request")
    r = await client.post("/auth/login", content="x" * 200,
                          headers={"content-type": "application/json"})
    assert r.status_code == 413
    matches = [rec for rec in caplog.records
              if rec.name == "app.request" and rec.message == "request"
              and getattr(rec, "fields", {}).get("status_code") == 413]
    assert matches, "the 413 rejection from limit_body_size must be logged by log_requests"
    assert matches[0].fields["path"] == "/auth/login"
    assert matches[0].fields["method"] == "POST"


async def test_token_missing_sub_claim_is_clean_401(client):
    """Wave 3 audit (Low, deps.py:25): a structurally-valid, correctly-signed
    JWT with no `sub` claim used to hit `payload["sub"]` and raise an uncaught
    KeyError, which FastAPI turns into a 500 rather than a 401. Not reachable
    via any current token-minting path (create_access_token always sets sub),
    but a latent trap for a hand-crafted or future-buggy token."""
    import jwt
    from app.config import settings
    no_sub = jwt.encode({"role": "ADMIN", "org_id": "x", "pwv": None},
                        settings.secret_key, algorithm=settings.algorithm)
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {no_sub}"})
    assert r.status_code == 401
    # A blank/falsy sub must be treated the same as a missing one.
    blank_sub = jwt.encode({"sub": "", "role": "ADMIN", "org_id": "x", "pwv": None},
                           settings.secret_key, algorithm=settings.algorithm)
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {blank_sub}"})
    assert r.status_code == 401


async def test_health_ready_round_trips_both_databases(client):
    """H12 — readiness is what a container healthcheck needs: it separates
    "process is up" (/health, which deliberately never touches the DB so a blip
    cannot take the process out of rotation) from "can actually serve". This app
    is useless without BOTH databases, so both are round-tripped and named."""
    r = await client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "healthy"
    r = await client.get("/health/ready")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    assert body["databases"] == {"users": "ok", "tasks": "ok"}
