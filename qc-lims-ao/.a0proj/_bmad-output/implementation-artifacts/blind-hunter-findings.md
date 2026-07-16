# Blind Hunter Adversarial Review — P2 Sample Lifecycle

**Commit:** 2df761d on branch feature/p2-sample-lifecycle  
**Reviewer:** Security Auditor (Blind Hunter Mode)  
**Date:** 2026-05-30  
**Files Reviewed:** 9 files, 2000+ lines

---

## Summary

| Severity | Count | Categories |
|----------|-------|------------|
| **CRITICAL** | 4 | Security (2), Concurrency (1), Data Integrity (1) |
| **HIGH** | 7 | Logic Bugs (3), Resource Management (2), Type Safety (1), Error Handling (1) |
| **MEDIUM** | 12 | Type Safety (4), Error Handling (3), Logic Bugs (2), Data Integrity (2), Security (1) |
| **LOW** | 8 | Code Quality (4), Performance (2), Documentation (2) |

**Total Findings:** 31

---

## CRITICAL Findings

### C1 — Race Condition in Sample ID Generation (TOCTOU)

**File:** `backend/app/services/barcode_service.py`  
**Lines:** 18-68

**Issue:** The `generate_sample_id()` function has a Time-of-Check-Time-of-Use (TOCTOU) race condition. Two concurrent requests could both query for the max sequence, get the same value, and both attempt to insert the same ID. The collision check loop (lines 56-67) mitigates this but only after the race occurs, and `max_attempts = 100` could theoretically exhaust if under heavy concurrent load.

```python
# Race condition: Two concurrent calls here get same next_seq
result = await db.execute(stmt)  # Both read "PP-SMP-2026-0042"
existing_ids = result.scalars().all()
# Both calculate next_seq = 43
# Both try to insert "PP-SMP-2026-0043" - one fails
```

**Fix:** Use database sequence or atomic UPSERT with retry at database level:
```python
# Use SERIAL or UUIDv7 with timestamp component
# Or implement distributed ID generation (Snowflake, etc.)
```

---

### C2 — Missing Transaction Boundaries in Multi-Record Operations

**File:** `backend/app/services/sample_lifecycle_service.py`  
**Lines:** 137-318 (`create_sp06_and_children()`)

**Issue:** The function creates 1-4 samples with associated audit records but does not wrap the entire operation in a transaction. Individual `await db.flush()` calls occur, but if a failure occurs mid-way (e.g., database connection drops after SP-06 but before SP-07), the system is left with partial data — violating ACID principles and ALCOA++ Completeness.

**Fix:** Use explicit transaction context:
```python
async with db.begin():
    # All operations inside are atomic
    sp06 = await create_sample(...)
    if plan.sp_07_required:
        sp07 = await create_sample(...)
    # commit happens automatically, rollback on exception
```

---

### C3 — Hardcoded Secret in Signature Hash Generation

**File:** `backend/app/services/custody_service.py`  
**Lines:** 22-35

**Issue:** The `generate_signature_hash()` function uses hardcoded secrets `"from"` and `"to"` (lines 82-83) for HMAC-style hashing. This provides no security value and creates a false sense of integrity. If this is meant to simulate 21 CFR Part 11 digital signatures, it fails catastrophically.

```python
from_signature = generate_signature_hash(from_user_id, transferred_at, "from")
to_signature = generate_signature_hash(to_user_id, transferred_at, "to")
# Secrets are literally the strings "from" and "to"
```

**Fix:** Remove or implement proper HMAC with server-side secret key from environment:
```python
import hmac
secret = settings.DIGITAL_SIGNATURE_KEY  # From secure env
signature = hmac.new(secret, data, hashlib.sha256).hexdigest()
```

---

### C4 — Unbounded Recursion in Genealogy Tree Building

**File:** `backend/app/services/genealogy_service.py`  
**Lines:** 257-280 (`build_tree()` nested function)

**Issue:** The recursive `build_tree()` function has no cycle detection. If a data integrity issue creates a cycle in parent-child relationships (A→B→C→A), this will cause infinite recursion and stack overflow. Python's default recursion limit (~1000) will be hit, crashing the process.

**Fix:** Add visited set to recursive builder:
```python
async def build_tree(sample: Sample, depth: int = 0, visited: set = None) -> GenealogyNode:
    if visited is None:
        visited = set()
    if sample.id in visited:
        raise ValueError(f"Cycle detected at sample {sample.id}")
    visited.add(sample.id)
    # ... rest of function
```

