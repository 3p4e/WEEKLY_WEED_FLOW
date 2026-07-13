"""tasks: per-department attributes (jsonb)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-12

Department-specific task metadata — room/strain/plant_count for Cultivation,
sample_ref for QC, equipment_ref for Maintenance, batch_ref for Production,
and so on. One open jsonb map instead of per-department columns: WHICH keys a
department captures is a frontend template concern (web/gf/dept-templates.js),
so new department fields never require another migration. The API validates
shape only (bounded key charset/count, scalar values, size cap — see
tasks._check_attributes).

NOT NULL DEFAULT '{}' so readers never branch on NULL-vs-empty; PG11+ fast
default means no table rewrite. No RLS change (0008's policies reference only
org/actor columns), no GRANT change (0007's table-level grants cover new
columns), and the audit_tasks row trigger captures the column automatically.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.tasks"
               " ADD COLUMN attributes jsonb DEFAULT '{}'::jsonb NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE public.tasks DROP COLUMN attributes")
