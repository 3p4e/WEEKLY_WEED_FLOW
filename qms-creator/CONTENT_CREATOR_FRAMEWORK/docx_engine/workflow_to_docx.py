"""
DOCX Generation from Letta Workflow Output

Converts section dict output from Letta agents into professional Purely Plant
DOCX documents with cover pages, TOC, formatted sections, RACI matrices, and styling.

Implements Document Creator Agent Skills Specification v1.0:
- Purely Plant color palette (PP_BLUE, PP_GREEN, PP_GRAY)
- Arial Narrow typography throughout
- Professional table styling with proper shading
- RACI matrix with color-coded cells
- Markdown content parsing
"""

from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
import re

from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from dateutil.relativedelta import relativedelta


# ============================================================================
# THEME CONFIGURATION SYSTEM
# ============================================================================
# To create a new visual schema, define a theme dict and set ACTIVE_THEME

THEMES = {
    # -------------------------------------------------------------------------
    # PP SOP THEME (Default) - Aligned with frontend qms-ui-v2 PP SOP Theme
    # Pharmaceutical-grade design system for EU GMP compliance
    # -------------------------------------------------------------------------
    "purely_plant": {
        "name": "PP SOP Theme",
        "description": "Pharmaceutical-grade design system aligned with frontend UI",

        # Primary colors (RGBColor objects) - from PP_SOP_Palette.json
        "primary": (0x1F, 0x4E, 0x79),      # #1F4E79 - Primary Blue
        "secondary": (0x53, 0x81, 0x35),    # #538135 - Secondary Green
        "text": (0x40, 0x40, 0x40),         # #404040 - Text Gray
        "accent": (0x53, 0x81, 0x35),       # Same as secondary in PP SOP

        # Status colors - aligned with frontend Design_Tokens.json
        "success": (0x16, 0xA3, 0x4A),      # #16A34A - Success Green
        "warning": (0xEA, 0x8C, 0x55),      # #EA8C55 - Warning Orange
        "error": (0xDC, 0x26, 0x26),        # #DC2626 - Error Red
        "info": (0x0E, 0xA5, 0xE9),         # #0EA5E9 - Info Cyan

        # Background colors (hex strings for XML shading)
        "bg_header": "D6E3F0",              # Light blue - table headers
        "bg_highlight": "E2F0D9",           # Light green - highlights
        "bg_alternate": "F5F7FA",           # #F5F7FA - Light Bg from tokens
        "bg_white": "FFFFFF",               # White - standard background
        "bg_border": "E2E8F0",              # #E2E8F0 - Border color

        # RACI matrix colors - derived from status colors
        "raci_r": "E2F0D9",                 # Responsible - light green
        "raci_a": "D6E3F0",                 # Accountable - light blue
        "raci_c": "FFF2CC",                 # Consulted - light yellow
        "raci_i": "F5F7FA",                 # Informed - light gray (aligned)

        # Typography - from Design_Tokens.json pp-sop theme
        "font_family": "Arial Narrow",
        "font_fallback": "Arial",

        # Font sizes (in points) - derived from px tokens (px * 0.75 = pt approx)
        "size_title": 16,                   # ~21px (2xl at 28px -> 21pt)
        "size_h1": 14,                      # ~19px (xl at 20px -> 15pt)
        "size_h2": 12,                      # ~16px (lg at 16px -> 12pt)
        "size_h3": 11,                      # ~15px
        "size_body": 10,                    # ~14px (base at 14px -> 10.5pt)
        "size_table_header": 10,
        "size_table_cell": 9,
        "size_footer": 8,                   # ~11px (xs at 11px -> 8pt)

        # Page layout (in cm)
        "margin_top": 2,
        "margin_bottom": 2,
        "margin_left": 2,
        "margin_right": 2,
    },

    # -------------------------------------------------------------------------
    # MODERN CLEAN THEME - Aligned with frontend qms-ui-v2 Modern Clean Theme
    # Contemporary minimal design system
    # -------------------------------------------------------------------------
    "modern_clean": {
        "name": "Modern Clean Theme",
        "description": "Contemporary minimal design aligned with frontend UI",

        # Primary colors - from Modern_Palette.json
        "primary": (0x25, 0x63, 0xEB),      # #2563EB - Modern Blue
        "secondary": (0x7C, 0x3A, 0xED),    # #7C3AED - Purple Accent
        "text": (0x1F, 0x29, 0x37),         # #1F2937 - Dark Text Gray
        "accent": (0x7C, 0x3A, 0xED),       # Same as secondary in Modern

        # Status colors - aligned with frontend Modern_Palette.json
        "success": (0x10, 0xB9, 0x81),      # #10B981 - Emerald Green
        "warning": (0xF5, 0x9E, 0x0B),      # #F59E0B - Amber
        "error": (0xEF, 0x44, 0x44),        # #EF4444 - Bright Red
        "info": (0x06, 0xB6, 0xD4),         # #06B6D4 - Cyan

        # Background colors (hex strings for XML shading)
        "bg_header": "EBF4FF",              # Very light blue tint
        "bg_highlight": "F3E8FF",           # Light purple tint
        "bg_alternate": "F3F4F6",           # #F3F4F6 - Light Bg from tokens
        "bg_white": "FFFFFF",               # White background
        "bg_border": "D1D5DB",              # #D1D5DB - Border color

        # RACI matrix colors - modern palette variants
        "raci_r": "D1FAE5",                 # Emerald tint for Responsible
        "raci_a": "DBEAFE",                 # Blue tint for Accountable
        "raci_c": "FEF3C7",                 # Amber tint for Consulted
        "raci_i": "F3F4F6",                 # Gray for Informed

        # Typography - from Design_Tokens.json modern theme
        "font_family": "Segoe UI",
        "font_fallback": "Helvetica Neue",

        # Font sizes (slightly larger for modern feel)
        "size_title": 20,                   # ~40px (4xl)
        "size_h1": 16,                      # ~32px (3xl)
        "size_h2": 13,                      # ~22px (xl at 22px)
        "size_h3": 11,                      # ~17px (lg)
        "size_body": 11,                    # ~15px (base at 15px)
        "size_table_header": 10,
        "size_table_cell": 9,
        "size_footer": 9,                   # ~13px (sm at 13px)

        # Page layout (in cm) - slightly tighter for modern look
        "margin_top": 1.8,
        "margin_bottom": 1.8,
        "margin_left": 2,
        "margin_right": 2,
    },

    # Alias for backward compatibility
    "modern_minimal": None,  # Will be set to modern_clean below

    # -------------------------------------------------------------------------
    # CORPORATE BLUE - Traditional corporate/legal style
    # -------------------------------------------------------------------------
    "corporate_blue": {
        "name": "Corporate Blue",
        "description": "Traditional corporate style with navy blue emphasis",

        "primary": (0x00, 0x32, 0x66),      # Navy blue
        "secondary": (0x00, 0x5A, 0x9C),    # Medium blue
        "text": (0x33, 0x33, 0x33),         # Charcoal
        "accent": (0xCC, 0x00, 0x00),       # Red accent

        # Status colors
        "success": (0x22, 0x8B, 0x22),      # Forest green
        "warning": (0xFF, 0xA5, 0x00),      # Orange
        "error": (0xCC, 0x00, 0x00),        # Red
        "info": (0x00, 0x5A, 0x9C),         # Medium blue

        "bg_header": "003366",              # Navy header
        "bg_highlight": "E6F0FF",           # Very light blue
        "bg_alternate": "F5F5F5",           # Light gray
        "bg_white": "FFFFFF",
        "bg_border": "CCCCCC",

        "raci_r": "C6EFCE",                 # Light green
        "raci_a": "BDD7EE",                 # Light blue
        "raci_c": "FFE699",                 # Light yellow
        "raci_i": "EDEDED",                 # Light gray

        "font_family": "Calibri",
        "font_fallback": "Arial",

        "size_title": 18,
        "size_h1": 14,
        "size_h2": 12,
        "size_h3": 11,
        "size_body": 11,
        "size_table_header": 10,
        "size_table_cell": 10,
        "size_footer": 9,

        "margin_top": 2.5,
        "margin_bottom": 2.5,
        "margin_left": 2.5,
        "margin_right": 2.5,
    },

    # -------------------------------------------------------------------------
    # PHARMA GMP - Strict pharmaceutical compliance style
    # -------------------------------------------------------------------------
    "pharma_gmp": {
        "name": "Pharma GMP",
        "description": "Strict pharmaceutical/GMP compliance documentation style",

        "primary": (0x00, 0x00, 0x80),      # Navy
        "secondary": (0x00, 0x64, 0x00),    # Dark green
        "text": (0x00, 0x00, 0x00),         # Pure black
        "accent": (0x8B, 0x00, 0x00),       # Dark red

        # Status colors
        "success": (0x00, 0x64, 0x00),      # Dark green
        "warning": (0xFF, 0x8C, 0x00),      # Dark orange
        "error": (0x8B, 0x00, 0x00),        # Dark red
        "info": (0x00, 0x00, 0x80),         # Navy

        "bg_header": "C0C0C0",              # Silver gray
        "bg_highlight": "E0FFE0",           # Pale green
        "bg_alternate": "F0F0F0",           # Light gray
        "bg_white": "FFFFFF",
        "bg_border": "808080",

        "raci_r": "90EE90",                 # Light green
        "raci_a": "ADD8E6",                 # Light blue
        "raci_c": "FFFFE0",                 # Light yellow
        "raci_i": "D3D3D3",                 # Light gray

        "font_family": "Times New Roman",
        "font_fallback": "Times",

        "size_title": 14,
        "size_h1": 12,
        "size_h2": 11,
        "size_h3": 10,
        "size_body": 10,
        "size_table_header": 10,
        "size_table_cell": 9,
        "size_footer": 8,

        "margin_top": 2.5,
        "margin_bottom": 2.5,
        "margin_left": 3,
        "margin_right": 2.5,
    },
}

