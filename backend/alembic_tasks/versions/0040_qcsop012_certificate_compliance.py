"""QCSOP 012 v3 certificate compliance — Voided state + External CoA Review Checklist

Revision ID: 0040
Revises: 0039
Create Date: 2026-07-21

Aligns the certificate surface with the governing SOP QCSOP 012 v3.0 (CoA/CoQ
issuance and management), Tier 1 (additive, non-breaking):

- qc_certificates: §6.6 the VOIDED state for a fundamentally-invalid certificate
  (wrong batch / wrong sample) — a distinct terminal disposition from SUPERSEDED,
  carrying a written reason + the voiding actor/time. The original record is
  never deleted (GxP): void is a status + reason, not a delete. The status CHECK
  is widened to admit 'VOIDED'.
- qc_ecoa_checklist: §6.3.2 the External CoA Review Checklist (record QCT 018) as
  a first-class child of qc_coa_documents — the SOP's mandated per-field review
  (sample-id match, method-per-TQA, units-per-spec, a Purely-Plant conformance
  determination affirmation, discrepancy flags), a reviewer signature, and the
  Accepted / Rejected outcome. Facility canon (uuid PK + org_id, FORCE/ENABLE
  RLS org_isolation, audit trigger, guarded GRANT).

All additive. New columns are nullable; the new table is independent. Existing
RLS / audit / grants cover the qc_certificates additions.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHECKLIST_OUTCOMES = ("PENDING", "ACCEPTED", "REJECTED")


def upgrade() -> None:
    # ── §6.6 — the VOIDED disposition on qc_certificates
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN void_reason text")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN voided_by uuid")
    op.execute("ALTER TABLE public.qc_certificates ADD COLUMN voided_at timestamp with time zone")
    op.execute("ALTER TABLE public.qc_certificates DROP CONSTRAINT qc_certificates_status_check")
    op.execute(
        "ALTER TABLE public.qc_certificates ADD CONSTRAINT qc_certificates_status_check"
        " CHECK ((status = ANY (ARRAY['DRAFT'::text, 'REVIEWED'::text, 'APPROVED'::text,"
        " 'RELEASED'::text, 'SUPERSEDED'::text, 'VOIDED'::text])))"
    )

    # ── §6.3.2 — External CoA Review Checklist (QCT 018)
    op.execute(
        """
        CREATE TABLE public.qc_ecoa_checklist (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            document_id uuid NOT NULL,
            sample_id_match boolean,
            method_per_tqa boolean,
            units_per_spec boolean,
            conformance_by_pp boolean,
            discrepancies text,
            notes text,
            outcome text DEFAULT 'PENDING'::text NOT NULL,
            reviewed_by uuid,
            reviewed_at timestamp with time zone,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_ecoa_checklist_pkey PRIMARY KEY (id),
            CONSTRAINT qc_ecoa_checklist_outcome_check CHECK (outcome = ANY (ARRAY[%s])),
            -- §6.3.2 one review checklist per eCoA document (DB-enforced so a
            -- concurrent double-PUT cannot create a second, editable review).
            CONSTRAINT qc_ecoa_checklist_document_key UNIQUE (org_id, document_id),
            CONSTRAINT qc_ecoa_checklist_document_fkey FOREIGN KEY (document_id)
                REFERENCES public.qc_coa_documents(id) ON DELETE CASCADE
        )
        """
        % ",".join(f"'{s}'::text" for s in _CHECKLIST_OUTCOMES)
    )
    op.execute("ALTER TABLE ONLY public.qc_ecoa_checklist FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.qc_ecoa_checklist ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.qc_ecoa_checklist"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_qc_ecoa_checklist AFTER INSERT OR DELETE OR UPDATE"
        " ON public.qc_ecoa_checklist FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE INDEX qc_ecoa_checklist_document_idx ON public.qc_ecoa_checklist"
        " USING btree (org_id, document_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_ecoa_checklist TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_ecoa_checklist TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # DESTRUCTIVE DOWNGRADE (same risk class migration 0010 flags explicitly).
    # This re-narrows a CHECK constraint that the upgrade widened. On any
    # database that has since USED one of the added values, the ALTER ... ADD
    # CONSTRAINT below fails validation and the downgrade aborts part-way —
    # after the DROPs above have already run. Before downgrading a real
    # database, first migrate or delete the rows carrying the newer values.
    op.execute("DROP TABLE public.qc_ecoa_checklist")
    op.execute("ALTER TABLE public.qc_certificates DROP CONSTRAINT qc_certificates_status_check")
    op.execute(
        "ALTER TABLE public.qc_certificates ADD CONSTRAINT qc_certificates_status_check"
        " CHECK ((status = ANY (ARRAY['DRAFT'::text, 'REVIEWED'::text, 'APPROVED'::text,"
        " 'RELEASED'::text, 'SUPERSEDED'::text])))"
    )
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN voided_at")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN voided_by")
    op.execute("ALTER TABLE public.qc_certificates DROP COLUMN void_reason")
