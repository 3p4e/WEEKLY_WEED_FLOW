# CoA_TRACK → QC_LIMS_Ao: SOP-Grounded Integration & Development Roadmap

**Author:** BMAD Innovation Strategist ⚡  
**Date:** 2026-05-24  
**Grounded in:** QCSOP 012 v03, QCSOP 010 v02, QCSOP 011-A01 v01, QCSP 003 (TD1-DF400), QCSP 002, QCSOP 009  

---

## Table of Contents

1. [SOP-to-Code Mapping: What Each SOP Demands](#1-sop-to-code-mapping)
2. [Specific Code Integration with SOP Justification](#2-specific-code-integration)
3. [Data Model Adaptation Grid](#3-data-model-adaptation-grid)
4. [Frontend Component Porting with SOP Rationale](#4-frontend-component-porting)
5. [AI Pipeline Integration with SOP Procedural Map](#5-ai-pipeline-integration)
6. [Phased Development Roadmap to Completion](#6-phased-development-roadmap)
7. [Completion Milestones: GMP Inspection Readiness](#7-completion-milestones)
8. [Risk Register & Mitigation](#8-risk-register)

---

## 1. SOP-to-Code Mapping

### 1.1 QCSOP 012 v03 — Certificate of Analysis Issuance & Management

**SOP Clause** | **Required System Behavior** | **CoA_TRACK Code to Reuse** | **Adaptation Needed**
---|---|---|---
§A01.2 — eCoA Workflow: Sample shipped → eCoA received → Provisional register entry → Review against Annex A03 checklist → Conformance vs PP spec → Decision → QC Manager signs → Register updated → Archival | 7-step state machine with role-gated transitions | `Document.status` workflow (draft → analyst_review → qc_approved → issued → superseded → cancelled) | Extend to 7 states: `RECEIVED` → `PROVISIONALLY_REGISTERED` → `CHECKLIST_REVIEW` → `CONFORMANCE_CHECKED` → `{DISCREPANCY / CONFORMING}` → `MANAGER_SIGNED` → `ARCHIVED`. Add `AnnexA03Checklist` model linked to each eCoA.
§A01.3 — CoQ Workflow | Compilation of multiple eCoA/iCoA into single CoQ | `CoQ` model + `CoQService.aggregate_parameters()` | Extend with cross-document traceability: each CoQ parameter must reference source CoA + certificate number.
§A01.1 — Internal COA (iCoA) Workflow | Full in-house COA generation from sample receipt to QP signature | Not in CoA_TRACK (focused on eCoA ingestion) | **New development** — build `InternalCOAWorkflow` using spec-driven parameter population, result entry with 2nd-person verification, QP digital signature.
### 1.2 QCSOP 010 v02 — Specification Development, Approval, Issuance & Handling

**SOP Clause** | **Required System Behavior** | **CoA_TRACK Code to Reuse** | **Adaptation Needed**
---|---|---|---
§6.3 — Specification Initiation: Any dept head initiates → QA coordinates → QC drafts | Spec creation with role-based initiation, multi-step approval | `SpecParameter` model structure | Add `initiated_by` FK, `initiation_date`, `specification_type` enum (IMG/IPM/FP/IMB per §6.6 numbering convention). Add `SpecificationDraft` state.
§6.4 — Drafting: Parameter name, test method, acceptance criteria, in-house vs external notation | Structured parameter entry with method references, limit types, external lab flags | `SpecParameter` fields: `name_local`, `name`, `test_method`, `limits_type` | Add `test_location` enum (IN_HOUSE/EXTERNAL), `external_lab_id` FK, `pharmacopoeia_ref` (e.g., "Ph. Eur. 2.2.32"), `compendial` boolean (for §Definitions: Compendial Specification).
§6.5 — Review/Approval: Self-review → QC Manager technical review → QA approval | 3-step approval with signature capture at each step | Not in CoA_TRACK | **New** — `SpecificationApproval` join table: `spec_id`, `role` (AUTHOR/QC_MANAGER/QA), `user_id`, `status` (PENDING/APPROVED/REJECTED), `comments`, `signed_at`, `signature_hash`.
§6.6 — Numbering: `[type]-[NNN]-v[VV]` (e.g., QCSP-FP-001-v02) | Auto-generated sequential numbers per spec type, version tracking | Not in CoA_TRACK | **New** — `spec_number` field with format validation, auto-increment per `spec_type`.
§6.7 — External Lab Communication | Track which parameters are tested externally and maintain technical quality agreement references | `SpecParameter` with external flag | Add `technical_agreement_ref` field, `last_communicated_date` for tracking when spec was sent to external lab.
§6.9 — Revision & Change Control (via QAT 043) | All spec changes through formal change control with impact assessment | Not in CoA_TRACK | **New** — `SpecificationChangeRequest` model linked to spec, with `change_type` (MAJOR/MINOR), `variation_type` (IA/IB/II per EU), `impact_assessment`, `regulatory_notification_required` boolean.
§6.11 — Master Specification Register | Central register of all specs with status, version, dates | Not in CoA_TRACK | **New** — `SpecificationRegister` view/endpoint with filtering by status (ACTIVE/SUPERSEDED/WITHDRAWN), quarterly review flag.
### 1.3 QCSOP 011-A01 v01 — Sampling Plan (Bilingual)

**SOP Clause** | **Required System Behavior** | **CoA_TRACK Code to Reuse** | **Adaptation Needed**
---|---|---|---
SP-06 is main batch release sampling point, triggers SP-07/SP-08/SP-09 in same session | Cascading sample creation: one trigger point auto-generates dependent samples | Not in CoA_TRACK | **New** — `SamplingTrigger` model defining parent-child relationships between sampling points. SP-06 creation auto-generates SP-07, SP-08, SP-09 records.
Sequenced workflow (strictly in order) | Step-by-step guided workflow with prerequisite gates | Not in CoA_TRACK | **New** — `SamplingSequence` defining order of operations, with `prerequisite_completed` check before next step unlocks.
Sampling formula: n = ROUNDUP(√N × 1.5) for final units, minimum 3 containers for raw material | Auto-calculate sample size from batch quantity | Not in CoA_TRACK | **New** — `calculate_sample_size()` utility: accepts `batch_size` and `material_type`, returns sample count per formula.
Identity testing on EVERY container (raw material, Annex 8 §2) | Mandatory identity test per container, not just per sample | Not in CoA_TRACK | **New** — `ContainerIdentityTest` model: one record per container received, linked to `Sample`.
Potency grade system: Total THC = (THCA × 0.877) + THC, tolerance ±10% (Ph.Eur.3028) | Auto-calculation of total THC from THCA + THC values, grade assignment | Not in CoA_TRACK | **New** — `calculate_total_thc()` utility in `utils/cannabinoid.py`, `PotencyGrade` model with tiers defined per strain.
FP LOD specification: ≤ 10.0% (Ph.Eur.3028, method c). Operational target <12% for sFP. | Different spec limits for finished product vs semi-finished product | Not in CoA_TRACK | Extend `SpecParameter` with `material_stage` context (FP/sFP) and `operational_limit` vs `release_limit` distinction.
Re-test (RT): ONLY after formal OOS investigation AND new registered RQS. Independent re-testing = CRITICAL violation. | System must prevent re-test without linked OOS record | Not in CoA_TRACK | **New** — `RetestRequest` requiring `oos_record_id` FK (not nullable). Validation: cannot create retest without approved OOS Phase I completion.
Batch packaged over multiple days → sub-batch designations (D1, D2...) | Auto-generate sub-batch codes for multi-day packaging | Not in CoA_TRACK | **New** — `sub_batch_code` field on `Sample`, auto-incrementing letter suffix per packaging day.
### 1.4 QCSP 003 — TD1-DF400 Technological Dossier

**SOP Clause** | **Required System Behavior** | **CoA_TRACK Code to Reuse** | **Adaptation Needed**
---|---|---|---
5 intermediary products (IPM-HT-001 → IPM-PK-001) each with IPC parameters | Product genealogy tree: final product traces back through all intermediates | Not in CoA_TRACK | **New** — `ProductGenealogy` model tracking `parent_material_code` → `child_material_code` relationships. Batch record links through the chain.
IPC parameters per stage (e.g., D3: Moisture Content <15% operational, <12% target) | Stage-specific parameter limits with operational vs target distinction | Not in CoA_TRACK | Extend `SpecParameter` with `ipm_stage` FK to `IntermediaryProduct`. Each IPM has its own parameter set.
Visual inspections under ≥500 lux lighting | Record inspection conditions (lighting, inspector qualification) | Not in CoA_TRACK | **New** — `InspectionCondition` model: `lighting_lux`, `inspector_training_record_ref`.
Moisture uniformity: \|ΔMC%\| ≤ 1.5% across flower size grades | Cross-grade moisture comparison with auto-flagging | Not in CoA_TRACK | **New** — `moisture_uniformity_check()`: compares MC% across size grades, flags if delta exceeds 1.5%.
### 1.5 QCSP 002 — Raw Material & Incoming Goods Specification

**SOP Clause** | **Required System Behavior** | **CoA_TRACK Code to Reuse** | **Adaptation Needed**
---|---|---|---
Parameter table: Appearance, Identity, Purity/Composition, pH, Moisture, Microbial Limits, Heavy Metals + custom parameters | Template-based spec with add/remove rows for custom parameters | Not in CoA_TRACK | **New** — `SpecificationTemplate` model: defines mandatory parameter set per material category, with ability to add/remove custom parameters.
Spec number format: QCSP-RMI-001v1 (Raw Material Incoming) | Consistent numbering per §6.6 of QCSOP 010 | Not in CoA_TRACK | Extend numbering to support RMI (Raw Material Incoming) prefix.
---

## 2. Specific Code Integration with SOP Justification

### 2.1 COA State Machine — Extending CoA_TRACK's Document Model

**SOP Reference:** QCSOP 012 v03 §A01.2 (eCoA Workflow)

```python
# CoA_TRACK current (app/models.py ~lines 96-178):
# Status: draft → analyst_review → qc_approved → issued

# QC_LIMS extension for full QCSOP 012 compliance:

class COAStatus(str, enum.Enum):
    """Per QCSOP 012 v03 §A01.2 workflow"""
    RECEIVED = "received"                          # eCoA received via secure channel
    PROVISIONALLY_REGISTERED = "provisionally_registered"  # Entry in provisional register
    CHECKLIST_REVIEW = "checklist_review"           # Review against Annex A03 checklist
    CONFORMANCE_CHECKED = "conformance_checked"     # vs PP spec determination
    DISCREPANCY_RAISED = "discrepancy_raised"       # Escalated to QC Manager
    CONFORMING = "conforming"                        # No discrepancy — proceed to sign
    MANAGER_SIGNED = "manager_signed"               # QC Manager signs checklist
    REGISTER_UPDATED = "register_updated"           # Register updated (QC Manager)
    ARCHIVED = "archived"                           # Final archival
    REJECTED = "rejected"                           # eCoA rejected after discrepancy

# State transitions (QCSOP 012 §A01.2):
COA_TRANSITIONS = {
    COAStatus.RECEIVED: [COAStatus.PROVISIONALLY_REGISTERED],
    COAStatus.PROVISIONALLY_REGISTERED: [COAStatus.CHECKLIST_REVIEW],
    COAStatus.CHECKLIST_REVIEW: [COAStatus.CONFORMANCE_CHECKED],
    COAStatus.CONFORMANCE_CHECKED: [COAStatus.DISCREPANCY_RAISED, COAStatus.CONFORMING],
    COAStatus.DISCREPANCY_RAISED: [COAStatus.REJECTED],
    COAStatus.CONFORMING: [COAStatus.MANAGER_SIGNED],
    COAStatus.MANAGER_SIGNED: [COAStatus.REGISTER_UPDATED],
    COAStatus.REGISTER_UPDATED: [COAStatus.ARCHIVED],
}
```

### 2.2 Specification Numbering — Per QCSOP 010 §6.6

```python
# New: backend/app/utils/spec_numbering.py

from enum import StrEnum

class SpecType(StrEnum):
    """Per QCSOP 010 v02 §6.6 numbering convention"""
    IMG = "IMG"  # Raw Material / Incoming Material
    IPM = "IPM"  # In-Process Material
    FP = "FP"    # Finished Product
    IMB = "IMB"  # Intermediate Bulk

def generate_spec_number(spec_type: SpecType, sequential: int, version: int) -> str:
    """Generate spec number per QCSOP 010 §6.6 format.
    
    Format: QCSP-[type]-[NNN]-v[VV]
    Examples:
        QCSP-FP-001-v02  (Finished Product spec #1, version 2)
        QCSP-IMG-003-v01 (Raw Material spec #3, version 1)
    """
    return f"QCSP-{spec_type.value}-{sequential:03d}-v{version:02d}"
```

### 2.3 Potency Calculation — Per QCSOP 011-A01 (Potency Grade System)

```python
# Adapted from CoA_TRACK's parameter result processing
# New: backend/app/utils/cannabinoid.py

def calculate_total_thc(thc: float, thca: float) -> float:
    """Calculate total THC per Ph. Eur. Monograph 3028 conversion.
    
    Per QCSOP 011-A01: Total THC = (THCA × 0.877) + THC
    Tolerance: ±10% (Ph.Eur.3028)
    """
    return round((thca * 0.877) + thc, 2)

def calculate_total_cbd(cbd: float, cbda: float) -> float:
    """Calculate total CBD using same conversion factor."""
    return round((cbda * 0.877) + cbd, 2)

def assign_potency_grade(
    total_thc: float,
    grade_definitions: list[dict],  # From PotencyGrade model
    tolerance_pct: float = 10.0
) -> str | None:
    """Assign batch to a potency grade based on total THC.
    
    Per QCSOP 011-A01: Tolerance ±10% (Ph.Eur.3028)
    CBD: <1.0% for all grades.
    """
    for grade in grade_definitions:
        lower = grade["thc_min"]
        upper = grade["thc_max"]
        tolerance = (upper - lower) * (tolerance_pct / 100)
        if (lower - tolerance) <= total_thc <= (upper + tolerance):
            return grade["name"]
    return None  # Out of all grade ranges — OOS trigger
```

### 2.4 Sample Size Calculation — Per QCSOP 011-A01

```python
# New: backend/app/utils/sampling.py

import math

def calculate_sample_size(
    population_size: int,
    material_type: str,
    is_identity_test: bool = False
) -> int:
    """Calculate sample size per QCSOP 011-A01 formulas.
    
    Finished product: n = ROUNDUP(√N × 1.5)
    Raw material full panel: n = ROUNDUP(√N × 1.5), minimum 3 containers
    Raw material identity: EVERY container (Annex 8 §2)
    """
    if is_identity_test and material_type == "RAW_MATERIAL":
        return population_size  # Every container — Annex 8 §2
    
    n = math.ceil(math.sqrt(population_size) * 1.5)
    
    if material_type == "RAW_MATERIAL":
        n = max(n, 3)  # Minimum 3 containers per QCSOP 011-A01
    
    return n
```

### 2.5 Annex A03 Checklist Model — Per QCSOP 012 §A01.2

```python
# New: backend/app/models/checklist.py

class AnnexA03Checklist(BaseModel):
    """QCSOP 012 §A01.2 — External COA review checklist."""
    __tablename__ = "annex_a03_checklists"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    coa_id: Mapped[UUID] = mapped_column(ForeignKey("certificates_of_analysis.id"))
    
    # Checklist items per QCSOP 012 Annex A03
    lab_accredited: Mapped[bool | None]  # Is contract lab ISO 17025 accredited?
    all_parameters_reported: Mapped[bool | None]  # All required parameters tested?
    methods_specified: Mapped[bool | None]  # Test methods clearly identified?
    acceptance_criteria_clear: Mapped[bool | None]  # Pass/fail clearly stated?
    results_within_spec: Mapped[bool | None]  # All results within PP spec limits?
    signatures_present: Mapped[bool | None]  # Lab analyst + reviewer signatures?
    date_within_validity: Mapped[bool | None]  # COA date within validity period?
    sample_id_matches: Mapped[bool | None]  # Sample ID matches PP submission?
    
    overall_result: Mapped[str | None]  # CONFORMING / DISCREPANCY
    reviewed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None]
    comments: Mapped[str | None] = mapped_column(Text)
```

---

## 3. Data Model Adaptation Grid

| CoA_TRACK Model | QC_LIMS Model | Structural Changes | SOP Justification | Migration Complexity |
|---|---|---|---|---|
| `Document` | `CertificateOfAnalysis` | `id: int` → `id: UUID`; add `sample_id` FK, `specification_id` FK, `checklist_id` FK; add `cert_type` extensions for iCoA; add `coa_number` auto-generation per PP-COA-YYYY-NNNN format | QCSOP 012 §A01.1-3 workflows; QCSOP 010 §6.6 numbering | Medium |
| `Parameter` | `TestResult` | `id: int` → `id: UUID`; add `spec_parameter_id` FK, `complies` boolean, `verified_by` FK, `verification_date`; keep dual `result_value` (string) + `result_numeric` (float) pattern | QCSOP 012 conformance determination; ALCOA++ 2nd person verification | Low — CoA_TRACK's dual field pattern is SOP-compliant |
| `SpecParameter` | `SpecParameter` | `id: int` → `id: UUID`; add `pharmacopoeia_ref`, `sort_order`, `test_location` enum, `external_lab_id` FK, `operational_limit` vs `release_limit`, `compendial` boolean | QCSOP 010 §6.4 (parameter definition), §6.7 (external labs); QCSP 003 dual limits | Low |
| `ProductSpec` | `Specification` | `id: int` → `id: UUID`; add `spec_number` (auto-generated), `material_code`, `material_type` enum (IMG/IPM/FP/IMB), `effective_date`, `expiry_date`, `status` enum (DRAFT/ACTIVE/SUPERSEDED/WITHDRAWN), `initiated_by` FK | QCSOP 010 §6.3-6.6, §6.11 register; QCSP 002 template | High — significant new fields |
| `WaterReport` | `WaterSample` | `id: int` → `id: UUID`; add `sample_point` enum, `alert_limit_*` / `action_limit_*` fields, `temperature_at_measurement`; add trending calculation methods | QCSOP 014 (pending); Ph. Eur. water monograph | Low |
| `AuditLog` | `AuditEntry` | Keep QC_LIMS `AuditMiddleware` pattern; merge CoA_TRACK's `_ENTITY_TO_TABLE` mapping and `AuditService.list_entries()` query patterns | EU GMP Annex 11 §15; 21 CFR Part 11 §11.10(e) | Medium — merge both approaches |
| `Batch` | `Sample` + `Batch` | Split: `Batch` = production context (strain, cultivation data); `Sample` = laboratory tracking (chain of custody, test assignment, storage location) | QCSOP 011 chain-of-custody; QCSOP 011-A01 sampling points | High — structural split |
| `CoQ` | `CertificateOfQuality` | Extend with `source_coa_ids` (array of FK), `aggregated_parameters` (JSONB snapshot frozen at approval), `ai_summary` text | QCSOP 012 §A01.3 CoQ workflow; ALCOA++ Complete (snapshot at time of approval) | Medium |
| `Embedding` | Qdrant (external) | Migrate from pgvector to Qdrant; re-embed with voyage-3 (1024d); use `pp_qms_sops` collection | Latency requirement: <5s for Letta agent responses; Qdrant HNSW outperforms pgvector at scale | High — storage migration |
| `User` | `User` | Keep QC_LIMS `Role` enum (admin/qc_analyst/qc_reviewer/qc_manager/qa_manager/qp/auditor); merge CoA_TRACK Google OAuth endpoint | QCSOP 001 roles; EU GMP Annex 11 §12 (access control) | Medium — merge auth |
| _(new)_ | `SamplingTrigger` | Parent-child: SP-06 triggers SP-07/SP-08/SP-09 automatically | QCSOP 011-A01 SP-06 as main release point | **New** |
| _(new)_ | `ProductGenealogy` | Tracks IPM chain: TD1-DF400 → IPM-HT-001 → IPM-MT-001 → IPM-DR-001 → IPM-CR-001 → IPM-PK-001 | QCSP 003 5-intermediary structure | **New** |
| _(new)_ | `AnnexA03Checklist` | Structured checklist linked to each eCoA | QCSOP 012 §A01.2 explicit checklist review step | **New** |
| _(new)_ | `SpecificationChangeRequest` | Change control per QAT 043 format | QCSOP 010 §6.9 revision workflow | **New** |

---

## 4. Frontend Component Porting with SOP Rationale

### 4.1 ESignatureModal.tsx — **Critical for QP Batch Release**

**SOP Reference:** QCSOP 012 §A01.2 (QC Manager signs checklist); EU GMP Annex 11 §14 (electronic signature); 21 CFR Part 11 §11.50 (signed electronic records), §11.200 (two-component identification)

**What CoA_TRACK has:**
- Password re-authentication modal
- Meaning-of-signature capture ("I approve this COA for batch release")
- Timestamp recording
- WCAG accessibility

**What QC_LIMS needs to add:**
- Second factor: password + TOTP token (per 21 CFR §11.200 two distinct components)
- Role-specific meaning statements per QCSOP 010 §6.5 approval chain:
  - Analyst: "I confirm these results are accurate and were obtained following approved methods."
  - QC Manager: "I have reviewed all results and confirm conformance to PP specifications."
  - QA: "I confirm this specification meets all regulatory requirements."
  - QP: "I certify this batch is suitable for release to the market."
- Signature linked to specific record (per §11.70 — signatures must prevent falsification)

**Integration:** Port `ESignatureModal.tsx` as-is, then extend with:
```tsx
<E-Signature-Modal
  recordType="certificate_of_analysis"
  recordId={coa.id}
  action="approve"
  meaningStatements={{
    qc_manager: "I have reviewed the Annex A03 checklist and confirm conformance...",
    qp: "I certify this batch is suitable for release to the medical market."
  }}
  requiredFactors={2}  // password + TOTP
/>
```

### 4.2 PermissionGate.tsx — Role-Based UI Access

**SOP Reference:** QCSOP 001 §roles; EU GMP Annex 11 §12 (access control)

**What CoA_TRACK has:** Component wrapper for admin/analyst/viewer roles.

**What QC_LIMS needs:** Extend to full GMP role set:
```tsx
<PermissionGate allowedRoles={['qc_analyst', 'qc_reviewer', 'qc_manager', 'qa_manager', 'qp']}>
  <ApproveCOAButton />
</PermissionGate>
// QP-only actions:
<PermissionGate allowedRoles={['qp']}>
  <ReleaseBatchButton />
</PermissionGate>
```

### 4.3 StatusBadge.tsx — WCAG Colorblind-Safe Status Display

**SOP Reference:** ALCOA++ Legible + Available; EU GMP Annex 11 §11 (clear status indication)

**What CoA_TRACK has:** Color-coded badges with pattern backup for colorblind users.

**QC_LIMS status values per SOPs:**

| Status | SOP Source | Badge Variant |
|---|---|---|
| QUARANTINE | QCSOP 011-A01 (material in quarantine until ARI APPROVED) | Orange (⚠ pattern) |
| IN_TEST | QCSOP 012 workflow | Blue (hourglass pattern) |
| CONFORMING | QCSOP 012 §A01.2 | Green (✓ pattern) |
| DISCREPANCY | QCSOP 012 §A01.2 | Red (✕ pattern) |
| MANAGER_SIGNED | QCSOP 012 §A01.2 | Green-bold (✓✓ pattern) |
| OOS_OPEN | QCSOP 019 | Red-flashing (!! pattern) |
| OOS_PHASE_I | QCSOP 019 §Phase I | Orange (magnifier pattern) |
| OOS_PHASE_II | QCSOP 019 §Phase II | Red (root-cause pattern) |
| RETEST_PENDING | QCSOP 011-A01 re-test rules | Purple (↻ pattern) |
| STABILITY_PULL_DUE | QCSOP 018 | Yellow (clock pattern) |
| STABILITY_OVERDUE | QCSOP 018 | Red (!! clock pattern) |

### 4.4 SessionTimeoutProvider.tsx — Annex 11 §6 Compliance

**SOP Reference:** EU GMP Annex 11 §6 (inactivity timeout)

**What CoA_TRACK has:** 5-min warning + auto-logout.

**QC_LIMS extension:**
- Configurable timeout per role (QP: 10 min, Analyst: 30 min, Auditor read-only: 1 hour)
- Warning at 80% of timeout
- Auto-save draft data before logout (no data loss)
- Audit log entry for timeout

### 4.5 DragDropUpload.tsx — eCoA PDF Ingestion

**SOP Reference:** QCSOP 012 §A01.2 (eCoA received via secure channel)

**What CoA_TRACK has:** Drag-drop upload with file validation.

**QC_LIMS extension:**
- File type validation: PDF only, max 20MB
- Auto-trigger AI extraction pipeline on upload
- Duplicate detection: hash check against existing eCoAs
- Secure channel logging: record upload method (API, Web UI, email-to-system)
- Provisional register entry auto-created on successful upload

---

## 5. AI Pipeline Integration with SOP Procedural Map

### 5.1 eCoA Extraction Pipeline → QCSOP 012 §A01.2 Review

```
USER ACTION                     AI PIPELINE                         SOP REFERENCE
────────────                    ────────────                        ─────────────
Upload eCoA PDF                 
    ↓
                                PyMuPDF text extraction             
                                ↓
                                DeepSeek structured extraction:     
                                - Batch number                      
                                - Test parameters + results         
                                - Lab identification                
                                - Date of analysis                  
                                ↓
                                Auto-fill Annex A03 Checklist:      QCSOP 012 §A01.2
                                - Lab accredited? (check DB)         
                                - All parameters? (compare vs spec) 
                                - Methods specified? (check fields)  
                                - Results in spec? (numeric compare) 
                                ↓
QC Analyst reviews             Conformance flag: PASS/FAIL/REVIEW   
                                with specific discrepancies highlighted
                                ↓
QC Manager approves            Checklist + conformance = sign       QCSOP 012 §A01.2
```

### 5.2 Letta Agent Integration Points

| SOP Workflow Step | Letta Agent | Prompt Type | RAG Source |
|---|---|---|---|
| eCoA discrepancy decision | CAPA Manager Elena | "Given these discrepancies [X,Y,Z], what is the severity classification? What are the next steps per QCSOP 019?" | `pp_qms_sops` → QCSOP 019 §OOS classification |
| Spec development: parameter justification | GMP Expert Viktor | "What are the Ph. Eur. 3028 requirements for [parameter]? What acceptance criteria are typical for cannabis flower?" | `pp_qms_sops` → Ph. Eur. 3028, ICH Q6A |
| OOS Phase I lab investigation | CAPA Manager Elena | "Result: [value] vs Spec: [limit]. What are the top 5 most likely lab errors to investigate first?" | `pp_qms_sops` → QCSOP 019 §Phase I checklist |
| Specification change impact assessment | Risk Assessor | "Changing FP LOD from 12% to 10%. What downstream SOPs, validations, and regulatory notifications are impacted?" | `pp_qms_sops` → QCSOP 010 §6.9, QCSOP 012, stability protocols |
| COA compilation for CoQ | QMS Orchestrator | "Assemble CoQ from eCoAs [A, B, C]. Identify any parameter gaps, conflicting results, or missing signatures." | `pp_qms_sops` → QCSOP 012 §A01.3 |
| Training: new analyst onboarding | SOP Writer | "Explain QCSOP 012 COA workflow in plain Macedonian with step-by-step summary." | `pp_qms_sops` → QCSOP 012 full text |

### 5.3 3-Tier AI Resilience — Per Letta RAG Pipeline Architecture

**SOP Reference:** EU GMP Annex 11 §16 (business continuity); no single point of failure for computerised systems

```
Tier 1: Letta Agent (full) ──────────► Response in <5s ──► Use
    │ FAILS (network, rate limit, model unavailable)
    ▼
Tier 2: Cached SOP snippets (local) ─► Pre-computed embedding lookup from SQLite cache
    │ FAILS (cache miss, corrupted)
    ▼
Tier 3: Static rule engine ──────────► Hardcoded SOP decision trees (e.g., "If LOD > 10%, FAIL")
    │ Guaranteed to respond; shows "AI unavailable — using static rules" banner
    ▼
User always gets an answer — degraded but functional.
```

**Code to port from CoA_TRACK:**
- `app/ai/fallback.py` (117 lines) — tiered degradation logic
- `app/ai/memory.py` — agent conversation context management
- `app/ai/prompts/extraction.py` — structured extraction prompts (Macedonian CoA parsing)

---

## 6. Phased Development Roadmap to Completion

### Architecture Principle

CoA_TRACK evolves into **QC_LIMS's "External COA Module"** — a self-contained sub-system within the larger LIMS monolith. The monolith provides shared infrastructure (auth, audit, spec management, sample tracking); the CoA module provides specialized COA ingestion, extraction, and assembly capabilities.

```
QC_LIMS_Ao (Monolith)
│
├── Infrastructure Layer (shared)
│   ├── Auth (JWT + Google OAuth)     ← Merge CoA_TRACK OAuth
│   ├── Audit Trail (WORM)            ← Merge CoA_TRACK audit query patterns
│   ├── Database (async SQLAlchemy)   ← Add CoA_TRACK models as migrations
│   └── File Storage (local + GDrive) ← Merge rclone sync pattern
│
├── Domain Modules (independent)
│   ├── Sample Management        ← NEW (QCSOP 011-based)
│   ├── Specification Management ← NEW (QCSOP 010-based)
│   ├── COA Module ───────────── ← CoA_TRACK EVOLVES HERE
│   │   ├── External COA Ingestion (from CoA_TRACK)
│   │   ├── Internal COA Generation (NEW)
│   │   ├── AI-Powered Extraction (from CoA_TRACK, upgraded)
│   │   ├── Annex A03 Review (NEW per QCSOP 012)
│   │   ├── Certificate of Quality Assembly (from CoA_TRACK CoQService)
│   │   ├── Progressive Review Workflow (NEW)
│   │   └── QP Digital Signature (from CoA_TRACK ESignatureModal, upgraded)
│   ├── OOS Investigation         ← NEW (QCSOP 019-based)
│   ├── Stability Studies         ← NEW (QCSOP 018-based)
│   ├── Water System QC           ← Port CoA_TRACK WaterReport
│   ├── Microbiological Monitoring← NEW (QCSOP 023/024-based)
│   ├── Equipment Calibration     ← NEW (QCSOP 008-based)
│   └── Inventory & Labeling      ← NEW (QCSOP 025-based)
│
└── AI Layer (Letta + Qdrant)
    ├── 5 Letta Agents (GMP, CAPA, SOP Writer, Risk, Orchestrator)
    ├── 3-Tier Resilience (from CoA_TRACK fallback.py)
    └── RAG Pipeline (Qdrant pp_qms_sops)
```

### Phase P0: Foundation (Weeks 1-2)

**Goal:** Ready both codebases for integration. CoA_TRACK becomes importable as a Python package.

| Week | Task | From CoA_TRACK | To QC_LIMS | SOP Grounding |
|------|------|---------------|------------|---------------|
| W1 | Alembic initialization | `models.py` → migration targets | `backend/alembic/` | Annex 11 §4 (validation) |
| W1 | Pydantic v2 schemas for all CoA_TRACK models | `Document`, `Parameter`, `SpecParameter`, `ProductSpec`, `WaterReport` → schemas | `backend/app/schemas/coa.py` | Data integrity (ALCOA+) |
| W1 | Repository pattern for CoA services | `coa_service.py`, `coq_service.py` → repository layer | `backend/app/repositories/coa_repo.py` | Testability (GAMP 5) |
| W2 | Qdrant client integration | Replace pgvector → Qdrant | `backend/app/services/qdrant_service.py` | Performance (<5s queries) |
| W2 | UUID migration script | Integer IDs → UUIDs | Migration `003_uuid_migration.py` | Data integrity |
| W2 | Google OAuth endpoint | `auth.py` → `POST /api/v1/auth/google` | `backend/app/api/auth.py` | SSO for Google Workspace |

**Deliverable:** CoA_TRACK models runnable within QC_LIMS backend, with UUID PKs, Pydantic schemas, and Qdrant embeddings.

### Phase P1: Specification Linkage (Weeks 3-4)

**Goal:** External CoA parameters auto-validate against active Purely Plant specifications.

| Week | Task | SOP Grounding |
|------|------|---------------|
| W3 | Build `Specification` model with numbering per QCSOP 010 §6.6 | QCSOP 010 §6.3-6.6 |
| W3 | Build `SpecParameter` with dual limits (operational/release) | QCSP 003 (TD1-DF400) dual LOD limits |
| W3 | Spec-driven validation: extracted parameters auto-compare to active spec | QCSOP 012 §A01.2 conformance check |
| W4 | Color-coded conformance: green check / red X per parameter | ALCOA++ Accurate + Available |
| W4 | Parameter-level traceability: each result → spec parameter → method → pharmacopoeia | QCSOP 010 §6.4 |
| W4 | Auto-populate Annex A03 checklist from extraction + spec comparison | QCSOP 012 §A01.2 |

**Deliverable:** Upload an eCoA PDF → system extracts parameters, compares against active PP spec, flags discrepancies, pre-fills A03 checklist.

### Phase P2: Sample Lifecycle Context (Weeks 5-7)

**Goal:** Every CoA is linked to a Sample with full chain-of-custody.

| Week | Task | SOP Grounding |
|------|------|---------------|
| W5 | Build `Sample` model with sampling points (SP-01 through SP-11) | QCSOP 011-A01 §sampling points |
| W5 | Auto-generate dependent samples: SP-06 → SP-07/08/09 | QCSOP 011-A01 §SP-06 as main trigger |
| W5 | Sample size auto-calculation: n = ROUNDUP(√N × 1.5) | QCSOP 011-A01 §formulas |
| W6 | Chain-of-custody: every transfer logged with signature | QCSOP 011 §chain of custody |
| W6 | Barcode/QR generation and scanning: scan once, populate everywhere | Quick-win requirement |
| W6 | Container-level identity testing: every RM container tested | QCSOP 011-A01 §Annex 8 §2 |
| W7 | Sub-batch designations: D1, D2... for multi-day packaging | QCSOP 011-A01 §sub-batch codes |
| W7 | Product genealogy tree: IPM-HT-001 → ... → IPM-PK-001 | QCSP 003 §5 intermediary products |

**Deliverable:** Sample received → barcode scanned → all test assignments created → chain of custody visible → CoA linked to sample context.

### Phase P3: Progressive Review & E-Signature (Weeks 8-9)

**Goal:** No "Submit for Review" button. Reviewers see work in progress. Signatures are declaration-level.

| Week | Task | SOP Grounding |
|------|------|---------------|
| W8 | Progressive review: Reviewer sees analyst's in-progress results in real-time | Disclosed automation (UX principle) |
| W8 | Auto-advance: when all results entered → auto-appears in reviewer queue | QCSOP 012 review workflow |
| W8 | Reviewer dashboard: risk-prioritized queue (overdue > OOS-linked > routine) | Stefan (QC Supervisor) persona |
| W9 | Declaration-level signing: QP sees all results + compliance summary before signing | Martin (QP) persona |
| W9 | E-Signature with 2-factor (password + TOTP) | 21 CFR Part 11 §11.200 |
| W9 | Role-specific meaning statements captured with signature | QCSOP 010 §6.5 approval chain |

**Deliverable:** Analyst enters results → Reviewer sees them live → Auto-routes to QP when complete → QP signs with 2FA + meaning statement.

### Phase P4: OOS Integration (Weeks 10-12)

**Goal:** OOS detected during extraction → auto-creates OOS record → guides Phase I/II investigation.

| Week | Task | SOP Grounding |
|------|------|---------------|
| W10 | OOS auto-detection: parameter outside spec → `OOSRecord` created | QCSOP 019 §detection |
| W10 | Phase I lab investigation form (QCSOP 019-A01) | QCSOP 019-A01 appendix |
| W10 | Lab error check: calculations, dilutions, equipment, standards, technique | QCSOP 019 §Phase I checklist |
| W11 | Re-test gating: no retest without approved OOS Phase I + new RQS | QCSOP 011-A01 §RT critical violation rule |
| W11 | Phase II: root cause categories, CAPA linkage (QAT 043 format) | QCSOP 010 §6.9 change control |
| W11 | CAPA Manager Letta agent integration: suggest root causes from history | QCSOP 019-A02/A03 historical patterns |
| W12 | OOS Register dashboard (QCSOP 019-A03) | QCSOP 019-A03 central log |
| W12 | Notification templates (QCSOP 019-A04) | QCSOP 019-A04 notification form |

**Deliverable:** eCoA extraction detects OOS → auto-creates investigation → guides Phase I → gates retest → tracks through Phase II → updates OOS register.

### Phase P5: AI Supercharge (Weeks 13-15)

**Goal:** AI agents provide proactive guidance throughout all workflows.

| Week | Task | SOP Grounding |
|------|------|---------------|
| W13 | Preventive prompts: before high-risk tests, system shows historical OOS rates for that test | QCSOP 019 historical patterns |
| W13 | Narrative audit trail: human-readable timeline instead of table | Audit trail requirement |
| W13 | AI-generated compliance narrative for CoQ (`ai_summary`) | QCSOP 012 §A01.3 |
| W14 | 3-tier resilience across all agents | EU GMP Annex 11 §16 |
| W14 | Macedonian-language AI responses for all 5 agents | Bilingual requirement |
| W14 | RAG re-index with voyage-3 + Qdrant HNSW optimization | Performance (<5s) |
| W15 | AI confidence scores on all suggestions | GAMP 5 validation (AI advisory only) |
| W15 | Human verification gate: no AI decision is final | EU GMP: human remains decision-maker |

**Deliverable:** AI agents proactively assist at every workflow step, with transparent confidence scores, degraded but functional under failure, and always advisory.

### Phase P6: Bilingual UX & Inspection Readiness (Weeks 16-17)

**Goal:** System ready for Macedonian GMP inspector walkthrough.

| Week | Task | SOP Grounding |
|------|------|---------------|
| W16 | All UI strings in MK/EN with language toggle (persistent preference) | Bilingual requirement |
| W16 | All generated documents bilingual (COA, CoQ, OOS forms) | QCSOP 012 bilingual template |
| W16 | Narrative audit trail in both languages | Inspection evidence |
| W17 | Inspector read-only role with full search/export | EU GMP Annex 11 §audit |
| W17 | PDF/A export for all final documents | ALCOA++ Enduring (10+ years) |
| W17 | Signature verification portal: inspector can verify any digital signature | 21 CFR Part 11 §11.70 |
| W17 | System validation documentation (IQ/OQ/PQ protocols) | EU GMP Annex 11 §validation |

**Deliverable:** System is GMP inspection-ready with bilingual UI, PDF/A document generation, immutable audit trail, inspector role, and signature verification.

---

## 7. Completion Milestones: GMP Inspection Readiness

### Milestone 1: Internal COA Generation (End of Phase P3 — Week 9)

**Demonstration:**
1. QC Analyst logs in, scans sample barcode
2. System auto-populates all required tests from active specification (QCSOP 010)
3. Analyst enters results with keyboard navigation (<2 min for 50 parameters)
4. Reviewer sees results live, verifies 2nd person
5. QP signs with 2FA + declaration: "I certify batch [X] is suitable for release"
6. PDF/A COA generated, digitally signed, stored immutably
7. Full audit trail: every keystroke, every review, every signature — immutable

**SOP Coverage:** QCSOP 012 (COA) ✓, QCSOP 010 (Specs) ✓, QCSOP 011 (Sampling) ✓

### Milestone 2: External COA Ingestion (End of Phase P2 — Week 7)

**Demonstration:**
1. Upload eCoA PDF from contract lab
2. AI extracts all parameters, compares against PP specification
3. Annex A03 checklist auto-filled with conformance flags
4. Discrepancy auto-escalated to QC Manager
5. Full eCoA workflow tracked per QCSOP 012 §A01.2

**SOP Coverage:** QCSOP 012 §A01.2 ✓

### Milestone 3: OOS Lifecycle (End of Phase P4 — Week 12)

**Demonstration:**
1. Test result outside spec → OOS record auto-created
2. Phase I investigation form auto-populated with lab error checklist
3. Re-test gated: cannot proceed without approved Phase I
4. Phase II root cause analysis with CAPA linkage
5. OOS Register updated, notification sent per QCSOP 019-A04

**SOP Coverage:** QCSOP 019 §§Phase I, II ✓, QCSOP 019 Appendices A01-A04 ✓

### Milestone 4: Full GMP Inspection Readiness (End of Phase P6 — Week 17)

**Demonstration:**
1. Inspector logs in with read-only auditor role
2. Searches any batch, sample, COA, OOS record by date range
3. Views full audit trail with hash-chain integrity verification
4. Verifies any digital signature (who signed, when, what they attested to)
5. Exports any record as PDF/A with complete metadata
6. System validation documentation available: IQ/OQ/PQ protocols
7. All UI bilingual MK/EN with inspector's language preference preserved

**SOP Coverage:** All QCSOP documents ✓, EU GMP Annex 11 ✓, 21 CFR Part 11 ✓, ALCOA++ ✓

---

## 8. Risk Register & Mitigation

| Risk ID | Risk | Likelihood | Impact | Mitigation | Phase |
|---------|------|-----------|--------|-----------|-------|
| R1 | CoA_TRACK creates tech debt if ported without architectural cleanup | Medium | High | Refactor to Repository pattern + Pydantic schemas BEFORE integrating business logic (P0) | P0 |
| R2 | eCoA AI extraction misclassifies Macedonian-language CoAs | Medium | Critical | Ground-truth dataset of 11 real PP CoA examples (available in gmp_docs) for prompt tuning. Manual review gate always present. | P1 |
| R3 | Letta agent latency >5s during GMP audit | Low | High | 3-tier resilience (P5); pre-compute common queries to SQLite cache | P5 |
| R4 | Spec version at time of testing not preserved (data integrity violation) | Medium | Critical | Denormalized snapshot: COA stores `spec_at_time_of_testing` as JSONB, frozen at approval. Never references live spec. | P1 |
| R5 | User resistance: analysts prefer paper/Excel workflow | Medium | Medium | Transparent automation principle; keyboard navigation; no time-pressure UX; onboarding training with Letta SOP Writer agent | P3 |
| R6 | Scope creep: trying to build all 13 modules simultaneously | High | High | Phased roadmap: only P0 modules are COA + Sample + Spec + Audit + Auth. All others are P2+. | All |
| R7 | Missing SOPs (QCSOP 016, 022) block cannabinoid & chemical modules | Medium | Medium | Build with Ph. Eur. monograph defaults; flag as "pending SOP validation" until documents received | P2 |
| R8 | External lab doesn't follow communicated spec format | Medium | Low | Technical Quality Agreement (QCSOP 010 §6.7) defines format; AI extraction is format-tolerant | P1 |

---

## Appendix A: Code Inventory — What to Port Now

### Immediate (This Week — P0)

| Source | Destination | Action |
|---|---|---|
| `CoA_TRACK/app/models.py` L96-178 (Document) | `backend/app/models/certificate.py` | Port with UUID + new status enum |
| `CoA_TRACK/app/models.py` L181-222 (Parameter) | `backend/app/models/test_result.py` | Port with dual-field pattern + `complies` |
| `CoA_TRACK/app/models.py` L437-459 (SpecParameter) | `backend/app/models/spec_parameter.py` | Port with pharmacopoeia refs |
| `CoA_TRACK/app/routers/auth.py` L120-170 (Google OAuth) | `backend/app/api/auth.py` | Port endpoint |
| `CoA_TRACK/app/services/catalog_service.py` (entire file) | `backend/app/services/import_service.py` | Direct copy (stdlib XLSX parser) |
| `CoA_TRACK/app/ai/fallback.py` (entire file) | `backend/app/ai/fallback.py` | Direct copy |
| `CoA_TRACK/frontend/src/components/ESignatureModal.tsx` | `frontend/src/components/ESignatureModal.tsx` | Port as-is, then extend |
| `CoA_TRACK/frontend/src/components/PermissionGate.tsx` | `frontend/src/components/PermissionGate.tsx` | Port with GMP roles |
| `CoA_TRACK/frontend/src/components/StatusBadge.tsx` | `frontend/src/components/StatusBadge.tsx` | Port with SOP status list |
| `CoA_TRACK/frontend/src/components/SessionTimeoutProvider.tsx` | `frontend/src/providers/SessionTimeoutProvider.tsx` | Port with role-based timeout |
| `CoA_TRACK/frontend/src/components/DragDropUpload.tsx` | `frontend/src/components/DragDropUpload.tsx` | Port with PDF-only validation |

### Short-Term (Weeks 2-4 — P1)

| Source | Destination | Action |
|---|---|---|
| `CoA_TRACK/app/services/coa_service.py` (status mapping, search, pagination) | `backend/app/services/coa_service.py` | Adapt with SOP state machine |
| `CoA_TRACK/app/services/audit_service.py` (entity mapping, query patterns) | `backend/app/services/audit_service.py` | Merge with QC_LIMS AuditMiddleware |
| `CoA_TRACK/app/ai/prompts/extraction.py` | `backend/app/ai/prompts/extraction.py` | Port + add MK language prompts |
| `CoA_TRACK/app/ai/memory.py` | `backend/app/ai/memory.py` | Port for Letta agent memory |
| `CoA_TRACK/frontend/src/components/PdfViewer.tsx` | `frontend/src/components/PdfViewer.tsx` | Adapt for split-panel review |

### Medium-Term (Weeks 5-9 — P2-P3)

| Source | Destination | Action |
|---|---|---|
| `CoA_TRACK/app/services/coq_service.py` (647 lines) | `backend/app/services/coq_service.py` | Port with cross-document traceability |
| `CoA_TRACK/nginx/default.conf` | `nginx/default.conf` | Port with QC_LIMS paths |
| `CoA_TRACK/docker-compose.yml` | `docker-compose.yml` | Extend with Qdrant + Letta |

---

## Appendix B: New Development Required (Not in CoA_TRACK)

These are SOP-mandated modules that have no counterpart in CoA_TRACK and must be built from scratch:

| Module | SOP Basis | Key Models | Priority |
|---|---|---|---|
| **Internal COA Workflow** | QCSOP 012 §A01.1 | `InternalCOA`, `ResultEntry`, `VerificationRecord` | P0-P3 |
| **Sampling Plan Engine** | QCSOP 011-A01 | `SamplingPoint`, `SamplingTrigger`, `SampleSizeCalc` | P2 |
| **Specification Lifecycle Manager** | QCSOP 010 §§6.3-6.11 | `Specification`, `SpecApproval`, `SpecChangeRequest`, `MasterSpecRegister` | P1 |
| **Product Genealogy** | QCSP 003 | `IntermediaryProduct`, `ProductGenealogy`, `IPCParameter` | P2 |
| **OOS Investigation Engine** | QCSOP 019 | `OOSRecord`, `PhaseIInvestigation`, `PhaseIIInvestigation`, `CAPALinkage` | P4 |
| **Stability Study Manager** | QCSOP 018 | `StabilityStudy`, `PullSchedule`, `ChamberManagement` | Post-P6 |
| **Equipment Calibration Tracker** | QCSOP 008 | `Equipment`, `CalibrationRecord`, `DailyCheckLog` | Post-P6 |
| **Microbiological Monitoring** | QCSOP 023/024 | `EnvironmentalSample`, `MicrobialLimitsTest`, `EMLocation` | Post-P6 |
| **Inventory & Labeling** | QCSOP 025 | `InventoryItem`, `LabelTemplate`, `SegregationLog` | Post-P6 |

---

## Conclusion

This roadmap is **grounded in actual Purely Plant SOPs**, not generic regulatory frameworks. Every model field, state transition, calculation formula, and UI component is traceable to a specific SOP clause. The integration is phased to deliver working functionality at each milestone (not a "big bang" at the end), and the completion path leads directly to GMP inspection readiness with full EU GMP Annex 11 + ALCOA++ compliance.

**Total estimated timeline: 17 weeks (4 months)** from start to GMP inspection-ready system, assuming 1-2 developers with this roadmap as the implementation guide.

**Next action:** Begin Phase P0 — Alembic initialization + model port with UUID migration.