# Set modern_minimal as alias for modern_clean (backward compatibility)
THEMES["modern_minimal"] = THEMES["modern_clean"]

# ============================================================================
# ACTIVE THEME SELECTION
# ============================================================================
# Available themes (aligned with qms-ui-v2 frontend):
#   - "purely_plant"  : PP SOP Theme (pharmaceutical-grade, EU GMP) [DEFAULT]
#   - "modern_clean"  : Modern Clean Theme (contemporary, minimal)
#   - "corporate_blue": Traditional corporate style
#   - "pharma_gmp"    : Strict pharmaceutical compliance style
#   - "modern_minimal": Alias for modern_clean (backward compatibility)
ACTIVE_THEME = "purely_plant"

# ============================================================================
# THEME HELPER FUNCTIONS
# ============================================================================

def get_theme():
    """Get the currently active theme configuration."""
    return THEMES.get(ACTIVE_THEME, THEMES["purely_plant"])


def get_color(color_key: str) -> RGBColor:
    """Get an RGBColor from the active theme."""
    theme = get_theme()
    rgb = theme.get(color_key, (0x40, 0x40, 0x40))
    return RGBColor(rgb[0], rgb[1], rgb[2])


def get_hex(color_key: str) -> str:
    """Get a hex color string from the active theme."""
    theme = get_theme()
    return theme.get(color_key, "FFFFFF")


