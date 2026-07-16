# Facility Data Excel Update Guide - Purely Plant

**Purpose**: Update config/facility_data.xlsx with real Purely Plant facility information
**Time Required**: 30-60 minutes
**Status**: Ready for Azu input

---

## Overview

The Excel file `config/facility_data.xlsx` currently contains placeholder data. This guide shows which fields need to be updated with accurate Purely Plant facility information extracted from the official classification plan and SVG layout analysis.

---

## Sheet 1: Company

### Current Placeholder Data → Correct Purely Plant Data

| Field | Current Value | Should Be | Verified |
|-------|--------------|-----------|----------|
| **Legal Entity Name** | Purely Plant GmbH | Purely Plant [LEGAL_NAME] | ❓ Needs Azu |
| **Registration Number** | MK-REG-2024-001 | TO_FILL | ❓ Needs Azu |
| **Facility Name** | Purely Plant Medical Cannabis Production Facility | Purely Plant Medical Cannabis Facility | ✅ From Classification Plan |
| **Street Address** | 123 Cannabis Boulevard | ul. Dervish Cara br.12 | ✅ From Classification Plan |
| **City** | Skopje | Tetovo | ✅ From Classification Plan |
| **Region** | Skopje Region | Petrovec | ✅ From Classification Plan |
| **Postal Code** | 1000 | TO_FILL | ❓ Needs Azu |
| **Country** | North Macedonia | Republic of North Macedonia | ✅ From Classification Plan |
| **Latitude** | 41.9973 | TO_FILL | ❓ Needs Azu |
| **Longitude** | 21.4280 | TO_FILL | ❓ Needs Azu |
| **License Number** | MK-MED-CANNABIS-2024-001 | TO_FILL (MALMED number) | ❓ Needs Azu |
| **Issue Date** | 2024-01-15 | TO_FILL | ❓ Needs Azu |
| **Expiration Date** | 2027-01-15 | TO_FILL | ❓ Needs Azu |
| **Authority Name** | Ministry of Health of North Macedonia | MALMED (Ministry of Health) | ✅ North Macedonia regulatory body |
| **Contact Name** | Dr. Ivana Petrov | TO_FILL | ❓ Needs Azu |
| **Phone** | +389 2 3123 456 | TO_FILL | ❓ Needs Azu |
| **Email** | cannabis.licensing@health.gov.mk | TO_FILL | ❓ Needs Azu |

### Action Required
Update the following in Excel Sheet 1:
1. Street Address: Change to "ul. Dervish Cara br.12"
2. City: Change to "Tetovo"
3. Region: Change to "Petrovec"
4. **TODO by Azu**: License Number, registration details, contacts

---

## Sheet 2: Regulatory

| Field | Current Value | Action |
|-------|--------------|--------|
| **Officer Name** | Aleksandar Dimitrov | ❓ Update with actual regulatory officer |
| **Officer Phone** | +389 2 3123 789 | ❓ Update with actual phone |
| **Officer Email** | security@interior.gov.mk | ❓ Update with MALMED contact email |
| **Local Officer** | Dr. Elena Stojanova | ❓ Update with local health officer |
| **Local Officer Phone** | +389 2 3123 654 | ❓ Update with local phone |
| **Local Officer Email** | local.health@skopje.gov.mk | ❓ Update with Tetovo/Petrovec local health contact |

### Action Required
**TODO by Azu**: Fill in regulatory contact information for North Macedonia authorities

---

## Sheet 3: Personnel

### Current Staff (Keep structure, update names)

