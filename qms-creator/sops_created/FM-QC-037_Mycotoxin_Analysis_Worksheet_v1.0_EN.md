<style>
.var { color: #00d9ff; font-weight: bold; }
</style>

# FM-QC-037: Mycotoxin Analysis Worksheet

## Form Information

| Field | Value |
|-------|-------|
| **Form Number** | FM-QC-037 |
| **Version** | 1.0 |
| **Effective Date** | <span class="var">[EFFECTIVE_DATE]</span> |
| **Parent SOP** | QC_04.08 Mycotoxin Testing |
| **Department** | Quality Control |

---

## Section 1: Sample Information

| Field | Entry |
|-------|-------|
| **Sample ID** | |
| **Batch Number** | |
| **Product Name/Cultivar** | |
| **Sample Type** | ☐ Dried Flower ☐ Extract ☐ Edible ☐ Other: _______ |
| **Sample Weight Received** | _________ g |
| **Storage Condition** | ☐ -20°C ☐ 2-8°C ☐ Room Temp |
| **Visible Mold Observed** | ☐ Yes ☐ No |
| **Date Received** | |
| **Date of Analysis** | |
| **Analyst** | |
| **Reviewer** | |

---

## Section 2: Method Selection

| Method | Selected | Rationale |
|--------|----------|-----------|
| **ELISA Screening** | ☐ | Rapid screening |
| **LC-MS/MS Confirmation** | ☐ | Quantitative/Regulatory |
| **IAC Cleanup + LC-MS/MS** | ☐ | Ph. Eur. compliance |

---

## Section 3: Sample Preparation

### 3.1 Homogenization

| Parameter | Value | Specification |
|-----------|-------|---------------|
| **Sample Weight Ground** | _________ g | <span class="var">[≥5 g]</span> |
| **Grinder ID** | | |
| **Particle Size Achieved** | ☐ <1 mm | <span class="var">[<1 mm]</span> |
| **Grinder Cleaned** | ☐ Yes ☐ No | Required |

### 3.2 QuEChERS Extraction (LC-MS/MS Method)

| Step | Value | Specification |
|------|-------|---------------|
| **Sample Weight** | _________ g | <span class="var">[2.0 ± 0.1 g]</span> |
| **Water Added** | _________ mL | <span class="var">[10 mL]</span> |
| **Hydration Time** | _________ min | <span class="var">[15 min]</span> |
| **IS Solution Added** | _________ µL | <span class="var">[100 µL]</span> |
| **Extraction Solvent** | _________ mL | <span class="var">[10 mL ACN:H₂O:AA]</span> |
| **Shaking Time** | _________ min | <span class="var">[10 min]</span> |
| **MgSO₄ Added** | _________ g | <span class="var">[4 g]</span> |
| **NaCl Added** | _________ g | <span class="var">[1 g]</span> |
| **Centrifuge Speed** | _________ rpm | <span class="var">[4000 rpm]</span> |
| **Centrifuge Time** | _________ min | <span class="var">[10 min]</span> |

### 3.3 Cleanup Method Used

☐ **MycoSep 226**
| Step | Value |
|------|-------|
| **Supernatant Applied** | _________ mL |
| **Column Lot #** | |

☐ **dSPE Cleanup**
| Step | Value | Specification |
|------|-------|---------------|
| **Supernatant Transferred** | _________ mL | <span class="var">[6 mL]</span> |
| **C18** | _________ mg | <span class="var">[400 mg]</span> |
| **PSA** | _________ mg | <span class="var">[150 mg]</span> |
| **MgSO₄** | _________ mg | <span class="var">[900 mg]</span> |

### 3.4 Final Extract

| Parameter | Value | Specification |
|-----------|-------|---------------|
| **Volume Evaporated** | _________ mL | <span class="var">[4 mL]</span> |
| **Evaporation Temp** | _________ °C | <span class="var">[40°C]</span> |
| **Reconstitution Volume** | _________ mL | <span class="var">[1 mL]</span> |
| **Reconstitution Solvent** | | Mobile Phase A:B (50:50) |
| **Filtered** | ☐ Yes ☐ No | <span class="var">[0.22 µm PTFE]</span> |

---

## Section 4: ELISA Screening (if applicable)

### 4.1 Kit Information

| Parameter | Value |
|-----------|-------|
| **Kit Name** | |
| **Kit Lot #** | |
| **Kit Expiry** | |
| **Target Analyte** | ☐ Total Aflatoxins ☐ Ochratoxin A ☐ Other: _____ |

### 4.2 Sample Preparation for ELISA

| Step | Value | Specification |
|------|-------|---------------|
| **Sample Weight** | _________ g | <span class="var">[5 g]</span> |
| **Extraction Solvent** | _________ mL | <span class="var">[25 mL MeOH:H₂O 70:30]</span> |
| **Shaking Time** | _________ min | <span class="var">[3 min]</span> |
| **Dilution Factor** | | Per kit instructions |

### 4.3 ELISA Plate Layout

| Well | Sample Type | Absorbance (450 nm) | %B/B₀ | Conc (µg/kg) |
|------|-------------|---------------------|-------|--------------|
| A1 | Standard 0 | | 100% | 0 |
| A2 | Standard 0 | | | |
| B1 | Standard 1 | | | |
| B2 | Standard 1 | | | |
| C1 | Standard 2 | | | |
| C2 | Standard 2 | | | |
| D1 | Standard 3 | | | |
| D2 | Standard 3 | | | |
| E1 | Standard 4 | | | |
| E2 | Standard 4 | | | |
| F1 | Positive Control | | | |
| F2 | Positive Control | | | |
| G1 | Sample | | | |
| G2 | Sample Duplicate | | | |

### 4.4 ELISA Results

| Parameter | Value | Specification | Pass/Fail |
|-----------|-------|---------------|-----------|
| **Standard Curve r²** | | <span class="var">[≥0.98]</span> | ☐ |
| **Duplicate %CV** | _______% | <span class="var">[≤15%]</span> | ☐ |
| **Positive Control** | _________ µg/kg | Per kit range | ☐ |
| **Sample Result** | _________ µg/kg | | |

### 4.5 ELISA Interpretation

| Result vs Limit | Action |
|-----------------|--------|
| ☐ **<50% of limit** | PASS - No confirmation needed |
| ☐ **50-150% of limit** | Confirm by LC-MS/MS |
| ☐ **>150% of limit** | Presumptive FAIL - Confirm by LC-MS/MS |

---

## Section 5: LC-MS/MS Analysis

### 5.1 Instrument Information

| Parameter | Value |
|-----------|-------|
| **Instrument ID** | |
| **Column ID** | |
| **Column Type** | <span class="var">[C18, 100 × 2.1 mm, 1.7 µm]</span> |
| **Column Lot #** | |
| **Last Qualification Date** | |
| **Mobile Phase A Lot** | |
| **Mobile Phase B Lot** | |

### 5.2 System Suitability

| Parameter | Specification | Actual | Pass/Fail |
|-----------|---------------|--------|-----------|
| **AFB₁ RT** | <span class="var">[5.8 ± 0.1 min]</span> | _________ min | ☐ |
| **AFB₁ Peak Shape** | Symmetrical | | ☐ |
| **IS Response** | <span class="var">[±30%]</span> of expected | | ☐ |
| **S/N at LOQ** | <span class="var">[≥10]</span> | | ☐ |

### 5.3 Calibration Standards

| Level | Aflatoxins (µg/kg) | OTA (µg/kg) | Prep Date | Lot # |
|-------|-------------------|-------------|-----------|-------|
| **Cal 1** | <span class="var">[0.2]</span> | <span class="var">[1.0]</span> | | |
| **Cal 2** | <span class="var">[0.5]</span> | <span class="var">[2.5]</span> | | |
| **Cal 3** | <span class="var">[1.0]</span> | <span class="var">[5.0]</span> | | |
| **Cal 4** | <span class="var">[2.0]</span> | <span class="var">[10.0]</span> | | |
| **Cal 5** | <span class="var">[5.0]</span> | <span class="var">[20.0]</span> | | |
| **Cal 6** | <span class="var">[10.0]</span> | <span class="var">[50.0]</span> | | |

### 5.4 Calibration Curve Results

| Mycotoxin | r² | Slope | Intercept | Spec (r²) | Pass/Fail |
|-----------|-----|-------|-----------|-----------|-----------|
| **Aflatoxin B₁** | | | | <span class="var">[≥0.99]</span> | ☐ |
| **Aflatoxin B₂** | | | | <span class="var">[≥0.99]</span> | ☐ |
| **Aflatoxin G₁** | | | | <span class="var">[≥0.99]</span> | ☐ |
| **Aflatoxin G₂** | | | | <span class="var">[≥0.99]</span> | ☐ |
| **Ochratoxin A** | | | | <span class="var">[≥0.99]</span> | ☐ |

---

## Section 6: Quality Control Results

### 6.1 Blanks

| QC Type | Aflatoxins | OTA | Specification | Pass/Fail |
|---------|------------|-----|---------------|-----------|
| **Reagent Blank** | ☐ ND | ☐ ND | No interference | ☐ |
| **Matrix Blank** | ☐ ND | ☐ ND | <LOQ | ☐ |

### 6.2 Quality Control Samples

| QC Level | Mycotoxin | Nominal (µg/kg) | Found (µg/kg) | Recovery % | Spec | Pass/Fail |
|----------|-----------|-----------------|---------------|------------|------|-----------|
| **Low QC** | AFB₁ | | | | <span class="var">[±30%]</span> | ☐ |
| **Low QC** | OTA | | | | <span class="var">[±30%]</span> | ☐ |
| **Mid QC** | AFB₁ | | | | <span class="var">[±25%]</span> | ☐ |
| **Mid QC** | OTA | | | | <span class="var">[±25%]</span> | ☐ |
| **High QC** | AFB₁ | | | | <span class="var">[±20%]</span> | ☐ |
| **High QC** | OTA | | | | <span class="var">[±20%]</span> | ☐ |

### 6.3 Matrix Spike

| Mycotoxin | Spike Level (µg/kg) | Sample Result | Spiked Result | Recovery % | Spec | Pass/Fail |
|-----------|---------------------|---------------|---------------|------------|------|-----------|
| **AFB₁** | | | | | <span class="var">[70-120%]</span> | ☐ |
| **AFB₂** | | | | | <span class="var">[70-120%]</span> | ☐ |
| **AFG₁** | | | | | <span class="var">[70-120%]</span> | ☐ |
| **AFG₂** | | | | | <span class="var">[70-120%]</span> | ☐ |
| **OTA** | | | | | <span class="var">[70-120%]</span> | ☐ |

### 6.4 Internal Standard Recovery

| Internal Standard | Expected | Found | % Recovery | Spec | Pass/Fail |
|-------------------|----------|-------|------------|------|-----------|
| **¹³C₁₇-AFB₁** | | | | <span class="var">[70-130%]</span> | ☐ |
| **¹³C₂₀-OTA** | | | | <span class="var">[70-130%]</span> | ☐ |

---

## Section 7: Sample Results

### 7.1 Identification Criteria

| Mycotoxin | RT Match (±0.1 min) | Ion Ratio Match (±30%) | Identified? |
|-----------|---------------------|------------------------|-------------|
| **Aflatoxin B₁** | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail | ☐ Yes ☐ No |
| **Aflatoxin B₂** | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail | ☐ Yes ☐ No |
| **Aflatoxin G₁** | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail | ☐ Yes ☐ No |
| **Aflatoxin G₂** | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail | ☐ Yes ☐ No |
| **Ochratoxin A** | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail | ☐ Yes ☐ No |

### 7.2 Quantitative Results

| Mycotoxin | LOQ (µg/kg) | Result (µg/kg) | Limit (µg/kg) | Pass/Fail |
|-----------|-------------|----------------|---------------|-----------|
| **Aflatoxin B₁** | <span class="var">[0.2]</span> | | <span class="var">[2.0]</span> | ☐ |
| **Aflatoxin B₂** | <span class="var">[0.2]</span> | | N/A | N/A |
| **Aflatoxin G₁** | <span class="var">[0.2]</span> | | N/A | N/A |
| **Aflatoxin G₂** | <span class="var">[0.2]</span> | | N/A | N/A |
| **Total Aflatoxins** | | **Calculated:** | <span class="var">[4.0]</span> | ☐ |
| **Ochratoxin A** | <span class="var">[1.0]</span> | | <span class="var">[10.0]</span> | ☐ |

**Total Aflatoxins Calculation:**
Total = AFB₁ + AFB₂ + AFG₁ + AFG₂ = _________ + _________ + _________ + _________ = _________ µg/kg

### 7.3 Extended Panel (if tested)

| Mycotoxin | LOQ (µg/kg) | Result (µg/kg) | Action Level (µg/kg) | Status |
|-----------|-------------|----------------|----------------------|--------|
| **Deoxynivalenol** | <span class="var">[50]</span> | | <span class="var">[1000]</span> | |
| **Zearalenone** | <span class="var">[10]</span> | | <span class="var">[100]</span> | |
| **Fumonisin B₁** | <span class="var">[25]</span> | | <span class="var">[1000]</span> | |
| **T-2 Toxin** | <span class="var">[10]</span> | | <span class="var">[100]</span> | |
| **HT-2 Toxin** | <span class="var">[10]</span> | | <span class="var">[100]</span> | |

---

## Section 8: Results Summary

| Test | Result | Specification | Determination |
|------|--------|---------------|---------------|
| **Aflatoxin B₁** | _________ µg/kg | <span class="var">[≤2.0 µg/kg]</span> | ☐ PASS ☐ FAIL |
| **Total Aflatoxins** | _________ µg/kg | <span class="var">[≤4.0 µg/kg]</span> | ☐ PASS ☐ FAIL |
| **Ochratoxin A** | _________ µg/kg | <span class="var">[≤10.0 µg/kg]</span> | ☐ PASS ☐ FAIL |

**Overall Mycotoxin Result:** ☐ **PASS** ☐ **FAIL**

---

## Section 9: Deviations and Comments

| Item | Description |
|------|-------------|
| **Deviations** | |
| **Observations** | |
| **Retest Required** | ☐ Yes ☐ No |
| **Reason** | |

---

## Section 10: Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| **Analyst** | | | |
| **Reviewer** | | | |
| **QC Manager** (if OOS) | | | |

---

## Section 11: Data File References

| Item | Reference |
|------|-----------|
| **LC-MS/MS Data File** | |
| **ELISA Raw Data** | |
| **Processing Method** | |
| **Sequence File** | |

---

*Form FM-QC-037 Version 1.0*
