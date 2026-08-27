"""URS alignment: accredited laboratory master (Chapter 7).

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-20

docs/URS-COQ-GAP-ANALYSIS-2026-07.md item 4 — replace the free-text
`source_institution`/`source_lab` provenance strings with a first-class
laboratory entity carrying the accreditation body/number, the ISO 17025
scope (so a result run on a method the lab is NOT accredited for can be
flagged), the quality-agreement reference, and the lab's decimal-separator
locale (the "decimal-comma defence": a German lab writes 1,5 for 1.5).

Additive only: `qc_laboratories` is new; certificates and eCoA documents
gain a nullable `laboratory_id`. The free-text columns are KEPT — they carry
provenance transcribed off historical documents and must never be dropped
(GxP: an issued record is immutable). A laboratory is reference master data,
so its lifecycle is the simple ACTIVE/INACTIVE pair, not the spec's chain.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LAB_STATUSES = ("ACTIVE", "INACTIVE")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE public.qc_lab_id_seq AS integer START WITH 1 INCREMENT BY 1")
    op.execute(
        """
        CREATE TABLE public.qc_laboratories (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            lab_code text NOT NULL,
            name text NOT NULL,
            accreditation_body text,
            accreditation_number text,
            iso17025_scope jsonb DEFAULT '[]'::jsonb NOT NULL,
            quality_agreement_ref text,
            locale text,
            decimal_separator text DEFAULT '.'::text NOT NULL,
            country text,
            contact text,
            status text DEFAULT 'ACTIVE'::text NOT NULL,
            notes text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_laboratories_pkey PRIMARY KEY (id),
            CONSTRAINT qc_laboratories_code_key UNIQUE (org_id, lab_code),
            CONSTRAINT qc_laboratories_status_check CHECK ((status = ANY (ARRAY[%s]))),
            CONSTRAINT qc_laboratories_decimal_sep_check
                CHECK ((decimal_separator = ANY (ARRAY['.'::text, ','::text])))
        )
        """
        % ",".join(f"'{s}'::text" for s in _LAB_STATUSES)
    )
    op.execute("ALTER TABLE ONLY public.qc_laboratories FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.qc_laboratories ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.qc_laboratories"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_qc_laboratories AFTER INSERT OR DELETE OR UPDATE"
        " ON public.qc_laboratories FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute("CREATE INDEX qc_laboratories_status_idx ON public.qc_laboratories USING btree (org_id, status)")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN laboratory_id uuid")
    op.execute(
        "ALTER TABLE ONLY public.qc_certificates ADD CONSTRAINT qc_certificates_laboratory_fkey"
        " FOREIGN KEY (laboratory_id) REFERENCES public.qc_laboratories(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE public.qc_coa_documents ADD COLUMN laboratory_id uuid")
    op.execute(
        "ALTER TABLE ONLY public.qc_coa_documents ADD CONSTRAINT qc_coa_documents_laboratory_fkey"
        " FOREIGN KEY (laboratory_id) REFERENCES public.qc_laboratories(id) ON DELETE SET NULL"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_laboratories TO app_user;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_lab_id_seq TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_laboratories TO app_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.qc_lab_id_seq TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.qc_coa_documents DROP CONSTRAINT qc_coa_documents_laboratory_fkey")
    op.execute("ALTER TABLE public.qc_coa_documents DROP COLUMN laboratory_id")
    op.execute("ALTER TABLE public.qc_certificates DROP CONSTRAINT qc_certificates_laboratory_fkey")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN laboratory_id")
    op.execute("DROP TABLE public.qc_laboratories")
    op.execute("DROP SEQUENCE public.qc_lab_id_seq")
