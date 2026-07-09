"""roles: rename SC_MGR → SE_MGR (Security), add MU_MGR (Maintenance)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-09

SC_MGR ("Supply Chain Manager") was a placeholder — Purely Plant has no
Supply Chain department. The Security department needs SE_MGR (Security
Manager) and the Maintenance department needs MU_MGR (Maintenance Manager).

No production profiles hold SC_MGR, so the UPDATE is safe (but included
for correctness). New role set:

  ADMIN | CEO | COO | QA_MGR | QC_MGR | PR_MGR | WH_MGR | SE_MGR |
  CU_MGR | MU_MGR | QP | USER
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_NEW = ("ARRAY['ADMIN'::text, 'CEO'::text, 'COO'::text, 'QA_MGR'::text,"
              " 'QC_MGR'::text, 'PR_MGR'::text, 'WH_MGR'::text, 'SE_MGR'::text,"
              " 'CU_MGR'::text, 'MU_MGR'::text, 'QP'::text, 'USER'::text]")
_ROLES_OLD = ("ARRAY['ADMIN'::text, 'CEO'::text, 'COO'::text, 'QA_MGR'::text,"
              " 'QC_MGR'::text, 'PR_MGR'::text, 'WH_MGR'::text, 'SC_MGR'::text,"
              " 'CU_MGR'::text, 'QP'::text, 'USER'::text]")

_ELEVATED_NEW = ("'ADMIN','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SE_MGR','CU_MGR','MU_MGR','QP'")
_ELEVATED_OLD = ("'ADMIN','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SC_MGR','CU_MGR','QP'")


def upgrade() -> None:
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    # Rename SC_MGR → SE_MGR (no prod rows expected, but correct for integrity).
    op.execute("UPDATE public.profiles SET role='SE_MGR' WHERE role='SC_MGR'")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_NEW})))")
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_NEW}) $$")


def downgrade() -> None:
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    # SE_MGR back to SC_MGR; MU_MGR has no pre-0004 equivalent → USER.
    op.execute("UPDATE public.profiles SET role='SC_MGR' WHERE role='SE_MGR'")
    op.execute("UPDATE public.profiles SET role='USER' WHERE role='MU_MGR'")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_OLD})))")
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_OLD}) $$")
