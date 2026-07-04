"""users database baseline — identity data (organizations, profiles,
password_reset_codes) plus its own hash-chained audit trail.

Revision ID: 0001
Revises:
Create Date: 2026-07-04

This is the v2 rebuild's fresh chain: WWF's data now lives in two separate
Postgres containers (identity here, work data in the tasks database — see
alembic_tasks/). Cross-database references are bare uuids with NO foreign
key (profiles.department_id points at a departments row in the OTHER
database), so referential integrity across the boundary is the app's job.

The audit trail is duplicated per database on purpose: account provisioning
and password events stay tamper-evident here, task events there, and each
chain verifies independently (/audit/verify reports both).

schema.users.sql is generated FROM the database this migration builds
(pg_dump), never edited by hand — CI diffs the two to catch drift.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UP = r"""
CREATE SCHEMA app;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

CREATE FUNCTION app.current_org_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.org_id', true), '')::uuid $$;

CREATE FUNCTION app."current_role"() RETURNS text
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.role', true), '') $$;

CREATE FUNCTION app.current_user_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION app.is_elevated() RETURNS boolean
    LANGUAGE sql STABLE
    AS $$ SELECT app.current_role() IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD') $$;

CREATE FUNCTION app.fn_audit_row() RETURNS trigger
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
END $$;

CREATE TABLE public.audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id uuid,
    user_id uuid,
    user_email text,
    action text NOT NULL,
    table_name text,
    record_id text,
    old_values jsonb,
    new_values jsonb,
    prev_hash text,
    entry_hash text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX audit_log_table_idx ON public.audit_log (table_name, record_id);
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_insert ON public.audit_log FOR INSERT WITH CHECK (true);
CREATE POLICY audit_read ON public.audit_log FOR SELECT
    USING (app.is_elevated() AND (org_id = app.current_org_id() OR org_id IS NULL));

CREATE TABLE public.organizations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY org_self ON public.organizations USING (id = app.current_org_id());

-- department_id is a bare uuid: departments live in the tasks database, so
-- no FK can exist here. The API validates it against /departments app-side.
CREATE TABLE public.profiles (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    username text NOT NULL UNIQUE,
    email text,
    password_hash text NOT NULL,
    full_name text NOT NULL,
    display_name text,
    role text DEFAULT 'USER' NOT NULL
        CONSTRAINT profiles_role_check CHECK (role = ANY (ARRAY['ADMIN'::text, 'DEPT_HEAD'::text, 'PROJECT_LEAD'::text, 'TEAM_LEADER'::text, 'USER'::text])),
    function_role text,
    department_id uuid,
    avatar_url text,
    is_active boolean DEFAULT true NOT NULL,
    must_change_password boolean DEFAULT true NOT NULL,
    password_set_at timestamp with time zone,
    created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY profiles_read ON public.profiles FOR SELECT
    USING (org_id = app.current_org_id());
CREATE POLICY profiles_self ON public.profiles FOR UPDATE
    USING (id = app.current_user_id()) WITH CHECK (id = app.current_user_id());
CREATE POLICY profiles_manage ON public.profiles
    USING (org_id = app.current_org_id() AND app.is_elevated())
    WITH CHECK (org_id = app.current_org_id() AND app.is_elevated());
CREATE TRIGGER audit_profiles AFTER INSERT OR DELETE OR UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();

CREATE TABLE public.password_reset_codes (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    code_hash text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE public.password_reset_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_reset_codes FORCE ROW LEVEL SECURITY;
CREATE POLICY reset_self ON public.password_reset_codes
    USING (user_id = app.current_user_id() OR app.is_elevated())
    WITH CHECK (user_id = app.current_user_id() OR app.is_elevated());
"""

_DOWN = r"""
DROP TABLE IF EXISTS public.password_reset_codes;
DROP TABLE IF EXISTS public.profiles;
DROP TABLE IF EXISTS public.organizations;
DROP TABLE IF EXISTS public.audit_log;
DROP SCHEMA IF EXISTS app CASCADE;
DROP EXTENSION IF EXISTS pgcrypto;
"""


def _exec_multi(sql: str) -> None:
    # SQLAlchemy's asyncpg dialect routes op.execute() through asyncpg's
    # prepared-statement path, which rejects multiple commands in one prepare
    # call. asyncpg's own Connection.execute() natively supports a
    # multi-statement string via the simple query protocol — drop to the raw
    # driver connection and use SQLAlchemy's greenlet bridge to await it
    # from this nominally-sync migration function.
    from sqlalchemy.util import await_only

    raw_connection = op.get_bind().connection.driver_connection
    await_only(raw_connection.execute(sql))


def upgrade() -> None:
    _exec_multi(_UP)


def downgrade() -> None:
    _exec_multi(_DOWN)
