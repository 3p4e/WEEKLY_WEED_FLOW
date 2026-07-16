---
document_code: MAT_02.01
title: Analytical Methods Validation
version: "1.0"
effective_date: 2025-01-15
review_date: 2026-01-15
author: Ana Dimitrova
department: Quality Control
classification: GMP Critical
language: EN
---

# MAT_02.01 - Analytical Methods Validation
# Валидација на Аналитички Методи

---

## APPROVAL SIGNATURES / ПОТПИСИ ЗА ОДОБРУВАЊЕ

| Role / Улога | Name / Име | Signature / Потпис | Date / Датум |
|--------------|------------|-------------------|--------------|
| Prepared by / Подготвил: | Ana Dimitrova, QC Manager | _________________ | ____________ |
| Checked by / Проверил: | Stefan Petrov, QA Manager | _________________ | ____________ |
| Approved by / Одобрил: | Azu Sozo, Qualified Person (QP) | _________________ | ____________ |

---

## DOCUMENT CONTROL / КОНТРОЛА НА ДОКУМЕНТОТ

| Parameter | Details |
|-----------|---------|
| Document Number | MAT_02.01 |
| Version | 1.0 |
| Category | Materials / Quality Control |
| Classification | GMP Critical |
| Effective Date | 2025-01-15 |
| Next Review | 2026-01-15 |
| Distribution | QC, QA, Validation Team |

---

## REVISION HISTORY / ИСТОРИЈА НА РЕВИЗИИ

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-15 | A. Dimitrova | Initial release |

---

## 1. PURPOSE / ЦЕЛ

**English:**
To establish the requirements and procedures for the validation of analytical methods used in the quality control of medical cannabis raw materials, intermediates, and finished products. This SOP ensures that all analytical methods produce reliable, reproducible results suitable for their intended purpose in compliance with ICH Q2(R1), European Pharmacopoeia, and EU GMP requirements.

**Македонски:**
Да се воспостават барањата и процедурите за валидација на аналитички методи користени во контрола на квалитетот на суровини, полупроизводи и готови производи од медицински канабис. Оваа SOP осигурува дека сите аналитички методи произведуваат сигурни, репродуктивни резултати соодветни за нивната намена во согласност со ICH Q2(R1), Европска Фармакопеја и барањата на EU GMP.

---

## 2. SCOPE / ОПСЕГ

This SOP applies to:
- Validation of new analytical methods
- Verification of compendial methods
- Method transfer validation
- Partial validation/revalidation after changes
- Method development documentation

**Methods Covered:**
- HPLC methods for cannabinoid analysis
- GC methods for terpene and residual solvent analysis
- ICP-MS/ICP-OES for heavy metals
- Microbiological methods
- Physical testing methods
- Identification methods

**Exclusions:**
- Environmental monitoring methods (separate validation)
- Process analytical technology (PAT) sensors

---

## 3. RESPONSIBILITIES / ОДГОВОРНОСТИ

### 3.1 QC Manager
- Overall responsibility for method validation
- Approve validation protocols and reports
- Ensure adequate resources for validation
- Maintain method validation documentation

### 3.2 Method Development Scientist
- Develop and optimize analytical methods
- Prepare validation protocols
- Execute validation experiments
- Prepare validation reports

### 3.3 Quality Assurance
- Review validation protocols for compliance
- Approve validation documentation
- Ensure regulatory compliance
- Maintain validation records

### 3.4 QC Analysts
- Execute validation experiments per protocol
- Document results accurately
- Report deviations and OOS results
- Maintain equipment and reference standards

### 3.5 Qualified Person (QP)
- Final approval of validated methods for batch release
- Review critical method validations
- Ensure methods support product certification

---

## 4. DEFINITIONS / ДЕФИНИЦИИ

