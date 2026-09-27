-- A dedicated database role for the DocEngine, with rights on its own schema
-- and nothing else. Run ONCE per database, as the postgres superuser, on the
-- wwf_tasks database (review 2026-09-27, DI-09).
--
-- Why. The service with the largest untrusted-input surface in the stack —
-- LLM output, retrieved corpus text, author-supplied markdown — connected as
-- app_admin: BYPASSRLS and DML on every table of every organisation. Its SQL
-- is parameterised, so this is defence in depth, not an open hole; but a bug
-- or a compromised dependency in DocEngine must not be a tasks-DB compromise.
--
-- What it grants. The role owns schema `docengine` (so the service's own
-- CREATE TABLE IF NOT EXISTS / ALTER TABLE ... ADD COLUMN IF NOT EXISTS at
-- startup keep working), can connect, and has NO privileges on `public`,
-- `app`, or any other schema: it cannot even see the tasks, QC or audit
-- tables. It is NOBYPASSRLS and NOSUPERUSER. It does not need CREATE ON
-- DATABASE: the schema is created here, once, and handed over.
--
-- Usage (the password is a psql variable, so it never appears in a SQL
-- string in the shell history; `dbname` defaults to wwf_tasks):
--   docker exec -i wwf-db-tasks psql -U postgres -d wwf_tasks \
--     -v pw='<a long random password>' -f - < docengine/sql/docengine_role.sql
-- then point DOCENGINE_DATABASE_URL in docengine.env at
--   postgresql://docengine:<password>@wwf-db-tasks:5432/wwf_tasks
-- and recreate the docengine service (docs/DEPLOY.md, "DocEngine database
-- role"). Re-running the file is safe: every statement is idempotent.

\set ON_ERROR_STOP on
\if :{?dbname}
\else
  \set dbname wwf_tasks
\endif

-- CREATE or ALTER, whichever applies. Built with \gexec because psql does
-- not interpolate variables inside a DO body.
SELECT format('CREATE ROLE docengine LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS', :'pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'docengine') \gexec
SELECT format('ALTER ROLE docengine WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS', :'pw')
 WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'docengine') \gexec

GRANT CONNECT ON DATABASE :"dbname" TO docengine;

-- The schema exists before the service ever starts under the new role, and
-- the role owns it: ownership is what lets it create and alter its own
-- tables without CREATE ON DATABASE.
CREATE SCHEMA IF NOT EXISTS docengine;
ALTER SCHEMA docengine OWNER TO docengine;
-- Tables the service created while it still ran as app_admin are owned by
-- app_admin; hand them over so the role can ALTER them at startup.
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'docengine' LOOP
    EXECUTE format('ALTER TABLE docengine.%I OWNER TO docengine', t.tablename);
  END LOOP;
  FOR t IN SELECT sequencename AS tablename FROM pg_sequences WHERE schemaname = 'docengine' LOOP
    EXECUTE format('ALTER SEQUENCE docengine.%I OWNER TO docengine', t.tablename);
  END LOOP;
END
$$;

-- Nothing outside its schema. PUBLIC has USAGE on `public` by default on
-- older clusters; revoke it for this role explicitly so the answer does not
-- depend on cluster defaults.
REVOKE ALL ON SCHEMA public FROM docengine;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM docengine;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM docengine;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'app') THEN
    EXECUTE 'REVOKE ALL ON SCHEMA app FROM docengine';
  END IF;
END
$$;

-- app_admin keeps its own rights on the schema so the backend's demo wipe and
-- any operator query still work; the service itself no longer uses them.
GRANT USAGE ON SCHEMA docengine TO app_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA docengine TO app_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE docengine IN SCHEMA docengine
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_admin;
