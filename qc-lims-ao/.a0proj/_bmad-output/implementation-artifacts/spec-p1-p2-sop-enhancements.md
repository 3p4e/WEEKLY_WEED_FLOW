---
title: 'P1+P2 SOP-Driven Enhancements — Specification & Sample Management'
type: 'feature'
created: '2026-05-31'
status: 'draft'
context:
  - 'implementation-artifacts/spec-p1-specification-linkage.md'
  - 'implementation-artifacts/spec-p2-sample-lifecycle.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The specification management and sample lifecycle modules are functionally correct but incomplete against newly analyzed SOP documents (PPQCSPECIB001, QCSOP 010 v02 §1-8, PP-QC-SOP-017, QCSP 003, QCSOP 011-A01 Cascade Rules). Missing: THC grade classification, chemotype routing, 8-stage specification lifecycle per QCSOP 010, 11-point sampling point model per PP-QC-SOP-017, Foreign Matter pre-test gating at SP-06, multi-day packaging cascade rules, RQS/SFR document models, and corrected genealogy chain codes.

**Approach:** Apply 12 targeted enhancement tasks — 6 for specification management (P1: grade class, analytical preset, chemotype routing, Ph.Eur method refs, 8-stage lifecycle, QAT 043 change workflow) and 6 for sample lifecycle (P2: 11 sampling points, FM pre-test gate, multi-day cascade, RQS/SFR models, genealogy code fix). All changes are additive — extend existing enums, add new fields with sensible defaults, create new models/services alongside existing ones. No data migration needed for existing records.

## Boundaries & Constraints

**Always:**
- All new models use UUID primary keys per project convention
- All new enums use StrEnum (Python 3.11+)
- All state-changing operations log to AuditEntry (ALCOA++)
- Bilingual field pairs (name_en / name_mk) for user-facing text
- Backward-compatible: add new enum members and optional fields — never remove or rename existing ones
- File naming: new models in `models/`, new services in `services/`, schemas in `schemas/`
- All new API endpoints follow existing pattern (Controller → Service → Repository)

**Ask First:**
- Data migration approach if any existing data conflicts with new constraints
- Regulatory variation classification overrides (IA / IB / II)
- Any field that requires a mandatory value but lacks a sensible default

**Never:**
- Do NOT delete or rename existing enums (SpecStatus, SamplingPointType, PotencyGrade)
- Do NOT modify existing API endpoint signatures — add new endpoints or optional query params
- Do NOT change database table names for existing models
- Do NOT attempt Alembic migration generation — only model/schema code
- Do NOT modify frontend code

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| P2-E2: FM Pre-test PASS | SP-06 triggered, FM result ≤2.0% | fm_pretest_passed=True, SP-06 sampling proceeds | N/A |
| P2-E2: FM Pre-test FAIL | SP-06 triggered, FM result >2.0% | fm_pretest_passed=False, SP-06 blocked, deviation raised, QP notified | Raise ValueError with "FM Pre-test failed: Foreign Matter {value}% exceeds 2.0% limit" |
| P2-E3: Multi-day Day 1 | Packaging starts, SP-06 creates SP-07/08/09 | HMA pre-gate runs (≥3 readings, all LOD≤10.0%) | N/A |
| P2-E3: Multi-day Day 2+ | Day 2 packaging begins | New HMA pre-gate required. If LOD ≤10.0% → proceed with reduced panel (potency dupes, LOD dupes, retention sample). If LOD >10.0% → MAJOR deviation | Raise ValueError for >10.0% moisture |
| P1-E3: Chemotype validation | THC 6.0%, CBD 0.5% | Chemotype=THC_DOMINANT, validation passes | N/A |
| P1-E3: Chemotype mismatch | THC 2.0%, CBD 0.3% | Reject: does not meet any chemotype criteria | Raise ValueError with threshold explanation |
| P1-E5: Lifecycle transition | DRAFT → QC_REVIEW | Requires QC Manager sign-off via SpecApproval | Raise ValueError if approval missing |
| P2-E6: Genealogy progression | Stage IPM‑DR‑001, next stage IPM‑CR‑001 | stage_order: 2→3, sequential validation passes | N/A |
| P2-E6: Genealogy skip | Stage IPM‑HT‑001, attempt IPM‑CR‑001 directly | Reject: stage_order gap detected (1→3) | Raise ValueError with current and target stage_order |

</frozen-after-approval>

## Code Map