| Term | Definition |
|------|------------|
| **Validation** | Process of demonstrating that an analytical method is suitable for its intended purpose |
| **Verification** | Confirmation that a compendial method performs appropriately under actual conditions of use |
| **Specificity** | Ability to assess the analyte in the presence of expected components |
| **Linearity** | Ability to obtain results proportional to analyte concentration |
| **Range** | Interval over which the method provides suitable precision and accuracy |
| **Accuracy** | Closeness of test results to true value |
| **Precision** | Closeness of agreement between independent test results |
| **Repeatability** | Precision under same operating conditions over short time |
| **Intermediate Precision** | Precision within a laboratory (different days, analysts, instruments) |
| **Reproducibility** | Precision between laboratories |
| **LOD** | Limit of Detection - lowest amount detectable |
| **LOQ** | Limit of Quantitation - lowest amount quantifiable with acceptable precision |
| **Robustness** | Method's capacity to remain unaffected by small variations |

---

## 5. METHOD VALIDATION REQUIREMENTS / БАРАЊА ЗА ВАЛИДАЦИЈА НА МЕТОДИ

### 5.1 Types of Analytical Procedures

| Procedure Type | Purpose | Examples |
|----------------|---------|----------|
| Identification | Confirm identity of analyte | UV/Vis spectrum, HPLC retention time, IR |
| Assay (Content) | Quantify active ingredient | HPLC cannabinoid content |
| Impurity (Quantitative) | Quantify known impurities | Pesticides, heavy metals, degradants |
| Impurity (Limit Test) | Confirm impurity below limit | Residual solvents, microbial limits |
| Dissolution/Release | Measure release rate | In-vitro dissolution |

### 5.2 Validation Parameters by Procedure Type

| Parameter | Identification | Assay | Impurity (Quant) | Impurity (Limit) |
|-----------|:-------------:|:-----:|:----------------:|:----------------:|
| Specificity | ● | ● | ● | ● |
| Linearity | - | ● | ● | - |
| Range | - | ● | ● | - |
| Accuracy | - | ● | ● | ○ |
| Repeatability | - | ● | ● | ● |
| Intermediate Precision | - | ● | ● | - |
| LOD | - | - | ○ | ● |
| LOQ | - | ○ | ● | - |
| Robustness | ○ | ● | ● | ○ |

**Legend:** ● = Required | ○ = May be required | - = Not required

---

## 6. VALIDATION PARAMETERS / ПАРАМЕТРИ ЗА ВАЛИДАЦИЈА

### 6.1 Specificity

**Definition:** Ability to unequivocally assess the analyte in the presence of components expected to be present.

**Procedure:**
1. Analyze samples containing:
   - Target analyte
   - Placebo (excipients without active)
   - Degraded samples (forced degradation)
   - Related substances
   - Process impurities
2. Demonstrate adequate separation/identification

**Acceptance Criteria:**
- No interference at analyte peak/detection
- Peak purity confirmed (for chromatography)
- Resolution ≥ 2.0 between analyte and nearest peak
- For identification: unique response for target

**For Cannabis Methods:**
- Demonstrate separation of all major cannabinoids (THC, THCA, CBD, CBDA, CBN, CBG)
- Confirm no matrix interference
- Peak purity index >0.999

### 6.2 Linearity

**Definition:** Ability to obtain results directly proportional to concentration within a given range.

**Procedure:**
1. Prepare minimum 5 concentration levels (including LOQ to 150% of target)
2. Analyze in triplicate at each level
3. Plot response vs. concentration
4. Calculate regression statistics

**Acceptance Criteria:**
- Correlation coefficient (r²) ≥ 0.999
- Y-intercept within ±2% of 100% response
- Residuals randomly distributed
- Visual inspection of linearity plot

**Concentration Range for Cannabis Assays:**
- 50% to 150% of specification
- Or wider range if products vary significantly

### 6.3 Range

**Definition:** Interval between upper and lower analyte concentration for which suitable precision, accuracy, and linearity have been demonstrated.

**For Different Procedure Types:**

| Procedure | Range |
|-----------|-------|
| Assay | 80-120% of test concentration |
| Content Uniformity | 70-130% of test concentration |
| Dissolution | ±20% over specified range |
| Impurity Testing | LOQ to 120% of specification |

### 6.4 Accuracy

**Definition:** Closeness of agreement between accepted reference value and value found.

**Approaches:**
1. **Comparison to reference standard**: For pure compounds
2. **Spiked recovery**: Add known amount to matrix
3. **Standard addition**: For matrix effects

