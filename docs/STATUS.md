# Status — delivered vs. the full WWF/SUMA spec

> **⚠️ This file documents the ORIGINAL task-tracker foundation only.** The
> platform has since expanded far beyond it (DocEngine, next-gen TMS, a full
> QC LIMS module, and a certificate pipeline). For current, authoritative
> completion status see **[`PLATFORM-ROADMAP-2026-07.md`](PLATFORM-ROADMAP-2026-07.md)**
> (the single source of truth for sequencing) and **[`DEPLOY.md`](DEPLOY.md)**
> (live image tags + migrations + smoke records).
>
> The quick snapshot that used to sit here (2026-07-16: production "frontend
> `v63` / alembic `0016`, every new module owner-gated and test-only") went
> stale and is removed rather than updated — a version number duplicated across
> two files is a number that will disagree with itself again. **`DEPLOY.md` is
> the only place live tags and migration heads are recorded.** Production
> promotion is still owner-gated; what has changed since is that several modules
> have now been promoted, so "test-only" is no longer true as a blanket
> statement.

A **deployed, working task-tracker**: the GrowFlow UI wired to a real FastAPI
backend over Postgres (RLS), running on KVM4 behind Traefik at
`https://wwf.srv1231216.hstgr.cloud`. The full [`SPEC.md`](SPEC.md) (React/TS
app, Qdrant RAG, automated snapshots) is the larger build it grows toward.

## ✅ Done now

- **Task-tracker front-end** (`web/`) — isolated GrowFlow `gf/*` app: 6 views,
  11 departments, bilingual EN/МК, drag-and-drop board, voice capture,
  assistant, CSV/JSON/PDF export. Wired to the live backend via
  `gf/integrate.js` (login overlay, real data, writes → API).
- **Backend** (`backend/app/`) — FastAPI (async, asyncpg over Postgres), **not**
  a thin gateway:
  - **Auth & RBAC** — JWT (HS256), 6 roles, no-self-signup provisioning with
    one-time passwords, forced first-login password change.
  - **Postgres RLS** — two roles/pools (`app_user` NOBYPASSRLS / `app_admin`
    BYPASSRLS); per-request identity GUCs stamp every transaction.
  - **Tasks** — departments, calendar weeks, task lifecycle + progress notes.
  - **Audit trail** — hash-chained `audit_log` with a read-only, tamper-evident
    API (`/audit`, `/audit/tables`, `/audit/verify`) and a UI view for elevated
    roles; secrets redacted; chain verified live (218 entries, 0 breaks).
  - **Collaboration** — per-task comment threads and assignment with
    accept/decline **acknowledgment** (assigning a teammate makes the task
    visible in their week; a decline reason is recorded as a comment).
  - **AI** — functions proxied to a bound **Letta** stateful agent.
  - **Weekly report + plan** — `GET /reports/weekly?mode=report|plan` with
    Fri→Thu rolling-window logic; 7-day activity time band bucketed by hour
    from real `task_progress` timestamps (regular/overtime/weekend coloring);
    AI-generated insights via the Letta `weekly_summary` function; department
    breakdown, summary stats, prev/next week navigation; bilingual UI view.
- **Schema** — `backend/schema.users.sql` + `backend/schema.tasks.sql` (two databases): tables, RLS
  policies, and the `app.fn_audit_row` audit trigger.
- **Docker stack** — [`docker-compose.yml`](../docker-compose.yml): db +
  backend + frontend, mirroring the live KVM4 containers (Traefik HTTPS).
- **CI** — `ci.yml` (deps + import/route check + image builds + compose
  validate); `deploy.yml` is a manual-dispatch SSH deploy (production is
  provisioned out-of-band).

## 🔜 Remaining for full spec (proposed phases)

1. ~~**Weekly report + plan**~~ ✅ Done — core Fri→Thu report + plan with
   activity time band and AI insights (see above).
2. **RAG + agents** — Qdrant + VoyageAI; semantic SOP search and the analytics /
   compliance agents wired into the UI.
3. **Automated weekly snapshot** — asyncio Thu 18:00 UTC job → JSON + Markdown
   digest → DB upsert → agent knowledge base.
4. **More general (non-QC) capabilities** adopted from the QC lab — e.g.
   electronic signatures, notifications, attachments, Alembic migrations.
5. **Front-end** — optional migration to React 18 + TS + Vite with the SUMA
   design system.

Tackled in order, each phase is independently shippable on top of the current
stack.
