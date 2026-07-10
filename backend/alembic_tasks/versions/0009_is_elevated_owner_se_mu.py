"""tasks-DB app.is_elevated(): add OWNER + SE_MGR/MU_MGR (drop retired SC_MGR)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-10

The tasks DB carries its own copy of app.is_elevated() (tasks_read/tasks_write,
audit_read, ai_pins org_isolation call it against the per-request app.role
GUC), and it silently fell out of sync with the users DB's role set TWICE:

- users-0004 renamed SC_MGR -> SE_MGR and added MU_MGR, but no tasks-side
  migration followed — so a Security/Maintenance manager gets USER-level task
  visibility (own tasks only) instead of the org-wide elevated read.
- users-0005 added OWNER, again with no tasks-side migration — so the business
  owner logs in to a completely EMPTY app: the endpoints admit the role
  (app/roles.py ELEVATED_ROLES includes it) but every RLS policy in this
  database filters out all rows.

CI's drift check never caught it because it compares the alembic-built schema
against schema.tasks.sql per database — both were consistently stale.

This aligns the tasks DB with app/roles.py: everything but USER is elevated.
No table data stores role strings — only the function changes.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ELEVATED_NEW = ("'ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SE_MGR','CU_MGR','MU_MGR','QP'")
_ELEVATED_OLD = ("'ADMIN','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SC_MGR','CU_MGR','QP'")


def upgrade() -> None:
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_NEW}) $$")


def downgrade() -> None:
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_OLD}) $$")
