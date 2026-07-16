# GrowFlow Unified — Agent Ecosystem (P2)

Stateful **Letta** agents on the KVM4 stack (deepseek-v4 via the BYOK gateway).
The app binds *functions* → *agents* through the `ai_agent_bindings` table
(`db/0005_agents.sql`), so capabilities are added as **rows, not code**. Every
call degrades gracefully: if no binding exists or the stack is unreachable, the
endpoint returns `{available:false}` and the UI falls back (3-tier resilience).

## Roster

| Function key | Agent | ID | Model | Role |
|---|---|---|---|---|
| `weekly_summary` | `wwf_weekly_coordinator` | `agent-9a3642a3…` | flash | Summarize the week; flag blocked/overdue/at-risk. |
| `next_week_plan` | `planner-next-week-plan` | `agent-815929b3…` | pro | Propose next week's plan from the corpus. |
| `weekly_report` | `planner-weekly-report` | `agent-c783d24a…` | flash | Draft the weekly report. |
| `draft_description` | `planner-task-rewrite` | `agent-e8518fbc…` | flash | Expand a title into description + subtasks. |
| `executive_analytics` | `planner-executive-analytics` | `agent-e72faed9…` | pro | Cross-department executive analytics. |
| `schema_advisor` | **`wwf_schema_advisor`** | `agent-f8e93334…` | pro | **Governed schema evolution** — proposes `change_proposal` rows. |
| `qms_architect` | `wwf_qms_architect` | `agent-4eacb33a…` | pro | Design-of-record keeper; adaptive-depth & data-integrity judge. |
| `gmp_compliance` | `eu_gmp_compliance_expert` | `agent-36d85817…` | pro | EU GMP Annex 1-19 / PIC-S guidance. |
| `gmp_audit` | `qms_gmp_auditor` | `agent-2940efd1…` | pro | Validate documents/records against EU GMP annexes. |

Grouped capabilities:

- **Task-Intelligence** = weekly_summary + next_week_plan + weekly_report + draft_description + executive_analytics. Grounded in the live task corpus (RAG over `planner_task`).
- **Governance** = schema_advisor (proposes) + qms_architect (architectural memory).
- **GMP-Compliance** = gmp_compliance + gmp_audit.

## Design-of-record

`wwf_qms_architect` holds the project's architectural memory across sessions.
The finalized P1 record (convergence, adaptive data model, validation evidence,
roster) is persisted as an **archival passage** (id `passage-942e81c7…`,
written 2026-06-28) so any future session can recover full context via
`search_archival`.

## Provisioning is reproducible

`wwf_schema_advisor` was created with the system prompt in
`wwf_schema_advisor.system.txt` and the standard deepseek-v4-pro llm/embedding
config (see `change_control.md`). To recreate it elsewhere, create a Letta agent
with that name + system prompt + config.
