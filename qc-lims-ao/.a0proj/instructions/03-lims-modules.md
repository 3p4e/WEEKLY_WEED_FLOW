# LIMS Modules — Specifications & SOP Mapping

## Module Overview

This document maps each LIMS module to its corresponding QCSOP document(s), EU GMP requirements, data model outline, and workflow. Every module must satisfy ALCOA++ data integrity principles and EU GMP Annex 11 computerised systems validation.

---

## 1. Sample Management Module

**SOP Basis**: QCSOP 011 (Sampling), QCSOP 001 (Department Activities)

### Scope
- Raw material sampling (incoming cannabis flower, packaging materials)
- In-process control (IPC) sampling during production
- Finished product sampling for release testing
- Stability pull samples
- Water system sampling

### Data Model
```python
class Sample:
    id: UUID (primary key)
    sample_id: str  # PP-SMP-YYYY-NNNN
    batch_id: ForeignKey -> Batch
    sample_type: enum[RAW_MATERIAL, IPC, FINISHED_PRODUCT, STABILITY, WATER, ENVIRONMENTAL]
    material_name: str  # Bilingual MK/EN
    material_code: str
    sampling_date: datetime
    sampled_by: ForeignKey -> User
    sampling_plan: ForeignKey -> SamplingPlan
    status: enum[COLLECTED, IN_TEST, TESTED, APPROVED, REJECTED, STABILITY]
    location: str  # Storage location
    quantity: float
    quantity_unit: str
    retention_sample: bool
    retention_expiry: date
    created_at: datetime (UTC, server-generated)
    updated_at: datetime
```

### Sampling Plan Model
```python
class SamplingPlan:
    id: UUID
    material_code: str
    sampling_frequency: enum[EVERY_BATCH, PERIODIC, RANDOM]
    sample_size: float
    sample_size_unit: str
    sampling_points: list[str]  # Specific locations
    test_required: list[ForeignKey -> TestMethod]
    active: bool
    effective_date: date
    version: int
```

### Workflow
1. Sample request created (linked to batch or schedule)
2. Label generated with unique sample ID (QR/barcode)
3. Collection logged: date, sampler, quantity, location
4. Chain of custody: each transfer logged with signatures
5. Test assignment: test methods assigned per specifications
6. Result entry by Analyst → 2nd person verification → Reviewer approval
7. Decision: Pass/Reject/Retest/OOS
8. Retention sample tracking (if applicable, per QCSOP 011)

### UI Requirements
- Dashboard: Pending collections, in-progress tests, overdue samples
- Sample lifecycle timeline view
- QR/barcode label printing
- Batch-to-sample relationship navigator

---

## 2. Specification Management Module

**SOP Basis**: QCSOP 010 (Specification Issuance)

### Scope
- Finished product specifications (cannabis flower)
- Raw material specifications
- Packaging material specifications
- In-process control limits

### Data Model
```python
class Specification:
    id: UUID
    spec_id: str  # PP-SPEC-YYYY-NNNN
    material_code: str
    material_name: str  # Bilingual MK/EN
    material_type: enum[RAW, FINISHED, PACKAGING, IPC]
    version: int
    effective_date: date
    expiry_date: date | None
    status: enum[DRAFT, ACTIVE, SUPERSEDED, WITHDRAWN]
    approved_by: ForeignKey -> User
    approved_date: datetime
    parameters: list[SpecParameter]
```

```python
class SpecParameter:
    id: UUID
    specification_id: ForeignKey -> Specification
    test_name: str  # Bilingual MK/EN (e.g., "Loss on Drying", "Губење при сушење")
    test_method: ForeignKey -> TestMethod
    specification_type: enum[NUMERIC_BOUNDED, NUMERIC_MAX, NUMERIC_MIN, CATEGORICAL, TEXT]
    lower_limit: float | None
    upper_limit: float | None
    unit: str
    categorical_values: list[str] | None
    pharmacopoeia_ref: str | None  # e.g., "Ph. Eur. 2.02.12"
    sorting_order: int
```

