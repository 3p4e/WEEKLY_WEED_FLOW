# Cannabis EU GMP QMS - Full Build-Out Work Plan

**Strategic Direction**: Option 3 - Full Build-Out (40 weeks to 100% completion)
**QP**: Azu Sozo, Master Pharmacist
**Facility**: Purely Plant GmbH, Skopje, North Macedonia
**Language**: English-only (translate later)
**Start Date**: January 13, 2026
**Target Completion**: October 2026

---

## 📊 Full Build-Out Overview

### Scope
- **Total Documents**: 213 SOPs + Annexes
- **Timeline**: 40 weeks (10 months)
- **Effort**: 850 hours total ≈ 21 hours/week
- **Language**: English-only initially
- **Deliverables**: Complete GMP-compliant QMS ready for EU certification

### Current Status
- **Existing**: 32 documents (15% complete)
- **In Progress**: 18 documents being developed
- **Target**: 213 documents (100% complete)

---

## 🗓️ Week 1 Work Plan (January 13-19, 2026)

### Package C: Update Facility Data ⏱️ 1 hour
**Priority**: Foundation - do this FIRST

**Tasks**:
1. ✅ Export facility_data.yaml to Excel
2. ⏳ **Azu**: Fill in real Purely Plant data:
   - Company registration details (GmbH/DOOEL legal entity)
   - GMP license number and effective date
   - GACP certification number
   - Real personnel names (QP, Facility Manager, QA Manager, QC Head, Production Manager, etc.)
   - Actual equipment models and serial numbers
   - Real facility room dimensions and GMP classifications
   - Contact information (phone, email)
3. ✅ Import updated Excel back to YAML
4. ✅ Test automation system with real data
5. ✅ Regenerate all 26 documents
6. ✅ Generate professional PDFs
7. ✅ Validate completeness

**Deliverable**: Automation system generating real Purely Plant documents

---

### Package B: Format Existing 14 SOPs ⏱️ 56 hours

#### Phase B1: Fully Developed SOPs (4 SOPs, 24 hours)

**B1.1: Batch Release SOP (SOP-BRR-001) → QC-01-001** ⏱️ 6 hours
- Extract from conversation history
- Format to pharmaceutical template
- Integrate 6 existing annexes:
  - A01: Batch Record Review Checklist
  - A02: Analytical Data Review Form
  - A03: QP Certification Template
  - A04: Batch Release Decision Matrix
  - A05: Release Non-Conformance Protocol
  - A06: Batch Retention Sample Log
- Add regulatory citations (EudraLex Vol 4 Chapter 6, Ph.Eur. 3028)
- Create .docx with GMP formatting
- Add to automation system template

**B1.2: Plant Health Monitoring → PRO-01-004** ⏱️ 10 hours
- Consolidate 8 phase-specific logs into master SOP
- Create master PRO-01-004 Plant Health Monitoring SOP
- Format 8 annexes:
  - A01: Cloning/Rooting Phase Log
  - A02: Vegetative Phase Log
  - A03: Flowering Phase Log
  - A04: Harvest Readiness Assessment Log
  - A05: Mother Plant Monitoring Log
  - A06: Selection/R&D Plant Log
  - A07: Cultivation Phase Summary Log
  - A08: Plant Health Monitoring Plan Template
- Add regulatory citations (GACP, EMA GACP Guideline)
- Create professional .docx package
- Add to automation templates

**B1.3: Out-of-Expected Investigation → QC-01-005** ⏱️ 4 hours
- Extract existing OOx investigation procedures
- Format to QC SOP structure
- Add annexes:
  - A01: OOx Investigation Protocol
  - A02: Root Cause Analysis Template
  - A03: Risk-Based Timeline Matrix (HIGH 20d, MEDIUM 30d, LOW 15d)
- Add regulatory citations (FDA OOS Guidance, EudraLex Vol 4)
- Format to .docx
- Add to automation system

**B1.4: Water Quality Management → QC-01-011** ⏱️ 4 hours
- Extract existing water quality SOP
- Format with Ph.Eur. compliance citations (2.2.42-44)
- Add annexes:
  - A01: Water Sampling Procedure ("no flush after sanitisation")
  - A02: Water Quality Monitoring Log
  - A03: Alert/Action Limit Investigation Protocol
- Format to .docx
- Add to automation templates

#### Phase B2: Complete SOPs (4 SOPs, 16 hours)

