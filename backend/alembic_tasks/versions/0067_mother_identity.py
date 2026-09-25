"""mother identity: campaign, product, mother number, generation, stock number

Revision ID: 0067
Revises: 0066
Create Date: 2026-09-05

The owner's mother-plant ID (2026-09-05):

    GP26_S1M03-2_020

  GP26  strain abbreviation + potency grade — i.e. the ImB PRODUCT (0066);
  _S1   the selection campaign, numbered FACILITY-WIDE: a selection event
        from seeds, new clones or phenotypes, "the 3 means this is third
        such event";
  M03   "motherplant number 03 of the corresponding Selection campaign";
  -2    the mother's own generation — a second-generation clone of the
        initial mother;
  _020  "individual mother plant clone number in stock", 001-999.

0065 stored that as one free-text `code`. A string cannot answer "what is the
next mother number in this campaign", cannot stop two mothers claiming one
line, and cannot be rebuilt if a segment is mistyped — so the segments become
columns and the code is composed from them (app/plantids.mother_code) and
stored for display and lookup.

`generation` also settles a name collision: the API's derived `generations`
meant "how many clone runs this mother was cut in", which is not the owner's
-2 at all. That reading is renamed `times_cut` in app/api/propagation.py, and
`generation` now means only what the owner means by it.

`cutting_no` on clone_run_mothers becomes NOT NULL: it is the xx in a clone's
own id (GP26_S1M03-2_020-03.147 — the third cutting from that mother), so a
cutting without a number cannot name the plants it produced.

STRICT, AND ALLOWED TO BE. mother_plants is empty in production (the bank
shipped days ago and is filled from the UI), so rather than back-fill
invented campaigns and numbers onto rows that predate the scheme, this
migration refuses to run over any existing row and says why.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0067"
down_revision: Union[str, None] = "0066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM public.mother_plants)
             OR EXISTS (SELECT 1 FROM public.clone_run_mothers) THEN
            RAISE EXCEPTION '0067: mother_plants / clone_run_mothers carry rows that predate the'
              ' structured mother ID (campaign, product, mother number, generation, stock number).'
              ' Production is empty by design; purge these rows, then upgrade.';
          END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE public.mother_plants ADD COLUMN product_id uuid NOT NULL")
    op.execute("ALTER TABLE public.mother_plants ADD COLUMN campaign_id uuid NOT NULL")
    op.execute("ALTER TABLE public.mother_plants ADD COLUMN mother_no integer NOT NULL")
    op.execute("ALTER TABLE public.mother_plants ADD COLUMN generation integer DEFAULT 1 NOT NULL")
    op.execute("ALTER TABLE public.mother_plants ADD COLUMN stock_no integer NOT NULL")
    op.execute("ALTER TABLE public.mother_plants ADD COLUMN parent_id uuid")
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_product_id_fkey"
        " FOREIGN KEY (product_id) REFERENCES public.qc_products(id) ON DELETE RESTRICT")
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_campaign_id_fkey"
        " FOREIGN KEY (campaign_id) REFERENCES public.selection_campaigns(id) ON DELETE RESTRICT")
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_parent_id_fkey"
        " FOREIGN KEY (parent_id) REFERENCES public.mother_plants(id) ON DELETE RESTRICT")
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_mother_no_check"
        " CHECK ((mother_no >= 1) AND (mother_no <= 99))")
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_generation_check"
        " CHECK (generation >= 1)")
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_stock_no_check"
        " CHECK ((stock_no >= 1) AND (stock_no <= 999))")
    # A first-generation mother was not cut from another mother; a later one
    # may name the mother it came from, but is never required to.
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_first_generation_check"
        " CHECK ((generation > 1) OR (parent_id IS NULL))")
    # One plant per line position — the id must identify exactly one mother.
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_line_key"
        " UNIQUE (org_id, campaign_id, product_id, mother_no, generation, stock_no)")

    op.execute("ALTER TABLE public.clone_run_mothers ALTER COLUMN cutting_no SET NOT NULL")

    # The clone run's ladder snapshot is replaced by its product (0066): the
    # official page is what the material is propagated against.
    op.execute("ALTER TABLE public.clone_runs DROP CONSTRAINT clone_runs_potency_spec_id_fkey")
    op.execute("ALTER TABLE public.clone_runs DROP COLUMN potency_spec_id")


def downgrade() -> None:
    op.execute("ALTER TABLE public.clone_runs ADD COLUMN potency_spec_id uuid")
    op.execute(
        "ALTER TABLE public.clone_runs ADD CONSTRAINT clone_runs_potency_spec_id_fkey"
        " FOREIGN KEY (potency_spec_id) REFERENCES public.qc_potency_specs(id) ON DELETE SET NULL")

    op.execute("ALTER TABLE public.clone_run_mothers ALTER COLUMN cutting_no DROP NOT NULL")

    for con in ("mother_plants_line_key", "mother_plants_first_generation_check",
                "mother_plants_stock_no_check", "mother_plants_generation_check",
                "mother_plants_mother_no_check", "mother_plants_parent_id_fkey",
                "mother_plants_campaign_id_fkey", "mother_plants_product_id_fkey"):
        op.execute(f"ALTER TABLE public.mother_plants DROP CONSTRAINT {con}")
    for col in ("parent_id", "stock_no", "generation", "mother_no", "campaign_id", "product_id"):
        op.execute(f"ALTER TABLE public.mother_plants DROP COLUMN {col}")
