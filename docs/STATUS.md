# Status — delivered vs. the full WWF/SUMA spec

The repo today is a **working, verified task‑tracker prototype + AI gateway +
deployable WWF stack**, isolated from the GrowFlow "Cloud Design". The full
[`SPEC.md`](SPEC.md) (React/TS production app, async FastAPI + Postgres/pgvector
+ RLS + JWT + Qdrant RAG) is the larger build it grows toward.

## ✅ Done now

- **Task‑tracker front‑end** (`web/`) — isolated GrowFlow `gf/*` app; verified it
  boots headless with all 6 views, 11 departments, 15 seed tasks, bilingual
  EN/МК, drag‑and‑drop board, voice capture, assistant, export. Many spec
  features already present: priorities, statuses, owner+helpers, weekday
  scheduling, room/batch, tags, blocker, subtasks, progress notes, dependencies,
  department handoff, weekly cycle + roll‑over, telemetry, role permissions,
  CSV/JSON/PDF export, AI rewrite + weekly summary.
- **AI gateway** (`backend/`) — FastAPI (async) bridging the app to the **Letta
  stateful agents**; task‑only endpoints (paraphrase, parse‑voice,
  weekly‑summary, chat, reset). QC endpoints removed.
- **Dependencies** — full set declared and **installed/verified** (FastAPI,
  Uvicorn/Gunicorn, Letta client, psycopg3 + SQLAlchemy 2.0 async, httpx,
  tenacity, dotenv).
- **WWF Docker stack** — single Compose project `wwf` (`wwf-web` + `wwf-gateway`),
  prod Dockerfiles, nginx same‑origin proxy, Traefik labels, `.env.example`.
- **CI/CD** — GitHub Actions: `ci.yml` (deps + image builds + compose validate)
  and `deploy.yml` (SSH deploy to KVM4 — the path around the sandbox port‑22 block).
- **Live infra inspected** — KVM4 (Hostinger), the 9‑agent WWF/planner group on
  Letta, and the Letta store confirmed as the task‑capture database (not suma_db).

## 🔜 Remaining for full spec (proposed phases)

1. **Backend ↔ Letta DB** — async SQLAlchemy/psycopg models over the Letta
   Postgres+pgvector store; task/annex/step tree; weekly plan/report documents;
   soft delete + hash‑chained audit; idempotent SQL migrations.
2. **Auth & RBAC** — JWT (HS256) sessions, 6 roles, provisioning, password reset,
   first‑login change, lockout; Postgres RLS (admin‑bypass / app‑no‑bypass).
3. **Assignment lifecycle** — acknowledgment (accept/decline + reason) on cards.
4. **RAG + agents** — Qdrant + VoyageAI; wire the 9 stateful agents (executive
   analytics, compliance, schema advisor) and semantic SOP search into the UI.
5. **Automated weekly snapshot** — asyncio Thu 18:00 UTC job → JSON + Markdown
   digest → DB upsert → agent knowledge base.
6. **Governance** — extensible field registry + AI‑proposed schema/workflow
   changes with human approval lifecycle.
7. **Front‑end** — migrate to React 18 + TS + Vite with the SUMA design system
   (6 themes), Lucide icons, jsPDF export, executive analytics dashboards.

Tackled in order, each phase is independently shippable on top of the current
stack.
