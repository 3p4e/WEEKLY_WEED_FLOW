---
title: 'Phase P0 Foundation — CoA_TRACK Integration'
type: 'feature'
created: '2026-05-24'
status: 'complete'
baseline_commit: 'c7fd382dddbe0f8537d39246973032b695cc860e'
context: ['{project-root}/instructions/01-gmp-compliance.md', '{project-root}/instructions/03-lims-modules.md']
context: ['{project-root}/instructions/01-gmp-compliance.md', '{project-root}/instructions/03-lims-modules.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** CoA_TRACK has proven CoA management code (Document, Parameter, SpecParameter models, Google OAuth, XLSX catalog parser) but uses Integer PKs, sync SQLAlchemy, and pgvector — incompatible with QC_LIMS's UUID-based async architecture. No schema validation, no alembic migrations, no Qdrant integration.

**Approach:** Set up Foundation layer in 6 sequential tasks: Alembic for migrations, Pydantic v2 schemas for all CoA_TRACK models, ported models with UUID PKs and GMP-compliant fields, Qdrant client wrapper, Google OAuth endpoint, and the XLSX catalog parser. Zero behavior changes — pure infrastructure and schema porting.

## Boundaries & Constraints

**Always:**
- All models MUST inherit from BaseModel (UUID v4 PK, TimestampMixin, SoftDeleteMixin)
- All model fields MUST have doc strings (ALCOA++ traceability)
- Alembic migrations MUST use async SQLAlchemy 2.0 with asyncpg
- Pydantic v2 schemas MUST use `from_attributes = True` for ORM mode
- Ported code MUST NOT introduce sync patterns into the async codebase
- Never modify CoA_TRACK source — copy-and-adapt only

**Ask First:**
- Any field rename that changes existing CoA_TRACK semantics
- Adding new dependencies beyond requirements.txt (currently has alembic, pydantic)
- Changing the BaseModel pattern (it's locked in)

**Never:**
- Do NOT implement business logic beyond schema porting — no extraction pipeline, no AI calls, no workflow state machines
- Do NOT create frontend components
- Do NOT run migrations against a live database unless user provides DB
- Do NOT install packages beyond requirements.txt without asking

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Alembic init succeeds, autogenerate detects all models | `alembic revision --autogenerate -m "initial"` | Migration file in alembic/versions/ with all tables: users, samples, specifications, spec_parameters, certificates_of_analysis, test_results, oos_records, audit_entries | If alembic not installed: halt, suggest pip install alembic |
| Alembic env.py uses async engine | `alembic/script.py.mako` not exists | `alembic init alembic` creates tree, env.py rewritten for async SQLAlchemy | Existing alembic/ dir: HALT and ask before overwriting |
| Pydantic v2 schemas validate all CoA_TRACK model fields | SchemaBase for each model (DocumentSchema, ParameterSchema, etc.) | All fields match their ORM types; Optional for nullable; enums as Literal | Runtime error if model-schema mismatch: test catches |
| Qdrant health check with no tunnel | `GET /collections` to localhost:6333 | Return `{"status": "connected", "collections": [...]}` or `{"status": "unreachable", "error": "..."}` | HTTP error → graceful unreachable response, never crash |
| Google OAuth with valid token | POST /auth/google {credential: "valid_google_access_token"} | 200 + LoginResponse (access_token + user) — find existing user by google_sub or email, or create new User with google_sub | Google API down → 502; invalid token → 401; missing GOOGLE_CLIENT_ID → 501 |
| Google OAuth with new user | First-time login via Google | User created with google_sub set, assigned QC_ANALYST role by default, is_active=True | Duplicate email conflict → link to existing user by email |
| catalog_service parse_xlsx with valid XLSX | Path to "List of COAs.xlsx" | Returns list of dicts with strain_name, batch_code, customer, quantity_kg, thc_percent, production_batch, coa_status | Corrupt XLSX → ValueError with details; missing file → FileNotFoundError |

</frozen-after-approval>

## Code Map

- `backend/app/models/base.py` — BaseModel (UUID PK, TimestampMixin, SoftDeleteMixin) — all new models inherit from this
- `backend/app/models/user.py` — User model (add google_sub and avatar_url fields)
- `backend/app/models/audit.py` — AuditEntry model MUST BE CREATED (referenced in models/__init__.py but file missing)
- `backend/app/core/config.py` — Settings (add GOOGLE_CLIENT_ID, QDRANT_URL env vars)
- `backend/app/core/database.py` — Async engine (alembic env.py targets this)
- `backend/requirements.txt` — Already has alembic, pydantic — add httpx (Google OAuth), qdrant-client
- `/tmp/CoA_TRACK/app/models.py` L96-178 — Document model (port to CertificateOfAnalysis extension)
- `/tmp/CoA_TRACK/app/models.py` L181-222 — Parameter model (port to TestResult extension)
- `/tmp/CoA_TRACK/app/models.py` L437-459 — SpecParameter model (port to SpecParameter extension)
- `/tmp/CoA_TRACK/app/routers/auth.py` L335-400 — Google OAuth endpoint (port)
- `/tmp/CoA_TRACK/app/services/catalog_service.py` — XLSX parser (direct copy)
- `backend/app/__init__.py` — Empty, ensure exists

## Tasks & Acceptance

**Execution:**
- [ ] `backend/requirements.txt` — add httpx, voyageai, qdrant-client deps — needed for tasks 4, 5
- [ ] `backend/app/models/audit.py` — create AuditEntry model with BaseModel UUID PK, timestamp, user_id, action enum, record_type, record_id, field_name, old_value, new_value, reason, ip_address, session_id, digital_signature_hash — missing file referenced by models/__init__.py, unblocks alembic autogenerate
- [ ] `backend/app/models/user.py` — add google_sub column (String, nullable, unique, index) and avatar_url column (String, nullable) — required for Google OAuth
- [ ] `backend/alembic/` — run `alembic init alembic`, rewrite env.py for async SQLAlchemy using settings.database_url and Base metadata from app.models, generate initial migration — establishes migration baseline for all 6 existing models
- [ ] `backend/app/schemas/__init__.py` — create empty init — directory structure
- [ ] `backend/app/schemas/coa_track_models.py` — create Pydantic v2 schemas: DocumentSchema, DocumentCreate, DocumentUpdate, ParameterSchema, ParameterCreate, SpecParameterSchema, ProductSpecSchema, WaterReportSchema, BatchSchema, BatchCreate, CoQSchema, CoQCreate — all from_attributes=True, enums typed as Python Enum or Literal
- [ ] `backend/app/models/certificate.py` — extend CertificateOfAnalysis with 10-state eCoA workflow fields: cert_type enum (ICOA|ECOA|COQ|WATER|OTHER), source_lab, filename, storage_path, file_hash, file_size, page_count, language, sampling_point, analysis_date, sampling_date, sampling_location, extraction_confidence, ocr_required, ocr_completed, processing_stage, processing_error, analyst_name (denormalized) — per QCSOP 012 port from Document
- [ ] `backend/app/models/certificate.py` — extend TestResult with dual result_value/result_numeric fields, name_local, category enum, min_limit/max_limit/limit_numeric_min/limit_numeric_max, method_reference, standard_ref, status enum (pass|fail|marginal|unknown), confidence, verified_by FK to User — per QCSOP 012 port from Parameter
- [ ] `backend/app/models/specification.py` — extend SpecParameter with pharmacopoeia_ref (already present — verify), test_location enum (IN_HOUSE|EXTERNAL), compendial boolean, operational_limit_min/max + release_limit_min/max dual limits — per QCSOP 010 port from SpecParameter
- [ ] `backend/app/services/__init__.py` — create empty init
- [ ] `backend/app/services/qdrant_service.py` — create QdrantService class with __init__(url, api_key optional), health_check() → dict, search(collection, query_vector, limit, filter) → list[dict], get_collections() → list[str] — client wrapper, no embedding (that's Task 6 of next phase)
- [ ] `backend/app/services/import_service.py` — copy /tmp/CoA_TRACK/app/services/catalog_service.py, replace import paths (from models → from app.models), convert sync parse_xlsx to keep stdlib only — XLSX parser port
- [ ] `backend/app/api/__init__.py` — create empty init
- [ ] `backend/app/api/auth.py` — create Google OAuth POST /auth/google endpoint: verify Google access token via Google userinfo API using httpx, find/create User with google_sub, return LoginResponse with JWT — ported from /tmp/CoA_TRACK/app/routers/auth.py L335-400
- [ ] `backend/app/main.py` — register auth_router from app.api.auth, add /health endpoint — wiring
- [ ] `backend/app/core/config.py` — add GOOGLE_CLIENT_ID: str, QDRANT_URL: str = "http://localhost:6333" fields to Settings

**Acceptance Criteria:**
- AC-01: Given backend/ directory with all models, when `alembic upgrade head` runs, then all tables (users, samples, specifications, spec_parameters, certificates_of_analysis, test_results, oos_records, audit_entries) exist in PostgreSQL with correct column types
- AC-02: Given Pydantic v2 schemas, when a valid JSON payload is validated for each schema, then all fields are accepted (including Optional fields) and unknown fields are rejected by model_config extra=forbid
- AC-03: Given CertificateOfAnalysis model, then it has all fields from both existing COA model PLUS the new eCoA fields (cert_type, source_lab, filename, etc.) with correct column types
- AC-04: Given TestResult model, then it has dual result_value (String) and result_numeric (Float nullable) fields plus complies boolean, verified_by FK, and category enum
- AC-05: Given SpecParameter model, then it has operational_limit_min/max + release_limit_min/max fields, test_location enum, compendial boolean, and pharmacopoeia_ref
- AC-06: Given QdrantService, when health_check() is called and Qdrant is reachable, then returns {"status": "connected". When unreachable, returns {"status": "unreachable", "error": "..."} — never raises unhandled exception
- AC-07: Given POST /auth/google with a valid Google access token, when user exists by google_sub or email, then returns 200 with JWT and user profile. When user is new, then creates User with google_sub and returns 200.
- AC-08: Given import_service.py, when parse_xlsx() is called with a valid XLSX path, then returns list of dicts. When file is missing, then raises FileNotFoundError. When XLSX is corrupt, then raises ValueError.

## Spec Change Log

## Verification

**Commands:**
- `cd backend && alembic upgrade head` — expected: no errors, tables created
- `cd backend && python -c "from app.schemas.coa_track_models import DocumentSchema, ParameterSchema; print('Schemas import OK')"` — expected: no import errors
- `cd backend && python -c "from app.services.qdrant_service import QdrantService; print('QdrantService imports OK')"` — expected: no import errors
- `cd backend && python -c "from app.services.import_service import parse_xlsx; print('import_service imports OK')"` — expected: no import errors

**Manual checks (if no CLI):**
- Verify alembic/versions/ directory contains at least one migration file after autogenerate
- Verify backend/app/models/audit.py exists with AuditEntry class
- Verify backend/app/models/user.py has google_sub and avatar_url columns
