"""decontamination: frozen positive controls + tool-sterilisation log

Revision ID: 0047
Revises: 0046
Create Date: 2026-07-30

Two more records the eradication plan calls for, both of which it ranks above
most of the equipment spend, and both of which are worthless if captured late.

**Frozen positive controls** (plan §11 priority 7, §27). Taken 30.07 BEFORE the
cull: infected leaf, root, and a scraping from a C171 table groove. The plan's
reasoning is the point — "Makes every later negative falsifiable. Free,
irreplaceable once plants are gone." Once the destruction is done there is no
way back to this material, so the record has a hard deadline of today and
nothing downstream can substitute for it: without a positive control, a negative
swab result cannot be distinguished from a failed assay.

**Tool sterilisation** (plan §28 control 2, ranked *decisive*). "Two-blade
rotation, one soaking in 10,000 ppm while the other is used, min 2 min.
Dedicated per room, colour-coded. Not flame, not alcohol, not hot water — none
work." Mechanical transmission on blades is HLVd's primary route, so this log is
the evidence that the control was actually operated rather than merely briefed.
Note the concentration: tools and drains are 10,000 ppm, DOUBLE the 5,000 ppm
surface specification in decon_bleach_log — they are deliberately separate
records with separate targets, and conflating them would under-dose the tools.

Purely additive; no data migration. Both tables key on rooms only (a control
sample and a tool bucket belong to a room, not necessarily to one cleaning
cycle), with an optional cycle_id for the common case where they do.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("decon_positive_controls", "decon_tool_log")


def upgrade() -> None:
    # ── decon_positive_controls — irreplaceable once the plants are gone ──
    op.execute(
        """
        CREATE TABLE public.decon_positive_controls (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            control_code text NOT NULL,
            room_id uuid,
            material text NOT NULL,
            source_desc text,
            taken_at timestamp with time zone DEFAULT now() NOT NULL,
            taken_by uuid NOT NULL,
            storage_location text,
            frozen boolean DEFAULT true NOT NULL,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT decon_positive_controls_pkey PRIMARY KEY (id),
            CONSTRAINT decon_positive_controls_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT decon_positive_controls_org_id_control_code_key
                UNIQUE (org_id, control_code),
            -- The three material types the plan names, plus 'other' so an
            -- unforeseen sample is recorded rather than skipped.
            CONSTRAINT decon_positive_controls_material_check CHECK (material = ANY (ARRAY[
                'leaf'::text, 'root'::text, 'surface_scraping'::text, 'other'::text]))
        )
        """
    )
    op.execute(
        "CREATE INDEX decon_positive_controls_org_idx ON public.decon_positive_controls"
        " USING btree (org_id, taken_at)"
    )

    # ── decon_tool_log — the 10,000 ppm blade soak, twice the surface spec ──
    op.execute(
        """
        CREATE TABLE public.decon_tool_log (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            room_id uuid NOT NULL,
            cycle_id uuid,
            tool_set text NOT NULL,
            ppm_strip_reading integer NOT NULL,
            soak_minutes numeric,
            checked_at timestamp with time zone DEFAULT now() NOT NULL,
            checked_by uuid NOT NULL,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT decon_tool_log_pkey PRIMARY KEY (id),
            CONSTRAINT decon_tool_log_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT decon_tool_log_cycle_id_fkey FOREIGN KEY (cycle_id)
                REFERENCES public.decon_room_cycles(id) ON DELETE RESTRICT,
            CONSTRAINT decon_tool_log_ppm_check CHECK (ppm_strip_reading >= 0),
            CONSTRAINT decon_tool_log_soak_check CHECK (soak_minutes IS NULL OR soak_minutes >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX decon_tool_log_org_room_idx ON public.decon_tool_log"
        " USING btree (org_id, room_id, checked_at)"
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
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.decon_positive_controls,
              public.decon_tool_log TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.decon_positive_controls,
              public.decon_tool_log TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.decon_tool_log")
    op.execute("DROP TABLE public.decon_positive_controls")
