"""role model: rename DEPT_HEAD -> DEP_MGR, remove PROJECT_LEAD

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-05

Purely Plant's org model has a "Department Manager" (DEP_MGR), not the
generic "Department Head" the v2 baseline shipped, and has no PROJECT_LEAD
role at all. This migrates the live identity DB to the corrected role set:

  ADMIN | DEP_MGR | TEAM_LEADER | USER   (was: + DEPT_HEAD, + PROJECT_LEAD)

Existing DEPT_HEAD accounts are renamed to DEP_MGR in place (so the sole
seeded dept-head survives the constraint change); any stray PROJECT_LEAD
row — there should be none — is demoted to USER rather than blocking the
migration. app.is_elevated() (used by the profiles RLS policy) is rebuilt
to recognize DEP_MGR and drop the two retired roles.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_NEW = "ARRAY['ADMIN'::text, 'DEP_MGR'::text, 'TEAM_LEADER'::text, 'USER'::text]"
_ROLES_OLD = ("ARRAY['ADMIN'::text, 'DEPT_HEAD'::text, 'PROJECT_LEAD'::text,"
              " 'TEAM_LEADER'::text, 'USER'::text]")


def upgrade() -> None:
    # The CHECK on profiles_role_check is validated immediately against every
    # existing row, including by an UPDATE — not just at ADD CONSTRAINT time.
    # The still-active OLD constraint doesn't allow 'DEP_MGR', so the rename
    # UPDATE below must run with NO constraint in effect: drop first, update
    # while unconstrained, then add the new constraint over the final state.
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    op.execute("UPDATE public.profiles SET role='DEP_MGR' WHERE role='DEPT_HEAD'")
    op.execute("UPDATE public.profiles SET role='USER' WHERE role='PROJECT_LEAD'")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_NEW})))")
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               " LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ('ADMIN','DEP_MGR') $$")


def downgrade() -> None:
    # Mirror upgrade()'s ordering for the same reason: the still-active NEW
    # constraint doesn't allow 'DEPT_HEAD', so drop it before the data UPDATE,
    # not after.
    op.execute("CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean"
               " LANGUAGE sql STABLE AS $$ SELECT app.current_role()"
               " IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD') $$")
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    op.execute("UPDATE public.profiles SET role='DEPT_HEAD' WHERE role='DEP_MGR'")
    op.execute("ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check"
               f" CHECK ((role = ANY ({_ROLES_OLD})))")