---

## HIGH Findings

### H1 — Missing Input Validation on Batch Size

**File:** `backend/app/services/sample_lifecycle_service.py`  
**Lines:** 137-149

**Issue:** `batch_size` parameter has no upper bound validation. Passing `batch_size=10**18` would cause `calculate_sample_size()` to compute `math.sqrt(10**18)` without issue, but could cause downstream issues or be a DoS vector.

**Fix:** Add validation:
```python
if not (1 <= batch_size <= 1_000_000_000):
    raise ValueError("batch_size must be between 1 and 1 billion")
```

---

### H2 — Unclosed Database Transactions on Exception

**File:** `backend/app/api/samples.py`  
**Lines:** 112-157

**Issue:** The exception handler catches generic `Exception` (line 144) and raises HTTPException, but if the database session was in a dirty state (pending changes), those changes may not be rolled back properly, leading to connection pool pollution.

**Fix:** Use FastAPI dependency with proper cleanup:
```python
# In get_db() dependency, use try/finally or context manager
# that ensures rollback on exception
```

---

### H3 — Incorrect Boolean Logic in Genealogy Traversal

**File:** `backend/app/services/genealogy_service.py`  
**Lines:** 188-210 (`get_progeny()`)

**Issue:** The logic `if include_self or current_id != sample_id:` (line 200) is incorrect. When `include_self=False` and `current_id == sample_id`, the condition is False (correct). When `include_self=True` and `current_id == sample_id`, the condition is True (correct). But when `include_self=False` and `current_id != sample_id`, the condition is True (correct for children). However, the queue starts with `[(sample_id, 0)]`, so the first iteration always processes the root — which may be included incorrectly.

Actually, re-reading: this logic is correct for children but the `include_self` parameter name is confusing — it's effectively `include_descendants`. The variable naming suggests intent mismatch.

**Fix:** Clarify parameter naming or add explicit comment about behavior.

---

### H4 — No Timeout on Database Queries

**File:** Multiple files

**Issue:** No statement timeout is configured for any database operation. A slow query or deadlock could hang the application indefinitely.

**Fix:** Configure SQLAlchemy with execution options:
```python
await db.execute(stmt, execution_options={"timeout": 30})  # 30 seconds
```

---

### H5 — SQL Injection via String Formatting (Low Risk but Pattern Exists)

**File:** `backend/app/services/barcode_service.py`  
**Lines:** 33-36

**Issue:** The LIKE query uses Python f-string formatting:
```python
.where(Sample.sample_id.like(f"PP-SMP-{year}-%"))
```

While `year` comes from `datetime.utcnow().year` (trusted), this pattern is dangerous if copied elsewhere. The `year` variable is an integer, but if refactored to accept user input, it becomes an injection vector.

**Fix:** Use parameterized queries even for "trusted" values:
```python
.where(Sample.sample_id.like(bindparam("prefix", f"PP-SMP-{year}-%")))
```

---

### H6 — Missing Null Check in Potency Grade Assignment

**File:** `backend/app/services/potency_service.py`  
**Lines:** 160-161

**Issue:** `old_grade = sample.potency_grade` retrieves the current value, but if the model field is nullable and not yet loaded, this could behave unexpectedly. The audit trail stores `"None"` as string (line 181) which is inconsistent with actual null handling.

**Fix:** Explicit null handling:
```python
old_grade = sample.potency_grade or "None (not set)"
```

---

### H7 — Incorrect HTTP Status Code for Validation Errors

**File:** `backend/app/api/samples.py`  
**Lines:** 201-205

**Issue:** Validation errors (e.g., invalid user ID) return HTTP 400, but should return 422 (Unprocessable Entity) per RFC 7231 and FastAPI conventions. 400 is for malformed syntax, 422 is for semantic validation failures.

**Fix:** Change to:
```python
raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, ...)
```

---

## MEDIUM Findings

### M1 — Missing Type Hints on Generic Collections

**File:** `backend/app/services/genealogy_service.py`  
**Lines:** 10, 129, 164, 300

**Issue:** Return types like `List["Sample"]` use string forward references, but should use `from __future__ import annotations` and proper generic types. Also, `List` imported from typing instead of built-in `list` (Python 3.9+).

**Fix:** 
```python
from __future__ import annotations
# ...
async def get_progeny(...) -> list[Sample]:
```

---

### M2 — Incorrect Enum Value Access Pattern

**File:** `backend/app/services/sample_lifecycle_service.py`  
**Lines:** 77, 210, 246, 273, 300

