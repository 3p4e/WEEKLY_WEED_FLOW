# QC_LIMS_Ao — GrowFlow Unified

EU GMP-compliant QC LIMS for **Purely Plant GmbH** — a licensed medical cannabis
flower producer and API manufacturer in North Macedonia. Scope: QC laboratory
operations for dried cannabis flower (medical use) — raw-material sampling,
in-process control testing, finished-product release, stability studies and water
system QC.

**GrowFlow Unified** is the application: one shell with two modes —

- **Production** — weekly cultivation/production task board (departments, owners,
  subtasks, dependencies, cross-department handoffs, telemetry).
- **QC Lab** — the QC LIMS workspace: samples, specifications, Certificate of
  Analysis, OOS investigations, results entry, SP-06 reception, AI search and an
  Annex 11 audit trail.

The UI is bilingual (English / Македонски).

## Architecture

A real client–server system (not a static page):

```
┌──────────────────────────┐   same-origin    ┌──────────────────────┐   asyncpg   ┌────────────┐
│  React + Vite SPA (nginx) │ ───── /api ────▶ │  FastAPI backend      │ ──────────▶ │ PostgreSQL │
│  GrowFlow Unified UI      │ ◀──────────────  │  JWT auth · audit trail│ ◀────────── │  (qc_lims) │
└──────────────────────────┘                   └──────────────────────┘             └────────────┘
        :8080 (nginx)                                  :8000 (uvicorn)                   :5432
```

- `frontend/` — React + Vite SPA. The prototype's pixel-perfect design tokens
  (`src/styles/app.css`) are reused verbatim; logic is rebuilt as components.
  Offline-first: runs on bundled seed data with no backend, and loads live data
  once a backend URL + login are provided.
- `backend/` — FastAPI + async SQLAlchemy 2.0 + asyncpg. Auth (JWT), samples,
  specifications, CoA, OOS, and an immutable audit trail. Seeded via
  `python -m app.seed`.
- `docker-compose.yml` — Postgres + backend + nginx, wired end-to-end.

## Run it

### Docker (everything, one command)

```bash
docker compose up --build
```

- App: <http://localhost:8080>
- API docs: <http://localhost:8000/docs>

The backend creates tables and seeds demo data (idempotent) on startup. nginx
serves the React build and proxies API calls to the backend (single origin).

**Demo login** (set the Backend API URL in Settings → it defaults to same-origin
under nginx, then use the header **Log in** button): `elena@purelyplant.eu` /
`Password123!` (other seeded users: `stefan@`, `jana@`, `sofija@`, `admin@`).

> Without logging in, the app still works fully on offline seed data — the QC Lab
> loads live records from the backend only once authenticated.

### Local dev (hot reload)

```bash
# backend
cd backend
pip install -r requirements.txt
python -m app.seed                       # against a local Postgres (see config.py)
uvicorn app.main:app --reload            # :8000

# frontend (separate terminal)
cd frontend
npm install
npm run dev                              # :5173, proxies /api → :8000
```

## EU GMP Annex 11 — where the controls live

A web UI is only the presentation layer; **GMP/Annex 11 technical controls are
enforced server-side**, in the FastAPI backend and PostgreSQL — never in the
browser, which is untrusted. This system implements the technical controls:

| Annex 11 clause | Control | Where |
| --- | --- | --- |
| §12 Security / access | Authentication + role-based access | `backend/app/api/auth.py`, `core/security.py` (JWT, bcrypt), `models/user.py` (`UserRole`) |
| §9 Audit trails | Immutable, attributable who/what/when, SHA-256 hash chain | `backend/app/api/audit.py`, `models/audit.py`, `core/audit.py`; surfaced in the **Audit Trail** view |
| §14 Electronic signatures | E-signature on CoA / release | CoA sign endpoint + QC Lab **Apply E-Signature** action |
| Data integrity (ALCOA+) | Persistent, server-validated records | PostgreSQL, `services/spec_validation_service.py` |
| §7 Data storage / retention | DB-backed, `data_retention_years` | `core/config.py`, Postgres volume |
| §5 Accuracy checks | Spec-limit validation of results | `services/spec_validation_service.py`, three-tier release/operational limits |

> **Validation disclaimer.** Software is necessary but **not sufficient** for GMP
> compliance. Annex 11 also requires Computerised System Validation (IQ/OQ/PQ),
> SOPs, change control, a qualified hosting environment, supplier assessment and
> periodic review. This repository provides a properly architected system **with
> the technical controls in place, ready to be validated** — it is not a
> certified product (no code is).

## Layout

```
backend/    FastAPI service (auth, samples, specs, CoA, OOS, audit) + seed
frontend/   React + Vite SPA (Production + QC Lab) + nginx + Dockerfile
docker-compose.yml
```

See [`frontend/README.md`](frontend/README.md) for the SPA structure and the
backend API contract it consumes.
