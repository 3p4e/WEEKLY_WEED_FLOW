# EU GMP Regulatory Compliance Framework — QC LIMS

## Applicable Regulations & Guidelines

### 1. EU GMP — EudraLex Volume 4 (EU Guidelines for Good Manufacturing Practice)

The primary regulatory framework. Key annexes for this LIMS:

| Annex | Title | LIMS Impact |
|-------|-------|-------------|
| **Annex 1** | Manufacture of Sterile Medicinal Products (applied to cannabis flower — cleanroom principles) | Environmental monitoring schedules, alert/action limits, room classification tracking |
| **Annex 11** | Computerised Systems | **Critical**: Validation of LIMS + audit trail + data integrity + user access control + backup/restore |
| **Annex 15** | Qualification & Validation | Process validation data, cleaning validation records, method validation |
| **Annex 16** | Certification by QP & Batch Release | QP review workflow, batch release decision, COA signing |

### 2. ICH Q10 — Pharmaceutical Quality System

| Element | LIMS Feature |
|---------|-------------|
| Process performance & product quality monitoring | Trending charts, statistical process control (SPC) |
| Corrective & Preventive Action (CAPA) system | OOS → CAPA workflow, root cause tracking, effectiveness checks |
| Change management system | Spec versioning, method updates, document revision control |
| Quality risk management | Risk assessment templates, FMEA integration for critical processes |

### 3. Data Integrity — ALCOA++ (Foundation: WHO TRS 996, MHRA Guidance, PIC/S PI-041)

All LIMS data entry must satisfy:

| Principle | Meaning | LIMS Implementation |
|-----------|---------|---------------------|
| **A**ttributable | Who performed an action & when | Digital signature, user login, timestamped audit trail |
| **L**egible | Permanently readable | Print-friendly COAs, clear UI, no overwriting |
| **C**ontemporaneous | Recorded at time of activity | Real-time data entry, no backdating, locked timestamps |
| **O**riginal | First record or certified copy | Immutable raw data store, PDF/A for final reports |
| **A**ccurate | Free from errors | Validation of results (2nd person check), range checks, limits validation |
| **+ Complete** | All data, including repeats & recalculations | Full metadata logging, re-injection tracking, recalculation history |
| **+ Consistent** | Chronological sequencing of events | Session UUIDs, logical clock ordering, no gaps in data stream |
| **+ Enduring** | Available for full record retention period (10+ years) | Regular backups, off-site archive, migration-ready format |
| **+ Available** | Accessible for review/audit throughout retention | Fast search, structured queries, read-only audit user role |

### 4. 21 CFR Part 11 (US — Applicable as Benchmark for Electronic Records)

Even though the facility follows EU GMP, Part 11 provides the most mature standard for electronic records/signatures:

- **§11.10**: Validation, audit trail, authority checks, device checks
- **§11.30**: Legacy system controls
- **§11.50**: Signed electronic records must include: printed name, date/time, meaning of signature
- **§11.70**: Signatures linked to records to prevent falsification
- **§11.100**: Electronic signatures uniquely tied to individuals
- **§11.200**: Two distinct identification components (e.g., password + SMS/2FA)

### 5. EU Pharmacopoeia (Ph. Eur.) — Cannabis Testing Methods