def get_size(size_key: str) -> int:
    """Get a font size from the active theme."""
    theme = get_theme()
    return theme.get(size_key, 10)


def get_font() -> str:
    """Get the primary font family from the active theme."""
    return get_theme().get("font_family", "Arial")


def get_margin(margin_key: str) -> float:
    """Get a margin value (in cm) from the active theme."""
    return get_theme().get(margin_key, 2)


def get_status_color(status: str) -> RGBColor:
    """
    Get a status color (success, warning, error, info) from the active theme.

    Args:
        status: One of "success", "warning", "error", "info"

    Returns:
        RGBColor for the status
    """
    theme = get_theme()
    rgb = theme.get(status, theme.get("text", (0x40, 0x40, 0x40)))
    return RGBColor(rgb[0], rgb[1], rgb[2])


def get_status_bg_hex(status: str) -> str:
    """
    Get a light background hex color for a status indicator.

    Args:
        status: One of "success", "warning", "error", "info"

    Returns:
        Hex color string suitable for cell shading (light tint of status color)
    """
    # Map status to RACI-like backgrounds (which are already light tints)
    status_bg_map = {
        "success": "raci_r",  # Light green
        "warning": "raci_c",  # Light yellow
        "error": "raci_c",    # Light yellow (for visibility)
        "info": "raci_a",     # Light blue
    }
    bg_key = status_bg_map.get(status, "bg_alternate")
    return get_hex(bg_key)


# ============================================================================
# BACKWARD COMPATIBILITY - Legacy color constants
# ============================================================================
# These are computed from the active theme for backward compatibility
# Note: Colors are computed at import time; switching themes requires reload

# Primary colors (RGBColor objects)
PP_BLUE = get_color("primary")
PP_GREEN = get_color("secondary")
PP_GRAY = get_color("text")

# Status colors (RGBColor objects) - aligned with frontend
PP_SUCCESS = get_status_color("success")
PP_WARNING = get_status_color("warning")
PP_ERROR = get_status_color("error")
PP_INFO = get_status_color("info")

# Background colors (hex strings for XML shading)
PP_LIGHT_BLUE_HEX = get_hex("bg_header")
PP_LIGHT_GREEN_HEX = get_hex("bg_highlight")
PP_LIGHT_GRAY_HEX = get_hex("bg_alternate")
PP_WHITE_HEX = get_hex("bg_white")
PP_BORDER_HEX = get_hex("bg_border") if "bg_border" in get_theme() else "E2E8F0"

# RACI matrix colors (hex strings)
RACI_COLORS = {
    'R': get_hex("raci_r"),
    'A': get_hex("raci_a"),
    'C': get_hex("raci_c"),
    'I': get_hex("raci_i"),
}

# Status background colors (hex strings for cell shading)
STATUS_BG_COLORS = {
    'success': get_hex("raci_r"),   # Light green tint
    'warning': get_hex("raci_c"),   # Light yellow tint
    'error': get_hex("raci_c"),     # Light yellow (visibility on print)
    'info': get_hex("raci_a"),      # Light blue tint
}

# Typography
FONT_FAMILY = get_font()
FONT_FAMILY_FALLBACK = get_theme().get("font_fallback", "Arial")


# Section display order and titles
SECTION_DISPLAY = [
    ("3. Purpose", "purpose"),
    ("4. Scope", "scope"),
    ("5. Definitions and Abbreviations", "definitions"),
    ("6. Roles and Responsibilities", "raci"),
    ("7. Regulatory Requirements", "regulatory"),
    ("8. Procedure", "procedure"),
    ("9. Documentation", "documentation"),
    ("10. Training Requirements", "training"),
]


