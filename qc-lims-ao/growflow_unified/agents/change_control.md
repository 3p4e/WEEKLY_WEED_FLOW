# Governed Change-Control Loop (P2)

GrowFlow Unified evolves its own schema **under GMP change control**. Agents are
advisors, not actors: they **propose**, a human **approves**, the backend
**applies** a validated, audit-trailed migration. Agents never touch the schema.

```
                 observe corpus telemetry
   wwf_schema_advisor ───────────────────────────────┐
        │  emits ONE change_proposal JSON             │
        ▼                                             │
   change_proposal (status=pending)  ◀── backend persists the proposal
        │                                             │
        ▼  Reviewer / QP / Manager decision in the UI │
   approved ──▶ backend applies migration ──▶ status=applied  ──┐
   rejected ──▶ status=rejected (kept for audit)                │
        │                                                       ▼
        └────────── field_registry / core column updated; AuditEntry hash-chained
```

## The proposal contract

A proposal is a single JSON object:

```json
{
  "kind": "add_field | promote_field | add_dependency | add_subworkflow",
  "target": "attributes.<key>  |  <task type>  |  <dept>->@<dept>",
  "payload": { "...": "shape depends on kind" },
  "rationale": "concise why",
  "evidence": { "count": 0, "of": 0, "pct": 0, "examples": ["..."] }
}
```

Persisted into `change_proposal` (see `db/0004_adaptive.sql`):
`proposed_by, kind, target, payload, rationale, evidence, status (pending|
approved|rejected|applied), reviewed_by, reviewed_at`.

### Promotion rule of thumb

Promote a key from `attributes` → core column only with real evidence:
a meaningful share of rows carry it, queries need it indexed/validated, or a
regulator expects it first-class. Otherwise leave it in the JSONB tail. Prefer
the smallest change that solves the need.

## Worked example (live, verified 2026-06-28)

Telemetry fed to `wwf_schema_advisor`: `provenance=183, estimated_hours=43,
workstream=31, est_hours_unverified=31, annex_ids=25, equipment_id=18` (of 195).

The advisor returned exactly one proposal:

```json
{"kind":"promote_field","target":"attributes.provenance",
 "payload":{"new_column":"provenance","data_type":"text","nullable":true,"index":"btree",
   "label_en":"Provenance","label_mk":"Потекло",
   "validation":"enum: deviation|capa|change_control|planned|ad_hoc|audit_finding|customer_complaint|management_review",
   "citations":["EudraLex Annex 11 §4.8","ICH Q10 §3.2.2"]},
 "rationale":"provenance present on 183/195 tasks (93.8%) — most pervasive key; promotion enables deterministic queries and Annex 11 traceability.",
 "evidence":{"count":183,"of":195,"pct":93.8}}
```

This is seeded into `change_proposal` as **pending** by `db/0005_agents.sql` — it
will appear in the Governance screen awaiting a human decision. Nothing is
applied until a Reviewer/QP/Manager approves.

## Reproducing the advisor

- llm_config: `deepseek-v4-pro` @ `https://api.deepseek.com/v1`, ctx 128k, temp 1.0, max_tokens 16384, provider `deepseek-prod`.
- embedding_config: `text-embedding-3-small` @ openai, dim 1536, chunk 300.
- system prompt: `wwf_schema_advisor.system.txt`.
