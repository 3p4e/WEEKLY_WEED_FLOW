"""role model: app.is_elevated() recognizes the executive/manager/QP set

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-05

The tasks DB carries its own copy of app.is_elevated() (the RLS policies here
— tasks_read/tasks_write, audit_read, ai_pins org_isolation — call it against
the per-request app.role GUC). It must agree with the users DB's role set
after 0003_role_org_model: everything but USER is elevated. No table data in
this DB stores role strings — only the function changes.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ELEVATED_NEW = ("'ADMIN','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SC_MGR','CU_MGR','QP'")


def upgrade() -> None:
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_NEW}) $$")


def downgrade() -> None:
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               " LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ('ADMIN','DEP_MGR') $$")