**Procedure (Spiked Recovery):**
1. Prepare samples at minimum 3 levels (low, medium, high)
2. 3 replicates at each level (minimum 9 determinations)
3. Calculate % recovery

**Acceptance Criteria:**
- Mean recovery: 98.0-102.0% (for assay)
- Mean recovery: 80-120% (for impurities at LOQ level)
- Individual recovery RSD ≤ 2%

### 6.5 Precision

#### 6.5.1 Repeatability (Intra-assay Precision)

**Procedure:**
- Option 1: 6 determinations at 100% concentration
- Option 2: 3 determinations at 3 concentrations (low, medium, high)

**Acceptance Criteria:**
- RSD ≤ 2.0% for assay
- RSD ≤ 5.0% for impurity methods

#### 6.5.2 Intermediate Precision (Intra-laboratory)

**Variables to Study:**
- Different days (minimum 3)
- Different analysts (minimum 2)
- Different instruments (if applicable)

**Acceptance Criteria:**
- RSD ≤ 3.0% for assay methods
- RSD ≤ 10% for impurity methods

#### 6.5.3 Reproducibility (Inter-laboratory)

**When Required:**
- Method transfer between sites
- Multi-site validation
- Standardization of methods

**Acceptance Criteria:**
- Defined based on method requirements
- Typically RSD ≤ 5% for assay

### 6.6 Limit of Detection (LOD)

**Definition:** Lowest amount of analyte that can be detected but not necessarily quantified.

**Determination Methods:**

**Method 1: Signal-to-Noise (S/N) Ratio**
- LOD = concentration giving S/N ≥ 3:1
- Document noise determination method

**Method 2: Standard Deviation of Response and Slope**
```
LOD = (3.3 × σ) / S

Where:
σ = standard deviation of response (y-intercepts or residuals)
S = slope of calibration curve
```

**Method 3: Visual Evaluation**
- Lowest concentration at which analyte is reliably detected
- Must be confirmed experimentally

### 6.7 Limit of Quantitation (LOQ)

**Definition:** Lowest amount of analyte that can be quantified with acceptable precision and accuracy.

**Determination Methods:**

**Method 1: Signal-to-Noise (S/N) Ratio**
- LOQ = concentration giving S/N ≥ 10:1

**Method 2: Standard Deviation and Slope**
```
LOQ = (10 × σ) / S
```

**Verification:**
- Prepare samples at calculated LOQ
- Demonstrate acceptable precision (RSD ≤ 10%)
- Demonstrate acceptable accuracy (80-120% recovery)

### 6.8 Robustness

**Definition:** Measure of method's capacity to remain unaffected by small, deliberate variations in parameters.

**Parameters to Evaluate (HPLC):**
- Mobile phase composition (±2%)
- pH of mobile phase (±0.1 unit)
- Column temperature (±2°C)
- Flow rate (±0.1 mL/min)
- Different columns (same type, different lots)
- Sample stability (time in autosampler)

**Parameters to Evaluate (GC):**
- Oven temperature program (±2°C)
- Flow rate (±10%)
- Injection volume (±10%)
- Column age/different lot

**Acceptance Criteria:**
- Results remain within method specifications
- Identify critical parameters requiring strict control
- System suitability criteria met

---

## 7. VALIDATION PROTOCOL / ПРОТОКОЛ ЗА ВАЛИДАЦИЈА

### 7.1 Protocol Contents

Each method validation protocol shall include:

1. **Objective and Scope**
   - Method description
   - Intended use
   - Matrices covered

2. **Responsibilities**
   - Protocol author
   - Execution team
   - Approvers

3. **Equipment and Materials**
   - Instruments required
   - Reference standards
   - Reagents and solvents
   - Sample preparation materials

4. **Method Description**
   - Detailed procedure
   - Instrument parameters
   - Calculations

5. **Validation Parameters**
   - Parameters to be evaluated
   - Experimental design
   - Number of determinations

6. **Acceptance Criteria**
   - Criteria for each parameter
   - Overall method acceptance

7. **Data Analysis**
   - Statistical methods
   - Calculations

8. **Documentation**
   - Raw data requirements
   - Report format

9. **Approval Signatures**

### 7.2 Protocol Approval

