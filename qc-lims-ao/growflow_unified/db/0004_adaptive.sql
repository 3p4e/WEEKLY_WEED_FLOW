-- T_PLAN adaptive layer: extensible per-task attributes + a governed field
-- registry + an agent change-proposal table (GMP change control).
ALTER TABLE planner_task ADD COLUMN IF NOT EXISTS attributes jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_planner_task_attrs ON planner_task USING gin (attributes);

-- The set of recognized variable parameters. Core columns stay validated/queryable;
-- the long tail lives in attributes until a key recurs enough to be promoted.
CREATE TABLE IF NOT EXISTS field_registry (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key         TEXT UNIQUE NOT NULL,
  label_en    TEXT NOT NULL,
  label_mk    TEXT,
  data_type   TEXT NOT NULL DEFAULT 'text',   -- text|number|date|bool|enum|ref
  applies_to  TEXT NOT NULL DEFAULT 'task',    -- task|annex|step|any
  validation  JSONB NOT NULL DEFAULT '{}',
  status      TEXT NOT NULL DEFAULT 'active',  -- active|proposed|deprecated
  promoted    BOOLEAN NOT NULL DEFAULT FALSE,  -- promoted to a core column?
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agent-driven, human-approved schema/workflow evolution (proposal -> approval -> migration).
CREATE TABLE IF NOT EXISTS change_proposal (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proposed_by  TEXT NOT NULL,                  -- agent name (e.g. schema_advisor)
  kind         TEXT NOT NULL,                  -- add_field|promote_field|add_dependency|add_subworkflow
  target       TEXT,                           -- e.g. 'attributes.equipment_id' or a task type
  payload      JSONB NOT NULL DEFAULT '{}',
  rationale    TEXT NOT NULL,
  evidence     JSONB NOT NULL DEFAULT '{}',    -- counts/examples backing the proposal
  status       TEXT NOT NULL DEFAULT 'pending',-- pending|approved|rejected|applied
  reviewed_by  UUID REFERENCES app_user(id),
  reviewed_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_change_proposal_status ON change_proposal(status);

-- Seed the registry with keys we already recognize in the QC corpus.
INSERT INTO field_registry(key,label_en,label_mk,data_type,applies_to) VALUES
  ('annex_ids','Annex IDs','Анекс ID','enum','task'),
  ('workstream','Workstream','Работен тек','text','any'),
  ('equipment_id','Equipment ID','ID на опрема','ref','any'),
  ('method_ref','Method reference','Метода','text','any'),
  ('estimated_hours','Estimated hours','Проценети часови','number','any'),
  ('provenance','Source provenance','Потекло','text','any')
ON CONFLICT (key) DO NOTHING;
