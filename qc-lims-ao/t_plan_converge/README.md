# T_PLAN convergence — data layer (validated)

Converging on **T_PLAN** as the canonical standalone planner (decision A), grafting
in today's recursive-tree model + the real QC task data.

- **0002_enrich.sql** — extends T_PLAN's `planner_task` into a recursive tree
  (`parent_id`, `node_kind`, `is_sop`, `annex_count`, `started_at`, `ended_at`).
- **gen_tplan_import.py** — builds the enriched import from `SUMA_tasks_by_week.zip`.
- **0003_import_qc.sql** — generated import (regenerate with the script).

## What it produces (validated on pgvector/pg17 against T_PLAN schema.sql)
- 718 nodes, all owned by the **Head of QC (Blagoj Nikolov)** account
- 149 tasks + 37 subtasks + **133 annexes** (9 real + 124 materialized, `generated-annex`)
  + **399 Draft/Review/Approve steps** (`generated-step`) → 3-level tree, 0 orphans
- `is_sop` on 74 tasks; `annex_count` sum = 124
- timestamps: `started_at` = source `created_at`; `ended_at` = max(completed/updated, created) + 1h
  (always ≥ start; 718/718)

Next: deploy the full T_PLAN stack (db+server+web+gateway) to KVM4 at wwf, wire the
gateway to the existing `planner-*` Letta agents, and graft WWF's RLS/OTP hardening.
