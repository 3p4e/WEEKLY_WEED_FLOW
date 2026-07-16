#!/usr/bin/env python3
"""
Debug script to examine and compare generated memorandum documents.
Helps identify issues with placeholder replacement, table population, and document structure.
"""

import os
import sys
from pathlib import Path

from docx import Document


def print_header(text, char="="):
    """Print formatted header."""
    print(f"\n{char * 80}")
    print(f"{text}")
    print(f"{char * 80}")


def analyze_document_structure(doc_path):
    """Analyze the structure of a DOCX document."""
    print_header(f"ANALYZING: {Path(doc_path).name}")

    try:
        doc = Document(doc_path)
    except Exception as e:
        print(f"ERROR: Could not open {doc_path}: {e}")
        return None

    analysis = {
        "path": str(doc_path),
        "name": Path(doc_path).name,
        "paragraph_count": len(doc.paragraphs),
        "table_count": len(doc.tables),
        "paragraphs": [],
        "tables": [],
        "headers_found": False,
    }

    # Check for headers
    for section in doc.sections:
        header = section.header
        if header and header.tables:
            analysis["headers_found"] = True
            analysis["header_tables"] = len(header.tables)
            print(f"Headers found: Yes (tables: {len(header.tables)})")
            for i, table in enumerate(header.tables):
                print(
                    f"  Header Table {i}: {len(table.rows)} rows x {len(table.columns) if table.rows else 0} cols"
                )
                for r, row in enumerate(table.rows):
                    cells = [c.text.strip() for c in row.cells]
                    print(f"    Row {r}: {cells}")
            break

    if not analysis["headers_found"]:
        print("Headers found: No")

    # Analyze paragraphs
    print(f"\nParagraph count: {analysis['paragraph_count']}")
    print("First 15 paragraphs:")
    for i, para in enumerate(doc.paragraphs[:15]):
        if para.text.strip():
            truncated = para.text[:100] + "..." if len(para.text) > 100 else para.text
            analysis["paragraphs"].append({"index": i, "text": para.text})
            print(f"  [{i:2d}] {truncated}")

    # Analyze tables
    print(f"\nTable count: {analysis['table_count']}")
    for i, table in enumerate(doc.tables):
        table_info = {
            "index": i,
            "rows": len(table.rows),
            "columns": len(table.columns) if table.rows else 0,
            "first_row": [],
            "content_sample": [],
        }

        if table.rows:
            # Get first row
            first_cells = [c.text.strip() for c in table.rows[0].cells]
            table_info["first_row"] = first_cells

            # Get content sample (first 3 data rows)
            sample_rows = []
            for r in range(min(3, len(table.rows))):
                cells = [c.text.strip() for c in table.rows[r].cells]
                sample_rows.append(cells)
            table_info["content_sample"] = sample_rows

        analysis["tables"].append(table_info)

        print(
            f"  Table {i}: {table_info['rows']} rows x {table_info['columns']} columns"
        )
        if first_cells:
            print(
                f"    First row: {first_cells[:3]}{'...' if len(first_cells) > 3 else ''}"
            )

    return analysis