### Cannabinoid Spec Parameters (per QCSOP 016 / Ph. Eur. 2.08.10)
| Parameter | Lower | Upper | Unit |
|-----------|-------|-------|------|
| THC | — | 1.0 | % w/w |
| CBD | 5.0 | 15.0 | % w/w |
| CBG | — | 1.0 | % w/w |
| CBC | — | 1.0 | % w/w |
| CBN | — | 0.2 | % w/w |
| THCV | — | 1.0 | % w/w |
| Total Cannabinoids | 8.0 | 20.0 | % w/w |
| Loss on Drying | — | 10.0 | % w/w |

### Workflow
1. Spec draft created by QC Analyst
2. Reviewed by QC Manager
3. Approved by QP (Qualified Person)
4. Becomes active on effective date
5. Previous version marked SUPERSEDED
6. All changes trigger Change Control (CAPA workflow)

### ALCOA++ Compliance
- Immutable version history — no edits to approved specs
- Change reason mandatory for new versions
- Date-effective specification at time of testing preserved in COA

---

## 3. Certificate of Analysis (COA) Generation Module

**SOP Basis**: QCSOP 012 (COA Issuance), QCCoA 001 (Template)

### Scope
- Finished product COA for release
- Raw material COA (review from supplier)
- Water system COA
- Stability study COA

### Data Model
```python
class CertificateOfAnalysis:
    id: UUID
    coa_number: str  # PP-COA-YYYY-NNNN
    batch_id: ForeignKey -> Batch
    specification_id: ForeignKey -> Specification
    report_date: date
    analyst: ForeignKey -> User
    reviewer: ForeignKey -> User
    approver: ForeignKey -> User (QP role)
    status: enum[DRAFT, REVIEWED, APPROVED, RELEASED]
    results: list[TestResult]
    decision: enum[PASS, FAIL, CONDITIONAL]
    pdf_path: str | None
    digital_signature_hash: str
    created_at: datetime
    released_at: datetime | None
```

```python
class TestResult:
    id: UUID
    coa_id: ForeignKey -> CertificateOfAnalysis
    parameter: ForeignKey -> SpecParameter
    value: str  # Raw result value
    unit: str
    specification: str  # Snapshot of spec limits at time of testing
    complies: bool
    method_ref: str
    instrument_id: str | None
    result_date: datetime
    analyst: ForeignKey -> User
    reviewer: ForeignKey -> User
    remarks: str | None
```

### Workflow
1. Test results entered for all specification parameters
2. Auto-comparison against active specification (pass/fail determination)
3. 2nd person verification of all analytical results
4. COA PDF generated (python-docx → Gotenberg PDF)
5. Reviewer checks completeness and compliance
6. QP approves for release
7. COA digitally signed (two-component electronic signature)
8. PDF stored immutably (PDF/A format)

### PDF Layout (based on QCCoA 001)
- Header: Company logo, COA number, QP signature block
- Product/Batch information section
- Test parameters table: Parameter | Specification | Result | Compliance
- Decision statement
- Digital signature lines: Analyst, Reviewer, QP
- Footer: Document number, page X of Y, issue date

---

## 4. Stability Studies Module

**SOP Basis**: QCSOP 018 (Stability Studies)

### Scope
- Long-term stability (25°C/60% RH)
- Accelerated stability (40°C/75% RH)
- Intermediate conditions
- Photostability
- In-use stability

### Data Model
```python
class StabilityStudy:
    id: UUID
    study_id: str  # PP-STB-YYYY-NNNN
    batch_id: ForeignKey -> Batch
    study_type: enum[LONG_TERM, ACCELERATED, INTERMEDIATE, PHOTO, IN_USE]
    conditions: str  # e.g., "25°C ± 2°C / 60% RH ± 5%"
    start_date: date
    end_date: date
    duration_months: int
    pull_schedule: list[PullPoint]
    status: enum[ACTIVE, COMPLETED, TERMINATED]
    chamber_id: str | None
    protocol_ref: str
```

```python
class PullPoint:
    id: UUID
    study_id: ForeignKey -> StabilityStudy
    month: int  # 0, 1, 3, 6, 9, 12, 18, 24, 36
    scheduled_date: date
    pulled_date: date | None
    pulled_by: ForeignKey -> User | None
    status: enum[SCHEDULED, PULLED, TESTED, COMPLETED]
    results: list[TestResult]
```