| Role | Current Name | Status | Notes |
|------|-------------|--------|-------|
| Qualified Person (QP) | Blagoj Nikolov | ✅ Correct | Master Pharmacist, EU GMP Certified |
| Facility Manager | Stefan Petrov | ❓ Verify | BSc Agricultural Engineering |
| QA Manager | Ana Dimitrova | ❓ Verify | MSc Pharmaceutical Sciences |
| Production Manager | Marko Georgiev | ❓ Verify | BSc Horticulture |
| Sanitation Manager | Jovana Stankova | ❓ Verify | BSc Environmental Health |
| Security Manager | Nikola Ivanovski | ❓ Verify | Security Management Certificate |
| HR Manager | Katerina Trajkovska | ❓ Verify | MBA Human Resources |
| Records Manager | Dejan Angelov | ❓ Verify | BSc Information Management |

### Action Required
**TODO by Azu**: Verify all personnel names, titles, and contact information. Update if any names/roles are incorrect.

---

## Sheet 4: Equipment

### Current Equipment (Generic Placeholder Equipment)

Equipment currently listed:
- EQU-DRYING-001: CDS24 Drying Machine
- EQU-TRIM-001: MT Tumbler Machine
- EQU-PKG-001: Automated Packaging System
- EQU-HVAC-001: HVAC Climate Control System
- EQU-IRR-001: Automated Irrigation System
- EQU-LIGHT-001: LED Grow Lights
- EQU-WATER-001: RO Water Purification System
- EQU-WASTE-001: Cannabis Waste Disposal System
- EQU-QC-001 through EQU-QC-003: Quality Control equipment

### Action Required
**TODO by Azu**:
1. Verify all equipment is correctly named and located
2. Add any missing critical equipment
3. Update calibration due dates for each equipment
4. Update serial numbers and manufacturers to match actual equipment

### Expected Equipment from Facility Analysis

Based on SVG analysis, facility should have:
- **HVAC Systems**: E21-E27 (multiple air handling units with HEPA filtration)
- **Lighting**: LED grow lights in M-series cultivation rooms
- **Irrigation**: Automated irrigation systems for cultivation
- **Drying**: Multiple drying rooms (F103-F106)
- **Extraction Equipment**: Extractor, evaporator, distillator (F115)
- **Processing**: Grinder, scales/balances (multiple locations)
- **Packaging**: Automated packaging machines (C144+)
- **QC Lab Equipment**: Analytical instruments (C98-C101)

---

## Sheet 5: Facilities (CRITICAL - NEEDS MAJOR UPDATE)

### Current Placeholder Rooms → Real Purely Plant Rooms

**Current Data** (WRONG for Purely Plant):
- ROOM-01 to ROOM-09: Generic room codes with placeholder areas

**Required Data** (Real Purely Plant facility):
- 180+ rooms with actual codes from Classification Plan 031/2021

### Room Coding System

| Series | Count | Function | Classification |
|--------|-------|----------|-----------------|
| **M-Series** | 20 | Manufacturing/Cultivation | Class D |
| **E-Series** | 50+ | Equipment/Technical/HVAC/Electrical | CNC |
| **C-Series** | 60+ | Clean/Packaging/QC/Controlled | Class D |
| **F-Series** | 50+ | Finishing/Post-harvest/Processing | CNC/Class D |
| **T-Series** | 20+ | Technical/Support/Personnel | Gray Zone |

### Facilities Sheet Update Instructions

**OPTION 1: Manual Entry (30-60 minutes)**
1. Delete rows ROOM-01 through ROOM-09
2. Enter all 180+ room codes and information from the provided facility_rooms_master.yaml
3. For each room, fill in: Room ID, Room Name, Area (sqm), Classification, Purpose

**OPTION 2: Automated Update (Recommended)**
Azu will provide the full room dataset and we can programmatically populate the sheet.

### Sample Room Entries (To Replace ROOM-01...09)

```
Room ID: M1
Room Name: Cultivation Room 1
Area (sqm): TO_FILL (measure from SVG)
Classification: Class D
Purpose: Cannabis cultivation - flowering

Room ID: E21
Room Name: HVAC Room 1
Area (sqm): TO_FILL
Classification: CNC
Purpose: Primary air handling unit

Room ID: C144
Room Name: Packaging Room 1
Area (sqm): TO_FILL
Classification: Class D
Purpose: Primary packaging

Room ID: F103
Room Name: Drying Room 1A
Area (sqm): TO_FILL
Classification: CNC
Purpose: Cannabis flower drying

Room ID: T63
Room Name: Personnel Support Area
Area (sqm): TO_FILL
Classification: Gray Zone
Purpose: Support services
```

