"""tasks.external_ref — the capture-import dedup key.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-04

Captured tasks (Master Capture Prompt / Drive sweep) carry a stable
external_ref slug ("pp-qc-sop-012") so the same piece of work captured in
different sessions merges instead of duplicating. A first-class column with
a per-org partial unique index makes /capture/import's upsert race-safe —
matching on a [ref:…] tag would not be.

The index ignores soft-deleted rows: a deleted task's ref becomes reusable
(re-capturing work whose old row was discarded must not conflict forever).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.tasks ADD COLUMN external_ref text")
    op.execute(
        "CREATE UNIQUE INDEX tasks_org_external_ref_key ON public.tasks (org_id, external_ref)"
        " WHERE external_ref IS NOT NULL AND is_deleted = false")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.tasks_org_external_ref_key")
    op.execute("ALTER TABLE public.tasks DROP COLUMN IF EXISTS external_ref")
