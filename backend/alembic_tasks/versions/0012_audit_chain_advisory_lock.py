"""tasks-DB app.fn_audit_row(): advisory-lock the chain-tail read (H1)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-14

fn_audit_row() reads the audit chain tail (SELECT entry_hash ... ORDER BY id
DESC LIMIT 1) with no lock, so two concurrent writers read the SAME tail and
both link their new row to it — forking the hash chain. /audit/verify then
reports linkage "breaks" that are an artifact of the fork, and real tampering
gets cover. This serializes audit inserts with a transaction-scoped advisory
lock taken before the tail read (auto-released at COMMIT/ROLLBACK). Every
audited write flows through this one trigger, so a single lock key fully
serializes the chain; at WWF's write volume the contention is negligible.

Function body is otherwise byte-identical to 0011's dump so the CI
schema-diff (pg_dump alembic-built vs schema.tasks.sql) stays clean. The users
DB carries its own copy of this trigger — users-0006 makes the identical
change there.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# NOTE: the body between $$...$$ must stay byte-identical to schema.tasks.sql's
# fn_audit_row prosrc, or the CI schema-diff fails. The ONLY delta vs the
# pre-0012 body is the single PERFORM pg_advisory_xact_lock line after BEGIN.
_FN_LOCKED = """CREATE OR REPLACE FUNCTION app.fn_audit_row() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'app', 'public'
    AS $$
DECLARE
  v_actor text := COALESCE(current_setting('app.user_id', true), 'system');
  v_prev  text;
  v_new   jsonb := CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  v_old   jsonb := CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  v_rec   text  := COALESCE((CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END).id::text, '');
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

_FN_UNLOCKED = """CREATE OR REPLACE FUNCTION app.fn_audit_row() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'app', 'public'
    AS $$
DECLARE
  v_actor text := COALESCE(current_setting('app.user_id', true), 'system');
  v_prev  text;
  v_new   jsonb := CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END;
  v_old   jsonb := CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END;
  v_rec   text  := COALESCE((CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END).id::text, '');
  v_payload text;
BEGIN
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
    op.execute(_FN_LOCKED)


def downgrade() -> None:
    op.execute(_FN_UNLOCKED)
