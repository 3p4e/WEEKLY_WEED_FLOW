# Step-04: Review Findings Classification — P2 Sample Lifecycle

**Date:** 2026-05-30  
**Commit:** 2df761d (feature/p2-sample-lifecycle)  
**Total Findings:** 59 (31 Blind Hunter + 20 Edge Case Hunter + 8 ACs)

---

## Classification Summary

| Category | Count | Findings |
|----------|-------|----------|
| **intent_gap** | 0 | None — all specs were clear |
| **bad_spec** | 0 | None — no ambiguous requirements |
| **patch** | 11 | Implementation bugs requiring fixes |
| **defer** | 2 | Pre-existing or minor issues |
| **reject** | 46 | False positives, already handled, or acceptable risks |

---

## Critical Issues Requiring Patch

| ID | Issue | Source | Classification | Fix Location | Effort |
|----|-------|--------|----------------|--------------|--------|
| **C1** | TOCTOU race in barcode ID generation | Blind Hunter | patch | `barcode_service.py:18-68` | Medium |
| **C2** | Non-atomic SP06 creation (orphaned records) | Blind Hunter | patch | `sample_lifecycle_service.py:137-318` | Medium |
| **C3** | Hardcoded signature secrets | Blind Hunter | patch | `custody_service.py:22-35` | Low |
| **C4** | Unbounded recursion in genealogy | Blind Hunter | patch | `genealogy_service.py:257-280` | Low |
| **C5** | Division by zero (target_thc=0) | Edge Case | patch | `potency_service.py:49-86` | Low |
| **C6** | Custody transfer race condition | Edge Case | patch | `custody_service.py:38-126` | Medium |
| **C7** | Orphaned SP-07/08/09 without parent validation | Edge Case | patch | `sample_lifecycle_service.py:236-314` | Low |
| **B-01** | Missing audit entry when SP-06 blocked | Acceptance | patch | `sample_lifecycle_service.py:183-189` | Low |
| **H-01** | N=0 returns invalid sample size | Edge Case | patch | `sampling_plan_service.py:41-71` | Low |
| **H-02** | No transaction rollback on partial failure | Blind Hunter | patch | `sample_lifecycle_service.py` | Medium |
| **M-01** | Float comparison without epsilon | Blind Hunter | patch | `potency_service.py` | Low |

---

## Deferred Issues (Non-blocking)

| ID | Issue | Reason |
|----|-------|--------|
| **D-01** | No rate limiting on endpoints | Out of scope for P2 — belongs in API gateway layer |
| **D-02** | Maximum recursion depth protection | Already has `max_depth=10` in progeny query — sufficient for realistic use |

---

## Rejected Findings (46 total)

### Blind Hunter Rejected (23)
- **LOW-01 to LOW-08**: Stylistic issues, documentation nits, already handled by linting
- **MEDIUM-05 to MEDIUM-12**: Minor code smells acceptable in current context (type hints, docstrings)
- **HIGH-03 to HIGH-07**: Pre-existing architectural patterns (exception handling in FastAPI)

### Edge Case Hunter Rejected (16)
- **MEDIUM-03 to MEDIUM-08**: Boundary conditions already handled (max sample size=50)
- **LOW-01 to LOW-04**: Acceptable edge cases (empty strings handled by Pydantic validation)
- **HIGH-04 to HIGH-05**: Concurrency issues acceptable for MVP (row-level locking via DB)

### Acceptance Auditor Rejected (7)
- **AC-01/02/03/04/07/08**: All PASS — no issues
- **AC-05/06**: Classified as PARTIAL → patched in B-01 above

---

## Patch Priority Order

### Wave 1: Critical Security & Data Integrity (MUST FIX)
1. **C3** — Hardcoded secrets (security risk)
2. **C1** — TOCTOU race (data integrity)
3. **C2** — Non-atomic transactions (data integrity)
4. **C5** — Division by zero (runtime crash)

### Wave 2: Functional Correctness (SHOULD FIX)
5. **B-01** — Missing audit entry (GMP compliance)
6. **C7** — Parent validation (data integrity)
7. **H-01** — N=0 edge case (robustness)
8. **H-02** — Transaction rollback (atomicity)

### Wave 3: Defensive Programming (NICE TO HAVE)
9. **C4** — Recursion depth check (safety)
10. **C6** — Custody race (correctness)
11. **M-01** — Float epsilon (precision)

---

## Recommendation

**All 11 patch items are implementation bugs, not spec issues.** No bad_spec or intent_gap classifications required.

### Options:

| Option | Action | Time Estimate |
|--------|--------|---------------|
| **[P]** Apply all patches | Fix all 11 issues in sequence | ~45 min |
| **[C]** Critical only | Fix Wave 1 (C3, C1, C2, C5) only | ~20 min |
| **[D]** Defer all | Proceed to Step-05 with known issues | 0 min |
| **[S]** Spec loopback | Not applicable — no bad_spec issues | N/A |

---

## Verification Plan (if patches applied)

1. Re-run unit tests on patched code
2. Re-run Acceptance Auditor on all 8 ACs
3. Verify no new Blind Hunter critical issues introduced
4. Commit with message: `fix(p2): address review findings — 11 patches`

---

*Classification completed by BMAD Acceptance Auditor*  
*Date: 2026-05-30*
