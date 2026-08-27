"""URS alignment: capture the lab's stated verdict on eCoA extractions.

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-20

QCSOP 012 §6.3.2 (and the Head-of-QC URS, docs/URS-COQ-GAP-ANALYSIS-2026-07.md
item 8): conformance is determined by Purely Plant and never taken from the
eCoA — but the lab's own stated pass/fail should be CAPTURED as reference and
reconciled against the in-house determination, so a disagreement is visible
instead of silently discarded. `lab_verdict` stores the verdict verbatim as it
appears on the source certificate; it is reference-only and never feeds the
`complies` computation.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE qc_coa_extractions ADD COLUMN lab_verdict text")


def downgrade() -> None:
    op.execute("ALTER TABLE qc_coa_extractions DROP COLUMN lab_verdict")
