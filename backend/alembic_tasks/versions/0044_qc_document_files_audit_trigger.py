"""Audit-trigger the QC document custody table (2026-07 review round 2)

Revision ID: 0044
Revises: 0043
Create Date: 2026-07-28

`qc_document_files` holds the PDF ORIGINALS of QC documents together with
their SHA-256 (URS item 12, custody of source records) and had no
`app.fn_audit_row()` trigger — so uploading, replacing or deleting a source
certificate produced no audit_log entry at all. For a GxP custody record that
is the worst shape a gap can take: nothing errors, and the absence is only
noticed when someone goes looking for a history that was never written.

Found by the new tests/test_audit_coverage.py, which is the point of it —
this is the same drift class that already required 0043 (tasks) and users-0007
four days earlier, on tables that had been shipping unaudited.

`events` and `notifications` are deliberately left without a trigger and are
exempted in that test with their reasons: both are append-only derived
telemetry (an event log, and its per-recipient fan-out with read state).
Auditing a read-receipt flip would bury the record it is meant to protect.

Purely additive; no data migration. fn_audit_row() is untouched (0043 already
made it id-column-agnostic, and qc_document_files has an `id` anyway).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TRIGGER audit_qc_document_files"
        " AFTER INSERT OR DELETE OR UPDATE ON public.qc_document_files"
        " FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_qc_document_files ON public.qc_document_files")
