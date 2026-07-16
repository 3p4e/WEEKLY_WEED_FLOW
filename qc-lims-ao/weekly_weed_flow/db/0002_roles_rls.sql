-- WEEKLY_WEED_FLOW — roles, grants, RLS (0002)
-- Two-role model: app_user (NOBYPASSRLS, request handlers) + app_admin
-- (BYPASSRLS, provisioning/audit). Passwords are set by the deploy script via
-- ALTER ROLE ... PASSWORD from env (never committed).

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='app_user') THEN
    CREATE ROLE app_user LOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='app_admin') THEN
    CREATE ROLE app_admin LOGIN BYPASSRLS;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public, app TO app_user, app_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO app_user, app_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user, app_admin;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user, app_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user, app_admin;

-- audit_log: append-only for app_user (trigger is SECURITY DEFINER and inserts
-- regardless); never UPDATE/DELETE.
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM app_user, app_admin;

-- ─────────────────────────── enable RLS ─────────────────────────────────────
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'organizations','departments','profiles','calendar_weeks','tasks',
    'task_progress','task_assignees','task_comments','handoffs',
    'password_reset_codes','ai_agent_bindings','ai_pins','audit_log'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

-- ─────────────────────────────── policies ───────────────────────────────────
-- Org isolation is the base rule on every tenant table.
CREATE POLICY org_isolation ON departments        USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE POLICY org_isolation ON calendar_weeks      USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE POLICY org_isolation ON task_assignees      USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE POLICY org_isolation ON task_comments       USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE POLICY org_isolation ON handoffs            USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE POLICY org_isolation ON ai_agent_bindings   USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());
CREATE POLICY org_isolation ON ai_pins             USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());

-- organizations: a member sees only their own org
CREATE POLICY org_self ON organizations USING (id = app.current_org_id());

-- profiles: visible within org; self-update; elevated manage
CREATE POLICY profiles_read   ON profiles FOR SELECT USING (org_id = app.current_org_id());
CREATE POLICY profiles_self   ON profiles FOR UPDATE USING (id = app.current_user_id()) WITH CHECK (id = app.current_user_id());
CREATE POLICY profiles_manage ON profiles FOR ALL    USING (org_id = app.current_org_id() AND app.is_elevated())
                                                     WITH CHECK (org_id = app.current_org_id() AND app.is_elevated());

-- tasks: org-scoped; readable by owner/assignee/elevated; writable by owner/elevated
CREATE POLICY tasks_read ON tasks FOR SELECT USING (
  org_id = app.current_org_id() AND (
    user_id = app.current_user_id()
    OR app.is_elevated()
    OR EXISTS (SELECT 1 FROM task_assignees a WHERE a.task_id = tasks.id AND a.user_id = app.current_user_id())
  )
);
CREATE POLICY tasks_write ON tasks FOR ALL USING (
  org_id = app.current_org_id() AND (user_id = app.current_user_id() OR app.is_elevated())
) WITH CHECK (org_id = app.current_org_id());

-- task_progress / task_comments: follow parent task visibility within org
CREATE POLICY progress_rw ON task_progress FOR ALL
  USING (org_id = app.current_org_id()) WITH CHECK (org_id = app.current_org_id());

-- password_reset_codes: only the owning user or elevated (server uses app_admin anyway)
CREATE POLICY reset_self ON password_reset_codes USING (
  user_id = app.current_user_id() OR app.is_elevated()
) WITH CHECK (true);

-- audit_log: append-only; readable only by elevated roles
CREATE POLICY audit_read   ON audit_log FOR SELECT USING (app.is_elevated() AND (org_id = app.current_org_id() OR org_id IS NULL));
CREATE POLICY audit_insert ON audit_log FOR INSERT WITH CHECK (true);
