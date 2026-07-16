---
title: 'P4 OOS Integration — Out-of-Specification Investigation Workflow'
type: 'feature'
created: '2026-05-31'
status: 'draft'
context:
  - 'QCSOP 019 — OOS Investigation & Handling'
  - 'QCSOP 019-A01 — Internal OOx Investigation'
  - 'QCSOP 019-A02 — External Contractor OOx Investigation'
  - 'QCSOP 019-A03 — OOx Register'
  - 'QCSOP 019-A04 — OOx Notification Form'
  - 'QAT 010 — Risk Analysis'
---

## Intent

**Problem:** When a TestResult exceeds specification limits, there is no systematic workflow to investigate, classify risk, determine root cause, and disposition the batch per EU GMP QCSOP 019. The OOS module must handle Phase I (laboratory investigation), Phase II (full cross-functional investigation), CAPA tracking, QP approval gates, and regulatory notifications.

**Approach:** Build complete OOS workflow with:
1. Automatic OOS detection from TestResult
2. Phase I investigation (Analyst immediate review + 7-Step Assessment)
3. Risk classification (HIGH/MEDIUM/LOW) with timeline enforcement
4. Phase II escalation when Phase I inconclusive
5. OOS Register (A03) — immutable central log
6. Notification system (A04 Parts A-D)
7. QP approval gates for HIGH risk and batch disposition
8. CAPA integration with effectiveness verification
9. Root cause analysis with supporting evidence
10. Batch disposition workflow (Release/Reject/Reprocess)

**Regulatory Basis:**
- EU GMP Annex 1, 11, 15, 16
- QCSOP 019 (Phase I/II investigation)
- ICH Q10 (CAPA system)
- ALCOA++ data integrity

## Boundaries & Constraints

**Always:**
- Every OOS creates immutable AuditEntry with full chain of custody
- Phase I must complete within 3-5 days (risk-dependent)
- HIGH risk requires QP notification within 24 hours
- All batch disposition decisions require QP approval (non-delegable)
- OOS Register (A03) is append-only, no edits after closure
- Follow existing patterns: UUID PKs, async SQLAlchemy, service layer
- Bilingual MK/EN support for all user-facing fields

**Ask First:**
- Changes to existing TestResult model relationships
- New dependencies beyond current requirements.txt
- Modifications to frozen P0/P1/P2 code

**Never:**
- Skip QP approval for HIGH risk or batch disposition
- Allow OOS record deletion (ALCOA++ violation)
- Store signatures as plain text (use HMAC with SECRET_KEY)

## I/O & Edge-Case Matrix

| Scenario | Input | Expected Output | Error Handling |
|----------|-------|-----------------|----------------|
| TestResult exceeds spec | Result value > limit | OOS auto-created, notification sent, batch held | Log error if notification fails |
| Phase I identifies lab error | Analyst confirms calculation error | OOS closed with lab error cause, retest authorized | Require retest result before closure |
| Phase I inconclusive | No assignable cause found | Auto-escalate to Phase II, create cross-functional team | Notify QC Manager within 24h |
| HIGH risk OOS | CQA failure (potency, safety) | Immediate QP notification, batch hold, 20-day timeline | Escalate to Head of QA if QP unavailable |
| Duplicate OOS detection | Same sample retested OOS | Link to existing OOS, add retest result, do not create duplicate | Check sample_id + test_type uniqueness |
| Phase II timeout | 20/30/15 days exceeded | Auto-escalate to Head of QA, flag in dashboard | Allow formal deviation with QA approval |
| CAPA effectiveness check | 30-90 days post-implementation | QA verifies effectiveness, closes loop | If ineffective, reopen CAPA |

## Code Map

- `models/oos.py` — OOSInvestigation, OOSPhaseI, OOSPhaseII, OOSRegisterEntry, OOSNotification
- `services/oos_service.py` — create_oos_from_result, conduct_phase_i, escalate_to_phase_ii, disposition_batch
- `services/capa_service.py` — create_capa, verify_effectiveness (linked to OOS)
- `api/oos.py` — POST /oos/detect, GET /oos/{id}, POST /oos/{id}/phase-i, POST /oos/{id}/phase-ii, POST /oos/{id}/disposition
- `api/audit.py` — GET /audit/oos (OOS-specific audit trail)

