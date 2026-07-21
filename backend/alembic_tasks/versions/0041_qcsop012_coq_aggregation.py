"""QCSOP 012 v3 — CoQ per-batch aggregation (C5) + iCoA field/language polish (C6/C7)

Revision ID: 0041
Revises: 0040
Create Date: 2026-07-21

The structural half of the QCSOP 012 alignment: the Certificate of Quality
becomes what §6.4 defines — a per-BATCH aggregation record consolidating every
iCoA + eCoA result against the approved specification, compiled and reviewed
INSIDE QC (Compiled by → Reviewed and Approved by HoQC, no QP signature), as an
input TO the QP batch-release decision. Coexists with the established
single-certificate CoQ render (nothing that works today is removed).

- qc_coq          — the aggregation record (per batch): CoQ number, batch
                    identification (§6.4.2: batch, product, manufacture date,
                    batch size), spec ref+version snapshot, compiled/reviewed
                    signatures, DRAFT→APPROVED (+VOIDED) lifecycle, and the
                    rendered-.docx pointer.
- qc_coq_sources  — the §6.4.2 source-certificate list: one row per iCoA/eCoA
                    certificate that contributed data, with its cited number,
                    type, and issue-date snapshot (immutable citation even if
                    the cert is later superseded).
- qc_coq_lines    — the §6.4.2 aggregated results table: ONE ROW PER SPEC
                    PARAMETER citing its source certificate + testing lab.

- qc_certificates — C6 (§6.2.2): analysis_start_date/analysis_end_date (the
                    SOP wants a date RANGE, not one report date) +
                    sampling_location echoed onto the certificate itself.
                    C7 (§6.7): issue_language (EN primary / EN-MK bilingual;
                    default EN-MK preserves current renderer behaviour) +
                    translation second-reviewer verification capture.

Facility canon throughout (uuid PK + org_id, FORCE/ENABLE RLS org_isolation,
audit triggers, guarded GRANTs). All additive; new NOT NULL columns carry
defaults. GxP: unknown values stay NULL for a human, never fabricated.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _canon(table: str, extra_indexes: list[str] | None = None) -> None:
    op.execute(f"ALTER TABLE ONLY public.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY org_isolation ON public.{table}"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        f"CREATE TRIGGER audit_{table} AFTER INSERT OR DELETE OR UPDATE"
        f" ON public.{table} FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    for idx in (extra_indexes or []):
        op.execute(idx)
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table} TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table} TO app_admin;
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    # ── C5 — qc_coq (the per-batch aggregation record)
    op.execute(
        """
        CREATE TABLE public.qc_coq (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            coq_number text NOT NULL,
            batch_id text NOT NULL,
            product_name text,
            manufacture_date date,
            batch_size text,
            specification_id uuid NOT NULL,
            spec_reference text,
            status text DEFAULT 'DRAFT'::text NOT NULL,
            overall_conform boolean,
            comments text,
            oos_reference text,
            compiled_by uuid,
            compiled_at timestamp with time zone,
            reviewed_by uuid,
            reviewed_at timestamp with time zone,
            void_reason text,
            voided_by uuid,
            voided_at timestamp with time zone,
            coq_document_id text,
            coq_generated_at timestamp with time zone,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_coq_pkey PRIMARY KEY (id),
            CONSTRAINT qc_coq_status_check CHECK (status = ANY
                (ARRAY['DRAFT'::text, 'APPROVED'::text, 'VOIDED'::text])),
            CONSTRAINT qc_coq_spec_fkey FOREIGN KEY (specification_id)
                REFERENCES public.qc_specifications(id) ON DELETE RESTRICT
        )
        """
    )
    _canon("qc_coq", [
        "CREATE INDEX qc_coq_batch_idx ON public.qc_coq USING btree (org_id, batch_id)",
    ])

    # ── C5 — qc_coq_sources (source-certificate citation list)
    op.execute(
        """
        CREATE TABLE public.qc_coq_sources (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            coq_id uuid NOT NULL,
            coa_id uuid NOT NULL,
            coa_number text NOT NULL,
            cert_type text,
            issue_date date,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_coq_sources_pkey PRIMARY KEY (id),
            CONSTRAINT qc_coq_sources_coq_fkey FOREIGN KEY (coq_id)
                REFERENCES public.qc_coq(id) ON DELETE CASCADE,
            CONSTRAINT qc_coq_sources_coa_fkey FOREIGN KEY (coa_id)
                REFERENCES public.qc_certificates(id) ON DELETE RESTRICT,
            CONSTRAINT qc_coq_sources_unique UNIQUE (org_id, coq_id, coa_id)
        )
        """
    )
    _canon("qc_coq_sources", [
        "CREATE INDEX qc_coq_sources_coq_idx ON public.qc_coq_sources USING btree (org_id, coq_id)",
    ])

    # ── C5 — qc_coq_lines (one row per spec parameter, citing its source)
    op.execute(
        """
        CREATE TABLE public.qc_coq_lines (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            coq_id uuid NOT NULL,
            parameter_id uuid,
            parameter_name text NOT NULL,
            test_method text,
            acceptance_criterion text,
            result_value text,
            result_numeric numeric,
            unit text,
            complies boolean,
            testing_lab text,
            source_coa_id uuid,
            source_coa_number text,
            sorting_order integer DEFAULT 0 NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_coq_lines_pkey PRIMARY KEY (id),
            CONSTRAINT qc_coq_lines_coq_fkey FOREIGN KEY (coq_id)
                REFERENCES public.qc_coq(id) ON DELETE CASCADE
        )
        """
    )
    _canon("qc_coq_lines", [
        "CREATE INDEX qc_coq_lines_coq_idx ON public.qc_coq_lines USING btree (org_id, coq_id)",
    ])

    # ── C6 (§6.2.2) — analysis date range + sampling-location echo on the cert
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN analysis_start_date date")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN analysis_end_date date")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN sampling_location text")

    # ── C7 (§6.7) — issue language + translation second-reviewer verification.
    # Default EN-MK preserves the current always-bilingual renderer behaviour.
    op.execute("ALTER TABLE public.qc_certificates"
               " ADD COLUMN issue_language text DEFAULT 'EN-MK'::text NOT NULL")
    op.execute("ALTER TABLE public.qc_certificates ADD CONSTRAINT qc_certificates_language_check"
               " CHECK (issue_language = ANY (ARRAY['EN'::text, 'EN-MK'::text]))")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN translation_verified_by uuid")
    op.execute("ALTER TABLE public.qc_certificates"
               " ADD COLUMN translation_verified_at timestamp with time zone")


def downgrade() -> None:
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN translation_verified_at")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN translation_verified_by")
    op.execute("ALTER TABLE public.qc_certificates DROP CONSTRAINT qc_certificates_language_check")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN issue_language")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN sampling_location")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN analysis_end_date")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN analysis_start_date")
    op.execute("DROP TABLE public.qc_coq_lines")
    op.execute("DROP TABLE public.qc_coq_sources")
    op.execute("DROP TABLE public.qc_coq")
