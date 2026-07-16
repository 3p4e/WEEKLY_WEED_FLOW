-- GrowFlow Unified — dedupe ai_agent_bindings + enforce global uniqueness.
-- The base UNIQUE(function_key, scope, scope_id) did NOT constrain global rows:
-- scope_id IS NULL, and with the default NULLS DISTINCT, NULLs are unique, so
-- every redeploy re-inserted the 9-agent roster (live DB had 54 = 6×).
-- Collapse to one row per (function_key, scope) for global bindings (keep newest),
-- then make the constraint NULLS NOT DISTINCT so future re-inserts no-op.
-- Fully idempotent (re-runnable on existing and fresh databases).

DELETE FROM ai_agent_bindings t
WHERE t.id IN (
  SELECT id FROM (
    SELECT id, row_number() OVER (
      PARTITION BY function_key, scope, scope_id
      ORDER BY created_at DESC, id
    ) AS rn
    FROM ai_agent_bindings
  ) d WHERE d.rn > 1
);

-- Drop any earlier partial-index attempt, then converge on NULLS NOT DISTINCT.
DROP INDEX IF EXISTS ai_agent_bindings_global_uq;
ALTER TABLE ai_agent_bindings
  DROP CONSTRAINT IF EXISTS ai_agent_bindings_function_key_scope_scope_id_key;
ALTER TABLE ai_agent_bindings
  ADD CONSTRAINT ai_agent_bindings_function_key_scope_scope_id_key
  UNIQUE NULLS NOT DISTINCT (function_key, scope, scope_id);
