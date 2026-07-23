"""Deep code-review remediation — schema changes

Revision ID: 0042
Revises: 0041
Create Date: 2026-07-22

Schema half of the 2026-07 deep-review fixes (docs/CODE-REVIEW-DEEP-2026-07.md):

- H4: `notifications_reason_check` gains `'workflow'` — the SUMA v2 sign-off
  workflow emits notifications with reason='workflow', which the CHECK rejected,
  so every approval alert was silently dropped by emit()'s savepoint.
- M9: `qc_oos_notifications.acknowledged_by_id` — an OOS acknowledgement must
  record WHO acknowledged (attributable GxP act), not just a bare flag.
- LOW (custody): `qc_chain_of_custody` becomes DB-enforced append-only — the
  single all-command `org_isolation` policy is split into SELECT + INSERT only,
  so FORCE RLS denies UPDATE/DELETE (matching the audit_log pattern); a custody
  chain must never be rewritten or reordered.

All additive / policy-only; no data migration.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REASONS_NEW = ("assigned", "mentioned", "comment", "status", "due", "report",
                "capa_stuck", "validation_stuck", "workflow")
_REASONS_OLD = _REASONS_NEW[:-1]


def _reason_check(values) -> str:
    arr = ", ".join(f"'{v}'::text" for v in values)
    return (f"reason = ANY (ARRAY[{arr}])")


def upgrade() -> None:
    # ── H4 — permit the 'workflow' notification reason
    op.execute("ALTER TABLE public.notifications DROP CONSTRAINT notifications_reason_check")
    op.execute("ALTER TABLE public.notifications ADD CONSTRAINT notifications_reason_check"
               f" CHECK (({_reason_check(_REASONS_NEW)}))")

    # ── M9 — record who acknowledged an OOS notification
    op.execute("ALTER TABLE public.qc_oos_notifications ADD COLUMN acknowledged_by_id uuid")

    # ── LOW — qc_chain_of_custody append-only (SELECT + INSERT only)
    op.execute("DROP POLICY org_isolation ON public.qc_chain_of_custody")
    op.execute("CREATE POLICY org_isolation_select ON public.qc_chain_of_custody"
               " FOR SELECT USING ((org_id = app.current_org_id()))")
    op.execute("CREATE POLICY org_isolation_insert ON public.qc_chain_of_custody"
               " FOR INSERT WITH CHECK ((org_id = app.current_org_id()))")


def downgrade() -> None:
    op.execute("DROP POLICY org_isolation_insert ON public.qc_chain_of_custody")
    op.execute("DROP POLICY org_isolation_select ON public.qc_chain_of_custody")
    op.execute("CREATE POLICY org_isolation ON public.qc_chain_of_custody"
               " USING ((org_id = app.current_org_id()))"
               " WITH CHECK ((org_id = app.current_org_id()))")

    op.execute("ALTER TABLE public.qc_oos_notifications DROP COLUMN acknowledged_by_id")

    op.execute("ALTER TABLE public.notifications DROP CONSTRAINT notifications_reason_check")
    op.execute("ALTER TABLE public.notifications ADD CONSTRAINT notifications_reason_check"
               f" CHECK (({_reason_check(_REASONS_OLD)}))")
