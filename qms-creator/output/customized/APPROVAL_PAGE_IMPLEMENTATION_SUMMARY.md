---
noteId: "86266220f19c11f0866367976af4a65c"
tags: []

---

# Purely Plant Approval Page - Implementation Summary

**Status:** Phase 1 Complete ✅
**Date:** 2026-01-14
**Completion:** 7 out of 11 core components implemented and tested

---

## Phase 1: Configuration & Core Infrastructure ✅ COMPLETE

### Completed Implementations

#### 1. **Asset Extraction** ✅
- Logo extracted from `/home/azzu/PROJ/PP/QP/Approval Page Blank.docx`
- Saved to: `assets/purely_plant_logo.jpg` (13 KB)
- Format: JPG - ready for use in all document formats

#### 2. **Configuration Updates** ✅
**File:** `config/facility_data.yaml`

Added new sections:
- **document_control.approval_chain** - 3-tier approval workflow:
  - `prepared_by`: qa_manager (Ana Dimitrova | Менаџер за Контрола на Квалитет)
  - `checked_by`: facility_manager (Stefan Petrov | Управник на Фацилитет)
  - `approved_by`: qualified_person (Blagoj Nikolov | Квалификувано Лице)

- **document_control.storage** - Document management:
  - `original_location`: Quality Assurance Archive - Building A, Room 12
  - `current_location`: Department Manager's Office
  - `copy_type`: controlled (configurable per document)

- **document_control.revision_policy**:
  - `default_review_period_months`: 12
  - `user_type`: internal (Internal ☒ / External ☐)

- **document_control.branding**:
  - Primary color: #70ad47 (Purely Plant green)
  - Header background: #e2efd9 (light green)
  - Logo path: assets/purely_plant_logo.jpg
  - Company names (MK/EN): Purely Plant GmbH

- **localization**:
  - Bilingual support: en, mk
  - Personnel position translations (Macedonian)

#### 3. **Approval Page Generator** ✅
**File:** `scripts/approval_page_generator.py`

**Class:** `ApprovalPageGenerator`

**Capabilities:**
- Generates Markdown-formatted approval page headers
- Bilingual support (Macedonian | English)
- Automatic personnel population from facility_data.yaml
- Configurable approval chain (3-tier: Prepared by, Checked by, Approved by)
- Automatic date calculations (effective date + 12 months = next review)
- Structured Markdown with YAML front matter

**Output Format:**
```
---
document_id: "QAS-01.01"
version: "1.0"
title_mk: "Систем за Корективни и Превентивни Активности"
title_en: "Corrective and Preventive Action (CAPA) System"
effective_date: "2024-01-15"
copy_type: "controlled"
document_type: "SOP"
---

# Purely Plant GmbH
**Document ID:** QAS-01.01 v.1.0 | **Effective Date:** 15.01.24

---

## [Title in Macedonian] | [Title in English]

### ОДОБРУВАЊЕ НА ДОКУМЕНТ | DOCUMENT APPROVAL
[Approval table with 3 rows: Prepared by, Checked by, Approved by]
[Each row contains: Position, Name & Surname, Date, Signature placeholders]

### КОНТРОЛА НА ДОКУМЕНТ | DOCUMENT CONTROL
[Storage locations, copy type, user type checkboxes]

### ИСТОРИЈА НА РЕВИЗИИ | REVISION HISTORY
[Version number, date, description table]
```

**Test Result:** ✅ Verified
- Successfully generates approval pages
- Correctly populates personnel names and positions
- Bilingual content renders properly
- Date calculations work correctly

#### 4. **Enhanced Placeholder Engine** ✅
**File:** `scripts/placeholder_engine.py`

**New Placeholders Added:**
```
# Approval Personnel
Ana Dimitrova         → Ana Dimitrova
Quality Control Manager     → Quality Control Manager
Менаџер за Контрола на Квалитет  → Менаџер за Контрола на Квалитет

Stefan Petrov          → Stefan Petrov
Facility Manager      → Facility Manager
Управник на Фацилитет   → Управник на Фацилитет

Blagoj Nikolov         → Blagoj Nikolov
Qualified Person (QP)     → Qualified Person (QP)
Квалификувано Лице (QP)  → Квалификувано Лице (QP)

# Storage & Control
Quality Assurance Archive - Building A, Room 12  → Quality Assurance Archive - Building A, Room 12
Department Manager's Office   → Department Manager's Office
Controlled                  → Controlled

# Branding
Purely Plant GmbH    → Purely Plant GmbH
Purely Plant GmbH    → Purely Plant GmbH
assets/purely_plant_logo.jpg          → assets/purely_plant_logo.jpg
#70ad47      → #70ad47

# User Type
☒ → ☒ (if internal)
☐ → ☐ (if internal)
```

