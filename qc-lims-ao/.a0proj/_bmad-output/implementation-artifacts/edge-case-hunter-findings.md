# Edge Case Hunter Review — P2 Sample Lifecycle

**Commit:** 2df761d on branch feature/p2-sample-lifecycle  
**Reviewer:** Test Engineer (Edge Case Hunter Mode)  
**Date:** 2026-05-30  
**Files Reviewed:** 9 files, ~2000 lines  
**Focus:** Boundary conditions, failure modes, edge cases, extreme values

---

## Summary

| Severity | Count | Categories |
|----------|-------|------------|
| **CRITICAL** | 3 | Data Integrity (1), Concurrency (1), Logic Errors (1) |
| **HIGH** | 5 | Type Safety (2), Error Handling (2), Data Integrity (1) |
| **MEDIUM** | 8 | Edge Cases (3), Validation (3), Timezone (2) |
| **LOW** | 4 | Code Quality (2), Documentation (2) |

**Total Findings:** 20

**Note:** This review is orthogonal to Blind Hunter adversarial review. Blind Hunter found 31 issues (4 critical, 7 high, 12 medium, 8 low) covering security, concurrency, and logic bugs. This review focuses specifically on boundary conditions, extreme values, and edge cases that may not have been fully exercised.

---

## CRITICAL Findings

### C1 — Division by Zero When Target THC = 0

**File:** `backend/app/services/potency_service.py`  
**Lines:** 78-86 (`assign_grade()`)

**Issue:** When `target=0` is passed to `assign_grade()`, the tolerance bounds calculation produces:
- `lower_bound = 0 * (1 - 0.10) = 0`
- `upper_bound = 0 * (1 + 0.10) = 0`

This causes ALL total_thc values to be classified as Grade A (Premium), which is semantically incorrect. A target of 0% THC would mean "no THC allowed" — all detected THC should be OOS.

**Edge Case:**
```python
# target_thc = 0 with any detected THC
assign_grade(0.5, 0, 0.10)  # Returns "A" (Premium) — WRONG!
# Should be "C" (Extracts) or rejected as invalid target
```

**Impact:** Could allow THC-containing product to be graded as Premium when it should be rejected or sent to extracts.

**Fix:** Add guard clause:
```python
if target <= 0:
    raise ValueError("Target THC must be positive (> 0)")
```

---

### C2 — Race Condition in Concurrent Custody Transfers

**File:** `backend/app/services/custody_service.py`  
**Lines:** 154-179 (`get_current_custodian()`)

**Issue:** Two concurrent custody transfers for the same sample could both query `get_current_custodian()`, get the same current custodian, and both create custody records claiming that custodian released the sample. The database has no unique constraint preventing duplicate `from_user_id` entries for the same sample.

**Edge Case:**
```
T0: User A has custody of Sample X
T1: User B requests transfer from A (reads A as current custodian)
T2: User C requests transfer from A (also reads A as current custodian)
T3: Both transfers succeed — Sample X now has two custody chains
```

**Impact:** Violates ALCOA++ Completeness principle. Chain of custody becomes ambiguous — who actually has the sample?

**Fix:** Add database-level constraint:
```sql
-- Ensure only one uncompleted custody chain per sample
CREATE UNIQUE INDEX idx_unique_current_custody 
ON chain_of_custody (sample_id) 
WHERE is_completed = false;
```

---

### C3 — Orphaned SP-07/08/09 Samples Can Be Created Without Valid Parent

**File:** `backend/app/services/sample_lifecycle_service.py`  
**Lines:** 68-91 (`create_sample()`)

**Issue:** The `create_sample()` function accepts a `parent_id` parameter but does NOT validate that:
1. The parent sample exists
2. The parent is an SP-06 (valid parent type)
3. The parent has not been deleted

This allows direct API calls to create orphaned SP-07 samples without going through the SP-06 cascade.

**Edge Case:**
```python
# Direct creation of SP-07 with fake parent_id
await create_sample(
    db=db,
    sample_id="PP-SMP-2026-9999",
    sp_type="SP_07",  # Child type
    parent_id=uuid.uuid4(),  # Non-existent parent
    # ... other params
)
# Creates orphaned sample violating genealogy integrity
```

**Impact:** Breaks product genealogy tracking. Orphaned samples cannot be traced to their batch of origin, violating QCSOP 011-A01 and EU GMP traceability requirements.

**Fix:** Add parent validation:
```python
if parent_id:
    parent = await db.get(Sample, parent_id)
    if parent is None:
        raise ValueError(f"Parent sample {parent_id} not found")
    if parent.sp_type != SamplingPointType.SP_06.value:
        raise ValueError(f"Invalid parent type: {parent.sp_type}. Only SP-06 can be parent.")
```

---

## HIGH Findings

### H1 — Negative Values Not Rejected for THC/THCA Measurements

**File:** `backend/app/api/samples.py`  
**Lines:** 77-79 (`PotencyGradeRequest`)

**Issue:** Pydantic schema uses `ge=0` (greater than or equal to 0) which allows zero values. However, the API should reject zero values for THC/THCA in real potency testing — you cannot have 0% THC and still have a valid measurement.

More critically, the schema allows values like:
- `thc=-0.001` (technically >= 0 if rounded, but negative before rounding)
- `thca=0` with `thc=0` (division by zero scenario when calculating grade)

**Edge Case:**
```json
{
  "thc": 0,
  "thca": 0,
  "target_thc": 0
}
# Passes validation but causes division by zero in grade calculation
```

**Impact:** Silent data corruption. Zero or near-zero values skew potency calculations and may cause unexpected grade assignments.

**Fix:** Use `gt=0` (greater than 0) for THC/THCA, and add minimum threshold validation:
```python
thc: float = Field(..., gt=0, le=100, description="Measured THC content (% w/w)")
```

---

### H2 — No Validation of Batch ID Format Allows Invalid Characters

**File:** `backend/app/api/samples.py`  
**Lines:** 33-37 (`SP06ReceiveRequest`)

**Issue:** The `batch_id` field accepts any string with no format validation. This allows:
- Empty string `