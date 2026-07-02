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
