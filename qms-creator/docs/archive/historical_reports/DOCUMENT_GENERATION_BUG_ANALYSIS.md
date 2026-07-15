# Document Generation Bug Analysis & Fix Plan

**Date**: January 23, 2026  
**Status**: CRITICAL ISSUES IDENTIFIED  
**Severity**: HIGH - Affects all generated PDFs and DOCX files  

---

## Executive Summary

The document generation pipeline has **critical bugs** causing:
1. **Duplicate Headers** - Section headers appearing multiple times
2. **Duplicate Titles** - Document titles rendered twice
3. **Garbled Text** - Character encoding issues creating illegible content
4. **Black Box Overlays** - Content covered by unintended graphics/shapes
5. **Strange Symbols** - Unicode and special character rendering errors

---

## Root Causes Identified

### Issue #1: Duplicate Header Loop (purely_plant_docx_generator.py)

**Location**: `scripts/purely_plant_docx_generator.py` lines 142-188

**Problem**: The section headers loop creates duplicates:
```python
for mk_header, en_header, content in section_headers:
    # Creates HEADER paragraph
    header_para = doc.add_paragraph()
    # ... adds MK header ...
    # ... adds EN header ...
    
    # Creates CONTENT paragraph with FULL HEADER TEXT AGAIN
    content_para = doc.add_paragraph()
    # Splits content by ' / ' - BUT the content still contains the full header!
```

**Why It Happens**: The content variable contains the full text including duplicate headers instead of just the section content.

**Impact**: Every section appears twice - once as header, once in content

---

### Issue #2: Approval Table Duplication

**Location**: `scripts/purely_plant_docx_generator.py` lines 90-140

**Problem**: The approval table is added to the document, but later the section_headers loop includes duplicate entries for "APPROVAL" information

**Impact**: Approval signatures section appears in multiple locations

---

### Issue #3: Character Encoding in Tables

**Location**: `scripts/purely_plant_docx_generator.py` and `scripts/professional_pdf_generator.py`

**Problem**: Bilingual (Macedonian/English) content uses pipe delimiter `|` but:
- Special characters in Macedonian may not be properly encoded
- PDF generation doesn't respect character encoding settings
- Table cells may overflow causing black boxes

**Impact**: Garbled text especially in Macedonian sections

---

### Issue #4: PDF Table Rendering (professional_pdf_generator.py)

**Location**: `scripts/professional_pdf_generator.py`

**Problem**: ReportLab tables with:
- Incorrect column widths causing text overflow
- Cell borders overlapping with content
- Shading/background colors covering text
- No proper height/width constraints

**Impact**: Black boxes covering content

---

### Issue #5: Multiple Generator Conflict

**Files**: 
- `scripts/pdf_generator.py`
- `scripts/professional_pdf_generator.py`  
- `scripts/purely_plant_docx_generator.py`
- `scripts/professional_docx_converter.py`

**Problem**: Multiple generators with conflicting implementations - unclear which one is primary

**Impact**: Inconsistent document generation, unexpected behavior

---

## Detailed Fixes Required

### Fix #1: Remove Duplicate Section Headers Loop

**File**: `scripts/purely_plant_docx_generator.py`

**Change**: The section headers should NOT be duplicated. Either:
- Option A: Remove the loop entirely (only use approval table)
- Option B: Keep loop but fix content to NOT include headers again

**Recommended**: Option B with corrected content

```python
# BEFORE (WRONG - Creates duplicates)
section_headers = [
    ("1.0 ЦЕЛ", "1.0 PURPOSE", "Целта на оваа СОП е... / The purpose of this SOP is..."),
    ...
]

for mk_header, en_header, content in section_headers:
    header_para = doc.add_paragraph()
    mk_run = header_para.add_run(mk_header)
    header_para.add_run(" | ")
    en_run = header_para.add_run(en_header)
    
    content_para = doc.add_paragraph()
    # IF content STILL contains the headers, this creates duplicates!

# AFTER (CORRECT - No duplicates)
# Only create content once, and content should be just the body text
for mk_header, en_header, mk_content, en_content in section_headers:
    header_para = doc.add_paragraph()
    mk_run = header_para.add_run(mk_header)
    header_para.add_run(" | ")
    en_run = header_para.add_run(en_header)
    
    content_para = doc.add_paragraph()
    mk_run = content_para.add_run(mk_content)
    content_para.add_run(" / ")
    en_run = content_para.add_run(en_content)
    # Content is ONLY the body text, not the header again
```

---

### Fix #2: Character Encoding for Bilingual Text

**File**: `scripts/purely_plant_docx_generator.py`

**Change**: Ensure proper UTF-8 encoding throughout:

