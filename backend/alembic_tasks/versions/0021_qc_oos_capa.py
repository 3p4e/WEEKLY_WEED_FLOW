"""QC LIMS U4: out-of-specification investigations + CAPA (deviation cluster)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-16

Phase 2 unit 4 — the deviation cluster. Native rebuild of the qc-lims-ao OOS
subsystem (models/oos.py) onto the WWF spine. A failing `qc_results` row (U3)
is the trigger: the analyst opens an OOS investigation that runs the GxP
two-phase flow (Phase I laboratory investigation → Phase II full/root-cause
investigation → QP disposition → close).

- `qc_oos_records` — one OOS/OOT/OOE/OOC investigation. Human id
  `PP-OOS-YYYY-NNNN` from `qc_oos_id_seq`. OPTIONALLY cites the triggering
  result (SET NULL) and the sample (SET NULL); phase/status lifecycle guarded
  in the API; disposition (RELEASE/REJECT/REPROCESS/RETAIN) is a QP decision.
- `qc_oos_register` — an append-only event log (one row per event). The
  prototype's "ONCE WRITTEN, NEVER MODIFIED" register; the API only ever
  INSERTs. CASCADE child of the OOS record.
- `qc_oos_notifications` — Part A/B/C/D regulatory/internal notifications with
  an acknowledgement flag. CASCADE child.

CAPA is NOT a table: it is derived at read time from the OOS rows (matching
the prototype's api/capa.py, which synthesises the CAPA register from OOS
state) — the only durable CAPA data are the root-cause / impact /
effectiveness / capa_reference columns on `qc_oos_records`.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OOS_TYPES = ("OOS", "OOT", "OOE", "OOC")
_OOS_RISK = ("HIGH", "MEDIUM", "LOW")
_OOS_PHASES = ("I", "II")
_OOS_STATUSES = ("OPEN", "PHASE_I", "PHASE_II", "CLOSED")
_OOS_DISPOSITIONS = ("RELEASE", "REJECT", "REPROCESS", "RETAIN")
_OOS_NOTIF_PARTS = ("A", "B", "C", "D")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE public.qc_oos_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute(
        """
        CREATE TABLE public.qc_oos_records (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            oos_number text NOT NULL,
            result_id uuid,
            sample_id uuid,
            batch_id text NOT NULL,
            material_code text,
            test_name text,
            method_ref text,
            specification_value text,
            obtained_value text,
            oos_type text DEFAULT 'OOS'::text NOT NULL,
            risk_level text,
            phase text DEFAULT 'I'::text NOT NULL,
            status text DEFAULT 'OPEN'::text NOT NULL,
            detection_date date,
            detected_by_id uuid,
            timeline_deadline date,
            lab_investigation_result text,
            lab_error boolean DEFAULT false NOT NULL,
            invalidated boolean DEFAULT false NOT NULL,
            retest_result text,
            phase_i_completed_at timestamp with time zone,
            phase_i_completed_by_id uuid,
            root_cause_category text,
            root_cause_description text,
            impact_assessment text,
            capa_reference text,
            effectiveness_check_date date,
            effectiveness_check_result text,
            phase_ii_completed_at timestamp with time zone,
            phase_ii_completed_by_id uuid,
            disposition text,
            disposition_reason text,
            qp_approved_at timestamp with time zone,
            qp_approved_by_id uuid,
            closed_at timestamp with time zone,
            closed_by_id uuid,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_oos_records_pkey PRIMARY KEY (id),
            CONSTRAINT qc_oos_records_number_key UNIQUE (org_id, oos_number),
            CONSTRAINT qc_oos_records_type_check CHECK (oos_type = ANY (ARRAY[%s])),
            CONSTRAINT qc_oos_records_risk_check CHECK (risk_level IS NULL OR risk_level = ANY (ARRAY[%s])),
            CONSTRAINT qc_oos_records_phase_check CHECK (phase = ANY (ARRAY[%s])),
            CONSTRAINT qc_oos_records_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_oos_records_disposition_check
                CHECK (disposition IS NULL OR disposition = ANY (ARRAY[%s])),
            CONSTRAINT qc_oos_records_result_fkey FOREIGN KEY (result_id)
                REFERENCES public.qc_results(id) ON DELETE SET NULL,
            CONSTRAINT qc_oos_records_sample_fkey FOREIGN KEY (sample_id)
                REFERENCES public.qc_samples(id) ON DELETE SET NULL
        )
        """
        % (
            ",".join(f"'{s}'::text" for s in _OOS_TYPES),
            ",".join(f"'{s}'::text" for s in _OOS_RISK),
            ",".join(f"'{s}'::text" for s in _OOS_PHASES),
            ",".join(f"'{s}'::text" for s in _OOS_STATUSES),
            ",".join(f"'{s}'::text" for s in _OOS_DISPOSITIONS),
        )
    )
    op.execute(
        """
        CREATE TABLE public.qc_oos_register (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            oos_id uuid NOT NULL,
            action text NOT NULL,
            actor_id uuid,
            details text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_oos_register_pkey PRIMARY KEY (id),
            CONSTRAINT qc_oos_register_oos_fkey FOREIGN KEY (oos_id)
                REFERENCES public.qc_oos_records(id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.qc_oos_notifications (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            oos_id uuid NOT NULL,
            part text NOT NULL,
            recipients jsonb DEFAULT '[]'::jsonb NOT NULL,
            message text,
            acknowledged boolean DEFAULT false NOT NULL,
            acknowledged_at timestamp with time zone,
            sent_by_id uuid,
            sent_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_oos_notifications_pkey PRIMARY KEY (id),
            CONSTRAINT qc_oos_notifications_part_check CHECK (part = ANY (ARRAY[%s])),
            CONSTRAINT qc_oos_notifications_oos_fkey FOREIGN KEY (oos_id)
                REFERENCES public.qc_oos_records(id) ON DELETE CASCADE
        )
        """
        % ",".join(f"'{s}'::text" for s in _OOS_NOTIF_PARTS)
    )
    for tbl in ("qc_oos_records", "qc_oos_register", "qc_oos_notifications"):
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
        "CREATE INDEX qc_oos_records_batch_idx ON public.qc_oos_records USING btree (org_id, batch_id)"
    )
    op.execute(
        "CREATE INDEX qc_oos_records_status_idx ON public.qc_oos_records USING btree (org_id, status)"
    )
    op.execute(
        "CREATE INDEX qc_oos_register_oos_idx ON public.qc_oos_register USING btree (org_id, oos_id)"
    )
    op.execute(
        "CREATE INDEX qc_oos_notifications_oos_idx ON public.qc_oos_notifications USING btree (org_id, oos_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_oos_records, public.qc_oos_register,
                public.qc_oos_notifications TO app_user;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_oos_id_seq TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_oos_records, public.qc_oos_register,
                public.qc_oos_notifications TO app_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_oos_id_seq TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_oos_notifications")
    op.execute("DROP TABLE public.qc_oos_register")
    op.execute("DROP TABLE public.qc_oos_records")
    op.execute("DROP SEQUENCE public.qc_oos_id_seq")