**B2.1: Transport & Logistics → LOG-01-002** ⏱️ 4 hours
- Extract existing transport SOPs
- Format with IATA compliance
- Add annexes:
  - A01: Controlled Substance Transport Procedure
  - A02: Temperature Monitoring Requirements
  - A03: Third-Party Logistics Qualification
  - A04: Transport Documentation Checklist
- Add regulatory citations (GDP, IATA)
- Format to .docx

**B2.2: Reagent Storage → QC-01-007** ⏱️ 3 hours
- Extract existing reagent storage procedures
- Expand to include solution preparation
- Add annexes:
  - A01: Reagent Storage Conditions Matrix
  - A02: Reagent Receipt and Qualification Log
  - A03: Expiry Date Tracking System
  - A04: Disposal Procedure
- Add Ph.Eur. citations
- Format to .docx

**B2.3: Memorandum Control → REC-01-003** ⏱️ 3 hours
- Extract existing memorandum control procedures
- Format to Records Management SOP structure
- Add annexes:
  - A01: Memorandum Template
  - A02: Distribution Log
  - A03: Archive Procedure
- Add EudraLex Chapter 4 citations
- Format to .docx

**B2.4: Curing Process Monitoring → PRO-01-007** ⏱️ 6 hours
- Extract existing curing monitoring records
- Convert to full SOP structure
- Add annexes:
  - A01: Curing Environmental Control Parameters (17-23°C, 50-55% RH)
  - A02: 7-Day Cycle Monitoring Log
  - A03: Quality Assessment Criteria
  - A04: Data Logger Qualification
- Add GACP and Ph.Eur. 3028 citations
- Format to .docx

#### Phase B3: Partially Developed SOPs (6 SOPs, 16 hours)

**B3.1: Equipment Calibration → EQU-01-002** ⏱️ 3 hours
- Extract existing GWP principles and weighing procedures
- Expand to general equipment calibration
- Add annexes:
  - A01: Calibration Schedule Matrix
  - A02: Calibration Procedure by Equipment Type
  - A03: Calibration Certificate Template
  - A04: Out-of-Tolerance Investigation
- Add ISO 17025, GWP citations
- Format to .docx

**B3.2: HVAC System Operation → EQU-01-004** ⏱️ 4 hours
- Extract AHU-5 qualification work (URS, IQ/OQ/PQ, TCC-HVAC-AHU5-2025-001)
- Convert to operational SOP (not qualification protocol)
- Add annexes:
  - A01: HVAC Operating Parameters
  - A02: Daily/Weekly/Monthly Checks
  - A03: Alarm Response Procedure
  - A04: Preventive Maintenance Schedule
  - A05: Change Control Integration
- Add EudraLex Annex 1 citations
- Format to .docx

**B3.3: Drying SOP → PRO-01-006** ⏱️ 3 hours
- Extract environmental control work (psychrometric calculations, drying room management)
- Create drying process SOP
- Add annexes:
  - A01: Drying Environmental Parameters (17-23°C, 50-55% RH)
  - A02: Moisture Load Calculations
  - A03: 7-Day Drying Cycle Protocol
  - A04: Quality Assessment Criteria
- Add GACP and Ph.Eur. 3028 citations
- Format to .docx

**B3.4: Stability Studies → QC-01-009** ⏱️ 3 hours
- Extract thesis methodology (kinetic analysis, Arrhenius modeling)
- Convert to SOP format
- Add annexes:
  - A01: Stability Study Protocol Template
  - A02: Long-Term Conditions (25°C/60% RH)
  - A03: Accelerated Conditions (40°C/75% RH)
  - A04: Statistical Analysis Method
  - A05: Kinetic Modeling Procedure
- Add ICH Q1A-F citations
- Format to .docx

**B3.5: Cultivation Master SOP → PRO-01-003** ⏱️ 6 hours
- Consolidate existing work (cloning, vegetative, flowering, mother plants)
- Create comprehensive master cultivation SOP
- Add annexes:
  - A01: Cloning/Propagation Procedure
  - A02: Vegetative Phase Management
  - A03: Flowering Phase Protocol
  - A04: Mother Plant Maintenance
  - A05: Environmental Control Parameters
  - A06: Nutrient Management
- Add GACP citations
- Format to .docx

