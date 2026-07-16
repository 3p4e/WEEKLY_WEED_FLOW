"""QC LIMS U1: specifications + spec parameters (master data)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-16

Phase 2 (QC LIMS), unit 1 — the master-data foundation everything downstream
references (CoA cites a spec; a result is judged against a spec parameter).
Native rebuild of the qc-lims-ao prototype's Specification aggregate on the
WWF spine: same org-isolation RLS + hash-chained audit trigger + guarded
grants as facility (0015). GMP zone — surfaced under QMS Studio, role-gated in
the API (read = elevated; write = QC_MGR / QP / execs / ADMIN).

- `qc_specifications` — one controlled specification version. Human id
  `PP-SPEC-YYYY-NNNN` from `qc_spec_id_seq` (stamped at insert). The 8-stage
  lifecycle (INITIATED→DRAFT→QC_REVIEW→QA_APPROVED→NUMBERED→TRAINED→ACTIVE→
  UNDER_CHANGE) plus terminal SUPERSEDED/WITHDRAWN. UNIQUE(org, material,
  version); a PARTIAL UNIQUE INDEX enforces at most one ACTIVE spec per
  (org, material_code) — the prototype's dual-activation guard.
- `qc_spec_parameters` — the per-test acceptance criteria (CASCADE child).
  Limits are numeric and NULLABLE: an unknown limit stays blank for a human,
  never fabricated.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SPEC_STATUSES = (
    "INITIATED", "DRAFT", "QC_REVIEW", "QA_APPROVED", "NUMBERED",
    "TRAINED", "ACTIVE", "UNDER_CHANGE", "SUPERSEDED", "WITHDRAWN",
)
_THC_GRADES = ("GRADE_I", "GRADE_II", "GRADE_III", "GRADE_IV", "GRADE_V")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE public.qc_spec_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute(
        """
        CREATE TABLE public.qc_specifications (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            spec_id text NOT NULL,
            material_code text NOT NULL,
            material_name_en text NOT NULL,
            material_name_mk text,
            version integer DEFAULT 1 NOT NULL,
            effective_date date,
            status text DEFAULT 'DRAFT'::text NOT NULL,
            thc_grade text,
            thc_acceptance_min numeric,
            thc_acceptance_max numeric,
            notes text,
            approved_by uuid,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_specifications_pkey PRIMARY KEY (id),
            CONSTRAINT qc_specifications_spec_id_key UNIQUE (org_id, spec_id),
            CONSTRAINT qc_specifications_material_version_key UNIQUE (org_id, material_code, version),
            CONSTRAINT qc_specifications_version_check CHECK (version >= 1),
            CONSTRAINT qc_specifications_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_specifications_thc_grade_check CHECK (thc_grade IS NULL OR thc_grade = ANY (ARRAY[%s]))
        )
        """
        % (
            ",".join(f"'{s}'::text" for s in _SPEC_STATUSES),
            ",".join(f"'{g}'::text" for g in _THC_GRADES),
        )
    )
    op.execute(
        """
        CREATE TABLE public.qc_spec_parameters (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            spec_id uuid NOT NULL,
            test_name_en text NOT NULL,
            test_name_mk text,
            test_method text,
            spec_type text,
            lower_limit numeric,
            upper_limit numeric,
            unit text,
            pharmacopoeia_ref text,
            test_location text,
            sorting_order integer DEFAULT 0 NOT NULL,
            created_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_spec_parameters_pkey PRIMARY KEY (id),
            CONSTRAINT qc_spec_parameters_spec_fkey FOREIGN KEY (spec_id)
                REFERENCES public.qc_specifications(id) ON DELETE CASCADE
        )
        """
    )
    for tbl in ("qc_specifications", "qc_spec_parameters"):
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
    # One ACTIVE spec per material (the prototype's dual-activation guard).
    op.execute(
        "CREATE UNIQUE INDEX qc_specifications_one_active_idx ON public.qc_specifications"
        " USING btree (org_id, material_code) WHERE (status = 'ACTIVE'::text)"
    )
    op.execute(
        "CREATE INDEX qc_specifications_material_idx ON public.qc_specifications"
        " USING btree (org_id, material_code)"
    )
    op.execute(
        "CREATE INDEX qc_spec_parameters_spec_idx ON public.qc_spec_parameters"
        " USING btree (org_id, spec_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_specifications, public.qc_spec_parameters TO app_user;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_spec_id_seq TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_specifications, public.qc_spec_parameters TO app_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_spec_id_seq TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_spec_parameters")
    op.execute("DROP TABLE public.qc_specifications")
    op.execute("DROP SEQUENCE public.qc_spec_id_seq")
