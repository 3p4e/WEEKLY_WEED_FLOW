"""tasks: explicit completion percentage

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-15

The owner's "how complete is this?" signal, set from the worklog panel —
until now the card progress bar was a status heuristic (working=50%,
review=75%, …), which is exactly the "indicator says not initiated"
complaint. progress is DISPLAY state, deliberately decoupled from status:
setting 100 never forces a task done (research rule: never hard-enforce
completion), while completing a task forward-fills 100 in the API for
consistency. smallint + CHECK keeps the column honest at the DB layer.

NOT NULL DEFAULT 0, PG11+ fast default (no rewrite). No RLS change (0008's
policies reference only org/actor columns), no GRANT change (0007's
table-level grants cover new columns); the audit_tasks row trigger captures
the column automatically.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.tasks"
               " ADD COLUMN progress smallint DEFAULT 0 NOT NULL")
    op.execute("ALTER TABLE public.tasks ADD CONSTRAINT tasks_progress_check"
               " CHECK (progress >= 0 AND progress <= 100)")


def downgrade() -> None:
    op.execute("ALTER TABLE public.tasks DROP CONSTRAINT tasks_progress_check")
    op.execute("ALTER TABLE public.tasks DROP COLUMN progress")
