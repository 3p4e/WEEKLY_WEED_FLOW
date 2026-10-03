"""users migration 0013 — profiles carries no write policy on the user pool.

RLS is the security boundary this codebase claims; on `profiles` it was not
one (APP-REVIEW-2026-07-14 L7, review 2026-09-27 BC-21): `profiles_manage`
let any elevated role write any profile in the org through the app_user
pool, role included, and `profiles_self` let anyone update every column of
their own row — `role` too. Nothing was exploitable only because every
profile write goes through the admin pool behind auth._can_manage. Both
policies are gone: app_user reads the org's profiles and writes nothing.
"""
from app.db import rls_users, users_admin_pool
from tests.conftest import create_user, login_and_set_password


async def test_user_pool_cannot_promote_itself_or_edit_a_colleague(client, admin_headers, org):
    op, otp = await create_user(client, admin_headers, role="USER", full_name="Self Promoter")
    await login_and_set_password(client, op["username"], otp)
    mgr, motp = await create_user(client, admin_headers, role="QC_MGR", full_name="Other Manager")
    await login_and_set_password(client, mgr["username"], motp)
    me = {"id": op["id"], "org_id": org["org_id"], "role": "USER"}
    manager = {"id": mgr["id"], "org_id": org["org_id"], "role": "QC_MGR"}

    # a user's own row: no self-update policy any more
    async with rls_users(me) as c:
        tag = await c.execute("UPDATE profiles SET role='ADMIN' WHERE id=$1", op["id"])
    assert tag == "UPDATE 0", tag
    # an elevated role: no org-wide write policy any more
    async with rls_users(manager) as c:
        tag = await c.execute("UPDATE profiles SET role='USER', is_active=false WHERE id=$1", op["id"])
        deleted = await c.execute("DELETE FROM profiles WHERE id=$1", op["id"])
    assert tag == "UPDATE 0" and deleted == "DELETE 0", (tag, deleted)
    # reads are untouched: the roster and the directory need them
    async with rls_users(me) as c:
        assert await c.fetchval("SELECT count(*) FROM profiles WHERE org_id=$1", org["org_id"]) >= 3

    row = await users_admin_pool().fetchrow("SELECT role, is_active FROM profiles WHERE id=$1", op["id"])
    assert row["role"] == "USER" and row["is_active"] is True


async def test_profiles_has_exactly_the_read_policy():
    """Pinned by name so a policy re-added by hand (or a downgrade that was
    never re-upgraded) is a red test, not a silent widening."""
    names = {r["polname"] for r in await users_admin_pool().fetch(
        "SELECT polname FROM pg_policy WHERE polrelid='public.profiles'::regclass")}
    assert names == {"profiles_read"}, names