def compare_with_template(generated_path, template_path):
    """Compare generated document with template to see what changed."""
    print_header(
        f"COMPARING: {Path(generated_path).name} vs {Path(template_path).name}"
    )

    try:
        gen_doc = Document(generated_path)
        temp_doc = Document(template_path)
    except Exception as e:
        print(f"ERROR: Could not open documents: {e}")
        return

    # Check paragraph differences
    print("Paragraph comparison:")
    print(f"  Generated: {len(gen_doc.paragraphs)} paragraphs")
    print(f"  Template:  {len(temp_doc.paragraphs)} paragraphs")

    # Check for placeholder text
    placeholders = [
        "[CONTENT:",
        "[SUBJECT:",
        "[Замени со",
        "[Replace with",
        "MEM____",
        "___ / ___",
        "eff. dd.mm.yy",
        "QMS-DC-SOP-XXX",
    ]

    print("\nSearching for leftover placeholders in generated document:")
    placeholder_found = False
    for i, para in enumerate(gen_doc.paragraphs):
        for placeholder in placeholders:
            if placeholder in para.text:
                print(f"  Paragraph {i}: Contains '{placeholder}'")
                print(f"    Text: {para.text[:150]}...")
                placeholder_found = True

    if not placeholder_found:
        print("  No leftover placeholders found ✓")

    # Check tables
    print(f"\nTable count comparison:")
    print(f"  Generated: {len(gen_doc.tables)} tables")
    print(f"  Template:  {len(temp_doc.tables)} tables")

    # Check if tables were populated
    if len(gen_doc.tables) > 0 and len(gen_doc.tables) == len(temp_doc.tables):
        print("\nTable population check:")
        for i, (gen_table, temp_table) in enumerate(
            zip(gen_doc.tables, temp_doc.tables)
        ):
            gen_empty = all(
                all(not cell.text.strip() for cell in row.cells)
                for row in gen_table.rows
            )
            temp_empty = all(
                all(not cell.text.strip() for cell in row.cells)
                for row in temp_table.rows
            )

            if gen_empty and not temp_empty:
                print(f"  Table {i}: Still empty (template had content)")
            elif not gen_empty and temp_empty:
                print(f"  Table {i}: Populated ✓")
            elif gen_empty and temp_empty:
                print(f"  Table {i}: Still empty")
            else:
                print(f"  Table {i}: Both have content")


def check_document_ids():
    """Check if all documents have proper IDs in headers."""
    print_header("DOCUMENT ID CHECK")

    memo_files = [
        "01_QUALITY_ASSURANCE/QA_00.04_MEM_Registry_Issuance_v1.0_EN.docx",
        "01_QUALITY_ASSURANCE/QA_00.04_A02_Registry_Distribution_v1.0_EN.docx",
        "01_QUALITY_ASSURANCE/QA_00.04_A03_Registry_Issuance_Log_v1.0_EN.docx",
        "01_QUALITY_ASSURANCE/QA_00.04_A04_Registry_Receipt_Log_v1.0_EN.docx",
    ]

    expected_ids = {
        "QA_00.04_MEM_Registry_Issuance_v1.0_EN.docx": "QA_00.04_MEM_01_v1",
        "QA_00.04_A02_Registry_Distribution_v1.0_EN.docx": "QA_00.04_A02_v1",
        "QA_00.04_A03_Registry_Issuance_Log_v1.0_EN.docx": "QA_00.04_A03_v1",
        "QA_00.04_A04_Registry_Receipt_Log_v1.0_EN.docx": "QA_00.04_A04_v1",
    }

    for file_path in memo_files:
        if not Path(file_path).exists():
            print(f"Missing: {Path(file_path).name}")
            continue

        try:
            doc = Document(file_path)
            doc_id_found = False

            # Check header for document ID
            for section in doc.sections:
                header = section.header
                if header and header.tables:
                    for table in header.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                if expected_ids[Path(file_path).name] in cell.text:
                                    doc_id_found = True
                                    break

            status = "✓" if doc_id_found else "✗"
            print(
                f"{status} {Path(file_path).name}: Expected '{expected_ids[Path(file_path).name]}' - {'Found' if doc_id_found else 'NOT FOUND'}"
            )

        except Exception as e:
            print(f"✗ {Path(file_path).name}: ERROR - {e}")


