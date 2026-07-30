"""app.fn_audit_row(): pin the function's TimeZone to UTC (H2)

Revision ID: 0050
Revises: 0049
Create Date: 2026-07-30

THE BUG, found in production on 2026-07-30 and diagnosed from the data.

`fn_audit_row()` hashes `now()::text`. For a `timestamptz`, `::text` renders under
the **session's** TimeZone — so the hash of a row depends on the TimeZone of
whatever connection happened to write it. `/audit/verify` recomputes from the
stored `created_at`, rendered under the **verifying** session's TimeZone. When the
two differ, every row that writer produced fails recomputation and is reported as
a hash break, with no tampering whatever.

That is not hypothetical. The production tasks chain carried **377 such rows**, all
from one transaction at `2026-07-13 00:29:14.082092+00`. Under `TimeZone=UTC`,
0 of 377 verified. Under `TimeZone=Europe/Skopje` (the facility zone, UTC+2 in
July), **377 of 377 verified exactly.** The rows were written by a session at
UTC+2 and read back under UTC. The data was always intact; the hash was simply not
reproducible across zones. `_CHAIN_SQL`'s own comment asserted the opposite —
"created_at renders under the same server TimeZone the writes used (neither the app
nor the admin pool overrides it)" — and that assumption was false.

THE FIX, and why it is this one.

`SET TimeZone TO 'UTC'` on the function. A per-function GUC applies for the
duration of the call and reverts afterwards, so `now()::text` inside the trigger
renders under UTC no matter what the caller's session is set to. Every future row
is canonical.

Deliberately NOT changed: the payload formula. Rewriting it (to an epoch, or an
explicit `to_char`) would be the more obvious fix and it is the wrong one here —
it would invalidate the recomputation of every row already written, forcing
`/audit/verify` to carry a cutover id and two formulas forever. Pinning the zone
achieves the same guarantee going forward while leaving all 3703 existing hashes
reproducible under the zone they were written in. One line, no cutover, no
re-hashing, and **no existing audit row is touched** — which matters more than
elegance in a tamper-evident log: the correct response to a chain that does not
verify is never to rewrite the chain.

The verifier is fixed separately and independently (`app/api/audit.py`): it now
recomputes under UTC *and* the facility zone, and reports a row that matches only
the latter as `hash_legacy_tz` rather than as a break — explaining the history
instead of hiding it.

The body is otherwise byte-identical to 0049's, so the CI schema-diff (pg_dump of
the alembic-built DB vs `schema.tasks.sql`) stays clean. The users DB carries its
own copy of this trigger; users-0009 makes the identical change there.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The ONLY delta between these two bodies is the `SET "TimeZone" TO 'UTC'` line.
# Everything else must stay byte-identical to schema.tasks.sql's prosrc or the CI
# schema-diff fails.
_FN_TZ_PINNED = """CREATE OR REPLACE FUNCTION app.fn_audit_row() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'app', 'public'
    SET "TimeZone" TO 'UTC'
    AS $$
DECLARE
  v_actor text := COALESCE(current_setting('app.user_id', true), 'system');
  v_prev  text;
  v_new   jsonb := CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  v_old   jsonb := CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  v_rec   text  := COALESCE((CASE WHEN TG_OP='DELETE' THEN v_old ELSE v_new END)->>'id', '');
  v_payload text;
BEGIN
  PERFORM pg_advisory_xact_lock(4019283746);  -- H1: serialize tail read; prevents concurrent hash-chain forks
  SELECT entry_hash INTO v_prev FROM audit_log ORDER BY id DESC LIMIT 1;
  -- IMPORTANT: convert_to(text,'UTF8'), never text::bytea (escape-format bug).
  -- H2: the function pins TimeZone=UTC, so now()::text here is zone-stable and
  -- /audit/verify can reproduce it from created_at without knowing who wrote it.
  v_payload := COALESCE(v_prev,'') || v_actor || TG_OP || TG_TABLE_NAME || v_rec
               || now()::text || COALESCE(v_new::text,'') || COALESCE(v_old::text,'');
  INSERT INTO audit_log(org_id,user_id,action,table_name,record_id,old_values,new_values,prev_hash,entry_hash)
  VALUES (
    NULLIF(current_setting('app.org_id', true),'')::uuid,
    NULLIF(current_setting('app.user_id', true),'')::uuid,
    TG_OP, TG_TABLE_NAME, v_rec, v_old, v_new, v_prev,
    encode(digest(convert_to(v_payload,'UTF8'),'sha256'),'hex')
  );
  RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$"""

_FN_TZ_UNPINNED = """CREATE OR REPLACE FUNCTION app.fn_audit_row() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'app', 'public'
    AS $$
DECLARE
  v_actor text := COALESCE(current_setting('app.user_id', true), 'system');
  v_prev  text;
  v_new   jsonb := CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  v_old   jsonb := CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  v_rec   text  := COALESCE((CASE WHEN TG_OP='DELETE' THEN v_old ELSE v_new END)->>'id', '');
  v_payload text;
BEGIN
  PERFORM pg_advisory_xact_lock(4019283746);  -- H1: serialize tail read; prevents concurrent hash-chain forks
  SELECT entry_hash INTO v_prev FROM audit_log ORDER BY id DESC LIMIT 1;
  -- IMPORTANT: convert_to(text,'UTF8'), never text::bytea (escape-format bug).
  v_payload := COALESCE(v_prev,'') || v_actor || TG_OP || TG_TABLE_NAME || v_rec
               || now()::text || COALESCE(v_new::text,'') || COALESCE(v_old::text,'');
  INSERT INTO audit_log(org_id,user_id,action,table_name,record_id,old_values,new_values,prev_hash,entry_hash)
  VALUES (
    NULLIF(current_setting('app.org_id', true),'')::uuid,
    NULLIF(current_setting('app.user_id', true),'')::uuid,
    TG_OP, TG_TABLE_NAME, v_rec, v_old, v_new, v_prev,
    encode(digest(convert_to(v_payload,'UTF8'),'sha256'),'hex')
  );
  RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$"""


def upgrade() -> None:
    op.execute(_FN_TZ_PINNED)


def downgrade() -> None:
    op.execute(_FN_TZ_UNPINNED)
