# AI feature inventory & letta-6ou3 migration status (2026-08-23)

Answers one question precisely: **of every AI feature this app has built or is
building, which ones actually reach `letta-6ou3` today?** Combines a full
code-level grep audit (every `backend/`, `docengine/`, `web/`, `qms-creator/`
file that touches Letta) with live verification against the running
production containers on kvm4. Where the two disagree, live verification
wins — several things below correct assumptions this session's own earlier
docs made.

**Bottom line:** two real subsystems reach letta-6ou3 and are confirmed
working live. Everything else the app has *built* AI-wise — 12 catalog
functions with live frontend UI — has never been connected to **any** Letta
server, old or new, because the table that turns them on has zero rows. That
is a different, unrelated problem from the server cutover, and fixing it is
not a "finish the migration" task — it's "activate a feature for the first
time."

---

## ✅ Fully migrated, verified live on letta-6ou3

### 1. DocEngine document-generation fleet

8 named agents (`gf_doc_orchestrator`, `gf_sop_author`, `gf_annex_author`,
`gf_translator_mk_en`, `gf_reg_checker`, `gf_raci_specialist`,
`gf_qa_auditor`, `gf_app_assistant`), declared in `docengine/agents/fleet.yaml`,
created idempotently by `docengine/app/fleet.py:ensure_fleet()`. Confirmed on
`letta-6ou3` right now (`docker exec letta-6ou3-db-1 psql … select name from
agents`) — all 8 present, model `deepseek/deepseek-v4-flash`, context window
128000.

Live-verified: `docker exec wwf-docengine … /health` →
`{"ok":true,"db":true,"letta":true,"engine":"pp-document-suite (canon
2026-07)"}`. Drives the QMS Studio wizard (`web/gf/qmsstudio-view.js`) —
questionnaire → section generation → per-section regulatory check → bilingual
gate → QA-auditor PASS/FIX loop → assembled `.docx`.

One gap: `gf_app_assistant`'s persona ("General GrowFlow in-app assistant,
non-document AI features") has **no caller anywhere in this repo** — declared
and created, never invoked. Not broken, just unused.

Retrieval doesn't run through Letta sources at all — a custom tool
`ragflow_search` hits RAGflow's REST API directly, scoped per-agent by a
`datasets:` allowlist. Three of the four datasets the document agents need
(`DB3_PP_CURRENT_unified`, `DB1_REGULATORY`, `GrowFlow_Weekly_Snapshots`) are
still un-ingested in RAGflow, so `gf_sop_author`/`gf_reg_checker`/
`gf_raci_specialist`/`gf_annex_author` currently draft without corpus
grounding. That's a RAGflow-ingestion gap, not a Letta-migration gap.

### 2. Weekly scheduler planner agents

3 agents (`wwf_weekly_report`, `wwf_next_week_plan`, `wwf_coordinator`),
created directly on letta-6ou3 during tonight's Phase 2, repointed via
`app.env`'s `LETTA_{WEEKLY_REPORT,NEXT_WEEK_PLAN,COORDINATOR}_AGENT_ID` during
Phase 3. Confirmed live: `wwf-scheduler` logs `already at wwf-prompts/v4,
skip` for both planner agents (proof the versioned system prompts in
`backend/scripts/planner_prompts.py` were applied against the real
letta-6ou3 agents, not a stale ID), and backend → letta-6ou3 returns HTTP 200
with all three IDs present.

Drives `backend/scripts/weekly_snapshot.py`'s Thursday 14:00 (Europe/Skopje)
run: builds the weekly digest, calls the two planner agents, writes `ai_pins`
rows the frontend reads (`GET /ai/pins`, rendered in
`web/gf/report-view.js:46-59`). This is genuinely live and user-visible —
report/plan pages show the scheduler's AI output — but the *generation* is
scheduler-only; there's no user-triggered "regenerate now" button for this
specific path (see `next_week_plan` on-demand, below).

One inert side-effect: `weekly_snapshot.py` also tries to upload the digest
to a Letta RAG *source* (`LETTA_SNAPSHOT_SOURCE_ID`) for
retrieval-augmentation. That variable was deliberately emptied during
tonight's cutover (retrieval now lives in RAGflow, not Letta sources), so
this path no-ops by design — the scheduler logs one benign `source attach …
failed` line per start until the backend image carrying the
`SNAPSHOT_SOURCE_ID` guard (commit `ed21fae`) is next rebuilt.

