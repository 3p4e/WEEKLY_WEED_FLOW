"""audit_log: index created_at DESC for the trail-list keyset query

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-05

The users-DB copy of the tasks-0055 change. The audit trail list
(`GET /audit`, app/api/audit.py) merges both chains and orders each by
`created_at DESC LIMIT n`, keyset-paginated on `created_at < $before`.
`audit_log` only carried a `(table_name, record_id)` index, so that ORDER BY
fell back to a full sort of the chain on every page.

A plain btree on `created_at DESC` serves both the default newest-first page and
the `before` keyset scan. Purely additive — no column/constraint change, and the
table's RLS policy and audit trigger are unaffected.

Applied here so the two databases' copies of `audit_log` stay symmetric: an
index present in one and absent in the other is exactly the kind of drift that
gets found years later by the side that was missed.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX audit_log_created_at_idx ON public.audit_log"
        " USING btree (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX public.audit_log_created_at_idx")
