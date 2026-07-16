# Purely Plant GmbH — QC LIMS Backend

## Overview
FastAPI backend for the EU GMP-compliant Quality Control Laboratory Information Management System (LIMS) for cannabis flower API manufacturing.

## Architecture
- **Three-layer**: Controller (routes) → Service (business logic) → Repository (database)
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy async + asyncpg
- **Migrations**: Alembic
- **Auth**: JWT with role-based access control
- **Audit Trail**: Middleware-based immutable logging (EU GMP Annex 11 / 21 CFR Part 11)
- **Data Integrity**: ALCOA++ — soft delete (is_deleted), UTC timestamps, hash-chain audit

## Setup

### 1. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
Copy `.env.example` to `.env` and fill in:
- `DATABASE_URL` (async PostgreSQL connection string)
- `SECRET_KEY` (random 256-bit key)
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS`

### 4. Run migrations
```bash
alembic upgrade head
```

### 5. Start server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation
Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Key Modules
| Module | Route Prefix |
|--------|-------------|
| Auth | `/auth` |
| Samples | `/samples` |
| Specifications | `/specifications` |
| Certificates of Analysis | `/coa` |
| OOS Investigations | `/oos` |
| Audit Trail | `/audit` |

## GMP Compliance Notes
- All GxP-relevant records use soft delete (`is_deleted` flag)
- Audit trail is immutable (no UPDATE/DELETE on audit table)
- Timestamps stored in UTC
- Electronic signatures required for approval actions
- 2nd person verification for analytical results
- Data retention: 10+ years
