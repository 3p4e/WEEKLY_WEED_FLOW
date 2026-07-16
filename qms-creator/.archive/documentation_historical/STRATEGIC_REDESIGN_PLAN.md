# Strategic Redesign Plan - Cannabis EU GMP QMS Creator
**Date:** 2026-01-27
**Status:** Fresh Start - All Test SOPs Archived to LEGACY/

---

## 🎯 Executive Summary

After successful implementation of the three AI features and API key configuration, we're resetting to a clean state to implement a more sophisticated approach. This plan covers:

1. **Comprehensive SOP Master List** (from project inception)
2. **Document Coding & Hierarchy** (EU GMP regulatory compliance)
3. **Latest LLM Model Strategy** (optimal model selection per task)
4. **Enhanced Questionnaire Framework** (medical cannabis factory compliance)
5. **AI Content Generation Approach** (regulatory-grade text for medical cannabis)

---

## PART 1: COMPREHENSIVE SOP MASTER LIST

### Original Vision (Project Inception)

The Cannabis EU GMP QMS Creator was designed to generate SOPs across these departments:

### **Quality Management System (QA_00)**
Foundation documents required by EudraLex Vol 4

| Code | Title | Purpose | Annexes |
|------|-------|---------|---------|
| QA_00.01 | Quality Manual | System overview & commitment | None |
| QA_00.02 | Document Control | Doc management, approval workflow | A01-A04 (templates, matrices, forms) |
| QA_00.03 | Training | Personnel qualifications, training records | A01-A04 (forms, records, evaluations) |
| QA_00.04 | Memorandum Control | Internal communications management | A01-A04 (forms, distribution records) |
| QA_00.05 | Change Control | Change management, risk assessment | A01-A03 (forms, templates) |
| QA_00.06 | CAPA System | Deviations, root cause analysis, effectiveness | A01-A03 (forms, RCA, effectiveness) |
| QA_00.07 | Deviations | Non-conformance handling & investigation | None |
| QA_00.08 | Self-Inspection | Internal audits & compliance checks | None |
| QA_00.12 | Site Master File | Facility documentation repository | None |
| QA_00.13 | Product Quality Review | Annual PQR & batch record review | None |
| QA_00.14 | Management Review | System effectiveness review | None |
| QA_00.15 | Document Retention | Record retention periods & archival | None |
| QA_00.16 | Labeling & Label Control | Label design, printing, application, controls | None |

### **Materials Management (MAT_02)**

| Code | Title | Purpose |
|------|-------|---------|
| MAT_02.01 | Analytical Methods Validation | Method validation for raw materials |
| MAT_02.02 | Material Supplier Management | Supplier qualification & assessment |
| MAT_02.03 | Material Receipt & Testing | Incoming quality control procedures |
| MAT_02.04 | Material Storage Conditions | Storage requirements & monitoring |
| MAT_02.05 | Contamination Control | Prevention of cross-contamination |

### **Production - Cultivation (PRO_01)**

| Code | Title | Purpose | Critical Controls |
|------|-------|---------|------------------|
| PRO_01.01 | Mother Plant Management | Genetic purity, health monitoring | Plant identity, health records |
| PRO_01.02 | Propagation & Cloning | Tissue culture, cuttings, rooting | Contamination prevention |
| PRO_01.03 | Seed Germination | Viable seed selection & germination | Seed viability testing |
| PRO_01.04 | Vegetative Growth | Nutrition, light, environmental control | NPK management, light schedule |
| PRO_01.05 | Flowering Management | Photoperiod control, triggering, monitoring | Flowering timeline, cannabinoid dev |
| PRO_01.06 | IPM (Integrated Pest Management) | Pest control without residues | Residue limits, monitoring |
| PRO_01.07 | Irrigation & Fertigation | Nutrient delivery, water quality | EC, pH, nutrient ratios |
| PRO_01.08 | Environmental Monitoring | Temperature, humidity, CO2 tracking | Optimal ranges by growth stage |
| PRO_01.09 | Trimming & Manicuring | Plant material preparation for harvest | Contamination control |
| PRO_01.10 | Plant Health Monitoring | Disease detection & prevention | Early intervention protocols |
| PRO_01.11 | Waste Management (Cultivation) | Disposal of contaminated plant material | Regulatory compliance |

