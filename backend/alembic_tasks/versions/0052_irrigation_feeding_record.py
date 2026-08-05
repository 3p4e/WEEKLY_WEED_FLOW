"""irrigation / feeding record — the last Phase 2 cultivation record

Revision ID: 0052
Revises: 0051
Create Date: 2026-08-05

The remaining Phase 2 record named by docs/CULTIVATION-DESIGN-2026-07.md §5:

    "Then irrigation/feeding and IPM, both room-level and dated."

IPM landed with harvest in 0051 because the pre-harvest interval forced the two
to be designed together. Irrigation/feeding has no such downstream gate — a
feed does not block a cut — so it lands on its own here, and is deliberately
the simpler table: a dated, room-level record of what solution went onto a room
(and optionally a batch) and the readings taken around it.

WHY ROOM-LEVEL AND DATED, NOT PER-PLANT AND TIMESTAMPED.

§3 of the design doc is explicit that per-plant tracking is the expensive kind
of record — every plant a row, every feed a row per plant — and that the audit
chain's per-row cost makes it the wrong grain for a daily operation. A feed is
administered to a whole room's reservoir/lines at once; the floor manages it as
"Room GR-2, today, this recipe, this volume, these runoff readings", never as a
per-plant fact. So `room_id` is REQUIRED (a feed with no room is a diary entry,
the same reasoning `ipm_applications_target_scope_check` encodes) and `batch_id`
is optional, for the room that holds more than one cultivar.

Unlike IPM's `applied_at timestamptz` (REI is measured in hours), this is a
`date`: a feed carries no re-entry or pre-harvest interval, so the hour it went
on is not a control input and a day is the grain the floor logs. The API still
resolves "today" at the SITE zone rather than trusting `date.today()` — the same
discipline migration 0050 and harvest.py established — but the column itself is a
plain date.

WHY THE READINGS ARE NULLABLE AND RANGE-CHECKED, NOT REQUIRED.

EC and pH are taken on feed and (separately) on runoff, but not every feed is
metered — a plain top-up may record only a volume, and a diagnostic feed may
record readings and no recipe. NULL therefore means "not measured", distinct
from a measured value. What the CHECKs enforce is that a value that IS present
is physically possible: pH lives on the 0-14 scale, and a volume or conductivity
cannot be negative. A pH of 20 or a negative EC is a data-entry slip every time,
so the database refuses it by any route including a direct SQL fix.

Purely additive: one new table, nothing existing altered. Every new table needs
the `app.fn_audit_row()` trigger or test_audit_coverage.py (default-deny) fails
the build — added below alongside RLS, exactly as 0051 does.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("irrigation_events",)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.irrigation_events (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            room_id uuid NOT NULL,
            batch_id uuid,
            applied_on date DEFAULT CURRENT_DATE NOT NULL,
            method text,
            water_volume_l numeric,
            feed_ec numeric,
            feed_ph numeric,
            runoff_ec numeric,
            runoff_ph numeric,
            nutrients text,
            applied_by uuid NOT NULL,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            created_by uuid NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_by uuid,
            CONSTRAINT irrigation_events_pkey PRIMARY KEY (id),
            CONSTRAINT irrigation_events_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT irrigation_events_batch_id_fkey FOREIGN KEY (batch_id)
                REFERENCES public.plant_batches(id) ON DELETE RESTRICT,
            -- Same set as ipm_applications_method_check's shape: a named method
            -- vocabulary so the board can group feeds, NULL for "not stated".
            CONSTRAINT irrigation_events_method_check CHECK (method IS NULL OR method = ANY (ARRAY[
                'drip'::text, 'hand'::text, 'flood'::text, 'boom'::text, 'other'::text])),
            -- A present reading must be physically possible; NULL = not measured.
            CONSTRAINT irrigation_events_water_check CHECK (water_volume_l IS NULL OR water_volume_l >= 0),
            CONSTRAINT irrigation_events_feed_ec_check CHECK (feed_ec IS NULL OR feed_ec >= 0),
            CONSTRAINT irrigation_events_runoff_ec_check CHECK (runoff_ec IS NULL OR runoff_ec >= 0),
            CONSTRAINT irrigation_events_feed_ph_check CHECK (feed_ph IS NULL OR (feed_ph >= 0 AND feed_ph <= 14)),
            CONSTRAINT irrigation_events_runoff_ph_check CHECK (runoff_ph IS NULL OR (runoff_ph >= 0 AND runoff_ph <= 14))
        )
        """
    )
    # The board and the room drill-down both read "feeds for this org, newest
    # first" and "feeds for this room, newest first"; batch is a secondary filter.
    op.execute(
        "CREATE INDEX irrigation_events_org_applied_idx ON public.irrigation_events"
        " USING btree (org_id, applied_on DESC)"
    )
    op.execute(
        "CREATE INDEX irrigation_events_room_idx ON public.irrigation_events"
        " USING btree (room_id, applied_on DESC)"
    )
    op.execute(
        "CREATE INDEX irrigation_events_batch_idx ON public.irrigation_events"
        " USING btree (batch_id, applied_on DESC) WHERE batch_id IS NOT NULL"
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

    # Same guarded grant block as 0045/0048/0049/0051 — CI's pure-alembic build
    # has no app roles; live and test databases do and need the grants at once.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.irrigation_events TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.irrigation_events TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.irrigation_events")
