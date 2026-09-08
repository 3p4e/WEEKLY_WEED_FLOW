"""propagation: the mother-plant bank and clone runs

Revision ID: 0065
Revises: 0064
Create Date: 2026-09-05

Where a batch begins. Cultivation runs the plant from seed, import or clone up
to the harvest cut (0064, roles.py); this is the clone end of that span, which
until now had no record at all: a batch could be opened in the `clone` phase,
but nothing said which mother plants it was cut from, how many cuttings were
taken, on what date, or against which product specification.

Owner's description (2026-09-05): a mother-plant bank listing the strains and
phenotypes of mother plants, the number of mother plants per strain, every one
with a unique ID, and per mother: when it was last cut for clones and how many
generations of clones it has produced, which mother room it stands in and the
pot number or location within it, and how old it is. Cloning is initiated on a
set date by cultivation or QA, designating the cultivar and the propagation
material's specification.

Three tables, all additive:

1. mother_plants — one row per mother plant. `code` is the unique ID (unique
   per org). `phenotype` is free text and nullable: the app carries no verified
   phenotype data (qc/spec_html.py renders it unselected for the same reason),
   so a mother with no recorded phenotype says nothing rather than something
   invented. `started_on` is the date the mother was established, from which
   its age is derived. `room_id` + `position` are where it stands. Status
   active / retired / destroyed.

2. clone_runs — one cutting event. Which cultivar, on which date (`started_on`,
   the date of cloning initiation), how many cuttings were planned, into which
   room, and — once the cuttings root — which coded batch they became
   (`batch_id`, SET NULL if the batch is ever removed). `potency_spec_id`
   snapshots the cultivar's APPROVED ImB product specification (the potency
   ladder, qc_potency_specs) at initiation, so the record still names the
   specification the material was propagated against after a newer ladder
   supersedes it. Nullable: no approved ladder is a fact, not an error.
   `code` is optional and unique per org where present — the facility has not
   yet said what a clone-run record is numbered like.

3. clone_run_mothers — which mothers the run was cut from, with the cuttings
   taken from each. A mother's "last cut" and "generations" are DERIVED from
   these rows (max started_on, count of runs), never stored as counters that
   could drift from their evidence. CASCADE from the run: a run's mother list
   is part of the run.

RLS, audit trigger and grants exactly as 0045 shaped them for the cultivation
tables.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("mother_plants", "clone_runs", "clone_run_mothers")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.mother_plants (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            cultivar_id uuid NOT NULL,
            code text NOT NULL,
            phenotype text,
            room_id uuid,
            "position" text,
            started_on date,
            source text,
            status text DEFAULT 'active'::text NOT NULL,
            status_since date DEFAULT CURRENT_DATE NOT NULL,
            note text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT mother_plants_pkey PRIMARY KEY (id),
            CONSTRAINT mother_plants_org_id_code_key UNIQUE (org_id, code),
            CONSTRAINT mother_plants_cultivar_id_fkey FOREIGN KEY (cultivar_id)
                REFERENCES public.cultivars(id) ON DELETE RESTRICT,
            CONSTRAINT mother_plants_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT mother_plants_status_check CHECK (status = ANY (ARRAY['active'::text,
                'retired'::text, 'destroyed'::text]))
        )
        """
    )
    op.execute(
        "CREATE INDEX mother_plants_org_cultivar_idx ON public.mother_plants"
        " USING btree (org_id, cultivar_id)"
    )

    op.execute(
        """
        CREATE TABLE public.clone_runs (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            cultivar_id uuid NOT NULL,
            code text,
            started_on date NOT NULL,
            planned_count integer DEFAULT 0 NOT NULL,
            room_id uuid,
            batch_id uuid,
            potency_spec_id uuid,
            status text DEFAULT 'started'::text NOT NULL,
            finished_on date,
            note text,
            created_by uuid,
            updated_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT clone_runs_pkey PRIMARY KEY (id),
            CONSTRAINT clone_runs_cultivar_id_fkey FOREIGN KEY (cultivar_id)
                REFERENCES public.cultivars(id) ON DELETE RESTRICT,
            CONSTRAINT clone_runs_room_id_fkey FOREIGN KEY (room_id)
                REFERENCES public.rooms(id) ON DELETE RESTRICT,
            CONSTRAINT clone_runs_batch_id_fkey FOREIGN KEY (batch_id)
                REFERENCES public.plant_batches(id) ON DELETE SET NULL,
            CONSTRAINT clone_runs_potency_spec_id_fkey FOREIGN KEY (potency_spec_id)
                REFERENCES public.qc_potency_specs(id) ON DELETE SET NULL,
            CONSTRAINT clone_runs_planned_count_check CHECK (planned_count >= 0),
            CONSTRAINT clone_runs_status_check CHECK (status = ANY (ARRAY['started'::text,
                'transplanted'::text, 'failed'::text]))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX clone_runs_org_code_key ON public.clone_runs"
        " USING btree (org_id, code) WHERE (code IS NOT NULL)"
    )
    op.execute(
        "CREATE INDEX clone_runs_org_cultivar_idx ON public.clone_runs"
        " USING btree (org_id, cultivar_id, started_on)"
    )
    op.execute(
        "CREATE INDEX clone_runs_batch_id_idx ON public.clone_runs USING btree (batch_id)"
    )

    op.execute(
        """
        CREATE TABLE public.clone_run_mothers (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            org_id uuid NOT NULL,
            run_id uuid NOT NULL,
            mother_plant_id uuid NOT NULL,
            cuttings integer,
            created_by uuid,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT clone_run_mothers_pkey PRIMARY KEY (id),
            CONSTRAINT clone_run_mothers_run_id_mother_plant_id_key UNIQUE (run_id, mother_plant_id),
            CONSTRAINT clone_run_mothers_run_id_fkey FOREIGN KEY (run_id)
                REFERENCES public.clone_runs(id) ON DELETE CASCADE,
            CONSTRAINT clone_run_mothers_mother_plant_id_fkey FOREIGN KEY (mother_plant_id)
                REFERENCES public.mother_plants(id) ON DELETE RESTRICT,
            CONSTRAINT clone_run_mothers_cuttings_check CHECK ((cuttings IS NULL) OR (cuttings >= 0))
        )
        """
    )
    op.execute(
        "CREATE INDEX clone_run_mothers_mother_plant_id_idx ON public.clone_run_mothers"
        " USING btree (mother_plant_id)"
    )

    # ── RLS + audit + grants: identical shape to 0045's cultivation tables ──
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

    # Same guarded grant block as 0045 — CI's pure-alembic build has no app
    # roles; live/test databases do and need the grants immediately.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.mother_plants, public.clone_runs, public.clone_run_mothers TO app_user;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.mother_plants, public.clone_runs, public.clone_run_mothers TO app_admin;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.clone_run_mothers")
    op.execute("DROP TABLE public.clone_runs")
    op.execute("DROP TABLE public.mother_plants")
