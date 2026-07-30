"""destruction / waste manifest — the reconciliation record

Revision ID: 0048
Revises: 0047
Create Date: 2026-07-30

The plan's live destruction window is 30.07-01.08 and it moves several tonnes of
infected plant material off site. Until now nothing recorded that: migration 0045
can mark a batch `destroyed`, which says the batch is gone but not what left the
building, how much it weighed, who watched it go, or who took it. That gap is the
one the design doc (§5c) calls the *regulatory invariant*, because destruction is
the only phase transition where the material stops being auditable afterwards —
a missing harvest record can be reconstructed from the lot, a missing destruction
record cannot be reconstructed from anything.

TWO TABLES, HEADER AND LINES, because one consignment routinely empties several
batches at once and the reconciliation question is per BATCH while the weighbridge
ticket and the carrier docket are per CONSIGNMENT. Collapsing them into one table
would force either one row per batch with a duplicated carrier reference (so two
rows could disagree about the same physical load) or one row per load with the
per-batch quantities in free text (so nothing reconciles).

WHY THE STATUS LADDER IS IN THE SCHEMA
`draft -> sealed -> witnessed -> disposed`. Each step is a different person's
assertion and they are not interchangeable:
  - draft     — being filled in; lines may still be added or removed;
  - sealed    — the contents are fixed and the gross weight is recorded;
  - witnessed — a SECOND named person saw the sealed load. The two-person rule is
                the entire point of a destruction witness, so `witnessed_by` is
                constrained to differ from `weighed_by` in the API layer (it
                cannot be a CHECK here, because weighed_by is nullable until the
                seal and a row-level CHECK would then permit the equal-and-null
                case);
  - disposed  — the carrier's own reference came back, closing the chain.
A ladder in the data means "who has actually signed off" is a query rather than
an interpretation of timestamps.

WHAT IS DELIBERATELY *NOT* CONSTRAINED HERE
The reconciliation invariant — destroyed quantity per batch must not exceed the
batch's plant count — is enforced in app/api/waste.py, not as a CHECK or a
trigger. It spans rows in two tables and would need either a per-statement
trigger (which cannot see the aggregate cheaply) or a materialised counter on
plant_batches (which is a second source of truth for a number already derivable).
Both are worse than one guarded endpoint, and the endpoint is tested against the
over-declare case directly.

Purely additive: no existing table is altered, so a v79 backend keeps working
against this schema unchanged.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("waste_manifests", "waste_manifest_lines")


def upgrade() -> None:
    # ── waste_manifests — one physical consignment ────────────────────────
    op.execute(
        """
        CREATE TABLE public.waste_manifests (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            manifest_code text NOT NULL,
            waste_type text NOT NULL,
            reason text NOT NULL,
            status text DEFAULT 'draft'::text NOT NULL,
            campaign text,
            origin_room_id uuid,
            destination text,
            carrier_name text,
            carrier_ref text,
            gross_weight_kg numeric,
            weighed_at timestamp with time zone,
            weighed_by uuid,
            sealed_at timestamp with time zone,
            witnessed_at timestamp with time zone,
            witnessed_by uuid,
            disposed_at timestamp with time zone,
            disposed_by uuid,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            created_by uuid NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_by uuid,
            CONSTRAINT waste_manifests_pkey PRIMARY KEY (id),
            CONSTRAINT waste_manifests_org_id_manifest_code_key UNIQUE (org_id, manifest_code),
            CONSTRAINT waste_manifests_origin_room_id_fkey FOREIGN KEY (origin_room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            -- The material classes the campaign actually moves. 'other' exists so
            -- an unforeseen stream is recorded rather than filed under a wrong
            -- class or, worse, not recorded at all.
            CONSTRAINT waste_manifests_waste_type_check CHECK (waste_type = ANY (ARRAY[
                'plant_material'::text, 'root_substrate'::text, 'growing_medium'::text,
                'trim'::text, 'packaging'::text, 'other'::text])),
            -- WHY it was destroyed is not optional: an eradication cull and a
            -- routine cull have different reporting consequences, and a record
            -- that does not distinguish them cannot answer either question.
            CONSTRAINT waste_manifests_reason_check CHECK (reason = ANY (ARRAY[
                'hlvd_eradication'::text, 'routine_cull'::text, 'failed_qc'::text,
                'expired'::text, 'spillage'::text, 'other'::text])),
            CONSTRAINT waste_manifests_status_check CHECK (status = ANY (ARRAY[
                'draft'::text, 'sealed'::text, 'witnessed'::text, 'disposed'::text])),
            CONSTRAINT waste_manifests_gross_weight_check
                CHECK (gross_weight_kg IS NULL OR gross_weight_kg >= 0),
            -- The ladder's own integrity, at the row level: a status cannot be
            -- claimed without the timestamp that evidences it. Without this a
            -- manifest could read 'disposed' with every signature column null.
            CONSTRAINT waste_manifests_seal_evidence_check CHECK (
                status = 'draft' OR (sealed_at IS NOT NULL AND weighed_by IS NOT NULL)),
            CONSTRAINT waste_manifests_witness_evidence_check CHECK (
                status IN ('draft', 'sealed')
                OR (witnessed_at IS NOT NULL AND witnessed_by IS NOT NULL)),
            CONSTRAINT waste_manifests_disposal_evidence_check CHECK (
                status <> 'disposed' OR (disposed_at IS NOT NULL AND disposed_by IS NOT NULL))
        )
        """
    )
    op.execute(
        "CREATE INDEX waste_manifests_org_idx ON public.waste_manifests"
        " USING btree (org_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX waste_manifests_org_status_idx ON public.waste_manifests"
        " USING btree (org_id, status)"
    )

    # ── waste_manifest_lines — what each consignment emptied ──────────────
    op.execute(
        """
        CREATE TABLE public.waste_manifest_lines (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            manifest_id uuid NOT NULL,
            batch_id uuid,
            room_id uuid,
            plant_qty integer,
            weight_kg numeric,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            created_by uuid NOT NULL,
            CONSTRAINT waste_manifest_lines_pkey PRIMARY KEY (id),
            -- CASCADE, uniquely in this schema: a line has no meaning apart from
            -- its manifest, and a draft manifest abandoned before sealing must be
            -- deletable. Every other FK here is RESTRICT because rooms and batches
            -- outlive the manifests that reference them.
            CONSTRAINT waste_manifest_lines_manifest_id_fkey FOREIGN KEY (manifest_id)
                REFERENCES public.waste_manifests(id) ON DELETE CASCADE,
            CONSTRAINT waste_manifest_lines_batch_id_fkey FOREIGN KEY (batch_id)
                REFERENCES public.plant_batches(id) ON DELETE RESTRICT,
            CONSTRAINT waste_manifest_lines_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT waste_manifest_lines_plant_qty_check
                CHECK (plant_qty IS NULL OR plant_qty >= 0),
            CONSTRAINT waste_manifest_lines_weight_check
                CHECK (weight_kg IS NULL OR weight_kg >= 0),
            -- A line that quantifies nothing is not a record. At least one of the
            -- two measures must be present; which one depends on the stream
            -- (plants are counted, substrate is weighed).
            CONSTRAINT waste_manifest_lines_quantified_check
                CHECK (plant_qty IS NOT NULL OR weight_kg IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE INDEX waste_manifest_lines_manifest_idx ON public.waste_manifest_lines"
        " USING btree (manifest_id)"
    )
    # The reconciliation query is "how much of this batch has been declared
    # destroyed", so batch_id leads. Partial: unattributed lines never appear in
    # a per-batch reconciliation and would only bloat the index.
    op.execute(
        "CREATE INDEX waste_manifest_lines_batch_idx ON public.waste_manifest_lines"
        " USING btree (batch_id) WHERE batch_id IS NOT NULL"
    )

    for tbl in _NEW_TABLES:
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
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.waste_manifests,
              public.waste_manifest_lines TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.waste_manifests,
              public.waste_manifest_lines TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.waste_manifest_lines")
    op.execute("DROP TABLE public.waste_manifests")