```python
# Add at the top of the file
# -*- coding: utf-8 -*-

# When adding bilingual text, ensure proper escaping:
def add_bilingual_text(paragraph, mk_text, en_text, mk_size=10, en_size=9):
    """Add Macedonian and English text to paragraph with proper encoding."""
    # Ensure text is properly encoded
    mk_text = mk_text.encode('utf-8').decode('utf-8')
    en_text = en_text.encode('utf-8').decode('utf-8')
    
    mk_run = paragraph.add_run(mk_text)
    mk_run.font.name = "Calibri"
    mk_run.font.size = Pt(mk_size)
    
    paragraph.add_run(" | ")
    
    en_run = paragraph.add_run(en_text)
    en_run.font.name = "Calibri"
    en_run.font.size = Pt(en_size)
    
    return paragraph
```

---

### Fix #3: PDF Table Cell Width & Overflow

**File**: `scripts/professional_pdf_generator.py`

**Change**: Add proper table configuration:

```python
def create_table(self, data, col_widths=None, row_heights=None):
    """Create properly formatted table with correct dimensions."""
    if col_widths is None:
        # Calculate based on content width
        page_width = 8.5  # inches for A4
        margin = 0.5
        available_width = page_width - (2 * margin)
        col_widths = [available_width / len(data[0])] * len(data[0])
    
    if row_heights is None:
        row_heights = [0.4] * len(data)  # inches
    
    table = Table(
        data,
        colWidths=[w * inch for w in col_widths],
        rowHeights=[h * inch for h in row_heights],
        style=TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY_GREEN),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Prevent overlap
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('ALIGNMENT', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGNMENT', (0, 0), (-1, -1), 'TOP'),  # Critical: prevent overlap
            ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),  # Handle long text
        ])
    )
    
    return table
```

---

### Fix #4: Remove Shading/Border Conflicts

**File**: `scripts/purely_plant_docx_generator.py`

**Change**: Simplify border and shading logic:

```python
def set_cell_background_safe(self, cell, color='70ad47'):
    """Set cell background without conflicts."""
    # Only apply shading, don't try to add borders/text at same time
    shading_elm = OxmlElement("w:shd")
    shading_elm.set(qn("w:fill"), color)
    cell._element.get_or_add_tcPr().append(shading_elm)
    
    # Clear any existing conflicting formatting
    tcPr = cell._element.get_or_add_tcPr()
    # Remove problematic tcBorders if they exist
    existing_borders = tcPr.find(qn('w:tcBorders'))
    if existing_borders is not None:
        tcPr.remove(existing_borders)
```

---

### Fix #5: Unify Generator Implementation

**Files**: Multiple generators creating conflicts

**Solution**: 
1. Keep `professional_pdf_generator.py` as PRIMARY PDF generator
2. Keep `purely_plant_docx_generator.py` as PRIMARY DOCX generator
3. Deprecate/remove:
   - `scripts/pdf_generator.py` (redundant)
   - `scripts/formatter_skill_approval_generator.py` (redundant)
   - `scripts/professional_docx_converter.py` (conflicts with DOCX generator)

---

## Implementation Priority

### Phase 1: CRITICAL (Do First)
1. ✅ Remove duplicate header loop in `purely_plant_docx_generator.py`
2. ✅ Fix character encoding UTF-8 issues
3. ✅ Fix table cell padding/overflow in PDF generator

### Phase 2: IMPORTANT (Do Second)
4. ✅ Remove conflicting generators
5. ✅ Unify generator interface
6. ✅ Add validation for generated documents

### Phase 3: QUALITY (Do Third)
7. ✅ Add unit tests for document generation
8. ✅ Add visual inspection tool
9. ✅ Create regression test suite

---

## Testing Strategy

After fixes, test with:

```bash
# Test DOCX generation
python scripts/purely_plant_docx_generator.py --output test_output.docx

# Test PDF generation
python scripts/professional_pdf_generator.py --output test_output.pdf

# Visual inspection
# Open PDF/DOCX in viewer and verify:
# 1. No duplicate headers
# 2. No garbled text
# 3. No black box overlays
# 4. Proper character encoding (Macedonian text readable)
# 5. Tables properly sized
# 6. All content visible
```

---

## Files Affected

- `scripts/purely_plant_docx_generator.py` - **NEEDS FIXES**
- `scripts/professional_pdf_generator.py` - **NEEDS FIXES**
- `CONTENT_CREATOR_FRAMEWORK/integrated_sop_generator_workflow.py` - May reference buggy generators
- `scripts/pdf_generator.py` - **DEPRECATE**
- `scripts/formatter_skill_approval_generator.py` - **DEPRECATE**
- `scripts/professional_docx_converter.py` - **DEPRECATE**

---

## Expected Outcomes After Fixes

✅ No duplicate headers or titles  
✅ No garbled text - Macedonian characters display correctly  
✅ No black box overlays - all content visible  
✅ Proper table formatting - no overflow  
✅ Consistent bilingual layout  
✅ Production-ready document generation  

---

## Estimated Time to Fix

- Phase 1: 2-3 hours
- Phase 2: 1-2 hours  
- Phase 3: 2-3 hours
- Testing & Validation: 1-2 hours

**Total**: 6-10 hours

---

**Next Step**: Proceed with implementing Phase 1 fixes
