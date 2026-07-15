# PRO_01.08 Environmental Monitoring and Control

<style>
.var { color: #00d9ff; font-weight: bold; }
</style>

---

## DOCUMENT CONTROL INFORMATION

| Field | Value |
|-------|-------|
| Document Number | <span class="var">[PRO_01.08]</span> |
| Version | <span class="var">[1.0]</span> |
| Effective Date | <span class="var">[DD-MMM-YYYY]</span> |
| Review Date | <span class="var">[DD-MMM-YYYY]</span> |
| Department | <span class="var">[Cultivation]</span> |
| Document Owner | <span class="var">[Cultivation Manager]</span> |

---

## 1. PURPOSE

This SOP establishes requirements for environmental monitoring and control systems in cannabis cultivation areas at <span class="var">[FACILITY_NAME]</span>, ensuring optimal growing conditions and compliance with EU GMP requirements for controlled environment agriculture.

---

## 2. SCOPE

Applies to:
- Temperature and humidity monitoring
- CO₂ monitoring and supplementation
- Lighting systems and control
- Air handling and circulation
- Environmental data logging and review
- Alarm systems and response

---

## 3. ENVIRONMENTAL PARAMETERS BY AREA

### 3.1 Summary of Target Conditions

| Area | Temp (Day) | Temp (Night) | RH | CO₂ | PPFD | Photoperiod |
|------|------------|--------------|----|----|------|-------------|
| Mother Room | <span class="var">[24°C]</span> | <span class="var">[22°C]</span> | <span class="var">[60%]</span> | <span class="var">[800 ppm]</span> | <span class="var">[500]</span> | <span class="var">[18/6]</span> |
| Propagation | <span class="var">[24°C]</span> | <span class="var">[22°C]</span> | <span class="var">[90-95%]</span>* | <span class="var">[Ambient]</span> | <span class="var">[200]</span> | <span class="var">[18/6]</span> |
| Vegetative | <span class="var">[26°C]</span> | <span class="var">[22°C]</span> | <span class="var">[60%]</span> | <span class="var">[1000 ppm]</span> | <span class="var">[600]</span> | <span class="var">[18/6]</span> |
| Flowering (Early) | <span class="var">[26°C]</span> | <span class="var">[22°C]</span> | <span class="var">[55%]</span> | <span class="var">[1200 ppm]</span> | <span class="var">[800]</span> | <span class="var">[12/12]</span> |
| Flowering (Late) | <span class="var">[24°C]</span> | <span class="var">[20°C]</span> | <span class="var">[45%]</span> | <span class="var">[1000 ppm]</span> | <span class="var">[800]</span> | <span class="var">[12/12]</span> |
| Drying | <span class="var">[18°C]</span> | <span class="var">[18°C]</span> | <span class="var">[60%]</span> | <span class="var">[Ambient]</span> | <span class="var">[Dark]</span> | <span class="var">[N/A]</span> |
| Curing | <span class="var">[18°C]</span> | <span class="var">[18°C]</span> | <span class="var">[60%]</span> | <span class="var">[Ambient]</span> | <span class="var">[Dark]</span> | <span class="var">[N/A]</span> |

*Dome humidity for propagation

### 3.2 Operating Ranges and Alert Limits

| Parameter | Target | Operating Range | Alert Limit | Action Limit |
|-----------|--------|-----------------|-------------|--------------|
| Temperature | <span class="var">[Per area]</span> | <span class="var">[±2°C]</span> | <span class="var">[±3°C]</span> | <span class="var">[±5°C]</span> |
| Humidity | <span class="var">[Per area]</span> | <span class="var">[±5%]</span> | <span class="var">[±8%]</span> | <span class="var">[±12%]</span> |
| CO₂ | <span class="var">[Per area]</span> | <span class="var">[±200 ppm]</span> | <span class="var">[±300 ppm]</span> | <span class="var">[±500 ppm]</span> |
| Light Intensity | <span class="var">[Per area]</span> | <span class="var">[±15%]</span> | <span class="var">[±25%]</span> | <span class="var">[>30%]</span> |

---

## 4. MONITORING EQUIPMENT

### 4.1 Required Monitoring Equipment

| Equipment | Specification | Calibration Frequency | Location |
|-----------|---------------|----------------------|----------|
| Temperature/RH sensor | <span class="var">[±0.5°C, ±3% RH]</span> | <span class="var">[Annual]</span> | <span class="var">[Each room, canopy level]</span> |
| CO₂ sensor | <span class="var">[NDIR, ±50 ppm]</span> | <span class="var">[Annual]</span> | <span class="var">[Each room]</span> |
| Data logger/BMS | <span class="var">[Continuous logging, ≤5 min intervals]</span> | <span class="var">[Per manufacturer]</span> | <span class="var">[Central system]</span> |
| PAR meter | <span class="var">[±5% accuracy]</span> | <span class="var">[Annual]</span> | <span class="var">[Portable, weekly use]</span> |
| Light meter (lux) | <span class="var">[±3% accuracy]</span> | <span class="var">[Annual]</span> | <span class="var">[For dark period verification]</span> |
| VPD calculator | <span class="var">[Software/calculated]</span> | <span class="var">[N/A]</span> | <span class="var">[Integrated or manual]</span> |

### 4.2 Sensor Placement

| Area | Temperature Sensor | RH Sensor | CO₂ Sensor |
|------|-------------------|-----------|------------|
| Cultivation rooms | <span class="var">[Canopy level, center of room]</span> | <span class="var">[Same location]</span> | <span class="var">[Canopy level]</span> |
| Large rooms | <span class="var">[Multiple points, average]</span> | <span class="var">[Multiple points]</span> | <span class="var">[Central + corners]</span> |
| Near HVAC | <span class="var">[NOT directly in airflow]</span> | <span class="var">[NOT directly in airflow]</span> | <span class="var">[Avoid discharge areas]</span> |

---

## 5. CONTROL SYSTEMS

### 5.1 HVAC System

| Component | Function | Control |
|-----------|----------|---------|
| Air Conditioning | Temperature cooling | <span class="var">[Thermostat/BMS]</span> |
| Heating | Temperature heating | <span class="var">[Thermostat/BMS]</span> |
| Dehumidifier | Humidity reduction | <span class="var">[Humidistat/BMS]</span> |
| Humidifier | Humidity addition | <span class="var">[Humidistat/BMS]</span> |
| Air Handler | Air circulation | <span class="var">[Continuous/timed]</span> |
| Exhaust fans | Air exchange | <span class="var">[Timer/CO₂ sensor]</span> |
| Intake with HEPA | Clean air supply | <span class="var">[Positive pressure maintained]</span> |

### 5.2 CO₂ Supplementation

| Method | Specification | Safety |
|--------|---------------|--------|
| Compressed CO₂ | <span class="var">[Regulated injection]</span> | <span class="var">[Max 1500 ppm, low O₂ alarm]</span> |
| CO₂ generator | <span class="var">[Burner-based]</span> | <span class="var">[Flame detection, CO alarm]</span> |

**CO₂ Control Logic:**
- Inject when: <span class="var">[Lights ON and CO₂ < setpoint]</span>
- Stop when: <span class="var">[CO₂ > setpoint or lights OFF]</span>
- Never supplement during dark period

### 5.3 Lighting Systems

| Type | Application | Efficiency |
|------|-------------|------------|
| LED Full Spectrum | <span class="var">[Primary cultivation lighting]</span> | <span class="var">[2.5-3.0 µmol/J]</span> |
| HPS (if used) | <span class="var">[Flowering supplemental]</span> | <span class="var">[1.7 µmol/J]</span> |
| T5 Fluorescent | <span class="var">[Propagation, mother rooms]</span> | <span class="var">[Lower intensity areas]</span> |

**Lighting Control:**
- Timer-controlled: <span class="var">[±1 minute accuracy]</span>
- Backup timer: <span class="var">[Mechanical backup recommended]</span>
- Emergency lighting: <span class="var">[Green spectrum only for dark period entry]</span>

---

## 6. MONITORING PROCEDURES

### 6.1 Continuous Monitoring (BMS)

The Building Management System shall:
- Log all parameters at <span class="var">[≤5 minute intervals]</span>
- Display real-time readings
- Generate trend reports
- Issue alarms when limits exceeded
- Store data with audit trail

### 6.2 Manual Verification

| Parameter | Frequency | Procedure | Document |
|-----------|-----------|-----------|----------|
| Temperature | <span class="var">[2x daily]</span> | Read BMS and handheld | <span class="var">[FM-ENV-001]</span> |
| Humidity | <span class="var">[2x daily]</span> | Read BMS and handheld | <span class="var">[FM-ENV-001]</span> |
| CO₂ | <span class="var">[Daily]</span> | Read BMS | <span class="var">[FM-ENV-001]</span> |
| Light intensity | <span class="var">[Weekly]</span> | PAR meter at canopy | <span class="var">[FM-ENV-002]</span> |
| Dark period verification | <span class="var">[Weekly]</span> | Light meter during dark | <span class="var">[FM-ENV-002]</span> |
| Timer accuracy | <span class="var">[Weekly]</span> | Compare to reference clock | <span class="var">[FM-ENV-002]</span> |

### 6.3 Daily Environmental Checklist

**Start of Shift:**

1. Review BMS overnight data
2. Check for any alarms/excursions
3. Verify current readings within range
4. Record readings on Daily Log <span class="var">[FM-ENV-001]</span>

**During Shift:**

1. Physical inspection of each room
2. Verify HVAC operation (visual/sound)
3. Check for equipment malfunctions
4. Note any concerns

**End of Shift:**

1. Record final readings
2. Verify systems running correctly for overnight
3. Report any issues to next shift

---

## 7. VAPOR PRESSURE DEFICIT (VPD)

### 7.1 VPD Targets

| Growth Stage | Target VPD | Range |
|--------------|------------|-------|
| Clones | <span class="var">[0.4-0.8 kPa]</span> | <span class="var">[0.3-0.9 kPa]</span> |
| Early Veg | <span class="var">[0.8-1.0 kPa]</span> | <span class="var">[0.7-1.1 kPa]</span> |
| Late Veg | <span class="var">[1.0-1.2 kPa]</span> | <span class="var">[0.9-1.3 kPa]</span> |
| Early Flower | <span class="var">[1.0-1.2 kPa]</span> | <span class="var">[0.9-1.4 kPa]</span> |
| Late Flower | <span class="var">[1.2-1.5 kPa]</span> | <span class="var">[1.0-1.6 kPa]</span> |

### 7.2 VPD Calculation

VPD = VPsat(leaf) - VPair

**Reference Table (Simplified):**

| Temp (°C) | 40% RH | 50% RH | 60% RH | 70% RH |
|-----------|--------|--------|--------|--------|
| 20 | <span class="var">[1.40]</span> | <span class="var">[1.17]</span> | <span class="var">[0.94]</span> | <span class="var">[0.70]</span> |
| 24 | <span class="var">[1.79]</span> | <span class="var">[1.49]</span> | <span class="var">[1.19]</span> | <span class="var">[0.90]</span> |
| 26 | <span class="var">[2.02]</span> | <span class="var">[1.68]</span> | <span class="var">[1.35]</span> | <span class="var">[1.01]</span> |
| 28 | <span class="var">[2.27]</span> | <span class="var">[1.89]</span> | <span class="var">[1.51]</span> | <span class="var">[1.14]</span> |

---

## 8. ALARM SYSTEM

### 8.1 Alarm Thresholds

| Parameter | Alert Alarm | Critical Alarm |
|-----------|-------------|----------------|
| High Temperature | <span class="var">[+3°C from setpoint]</span> | <span class="var">[+5°C or >32°C]</span> |
| Low Temperature | <span class="var">[-3°C from setpoint]</span> | <span class="var">[-5°C or <16°C]</span> |
| High Humidity | <span class="var">[+8% from setpoint]</span> | <span class="var">[>75% (veg) / >60% (flower)]</span> |
| Low Humidity | <span class="var">[-8% from setpoint]</span> | <span class="var">[<40%]</span> |
| High CO₂ | <span class="var">[1500 ppm]</span> | <span class="var">[2000 ppm]</span> |
| Low CO₂ (when supplementing) | <span class="var">[<600 ppm]</span> | <span class="var">[<400 ppm]</span> |
| Lighting failure | <span class="var">[Any fixture]</span> | <span class="var">[>25% fixtures]</span> |
| Light leak (dark period) | <span class="var">[>1 lux]</span> | <span class="var">[Flowering rooms]</span> |

### 8.2 Alarm Response Protocol

**Alert Alarm:**
1. Acknowledge alarm
2. Investigate cause
3. Implement correction
4. Document in Environmental Log
5. Monitor for resolution

**Critical Alarm:**
1. Immediate response required
2. Notify Cultivation Manager (after hours: on-call)
3. Implement emergency measures
4. Complete Deviation Report per <span class="var">[QA_00.05]</span>
5. Document all actions

### 8.3 Alarm Notification

| Time | Notification Method |
|------|---------------------|
| Business hours | <span class="var">[BMS display, audible, email]</span> |
| After hours | <span class="var">[SMS/phone to on-call personnel]</span> |
| Critical (any time) | <span class="var">[Immediate phone call to on-call]</span> |

---

## 9. DATA MANAGEMENT

### 9.1 Data Recording Requirements

| Data Type | Recording Frequency | Storage |
|-----------|---------------------|---------|
| Temperature | <span class="var">[≤5 minutes]</span> | <span class="var">[BMS + backup]</span> |
| Humidity | <span class="var">[≤5 minutes]</span> | <span class="var">[BMS + backup]</span> |
| CO₂ | <span class="var">[≤5 minutes]</span> | <span class="var">[BMS + backup]</span> |
| Manual readings | <span class="var">[Per procedure]</span> | <span class="var">[Paper + scan/electronic]</span> |
| Alarm events | <span class="var">[Real-time]</span> | <span class="var">[BMS with audit trail]</span> |

### 9.2 Data Review

| Review Type | Frequency | Reviewer |
|-------------|-----------|----------|
| Daily trend review | <span class="var">[Daily]</span> | Cultivation Supervisor |
| Weekly summary | <span class="var">[Weekly]</span> | Cultivation Manager |
| Monthly trend analysis | <span class="var">[Monthly]</span> | Cultivation Manager + QA |
| Excursion review | <span class="var">[Per event]</span> | Cultivation Manager + QA |

### 9.3 Data Retention

All environmental data shall be retained for <span class="var">[minimum 5 years]</span> with:
- Secure storage
- Backup copies
- Audit trail integrity
- Accessible for regulatory inspection

---

## 10. EQUIPMENT MAINTENANCE

### 10.1 Preventive Maintenance Schedule

| Equipment | Task | Frequency |
|-----------|------|-----------|
| HVAC units | Filter change | <span class="var">[Monthly]</span> |
| HVAC units | Coil cleaning | <span class="var">[Quarterly]</span> |
| HVAC units | Full service | <span class="var">[Annually]</span> |
| Dehumidifiers | Filter/coil clean | <span class="var">[Monthly]</span> |
| Humidifiers | Clean/descale | <span class="var">[Weekly]</span> |
| Sensors | Calibration verify | <span class="var">[Annually]</span> |
| Fans | Inspect/clean | <span class="var">[Monthly]</span> |
| Lights | Clean reflectors | <span class="var">[Monthly]</span> |
| Lights | Replace (HPS) | <span class="var">[Per manufacturer hours]</span> |
| Timers | Verify accuracy | <span class="var">[Weekly]</span> |
| CO₂ system | Leak check | <span class="var">[Monthly]</span> |

### 10.2 Maintenance Documentation

Document all maintenance in:
- Equipment Maintenance Log <span class="var">[FM-MAINT-001]</span>
- Calibration records <span class="var">[FM-CAL-001]</span>
- Work orders (if applicable)

---

## 11. DOCUMENTATION

| Document | Form Number | Retention |
|----------|-------------|-----------|
| Daily Environmental Log | <span class="var">[FM-ENV-001]</span> | <span class="var">[5 years]</span> |
| Weekly Light/Timer Verification | <span class="var">[FM-ENV-002]</span> | <span class="var">[5 years]</span> |
| Environmental Excursion Report | <span class="var">[FM-ENV-003]</span> | <span class="var">[5 years]</span> |
| BMS Data Export | <span class="var">[Electronic]</span> | <span class="var">[5 years]</span> |
| Sensor Calibration Records | <span class="var">[FM-CAL-001]</span> | <span class="var">[Sensor life + 5 years]</span> |

---

## 12. REVISION HISTORY

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

**END OF DOCUMENT PRO_01.08**