| Role | Requirement |
|------|-------------|
| Author | Sign protocol as prepared |
| Reviewer (QC) | Technical review |
| QA | Compliance review |
| QC Manager | Approve to execute |

---

## 8. CANNABIS-SPECIFIC METHOD VALIDATION / ВАЛИДАЦИЈА СПЕЦИФИЧНА ЗА КАНАБИС

### 8.1 Cannabinoid Potency Method (HPLC)

**Analytes:**
- Δ9-THC, THCA, Total THC
- CBD, CBDA, Total CBD
- CBN, CBG, CBC (as applicable)

**Specificity Requirements:**
- Baseline resolution of all analytes
- No matrix interference (plant, extract, formulation)
- Peak purity confirmation
- Forced degradation (heat, light, oxidation)

**Linearity:**
- Range: 50-150% of expected concentration
- Minimum 5 levels
- r² ≥ 0.999 for each analyte

**Accuracy:**
- Spiked recovery at 3 levels
- Recovery 98-102% for major cannabinoids
- Recovery 90-110% for minor cannabinoids

**Precision:**
- Repeatability RSD ≤ 2%
- Intermediate precision RSD ≤ 3%

**Robustness Parameters:**
- Column temperature
- Mobile phase ratio
- Injection volume
- Sample preparation variations

### 8.2 Terpene Profile Method (GC)

**Analytes:** Monoterpenes, sesquiterpenes (20+ compounds typical)

**Specificity:**
- Identify each terpene by retention time and MS spectrum
- Resolution criteria for co-eluting peaks

**Linearity:**
- Individual calibration for each terpene
- r² ≥ 0.99 for each compound

**Precision:**
- RSD ≤ 5% for major terpenes
- RSD ≤ 10% for minor terpenes

### 8.3 Residual Solvents Method (GC-HS)

Per ICH Q3C requirements:

**Analytes:** Class 1, 2, 3 solvents as applicable

**LOD/LOQ:**
- LOQ ≤ 50% of specification limit
- Demonstrate at each solvent's limit

**Accuracy:**
- Spiked matrix recovery
- 80-120% recovery at LOQ level

### 8.4 Heavy Metals Method (ICP-MS/ICP-OES)

Per ICH Q3D requirements:

**Elements:** Pb, Cd, As, Hg (minimum); additional per risk assessment

**Specificity:**
- No polyatomic interferences
- Matrix matched calibration

**LOQ:**
- ≤ 50% of specification limit (J-value)
- Verified at each element

**Accuracy:**
- Spiked matrix recovery
- CRM (Certified Reference Material) accuracy

### 8.5 Pesticide Residues Method (GC-MS/MS, LC-MS/MS)

Per Ph.Eur. requirements:

**Scope:** 60+ pesticides (typical panel)

**LOQ:**
- ≤ 50% of specification limit for each pesticide
- Demonstrate for representative compounds

**Matrix Effects:**
- Evaluate using matrix-matched standards
- Quantify suppression/enhancement

**Stability:**
- Sample extract stability
- Standard stability

### 8.6 Microbiological Methods

Per Ph.Eur. 2.6.12/2.6.13:

**Method Suitability:**
- Growth promotion (media)
- Inhibitory substance neutralization
- Recovery of target organisms

**Validation Elements:**
- LOD for pathogens (present/absent tests)
- LOQ for enumeration tests
- Precision of counting methods

---

## 9. METHOD VERIFICATION / ВЕРИФИКАЦИЈА НА МЕТОДИ

### 9.1 When Verification Applies

Verification is performed for compendial methods (Ph.Eur., USP) when:
- Using published methods as written
- Applying to specific matrix
- First-time implementation in laboratory

### 9.2 Verification Requirements

**Minimum Parameters:**
- Specificity in actual matrix
- Accuracy (recovery)
- Precision (repeatability)
- LOQ verification (for impurity methods)

**Acceptance Criteria:**
- Per compendial specifications
- Or tighter criteria if appropriate

### 9.3 Documentation

- Verification protocol (abbreviated)
- Results summary
- Comparison to compendial requirements
- Approval for use

---

## 10. VALIDATION REPORT / ИЗВЕШТАЈ ОД ВАЛИДАЦИЈА

### 10.1 Report Contents

