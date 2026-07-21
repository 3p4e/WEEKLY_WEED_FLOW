"""D1 CoQ layout parity: certificate metadata for the house Certificate-of-Quality

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-21

The approved house Certificate of Quality (CoQ_Template_v02_VariationF) carries
a richer product/identity meta grid than the model held: an upstream cultivation
batch distinct from the production batch, a packaged product code, the packaging
(dosage form), the manufacturing / packaging / expiry / retest dates, and the
botanical classification (type + chemotype). These are certificate-level facts a
QC user records; the CoQ renderer surfaces each when present and simply omits it
when absent.

All additive ALTER … ADD COLUMN — nullable, no CHECK (free-text / dates). GxP:
an unknown value stays NULL for a human; the renderer never fabricates one. The
existing RLS/audit trigger/grants on qc_certificates cover the new columns. No
new tables, sequences, or grants.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN cultivation_batch text")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN product_code text")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN packaging text")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN packaging_date date")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN manufacture_date date")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN expiry_date date")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN retest_date date")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN botanical_type text")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN chemotype text")


def downgrade() -> None:
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN chemotype")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN botanical_type")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN retest_date")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN expiry_date")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN manufacture_date")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN packaging_date")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN packaging")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN product_code")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN cultivation_batch")
