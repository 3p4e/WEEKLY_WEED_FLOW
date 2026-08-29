"""one physical sample carries one active custody record (audit gap)

The 2026-08 audit reported that nothing stops one physical sample being linked
to two custody records, and it was recorded rather than fixed. Fixing it needed
the right table identified first, because the obvious candidate is the wrong
one:

`qc_chain_of_custody` is an append-only log of TRANSFER EVENTS. Many rows per
sample is precisely what it is for — field-to-lab, lab-internal, lab-to-disposal
— and a uniqueness constraint there would break the chain it exists to record.
It is deliberately untouched.

The gap is the custody RECORD of the specimen. `qc_sample_field_records` (the
SFR — one sampling act, one specimen, its transport and receipt) carries a plain
nullable `sample_id` with no uniqueness at all; the only unique key on the table
is `(org_id, sfr_number)`. `qc_sampling_requests` has the same shape. So two
active field records could each claim the same `qc_samples` row, and every
downstream reader — custody chain, receipt condition, the CoA lineage — would
have two mutually inconsistent answers to "where did this sample come from and
who handled it", with nothing marking either as wrong.

PARTIAL, and excluding CANCELLED on purpose. Both tables carry CANCELLED in
their status lifecycle, and an SFR/RQS raised in error is cancelled rather than
deleted (`_SFR_TRANSITIONS`, `_RQS_STATUSES` in app/api/qc/custody.py). A plain
unique index would make that correction impossible: cancel the botched record,
re-issue for the same physical sample, and the dead row would still hold the
link. Excluding CANCELLED keeps the cancel-and-reissue flow legal while still
allowing only ONE live claim at a time.

No org_id in the key: `sample_id` is a uuid PK from `qc_samples`, globally
unique already, and the FK plus RLS keep an org from referencing another org's
sample. Adding org_id would weaken the constraint, not strengthen it — two orgs
could then both claim one sample id.

Pre-flight on production before writing this (the convention from
DEPLOY-2026-08-26-v90.md): zero duplicate active links in either table, and
both tables empty. Additive index only — the running backend writes these
columns from app/api/qc/custody.py alone, which now rejects a duplicate link
with a 409 before reaching the index.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0063"
down_revision: Union[str, None] = "0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX qc_sfr_sample_active_uniq"
        " ON public.qc_sample_field_records (sample_id)"
        " WHERE ((sample_id IS NOT NULL) AND (status <> 'CANCELLED'::text))"
    )
    op.execute(
        "CREATE UNIQUE INDEX qc_rqs_sample_active_uniq"
        " ON public.qc_sampling_requests (sample_id)"
        " WHERE ((sample_id IS NOT NULL) AND (status <> 'CANCELLED'::text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.qc_rqs_sample_active_uniq")
    op.execute("DROP INDEX IF EXISTS public.qc_sfr_sample_active_uniq")