1. **Executive Summary**
   - Method description
   - Validation outcome
   - Recommendations

2. **Introduction**
   - Purpose and scope
   - Protocol reference

3. **Materials and Equipment**
   - Instruments (model, serial number)
   - Reference standards (lot, purity)
   - Reagents

4. **Method Description**
   - Sample preparation
   - Instrument parameters
   - Calculations

5. **Results**
   - Detailed results for each parameter
   - Data tables
   - Chromatograms/spectra
   - Statistical analysis

6. **Deviations**
   - Any protocol deviations
   - Impact assessment

7. **Discussion**
   - Interpretation of results
   - Comparison to acceptance criteria
   - Any limitations identified

8. **Conclusions**
   - Validation status
   - Method applicability
   - Any restrictions on use

9. **Attachments**
   - Raw data
   - Calculations
   - Representative chromatograms

### 10.2 Report Approval

| Role | Responsibility |
|------|----------------|
| Author | Technical accuracy |
| Reviewer | Technical verification |
| QC Manager | Method approval |
| QA Manager | Compliance approval |
| QP | Final approval for batch release methods |

---

## 11. PARTIAL VALIDATION/REVALIDATION / ДЕЛУМНА ВАЛИДАЦИЈА

### 11.1 Triggers for Revalidation

Partial or full revalidation required when:
- Change in instrument type
- Change in sample matrix
- Change in method parameters
- Regulatory requirement changes
- Trend of OOS/OOT results
- Method transfer to different site

### 11.2 Revalidation Scope

| Change | Validation Parameters Required |
|--------|-------------------------------|
| New instrument (same type) | Specificity, precision, accuracy |
| Different column lot | Specificity, system suitability |
| New matrix | Specificity, accuracy, precision |
| Method parameter change | Per change assessment |
| Different laboratory | Full validation or transfer protocol |

### 11.3 Change Control Integration

- All method changes through change control (QA_00.06)
- Validation impact assessment required
- Revalidation scope determined
- Documentation updated

---

## 12. METHOD TRANSFER / ТРАНСФЕР НА МЕТОДИ

### 12.1 Transfer Protocol Requirements

When transferring validated methods:
1. Sending laboratory (SL) provides validation documentation
2. Receiving laboratory (RL) executes transfer protocol
3. Comparative testing performed
4. Statistical comparison of results

### 12.2 Transfer Testing

**Minimum Requirements:**
- Same samples tested at both sites
- Blind samples preferred
- Statistical comparison (t-test, F-test)
- Acceptance criteria defined

**Acceptance Criteria:**
- Results agree within predefined limits
- No statistically significant bias
- RL precision comparable to SL

### 12.3 Documentation

- Transfer protocol
- Training documentation
- Results comparison
- Transfer report
- Method authorization at RL

---

## 13. REFERENCES / РЕФЕРЕНЦИ

### 13.1 Regulatory References
- ICH Q2(R1) Validation of Analytical Procedures
- ICH Q2(R2)/Q14 (when applicable)
- European Pharmacopoeia, General Chapter 2.2
- EU GMP Guide, Part I, Chapter 6
- EU GMP Annex 15
- USP General Chapter <1225>
- USP General Chapter <1226>

### 13.2 Internal References
- QC_01.01 - QC Laboratory Management
- QC_01.08 - Cannabinoid Content Testing (HPLC)
- QC_01.14 - Method Validation Protocol
- QA_00.06 - Change Control
- QA_00.10 - OOS Investigation

---

## 14. APPENDICES / ПРИЛОЗИ

### Appendix A: Method Validation Protocol Template

