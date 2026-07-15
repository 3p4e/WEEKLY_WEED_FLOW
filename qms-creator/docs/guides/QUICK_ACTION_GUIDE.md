# QUICK ACTION GUIDE - What To Do Next

**Date**: January 13, 2026
**Your Role**: Fill facility data Excel file (30-60 minutes)

---

## 🎯 YOUR IMMEDIATE ACTION

### Step 1: Open the Excel File

**File Location**: `/home/azzu/PROJ/Cannabis EU GMP QMS Creator/config/facility_data.xlsx`

**Quick Access**:
```bash
# Open with your preferred spreadsheet application
cd "/home/azzu/PROJ/Cannabis EU GMP QMS Creator"
xdg-open config/facility_data.xlsx
```

Or navigate in your file manager to:
- `Cannabis EU GMP QMS Creator` folder
- `config` subfolder
- `facility_data.xlsx` file

---

## 📋 Step 2: Fill These 9 Sheets

### Sheet 1: COMPANY
**Replace test data with real Purely Plant information**:
- **Company Name**: Purely Plant GmbH (or DOOEL - confirm legal entity)
- **Legal Address**: Full street address in Skopje, North Macedonia
- **Registration Number**: Your actual company registration number
- **Legal Entity Type**: GmbH or DOOEL
- **CEO Name**: Mr. Keckoski's full legal name
- **Owner Name**: Mr. J's full legal name
- **Company Contact**: Main phone, email, website

---

### Sheet 2: REGULATORY
**Your licenses and certifications**:
- **GMP License Number**: Your actual EU GMP or North Macedonian GMP license number
- **GMP License Effective Date**: When license was granted
- **GACP Certification Number**: Your GACP certificate number (if you have it)
- **GACP Effective Date**: When GACP was granted
- **Regulatory Contact Person**: Who handles regulatory matters
- **Inspection History**: Last GMP inspection date (if applicable)

---

### Sheet 3: PERSONNEL
**Real names of your team** (NOT "Jane Smith" or "John Doe"):

