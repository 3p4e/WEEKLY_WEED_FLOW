# Document Generation Bug Fixes - Implementation Guide

**Status**: Ready to Implement  
**Date**: January 23, 2026  
**Critical Issues**: Duplicate headers, garbled text, black box overlays  

---

## Root Cause Analysis

The document generation pipeline has **multiple generators** creating PDFs/DOCX files through `test_pipeline.py`:

### Files in Pipeline:
1. **`scripts/pdf_generator.py`** - Main PDF generator (ReportLab)
2. **`scripts/purely_plant_docx_generator.py`** - DOCX template generator
3. **`test_pipeline.py`** - Test harness calling both generators

### Issues Found:

#### Issue #1: Aggressive Heading Detection in pdf_generator.py

**Location**: `scripts/pdf_generator.py` lines 445-480

**Problem**: The `_is_heading1`, `_is_heading2`, `_is_heading3` methods use regex that matches too broadly:

```python
def _is_heading1(self, line: str) -> bool:
    # ALL CAPS lines or lines starting with single digit
    return (line.isupper() and len(line) > 5) or re.match(r'^\d+\.\s+[A-Z]', line)
```

**Why It's a Bug**: 
- Lines like "STANDARD OPERATING PROCEDURE" (all caps) are detected as headings
- Then the SAME line is processed again in the content loop
- If a line contains both "# TITLE" and content after, it gets parsed twice

**Impact**: Duplicate headers appearing multiple times in PDFs

---

#### Issue #2: No Deduplication Logic

**Location**: `scripts/pdf_generator.py` lines 435-465

**Problem**: The `_parse_content` method doesn't check if a line has already been processed:

```python
while i < len(lines):
    line = lines[i].rstrip()
    
    if not line:
        i += 1
        continue
    
    # DETECTS heading
    if self._is_heading1(line):
        story.append(Paragraph(line, self.styles['Heading1']))
    # ... more checks ...
    else:
        # BUT ALSO ADDS IT HERE if none of the checks match
        escaped_line = self._escape_text(line)
        story.append(Paragraph(escaped_line, self.styles['Normal']))
    
    i += 1  # Line is always moved forward
```

**Why It's a Bug**: If a line matches as a heading, it's added, but the `else` block still executes due to elif chain.

**Impact**: Content appears twice

---

#### Issue #3: Character Encoding for Bilingual Content

**Location**: `scripts/pdf_generator.py` lines 480+

**Problem**: The `_escape_text` method only escapes `&`, `<`, `>` but NOT Macedonian/Unicode characters

```python
def _escape_text(self, text: str) -> str:
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text
```

**Why It's a Bug**: 
- Macedonian text contains characters like Ц, Д, Љ, Њ, Ј, Џ
- ReportLab may not handle these properly without explicit encoding
- This causes garbled text in Macedonian sections

**Impact**: Illegible Macedonian text in PDFs

---

#### Issue #4: Table Overlap in ReportLab

**Location**: Tables created with implicit dimensions

**Problem**: Tables don't specify rowHeights/colWidths, causing content to overlap:

```python
# No explicit height/width constraints
table = Table(data)  # BAD - causes overlapping

# Should be:
table = Table(
    data,
    colWidths=[inch * 2, inch * 3, inch * 1.5],  # GOOD
    rowHeights=[inch * 0.5 for _ in data]  # GOOD
)
```

**Impact**: Black boxes covering content in tables

---

## Fixes Implementation

### Fix #1: Improve Heading Detection Logic

**File**: `scripts/pdf_generator.py`

**Change**: Make heading detection more specific and prevent double-processing

```python
def _parse_content(self, content: str) -> List:
    """Parse text content into PDF elements."""
    story = []
    lines = content.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Detect and process headings
        if self._is_heading1(line):
            # Clean the heading (remove markdown markers)
            clean_heading = self._clean_heading(line)
            story.append(Paragraph(clean_heading, self.styles['Heading1']))
            i += 1  # Move to next line
            continue  # IMPORTANT: continue to skip the else block
            
        elif self._is_heading2(line):
            clean_heading = self._clean_heading(line)
            story.append(Paragraph(clean_heading, self.styles['Heading2']))
            i += 1
            continue  # Skip else block
            
        elif self._is_heading3(line):
            clean_heading = self._clean_heading(line)
            story.append(Paragraph(clean_heading, self.styles['Heading3']))
            i += 1
            continue  # Skip else block
            
        # Detect bullet points
        elif line.strip().startswith(('- ', '• ', '* ')):
            bullet_text = line.strip()[2:].strip()
            story.append(Paragraph(f'• {bullet_text}', self.styles['Bullet']))
            i += 1
            continue
            
        # Regular paragraph
        else:
            escaped_line = self._escape_text(line)
            # Only add if not empty after escaping
            if escaped_line.strip():
                story.append(Paragraph(escaped_line, self.styles['Normal']))
            i += 1

    return story

def _clean_heading(self, line: str) -> str:
    """Clean heading by removing markdown markers."""
    # Remove markdown heading markers (# ## ###)
    line = re.sub(r'^#+\s+', '', line)
    # Remove trailing markdown
    line = re.sub(r'\s+#+$', '', line)
    # Trim whitespace
    return line.strip()
```

---

### Fix #2: Improve Character Encoding for Bilingual Text

**File**: `scripts/pdf_generator.py`

**Change**: Add proper Unicode handling

```python
def _escape_text(self, text: str) -> str:
    """Escape special characters for ReportLab, preserve Unicode."""
    # Ensure text is properly encoded as UTF-8
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    
    # Only escape XML-special characters that break ReportLab
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    # Ensure no control characters that can break rendering
    # Keep Unicode characters intact (Macedonian, etc)
    text = ''.join(c for c in text if ord(c) >= 32 or c in '\t\n\r')
    
    return text
```

