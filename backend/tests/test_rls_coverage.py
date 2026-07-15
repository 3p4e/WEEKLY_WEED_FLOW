"""Every public table in BOTH databases must have row-level security enabled.

Postgres RLS silently exposes ALL rows on any table where RLS was never
enabled (docs: ddl-rowsecurity) — a forgotten `ENABLE ROW LEVEL SECURITY` on a
new table is the exact mechanism by which org/department scoping silently
breaks. This guard turns that failure mode into a red test the moment a
migration adds an unprotected table. (2026-07 landscape research, finding R1 —
docs/RESEARCH-LANDSCAPE-2026-07.md.)

audit_log is NOT exempt — it carries org-scoped policies (audit_read/insert).
alembic_version is bookkeeping with no org data and is the only exemption.
"""
from app.db import tasks_admin_pool, users_admin_pool

_EXEMPT = {"alembic_version"}

_Q = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity
ORDER BY c.relname
"""


async def test_every_tasks_table_has_rls_enabled():
    rows = await tasks_admin_pool().fetch(_Q)
    unprotected = [r["relname"] for r in rows if r["relname"] not in _EXEMPT]
    assert not unprotected, (
        "tasks-DB tables WITHOUT row-level security (org/department scoping "
        f"silently bypassed on these): {unprotected}"
    )


async def test_every_users_table_has_rls_enabled():
    rows = await users_admin_pool().fetch(_Q)
    unprotected = [r["relname"] for r in rows if r["relname"] not in _EXEMPT]
    assert not unprotected, (
        "users-DB tables WITHOUT row-level security: " + str(unprotected)
    )
