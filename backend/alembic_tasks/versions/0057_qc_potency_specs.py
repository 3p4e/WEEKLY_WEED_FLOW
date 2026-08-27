"""qc potency specifications — per-cultivar THC grade ladders (PP-QC-SPEC-001)

Revision ID: 0057
Revises: 0056
Create Date: 2026-08-07

PP-QC-SPEC-001 v5.2 (variant A) grades a batch on **Total Δ9-THC** (= Δ9-THC +
0.877 × Δ9-THCA) against a ladder that is **specific to each cultivar**, not a
single global table. Per strain: floor = the strain's lowest observed batch −
1.00 pp; the span [floor, 30 %] is cut into 2–4 specifications; **Spec I is the
top range (up to 30 %)**, descending II/III/IV; each carries a 2-decimal range, a
width (pp) and a nominal declared on nn.0/nn.5. A strain with ≥3 batches is
"data-supported"; with <3 it is "provisional" (floor/width from the observed
value + analytical minimum, to be reviewed once a third batch exists).

The owner's decision (2026-08-07) is that these ladders are **stored, approved
spec data** — authored and APPROVED by a human, read as-is when a certificate is
issued — NOT recomputed on the fly. So this models them the same controlled way
`qc_specifications` models material specs: a versioned parent
(`qc_potency_specs`, one APPROVED row per cultivar at a time) with child tier
rows (`qc_potency_spec_ranges`). Disposition (which Spec a batch falls in) is a
read against the APPROVED ladder, handled in the API, not here.

Purely additive: two new tables, nothing existing altered. RLS + the
app.fn_audit_row() trigger + the guarded grant block, exactly as 0051–0053.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("qc_potency_specs", "qc_potency_spec_ranges")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.qc_potency_specs (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            cultivar_id uuid NOT NULL,
            spec_code text DEFAULT 'PP-QC-SPEC-001'::text NOT NULL,
            version text NOT NULL,
            variant text,
            basis text DEFAULT 'total_d9_thc'::text NOT NULL,
            floor_pct numeric NOT NULL,
            observed_min numeric,
            observed_max numeric,
            n_batches integer DEFAULT 0 NOT NULL,
            data_supported boolean DEFAULT false NOT NULL,
            status text DEFAULT 'DRAFT'::text NOT NULL,
            effective_date date,
            approved_by uuid,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_potency_specs_pkey PRIMARY KEY (id),
            CONSTRAINT qc_potency_specs_cultivar_fkey FOREIGN KEY (cultivar_id)
                REFERENCES public.cultivars(id) ON DELETE RESTRICT,
            CONSTRAINT qc_potency_specs_status_check
                CHECK (status = ANY (ARRAY['DRAFT'::text, 'APPROVED'::text, 'SUPERSEDED'::text])),
            CONSTRAINT qc_potency_specs_basis_check CHECK (basis = 'total_d9_thc'::text),
            CONSTRAINT qc_potency_specs_floor_check CHECK (floor_pct >= 0 AND floor_pct <= 30),
            CONSTRAINT qc_potency_specs_n_check CHECK (n_batches >= 0),
            CONSTRAINT qc_potency_specs_version_key UNIQUE (org_id, cultivar_id, version)
        )
        """
    )
    # One APPROVED ladder per cultivar at a time (mirrors qc_specifications'
    # one-ACTIVE-per-material rule) — the disposition read must be unambiguous.
    op.execute(
        "CREATE UNIQUE INDEX qc_potency_specs_one_approved_idx ON public.qc_potency_specs"
        " USING btree (org_id, cultivar_id) WHERE status = 'APPROVED'"
    )

    op.execute(
        """
        CREATE TABLE public.qc_potency_spec_ranges (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            potency_spec_id uuid NOT NULL,
            tier smallint NOT NULL,
            range_min numeric NOT NULL,
            range_max numeric NOT NULL,
            nominal numeric NOT NULL,
            width_pp numeric,
            n_batches integer DEFAULT 0 NOT NULL,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_potency_spec_ranges_pkey PRIMARY KEY (id),
            CONSTRAINT qc_potency_spec_ranges_spec_fkey FOREIGN KEY (potency_spec_id)
                REFERENCES public.qc_potency_specs(id) ON DELETE CASCADE,
            -- tier 1 = Spec I (the top range, up to 30 %), descending to IV/V.
            CONSTRAINT qc_potency_spec_ranges_tier_check CHECK (tier >= 1 AND tier <= 6),
            CONSTRAINT qc_potency_spec_ranges_range_check CHECK (range_max > range_min),
            CONSTRAINT qc_potency_spec_ranges_tier_key UNIQUE (potency_spec_id, tier)
        )
        """
    )
    op.execute(
        "CREATE INDEX qc_potency_spec_ranges_spec_idx ON public.qc_potency_spec_ranges"
        " USING btree (potency_spec_id, tier)"
    )

    for tbl in _NEW_TABLES:
        op.execute(f"ALTER TABLE ONLY public.{tbl} FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY org_isolation ON public.{tbl}"
            f" USING ((org_id = app.current_org_id()))"
            f" WITH CHECK ((org_id = app.current_org_id()))"
        )
        op.execute(
            f"CREATE TRIGGER audit_{tbl} AFTER INSERT OR DELETE OR UPDATE ON public.{tbl}"
            f" FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
        )

    op.execute(
        """
        DO $$
        DECLARE t text;
        BEGIN
          FOREACH t IN ARRAY ARRAY['qc_potency_specs','qc_potency_spec_ranges'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
              EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO app_user', t);
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
              EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO app_admin', t);
            END IF;
          END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_potency_spec_ranges")
    op.execute("DROP TABLE public.qc_potency_specs")
