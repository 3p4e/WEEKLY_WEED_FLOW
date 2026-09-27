# WWF / SUMA — Authoritative Specification

Target specification for **Weekly Weed Flow** (SUMA). The vanilla‑JS app under
`web/` is the working **task‑tracker prototype** isolated from the GrowFlow
design; this document is the production north star it grows toward. See
[`STATUS.md`](STATUS.md) for the done‑vs‑remaining map.

> **Persistence:** task capture runs on the **Letta stateful agents and their
> backing database** (PostgreSQL 17 + pgvector) — *not* the separate Supabase
> `suma_db`. The "Database" row below refers to Letta's own store.

## Features & Capabilities

### Core task management
Create / edit / delete tasks with title, description, priority (critical→low)
and status (pending → working → in review → stuck → postponed → done); owner +
helpers; schedule to a work week and weekdays; room/location + batch/lot
metadata; free‑form tags; blocker capture when stuck; outcome/resolution
narrative on completion; checklist subtasks; per‑day progress notes; task
dependencies; department handoff with tracked status.

### Assignment lifecycle
Cross‑user assignment raises an acknowledgment request; assignee accepts/declines
with optional reason; assignment state (pending/accepted/declined) shown on every
card; reassignment resets the acknowledgment cycle.

### Hierarchical task tree
Three‑level adaptive structure: **task → annex → step**; SOP flag and annex count
per node; nested tree‑view navigation.

### Work‑week cycle (Fri → Thu)
Weekly **plan** (upcoming) and **report** (completed) documents; status‑band
summary (total, done %, working, in review, stuck, postponed, pending); week
navigation; draft → submit workflow.

### Document export
JSON (full snapshot) · CSV (status‑summary + per‑task rows, UTF‑8 BOM) ·
PDF (A4 table + GMP sign‑off block: Prepared/Reviewed/Approved + dates)
— *the weekly-document PDF is not implemented; QC documents (CoQ .docx, the
A4 specification page, DocEngine PDFs) and e‑signatures ARE implemented — see
[`docs/SCOPE.md`](SCOPE.md) "Status 2026-09-27"* · Markdown digest (pushed to
AI agents).

### Automated weekly snapshot
In‑process asyncio job (Thu 18:00 UTC) captures the closing week → writes JSON +
Markdown digest to disk, upserts into the DB, and pushes the digest to the agent
knowledge base (idempotent).

### AI integration
AI‑assisted report drafting; AI rewrite with tone (concise/formal/friendly);
nine stateful Letta agents (weekly coordinator, planner‑executive, analytics,
compliance, schema advisor, …); agent invocation from the UI; semantic
SOP/document search (RAG via vector embeddings); executive insights
(highlights, risks, forward‑looking analysis).

### Executive analytics
Cross‑department completion rates + headcount; per‑user workload/done counts;
report submission tracking; AI executive summary across teams.

### Governance & change control
Extensible field registry (core columns + long‑tail JSON attributes); AI‑proposed
schema/workflow changes with human approval; proposal lifecycle
pending → approved → rejected → applied.

### User & access management
JWT sessions (configurable TTL, 12 h default); 14 roles (`backend/app/roles.py`:
ADMIN, OWNER/CEO/COO, the eight department managers QA_MGR/QC_MGR/PR_MGR/
WH_MGR/SE_MGR/CU_MGR/IR_MGR/MU_MGR, QP, USER); department affiliation +
cross‑department flag; admin provisioning with one‑time temporary password;
self‑service password reset (email or shown‑once code); forced first‑login
change; login‑attempt limiting with timed lockout.

### Compliance & audit
Soft delete everywhere (`is_deleted`, 10‑year retention, no hard erase);
hash‑chained audit trail on every write; Row‑Level Security at the DB layer;
UTC timestamps; electronic‑signature metadata — *not implemented; out of
scope per [`docs/SCOPE.md`](SCOPE.md), WWF is a non‑GMP planning tool*.

### Internationalization & theming
Bilingual UI (English + second language), runtime switch; six visual themes,
persisted per device; fully token‑driven design system (CSS custom properties).

## Technology stack

| Layer | Technology |
|---|---|
| API runtime | Python 3.12, FastAPI (async), Uvicorn |
| Database | PostgreSQL 17 + pgvector |
| Driver | asyncpg (raw SQL); two alembic chains (`alembic_users`, `alembic_tasks`) with `schema.*.sql` baselines diffed in CI |
| Auth | JWT (HS256), bcrypt |
| DB security | Postgres RLS on every org table, two roles (admin bypass / app no‑bypass), hash‑chained audit log |
| Frontend | Vanilla JS (`web/gf/*.js`, no build step), service worker, jsdom unit tests + Playwright e2e |
| Documents | python‑docx / WeasyPrint server‑side (CoQ .docx, A4 specification page); DocEngine PDFs |
| Design system | Custom (CSS custom properties, skins) |
| AI agents | Letta (stateful, long‑memory) via DocEngine and the backend's function catalogue |
| Retrieval | RAGflow datasets (see `docengine/fleet.yaml`) |
| Scheduler | asyncio background task (in‑process) |
| Orchestration | Docker Compose |
| Reverse proxy / TLS | Traefik + Let's Encrypt |
| CI/CD | GitHub Actions → SSH deploy to VPS |
| Migrations | Hand‑authored idempotent SQL (IF NOT EXISTS / ON CONFLICT) |
| Export | JSON, CSV (UTF‑8 BOM), PDF (A4), Markdown |
