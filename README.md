# GrowFlow — Weekly Production Task Tracker

The operations application of a GMP‑licensed medical‑cannabis facility
(Purely Plant, Petrovec). It began in July 2026 as the task‑tracking surface
of the GrowFlow design; by September 2026 it also holds the QC / LIMS modules
(specifications, samples and custody, CoA / eCoA / iCoA, Certificates of
Quality, OOS, e‑signatures, the official product catalogue), cultivation
(batches, plant and mother‑plant identity, phases, harvest gates, the
as‑built facility layout) and DocEngine Studio (controlled‑document
drafting). The complete list of what the application contains, with dates
and provenance, is [`docs/review-2026-09-27/inventory.md`](docs/review-2026-09-27/inventory.md);
the validation status and the open scope decision are in
[`docs/SCOPE.md`](docs/SCOPE.md). The section below describes the original
task‑tracking core, which is unchanged.

> Plan, assign, schedule and track production work across the week — by
> department, person, priority and status — with bilingual EN/МК UI, voice
> capture, an AI assistant, and weekly AI summaries.

---

## Features

- **Six work views**
  - **My Week** — this‑week / next‑week panels, expandable task cards, live
    completion telemetry (completion %, totals, working / stuck / postponed,
    busiest day).
  - **Board** — kanban by status with drag‑and‑drop.
  - **Timeline** — Mon–Fri day columns.
  - **Coordination** — cross‑department handoff chain
    (Cloning → Veg → Flower → Production → QC → QA → Warehouse‑out) with
    ready / waiting / blocked state.
  - **Dashboard** — KPIs plus status, department and per‑person workload
    breakdowns and a blocker list.
  - **Team** — people & roles management (create / edit / remove).
- **Rich tasks** — accountable owner + responsible helpers, status, priority,
  weekday scheduling, week, room, batch, tags, description, blocker, progress
  notes, subtasks and dependencies (met / unmet).
- **Filtering & search** — by day, by department, and free‑text across title /
  room / batch / id; week navigation and roll‑over of unfinished work.
- **Role‑based permissions** — 14 roles (`backend/app/roles.py`): ADMIN;
  the executives OWNER, CEO, COO; the department managers QA_MGR, QC_MGR,
  PR_MGR, WH_MGR, SE_MGR, CU_MGR, IR_MGR, MU_MGR; the QP; and USER. A
  manager's scope is their department and its sub‑departments
  (`docs/DEPARTMENT-MODEL-2026-09.md`).
- **Bilingual** — English / Македонски throughout (UI, statuses, departments,
  priorities).
- **Voice task capture** — speak a task; it is parsed into structured fields
  (Web Speech API + AI parsing).
- **AI assistant** — drafting, weekly report / next‑week plan, risk & blocker
  flagging, handoff suggestions, and free chat. Works offline for the
  deterministic quick actions; richer prose when an AI backend is reachable.
- **Export** — CSV · JSON · PDF.
- **Audit Trail** — read-only, tamper-evident view of the hash-chained audit
  log (elevated roles), with chain-integrity verification and before/after diffs.
- **Two modes** — the `web/` UI can run standalone on `localStorage` for a quick
  look, but the deployed build is wired to the real backend (live auth, data
  and audit) via `gf/integrate.js`.

## Repository layout

```
web/                 Standalone front-end (open web/index.html — no build step)
  index.html         App shell + all modals, loads the gf/ modules in order
  gf/                Vanilla-JS app modules
    boot-guard.js    Schema-guard (drops stale gf_* data on version change)
    data.js          Bilingual EN/МК dictionary + status/priority/department definitions
    core.js          State, storage, calendar, roles/permissions, helpers
    render.js        My-Week + task-card rendering
    views.js         Board / Timeline / Coordination / Dashboard / Team
    assistant.js     Assistant drawer (quick actions + chat)
    voice.js         Voice capture + parse-to-task
    export.js        CSV / JSON / PDF export
    leaf-fx.js       Brand leaf animation
    main.js          Boot, CRUD, add-task, team mgmt, settings, shortcuts
    api.js           Backend client (login, tasks, ai, audit)
    integrate.js     Wires the UI to the live backend (auth, real data, audit view)
    *.css            app / brand / mobile / views / leaf-fx styles
  assets/            Purely Plant brand images
  Dockerfile         nginx image; nginx.conf reverse-proxies the API same-origin
backend/             FastAPI API (asyncpg, JWT, RLS, audit) — app/ package
  app/               main, config, db, security, deps, api/{auth,tasks,ai,audit}
  schema.users.sql / schema.tasks.sql   per-database structure + RLS + audit trigger (generated)
docker-compose.yml   Deployed stack: db + backend + frontend (mirrors KVM4)
docs/                Spec, status, deploy guide, provenance + design HTML
```

