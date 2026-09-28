"""P1 — /auth/login rate limiting. There is no other brute-force protection,
so this is the only thing standing between an attacker and unlimited
password guesses against a real account."""
from app.api.auth import _LOGIN_MAX_ATTEMPTS_PER_ID as _LOGIN_MAX_ATTEMPTS
from app.api.auth import _LOGIN_MAX_ATTEMPTS_PER_IP


async def test_repeated_failures_against_one_identifier_eventually_429(client, org):
    for _ in range(_LOGIN_MAX_ATTEMPTS):
        r = await client.post("/auth/login", json={"email": org["username"], "password": "wrong"})
        assert r.status_code == 401

    r = await client.post("/auth/login", json={"email": org["username"], "password": "wrong"})
    assert r.status_code == 429

    # The correct password is rejected too while rate-limited — this guards
    # the account, it doesn't just gate wrong-password responses.
    r = await client.post("/auth/login", json={"email": org["username"], "password": org["password"]})
    assert r.status_code == 429


async def test_a_different_identifier_on_the_same_ip_is_not_affected(client, org):
    """This is a single-facility app — many real staff plausibly share one
    office IP. Exhausting one account's per-identifier budget must not also
    trip the (much looser) per-IP budget, or one person's typos would lock
    out everyone else logging in from the same network."""
    for _ in range(_LOGIN_MAX_ATTEMPTS):
        r = await client.post("/auth/login", json={"email": org["username"], "password": "wrong"})
        assert r.status_code == 401
    r = await client.post("/auth/login", json={"email": org["username"], "password": "wrong"})
    assert r.status_code == 429

    r = await client.post("/auth/login", json={"email": org["username"] + "-does-not-exist", "password": "wrong"})
    assert r.status_code == 401  # not 429 — a fresh identifier has its own budget


async def test_successful_login_clears_the_failure_count(client, org):
    for _ in range(_LOGIN_MAX_ATTEMPTS - 1):
        r = await client.post("/auth/login", json={"email": org["username"], "password": "wrong"})
        assert r.status_code == 401

    r = await client.post("/auth/login", json={"email": org["username"], "password": org["password"]})
    assert r.status_code == 200

    # Budget reset — another wrong attempt right after a success is still
    # just a plain 401, not 429.
    r = await client.post("/auth/login", json={"email": org["username"], "password": "wrong"})
    assert r.status_code == 401


async def test_successful_login_does_not_clear_the_shared_ip_bucket(client, org):
    """Review 2026-09-27, BC-01: a success used to clear BOTH keys, including
    the per-IP bucket every client behind one address shares. An attacker
    spraying accounts from one address only had to log into any account they
    legitimately held (or wait for a colleague to) to reset the address's
    whole brute-force counter. The account's own budget is forgiven on a
    success; the address's is not — its failures age out with the window."""
    # One failure each across distinct identifiers, so no per-account budget
    # trips first and only the per-IP bucket accumulates.
    for i in range(_LOGIN_MAX_ATTEMPTS_PER_IP - 1):
        r = await client.post("/auth/login", json={"email": f"spray-{i}@test.invalid", "password": "wrong"})
        assert r.status_code == 401, r.text
    r = await client.post("/auth/login", json={"email": org["username"], "password": org["password"]})
    assert r.status_code == 200, r.text
    # The bucket still holds the earlier failures: one more fills it...
    r = await client.post("/auth/login", json={"email": "spray-last@test.invalid", "password": "wrong"})
    assert r.status_code == 401
    # ...and the address is now throttled, success or no success in between.
    r = await client.post("/auth/login", json={"email": "spray-after@test.invalid", "password": "wrong"})
    assert r.status_code == 429
