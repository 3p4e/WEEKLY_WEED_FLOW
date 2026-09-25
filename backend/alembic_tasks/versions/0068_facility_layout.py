"""the as-built facility layout: one row per room on the ground-floor plan

Revision ID: 0068
Revises: 0067
Create Date: 2026-09-06

The owner supplied the Archicad A0 ground-floor sheet for the Petrovec site on
2026-09-05 and asked that the app know the real facility: every room, its
GACP / GMP standing, its cleanliness classification, and a visual reference for
each one. `docs/FACILITY-LAYOUT-2026-09.md` records how the 191 rooms were read
off the drawing and what the drawing does and does not say.

This is a REGISTER, deliberately separate from `rooms`:

  rooms            — the handful of places the app SCHEDULES. A batch sits in a
                     room, a clone run happens in a room, decon cycles a room.
                     Codes are lowercase slugs, kinds are the cultivation
                     vocabulary, and the table is small by design.
  facility_rooms   — the building as drawn. 191 rooms including corridors,
                     air locks, plant rooms, toilets and fire escapes, keyed by
                     the architect's own code (C180, F104, T160), carrying the
                     stamped area and perimeter and an anchor point on the sheet.

Folding the second into the first would have been wrong twice over: it would
put 160 rooms nobody schedules into every room picker, and it would force the
architect's codes and the operational slugs to be the same string. So the two
are linked instead — rooms.facility_room_id says "this grow room is C180 on the
plan" — and either can exist without the other.

`grade` is nullable and starts null on purpose. No cleanliness grade appears
anywhere on the drawing; assigning one is a QA decision, and the app must not
invent it. `regime` is different: the owner has already stated the rule
("harvest, cure and defoliating end of GACP -> start of GMP process") and the
building's air-lock topology agrees with it, so it is seeded.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0068"
down_revision: Union[str, None] = "0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("facility_rooms",)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.facility_rooms (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            code text NOT NULL,
            name_en text,
            name_mk text,
            wing text NOT NULL,
            zone text,
            regime text,
            grade text,
            floor text DEFAULT 'ground'::text NOT NULL,
            area_m2 numeric,
            net_area_m2 numeric,
            perimeter_m numeric,
            plan_x numeric,
            plan_y numeric,
            department_id uuid,
            source text,
            notes text,
            is_active boolean DEFAULT true NOT NULL,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT facility_rooms_pkey PRIMARY KEY (id),
            CONSTRAINT facility_rooms_org_id_floor_code_key UNIQUE (org_id, floor, code),
            CONSTRAINT facility_rooms_department_id_fkey FOREIGN KEY (department_id)
                REFERENCES public.departments(id) ON DELETE SET NULL,
            CONSTRAINT facility_rooms_wing_check CHECK (wing = ANY (ARRAY['cultivation'::text,
                'processing'::text, 'extraction'::text, 'main'::text, 'technical'::text,
                'washing'::text, 'other'::text])),
            CONSTRAINT facility_rooms_zone_check CHECK ((zone IS NULL) OR (zone = ANY (ARRAY[
                'cultivation'::text, 'post_harvest'::text, 'production'::text, 'quality'::text,
                'warehouse'::text, 'airlock'::text, 'circulation'::text, 'personnel'::text,
                'technical'::text, 'utility'::text, 'waste'::text, 'egress'::text]))),
            CONSTRAINT facility_rooms_regime_check CHECK ((regime IS NULL) OR (regime = ANY (ARRAY[
                'GACP'::text, 'GMP'::text, 'SUPPORT'::text]))),
            CONSTRAINT facility_rooms_area_check CHECK (
                ((area_m2 IS NULL) OR (area_m2 > (0)::numeric))
                AND ((net_area_m2 IS NULL) OR (net_area_m2 > (0)::numeric))
                AND ((perimeter_m IS NULL) OR (perimeter_m > (0)::numeric))),
            CONSTRAINT facility_rooms_plan_check CHECK (
                ((plan_x IS NULL) = (plan_y IS NULL))
                AND ((plan_x IS NULL) OR ((plan_x >= (0)::numeric) AND (plan_x <= (1)::numeric)
                     AND (plan_y >= (0)::numeric) AND (plan_y <= (1)::numeric))))
        )
        """
    )
    op.execute(
        "CREATE INDEX facility_rooms_org_zone_idx ON public.facility_rooms"
        " USING btree (org_id, zone)"
    )
    op.execute(
        "CREATE INDEX facility_rooms_department_id_idx ON public.facility_rooms"
        " USING btree (department_id)"
    )

    # The link, from the operational room to the room on the drawing. Nullable
    # both ways: a grow room may not have been located on the plan yet, and most
    # rooms on the plan are never scheduled.
    op.execute("ALTER TABLE public.rooms ADD COLUMN facility_room_id uuid")
    op.execute("ALTER TABLE public.rooms ADD CONSTRAINT rooms_facility_room_id_fkey"
               " FOREIGN KEY (facility_room_id) REFERENCES public.facility_rooms(id)"
               " ON DELETE SET NULL")
    op.execute("CREATE UNIQUE INDEX rooms_facility_room_id_key ON public.rooms"
               " USING btree (facility_room_id) WHERE (facility_room_id IS NOT NULL)")

    # ── RLS + audit + grants: identical shape to 0065 / 0066 ──────────────
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
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.facility_rooms TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.facility_rooms TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX public.rooms_facility_room_id_key")
    op.execute("ALTER TABLE public.rooms DROP CONSTRAINT rooms_facility_room_id_fkey")
    op.execute("ALTER TABLE public.rooms DROP COLUMN facility_room_id")
    op.execute("DROP TABLE public.facility_rooms")