**B3.6: R&D/Phenotype Selection → PRO-01-012** ⏱️ 3 hours
- Extract selection plant monitoring protocols
- Format R&D procedures
- Add annexes:
  - A01: Phenotype Selection Criteria
  - A02: Selection Plant Monitoring Log
  - A03: Trait Evaluation Matrix
  - A04: Selection Decision Documentation
- Add GACP citations
- Format to .docx

**Package B Total**: 14 SOPs formatted, 56 hours effort

---

### Package A: Create New Critical SOPs ⏱️ 34 hours

**A1: Document Control SOP (QAS-00-002)** ⏱️ 12 hours
- **Regulatory Basis**: EudraLex Vol 4 Chapter 4 - Documentation
- **Source**: `/EudraLex/chapter4_01-2011_en - Documentation.pdf`
- **Structure**:
  1. Purpose & Scope
  2. Definitions
  3. Responsibilities
  4. Document Lifecycle (creation, review, approval, distribution, archival)
  5. Document Numbering System (12-chapter code structure)
  6. Version Control
  7. Change Management Integration
  8. Document Destruction
  9. Training & Competency
  10. References

- **Annexes** (4):
  - A01: Document Template Standards (SOP structure, formatting requirements)
  - A02: Document Approval Matrix (who approves what)
  - A03: Document Change Request Form
  - A04: Obsolete Document Handling Procedure

- **Key Content**:
  - ALCOA+ principles for documentation
  - Electronic vs paper document management
  - Controlled copy distribution
  - Master document repository
  - Periodic review requirements (annual)

**A2: Change Control SOP (QAS-00-005)** ⏱️ 10 hours
- **Regulatory Basis**: ICH Q10, EudraLex Vol 4
- **Source**: ICH Q10 guidance, existing TCC-HVAC-AHU5-2025-001 as example
- **Structure**:
  1. Purpose & Scope
  2. Definitions (minor change, major change, critical change)
  3. Responsibilities (Change Control Board)
  4. Change Categories & Classification
  5. Change Request Process
  6. Impact Assessment (5M1E: Man, Machine, Material, Method, Measurement, Environment)
  7. Risk Assessment (ICH Q9 principles)
  8. Approval & Implementation
  9. Verification & Effectiveness Check
  10. Documentation & Records

- **Annexes** (3):
  - A01: Change Request Form
  - A02: Impact Assessment Template (5M1E matrix)
  - A03: Change Implementation Plan Template

- **Key Content**:
  - Emergency changes vs planned changes
  - Technical Change Control (TCC) for equipment
  - Software change control
  - Link to CAPA system
  - Requalification triggers

**A3: CAPA System SOP (QAS-00-006)** ⏱️ 12 hours
- **Regulatory Basis**: ICH Q10, FDA CAPA Guidance
- **Source**: ICH Q10, FDA guidance documents
- **Structure**:
  1. Purpose & Scope
  2. Definitions (corrective action, preventive action)
  3. Responsibilities
  4. CAPA Initiation (sources: deviations, OOS, complaints, audits)
  5. Root Cause Analysis Methods (5 Whys, Fishbone, Fault Tree)
  6. CAPA Plan Development
  7. CAPA Implementation & Tracking
  8. Effectiveness Check
  9. CAPA Closure
  10. Trending & Analysis

- **Annexes** (3):
  - A01: CAPA Initiation Form
  - A02: Root Cause Analysis Template (multiple methods)
  - A03: Effectiveness Check Procedure

- **Key Content**:
  - Integration with deviation management
  - Preventive action triggers (trending, risk assessment)
  - CAPA effectiveness metrics
  - Management review of CAPA
  - Time limits for CAPA completion

**Package A Total**: 3 critical SOPs + 10 annexes, 34 hours effort

---

## 📈 Week 1 Summary

### Deliverables by End of Week
- ✅ **Real Purely Plant data** in automation system
- ✅ **14 existing SOPs** formatted and integrated
- ✅ **3 new critical SOPs** created
- ✅ **Total: 17 SOPs completed** this week
- ✅ **Progress**: 15% → 23% complete

### Hours Breakdown
- Package C: 1 hour (Azu: 0.5 hr, System: 0.5 hr)
- Package B: 56 hours (formatting existing work)
- Package A: 34 hours (creating new SOPs)
- **Total Week 1**: 91 hours (ambitious but achievable with focused effort)

---

## 🗺️ Weeks 2-40: Full Build-Out Roadmap