### **Production - Post-Harvest (PRO_02 & PRO_03)**

| Code | Title | Purpose | Timeline |
|------|-------|---------|----------|
| PRO_02.01 | Harvest Procedures | Harvest timing, cutting, handling | Optimized cannabinoid/terpene window |
| PRO_03.01 | Curing Procedures | Slow drying & fermentation | 1-3 months, controlled conditions |
| PRO_03.02 | Drying Procedures | Moisture reduction to 7-12% | Temperature/humidity controlled |
| PRO_03.03 | Processing (Grinding, Extraction) | Conversion to final product form | Consistency, identity preservation |
| PRO_04.01 | Primary Packaging | Product containment & labeling | Child-resistant, track-and-trace |

### **Distribution & Logistics (PRO_06)**

| Code | Title | Purpose |
|------|-------|---------|
| PRO_06.01 | Distribution SOP | Shipping procedures, documentation |
| PRO_06.02 | Cold Chain Management | Temperature-controlled storage/transport |
| PRO_06.03 | Track & Trace | Serialization, batch tracking |

### **Quality Control & Testing (QC_01 or QC_04)**

| Code | Title | Method/Purpose |
|------|-------|-----------------|
| QC_01.01 | Batch Release | Final approval before distribution |
| QC_01.02 | Sampling Procedures | Representative sampling from batches |
| QC_01.03 | Out-of-Specification Investigation | OOS handling & impact assessment |
| QC_01.04 | Specifications Management | Quality standards for products |
| QC_01.05 | Laboratory Organization | Lab safety, equipment, documentation |
| QC_01.06 | QC Documentation | Record-keeping for all tests |
| QC_01.07 | Sampling Plan | Sampling frequency & quantities |
| QC_01.08 | Cannabinoid Testing (HPLC) | THC, CBD, minor cannabinoid quantitation |
| QC_01.09 | Microbial Limit Testing | Total plate count, pathogens (E.coli, Listeria) |
| QC_01.10 | Heavy Metals Testing | Cd, Pb, As, Hg in plant material |
| QC_01.11 | Pesticide Residue Testing | Agri-chemicals, synthetic pesticides |
| QC_01.12 | Moisture Content | Water activity, stability |
| QC_01.13 | Laboratory Sample Management | Sample receipt, storage, disposal |
| QC_01.14 | Method Validation Protocol | HPLC, GC-MS, ICP-MS validation |

### **Human Resources (HRM_05)**

| Code | Title | Purpose |
|------|-------|---------|
| HRM_05.01 | Personnel Management | Hiring, qualification, records |
| HRM_05.02 | Personnel Qualification | Education & experience requirements |
| HRM_05.04 | GMP Training Program | Initial & refresher training |
| HRM_05.05 | Employee Hygiene | Health & hygiene standards |
| HRM_05.06 | Visitor Management | Visitor access & gowning |
| HRM_05.07 | Gowning Procedures | Proper PPE donning procedures |

### **Equipment Management (EQU_06)**

| Code | Title | Purpose |
|------|-------|---------|
| EQU_06.01 | Equipment Operation | Standard operating procedures for equipment |
| EQU_06.02 | Equipment Calibration | Maintenance of accuracy (HPLC, scales, etc.) |
| EQU_06.03 | Equipment Qualification | IQ/OQ/PQ for new equipment |
| EQU_06.04 | Equipment Maintenance | Preventive & corrective maintenance |

### **Sanitation & Hygiene (SAN_07)**

| Code | Title | Purpose |
|------|-------|---------|
| SAN_07.01 | Cleaning & Sanitation | Facility & equipment cleaning procedures |
| SAN_07.02 | Cleaning Validation | Protocol validation for cleaning processes |
| SAN_07.03 | Environmental Monitoring | Surface & air monitoring for contamination |

### **Validation & Qualification (VAL_08)**

