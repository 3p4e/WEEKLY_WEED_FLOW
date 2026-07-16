"""Async SQLAlchemy engines/sessions for the centralised PostgreSQL database.

Two engines mirror the two-role RLS model (grafted from the SUMA/WWF methodology):
  • admin engine (database_url)      → owner/BYPASSRLS: login, provisioning, migrations
  • app engine   (app_database_url)  → growflow_app/NOBYPASSRLS: request-scoped data

`rls_session` (see auth_deps) opens a transaction on the app engine and stamps the
per-request identity GUCs (app.user_id / app.role) with SET LOCAL, so RLS policies
and the audit trail see the caller. SET LOCAL is transaction-scoped → pool-safe.
When app_database_url is unset, the app engine falls back to the admin engine
(RLS is still defined in the DB; the app simply connects as owner).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_app_engine: AsyncEngine | None = None
_app_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Admin/owner engine (BYPASSRLS path)."""
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def app_session_maker() -> async_sessionmaker[AsyncSession]:
    """RLS-enforced app engine; falls back to the admin engine when unconfigured."""
    global _app_engine, _app_sessionmaker
    s = get_settings()
    if not s.app_database_url:
        get_engine()
        assert _sessionmaker is not None
        return _sessionmaker
    if _app_engine is None:
        _app_engine = create_async_engine(s.app_database_url, pool_pre_ping=True)
        _app_sessionmaker = async_sessionmaker(_app_engine, expire_on_commit=False)
    assert _app_sessionmaker is not None
    return _app_sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """Admin session — login, provisioning, anything that must bypass RLS."""
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session


async def stamp_identity(session: AsyncSession, user_id: str, role: str) -> None:
    """Set session-scoped identity GUCs (survive the mid-request commits that the
    task router performs). Overwritten every request; reset on teardown."""
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, false), "
             "set_config('app.role', :role, false)"),
        {"uid": str(user_id), "role": role},
    )
    await session.commit()


async def clear_identity(session: AsyncSession) -> None:
    """Reset identity GUCs before the connection returns to the pool (no leakage)."""
    await session.execute(
        text("SELECT set_config('app.user_id', '', false), set_config('app.role', '', false)")
    )
    await session.commit()
