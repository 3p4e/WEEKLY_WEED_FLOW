"""URS alignment: certificate register completeness (QCLB 020 §6.13).

Revision ID: 0031
Revises: 0030
Create Date: 2026-07-20

docs/URS-COQ-GAP-ANALYSIS-2026-07.md item 6 — the certificate register needs
the retention/archive fields QCLB 020 §6.13 records against each certificate:
where the physical/electronic original is filed (`archive_ref`) and the
retention window (`retention_start`/`retention_expiry`). The OOS and
supersession cross-references the register also needs are already derivable
(OOS by batch_id, supersession via supersedes_id) so no columns are added for
them; the §6.13 canned queries and the numbering-gap data-integrity report are
pure read layers over the existing rows (see app/api/qc.py /register endpoints).

Additive only — a GxP record is immutable, so these are nullable and never
back-filled with an invented value.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN retention_start date")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN retention_expiry date")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN archive_ref text")


def downgrade() -> None:
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN archive_ref")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN retention_expiry")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN retention_start")
