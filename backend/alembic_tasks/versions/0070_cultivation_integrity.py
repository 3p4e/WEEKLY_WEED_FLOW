"""cultivation integrity: a mother number names one plant line per campaign

Revision ID: 0070
Revises: 0069
Create Date: 2026-09-27

The 2026-09-27 review of the cultivation domain (docs/review-2026-09-27/
cultivation-schema.md, CS-04) found that "M03 of campaign S1" could name
several different mothers: the line key from 0067 included product_id, so
GP26_S1M03-1_001 and OPM22_S1M03-1_001 were both accepted, even though the
owner's convention is "M03 = motherplant number 03 of the corresponding
Selection campaign" — the number counts per campaign, whatever the strain.

So the line key drops the product: (org, campaign, mother_no, generation,
stock_no) identifies exactly one plant. Which product a mother number belongs
to is then a property of the number itself, enforced in app/api/propagation.py
under an advisory lock per campaign (a mother_no already used in the campaign
by another product is refused with 422), and the next-number reads happen
under the same lock so two registrations at once cannot both take M05.

WHAT THIS DOES NOT CHANGE, AND WHY IT IS SAFE. Production's cultivation tables
are empty (docs/HANDOFF.md, 2026-09-27: no plant_batches beyond the demo org,
no plants, no mother_plants — 0067 already refused to run over any mother row
and ran clean). A constraint swap on an empty table cannot fail; on a table
that did hold two mothers sharing a line across products, the ADD CONSTRAINT
would refuse, which is the right outcome — such rows would be the defect this
migration exists to prevent, and they need a human, not a back-fill.

Two application-level conventions changed in the same review land with this
revision but need no DDL, and are recorded here so a reader of the chain sees
where they entered:

  - the legacy plant id (a plant with no known mother) is now
    <clone-date>_<batch code>_<seq> instead of <clone-date>_<cultivar>_<seq>
    (CS-02): two batches of one cultivar cloned the same day used to compute
    the same codes and the second batch's fill hit plants_org_id_plant_code_key
    on every retry. plant_code is free text, so no column changes; production
    holds no plants, so no existing id is renamed.
  - cutting numbers stay 01-99 (clone_run_mothers_cutting_no_check is
    unchanged). The owner wrote "xx = 00-99"; whether the floor labels its
    first cutting 00 or 01 is still to be confirmed (CS-11), and the CHECK is
    the one place that changes if it is 00.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0070"
down_revision: Union[str, None] = "0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.mother_plants DROP CONSTRAINT mother_plants_line_key")
    # One plant per line position, and the line no longer carries the product:
    # M03 of S1 is one line whatever the strain, so the product is a property
    # of the number, not part of the key.
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_line_key"
        " UNIQUE (org_id, campaign_id, mother_no, generation, stock_no)")


def downgrade() -> None:
    op.execute("ALTER TABLE public.mother_plants DROP CONSTRAINT mother_plants_line_key")
    op.execute(
        "ALTER TABLE public.mother_plants ADD CONSTRAINT mother_plants_line_key"
        " UNIQUE (org_id, campaign_id, product_id, mother_no, generation, stock_no)")
