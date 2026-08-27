"""batch commercial identities — per-batch Original→Neu rename + brand + label

Revision ID: 0059
Revises: 0058
Create Date: 2026-08-14

The owner's Portfolio Master (BCP_PRODUCT_MASTER_FINAL.xlsx ·
01_Portfolio_Master, mirrored at app/data/portfolio_master.json — 78 batches
across 3 tranches) renames strains **per batch**, not per strain: the same
original cultivar maps to different commercial ("Neu") names on different
batches (Cap Junkie → Cookie Kush on CJ052501/01 but → OG Banana's on
CJ062501/2), each with a brand (STEADY/CAYN), a final label, a declared THC%
and a commercial THC bracket. The `cultivars` table cannot express that, so
this is its own table keyed by the batch code string — the same free-text code
QC rows carry in `qc_certificates.batch_id` / `qc_coq.batch_id` (deliberately
no FK: QC batch ids predate plant_batches.code and include external batches).

Owner decision 2026-08-14: full table + API (not read-only reference data).
Purely additive. RLS + app.fn_audit_row() + guarded grants, exactly as 0057.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.batch_commercial_identities (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            batch_code text NOT NULL,
            tranche smallint,
            original_name text,
            neu_name text NOT NULL,
            brand text,
            final_label text,
            thc_declared numeric,
            thc_bracket text,
            volume_kg numeric,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT batch_commercial_identities_pkey PRIMARY KEY (id),
            CONSTRAINT batch_commercial_identities_batch_key UNIQUE (org_id, batch_code),
            CONSTRAINT batch_commercial_identities_thc_check
                CHECK (thc_declared IS NULL OR (thc_declared >= 0 AND thc_declared <= 100)),
            CONSTRAINT batch_commercial_identities_volume_check
                CHECK (volume_kg IS NULL OR volume_kg >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX batch_commercial_identities_tranche_idx"
        " ON public.batch_commercial_identities USING btree (org_id, tranche)"
    )
    op.execute("ALTER TABLE ONLY public.batch_commercial_identities FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.batch_commercial_identities ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.batch_commercial_identities"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_batch_commercial_identities"
        " AFTER INSERT OR DELETE OR UPDATE ON public.batch_commercial_identities"
        " FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.batch_commercial_identities TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.batch_commercial_identities TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.batch_commercial_identities")
