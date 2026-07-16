---
title: 'Phase P1 — Specification Linkage & Lifecycle'
type: 'feature'
created: '2026-05-29'
status: 'complete'
baseline_commit: '21e0112'
context: ['{project-root}/instructions/01-gmp-compliance.md', '{project-root}/instructions/03-lims-modules.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The LIMS has SpecParameter model with dual limits (operational/release) but no verification pipeline, no spec lifecycle state machine, no numbering system, and no change control. Specifications are data without enforcement. Two real approved specs (QCSP-FP-001 v.01, QCSP-IMB-001 v.01 — 19 parameters each with cannabinoid grade tables) exist but are not ingested.

**Approach:** Build the Specification engine: ingestion of approved specs, auto-numbering per QCSOP 010 §6.6, 7-step lifecycle state machine, spec-driven validation of TestResults against dual limits, auto-generated Annex A03 checklist for COA review, and change control requests linked to CAPA.

## Boundaries & Constraints

**Always:**
- Extend existing `Specification`/`SpecParameter` models — do NOT replace
- All new models inherit from `BaseModel` (UUID v4 PK, TimestampMixin, SoftDeleteMixin)
- Pydantic v2 schemas: `from_attributes=True, extra="forbid"`
- Three-layer: router → service → model (no model writes in router)
- EU GMP Annex 11 audit trail: every state transition logged to AuditEntry
- Bilingual MK/EN: all user-facing test names and status labels support both languages
- Use existing `SpecStatus` enum (DRAFT/ACTIVE/SUPERSEDED/WITHDRAWN) — extend, don't replace
- Numbering format: `QCSP-[TYPE]-[NNN]-v[VV]` per QCSOP 010 §6.6

**Ask First:**
- Any database migration (Alembic revision) — ask before running
- Seeding approved specs into production DB — ask before upserting
- Changing existing field types or constraints on Specification/SpecParameter

**Never:**
- Do NOT create frontend components
- Do NOT implement COA workflow state machine (P3 scope)
- Do NOT hard-delete specification versions (ALCOA++ Enduring)
- Do NOT bypass the second-person verification gate for results

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Validation pass | TestResult (loss_on_drying=8.5, unit="% w/w") + active SpecParameter (op_limit_max=10, rel_limit_max=12) | `{"complies": true, "status": "pass", "limit_type": "within_operational"}` | N/A |
| Operational alert | TestResult (loss_on_drying=11.2) + SpecParameter (op_max=10, rel_max=12) | `{"complies": true, "status": "alert", "limit_type": "operational_breach", "alert_message": "..."}` | N/A |
| Release fail | TestResult (loss_on_drying=13.0) + SpecParameter (rel_max=12) | `{"complies": false, "status": "fail", "limit_type": "release_breach"}` | N/A |
| No active spec | TestResult with batch material_code, no ACTIVE Specification for that code | `{"complies": null, "status": "error", "message": "No active specification for material_code XYZ"}` | 422 with detail |
| Spec not yet effective | Spec with effective_date tomorrow, TestResult today | `{"complies": null, "status": "error", "message": "Spec not yet effective"}` | 422 |
| State transition denied | Spec in ACTIVE → directly to DRAFT | 409 Conflict: "Cannot demote from ACTIVE to DRAFT" | State machine validator raises ValueError → 409 |
| Dual activation conflict | Activate Spec A for material_code FP (Spec B already ACTIVE for same code) | Deactivate Spec B → activate Spec A in one transaction | Rollback on failure |
| Numbering collision | generate_spec_number(FP, 1, 1) → "QCSP-FP-001-v01" already exists | Auto-increment to next available sequential: "QCSP-FP-002-v01" | DB unique constraint → retry with incremented seq |

</frozen-after-approval>

## Code Map

- `backend/app/models/specification.py` — existing Specification + SpecParameter model (DUAL LIMITS already present: operational_limit_min/max + release_limit_min/max, test_location, compendial, pharmacopoeia_ref, SpecStatus enum) — EXTEND with lifecycle state machine transitions + new SpecChangeRequest + SpecApproval models
- `backend/app/models/certificate.py` — CertificateOfAnalysis + TestResult models (TestResult fields: result_value, result_numeric, limit_numeric_min/max, status enum PASS/FAIL/MARGINAL/UNKNOWN) — REFERENCE for validation service input/output mapping
- `backend/app/models/base.py` — BaseModel pattern (UUID PK, TimestampMixin, SoftDeleteMixin) — INHERIT for all new models
- `backend/app/schemas/coa_track_models.py` — existing SpecParameterSchema + ProductSpecSchema — REFERENCE for schema patterns; EXTEND with new schemas below
- `backend/app/api/specifications.py` — placeholder router (4 lines) — BUILD OUT CRUD, validation, checklist endpoints
- `backend/app/core/audit.py` — existing audit middleware records all state changes — NO CHANGES needed (already hooked to BaseModel updates)
- `backend/app/services/__init__.py` — existing empty init — add new service imports
- `backend/app/services/spec_validation_service.py` — NEW: validate TestResult against active SpecParameter
- `backend/app/services/spec_numbering_service.py` — NEW: generate QCSP-XXX-NNN-vVV
- `backend/app/services/spec_lifecycle_service.py` — NEW: state machine transitions with audit logging
- `backend/app/services/spec_ingestion_service.py` — NEW: ingest approved QCSP-FP-001 and QCSP-IMB-001 DOCX into DB
- `backend/app/schemas/specification.py` — NEW: SpecificationCreate/Read/Update schemas, SpecParameterCreate, SpecValidationResponse, AnnexA03ChecklistItem, SpecChangeRequestCreate/Read, SpecStateTransition

## Tasks & Acceptance

**Execution:**
- [ ] `backend/app/services/spec_numbering_service.py` — NEW — `generate_spec_number(spec_type: str, sequential: int, version: int) → str` per QCSOP 010 §6.6 format `QCSP-[TYPE]-[NNN]-v[VV]` with auto-increment collision avoidance — seed with FP=001, IMB=001
- [ ] `backend/app/models/specification.py` — EXTEND — add `SpecApproval` model (spec_id FK, role enum AUTHOR/QC_MANAGER/QA, user_id FK, status PENDING/APPROVED/REJECTED, comments, signed_at, signature_hash) and `SpecChangeRequest` model (spec_id FK, change_type MAJOR/MINOR, variation_type IA/IB/II, impact_assessment, regulatory_notification_required, capa_ref) — life cycle audit trail
- [ ] `backend/app/services/spec_lifecycle_service.py` — NEW — state machine: `transition(spec: Specification, target_status: SpecStatus, user_id: UUID, reason: str) → Specification` with validated transition map (DRAFT→ACTIVE via APPROVAL, ACTIVE→SUPERSEDED on new version activation, ACTIVE→WITHDRAWN, SUPERSEDED→WITHDRAWN) — dual-activation guard: only one ACTIVE per material_code at a time
- [ ] `backend/app/services/spec_validation_service.py` — NEW — `validate_result(result: TestResult, spec_param: SpecParameter | None) → SpecValidationResponse` with triple-tier logic: within operational limits → pass, between operational and release → alert with message, outside release → fail — handles categorical/text specs via string match
- [ ] `backend/app/schemas/specification.py` — NEW — Pydantic v2 schemas: SpecValidationResponse (complies: bool | null, status: pass|alert|fail|error, limit_type, alert_message, spec_id ref), AnnexA03ChecklistItem (parameter_name, method_ref, result, spec_limit, complies, checked_by), SpecParameterCreate/Read, SpecificationCreate/Read/Update, SpecStateTransition (target_status: SpecStatus, reason: str), SpecChangeRequestCreate/Read
- [ ] `backend/app/api/specifications.py` — EXTEND from placeholder — CRUD endpoints: POST /specifications (create draft), GET /specifications?status=ACTIVE&material_code=FP (list/filter), GET /specifications/{id} (with parameters), PATCH /specifications/{id}/transition (state change with SpecStateTransition body), POST /specifications/{id}/validate (validate TestResult input against spec), GET /specifications/{id}/checklist-a03 (generate Annex A03 checklist items from spec parameters) — all endpoints require auth, state transitions require QC_MANAGER or QA role
- [ ] `backend/app/services/spec_ingestion_service.py` — NEW — `ingest_approved_spec(docx_path: str) → Specification` — parse QCSP-FP-001/QCSP-IMB-001 DOCX files using python-docx, extract spec metadata (number, version, effective_date, material_code, product_name), extract parameter table rows into SpecParameter records with dual operational/release limits from the real data, create Specification with status=ACTIVE — idempotent: skip if spec_number already exists
- [ ] `backend/app/main.py` — EXTEND — register `spec_router` with prefix /api/specifications (if not already registered)

**Acceptance Criteria:**
- AC-01: Given QCSP-FP-001 ingested and a TestResult for THC=26.5% (Grade I range 25.0–28.9%), when validate endpoint is called, then returns `{"complies": true, "status": "pass", "limit_type": "within_operational"}`
- AC-02: Given TestResult for loss_on_drying=11.2% (operational max=10%, release max=12%), when validate endpoint is called, then returns `{"complies": true, "status": "alert", "limit_type": "operational_breach"}` (not fail — within release limit)
- AC-03: Given TestResult for loss_on_drying=13.5% (release max=12%), when validate endpoint is called, then returns `{"complies": false, "status": "fail"}`
- AC-04: Given Spec in DRAFT status, when transition to ACTIVE is requested, then returns 409 (DRAFT→ACTIVE requires QC_MANAGER approval first, not direct)
- AC-05: Given numbering service called with type=FP seq=1 ver=1, when spec already exists, then auto-increments to seq=2 and returns "QCSP-FP-002-v01"
- AC-06: Given active Spec A for material_code FP, when Spec B for FP is activated, then Spec A is auto-superseded in the same DB transaction
- AC-07: Given QCSP-FP-001 DOCX uploaded, when ingestion service runs, then 19 SpecParameter records are created with correct dual limits matching the document's values including the 5-grade THC table
- AC-08: Given GET /specifications/{id}/checklist-a03, when spec has 19 parameters, then returns 19 AnnexA03ChecklistItem objects with parameter_name, method_ref, spec_limit fields populated — ready for COA review workflow

## Design Notes

**Validation tier logic (per QCSP 003 dual LOD limits):**
```python
def evaluate_limit(result: float, op_min: float|None, op_max: float|None,
                   rel_min: float|None, rel_max: float|None) -> dict:
    within_op = (op_min or -inf) <= result <= (op_max or inf)
    within_rel = (rel_min or -inf) <= result <= (rel_max or inf)
    if not within_rel: return {"complies": False, "status": "fail"}
    if not within_op:  return {"complies": True, "status": "alert"}
    return {"complies": True, "status": "pass"}
```

**State machine transition map:**
```python
SPEC_TRANSITIONS = {
    SpecStatus.DRAFT:       [SpecStatus.ACTIVE],       # after QA approval
    SpecStatus.ACTIVE:       [SpecStatus.SUPERSEDED, SpecStatus.WITHDRAWN],
    SpecStatus.SUPERSEDED:   [SpecStatus.WITHDRAWN],
    SpecStatus.WITHDRAWN:    [],
}
```

## Verification

**Commands:**
- `cd backend && python -c "from app.services.spec_numbering_service import generate_spec_number; print(generate_spec_number('FP', 1, 1))"` — expected: "QCSP-FP-001-v01"
- `cd backend && python -c "from app.services.spec_validation_service import SpecValidationService; print('OK')"` — expected: no import errors
- `cd backend && python -m pytest tests/unit/test_spec_validation.py -v` — expected: all pass (create minimal test file)
- `cd backend && python -c "from app.services.spec_lifecycle_service import SPEC_TRANSITIONS; print(SPEC_TRANSITIONS)"` — expected: transition map printed

**Manual checks (if no CLI):**
- Verify `specification.py` has `SpecApproval` and `SpecChangeRequest` model classes after task completion
- Verify `spec_ingestion_service.py` can parse real DOCX paths without errors
- Verify `specifications.py` router has at least 6 endpoints registered
