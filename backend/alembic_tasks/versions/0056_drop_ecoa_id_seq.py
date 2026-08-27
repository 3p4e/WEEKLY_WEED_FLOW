"""qc_coa_documents: drop the global qc_ecoa_id_seq (per-org doc numbering, M7)

eCoA document numbers were minted 'PP-ECOA-YYYY-' || nextval('qc_ecoa_id_seq'),
a SINGLE sequence shared across every tenant. That leaked cross-tenant volume (an
org could infer another's upload count from the gaps in its own numbers), never
reset per year, and broke the per-(org, cert_type, year) model every other QC
number series follows (_mint_cert_number). app/api/qc/ecoa.py now mints
doc_number with an advisory-locked per-(org, year) max+1 (ecoa._mint_doc_number),
so the sequence is dead. The UNIQUE constraint on qc_coa_documents is
(org_id, doc_number), so per-org numbering never collides across tenants.

Purely a cleanup of the now-unused object — no table, column, or data change.
Existing 'PP-ECOA-YYYY-NNNN' numbers are untouched and the new minting continues
each org from its own current maximum.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS public.qc_ecoa_id_seq")


def downgrade() -> None:
    op.execute(
        "CREATE SEQUENCE public.qc_ecoa_id_seq"
        " AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1"
    )
