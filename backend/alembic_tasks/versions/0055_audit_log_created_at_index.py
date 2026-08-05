"""audit_log: index created_at DESC for the trail-list keyset query

Revision ID: 0055
Revises: 0054
Create Date: 2026-08-05

The audit trail list (`GET /audit`, app/api/audit.py) orders every page by
`created_at DESC LIMIT n` — that is the keyset the `before` cursor paginates on
too. `audit_log` only carried a `(table_name, record_id)` index (the per-record
history lookup), so the ORDER BY had nothing to use and fell back to a full
sort of the whole chain on every page. As the log grows that is the one query
that degrades linearly.

A plain btree on `created_at DESC` serves both the default newest-first page and
the `created_at < $before` keyset scan directly. Purely additive — no column or
constraint change, and the table's existing RLS policy and audit trigger are
unaffected.

`audit_log` exists in BOTH databases (identity events chain in the users DB,
work events in the tasks DB); the users chain gets the identical index in
users-0010, so the two copies of the table stay symmetric.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX audit_log_created_at_idx ON public.audit_log"
        " USING btree (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX public.audit_log_created_at_idx")
