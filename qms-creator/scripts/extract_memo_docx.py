#!/usr/bin/env python3
"""
extract_memo_docx.py

Utility script that extracts human-readable text from the memorandum control SOP
source documents (DOCX format) located beneath reference materials. The script
walks the input directory, converts each DOCX file into a UTF-8 text file, and
stores the result in the specified output directory while preserving file stems.

Example usage:

    python3 scripts/extract_memo_docx.py \
        --input "REFERENCE_MATERIALS/Memo SOP" \
        --output "output/memo_analysis"

Requirements:
    pip install python-docx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

try:
    from docx import Document
    from docx.document import Document as DocxDocument
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table, _Cell
    from docx.text.paragraph import Paragraph
except ImportError as exc:  # pragma: no cover - dependency import guard
    raise SystemExit(
        "python-docx is required to run this extractor. "
        "Install it with `pip install python-docx` and retry."
    ) from exc


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def iter_block_items(parent) -> Iterable[Paragraph | Table]:
    """
    Yield each paragraph and table child within *parent* in document order.
    Supports both Document objects and table cells for recursive traversal.
    """
    if isinstance(parent, DocxDocument):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise TypeError(f"Unsupported parent type: {type(parent)!r}")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent_elm)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent_elm)


def extract_table_text(table: Table) -> List[str]:
    """
    Flatten a docx Table into list of string rows with tab-separated columns.
    """
    rows: List[str] = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cell_lines = []
            for item in iter_block_items(cell):
                if isinstance(item, Paragraph):
                    text = item.text.strip()
                    if text:
                        cell_lines.append(text)
                elif isinstance(item, Table):
                    # Recursively flatten nested tables
                    nested_lines = extract_table_text(item)
                    if nested_lines:
                        cell_lines.append(" | ".join(nested_lines))
            cells.append(" ".join(cell_lines).strip())
        rows.append("\t".join(cells))
    return rows


def extract_docx_to_lines(doc_path: Path) -> List[str]:
    """
    Convert a DOCX file into a list of cleaned text lines, preserving basic structure.
    """
    document = Document(doc_path)
    lines: List[str] = []

    for item in iter_block_items(document):
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if text:
                lines.append(text)
        elif isinstance(item, Table):
            table_lines = extract_table_text(item)
            if table_lines:
                lines.append("\n".join(table_lines))

    return lines


def safe_write_text(output_path: Path, lines: List[str]) -> None:
    """
    Write the extracted lines to disk using UTF-8 encoding.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI interface
# --------------------------------------------------------------------------- #
def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract text from memorandum SOP DOCX files."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("REFERENCE_MATERIALS/Memo SOP"),
        help="Directory containing DOCX source files (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/memo_analysis"),
        help="Directory to write extracted .txt files (default: %(default)s)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress information while processing files.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if not args.input.exists() or not args.input.is_dir():
        print(f"[ERROR] Input directory not found: {args.input}", file=sys.stderr)
        return 1

    docx_files = sorted(args.input.glob("*.docx"))
    if not docx_files:
        print(f"[WARNING] No DOCX files found in: {args.input}", file=sys.stderr)
        return 0

    extracted_count = 0
    for docx_path in docx_files:
        try:
            lines = extract_docx_to_lines(docx_path)
            if not lines:
                print(
                    f"[WARNING] No text extracted from {docx_path.name}",
                    file=sys.stderr,
                )
            output_path = args.output / f"{docx_path.stem}.txt"
            safe_write_text(output_path, lines)
            extracted_count += 1
            if args.verbose:
                print(f"[OK] {docx_path.name} -> {output_path}")
        except Exception as exc:  # pragma: no cover - runtime guard
            print(f"[ERROR] Failed to extract {docx_path.name}: {exc}", file=sys.stderr)

    print(
        f"Extraction complete. {extracted_count}/{len(docx_files)} files processed. "
        f"Output directory: {args.output}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
