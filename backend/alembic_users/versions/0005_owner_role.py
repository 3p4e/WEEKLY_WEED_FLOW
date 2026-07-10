"""roles: add OWNER (business owner — executive tier, no department)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-10

Purely Plant needs a distinct OWNER role for the actual company owner,
separate from CEO/COO and from the ADMIN system role. OWNER sits alongside
CEO/COO as a cross-org executive: elevated (org-wide task read + audit),
no department, not a provisioning role (same as CEO/COO today — only ADMIN
and the department managers create/edit/delete accounts). New role set:

  ADMIN | OWNER | CEO | COO | QA_MGR | QC_MGR | PR_MGR | WH_MGR | SE_MGR |
  CU_MGR | MU_MGR | QP | USER
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_NEW = ("ARRAY['ADMIN'::text, 'OWNER'::text, 'CEO'::text, 'COO'::text, 'QA_MGR'::text,"
              " 'QC_MGR'::text, 'PR_MGR'::text, 'WH_MGR'::text, 'SE_MGR'::text,"
              " 'CU_MGR'::text, 'MU_MGR'::text, 'QP'::text, 'USER'::text]")
_ROLES_OLD = ("ARRAY['ADMIN'::text, 'CEO'::text, 'COO'::text, 'QA_MGR'::text,"
              " 'QC_MGR'::text, 'PR_MGR'::text, 'WH_MGR'::text, 'SE_MGR'::text,"
              " 'CU_MGR'::text, 'MU_MGR'::text, 'QP'::text, 'USER'::text]")

_ELEVATED_NEW = ("'ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SE_MGR','CU_MGR','MU_MGR','QP'")
_ELEVATED_OLD = ("'ADMIN','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SE_MGR','CU_MGR','MU_MGR','QP'")


def upgrade() -> None:
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_NEW})))")
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_NEW}) $$")


def downgrade() -> None:
    # No pre-0005 equivalent for OWNER — collapse to USER so the old
    # constraint can be re-applied.
    op.execute("UPDATE public.profiles SET role='USER' WHERE role='OWNER'")
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_OLD})))")
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_OLD}) $$")
