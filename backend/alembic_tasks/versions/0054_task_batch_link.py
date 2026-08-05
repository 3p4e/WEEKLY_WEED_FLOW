"""cultivation Phase 3, part 1: tasks reference the batch they act on

Revision ID: 0054
Revises: 0053
Create Date: 2026-08-05

docs/CULTIVATION-DESIGN-2026-07.md §5, "Phase 3 — tasks on top":

    "Phase transitions generate the per-phase task sets, and tasks reference the
     batch they act on, so the batch record accumulates from work actually
     performed. This is the half that makes the two existing halves one
     department."

The "two existing halves" are the identity/lifecycle model (migration 0045:
cultivars, batches, plants, phase events) and the records built on top of it
(harvest, IPM, irrigation, biosecurity — 0051-0053). Both know a batch exists;
neither lets a general TASK say which batch it was performed on. The cultivation
department's dept-template already offers a `batch_ref` field on the create form
— but it is free text, a label, not a reference. Nothing stops it drifting from
the real code, and nothing can join "every task ever done on batch GP-2026-041"
back to the batch itself. That join is what this migration adds.

ONE NULLABLE COLUMN, NOT A NEW TABLE. A task either acts on a batch or it does
not; when it does, there is exactly one. `tasks.batch_id` is nullable (every
non-cultivation task, and most cultivation tasks, will never set it) and FK'd to
`plant_batches` with ON DELETE RESTRICT — the same convention `harvests`,
`ipm_applications` and `irrigation_events` already use for their batch_id
columns (0051/0052), because nothing in this app hard-deletes a plant_batches
row (terminal phases retire a batch in place; DROP is not part of its
lifecycle), so RESTRICT costs nothing and keeps the convention uniform across
every table that references a batch.

Purely additive to `tasks`: no existing column changes, no CHECK narrows, and
the table's RLS policy and `app.fn_audit_row()` trigger (already present since
`tasks` is an existing table) apply to the new column automatically — no new
policy or trigger needed here.

Part 2 (the phase-transition task-set generation itself) is application logic
in `app/api/cultivation.py`'s `move_batch`, not schema — see that module for
the templates and the idempotency rule.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.tasks ADD COLUMN batch_id uuid")
    op.execute(
        "ALTER TABLE public.tasks ADD CONSTRAINT tasks_batch_id_fkey"
        " FOREIGN KEY (batch_id) REFERENCES public.plant_batches(id) ON DELETE RESTRICT"
    )
    # Partial: the overwhelming majority of tasks never set this column, so a
    # full index would mostly index NULLs. The one real query this serves —
    # "every task performed on batch X" — only ever asks for rows that have it.
    op.execute(
        "CREATE INDEX tasks_batch_idx ON public.tasks USING btree (batch_id)"
        " WHERE batch_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX public.tasks_batch_idx")
    op.execute("ALTER TABLE public.tasks DROP CONSTRAINT tasks_batch_id_fkey")
    op.execute("ALTER TABLE public.tasks DROP COLUMN batch_id")
