"""Add the missing audit_<tbl> trigger to 6 tables (2026-07 review)

Revision ID: 0043
Revises: 0042
Create Date: 2026-07-24

Every org-scoped tasks-DB table is meant to carry an `audit_<tbl>` trigger
wiring it into the hash-chained `audit_log` (app.fn_audit_row()) — the
GxP-relevant "who changed what, when" trail. Six tables were missed when
they were first created and had none: `ai_agent_bindings`, `ai_pins`,
`calendar_weeks`, `task_links`, `task_assignees`, `task_comments`.

`task_assignees` has a composite (task_id, user_id) key with no `id` column
— wiring its trigger straight up hit `app.fn_audit_row()`'s hardcoded
`(...).id::text` row access, which fails at parse time with "column id not
found in data type task_assignees" the instant an assignment is written.
fn_audit_row() is fixed first (composite-type `.id` access swapped for a
jsonb `->>'id'` lookup, which degrades to NULL/'' instead of erroring on a
table with no id column) so the new trigger is actually safe to attach.
Purely additive; no data migration.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "ai_agent_bindings", "ai_pins", "calendar_weeks",
    "task_links", "task_assignees", "task_comments",
)

# Body between $$...$$ must stay byte-identical to users-0007's copy (the
# users DB carries its own copy of this function; CI schema-diffs each DB
# independently). Only delta vs. the pre-fix body is the v_rec line: a jsonb
# ->>'id' lookup instead of a composite-type (...).id cast, so a table with
# no `id` column (task_assignees) degrades to an empty record_id instead of
# raising "column id not found in data type <table>" on every write.
_FN_JSONB_ID = """CREATE OR REPLACE FUNCTION app.fn_audit_row() RETURNS trigger
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

_FN_DOT_ID = """CREATE OR REPLACE FUNCTION app.fn_audit_row() RETURNS trigger
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


def upgrade() -> None:
    op.execute(_FN_JSONB_ID)
    for t in _TABLES:
        op.execute(
            f"CREATE TRIGGER audit_{t} AFTER INSERT OR DELETE OR UPDATE ON public.{t}"
            f" FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row()"
        )


def downgrade() -> None:
    for t in reversed(_TABLES):
        op.execute(f"DROP TRIGGER audit_{t} ON public.{t}")
    op.execute(_FN_DOT_ID)
