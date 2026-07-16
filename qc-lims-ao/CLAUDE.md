# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**QC_LIMS_Ao** ("GrowFlow Unified") is an EU GMP-compliant Laboratory Information Management System (LIMS) for Purely Plant GmbH, a licensed medical cannabis manufacturer in North Macedonia. It manages QC laboratory operations, regulatory compliance (Annex 11 / 21 CFR Part 11), OOS investigations, and production tracking. The UI is bilingual (English + Macedonian) throughout.

## Commands

### Full Stack (Docker)
```bash
docker compose up --build        # Start everything: Postgres + FastAPI + nginx (:8080)
docker compose down              # Stop all containers
```

### Backend (FastAPI)
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

alembic upgrade head             # Run database migrations
python -m app.seed               # Seed demo data (idempotent)
uvicorn app.main:app --reload    # Dev server on :8000
```

### Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev      # Dev server on :5173, proxies /api → :8000
npm run build    # Production build → dist/
npm run preview  # Serve production build locally
```

### Tests
```bash
cd backend
pytest tests/test_letta_service.py   # Only existing test file
```

### Deployment
```bash
bash deploy/kvm4.sh              # One-shot deploy to KVM4 VPS (72.60.35.12)
# Or trigger GitHub Actions workflow: .github/workflows/deploy-kvm4.yml
```

## Architecture

### System Topology
```
React SPA (:8080 via nginx)
    ↕ /api proxy
FastAPI (:8000, uvicorn, async)
    ↕ asyncpg
PostgreSQL 16 (:5432, Docker volume: pgdata)
    +
Letta (stateful AI agents) + Qdrant (vector DB) + VoyageAI (embeddings)
```

In production, all services run in Docker Compose. In dev, frontend Vite proxies `/api` to the backend, which must be running separately.

### Backend Layer Pattern
Every feature follows: **API Router → Service → SQLAlchemy Model**

- `backend/app/api/` — FastAPI routers (12 files), thin controllers that delegate to services
- `backend/app/services/` — Business logic (19+ files); this is where most complexity lives
- `backend/app/models/` — SQLAlchemy 2.0 ORM models (async, 14 files)
- `backend/app/schemas/` — Pydantic request/response models
- `backend/app/core/` — Cross-cutting: config, database engine, JWT/bcrypt security, audit middleware

### Key Backend Files
- `app/main.py` — FastAPI app entry, lifespan handler, all router registrations
- `app/core/config.py` — Pydantic `Settings` (reads from env vars): DB URL, JWT secret, Letta/Qdrant URLs, GMP parameters
- `app/core/database.py` — Async SQLAlchemy engine, session factory (`AsyncSession`)
- `app/core/audit.py` — `AuditMiddleware` + audit logging; writes to `AuditEntry` with hash-chain for 21 CFR Part 11
- `app/seed.py` — Idempotent demo data: users, samples, specs, COAs, OOS records

### Frontend Architecture
The SPA has two **modes** switched in `App.jsx`:
- **QC Lab mode** (`src/qc/`) — Primary workspace; 15+ screens routed through `QcModule.jsx`
- **Production board mode** (`src/production/`) — Weekly task tracking

Key frontend files:
- `src/App.jsx` — Shell, auth state, mode toggle
- `src/api/client.js` — Fetch client, JWT injection, all typed API methods
- `src/lib/i18n.js` — All EN/МК translation strings (add new strings here)
- `src/styles/app.css` — Design token system and all component styles; **do not duplicate styles inline**
- `src/qc/screens/` — Individual screens (dashboard, samples, specs, oos, coa, water, stability, etc.)

### GMP-Critical Design Decisions
1. **Immutable audit trail** — Every write goes through `AuditMiddleware`, which appends a hash-chained `AuditEntry`. Never bypass this middleware.
2. **Soft deletes only** — Records use `is_deleted` flag; never hard-delete GMP data (10-year retention requirement).
3. **Async throughout** — SQLAlchemy 2.0 async + asyncpg; always use `async def` and `await` in service/repository code.
4. **Roles**: `Analyst`, `Reviewer`, `Manager`, `QP` (Qualified Person), `Auditor`, `Admin` — enforce role checks at the API layer.
5. **UTC timestamps** — All `created_at`/`updated_at` fields must be UTC.

### Letta AI Integration (3-Tier Resilience)
- **Tier 1**: Full RAG via Qdrant (SOP semantic search) + Letta stateful agents
- **Tier 2**: Cached SOPs (fallback when Qdrant unreachable)
- **Tier 3**: Static validation only (fully offline fallback)

Letta is accessed via SSH tunnel to KVM4 in production. The service wrapper is `backend/app/services/letta_service.py`. Qdrant SOP ingestion lives in `spec_ingestion_service.py`.

### Database Notes
- Tables are currently created via `Base.metadata.create_all()` in the lifespan handler (not Alembic migrations). Alembic is configured but not yet the source of truth.
- Connection pool: `pool_size=20`, `max_overflow=10`
- `BaseModel` in `models/base.py` provides shared fields (`id`, `created_at`, `updated_at`, `is_deleted`)

## Configuration

All runtime config is in `backend/app/core/config.py` (Pydantic `Settings`). Notable settings:

| Setting | Default / Notes |
|---|---|
| `database_url` | Async PostgreSQL URL |
| `secret_key` | JWT signing key (generated once in deploy script) |
| `cors_origins` | `["http://localhost:5173"]` in dev |
| `data_retention_years` | `10` (GMP requirement) |
| `inactivity_timeout_minutes` | `15` (auto-logout) |
| `max_login_attempts` | `5` |
| `qdrant_url` | `localhost:6333` |
| `letta_base_url` | `localhost:8283` (or via SSH tunnel) |

## Key Documentation
- `QC_LIMS_Comprehensive_Vision_and_Architecture.md` — Full 688-line architecture reference including 8 ADRs
- `backend/README.md` — Backend setup, API endpoints, GMP compliance notes
- `frontend/README.md` — Frontend structure and full API contract table