# ============================================================================
# HELPER FUNCTIONS - Styled Element Creation
# ============================================================================

def _apply_cell_shading(cell, fill_color: str):
    """
    Apply background shading to a table cell using XML.
    CRITICAL: Always use 'clear' value, NEVER 'solid' (causes black backgrounds).
    """
    shading = OxmlElement('w:shd')
    shading.set(qn('w:val'), 'clear')
    shading.set(qn('w:color'), 'auto')
    shading.set(qn('w:fill'), fill_color)
    cell._tc.get_or_add_tcPr().append(shading)


def _set_font(run, font_name: str = FONT_FAMILY, size_pt: int = 10,
              color: RGBColor = PP_GRAY, bold: bool = False, italic: bool = False):
    """Apply consistent font styling to a run."""
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.color.rgb = color
    run.bold = bold
    run.italic = italic
    # Set east asian font as well for consistency
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)


def create_header_cell(cell, text: str):
    """
    Style a table cell as a header cell.
    PP_LIGHT_BLUE background, PP_BLUE text, Bold.
    """
    cell.text = ""
    para = cell.paragraphs[0]
    run = para.add_run(text)
    _set_font(run, size_pt=10, color=PP_BLUE, bold=True)
    _apply_cell_shading(cell, PP_LIGHT_BLUE_HEX)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return cell


def create_data_cell(cell, text: str, alternate_row: bool = False):
    """
    Style a table cell as a data cell.
    PP_GRAY text, optional alternating background.
    """
    cell.text = ""
    para = cell.paragraphs[0]
    run = para.add_run(str(text))
    _set_font(run, size_pt=9, color=PP_GRAY)

    if alternate_row:
        _apply_cell_shading(cell, PP_LIGHT_GRAY_HEX)
    return cell


def create_raci_cell(cell, value: str):
    """
    Style a RACI matrix cell with appropriate color coding.
    R=Green, A=Blue, C=Yellow, I=Gray
    """
    cell.text = ""
    para = cell.paragraphs[0]
    run = para.add_run(value.strip().upper() if value else "")
    _set_font(run, size_pt=10, color=PP_GRAY, bold=True)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Apply RACI-specific color
    value_upper = value.strip().upper() if value else ""
    if value_upper in RACI_COLORS:
        _apply_cell_shading(cell, RACI_COLORS[value_upper])
    return cell


