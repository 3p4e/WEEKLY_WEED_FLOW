"""QC LIMS U3: certificates of analysis + test results (certification cluster)

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-16

Phase 2 unit 3 — the certification cluster and the join point for the Phase-3
certificate pipeline (the DocEngine renders the release CoA/COQ from these
rows). Native rebuild of the qc-lims-ao CoA + TestResult aggregate.

- `qc_certificates` — one certificate of analysis. Human id `PP-COA-YYYY-NNNN`
  from `qc_coa_id_seq`. Cites a specification (RESTRICT — a CoA must not be
  orphaned from the spec its results were judged against) and OPTIONALLY links
  a physical sample (SET NULL). Lifecycle DRAFT→REVIEWED→APPROVED→RELEASED with
  a PASS/FAIL decision; analyst/reviewer/approver ids carry the GxP roles (the
  API enforces reviewer ≠ analyst).
- `qc_results` — one measured result (CASCADE child). Keeps the raw string
  ("n.d.", "<0.1") AND the numeric; snapshots the limits it was judged against;
  `complies` is computed at entry. A non-complying result quarantines the
  linked sample (the OOS hook), handled in the API.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COA_STATUSES = ("DRAFT", "REVIEWED", "APPROVED", "RELEASED")
_DECISIONS = ("PASS", "FAIL")
_CERT_TYPES = ("ICOA", "ECOA", "COQ", "WATER", "OTHER")
_RESULT_STATUSES = ("pass", "fail", "marginal", "unknown")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE public.qc_coa_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute(
        """
        CREATE TABLE public.qc_certificates (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            coa_number text NOT NULL,
            batch_id text NOT NULL,
            specification_id uuid NOT NULL,
            sample_id uuid,
            report_date date,
            status text DEFAULT 'DRAFT'::text NOT NULL,
            decision text,
            cert_type text DEFAULT 'ICOA'::text NOT NULL,
            source_lab text,
            analyst_id uuid,
            reviewer_id uuid,
            approver_id uuid,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_certificates_pkey PRIMARY KEY (id),
            CONSTRAINT qc_certificates_coa_number_key UNIQUE (org_id, coa_number),
            CONSTRAINT qc_certificates_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_certificates_decision_check CHECK (decision IS NULL OR decision = ANY (ARRAY[%s])),
            CONSTRAINT qc_certificates_cert_type_check CHECK (cert_type = ANY (ARRAY[%s])),
            CONSTRAINT qc_certificates_spec_fkey FOREIGN KEY (specification_id)
                REFERENCES public.qc_specifications(id) ON DELETE RESTRICT,
            CONSTRAINT qc_certificates_sample_fkey FOREIGN KEY (sample_id)
                REFERENCES public.qc_samples(id) ON DELETE SET NULL
        )
        """
        % (
            ",".join(f"'{s}'::text" for s in _COA_STATUSES),
            ",".join(f"'{d}'::text" for d in _DECISIONS),
            ",".join(f"'{t}'::text" for t in _CERT_TYPES),
        )
    )
    op.execute(
        """
        CREATE TABLE public.qc_results (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            coa_id uuid NOT NULL,
            parameter_id uuid,
            test_name text NOT NULL,
            result_value text,
            result_numeric numeric,
            unit text,
            lower_limit numeric,
            upper_limit numeric,
            complies boolean,
            status text DEFAULT 'unknown'::text NOT NULL,
            analyst_id uuid,
            verified_by_id uuid,
            result_date date,
            created_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_results_pkey PRIMARY KEY (id),
            CONSTRAINT qc_results_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_results_coa_fkey FOREIGN KEY (coa_id)
                REFERENCES public.qc_certificates(id) ON DELETE CASCADE,
            CONSTRAINT qc_results_param_fkey FOREIGN KEY (parameter_id)
                REFERENCES public.qc_spec_parameters(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _RESULT_STATUSES)
    )
    for tbl in ("qc_certificates", "qc_results"):
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
        "CREATE INDEX qc_certificates_batch_idx ON public.qc_certificates USING btree (org_id, batch_id)"
    )
    op.execute(
        "CREATE INDEX qc_certificates_spec_idx ON public.qc_certificates USING btree (org_id, specification_id)"
    )
    op.execute(
        "CREATE INDEX qc_results_coa_idx ON public.qc_results USING btree (org_id, coa_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_certificates, public.qc_results TO app_user;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_coa_id_seq TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_certificates, public.qc_results TO app_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_coa_id_seq TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_results")
    op.execute("DROP TABLE public.qc_certificates")
    op.execute("DROP SEQUENCE public.qc_coa_id_seq")