- `backend/app/models/specification.py` — Specification, SpecParameter, SpecStatus, SpecChangeRequest, SpecApproval models (P1-E1, P1-E3, P1-E4, P1-E5, P1-E6)
- `backend/app/models/sample.py` — Sample model, SampleType, SamplingPointType, SampleStatus, PotencyGrade enums (P2-E1, P2-E2)
- `backend/app/models/sampling_plan.py` — SamplingPlan with sp_07/08/09_required fields (P2-E1)
- `backend/app/models/custody.py` — ChainOfCustody model (P2-E5 SFR reference extension)
- `backend/app/schemas/specification.py` — Pydantic schemas for specification API (P1 all)
- `backend/app/services/spec_ingestion_service.py` — Bulk specification creation (P1-E2: get_finished_product_preset)
- `backend/app/services/spec_validation_service.py` — Spec validation logic (P1-E3: chemotype routing)
- `backend/app/services/spec_lifecycle_service.py` — Spec lifecycle state machine (P1-E5: 8-stage transitions)
- `backend/app/services/sample_lifecycle_service.py` — Sample creation, SP-06 cascade (P2-E2: FM gate, P2-E3: multi-day cascade)
- `backend/app/services/genealogy_service.py` — Genealogy tracking with GenealogyNode (P2-E6: corrected codes + stage_order)
- NEW: `backend/app/models/sampling_request.py` — RQS model (P2-E4)
- NEW: `backend/app/models/sfr.py` — SampleFieldRecord model (P2-E5)
- NEW: `backend/app/services/sampling_request_service.py` — RQS CRUD (P2-E4)
- NEW: `backend/app/services/spec_change_service.py` — QAT 043 change workflow (P1-E6)
- `backend/app/api/specifications.py` — Specification API endpoints (P1-E5, P1-E6 new endpoints)
- `backend/app/api/samples.py` — Sample API endpoints (P2 new endpoints)

## Tasks & Acceptance

**Execution:**

### P1 — Specification Management (6 tasks)

- [ ] `models/specification.py` — ADD THCGrade enum + grade/acceptance_range fields to Specification — P1-E1: THC classification per PPQCSPECIB001 (GRADE_I 25.0-28.9%, GRADE_II 21.0-24.9%, GRADE_III 17.0-20.9%, GRADE_IV 13.0-16.9%, GRADE_V 5.0-12.9%)
- [ ] `services/spec_ingestion_service.py` — ADD get_finished_product_preset() returning 11-parameter dict — P1-E2: 11 analytical parameters (LOD, FM, Total CBN, heavy metals, aflatoxins, pesticides, micro, ID, terpenes)
- [ ] `models/specification.py` + `services/spec_validation_service.py` — ADD Chemotype enum + validate_chemotype() — P1-E3: THC-dominant (THC≥5.0%, CBD≤1.0%), intermediate (THC 1.0-5.0%, CBD≥1.0%, ratio 0.2-5.0), CBD-dominant (THC≤1.0%, CBD≥5.0%)
- [ ] `models/specification.py` — ADD TestMethodRef enum — P1-E4: Ph.Eur monograph references (2.2.32, 2.8.2, 2.4.27, 2.8.18, 2.8.13, 2.6.12/2.6.13, 2.8.10)
- [ ] `models/specification.py` (expand SpecStatus) + `services/spec_lifecycle_service.py` — EXPAND spec lifecycle to 8 stages — P1-E5: INITIATED→DRAFT→QC_REVIEW→QA_APPROVED→NUMBERED→TRAINED→ACTIVE→UNDER_CHANGE with transition guards
- [ ] `models/specification.py` (expand SpecChangeRequest) + NEW `services/spec_change_service.py` — ADD change request workflow — P1-E6: submit/approve/implement statuses, technical justification, regulatory classification (TYPE_IB/TYPE_II)

### P2 — Sample Lifecycle (6 tasks)

- [ ] `models/sample.py` + `models/sampling_plan.py` — EXPAND SamplingPointType to 11 points — P2-E1: SP01-SP11 per PP-QC-SOP-017 with triggers and descriptions
- [ ] `models/sample.py` + `services/sample_lifecycle_service.py` — ADD fm_pretest_passed field + SP-06 FM gate validation — P2-E2: FM test MUST PASS before SP-06; if fail → block + deviation + QP notify
- [ ] `services/sample_lifecycle_service.py` — ADD multi-day packaging cascade logic — P2-E3: SP-06 creates SP-07/08/09, Day 2+ HMA pre-gate, moisture >10.0% = deviation, reduced analytical panel for Day 2+
- [ ] NEW `models/sampling_request.py` + NEW `services/sampling_request_service.py` — ADD RQS model + CRUD — P2-E4: PP-RQS-YYYY-NNNN, status OPEN→REGISTERED→IN_PROGRESS→COMPLETED, 24h registration window
- [ ] NEW `models/sfr.py` + EXTEND `models/custody.py` — ADD SampleFieldRecord model + SFR ref to ChainOfCustody — P2-E5: SFR fields (sfr_id, barrel_numbers JSON, destination), custody linkage
- [ ] `services/genealogy_service.py` + `models/sample.py` — FIX genealogy codes + ADD stage_order — P2-E6: IPM‑HT‑001→IPM‑MT‑001→IPM‑DR‑001→IPM‑CR‑001→IPM‑PK‑001 with sequential stage_order validation

**Acceptance Criteria:**