class DocxAssembler:
    """
    Converts section dicts to professional Purely Plant DOCX documents.

    Features:
    - Professional cover page with logo and metadata
    - Approval/signature section with revision history
    - Auto-generated Table of Contents
    - Formatted sections with proper heading hierarchy
    - RACI matrices with role explanations
    - Professional styling (fonts, colors, spacing)
    """

    def __init__(self, template_path: Optional[str] = None):
        self.doc = Document(template_path) if template_path else Document()
        self.setup_styles()
        self.section = self.doc.sections[0]
        self.setup_page_margins()
        self.sop_code = ""  # Will be set during cover page generation

    def setup_page_margins(self):
        """Configure page margins from active theme."""
        self.section.top_margin = Cm(get_margin("margin_top"))
        self.section.bottom_margin = Cm(get_margin("margin_bottom"))
        self.section.left_margin = Cm(get_margin("margin_left"))
        self.section.right_margin = Cm(get_margin("margin_right"))

    def setup_header_footer(self, sop_code: str):
        """
        Configure header and footer with Purely Plant styling.

        Header: left = SOP code (PP_GRAY), right = CONFIDENTIAL (PP_BLUE bold)
        Footer: center = Page X of Y, right = generation date
        """
        # Header
        header = self.section.header
        header_para = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        header_para.text = ""

        # Left-aligned SOP code
        left_run = header_para.add_run(sop_code)
        _set_font(left_run, size_pt=8, color=PP_GRAY)

        # Tab to right side for CONFIDENTIAL
        header_para.add_run("\t\t")
        right_run = header_para.add_run("CONFIDENTIAL")
        _set_font(right_run, size_pt=8, color=PP_BLUE, bold=True)

        # Footer
        footer = self.section.footer
        footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Page number: "Page X"
        page_run = footer_para.add_run("Page ")
        _set_font(page_run, size_pt=8, color=PP_GRAY)

        # PAGE field
        fldChar1 = OxmlElement("w:fldChar")
        fldChar1.set(qn("w:fldCharType"), "begin")
        instrText = OxmlElement("w:instrText")
        instrText.set(qn("xml:space"), "preserve")
        instrText.text = "PAGE"
        fldChar2 = OxmlElement("w:fldChar")
        fldChar2.set(qn("w:fldCharType"), "end")

        page_num_run = footer_para.add_run()
        page_num_run._r.append(fldChar1)
        page_num_run._r.append(instrText)
        page_num_run._r.append(fldChar2)
        _set_font(page_num_run, size_pt=8, color=PP_GRAY)

        # " of "
        of_run = footer_para.add_run(" of ")
        _set_font(of_run, size_pt=8, color=PP_GRAY)

        # NUMPAGES field
        fldChar3 = OxmlElement("w:fldChar")
        fldChar3.set(qn("w:fldCharType"), "begin")
        instrText2 = OxmlElement("w:instrText")
        instrText2.set(qn("xml:space"), "preserve")
        instrText2.text = "NUMPAGES"
        fldChar4 = OxmlElement("w:fldChar")
        fldChar4.set(qn("w:fldCharType"), "end")

        total_run = footer_para.add_run()
        total_run._r.append(fldChar3)
        total_run._r.append(instrText2)
        total_run._r.append(fldChar4)
        _set_font(total_run, size_pt=8, color=PP_GRAY)

        # Generation date (right-aligned via tab)
        footer_para.add_run("\t\t")
        date_run = footer_para.add_run(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
        _set_font(date_run, size_pt=8, color=PP_GRAY)

    def setup_styles(self):
        """
        Configure document styles from active theme.

        Typography hierarchy uses theme-defined sizes and colors.
        """
        style_configs = [
            ("Title", get_size("size_title"), True, get_color("primary")),
            ("Heading 1", get_size("size_h1"), True, get_color("primary")),
            ("Heading 2", get_size("size_h2"), True, get_color("secondary")),
            ("Heading 3", get_size("size_h3"), True, get_color("text")),
            ("Normal", get_size("size_body"), False, get_color("text")),
            ("List Bullet", get_size("size_body"), False, get_color("text")),
            ("List Number", get_size("size_body"), False, get_color("text")),
        ]

        for style_name, font_size, bold, color in style_configs:
            try:
                style = self.doc.styles[style_name]
                style.font.name = get_font()
                style.font.size = Pt(font_size)
                style.font.bold = bold
                style.font.color.rgb = color
                # Set paragraph spacing
                if hasattr(style, 'paragraph_format'):
                    style.paragraph_format.space_after = Pt(6)
                    style.paragraph_format.line_spacing = 1.15
            except Exception:
                # Style may not exist, skip
                pass

    def add_cover_page(
        self,
        sop_name: str,
        sop_code: str,
        department: str = "Quality",
        document_type: str = "SOP",
        version: str = "1.0",
    ):
        """
        Add enhanced professional cover page with Purely Plant styling.

        Includes:
        - Logo placeholder area
        - Document type and title
        - Metadata table with PP_LIGHT_BLUE headers
        - Approval signatures table
        """
        self.sop_code = sop_code  # Store for header/footer

        # Logo placeholder area (centered)
        logo_para = self.doc.add_paragraph()
        logo_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        logo_para.paragraph_format.space_after = Pt(24)
        logo_run = logo_para.add_run("[COMPANY LOGO]")
        _set_font(logo_run, size_pt=12, color=RGBColor(0x80, 0x80, 0x80))

        # Document Type header
        type_para = self.doc.add_paragraph()
        type_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        type_run = type_para.add_run("STANDARD OPERATING PROCEDURE")
        _set_font(type_run, size_pt=16, color=PP_BLUE, bold=True)
        type_para.paragraph_format.space_after = Pt(6)

        # Document Title
        title_para = self.doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run(sop_name)
        _set_font(title_run, size_pt=14, color=PP_GREEN, bold=True)
        title_para.paragraph_format.space_after = Pt(24)

        # Document metadata table with styled headers
        effective_date = datetime.now()
        review_date = effective_date + relativedelta(years=2)

        meta_rows = [
            ("Document Code", sop_code),
            ("Document Type", document_type),
            ("Department", department),
            ("Facility Type", "Cannabis EU GMP"),
            ("Version", version),
            ("Effective Date", effective_date.strftime("%Y-%m-%d")),
            ("Review Date", review_date.strftime("%Y-%m-%d")),
            ("Confidentiality", "CONFIDENTIAL - Internal Use Only"),
            ("Classification", "GMP Controlled Document"),
        ]

        info_table = self.doc.add_table(rows=len(meta_rows), cols=2)
        info_table.style = "Table Grid"
        info_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for i, (label, value) in enumerate(meta_rows):
            # Label cell (styled as header)
            create_header_cell(info_table.rows[i].cells[0], label)
            # Value cell (styled as data)
            create_data_cell(info_table.rows[i].cells[1], value)

        self.doc.add_paragraph()

        # Approval section heading
        approval_heading = self.doc.add_paragraph()
        approval_run = approval_heading.add_run("Approvals")
        _set_font(approval_run, size_pt=12, color=PP_GREEN, bold=True)
        approval_heading.paragraph_format.space_before = Pt(12)
        approval_heading.paragraph_format.space_after = Pt(6)

        # Approval table with proper styling
        approval_table = self.doc.add_table(rows=4, cols=4)
        approval_table.style = "Table Grid"
        approval_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Header row
        headers = ["Role", "Name", "Signature", "Date"]
        for i, header in enumerate(headers):
            create_header_cell(approval_table.rows[0].cells[i], header)

        # Data rows
        roles = ["Quality Assurance Manager", "Production Manager", "Compliance Officer"]
        for i, role in enumerate(roles, 1):
            create_data_cell(approval_table.rows[i].cells[0], role)
            create_data_cell(approval_table.rows[i].cells[1], "[Name]")
            create_data_cell(approval_table.rows[i].cells[2], "")
            create_data_cell(approval_table.rows[i].cells[3], "____/____/______")

        self.doc.add_paragraph()
        self.doc.add_page_break()

    def add_revision_history(self, version: str = "1.0"):
        """Add Revision History section with Purely Plant styling."""
        # Section heading
        heading = self.doc.add_paragraph()
        heading_run = heading.add_run("Revision History")
        _set_font(heading_run, size_pt=12, color=PP_GREEN, bold=True)
        heading.paragraph_format.space_before = Pt(12)
        heading.paragraph_format.space_after = Pt(6)

        history_table = self.doc.add_table(rows=2, cols=4)
        history_table.style = "Table Grid"
        history_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Header row
        headers = ["Version", "Date", "Changes", "Approved By"]
        for i, header in enumerate(headers):
            create_header_cell(history_table.rows[0].cells[i], header)

        # Data row
        data = [version, datetime.now().strftime("%Y-%m-%d"), "Initial document creation", "QA Team"]
        for i, value in enumerate(data):
            create_data_cell(history_table.rows[1].cells[i], value)

        self.doc.add_paragraph()

    def add_table_of_contents(self):
        """Add auto-generating Table of Contents."""
        self.doc.add_heading("Table of Contents", 1)

        paragraph = self.doc.add_paragraph()
        run = paragraph.add_run()

        fldChar = OxmlElement("w:fldChar")
        fldChar.set(qn("w:fldCharType"), "begin")
        instrText = OxmlElement("w:instrText")
        instrText.set(qn("xml:space"), "preserve")
        instrText.text = 'TOC \\o "1-3" \\h \\z \\u'
        fldChar2 = OxmlElement("w:fldChar")
        fldChar2.set(qn("w:fldCharType"), "end")

        run._r.append(fldChar)
        run._r.append(instrText)
        run._r.append(fldChar2)

        self.doc.add_page_break()

    def add_section(self, title: str, content: str, level: int = 1):
        """
        Add a section with formatted content and markdown parsing.

        Supports:
        - ## Subsection headings
        - ### Sub-subsection headings
        - Bullet lists (- item)
        - Numbered lists (1. item)
        - Pipe-delimited tables
        - Regular paragraphs
        """
        self.doc.add_heading(title, level)
        self._parse_markdown_content(content)

    def _parse_markdown_content(self, content: str):
        """Parse markdown content and add to document with proper styling."""
        lines = content.split("\n")
        i = 0
        current_paragraph_lines = []

        def flush_paragraph():
            """Flush accumulated paragraph lines."""
            nonlocal current_paragraph_lines
            if current_paragraph_lines:
                text = " ".join(current_paragraph_lines).strip()
                if text:
                    para = self.doc.add_paragraph()
                    run = para.add_run(text)
                    _set_font(run, size_pt=10, color=PP_GRAY)
                    para.paragraph_format.line_spacing = 1.15
                    para.paragraph_format.space_after = Pt(6)
                    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                current_paragraph_lines = []

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Skip empty lines (flush paragraph)
            if not stripped:
                flush_paragraph()
                i += 1
                continue

            # Heading 2 (##)
            if stripped.startswith("## "):
                flush_paragraph()
                heading_text = stripped[3:].strip()
                h2 = self.doc.add_heading(heading_text, 2)
                for run in h2.runs:
                    _set_font(run, size_pt=12, color=PP_GREEN, bold=True)
                i += 1
                continue

            # Heading 3 (###)
            if stripped.startswith("### "):
                flush_paragraph()
                heading_text = stripped[4:].strip()
                h3 = self.doc.add_heading(heading_text, 3)
                for run in h3.runs:
                    _set_font(run, size_pt=11, color=PP_GRAY, bold=True)
                i += 1
                continue

            # Bullet list
            if stripped.startswith("- ") or stripped.startswith("* "):
                flush_paragraph()
                bullet_items = []
                while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                    bullet_items.append(lines[i].strip()[2:])
                    i += 1
                for item in bullet_items:
                    para = self.doc.add_paragraph(style='List Bullet')
                    run = para.add_run(item)
                    _set_font(run, size_pt=10, color=PP_GRAY)
                continue

            # Numbered list
            if re.match(r'^\d+\.', stripped):
                flush_paragraph()
                num_items = []
                while i < len(lines) and re.match(r'^\d+\.', lines[i].strip()):
                    num_items.append(re.sub(r'^\d+\.\s*', '', lines[i].strip()))
                    i += 1
                for item in num_items:
                    para = self.doc.add_paragraph(style='List Number')
                    run = para.add_run(item)
                    _set_font(run, size_pt=10, color=PP_GRAY)
                continue

            # Pipe-delimited table
            if stripped.startswith("|") and "|" in stripped[1:]:
                flush_paragraph()
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                self._add_markdown_table("\n".join(table_lines))
                continue

            # Regular text - accumulate for paragraph
            current_paragraph_lines.append(stripped)
            i += 1

        # Flush any remaining paragraph
        flush_paragraph()

    def add_raci_matrix(self, raci_content: str):
        """
        Add RACI matrix section with color-coded table.

        RACI Cell Colors:
        - R (Responsible): PP_LIGHT_GREEN
        - A (Accountable): PP_LIGHT_BLUE
        - C (Consulted): Light Yellow
        - I (Informed): PP_LIGHT_GRAY
        """
        self.doc.add_heading("6. Roles and Responsibilities", 1)

        # Add RACI legend
        legend_para = self.doc.add_paragraph()
        legend_run = legend_para.add_run(
            "RACI Legend: R=Responsible, A=Accountable, C=Consulted, I=Informed"
        )
        _set_font(legend_run, size_pt=9, color=PP_GRAY, italic=True)
        legend_para.paragraph_format.space_after = Pt(12)

        lines = raci_content.split("\n")
        matrix_started = False
        table_data = []

        def is_separator_line(line: str) -> bool:
            """Check if line is a markdown table separator (e.g., | --- | --- |)."""
            stripped = line.replace("|", "").replace("-", "").replace(" ", "").replace(":", "")
            return stripped == ""

        def is_table_row(line: str) -> bool:
            """Check if line looks like a table row with pipes."""
            return "|" in line and line.strip().startswith("|")

        for line in lines:
            # Skip separator lines
            if is_separator_line(line):
                continue

            # Check for start of RACI matrix (header line with Activity column)
            if not matrix_started and is_table_row(line) and "Activity" in line:
                matrix_started = True
                # Also capture this header row
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if parts and len(parts) > 1:
                    table_data.append(parts)
            elif matrix_started and line.strip() and is_table_row(line):
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if parts and len(parts) > 1:
                    table_data.append(parts)

        if table_data and len(table_data) > 1:
            cols_count = max(len(row) for row in table_data)
            raci_table = self.doc.add_table(rows=len(table_data), cols=cols_count)
            raci_table.style = "Table Grid"
            raci_table.alignment = WD_TABLE_ALIGNMENT.CENTER

            for row_idx, row_data in enumerate(table_data):
                for col_idx, cell_text in enumerate(row_data):
                    if col_idx < cols_count:
                        cell = raci_table.rows[row_idx].cells[col_idx]

                        if row_idx == 0:
                            # Header row
                            create_header_cell(cell, cell_text)
                        elif col_idx == 0:
                            # Activity name column (first column)
                            create_data_cell(cell, cell_text)
                        else:
                            # RACI value cells - apply color coding
                            create_raci_cell(cell, cell_text)
        else:
            # Fallback: add content as paragraph if no table detected
            para = self.doc.add_paragraph()
            run = para.add_run(raci_content)
            _set_font(run, size_pt=10, color=PP_GRAY)

    def add_all_sections(self, sections: Dict[str, str]):
        """Add all SOP sections from a dict."""
        for section_title, section_key in SECTION_DISPLAY:
            content = sections.get(section_key, "")

            if content:
                if section_key == "raci":
                    self.add_raci_matrix(content)
                else:
                    self.add_section(section_title, content, level=1)
            else:
                self.doc.add_heading(section_title, 1)
                self.doc.add_paragraph("[Section content to be generated]")

            self.doc.add_paragraph()

    def add_generation_summary(self, section_count: int, error_count: int = 0):
        """Add document generation summary with Purely Plant styling."""
        self.doc.add_page_break()
        self.doc.add_heading("Document Quality Summary", 1)

        summary_table = self.doc.add_table(rows=3, cols=2)
        summary_table.style = "Table Grid"
        summary_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        rows = [
            ("Document Generation Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("Sections Generated", str(section_count)),
            ("Generation Status", "Completed" if error_count == 0 else f"{error_count} errors"),
        ]

        for i, (label, value) in enumerate(rows):
            create_header_cell(summary_table.rows[i].cells[0], label)
            create_data_cell(summary_table.rows[i].cells[1], value)

    def add_annex_section(self, label: str, title: str, content: str):
        """
        Add an annex with Purely Plant styling.

        Args:
            label: "Annex A", "Annex B", etc.
            title: Annex title (e.g., "Transport Manifest Form")
            content: Annex content (markdown)
        """
        self.doc.add_page_break()

        # Annex label (centered, PP_BLUE)
        label_para = self.doc.add_paragraph()
        label_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        label_run = label_para.add_run(label.upper())
        _set_font(label_run, size_pt=14, color=PP_BLUE, bold=True)
        label_para.paragraph_format.space_after = Pt(6)

        # Annex title (centered, PP_GREEN)
        title_para = self.doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run(title)
        _set_font(title_run, size_pt=12, color=PP_GREEN, bold=True)
        title_para.paragraph_format.space_after = Pt(18)

        # Parse and add content using markdown parser
        self._parse_markdown_content(content)

    def _add_markdown_table(self, table_text: str):
        """
        Parse and add a markdown table with Purely Plant styling.

        Features:
        - PP_LIGHT_BLUE header row
        - Alternating row colors
        - Proper font styling throughout
        """
        lines = [line.strip() for line in table_text.split("\n") if line.strip()]
        # Filter out separator lines (----)
        table_lines = [line for line in lines if not line.replace("|", "").replace("-", "").replace(" ", "").replace(":", "") == ""]

        if len(table_lines) < 2:
            # Not a valid table, add as paragraph
            para = self.doc.add_paragraph()
            run = para.add_run(table_text)
            _set_font(run, size_pt=10, color=PP_GRAY)
            return

        table_data = []
        for line in table_lines:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if cells:
                table_data.append(cells)

        if table_data:
            cols_count = max(len(row) for row in table_data)
            doc_table = self.doc.add_table(rows=len(table_data), cols=cols_count)
            doc_table.style = "Table Grid"
            doc_table.alignment = WD_TABLE_ALIGNMENT.CENTER

            for row_idx, row_data in enumerate(table_data):
                for col_idx, cell_text in enumerate(row_data):
                    if col_idx < cols_count:
                        cell = doc_table.rows[row_idx].cells[col_idx]
                        if row_idx == 0:
                            # Header row with PP_LIGHT_BLUE background
                            create_header_cell(cell, cell_text)
                        else:
                            # Data row with alternating colors
                            create_data_cell(cell, cell_text, alternate_row=(row_idx % 2 == 0))

            self.doc.add_paragraph()  # Space after table

    def add_draft_watermark(self):
        """
        Add diagonal DRAFT watermark to document.

        Note: Full diagonal watermark requires complex XML. This implementation
        adds a centered "DRAFT" text to the header as a simpler alternative.
        """
        for section in self.doc.sections:
            header = section.header
            # Insert draft para at beginning of header
            draft_para = header.paragraphs[0] if header.paragraphs else header.add_paragraph()

            # Clear and add DRAFT text
            draft_para.clear()
            draft_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            draft_run = draft_para.add_run("D R A F T")
            draft_run.font.size = Pt(36)
            draft_run.font.name = FONT_FAMILY
            draft_run.font.color.rgb = RGBColor(0xDC, 0xDC, 0xDC)  # Light gray
            draft_run.font.bold = True
            draft_para.paragraph_format.space_after = Pt(6)


def generate_docx_from_sections(
    sections: Dict[str, str],
    sop_name: str,
    sop_code: str,
    department: str = "Quality",
    output_path: Optional[str] = None,
    template_path: Optional[str] = None,
) -> str:
    """
    Generate a DOCX document from a dict of section content.

    This is the primary integration point for the Letta workflow.

    Args:
        sections: Dict mapping section keys to content strings.
        sop_name: SOP title.
        sop_code: Document code.
        department: Department name.
        output_path: Path to save DOCX (auto-generated if None).
        template_path: Optional DOCX template.

    Returns:
        Path to generated DOCX file.
    """
    assembler = DocxAssembler(template_path=template_path)

    # Build document
    assembler.add_cover_page(sop_name, sop_code, department)
    assembler.setup_header_footer(sop_code)
    assembler.add_revision_history()
    assembler.add_table_of_contents()
    assembler.add_all_sections(sections)

    valid_sections = sum(1 for v in sections.values() if v and not v.startswith("["))
    assembler.add_generation_summary(valid_sections)

    # Output path
    if not output_path:
        output_dir = Path(__file__).parent.parent.parent / "output" / "generated_sops"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{sop_code}_{sop_name.replace(' ', '_')}_{timestamp}.docx"
        output_path = str(output_dir / filename)

    assembler.doc.save(output_path)
    return output_path


def append_annexes(docx_path: str, annex_sections: Dict[str, str]):
    """
    Append annexes to an existing DOCX file.

    Args:
        docx_path: Path to existing DOCX file
        annex_sections: Dict mapping annex labels ("Annex A", "Annex B") to content
    """
    doc = Document(docx_path)
    assembler = DocxAssembler()
    assembler.doc = doc  # Use existing document

    # Add each annex
    for label, content in annex_sections.items():
        # Extract title from content if present (first line often has title)
        lines = content.split("\n", 1)
        title = lines[0].strip("#").strip() if lines else "Supporting Document"
        annex_content = lines[1] if len(lines) > 1 else content

        assembler.add_annex_section(label, title, annex_content)

    # Save back to same file
    doc.save(docx_path)