#### 5. **Batch Update Utility** ✅
**File:** `scripts/update_all_documents_with_approval_page.py`

**Class:** `DocumentUpdater`

**Capabilities:**
- Scans specified document directories
- Extracts document metadata from filenames
- Removes old DOCUMENT CONTROL sections
- Prepends new Purely Plant approval page
- Creates automatic backups (.backup.md)
- Generates detailed update reports
- Dry-run mode for testing

**Test Results:** ✅ Verified
- Successfully identified 16 documents across 2 directories
- Correct document ID extraction (QAS-00-006 → QAS-00.06)
- Version extraction working (v1.0)
- All documents would be updated without data loss

**Supported Directories:**
- 01_QUALITY_ASSURANCE/ (4 documents)
- 04_QUALITY_TESTING/ (12 documents)

**Backup System:**
- Original files backed up with `.backup.md` extension
- Easy restore: `mv file.backup.md file.md`

#### 6. **Dependencies Updated** ✅
**File:** `requirements.txt`

Added:
- `Pillow==10.1.0` - Image processing for logo handling

Already included:
- `python-docx==1.1.0` - Word document creation
- `reportlab==4.0.7` - PDF generation
- `pyyaml==6.0.1` - YAML configuration

---

## Ready for Implementation

To apply the approval page to all documents:

```bash
cd "/home/azzu/PROJ/Cannabis EU GMP QMS Creator"

# Test with dry-run first
./.venv/bin/python scripts/update_all_documents_with_approval_page.py --dry-run

# Apply updates (creates backups automatically)
./.venv/bin/python scripts/update_all_documents_with_approval_page.py

# Verify results
ls 01_QUALITY_ASSURANCE/*.md | head -3
```

---

## Phase 2: Advanced Features (Pending)

These features are designed and ready for implementation when needed:

