"""QC review 2026-09-27 — CoQ purpose/timepoint, CoQ e-signatures, OOS register
append-only, retired QC id sequences

Revision ID: 0071
Revises: 0070
Create Date: 2026-09-27

Four schema-level pieces of the 2026-09-27 QC review fixes (docs/review-2026-
09-27/backend-qc.md), one migration because they ship together:

QC-15 — CoQs for the initial release and for later re-test periods could not
coexist: qc_coq_one_approved_idx was unique on (org, batch, spec) alone, so a
re-test-period CoQ against the same specification forced the HoQC to VOID the
valid initial-release CoQ (§6.6 reserves voiding for fundamentally invalid
records). qc_coq gains `purpose` (INITIAL | RETEST) and `timepoint` (free text
such as '6M', required for RETEST); the one-live-APPROVED rule is scoped to
(org, batch, spec, purpose, timepoint). Every existing row is INITIAL.

QC-12 — the SOP-path aggregation CoQ (qc_coq) could never carry an Annex 11
e-signature, so the printed certificate always said "this document carries no
electronic signature". qc_signatures already keys on (object_type, object_id);
its meaning CHECK gains 'COMPILED' for the compiler's signature on a qc_coq.

QC-31 — qc_oos_register is append-only by convention only: it kept the
all-command org_isolation RLS policy while 0061 hardened qc_signatures to
SELECT+INSERT. Same treatment here; no UPDATE/DELETE exists in app code.

QC-28 — the remaining QC identifier series (PP-SPEC, PP-SMP, PP-SPL, PP-LAB,
PP-SFR, PP-WT, PP-STB, PP-TRN) were drawn from global nextval() sequences
shared across every tenant, never reset per year, and burned a number on every
rolled-back insert — the M7 defect class fixed for eCoA (0056) and OOS (0062).
app/api/qc/common.mint_series_number now mints each per-(org, year) from the
org's own max, so the eight sequences are dead and dropped, as 0062 did.
Existing numbers are untouched; each org continues from its current maximum.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DEAD_SEQUENCES = ("qc_spec_id_seq", "qc_sample_id_seq", "qc_sampling_plan_id_seq",
                   "qc_lab_id_seq", "qc_sfr_id_seq", "qc_wt_id_seq", "qc_stb_id_seq",
                   "qc_trn_id_seq")


def upgrade() -> None:
    # QC-15 — CoQ purpose / timepoint
    op.execute(
        "ALTER TABLE public.qc_coq"
        " ADD COLUMN purpose text DEFAULT 'INITIAL'::text NOT NULL,"
        " ADD COLUMN timepoint text,"
        " ADD CONSTRAINT qc_coq_purpose_check"
        "   CHECK (purpose = ANY (ARRAY['INITIAL'::text, 'RETEST'::text])),"
        " ADD CONSTRAINT qc_coq_retest_timepoint_check"
        "   CHECK (purpose <> 'RETEST'::text OR timepoint IS NOT NULL)"
    )
    op.execute("DROP INDEX public.qc_coq_one_approved_idx")
    op.execute(
        "CREATE UNIQUE INDEX qc_coq_one_approved_idx ON public.qc_coq"
        " USING btree (org_id, batch_id, specification_id, purpose,"
        " COALESCE(timepoint, ''::text)) WHERE (status = 'APPROVED'::text)"
    )
    # QC-12 — COMPILED meaning for qc_coq signatures
    op.execute("ALTER TABLE public.qc_signatures DROP CONSTRAINT qc_signatures_meaning_check")
    op.execute(
        "ALTER TABLE public.qc_signatures ADD CONSTRAINT qc_signatures_meaning_check"
        " CHECK ((meaning = ANY (ARRAY['AUTHORED'::text, 'REVIEWED'::text, 'APPROVED'::text,"
        " 'RELEASED'::text, 'VERIFIED'::text, 'COQ_ISSUED'::text, 'COMPILED'::text])))"
    )
    # QC-31 — qc_oos_register append-only at the DB layer
    op.execute("DROP POLICY org_isolation ON public.qc_oos_register")
    op.execute("CREATE POLICY org_isolation_select ON public.qc_oos_register"
               " FOR SELECT USING ((org_id = app.current_org_id()))")
    op.execute("CREATE POLICY org_isolation_insert ON public.qc_oos_register"
               " FOR INSERT WITH CHECK ((org_id = app.current_org_id()))")
    # QC-28 — the retired global sequences
    for seq in _DEAD_SEQUENCES:
        op.execute(f"DROP SEQUENCE IF EXISTS public.{seq}")


def downgrade() -> None:
    for seq in _DEAD_SEQUENCES:
        op.execute(f"CREATE SEQUENCE public.{seq} AS integer START WITH 1 INCREMENT BY 1")
    op.execute("DROP POLICY org_isolation_insert ON public.qc_oos_register")
    op.execute("DROP POLICY org_isolation_select ON public.qc_oos_register")
    op.execute("CREATE POLICY org_isolation ON public.qc_oos_register"
               " USING ((org_id = app.current_org_id()))"
               " WITH CHECK ((org_id = app.current_org_id()))")
    op.execute("DELETE FROM public.qc_signatures WHERE meaning = 'COMPILED'")
    op.execute("ALTER TABLE public.qc_signatures DROP CONSTRAINT qc_signatures_meaning_check")
    op.execute(
        "ALTER TABLE public.qc_signatures ADD CONSTRAINT qc_signatures_meaning_check"
        " CHECK ((meaning = ANY (ARRAY['AUTHORED'::text, 'REVIEWED'::text, 'APPROVED'::text,"
        " 'RELEASED'::text, 'VERIFIED'::text, 'COQ_ISSUED'::text])))"
    )
    op.execute("DROP INDEX public.qc_coq_one_approved_idx")
    op.execute(
        "CREATE UNIQUE INDEX qc_coq_one_approved_idx ON public.qc_coq"
        " USING btree (org_id, batch_id, specification_id) WHERE (status = 'APPROVED'::text)"
    )
    op.execute(
        "ALTER TABLE public.qc_coq"
        " DROP CONSTRAINT qc_coq_retest_timepoint_check,"
        " DROP CONSTRAINT qc_coq_purpose_check,"
        " DROP COLUMN timepoint,"
        " DROP COLUMN purpose"
    )
