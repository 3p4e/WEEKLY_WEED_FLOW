"""P0 — does the app come up and can anyone log in at all."""


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