- **AC-01:** Given any THC percentage in product spec, when grade assignment occurs, then correct grade (I-V) is assigned based on PPQCSPECIB001 ranges
- **AC-02:** Given a new finished product spec creation, when requesting the analytical preset, then 11 parameters are returned with correct Ph.Eur method references, limit types, and bilingual names
- **AC-03:** Given a specification with THC and CBD results, when chemotype routing validates, then the correct chemotype (THC_DOMINANT, THC_CBD_INTERMEDIATE, CBD_DOMINANT) is assigned or validation error raised for mismatches
- **AC-04:** Given a specification created in INITIATED status, when transitioning through the lifecycle, then each of the 8 stages requires its defined guard condition (approval, numbering, training, effective date) before progressing
- **AC-05:** Given a specification change request, when submitted for review, then it progresses through SUBMITTED→UNDER_REVIEW→APPROVED→IMPLEMENTED with traceable audit trail
- **AC-06:** Given any batch entering QC, when SP-02 through SP-06 sampling points trigger, then each is activated at its defined trigger condition per PP-QC-SOP-017
- **AC-07:** Given SP-06 arrival sampling, when Foreign Matter pre-test result is checked, then FM >2.0% blocks all further SP-06 sampling and triggers deviation notification
- **AC-08:** Given multi-day packaging with SP-06 active, when Day 2 begins, then a new HMA pre-gate is required; if moisture ≤10.0%, proceed with reduced analytical panel; if >10.0%, raise MAJOR deviation
- **AC-09:** Given a sampling request from originating department, when registered by QC, then RQS transitions from OPEN to REGISTERED within 24 hours and assigns sampling point (SP01-SP11)
- **AC-10:** Given a genealogy chain query, when traversing from IPM‑HT‑001 through IPM‑PK‑001, then stage_order enforces strict sequential progression with no gaps

## Design Notes

### P1-E5: 8-Stage Lifecycle Transition Guards

```python
class SpecStatus(StrEnum):
    INITIATED = "INITIATED"
    DRAFT = "DRAFT"
    QC_REVIEW = "QC_REVIEW"
    QA_APPROVED = "QA_APPROVED"
    NUMBERED = "NUMBERED"
    TRAINED = "TRAINED"
    ACTIVE = "ACTIVE"
    UNDER_CHANGE = "UNDER_CHANGE"
    # Retain legacy statuses for backward compat:
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"
```

Transition guards:
- INITIATED→DRAFT: Complete info gathering (all mandatory fields populated)
- DRAFT→QC_REVIEW: QC Manager SpecApproval with role=QC_MANAGER and status=APPROVED
- QC_REVIEW→QA_APPROVED: QA SpecApproval with role=QA and status=APPROVED
- QA_APPROVED→NUMBERED: Unique spec_id assigned (PP-SPEC-YYYY-NNNN)
- NUMBERED→TRAINED: All relevant users confirmed training
- TRAINED→ACTIVE: effective_date reached (auto-transition)
- ACTIVE→UNDER_CHANGE: SpecChangeRequest initiated (triggers QAT 043)

### P2-E6: Corrected Genealogy Chain

```python
# OLD (WRONG):
# IPM-HT → IPM-IN → IPM-DS → IPM-PK

# NEW (CORRECT per QCSP 003):
class GenealogyStage(StrEnum):
    IPM_HT_001 = "IPM‑HT‑001"  # stage_order=0 — wet inflorescences
    IPM_MT_001 = "IPM‑MT‑001"  # stage_order=1 — hand-trimmed
    IPM_DR_001 = "IPM‑DR‑001"  # stage_order=2 — machine-trimmed
    IPM_CR_001 = "IPM‑CR‑001"  # stage_order=3 — dried
    IPM_PK_001 = "IPM‑PK‑001"  # stage_order=4 — cured, ready for packaging
```

## Verification

**Commands:**
- `cd backend && python -m pytest app/tests/ -k "spec_history or sampling or genealogy" -v` — expected: existing tests pass with new enums/fields
- `cd backend && python -c "from app.models.specification import THCGrade, Chemotype, TestMethodRef; print('P1 enums OK')"` — expected: imports succeed
- `cd backend && python -c "from app.models.sample import SamplingPointType; assert len(SamplingPointType) >= 11; print('P2-E1 OK')"` — expected: 11+ sampling points
- `cd backend && python -c "from app.services.spec_ingestion_service import get_finished_product_preset; p = get_finished_product_preset(); assert len(p) == 11; print('P1-E2 OK')"` — expected: 11 parameters returned

**Manual checks (if no CLI):**
- Verify SpecChangeRequest model includes `technical_justification: Text | None` and `regulatory_classification: str | None` (TYPE_IB/TYPE_II)
- Verify SampleFieldRecord model links to both Sample and ChainOfCustody via FK
- Verify SamplingRequest model supports RQS ID format PP-RQS-YYYY-NNNN