### Phase 1: Foundation (Weeks 1-8)
**Goal**: Critical & high-priority operational SOPs
**Deliverables**: 50 SOPs (15% → 25%)
**Focus**:
- Week 1: Packages A, B, C (17 SOPs) ✅ IN PROGRESS
- Week 2-3: Quality Assurance SOPs (10 SOPs)
- Week 4-5: Quality Control SOPs (12 SOPs)
- Week 6-7: Production & Cultivation SOPs (18 SOPs)
- Week 8: Sanitation & Equipment SOPs (10 SOPs)

### Phase 2: Validation (Weeks 9-16)
**Goal**: Qualification & validation framework
**Deliverables**: 35 SOPs (25% → 42%)
**Focus**:
- Week 9-10: Validation Master Plan + Equipment Qualification (8 SOPs)
- Week 11-12: Process Validation + Cleaning Validation (8 SOPs)
- Week 13-14: Method Validation + CSV (6 SOPs)
- Week 15-16: Requalification + Periodic Review (13 SOPs)

### Phase 3: Operations (Weeks 17-24)
**Goal**: Supporting operational procedures
**Deliverables**: 45 SOPs (42% → 63%)
**Focus**:
- Week 17-18: Materials Management (12 SOPs)
- Week 19-20: Facilities & Utilities (12 SOPs)
- Week 21-22: HR & Training (16 SOPs)
- Week 23-24: Security & Access Control (9 SOPs)

### Phase 4: Advanced Systems (Weeks 25-32)
**Goal**: Advanced compliance systems
**Deliverables**: 40 SOPs (63% → 82%)
**Focus**:
- Week 25-26: Records Management (10 SOPs)
- Week 27-28: Logistics & Distribution (11 SOPs)
- Week 29-30: Risk Management & Audits (10 SOPs)
- Week 31-32: Supplier Management & Complaints (9 SOPs)

### Phase 5: Finalization (Weeks 33-40)
**Goal**: Complete all remaining SOPs and review
**Deliverables**: 38 SOPs (82% → 100%)
**Focus**:
- Week 33-36: Remaining specialized SOPs (28 SOPs)
- Week 37-38: Complete any gaps (10 SOPs)
- Week 39: Full QMS review and refinement
- Week 40: Final validation, export package creation

---

## 🔄 Weekly Workflow Pattern

### Standard Week Structure (Weeks 2-40)

**Monday** (4 hours):
- Create 1 major SOP with regulatory research
- Extract relevant citations from EudraLex library

**Tuesday** (4 hours):
- Complete SOP and create 2-3 annexes
- Professional .docx formatting

**Wednesday** (4 hours):
- Create second SOP of the week
- Format annexes

**Thursday** (4 hours):
- Complete second SOP
- Add to automation system templates

**Friday** (4 hours):
- Quality review of week's work
- Test automation with new templates
- Generate PDFs
- Update QMS tracker

**Weekend** (1 hour):
- Azu: Review and provide feedback
- Planning for next week's SOPs

**Average**: 5 SOPs per week, 20 hours effort

---

## 📊 Progress Milestones

| Week | SOPs Complete | Cumulative % | Milestone |
|------|---------------|--------------|-----------|
| 1 | 17 | 23% | ✅ Week 1 packages complete |
| 8 | 50 | 35% | Foundation complete |
| 16 | 85 | 55% | **GMP audit-ready** |
| 24 | 130 | 70% | Operations complete |
| 32 | 175 | 85% | Advanced systems complete |
| 40 | 213 | 100% | **Full QMS complete** |

---

## 🎯 Success Criteria

### Quality Standards
- ✅ All SOPs cite regulatory basis (EudraLex, ICH, Ph.Eur., GACP)
- ✅ Professional .docx formatting with pharmaceutical standards
- ✅ Complete annexes for all procedures
- ✅ Integrated into automation system for future updates
- ✅ Cross-references validated
- ✅ English-only (bilingual translation Phase 2)

### Compliance Standards
- ✅ EudraLex Vol 4 compliance
- ✅ ICH Q-series alignment
- ✅ Ph.Eur. monograph 3028 (cannabis) compliance
- ✅ GACP requirements met
- ✅ ISO 17025 (laboratory) compliance
- ✅ ALCOA+ data integrity principles

