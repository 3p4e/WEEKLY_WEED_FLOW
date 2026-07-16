"""QC LIMS Phase 3 U2: eCOA / CoA ingestion (the CoA-in half of the pipeline)

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-16

Phase 3 unit 2 — the "CoA in" half of the certificate pipeline (U1 was the
"COQ out" half). A supplier / contract-lab Certificate of Analysis (a PDF —
"eCoA") is registered, its fields are transcribed into a staging area, the
server GRADES each transcribed value against the material's approved
specification, unknown field labels surface to an adaptive review queue, and a
reviewed document is PROMOTED into a native DRAFT `qc_certificate` + `qc_results`
(U3) — which then flows on to the U1 COQ. Consolidates CoA_TRACK / COQ_GEN /
Kade onto the WWF spine (no separate service).

GxP: transcription is never auto-trusted — the server only grades, never
invents a value; an unmapped label is queued for a human (never silently
dropped or guessed); an unmeasured value stays NULL with `complies` unknown.

- `qc_coa_documents` — the ingested-document spine. Human id
  `PP-ECOA-YYYY-NNNN` from `qc_ecoa_id_seq`. OPTIONALLY cites the material
  spec (SET NULL) and a sample (SET NULL); status
  UPLOADED→EXTRACTED→REVIEWED→PROMOTED (+ REJECTED) guarded in the API;
  `promoted_coa_id` points at the certificate minted on promote.
- `qc_coa_extractions` — one transcribed field per row (CASCADE child). Maps to
  a `qc_spec_parameter` (SET NULL) once matched; carries the graded `complies`
  + a limit snapshot + the extractor `confidence`.
- `qc_field_placeholders` — the adaptive-discovery queue (Kade's idea): an
  unmapped label seen on an incoming CoA lands here (deduped per org by a
  normalized label, occurrences counted); a human maps it to a spec parameter
  (→ future CoAs auto-map) or ignores it. NOT tied to one document.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DOC_STATUSES = ("UPLOADED", "EXTRACTED", "REVIEWED", "PROMOTED", "REJECTED")
_EXTRACT_GRADES = ("unmapped", "graded", "unknown")
_PLACEHOLDER_STATUSES = ("OPEN", "MAPPED", "IGNORED")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE public.qc_ecoa_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute(
        """
        CREATE TABLE public.qc_coa_documents (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            doc_number text NOT NULL,
            source_institution text,
            batch_id text NOT NULL,
            material_code text,
            specification_id uuid,
            sample_id uuid,
            original_filename text,
            mime_type text,
            storage_ref text,
            page_count integer,
            report_date date,
            status text DEFAULT 'UPLOADED'::text NOT NULL,
            promoted_coa_id uuid,
            notes text,
            uploaded_by uuid,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_coa_documents_pkey PRIMARY KEY (id),
            CONSTRAINT qc_coa_documents_number_key UNIQUE (org_id, doc_number),
            CONSTRAINT qc_coa_documents_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_coa_documents_spec_fkey FOREIGN KEY (specification_id)
                REFERENCES public.qc_specifications(id) ON DELETE SET NULL,
            CONSTRAINT qc_coa_documents_sample_fkey FOREIGN KEY (sample_id)
                REFERENCES public.qc_samples(id) ON DELETE SET NULL,
            CONSTRAINT qc_coa_documents_promoted_fkey FOREIGN KEY (promoted_coa_id)
                REFERENCES public.qc_certificates(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _DOC_STATUSES)
    )
    op.execute(
        """
        CREATE TABLE public.qc_coa_extractions (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            document_id uuid NOT NULL,
            raw_label text NOT NULL,
            raw_value text,
            numeric_value double precision,
            unit text,
            parameter_id uuid,
            test_name text,
            lower_limit double precision,
            upper_limit double precision,
            complies boolean,
            grade_status text DEFAULT 'unmapped'::text NOT NULL,
            confidence double precision,
            source_page integer,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_coa_extractions_pkey PRIMARY KEY (id),
            CONSTRAINT qc_coa_extractions_grade_check CHECK (grade_status = ANY (ARRAY[%s])),
            CONSTRAINT qc_coa_extractions_document_fkey FOREIGN KEY (document_id)
                REFERENCES public.qc_coa_documents(id) ON DELETE CASCADE,
            CONSTRAINT qc_coa_extractions_parameter_fkey FOREIGN KEY (parameter_id)
                REFERENCES public.qc_spec_parameters(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _EXTRACT_GRADES)
    )
    op.execute(
        """
        CREATE TABLE public.qc_field_placeholders (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            raw_label text NOT NULL,
            normalized_label text NOT NULL,
            occurrences integer DEFAULT 1 NOT NULL,
            suggested_test_name text,
            mapped_parameter_id uuid,
            status text DEFAULT 'OPEN'::text NOT NULL,
            first_seen_document_id uuid,
            resolved_by uuid,
            resolved_at timestamp with time zone,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_field_placeholders_pkey PRIMARY KEY (id),
            CONSTRAINT qc_field_placeholders_label_key UNIQUE (org_id, normalized_label),
            CONSTRAINT qc_field_placeholders_status_check CHECK (status = ANY (ARRAY[%s])),
            CONSTRAINT qc_field_placeholders_parameter_fkey FOREIGN KEY (mapped_parameter_id)
                REFERENCES public.qc_spec_parameters(id) ON DELETE SET NULL,
            CONSTRAINT qc_field_placeholders_document_fkey FOREIGN KEY (first_seen_document_id)
                REFERENCES public.qc_coa_documents(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _PLACEHOLDER_STATUSES)
    )
    for tbl in ("qc_coa_documents", "qc_coa_extractions", "qc_field_placeholders"):
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
        "CREATE INDEX qc_coa_documents_batch_idx ON public.qc_coa_documents USING btree (org_id, batch_id)"
    )
    op.execute(
        "CREATE INDEX qc_coa_documents_status_idx ON public.qc_coa_documents USING btree (org_id, status)"
    )
    op.execute(
        "CREATE INDEX qc_coa_extractions_document_idx ON public.qc_coa_extractions USING btree (org_id, document_id)"
    )
    op.execute(
        "CREATE INDEX qc_field_placeholders_status_idx ON public.qc_field_placeholders USING btree (org_id, status)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_coa_documents, public.qc_coa_extractions,
                public.qc_field_placeholders TO app_user;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_ecoa_id_seq TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_coa_documents, public.qc_coa_extractions,
                public.qc_field_placeholders TO app_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_ecoa_id_seq TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_field_placeholders")
    op.execute("DROP TABLE public.qc_coa_extractions")
    op.execute("DROP TABLE public.qc_coa_documents")
    op.execute("DROP SEQUENCE public.qc_ecoa_id_seq")
