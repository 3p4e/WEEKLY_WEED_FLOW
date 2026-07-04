# GrowFlow — Weekly Production Task Tracker

A standalone **task‑tracking application** for a GMP‑licensed medical‑cannabis
production facility (Purely Plant). It is the task‑management surface isolated
from the larger GrowFlow QMS/QC‑LIMS design — every task‑tracking capability,
none of the QC‑laboratory / CoA / compliance modules. **WWF is an internal
operational planning tool, not a validated GxP/Part‑11 computerized system and
not part of the QMS — see [`docs/SCOPE.md`](docs/SCOPE.md).**

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
- **Role‑based permissions** — admin · HOD · QA · QP · operator · viewer.
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
  schema.sql         DB structure + RLS policies + hash-chained audit trigger
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
cp ../.env.example .env      # DATABASE_URL / ADMIN_DATABASE_URL / SECRET_KEY / LETTA_*
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Deploy — Docker stack

[`docker-compose.yml`](docker-compose.yml) describes the deployed stack
(Ubuntu 24.04 + Docker + Traefik on KVM4):

| Service    | Image                          | Role |
|------------|--------------------------------|------|
| `db`       | `postgres:17-alpine`           | RLS policies + audit trigger |
| `backend`  | `weekly_weed_flow-backend`     | FastAPI API (:8000, internal) |
| `frontend` | `wwf-growflow`                 | nginx + GrowFlow UI, published by Traefik (HTTPS) |

The always-on **Letta** agent layer runs in its own pre-existing stack and is
reached over `host.docker.internal`. Production was provisioned out-of-band, so
the SSH-based [`deploy.yml`](.github/workflows/deploy.yml) is **manual-dispatch
only**. Full guide incl. the one-time role bootstrap: [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Status & roadmap

This repo is a working task‑tracker prototype + AI gateway + deployable stack.
The full production target (React/TS, async FastAPI over the Letta Postgres,
RLS/JWT, Qdrant RAG) is captured in [`docs/SPEC.md`](docs/SPEC.md); what's done
vs. remaining is in [`docs/STATUS.md`](docs/STATUS.md).

## Keyboard shortcuts

`←` / `→` change week · `Ctrl/⌘ + K` focus search · `Esc` close modals.

## Provenance

Isolated from the multi‑module GrowFlow "Cloud Design" source (Production task
manager **+** QC‑LIMS). Only the production task‑tracking modules (`gf/*`) and
the task‑relevant gateway endpoints are included here; the QC‑laboratory, CoA,
stability and OOS modules are intentionally excluded. See
[`docs/PROVENANCE.md`](docs/PROVENANCE.md).
