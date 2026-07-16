"""
asyncpg connection pools + RLS context.

Two pools mirror the two Postgres roles:
  • user_pool  → app_user  (NOBYPASSRLS) for request-scoped data access
  • admin_pool → app_admin (BYPASSRLS)  for auth lookups + provisioning

`rls(conn_user)` opens a transaction and stamps the per-request identity GUCs
(app.user_id / app.org_id / app.role) with set_config(..., is_local=true), so
RLS policies and the audit trigger see the caller. SET LOCAL is transaction
scoped → pool-safe (never leaks across requests on a shared connection).
"""
from contextlib import asynccontextmanager

import asyncpg

from app.config import settings

_pools: dict[str, asyncpg.Pool] = {}


async def init_pools() -> None:
    _pools["user"] = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    _pools["admin"] = await asyncpg.create_pool(settings.admin_database_url, min_size=1, max_size=5)


async def close_pools() -> None:
    for p in _pools.values():
        await p.close()
    _pools.clear()


def admin_pool() -> asyncpg.Pool:
    return _pools["admin"]


def user_pool() -> asyncpg.Pool:
    return _pools["user"]


@asynccontextmanager
async def rls(user, *, admin: bool = False):
    """Transactional connection with identity GUCs set for RLS + audit.

    `user` is the dict from get_current_user (id, org_id, role). Pass admin=True
    to use the BYPASSRLS pool (provisioning) while still stamping the actor so
    the audit trigger attributes the action correctly.
    """
    pool = _pools["admin"] if admin else _pools["user"]
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.user_id',$1,true),"
                "       set_config('app.org_id',$2,true),"
                "       set_config('app.role',$3,true)",
                str(user["id"]), str(user["org_id"]), user["role"],
            )
            yield conn
