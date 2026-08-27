"""corridor cleaning — the cadence record, not just a cleaning log

Revision ID: 0049
Revises: 0048
Create Date: 2026-07-30

The plan's §25 asks for the cultivation corridors (C146/C152/C155/C169/C170) to
be cleaned **after every waste movement, every 4 hours, and at shift changeover**
during the campaign. That is a *cadence* requirement, and a cadence requirement is
not satisfied by a log: a log answers "was it cleaned" while the requirement asks
"was it cleaned OFTEN ENOUGH, and after the specific events that demand it".

WHY A TRIGGER COLUMN, AND WHY IT IS NOT FREE TEXT
`trigger` records which of the three rules this cleaning discharges. Without it
the four-hourly rule and the after-waste-movement rule are indistinguishable in
the data, so a shift that moved waste four times and cleaned four times looks
identical to one that cleaned on the clock and never after a movement — and only
the second is a breach. The values are a CHECK, not free text, because the whole
point is to count them by class.

WHY manifest_id IS HERE
"After every waste movement" only becomes checkable once the movements themselves
are records, which migration 0048 just made them. A cleaning with
`trigger='waste_movement'` cites the manifest it followed, which turns the rule
into a join: **a disposed manifest with no corridor cleaning recorded after it is
a gap.** That gap is invisible to either table alone. The FK is nullable and
RESTRICT — a clock-driven or shift-driven cleaning cites nothing, and a manifest
must not be deletable out from under a cleaning that references it.

WHAT IS DELIBERATELY NOT MODELLED
No "due at" column and no scheduler row. The cadence is derived from
`cleaned_at` at read time (app/api/decon.py, GET /decon/corridors), because a
stored due-date is a second source of truth that goes stale the moment someone
cleans early, and because a due-date row implies something will act on it. The
four-hour interval lives in ONE place in the API and is reported, not enforced —
software cannot make anyone mop a corridor, and pretending otherwise would put a
false green on a board.

Purely additive: one new table, nothing existing altered, so a v79 backend runs
against this schema unchanged.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("corridor_cleanings",)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.corridor_cleanings (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            room_id uuid NOT NULL,
            campaign text,
            trigger text NOT NULL,
            manifest_id uuid,
            ppm_strip_reading integer,
            cleaned_at timestamp with time zone DEFAULT now() NOT NULL,
            cleaned_by uuid NOT NULL,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT corridor_cleanings_pkey PRIMARY KEY (id),
            CONSTRAINT corridor_cleanings_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT corridor_cleanings_manifest_id_fkey FOREIGN KEY (manifest_id)
                REFERENCES public.waste_manifests(id) ON DELETE RESTRICT,
            -- The plan's three rules, plus 'other' so an unforeseen clean is
            -- recorded rather than filed under a rule it did not discharge.
            CONSTRAINT corridor_cleanings_trigger_check CHECK (trigger = ANY (ARRAY[
                'waste_movement'::text, 'four_hourly'::text, 'shift_change'::text,
                'other'::text])),
            CONSTRAINT corridor_cleanings_ppm_check
                CHECK (ppm_strip_reading IS NULL OR ppm_strip_reading >= 0),
            -- A waste-movement cleaning without the manifest it followed cannot
            -- discharge "after every waste movement" — there is nothing to tie it
            -- to. Enforced in the row because the whole rule depends on the link.
            CONSTRAINT corridor_cleanings_movement_cites_manifest_check CHECK (
                trigger <> 'waste_movement' OR manifest_id IS NOT NULL)
        )
        """
    )
    # The cadence query is "most recent cleaning per corridor", so room leads and
    # time descends.
    op.execute(
        "CREATE INDEX corridor_cleanings_org_room_idx ON public.corridor_cleanings"
        " USING btree (org_id, room_id, cleaned_at DESC)"
    )
    # The after-a-movement join. Partial: clock- and shift-driven cleanings cite
    # no manifest and would only bloat it.
    op.execute(
        "CREATE INDEX corridor_cleanings_manifest_idx ON public.corridor_cleanings"
        " USING btree (manifest_id) WHERE manifest_id IS NOT NULL"
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
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.corridor_cleanings TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.corridor_cleanings TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.corridor_cleanings")
