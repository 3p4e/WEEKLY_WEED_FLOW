"""URS alignment: carry the lab's stated verdict onto the permanent result.

Revision ID: 0033
Revises: 0032
Create Date: 2026-07-21

docs/URS-COQ-GAP-ANALYSIS-2026-07.md item 8 — the lab's own pass/fail was
captured at eCoA extraction (mig 0028, qc_coa_extractions.lab_verdict) and
reconciled there, but was DROPPED when the extraction was promoted into a
certificate: the reconciliation lived only in transient staging and never
reached the released record. `qc_results.lab_verdict` retains that verbatim
reference on the permanent result — populated at promotion from the source
extraction and settable on a manually-entered (iCoA) result — so the lab-vs-
in-house disagreement is visible on the certificate, not just the intake queue.

Reference-only: it never feeds the in-house `complies` determination
(QCSOP 012 §6.3.2). Additive, nullable — never back-filled.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.qc_results ADD COLUMN lab_verdict text")


def downgrade() -> None:
    op.execute("ALTER TABLE public.qc_results DROP COLUMN lab_verdict")
