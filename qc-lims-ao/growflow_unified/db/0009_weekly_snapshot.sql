-- GrowFlow Unified — weekly task snapshots (Fri→Thu work week).
-- One row per work-week window; holds the JSON captured by the scheduled
-- export job (planner_api.jobs.weekly_export). Written by the owner/admin
-- connection, so no RLS policy is required. Idempotent (re-runnable).
CREATE TABLE IF NOT EXISTS planner_weekly_snapshot (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  week_from     DATE NOT NULL,                 -- Friday (work-week start)
  week_to       DATE NOT NULL,                 -- Thursday (work-week end)
  generated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  task_count    INTEGER NOT NULL DEFAULT 0,
  created_count INTEGER NOT NULL DEFAULT 0,
  completed_count INTEGER NOT NULL DEFAULT 0,
  note_count    INTEGER NOT NULL DEFAULT 0,
  payload       JSONB NOT NULL,
  UNIQUE (week_from, week_to)
);
CREATE INDEX IF NOT EXISTS idx_pws_window ON planner_weekly_snapshot(week_from, week_to);
