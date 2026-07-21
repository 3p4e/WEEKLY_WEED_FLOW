"""URS alignment: source-document custody + SHA-256 (Phase-2 item 12).

Revision ID: 0035
Revises: 0034
Create Date: 2026-07-21

docs/URS-COQ-GAP-ANALYSIS-2026-07.md item 12 — store the ORIGINAL source
document (the supplier eCoA PDF) alongside the transcribed record, with a
SHA-256 for tamper-evidence (ALCOA+ "Original" + "Accurate"). Polymorphic
(`object_type`/`object_id`) so any record can carry originals; today the eCoA
document. The bytes live in a `content` bytea; the file is written once and
never updated (no update/delete endpoint), so its integrity anchor is the
stored SHA-256, which the upload records into the global hash-chained audit_log
via the application's emit() — that chained hash of the file digest is the
tamper-evidence, not the blob itself.

DELIBERATELY NO row-level audit trigger on this table: the shared
app.fn_audit_row() serialises the WHOLE row (to_jsonb(NEW)) into the audit
chain, which for a multi-megabyte bytea would bloat every audit entry and the
hash chain. RLS is still FORCED/ENABLED (org isolation, per the coverage gate);
the custody ACT is audited via emit(), and the SHA-256 is the integrity control.
When OCR lands, page/bbox traceability per extracted value attaches here.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.qc_document_files (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            object_type text NOT NULL,
            object_id uuid NOT NULL,
            filename text NOT NULL,
            content_type text,
            size_bytes integer NOT NULL,
            sha256 text NOT NULL,
            content bytea NOT NULL,
            uploaded_by uuid,
            uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_document_files_pkey PRIMARY KEY (id),
            CONSTRAINT qc_document_files_size_check CHECK ((size_bytes >= 0))
        )
        """
    )
    op.execute("ALTER TABLE ONLY public.qc_document_files FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.qc_document_files ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.qc_document_files"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE INDEX qc_document_files_object_idx ON public.qc_document_files"
        " USING btree (org_id, object_type, object_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_document_files TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_document_files TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_document_files")
