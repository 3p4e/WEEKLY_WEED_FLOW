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
