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

DOWNGRADE (review 2026-09-27 QR-12 / INV-10) — records are preserved, never
destroyed, and what the old schema cannot represent is refused up front:

  * it REFUSES (RuntimeError, nothing touched) while any RETEST CoQ exists:
    `purpose`/`timepoint` have no column before 0071, and the old
    one-APPROVED-per-(org, batch, spec) index cannot be recreated over an
    INITIAL and a RETEST CoQ approved for one batch. Void the RETEST CoQs
    deliberately (a Head-of-QC act with a reason) before downgrading, or do
    not downgrade;
  * the COMPILED e-signatures are KEPT (Annex 11 records are evidence — a
    downgrade must not erase them); the pre-0071 meaning CHECK is re-added
    NOT VALID, so new rows are checked and the existing COMPILED rows stay;
  * the eight sequences are recreated seeded past each series' current
    maximum (the org-wide max of the trailing number, exactly what the old
    nextval() minting would have needed next), not at 1 — otherwise the
    pre-0071 code would re-mint PP-SPEC-2026-0001 into a unique violation.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DEAD_SEQUENCES = ("qc_spec_id_seq", "qc_sample_id_seq", "qc_sampling_plan_id_seq",
                   "qc_lab_id_seq", "qc_sfr_id_seq", "qc_wt_id_seq", "qc_stb_id_seq",
                   "qc_trn_id_seq")

# Which identifier series each retired sequence fed (table, column) — the
# pre-0071 minting was '<PREFIX>-<year>-' || lpad(nextval(seq), 4, '0'), so
# the trailing number of the column is the sequence's own value.
SERIES = {
    "qc_spec_id_seq": ("qc_specifications", "spec_id"),
    "qc_sample_id_seq": ("qc_samples", "sample_id"),
    "qc_sampling_plan_id_seq": ("qc_sampling_plans", "plan_id"),
    "qc_lab_id_seq": ("qc_laboratories", "lab_code"),
    "qc_sfr_id_seq": ("qc_sample_field_records", "sfr_number"),
    "qc_wt_id_seq": ("qc_water_tests", "water_test_id"),
    "qc_stb_id_seq": ("qc_stability_studies", "study_id"),
    "qc_trn_id_seq": ("qc_sample_transports", "transport_id"),
}

_OLD_MEANING_CHECK = (
    "CHECK ((meaning = ANY (ARRAY['AUTHORED'::text, 'REVIEWED'::text, 'APPROVED'::text,"
    " 'RELEASED'::text, 'VERIFIED'::text, 'COQ_ISSUED'::text])))")


def series_max_sql(table: str, column: str) -> str:
    """The highest trailing number the series has minted so far (0 when the
    table is empty) — the seed the recreated sequence must start past.
    `table`/`column` come from SERIES, never from input."""
    return (f"SELECT coalesce(max((regexp_match({column}, '-([0-9]+)$'))[1]::int), 0)"
            f" FROM public.{table}")


def recreate_sequence_sql(seq: str, current_max: int) -> str:
    """CREATE SEQUENCE seeded past the series' current maximum, never at 1."""
    return (f"CREATE SEQUENCE public.{seq} AS integer START WITH {int(current_max) + 1}"
            " INCREMENT BY 1")


def unrepresentable(retest_rows: int, approved_period_dups: int) -> list[str]:
    """What the pre-0071 schema cannot hold, as refusal lines (empty = safe)."""
    out = []
    if retest_rows:
        out.append(f"{retest_rows} RETEST CoQ row(s) exist: qc_coq.purpose/timepoint have no"
                   " column before 0071 and would be lost — void them deliberately first")
    if approved_period_dups:
        out.append(f"{approved_period_dups} (org, batch, specification) group(s) hold more than"
                   " one APPROVED CoQ across testing periods: the pre-0071 unique index"
                   " qc_coq_one_approved_idx cannot be recreated over them")
    return out


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
    bind = op.get_bind()
    retest = bind.execute(text("SELECT count(*) FROM public.qc_coq WHERE purpose='RETEST'")).scalar()
    dups = bind.execute(text(
        "SELECT count(*) FROM (SELECT 1 FROM public.qc_coq WHERE status='APPROVED'"
        " GROUP BY org_id, batch_id, specification_id HAVING count(*) > 1) d")).scalar()
    problems = unrepresentable(int(retest or 0), int(dups or 0))
    if problems:
        raise RuntimeError("0071 downgrade refused — the database holds data the pre-0071"
                           " schema cannot represent: " + "; ".join(problems))
    for seq, (table, column) in SERIES.items():
        current = bind.execute(text(series_max_sql(table, column))).scalar()
        op.execute(recreate_sequence_sql(seq, int(current or 0)))
    op.execute("DROP POLICY org_isolation_insert ON public.qc_oos_register")
    op.execute("DROP POLICY org_isolation_select ON public.qc_oos_register")
    op.execute("CREATE POLICY org_isolation ON public.qc_oos_register"
               " USING ((org_id = app.current_org_id()))"
               " WITH CHECK ((org_id = app.current_org_id()))")
    # The COMPILED signatures stay (Annex 11 evidence); the old CHECK goes
    # back NOT VALID so it binds new rows without judging the existing ones.
    op.execute("ALTER TABLE public.qc_signatures DROP CONSTRAINT qc_signatures_meaning_check")
    op.execute("ALTER TABLE public.qc_signatures ADD CONSTRAINT qc_signatures_meaning_check "
               + _OLD_MEANING_CHECK + " NOT VALID")
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
