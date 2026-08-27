"""harvest / yield record, and the IPM applications it has to block on

Revision ID: 0051
Revises: 0050
Create Date: 2026-07-30

Phase 2 item 1 of the cultivation build (docs/CULTIVATION-DESIGN-2026-07.md §5).
The design doc puts harvest first in Phase 2 for one reason: it is the record
that finally connects cultivation to the QC lot. `qc_batch_genealogy` (migration
0036) has carried a `relation = 'CULTIVATION'` slot since before any of the
cultivation work existed, and **nothing upstream has ever produced the identifier
to put in it**. A harvest lot code is that identifier. Until this table exists, a
finished-product CoQ cannot trace past the processing lot; after it, the chain
runs cultivar → batch → harvest lot → processing → packaging without a gap.

WHY IPM IS IN THIS MIGRATION AND NOT A LATER ONE

The design doc is explicit about the sequencing:

    "IPM carries re-entry and pre-harvest intervals, which the harvest step must
     then be able to *block* on — that interaction should be designed with
     harvest, not bolted on after."

A pre-harvest interval is not an IPM feature that harvest happens to consult. It
is a *harvest gate* whose evidence lives on the IPM row. Shipping harvest first
with a `phi_acknowledged boolean` for a later migration to make real is exactly
the bolt-on the doc warns against: the gate would be untestable (nothing to read),
the override would have no evidence to override, and the eventual IPM table would
be shaped to fit a placeholder instead of the other way round. So the two tables
land together, and `app/api/harvest.py` enforces a gate that reads real rows from
day one.

`ipm_applications.applied_at` is a **timestamptz, not a date**, because REI is
measured in hours. A room sprayed at 08:00 with a 12-hour re-entry is enterable
at 20:00 the same day; a date column cannot express that and would round the
control to "not today", which is both wrong and, on the permissive side, wrong in
the direction that puts people in a treated room.

WHY THE HARVEST LADDER HAS THREE RUNGS AND NOT FOUR

  wet → dried → closed

Each rung is a different fact established at a different time by (usually) a
different person: what came off the plants, what came out of the dry room, and
that the lot is final. A fourth 'drying' state was considered and dropped — it
would carry no gate of its own (nothing is asserted by entering the dry room that
is not already asserted by the wet weight) and a status with no gate is a status
people forget to set.

WHY THE YIELD ARITHMETIC IS A CHECK HERE AND THE HEADCOUNT INVARIANT IS NOT

`dry_flower + dry_trim + dry_waste <= wet_weight` involves four columns of ONE
row, so the database is the right place for it: nothing can put an impossible
yield in this table, including a direct SQL fix at 2am. Water does not get added
in a dry room, and a lot that gained mass while drying is a data-entry error every
time.

The headcount invariant — harvested plants plus destroyed plants may not exceed
the batch — spans `harvests`, `waste_manifest_lines` and `plant_batches`, so it
cannot be a CHECK and deliberately is not a trigger either. It lives in
`app/api/harvest.py` for the same reason waste's does (0048): a trigger would
serialize under the audit chain's global advisory lock, and a counter column on
`plant_batches` would be a second source of truth for a number already derivable.

WHY THE PHI OVERRIDE IS THREE COLUMNS AND NOT A NOTE

An override that is only a free-text note is indistinguishable from a comment, and
a control that can be bypassed without leaving a named, reasoned, timestamped
record is not a control. The CHECK makes all three columns arrive together or not
at all, so there is no such thing as an anonymous override or one without a
stated reason. Who is *allowed* to override is an application decision (QA
authority, never the person recording the cut) and lives in the API.

WHY WEIGHTS ARE IN GRAMS HERE AND KILOGRAMS IN THE WASTE REGISTER

Not an oversight. Waste is weighed on a pallet scale as whole consignments and is
reported in kg; harvest is weighed on a bench scale and the operating metric the
floor actually manages is **grams per plant**, which is unreadable in kg. The unit
is in every column name (`_g`, `_kg`) precisely so the two can never be confused
by a reader who does not know that history.

Purely additive: two new tables, nothing existing altered.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("ipm_applications", "harvests")


def upgrade() -> None:
    # ── ipm_applications — what was applied, where, and what it locks out ──
    op.execute(
        """
        CREATE TABLE public.ipm_applications (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            room_id uuid,
            batch_id uuid,
            product text NOT NULL,
            active_ingredient text,
            category text NOT NULL,
            method text,
            dose text,
            target text,
            applied_at timestamp with time zone DEFAULT now() NOT NULL,
            rei_hours integer,
            phi_days integer,
            applied_by uuid NOT NULL,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            created_by uuid NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_by uuid,
            CONSTRAINT ipm_applications_pkey PRIMARY KEY (id),
            CONSTRAINT ipm_applications_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT ipm_applications_batch_id_fkey FOREIGN KEY (batch_id)
                REFERENCES public.plant_batches(id) ON DELETE RESTRICT,
            -- An application that names neither a room nor a batch cannot be
            -- reasoned about by either the re-entry control or the pre-harvest
            -- control, which are the only two things this record exists to feed.
            -- It would be a diary entry, not a record.
            CONSTRAINT ipm_applications_target_scope_check
                CHECK (room_id IS NOT NULL OR batch_id IS NOT NULL),
            -- Biological and botanical are separated from chemical because they
            -- carry different intervals and different reporting duties; a single
            -- 'pesticide' class would erase exactly the distinction the record
            -- is for.
            CONSTRAINT ipm_applications_category_check CHECK (category = ANY (ARRAY[
                'biological'::text, 'botanical'::text, 'chemical'::text,
                'mechanical'::text, 'other'::text])),
            CONSTRAINT ipm_applications_method_check CHECK (method IS NULL OR method = ANY (ARRAY[
                'spray'::text, 'drench'::text, 'fog'::text, 'dust'::text,
                'release'::text, 'other'::text])),
            -- NULL means "no interval declared", which is a different statement
            -- from zero ("declared, and it is nil"). The harvest gate treats NULL
            -- as no block; the UI asks for the number explicitly so that NULL is
            -- a decision rather than an omission.
            CONSTRAINT ipm_applications_rei_check CHECK (rei_hours IS NULL OR rei_hours >= 0),
            CONSTRAINT ipm_applications_phi_check CHECK (phi_days IS NULL OR phi_days >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX ipm_applications_org_applied_idx ON public.ipm_applications"
        " USING btree (org_id, applied_at DESC)"
    )
    # The PHI gate's query is "what was applied to this batch / this room", so
    # both scopes get a partial index — an application scoped to one of them
    # never appears in the other's lookup.
    op.execute(
        "CREATE INDEX ipm_applications_batch_idx ON public.ipm_applications"
        " USING btree (batch_id, applied_at DESC) WHERE batch_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ipm_applications_room_idx ON public.ipm_applications"
        " USING btree (room_id, applied_at DESC) WHERE room_id IS NOT NULL"
    )

    # ── harvests — the yield record and the lot identifier ────────────────
    op.execute(
        """
        CREATE TABLE public.harvests (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            batch_id uuid NOT NULL,
            room_id uuid,
            lot_code text NOT NULL,
            status text DEFAULT 'wet'::text NOT NULL,
            harvested_on date DEFAULT CURRENT_DATE NOT NULL,
            plants_harvested integer NOT NULL,
            wet_weight_g numeric NOT NULL,
            dried_on date,
            dry_flower_g numeric,
            dry_trim_g numeric,
            dry_waste_g numeric,
            phi_override_at timestamp with time zone,
            phi_override_by uuid,
            phi_override_reason text,
            harvested_by uuid NOT NULL,
            closed_at timestamp with time zone,
            closed_by uuid,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            created_by uuid NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_by uuid,
            CONSTRAINT harvests_pkey PRIMARY KEY (id),
            -- The lot code is the identifier that goes into qc_batch_genealogy as
            -- the child of the cultivation batch. It has to be unique per org for
            -- the same reason a batch code does: it names a physical lot that a
            -- certificate will later be issued against.
            CONSTRAINT harvests_org_id_lot_code_key UNIQUE (org_id, lot_code),
            CONSTRAINT harvests_batch_id_fkey FOREIGN KEY (batch_id)
                REFERENCES public.plant_batches(id) ON DELETE RESTRICT,
            CONSTRAINT harvests_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT harvests_status_check CHECK (status = ANY (ARRAY[
                'wet'::text, 'dried'::text, 'closed'::text])),
            -- 0 is legitimate: a partial-canopy pull takes the tops and leaves the
            -- plants standing, retiring none of them. It is the headcount
            -- invariant's input, so it must be stated either way.
            CONSTRAINT harvests_plants_check CHECK (plants_harvested >= 0),
            CONSTRAINT harvests_wet_weight_check CHECK (wet_weight_g >= 0),
            CONSTRAINT harvests_dry_flower_check CHECK (dry_flower_g IS NULL OR dry_flower_g >= 0),
            CONSTRAINT harvests_dry_trim_check CHECK (dry_trim_g IS NULL OR dry_trim_g >= 0),
            CONSTRAINT harvests_dry_waste_check CHECK (dry_waste_g IS NULL OR dry_waste_g >= 0),
            -- THE YIELD ARITHMETIC. Four columns, one row, so it belongs here and
            -- not in the application: nothing can put a lot that gained mass in
            -- the dry room into this table, by any route.
            CONSTRAINT harvests_yield_check CHECK (
                COALESCE(dry_flower_g, 0) + COALESCE(dry_trim_g, 0)
                + COALESCE(dry_waste_g, 0) <= wet_weight_g),
            -- Ladder integrity, same shape as waste_manifests in 0048: a status
            -- cannot be claimed without the evidence that makes it true. Without
            -- these a row could read 'closed' with no dry weight and no signature.
            CONSTRAINT harvests_dry_evidence_check CHECK (
                status = 'wet' OR (dried_on IS NOT NULL AND dry_flower_g IS NOT NULL)),
            CONSTRAINT harvests_close_evidence_check CHECK (
                status <> 'closed' OR (closed_at IS NOT NULL AND closed_by IS NOT NULL)),
            -- An override arrives whole or not at all. A named person, a stated
            -- reason and a time, or none of the three — because an anonymous
            -- override, or one with a blank reason, is indistinguishable from the
            -- gate never having been there.
            CONSTRAINT harvests_phi_override_check CHECK (
                (phi_override_at IS NULL AND phi_override_by IS NULL
                 AND phi_override_reason IS NULL)
                OR (phi_override_at IS NOT NULL AND phi_override_by IS NOT NULL
                    AND phi_override_reason IS NOT NULL
                    AND length(btrim(phi_override_reason)) > 0))
        )
        """
    )
    op.execute(
        "CREATE INDEX harvests_org_harvested_idx ON public.harvests"
        " USING btree (org_id, harvested_on DESC)"
    )
    # The headcount invariant and the yield report are both "everything harvested
    # from this batch", so batch_id leads.
    op.execute(
        "CREATE INDEX harvests_batch_idx ON public.harvests USING btree (batch_id)"
    )
    op.execute(
        "CREATE INDEX harvests_org_status_idx ON public.harvests USING btree (org_id, status)"
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

    # Same guarded grant block as 0045/0048/0049 — CI's pure-alembic build has no
    # app roles; live and test databases do and need the grants immediately.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.ipm_applications, public.harvests TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.ipm_applications, public.harvests TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.harvests")
    op.execute("DROP TABLE public.ipm_applications")