| Code | Title | Purpose |
|------|-------|---------|
| VAL_08.01 | Validation Master Plan | Overall validation strategy |
| VAL_08.02 | Process Validation Protocol | IQ/OQ/PQ framework |
| VAL_08.03 | Analytical Method Validation | Method validation for testing procedures |
| VAL_08.04 | Cleaning Validation | Cleaning procedure effectiveness |
| VAL_08.05 | Computer System Validation | LIMS, ERP systems |
| VAL_08.06 | Facility Qualification | Building systems (HVAC, water, utilities) |
| VAL_08.07 | Equipment Qualification | Equipment IQ/OQ/PQ |
| VAL_08.08 | Extraction Process Validation | If applicable |

### **Records Management (REC_09 or RES_10)**

| Code | Title | Purpose |
|------|-------|---------|
| REC_09.01 | Records Management | Documentation, storage, archival |
| RES_10.01 | Research & Development | Experimental procedures, documentation |

---

## PART 2: DOCUMENT CODING & HIERARCHY STRATEGY

### Current Coding System
```
[DEPARTMENT]_[FAMILY].[SOP_NUMBER]_v[VERSION]_[LANGUAGE]

Example: QC_01.15_v1.0_EN
├─ QC = Department (Quality Control)
├─ 01 = Family (Batch Release & Certification)
├─ 15 = Sequential SOP number within family
├─ v1.0 = Version
└─ EN = Language
```

### Improved Hierarchy Model (Recommended)

**Tier 1: Department (2 letters)**
```
QA = Quality Assurance / Management System
QC = Quality Control / Testing
PRO = Production (Cultivation & Post-harvest)
MAT = Materials & Suppliers
HRM = Human Resources
EQU = Equipment
SAN = Sanitation
VAL = Validation
REC = Records
RES = Research
```

**Tier 2: Family (2 digits)**
```
Quality Assurance (QA)
├─ 00 = Core QMS (Quality Manual, Doc Control, Training, etc.)
├─ 01 = Document Control & Management
├─ 02 = Change Control & Risk Assessment
├─ 03 = CAPA & Deviations
└─ 04 = Internal Quality Audits

Production - Cultivation (PRO)
├─ 01 = Indoor Cultivation Processes
├─ 02 = Outdoor Cultivation (if applicable)
└─ 03 = Harvest & Post-Harvest

Quality Control (QC)
├─ 01 = Batch Release & General Testing
├─ 02 = Cannabinoid Testing Methods
├─ 03 = Microbial & Contaminant Testing
└─ 04 = Specialized Analysis Methods
```

**Tier 3: Sequential Number (2-3 digits)**
- Automatically assigned based on family
- Ensures uniqueness within department

**Implementation:** The DocumentCodeService already implements this with keyword-based auto-assignment

### Regulatory Compliance Mapping

Each SOP should reference:
- **EudraLex Vol 4** (EU GMP basics)
- **Annex 15** (Qualification & Validation)
- **ICH Q7** (GMP for Active Pharmaceutical Ingredients)
- **WHO GMP** (Guidelines for medicinal plant materials)
- **Cannabis-specific:** EU Medical Cannabis regulations

---

## PART 3: LATEST LLM MODELS & OPTIMAL SELECTION STRATEGY

### Available Models (from configured API keys)

#### **OpenAI - PRIMARY CHOICE** ✅
- **Model:** `gpt-4-turbo-preview`
- **Context:** 128K tokens
- **Strengths:** Best for regulatory compliance, medical terminology, structured content
- **Cost:** $0.01/$0.03 per 1K tokens (in/out)
- **Use Cases:**
  - SOP body text (Procedure, Responsibilities, etc.)
  - Regulatory compliance checks
  - Quality Management content
  - **RECOMMENDED for main SOP content**

#### **Google Gemini - SECONDARY CHOICE** ✅
- **Model:** `gemini-1.5-pro`
- **Context:** 1M tokens (largest available)
- **Strengths:** Better at complex formatting, long documents, technical specifications
- **Cost:** $0.075/$0.3 per 1M tokens
- **Use Cases:**
  - Annexes (forms, templates, checklists)
  - Long procedures with multiple sub-steps
  - Integrated system documentation
  - **RECOMMENDED for Annex generation**

#### **Perplexity - RESEARCH/REFERENCE** ✅
- **Model:** `sonar-small-online`
- **Strengths:** Web research, current regulations, citations
- **Use Cases:**
  - Regulatory updates & compliance verification
  - External references & citations
  - **RECOMMENDED for regulatory context & research**

