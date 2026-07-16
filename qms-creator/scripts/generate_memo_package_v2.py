#!/usr/bin/env python3
"""
Generate all memorandum annexes for the Document Registry issuance.
This script creates properly formatted annex documents populated with 
data for the memorandum being issued to all departments.
"""

import yaml
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
from pathlib import Path
import subprocess

def load_registry():
    """Load the document registry YAML file."""
    with open('config/document_registry.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_all_documents_by_chapter(registry):
    """
    Get all documents organized by chapter/department.
    Returns a dictionary with chapter codes as keys.
    """
    chapters = {}
    
    for fam_id, fam_data in registry.get('families', {}).items():
        chapter_code = fam_id.split('_')[0]  # QA, QC, PRO, etc.
        chapter_name = fam_data.get('name_en', fam_id)
        chapter_desc = fam_data.get('description', '')
        
        if chapter_code not in chapters:
            chapters[chapter_code] = {
                'name': chapter_name,
                'description': chapter_desc,
                'sops': [],
                'annexes': []
            }
        
        for sop_id, sop_data in fam_data.get('sops', {}).items():
            doc_info = {
                'id': sop_id,
                'title_en': sop_data.get('title_en', ''),
                'title_mk': sop_data.get('title_mk', ''),
                'type': 'SOP'
            }
            chapters[chapter_code]['sops'].append(doc_info)
            
            # Get annexes
            for ann_id, ann_data in sop_data.get('annexes', {}).items():
                ann_info = {
                    'id': ann_id,
                    'title_en': ann_data.get('title_en', ''),
                    'title_mk': ann_data.get('title_mk', ''),
                    'type': 'Annex',
                    'parent_sop': sop_id
                }
                chapters[chapter_code]['annexes'].append(ann_info)
    
    return chapters

def set_cell_shading(cell, color):
    """Set cell background color."""
    shading_elm = parse_xml(r'<w:shd {} w:fill="{}"/>'.format(nsdecls('w'), color))
    cell._tc.get_or_add_tcPr().append(shading_elm)

def replace_text_in_doc(doc, old_text, new_text):
    """Replace text in all paragraphs of a document."""
    for paragraph in doc.paragraphs:
        if old_text in paragraph.text:
            paragraph.text = paragraph.text.replace(old_text, new_text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    if old_text in paragraph.text:
                        paragraph.text = paragraph.text.replace(old_text, new_text)

def add_document_table(doc, registry):
    """Add the complete document list table to the memo."""
    # Create main document table
    table = doc.add_table(rows=1, cols=5)
    table.style = 'Table Grid'
    
    # Set header row
    header_cells = table.rows[0].cells
    header_cells[0].text = 'Chapter'
    header_cells[1].text = 'Doc Code'
    header_cells[2].text = 'Title (English)'
    header_cells[3].text = 'Type'
    header_cells[4].text = 'Status'
    
    # Style header
    for cell in header_cells:
        set_cell_shading(cell, '2E7D32')  # Dark green
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.bold = True
                run.font.size = Pt(10)
    
    # Get all documents by chapter
    chapters = get_all_documents_by_chapter(registry)
    
    # Track if we've started a new chapter
    current_chapter = None
    
    for chapter_code, chapter_data in sorted(chapters.items()):
        # Add chapter header row
        chapter_name = chapter_data['name']
        chapter_desc = chapter_data['description']
        
        # Add SOPs
        for sop in sorted(chapter_data['sops'], key=lambda x: x['id']):
            row = table.add_row()
            cells = row.cells
            cells[0].text = f"{chapter_code}\n{chapter_name}"
            cells[1].text = sop['id']
            cells[2].text = sop['title_en']
            cells[3].text = 'SOP'
            cells[4].text = 'Issued'
            
            # Style cells
            for cell in cells:
                cell.paragraphs[0].runs[0].font.size = Pt(9)
        
        # Add Annexes
        for ann in sorted(chapter_data['annexes'], key=lambda x: x['id']):
            row = table.add_row()
            cells = row.cells
            cells[0].text = f"{chapter_code}\n{chapter_name}"
            cells[1].text = ann['id']
            cells[2].text = ann['title_en']
            cells[3].text = 'Annex'
            cells[4].text = 'Issued'
            
            for cell in cells:
                cell.paragraphs[0].runs[0].font.size = Pt(9)

def create_memorandum_annex_01(registry, output_path):
    """Create Annex 01 - General Memorandum Template."""
    src = Path("REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-01_General_Memorandum_v4_EDITED.docx")
    if not src.exists():
        print(f"Source file not found: {src}")
        return False
    
    doc = Document(src)
    
    # Update document code
    replace_text_in_doc(doc, "QMS-DC-SOP-XXX-ANX-01", "QA_00.04_A01_v1")
    
    # Update MEM code
    replace_text_in_doc(doc, "MEMYY_DD_nnn", "MEM25_QA_001")
    
    # Update date
    replace_text_in_doc(doc, "___ / ___ / 20__", "15 / 01 / 2025")
    
    # Update recipient
    replace_text_in_doc(doc, "[Замени со Име, Организација, Оддел | Replace with Name / Organization / Department: ]", 
                       "All Departments | Сите оддели")
    
    # Update sender
    replace_text_in_doc(doc, "[Замени со Име, Организација, Оддел | Replace with Name / Organization / Department:]", 
                       "Quality Assurance | Осигурување на квалитет")
    
    # Update subject
    replace_text_in_doc(doc, "[ SUBJECT:  Replace with Document Type by format and intended use]", 
                       "Purely Plant Document Registry | Регистар на документи на Purely Plant")
    
    doc.save(output_path)
    print(f"Created: {output_path}")
    return True

def create_annex_02_distribution_record(output_path, recipients):
    """Create Annex 02 - Document Distribution Record."""
    src = Path("REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-02_Distribution_Record_v4.docx")
    if not src.exists():
        print(f"Source file not found: {src}")
        return False
    
    doc = Document(src)
    
    # Update header
    replace_text_in_doc(doc, "QMS-DC-SOP-XXX-ANX-02", "QA_00.04_A02_v1")
    replace_text_in_doc(doc, "MEM____/____/____", "MEM25_QA_001")
    replace_text_in_doc(doc, "Subject of Memorandum", "Purely Plant Document Registry")
    replace_text_in_doc(doc, "Issuing Department", "Quality Assurance")
    replace_text_in_doc(doc, "Date of Distribution", "15.01.2025")
    
    # Populate recipient table (Table 1 has 27 rows + header)
    # From our analysis: Table 1 has 27 rows x 5 columns
    table = doc.tables[1]  # Distribution table
    
    for i, recipient in enumerate(recipients):
        if i + 1 < len(table.rows):  # Skip header row
            row = table.rows[i + 1]
            row.cells[1].text = recipient['name']
            row.cells[2].text = recipient['department']
            row.cells[3].text = "15.01.2025"
    
    doc.save(output_path)
    print(f"Created: {output_path}")
    return True

def create_annex_03_issuance_list(output_path, memo_code="MEM25_QA_001"):
    """Create Annex 03 - Memorandum Issuance List."""
    src = Path("REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-03_Memorandum_Issuance_List_v5.docx")
    if not src.exists():
        print(f"Source file not found: {src}")
        return False
    
    doc = Document(src)
    
    # Update header - Table 0 is the identification table
    table0 = doc.tables[0]
    table0.rows[1].cells[1].text = memo_code
    table0.rows[1].cells[0].text = "MEMO Issuance List Code:"
    
    # Update register table - Table 2 is the first log page (26 rows x 10 cols)
    table2 = doc.tables[2]
    row = table2.rows[1]  # First entry row
    row.cells[1].text = memo_code  # REF NO
    row.cells[2].text = "15.01.2025"  # DATE
    row.cells[3].text = "All Depts"  # TO DEPT
    row.cells[4].text = "QMS Document Registry"  # SUBJECT
    row.cells[5].text = "AD"  # PREP
    row.cells[6].text = "Y"  # DDR
    row.cells[7].text = "Open"  # STAT
    row.cells[8].text = "C"  # CLOSED
    
    doc.save(output_path)
    print(f"Created: {output_path}")
    return True

def create_annex_04_receipt_list(output_path, memo_code="MEM25_QA_001"):
    """Create Annex 04 - Memorandum Receipt List."""
    src = Path("REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-04_Memorandum_Receipt_List_v2.docx")
    if not src.exists():
        print(f"Source file not found: {src}")
        return False
    
    doc = Document(src)
    
    # Update header - Table 0 is the identification table
    table0 = doc.tables[0]
    table0.rows[1].cells[1].text = f"r{memo_code}"  # rMEM25_QA_001
    table0.rows[1].cells[0].text = "MEMO Receipt List Code:"
    
    # Update register table - Table 2 is the first log page
    table2 = doc.tables[2]
    row = table2.rows[1]  # First entry row
    row.cells[1].text = memo_code  # REF NO
    row.cells[2].text = "15.01.2025"  # DATE REC
    
    doc.save(output_path)
    print(f"Created: {output_path}")
    return True

def create_registry_memorandum(registry, output_path):
    """Create the main registry memorandum with document list."""
    src = Path("REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-01_General_Memorandum_v4_EDITED.docx")
    if not src.exists():
        print(f"Source file not found: {src}")
        return False
    
    doc = Document(src)
    
    # Update header info
    replace_text_in_doc(doc, "QMS-DC-SOP-XXX-ANX-01", "QA_00.04_MEM_01_v1")
    replace_text_in_doc(doc, "MEMYY_DD_nnn", "MEM25_QA_001")
    replace_text_in_doc(doc, "___ / ___ / 20__", "15 / 01 / 2025")
    replace_text_in_doc(doc, "[Замени со Име, Организација, Оддел | Replace with Name / Organization / Department: ]", 
                       "All Departments | Сите оддели")
    replace_text_in_doc(doc, "[Замени со Име, Организација, Оддел | Replace with Name / Organization / Department:]", 
                       "Quality Assurance | Осигурување на квалитет")
    replace_text_in_doc(doc, "[ SUBJECT:  Replace with Document Type by format and intended use]", 
                       "Purely Plant Document Registry | Регистар на документи на Purely Plant")
    
    # Find the placeholder for the table and replace with document list
    for paragraph in doc.paragraphs:
        if "[CONTENT:" in paragraph.text:
            paragraph.clear()
            add_document_table(doc, registry)
            break
    
    doc.save(output_path)
    print(f"Created: {output_path}")
    return True

def convert_to_pdf(docx_path):
    """Convert DOCX to PDF using LibreOffice."""
    try:
        subprocess.run([
            "soffice", "--headless", "--convert-to", "pdf", 
            "--outdir", str(Path(docx_path).parent), str(docx_path)
        ], check=True, capture_output=True)
        print(f"Converted to PDF: {Path(docx_path).with_suffix('.pdf')}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting {docx_path} to PDF: {e}")
        return False

def main():
    print("=" * 80)
    print("GENERATING MEMORANDUM PACKAGE FOR DOCUMENT REGISTRY")
    print("=" * 80)
    
    # Load registry
    registry = load_registry()
    print(f"\nLoaded document registry with {len(registry.get('families', {}))} families")
    
    # Define recipients for distribution record (25 people)
    recipients = [
        {"name": "Ana Dimitrova", "department": "QA Manager"},
        {"name": "Stefan Petrov", "department": "Facility Manager"},
        {"name": "Blagoj Nikolov", "department": "QP"},
        {"name": "Marija Stojanova", "department": "QC Manager"},
        {"name": "Igor Angelov", "department": "QC Analyst"},
        {"name": "Elena Koneska", "department": "QC Analyst"},
        {"name": "Dragan Talevski", "department": "Production Manager"},
        {"name": "Vesna Mitrevska", "department": "Production Supervisor"},
        {"name": "Zoran Trajkovski", "department": "Production Operator"},
        {"name": "Petar Naumov", "department": "Cultivation Manager"},
        {"name": "Biljana Ristovska", "department": "Cultivation Supervisor"},
        {"name": "Goran Acevski", "department": "Cultivation Operator"},
        {"name": "Sanja Popova", "department": "HR Manager"},
        {"name": "Darko Dimovski", "department": "Logistics Manager"},
        {"name": "Tanja Ilievska", "department": "R&D Manager"},
        {"name": "Nikola Gruev", "department": "Maintenance Manager"},
        {"name": "Maja Ivanova", "department": "QA Specialist"},
        {"name": "Viktor Nikolov", "department": "QA Specialist"},
        {"name": "Katerina Savevska", "department": "QC Specialist"},
        {"name": "Filip Jovanov", "department": "Production Specialist"},
        {"name": "Snezana Koleva", "department": "Cultivation Specialist"},
        {"name": "Andrej Markov", "department": "Logistics Specialist"},
        {"name": "Ivana Janevska", "department": "HR Specialist"},
        {"name": "Bojan Stojanovski", "department": "IT Specialist"},
        {"name": "Hristina Georgieva", "department": "Regulatory Affairs"},
    ]
    
    output_dir = Path("01_QUALITY_ASSURANCE")
    
    # Create all documents
    docs_created = []
    
    # 1. Create main registry memorandum with document list
    memo_path = output_dir / "QA_00.04_MEM_Document_Registry_v1.0_EN.docx"
    if create_registry_memorandum(registry, memo_path):
        docs_created.append(memo_path)
    
    # 2. Create Annex 01
    a01_path = output_dir / "QA_00.04_A01_General_Memorandum_v1.0_EN.docx"
    if create_memorandum_annex_01(registry, a01_path):
        docs_created.append(a01_path)
    
    # 3. Create Annex 02 with recipients
    a02_path = output_dir / "QA_00.04_A02_Distribution_Record_v1.0_EN.docx"
    if create_annex_02_distribution_record(a02_path, recipients):
        docs_created.append(a02_path)
    
    # 4. Create Annex 03
    a03_path = output_dir / "QA_00.04_A03_Memorandum_Issuance_List_v1.0_EN.docx"
    if create_annex_03_issuance_list(a03_path):
        docs_created.append(a03_path)
    
    # 5. Create Annex 04
    a04_path = output_dir / "QA_00.04_A04_Memorandum_Receipt_List_v1.0_EN.docx"
    if create_annex_04_receipt_list(a04_path):
        docs_created.append(a04_path)
    
    # Convert all to PDF
    print("\n" + "=" * 80)
    print("CONVERTING TO PDF")
    print("=" * 80)
    for doc_path in docs_created:
        convert_to_pdf(doc_path)
    
    print("\n" + "=" * 80)
    print("MEMORANDUM PACKAGE GENERATION COMPLETE")
    print("=" * 80)
    print(f"\nDocuments created:")
    for doc_path in docs_created:
        print(f"  - {doc_path}")
        pdf_path = doc_path.with_suffix('.pdf')
        if pdf_path.exists():
            print(f"    + {pdf_path}")

if __name__ == "__main__":
    main()
