"""facility: rooms + plant batches (live cultivation occupancy)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-15

The owner's facility board: how many plants are in each grow room, what
strain, and what cultivation phase (clones/nursery, vegetation, flowering).
Modeled after the owner's mockup facility screen (design/mass-weed-mockup/
facility.html) minus environment telemetry — no sensor feed exists.

- `rooms` — the physical registry (6 grow rooms + nursery + veg hall at
  Purely Plant; org-specific rows are seeded via the ADMIN API, not here).
- `plant_batches` — one row per strain-group in a room: strain, live plant
  count, phase, when the phase started. Closing a batch (harvest/cull) sets
  is_active=false; history stays queryable and fully audited.

Both tables carry the standard hash-chained audit trigger (these are real
work/inventory records, unlike the 0013 awareness tables) and the same
org_isolation RLS shape as departments — role gating (read: everyone above
base USER; write: cultivation manager + executives + ADMIN) lives at the
API layer like every other role rule.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.rooms (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            code text NOT NULL,
            name text NOT NULL,
            name_mk text,
            kind text DEFAULT 'flower'::text NOT NULL,
            sort integer DEFAULT 0 NOT NULL,
            is_active boolean DEFAULT true NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT rooms_pkey PRIMARY KEY (id),
            CONSTRAINT rooms_kind_check CHECK (kind = ANY (ARRAY['nursery'::text, 'veg'::text, 'flower'::text, 'mother'::text, 'dry'::text, 'other'::text])),
            CONSTRAINT rooms_org_id_code_key UNIQUE (org_id, code)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.plant_batches (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            room_id uuid NOT NULL,
            strain text NOT NULL,
            plant_count integer NOT NULL,
            phase text NOT NULL,
            phase_since date DEFAULT CURRENT_DATE NOT NULL,
            note text,
            is_active boolean DEFAULT true NOT NULL,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT plant_batches_pkey PRIMARY KEY (id),
            CONSTRAINT plant_batches_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT plant_batches_plant_count_check CHECK (plant_count >= 0),
            CONSTRAINT plant_batches_phase_check CHECK (phase = ANY (ARRAY['clone'::text, 'veg'::text, 'flower'::text, 'mother'::text, 'drying'::text]))
        )
        """
    )
    for tbl in ("rooms", "plant_batches"):
        op.execute(f"ALTER TABLE ONLY public.{tbl} FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY org_isolation ON public.{tbl}"
            f" USING ((org_id = app.current_org_id()))"
            f" WITH CHECK ((org_id = app.current_org_id()))"
        )
    op.execute(
        "CREATE TRIGGER audit_rooms AFTER INSERT OR DELETE OR UPDATE ON public.rooms"
        " FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE TRIGGER audit_plant_batches AFTER INSERT OR DELETE OR UPDATE ON public.plant_batches"
        " FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
    )
    op.execute(
        "CREATE INDEX plant_batches_org_room_idx ON public.plant_batches"
        " USING btree (org_id, room_id) WHERE is_active"
    )

    # Same guarded grant block as 0007/0011/0013 — CI's pure-alembic build has
    # no app roles; live/test databases do and need the grants immediately.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.rooms, public.plant_batches TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.rooms, public.plant_batches TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.plant_batches")
    op.execute("DROP TABLE public.rooms")