### Proposed Model Selection Strategy

```
SOP Generation Workflow:

1. SOP Overview & Structure
   └─ Model: GPT-4-Turbo ✅ (structured output, GMP knowledge)

2. Purpose & Scope Sections
   └─ Model: GPT-4-Turbo ✅ (regulatory compliance)

3. Responsibilities Section
   └─ Model: GPT-4-Turbo ✅ (role clarity, compliance)

4. Procedure Steps (1-20+ steps)
   ├─ Long procedures (10+ steps): Gemini-1.5-Pro ✅ (handles long context)
   └─ Standard procedures (5-10 steps): GPT-4-Turbo ✅ (faster)

5. In-Process Controls & Critical Parameters
   └─ Model: Gemini-1.5-Pro ✅ (detailed specifications)

6. Quality Attributes (CQAs, CPPs)
   └─ Model: GPT-4-Turbo ✅ (regulatory framework)

7. Documentation & Record-Keeping
   └─ Model: Gemini-1.5-Pro ✅ (forms, annexes)

8. Regulatory Compliance Review
   └─ Model: Perplexity ✅ (external validation)

9. Annex Generation (Forms, Checklists, Templates)
   └─ Model: Gemini-1.5-Pro ✅ (large context, forms)

10. Final Audit & Compliance Check
    └─ Model: GPT-4-Turbo ✅ (regulatory auditor role)
```

### Optimization Configuration

**Create model selection in prompts.yaml:**
```yaml
model_selection:
  sop_overview: "gpt-4-turbo-preview"
  purpose_scope: "gpt-4-turbo-preview"
  responsibilities: "gpt-4-turbo-preview"
  procedure_short: "gpt-4-turbo-preview"
  procedure_long: "gemini-1.5-pro"
  cqa_cpp: "gpt-4-turbo-preview"
  annexes: "gemini-1.5-pro"
  regulatory_review: "gpt-4-turbo-preview"
  fallback: ["gemini-1.5-pro", "sonar-small-online"]
```

---

## PART 4: ENHANCED QUESTIONNAIRE FRAMEWORK

### Current Structure (12 Sections)

Current questionnaire focuses on general SOP attributes. For medical cannabis GMP compliance, we need MORE SPECIFIC sections.

### Proposed Enhanced Framework (16-18 Sections)

#### **Section 1: Document Identification** (unchanged)
- SOP Title ✅
- Document Code (auto-assigned) ✅
- Document Type ✅
- Version & Effective Date ✅
- Language ✅

#### **Section 2: Regulatory Scope & Applicability** (NEW)
- Primary regulatory framework (EudraLex, ICH, WHO, Cannabis-specific)
- Geographic scope (EU, Member States)
- Facility type affected (Cultivation, Testing, Processing)
- Product types covered (Flower, Extract, Oil, etc.)
- Critical Quality Attributes affected?

#### **Section 3: Cannabis-Specific Parameters** (NEW for medical cannabis)
- Does this SOP affect cannabinoid content (THC/CBD)?
- Terpene profile management required?
- Microbial/contaminant testing scope?
- Extraction method involved?
- Post-harvest processing?
- Final product form?

#### **Section 4: Process Controls & Critical Parameters** (NEW)
- Controlled variables (Temperature, pH, Pressure, Time, Concentration)?
- Acceptance limits/ranges for each parameter?
- In-process control points needed?
- Critical Process Parameters (CPPs) involved?
- Critical Quality Attributes (CQAs) affected?

#### **Section 5: Risk Assessment** (ENHANCED from current)
- Risk category (Low/Medium/High/Critical)?
- Main failure modes?
- Consequence of failure (Product quality, Safety, Compliance)?
- Control measures in place?
- Residual risk acceptable?

#### **Section 6: Facility & Equipment Requirements** (NEW)
- Specific equipment required (HPLC, GC-MS, Incubator, etc.)?
- Environmental conditions needed (Temperature, Humidity, Light, Pressure)?
- Facility classification (ISO Class, HVAC specs)?
- Maintenance schedule?
- Calibration requirements?

