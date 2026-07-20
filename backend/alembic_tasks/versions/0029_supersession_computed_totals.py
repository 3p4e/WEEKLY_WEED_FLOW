"""URS alignment: certificate supersession chain + computed total THC/CBD.

Revision ID: 0029
Revises: 0028
Create Date: 2026-07-20

Two items from docs/URS-COQ-GAP-ANALYSIS-2026-07.md:

- QCSOP 012 §6.7 supersession: an approved certificate is immutable — any
  change is a NEW certificate with a new number carrying `supersedes_id` +
  `revision_reason`; when the revision is RELEASED the original moves to the
  new terminal status SUPERSEDED (never deleted).
- Ph. Eur. monograph 3028 derived parameters: a spec parameter may be flagged
  `computed_kind` (total_thc / total_cbd) with explicit links to its two
  component parameters (a = neutral form, b = acid form; the engine computes
  a + 0.877 × b deterministically at COQ compile time — computed, never
  transcribed).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE qc_certificates ADD COLUMN supersedes_id uuid REFERENCES qc_certificates(id)")
    op.execute("ALTER TABLE qc_certificates ADD COLUMN revision_reason text")
    op.execute("ALTER TABLE qc_certificates DROP CONSTRAINT qc_certificates_status_check")
    op.execute(
        "ALTER TABLE qc_certificates ADD CONSTRAINT qc_certificates_status_check"
        " CHECK ((status = ANY (ARRAY['DRAFT'::text, 'REVIEWED'::text, 'APPROVED'::text,"
        " 'RELEASED'::text, 'SUPERSEDED'::text])))")
    op.execute("ALTER TABLE qc_spec_parameters ADD COLUMN computed_kind text")
    op.execute("ALTER TABLE qc_spec_parameters ADD COLUMN component_a_id uuid REFERENCES qc_spec_parameters(id)")
    op.execute("ALTER TABLE qc_spec_parameters ADD COLUMN component_b_id uuid REFERENCES qc_spec_parameters(id)")
    op.execute(
        "ALTER TABLE qc_spec_parameters ADD CONSTRAINT qc_spec_parameters_computed_kind_check"
        " CHECK (((computed_kind IS NULL) OR (computed_kind = ANY (ARRAY['total_thc'::text,"
        " 'total_cbd'::text]))))")


def downgrade() -> None:
    op.execute("ALTER TABLE qc_spec_parameters DROP CONSTRAINT qc_spec_parameters_computed_kind_check")
    op.execute("ALTER TABLE qc_spec_parameters DROP COLUMN component_b_id")
    op.execute("ALTER TABLE qc_spec_parameters DROP COLUMN component_a_id")
    op.execute("ALTER TABLE qc_spec_parameters DROP COLUMN computed_kind")
    op.execute("ALTER TABLE qc_certificates DROP CONSTRAINT qc_certificates_status_check")
    op.execute(
        "ALTER TABLE qc_certificates ADD CONSTRAINT qc_certificates_status_check"
        " CHECK ((status = ANY (ARRAY['DRAFT'::text, 'REVIEWED'::text, 'APPROVED'::text,"
        " 'RELEASED'::text])))")
    op.execute("ALTER TABLE qc_certificates DROP COLUMN revision_reason")
    op.execute("ALTER TABLE qc_certificates DROP COLUMN supersedes_id")
