-- Adopt two pieces of the QC task-management lifecycle onto planner_task:
--   1. outcome  — the solution / resolution narrative recorded when work concludes
--                 (mirrors the QC "outcome" field; flows into the weekly documents).
--   2. assignment acknowledgment — an assignee accepts or declines the work
--                 (accept/decline + timestamp + optional reason).
-- assignment_status defaults to 'accepted' so the backfill of existing rows (and any
-- task not created through the API) needs no acknowledgment; create_task/update_task
-- set 'pending' explicitly when work is assigned to someone other than its creator.
ALTER TABLE planner_task
  ADD COLUMN IF NOT EXISTS outcome                 TEXT,
  ADD COLUMN IF NOT EXISTS assignment_status       TEXT NOT NULL DEFAULT 'accepted',  -- pending|accepted|declined
  ADD COLUMN IF NOT EXISTS assignment_responded_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS assignment_note         TEXT;

CREATE INDEX IF NOT EXISTS idx_planner_task_assignment ON planner_task(assignment_status);
