"""qc_signatures append-only — DB-enforced (RLS)

Revision ID: 0061
Revises: 0060
Create Date: 2026-08-26

Low-severity finding from the 2026-08 full-stack audit: qc_signatures (the
Annex 11 electronic-signature log on certificates — POST /certificates/{id}/
sign, backend/app/api/qc/signatures.py) is described in migration 0034's own
docstring as "an append-only attestation log," but it kept the standard
all-command `org_isolation` RLS policy — UPDATE and DELETE were permitted at
the DB layer for any in-org app_user, the same as an ordinary mutable table.
qc_chain_of_custody started in the identical shape and was correctly hardened
to SELECT+INSERT-only in migration 0042 for the same "must never be rewritten
or reordered" reason. qc_signatures — arguably the more compliance-sensitive
of the two, since it's the literal e-signature record — never received the
equivalent treatment.

Confirmed safe to harden: no UPDATE or DELETE against qc_signatures exists
anywhere in current application code (grepped backend/app/); the one bulk
DELETE in this table's history (migration 0060's dedup step) ran once, via
the admin/BYPASSRLS pool, and is already applied — a future admin-pool
migration is unaffected by an app_user-scoped RLS policy change.

Additive / policy-only; no data migration.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP POLICY org_isolation ON public.qc_signatures")
    op.execute("CREATE POLICY org_isolation_select ON public.qc_signatures"
               " FOR SELECT USING ((org_id = app.current_org_id()))")
    op.execute("CREATE POLICY org_isolation_insert ON public.qc_signatures"
               " FOR INSERT WITH CHECK ((org_id = app.current_org_id()))")


def downgrade() -> None:
    op.execute("DROP POLICY org_isolation_insert ON public.qc_signatures")
    op.execute("DROP POLICY org_isolation_select ON public.qc_signatures")
    op.execute("CREATE POLICY org_isolation ON public.qc_signatures"
               " USING ((org_id = app.current_org_id()))"
               " WITH CHECK ((org_id = app.current_org_id()))")
