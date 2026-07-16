-- GrowFlow Unified — auth hardening + two-role Row-Level Security.
-- Grafts the SUMA/WWF auth methodology onto T_PLAN's RBAC:
--   * OTP provisioning + forced first-login change + lockout (columns below)
--   * two Postgres roles (app NOBYPASSRLS / admin BYPASSRLS) + RLS policies
--   * per-request identity via SET LOCAL app.user_id / app.role (see server/db.py)

-- ── auth hardening columns ─────────────────────────────────────────────────
ALTER TABLE app_user
  ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS failed_login_count   INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS locked_until         TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_login_at        TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS password_set_at      TIMESTAMPTZ;

-- ── identity helpers (read the per-request GUCs set by the app) ─────────────
CREATE SCHEMA IF NOT EXISTS app;
CREATE OR REPLACE FUNCTION app.uid() RETURNS UUID LANGUAGE sql STABLE AS
  $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;
CREATE OR REPLACE FUNCTION app.urole() RETURNS TEXT LANGUAGE sql STABLE AS
  $$ SELECT NULLIF(current_setting('app.role', true), '') $$;

-- ── two roles ──────────────────────────────────────────────────────────────
-- growflow_app : the request-scoped role the API uses; RLS APPLIES to it.
-- growflow_admin: BYPASSRLS, used for login lookups, provisioning, migrations.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='growflow_app') THEN
    CREATE ROLE growflow_app LOGIN PASSWORD 'change_me_app' NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='growflow_admin') THEN
    CREATE ROLE growflow_admin LOGIN PASSWORD 'change_me_admin' BYPASSRLS;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public, app TO growflow_app, growflow_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO growflow_app, growflow_admin;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO growflow_app, growflow_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO growflow_app, growflow_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO growflow_app, growflow_admin;

-- ── enable RLS + policies (defense-in-depth; admin role bypasses) ───────────
-- A valid identity (app.user_id) must be present for any access through the app role.
ALTER TABLE planner_task        ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_user            ENABLE ROW LEVEL SECURITY;
ALTER TABLE change_proposal     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_agent_bindings   ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_event         ENABLE ROW LEVEL SECURITY;

-- planner_task: team-wide read; writes require identity; destructive deletes are privileged.
DROP POLICY IF EXISTS task_read  ON planner_task;
DROP POLICY IF EXISTS task_write ON planner_task;
DROP POLICY IF EXISTS task_del   ON planner_task;
CREATE POLICY task_read  ON planner_task FOR SELECT USING (app.uid() IS NOT NULL);
CREATE POLICY task_write ON planner_task FOR ALL    USING (app.uid() IS NOT NULL) WITH CHECK (app.uid() IS NOT NULL);
CREATE POLICY task_del   ON planner_task FOR DELETE USING (app.urole() IN ('manager','admin','qp','hod'));

-- app_user: readable when identity present; a user updates only their own row (admin role bypasses).
DROP POLICY IF EXISTS user_read   ON app_user;
DROP POLICY IF EXISTS user_update ON app_user;
CREATE POLICY user_read   ON app_user FOR SELECT USING (app.uid() IS NOT NULL);
CREATE POLICY user_update ON app_user FOR UPDATE USING (id = app.uid()) WITH CHECK (id = app.uid());

-- change_proposal: anyone authenticated reads/inserts; only approvers update (approve/reject).
DROP POLICY IF EXISTS cp_read   ON change_proposal;
DROP POLICY IF EXISTS cp_insert ON change_proposal;
DROP POLICY IF EXISTS cp_update ON change_proposal;
CREATE POLICY cp_read   ON change_proposal FOR SELECT USING (app.uid() IS NOT NULL);
CREATE POLICY cp_insert ON change_proposal FOR INSERT WITH CHECK (app.uid() IS NOT NULL);
CREATE POLICY cp_update ON change_proposal FOR UPDATE USING (app.urole() IN ('reviewer','manager','qp','hod','admin'));

-- ai_agent_bindings: read for all; writes admin-only (through the app role).
DROP POLICY IF EXISTS ab_read  ON ai_agent_bindings;
DROP POLICY IF EXISTS ab_write ON ai_agent_bindings;
CREATE POLICY ab_read  ON ai_agent_bindings FOR SELECT USING (app.uid() IS NOT NULL);
CREATE POLICY ab_write ON ai_agent_bindings FOR ALL    USING (app.urole() = 'admin') WITH CHECK (app.urole() = 'admin');

-- audit_event: APPEND-ONLY. Read + insert only; no update/delete policy => denied for app role.
DROP POLICY IF EXISTS ae_read   ON audit_event;
DROP POLICY IF EXISTS ae_insert ON audit_event;
CREATE POLICY ae_read   ON audit_event FOR SELECT USING (app.uid() IS NOT NULL);
CREATE POLICY ae_insert ON audit_event FOR INSERT WITH CHECK (app.uid() IS NOT NULL);
