-- WEEKLY_WEED_FLOW — initial schema (0001)
-- Modeled on SUMA_DB's task-lifecycle columns so the SUMA-format export imports
-- 1:1, but with our own auth/audit/RLS (no Supabase auth.users dependency).
-- Excludes all QC/QMS modules (reports, exec metrics, electronic_signatures).
--
-- Identity for RLS comes from per-request GUCs set by the API inside a txn:
--   SELECT set_config('app.user_id', '<uuid>', true);
--   SELECT set_config('app.org_id',  '<uuid>', true);
--   SELECT set_config('app.role',    '<role>', true);
-- The app connects as a NOBYPASSRLS role; a separate BYPASSRLS admin role is
-- used only for provisioning/audit writes.

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), digest()

-- ─────────────────────────── identity helpers ───────────────────────────────
CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
  LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION app.current_org_id() RETURNS uuid
  LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.org_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION app.current_role() RETURNS text
  LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.role', true), '') $$;

CREATE OR REPLACE FUNCTION app.is_elevated() RETURNS boolean
  LANGUAGE sql STABLE AS $$ SELECT app.current_role() IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD','QA_AUDITOR') $$;

-- ─────────────────────────────── tables ─────────────────────────────────────
CREATE TABLE organizations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  slug        text UNIQUE NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE departments (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  code        text NOT NULL,
  name        text NOT NULL,
  name_mk     text,
  parent_id   uuid REFERENCES departments(id) ON DELETE SET NULL,
  head_user_id uuid,                       -- FK added after profiles exists
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, code)
);

