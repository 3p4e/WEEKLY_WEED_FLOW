"""qc_oos_records: drop the global qc_oos_id_seq (per-org OOS numbering, M7)

OOS numbers were minted 'PP-OOS-YYYY-' || lpad(nextval('qc_oos_id_seq')::text,
4, '0'), a SINGLE sequence shared across every tenant. That leaked cross-tenant
volume (an org's own OOS numbers showed gaps caused purely by OTHER orgs'
investigations, letting a tenant infer another tenant's investigation
volume/cadence from its own gap size), never reset per year, and broke the
per-(org, year) model every other QC number series follows (_mint_doc_number,
_mint_cert_number). app/api/qc/oos.py now mints oos_number with an
advisory-locked per-(org, year) max+1 (oos._mint_oos_number), so the sequence
is dead. The UNIQUE constraint on qc_oos_records is (org_id, oos_number), so
per-org numbering never collides across tenants.

Purely a cleanup of the now-unused object — no table, column, or data change.
Existing 'PP-OOS-YYYY-NNNN' numbers are untouched and the new minting
continues each org from its own current maximum.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS public.qc_oos_id_seq")


def downgrade() -> None:
    op.execute(
        "CREATE SEQUENCE public.qc_oos_id_seq"
        " AS integer START WITH 1 INCREMENT BY 1"
    )
