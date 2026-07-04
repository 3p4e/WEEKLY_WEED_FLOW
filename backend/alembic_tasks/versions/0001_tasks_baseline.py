"""tasks database baseline — all work data, v2 task model, own audit chain.

Revision ID: 0001
Revises:
Create Date: 2026-07-04

The v2 rebuild's fresh chain for the work-data database (identity lives in
the users database — see alembic_users/). Every reference to a profile
(user_id, created_by, assigned_by, subject_user_id, head_user_id, ...) and
to organizations (org_id) is a bare uuid with NO foreign key: those rows
live in the other database. In-database FKs (task→task, task→department,
task→calendar_week, child tables→task) are kept.

New in v2 versus the old single-database schema:
  • work_sessions — the overtime engine's source of truth: every sitting of
    real work with started_at (+ended_at or hours). Regular/overtime/night/
    weekend classification is computed at query time (reports), never
    stored, so the rules can evolve without rewriting history.
  • task_links — external references (Drive docs, SOPs) as URLs; WWF stores
    no files.
  • tasks.task_type / reference_code / blocker_reason / recurrence.

schema.tasks.sql is generated FROM the database this migration builds
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

-- head_user_id is a bare uuid (profiles live in the users database).
CREATE TABLE public.departments (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    name_mk text,
    parent_id uuid REFERENCES public.departments(id) ON DELETE SET NULL,
    head_user_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    UNIQUE (org_id, code)
);
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.departments FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.departments
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE TRIGGER audit_departments AFTER INSERT OR DELETE OR UPDATE ON public.departments
    FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();

CREATE TABLE public.calendar_weeks (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    iso_year smallint NOT NULL,
    iso_week smallint NOT NULL,
    starts_on date NOT NULL,
    ends_on date NOT NULL,
    UNIQUE (org_id, iso_year, iso_week)
);
ALTER TABLE public.calendar_weeks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.calendar_weeks FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.calendar_weeks
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());

-- user_id / created_by / updated_by are bare uuids (users database).
CREATE TABLE public.tasks (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    user_id uuid NOT NULL,
    parent_id uuid REFERENCES public.tasks(id) ON DELETE CASCADE,
    title text NOT NULL,
    description text,
    status text DEFAULT 'pending' NOT NULL
        CONSTRAINT tasks_status_check CHECK (status = ANY (ARRAY['pending'::text, 'ongoing'::text, 'review'::text, 'stuck'::text, 'postponed'::text, 'completed'::text])),
    priority text DEFAULT 'medium' NOT NULL,
    workflow_state text DEFAULT 'draft' NOT NULL,
    task_type text DEFAULT 'other' NOT NULL
        CONSTRAINT tasks_task_type_check CHECK (task_type = ANY (ARRAY['capa'::text, 'sop'::text, 'validation'::text, 'document'::text, 'lab'::text, 'meeting'::text, 'admin'::text, 'other'::text])),
    reference_code text,
    blocker_reason text,
    recurrence jsonb,
    department text,
    department_id uuid REFERENCES public.departments(id) ON DELETE SET NULL,
    week_id uuid REFERENCES public.calendar_weeks(id) ON DELETE SET NULL,
    week_start date,
    days text[] DEFAULT '{}'::text[] NOT NULL,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    due_date date,
    completed_date date,
    estimated_hours numeric,
    actual_hours numeric,
    outcome text,
    is_archived boolean DEFAULT false NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    created_by uuid,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tasks_hours_nonnegative_check CHECK (((estimated_hours IS NULL) OR (estimated_hours >= (0)::numeric)) AND ((actual_hours IS NULL) OR (actual_hours >= (0)::numeric)))
);
CREATE INDEX tasks_org_idx ON public.tasks (org_id);
CREATE INDEX tasks_owner_idx ON public.tasks (user_id);
CREATE INDEX tasks_parent_idx ON public.tasks (parent_id);
CREATE INDEX tasks_week_idx ON public.tasks (week_id);
CREATE INDEX tasks_dept_idx ON public.tasks (department_id);
CREATE INDEX tasks_org_week_start_idx ON public.tasks (org_id, week_start DESC, created_at DESC);
CREATE INDEX tasks_due_idx ON public.tasks (org_id, due_date) WHERE due_date IS NOT NULL;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks FORCE ROW LEVEL SECURITY;
-- tasks_read/tasks_write policies are created after task_assignees below
-- (their USING subqueries reference it, and CREATE POLICY validates that).
CREATE TRIGGER audit_tasks AFTER INSERT OR DELETE OR UPDATE ON public.tasks
    FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();

CREATE TABLE public.task_progress (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    day_label text NOT NULL,
    note text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX task_progress_task_idx ON public.task_progress (task_id);
ALTER TABLE public.task_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_progress FORCE ROW LEVEL SECURITY;
CREATE POLICY progress_rw ON public.task_progress
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE TRIGGER audit_task_prog AFTER INSERT OR DELETE OR UPDATE ON public.task_progress
    FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();

-- Every sitting of real work. Either ended_at or hours carries the duration
-- (both may be set; hours wins at read time). Classification into regular /
-- overtime / night / weekend happens in queries from started_at — stored
-- rows are just facts.
CREATE TABLE public.work_sessions (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    hours numeric,
    note text,
    source text DEFAULT 'manual' NOT NULL
        CONSTRAINT work_sessions_source_check CHECK (source = ANY (ARRAY['manual'::text, 'timer'::text, 'capture'::text])),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT work_sessions_hours_positive_check CHECK ((hours IS NULL) OR (hours > (0)::numeric)),
    CONSTRAINT work_sessions_range_check CHECK ((ended_at IS NULL) OR (ended_at > started_at)),
    CONSTRAINT work_sessions_duration_check CHECK ((hours IS NOT NULL) OR (ended_at IS NOT NULL))
);
CREATE INDEX work_sessions_task_idx ON public.work_sessions (task_id);
CREATE INDEX work_sessions_org_started_idx ON public.work_sessions (org_id, started_at);
ALTER TABLE public.work_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.work_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.work_sessions
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE TRIGGER audit_work_sessions AFTER INSERT OR DELETE OR UPDATE ON public.work_sessions
    FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();

-- External references only (Drive docs, SOP registry entries) — WWF stores
-- no files, per docs/SCOPE.md.
CREATE TABLE public.task_links (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    url text NOT NULL,
    label text,
    kind text DEFAULT 'other' NOT NULL
        CONSTRAINT task_links_kind_check CHECK (kind = ANY (ARRAY['drive'::text, 'sop'::text, 'doc'::text, 'other'::text])),
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX task_links_task_idx ON public.task_links (task_id);
ALTER TABLE public.task_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_links FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.task_links
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());

CREATE TABLE public.task_assignees (
    task_id uuid NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    org_id uuid NOT NULL,
    role text DEFAULT 'assignee' NOT NULL,
    assigned_by uuid,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL,
    accepted boolean,
    accepted_at timestamp with time zone,
    PRIMARY KEY (task_id, user_id)
);
ALTER TABLE public.task_assignees ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_assignees FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.task_assignees
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());

CREATE POLICY tasks_read ON public.tasks FOR SELECT
    USING (org_id = app.current_org_id() AND (user_id = app.current_user_id() OR app.is_elevated()
           OR EXISTS (SELECT 1 FROM public.task_assignees a
                      WHERE a.task_id = tasks.id AND a.user_id = app.current_user_id())));
CREATE POLICY tasks_write ON public.tasks
    USING (org_id = app.current_org_id() AND (user_id = app.current_user_id() OR app.is_elevated()
           OR EXISTS (SELECT 1 FROM public.task_assignees a
                      WHERE a.task_id = tasks.id AND a.user_id = app.current_user_id())))
    WITH CHECK (org_id = app.current_org_id());

CREATE TABLE public.task_comments (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    content text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE public.task_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_comments FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.task_comments
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());

CREATE TABLE public.handoffs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    task_id uuid NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    from_dept_id uuid REFERENCES public.departments(id) ON DELETE SET NULL,
    to_dept_id uuid REFERENCES public.departments(id) ON DELETE SET NULL,
    requested_by uuid NOT NULL,
    status text DEFAULT 'proposed' NOT NULL
        CONSTRAINT handoffs_status_check CHECK (status = ANY (ARRAY['proposed'::text, 'accepted'::text, 'rejected'::text, 'cancelled'::text])),
    note text,
    resolved_by uuid,
    resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE public.handoffs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.handoffs FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.handoffs
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE TRIGGER audit_handoffs AFTER INSERT OR DELETE OR UPDATE ON public.handoffs
    FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();

-- created_by / subject_user_id are bare uuids (users database).
CREATE TABLE public.ai_pins (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    function_key text NOT NULL,
    task_id uuid REFERENCES public.tasks(id) ON DELETE CASCADE,
    week_id uuid REFERENCES public.calendar_weeks(id) ON DELETE CASCADE,
    title text,
    body text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    subject_user_id uuid,
    prompt_version text
);
ALTER TABLE public.ai_pins ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_pins FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.ai_pins
    USING (org_id = app.current_org_id() AND (subject_user_id IS NULL OR subject_user_id = app.current_user_id() OR app.is_elevated()))
    WITH CHECK (org_id = app.current_org_id());

CREATE TABLE public.ai_agent_bindings (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    org_id uuid NOT NULL,
    function_key text NOT NULL,
    letta_agent_id text NOT NULL,
    scope text DEFAULT 'org' NOT NULL,
    scope_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    UNIQUE (org_id, function_key, scope, scope_id)
);
ALTER TABLE public.ai_agent_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_agent_bindings FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON public.ai_agent_bindings
    USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
"""

_DOWN = r"""
DROP TABLE IF EXISTS public.ai_agent_bindings;
DROP TABLE IF EXISTS public.ai_pins;
DROP TABLE IF EXISTS public.handoffs;
DROP TABLE IF EXISTS public.task_comments;
DROP TABLE IF EXISTS public.task_assignees;
DROP TABLE IF EXISTS public.task_links;
DROP TABLE IF EXISTS public.work_sessions;
DROP TABLE IF EXISTS public.task_progress;
DROP TABLE IF EXISTS public.tasks;
DROP TABLE IF EXISTS public.calendar_weeks;
DROP TABLE IF EXISTS public.departments;
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
