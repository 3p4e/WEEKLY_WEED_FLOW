"""URS alignment: Annex 11 electronic signatures for QC approvals.

Revision ID: 0034
Revises: 0033
Create Date: 2026-07-21

docs/URS-COQ-GAP-ANALYSIS-2026-07.md §3 (e-signatures REOPENED → required by
URS 10.2/§14) and item 11 (iCoA analyst + Head-of-QC signature capture). EU GMP
Annex 11 §14 requires that an electronic signature carry the signer's name, the
MEANING of the signature (reviewed / approved / released…), the date and time,
and be permanently linked to the record — executed by the signer (re-
authentication at the moment of signing).

`qc_signatures` is an append-only attestation log: one row per signing act,
polymorphically linked to the signed record (`object_type` + `object_id`; today
the certificate, later OOS closures etc.). The signer's name and role are
snapshotted at sign time so the certificate carries the credential even if the
account is later renamed or its role changes. This is distinct from the global
hash-chained audit_log (which records the mutation): the signature captures the
deliberate, re-authenticated ATTESTATION with its meaning. The in-app role and
second-person gates on the underlying transition are unchanged — the signature
does not replace them. `signer_id` is a plain uuid (users live in the separate
users DB, like every other actor id in the QC schema); `object_id` is
polymorphic, so neither carries a foreign key.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SIG_MEANINGS = ("AUTHORED", "REVIEWED", "APPROVED", "RELEASED", "VERIFIED", "COQ_ISSUED")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.qc_signatures (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            object_type text NOT NULL,
            object_id uuid NOT NULL,
            signer_id uuid NOT NULL,
            signer_name text NOT NULL,
            signer_role text,
            meaning text NOT NULL,
            statement text,
            signed_at timestamp with time zone DEFAULT now() NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT qc_signatures_pkey PRIMARY KEY (id),
            CONSTRAINT qc_signatures_meaning_check CHECK ((meaning = ANY (ARRAY[%s])))
        )
        """
        % ",".join(f"'{s}'::text" for s in _SIG_MEANINGS)
    )
    op.execute("ALTER TABLE ONLY public.qc_signatures FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.qc_signatures ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation ON public.qc_signatures"
        " USING ((org_id = app.current_org_id()))"
        " WITH CHECK ((org_id = app.current_org_id()))"
    )
    op.execute(
        "CREATE TRIGGER audit_qc_signatures AFTER INSERT OR DELETE OR UPDATE"
        " ON public.qc_signatures FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE INDEX qc_signatures_object_idx ON public.qc_signatures"
        " USING btree (org_id, object_type, object_id)"
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_signatures TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.qc_signatures TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.qc_signatures")
