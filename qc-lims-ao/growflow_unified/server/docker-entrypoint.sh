#!/usr/bin/env sh
# Wait for Postgres, apply the converged migrations in order (idempotent), set the
# RLS app-role password from env, then serve.
set -e

PGHOST="${PGHOST:-db}"; PGUSER="${PGUSER:-postgres}"; PGDATABASE="${PGDATABASE:-growflow}"
export PGPASSWORD="${PGPASSWORD:-postgres}"

echo "==> waiting for postgres at ${PGHOST}:5432"
until pg_isready -h "$PGHOST" -U "$PGUSER" >/dev/null 2>&1; do sleep 2; done

echo "==> applying migrations"
# The baseline (0000) is not idempotent (plain CREATE TABLE); every later migration
# is (IF NOT EXISTS / ON CONFLICT / DROP POLICY IF EXISTS). So skip the baseline when
# the schema already exists — makes redeploys against a persisted volume safe.
SCHEMA_PRESENT=$(psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -tAc \
  "SELECT to_regclass('public.planner_department') IS NOT NULL" 2>/dev/null || echo f)
for f in 0000_schema 0002_enrich 0004_adaptive 0003_import_qc 0005_agents 0006_auth_rls 0007_hierarchy 0008_password_reset 0009_weekly_snapshot 0010_agent_bindings_dedupe 0011_task_outcome_assignment; do
  if [ "$f" = "0000_schema" ] && [ "$SCHEMA_PRESENT" = "t" ]; then
    echo "    -> $f.sql (skip: schema already present)"; continue
  fi
  echo "    -> $f.sql"
  psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -q -f "/app/db/$f.sql"
done

# Provision the RLS app-role password (growflow_app) so the NOBYPASSRLS data
# connection can authenticate. Without this the app falls back to the admin role.
if [ -n "$GROWFLOW_APP_PASSWORD" ]; then
  echo "==> setting growflow_app role password"
  psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -q \
    -c "ALTER ROLE growflow_app LOGIN PASSWORD '${GROWFLOW_APP_PASSWORD}';"
fi

echo "==> starting GrowFlow Unified API"
exec python -m planner_api.main
