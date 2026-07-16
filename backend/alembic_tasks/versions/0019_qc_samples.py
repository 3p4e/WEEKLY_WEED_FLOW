"""QC LIMS U2: sampling plans + samples (physical-sample cluster)

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-16

Phase 2 unit 2 — the physical-sample aggregate root and its lifecycle. Native
rebuild of the qc-lims-ao Sample model on the WWF spine (facility pattern).

- `qc_sampling_plans` — how a material is sampled (frequency, size formula).
  Human id `PP-SPL-YYYY-NNNN` from `qc_sampling_plan_id_seq`.
- `qc_samples` — one physical sample. Human id `PP-SMP-YYYY-NNNN` from
  `qc_sample_id_seq`. The vision's fuller state machine (COLLECTED → IN_TRANSIT
  → RECEIVED → IN_TEST → TESTED → REVIEWED → APPROVED → RELEASED, plus terminal
  REJECTED and the OOS branch QUARANTINE) — the CHECK lists every state; the
  legal transitions are enforced in-app (qc.py). Self-FK `parent_id` carries
  sample genealogy (sub-batches / retests); ON DELETE SET NULL so removing a
  parent never cascades away its children's records. `sampling_plan_id` FK is
  SET NULL for the same reason.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SAMPLE_STATUSES = (
    "COLLECTED", "IN_TRANSIT", "RECEIVED", "IN_TEST", "TESTED",
    "REVIEWED", "APPROVED", "RELEASED", "REJECTED", "QUARANTINE",
)
_FREQUENCIES = ("EVERY_BATCH", "PERIODIC", "RANDOM")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE public.qc_sampling_plan_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute("CREATE SEQUENCE public.qc_sample_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute(
        """
        CREATE TABLE public.qc_sampling_plans (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            plan_id text NOT NULL,
            material_code text NOT NULL,
            sampling_frequency text DEFAULT 'EVERY_BATCH'::text NOT NULL,
            sample_size_formula text DEFAULT 'ROUNDUP(SQRT(N)*1.5)'::text NOT NULL,
            min_sample_size integer,
            max_sample_size integer,
            active boolean DEFAULT true NOT NULL,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_sampling_plans_pkey PRIMARY KEY (id),
            CONSTRAINT qc_sampling_plans_plan_id_key UNIQUE (org_id, plan_id),
            CONSTRAINT qc_sampling_plans_freq_check CHECK (sampling_frequency = ANY (ARRAY[%s]))
        )
        """
        % ",".join(f"'{f}'::text" for f in _FREQUENCIES)
    )
    op.execute(
        """
        CREATE TABLE public.qc_samples (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            sample_id text NOT NULL,
            batch_id text NOT NULL,
            sample_type text,
            material_code text NOT NULL,
            material_name_en text,
            material_name_mk text,
            sampling_date date,
            status text DEFAULT 'COLLECTED'::text NOT NULL,
            location text,
            quantity numeric,
            quantity_unit text,
            retention_sample boolean DEFAULT false NOT NULL,
            parent_id uuid,
            sampling_plan_id uuid,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_samples_pkey PRIMARY KEY (id),
            CONSTRAINT qc_samples_sample_id_key UNIQUE (org_id, sample_id),
            CONSTRAINT qc_samples_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_samples_parent_fkey FOREIGN KEY (parent_id)
                REFERENCES public.qc_samples(id) ON DELETE SET NULL,
            CONSTRAINT qc_samples_plan_fkey FOREIGN KEY (sampling_plan_id)
                REFERENCES public.qc_sampling_plans(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _SAMPLE_STATUSES)
    )
    for tbl in ("qc_sampling_plans", "qc_samples"):
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
        "CREATE INDEX qc_samples_batch_idx ON public.qc_samples USING btree (org_id, batch_id)"
    )
    op.execute(
        "CREATE INDEX qc_samples_status_idx ON public.qc_samples USING btree (org_id, status)"
    )
    op.execute(
        "CREATE INDEX qc_samples_parent_idx ON public.qc_samples USING btree (org_id, parent_id)"
        " WHERE parent_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX qc_sampling_plans_material_idx ON public.qc_sampling_plans"
        " USING btree (org_id, material_code) WHERE active"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_sampling_plans, public.qc_samples TO app_user;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_sampling_plan_id_seq, public.qc_sample_id_seq TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_sampling_plans, public.qc_samples TO app_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_sampling_plan_id_seq, public.qc_sample_id_seq TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_samples")
    op.execute("DROP TABLE public.qc_sampling_plans")
    op.execute("DROP SEQUENCE public.qc_sample_id_seq")
    op.execute("DROP SEQUENCE public.qc_sampling_plan_id_seq")
