"""per-user pin visibility, hours invariant at the DB, week_start sort index

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-03

Three fixes surfaced by the post-ship review:

1. ai_pins gains subject_user_id. The weekly snapshot job writes one
   weekly_report_user / next_week_plan_user pin per employee; before this
   column existed those pins were only org-scoped, so ANY authenticated
   member could read every colleague's individual AI performance report via
   GET /ai/pins. The RLS SELECT visibility is tightened here — in the
   policy, not the endpoint — because RLS is this app's security boundary:
   a pin is visible if it has no subject (org-level), if you ARE the
   subject, or if you're elevated (ADMIN/DEPT_HEAD/PROJECT_LEAD).

2. tasks.estimated_hours / actual_hours get a CHECK (>= 0). The API layer
   already validates ge=0, but BYPASSRLS scripts and any future write path
   skip Pydantic entirely, and the weekly digest sums these columns
   verbatim — the DB is the right place for a domain invariant, matching
   the precedent set by profiles_role_check / handoffs_status_check.

3. tasks gets an (org_id, week_start DESC, created_at DESC) index: the
   interactive AI context query (_task_context's no-week_id branch) sorts
   by exactly this and previously paid a full org scan+sort per call.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.ai_pins ADD COLUMN subject_user_id uuid "
        "REFERENCES public.profiles(id) ON DELETE CASCADE"
    )
    op.execute("DROP POLICY org_isolation ON public.ai_pins")
    op.execute(
        "CREATE POLICY org_isolation ON public.ai_pins "
        "USING (((org_id = app.current_org_id()) AND ((subject_user_id IS NULL) "
        "OR (subject_user_id = app.current_user_id()) OR app.is_elevated()))) "
        "WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "ALTER TABLE public.tasks ADD CONSTRAINT tasks_hours_nonnegative_check "
        "CHECK (((estimated_hours IS NULL) OR (estimated_hours >= (0)::numeric)) "
        "AND ((actual_hours IS NULL) OR (actual_hours >= (0)::numeric)))"
    )
    op.execute(
        "CREATE INDEX tasks_org_week_start_idx ON public.tasks "
        "USING btree (org_id, week_start DESC, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX public.tasks_org_week_start_idx")
    op.execute("ALTER TABLE public.tasks DROP CONSTRAINT tasks_hours_nonnegative_check")
    op.execute("DROP POLICY org_isolation ON public.ai_pins")
    op.execute(
        "CREATE POLICY org_isolation ON public.ai_pins "
        "USING ((org_id = app.current_org_id())) "
        "WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute("ALTER TABLE public.ai_pins DROP COLUMN subject_user_id")
