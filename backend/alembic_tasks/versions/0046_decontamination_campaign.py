"""decontamination: per-room signed cycle, bleach log, RT-qPCR swab gate

Revision ID: 0046
Revises: 0045
Create Date: 2026-07-30

The record the CEO's HLVd eradication plan demands this week — the plan itself
names the documents (QASOP 032 A01 room decontamination batch record, QCSOP 024
sampling/RT-qPCR) and states the mechanism plainly: "Tracking cleaning per room
against a defined cycle, rather than as daily tasks on a schedule, is what
prevents a step being lost." This is a SEPARATE, EARLIER record from cultivation
Phase 1 (0045) — it precedes the new genetics (arriving 13-19.08) rather than
tracking them, and does not touch plant_batches/plants/cultivars at all.

Per the plan (docs/CULTIVATION-DESIGN-2026-07.md §5b):
  - Every room passes 5 steps IN ORDER: dry clean, detergent wash, rinse 1 +
    white-cloth gate (a second person's check — soiled cloth means wash again,
    the bleach does not go on), bleach (5,000 ppm, min 2 min wet), rinse 2
    (same day). A room is not "finished" until every step has a signature.
  - Every bleach bucket is strip-verified and logged — the plan calls this
    "the cheapest, most valuable record" and the #1 risk in the register is a
    crew defaulting to housekeeping strength without one.
  - A room is released by the QA Manager, in writing, against a complete batch
    record: every step signed, ALL swab/RT-qPCR results within limits. Nobody
    else releases a room, and no room is released verbally or on a pending
    result.

Room codes are NOT seeded here. The plan's own Appendix B lists "Rooms 1-6 ->
C180-C185 mapping is an assumption requiring confirmation" — this migration
must not bake in an unconfirmed mapping. Rooms are provisioned through the
existing ADMIN-only POST /facility/rooms, same as always.

Purely additive; no data migration.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("decon_room_cycles", "decon_step_signoffs", "decon_bleach_log", "decon_swabs")


def upgrade() -> None:
    # ── decon_room_cycles — the room's batch record shell ──
    op.execute(
        """
        CREATE TABLE public.decon_room_cycles (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            room_id uuid NOT NULL,
            campaign text NOT NULL,
            status text DEFAULT 'in_progress'::text NOT NULL,
            started_on date DEFAULT CURRENT_DATE NOT NULL,
            sealed_at timestamp with time zone,
            released_by uuid,
            released_at timestamp with time zone,
            release_note text,
            note text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT decon_room_cycles_pkey PRIMARY KEY (id),
            CONSTRAINT decon_room_cycles_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT decon_room_cycles_status_check CHECK (status = ANY (ARRAY[
                'in_progress'::text, 'awaiting_verification'::text,
                'released'::text, 'failed'::text]))
        )
        """
    )
    # One OPEN cycle per room per campaign — a room mid-cycle cannot be started
    # twice. A room CAN get a new cycle in a later campaign (a partial unique
    # index on the non-terminal statuses, rather than a plain unique
    # constraint on (room_id, campaign), is what allows that).
    op.execute(
        "CREATE UNIQUE INDEX decon_room_cycles_open_idx ON public.decon_room_cycles"
        " (org_id, room_id, campaign) WHERE status IN ('in_progress', 'awaiting_verification')"
    )
    op.execute(
        "CREATE INDEX decon_room_cycles_org_campaign_idx ON public.decon_room_cycles"
        " USING btree (org_id, campaign)"
    )

    # ── decon_step_signoffs — the 5-step signed sequence, one row per attempt ──
    # A room can revisit detergent_wash/rinse1_whitecloth after a failed
    # white-cloth check (the plan: "soiled cloth -> wash again"), so this is an
    # append-only log of attempts, not one row per step. The CURRENT state of a
    # cycle is derived by the API from the latest signoff per step, not stored
    # redundantly here.
    op.execute(
        """
        CREATE TABLE public.decon_step_signoffs (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            cycle_id uuid NOT NULL,
            step text NOT NULL,
            passed boolean,
            signed_by uuid NOT NULL,
            signed_at timestamp with time zone DEFAULT now() NOT NULL,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT decon_step_signoffs_pkey PRIMARY KEY (id),
            CONSTRAINT decon_step_signoffs_cycle_id_fkey FOREIGN KEY (cycle_id)
                REFERENCES public.decon_room_cycles(id) ON DELETE RESTRICT,
            CONSTRAINT decon_step_signoffs_step_check CHECK (step = ANY (ARRAY[
                'dry_clean'::text, 'detergent_wash'::text,
                'rinse1_whitecloth'::text, 'bleach'::text, 'rinse2'::text]))
        )
        """
    )
    op.execute(
        "CREATE INDEX decon_step_signoffs_cycle_idx ON public.decon_step_signoffs"
        " USING btree (cycle_id, signed_at)"
    )

    # ── decon_bleach_log — "the cheapest, most valuable record" per the plan ──
    op.execute(
        """
        CREATE TABLE public.decon_bleach_log (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            room_id uuid NOT NULL,
            cycle_id uuid,
            mixed_at timestamp with time zone DEFAULT now() NOT NULL,
            ppm_strip_reading integer NOT NULL,
            mixed_by uuid NOT NULL,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT decon_bleach_log_pkey PRIMARY KEY (id),
            CONSTRAINT decon_bleach_log_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT decon_bleach_log_cycle_id_fkey FOREIGN KEY (cycle_id)
                REFERENCES public.decon_room_cycles(id) ON DELETE RESTRICT,
            CONSTRAINT decon_bleach_log_ppm_check CHECK (ppm_strip_reading >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX decon_bleach_log_org_room_idx ON public.decon_bleach_log"
        " USING btree (org_id, room_id, mixed_at)"
    )

    # ── decon_swabs — RT-qPCR verification; a positive/pending swab blocks release ──
    op.execute(
        """
        CREATE TABLE public.decon_swabs (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            room_id uuid NOT NULL,
            cycle_id uuid,
            swab_code text NOT NULL,
            location_desc text,
            taken_at timestamp with time zone DEFAULT now() NOT NULL,
            taken_by uuid NOT NULL,
            lab_name text,
            sent_at timestamp with time zone,
            result text DEFAULT 'pending'::text NOT NULL,
            ct_value numeric,
            result_at timestamp with time zone,
            action_taken text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT decon_swabs_pkey PRIMARY KEY (id),
            CONSTRAINT decon_swabs_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT decon_swabs_cycle_id_fkey FOREIGN KEY (cycle_id)
                REFERENCES public.decon_room_cycles(id) ON DELETE RESTRICT,
            CONSTRAINT decon_swabs_org_id_swab_code_key UNIQUE (org_id, swab_code),
            CONSTRAINT decon_swabs_result_check CHECK (result = ANY (ARRAY[
                'pending'::text, 'negative'::text, 'positive'::text,
                'inconclusive'::text]))
        )
        """
    )
    op.execute(
        "CREATE INDEX decon_swabs_org_room_idx ON public.decon_swabs"
        " USING btree (org_id, room_id)"
    )
    op.execute(
        "CREATE INDEX decon_swabs_cycle_idx ON public.decon_swabs USING btree (cycle_id)"
    )

    # ── RLS + audit + grants: identical shape to 0015/0045 ──
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
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.decon_room_cycles,
              public.decon_step_signoffs, public.decon_bleach_log, public.decon_swabs
              TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.decon_room_cycles,
              public.decon_step_signoffs, public.decon_bleach_log, public.decon_swabs
              TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.decon_swabs")
    op.execute("DROP TABLE public.decon_bleach_log")
    op.execute("DROP TABLE public.decon_step_signoffs")
    op.execute("DROP TABLE public.decon_room_cycles")