| Ph. Eur. Monograph | Method | LIMS Data Capture |
|--------------------|--------|-------------------|
| 2.02.12 | Loss on Drying | Moisture balance readings, % loss calculation |
| 2.02.32 | Water by Karl Fischer | Titrator output, water content (if applicable) |
| 2.04.05 | Heavy Metals | ICP-MS/OES results, spec limits |
| 2.06.13 | Microbiological Examination of Non-sterile Products | TAMC, TYMC, specified pathogens (S. aureus, P. aeruginosa, E. coli, Salmonella, B. cepacia, C. albicans) |
| 2.06.14 | Test for Specified Micro-Organisms | Pathogen detection with confirmation steps |
| 2.08.10 | Cannabinoid Profile by HPLC | CBD, THC, CBG, CBC, CBN, THCV — quantitative and qualitative |
| 2.08.11 | Terpene Profile by GC | α-pinene, β-myrcene, limonene, linalool, etc. |
| 2.08.12 | Residual Solvents by GC-HS | Class 1, 2, 3 solvent limits per ICH Q3C |
| 2.08.13 | Mycotoxins (Aflatoxins B1, B2, G1, G2; Ochratoxin A) | LC-MS/MS quantification |
| 2.08.14 | Pesticide Residues | GC-MS/MS / LC-MS/MS — 200+ pesticide screening |

### 6. WHO TRS 902 Annex 9 — Guidance on GMP for Herbal Medicinal Products

Applicable as cannabis is classified as a herbal medicinal product:
- **Section 4.8**: Quality control of starting materials (botanical identity, purity)
- **Section 5.3**: Stability testing of herbal preparations
- **Section 6.1**: Documentation requirements specific to botanical products

---

## LIMS Validation Requirements (per EU GMP Annex 11)

### Validation Scope

| Category | Systems | Validation Level |
|----------|---------|-----------------|
| 1 — Infrastructure | OS, Database (PostgreSQL) | IQ (Installation Qualification) |
| 2 — Non-configured | Fixed logic (e.g., printer driver) | IQ only |
| 3 — Configured | LIMS forms, user roles, workflows, templates | IQ + OQ (Operational Qualification) |
| 4 — Complex/Custom | AI-powered QMS, Letta agents, RAG pipeline, auto-COA generation | IQ + OQ + PQ (Performance Qualification) + periodic review |

### Key Validation Documents

1. **URS** (User Requirements Specification) — What the LIMS must do
2. **FS** (Functional Specification) — How the LIMS meets each URS
3. **DS** (Design Specification) — Technical architecture, data flows, UI design
4. **RA** (Risk Assessment) — GAMP 5 risk-based approach per Annex 20
5. **IQ/OQ/PQ Protocols** — Test scripts with pass/fail criteria
6. **Validation Report** — Summary of all testing and approval for release

### 21 CFR Part 11 Compliant Audit Trail Requirements

Every LIMS transaction must record:
```yaml
audit_entry:
  timestamp: ISO 8601 (UTC + local time)
  user_id: string
  action_type: enum[CREATE, UPDATE, DELETE, VIEW, APPROVE, REJECT, SIGN, EXPORT, PRINT]
  record_id: string (UUID v4)
  record_type: string (e.g., "test_result", "specification", "coa")
  field_name: string | null
  old_value: string | null  # Encrypted at rest, viewable only by audit role
  new_value: string | null
  reason: string | null      # Required for critical changes
  digital_signature: string  # Hash chain linking to previous entry
  ip_address: string
  session_id: string
```

---

## Compliance Checklist for Every LIMS Module

- [ ] **User authentication**: Password complexity + MFA + automatic lockout (5 failed attempts)
- [ ] **Role-based access**: Admin, Analyst, Reviewer, Approver, QP, Auditor (read-only), System Admin
- [ ] **Electronic signatures**: Two-component (password + token) for release/approve/reject
- [ ] **Audit trail**: Immutable, WORM (Write Once Read Many) storage, not modifiable by any role
- [ ] **Data backup**: Daily incremental + weekly full backup with restore testing documented quarterly
- [ ] **Time synchronization**: NTP + all timestamps in UTC with local time offset stored separately
- [ ] **Input validation**: Range checks, type enforcement, mandatory fields, 2nd person verification for critical data
- [ ] **Change control**: Any configuration change must trigger CAPA workflow
- [ ] **Archival**: Records retained 10+ years with migration plan for format obsolescence
- [ ] **Business continuity**: Disaster recovery plan tested annually, RPO ≤ 1 hour, RTO ≤ 24 hours