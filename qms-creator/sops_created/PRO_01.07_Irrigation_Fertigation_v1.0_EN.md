# PRO_01.07 Irrigation and Fertigation Management

<style>
.var { color: #00d9ff; font-weight: bold; }
</style>

---

## DOCUMENT CONTROL INFORMATION

| Field | Value |
|-------|-------|
| Document Number | <span class="var">[PRO_01.07]</span> |
| Version | <span class="var">[1.0]</span> |
| Effective Date | <span class="var">[DD-MMM-YYYY]</span> |
| Review Date | <span class="var">[DD-MMM-YYYY]</span> |
| Department | <span class="var">[Cultivation]</span> |
| Document Owner | <span class="var">[Cultivation Manager]</span> |

---

## 1. PURPOSE

This SOP establishes procedures for irrigation and fertigation (fertilizer injection) systems used in cannabis cultivation at <span class="var">[FACILITY_NAME]</span>, ensuring consistent and optimal plant nutrition and water delivery.

---

## 2. SCOPE

Applies to:
- Water quality management
- Nutrient solution preparation
- Irrigation system operation
- pH and EC monitoring and adjustment
- Fertigation scheduling
- System maintenance and calibration

---

## 3. WATER QUALITY REQUIREMENTS

### 3.1 Source Water Specifications

| Parameter | Target | Acceptable Range | Action Limit |
|-----------|--------|------------------|--------------|
| pH | <span class="var">[6.5-7.0]</span> | <span class="var">[6.0-7.5]</span> | <span class="var">[<5.5 or >8.0]</span> |
| EC (background) | <span class="var">[<0.3 mS/cm]</span> | <span class="var">[<0.5 mS/cm]</span> | <span class="var">[>0.5 mS/cm]</span> |
| Total Dissolved Solids | <span class="var">[<200 ppm]</span> | <span class="var">[<350 ppm]</span> | <span class="var">[>350 ppm]</span> |
| Chlorine | <span class="var">[<0.5 ppm]</span> | <span class="var">[<1.0 ppm]</span> | <span class="var">[>2.0 ppm]</span> |
| Sodium | <span class="var">[<50 ppm]</span> | <span class="var">[<100 ppm]</span> | <span class="var">[>150 ppm]</span> |
| Bicarbonates | <span class="var">[<100 ppm]</span> | <span class="var">[<150 ppm]</span> | <span class="var">[>200 ppm]</span> |
| Iron | <span class="var">[<1.0 ppm]</span> | <span class="var">[<2.0 ppm]</span> | <span class="var">[>3.0 ppm]</span> |
| Microbial (Total Coliforms) | <span class="var">[<1 CFU/100mL]</span> | <span class="var">[<10 CFU/100mL]</span> | <span class="var">[>100 CFU/100mL]</span> |

### 3.2 Water Treatment

| Treatment | Purpose | Specification |
|-----------|---------|---------------|
| Reverse Osmosis | Remove dissolved solids | <span class="var">[Target <50 ppm TDS]</span> |
| Sediment filtration | Remove particulates | <span class="var">[5 µm pre-filter]</span> |
| UV sterilization | Pathogen control | <span class="var">[40 mJ/cm² minimum]</span> |
| Carbon filtration | Chlorine removal | <span class="var">[If chlorinated source]</span> |

### 3.3 Water Quality Testing Schedule

| Test | Frequency | Method |
|------|-----------|--------|
| pH, EC, TDS | <span class="var">[Daily]</span> | In-house meters |
| Chlorine | <span class="var">[Daily if treated]</span> | Test strips |
| Full mineral analysis | <span class="var">[Quarterly]</span> | External laboratory |
| Microbial | <span class="var">[Monthly]</span> | External laboratory |

---

## 4. NUTRIENT SOLUTION MANAGEMENT

### 4.1 Nutrient Stock Solutions

| Stock | Contents | Concentration | Storage |
|-------|----------|---------------|---------|
| Stock A | <span class="var">[Macro NPK + micros]</span> | <span class="var">[100x concentrate]</span> | <span class="var">[Cool, dark, sealed]</span> |
| Stock B | <span class="var">[Calcium nitrate]</span> | <span class="var">[100x concentrate]</span> | <span class="var">[Separate from A]</span> |
| Stock C (optional) | <span class="var">[Magnesium sulfate]</span> | <span class="var">[100x concentrate]</span> | <span class="var">[Separate storage]</span> |
| pH Down | <span class="var">[Phosphoric acid 85%]</span> | <span class="var">[As supplied]</span> | <span class="var">[Acid cabinet]</span> |
| pH Up | <span class="var">[Potassium hydroxide]</span> | <span class="var">[As supplied]</span> | <span class="var">[Alkali cabinet]</span> |

**NEVER mix Stock A and Stock B concentrates directly - precipitation will occur**

### 4.2 Feeding Schedules by Growth Phase

#### 4.2.1 Propagation/Clones

| Week | N-P-K Ratio | Target EC | pH | Notes |
|------|-------------|-----------|-----|-------|
| 1 | <span class="var">[Minimal]</span> | <span class="var">[0.4-0.6]</span> | <span class="var">[5.5-5.8]</span> | Plain water initially |
| 2 | <span class="var">[1-1-1]</span> | <span class="var">[0.6-0.8]</span> | <span class="var">[5.6-6.0]</span> | Light veg feed |

#### 4.2.2 Vegetative Phase

| Week | N-P-K Ratio | Target EC | pH | Notes |
|------|-------------|-----------|-----|-------|
| 1-2 | <span class="var">[3-1-2]</span> | <span class="var">[1.0-1.2]</span> | <span class="var">[5.8-6.0]</span> | Establishment |
| 3-4 | <span class="var">[3-1-2]</span> | <span class="var">[1.4-1.6]</span> | <span class="var">[5.8-6.0]</span> | Active growth |
| 5+ | <span class="var">[3-1-2]</span> | <span class="var">[1.6-1.8]</span> | <span class="var">[6.0]</span> | Pre-transition |

#### 4.2.3 Flowering Phase

| Week | N-P-K Ratio | Target EC | pH | Notes |
|------|-------------|-----------|-----|-------|
| 1-2 | <span class="var">[2-2-3]</span> | <span class="var">[1.6-1.8]</span> | <span class="var">[6.0]</span> | Transition |
| 3-4 | <span class="var">[1-3-4]</span> | <span class="var">[1.8-2.0]</span> | <span class="var">[6.0-6.2]</span> | Early bloom |
| 5-6 | <span class="var">[1-3-4]</span> | <span class="var">[1.8-2.0]</span> | <span class="var">[6.0-6.2]</span> | Bulk phase + PK boost |
| 7-8 | <span class="var">[0.5-3-4]</span> | <span class="var">[1.6-1.8]</span> | <span class="var">[6.2]</span> | Ripen, reduce N |
| 9+ | <span class="var">[Plain water]</span> | <span class="var">[0.0-0.3]</span> | <span class="var">[6.0]</span> | Flush |

### 4.3 Nutrient Solution Preparation

#### 4.3.1 Mixing Procedure

1. Calculate required volumes based on:
   - Number of plants
   - Container size
   - Expected consumption

2. Fill reservoir with treated water:
   - Temperature: <span class="var">[18-22°C]</span>
   - Allow to equilibrate <span class="var">[30 minutes]</span>

3. Add nutrients in order:
   a. Add Stock A, mix thoroughly
   b. Add Stock B, mix thoroughly
   c. Add supplements (if used)
   d. Mix for <span class="var">[10-15 minutes]</span>

4. Measure and record:
   - EC: Compare to target
   - pH: Adjust as needed

5. pH Adjustment:
   - Add pH Down/Up in small increments
   - Mix between additions
   - Recheck until target achieved

6. Document in Nutrient Preparation Log <span class="var">[FM-FERT-001]</span>

#### 4.3.2 Solution Maintenance

| Parameter | Check Frequency | Action |
|-----------|-----------------|--------|
| pH | <span class="var">[2x daily]</span> | Adjust if outside range |
| EC | <span class="var">[2x daily]</span> | Top up or replace |
| Temperature | <span class="var">[Daily]</span> | Chill/heat if needed |
| Volume | <span class="var">[Daily]</span> | Maintain minimum level |
| Reservoir cleaning | <span class="var">[Weekly or between batches]</span> | Full clean/sanitize |

---

## 5. IRRIGATION SYSTEM OPERATION

### 5.1 System Components

| Component | Specification | Maintenance |
|-----------|---------------|-------------|
| Reservoir | <span class="var">[Food-grade, light-proof]</span> | <span class="var">[Weekly clean]</span> |
| Pump | <span class="var">[Sized for flow rate]</span> | <span class="var">[Monthly inspection]</span> |
| Filters | <span class="var">[150 mesh inline]</span> | <span class="var">[Weekly clean/replace]</span> |
| Main lines | <span class="var">[PVC/PE, UV resistant]</span> | <span class="var">[Annual inspection]</span> |
| Drip emitters | <span class="var">[2-4 L/hr pressure compensating]</span> | <span class="var">[Monthly check]</span> |
| Dosing system | <span class="var">[EC/pH controlled injector]</span> | <span class="var">[Daily calibration check]</span> |

### 5.2 Irrigation Scheduling

#### 5.2.1 Schedule Determination

Factors to consider:
- Plant size and growth phase
- Container size and medium type
- Environmental conditions (VPD)
- Time since last irrigation
- Runoff from previous event

#### 5.2.2 Typical Schedules

| Growth Phase | Events/Day | Volume/Event | Target Runoff |
|--------------|------------|--------------|---------------|
| Clones | <span class="var">[Mist 4-6x]</span> | <span class="var">[Light mist]</span> | <span class="var">[None]</span> |
| Veg Week 1-2 | <span class="var">[2-3]</span> | <span class="var">[5-10% container]</span> | <span class="var">[10-15%]</span> |
| Veg Week 3+ | <span class="var">[3-5]</span> | <span class="var">[5-10% container]</span> | <span class="var">[15-20%]</span> |
| Flower Week 1-4 | <span class="var">[4-6]</span> | <span class="var">[5-10% container]</span> | <span class="var">[15-20%]</span> |
| Flower Week 5+ | <span class="var">[4-5]</span> | <span class="var">[5-10% container]</span> | <span class="var">[15-20%]</span> |
| Flush | <span class="var">[2-3]</span> | <span class="var">[Higher volume]</span> | <span class="var">[20-30%]</span> |

#### 5.2.3 Timing Considerations

- First irrigation: <span class="var">[30-60 minutes after lights on]</span>
- Last irrigation: <span class="var">[2-3 hours before lights off]</span>
- Avoid irrigation during dark period
- Space events evenly during light period

### 5.3 Daily Irrigation Procedure

1. **Pre-Irrigation Checks:**
   - Verify reservoir levels adequate
   - Check pH and EC of solution
   - Inspect system for leaks/blockages
   - Confirm timer/controller settings

2. **During Irrigation:**
   - Observe flow to emitters
   - Check for uneven distribution
   - Note any plant stress response

3. **Post-Irrigation:**
   - Measure and record runoff:
     - Volume (calculate %)
     - pH
     - EC
   - Compare to feed values
   - Document in Daily Irrigation Log <span class="var">[FM-FERT-002]</span>

### 5.4 Runoff Analysis and Response

| Runoff EC vs Feed EC | Interpretation | Action |
|----------------------|----------------|--------|
| Runoff EC < Feed EC | Underfeeding or lockout | Check root health, verify feed |
| Runoff EC = Feed EC (±10%) | Optimal | Continue schedule |
| Runoff EC > Feed EC (10-25%) | Slight salt accumulation | Monitor, slight flush if persists |
| Runoff EC > Feed EC (>25%) | Significant accumulation | Flush with plain water, reduce EC |

---

## 6. EQUIPMENT CALIBRATION

### 6.1 pH Meter Calibration

**Frequency:** <span class="var">[Daily before use, or weekly minimum]</span>

**Procedure:**
1. Rinse probe with distilled water
2. Calibrate with pH 7.0 buffer
3. Calibrate with pH 4.0 buffer
4. Verify with pH 10.0 (optional 3-point)
5. Record in Calibration Log <span class="var">[FM-CAL-001]</span>

**Acceptance:** <span class="var">[±0.1 pH from buffer value]</span>

### 6.2 EC Meter Calibration

**Frequency:** <span class="var">[Weekly minimum]</span>

**Procedure:**
1. Rinse probe with distilled water
2. Calibrate with <span class="var">[1.413 mS/cm]</span> standard
3. Verify with second standard (optional)
4. Record in Calibration Log

**Acceptance:** <span class="var">[±0.1 mS/cm from standard]</span>

### 6.3 Dosing System Verification

**Frequency:** <span class="var">[Weekly]</span>

**Procedure:**
1. Prepare solution manually to known EC
2. Run through dosing system
3. Measure output EC
4. Compare to setpoint
5. Adjust injectors if needed

---

## 7. SYSTEM MAINTENANCE

### 7.1 Routine Maintenance Schedule

| Task | Frequency | Responsible |
|------|-----------|-------------|
| Check emitter flow | <span class="var">[Daily]</span> | Cultivation Tech |
| Clean filters | <span class="var">[Weekly]</span> | Cultivation Tech |
| Clean reservoir | <span class="var">[Weekly/batch change]</span> | Cultivation Tech |
| Flush lines | <span class="var">[Monthly]</span> | Maintenance/Cultivation |
| Inspect pumps | <span class="var">[Monthly]</span> | Maintenance |
| Replace emitters | <span class="var">[Annually or as needed]</span> | Maintenance |
| Full system sanitization | <span class="var">[Between crops]</span> | Cultivation/Maintenance |

### 7.2 System Sanitization

**Between crops or upon contamination:**

1. Drain system completely
2. Prepare sanitization solution:
   - <span class="var">[Hydrogen peroxide 3%]</span> or
   - <span class="var">[Hypochlorous acid 50-100 ppm]</span>
3. Fill and circulate through system <span class="var">[30 minutes]</span>
4. Drain completely
5. Rinse with clean water <span class="var">[2-3 times]</span>
6. Document in System Maintenance Log <span class="var">[FM-FERT-003]</span>

---

## 8. TROUBLESHOOTING

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| Uneven watering | Clogged emitters, low pressure | Clean/replace emitters, check pump |
| pH drift (rising) | Algae growth, carbonate buildup | Clean reservoir, check water source |
| pH drift (falling) | Organic acid production | Check root health, clean system |
| EC increasing in reservoir | Evaporation exceeds uptake | Top up with plain water |
| EC decreasing in reservoir | Heavy plant uptake | Add nutrient concentrate |
| Nutrient deficiency despite adequate EC | pH lockout, root issues | Check pH, inspect roots |

---

## 9. DOCUMENTATION

| Document | Form Number | Retention |
|----------|-------------|-----------|
| Nutrient Preparation Log | <span class="var">[FM-FERT-001]</span> | <span class="var">[5 years]</span> |
| Daily Irrigation Log | <span class="var">[FM-FERT-002]</span> | <span class="var">[5 years]</span> |
| System Maintenance Log | <span class="var">[FM-FERT-003]</span> | <span class="var">[5 years]</span> |
| Water Quality Records | <span class="var">[FM-FERT-004]</span> | <span class="var">[5 years]</span> |
| Calibration Log | <span class="var">[FM-CAL-001]</span> | <span class="var">[5 years]</span> |

---

## 10. REVISION HISTORY

| Version | Effective Date | Author | Change Description |
|---------|---------------|--------|-------------------|
| <span class="var">[1.0]</span> | <span class="var">[DD-MMM-YYYY]</span> | <span class="var">[Author Name]</span> | Initial release |

---

## APPROVAL SIGNATURES

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Author | <span class="var">[Author Name]</span> | _________________ | _________ |
| Reviewed By | <span class="var">[Cultivation Manager]</span> | _________________ | _________ |
| Approved By | <span class="var">[QA Manager]</span> | _________________ | _________ |

---

**END OF DOCUMENT PRO_01.07**
