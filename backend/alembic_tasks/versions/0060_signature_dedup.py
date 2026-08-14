"""qc_signatures: one signature per (object, meaning, signer)

Revision ID: 0060
Revises: 0059
Create Date: 2026-08-14

qc_signatures had only its primary key — the same person could apply the same
Annex-11 meaning to the same certificate any number of times, and every
duplicate rendered as another signatory row on the CoQ. A signature asserts a
fact ("this person approved this record"); asserting it twice adds no fact and
bloats the signature table on a controlled document. The partial-free unique
index below makes the duplicate a 409 at the API instead.

Deliberately NOT unique on (object, meaning) alone: two DIFFERENT people may
both sign REVIEWED (a re-review after a kick-back is a real event), and the
handoff's 3-tier iCoA chain has three different people signing three different
meanings. Only the exact triplicate is nonsense.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Duplicates may already exist (nothing prevented them); keep the FIRST of
    # each group and drop the rest, so the unique index can build. The audit
    # trail (audit_log) retains every original INSERT.
    op.execute(
        """
        DELETE FROM public.qc_signatures s
        USING public.qc_signatures keep
        WHERE s.org_id = keep.org_id
          AND s.object_type = keep.object_type
          AND s.object_id = keep.object_id
          AND s.meaning = keep.meaning
          AND s.signer_id IS NOT DISTINCT FROM keep.signer_id
          AND s.id <> keep.id
          AND (keep.signed_at, keep.id) < (s.signed_at, s.id)
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX qc_signatures_unique_meaning_idx ON public.qc_signatures"
        " USING btree (org_id, object_type, object_id, meaning, signer_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX public.qc_signatures_unique_meaning_idx")
