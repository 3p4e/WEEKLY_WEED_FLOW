# GrowFlow Unified — Adaptive Data Layer (P1)

This is the converged data layer for **GrowFlow Unified**: the **T_PLAN**
recursive planner schema (the furthest-along standalone iteration) extended with
an **adaptive, extensible, GMP-governed** model, and seeded with the real
**Quality Control** task corpus (195 SUMA tasks) owned by the **Head of QC**.

## Migration order

Apply in this exact order (each is idempotent — `IF NOT EXISTS` / `ON CONFLICT`):

| # | File | Purpose |
|---|------|---------|
| 0 | `0000_schema.sql` | T_PLAN base: `app_user`, `planner_department`, `planner_task` (flat), `planner_subtask`, progress notes, weekly reports, pgvector embeddings, `audit_event`. |
| 1 | `0002_enrich.sql` | Make `planner_task` a **recursive tree** (`parent_id`, `node_kind`, `is_sop`, `annex_count`, `started_at`, `ended_at`) + indexes. |
| 2 | `0004_adaptive.sql` | **Adaptive layer**: `attributes jsonb` (+GIN), `field_registry` (recognized variable params), `change_proposal` (agent→human governed schema evolution). |
| 3 | `0003_import_qc.sql` | Import: Head-of-QC user, departments, and the 586-node QC task tree. |

> Numbering keeps `0002`/`0003` aligned with the upstream T_PLAN convention; `0004`
> is applied **before** `0003` because the import populates `attributes`.

## Adaptive depth — the core design decision

The earlier rigid "every branch forced to 3 levels (Draft/Review/Approve)" model
was wrong. Depth is now **1..3 by the *nature* of the node**, never forced:

```
task (depth 1)                         ← every work item; leaf if no annexes
└─ annex (depth 2)                     ← each annex = its own subtask
   └─ Draft → Review → Approve (depth 3)  ← ONLY when the annex is a controlled document
```

Rule, in plain terms:

- A **task with no annexes** stays a leaf → **depth 1**.
- A **non-SOP annex** is an attachment → stays a leaf → **depth 2**.
- An **SOP annex** is a *controlled document*, so it carries the GMP document
  lifecycle **Draft → Review → Approve** (author / independent reviewer /
  QP-or-Manager approval) → **depth 3**.

**Completion never deletes the lifecycle — it sets the step *status*.** A
completed SOP annex keeps a full, *done* audit trail (ALCOA+ / 21 CFR Part 11),
rather than vanishing. This is why the tree has 267 lifecycle steps even though
all SOP-with-annex tasks in the corpus are historically `completed`.

`Draft/Review/Approve` is the only fixed count, and it is not arbitrary: it maps
to the GMP document-control workflow and the role model
(`Analyst`→`Reviewer`→`QP`). Everything else flexes with the data.

## Extensibility — columns are not frozen

Variable, long-tail parameters live in `planner_task.attributes` (JSONB, GIN
indexed) instead of new columns. The corpus already populates:
`annex_ids`, `annex_no`, `workstream`, `equipment_id`, `method_ref`,
`estimated_hours`, `est_hours_unverified`, `provenance`, and (`lifecycle`,
`position`) on steps.

`field_registry` is the catalog of recognized keys (label EN/MK, data type,
applies-to, validation). When a key recurs enough to deserve first-class status,
it is **promoted** to a core column.

`change_proposal` is the **governed evolution loop** (GMP change control): a
stateful agent proposes `add_field | promote_field | add_dependency |
add_subworkflow` with rationale + evidence; a human (`reviewed_by`) approves;
only then is a migration applied. Agents never mutate the schema directly. (P2
wires the agents to this table.)

## Provenance & safety

- All nodes are owned by **Blagoj Nikolov** (`username=blagoj`, role `hod`),
  the Head of QC, per the requirement to import under the QC department account.
- Data comes from the **uploaded SUMA export zip**, never from the live SumaDB
  Supabase project (which is read-only/off-limits real data).
- Soft-delete and the hash-chained `audit_event` table are inherited from T_PLAN.

## Validation (throwaway pgvector/pg17, all migrations applied clean)

| Check | Result |
|---|---|
| Migrations apply (0000→0002→0004→0003) | **4/4 PASS** |
| Total nodes | **586** (186 task · 133 annex · 267 step) |
| Adaptive depth (0-indexed) | d0=149 · d1=167 · d2=270 (**not uniform**) |
| Orphan nodes (bad parent_id) | **0** |
| Owned by Head-of-QC | **100%** |
| SOP tasks | 74 · annex_count sum **124** |
| Temporal integrity (ended ≥ started) | **586/586** |
| Tasks carrying attributes | 574 · 9 distinct keys |
| field_registry / change_proposal / GIN index | 6 rows / table ready / present |

## Regenerate the import

```sh
python3 gen_import.py <suma_export_dir> > 0003_import_qc.sql   # needs all_tasks.json
sh validate.sh                                                  # throwaway PG self-check
```
