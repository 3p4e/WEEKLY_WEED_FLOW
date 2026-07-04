"""allow date-only work sessions (a timestamp with unknown duration)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05

The capture contract (docs/TASK-CAPTURE-PROMPT.md) explicitly permits a
session with "hours": null when the duration is genuinely unknown — the
point being to record WHEN work happened even if you can't say for how long
(common when reconstructing a backlog from a registry). The original
work_sessions_duration_check required hours OR ended_at, which rejected
those honest date-only sessions and silently skipped their whole task on
import. Drop that constraint: a session now needs only a started_at.

The other two guards stay: hours (when given) must be > 0, and ended_at
(when given) must be after started_at. A date-only session contributes 0 to
hour totals but still appears in the activity time band and is classified
(regular/overtime/night/weekend) from its start time.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.work_sessions DROP CONSTRAINT work_sessions_duration_check")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.work_sessions ADD CONSTRAINT work_sessions_duration_check"
        " CHECK ((hours IS NOT NULL) OR (ended_at IS NOT NULL))")