def verify_distribution_list():
    """Verify the distribution list is properly populated."""
    print_header("DISTRIBUTION LIST VERIFICATION")

    dist_file = "01_QUALITY_ASSURANCE/QA_00.04_A02_Registry_Distribution_v1.0_EN.docx"

    if not Path(dist_file).exists():
        print(f"Missing: {dist_file}")
        return

    try:
        doc = Document(dist_file)

        if len(doc.tables) < 2:
            print("ERROR: Not enough tables in document")
            return

        # Table 1 should be the distribution table (based on earlier analysis)
        dist_table = doc.tables[1]
        print(
            f"Distribution table: {len(dist_table.rows)} rows x {len(dist_table.columns) if dist_table.rows else 0} columns"
        )

        # Count populated rows (skip header rows 0 and 1)
        populated_rows = 0
        empty_rows = 0

        print("\nFirst 10 data rows (starting from row 2):")
        for r in range(2, min(12, len(dist_table.rows))):
            cells = [c.text.strip() for c in dist_table.rows[r].cells]
            is_empty = all(cell == "" for cell in cells)

            if not is_empty:
                populated_rows += 1
                print(f"  Row {r}: {cells}")
            else:
                empty_rows += 1

        print(f"\nDistribution list statistics:")
        print(f"  Total rows in table: {len(dist_table.rows)}")
        print(f"  Header rows: 2")
        print(f"  Populated data rows: {populated_rows}")
        print(f"  Empty data rows: {empty_rows}")

        if populated_rows >= 25:
            print("  ✓ Distribution list has at least 25 recipients")
        else:
            print(
                f"  ✗ Distribution list only has {populated_rows} recipients (expected 25)"
            )

    except Exception as e:
        print(f"ERROR: {e}")


def check_registry_table():
    """Check if the registry table was properly inserted."""
    print_header("REGISTRY TABLE CHECK")

    memo_file = "01_QUALITY_ASSURANCE/QA_00.04_MEM_Registry_Issuance_v1.0_EN.docx"

    if not Path(memo_file).exists():
        print(f"Missing: {memo_file}")
        return

    try:
        doc = Document(memo_file)

        # Look for the registry table (should be the last table)
        if len(doc.tables) == 0:
            print("No tables found in document")
            return

        registry_table = doc.tables[-1]
        print(
            f"Registry table: {len(registry_table.rows)} rows x {len(registry_table.columns) if registry_table.rows else 0} columns"
        )

        # Check header
        if registry_table.rows:
            header_cells = [c.text.strip() for c in registry_table.rows[0].cells]
            print(f"Header: {header_cells}")

        # Count entries
        data_rows = max(0, len(registry_table.rows) - 1)  # Subtract header
        print(f"Data rows: {data_rows}")

        if data_rows > 50:
            print("✓ Registry table appears to be populated with many entries")
        else:
            print(
                f"✗ Registry table only has {data_rows} data rows (expected many more)"
            )

        # Check for document families
        family_headers = 0
        for row in registry_table.rows:
            cells = [c.text.strip() for c in row.cells]
            if len(cells) > 0 and "QA_" in cells[0] and ":" in cells[0]:
                family_headers += 1

        print(f"Document family headers found: {family_headers}")

    except Exception as e:
        print(f"ERROR: {e}")


def main():
    """Main function to run all debug checks."""
    print_header("MEMORANDUM PACKAGE DEBUG ANALYSIS")

    # Set current directory
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)

    # Define files to analyze
    files_to_analyze = [
        (
            "01_QUALITY_ASSURANCE/QA_00.04_MEM_Registry_Issuance_v1.0_EN.docx",
            "REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-01_General_Memorandum_v4_EDITED.docx",
        ),
        (
            "01_QUALITY_ASSURANCE/QA_00.04_A02_Registry_Distribution_v1.0_EN.docx",
            "REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-02_Distribution_Record_v4.docx",
        ),
        (
            "01_QUALITY_ASSURANCE/QA_00.04_A03_Registry_Issuance_Log_v1.0_EN.docx",
            "REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-03_Memorandum_Issuance_List_v5.docx",
        ),
        (
            "01_QUALITY_ASSURANCE/QA_00.04_A04_Registry_Receipt_Log_v1.0_EN.docx",
            "REFERENCE_MATERIALS/Memo SOP/QMS-DC-SOP-XXX-ANX-04_Memorandum_Receipt_List_v2.docx",
        ),
    ]

    # Run analyses
    for gen_file, temp_file in files_to_analyze:
        if Path(gen_file).exists():
            analyze_document_structure(gen_file)
            if Path(temp_file).exists():
                compare_with_template(gen_file, temp_file)
            else:
                print(f"\nTemplate not found: {temp_file}")
        else:
            print(f"\nGenerated file not found: {gen_file}")

    # Run specific checks
    check_document_ids()
    verify_distribution_list()
    check_registry_table()

    print_header("ANALYSIS COMPLETE")


if __name__ == "__main__":
    main()
