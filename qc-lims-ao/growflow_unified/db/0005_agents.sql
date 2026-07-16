-- GrowFlow Unified — agent ecosystem bindings + the governed change-control loop.
-- Data-driven: the app reads ai_agent_bindings to decide which stateful Letta
-- agent handles which function. New AI capabilities are added as ROWS, not code.

CREATE TABLE IF NOT EXISTS ai_agent_bindings (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  function_key   TEXT NOT NULL,                 -- catalog key the app invokes
  letta_agent_id TEXT NOT NULL,                 -- stateful agent id on the Letta stack
  agent_name     TEXT,                          -- human-readable, for operability
  scope          TEXT NOT NULL DEFAULT 'global',-- global | department | user
  scope_id       UUID,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  config         JSONB NOT NULL DEFAULT '{}',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- NULLS NOT DISTINCT so global bindings (scope_id IS NULL) are unique per
  -- (function_key, scope) — otherwise NULL scope_id re-duplicates on every redeploy.
  UNIQUE NULLS NOT DISTINCT (function_key, scope, scope_id)
);

-- Roster (provisioned on the KVM4 Letta stack; see agents/roster.md).
INSERT INTO ai_agent_bindings(function_key, letta_agent_id, agent_name) VALUES
  -- Task-Intelligence (grounded in the live task corpus)
  ('weekly_summary',      'agent-9a3642a3-f03c-4452-9462-6212eabfed4d', 'wwf_weekly_coordinator'),
  ('next_week_plan',      'agent-815929b3-8ffb-4671-992b-ee7d55273f24', 'planner-next-week-plan'),
  ('weekly_report',       'agent-c783d24a-9d85-4b0b-8882-e210f504504a', 'planner-weekly-report'),
  ('draft_description',   'agent-e8518fbc-29a2-4585-8ba8-7cb45a936a18', 'planner-task-rewrite'),
  ('executive_analytics', 'agent-e72faed9-38f8-4808-9dde-2fac12038f22', 'planner-executive-analytics'),
  -- Governance & architecture
  ('schema_advisor',      'agent-f8e93334-5ade-40a5-92a2-21fdd10ca4fc', 'wwf_schema_advisor'),
  ('qms_architect',       'agent-4eacb33a-721b-41ca-aa1d-c0389d4a7593', 'wwf_qms_architect'),
  -- GMP compliance
  ('gmp_compliance',      'agent-36d85817-fb2c-4f89-8e82-21213030d2e8', 'eu_gmp_compliance_expert'),
  ('gmp_audit',           'agent-2940efd1-ce9c-423f-a2b7-067a1e82b60d', 'qms_gmp_auditor')
-- Bare ON CONFLICT (no target) is robust to either the base constraint or a
-- legacy partial index; with NULLS NOT DISTINCT above, global re-inserts no-op.
ON CONFLICT DO NOTHING;

-- ── Worked example of the governed loop (agent proposes → human approves → migrate)
-- The Schema-Advisor's first real proposal, recorded as PENDING and awaiting a
-- human (Reviewer/QP/Manager) decision. Nothing is applied until approved.
INSERT INTO change_proposal(proposed_by, kind, target, payload, rationale, evidence, status)
SELECT 'wwf_schema_advisor', 'promote_field', 'attributes.provenance',
  jsonb_build_object(
    'new_column','provenance', 'data_type','text', 'nullable',true, 'index','btree',
    'label_en','Provenance', 'label_mk','Потекло',
    'validation','enum: deviation|capa|change_control|planned|ad_hoc|audit_finding|customer_complaint|management_review',
    'citations', jsonb_build_array('EudraLex Annex 11 §4.8','ICH Q10 §3.2.2')),
  'provenance is present on 183/195 tasks (93.8%) — the most pervasive attribute key by a wide margin. Promotion to a first-class indexed column enables deterministic query plans and satisfies Annex 11 audit-trail traceability without JSONB extraction overhead.',
  jsonb_build_object('count',183,'of',195,'pct',93.8,'distinct_keys',6),
  'pending'
WHERE NOT EXISTS (
  SELECT 1 FROM change_proposal WHERE proposed_by='wwf_schema_advisor' AND target='attributes.provenance'
);
