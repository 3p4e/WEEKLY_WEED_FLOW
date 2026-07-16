# Edge Case Review Report — QC LIMS P0 Diff

**Scope:** 1,574-line diff + existing FastAPI / async SQLAlchemy 2.0 patterns  
**Focus:** Runtime failures under unusual but valid conditions only (no style/docstring nits)  
**Date:** 2026-05-25  

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 7 |
| HIGH | 11 |
| MEDIUM | 14 |
| LOW | 8 |
| **Total** | **40** |

---

## CRITICAL

### C1 — Pydantic schemas declare `int` IDs while ORM uses `UUID`
- **File:** `backend/app/schemas/coa_track_models.py` (multiple lines: 1051, 1130, 1178, 1204, 1245, 1261, 1276)
- **Edge case:** Every read schema (`DocumentSchema`, `ParameterSchema`, `BatchSchema`, `CoQSchema`, etc.) declares `id: int`. The ORM `BaseModel` defines `id: Mapped[uuid.UUID]`.
- **What happens:** When FastAPI serializes any ORM instance through these schemas, Pydantic v2 raises `ValidationError` (UUID is not a valid int). All API read endpoints returning these schemas will return HTTP 500.

### C2 — `AuditMiddleware` passes URL path strings into `record_id` UUID column
- **File:** `backend/app/core/audit.py:99` → `backend/app/models/audit.py:81`
- **Edge case:** `core/audit.py` extracts `record_id = path_parts[1]` (e.g., `"123"`, `"PP-COA-2025-001"`). `models/audit.py` defines `record_id: Mapped[uuid.UUID]`.
- **What happens:** When pending entries are flushed to the database, `asyncpg` raises `DataError` because `"123"` is not a valid UUID format. The audit trail cannot be persisted.

### C3 — `AuditMiddleware` sets `user_id=None` for anonymous requests but model rejects NULL
- **File:** `backend/app/core/audit.py:95` → `backend/app/models/audit.py:58`
- **Edge case:** Unauthenticated mutating requests (or requests with expired Bearer tokens) produce `user_id=None`. `AuditEntry.user_id` is `nullable=False`.
- **What happens:** DB flush raises `IntegrityError` on every unauthenticated POST/PUT/PATCH/DELETE.

### C4 — Account takeover via email linking without re-authentication
- **File:** `backend/app/api/auth.py:115–123`
- **Edge case:** Attacker creates a Google account with the same email as an existing local user. The endpoint finds the user by email and overwrites `google_sub` without password re-authentication or admin approval.
- **What happens:** Attacker gains JWT access to the victim's account with full role permissions.

### C5 — Hard deletion of analytical results via cascade
- **File:** `backend/app/models/certificate.py:184`
- **Edge case:** `results = relationship(..., cascade="all, delete-orphan")` combined with FK `ondelete="CASCADE"`. If any service code calls `session.delete(coa)`, all linked `TestResult` rows are permanently removed from PostgreSQL.
- **What happens:** GMP violation — analytical results (GxP raw data) are destroyed instead of retained. ALCOA++ `Enduring` and `Complete` principles violated.

### C6 — ZipFile handle leak on malformed XLSX
- **File:** `backend/app/services/import_service.py:61`
- **Edge case:** `zipfile.ZipFile(path)` is not used as a context manager. If `z.read("xl/sharedStrings.xml")` raises `KeyError` (missing internal file, corrupt zip), the exception propagates before `z.close()` at line 113.
- **What happens:** File descriptor leak; repeated imports exhaust process file handles.

### C7 — Google OAuth access token accepted without audience verification
- **File:** `backend/app/api/auth.py:79–95`
- **Edge case:** The endpoint calls Google userinfo API but never verifies the `aud` claim of the token against `settings.google_client_id`. Any valid Google access token (from any OAuth client) is accepted.
- **What happens:** Authentication bypass — tokens issued to unrelated apps authenticate users in the LIMS.

---

## HIGH

### H1 — Race condition in username generation (TOCTOU)
- **File:** `backend/app/api/auth.py:129–138`
- **Edge case:** Two concurrent sign-up requests with the same base email both query for username availability, both see it as free, then both call `db.add(user)` with the same username.
- **What happens:** Second commit raises `IntegrityError` (500 response) instead of graceful retry.

### H2 — Race condition in QdrantService singleton initialization
- **File:** `backend/app/services/qdrant_service.py:1568–1572`
- **Edge case:** `get_qdrant_service()` checks `_singleton is None` and then assigns it. Two concurrent calls (e.g., from different request handlers) can interleave between check and assignment.
- **What happens:** Multiple `QdrantClient` instances are created; connection pool exhaustion or inconsistent state.