### Regulatory Requirements
- Pull schedule follows ICH Q1A/Q1B
- Zero-time data (month 0) established before stability start
- 10+ years retention for stability records (per EU GMP)
- Temperature/RH excursion handling per QCSOP 018

### Feature Requirements
- Automated pull point generation from study parameters
- Dashboard: upcoming pulls (30-day, 7-day, overdue)
- Temperature excursion alerting
- Trending: parameter vs. time charts for each study

---

## 5. OOS Investigation Module

**SOP Basis**: QCSOP 019 + Appendices A01–A04

### Scope
- Out-of-Specification results for finished product testing
- OOS for in-process controls
- OOS for stability time points
- Out-of-Trend (OOT) detection

### Investigation Phases (per QCSOP 019)

**Phase I — Laboratory Investigation**
- Analyst identifies OOS result
- Immediate notification to QC Manager
- Laboratory investigation within 1 working day
- Check: calculations, dilutions, equipment, standards, analyst technique
- If assignable lab error → invalidate OOS, retest (documented)

**Phase II — Full Investigation**
- If no lab error identified
- CAPA initiated (deviation investigation)
- Root cause analysis (Fishbone / 5-Whys)
- Impact assessment on other batches
- CAPA effectiveness check at defined interval

### Data Model
```python
class OOSRecord:
    id: UUID
    oos_number: str  # PP-OOS-YYYY-NNNN
    test_result_id: ForeignKey -> TestResult
    detection_date: datetime
    detected_by: ForeignKey -> User
    specification_value: str
    obtained_value: str
    deviation_percentage: float
    phase: enum[I, II]
    status: enum[OPEN, PHASE_I, PHASE_II, CLOSED]
    
    # Phase I fields
    lab_investigation_complete: bool
    lab_investigation_result: enum[LAB_ERROR, NO_LAB_ERROR]
    lab_error_description: str | None
    invalidated: bool
    retest_result: str | None
    
    # Phase II fields
    root_cause_category: str | None
    root_cause_description: str | None
    impact_assessment: str | None
    capa_reference: str | None
    effectiveness_check_date: date | None
    effectiveness_check_result: str | None
    
    # Attachments
    phase_i_form: ForeignKey -> Document (QCSOP 019-A01)
    phase_ii_form: ForeignKey -> Document (QCSOP 019-A02)
    
    created_at: datetime
    closed_at: datetime | None
    closed_by: ForeignKey -> User | None
```

### Letta AI Integration
- **CAPA Manager Agent** guides analyst through Phase I/II investigation
- Suggest possible root causes based on historical OOS patterns
- Auto-generate investigation forms (A01/A02/A03/A04)
- RAG search over past OOS records for similar patterns

---

## 6. Audit Trail Module (ALCOA++ / EU GMP Annex 11)

### Core Principle
Every CREATE, UPDATE, DELETE, VIEW, APPROVE, REJECT, SIGN, EXPORT, PRINT operation on any GxP-relevant record must be logged immutably.

### Data Model
```python
class AuditEntry:
    id: UUID
    timestamp: datetime  # UTC + local time offset
    user_id: ForeignKey -> User
    user_full_name: str
    action: enum[CREATE, UPDATE, DELETE, VIEW, APPROVE, REJECT, SIGN, EXPORT, PRINT]
    record_type: str  # e.g., "coa", "test_result", "specification", "oos_record"
    record_id: UUID
    record_identifier: str  # Human-readable ID
    field_name: str | None
    old_value: str | None  # Encrypted at rest
    new_value: str | None
    reason: str | None  # Required for critical changes
    ip_address: str
    session_id: str
    digital_signature_hash: str | None  # Hash chain
```

### Audit Trail Requirements
- **Immutable**: No UPDATE or DELETE operations on audit table
- **Tamper-evident**: Hash chain linking each entry to previous (SHA-256)
- **Complete**: Records all relevant actions including VIEW for sensitive data
- **Accessible**: Read-only access for QA/Regulatory/Auditors
- **Searchable**: Filter by date range, user, record type, action
- **Exportable**: PDF/A export for regulatory submission
- **Retention**: Minimum 10 years (EU GMP), with integrity verification

---

## 7. Water System QC Module

**SOP Basis**: QCSOP 014 (pending upload — Water System Sampling & QC)

