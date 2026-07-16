-- T_PLAN enrichment (grafted from today's WWF build):
-- make planner_task a recursive tree so it holds the 3-level QC model
-- (task -> annex -> Draft/Review/Approve) and carries SOP/annex/temporal data.
ALTER TABLE planner_task
  ADD COLUMN IF NOT EXISTS parent_id   UUID REFERENCES planner_task(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS node_kind   TEXT NOT NULL DEFAULT 'task',     -- task | annex | step
  ADD COLUMN IF NOT EXISTS is_sop      BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS annex_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS started_at  TIMESTAMPTZ,                       -- = source created_at
  ADD COLUMN IF NOT EXISTS ended_at    TIMESTAMPTZ;                       -- = end (+1h)
CREATE INDEX IF NOT EXISTS idx_planner_task_parent ON planner_task(parent_id);
CREATE INDEX IF NOT EXISTS idx_planner_task_kind   ON planner_task(node_kind);
