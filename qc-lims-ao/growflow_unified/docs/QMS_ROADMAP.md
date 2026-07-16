# GrowFlow Unified — QMS Module Roadmap (P6)

How the converged task manager grows into a full EU-GMP / ISO 17025 / 21 CFR
Part 11 **Quality Management System** — *by extension, not rewrite*. Every module
below reuses the five primitives already shipped (P1–P5):

| Primitive | Reused for QMS as… |
|---|---|
| Recursive tree (`node_kind`) | new record types are new `node_kind`s (deviation, capa, sop, …) under the same tree + RLS |
| `attributes` JSONB + `field_registry` | per-record-type variable fields, governed before promotion |
| `change_proposal` loop | the *engine* for formal Change Control; the template for every approval workflow |
| Stateful agents | one advisory + one compliance agent per module (propose, never decide) |
| RLS + hash-chained audit | record-level access + ALCOA+ e-records for every module |

Sequencing favours regulatory weight and dependency order. Each phase lands a
migration (`00NN_*.sql`), a router, a view, agent bindings, and acceptance tests —
the same rhythm as P1–P5.

---

## Q1 — Document Control (SOPs, controlled documents)

**Why first:** everything else references controlled documents; the SOP-annex
lifecycle (Draft→Review→Approve) already exists as `node_kind='step'`.

- **Model:** `node_kind='sop'` task with `attributes`: `doc_number`, `version`,
  `effective_date`, `review_due`, `state` (draft|effective|superseded|retired),
  `supersedes`. Annex children + lifecycle steps already model the authoring flow.
- **New:** version chain (`supersedes` self-ref), periodic-review scheduler
  (a daily job raises a review task when `review_due` ≤ today + N).
- **e-signature:** extend `audit_event` with `meaning` (authored|reviewed|approved)
  + signer identity — the hash chain already gives tamper-evidence.
- **Agent:** `qms_sop_expert` (exists) drafts; `qms_gmp_auditor` (exists) checks.
- **Refs:** EudraLex Ch. 4; Annex 11 §4, §8; 21 CFR 211.180/211.186.
- **Done when:** create→review→approve→effective→supersede works end-to-end with
  signed audit entries and an automatic periodic-review task.

## Q2 — Deviation & OOS → CAPA

**Why next:** the highest-frequency quality event; feeds CAPA and Change Control.

- **Model:** `node_kind='deviation'` and `node_kind='oos'`; `attributes`:
  `severity`, `batch`, `root_cause`, `risk_class`, `disposition`. Investigation
  steps are children (immediate action → investigation → root-cause → CAPA link).
- **CAPA:** `node_kind='capa'` with `attributes`: `type` (corrective|preventive),
  `owner`, `due`, `effectiveness_check_due`, `verification`. A CAPA links to its
  source deviation/OOS via `planner_task_dependency`.
- **Governed close-out:** closing a CAPA/deviation routes through the
  `change_proposal`-style approval (QP/Manager sign-off) — reuse the loop.
- **Agent:** a new `capa_advisor` proposes root-cause categories + CAPA actions
  from similar past events (RAG over the corpus); humans decide.
- **Refs:** Annex 11; ICH Q10 §3.2.1; 21 CFR 211.192.
- **Done when:** an OOS opens an investigation, spawns a CAPA, and both close with
  effectiveness verification + audit trail.

## Q3 — Change Control (formal register)

**Why now:** Q1/Q2 generate changes; we already have the *engine*.

- **Model:** promote `change_proposal` into a first-class **Change Control**
  register: add `risk_assessment`, `impacted_documents[]`, `implementation_plan`,
  `verification`, `closure`. Schema-evolution proposals become one *category* of a
  general CC record.
- **Workflow:** raise → impact/risk assess → approve (QP) → implement → verify →
  close — each a lifecycle step, each signed.
- **Agent:** `wwf_schema_advisor` (exists) for schema CCs; `wwf_qms_architect`
  (exists) for impact analysis.
- **Refs:** Annex 15; ICH Q10 §3.2.3; 21 CFR 211.100.
- **Done when:** a change (incl. an agent-proposed field promotion) flows raise→
  close with linked impacted documents and a verified implementation.

## Q4 — Training & Competency

**Why:** SOP effectiveness depends on read-and-understood; inspections check it.

- **Model:** `training_record` linking `app_user` × controlled document × version,
  with `assigned`, `completed`, `assessment_score`. New effective SOP versions
  auto-assign read-training to role-matched users.
- **Gate:** optionally block a user from owning a task type until trained
  (enforced in the API + surfaced in the UI).
- **Agent:** a `training_curator` proposes the assignment matrix (role × SOP).
- **Refs:** EudraLex Ch. 2; 21 CFR 211.25.
- **Done when:** approving an SOP version raises training tasks and a competency
  matrix view shows per-user gaps.

## Q5 — Equipment & Calibration

**Why:** ISO 17025 core; the `equipment_id` attribute key already appears in the
corpus (a Schema-Advisor promotion candidate).

- **Model:** `node_kind='equipment'` + `calibration`/`maintenance` child records;
  `attributes`: `instrument_id`, `last_cal`, `cal_due`, `status`
  (in-service|out-of-service|quarantine). Promote `equipment_id` to a core column
  via the governed loop once usage justifies it.
- **Scheduler:** `cal_due` raises calibration tasks; out-of-cal equipment blocks
  dependent test tasks.
- **Refs:** ISO 17025 §6.4; Annex 1; 21 CFR 211.68.
- **Done when:** equipment carries a calibration schedule and overdue calibration
  flags/blocks dependent QC work.

---

## Cross-cutting (delivered alongside, not as a separate phase)

- **E-signatures (21 CFR Part 11 §11.50/11.70):** signer + meaning + timestamp on
  every approval, chained into `audit_event`. Foundation already in place.
- **Periodic review engine:** one scheduled job driving Q1 review, Q4 retraining,
  Q5 calibration due-dates — a single due-date sweeper over `attributes`.
- **Supplier/vendor qualification & audit-readiness:** later record types reusing
  the same tree + governance.
- **Reporting / inspection pack:** export a date-bounded, hash-verified slice of
  `audit_event` + records for an inspector.

## Engineering pattern per module (the repeatable recipe)

1. `db/00NN_<module>.sql` — new `node_kind` values, `attributes` keys seeded into
   `field_registry`, any new link/lifecycle, RLS policies, indexes.
2. `server/routers/<module>.py` — CRUD + lifecycle transitions through `rls_session`,
   each transition writing a signed `audit_event`.
3. `web/src/views/<Module>View.tsx` — list + record + lifecycle, bilingual EN/МК,
   compliance badges.
4. Agent binding row in `ai_agent_bindings` (+ a system prompt file under `agents/`).
5. Acceptance tests in the `smoke_gf.py` style (in-process ASGI vs a live DB),
   asserting the lifecycle, RLS, and audit chain.

This keeps the system one coherent app — a single tree, one governance loop, one
audit chain, one auth model — that *accretes* QMS capability module by module.