### Scope
- Purified Water (PW) sampling points
- Water for Injection (WFI) if applicable
- Testing: Conductivity, TOC, Microbial limits, Endotoxins (if WFI)
- Action/Alert limit trending

### Data Model (Initial — refine once QCSOP 014 uploaded)
```python
class WaterSample:
    id: UUID
    sample_point: str  # e.g., "PW-001", "PW-RO-01"
    sample_type: enum[ROUTINE, AFTER_SANITIZATION, INVESTIGATIONAL]
    sampling_date: datetime
    conductivity: float  # µS/cm @ 25°C
    toc: float  # µg/L
    microbial_count: int  # CFU/mL
    endotoxin: float | None  # EU/mL (WFI only)
    temperature: float  # °C at time of measurement
    alert_limit_conductivity: float
    action_limit_conductivity: float
    alert_limit_toc: float
    action_limit_toc: float
    complies: bool
    sampled_by: ForeignKey -> User
    status: enum[PENDING, TESTED, REVIEWED, APPROVED]
```

### Trending & Reporting
- Weekly/monthly trend charts per sample point
- Alert/action limit exceedance notifications
- Annual water quality review report

---

## 8. Microbiological Monitoring Module

**SOP Basis**: QCSOP 023 (Environmental Monitoring), QCSOP 024 (Microbiological Analysis)

### Scope
- Air monitoring (active/passive): settle plates, volumetric air samplers
- Surface monitoring: contact plates, swabs
- Personnel monitoring: gloved hand plates, gowning verification
- Grade classification: A, B, C, D (per Annex 1)
- Microbial limits testing of finished product

### Data Model
```python
class EnvironmentalSample:
    id: UUID
    sample_id: str  # PP-EM-YYYY-NNNN
    location: str  # Room + specific location
    monitoring_type: enum[AIR_ACTIVE, AIR_PASSIVE, SURFACE, PERSONNEL]
    grade: enum[A, B, C, D]
    sampling_date: datetime
    media_type: str  # e.g., "TSA", "SDA"
    incubation_temp: float  # °C
    incubation_time: int  # hours
    result_cfu: int  # Colony Forming Units
    action_limit: int
    alert_limit: int
    organism_identified: str | None
    complies: bool
    sampled_by: ForeignKey -> User
    status: enum[IN_TEST, IN_READING, READ, REVIEWED]
```

### Microbial Limits Testing (QCSOP 024)
| Test | Method | Enumeration | Spec Limit |
|------|--------|-------------|------------|
| TAMC | Ph. Eur. 2.06.13 | Total Aerobic Microbial Count | < 10^5 CFU/g |
| TYMC | Ph. Eur. 2.06.13 | Total Yeast & Mould Count | < 10^4 CFU/g |
| S. aureus | Ph. Eur. 2.06.14 | Detection | Absent in 1g |
| P. aeruginosa | Ph. Eur. 2.06.14 | Detection | Absent in 1g |
| E. coli | Ph. Eur. 2.06.14 | Detection | Absent in 1g |
| Salmonella | Ph. Eur. 2.06.14 | Detection | Absent in 10g |
| B. cepacia | Ph. Eur. 2.06.14 | Detection | Absent in 1g |
| C. albicans | Ph. Eur. 2.06.14 | Detection | Absent in 1g |

### Trending Requirements
- Rolling monthly/quarterly trend reports per location
- Alert/action limit exceedance alerting
- Annual environmental monitoring review
- Seasonal pattern analysis

---

## 9. Cannabinoid Testing Module

**SOP Basis**: QCSOP 016 (pending upload), Ph. Eur. 2.08.10

### Scope
- Quantitative cannabinoid profile by HPLC-DAD
- Qualitative identification of major cannabinoids
- Sample preparation: extraction with methanol/acetonitrile
- System suitability: resolution, tailing factor, RSD of standards

### Data Integration
- Manual entry (for early deployment)
- Future: LIMS → Chromeleon/Empower data export parsing
- Calculated parameters:
  - Moisture-adjusted cannabinoid content
  - Total THC = THC + (THCA × 0.877)
  - Total CBD = CBD + (CBDA × 0.877)

---

## 10. Equipment Calibration Module

**SOP Basis**: QCSOP 008 (Measurement Traceability)

