"""QC LIMS Phase 3 U4: RAG Q&A over ingested CoAs (qc_coa_chunks + FTS)

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-16

The deferred certificate-pipeline retrieval layer. An ingested CoA (U2) can be
chunked into `qc_coa_chunks`; a Postgres full-text `tsvector` (generated column
+ GIN index) makes the chunks searchable. The Q&A endpoint retrieves the
top-ranked passages for a question and returns them **cited** — retrieval that
grounds every answer in real document text (GxP: the server never fabricates an
answer; synthesis, if any, grounds strictly on the retrieved passages).

Postgres FTS is deliberately chosen over a parallel embedding stack: the
DocEngine's Letta fleet already owns semantic retrieval, and FTS gives a
dependency-free, fully-testable, offline retrieval layer over the ingested CoAs
with no new infrastructure.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.qc_coa_chunks (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            document_id uuid NOT NULL,
            chunk_index integer DEFAULT 0 NOT NULL,
            content text NOT NULL,
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED,
            created_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_coa_chunks_pkey PRIMARY KEY (id),
            CONSTRAINT qc_coa_chunks_document_fkey FOREIGN KEY (document_id)
                REFERENCES public.qc_coa_documents(id) ON DELETE CASCADE
        )
        """
    )
    op.execute("ALTER TABLE ONLY public.qc_coa_chunks FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.qc_coa_chunks ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.qc_coa_chunks"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_qc_coa_chunks AFTER INSERT OR DELETE OR UPDATE"
        " ON public.qc_coa_chunks FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute("CREATE INDEX qc_coa_chunks_tsv_idx ON public.qc_coa_chunks USING gin (tsv)")
    op.execute("CREATE INDEX qc_coa_chunks_doc_idx ON public.qc_coa_chunks USING btree (org_id, document_id)")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_coa_chunks TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_coa_chunks TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_coa_chunks")