CREATE TABLE profiles (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  username      text UNIQUE NOT NULL,
  email         text,
  password_hash text NOT NULL,
  full_name     text NOT NULL,
  display_name  text,
  role          text NOT NULL DEFAULT 'USER'
                  CHECK (role IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD','TEAM_LEADER','USER','QA_AUDITOR')),
  function_role text,                       -- free-text e.g. "Head of QC"
  department_id uuid REFERENCES departments(id) ON DELETE SET NULL,
  avatar_url    text,
  is_active     boolean NOT NULL DEFAULT true,
  must_change_password boolean NOT NULL DEFAULT true,
  password_set_at timestamptz,
  created_by    uuid REFERENCES profiles(id) ON DELETE SET NULL,
  is_deleted    boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE departments
  ADD CONSTRAINT departments_head_fk FOREIGN KEY (head_user_id) REFERENCES profiles(id) ON DELETE SET NULL;

CREATE TABLE calendar_weeks (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  iso_year   smallint NOT NULL,
  iso_week   smallint NOT NULL,
  starts_on  date NOT NULL,
  ends_on    date NOT NULL,
  UNIQUE (org_id, iso_year, iso_week)
);

CREATE TABLE tasks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id       uuid NOT NULL REFERENCES profiles(id),         -- owner
  parent_id     uuid REFERENCES tasks(id) ON DELETE CASCADE,   -- subtask tree
  title         text NOT NULL,
  description   text,
  status        text NOT NULL DEFAULT 'pending',
  priority      text NOT NULL DEFAULT 'medium',
  workflow_state text NOT NULL DEFAULT 'draft',
  department    text,                                          -- denormalized label from export
  department_id uuid REFERENCES departments(id) ON DELETE SET NULL,
  week_id       uuid REFERENCES calendar_weeks(id) ON DELETE SET NULL,
  week_start    date,
  days          text[] NOT NULL DEFAULT '{}',
  tags          text[] NOT NULL DEFAULT '{}',
  deps          uuid[] NOT NULL DEFAULT '{}',                  -- task dependencies
  progress_notes jsonb NOT NULL DEFAULT '[]',                  -- [{day,note,at,...}]
  due_date      date,
  completed_date date,
  estimated_hours numeric,
  actual_hours   numeric,
  outcome       text,
  is_archived   boolean NOT NULL DEFAULT false,
  is_deleted    boolean NOT NULL DEFAULT false,
  created_by    uuid REFERENCES profiles(id) ON DELETE SET NULL,
  updated_by    uuid REFERENCES profiles(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tasks_org_idx        ON tasks(org_id);
CREATE INDEX tasks_parent_idx     ON tasks(parent_id);
CREATE INDEX tasks_week_idx       ON tasks(week_id);
CREATE INDEX tasks_owner_idx      ON tasks(user_id);
CREATE INDEX tasks_dept_idx       ON tasks(department_id);

CREATE TABLE task_progress (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  task_id    uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES profiles(id),
  day_label  text NOT NULL,
  note       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX task_progress_task_idx ON task_progress(task_id);

CREATE TABLE task_assignees (
  task_id     uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  role        text NOT NULL DEFAULT 'assignee',
  assigned_by uuid REFERENCES profiles(id) ON DELETE SET NULL,
  assigned_at timestamptz NOT NULL DEFAULT now(),
  accepted    boolean,
  accepted_at timestamptz,
  PRIMARY KEY (task_id, user_id)
);

CREATE TABLE task_comments (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  task_id    uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES profiles(id),
  content    text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Cross-department handoffs (first-class, accept/reject workflow)
CREATE TABLE handoffs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  task_id       uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  from_dept_id  uuid REFERENCES departments(id) ON DELETE SET NULL,
  to_dept_id    uuid REFERENCES departments(id) ON DELETE SET NULL,
  requested_by  uuid NOT NULL REFERENCES profiles(id),
  status        text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','accepted','rejected','cancelled')),
  note          text,
  resolved_by   uuid REFERENCES profiles(id) ON DELETE SET NULL,
  resolved_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Auth: single-use password reset / OTP codes
CREATE TABLE password_reset_codes (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  code_hash  text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ───────────────────────── LITA / Letta AI seam ─────────────────────────────
-- Always-on binding of WWF scopes/functions to Letta stateful agents. The app
-- reads this to decide which agent handles which function; new AI functions are
-- added as rows, not code rewires.
CREATE TABLE ai_agent_bindings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  function_key  text NOT NULL,             -- e.g. 'weekly_summary','dependency_advisor','corpus_qa'
  letta_agent_id text NOT NULL,            -- id of the stateful agent in the Letta stack
  scope         text NOT NULL DEFAULT 'org', -- org | department | project | user
  scope_id      uuid,
  is_active     boolean NOT NULL DEFAULT true,
  config        jsonb NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, function_key, scope, scope_id)
);

-- Pinned AI outputs (summaries, suggestions) surfaced in the UI
CREATE TABLE ai_pins (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  function_key text NOT NULL,
  task_id      uuid REFERENCES tasks(id) ON DELETE CASCADE,
  week_id      uuid REFERENCES calendar_weeks(id) ON DELETE CASCADE,
  title        text,
  body         text NOT NULL,
  created_by   uuid REFERENCES profiles(id) ON DELETE SET NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────── hash-chained audit trail ───────────────────────────
CREATE TABLE audit_log (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id      uuid,
  user_id     uuid,
  user_email  text,
  action      text NOT NULL,            -- INSERT | UPDATE | DELETE | business action
  table_name  text,
  record_id   text,
  old_values  jsonb,
  new_values  jsonb,
  prev_hash   text,
  entry_hash  text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_table_idx ON audit_log(table_name, record_id);

CREATE OR REPLACE FUNCTION app.fn_audit_row() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = app, public AS $$
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

CREATE TRIGGER audit_tasks       AFTER INSERT OR UPDATE OR DELETE ON tasks         FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();
CREATE TRIGGER audit_task_prog   AFTER INSERT OR UPDATE OR DELETE ON task_progress FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();
CREATE TRIGGER audit_profiles    AFTER INSERT OR UPDATE OR DELETE ON profiles      FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();
CREATE TRIGGER audit_departments AFTER INSERT OR UPDATE OR DELETE ON departments   FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();
CREATE TRIGGER audit_handoffs    AFTER INSERT OR UPDATE OR DELETE ON handoffs      FOR EACH ROW EXECUTE FUNCTION app.fn_audit_row();

-- audit_log is append-only: revoke mutation from app roles (granted in 0002_roles.sql)
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;
