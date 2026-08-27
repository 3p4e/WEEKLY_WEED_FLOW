"""URS alignment: 5-working-day eCoA review clock (QCSOP 012 §6.3.1).

Revision ID: 0032
Revises: 0031
Create Date: 2026-07-20

docs/URS-COQ-GAP-ANALYSIS-2026-07.md item 7 — an ingested eCoA must be
reviewed within 5 working days of registration (§6.3.1), the same deadline-
window control already built for the 24-hour RQS registration window
(qc_sampling_requests.registration_deadline / registration_window_met).

`review_deadline` is stamped at registration (5 working days ahead — which,
from any weekday, is exactly 7 calendar days: 5 business days always cross one
weekend); `reviewed_at` + `review_window_met` are stamped when the document
transitions to REVIEWED. Additive, nullable — never back-filled.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.qc_coa_documents ADD COLUMN review_deadline date")
    op.execute("ALTER TABLE public.qc_coa_documents ADD COLUMN reviewed_at timestamp with time zone")
    op.execute("ALTER TABLE public.qc_coa_documents ADD COLUMN review_window_met boolean")


def downgrade() -> None:
    op.execute("ALTER TABLE public.qc_coa_documents DROP COLUMN review_window_met")
    op.execute("ALTER TABLE public.qc_coa_documents DROP COLUMN reviewed_at")
    op.execute("ALTER TABLE public.qc_coa_documents DROP COLUMN review_deadline")