## Run the front-end

It is a static app with no build step. Any static server works:

```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000
```

(Opening `web/index.html` directly via `file://` also works, though a local
server is recommended so the browser treats it as a normal origin.)

The app runs **fully offline**: tasks, all views, filtering, voice capture and
export need no backend. AI features light up automatically when either the
in‑browser model is available or an AI gateway is configured in **Settings**.

## Run the backend

The real backend is a **FastAPI** app (asyncpg over Postgres, JWT auth, RLS,
provisioning, and a hash-chained audit trail) that the GrowFlow UI talks to
same-origin via nginx. AI functions are proxied to a **Letta stateful agent**;
credentials never reach the browser. See [`backend/README.md`](backend/README.md).

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env      # USERS_/TASKS_DATABASE_URL (+_ADMIN_) / SECRET_KEY / LETTA_*
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Deploy — Docker stack

[`docker-compose.yml`](docker-compose.yml) describes the deployed stack
(Ubuntu 24.04 + Docker + Traefik on KVM4):

| Service          | Image                        | Role |
|------------------|------------------------------|------|
| `db-users`       | `postgres:17-alpine`         | Identity DB (organizations, profiles) — own RLS + audit chain |
| `db-tasks`       | `postgres:17-alpine`         | Work DB (tasks, QC LIMS, documents) — own RLS + audit chain |
| `backend`        | `weekly_weed_flow-backend`   | FastAPI API (:8000, internal) |
| `scheduler`      | `weekly_weed_flow-backend`   | Same image, scheduler entrypoint — weekly snapshot + due-scan |
| `frontend`       | `wwf-growflow`               | nginx + GrowFlow UI, published by Traefik (HTTPS) |
| `db-backup`      | `postgres:17-alpine`         | Scheduled `pg_dump` of both databases to a local volume |
| `backup-offsite` | `rclone/rclone:1`            | Encrypted push of those dumps to Google Drive (rclone crypt) |
| `capture-mcp`    | `wwf-capture-mcp`            | MCP connector for task capture (`connector/`) |

This table is what `docker-compose.yml` defines at HEAD, including the
`docengine` service and the `ai-net` network the host runs it on (added to the
compose file on 2026-09-27; before that the service block lived only in
[`docs/DEPLOY.md`](docs/DEPLOY.md)).

The always-on **Letta** agent layer runs in its own pre-existing stack and is
reached over `host.docker.internal`. Production was provisioned out-of-band;
[`deploy.yml`](.github/workflows/deploy.yml) is **manual-dispatch only** and
drives the deploy through the host's kvm4-runner `/shell` API (no SSH), one
service scope at a time. Full guide incl. the one-time role bootstrap:
[`docs/DEPLOY.md`](docs/DEPLOY.md).

## Status & roadmap

What the application contains, with dates and provenance, is
[`docs/review-2026-09-27/inventory.md`](docs/review-2026-09-27/inventory.md);
its validation status and the open operating-mode decision are in
[`docs/SCOPE.md`](docs/SCOPE.md); the decisions still waiting on the owner are
in [`docs/DECISIONS-2026-09.md`](docs/DECISIONS-2026-09.md). `docs/SPEC.md` is
the original July target and is kept as history.

## Keyboard shortcuts

`←` / `→` change week · `Ctrl/⌘ + K` focus search · `Esc` close modals.

## Provenance

Isolated in July 2026 from the multi‑module GrowFlow "Cloud Design" source
(Production task manager **+** QC‑LIMS) as the task‑tracking modules only. Since
August the QC / LIMS, cultivation and DocEngine modules have been built into this
same application (see the first paragraph and the inventory); the July exclusion
no longer describes the code. History: [`docs/PROVENANCE.md`](docs/PROVENANCE.md).
