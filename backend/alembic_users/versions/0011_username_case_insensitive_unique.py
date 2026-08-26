"""profiles: case-insensitive unique index on username

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-26

profiles_username_key (migration 0001) is a plain UNIQUE(username) —
case-SENSITIVE, so "Alice.Q" and "alice.q" could coexist as two distinct
accounts. The application now normalizes every username to lowercase at
creation time (app/api/auth.py's CreateUserReq — username is immutable
thereafter, see UpdateUserReq), which already prevents new collisions
in the normal path, but that is an application-layer guarantee only.

This adds a DB-level backstop: a unique index on lower(username), so a
case-insensitive collision can never be written even if the app-layer
normalization is ever bypassed (a direct INSERT, a future code path that
forgets to normalize, etc.).

Scope matches the existing constraint exactly: profiles_username_key is
GLOBAL (not per-org), so this index is global too — not (org_id,
lower(username)).

Verified safe to apply: every username-writing path in the codebase
already produces lowercase values (app/demo_org.py's _username() lowercases
full_name before building the handle; backend/scripts/seed_e2e_org.py's
"e2e_admin_"/"e2e_operator_" prefixes + lowercase hex suffix; every test
fixture's username literal is already lowercase), so there is no existing
data this index could reject.

The old case-SENSITIVE profiles_username_key is left in place — it still
does useful work (the exact-match case), costs nothing extra to keep, and
removing it is out of scope for this fix.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX profiles_username_lower_uniq ON public.profiles"
        " (lower(username))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX public.profiles_username_lower_uniq")