---

## ⚠️ Built, live frontend UI, but bound to nothing — not a migration gap, an activation gap

`backend/app/api/ai.py`'s generic catalog (`CATALOG` dict, 12 function keys)
is the app's main AI surface. Every one of the 12 is wired the same way: a
row in the `ai_agent_bindings` table (`org_id, function_key, letta_agent_id,
scope, is_active`) maps a function to a specific agent. **That table has
zero rows in production** — confirmed tonight (`select count(*) from
ai_agent_bindings` → `0`) and unchanged by any of this session's Letta work,
because there was nothing to migrate: no function was ever bound to an agent
on the *old* server either.

Consequence: `POST /ai/{function_key}` returns
`{"available": false, "reason": "not_configured"}` for all 12, on any Letta
server, until an ADMIN visits Settings → "AI agents" (`web/gf/integrate.js`'s
`renderAiTab`/`saveBinding`, itself fully live) and binds each function to an
agent ID.

This is real, user-facing functionality sitting behind that one empty table
— not backend scaffolding nobody built the UI for:

| Function | Frontend caller | Reachable from |
| --- | --- | --- |
| `weekly_summary` | `web/gf/integrate.js:581`, `report-view.js:83`, `views.js:623` | Report page, week view |
| `draft_description` | `web/gf/integrate.js:592,603` | Task create/edit ("expand" / "rewrite concisely") |
| `voice_capture` | `web/gf/integrate.js:632`, `web/gf/voice.js` | Voice-capture task entry |
| `corpus_qa` | `web/gf/integrate.js:646-661` (overrides `GF.assistant.complete`) | **The Assistant chat drawer** — every free-text question a user types there calls this |
| `translate_bilingual` | via `/intake/bilingual` fallback chain | AI Intake |
| `task_extract` | via `/intake/extract` fallback chain, `web/gf/intake-view.js:82` | AI Intake (paste email/plan → task candidates) |
| `risk_flag`, `progress_digest`, `dependency_advisor` | server-side only, from `documents.py`'s `_AI_SECTIONS` | "Compile document" (weekly report/plan) |
| `template_narrative` | `documents.py:_prefill_template_narratives` | Per-department GMP template sections, optional prefill |
| `workload_balance` | **no caller anywhere in `web/gf/*.js`** | Not reachable from any UI yet |
| `next_week_plan` (on-demand variant) | **no caller** — the scheduler-produced pin is a *different* code path (see above) and IS live | Not reachable on-demand |

The assistant chat drawer deserves a specific correction to earlier session
notes: `assistant.js` itself contains dead-looking logic referencing
`window.claude`/`GF.state.aiBase`/a nonexistent `/ai/chat` route — that code
never runs in production, because `integrate.js:646-661` unconditionally
overrides `provider()`/`complete()` to call the real `/ai/corpus_qa` catalog
entry instead. The drawer is correctly wired to the real system; it's
`corpus_qa`'s empty binding, not a missing route, that makes it answer
"no-ai" today.

**To activate any of these on letta-6ou3**: bind the function_key to one of
the existing `gf_*`/`wwf_*` agents (several personas overlap reasonably — e.g.
`gf_app_assistant`, currently unused, is a plausible `corpus_qa` target) or
create purpose-built agents and bind those. Either way this is a Settings-tab
action plus, for new agents, the same `fleet.yaml`-style declaration pattern
already proven for the other two subsystems above — not a data-migration
step.

---

## 🔀 Two entirely separate apps, wired to the *old* server, not called by this app

Both of these use `LETTA_URL=http://letta:8283` (the old server) and were the
main reason `docs/OLD-LETTA-DECOMMISSION-2026-08-23.md` originally listed
them as "consumers that must be repointed." A code-level grep across
`backend/` and `web/` found **zero call sites** for either — corrected in
that document tonight.

### `qms-creator/` (own `qms-api` container)

A verbatim import of a *separate* repo (`3p4e/Cannabis-EU-GMP-QMS-Creator`,
imported 2026-07-15) with its own Docker stack
(`qms-creator/docker-compose.yml`: `qms-api`/`qms-ui`/`qms-db`), never
composed into this app's `docker-compose.yml`. Its provenance doc states
outright: "nothing under `qms-creator/` is imported by `backend/` or `web/`."

