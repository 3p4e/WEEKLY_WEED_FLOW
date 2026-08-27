"""Drop the dead password_reset_codes table (2026-07 review round 2)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-28

`password_reset_codes` has never been read or written by any application code.
The password-reset flow issues a one-time password through
`auth.reset_password`, which writes `profiles.password_hash` +
`must_change_password` directly — this table is a leftover from a design that
was replaced before it shipped. Two independent reviewers flagged it, and the
new tests/test_audit_coverage.py flagged it a third time as the only users-DB
table with no audit trigger.

Dropping it beats adding a trigger: an audited table nothing writes to is
still dead schema, and dead schema with an RLS policy on it invites someone to
"reuse" it later without noticing that no code path maintains expiry or
single-use semantics. Only comments referenced it (app/db.py's module
docstring, demo_org.py's cascade note, test_rls.py's docstring); those are
updated in the same change.

Empty in every environment (nothing has ever inserted), so DROP loses no data.
The downgrade restores the table, its FK, RLS and policy exactly as
schema.users.sql had them.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE public.password_reset_codes")


def downgrade() -> None:
    op.execute(
        "CREATE TABLE public.password_reset_codes ("
        " id uuid DEFAULT gen_random_uuid() NOT NULL,"
        " user_id uuid NOT NULL,"
        " code_hash text NOT NULL,"
        " expires_at timestamp with time zone NOT NULL,"
        " used_at timestamp with time zone,"
        " created_at timestamp with time zone DEFAULT now() NOT NULL)"
    )
    op.execute("ALTER TABLE ONLY public.password_reset_codes"
               " ADD CONSTRAINT password_reset_codes_pkey PRIMARY KEY (id)")
    op.execute("ALTER TABLE ONLY public.password_reset_codes"
               " ADD CONSTRAINT password_reset_codes_user_id_fkey"
               " FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE public.password_reset_codes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.password_reset_codes FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY reset_self ON public.password_reset_codes"
        " USING (((user_id = app.current_user_id()) OR app.is_elevated()))"
        " WITH CHECK (((user_id = app.current_user_id()) OR app.is_elevated()))"
    )
