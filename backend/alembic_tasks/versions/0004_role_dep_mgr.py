"""role model: app.is_elevated() recognizes DEP_MGR, not DEPT_HEAD/PROJECT_LEAD

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-05

The tasks DB carries its own copy of app.is_elevated() because the RLS
policies here (tasks_read/tasks_write, audit_read, ai_pins org_isolation)
call it against the per-request app.role GUC. It must agree with the users
DB's corrected role set after 0002_role_dep_mgr, so a DEP_MGR is treated as
elevated and the retired DEPT_HEAD/PROJECT_LEAD names are dropped. No table
data in this DB stores role strings — only the function changes.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               " LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ('ADMIN','DEP_MGR') $$")


def downgrade() -> None:
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               " LANGUAGE sql STABLE AS $$ SELECT app.current_role()"
               " IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD') $$")