### H3 — httpx call to Google has no timeout
- **File:** `backend/app/api/auth.py:81`
- **Edge case:** If Google's network path is black-holed or severely degraded, `client.get()` waits indefinitely.
- **What happens:** Request handler coroutine hangs forever; Uvicorn worker slot is permanently lost.

### H4 — `_parse_thc` crashes on malformed numeric strings
- **File:** `backend/app/services/import_service.py:33–34`
- **Edge case:** Regex `([\d.]+)` matches `"1.2.3"` from a malformed cell; `float("1.2.3")` raises `ValueError`. There is no `try/except`.
- **What happens:** Import service crashes with unhandled exception on corrupt catalog data.

### H5 — Pending audit entries grow unbounded in memory
- **File:** `backend/app/core/audit.py:27`
- **Edge case:** `_pending_entries` is a global list. No `flush_pending()` caller exists in the codebase. Every mutating request appends entries indefinitely.
- **What happens:** Process memory grows until OOM kill; all audit data is lost on restart.

### H6 — WORM not enforced; audit entries inherit soft-delete and update timestamps
- **File:** `backend/app/models/audit.py:39`
- **Edge case:** `AuditEntry` inherits `BaseModel`, which provides `is_deleted` (`SoftDeleteMixin`) and `updated_at` with `onupdate=func.now()` (`TimestampMixin`).
- **What happens:** A buggy or malicious admin can soft-delete audit records or trigger an UPDATE that changes `updated_at`, violating EU GMP Annex 11 immutability requirements.

### H7 — No foreign key constraint on `AuditEntry.user_id`
- **File:** `backend/app/models/audit.py:58`
- **Edge case:** `user_id` is declared as `UUID(...)` but has no `ForeignKey("users.id")`.
- **What happens:** If a user is hard-deleted (or UUID typo occurs), audit entries reference non-existent users; referential integrity is not enforced by PostgreSQL.

### H8 — Shared string index out of bounds causes silent data corruption
- **File:** `backend/app/services/import_service.py:92`
- **Edge case:** `val = strings[idx] if idx < len(strings) else val` falls back to the raw numeric string if the shared string index is invalid.
- **What happens:** Corrupt XLSX files produce silently wrong string values (numeric IDs displayed as text) instead of raising an error. Data integrity compromised without detection.

### H9 — `resp.json()` crashes on non-JSON Google error responses
- **File:** `backend/app/api/auth.py:97`
- **Edge case:** If Google returns an HTML error page (e.g., during an outage), `resp.json()` raises `JSONDecodeError`.
- **What happens:** Unhandled exception returns 500 instead of the intended 401/502.

### H10 — `Base.metadata.create_all` races in multi-worker deployments
- **File:** `backend/app/main.py:28`
- **Edge case:** Multiple Uvicorn workers execute `create_all` simultaneously on startup.
- **What happens:** `DuplicateTable` or `DuplicateObject` exceptions on startup; pods crash-loop.

### H11 — `file_size` column overflows for files > 2 GB
- **File:** `backend/app/models/certificate.py:125–126`
- **Edge case:** `file_size: Mapped[int]` uses SQLAlchemy `Integer` (4-byte signed, max 2,147,483,647). Large PDFs or bulk uploads exceed this.
- **What happens:** PostgreSQL raises `integer out of range` on insert.

---

## MEDIUM

### M1 — `_parse_qty` rejects legitimate negative numbers
- **File:** `backend/app/services/import_service.py:40`
- **Edge case:** `raw.startswith("-")` treats any string beginning with `-` as missing, including `"-0.5"`.
- **What happens:** Legitimate negative quantities are silently stored as `None`.

### M2 — Missing internal XML files raise `KeyError`, not `ValueError`
- **File:** `backend/app/services/import_service.py:64,72`
- **Edge case:** Docstring promises `ValueError` on corrupt files, but missing `xl/sharedStrings.xml` or `xl/worksheets/sheet1.xml` raises `KeyError`.
- **What happens:** Caller expecting `ValueError` will not catch the exception.

### M3 — `parse_xlsx` accepts any ZIP file without format validation
- **File:** `backend/app/services/import_service.py:61`
- **Edge case:** A valid ZIP archive that is not an XLSX will fail on `z.read()` with `KeyError`.
- **What happens:** Poor error diagnostics; callers cannot distinguish corrupt XLSX from completely wrong file type.

### M4 — Qdrant `search()` and `get_collections()` raise unhandled connection errors
- **File:** `backend/app/services/qdrant_service.py:1526,1541`
- **Edge case:** `health_check()` catches exceptions, but `search()` and `get_collections()` do not.
- **What happens:** If Qdrant is unreachable, API endpoints calling these methods return 500 instead of graceful degradation.

