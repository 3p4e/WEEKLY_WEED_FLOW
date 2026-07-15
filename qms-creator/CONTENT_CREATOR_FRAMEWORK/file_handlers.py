"""
Multi-Format File Handlers

Extracts text and metadata from various document formats for RAG indexing.
Supports: PDF, DOCX, Markdown, TXT, CSV, images (metadata only), CAD (metadata only).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class FileHandler(ABC):
    """Base class for format-specific text extraction and metadata."""

    @abstractmethod
    def extract_text(self, file_path: Path) -> Optional[str]:
        """
        Extract text content from file.

        Returns None for non-text formats (images, CAD).
        """
        ...

    @abstractmethod
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract file metadata (always available regardless of text support)."""
        ...

    def _base_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Common metadata for all file types."""
        stat = file_path.stat()
        return {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_stem": file_path.stem,
            "extension": file_path.suffix.lower(),
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 1),
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "parent_folder": file_path.parent.name,
        }


class PDFHandler(FileHandler):
    """Extract text from PDF files using PyPDF2, with Gemini OCR fallback for scanned pages."""

    def extract_text(self, file_path: Path) -> Optional[str]:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(file_path))
            pages = []
            empty_page_indices = []

            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages.append((i, text.strip()))
                else:
                    empty_page_indices.append(i)

            # OCR fallback for pages PyPDF2 couldn't extract
            if empty_page_indices:
                try:
                    from CONTENT_CREATOR_FRAMEWORK.ocr import GeminiOCR

                    ocr = GeminiOCR()
                    if ocr.available:
                        logger.info(
                            f"OCR fallback for {len(empty_page_indices)} scanned pages "
                            f"in {file_path.name}"
                        )
                        ocr_texts = ocr.ocr_pdf_pages(file_path, empty_page_indices)
                        for idx, text in zip(empty_page_indices, ocr_texts):
                            if text and text.strip():
                                pages.append((idx, text.strip()))
                    else:
                        logger.warning(
                            f"{len(empty_page_indices)} scanned pages skipped "
                            f"in {file_path.name} (no OCR available)"
                        )
                except ImportError:
                    logger.warning(
                        f"{len(empty_page_indices)} scanned pages skipped "
                        f"in {file_path.name} (OCR module not available)"
                    )

            # Sort by page index and join
            pages.sort(key=lambda x: x[0])
            full_text = "\n\n".join(text for _, text in pages)

            if not full_text.strip():
                logger.warning(f"PDF has no extractable text: {file_path.name}")
                return None
            return full_text

        except Exception as e:
            logger.error(f"PDF extraction failed for {file_path.name}: {e}")
            return None

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata = self._base_metadata(file_path)
        metadata["format"] = "pdf"
        metadata["text_extractable"] = True

        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(file_path))
            metadata["page_count"] = len(reader.pages)

            info = reader.metadata
            if info:
                metadata["pdf_title"] = info.get("/Title", "")
                metadata["pdf_author"] = info.get("/Author", "")
                metadata["pdf_subject"] = info.get("/Subject", "")
        except Exception:
            metadata["page_count"] = 0

        return metadata


class DOCXHandler(FileHandler):
    """Extract text from DOCX files using python-docx."""

    def extract_text(self, file_path: Path) -> Optional[str]:
        try:
            from docx import Document

            doc = Document(str(file_path))
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text.strip())

            # Also extract table content
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(
                        cell.text.strip() for cell in row.cells if cell.text.strip()
                    )
                    if row_text:
                        paragraphs.append(row_text)

            full_text = "\n\n".join(paragraphs)
            if not full_text.strip():
                logger.warning(f"DOCX has no text: {file_path.name}")
                return None
            return full_text

        except Exception as e:
            logger.error(f"DOCX extraction failed for {file_path.name}: {e}")
            return None

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata = self._base_metadata(file_path)
        metadata["format"] = "docx"
        metadata["text_extractable"] = True

        try:
            from docx import Document

            doc = Document(str(file_path))
            metadata["paragraph_count"] = len(doc.paragraphs)
            metadata["table_count"] = len(doc.tables)

            core = doc.core_properties
            if core:
                metadata["docx_title"] = core.title or ""
                metadata["docx_author"] = core.author or ""
                metadata["docx_subject"] = core.subject or ""
        except Exception:
            pass

        return metadata


class MarkdownHandler(FileHandler):
    """Extract text from Markdown and plain text files."""

    def extract_text(self, file_path: Path) -> Optional[str]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                return None
            return text
        except Exception as e:
            logger.error(f"Text extraction failed for {file_path.name}: {e}")
            return None

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata = self._base_metadata(file_path)
        metadata["format"] = "markdown" if file_path.suffix == ".md" else "text"
        metadata["text_extractable"] = True

        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            metadata["line_count"] = text.count("\n") + 1
            metadata["word_count"] = len(text.split())
        except Exception:
            pass

        return metadata


class CSVHandler(FileHandler):
    """Extract text from CSV/Excel files."""

    def extract_text(self, file_path: Path) -> Optional[str]:
        try:
            import pandas as pd

            ext = file_path.suffix.lower()
            if ext == ".csv":
                df = pd.read_csv(str(file_path), encoding="utf-8", encoding_errors="replace")
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(str(file_path))
            else:
                return None

            # Convert to readable text: column headers + rows
            text_parts = []
            text_parts.append("Columns: " + ", ".join(str(c) for c in df.columns))
            text_parts.append(df.to_string(index=False, max_rows=500))

            full_text = "\n\n".join(text_parts)
            return full_text if full_text.strip() else None

        except Exception as e:
            logger.error(f"CSV/Excel extraction failed for {file_path.name}: {e}")
            return None

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata = self._base_metadata(file_path)
        metadata["format"] = "spreadsheet"
        metadata["text_extractable"] = True

        try:
            import pandas as pd

            ext = file_path.suffix.lower()
            if ext == ".csv":
                df = pd.read_csv(str(file_path), nrows=0)
            else:
                df = pd.read_excel(str(file_path), nrows=0)

            metadata["column_count"] = len(df.columns)
            metadata["columns"] = list(str(c) for c in df.columns)
        except Exception:
            pass

        return metadata


class ImageHandler(FileHandler):
    """
    Handle image files - metadata extraction only (no OCR).

    Images are classified and stored as metadata entries in the index
    so agents know they exist, but text content is not extracted.
    """

    def extract_text(self, file_path: Path) -> Optional[str]:
        # No text extraction for images
        return None

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata = self._base_metadata(file_path)
        metadata["format"] = "image"
        metadata["text_extractable"] = False

        try:
            from PIL import Image

            with Image.open(str(file_path)) as img:
                metadata["image_width"] = img.width
                metadata["image_height"] = img.height
                metadata["image_format"] = img.format
                metadata["image_mode"] = img.mode
        except Exception:
            pass

        return metadata


class CADHandler(FileHandler):
    """
    Handle CAD files - metadata only (no content extraction).

    CAD files are cataloged so agents know about engineering drawings
    and can reference them, but content is not extracted.
    """

    def extract_text(self, file_path: Path) -> Optional[str]:
        # No text extraction for CAD files
        return None

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata = self._base_metadata(file_path)
        metadata["format"] = "cad"
        metadata["text_extractable"] = False
        metadata["cad_type"] = file_path.suffix.lower().lstrip(".")
        return metadata


# ============================================================
# Handler Registry
# ============================================================

HANDLER_MAP: Dict[str, type] = {
    # Text-extractable formats
    ".pdf": PDFHandler,
    ".docx": DOCXHandler,
    ".doc": DOCXHandler,  # python-docx may handle some .doc files
    ".md": MarkdownHandler,
    ".txt": MarkdownHandler,
    ".csv": CSVHandler,
    ".xlsx": CSVHandler,
    ".xls": CSVHandler,
    # Image formats (metadata only)
    ".jpg": ImageHandler,
    ".jpeg": ImageHandler,
    ".png": ImageHandler,
    ".tiff": ImageHandler,
    ".tif": ImageHandler,
    ".bmp": ImageHandler,
    ".gif": ImageHandler,
    ".webp": ImageHandler,
    # CAD formats (metadata only)
    ".dwg": CADHandler,
    ".dxf": CADHandler,
    ".step": CADHandler,
    ".stp": CADHandler,
    ".iges": CADHandler,
    ".igs": CADHandler,
    ".stl": CADHandler,
}


def get_handler(file_path: Path) -> Optional[FileHandler]:
    """
    Get appropriate handler for a file based on its extension.

    Returns None if extension is not supported.
    """
    ext = file_path.suffix.lower()
    handler_cls = HANDLER_MAP.get(ext)
    if handler_cls:
        return handler_cls()
    return None


def is_supported(file_path: Path) -> bool:
    """Check if file extension is supported."""
    return file_path.suffix.lower() in HANDLER_MAP


def get_supported_extensions() -> List[str]:
    """Return all supported file extensions."""
    return list(HANDLER_MAP.keys())
