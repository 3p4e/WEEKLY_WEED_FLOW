"""role model: executives + department managers + QP; drop DEP_MGR/TEAM_LEADER

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05

Purely Plant's real org model replaces the generic DEP_MGR with specific
department-manager roles, adds executives, and puts the Qualified Person at
manager rank. TEAM_LEADER is dropped. New role set (see app/roles.py, the code
side's single source of truth):

  ADMIN | CEO | COO | QA_MGR | QC_MGR | PR_MGR | WH_MGR | SC_MGR | CU_MGR | QP | USER

Everything but USER is elevated. Any live DEP_MGR/TEAM_LEADER row (there are
none in production — both accounts are ADMIN) is demoted to USER so it can't
block the constraint swap. Drop-before-update ordering is required: a CHECK is
validated against existing rows on UPDATE too, not only at ADD time (the bug
fixed in 0002).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_NEW = ("ARRAY['ADMIN'::text, 'CEO'::text, 'COO'::text, 'QA_MGR'::text,"
              " 'QC_MGR'::text, 'PR_MGR'::text, 'WH_MGR'::text, 'SC_MGR'::text,"
              " 'CU_MGR'::text, 'QP'::text, 'USER'::text]")
_ROLES_OLD = "ARRAY['ADMIN'::text, 'DEP_MGR'::text, 'TEAM_LEADER'::text, 'USER'::text]"

_ELEVATED_NEW = ("'ADMIN','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SC_MGR','CU_MGR','QP'")


def upgrade() -> None:
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    # Retired roles → USER before the new constraint (none exist in prod).
    op.execute("UPDATE public.profiles SET role='USER' WHERE role IN ('DEP_MGR','TEAM_LEADER')")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_NEW})))")
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_NEW}) $$")


def downgrade() -> None:
    # Managers/executives have no pre-0003 equivalent — collapse them to USER
    # (ADMIN is preserved) so the old 4-role constraint can be re-applied.
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               " LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ('ADMIN','DEP_MGR') $$")
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    op.execute("UPDATE public.profiles SET role='USER'"
               " WHERE role IN ('CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR','SC_MGR','CU_MGR','QP')")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_OLD})))")