### M5 — Timezone-aware datetime assigned to `Date` columns
- **File:** `backend/app/models/certificate.py:141,145`
- **Edge case:** `analysis_date` and `sampling_date` are `Date` columns. If application code passes `datetime.now(timezone.utc)`, asyncpg may raise or silently truncate depending on driver settings.
- **What happens:** `DataError` on insert/update if timezone-aware datetime is passed.

### M6 — Float columns accept NaN/Inf without validation
- **File:** `backend/app/models/certificate.py:153,213`
- **Edge case:** `extraction_confidence` and `confidence` are `Float` with no range constraints. NaN can be stored in PostgreSQL float columns.
- **What happens:** Compliance comparisons involving NaN always return `False`, causing incorrect pass/fail logic.

### M7 — `record_identifier` missing from middleware-generated audit dicts
- **File:** `backend/app/core/audit.py:92–110`
- **Edge case:** `AuditEntry.record_identifier` is `nullable=False`, but `_pending_entries` dicts produced by `AuditMiddleware` do not contain this key.
- **What happens:** Flush logic will raise `IntegrityError` because the required field is absent.

### M8 — Audit `old_value`/`new_value` encryption documented but not implemented
- **File:** `backend/app/models/audit.py:97,102`
- **Edge case:** Docstring states "encrypted at rest per Annex 11", but no encryption layer exists in code.
- **What happens:** If PostgreSQL data is exfiltrated, audit values are plaintext. Compliance gap, not immediate runtime failure.

### M9 — Empty `password_hash` for OAuth users may enable bypass in future local-auth code
- **File:** `backend/app/models/user.py:45` + `backend/app/api/auth.py:142`
- **Edge case:** `password_hash` is non-nullable. OAuth users get `""`. If a future local-login endpoint checks `if not user.password_hash:` as a shortcut, empty string evaluates to `False` and authentication is skipped.
- **What happens:** Potential future auth bypass depending on downstream code.