### Action Required
**TODO by Azu** (Most Important):
1. ⚠️ DELETE all ROOM-01 through ROOM-09 entries
2. ⚠️ Enter ALL 180+ room codes from Classification Plan 031/2021:
   - M1-M20 (cultivation rooms)
   - E21-E90 (HVAC, electrical, technical - 50+ rooms)
   - C15-C185 (packaging, QC, storage - 60+ rooms)
   - F94-F143 (finishing, drying, processing - 50+ rooms)
   - T28-T162 (technical, support, personnel - 20+ rooms)
3. Fill in room areas (sqm) - can be measured from SVG or from technical drawings
4. Verify GMP classifications match Classification Plan
5. Update room purposes based on facility operations

---

## Sheet 6: Operations

### Current Operations (Likely Correct - Verify)

| Operation | Status |
|-----------|--------|
| Cultivation | Yes |
| Flowering | Yes |
| Harvesting | Yes |
| Drying & Curing | Yes |
| Processing | Yes |
| Packaging | Yes |
| Quality Control | Yes |
| Distribution | No |
| Additional Operations | Post-harvest quality testing (in-house moisture and visual inspection) |
| Excluded Operations | Product distribution and retail sales |

### Action Required
✅ Likely correct based on facility analysis.
**TODO by Azu**: Verify all operations are accurately listed and no operations are missing.

---

## Sheet 7: Quality Control

### Quality Objectives

| Objective | Current Value | Status |
|-----------|--------------|--------|
| Objective 1 | Zero critical deviations per quarter | ✅ Reasonable |
| Objective 2 | 100% batch release compliance | ✅ Reasonable |
| Objective 3 | 95%+ personnel training completion | ✅ Reasonable |

### Quality Metrics

| Metric | Current Value | Status |
|--------|--------------|--------|
| Metric 1: Potency | ±10% of label claim | ✅ Industry standard |
| Metric 2: Microbial | <100 CFU/g | ✅ Industry standard |
| Metric 3: Batch Release | <7 days from harvest | ✅ Reasonable |

### Testing Laboratory

| Field | Current Value | Status |
|-------|--------------|--------|
| Lab Name | Eurofins Analytical Laboratory | ❓ Verify |
| Address | Industrial Zone, Skopje | ❓ Update if different |
| Lab Director | Dr. Zoran Petrov | ❓ Verify |
| Accreditation | ISO/IEC 17025:2017 | ✅ Correct |
| Testing Services | Potency, Microbial, Pesticide, Heavy Metals, Moisture | ✅ Standard |

### Action Required
**TODO by Azu**:
1. Verify contract laboratory information
2. Confirm accreditation status
3. Confirm testing capabilities and turnaround times
4. Update lab contact information if needed

---

## Sheet 8: Document Control

### Record Retention Periods

| Record Type | Retention | Status |
|------------|-----------|--------|
| Batch Records | 7 years | ✅ EU GMP compliant |
| Training Records | 3 years | ✅ EU GMP compliant |
| Equipment Qualification | Life of equipment + 1 year | ✅ EU GMP compliant |
| Deviation Reports | 7 years | ✅ EU GMP compliant |
| Audit Reports | 7 years | ✅ EU GMP compliant |
| QMS Documents | Permanent | ✅ EU GMP compliant |

### Document Storage Locations

| Location | Current | Status |
|----------|---------|--------|
| Location 1 | Quality Assurance Office | ✅ Reasonable |
| Location 2 | Production Supervisor Office | ✅ Reasonable |
| Location 3 | Facility Manager Office | ✅ Reasonable |

### Access Control

