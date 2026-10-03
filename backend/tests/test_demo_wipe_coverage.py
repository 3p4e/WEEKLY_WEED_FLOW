"""Every org-scoped table in the tasks DB must appear in the demo wipe.

`demo_org._TASKS_WIPE_ORDER` is a hand-maintained list, and a table left out of
it is not a loud failure: the wipe simply leaves those rows behind, so the next
visitor to the demo org inherits the previous one's data. Worse, the rows are
invisible from the demo UI once their parents are gone, so nobody notices until
a FK refuses a later delete.

This is the same shape of guard as test_rls_coverage / test_audit_coverage:
enumerate what the database actually has rather than trusting a list to be kept
in step by hand. A table with no `org_id` is not org-scoped and is exempt by
construction, as is the audit log, which the wipe must never touch — its hash
chain is append-only (see test_demo.test_wipe_introduces_no_audit_break).
"""
from app.db import tasks_admin_pool
from app.demo_org import _TASKS_WIPE_ORDER

# audit_log is org-scoped but deliberately never wiped: the hash chain is the
# record that the demo org existed at all.
_EXEMPT = {"audit_log"}

_ORG_SCOPED = """
SELECT c.relname
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_attribute a ON a.attrelid = c.oid
 WHERE n.nspname = 'public' AND c.relkind = 'r'
   AND a.attname = 'org_id' AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY c.relname
"""


async def test_every_org_scoped_tasks_table_is_wiped():
    rows = await tasks_admin_pool().fetch(_ORG_SCOPED)
    tables = {r["relname"] for r in rows} - _EXEMPT
    missing = sorted(tables - set(_TASKS_WIPE_ORDER))
    assert not missing, (
        "org-scoped tasks-DB tables missing from demo_org._TASKS_WIPE_ORDER — "
        "a demo reset would leave their rows behind for the next visitor: "
        f"{missing}"
    )


async def test_the_wipe_list_names_only_real_tables():
    """A renamed or dropped table left in the list makes every wipe fail with an
    UndefinedTable, which is a demo outage rather than a stale comment."""
    rows = await tasks_admin_pool().fetch(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = 'public' AND c.relkind = 'r'")
    real = {r["relname"] for r in rows}
    unknown = sorted(set(_TASKS_WIPE_ORDER) - real)
    assert not unknown, f"_TASKS_WIPE_ORDER names tables that do not exist: {unknown}"