---

### Fix #3: Add Explicit Table Dimensions

**File**: `scripts/pdf_generator.py`

**Change**: Specify column widths and row heights in `_create_title_page`

```python
def _create_title_page(self, metadata: Dict) -> List:
    """Create document title page."""
    story = []
    story.append(Spacer(1, 2 * inch))
    
    # Title
    title_style = ParagraphStyle(
        'Title',
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    story.append(Paragraph(metadata['document_title'], title_style))

    # Document ID
    doc_id_style = ParagraphStyle(
        'DocID',
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#3498DB'),
        alignment=TA_CENTER,
        spaceAfter=40
    )
    story.append(Paragraph(metadata['document_id'], doc_id_style))

    story.append(Spacer(1, 1 * inch))

    # Metadata table with EXPLICIT dimensions
    metadata_data = [
        ['Effective Date:', metadata['effective_date']],
        ['Version:', metadata['version']],
        ['Department:', metadata['department']],
        ['Approved By:', metadata['approved_by']],
        ['Classification:', 'CONFIDENTIAL - INTERNAL USE ONLY']
    ]

    # FIX: Add explicit column widths and row heights
    metadata_table = Table(
        metadata_data,
        colWidths=[2.5 * inch, 2.5 * inch],  # Two equal columns
        rowHeights=[0.4 * inch] * len(metadata_data),  # Fixed row height
        style=TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F4F8')),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertical center
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 11),
            ('FONT', (1, 0), (1, -1), 'Helvetica', 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ])
    )
    story.append(metadata_table)

    return story
```

---

### Fix #4: Add Heading Detection Improvements

**File**: `scripts/pdf_generator.py`

**Change**: Make detection less aggressive and handle edge cases

```python
def _is_heading1(self, line: str) -> bool:
    """Detect if line is a major heading."""
    stripped = line.strip()
    
    # Markdown-style heading (one or more #)
    if re.match(r'^#+\s+', stripped):
        return True
    
    # All caps AND long enough to be a title (not just one word)
    if (stripped.isupper() and len(stripped) > 10 and 
        not stripped.endswith((':', '|', '-')) and
        ' ' in stripped):  # Must have space (multi-word)
        return True
    
    # Numbered section like "1. PURPOSE"
    if re.match(r'^\d+\.\s+[A-Z]{3,}', stripped):
        return True
    
    return False

def _is_heading2(self, line: str) -> bool:
    """Detect if line is a subheading."""
    stripped = line.strip()
    
    # Markdown-style level 2
    if re.match(r'^#{2,}\s+', stripped):
        return True
    
    # Numbered subsection like "1.1 Details"
    if re.match(r'^\d+\.\d+\s+[A-Z]', stripped):
        return True
    
    return False

def _is_heading3(self, line: str) -> bool:
    """Detect if line is a sub-subheading."""
    stripped = line.strip()
    
    # Markdown-style level 3+
    if re.match(r'^#{3,}\s+', stripped):
        return True
    
    # Numbered sub-subsection like "1.1.1 Detail"
    if re.match(r'^\d+\.\d+\.\d+\s+[A-Z]', stripped):
        return True
    
    return False
```

---

## Testing After Fixes

### Unit Tests to Add

```python
# In a new file: scripts/test_pdf_generator.py

def test_no_duplicate_headers():
    """Ensure headers are not duplicated in output"""
    generator = PDFGenerator()
    content = "# Title\nSome content\n## Subtitle\nMore content"
    story = generator._parse_content(content)
    
    # Count Paragraph elements that are headings
    heading_count = sum(1 for p in story if isinstance(p, Paragraph))
    # Should be 4 (2 headings + 2 content paragraphs)
    assert heading_count == 4, f"Expected 4 elements, got {heading_count}"

def test_unicode_preservation():
    """Ensure Macedonian characters preserved"""
    generator = PDFGenerator()
    macedonian_text = "Целта на оваа СОП е да воспостави процедура"
    escaped = generator._escape_text(macedonian_text)
    
    # Should preserve Macedonian characters
    assert "Целта" in escaped
    assert "СОП" in escaped
    assert len(escaped) > len(macedonian_text) - 5  # Allow some XML escaping

def test_table_dimensions():
    """Ensure tables have explicit dimensions"""
    # Tables should specify colWidths and rowHeights
    pass
```

---

## Fixes Application Order

1. **Phase 1** (Critical - Do First):
   - Apply Fix #1: Heading detection with `continue` statements
   - Apply Fix #2: Unicode character handling
   - Apply Fix #4: Improved heading detection regex

2. **Phase 2** (Important - Do Second):
   - Apply Fix #3: Table dimension specifications
   - Add unit tests
   - Run test_pipeline.py

3. **Phase 3** (Quality - Do Third):
   - Visual inspection of generated PDFs
   - Check for remaining duplicates
   - Verify Macedonian text readability
   - Check table formatting

---

## Expected Results After Fixes

✅ No duplicate headers or titles  
✅ Macedonian characters display correctly  
✅ No black box overlays - all table content visible  
✅ Proper paragraph spacing and alignment  
✅ All content readable without formatting issues  

---

## Files to Modify

- ✅ `scripts/pdf_generator.py` - PRIMARY FOCUS
- ✅ `scripts/purely_plant_docx_generator.py` - Secondary (may need similar fixes)

## Files to Test

- ✅ Run: `python test_pipeline.py --sop QA_00.06 --output test_output/`
- ✅ Visual inspection of: `test_output/QA_00.06.pdf` and `test_output/QA_00.06_approval_page.docx`

---

**Implementation Status**: Ready to begin Phase 1 fixes