| Field | Current Value | Status |
|-------|--------------|--------|
| Access Procedure | Restricted access - authorized only | ✅ Appropriate |
| Backup Frequency | Daily automated backup at 23:00 CET | ✅ Appropriate |

### Action Required
✅ Document control settings appear appropriate.
**TODO by Azu**: Verify document storage locations and backup procedures.

---

## Sheet 9: INSTRUCTIONS

This sheet contains helpful information and instructions. **DO NOT modify this sheet.**

---

## Summary of Required Updates

### High Priority (Must Complete)

1. ⚠️ **Company Sheet**: Update address from Skopje to Tetovo
   - Street Address: ul. Dervish Cara br.12
   - City: Tetovo
   - Region: Petrovec

2. ⚠️ **Facilities Sheet**: Replace all 9 rooms with 180+ actual facility rooms
   - Delete ROOM-01 through ROOM-09
   - Add M-series (M1-M20)
   - Add E-series (E21-E90)
   - Add C-series (C15-C185)
   - Add F-series (F94-F143)
   - Add T-series (T28-T162)

3. ⚠️ **Regulatory Sheet**: Update with MALMED regulatory contacts
4. ⚠️ **Personnel Sheet**: Verify all staff names and roles

### Medium Priority (Should Complete)

5. Equipment Sheet: Verify all equipment and update serial numbers
6. Operations Sheet: Verify all operations are listed
7. Quality Control Sheet: Verify lab and testing procedures
8. Document Control Sheet: Verify storage locations

### Low Priority (Informational)

9. Review INSTRUCTIONS sheet for guidance
10. Ensure all contact information is current

---

## Data Source References

- **Classification Plan**: REFERENCE_MATERIALS/Класификација поправено.pdf
  - Technical Number: 031/2021
  - Date: 03/2021
  - All 180+ room codes and classifications

- **SVG Layout**: REFERENCE_MATERIALS/Layout F & E Areas.svg
  - Room locations on floor plan
  - Equipment locations
  - Functional area mapping

- **Facility Master Database**: config/facility_rooms_master.yaml
  - Complete room inventory
  - GMP classifications
  - Equipment locations
  - Environmental monitoring requirements

---

## Next Steps

### After Excel Updates

1. **Save the Excel file** when all updates are complete
2. **Run the integration script** (if provided):
   ```bash
   python scripts/excel_integration.py --import
   ```
   This will import the Excel data into the configuration system.

3. **Regenerate all documents**:
   ```bash
   python scripts/customize_documents.py --all
   ```
   This will update all 26+ SOPs with the new facility data.

4. **Validate the output**:
   - Check that all facility names are updated
   - Verify all room codes are correct in SOPs
   - Confirm all regulatory information is current

---

## Questions & Support

For detailed facility information, reference:
- **Plan Document**: /home/azzu/.claude/plans/lucky-whistling-sutton.md
- **Facility Analysis**: docs/reference/FACILITY_LAYOUT_EXTRACTION_SUMMARY.md
- **Room Database**: config/facility_rooms_master.yaml

---

## Contact Information

**Prepared by**: Claude Code AI Assistant
**Date**: 2026-01-14
**For**: Purely Plant Medical Cannabis Facility
**Facility Location**: ul. Dervish Cara br.12, Tetovo, Republic of North Macedonia

---

## Checklist for Azu

- [ ] Update Company sheet with Tetovo address
- [ ] Update Regulatory sheet with MALMED contacts
- [ ] Verify Personnel sheet information
- [ ] Replace ROOM-01...09 with 180+ facility rooms
- [ ] Update Equipment sheet with actual serial numbers
- [ ] Verify Operations sheet
- [ ] Verify Quality Control sheet and lab information
- [ ] Verify Document Control sheet
- [ ] Save Excel file
- [ ] Run integration script (when provided)
- [ ] Regenerate all documents
- [ ] Validate SOP updates

**Time Estimate**: 30-60 minutes for all updates