### Scope
- Analytical balances (daily routine testing, calibration)
- pH meters
- Conductivity meters
- HPLC/GC systems
- Temperature sensors (stability chambers, refrigerators)
- Pipettes and volumetric equipment

### Data Model
```python
class Equipment:
    id: UUID
    equipment_id: str  # PP-EQ-YYYY-NNNN
    name: str  # Bilingual MK/EN
    type: enum[BALANCE, PH_METER, CONDUCTIVITY, HPLC, GC, TEMPERATURE, PIPETTE, VOLUMETRIC]
    manufacturer: str
    model: str
    serial_number: str
    location: str
    calibration_frequency_days: int
    last_calibration_date: date
    next_calibration_date: date
    status: enum[ACTIVE, CALIBRATION_DUE, OVERDUE, OUT_OF_SERVICE, RETIRED]
    daily_check_required: bool
```

---

## 11. Labeling & Inventory Module

**SOP Basis**: QCSOP 025 (Labeling, Segregation, Inventory Control)

### Scope
- Chemical/reagent inventory
- Reference standard tracking
- Column inventory (HPLC/GC)
- Media and consumables
- Waste management tracking (QCSOP 004)

---

## 12. User Management & Roles

**SOP Basis**: QCSOP 001 (Department Activities), QCSOP 005 (Workwear/PPE)

### Roles (per Annex 11 + QCSOP 001)
| Role | Permissions | Training Required |
|------|------------|-------------------|
| **System Admin** | Full configuration, user management | Annex 11 validation training |
| **QC Analyst** | Enter results, view specifications | GMP + analytical methods training |
| **QC Reviewer** | Review results, verify entries | Analyst qualification + 2nd person check training |
| **QC Manager** | Approve results, manage investigations | GMP management training |
| **Qualified Person (QP)** | Release batches, approve COAs | QP certification (EU GMP Art. 51) |
| **QA Auditor** | Read-only access to all records | GMP auditing qualification |

### Authentication Requirements
- Password: min 8 chars, complexity, 90-day expiry
- MFA for release/approve/reject actions
- Automatic lockout after 5 failed attempts
- Inactivity timeout: 15 minutes

---

## 13. AI-Assisted QMS Module (Letta Integration)

### Agents
| Agent | Purpose | Data Source |
|-------|---------|-------------|
| GMP Expert | Answers compliance questions, cites SOP clauses | Regulatory RAG + SOP docs |
| SOP Writer | Drafts new/revised SOPs in bilingual format | SOP templates RAG |
| CAPA Manager | Guides OOS investigation, suggests root causes | OOS records RAG |
| Risk Assessor | FMEA-based risk assessment for deviations | Risk templates RAG |
| QMS Orchestrator | Routes user requests to specialist agents | All collections |

### Integration Points
- **QA Dashboard**: "Ask GMP Expert" query field
- **OOS Form**: Auto-suggest root cause categories from historical data
- **SOP Creation**: Draft SOP from spec → AI generates bilingual content
- **Training**: Letta agents can answer GMP questions in training context

---

## Implementation Priority

| Priority | Module | Dependencies | SOP Status |
|----------|--------|--------------|------------|
| P0 | Sample Management + Chain of Custody | None | QCSOP 011 available |
| P0 | COA Generation | Sample Mgmt, Spec Mgmt | QCSOP 012 available |
| P0 | Specification Management | None | QCSOP 010 available |
| P1 | Audit Trail | User Mgmt | Annex 11 req. |
| P1 | User Management | None | QCSOP 001 available |
| P1 | OOS Investigation | Sample Mgmt, Spec Mgmt | QCSOP 019 available |
| P2 | Water System QC | Sample Mgmt | **QCSOP 014 pending** |
| P2 | Microbiological Monitoring | Sample Mgmt | QCSOP 023/024 available |
| P2 | Cannabinoid Testing | Spec Mgmt, COA | **QCSOP 016 pending** |
| P3 | Stability Studies | Sample Mgmt, COA | QCSOP 018 available |
| P3 | Equipment Calibration | None | QCSOP 008 available |
| P3 | Inventory/Labeling | None | QCSOP 025 available |
| P4 | AI QMS (Letta Agents) | All modules | Requires RAG ingest |