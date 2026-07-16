#!/usr/bin/env python3
"""
Script to examine table counts and structure in reference annex files.
Helps understand the layout of memorandum annex templates for proper document generation.
"""

import os
import sys
from pathlib import Path

from docx import Document


def analyze_docx_tables(filepath):
    """
    Analyze all tables in a DOCX file.

    Args:
        filepath (str or Path): Path to the DOCX file

    Returns:
        dict: Analysis results with table counts, dimensions, and sample content
    """
    try:
        doc = Document(filepath)
        tables = doc.tables

        analysis = {
            "file_path": str(filepath),
            "table_count": len(tables),
            "tables": [],
        }

        for i, table in enumerate(tables):
            table_info = {
                "index": i,
                "rows": len(table.rows),
                "columns": len(table.columns) if table.rows else 0,
                "header_sample": [],
                "first_row_sample": [],
            }

            # Get header sample (first row content)
            if table.rows:
                header_cells = []
                for cell in table.rows[0].cells:
                    text = cell.text.strip()
                    header_cells.append(text)
                table_info["header_sample"] = header_cells

            # Get first data row sample if available
            if len(table.rows) > 1:
                data_cells = []
                for cell in table.rows[1].cells:
                    text = cell.text.strip()
                    data_cells.append(text)
                table_info["first_row_sample"] = data_cells

            # Identify likely table type based on content
            header_text = " ".join(header_cells).lower() if header_cells else ""
            if any(keyword in header_text for keyword in ["code", "код", "document"]):
                table_info["likely_type"] = "document_registry"
            elif any(
                keyword in header_text for keyword in ["name", "име", "recipient"]
            ):
                table_info["likely_type"] = "distribution_list"
            elif any(keyword in header_text for keyword in ["date", "датум", "issued"]):
                table_info["likely_type"] = "issuance_log"
            elif any(
                keyword in header_text
                for keyword in ["received", "прием", "acknowledge"]
            ):
                table_info["likely_type"] = "receipt_log"
            elif any(
                keyword in header_text for keyword in ["memorandum", "меморандум"]
            ):
                table_info["likely_type"] = "memorandum_header"
            else:
                table_info["likely_type"] = "unknown"

            analysis["tables"].append(table_info)

        return analysis

    except Exception as e:
        return {
            "file_path": str(filepath),
            "error": str(e),
            "table_count": 0,
            "tables": [],
        }


def print_analysis_summary(analysis):
    """Print formatted analysis results."""
    print(f"\n{'=' * 80}")
    print(f"FILE: {Path(analysis['file_path']).name}")
    print(f"PATH: {analysis['file_path']}")

    if "error" in analysis:
        print(f"ERROR: {analysis['error']}")
        return

    print(f"TABLES: {analysis['table_count']}")

    for table_info in analysis["tables"]:
        print(
            f"\n  Table {table_info['index']}: {table_info['rows']} rows × {table_info['columns']} columns"
        )
        print(f"    Likely type: {table_info['likely_type']}")

        if table_info["header_sample"]:
            header_display = " | ".join(table_info["header_sample"][:3])
            if len(table_info["header_sample"]) > 3:
                header_display += f" ... (+{len(table_info['header_sample']) - 3} more)"
            print(f"    Header: {header_display}")

        if table_info["first_row_sample"]:
            data_display = " | ".join(table_info["first_row_sample"][:3])
            if len(table_info["first_row_sample"]) > 3:
                data_display += (
                    f" ... (+{len(table_info['first_row_sample']) - 3} more)"
                )
            print(f"    First row: {data_display}")


def analyze_all_annex_files():
    """Analyze all annex files in the reference materials directory."""
    script_dir = Path(__file__).parent.parent
    memo_sop_dir = script_dir / "REFERENCE_MATERIALS" / "Memo SOP"

    if not memo_sop_dir.exists():
        print(f"ERROR: Directory not found: {memo_sop_dir}")
        return []

    # Find all DOCX files
    docx_files = list(memo_sop_dir.glob("*.docx"))

    if not docx_files:
        print(f"ERROR: No DOCX files found in {memo_sop_dir}")
        return []

    print(f"Found {len(docx_files)} DOCX files in {memo_sop_dir}")

    all_analyses = []
    for docx_file in sorted(docx_files):
        print(f"\nAnalyzing: {docx_file.name}")
        analysis = analyze_docx_tables(docx_file)
        all_analyses.append(analysis)
        print_analysis_summary(analysis)

    return all_analyses


def generate_table_summary_table(all_analyses):
    """Generate a summary table of all files and their table structures."""
    print(f"\n{'=' * 80}")
    print("SUMMARY OF ALL ANNEX FILES")
    print("=" * 80)

    summary_data = []
    for analysis in all_analyses:
        if "error" in analysis:
            continue

        filename = Path(analysis["file_path"]).name
        table_count = analysis["table_count"]

        # Extract key information
        table_types = []
        for table in analysis["tables"]:
            table_types.append(
                f"T{table['index']}: {table['likely_type']} ({table['rows']}×{table['columns']})"
            )

        summary_data.append(
            {"file": filename, "tables": table_count, "types": ", ".join(table_types)}
        )

    # Print summary table
    print(f"{'File':<40} {'Tables':<8} {'Table Types and Dimensions'}")
    print(f"{'-' * 40} {'-' * 8} {'-' * 50}")

    for item in summary_data:
        print(f"{item['file']:<40} {item['tables']:<8} {item['types']}")


def main():
    """Main function to run the table analysis."""
    print("=" * 80)
    print("ANNEX TABLE STRUCTURE ANALYZER")
    print("=" * 80)
    print("Analyzing table structures in reference memorandum annex files...")

    try:
        all_analyses = analyze_all_annex_files()

        if all_analyses:
            generate_table_summary_table(all_analyses)

            # Save detailed report to file
            report_path = Path(__file__).parent / "table_analysis_report.txt"
            with open(report_path, "w", encoding="utf-8") as f:
                original_stdout = sys.stdout
                sys.stdout = f

                print("ANNEX TABLE STRUCTURE ANALYSIS REPORT")
                print("Generated by check_tables.py")
                print("=" * 80)

                for analysis in all_analyses:
                    print_analysis_summary(analysis)

                generate_table_summary_table(all_analyses)

                sys.stdout = original_stdout

            print(f"\nDetailed report saved to: {report_path}")

        print("\nAnalysis complete!")

    except ImportError as e:
        print(f"\nERROR: Required module not found: {e}")
        print("Please install python-docx: pip install python-docx")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