## Tasks

### Task 1: Extend OOS Model (models/oos.py)
- OOSInvestigation: id, oos_number (PP-OOx-YYYY-NNN), test_result_id FK, batch_id, sample_id
- status (OPEN, PHASE_I, PHASE_II, CLOSED), risk_level (HIGH, MEDIUM, LOW)
- detection_date, closure_date, root_cause, disposition (RELEASE, REJECT, REPROCESS)
- created_by, qp_approved_by, qp_approved_at

### Task 2: Phase I Investigation Model
- OOSPhaseI: id, oos_id FK, phase_ia_analyst_review (JSON), phase_ib_7step (JSON)
- lab_error_identified (bool), error_description, retest_authorized (bool)
- completed_by, completed_at, conclusion (LAB_ERROR, INCONCLUSIVE)

### Task 3: Phase II Investigation Model
- OOSPhaseII: id, oos_id FK, cross_functional_team (JSON)
- manufacturing_review, cultivation_review, environmental_review
- root_cause_category, root_cause_description, capa_id FK
- completed_by, completed_at

### Task 4: OOS Register (A03) Service
- OOSRegisterEntry: id, oos_id, investigation_number, type, risk_level
- dates (opened, phase_i_closed, phase_ii_closed), root_cause, disposition
- Append-only, no updates after closure

### Task 5: Notification Service (A04)
- OOSNotification: id, oos_id, part (A, B, C, D), content (JSON)
- Part A: Initial notification (ALL events)
- Part B: Risk escalation (HIGH/MEDIUM)
- Part C: External lab request
- Part D: Regulatory assessment

### Task 6: OOS Detection Service
- Auto-detect from TestResult: if result > release_limit_max or < release_limit_min
- Create OOSInvestigation, send notification, hold batch
- Link to existing OOS if duplicate

### Task 7: Phase I Workflow Service
- conduct_phase_i(): 7-Step Assessment checklist
- If lab error: authorize retest, close OOS
- If inconclusive: escalate_to_phase_ii()

### Task 8: Phase II Workflow Service
- escalate_to_phase_ii(): Create cross-functional team, notify QC Manager
- Timeline enforcement: HIGH 20d, MEDIUM 30d, LOW 15d
- Root cause analysis with evidence

### Task 9: CAPA Integration
- create_capa_from_oos(): Link CAPA to OOSPhaseII
- verify_capa_effectiveness(): 30-90 day check
- Effectiveness verification by Head of QA

### Task 10: QP Approval Gates
- qp_approve_oos(): Final approval for HIGH risk
- qp_disposition_batch(): Release/Reject/Reprocess decision
- Non-delegable per QCSOP 019

### Task 11: API Endpoints
- POST /oos/detect — Manual trigger or auto from TestResult
- GET /oos/{id} — Full OOS with Phase I/II
- POST /oos/{id}/phase-i — Submit Phase I results
- POST /oos/{id}/phase-ii — Submit Phase II results
- POST /oos/{id}/disposition — QP batch disposition
- GET /oos/register — A03 register view

### Task 12: Timeline Enforcement
- Background job: Check OOS approaching deadline
- Auto-notify if 80% of timeline elapsed
- Escalate to Head of QA if deadline exceeded

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| AC-1 | OOS auto-detected from TestResult exceeding spec | Create TestResult > limit → OOS created |
| AC-2 | Phase I completes within 3 days (HIGH/MEDIUM) or 5 days (LOW) | Set deadline, verify enforcement |
| AC-3 | HIGH risk triggers QP notification within 24 hours | Create HIGH risk OOS → notification logged |
| AC-4 | OOS Register append-only, no edits after closure | Attempt update → rejection |
| AC-5 | QP approval required for batch disposition | Try disposition without QP → 403 Forbidden |
| AC-6 | CAPA linked to Phase II with effectiveness verification | Create Phase II → CAPA created → 30-day verification |
| AC-7 | A04 Parts A-D generated correctly | Verify all parts created per trigger rules |
| AC-8 | Duplicate OOS detection prevented | Same sample+test OOS twice → linked, not duplicate |
| AC-9 | Timeline enforcement with auto-escalation | Exceed deadline → escalated to Head of QA |

---
*spec-p4-oos-integration.md*
