"""tasks.status CHECK constraint, ai_pins.prompt_version, two dead columns dropped

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-04

Four small, independently-motivated fixes from the post-ship review:

1. tasks.status gets a CHECK constraint matching the six canonical wire
   values (pending/ongoing/review/stuck/postponed/completed), same pattern
   as profiles_role_check / handoffs_status_check. Safe to add: the
   frontend's S_IN/S_OUT maps (web/gf/integrate.js) already translate its
   internal working/done spelling before anything reaches the API, so only
   the canonical six have ever been written by the app itself. Verified via
   `SELECT status, count(*) FROM tasks GROUP BY status` against production
   before this migration was applied — one stray 'working' row turned out to
   be leftover test debris from an earlier session's RLS testing and was
   soft-deleted (is_deleted=true, per the app's own never-hard-delete
   policy) rather than reinterpreted as real data.

2. tasks.progress_notes (jsonb) is dropped. It was set once at INSERT and
   never updated by any write path — POST /tasks/{id}/progress only ever
   wrote to the separate task_progress table — so every task card's notes
   section showed nothing, always, in production. list_tasks now aggregates
   live from task_progress instead (see app/api/tasks.py); the column was
   dead weight duplicating a source of truth it never actually mirrored.

3. tasks.deps (uuid[]) is dropped. Zero write path anywhere (no TaskIn/
   TaskPatch field, no INSERT/UPDATE ever sets it) and the frontend's
   transform hardcodes deps: [] regardless of what the API returns.

4. ai_pins.prompt_version (text) is added so each AI-authored pin records
   which planner_prompts.PROMPT_VERSION produced it ('fallback' for the
   deterministic no-Letta path, NULL for the raw digest pin which is never
   LLM-authored at all) — closes the review's "no persisted record of which
   prompt version produced which pin" gap.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.tasks ADD CONSTRAINT tasks_status_check "
        "CHECK (status = ANY (ARRAY['pending'::text, 'ongoing'::text, 'review'::text, "
        "'stuck'::text, 'postponed'::text, 'completed'::text]))"
    )
    op.execute("ALTER TABLE public.tasks DROP COLUMN progress_notes")
    op.execute("ALTER TABLE public.tasks DROP COLUMN deps")
    op.execute("ALTER TABLE public.ai_pins ADD COLUMN prompt_version text")


def downgrade() -> None:
    op.execute("ALTER TABLE public.ai_pins DROP COLUMN prompt_version")
    op.execute("ALTER TABLE public.tasks ADD COLUMN deps uuid[] DEFAULT '{}'::uuid[] NOT NULL")
    op.execute("ALTER TABLE public.tasks ADD COLUMN progress_notes jsonb DEFAULT '[]'::jsonb NOT NULL")
    op.execute("ALTER TABLE public.tasks DROP CONSTRAINT tasks_status_check")
