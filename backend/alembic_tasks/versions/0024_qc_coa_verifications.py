"""QC LIMS Phase 3 U3: certificate verify loop (source reconciliation record)

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-16

Phase 3 unit 3 — the verify loop that closes the certificate pipeline. A
certificate promoted from an ingested eCoA (U2) is reconciled against its source
document: every promoted `qc_result` is matched (by spec parameter) to the
`qc_coa_extraction` it came from and the value / verdict / limits are compared.
The outcome is written to `qc_coa_verifications` as an auditable GxP second
check — a durable record of who verified, when, and whether the promoted data
still agrees with the source.

- `qc_coa_verifications` — one verification run. CASCADE child of the
  certificate; OPTIONALLY cites the source document (SET NULL). `verdict` is
  VERIFIED (every line agreed) or DISCREPANCY (≥1 mismatch); `details` is the
  per-line comparison (jsonb). Append-style: a new run is a new row, so the
  history of checks is preserved.

RAG Q&A over ingested CoAs (a `qc_coa_chunks` embeddings table) is deliberately
deferred — the DocEngine's Letta fleet already owns retrieval, and the concrete
GxP need here is source reconciliation, not free-text search.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VERDICTS = ("VERIFIED", "DISCREPANCY")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.qc_coa_verifications (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            coa_id uuid NOT NULL,
            source_document_id uuid,
            verdict text NOT NULL,
            checked integer DEFAULT 0 NOT NULL,
            mismatches integer DEFAULT 0 NOT NULL,
            details jsonb DEFAULT '[]'::jsonb NOT NULL,
            verified_by uuid,
            verified_at timestamp with time zone DEFAULT now() NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_coa_verifications_pkey PRIMARY KEY (id),
            CONSTRAINT qc_coa_verifications_verdict_check CHECK (verdict = ANY (ARRAY[%s])),
            CONSTRAINT qc_coa_verifications_coa_fkey FOREIGN KEY (coa_id)
                REFERENCES public.qc_certificates(id) ON DELETE CASCADE,
            CONSTRAINT qc_coa_verifications_document_fkey FOREIGN KEY (source_document_id)
                REFERENCES public.qc_coa_documents(id) ON DELETE SET NULL
        )
        """
        % ",".join(f"'{s}'::text" for s in _VERDICTS)
    )
    op.execute("ALTER TABLE ONLY public.qc_coa_verifications FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.qc_coa_verifications ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.qc_coa_verifications"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_qc_coa_verifications AFTER INSERT OR DELETE OR UPDATE"
        " ON public.qc_coa_verifications FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE INDEX qc_coa_verifications_coa_idx ON public.qc_coa_verifications"
        " USING btree (org_id, coa_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_coa_verifications TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_coa_verifications TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_coa_verifications")
