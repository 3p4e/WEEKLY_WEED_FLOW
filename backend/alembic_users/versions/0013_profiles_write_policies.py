"""profiles: drop the two write policies the API never uses

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-27

RLS is described everywhere in this codebase as the real security boundary.
On `profiles` it was not one (APP-REVIEW-2026-07-14 L7, review 2026-09-27
BC-21):

  * `profiles_manage` (ALL commands, USING/WITH CHECK org + app.is_elevated())
    let ANY elevated role — a QC manager — insert, update or delete any
    profile in the org through the app_user pool, including its role.
  * `profiles_self` (FOR UPDATE, id = current user) let a user update their
    OWN row — every column of it, `role` and `is_active` included.

Nothing was exploitable today only because every profile write in the app
goes through the BYPASSRLS admin pool behind auth._can_manage; the first
`rls_users(user)` UPDATE anyone added would have opened both holes. The API
has no self-service profile edit and no manager write on the user pool, so
the honest fix is not a narrower policy but none: app_user keeps
`profiles_read` (SELECT, org-wide — the roster, directory and mention
resolution need it) and can write nothing. RLS is default-deny for a command
with no permissive policy, so an UPDATE/INSERT/DELETE from the user pool
affects zero rows. A future self-service edit adds a column-safe policy (or
a BEFORE UPDATE trigger) deliberately, with a test, rather than inheriting
these.

Downgrade restores both policies exactly as the baseline created them.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS profiles_manage ON public.profiles")
    op.execute("DROP POLICY IF EXISTS profiles_self ON public.profiles")


def downgrade() -> None:
    op.execute(
        "CREATE POLICY profiles_manage ON public.profiles"
        " USING (((org_id = app.current_org_id()) AND app.is_elevated()))"
        " WITH CHECK (((org_id = app.current_org_id()) AND app.is_elevated()))")
    op.execute(
        "CREATE POLICY profiles_self ON public.profiles FOR UPDATE"
        " USING ((id = app.current_user_id())) WITH CHECK ((id = app.current_user_id()))")
