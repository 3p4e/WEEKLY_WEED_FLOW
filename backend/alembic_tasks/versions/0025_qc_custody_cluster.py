"""QC LIMS U5: custody cluster — sampling requests (RQS) + field records (SFR)
+ chain of custody

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-16

Phase 2 unit 5 — the custody cluster: field-to-lab traceability (ALCOA++).
Native rebuild of the qc-lims-ao custody subsystem (models/sampling_request.py,
sfr.py, custody.py) onto the WWF spine.

- `qc_sampling_requests` (RQS, `PP-RQS-YYYY-NNNN`) — a department asks QC to
  sample a material/batch (PP-QC-SOP-017). Lifecycle OPEN→REGISTERED→
  IN_PROGRESS→COMPLETED (+CANCELLED), guarded in the API; a 24-hour QC
  registration window is tracked (`registration_deadline` +
  `registration_window_met`). Produces a `qc_samples` row on completion (SET
  NULL FK).
- `qc_sample_field_records` (SFR, `PP-SFR-YYYY-NNNN`) — a field sampling
  operation: location/GPS, barrel/container numbers (jsonb), destination
  facility, planned/actual departure & arrival, personnel. Lifecycle
  CREATED→IN_FIELD→COMPLETED (+CANCELLED). Optionally cites the RQS (SET NULL)
  and the produced sample (SET NULL).
- `qc_chain_of_custody` — one custody handoff of a sample (from_user→to_user,
  timestamp, from/to location, reason, transfer_type). The ALCOA++ audit trail
  of who held a sample when. CASCADE child of the sample; optionally cites the
  SFR (SET NULL). Append-style — the API only INSERTs.

User references are plain uuid columns (no FK) — identities live in the
separate users DB, exactly like every other `*_id` actor column in this schema.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RQS_STATUSES = ("OPEN", "REGISTERED", "IN_PROGRESS", "COMPLETED", "CANCELLED")
_SFR_STATUSES = ("CREATED", "IN_FIELD", "COMPLETED", "CANCELLED")
_TRANSFER_TYPES = ("FIELD_TO_LAB", "LAB_INTERNAL", "LAB_TO_DISPOSAL", "STABILITY_TRANSFER")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE public.qc_rqs_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute("CREATE SEQUENCE public.qc_sfr_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute(
        """
        CREATE TABLE public.qc_sampling_requests (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            rqs_number text NOT NULL,
            material_code text NOT NULL,
            material_name_en text,
            material_name_mk text,
            batch_id text,
            originating_department text NOT NULL,
            requested_by_id uuid,
            requested_at timestamp with time zone DEFAULT now() NOT NULL,
            assigned_sp_type text,
            status text DEFAULT 'OPEN'::text NOT NULL,
            registered_by_id uuid,
            registered_at timestamp with time zone,
            registration_deadline timestamp with time zone,
            registration_window_met boolean,
            assigned_to_id uuid,
            assigned_at timestamp with time zone,
            completed_at timestamp with time zone,
            sample_id uuid,
            cancelled_by_id uuid,
            cancelled_at timestamp with time zone,
            cancellation_reason text,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_sampling_requests_pkey PRIMARY KEY (id),
            CONSTRAINT qc_sampling_requests_number_key UNIQUE (org_id, rqs_number),
            CONSTRAINT qc_sampling_requests_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_sampling_requests_sample_fkey FOREIGN KEY (sample_id)
                REFERENCES public.qc_samples(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _RQS_STATUSES)
    )
    op.execute(
        """
        CREATE TABLE public.qc_sample_field_records (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            sfr_number text NOT NULL,
            rqs_id uuid,
            sampling_location text NOT NULL,
            sampling_coordinates text,
            barrel_numbers jsonb DEFAULT '[]'::jsonb NOT NULL,
            num_containers integer,
            destination_facility text NOT NULL,
            destination_location text,
            planned_departure timestamp with time zone,
            actual_departure timestamp with time zone,
            planned_arrival timestamp with time zone,
            actual_arrival timestamp with time zone,
            status text DEFAULT 'CREATED'::text NOT NULL,
            sampled_by_id uuid,
            escort_id uuid,
            received_by_id uuid,
            sample_id uuid,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_sample_field_records_pkey PRIMARY KEY (id),
            CONSTRAINT qc_sample_field_records_number_key UNIQUE (org_id, sfr_number),
            CONSTRAINT qc_sample_field_records_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_sample_field_records_rqs_fkey FOREIGN KEY (rqs_id)
                REFERENCES public.qc_sampling_requests(id) ON DELETE SET NULL,
            CONSTRAINT qc_sample_field_records_sample_fkey FOREIGN KEY (sample_id)
                REFERENCES public.qc_samples(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _SFR_STATUSES)
    )
    op.execute(
        """
        CREATE TABLE public.qc_chain_of_custody (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            sample_id uuid NOT NULL,
            from_user_id uuid,
            to_user_id uuid,
            transferred_at timestamp with time zone DEFAULT now() NOT NULL,
            from_location text,
            to_location text,
            transfer_reason text,
            transfer_type text,
            sfr_id uuid,
            created_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_chain_of_custody_pkey PRIMARY KEY (id),
            CONSTRAINT qc_chain_of_custody_type_check
                CHECK (transfer_type IS NULL OR transfer_type = ANY (ARRAY[%s])),
            CONSTRAINT qc_chain_of_custody_sample_fkey FOREIGN KEY (sample_id)
                REFERENCES public.qc_samples(id) ON DELETE CASCADE,
            CONSTRAINT qc_chain_of_custody_sfr_fkey FOREIGN KEY (sfr_id)
                REFERENCES public.qc_sample_field_records(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _TRANSFER_TYPES)
    )
    for tbl in ("qc_sampling_requests", "qc_sample_field_records", "qc_chain_of_custody"):
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
        "CREATE INDEX qc_sampling_requests_status_idx ON public.qc_sampling_requests"
        " USING btree (org_id, status)"
    )
    op.execute(
        "CREATE INDEX qc_sampling_requests_batch_idx ON public.qc_sampling_requests"
        " USING btree (org_id, batch_id)"
    )
    op.execute(
        "CREATE INDEX qc_sample_field_records_status_idx ON public.qc_sample_field_records"
        " USING btree (org_id, status)"
    )
    op.execute(
        "CREATE INDEX qc_chain_of_custody_sample_idx ON public.qc_chain_of_custody"
        " USING btree (org_id, sample_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_sampling_requests,
                public.qc_sample_field_records, public.qc_chain_of_custody TO app_user;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_rqs_id_seq, public.qc_sfr_id_seq TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_sampling_requests,
                public.qc_sample_field_records, public.qc_chain_of_custody TO app_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_rqs_id_seq, public.qc_sfr_id_seq TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_chain_of_custody")
    op.execute("DROP TABLE public.qc_sample_field_records")
    op.execute("DROP TABLE public.qc_sampling_requests")
    op.execute("DROP SEQUENCE public.qc_sfr_id_seq")
    op.execute("DROP SEQUENCE public.qc_rqs_id_seq")
