"""roles: add IR_MGR (Irrigation Manager)

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-05

Irrigation — the fertigation plant and its distribution to every room — is a
department of its own at the facility, not a cultivation duty. The irrigation
record (tasks migration 0052) has existed since July with cultivation as its
only writer, and nothing in the role set could own it. This gives the
department a manager role; app/api/irrigation.py now gates the record on it.

Role set after this migration, in ALL_ROLES order — the CHECK's ARRAY order
must match app/roles.py exactly, and CI byte-diffs schema.users.sql against
`alembic upgrade head`:

  ADMIN | OWNER | CEO | COO | QA_MGR | QC_MGR | PR_MGR | WH_MGR | SE_MGR |
  CU_MGR | IR_MGR | MU_MGR | QP | USER

The tasks DB carries its OWN copy of app.is_elevated() and it has silently
fallen out of step with this one twice (see tasks migration 0009). Tasks
migration 0064 makes the matching change there; neither is complete alone.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_NEW = ("ARRAY['ADMIN'::text, 'OWNER'::text, 'CEO'::text, 'COO'::text, 'QA_MGR'::text,"
              " 'QC_MGR'::text, 'PR_MGR'::text, 'WH_MGR'::text, 'SE_MGR'::text,"
              " 'CU_MGR'::text, 'IR_MGR'::text, 'MU_MGR'::text, 'QP'::text, 'USER'::text]")
_ROLES_OLD = ("ARRAY['ADMIN'::text, 'OWNER'::text, 'CEO'::text, 'COO'::text, 'QA_MGR'::text,"
              " 'QC_MGR'::text, 'PR_MGR'::text, 'WH_MGR'::text, 'SE_MGR'::text,"
              " 'CU_MGR'::text, 'MU_MGR'::text, 'QP'::text, 'USER'::text]")

_ELEVATED_NEW = ("'ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SE_MGR','CU_MGR','IR_MGR','MU_MGR','QP'")
_ELEVATED_OLD = ("'ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR',"
                 "'SE_MGR','CU_MGR','MU_MGR','QP'")


def upgrade() -> None:
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_NEW})))")
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_NEW}) $$")


def downgrade() -> None:
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    # IR_MGR has no pre-0012 equivalent → base staff, same as MU_MGR in 0004.
    op.execute("UPDATE public.profiles SET role='USER' WHERE role='IR_MGR'")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_OLD})))")
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               f" LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ({_ELEVATED_OLD}) $$")
