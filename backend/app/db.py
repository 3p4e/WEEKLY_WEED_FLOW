"""
asyncpg connection pools + RLS context — over TWO databases.

Identity data (organizations, profiles, password_reset_codes + their audit
chain) lives in the users database; all work data (tasks, sessions, pins,
their audit chain, ...) lives in the tasks database. They run as separate
Postgres containers; nothing joins across them at the SQL level — app-side
merges go through app/roster.py.

Each database is reached through two roles:
  • *_user_pool  → app_user  (NOBYPASSRLS) for request-scoped data access
  • *_admin_pool → app_admin (BYPASSRLS)  for auth lookups + provisioning

`rls(user)` (tasks DB) / `rls_users(user)` (users DB) open a transaction and
stamp the per-request identity GUCs (app.user_id / app.org_id / app.role)
with set_config(..., is_local=true), so RLS policies and the audit trigger
see the caller. SET LOCAL is transaction scoped → pool-safe (never leaks
across requests on a shared connection).
"""
import json
from contextlib import asynccontextmanager

import asyncpg

from app.config import settings

_pools: dict[str, asyncpg.Pool] = {}


async def _init_connection(conn: asyncpg.Connection) -> None:
    # asyncpg returns jsonb columns as raw text by default; every jsonb
    # column (audit_log.old_values/new_values, ai_agent_bindings.config,
    # tasks.recurrence) should come back as real JSON to callers, not a
    # string they then have to know to parse themselves.
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text")


async def init_pools() -> None:
    # If a later pool fails to connect (DB unreachable mid-startup-retry), the
    # earlier ones already created must be closed before re-raising — leaving
    # them in `_pools` with nothing referencing them once a caller retries
    # (each key gets silently overwritten) leaks their live connections.
    try:
        _pools["users_user"] = await asyncpg.create_pool(
            settings.users_database_url, min_size=1, max_size=5, init=_init_connection)
        _pools["users_admin"] = await asyncpg.create_pool(
            settings.users_admin_database_url, min_size=1, max_size=5, init=_init_connection)
        _pools["tasks_user"] = await asyncpg.create_pool(
            settings.tasks_database_url, min_size=2, max_size=10, init=_init_connection)
        _pools["tasks_admin"] = await asyncpg.create_pool(
            settings.tasks_admin_database_url, min_size=1, max_size=5, init=_init_connection)
    except Exception:
        await close_pools()
        raise


async def close_pools() -> None:
    for p in _pools.values():
        await p.close()
    _pools.clear()


def users_user_pool() -> asyncpg.Pool:
    return _pools["users_user"]


def users_admin_pool() -> asyncpg.Pool:
    return _pools["users_admin"]


def tasks_user_pool() -> asyncpg.Pool:
    return _pools["tasks_user"]


def tasks_admin_pool() -> asyncpg.Pool:
    return _pools["tasks_admin"]


@asynccontextmanager
async def _guc_conn(pool: asyncpg.Pool, user):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.user_id',$1,true),"
                "       set_config('app.org_id',$2,true),"
                "       set_config('app.role',$3,true)",
                str(user["id"]), str(user["org_id"]), user["role"],
            )
            yield conn


def rls(user, *, admin: bool = False):
    """Transactional TASKS-DB connection with identity GUCs set for RLS + audit.

    `user` is the dict from get_current_user (id, org_id, role). Pass admin=True
    to use the BYPASSRLS pool while still stamping the actor so the audit
    trigger attributes the action correctly.
    """
    return _guc_conn(_pools["tasks_admin"] if admin else _pools["tasks_user"], user)


def rls_users(user, *, admin: bool = False):
    """Same as rls() but against the USERS database (profiles etc.)."""
    return _guc_conn(_pools["users_admin"] if admin else _pools["users_user"], user)