#### **Section 7: Training & Competency** (ENHANCED)
- Specialized training required? (e.g., HPLC operation, aseptic technique)
- Training duration & frequency?
- Competency assessment method?
- Hands-on/practical demonstration needed?
- Refresher training frequency?

#### **Section 8: Documentation & Records** (ENHANCED)
- Types of records to maintain? (Batch records, logs, test results)
- Retention period? (3 months, 1 year, product shelf-life + 1 year)
- Electronic vs paper records?
- Audit trail requirements?
- Data integrity requirements?

#### **Section 9: Quality System Integration** (NEW)
- Related SOPs/procedures?
- Interfaces with other systems?
- Change control implications?
- Deviation reporting required?
- CAPA triggers defined?

#### **Section 10: Sampling & Statistical Approach** (NEW - for testing SOPs)
- Sampling strategy (representative, statistical)?
- Sample size determination?
- Sampling frequency?
- Acceptance criteria (AQL, USL, LSL)?

#### **Section 11: Analytical Methods** (NEW - for testing SOPs)
- Method type (HPLC, GC-MS, ICP-MS, Microbiology, etc.)?
- Substance being measured?
- Detection/quantitation limit needed?
- Method validation required?

#### **Section 12: Cannabis Cannabinoid Profile** (NEW - if applicable)
- Target THC range?
- Target CBD range?
- Minor cannabinoid monitoring?
- Terpene profiling?
- Potency acceptance limits?

#### **Section 13: Microbial & Contaminant Control** (NEW)
- Microbial limits (TPC, pathogens)?
- Heavy metal limits (Cd, Pb, As, Hg)?
- Pesticide residue limits?
- Solvent residue limits (if extraction)?
- Mold/mycotoxin testing?

#### **Section 14: Sustainability & Environmental** (NEW)
- Waste disposal method?
- Environmental impact?
- Recycling/reuse of materials?
- Energy efficiency considerations?

#### **Section 15: Appendices & Annexes** (ENHANCED)
- Forms needed? (Log sheets, inspection forms, batch records)
- Checklists required?
- Templates to include?
- Reference materials needed?
- Acceptance limits tables?

#### **Section 16: Regulatory & Compliance Verification** (NEW)
- EudraLex Vol 4 Chapter compliance?
- Annex 15 requirements (if applicable)?
- ICH Q7 compliance?
- Cannabis-specific regulation compliance?
- Third-party audit-ready?

---

## PART 5: MEDICAL CANNABIS GMP COMPLIANCE - AI CONTENT GENERATION APPROACH

### The Challenge

Medical cannabis SOPs require:
1. **Regulatory precision** - EU GMP compliance for pharmaceutical standards
2. **Scientific accuracy** - Cannabinoid chemistry, microbiology, analytical chemistry
3. **Safety focus** - Patient safety, contamination prevention, traceability
4. **Practical execution** - Real-world procedures that can be followed
5. **Documentation rigor** - Records suitable for regulatory inspection

### AI Content Generation Strategy

#### **Phase 1: Regulatory Foundation (GPT-4-Turbo)**

**System Prompt:**
```
You are an expert in EU GMP (Good Manufacturing Practice) for medicinal cannabis
production, specifically for pharmaceutical-grade products. You have deep knowledge of:

- EudraLex Volume 4 (EU Guidelines for GMP)
- Annex 15 (Qualification & Validation)
- ICH Q7 (GMP for Active Pharmaceutical Ingredients)
- WHO GMP Guidelines
- EU Medical Cannabis Regulations (CBD/THC licensing)
- Cannabis-specific regulatory frameworks

Your role is to generate SOP sections that are:
✓ Regulatory-compliant
✓ Scientifically accurate
✓ Practically executable
✓ Audit-ready
✓ Industry-standard quality
```

**Example Purpose Section Generation:**
```
Input:
- Title: "Cannabinoid Potency Testing by HPLC-UV"
- Department: QC_01 (Quality Control)
- Facility: Medical Cannabis Production Facility
- Product: Cannabis flower, oil extracts

Expected Output:
1. Clear statement of regulatory purpose (EudraLex, ICH compliance)
2. Reference to Critical Quality Attributes (THC, CBD quantitation)
3. Links to other SOPs (Sampling, Method Validation)
4. Safety implications (Patient safety, dosage accuracy)
5. Recording/documentation expectations
```

