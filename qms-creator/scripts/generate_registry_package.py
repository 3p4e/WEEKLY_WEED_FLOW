#!/usr/bin/env python3
"""
Script to generate the registry package for QMS documents.
"""

import os
import subprocess
from pathlib import Path

import yaml
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


def load_registry():
    """Load the document registry from the YAML file."""
    with open("config/document_registry.yaml", "r") as f:
        return yaml.safe_load(f)


def get_doc_status(doc_id):
    """Determine the status of a document based on its existence in specific directories."""
    search_dirs = [
        "01_QUALITY_ASSURANCE",
        "04_QUALITY_TESTING",
        "sops_created",
        "00_MASTER_DOCUMENTS",
    ]
    for d in search_dirs:
        p = Path(d)
        if p.exists():
            for f in p.glob(f"*{doc_id}*.pdf"):
                return "Issued | Издадено"

    for d in search_dirs:
        p = Path(d)
        if p.exists():
            for f in p.glob(f"*{doc_id}*.md"):
                return "Draft | Нацрт"
            for f in p.glob(f"*{doc_id}*.txt"):
                return "Draft | Нацрт"

    return "Planned | Планирано"


def set_cell_border(cell, **kwargs):
    """
    Set cell border with specified properties.

    Usage:
    set_cell_border(
        cell,
        top={"sz":12, "val": "single", "color": "#FF0000", "space": "0"},
        bottom={"sz":12, "color": "#00FF00", "val": "single"},
        start={"sz":24, "val": "dashed", "shadow": "true"},
        end={"sz":12, "val": "dashed"},
    )
    """
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()

    for edge in ("top", "start", "bottom", "end"):
        edge_data = kwargs.get(edge)
        if edge_data:
            tag = f"w:{edge}"
            element = tcPr.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcPr.append(element)

            for key in ["sz", "val", "color", "space", "shadow"]:
                if key in edge_data:
                    element.set(qn(f"w:{key}"), str(edge_data[key]))


def create_registry_table(doc, registry):
    """Create the registry table in the document."""
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    table.autofit = False

    # Set column widths (approximate)
    # Total width is usually around 9000-10000 units (twips)
    # Col1 (Code): 1500
    # Col2 (Title): 5000
    # Col3 (Type): 1000
    # Col4 (Status): 1500

    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Code | Код"
    hdr_cells[1].text = "Title | Наслов"
    hdr_cells[2].text = "Type | Тип"
    hdr_cells[3].text = "Status | Статус"

    # Style header
    for cell in hdr_cells:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True

    for fam_id, fam_data in registry["families"].items():
        # Add Family Header Row
        row = table.add_row()
        row.cells[0].merge(row.cells[3])
        row.cells[
            0
        ].text = f"{fam_id}: {fam_data.get('name_en')} | {fam_data.get('name_mk')}"
        for paragraph in row.cells[0].paragraphs:
            for run in paragraph.runs:
                run.font.bold = True

        sops = fam_data.get("sops", {})
        for sop_id, sop_data in sops.items():
            row_cells = table.add_row().cells
            row_cells[0].text = sop_id
            row_cells[
                1
            ].text = f"{sop_data.get('title_mk')} | {sop_data.get('title_en')}"
            row_cells[2].text = "SOP"
            row_cells[3].text = get_doc_status(sop_id)

            annexes = sop_data.get("annexes", {})
            for ann_id, ann_data in annexes.items():
                row_cells = table.add_row().cells
                row_cells[0].text = ann_id
                row_cells[
                    1
                ].text = f"{ann_data.get('title_mk')} | {ann_data.get('title_en')}"
                row_cells[2].text = "Annex"
                row_cells[3].text = get_doc_status(ann_id)


def replace_text(doc, old, new):
    """Replace text in document paragraphs and tables."""
    for p in doc.paragraphs:
        if old in p.text:
            p.text = p.text.replace(old, new)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if old in p.text:
                        p.text = p.text.replace(old, new)

    for section in doc.sections:
        for header in [
            section.header,
            section.first_page_header,
            section.even_page_header,
        ]:
            if header:
                for p in header.paragraphs:
                    if old in p.text:
                        p.text = p.text.replace(old, new)
                for table in header.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            for p in cell.paragraphs:
                                if old in p.text:
                                    p.text = p.text.replace(old, new)


