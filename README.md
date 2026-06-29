# GrowFlow — Weekly Production Task Tracker

A standalone **task‑tracking application** for a GMP‑licensed medical‑cannabis
production facility (Purely Plant). It is the task‑management surface isolated
from the larger GrowFlow QMS/QC‑LIMS design — every task‑tracking capability,
none of the QC‑laboratory / CoA / compliance modules.

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
- **Local‑first** — state persists in `localStorage`; no server required to run.

## Repository layout

```
web/                 Standalone front-end (open web/index.html — no build step)
  index.html         App shell + all modals, loads the gf/ modules in order
  gf/                Vanilla-JS app modules
    boot-guard.js    Schema-guard (drops stale gf_* data on version change)
    data.js          Seed data + bilingual EN/МК dictionary
    core.js          State, storage, calendar, roles/permissions, helpers
    render.js        My-Week + task-card rendering
    views.js         Board / Timeline / Coordination / Dashboard / Team
    ai.js            AI helpers (Letta gateway → built-in fallback)
    assistant.js     Assistant drawer (quick actions + chat)
    voice.js         Voice capture + parse-to-task
    export.js        CSV / JSON / PDF export
    leaf-fx.js       Brand leaf animation
    main.js          Boot, CRUD, add-task, team mgmt, settings, shortcuts
    *.css            app / brand / mobile / views / leaf-fx styles
  assets/            Purely Plant brand images
backend/             Optional FastAPI + Letta "AI Gateway" (stateful agents)
deploy/              Dockerfile + nginx + compose for serving the app
docs/                Provenance + the original design HTML for reference
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

## Run the AI backend (optional)

The front‑end talks to an optional **GrowFlow AI Gateway** — a small FastAPI
service that maps each user to their own persistent **Letta stateful agent**
(running in Docker, e.g. on the KVM4 server). See [`backend/README.md`](backend/README.md).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # point LETTA_BASE_URL at your Letta server
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Then in the app open **Settings → AI backend** and set the gateway URL.

## Deploy — single Docker stack (`wwf`)

The whole thing ships as one Compose project named **`wwf`** (`wwf-web` +
`wwf-gateway`), built for KVM4 (Ubuntu 24.04 + Docker + Traefik):

```bash
cp .env.example .env        # Letta URL/key, Qdrant, JWT, Traefik host…
docker compose up -d --build
```

The gateway connects to the **Letta stateful agents and their database** (the
task‑capture store — not Supabase). Because the build sandbox blocks outbound
SSH, live deployment runs from **GitHub Actions** (`.github/workflows/deploy.yml`)
which SSH‑deploys to the VPS. Full guide: [`docs/DEPLOY.md`](docs/DEPLOY.md).

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
