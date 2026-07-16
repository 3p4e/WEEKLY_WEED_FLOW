"""
Purely Plant SOP Document Generator Engine

Professional DOCX generation with Purely Plant corporate styles, RACI matrices,
embedded diagrams, and complete SOP structure.
"""

from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import io
from datetime import datetime

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class PurelyPlantColors:
    """Purely Plant corporate color palette"""
    FOREST_GREEN = RGBColor(34, 139, 34)  # #228B22
    DARK_BLUE = RGBColor(0, 51, 102)  # #003366
    GOLD = RGBColor(255, 215, 0)  # #FFD700
    LIGHT_GRAY = RGBColor(240, 240, 240)  # #F0F0F0
    DARK_GRAY = RGBColor(64, 64, 64)  # #404040
    WHITE = RGBColor(255, 255, 255)  # #FFFFFF


class PurelyPlantDocxEngine:
    """
    Professional DOCX generator for Purely Plant SOPs.

    Generates complete SOP documents with:
    - Cover page with approvals and revision history
    - Table of contents (auto-generated)
    - All 11 standard sections
    - RACI matrix with duty explanations
    - Embedded diagrams
    - Professional formatting and branding
    """

    def __init__(self, template_path: Optional[str] = None):
        """
        Initialize DOCX engine.

        Args:
            template_path: Optional path to template DOCX file
        """
        if template_path and Path(template_path).exists():
            self.doc = Document(template_path)
        else:
            self.doc = Document()

        self._setup_styles()
        self.image_counter = 0

    def _setup_styles(self):
        """Configure Purely Plant corporate styles"""

        # Document margins
        sections = self.doc.sections
        for section in sections:
            section.top_margin = Cm(2)
            section.bottom_margin = Cm(2)
            section.left_margin = Cm(2.5)
            section.right_margin = Cm(2.5)

        # Title style
        if "Title" in self.doc.styles:
            style = self.doc.styles["Title"]
            style.font.name = "Arial"
            style.font.size = Pt(28)
            style.font.bold = True
            style.font.color.rgb = PurelyPlantColors.DARK_BLUE
            style.paragraph_format.space_after = Pt(12)

        # Heading 1 (Section headings)
        if "Heading 1" in self.doc.styles:
            style = self.doc.styles["Heading 1"]
            style.font.name = "Arial"
            style.font.size = Pt(16)
            style.font.bold = True
            style.font.color.rgb = PurelyPlantColors.FOREST_GREEN
            style.paragraph_format.space_before = Pt(12)
            style.paragraph_format.space_after = Pt(6)

        # Heading 2 (Subsection headings)
        if "Heading 2" in self.doc.styles:
            style = self.doc.styles["Heading 2"]
            style.font.name = "Arial"
            style.font.size = Pt(13)
            style.font.bold = True
            style.font.color.rgb = PurelyPlantColors.FOREST_GREEN
            style.paragraph_format.space_before = Pt(10)
            style.paragraph_format.space_after = Pt(4)

        # Normal style
        if "Normal" in self.doc.styles:
            style = self.doc.styles["Normal"]
            style.font.name = "Calibri"
            style.font.size = Pt(11)
            style.paragraph_format.line_spacing = 1.15

    def add_cover_page(self, metadata: Dict[str, Any]) -> None:
        """
        Add professional cover page with Purely Plant branding.

        Args:
            metadata: Dictionary with:
                - title: SOP title
                - code: Document code (e.g., QA_00.02)
                - version: Version number
                - effective_date: Effective date
                - department: Responsible department
                - owner: Document owner
                - logo_path: Optional path to logo
                - approvals: List of approval signatures
                - revisions: List of revision history
        """

        # Logo (if provided)
        if metadata.get("logo_path"):
            try:
                logo_path = metadata["logo_path"]
                if Path(logo_path).exists():
                    self.doc.add_picture(logo_path, width=Inches(1.5))
                    self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                logger.warning(f"Could not add logo: {e}")

        # Title
        title = self.doc.add_heading(metadata.get("title", "Untitled SOP"), 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Document Information Table
        self.doc.add_paragraph()
        info_table = self.doc.add_table(rows=6, cols=2)
        info_table.style = "Light Grid Accent 1"

        # Populate info table
        rows = [
            ("Document Code:", metadata.get("code", "N/A")),
            ("Version:", metadata.get("version", "1.0")),
            ("Effective Date:", metadata.get("effective_date", "")),
            ("Department:", metadata.get("department", "")),
            ("Document Owner:", metadata.get("owner", "")),
            ("Last Updated:", datetime.now().strftime("%Y-%m-%d")),
        ]

        for i, (label, value) in enumerate(rows):
            info_table.rows[i].cells[0].text = label
            info_table.rows[i].cells[0]._element.get_or_add_tcPr().append(
                OxmlElement("w:shd")
            )
            info_table.rows[i].cells[1].text = value

        # Approval Section
        self.doc.add_paragraph()
        self.doc.add_heading("Approvals", level=2)

        approval_table = self.doc.add_table(rows=1 + len(metadata.get("approvals", [])), cols=4)
        approval_table.style = "Light Grid Accent 1"

        # Header row
        header_cells = approval_table.rows[0].cells
        header_cells[0].text = "Role"
        header_cells[1].text = "Name"
        header_cells[2].text = "Signature"
        header_cells[3].text = "Date"

        # Approval rows
        for i, approval in enumerate(metadata.get("approvals", []), 1):
            row = approval_table.rows[i]
            row.cells[0].text = approval.get("role", "")
            row.cells[1].text = approval.get("name", "")
            row.cells[2].text = "_" * 20  # Signature line
            row.cells[3].text = "_" * 10  # Date line

        # Revision History
        self.doc.add_paragraph()
        self.doc.add_heading("Document Revision History", level=2)

        revisions = metadata.get("revisions", [])
        if revisions:
            rev_table = self.doc.add_table(rows=1 + len(revisions), cols=4)
            rev_table.style = "Light Grid Accent 1"

            # Header
            header = rev_table.rows[0].cells
            header[0].text = "Version"
            header[1].text = "Date"
            header[2].text = "Changes"
            header[3].text = "Author"

            # Revisions
            for i, rev in enumerate(revisions, 1):
                row = rev_table.rows[i]
                row.cells[0].text = rev.get("version", "")
                row.cells[1].text = rev.get("date", "")
                row.cells[2].text = rev.get("changes", "")
                row.cells[3].text = rev.get("author", "")

        self.doc.add_page_break()

    def add_table_of_contents(self) -> None:
        """Add table of contents (will be auto-generated in Word)"""
        self.doc.add_heading("Table of Contents", 1)

        # Field code for TOC
        paragraph = self.doc.add_paragraph()
        run = paragraph.add_run()

        fldChar1 = OxmlElement("w:fldChar")
        fldChar1.set(qn("w:fldCharType"), "begin")

        instrText = OxmlElement("w:instrText")
        instrText.set(qn("xml:space"), "preserve")
        instrText.text = "TOC \\o \"1-2\" \\h \\z \\u"

        fldChar2 = OxmlElement("w:fldChar")
        fldChar2.set(qn("w:fldCharType"), "end")

        run._r.append(fldChar1)
        run._r.append(instrText)
        run._r.append(fldChar2)

        self.doc.add_page_break()

    def add_section_heading(self, number: int, title: str) -> None:
        """Add a numbered section heading"""
        self.doc.add_heading(f"{number}. {title}", level=1)

    def add_section_content(self, content: str) -> None:
        """Add paragraph content to document"""
        if content:
            self.doc.add_paragraph(content)

    def add_raci_matrix(
        self,
        raci_data: Dict[str, Any],
        include_descriptions: bool = True,
    ) -> None:
        """
        Add RACI matrix with role duty explanations.

        Args:
            raci_data: Dictionary containing:
                - roles: Dict of role -> description
                - activities: List of activities
                - matrix: Dict of (activity, role) -> assignment (R/A/C/I)
            include_descriptions: Whether to include duty descriptions
        """

        self.doc.add_heading("6. Roles and Responsibilities", level=1)

        # RACI Matrix Table
        roles = list(raci_data.get("roles", {}).keys())
        activities = list(raci_data.get("activities", {}).keys())

        matrix_table = self.doc.add_table(rows=len(activities) + 1, cols=len(roles) + 1)
        matrix_table.style = "Light Grid Accent 1"

        # Header row
        matrix_table.rows[0].cells[0].text = "Activity"
        for j, role in enumerate(roles):
            matrix_table.rows[0].cells[j + 1].text = role

        # Data rows
        matrix = raci_data.get("matrix", {})
        for i, activity in enumerate(activities):
            matrix_table.rows[i + 1].cells[0].text = activity
            for j, role in enumerate(roles):
                assignment = matrix.get((activity, role), "-")
                matrix_table.rows[i + 1].cells[j + 1].text = assignment

        # Add role descriptions if requested
        if include_descriptions:
            self.doc.add_paragraph()
            self.doc.add_heading("Role Descriptions", level=2)

            for role, description in raci_data.get("roles", {}).items():
                self.doc.add_heading(role, level=3)
                self.doc.add_paragraph(description)

    def add_diagram(
        self,
        diagram_path: str,
        caption: str,
        width: Optional[float] = None,
    ) -> None:
        """
        Embed diagram image in document.

        Args:
            diagram_path: Path to diagram file (PNG/SVG converted to PNG)
            caption: Diagram caption
            width: Optional width in inches
        """
        try:
            if Path(diagram_path).exists():
                width = width or 6.0
                self.doc.add_picture(diagram_path, width=Inches(width))

                # Add caption
                caption_para = self.doc.add_paragraph()
                caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = caption_para.add_run(f"Figure: {caption}")
                run.italic = True
                run.font.size = Pt(10)

                self.image_counter += 1
        except Exception as e:
            logger.error(f"Failed to add diagram: {e}")

    def add_procedure_steps(
        self, steps: List[Dict[str, Any]]
    ) -> None:
        """
        Add procedure steps as a numbered list.

        Args:
            steps: List of step dictionaries with title, description, etc.
        """
        for i, step in enumerate(steps, 1):
            self.doc.add_paragraph(
                f"{i}. {step.get('title', '')}",
                style="List Number",
            )

            if step.get("description"):
                self.doc.add_paragraph(
                    step["description"],
                    style="List Paragraph",
                )

            # Add warnings or notes if present
            if step.get("warning"):
                warning_para = self.doc.add_paragraph(
                    f"WARNING: {step['warning']}"
                )
                warning_para.paragraph_format.left_indent = Inches(0.5)
                warning_para.runs[0].font.color.rgb = RGBColor(192, 0, 0)  # Red
                warning_para.runs[0].bold = True

    def add_approval_signature_block(self, approvers: List[Dict[str, str]]) -> None:
        """
        Add final approval signature block.

        Args:
            approvers: List of approver dictionaries with name and role
        """
        self.doc.add_page_break()
        self.doc.add_heading("Document Approval", level=1)

        sig_table = self.doc.add_table(rows=len(approvers), cols=3)
        sig_table.style = "Table Grid"

        for i, approver in enumerate(approvers):
            row = sig_table.rows[i]
            row.cells[0].text = approver.get("role", "")
            row.cells[1].text = "_" * 30  # Signature line
            row.cells[2].text = "_" * 15  # Date line

    def save(self, output_path: str) -> bool:
        """
        Save document to file.

        Args:
            output_path: Path to save DOCX file

        Returns:
            Whether save was successful
        """
        try:
            self.doc.save(output_path)
            logger.info(f"✓ DOCX saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save DOCX: {e}")
            return False

    def get_document_stats(self) -> Dict[str, Any]:
        """Get statistics about the generated document"""
        # Count paragraphs and tables
        num_paragraphs = len(self.doc.paragraphs)
        num_tables = len(self.doc.tables)
        num_images = len(self.doc.inline_shapes)

        # Estimate page count (rough: ~450 words per page)
        word_count = sum(len(p.text.split()) for p in self.doc.paragraphs)
        estimated_pages = max(1, word_count // 450)

        return {
            "word_count": word_count,
            "paragraphs": num_paragraphs,
            "tables": num_tables,
            "images": num_images,
            "estimated_pages": estimated_pages,
        }


def create_purely_plant_docx(
    metadata: Dict[str, Any],
    sections: Dict[str, str],
    output_path: str,
    diagrams: Optional[Dict[str, str]] = None,
    raci_data: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Create a complete Purely Plant format DOCX document.

    Args:
        metadata: SOP metadata (title, code, version, etc.)
        sections: Dictionary of section_name -> content
        output_path: Where to save the DOCX file
        diagrams: Optional dictionary of diagram_name -> diagram_path
        raci_data: Optional RACI matrix data

    Returns:
        Tuple of (success, message)
    """
    try:
        engine = PurelyPlantDocxEngine()

        # Add cover page
        engine.add_cover_page(metadata)

        # Add table of contents
        engine.add_table_of_contents()

        # Add sections in order
        section_order = [
            ("purpose", "Purpose"),
            ("scope", "Scope"),
            ("definitions", "Definitions and Abbreviations"),
            ("regulatory", "Regulatory Requirements"),
        ]

        section_num = 1
        for section_key, section_title in section_order:
            if section_key in sections:
                engine.add_section_heading(section_num, section_title)
                engine.add_section_content(sections[section_key])
                section_num += 1

        # Add RACI if provided
        if raci_data:
            engine.add_raci_matrix(raci_data)
            section_num += 1

        # Add procedure
        if "procedure" in sections:
            engine.add_section_heading(section_num, "Procedure")
            engine.add_section_content(sections["procedure"])
            section_num += 1

        # Add diagrams
        if diagrams:
            for diagram_name, diagram_path in diagrams.items():
                engine.add_diagram(diagram_path, diagram_name)

        # Save document
        success = engine.save(output_path)

        if success:
            stats = engine.get_document_stats()
            message = f"✓ DOCX created: {output_path} ({stats['estimated_pages']} pages, {stats['word_count']} words)"
        else:
            message = "✗ Failed to save DOCX"

        return success, message

    except Exception as e:
        return False, f"✗ Error creating DOCX: {e}"