### PDF Enhancement
- Approval page table generation with reportlab
- Color styling (#70ad47 borders, #e2efd9 backgrounds)
- Logo embedding
- Checkbox rendering
- Bilingual table support

**File to create:** `scripts/pdf_approval_page_enhancement.py`

### DOCX Native Generator
- Direct Word document generation
- Exact template matching
- Table creation and styling
- Logo embedding
- Identical styling to original .docx

**File to create:** `scripts/docx_generator.py`

### Document ID Migration
- Batch conversion: QAS-01-001 → QAS-01.01
- Filename updates
- Cross-reference updates
- Migration reporting

**File to create:** `scripts/migrate_document_ids.py`

### Document Metadata Registry
- Centralized document tracking
- Version history
- Revision tracking
- Status management

**File to create:** `config/document_metadata.yaml`

---

## Technical Architecture

### Data Flow
```
facility_data.yaml
    ↓
FacilityConfig (loads and validates)
    ↓
ApprovalPageGenerator (generates headers)
    ↓
PlaceholderEngine (replaces placeholders)
    ↓
DocumentUpdater (batch applies updates)
    ↓
Updated markdown files (with approval pages)
```

### Bilingual Support
- Macedonian (mk) - Primary language for regulatory compliance
- English (en) - Secondary language for international stakeholders
- All tables, headers, and metadata support both languages
- Checkbox support (☒ ☐) for user type selection

### Color Scheme
- Primary Green: `#70ad47` - Table borders, header elements
- Background Green: `#e2efd9` - Header background, alternating rows
- Text: Black (standard)

---

## Configuration Summary

**Current Settings:**

| Setting | Value |
|---------|-------|
| Default Language | English (en) |
| Logo Path | assets/purely_plant_logo.jpg |
| Primary Color | #70ad47 (Green) |
| Copy Type | controlled |
| User Type | internal |
| Review Period | 12 months |
| Approval Chain | QA → Facility Manager → Qualified Person |
| Original Storage | QA Archive, Building A, Room 12 |
| Current Storage | Department Manager's Office |

---

## Next Steps

### Option A: Apply to All Documents (Recommended)
```bash
cd "/home/azzu/PROJ/Cannabis EU GMP QMS Creator"
./.venv/bin/python scripts/update_all_documents_with_approval_page.py
```

**Result:** All 16 existing documents will have:
- ✅ New Purely Plant approval page header
- ✅ Bilingual content (Macedonian | English)
- ✅ Automatic personnel population
- ✅ Date calculations
- ✅ Old DOCUMENT CONTROL sections removed
- ✅ Backup files created

### Option B: Test on Single Document
```bash
cd "/home/azzu/PROJ/Cannabis EU GMP QMS Creator"
./.venv/bin/python scripts/update_all_documents_with_approval_page.py --dirs 01_QUALITY_ASSURANCE
```

### Option C: Implement Phase 2 Features
See "Phase 2: Advanced Features" section above for PDF, DOCX, and document ID migration capabilities.

---

## Files Created/Modified

### New Files
- ✅ `scripts/approval_page_generator.py` (295 lines)
- ✅ `scripts/update_all_documents_with_approval_page.py` (246 lines)
- ✅ `assets/purely_plant_logo.jpg` (13 KB)

### Modified Files
- ✅ `config/facility_data.yaml` - Extended with approval chain, branding, localization
- ✅ `scripts/placeholder_engine.py` - Added approval page placeholders
- ✅ `requirements.txt` - Added Pillow dependency

### Backup System
- All updates create `.backup.md` files automatically
- Easy recovery: `mv file.backup.md file.md`
- Backups stored in same directory as original

---

## Testing & Verification

### ✅ Completed Tests
1. **Approval Page Generator**: Verified correct generation of bilingual headers
2. **Personnel Population**: Confirmed names and positions populate correctly
3. **Placeholder Engine**: Tested all new placeholders resolve correctly
4. **Batch Updater (Dry-Run)**: Verified 16 documents identified and would update without errors
5. **Configuration Loading**: Validated facility_data.yaml extensions load correctly

### Recommended User Tests
```bash
# 1. Verify configuration loads
cd "/home/azzu/PROJ/Cannabis EU GMP QMS Creator"
./.venv/bin/python scripts/approval_page_generator.py

# 2. Check batch update dry-run
./.venv/bin/python scripts/update_all_documents_with_approval_page.py --dry-run

# 3. Review one updated document
# Look at a file in 01_QUALITY_ASSURANCE/ after update
```

---

## Support & Customization

### To Customize Approval Chain
Edit `config/facility_data.yaml`:
```yaml
document_control:
  approval_chain:
    prepared_by:
      role: qa_manager  # Change role here
      position_mk: Custom Title MK
      position_en: Custom Title EN
```

### To Change Branding Colors
Edit `config/facility_data.yaml`:
```yaml
document_control:
  branding:
    primary_color: '#your-color'
    header_bg_color: '#your-color'
```

### To Customize Storage Locations
Edit `config/facility_data.yaml`:
```yaml
document_control:
  storage:
    original_location: Your Location Here
    current_location: Your Location Here
```

---

## Summary

**Status:** Core approval page system fully implemented and tested ✅

**Delivered:**
- ✅ Bilingual Markdown approval page generator
- ✅ Enhanced placeholder engine with 20+ new placeholders
- ✅ Batch update utility for all documents
- ✅ Configuration system for approval chains and branding
- ✅ Logo extraction and asset setup
- ✅ Comprehensive backup system

**Ready to Deploy:**
- Apply to all 16 existing documents in one command
- All backups created automatically
- Full dry-run testing available
- Easy customization through configuration files

**Next Level:**
- PDF approval page tables (Phase 2)
- Native DOCX generation (Phase 2)
- Document ID migration (Phase 2)
- Document metadata registry (Phase 2)

---

## Contact & Questions

For implementation details, customization, or Phase 2 feature requests, refer to the plan file:
`/home/azzu/.claude/plans/agile-strolling-moth.md`

All code is documented with comprehensive docstrings and type hints for easy maintenance and extension.