**Critical Roles**:
- **Qualified Person (QP)**: Azu Sozo, Master Pharmacist (that's you!)
  - License number, contact info

- **Quality Manager**: [Real name]
  - Title, qualifications, contact

- **Quality Assurance Manager**: [Real name]
  - Title, contact

- **Facility Manager**: [Real name]
  - Who manages the facility day-to-day?

- **Production Manager**: [Real name]
  - Who oversees cultivation and manufacturing?

- **QC Manager/Head**: [Real name]
  - Who runs the laboratory?

- **Engineering Manager**: [Real name if you have one]
  - Or facilities maintenance person

- **Warehouse Manager**: [Real name if separate role]

**Additional Staff** (if applicable):
- HR Manager
- Security Officer
- Cultivation Lead
- QC Analysts (list names if you want)

---

### Sheet 4: EQUIPMENT
**Your actual equipment inventory**:

For each piece of equipment:
- **Equipment Name**: e.g., "HPLC System", "Autoclave", "AHU-5", "Moisture Analyzer"
- **Manufacturer**: e.g., "Agilent", "Systec", "Carrier"
- **Model**: e.g., "1260 Infinity II", "Model D-23"
- **Serial Number**: The actual serial number from the equipment
- **Equipment ID**: Your internal ID (e.g., "EQU-LAB-001")
- **Location**: Where it's located (e.g., "QC Laboratory", "Cultivation Room 1")
- **Calibration Due Date**: When next calibration is needed
- **Status**: Qualified / In Use / Under Calibration

**Common Cannabis GMP Equipment**:
- HPLC (for cannabinoid testing)
- Moisture analyzer
- Microscope (for microbial testing)
- pH meter
- Scales/balances
- Environmental monitoring equipment
- HVAC system (AHU units)
- Autoclave or sterilizer
- Refrigerators/freezers
- Drying room equipment
- Curing room environmental controls

*Fill in what you actually have*

---

### Sheet 5: FACILITIES
**Your actual rooms and their GMP classifications**:

For each room/area:
- **Room Name**: e.g., "Cultivation Room 1", "Drying Room", "QC Laboratory", "Packaging Area"
- **Room Code**: Your internal code (e.g., "CULT-01", "DRY-01", "LAB-01")
- **Dimensions**: Actual room size in square meters (e.g., "20 m²" or "5m × 4m")
- **GMP Classification**:
  - **Grade A**: Sterile operations (probably not applicable for cannabis)
  - **Grade B**: Background for Grade A (probably not applicable)
  - **Grade C**: Clean area for certain operations
  - **Grade D**: Clean area for less critical operations
  - **Unclassified**: General manufacturing area
  - **GACP Zone**: For cultivation/agricultural areas
- **Purpose**: What happens in this room (e.g., "Cannabis flowering", "Cannabinoid testing", "Drying and curing")
- **Environmental Controls**:
  - Temperature range (e.g., "18-22°C")
  - Humidity range (e.g., "40-60% RH")
  - Air changes per hour (if you know)
- **Access Control**: Who can access (e.g., "Authorized cultivation personnel only")

**Typical Purely Plant Rooms** (adjust to your actual facility):
- Cloning/propagation room
- Vegetative growth room
- Flowering rooms (multiple?)
- Mother plant room
- Drying room
- Curing room
- Trimming/processing area
- Packaging area
- QC laboratory
- Warehouse/storage
- Equipment storage
- Waste storage
- Personnel changing rooms
- Offices

---

### Sheet 6: OPERATIONS
**Your products and production info**:

- **Product Names**: What cannabis products do you produce?
  - e.g., "Cannabis Flos" (dried flower)
  - "Cannabis Extract"
  - "Cannabis Oil"
  - List by strain if relevant (e.g., "Indica Strain A", "Sativa Strain B")

- **Batch Sizes**: Typical batch size (e.g., "5 kg dried flower", "10 liters extract")

- **Annual Production Capacity**: How much can you produce per year?

- **Manufacturing Schedule**: Do you run batches weekly, monthly?

- **Product Specifications**: THC%, CBD%, moisture content limits, microbial limits

---

### Sheet 7: QUALITY CONTROL
**Your lab testing capabilities**:

**Tests You Perform**:
- ☑ Cannabinoid content (THC, CBD, etc.) - **Method**: HPLC, GC, etc.
- ☑ Moisture content - **Method**: Loss on drying, moisture analyzer
- ☑ Microbial testing - **Method**: Ph.Eur., USP, send to external lab?
- ☑ Heavy metals - **Method**: ICP-MS, external lab?
- ☑ Pesticide residues - **Method**: GC-MS, external lab?
- ☑ Foreign matter - **Method**: Visual inspection, microscopy
- ☑ Identity testing - **Method**: Macroscopic, microscopic per Ph.Eur. 3028

**Laboratory Accreditation**:
- Do you have ISO 17025 accreditation? (If yes, certificate number and scope)
- External lab you use for some tests? (Name and accreditation)

**QC Equipment**:
- List from Sheet 4 (Equipment) - reference your HPLC, microscope, etc.

---

### Sheet 8: DOCUMENT CONTROL
**QMS metadata**:

- **Document Storage Location**: Where do you keep SOPs? (e.g., shared drive path, physical cabinet location)
- **Document Control Responsible Person**: Probably you (Azu) or your QA Manager
- **Current QMS Version**: You can put "1.0" or the date you started QMS
- **Last Management Review Date**: When did management last review the QMS?
- **Next Management Review Due**: Typically annually

---

### Sheet 9: INSTRUCTIONS
**This sheet has instructions - read it first!**
- Explains what each field means
- Shows required vs. optional fields
- Provides examples
- Data format guidance (e.g., dates as DD-MMM-YYYY)

---

## ⚡ Step 3: Save and Notify

After filling all data:

1. **Save the Excel file** (Ctrl+S or Cmd+S)
2. **Close Excel**
3. **Notify me** by sending a message: "Facility data complete"

---

## 🚀 What Happens Next (Automatic)

**After you notify completion, I will**:

1. **Import your data** (5 minutes)
   - Run import script to load Excel data into automation system
   - Validate all required fields filled

2. **Regenerate all automated documents** (3 minutes)
   - All 26 automated documents regenerate with YOUR REAL DATA
   - No more placeholders like "[FACILITY_NAME]"
   - Professional PDFs with "Purely Plant GmbH" throughout

3. **Show you the results**
   - You'll see actual company name, your name as QP, real addresses
   - Documents ready for printing and regulatory submission

4. **Continue parallel work**
   - Package A: Start Change Control SOP
   - Package B: Format first existing SOP from extracted content
   - Package C: Complete! Real data integrated

---

## 📊 What You're Creating

**By filling this Excel file, you enable**:
- 26 automated documents → Instantly updated with real Purely Plant data
- 213 total QMS documents → All will use your real data when generated
- Professional QMS system → Inspector-ready, GMP-compliant

**Documents that will automatically update**:
- Quality Manual
- Facility Profile
- Site Master File
- All SOPs with your company name
- All forms with your real addresses
- All specifications with your actual equipment
- Batch records with your real facility data

---

## ❓ Questions While Filling?

**If you're unsure about a field**:
- Leave it blank for now (we can fill later)
- Or put your best estimate
- Or use "TBD" or "To Be Determined"

**Common questions**:
- "I don't have ISO 17025" → That's fine, mark "No" or leave blank
- "We send some tests to external lab" → Note the external lab name
- "I'm not sure of exact GMP classification" → Use "Unclassified" or "GACP Zone"
- "Some equipment doesn't have serial numbers" → Use equipment ID or leave blank

**The important fields are**:
- Company name and address (required)
- Your name as QP (required)
- Key personnel names (at least Quality Manager, Production Manager)
- Main equipment you use (at least HPLC, balances, environmental monitoring)
- Main rooms/areas (at least cultivation, drying, QC lab, packaging)

Everything else can be refined later!

---

## 🎯 Time Estimate

**Realistic time**: 30-60 minutes

**Breakdown**:
- Company info (5 min) - straightforward
- Regulatory (5 min) - just need license numbers
- Personnel (10 min) - list your team
- Equipment (10-15 min) - may need to check serial numbers
- Facilities (10-15 min) - room measurements
- Operations (5 min) - product info
- Quality Control (5 min) - testing methods
- Document Control (5 min) - quick metadata

**Total**: ~55 minutes average

---

## 🌟 Why This Matters

**This Excel file is the heart of the automation system.**

Once filled:
- **Every SOP** will say "Purely Plant GmbH" instead of "[FACILITY_NAME]"
- **Every form** will have your real address
- **Every specification** will reference your actual equipment
- **Every batch record** will use your real room codes
- **Quality Manual** will have your organizational structure
- **Site Master File** will be inspection-ready

**One hour of your time** → **Entire QMS personalized**

---

## 📍 File Location Reminder

```
/home/azzu/PROJ/Cannabis EU GMP QMS Creator/config/facility_data.xlsx
```

**Ready when you are!** 🚀

---

*Quick Action Guide - January 13, 2026*
*Purely Plant GmbH - Cannabis EU GMP QMS Creator*
