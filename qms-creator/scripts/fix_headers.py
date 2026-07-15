#!/usr/bin/env python3
"""
QMS Document Header Fixer
Properly structures document headers in Word document format.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print("ERROR: python-docx not available")
    sys.exit(1)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_proper_header(doc: Document, doc_number: str, title: str):
    """Add a properly formatted Word header to the document"""
    
    # Get or create header section
    section = doc.sections[0]
    header = section.header
    
    # Clear existing header
    for p in header.paragraphs:
        p.clear()
    
    # Create header table (3 columns)
    header_table = header.add_table(rows=2, cols=3, width=Inches(6.5))
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Row 1: Logo | Title | Doc Number
    row1 = header_table.rows[0]
    row1.cells[0].text = "PURELY PLANT DOOEL"
    row1.cells[1].text = title.replace("_", " ").upper()
    row1.cells[2].text = f"Doc No: {doc_number}"
    
    # Row 2: Department | Version | Effective Date
    row2 = header_table.rows[1]
    row2.cells[0].text = "Department: Quality"
    row2.cells[1].text = "Version: 1.0"
    row2.cells[2].text = f"Effective: {datetime.now().strftime('%Y-%m-%d')}"
    
    # Format cells
    for row in header_table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in para.runs:
                    run.font.size = Pt(9)
                    run.font.bold = True


def add_traceability_section(doc: Document):
    """Add traceability elements to document"""
    
    traceability_text = """
TRACEABILITY REQUIREMENTS
• All records must include Batch Number / Lot Number
• Record the date and time of activity
• Include operator initials or signature
• Reference related batch documentation
• Maintain chain of custody for samples
"""
    
    # Add at end of document
    doc.add_paragraph()  # Spacing
    p = doc.add_paragraph(traceability_text)
    for run in p.runs:
        run.font.size = Pt(10)


def fix_all_headers(target_dir: str):
    """Fix headers in all docx files"""
    target_path = Path(target_dir)
    fixed = 0
    
    for docx_file in target_path.glob("**/*.docx"):
        try:
            doc = Document(docx_file)
            
            # Extract document number from filename
            doc_number = docx_file.stem.split("_")[0] if "_" in docx_file.stem else "DOC-XXX"
            title = docx_file.stem
            
            # Add proper header
            add_proper_header(doc, doc_number, title)
            
            # Add traceability if not present
            full_text = "\n".join([p.text for p in doc.paragraphs])
            if "batch" not in full_text.lower() and "lot" not in full_text.lower():
                add_traceability_section(doc)
            
            doc.save(docx_file)
            fixed += 1
            logger.info(f"✅ Fixed header: {docx_file.name}")
            
        except Exception as e:
            logger.error(f"❌ Error: {docx_file.name}: {e}")
    
    return fixed


if __name__ == "__main__":
    project_root = "/home/azzu/PROJ/Cannabis EU GMP QMS Creator"
    target_dir = os.path.join(project_root, "00_MASTER_DOCUMENTS")
    
    print("\n" + "="*60)
    print("QMS HEADER FIXER")
    print("="*60 + "\n")
    
    fixed = fix_all_headers(target_dir)
    print(f"\n✅ Fixed {fixed} documents with proper Word headers")
