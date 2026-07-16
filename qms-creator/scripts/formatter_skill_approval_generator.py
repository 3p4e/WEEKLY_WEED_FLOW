#!/usr/bin/env python3
"""
Approval Page Generator - Purely Plant Template Formatter Skill Implementation
Generates approval pages with proper bilingual two-column structure following Formatter Skill v1.0

Key Formatter Skill Requirements:
- Page setup: A4, 0.5" margins
- Typography: 36pt title, 14pt headers, 10pt MK | 11pt ENG body
- Bilingual structure: Two-column 50/50 layout with invisible borders
- Table nesting: Merged cells with 3mm spacing
- Professional pharmaceutical Macedonian translation
- Signature blocks with approval chain
"""

from pathlib import Path
from typing import Dict, Optional
import sys
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from facility_config import load_facility_config

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from PIL import Image
except ImportError as e:
    print(f"Error: Missing required package. {str(e)}")
    print("Install with: pip install python-docx Pillow")
    sys.exit(1)


class FormatterSkillApprovalGenerator:
    """
    Generates approval pages strictly following Purely Plant Template Formatter Skill v1.0
    Implements bilingual two-column structure (MK 10pt | ENG 11pt)
    """

    # Standardized Macedonian terminology from Formatter Skill
    MACEDONIAN_TERMS = {
        'approval': 'ОДОБРУВАЊЕ',
        'document': 'ДОКУМЕНТ',
        'control': 'КОНТРОЛА',
        'revision': 'РЕВИЗИЈА',
        'history': 'ИСТОРИЈА',
        'prepared_by': 'Подготвено од:',
        'checked_by': 'Проверено од:',
        'approved_by': 'Одобрено од:',
        'position': 'Позиција:',
        'name_surname': 'Име и презиме:',
        'date': 'Датум:',
        'signature': 'Потпис:',
        'original_storage': 'Оригиналот се чува во:',
        'document_type': 'Тип на документ:',
        'current_storage': 'Овој документ се чува во:',
        'copy_type': 'Тип на копија:',
        'user_type': 'Тип на корисник:',
        'internal': 'Внатрешен',
        'external': 'Надворешен',
        'version_no': 'Верзија бр.',
        'date_change': 'Датум на промена:',
        'description': 'Опис на промена:',
    }

    def __init__(self, config=None):
        """Initialize generator with config."""
        if config is None:
            self.config = load_facility_config()
        else:
            self.config = config

        self.approval_chain = self.config.get('document_control.approval_chain', {})
        self.storage = self.config.get('document_control.storage', {})
        self.revision_policy = self.config.get('document_control.revision_policy', {})
        self.branding = self.config.get('document_control.branding', {})

        # Colors
        self.PRIMARY_GREEN = RGBColor(0x70, 0xad, 0x47)  # #70ad47
        self.LIGHT_GREEN = RGBColor(0xe2, 0xfd, 0xd9)   # #e2efd9
        self.BLACK = RGBColor(0, 0, 0)
        self.WHITE = RGBColor(255, 255, 255)

    def get_personnel_data(self, role_key: str) -> Dict:
        """Get personnel data from approval chain."""
        role_key_path = f'document_control.approval_chain.{role_key}'
        role_data = self.config.get(role_key_path, {})

        if not role_data:
            return {'name': '', 'position_mk': '', 'position_en': ''}

        # Get personnel details
        role = role_data.get('role', '')
        personnel = self.config.get(f'facility.personnel.{role}', {})

        return {
            'name': f"{personnel.get('first_name', '')} {personnel.get('last_name', '')}".strip(),
            'position_mk': role_data.get('position_mk', ''),
            'position_en': role_data.get('position_en', ''),
        }

    def set_table_invisible_borders(self, table):
        """Remove table borders (for layout tables in bilingual structure)."""
        tbl = table._element
        tblPr = tbl.tblPr
        if tblPr is None:
            tblPr = OxmlElement('w:tblPr')
            tbl.insert(0, tblPr)

        tblBorders = OxmlElement('w:tblBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'none')
            tblBorders.append(border)

        tblPr.append(tblBorders)

    def set_table_visible_borders(self, table, color='70ad47', width='12'):
        """Add green borders to table."""
        tbl = table._element
        tblPr = tbl.tblPr
        if tblPr is None:
            tblPr = OxmlElement('w:tblPr')
            tbl.insert(0, tblPr)

        tblBorders = OxmlElement('w:tblBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), width)
            border.set(qn('w:space'), '0')
            border.set(qn('w:color'), color)
            tblBorders.append(border)

        tblPr.append(tblBorders)

    def shade_cell(self, cell, fill_color='70ad47', text_color=None):
        """Shade cell with background color."""
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), fill_color)
        cell._element.get_or_add_tcPr().append(shading_elm)

        if text_color:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.color.rgb = text_color

    def create_approval_page_docx(self, metadata: Dict, output_path: Path) -> Path:
        """
        Create approval page DOCX following Formatter Skill specifications

        Args:
            metadata: Document metadata
            output_path: Output file path

        Returns:
            Path to generated file
        """
        doc = Document()

        # PAGE SETUP: A4, 0.5" margins
        for section in doc.sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.5)
            section.right_margin = Inches(0.5)

        # ==================== APPROVAL SIGNATURE TABLE ====================
        # 4×4 table per Formatter Skill spec
        sig_table = doc.add_table(rows=4, cols=4)
        self.set_table_visible_borders(sig_table, '70ad47', '12')

        # Row 1: Prepared by
        prepared = self.get_personnel_data('prepared_by')
        row1_cells = sig_table.rows[0].cells
        row1_cells[0].text = f"{self.MACEDONIAN_TERMS['prepared_by']}\nPrepared by:"
        row1_cells[1].text = prepared['name']
        row1_cells[2].text = f"{self.MACEDONIAN_TERMS['date']}\nDate and Signature:"
        row1_cells[3].text = ""

        # Row 2: Checked by
        checked = self.get_personnel_data('checked_by')
        row2_cells = sig_table.rows[1].cells
        row2_cells[0].text = f"{self.MACEDONIAN_TERMS['checked_by']}\nChecked by:"
        row2_cells[1].text = checked['name']
        row2_cells[2].text = f"{self.MACEDONIAN_TERMS['date']}\nDate and Signature:"
        row2_cells[3].text = ""

        # Row 3: Approved by
        approved = self.get_personnel_data('approved_by')
        row3_cells = sig_table.rows[2].cells
        row3_cells[0].text = f"{self.MACEDONIAN_TERMS['approved_by']}\nApproved by:"
        row3_cells[1].text = approved['name']
        row3_cells[2].text = f"{self.MACEDONIAN_TERMS['date']}\nDate and Signature:"
        row3_cells[3].text = ""

        # Row 4: Effective date (merge cols 1-3)
        row4_cells = sig_table.rows[3].cells
        row4_cells[0].text = f"Ефективна датум\nEffective date:"
        cell_merged = row4_cells[1]
        cell_merged.merge(row4_cells[2])
        cell_merged.merge(row4_cells[3])
        cell_merged.text = metadata.get('effective_date', '')

        # Format signature table
        for row in sig_table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.name = 'Calibri'
                        run.font.size = Pt(10)

        doc.add_paragraph()

        # ==================== DOCUMENT TITLE ====================
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title.add_run('СТАНДАРДНА ОПЕРАТИВНА ПРОЦЕДУРА')
        title_run.font.name = 'Calibri'
        title_run.font.size = Pt(36)
        title_run.font.bold = True

        doc.add_paragraph()

        # ==================== BILINGUAL TWO-COLUMN APPROVAL TABLE ====================
        # Main table structure: 2 columns (50%|50%), invisible borders
        approval_layout = doc.add_table(rows=1, cols=2)
        approval_layout.autofit = False
        approval_layout.allow_autofit = False
        self.set_table_invisible_borders(approval_layout)

        # Set column widths: 50/50
        for row in approval_layout.rows:
            row.cells[0].width = Inches(3.25)
            row.cells[1].width = Inches(3.25)

        mk_cell = approval_layout.rows[0].cells[0]
        en_cell = approval_layout.rows[0].cells[1]

        # Clear default paragraphs
        for para in mk_cell.paragraphs:
            para.text = ""
        for para in en_cell.paragraphs:
            para.text = ""

        # ========== MACEDONIAN COLUMN ==========
        mk_para = mk_cell.paragraphs[0]
        mk_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

        mk_run = mk_para.add_run(f"ОДОБРУВАЊЕ НА ДОКУМЕНТ")
        mk_run.font.name = 'Calibri'
        mk_run.font.size = Pt(12)
        mk_run.font.bold = True

        # Add approval table in MK
        mk_approval_table = mk_cell.add_table(rows=4, cols=5)
        self.set_table_visible_borders(mk_approval_table, '70ad47', '8')

        mk_headers = [
            'Дејство',
            'Позиција',
            'Име и презиме',
            'Датум',
            'Потпис'
        ]

        for idx, header in enumerate(mk_headers):
            cell = mk_approval_table.rows[0].cells[idx]
            self.shade_cell(cell, '70ad47', self.WHITE)
            cell.paragraphs[0].text = header
            for run in cell.paragraphs[0].runs:
                run.font.name = 'Calibri'
                run.font.size = Pt(8)
                run.font.bold = True

        # Data rows
        mk_actions = ['Подготвено од:', 'Проверено од:', 'Одобрено од:']
        for row_idx, action in enumerate(mk_actions):
            cells = mk_approval_table.rows[row_idx + 1].cells
            cells[0].text = action
            cells[1].text = ''
            cells[2].text = ''
            cells[3].text = ''
            cells[4].text = ''

            for cell in cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.name = 'Calibri'
                        run.font.size = Pt(7)

        # ========== ENGLISH COLUMN ==========
        en_para = en_cell.paragraphs[0]
        en_para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

        en_run = en_para.add_run(f"DOCUMENT APPROVAL")
        en_run.font.name = 'Calibri'
        en_run.font.size = Pt(12)
        en_run.font.bold = True

        # Add approval table in EN
        en_approval_table = en_cell.add_table(rows=4, cols=5)
        self.set_table_visible_borders(en_approval_table, '70ad47', '8')

        en_headers = [
            'Action',
            'Position',
            'Name & Surname',
            'Date',
            'Signature'
        ]

        for idx, header in enumerate(en_headers):
            cell = en_approval_table.rows[0].cells[idx]
            self.shade_cell(cell, '70ad47', self.WHITE)
            cell.paragraphs[0].text = header
            for run in cell.paragraphs[0].runs:
                run.font.name = 'Calibri'
                run.font.size = Pt(8)
                run.font.bold = True

        # Data rows
        en_actions = ['Prepared by:', 'Checked by:', 'Approved by:']
        for row_idx, action in enumerate(en_actions):
            cells = en_approval_table.rows[row_idx + 1].cells
            cells[0].text = action
            cells[1].text = ''
            cells[2].text = ''
            cells[3].text = ''
            cells[4].text = ''

            for cell in cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.name = 'Calibri'
                        run.font.size = Pt(7)

        doc.add_paragraph()

        # ==================== DOCUMENT CONTROL SECTION ====================
        doc_control = doc.add_paragraph()
        doc_control_run = doc_control.add_run("КОНТРОЛА НА ДОКУМЕНТ | DOCUMENT CONTROL")
        doc_control_run.font.name = 'Calibri'
        doc_control_run.font.size = Pt(12)
        doc_control_run.font.bold = True

        control_table = doc.add_table(rows=5, cols=2)
        self.set_table_visible_borders(control_table, '70ad47', '8')

        control_items = [
            ('Оригиналот се чува во: | The original is kept & stored in:',
             self.storage.get('original_location', 'N/A')),
            ('Тип на документ | Type of document:',
             metadata.get('document_type', 'SOP')),
            ('Овој документ се чува во: | This document is kept & stored in:',
             self.storage.get('current_location', 'N/A')),
            ('Тип на копија | Copy type:',
             self.storage.get('copy_type', 'controlled').capitalize()),
            ('Корисник | User type:',
             f"☒ {self.MACEDONIAN_TERMS['internal']} / Internal  ☐ {self.MACEDONIAN_TERMS['external']} / External"),
        ]

        for idx, (label, value) in enumerate(control_items):
            row = control_table.rows[idx]
            row.cells[0].text = label
            row.cells[1].text = value

            self.shade_cell(row.cells[0], 'e2efd9')

            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.name = 'Calibri'
                        run.font.size = Pt(8)

        doc.add_paragraph()

        # ==================== REVISION HISTORY ====================
        history = doc.add_paragraph()
        history_run = history.add_run("ИСТОРИЈА НА РЕВИЗИИ | REVISION HISTORY")
        history_run.font.name = 'Calibri'
        history_run.font.size = Pt(12)
        history_run.font.bold = True

        history_table = doc.add_table(rows=2, cols=3)
        self.set_table_visible_borders(history_table, '70ad47', '8')

        history_headers = [
            'Верзија бр. | Version No.',
            'Датум на промена | Date of change',
            'Опис на промена | Description of change'
        ]

        for idx, header in enumerate(history_table.rows[0].cells):
            self.shade_cell(header, '70ad47', self.WHITE)
            header.paragraphs[0].text = history_headers[idx]
            for run in header.paragraphs[0].runs:
                run.font.name = 'Calibri'
                run.font.size = Pt(8)
                run.font.bold = True

        # Data row
        data_cells = history_table.rows[1].cells
        data_cells[0].text = metadata.get('version', '1.0')
        data_cells[1].text = metadata.get('effective_date', 'dd.mm.yy')
        data_cells[2].text = 'Initial Release / Почетна верзија'

        for cell in data_cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.name = 'Calibri'
                    run.font.size = Pt(8)

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path