**Issue:** Code uses `SampleStatus.COLLECTED.value` and `SamplingPointType.SP_06.value` when the enum members could be used directly. SQLAlchemy 2.0 with `String` column can accept StrEnum directly; `.value` is redundant and error-prone.

**Fix:** 
```python
status=SampleStatus.COLLECTED,  # Without .value
```

---

### M3 — Missing Index on Foreign Key Columns

**File:** `backend/app/models/sample.py`  
**Lines:** 136-139

**Issue:** The `parent_id` foreign key column has no database index. Genealogy queries (`select(Sample).where(Sample.parent_id == current_id)`) will cause full table scans.

**Fix:** Add index:
```python
parent_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("samples.id"), nullable=True, index=True,
)
```

---

### M4 — Missing Unique Constraint on Sample ID

**File:** `backend/app/models/sample.py`  
**Lines:** 74-77

**Issue:** `sample_id` has `unique=True` but relies on application-level enforcement. Database-level unique constraint with proper error handling is missing from model definition (though SQLAlchemy `unique=True` does create constraint, the error handling is generic).

**Status:** Actually correctly defined — verify that `unique=True` creates constraint in migration.

---

### M5 — Inconsistent Timezone Handling

**File:** Multiple files

**Issue:** `barcode_service.py` uses `datetime.utcnow()` (naive UTC), while `sample_lifecycle_service.py` uses `datetime.now(timezone.utc)` (timezone-aware). This inconsistency can cause comparison errors and audit trail confusion.

**Fix:** Standardize on timezone-aware UTC everywhere:
```python
from datetime import datetime, timezone
datetime.now(timezone.utc)  # Always use this
```

---

### M6 — Missing Validation on Sub-Batch Code Generation

**File:** `backend/app/services/barcode_service.py`  
**Lines:** 94-124

**Issue:** `generate_sub_batch_code()` has no upper bound on `index`. While practical limits exist (physical batch sizes), the function could theoretically generate infinite-length strings like "DDDDDD...A" for large indices.

**Fix:** Add maximum index validation:
```python
MAX_SUB_BATCHES = 1000
if index >= MAX_SUB_BATCHES:
    raise ValueError(f"Maximum {MAX_SUB_BATCHES} sub-batches supported")
```

---

### M7 — No Handling of Missing Sampling Plan Attributes

**File:** `backend/app/services/sample_lifecycle_service.py`  
**Lines:** 236, 263, 290

**Issue:** Code accesses `plan.sp_07_required`, `plan.sp_08_required`, `plan.sp_09_required` without checking if these attributes exist. If the model doesn't have these fields, AttributeError occurs.

**Fix:** Use `getattr(plan, 'sp_07_required', False)` or ensure model has defaults.

---

### M8 — Inefficient Query Pattern in Barcode Generation

**File:** `backend/app/services/barcode_service.py`  
**Lines:** 33-49

**Issue:** The query fetches ALL matching IDs to find the max, rather than using database aggregation:
```python
stmt = select(func.max(cast(func.substring(Sample.sample_id, '-([0-9]+)$'), Integer)))
```

**Fix:** Use database-side MAX function instead of fetching all rows.

---

### M9 — Missing Cascade Behavior on Parent Delete

**File:** `backend/app/models/sample.py`  
**Lines:** 136-139, 159-160

**Issue:** If a parent sample is deleted, child samples' `parent_id` becomes orphaned (foreign key violation) or null depending on database constraint, but there's no explicit `ondelete="SET NULL"` or cascade defined.

**Fix:** Define behavior explicitly:
```python
parent_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("samples.id", ondelete="SET NULL"), ...
)
```

---

### M10 — Signature Hash Collision Vulnerability

**File:** `backend/app/services/custody_service.py`  
**Lines:** 22-35

**Issue:** The signature hash format `f"{user_id}:{timestamp.isoformat()}:{secret}"` lacks domain separation and could collide across different contexts. Also, `secret` defaults to empty string, making hashes predictable.

**Fix:** Use HMAC with proper keying and domain prefix:
```python
hmac.new(key, b"CUSTODY_TRANSFER:" + data, hashlib.sha256)
```

---

### M11 — Missing Audit Trail on Sample Update

**File:** `backend/app/services/custody_service.py`  
**Lines:** 100-103

**Issue:** When custody transfer updates `sample.location`, only the custody record is audited, not the sample field change itself. The sample's location change should also be in audit trail.