It has its own independent, fairly elaborate Letta wiring — 12 named agents
(`cover, purpose, scope, definitions, raci, regulatory, procedure,
documentation, training, annex, assembler, researcher` —
`CONTENT_CREATOR_FRAMEWORK/agent_definitions.py`), native Letta *archival
memory* (not RAGflow) for two archives `db1_regulatory`/`db2_entity_qms`, and
two shared specialist agents named by env var:
`LETTA_COMPLIANCE_AGENT=eu_gmp_compliance_expert`,
`LETTA_RAG_AGENT=gmp_rag_agent`. **These two names match exactly two of the
66 agents catalogued on the old server** in
`OLD-LETTA-DECOMMISSION-2026-08-23.md`'s dormant-families list — confirming
those specific two agents belong to `qms-creator`, not to any WWF feature.

WWF's *own* federation proxy that would have talked to a `qms-api` at that
same default hostname (`backend/app/api/qms.py`) has had its API key blank in
every environment since a deliberate 2026-07-16 retirement
(`docs/DEPLOY.md`), confirmed still blank in prod tonight. The frontend
doesn't even attempt the call anymore — `web/gf/qmsknow-view.js` hardcodes a
"Knowledge search retired (503)" message. **Whatever `qms-api` container is
running on kvm4 today is an orphaned instance of this separate app, not a
WWF dependency.** No migration action needed for WWF's sake; if `qms-creator`
itself is still wanted as a product, it needs its own, separate cutover.

### `suma-api`

Zero references anywhere in this repo's `backend/` or `web/`. Belongs to the
separate SUMA/ISO17 product line (`docs/DEPLOY.md`'s "SUMA assimilation"
section describes it as WWF's ancestor project, not a subsystem of it). Out
of scope for this app's AI-feature migration entirely.

---

## Agent-free "AI-adjacent" features — no Letta dependency, nothing to migrate

Two features read as AI in name/UI but never call a language model, by
design:

- **CoQ (Certificate of Quality) generation** — `backend/app/api/qc/coq_docx.py`,
  `coq_aggregation.py` call DocEngine's *Mode B* direct-build path
  (`POST /build`), which is deterministic bilingual-Markdown-to-verified-.docx
  assembly. No agent call, despite living in "the Letta-powered document
  engine" container.
- **CoA Q&A** (`backend/app/api/qc/coa_qa.py`, `POST /qc/coa-qa`) — plain
  Postgres full-text search (`tsvector`/`websearch_to_tsquery`) over
  `qc_coa_chunks`. Migration comments in `alembic_tasks/versions/0024…py` and
  `0027…py` say this was *deliberately* deferred as FTS-only because
  "the DocEngine's Letta fleet already owns retrieval" — it was never meant
  to become a Letta feature.

---

## Dead configuration — safe to ignore, already partly cleaned up

- `LETTA_MCP_URL` / `settings.letta_mcp_url` — no backend code reads it.
  Already dropped from `.env.example` in tonight's cutover commits.
- `QDRANT_URL` / `settings.qdrant_url` — same, already dropped.
- Both were leftovers from the old server's config surface implying
  dependencies that never existed in code.

---

## Summary table

| Subsystem | Target agents | On letta-6ou3? | Live/working? |
| --- | --- | --- | --- |
| DocEngine fleet | 8 `gf_*` | ✅ yes | ✅ yes (`letta:true`, drives QMS Studio) |
| Scheduler planners | 3 `wwf_*` | ✅ yes | ✅ yes (weekly digest, report/plan pins) |
| Generic `/ai` catalog (12 functions) | *none bound* | n/a — nothing to migrate | ❌ `not_configured`, always has been |
| `documents.py` AI sections | *none bound* (same table) | n/a | ❌ same gap |
| AI Intake | *none bound* (same table) | n/a | ❌ same gap |
| Assistant chat drawer | *none bound* (`corpus_qa`) | n/a | ❌ same gap (route is correctly wired) |
| `qms-creator` (separate app) | 12 named + 2 specialists | ❌ still on old server | irrelevant to WWF; not WWF's to migrate |
| `suma-api` (separate app) | unknown | ❌ still on old server | irrelevant to WWF |
| CoQ generation, CoA Q&A | none — no LLM call | n/a | ✅ working, was never Letta-backed |
