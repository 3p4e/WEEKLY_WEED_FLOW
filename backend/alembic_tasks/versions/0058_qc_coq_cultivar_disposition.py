"""qc_coq: cultivar link + frozen potency-ladder reference (Phase B)

Revision ID: 0058
Revises: 0057
Create Date: 2026-08-07

A Certificate of Quality grades its batch on Total Δ9-THC against the cultivar's
approved potency ladder (PP-QC-SPEC-001, migration 0057). To carry that grade,
the CoQ must know WHICH cultivar it is for and WHICH ladder version graded it.

Two nullable columns on qc_coq (nullable — a CoQ compiled before a cultivar is
mapped, or before an approved ladder exists, simply carries no grade; GxP never
invents one):
  • cultivar_id     the cultivar this batch is, FK cultivars ON DELETE RESTRICT.
  • potency_spec_id the APPROVED ladder version FROZEN at compile time, FK
                    qc_potency_specs ON DELETE RESTRICT. Freezing the version (not
                    re-resolving live) makes the printed grade stable and traceable
                    even after the ladder is later superseded.

Purely additive columns on an existing table — qc_coq already carries RLS +
the audit trigger + grants, so nothing else changes. The test/prod org purge
already deletes qc_coq before both cultivars and qc_potency_specs, so the two
RESTRICT edges are satisfied.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.qc_coq"
        " ADD COLUMN cultivar_id uuid,"
        " ADD COLUMN potency_spec_id uuid,"
        " ADD CONSTRAINT qc_coq_cultivar_fkey FOREIGN KEY (cultivar_id)"
        "   REFERENCES public.cultivars(id) ON DELETE RESTRICT,"
        " ADD CONSTRAINT qc_coq_potency_spec_fkey FOREIGN KEY (potency_spec_id)"
        "   REFERENCES public.qc_potency_specs(id) ON DELETE RESTRICT"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.qc_coq"
        " DROP COLUMN potency_spec_id,"
        " DROP COLUMN cultivar_id"
    )
