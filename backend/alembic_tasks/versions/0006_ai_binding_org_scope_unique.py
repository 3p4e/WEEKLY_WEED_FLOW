"""ai_agent_bindings: real uniqueness for org-scoped bindings

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-05

The existing UNIQUE(org_id, function_key, scope, scope_id) constraint does
NOT prevent duplicate org-scoped bindings: Postgres treats every NULL as
distinct in a unique constraint, and org-scoped rows always have scope_id
IS NULL. set_binding() in app/api/ai.py worked around this by hand-rolling
UPDATE-then-INSERT-if-0-rows, which is a race under concurrent requests
(two PUTs can both see 0 rows updated and both INSERT). A partial unique
index on (org_id, function_key) WHERE scope='org' closes the gap and lets
set_binding use a single atomic INSERT ... ON CONFLICT DO UPDATE.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX ai_agent_bindings_org_scope_uniq"
        " ON public.ai_agent_bindings (org_id, function_key) WHERE (scope = 'org')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ai_agent_bindings_org_scope_uniq")