#### **Phase 2: Cannabis-Specific Content (Specialized Prompts)**

**For Cannabinoid-Related SOPs:**
```
Include:
- THC/CBD/minor cannabinoid content targets
- Cannabinoid stability during storage/processing
- Testing frequency & acceptance limits
- Licensed potency limits compliance (EU varying by Member State)
- Patient safety implications
```

**For Cultivation SOPs:**
```
Include:
- Environmental control parameters (PPM CO2, DLI light, etc.)
- Nutrient management (optimal N-P-K ratios for cannabinoid development)
- Pest/disease control WITHOUT synthetic pesticides (critical for medical)
- Harvest timing for cannabinoid/terpene maturity
- Plant traceability & identity preservation
```

**For Contamination Control:**
```
Include:
- Microbial limits (Pharmaceutical standard, not agricultural)
  - Total Plate Count limits
  - Absence of E. coli, Salmonella, Listeria
  - Mold/mycotoxin (Aspergillus, Aflatoxin)
- Heavy metals (Medical cannabis grade)
  - Cadmium, Lead, Arsenic, Mercury limits
- Pesticide residues (Zero-residue medical standard)
- Solvent residues (if extraction involved)
```

**For Testing Method SOPs:**
```
Include:
- HPLC method specifics (Column, wavelength, retention times)
- Quality parameters (Sensitivity, specificity, linearity, accuracy, precision)
- Method validation plan (ICH Q2(R1) guidelines)
- Acceptance criteria (Relative Standard Deviation, recovery, etc.)
- Data integrity measures (Audit trail, electronic records)
```

#### **Phase 3: Structure & Format Standards (Gemini-1.5-Pro)**

**Consistent SOP Structure:**
```
1. PURPOSE (1-2 pages)
   - Business objective
   - Regulatory requirement
   - Scope statement
   - Link to Quality System

2. SCOPE (0.5-1 page)
   - What's covered
   - What's excluded
   - Applicability across facility
   - Interfaces with other SOPs

3. RESPONSIBILITIES (0.5-1 page)
   - Operator/Analyst
   - Supervisor/Manager
   - QA/QP oversight
   - Document approval authority

4. PROCEDURE (2-5 pages)
   4.1 Prerequisites
       - Training requirements
       - Equipment/materials needed
   4.2 Step-by-step procedure (numbered, detailed)
   4.3 In-process controls (CPPs, CQAs)
   4.4 Out-of-specification handling
   4.5 Deviation reporting

5. DOCUMENTATION (0.5 page)
   - Records to maintain
   - Retention period
   - Audit trail requirements

6. ATTACHMENTS/ANNEXES
   - Forms (batch records, logs)
   - Checklists
   - Acceptance limits
   - Reference materials
```

#### **Phase 4: Medical Cannabis Quality Standards (GPT-4-Turbo)**

**Key Parameters to Include:**

**Potency (for THC/CBD products):**
```
- Target THC range: e.g., 18-22% w/w
- Target CBD range: e.g., 0.1-0.5% w/w
- Testing frequency: Every batch
- Acceptable variation: ±5% of target
- Patient safety implication: Dosage accuracy
```

**Microbiology (Pharmaceutical Standard):**
```
- Total Plate Count: ≤10⁴ CFU/g (medical standard, not 10⁶ agriculture)
- E. coli: Absence (not >10² like agriculture)
- Salmonella: Absence in 25g
- Listeria: Absence
- Aspergillus/Aflatoxin: Limits per EU regulation
```

**Heavy Metals (Medical Grade):**
```
- Cadmium: ≤2 μg/g
- Lead: ≤3 μg/g
- Arsenic: ≤0.5 μg/g
- Mercury: ≤0.5 μg/g
(Stricter than agricultural, matching pharmaceutical standards)
```

**Pesticides:**
```
- Target: Zero detectable residues
- Testing method: GC-MS or LC-MS/MS
- Limit of detection: <0.01 mg/kg
- List of prohibited pesticides (EU canabis-specific)
```