def main():
    """Main function to generate registry documents."""
    registry = load_registry()

    # 1. Generate MEMO (A01)
    memo_src = Path(
        "REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-01_General_Memorandum_v4_EDITED.docx"
    )
    memo_dest = Path("01_QUALITY_ASSURANCE/QA_00.04_MEM_Registry_Issuance_v1.0_EN.docx")

    print(f"Generating Registry Memo from {memo_src}...")
    doc = Document(memo_src)

    # Update Header
    for section in doc.sections:
        header = section.header
        if header and header.tables:
            table = header.tables[0]
            # Row 0, Cell 0: ID
            if len(table.rows) > 0:
                table.rows[0].cells[0].text = "QA_00.04_MEM_01_v1"

            # Set Title in Row 1, Cell 1 (replacing placeholder)
            if len(table.rows) > 1:
                table.rows[1].cells[
                    1
                ].text = "Purely Plant Document Registry | Регистар на документи на Purely Plant"

            # Set Date in Row 2
            if len(table.rows) > 2:
                table.rows[2].cells[0].text = "Eff. Date: 15.01.2025"
                table.rows[2].cells[1].text = "Version: 1.0"

    # Replace body placeholders
    replace_text(
        doc,
        "[Document Type and Description]",
        "Purely Plant Document Registry | Регистар на документи на Purely Plant",
    )
    replace_text(doc, "eff. dd.mm.yy", "15.01.25")
    replace_text(doc, "MEMYY_DD_nnn", "MEM25_QA_001")
    replace_text(doc, "___ / ___ /20__", "15 / 01 / 2025")
    replace_text(
        doc,
        "[Замени со Име, Организација, Оддел | Replace with Name / Organization / Department: ]",
        "All Departments | Сите оддели",
    )
    replace_text(
        doc,
        "[Замени со Име, Организација, Оддел | Replace with Name / Organization / Department:]",
        "Quality Assurance | Осигурување на квалитет",
    )
    replace_text(
        doc,
        "[ SUBJECT: Replace with Document Type by format and intended use, ex. REQUEST / COMPLAINT / NOTATION / URGENT INSTRUCTION etc.]",
        "Purely Plant Document Registry | Регистар на документи на Purely Plant",
    )

    # Insert Registry Table
    # Find the content placeholder and insert table there
    content_found = False
    for i, p in enumerate(doc.paragraphs):
        if "[CONTENT:" in p.text:
            p.text = "Please find attached the current status of all QMS documents and annexes."
            # Insert table after this paragraph
            # We can't easily insert *after* a paragraph in python-docx without moving elements
            # So we'll add it to the end, or try to append to the document body
            create_registry_table(doc, registry)
            content_found = True
            break

    if not content_found:
        print("Warning: Content placeholder not found, appending table to end.")
        create_registry_table(doc, registry)

    doc.save(memo_dest)
    print(f"Saved {memo_dest}")

    # 2. Generate Distribution Record (A02)
    dist_src = Path(
        "REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-02_Distribution_Record_v4.docx"
    )
    dist_dest = Path(
        "01_QUALITY_ASSURANCE/QA_00.04_A02_Registry_Distribution_v1.0_EN.docx"
    )

    print(f"Generating Distribution Record from {dist_src}...")
    doc = Document(dist_src)

    # Update Header
    for section in doc.sections:
        header = section.header
        if header and header.tables:
            table = header.tables[0]
            if len(table.rows) > 0:
                table.rows[0].cells[0].text = "QA_00.04_A02_v1"

    replace_text(doc, "QMS-DC-SOP-XXX-ANX-02", "QA_00.04_A02_v1")
    replace_text(doc, "MEM____/____/____", "MEM25_QA_001")
    replace_text(doc, "Subject of Memorandum", "Purely Plant Document Registry")
    replace_text(doc, "Issuing Department", "Quality Assurance")
    replace_text(doc, "Date of Distribution", "15.01.2025")

    recipients = [
        ("Ana Dimitrova", "QA"),
        ("Stefan Petrov", "Facility"),
        ("Blagoj Nikolov", "QP"),
        ("Marija Stojanova", "QC"),
        ("Igor Angelov", "QC"),
        ("Elena Koneska", "QC"),
        ("Dragan Talevski", "Production"),
        ("Vesna Mitrevska", "Production"),
        ("Zoran Trajkovski", "Production"),
        ("Petar Naumov", "Cultivation"),
        ("Biljana Ristovska", "Cultivation"),
        ("Goran Acevski", "Cultivation"),
        ("Sanja Popova", "HR"),
        ("Darko Dimovski", "Logistics"),
        ("Tanja Ilievska", "R&D"),
        ("Nikola Gruev", "Maintenance"),
        ("Maja Ivanova", "QA"),
        ("Viktor Nikolov", "QA"),
        ("Katerina Savevska", "QC"),
        ("Filip Jovanov", "Production"),
        ("Snezana Koleva", "Cultivation"),
        ("Andrej Markov", "Logistics"),
        ("Ivana Janevska", "HR"),
        ("Bojan Stojanovski", "IT"),
        ("Hristina Georgieva", "Regulatory"),
    ]

    # Find the recipient table (Table 1 usually)
    # Based on check_tables.py: Table 1: 27 rows x 5 columns
    if len(doc.tables) > 1:
        table = doc.tables[1]
        # Start from row 2 (row 0 is section header, row 1 is column headers)
        for i, (name, dept) in enumerate(recipients):
            row_idx = i + 2
            if row_idx < len(table.rows):
                row = table.rows[row_idx]
                row.cells[0].text = str(i + 1)
                row.cells[1].text = name
                row.cells[2].text = dept
                row.cells[3].text = "15.01.2025"
            else:
                row = table.add_row()
                row.cells[0].text = str(i + 1)
                row.cells[1].text = name
                row.cells[2].text = dept
                row.cells[3].text = "15.01.2025"
                # Add empty cells for signature
                while len(row.cells) < 5:
                    row.add_cell()

    doc.save(dist_dest)
    print(f"Saved {dist_dest}")

    # 3. Generate Issuance List (A03)
    iss_src = Path(
        "REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-03_Memorandum_Issuance_List_v5.docx"
    )
    iss_dest = Path(
        "01_QUALITY_ASSURANCE/QA_00.04_A03_Registry_Issuance_Log_v1.0_EN.docx"
    )

    print(f"Generating Issuance List from {iss_src}...")
    doc = Document(iss_src)

    # Update Header
    for section in doc.sections:
        header = section.header
        if header and header.tables:
            table = header.tables[0]
            if len(table.rows) > 0:
                table.rows[0].cells[0].text = "QA_00.04_A03_v1"

    replace_text(doc, "MEM_ _ /", "MEM_QA_01/25")
    replace_text(doc, "Issuing Department", "Quality Assurance")
    replace_text(doc, "Date Issued", "15.01.2025")

    # Find the register table (Table 2 usually)
    # Based on check_tables.py: Table 2: 26 rows x 10 columns
    if len(doc.tables) > 2:
        table = doc.tables[2]
        if len(table.rows) > 1:
            row = table.rows[1]
            row.cells[1].text = "MEM25_QA_001"
            row.cells[2].text = "15.01.2025"
            row.cells[3].text = "All Depts"
            row.cells[4].text = "QMS Document Registry"
            row.cells[5].text = "AD"
            row.cells[6].text = "Y"
            row.cells[7].text = "Open"
            row.cells[8].text = "C"

    doc.save(iss_dest)
    print(f"Saved {iss_dest}")

    # 4. Generate Receipt List (A04)
    rec_src = Path(
        "REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-04_Memorandum_Receipt_List_v2.docx"
    )
    rec_dest = Path(
        "01_QUALITY_ASSURANCE/QA_00.04_A04_Registry_Receipt_Log_v1.0_EN.docx"
    )

    print(f"Generating Receipt List from {rec_src}...")
    doc = Document(rec_src)

    # Update Header
    for section in doc.sections:
        header = section.header
        if header and header.tables:
            table = header.tables[0]
            if len(table.rows) > 0:
                table.rows[0].cells[0].text = "QA_00.04_A04_v1"

    replace_text(doc, "rMEM_ _ /", "rMEM_QA_01/25")
    replace_text(doc, "Receiving Department", "Quality Assurance")
    replace_text(doc, "Date Issued", "15.01.2025")

    # Populate one entry for QA receiving the registry (from itself/QA)
    if len(doc.tables) > 2:
        table = doc.tables[2]
        if len(table.rows) > 1:
            row = table.rows[1]
            row.cells[1].text = "MEM25_QA_001"
            row.cells[2].text = "15.01.2025"
            row.cells[3].text = "AD"  # Receiver Initials
            row.cells[4].text = "15.01.2025"  # Action Date
            row.cells[5].text = "15.01.2025"  # Completed Date

    doc.save(rec_dest)
    print(f"Saved {rec_dest}")

    # Convert to PDF
    print("Converting to PDF...")
    for f in [memo_dest, dist_dest, iss_dest, rec_dest]:
        try:
            subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    "01_QUALITY_ASSURANCE",
                    str(f),
                ],
                check=True,
                timeout=60,
            )
            print(f"Converted {f.name} to PDF")
        except Exception as e:
            print(f"Error converting {f.name}: {e}")


if __name__ == "__main__":
    main()
