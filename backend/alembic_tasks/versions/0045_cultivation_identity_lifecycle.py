"""cultivation: cultivar master, batch codes, per-plant identity, phase events

Revision ID: 0045
Revises: 0044
Create Date: 2026-07-30

Phase 1 of the cultivation department build (docs/CULTIVATION-DESIGN-2026-07.md).
It gives cultivation the identity it was missing so it can finally join the
existing genealogy -> CoA/CoQ chain, and models the individual-plant tracking
the owner confirmed for the genetics arriving 13-19.08.

Owner-confirmed scheme (2026-07-30):
  - Batch = one cultivar in one flowering room. Usually a whole flowering room
    is a single cultivar (one batch); occasionally a room holds several
    cultivars and each is its own batch. ~2000 plants per flowering room.
  - Batch code like `GP072501` (site prefix + period + sequence).
  - Every plant carries an ID `<clone-date>_<cultivar>_<seq>`, seq incrementing
    from 1 within the batch.

THE LOAD-BEARING DESIGN DECISION — phase lives on the BATCH, not the plant.
app.fn_audit_row() takes a single GLOBAL pg_advisory_xact_lock before every
chain-tail read and holds it until commit (see tasks-0012 / users-0006). If
`plants` carried a phase column, moving a ~2000-plant room veg->flower would be
2000 UPDATEs, i.e. 2000 audited writes serialized under that one lock, blocking
every other audited write in the database — task updates, QC results, logins —
for the whole transaction. So a whole-room phase move is ONE `plant_batches`
row update plus ONE `plant_phase_events` row. The per-plant `plants.status`
changes only for exceptions (this plant culled/destroyed/harvested), which are
bounded. Bulk plant INSERT at batch creation is still ~2000 rows, so the API
must chunk it into bounded transactions (documented in the design doc); this
migration only defines the shape.

Additive: new `cultivars`, `plants`, `plant_phase_events` tables, and new
nullable columns + a widened phase CHECK on the existing `plant_batches`. No
data migration; existing batches keep their free-text `strain` (now
soft-deprecated in favour of `cultivar_id`) and a NULL `code`.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("cultivars", "plants", "plant_phase_events")


def upgrade() -> None:
    # ── cultivar master — retires free-text plant_batches.strain ──
    op.execute(
        """
        CREATE TABLE public.cultivars (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            code text NOT NULL,
            name text NOT NULL,
            name_mk text,
            note text,
            is_active boolean DEFAULT true NOT NULL,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT cultivars_pkey PRIMARY KEY (id),
            CONSTRAINT cultivars_org_id_code_key UNIQUE (org_id, code)
        )
        """
    )

    # ── plant_batches: batch code + cultivar link + terminal/nursery phases ──
    op.execute("ALTER TABLE public.plant_batches ADD COLUMN code text")
    op.execute("ALTER TABLE public.plant_batches ADD COLUMN cultivar_id uuid")
    op.execute(
        "ALTER TABLE public.plant_batches"
        " ADD CONSTRAINT plant_batches_cultivar_id_fkey FOREIGN KEY (cultivar_id)"
        " REFERENCES public.cultivars(id) ON DELETE RESTRICT"
    )
    # Batch code is unique per org WHERE present — existing rows have NULL and a
    # plain UNIQUE would reject more than one of them.
    op.execute(
        "CREATE UNIQUE INDEX plant_batches_org_code_key ON public.plant_batches"
        " (org_id, code) WHERE code IS NOT NULL"
    )
    # Widen the phase vocabulary: split nursery out of clone (the plan and room
    # register treat them separately) and add the two terminal states so a
    # finished batch is 'harvested'/'destroyed' rather than an ambiguous
    # is_active=false. Drop-then-add because a CHECK cannot be altered in place.
    op.execute("ALTER TABLE public.plant_batches DROP CONSTRAINT plant_batches_phase_check")
    op.execute(
        "ALTER TABLE public.plant_batches ADD CONSTRAINT plant_batches_phase_check"
        " CHECK (phase = ANY (ARRAY['nursery'::text, 'clone'::text, 'veg'::text,"
        " 'flower'::text, 'mother'::text, 'drying'::text, 'harvested'::text,"
        " 'destroyed'::text]))"
    )

    # ── plants — individual identity. NO phase column, by design (see header). ──
    op.execute(
        """
        CREATE TABLE public.plants (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            batch_id uuid NOT NULL,
            room_id uuid,
            cultivar_id uuid,
            plant_code text NOT NULL,
            clone_date date,
            seq integer NOT NULL,
            status text DEFAULT 'active'::text NOT NULL,
            status_since date DEFAULT CURRENT_DATE NOT NULL,
            reason text,
            note text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT plants_pkey PRIMARY KEY (id),
            CONSTRAINT plants_batch_id_fkey FOREIGN KEY (batch_id)
                REFERENCES public.plant_batches(id) ON DELETE RESTRICT,
            CONSTRAINT plants_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT plants_cultivar_id_fkey FOREIGN KEY (cultivar_id)
                REFERENCES public.cultivars(id) ON DELETE RESTRICT,
            CONSTRAINT plants_seq_check CHECK (seq >= 1),
            CONSTRAINT plants_status_check CHECK (status = ANY (ARRAY['active'::text,
                'culled'::text, 'destroyed'::text, 'harvested'::text, 'moved'::text])),
            CONSTRAINT plants_org_id_plant_code_key UNIQUE (org_id, plant_code),
            CONSTRAINT plants_batch_id_seq_key UNIQUE (batch_id, seq)
        )
        """
    )
    op.execute(
        "CREATE INDEX plants_org_batch_idx ON public.plants"
        " USING btree (org_id, batch_id)"
    )
    # Partial index for the common query — the living population of a batch.
    op.execute(
        "CREATE INDEX plants_active_batch_idx ON public.plants"
        " USING btree (batch_id) WHERE status = 'active'"
    )

    # ── plant_phase_events — dated batch-level lifecycle history ──
    # One row per transition. Batch-level by default (plant_id NULL); a per-plant
    # exception (single cull/destroy) sets plant_id. `qty` records how many
    # plants the event covered so a batch move is auditable without 2000 rows.
    op.execute(
        """
        CREATE TABLE public.plant_phase_events (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            batch_id uuid NOT NULL,
            plant_id uuid,
            event text NOT NULL,
            from_phase text,
            to_phase text,
            qty integer,
            to_room_id uuid,
            occurred_on date DEFAULT CURRENT_DATE NOT NULL,
            reason text,
            note text,
            created_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT plant_phase_events_pkey PRIMARY KEY (id),
            CONSTRAINT plant_phase_events_batch_id_fkey FOREIGN KEY (batch_id)
                REFERENCES public.plant_batches(id) ON DELETE RESTRICT,
            CONSTRAINT plant_phase_events_plant_id_fkey FOREIGN KEY (plant_id)
                REFERENCES public.plants(id) ON DELETE RESTRICT,
            CONSTRAINT plant_phase_events_to_room_id_fkey FOREIGN KEY (to_room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT plant_phase_events_qty_check CHECK (qty IS NULL OR qty >= 0),
            CONSTRAINT plant_phase_events_event_check CHECK (event = ANY (ARRAY['create'::text,
                'move'::text, 'cull'::text, 'destroy'::text, 'harvest'::text, 'note'::text]))
        )
        """
    )
    op.execute(
        "CREATE INDEX plant_phase_events_org_batch_idx ON public.plant_phase_events"
        " USING btree (org_id, batch_id, occurred_on)"
    )

    # ── RLS + audit + grants: identical shape to 0015's rooms/plant_batches ──
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

    # Same guarded grant block as 0015 — CI's pure-alembic build has no app
    # roles; live/test databases do and need the grants immediately.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.cultivars, public.plants, public.plant_phase_events TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.cultivars, public.plants, public.plant_phase_events TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.plant_phase_events")
    op.execute("DROP TABLE public.plants")
    op.execute("ALTER TABLE public.plant_batches DROP CONSTRAINT plant_batches_phase_check")
    op.execute(
        "ALTER TABLE public.plant_batches ADD CONSTRAINT plant_batches_phase_check"
        " CHECK (phase = ANY (ARRAY['clone'::text, 'veg'::text, 'flower'::text,"
        " 'mother'::text, 'drying'::text]))"
    )
    op.execute("DROP INDEX public.plant_batches_org_code_key")
    op.execute("ALTER TABLE public.plant_batches DROP CONSTRAINT plant_batches_cultivar_id_fkey")
    op.execute("ALTER TABLE public.plant_batches DROP COLUMN cultivar_id")
    op.execute("ALTER TABLE public.plant_batches DROP COLUMN code")
    op.execute("DROP TABLE public.cultivars")