### M10 — `storage_path` length may exceed OS limits
- **File:** `backend/app/models/certificate.py:117`
- **Edge case:** `String(500)` allows 500-character paths. Windows `MAX_PATH` is 260 without `\\?\` prefix.
- **What happens:** File operations on stored paths fail at OS level despite DB acceptance.

### M11 — `page_count` accepts zero
- **File:** `backend/app/models/certificate.py:129`
- **Edge case:** `page_count` defaults to 1 but allows 0. A zero-page PDF is invalid.
- **What happens:** Downstream PDF generators or viewers may crash or misbehave.

### M12 — `reason` field for critical changes not enforced
- **File:** `backend/app/models/audit.py:107`
- **Edge case:** EU GMP Annex 11 §12.4 requires a reason for critical changes. The field is nullable with no code-level enforcement.
- **What happens:** Critical changes can be logged without reason, causing regulatory inspection findings.

### M13 — `get_collections()` in QdrantService also unhandled
- **File:** `backend/app/services/qdrant_service.py:1541–1552`
- **Edge case:** Same as M4 — no exception handling for network failures.

### M14 — Alembic autogenerate may miss models if `__init__.py` incomplete
- **File:** `backend/alembic/env.py:504`
- **Edge case:** `from app.models import *` depends on `models/__init__.py` exporting all models. If a model is not imported there, autogenerate silently omits it.
- **What happens:** Migrations are incomplete; tables missing in production.

---

## LOW

### L1 — `user_id` passed as string UUID into UUID column
- **File:** `backend/app/core/audit.py:95` → `backend/app/models/audit.py:58`
- **Edge case:** asyncpg typically auto-casts valid UUID strings, but this is driver-dependent and implicit. Relying on implicit casting is fragile.

### L2 — `session_id` is regenerated per HTTP request, not per user session
- **File:** `backend/app/core/audit.py:107`
- **Edge case:** Correlating actions within a logical browser session is impossible. Each request gets a new random UUID, making session-based forensic analysis difficult.

### L3 — `updated_at` on audit entries can mutate on accidental UPDATE
- **File:** `backend/app/models/base.py:37–43`
- **Edge case:** `TimestampMixin.onupdate=func.now()` fires if any UPDATE reaches the table, breaking immutability. Even a no-op UPDATE would modify the timestamp.

### L4 — CORS with wildcard origin + credentials is invalid if configured
- **File:** `backend/app/main.py:49–55`
- **Edge case:** If `settings.cors_origins` is changed to `["*"]` with `allow_credentials=True`, browsers reject credentialed requests per Fetch spec. Current default is explicit origins, but this is a latent foot-gun.

### L5 — `email_verified` claim not checked during Google OAuth
- **File:** `backend/app/api/auth.py:99`
- **Edge case:** Unverified Google emails are accepted. An attacker could create a Google account with a victim's unverified email and gain access before the victim verifies.

### L6 — `full_name` can be empty string
- **File:** `backend/app/api/auth.py:100` → `backend/app/models/user.py:49`
- **Edge case:** Google may return empty name; DB accepts it, breaking audit attribution (ALCOA++ `Attributable`).

### L7 — `create_access_token` does not validate non-positive expiry
- **File:** `backend/app/core/security.py:60–76`
- **Edge case:** If `settings.access_token_expire_minutes` is 0 or negative, token is immediately invalid. No guard prevents this misconfiguration.

### L8 — `TestResult.__repr__` may access detached `parameter` relationship
- **File:** `backend/app/models/certificate.py:296–299`
- **Edge case:** Guard exists (`if self.parameter else '?'`), but if relationship is expired in detached session, SQLAlchemy may still attempt lazy load and raise `DetachedInstanceError`.

---

## Cross-Cutting Patterns

### Pattern 1 — Schema/ORM type fracture: UUID vs int
Every Pydantic read schema in `coa_track_models.py` uses `int` IDs while the ORM uses `UUID`. This is a systematic breakage that will prevent any CoA_TRACK-ported endpoint from returning data. Root cause: porting legacy CoA_TRACK (which used integer IDs) without aligning to the new UUID-based `BaseModel`.

**Affected files:** `schemas/coa_track_models.py` (all read schemas)  
**Fix:** Change all `id: int` to `id: uuid.UUID` (or `str` if serialized).

### Pattern 2 — Audit trail is non-functional end-to-end
Three independent breaks form a complete failure:
- (a) middleware captures `record_id` as string path segments instead of UUIDs
- (b) `user_id` can be None for anonymous traffic, violating NOT NULL
- (c) `record_identifier` is never populated by middleware, violating NOT NULL
- (d) no service ever calls `flush_pending()` to persist entries

The audit module is effectively a memory leak that crashes on first flush attempt.

**Affected files:** `core/audit.py`, `models/audit.py`  
**Fix:** Align middleware output with model columns; add `flush_pending()` caller; or remove middleware and use SQLAlchemy event listeners.

### Pattern 3 — GMP hard-delete exposure via `cascade="all, delete-orphan"`
`CertificateOfAnalysis.results` and `Specification.parameters` both configure ORM+DB-level cascade deletion. In a GMP system, child records (TestResults, SpecParameters) must survive parent deletion. The current model allows permanent data destruction if any developer calls `session.delete()` instead of setting `is_deleted=True`.

**Affected files:** `models/certificate.py`, `models/specification.py`  
**Fix:** Remove `cascade="all, delete-orphan"` and `ondelete="CASCADE"`; implement soft-delete logic at service layer that cascades `is_deleted=True` instead.

### Pattern 4 — Resource leaks in stdlib parsers
Both `zipfile.ZipFile` (`import_service.py`) and the implicit `ET.fromstring` buffers lack deterministic cleanup on exception paths. In a production import pipeline processing hundreds of files, this leads to file-descriptor exhaustion.

**Affected files:** `services/import_service.py`  
**Fix:** Use `with zipfile.ZipFile(path) as z:` context manager.

### Pattern 5 — Race conditions in identity-sensitive operations
Username generation (`auth.py`) and singleton initialization (`qdrant_service.py`) both use check-then-act patterns without atomic guards. Under concurrent load (e.g., onboarding day with multiple analysts), these collide and raise `IntegrityError` or spawn duplicate connections.

**Affected files:** `api/auth.py`, `services/qdrant_service.py`  
**Fix:** Use `asyncio.Lock` for singleton init; use DB unique constraint + retry loop for username generation.

---

## Recommended Priority Order

1. **C1** (fix schema IDs to UUID) — blocks all read endpoints
2. **C4 + C7** (OAuth security) — authentication bypass
3. **C5** (remove hard-delete cascade) — GMP data integrity violation
4. **C2 + C3 + M7 + H5** (audit trail end-to-end fix) — compliance requirement
5. **C6 + Pattern 4** (resource leaks) — operational stability
6. **H1 + H2 + Pattern 5** (race conditions) — concurrency correctness
7. **H3 + H4 + H9** (exception handling) — reliability
8. **H6 + L3** (WORM enforcement) — regulatory compliance
9. **Remaining MEDIUM/LOW** — hardening
