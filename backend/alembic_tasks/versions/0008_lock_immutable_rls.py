"""weekly_documents: enforce locked-record immutability at the DB layer

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-07

A locked weekly document is the submitted record — the app layer enforces
that with `WHERE status='draft'` on every UPDATE/lock, but nothing at the DB
level stopped an in-org `app_user` connection from rewriting or deleting a
locked row (the single `org_isolation` FOR ALL policy permitted it). This
mirrors the append-only guarantee `audit_log` already gets from command-scoped
policies: replace the FOR ALL policy with per-command ones so UPDATE and DELETE
only see DRAFT rows. Reads stay org-scoped exactly as before; the draft→locked
transition still works (USING checks the OLD row, which is still 'draft').
`app_admin` keeps BYPASSRLS for provisioning/teardown.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP POLICY org_isolation ON public.weekly_documents")
    op.execute(
        "CREATE POLICY wd_select ON public.weekly_documents FOR SELECT"
        " USING ((org_id = app.current_org_id()))")
    op.execute(
        "CREATE POLICY wd_insert ON public.weekly_documents FOR INSERT"
        " WITH CHECK ((org_id = app.current_org_id()))")
    # USING is evaluated against the OLD row, so a locked row is invisible to
    # UPDATE (can't be mutated) while the draft→locked write itself passes;
    # WITH CHECK guards only org on the NEW row so status may change to 'locked'.
    op.execute(
        "CREATE POLICY wd_update ON public.weekly_documents FOR UPDATE"
        " USING ((org_id = app.current_org_id() AND status = 'draft'))"
        " WITH CHECK ((org_id = app.current_org_id()))")
    op.execute(
        "CREATE POLICY wd_delete ON public.weekly_documents FOR DELETE"
        " USING ((org_id = app.current_org_id() AND status = 'draft'))")


def downgrade() -> None:
    op.execute("DROP POLICY wd_delete ON public.weekly_documents")
    op.execute("DROP POLICY wd_update ON public.weekly_documents")
    op.execute("DROP POLICY wd_insert ON public.weekly_documents")
    op.execute("DROP POLICY wd_select ON public.weekly_documents")
    op.execute(
        "CREATE POLICY org_isolation ON public.weekly_documents"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))")
