"""remove QA_AUDITOR role entirely

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02

QA_AUDITOR is removed as a concept from the app: not just excluded from
app.is_elevated() (which would leave it creatable but powerless), but
dropped from profiles_role_check entirely so it can never be assigned to
an account again. Confirmed zero existing production profiles carry this
role before writing this migration, so no data backfill is needed.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean "
        "LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD') $$"
    )
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    op.execute(
        "ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check "
        "CHECK (role = ANY (ARRAY['ADMIN'::text, 'DEPT_HEAD'::text, 'PROJECT_LEAD'::text, "
        "'TEAM_LEADER'::text, 'USER'::text]))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT profiles_role_check")
    op.execute(
        "ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check "
        "CHECK (role = ANY (ARRAY['ADMIN'::text, 'DEPT_HEAD'::text, 'PROJECT_LEAD'::text, "
        "'TEAM_LEADER'::text, 'USER'::text, 'QA_AUDITOR'::text]))"
    )
    op.execute(
        "CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean "
        "LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN "
        "('ADMIN','DEPT_HEAD','PROJECT_LEAD','QA_AUDITOR') $$"
    )