### Documentation Standards
- ✅ Consistent formatting across all SOPs
- ✅ Unique document codes (12-chapter system)
- ✅ Version control from v1.0
- ✅ Approval blocks (Prepared, Reviewed, Approved)
- ✅ Effective dates
- ✅ Training requirements specified

---

## 💡 Risk Management

### Potential Challenges

**Challenge 1: Time Commitment (91 hrs Week 1)**
- **Risk**: Burnout, quality compromise
- **Mitigation**: Front-load existing work (Package B uses conversation history), focus quality over speed
- **Contingency**: Extend Week 1 to 10 days if needed

**Challenge 2: Regulatory Citation Accuracy**
- **Risk**: Incorrect or outdated references
- **Mitigation**: Cross-reference with multiple EudraLex sources, use latest versions
- **Contingency**: Azu reviews all regulatory citations

**Challenge 3: Scope Creep (213 → more?)**
- **Risk**: Discovering additional SOPs needed
- **Mitigation**: Stick to QMS Tracker, only add if truly critical
- **Contingency**: Add to Phase 5 if urgent

**Challenge 4: Maintaining Consistency**
- **Risk**: Format/style drift over 40 weeks
- **Mitigation**: Use templates, automation system enforces consistency
- **Contingency**: Quarterly formatting reviews (Weeks 10, 20, 30, 40)

---

## 🔧 Tools & Resources

### Development Environment
- VSCode with Claude Code extension
- Python 3.12 automation system
- Regulatory library (82 PDFs)
- Conversation history (existing SOP work)

### Documentation Tools
- Automation system for template management
- Excel for facility data
- PDF generator for professional output
- Cross-reference validator

### Regulatory Resources
- EudraLex Vol 4 (Chapters 1-9)
- GMP Annexes (1, 7, 8, 11, 15, 16, 17, 19, 21)
- ICH Guidelines (Q8, Q9, Q10)
- Ph.Eur. monographs
- WHO GACP guidelines
- Laboratory QMS (ISO 17025)
- GWP literature (25+ guides)

---

## 📞 Communication & Review

### Weekly Review Meetings
**Frequency**: Friday end-of-week
**Duration**: 30-60 minutes
**Attendees**: Azu (QP) + Development team
**Agenda**:
1. Week accomplishments review
2. Quality check of SOPs created
3. Regulatory citation validation
4. Next week planning
5. Blockers/issues discussion

### Monthly Progress Reviews
**Frequency**: End of each month (Weeks 4, 8, 12, etc.)
**Duration**: 2 hours
**Focus**:
1. Progress vs plan (on track?)
2. Quality metrics review
3. Adjustments to timeline if needed
4. Stakeholder updates

### Quarterly QMS Audits
**Frequency**: Weeks 10, 20, 30, 40
**Duration**: Half-day
**Focus**:
1. Complete QMS review
2. Cross-reference validation
3. Consistency check
4. Regulatory compliance verification
5. Gap analysis

---

## ✅ Week 1 Action Items

### Immediate (Today - January 13)
1. ✅ Export facility_data.yaml to Excel
2. ⏳ **Azu**: Fill real Purely Plant data (30-60 min)
3. ✅ Extract Batch Release SOP from conversation history
4. ✅ Begin formatting Batch Release SOP

### This Week (January 14-19)
1. Complete Package C: Import real data, test system
2. Complete Package B: Format all 14 existing SOPs
3. Complete Package A: Create 3 critical new SOPs
4. Generate all PDFs
5. Update QMS Tracker
6. Friday review meeting

---

## 🎉 End State (Week 40)

### What You'll Have
- ✅ **213 complete SOPs** with full annexes
- ✅ **500+ supporting documents** (forms, templates, logs)
- ✅ **Automated generation system** for all updates
- ✅ **Professional PDF packages** for all documents
- ✅ **Complete regulatory citations** for every procedure
- ✅ **GMP certification-ready** documentation
- ✅ **English-language QMS** (translation-ready)

### Business Value
- **€170,000+ time savings** (vs manual creation)
- **GMP certification ready** in 10 months vs 24+ months
- **Professional appearance** impressing inspectors
- **Scalable system** for future growth
- **Automated updates** for regulatory changes
- **Complete traceability** and version control

---

**Let's build this! Starting with Week 1 Packages A, B, and C.** 🚀

*Created: January 13, 2026*
*QP: Azu Sozo, Master Pharmacist*
*Purely Plant GmbH, Skopje, North Macedonia*