```
ANALYTICAL METHOD VALIDATION PROTOCOL
Protocol No.: VAL-AM-XXX-XX

1. OBJECTIVE
To validate the [method name] for the determination of [analyte(s)]
in [matrix/product].

2. SCOPE
This protocol covers validation of [HPLC/GC/etc.] method for:
- [Product/material 1]
- [Product/material 2]

3. RESPONSIBILITIES
Author: _________________
Execution: _______________
Review: _________________
Approval: ________________

4. EQUIPMENT AND MATERIALS

Equipment:
| Equipment | Model | ID Number |
|-----------|-------|-----------|
|           |       |           |

Reference Standards:
| Standard | Lot No. | Purity | Expiry |
|----------|---------|--------|--------|
|          |         |        |        |

5. METHOD DESCRIPTION
[Include detailed procedure]

6. VALIDATION PARAMETERS

6.1 Specificity
Design: _______________________________________
Acceptance Criteria: ___________________________

6.2 Linearity
Range: ________________________________________
Levels: _______________________________________
Replicates: ___________________________________
Acceptance Criteria: r² ≥ 0.999

6.3 Accuracy
Levels: Low (___%), Medium (___%), High (___%)
Replicates: 3 at each level
Acceptance Criteria: Recovery 98-102%

6.4 Precision
Repeatability: 6 determinations at 100%
Acceptance Criteria: RSD ≤ 2%
Intermediate Precision: 2 analysts × 3 days
Acceptance Criteria: RSD ≤ 3%

6.5 LOD/LOQ (if applicable)
Method: _____________________________________
Acceptance Criteria: __________________________

6.6 Robustness
Parameters: _________________________________
Acceptance Criteria: __________________________

7. DATA ANALYSIS
[Statistical methods to be used]

8. ACCEPTANCE CRITERIA SUMMARY
[Complete summary table]

9. PROTOCOL APPROVAL

Prepared by: _________________ Date: _________
Reviewed by: _________________ Date: _________
Approved by: _________________ Date: _________
```

### Appendix B: Validation Results Summary Table

```
METHOD VALIDATION RESULTS SUMMARY
Method: ___________________
Protocol No.: ______________

PARAMETER RESULTS:

| Parameter | Specification | Result | Pass/Fail |
|-----------|---------------|--------|-----------|
| Specificity | No interference | | |
| Linearity (r²) | ≥ 0.999 | | |
| Range | [specify] | | |
| Accuracy - Low | 98-102% | | |
| Accuracy - Medium | 98-102% | | |
| Accuracy - High | 98-102% | | |
| Repeatability (RSD) | ≤ 2% | | |
| Intermediate Precision (RSD) | ≤ 3% | | |
| LOD | [specify] | | |
| LOQ | [specify] | | |
| Robustness | Per SST | | |

OVERALL RESULT: □ VALIDATED □ NOT VALIDATED

Prepared by: _________________ Date: _________
Reviewed by: _________________ Date: _________
Approved by: _________________ Date: _________
```

### Appendix C: Linearity Data Sheet

```
LINEARITY DATA SHEET
Method: ___________________
Analyte: __________________

Calibration Data:
| Level | Concentration | Rep 1 | Rep 2 | Rep 3 | Mean | RSD% |
|-------|---------------|-------|-------|-------|------|------|
| 1 |               |       |       |       |      |      |
| 2 |               |       |       |       |      |      |
| 3 |               |       |       |       |      |      |
| 4 |               |       |       |       |      |      |
| 5 |               |       |       |       |      |      |

Regression Statistics:
Slope: ______________
Intercept: __________
r²: ________________
Residual Sum of Squares: ____________

Y-Intercept as % of 100% response: __________%
Acceptance: ≤ ±2%

Result: □ Pass □ Fail

Analyst: ___________________ Date: ___________
```

### Appendix D: Accuracy/Recovery Data Sheet

```
ACCURACY DATA SHEET
Method: ___________________
Analyte: __________________

| Level | Spiked Amount | Found Amount | % Recovery |
|-------|---------------|--------------|------------|
| Low-1 |               |              |            |
| Low-2 |               |              |            |
| Low-3 |               |              |            |
| Med-1 |               |              |            |
| Med-2 |               |              |            |
| Med-3 |               |              |            |
| High-1|               |              |            |
| High-2|               |              |            |
| High-3|               |              |            |

Statistics:
| Level | Mean Recovery | RSD% |
|-------|---------------|------|
| Low   |               |      |
| Medium|               |      |
| High  |               |      |
| Overall|              |      |

Acceptance Criteria: Mean 98-102%, RSD ≤ 2%
Result: □ Pass □ Fail

Analyst: ___________________ Date: ___________
```

---

**Document End**

*This document is the property of Purely Plant GmbH and contains confidential information. Unauthorized copying or distribution is prohibited.*
