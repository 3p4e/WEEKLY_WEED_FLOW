"""Phase 3 U1: COQ generation fields (per-result provenance + artifact pointer)

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-16

The Certificate of Quality (COQ) is `qc_certificates(cert_type='COQ')` + its
`qc_results`, rendered to a house-style .docx by the DocEngine. Generating a
faithful COQ needs two things the model didn't carry yet (harvested from the
COQ_GEN prototype's mandatory source-mapping guard + rendered-artifact record):

- `qc_results.source_document_code/date/institution` — every result line on a
  COQ must map back to the source iCoA/eCoA it came from (a hard rule in the
  COQ template). Additive, nullable — unknown provenance stays blank.
- `qc_certificates.coq_document_id/coq_generated_at` — a pointer to the
  DocEngine registry document produced by the PASS-gated render, so the COQ is
  re-downloadable and audit-linked.

All additive ALTER … ADD COLUMN; the existing RLS/audit/grants cover the new
columns. No new tables, sequences, or grants.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.qc_results ADD COLUMN source_document_code text")
    op.execute("ALTER TABLE public.qc_results ADD COLUMN source_document_date date")
    op.execute("ALTER TABLE public.qc_results ADD COLUMN source_institution text")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN coq_document_id text")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN coq_generated_at timestamp with time zone")


def downgrade() -> None:
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN coq_generated_at")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN coq_document_id")
    op.execute("ALTER TABLE public.qc_results DROP COLUMN source_institution")
    op.execute("ALTER TABLE public.qc_results DROP COLUMN source_document_date")
    op.execute("ALTER TABLE public.qc_results DROP COLUMN source_document_code")