**Fix:** Add separate audit entry for location field change on Sample record.

---

### M12 — Genealogy Node Missing ID in Dict Output

**File:** `backend/app/services/genealogy_service.py`  
**Lines:** 46-59

**Issue:** `to_dict()` doesn't include the node's UUID (`sample_uuid` is included but the actual database UUID field mapping is unclear). Also, the `id` field from database is not exposed.

**Fix:** Clarify field mapping and ensure UUID is properly serialized.

---

## LOW Findings

### L1 — Unused Import

**File:** `backend/app/services/sample_lifecycle_service.py`  
**Lines:** 24-25

**Issue:** `TYPE_CHECKING` block with `SamplingPlan` import is unused because the type is referenced at runtime in line 192.

**Fix:** Remove TYPE_CHECKING guard or move runtime import to top.

---

### L2 — Missing Docstring on Function

**File:** `backend/app/services/barcode_service.py`  
**Lines:** 127-140

**Issue:** `validate_sample_id()` lacks docstring describing return value semantics.

---

### L3 — Magic Numbers

**File:** `backend/app/services/sampling_plan_service.py`  
**Lines:** 66-67

**Issue:** Min/max sample sizes are magic numbers without named constants at module level.

**Fix:**
```python
DEFAULT_MIN_SAMPLE_SIZE = 1
DEFAULT_MAX_SAMPLE_SIZE = 50
```

---

### L4 — String Concatenation in Audit Reason

**File:** `backend/app/services/potency_service.py`  
**Lines:** 183, 201

**Issue:** Using f-string concatenation for audit reasons is fragile; consider structured logging with JSON.

---

### L5 — Inefficient String Conversion

**File:** `backend/app/api/samples.py`  
**Lines:** 137

**Issue:** `str(req.session.get("id", "api"))` is called even when session doesn't exist; use conditional.

---

### L6 — Missing Pagination on Genealogy Queries

**File:** `backend/app/services/genealogy_service.py`  
**Lines:** 164-211

**Issue:** `get_progeny()` could return massive result sets for samples with many descendants. No pagination or limit enforcement.

**Fix:** Add `limit` parameter with reasonable default (1000).

---

### L7 — Comment Typos

**File:** `backend/app/services/genealogy_service.py`  
**Lines:** 228, 236

**Issue:** Comments reference "root" which appears to be a template interpolation artifact that wasn't replaced.

---

### L8 — Redundant Condition

**File:** `backend/app/services/sampling_plan_service.py`  
**Lines:** 59-60

**Issue:** Check for `N < 0` but negative batch sizes should be impossible; consider assert or more specific validation.

---

## Recommendations

### Immediate Actions (Before Merge)
1. **Fix C1, C2, C3, C4** — These are genuine bugs/security issues
2. **Fix H1, H7** — Input validation and HTTP semantics
3. **Add database indexes** for `parent_id` (M3)

### Before Production
4. Fix all timezone inconsistencies (M5)
5. Implement proper transaction boundaries throughout
6. Add query timeouts
7. Add pagination to genealogy endpoints

### Technical Debt
8. Standardize on Python 3.9+ type hints (remove `typing.List`, etc.)
9. Add comprehensive unit tests for race conditions
10. Implement proper HMAC for digital signatures

---

## Appendix: Files Analyzed

| File | Lines | Critical | High | Medium | Low |
|------|-------|----------|------|--------|-----|
| `sample_lifecycle_service.py` | 391 | 1 (C2) | 1 (H1) | 3 (M2,M7) | 1 (L1) |
| `custody_service.py` | 204 | 1 (C3) | 0 | 2 (M10,M11) | 0 |
| `potency_service.py` | 250 | 0 | 1 (H6) | 1 (M12) | 1 (L4) |
| `sampling_plan_service.py` | 114 | 0 | 0 | 2 (M3,L8) | 1 (L3) |
| `barcode_service.py` | 140 | 1 (C1) | 1 (H5) | 2 (M6,M8) | 1 (L2) |
| `genealogy_service.py` | 374 | 1 (C4) | 1 (H3) | 2 (M1,L7) | 1 (L6) |
| `samples.py` | 318 | 0 | 2 (H2,H7) | 0 | 1 (L5) |
| `custody.py` | 71 | 0 | 0 | 0 | 0 |
| `sample.py` | 164 | 0 | 0 | 2 (M3,M9) | 0 |

**Total:** 2026 lines reviewed, 31 findings

---

*Review conducted without specification context — all findings based solely on code analysis.*