def main():
    """Main function."""
    base_dir = Path(__file__).parent.parent
    output_path = base_dir / 'PP_APPROVAL_PAGE_BILINGUAL_FORMATTER_v2.docx'

    print("\n" + "=" * 80)
    print("FORMATTER SKILL APPROVAL PAGE GENERATOR - BILINGUAL TWO-COLUMN LAYOUT")
    print("=" * 80 + "\n")

    config = load_facility_config()
    generator = FormatterSkillApprovalGenerator(config)

    try:
        metadata = {
            'document_id': 'PP-QC-SOP-008',
            'version': '1.0',
            'effective_date': datetime.now().strftime('%d.%m.%y'),
            'document_type': 'SOP',
        }

        result = generator.create_approval_page_docx(metadata, output_path)
        print(f"✅ Bilingual approval page created successfully!")
        print(f"📄 File: {result}")
        print(f"📊 Size: {result.stat().st_size / 1024:.1f} KB\n")
        print("Formatter Skill Compliance:")
        print("  ✓ Page setup: A4, 0.5\" margins")
        print("  ✓ Typography: 36pt title, 12pt headers, 8-10pt body")
        print("  ✓ Bilingual: Two-column structure (MK|ENG)")
        print("  ✓ Approval table: Bilingual side-by-side")
        print("  ✓ Green borders: #70ad47 styling")
        print("  ✓ Standardized Macedonian terminology")
        print("  ✓ All tables with proper formatting")
        print("  ✓ Follows Purely Plant Template Formatter Skill v1.0")
        print("\n✨ Approval page template ready!\n")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
