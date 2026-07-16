---
title: 'P3 Progressive Review — Cross-Module Integration & GMP Hardening'
type: 'feature'
created: '2026-05-31'
status: 'draft'
context:
  - 'spec-p0-foundation.md'
  - 'spec-p1-specification-linkage.md'
  - 'spec-p2-sample-lifecycle.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** P0 (Foundation), P1 (Specification Linkage), and P2 (Sample Lifecycle) were built sequentially. Cross-module integration has not been verified: API contracts between samples ↔ specifications may be inconsistent, audit trail logging is uneven across services, COA/OOS/Audit API routers exist as stubs with no endpoints, Alembic migrations have never been generated, and GMP compliance gaps (ALCOA++ completeness, transaction atomicity, unauthenticated endpoints) persist across the stack.

**Approach:** Progressive integration review — audit every module boundary, harden audit trail coverage on all state-changing operations, generate initial Alembic migration, populate stub routers with at least minimal CRUD endpoints, verify no unprotected endpoints exist, and ensure transaction atomicity for multi-entity operations (custody transfers, spec lifecycle transitions, potency updates).

## Boundaries & Constraints

**Always:**
- All existing tests must pass after changes (currently 0 tests — no regression guard)
- Never modify frozen intent from P0/P1/P2 specs
- Every state-changing endpoint MUST log an immutable AuditEntry
- All routers except /auth/* and /health MUST require authentication
- Alembic migration must use `--autogenerate` against the current model set
- Transaction boundaries must span all writes in a single HTTP request (no partial commits)
- Follow existing code patterns: service-layer audit logging, UUID PKs, async SQLAlchemy

**Ask First:**
- Adding new dependencies beyond what's already in requirements.txt
- Changing the frozen intent from any prior spec
- Deleting or renaming existing models/endpoints
- Any decision that would break the existing API contract

**Never:**
- Do not write unit tests (test suite does not exist yet — deferred to QA phase)
- Do not refactor model relationships (P0/P1/P2 models are frozen)
- Do not add new features beyond audit hardening and stub population
- Do not change authentication flow (Google OAuth is frozen from P0)
- Do not remove cascade protections that safeguard ALCOA++ data integrity

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Alembic autogenerate on empty DB | Fresh PostgreSQL, all models imported | Migration script created in alembic/versions/ with upgrade() creating all tables | Graceful error if DB unreachable; warn but don't block |
| Unauthenticated access to protected endpoint | No Authorization header, GET /samples | 401 Unauthorized JSON response | Return 401, audit log the attempt |
| Database connection failure during migration | PostgreSQL down, `alembic upgrade head` | Script exits with non-zero code and clear error message | Catch OperationalError, print connection details |
| Concurrent custody transfer on same sample | Two requests transfer same sample simultaneously | One succeeds, other gets 409 Conflict with "sample custody already transferred" | Use SELECT ... FOR UPDATE or optimistic locking via version column |
| Spec lifecycle transition with invalid role | QC_ANALYST tries to approve spec (requires QC_MANAGER) | 403 Forbidden with role requirement in detail | Audit log the denied attempt |

</frozen-after-approval>

## Code Map

- `backend/app/api/auth.py` — Google OAuth endpoint (frozen from P0, do not modify)
- `backend/app/api/samples.py` — 4 endpoints: create, transfer custody, get genealogy, update potency
- `backend/app/api/specifications.py` — 12 endpoints: CRUD + lifecycle (submit, approve, withdraw) + validation + A03 checklist
- `backend/app/api/coa.py` — STUB: router defined, 0 endpoints
- `backend/app/api/oos.py` — STUB: router defined, 0 endpoints
- `backend/app/api/audit.py` — STUB: router defined, 0 endpoints (needs GET /audit for read-only access)
- `backend/app/services/custody_service.py` — custody transfer with audit logging
- `backend/app/services/potency_service.py` — potency update with audit + OOS detection
- `backend/app/services/sample_lifecycle_service.py` — sample CRUD with audit logging
- `backend/app/services/spec_lifecycle_service.py` — spec lifecycle transitions with audit logging
- `backend/app/services/spec_validation_service.py` — dual-limit validation (operational vs release)
- `backend/app/core/audit.py` — AuditEntry model + create_audit_entry helper
- `backend/app/core/security.py` — get_current_user, require_role decorators
- `backend/app/main.py` — FastAPI app, router registration, /health endpoint
- `backend/alembic/` — Alembic config, env.py (async), empty versions/ folder

## Tasks & Acceptance

**Execution:**

### Task A: Alembic Migration Generation (P0+P1+P2 models)
- [ ] `backend/alembic/env.py` — VERIFY async engine configuration imports all models — prerequisite for autogenerate
- [ ] `backend/alembic/versions/` — GENERATE initial migration via `alembic revision --autogenerate -m "initial_p0_p1_p2"`
- [ ] `backend/alembic/versions/` — REVIEW generated migration for correctness (all tables, constraints, indexes)

### Task B: Stub Router Population (COA, OOS, Audit)
- [ ] `backend/app/api/audit.py` — ADD GET /audit endpoint (read-only, requires AUDITOR or ADMIN role) returning paginated AuditEntry list
- [ ] `backend/app/api/coa.py` — ADD GET /coa/{coa_id} endpoint (requires QC_ANALYST role, returns CertificateOfAnalysis with nested TestResults)
- [ ] `backend/app/api/oos.py` — ADD GET /oos endpoint (list OOS records, requires QC_ANALYST role)

### Task C: Auth Guard Audit & Hardening
- [ ] `backend/app/api/specifications.py` — AUDIT all 12 endpoints; ensure each has Depends(get_current_user). Identify and fix any unguarded endpoint.
- [ ] `backend/app/api/samples.py` — AUDIT all 4 endpoints; confirm universal auth guard.
- [ ] `backend/app/main.py` — CONFIRM /health endpoint is explicitly excluded from auth (if not, document it as intentional)
- [ ] `backend/app/api/__init__.py` — VERIFY router registration includes audit, coa, oos routers

### Task D: Audit Trail Completeness
- [ ] `backend/app/services/spec_lifecycle_service.py` — VERIFY every state transition (submit, approve, withdraw) creates AuditEntry with old_value/new_value for status field
- [ ] `backend/app/services/sample_lifecycle_service.py` — VERIFY every create/update operation creates AuditEntry covering all changed fields
- [ ] `backend/app/services/custody_service.py` — VERIFY custody transfer creates AuditEntry for sample.from_location → to_location transition
- [ ] `backend/app/services/potency_service.py` — VERIFY potency update creates AuditEntry for each cannabinoid result change
- [ ] `backend/app/core/audit.py` — ADD helper function `log_status_transition(db, record_type, record_id, old_status, new_status, user, reason=None)` for DRY audit logging

### Task E: Transaction Atomicity
- [ ] `backend/app/services/custody_service.py` — WRAP custody transfer + audit log in single transaction (remove separate db.commit)
- [ ] `backend/app/services/potency_service.py` — WRAP potency update + audit log + OOS check in single transaction
- [ ] `backend/app/services/sample_lifecycle_service.py` — WRAP sample create + cascade updates + audit log in single transaction
- [ ] `backend/app/services/spec_lifecycle_service.py` — VERIFY spec lifecycle transition + audit log are in single transaction

### Task F: Cross-Module API Contract Verification
- [ ] `backend/app/api/samples.py` — VERIFY sample creation references valid Specification ID; add validation that spec exists and is ACTIVE
- [ ] `backend/app/services/spec_validation_service.py` — VERIFY input schemas for batch validation match sample result schemas
- [ ] `backend/app/schemas/` — AUDIT schema consistency: ensure request/response schemas across samples, specs, coa share consistent field names for shared concepts (e.g., `spec_id`, `sample_id`, `batch_code`)

### Task G: Import Integrity & Final Verification
- [ ] Run `python -c "from app.main import app"` — must import without errors
- [ ] Run `python -c "from app.models import *; from app.schemas import *; from app.services import *; from app.api import *; from app.core import *"` — all modules import clean
- [ ] Run `python -c "import alembic; print(alembic.__version__)"` — confirm alembic is importable
- [ ] Run `cd backend && alembic check` — verify no schema drift (if DB available)

**Acceptance Criteria:**
- AC-01: Given an empty PostgreSQL database, when `alembic upgrade head` is executed, then all P0+P1+P2 tables are created with correct columns, constraints, and indexes.
- AC-02: Given an unauthenticated request to any non-auth/non-health endpoint, when the request is sent, then a 401 Unauthorized response is returned and an audit entry is logged.
- AC-03: Given a custody transfer of sample S1 from location A to location B, when the transfer succeeds, then exactly one AuditEntry exists recording the location change with old_value='A' and new_value='B'.
- AC-04: Given a spec lifecycle transition (submit/approve/withdraw), when the transition succeeds, then exactly one AuditEntry exists recording the status change with old and new status values.
- AC-05: Given a potency update that triggers an OOS condition, when the update is processed, then both a potency AuditEntry and an OOS AuditEntry are created within the same transaction.
- AC-06: Given the backend application starts, when `from app.main import app` is executed, then all modules import cleanly with zero ImportError or circular import exceptions.
- AC-07: Given GET /audit is called with AUDITOR role, when the request is processed, then a paginated list of AuditEntry records is returned with all 13 audit fields populated.
- AC-08: Given GET /coa/{coa_id} is called with QC_ANALYST role, when the COA exists, then the CertificateOfAnalysis is returned with nested TestResults and SpecParameter data.
- AC-09: Given GET /oos is called with QC_ANALYST role, when OOS records exist, then a list of OOSRecord summaries is returned with oos_number, detection_date, phase, and status.

## Spec Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Verification

**Commands:**
- `cd backend && alembic revision --autogenerate -m "initial_p0_p1_p2"` — expected: creates migration file without errors
- `cd backend && python -c "from app.main import app; print('OK')"` — expected: prints OK without ImportError
- `cd backend && python -c "from app.models import *; from app.schemas import *; from app.services import *; from app.api import *; from app.core import *; print('ALL CLEAN')"` — expected: prints ALL CLEAN

**Manual checks (if no CLI):**
- Inspect alembic/versions/ for new migration file with upgrade() creating all tables
- Inspect app/api/*.py for Depends(get_current_user) on every non-auth, non-health endpoint
- Inspect app/services/*.py for AuditEntry creation on every state-changing operation
