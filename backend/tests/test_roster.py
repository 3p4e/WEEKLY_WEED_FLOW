"""Wave 3 audit (Low, roster.py:13-21 pre-Wave-1 lines — "org roster re-fetched
with no caching on every call, a scaling watch-point"): pins the short-TTL
org-scoped in-process cache added in response. Every call site uses roster()
purely to resolve ids to display names, never for an authorization decision —
see app/roster.py's module comment for the full reasoning on why a few
seconds of staleness is safe here and a real invalidation scheme was not
worth building for this."""
import uuid

import app.roster as roster_mod
from app.db import users_admin_pool
from app.roster import roster
from tests.conftest import purge_org


async def test_roster_is_cached_within_ttl(org):
    """A same-TTL-window call must be served from the cache, not a fresh
    query — proved by inserting a profile directly (bypassing roster()
    entirely) and confirming it is invisible until the cache is cleared."""
    roster_mod._cache.clear()
    actor = {"id": org["admin_id"], "org_id": org["org_id"], "role": "ADMIN"}
    first = await roster(actor)
    assert org["admin_id"] in first

    new_id = uuid.uuid4()
    await users_admin_pool().execute(
        "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role,"
        " must_change_password) VALUES ($1,$2,$3,'x','Cache Test','USER',false)",
        new_id, org["org_id"], f"cachetest_{uuid.uuid4().hex[:8]}")

    second = await roster(actor)
    assert str(new_id) not in second, "a fresh cache hit must not re-query the DB"

    # Expiry (without sleeping out the real TTL) makes the new profile visible
    # — the cache does not pin data forever, it just smooths a short window.
    roster_mod._cache.clear()
    third = await roster(actor)
    assert str(new_id) in third


async def test_roster_cache_is_org_scoped(org):
    """One org's cached roster must never answer another org's lookup."""
    roster_mod._cache.clear()
    org2_id = uuid.uuid4()
    admin2_id = uuid.uuid4()
    suffix = uuid.uuid4().hex[:8]
    await users_admin_pool().execute(
        "INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
        org2_id, f"Test Org {suffix}", f"test-{suffix}")
    await users_admin_pool().execute(
        "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role,"
        " must_change_password) VALUES ($1,$2,$3,'x','Admin Two','ADMIN',false)",
        admin2_id, org2_id, f"admin2_{suffix}")
    try:
        actor1 = {"id": org["admin_id"], "org_id": org["org_id"], "role": "ADMIN"}
        actor2 = {"id": str(admin2_id), "org_id": str(org2_id), "role": "ADMIN"}
        r1 = await roster(actor1)
        r2 = await roster(actor2)
        assert org["admin_id"] in r1 and str(admin2_id) not in r1
        assert str(admin2_id) in r2 and org["admin_id"] not in r2
    finally:
        await purge_org(org2_id)