#### **Phase 5: AI Audit & Compliance Verification (GPT-4-Turbo)**

**After SOP Generation, AI reviews:**

1. **Regulatory Checklist:**
   - ✓ EudraLex Vol 4 compliance points
   - ✓ Annex 15 requirements met
   - ✓ ICH Q7 principles followed
   - ✓ Cannabis regulations addressed

2. **Medical Cannabis Specifics:**
   - ✓ Potency limits appropriate
   - ✓ Contamination controls adequate
   - ✓ Traceability enabled
   - ✓ Patient safety protected

3. **Documentation Quality:**
   - ✓ Records defined
   - ✓ Audit trail enabled
   - ✓ Deviation handling clear
   - ✓ Change control integrated

4. **Procedural Clarity:**
   - ✓ Steps are executable
   - ✓ Critical points highlighted
   - ✓ Accept/reject criteria clear
   - ✓ Troubleshooting guidance included

### Implementation in LLM Client

```python
# New method in llm_client.py
def generate_sop_content(
    self,
    sop_type: str,           # 'cultivation', 'testing', 'control', etc.
    section: str,            # 'purpose', 'procedure', 'annex', etc.
    facility_context: dict,  # Cannabinoid targets, equipment, etc.
    regulatory_framework: str  # 'eudralex', 'ich', 'who', 'cannabis'
) -> str:
    """
    Generate SOP content using optimal model per section type

    Models selected based on section complexity & content length
    """

    # Select model based on section
    if section in ['procedure', 'annex'] and len_is_long:
        model = "gemini-1.5-pro"  # For long, complex content
    elif 'audit' in section or 'compliance' in section:
        model = "gpt-4-turbo"  # For regulatory/compliance
    else:
        model = "gpt-4-turbo"  # Default to fastest for most sections

    # Build cannabis-specific system prompt
    system_prompt = self._build_cannabis_system_prompt(
        sop_type,
        facility_context,
        regulatory_framework
    )

    # Generate content with selected model
    return self.generate_text(
        system_prompt,
        user_prompt,
        temperature=0.3,  # Lower temp for regulatory text
        model=model
    )
```

---

## NEXT STEPS: FRESH START IMPLEMENTATION

### Phase 1: Clean Slate ✅
- [x] Archive all test SOPs to LEGACY/
- [x] Keep only official structure & templates
- [x] Ready for fresh generation

### Phase 2: Framework Implementation (TODO)
1. Update questionnaire schema with 16-18 sections
2. Integrate model selection logic
3. Enhanced cannabis-specific prompts
4. Regulatory audit automation

### Phase 3: First Complete SOP Generation (TODO)
1. Select a high-priority SOP (e.g., QA_00.02 Document Control)
2. Run through enhanced questionnaire
3. Generate using optimal models
4. Validate compliance
5. Review & iterate

### Phase 4: Batch Generation (TODO)
1. Generate all QA_00 (Quality Management) SOPs first
2. Then QC_01 (Quality Control) SOPs
3. Then PRO (Production) SOPs
4. Then specialized SOPs

---

## SUMMARY TABLE: Implementation Priorities

| Priority | Department | Target SOPs | Rationale |
|----------|-----------|------------|-----------|
| 1 | QA (Quality) | QA_00.01-08, 12-16 | Foundation for all other SOPs |
| 2 | QC (Testing) | QC_01.01-06 | Core quality control procedures |
| 3 | PRO (Production) | PRO_01.01-11, PRO_02-03 | Operational core |
| 4 | HRM (HR) | HRM_05 suite | Training & competency foundation |
| 5 | Equipment | EQU_06 suite | Support processes |
| 6 | Validation | VAL_08 suite | Compliance assurance |
| 7 | Sanitation | SAN_07 suite | Contamination control |
| 8 | Advanced Testing | QC_01.08-14 | Analytical methods |

---

**Ready to proceed with Phase 2: Framework Implementation?**

Questions to clarify before starting:
1. Should we start with QA_00.02 (Document Control) as first full SOP?
2. Which medical cannabis product form is priority? (Flower, Oil, Extract)
3. Any specific cultivation constraints? (Indoor/outdoor, facility capacity)
4. Target market regulations? (Which EU Member States)
