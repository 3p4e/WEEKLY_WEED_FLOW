"""Every org-scoped public table in BOTH databases must carry the audit trigger.

The mirror of test_rls_coverage.py, for the other silent-failure mode. A table
with no `app.fn_audit_row()` trigger simply produces no audit_log rows: nothing
errors, nothing looks wrong, and the gap is only discovered when someone goes
looking for a change history that was never recorded. For a GxP record that is
the worst shape a defect can take.

This is not hypothetical here — it is exactly the drift that required
remediation migrations 0043 (tasks) and 0007 (users) earlier in this same
review cycle, on tables that had been shipping without audit coverage. Nothing
would have caught the next one either, so this makes it a red test the moment a
migration adds an audited table without its trigger.

Exemptions are deliberate and each states WHY:
  • alembic_version   — migration bookkeeping, no org data (same as RLS).
  • audit_log         — the audit table itself; auditing it would recurse.
  • qc_coa_chunks     — derived RAG index rebuilt from qc_coa_documents; the
                        source document IS audited, and the chunks carry no
                        independently-authored content.
  • events            — append-only activity log; it IS a record of what
                        happened, and the underlying object change is audited
                        separately. Auditing the log would double every entry.
  • notifications     — per-recipient fan-out of `events` plus read state.
                        Auditing a read-receipt flip would bury the records
                        the trail exists to protect.
"""
from app.db import tasks_admin_pool, users_admin_pool

_EXEMPT = {"alembic_version", "audit_log", "qc_coa_chunks", "events", "notifications"}

# Tables in `public` with no AFTER INSERT/UPDATE/DELETE trigger calling
# app.fn_audit_row(). tgisinternal filters FK-enforcement triggers.
_Q = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
  AND NOT EXISTS (
    SELECT 1 FROM pg_trigger t
    JOIN pg_proc p ON p.oid = t.tgfoid
    JOIN pg_namespace pn ON pn.oid = p.pronamespace
    WHERE t.tgrelid = c.oid AND NOT t.tgisinternal
      AND pn.nspname = 'app' AND p.proname = 'fn_audit_row'
  )
ORDER BY c.relname
"""


async def test_every_tasks_table_has_the_audit_trigger():
    rows = await tasks_admin_pool().fetch(_Q)
    missing = [r["relname"] for r in rows if r["relname"] not in _EXEMPT]
    assert not missing, (
        "tasks-DB tables with NO app.fn_audit_row() trigger — changes to these "
        f"leave no audit trail at all: {missing}"
    )


async def test_every_users_table_has_the_audit_trigger():
    rows = await users_admin_pool().fetch(_Q)
    missing = [r["relname"] for r in rows if r["relname"] not in _EXEMPT]
    assert not missing, (
        "users-DB tables with NO app.fn_audit_row() trigger: " + str(missing)
    )


async def test_audit_function_is_byte_identical_across_both_databases():
    """The two databases carry their own copy of app.fn_audit_row(). They must
    stay identical: a fix applied to one and not the other means the audit
    record means different things depending on which DB a row lives in, which
    is impossible to reason about after the fact."""
    q = ("SELECT prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
         " WHERE n.nspname='app' AND p.proname='fn_audit_row'")
    tasks_src = await tasks_admin_pool().fetchval(q)
    users_src = await users_admin_pool().fetchval(q)
    assert tasks_src and users_src, "app.fn_audit_row() missing from one of the databases"
    assert tasks_src == users_src, (
        "app.fn_audit_row() has DRIFTED between the tasks and users databases — "
        "the same change produces different audit rows depending on the DB"
    )
