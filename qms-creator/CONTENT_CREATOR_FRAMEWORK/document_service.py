"""
QMS Document Service
Scans output directories and builds document hierarchy for the web application.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Base paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
PDF_DIR = OUTPUT_DIR / "pdf"
DOCX_DIR = OUTPUT_DIR / "docx"


@dataclass
class Annex:
    """Represents an annex document attached to a parent SOP."""

    id: str
    code: str
    title: str
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    version: str = "1.0"


@dataclass
class Document:
    """Represents a main SOP document."""

    id: str
    code: str
    title: str
    department: str
    department_code: str
    status: str = "completed"
    version: str = "1.0"
    effective_date: str = "2025-01-22"
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    annexes: list = field(default_factory=list)


@dataclass
class Chapter:
    """Represents a document chapter/department."""

    id: str
    code: str
    name: str
    folder: str
    documents: list = field(default_factory=list)


# Department mappings
DEPARTMENTS = {
    "01": {"code": "QA", "name": "Quality Assurance", "folder": "01_QUALITY_ASSURANCE"},
    "02": {"code": "MAT", "name": "Materials Management", "folder": "02_MATERIALS"},
    "03": {"code": "PRO", "name": "Production", "folder": "03_PRODUCTION"},
    "04": {"code": "QC", "name": "Quality Testing", "folder": "04_QUALITY_TESTING"},
    "05": {"code": "HRM", "name": "Human Resources", "folder": "05_HUMAN_RESOURCES"},
    "06": {"code": "EQU", "name": "Equipment", "folder": "06_EQUIPMENT"},
    "07": {"code": "SAN", "name": "Sanitation", "folder": "07_SANITATION"},
    "08": {"code": "VAL", "name": "Validation", "folder": "08_VALIDATION"},
    "09": {"code": "REC", "name": "Records Management", "folder": "09_RECORDS"},
}

# Code prefix to department mapping
CODE_TO_DEPT = {
    "QA": "01",
    "MAT": "02",
    "PRO": "03",
    "QC": "04",
    "HRM": "05",
    "EQU": "06",
    "SAN": "07",
    "VAL": "08",
    "REC": "09",
}


def parse_filename(filename: str) -> dict:
    """
    Parse a document filename to extract metadata.

    Examples:
        QA_00.01_Quality_Manual_v1.0_EN.pdf
        QA_00.02_A01_Document_Templates_v1.0_EN.pdf
        QC_01.08_Cannabinoid_Testing_HPLC_v1.0_EN.pdf
    """
    # Remove extension
    name = Path(filename).stem

    # Pattern for main documents: CODE_XX.YY_Title_vX.Y_LANG
    # Pattern for annexes: CODE_XX.YY_AZZ_Title_vX.Y_LANG

    # Try annex pattern first (has _A followed by digits)
    annex_pattern = r"^([A-Z]+)_(\d+\.\d+)_(A\d+)_(.+)_v(\d+\.\d+)_([A-Z]+)$"
    annex_match = re.match(annex_pattern, name)

    if annex_match:
        code_prefix, code_num, annex_num, title, version, lang = annex_match.groups()
        return {
            "type": "annex",
            "code_prefix": code_prefix,
            "code": f"{code_prefix}_{code_num}",
            "annex_code": f"{code_prefix}_{code_num}_{annex_num}",
            "annex_num": annex_num,
            "title": title.replace("_", " "),
            "version": version,
            "language": lang,
        }

    # Try main document pattern
    main_pattern = r"^([A-Z]+)_(\d+\.\d+)_(.+)_v(\d+\.\d+)_([A-Z]+)$"
    main_match = re.match(main_pattern, name)

    if main_match:
        code_prefix, code_num, title, version, lang = main_match.groups()
        return {
            "type": "document",
            "code_prefix": code_prefix,
            "code": f"{code_prefix}_{code_num}",
            "title": title.replace("_", " "),
            "version": version,
            "language": lang,
        }

    # Fallback for non-standard names
    return {
        "type": "unknown",
        "code": name,
        "title": name.replace("_", " "),
        "version": "1.0",
    }


def scan_pdf_directory() -> dict:
    """Scan PDF directory and return mapping of code to file path."""
    pdf_files = {}

    if not PDF_DIR.exists():
        return pdf_files

    # Scan root pdf directory
    for f in PDF_DIR.glob("*.pdf"):
        parsed = parse_filename(f.name)
        key = parsed.get("annex_code") or parsed.get("code")
        if key:
            pdf_files[key] = str(f.relative_to(BASE_DIR))

    # Scan subdirectories
    for subdir in PDF_DIR.iterdir():
        if subdir.is_dir():
            for f in subdir.glob("*.pdf"):
                parsed = parse_filename(f.name)
                key = parsed.get("annex_code") or parsed.get("code")
                if key:
                    pdf_files[key] = str(f.relative_to(BASE_DIR))

    return pdf_files


def scan_docx_directory() -> dict:
    """Scan DOCX and MD directory and return mapping of code to file path."""
    docx_files = {}

    if not DOCX_DIR.exists():
        return docx_files

    # Scan root directory for both docx and md
    extensions = ["*.docx", "*.md"]
    
    for ext in extensions:
        for f in DOCX_DIR.glob(ext):
            parsed = parse_filename(f.name)
            key = parsed.get("annex_code") or parsed.get("code")
            if key:
                docx_files[key] = str(f.relative_to(BASE_DIR))

    # Scan subdirectories
    for subdir in DOCX_DIR.iterdir():
        if subdir.is_dir():
            for ext in extensions:
                for f in subdir.glob(ext):
                    parsed = parse_filename(f.name)
                    key = parsed.get("annex_code") or parsed.get("code")
                    if key:
                        docx_files[key] = str(f.relative_to(BASE_DIR))

    return docx_files


def build_document_hierarchy() -> list:
    """
    Build the complete document hierarchy.
    Returns list of Chapter objects with nested Documents and Annexes.
    """
    pdf_files = scan_pdf_directory()
    docx_files = scan_docx_directory()

    # Collect all document codes
    all_codes = set(pdf_files.keys()) | set(docx_files.keys())

    # Separate main documents from annexes
    main_docs = {}
    annexes = {}

    for code in all_codes:
        if "_A" in code and re.search(r"_A\d+$", code):
            # This is an annex
            # Extract parent code (e.g., QA_00.02 from QA_00.02_A01)
            parent_code = re.sub(r"_A\d+$", "", code)
            if parent_code not in annexes:
                annexes[parent_code] = []
            annexes[parent_code].append(code)
        else:
            main_docs[code] = True

    # Build chapters
    chapters = {}

    for code in main_docs:
        # Extract department from code prefix
        code_prefix = code.split("_")[0]
        dept_num = CODE_TO_DEPT.get(code_prefix, "00")
        dept_info = DEPARTMENTS.get(
            dept_num,
            {
                "code": code_prefix,
                "name": code_prefix,
                "folder": f"{dept_num}_{code_prefix}",
            },
        )

        if dept_num not in chapters:
            chapters[dept_num] = Chapter(
                id=f"chapter-{dept_num}",
                code=dept_info["code"],
                name=f"{dept_num} {dept_info['name']}",
                folder=dept_info["folder"],
                documents=[],
            )

        # Parse the filename to get title
        pdf_path = pdf_files.get(code)
        docx_path = docx_files.get(code)

        title = code  # Default
        if pdf_path:
            parsed = parse_filename(Path(pdf_path).name)
            title = parsed.get("title", code)
        elif docx_path:
            parsed = parse_filename(Path(docx_path).name)
            title = parsed.get("title", code)

        # Build annexes for this document
        doc_annexes = []
        for annex_code in sorted(annexes.get(code, [])):
            annex_pdf = pdf_files.get(annex_code)
            annex_docx = docx_files.get(annex_code)

            annex_title = annex_code
            if annex_pdf:
                parsed = parse_filename(Path(annex_pdf).name)
                annex_title = parsed.get("title", annex_code)

            doc_annexes.append(
                Annex(
                    id=f"annex-{annex_code.replace('.', '-').replace('_', '-')}",
                    code=annex_code,
                    title=annex_title,
                    pdf_path=annex_pdf,
                    docx_path=annex_docx,
                )
            )

        # Create document
        doc = Document(
            id=f"doc-{code.replace('.', '-').replace('_', '-')}",
            code=code,
            title=title,
            department=dept_info["name"],
            department_code=dept_info["code"],
            pdf_path=pdf_path,
            docx_path=docx_path,
            annexes=doc_annexes,
        )

        chapters[dept_num].documents.append(doc)

    # Sort documents within each chapter
    for chapter in chapters.values():
        chapter.documents.sort(key=lambda d: d.code)

    # Return sorted chapters
    return [chapters[k] for k in sorted(chapters.keys())]


def get_document_by_code(code: str) -> Optional[Document]:
    """Find a document by its code."""
    hierarchy = build_document_hierarchy()

    for chapter in hierarchy:
        for doc in chapter.documents:
            if doc.code == code:
                return doc
            # Check annexes
            for annex in doc.annexes:
                if annex.code == code:
                    return annex

    return None


def get_file_path(code: str, file_type: str = "pdf") -> Optional[str]:
    """Get the absolute file path for a document code."""
    if file_type == "pdf":
        files = scan_pdf_directory()
    else:
        files = scan_docx_directory()

    relative_path = files.get(code)
    if relative_path:
        return str(BASE_DIR / relative_path)

    return None


def get_hierarchy_json() -> list:
    """Get the hierarchy as JSON-serializable dictionaries."""
    hierarchy = build_document_hierarchy()

    result = []
    for chapter in hierarchy:
        chapter_dict = {
            "id": chapter.id,
            "code": chapter.code,
            "name": chapter.name,
            "folder": chapter.folder,
            "documentCount": len(chapter.documents),
            "documents": [],
        }

        for doc in chapter.documents:
            doc_dict = {
                "id": doc.id,
                "code": doc.code,
                "title": doc.title,
                "department": doc.department,
                "departmentCode": doc.department_code,
                "status": doc.status,
                "version": doc.version,
                "effectiveDate": doc.effective_date,
                "pdfPath": doc.pdf_path,
                "docxPath": doc.docx_path,
                "annexCount": len(doc.annexes),
                "annexes": [],
            }

            for annex in doc.annexes:
                annex_dict = {
                    "id": annex.id,
                    "code": annex.code,
                    "title": annex.title,
                    "version": annex.version,
                    "pdfPath": annex.pdf_path,
                    "docxPath": annex.docx_path,
                }
                doc_dict["annexes"].append(annex_dict)

            chapter_dict["documents"].append(doc_dict)

        result.append(chapter_dict)

    return result


def get_stats() -> dict:
    """Get document statistics."""
    hierarchy = build_document_hierarchy()

    total_docs = 0
    total_annexes = 0
    pdf_count = len(scan_pdf_directory())
    docx_count = len(scan_docx_directory())

    for chapter in hierarchy:
        total_docs += len(chapter.documents)
        for doc in chapter.documents:
            total_annexes += len(doc.annexes)

    return {
        "totalDocuments": total_docs,
        "totalAnnexes": total_annexes,
        "totalFiles": total_docs + total_annexes,
        "pdfFiles": pdf_count,
        "docxFiles": docx_count,
        "chapters": len(hierarchy),
        "lastUpdated": datetime.now().isoformat(),
    }


# Quick test
if __name__ == "__main__":
    print("Scanning documents...")

    stats = get_stats()
    print(f"\nStatistics:")
    print(f"  Total Documents: {stats['totalDocuments']}")
    print(f"  Total Annexes: {stats['totalAnnexes']}")
    print(f"  PDF Files: {stats['pdfFiles']}")
    print(f"  DOCX Files: {stats['docxFiles']}")
    print(f"  Chapters: {stats['chapters']}")

    hierarchy = get_hierarchy_json()
    print(f"\nChapters:")
    for chapter in hierarchy:
        print(f"  {chapter['name']}: {chapter['documentCount']} documents")
