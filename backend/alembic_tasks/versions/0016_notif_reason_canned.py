"""notifications.reason: widen CHECK for canned automation rules

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-15

app/automation.py's fixed rule set (CAPA -> stuck notifies QA + the
Qualified Person; validation -> stuck notifies the Qualified Person) gives
those recipients a distinct reason from the generic 'status' so the inbox
can explain WHY they — often non-participants — are seeing the row. The
0013 CHECK enumerated a closed reason set that didn't anticipate this;
without widening it every canned-rule INSERT hits the constraint and is
silently dropped by emit()'s per-recipient try/except (by design, so one
bad recipient never fails the whole notification fan-out — but it means a
missing reason value fails just as quietly as a real duplicate). The
unassign/due-soon/overdue/mention features that shipped earlier all reused
existing reason values ('assigned', 'due', 'mentioned') so they never hit
this; capa_stuck/validation_stuck are the first genuinely new ones.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = ("assigned", "mentioned", "comment", "status", "due", "report")
_NEW = _OLD + ("capa_stuck", "validation_stuck")


def upgrade() -> None:
    op.execute("ALTER TABLE public.notifications DROP CONSTRAINT notifications_reason_check")
    op.execute(
        "ALTER TABLE public.notifications ADD CONSTRAINT notifications_reason_check "
        "CHECK (reason = ANY (ARRAY[" + ",".join(f"'{r}'::text" for r in _NEW) + "]))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.notifications DROP CONSTRAINT notifications_reason_check")
    op.execute(
        "ALTER TABLE public.notifications ADD CONSTRAINT notifications_reason_check "
        "CHECK (reason = ANY (ARRAY[" + ",".join(f"'{r}'::text" for r in _OLD) + "]))"
    )
