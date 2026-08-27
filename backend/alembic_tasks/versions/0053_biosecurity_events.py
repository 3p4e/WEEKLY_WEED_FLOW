"""biosecurity events — the four remaining §5c record types, one table

Revision ID: 0053
Revises: 0052
Create Date: 2026-08-05

docs/CULTIVATION-DESIGN-2026-07.md §5c lists four plan requirements still marked
"NOT built", and says of them plainly:

    "The unbuilt rows are all *additional record types of the same shape* as
     those already built, not changes to the model."

They are:
  - AHU filter pull/refit (§18);
  - disinfection-mat refill + strip verification (§20);
  - contact plates for drying/curing, and the sentinel bioassay (§27);
  - gowning / zone-crossing control (§23, §28 control 5).

WHY ONE TABLE WITH A `kind`, NOT FOUR TABLES.

Each is the same shape: a dated biosecurity check, performed somewhere (a room,
an AHU, a mat station, a gowning threshold) by someone, that either passes or
does not, and — when it does not — must carry the action taken. That last clause
is the one real invariant, and it is identical across all four (the decon swab's
"a positive needs a stated action" rule, §27). Four near-identical tables would
duplicate that invariant four times and give it four chances to drift. A single
`biosecurity_events` table with a `kind` discriminator keeps the rule in one
CHECK and reads as one board. This is the same call the app already makes for
`events` and `audit_log`: heterogeneous-but-similar records in one typed log.

The columns that are specific to a kind are nullable and named generically:
`subject` (which filter / which mat / which plate location / who crossed),
`measure_value` + `measure_unit` (ppm for a mat strip, CFU for a plate; NULL for
a gowning check that measures nothing), `result`, and `action_taken`.

THE ONE INVARIANT, IN THE DATABASE.

`biosecurity_events_action_on_fail_check`: a result of `fail` or `below_spec`
cannot be recorded without a non-blank `action_taken`. A failed biosecurity
check with no stated response is the exact gap §27 exists to close — a below-spec
mat or a positive plate that nobody did anything about — so the database refuses
it by any route, a direct SQL fix at 2am included. `pass` and `pending` need no
action; NULL result (a plate placed but not yet read) is a `pending`-shaped
state and also needs none.

Purely additive: one new table, nothing existing altered. RLS + the
app.fn_audit_row() trigger + the guarded grant block, exactly as 0051/0052.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("biosecurity_events",)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.biosecurity_events (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            kind text NOT NULL,
            room_id uuid,
            location text,
            occurred_on date DEFAULT CURRENT_DATE NOT NULL,
            subject text,
            action text,
            measure_value numeric,
            measure_unit text,
            result text,
            action_taken text,
            performed_by uuid NOT NULL,
            note text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            created_by uuid NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_by uuid,
            CONSTRAINT biosecurity_events_pkey PRIMARY KEY (id),
            CONSTRAINT biosecurity_events_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            -- The four §5c record types, plus the sentinel bioassay that shares
            -- §27's row with the contact plate. Stay in step with the tuple in
            -- app/api/biosecurity.py.
            CONSTRAINT biosecurity_events_kind_check CHECK (kind = ANY (ARRAY[
                'ahu_filter'::text, 'disinfection_mat'::text, 'contact_plate'::text,
                'sentinel_bioassay'::text, 'gowning'::text])),
            -- NULL = not yet read / not applicable (a plate placed, a gowning
            -- check with no measured outcome). The named set is what the board
            -- colours and what the invariant below keys off.
            CONSTRAINT biosecurity_events_result_check CHECK (result IS NULL OR result = ANY (ARRAY[
                'pass'::text, 'fail'::text, 'below_spec'::text, 'pending'::text])),
            CONSTRAINT biosecurity_events_measure_check CHECK (measure_value IS NULL OR measure_value >= 0),
            -- THE INVARIANT (§27). A failing result must carry the action taken;
            -- a below-spec mat or a positive plate that nobody responded to is
            -- the precise gap this record exists to close.
            CONSTRAINT biosecurity_events_action_on_fail_check CHECK (
                result IS NULL OR result NOT IN ('fail', 'below_spec')
                OR (action_taken IS NOT NULL AND length(btrim(action_taken)) > 0))
        )
        """
    )
    op.execute(
        "CREATE INDEX biosecurity_events_org_kind_idx ON public.biosecurity_events"
        " USING btree (org_id, kind, occurred_on DESC)"
    )
    op.execute(
        "CREATE INDEX biosecurity_events_room_idx ON public.biosecurity_events"
        " USING btree (room_id, occurred_on DESC) WHERE room_id IS NOT NULL"
    )
    # The board's default banner is "unresolved failures": a partial index keeps
    # that scan tiny even as the pass rows accumulate.
    op.execute(
        "CREATE INDEX biosecurity_events_open_fail_idx ON public.biosecurity_events"
        " USING btree (org_id, occurred_on DESC) WHERE result IN ('fail', 'below_spec')"
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
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.biosecurity_events TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.biosecurity_events TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.biosecurity_events")
