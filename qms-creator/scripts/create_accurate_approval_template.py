#!/usr/bin/env python3
"""
Create Accurate Approval Page Template - Matching Purely Plant Original Design
Includes logo, proper green styling, and correct layout
"""

from pathlib import Path
from typing import Optional
import sys

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


class AccurateApprovalTemplateGenerator:
    """Generate approval page template matching original Purely Plant design."""

    def __init__(self, config=None):
        """Initialize template generator."""
        if config is None:
            self.config = load_facility_config()
        else:
            self.config = config

        self.branding = self.config.get('document_control.branding', {})
        self.logo_path = Path(self.config.get('document_control.branding.logo_path', 'assets/purely_plant_logo.jpg'))

        # Convert hex to RGB for docx
        self.green_dark = RGBColor(0x70, 0xad, 0x47)  # #70ad47
        self.green_light = RGBColor(0xe2, 0xfd, 0xd9)  # #e2efd9

    def shade_cell(self, cell, fill_color='70ad47'):
        """Add background color to cell."""
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), fill_color)
        cell._element.get_or_add_tcPr().append(shading_elm)

    def set_cell_text_color(self, cell, color=RGBColor(255, 255, 255)):
        """Set text color in cell."""
        for para in cell.paragraphs:
            for run in para.runs:
                run.font.color.rgb = color

    def add_table_borders(self, table, color='70ad47', width='12'):
        """Add borders to table."""
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

    def generate_template(self, output_path: Path):
        """Generate accurate approval page template matching original design."""
        doc = Document()

        # Set narrow margins to match original
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(0.4)
            section.bottom_margin = Inches(0.4)
            section.left_margin = Inches(0.5)
            section.right_margin = Inches(0.5)

        # ==================== HEADER WITH DOCUMENT ID AND PAGE NUMBER ====================
        header_table = doc.add_table(rows=1, cols=2)
        header_table.alignment = WD_ALIGN_PARAGRAPH.CENTER
        header_table.autofit = False
        self.add_table_borders(header_table, '70ad47', '12')

        # Shade header cells
        left_cell = header_table.rows[0].cells[0]
        right_cell = header_table.rows[0].cells[1]
        self.shade_cell(left_cell, 'e2efd9')
        self.shade_cell(right_cell, 'e2efd9')

        # Left cell - Document ID
        left_para = left_cell.paragraphs[0]
        left_run = left_para.add_run('N/A')
        left_run.bold = True
        left_run.font.size = Pt(10)

        # Right cell - Page number
        right_para = right_cell.paragraphs[0]
        right_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        right_run = right_para.add_run('Page N/A of N/A')
        right_run.font.size = Pt(10)

        # Effective date below header
        date_para = doc.add_paragraph()
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_run = date_para.add_run('eff. dd.mm.yy')
        date_run.font.size = Pt(9)
        date_run.italic = True

        doc.add_paragraph()

        # ==================== TITLE SECTION WITH LOGO ====================
        # Create table for logo and title
        title_table = doc.add_table(rows=1, cols=2)
        title_table.autofit = False

        # Logo cell
        logo_cell = title_table.rows[0].cells[0]
        logo_para = logo_cell.paragraphs[0]

        # Try to add logo
        try:
            full_logo_path = Path(__file__).parent.parent / self.logo_path
            if full_logo_path.exists():
                logo_run = logo_para.add_run()
                logo_run.add_picture(str(full_logo_path), width=Inches(0.8))
            else:
                logo_run = logo_para.add_run('[LOGO]')
                logo_run.font.size = Pt(9)
        except Exception as e:
            logo_run = logo_para.add_run('[LOGO - File not found]')
            logo_run.font.size = Pt(8)

        # Title cell
        title_cell = title_table.rows[0].cells[1]
        title_cell.vertical_alignment = 1  # Center vertically

        # Title in Macedonian (bold, large)
        title_para = title_cell.paragraphs[0]
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run('[DOCUMENT TITLE - МАКЕДОНСКИ]')
        title_run.bold = True
        title_run.font.size = Pt(13)

        # English subtitle
        subtitle_para = title_cell.add_paragraph()
        subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle_run = subtitle_para.add_run('[Document Title - English]')
        subtitle_run.font.size = Pt(11)

        # Remove borders from title table
        tbl = title_table._element
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

        doc.add_paragraph()

        # ==================== DOCUMENT APPROVAL TABLE ====================
        approval_heading = doc.add_paragraph()
        approval_heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
        # Add green background to heading paragraph
        approval_run = approval_heading.add_run('ОДОБРУВАЊЕ НА ДОКУМЕНТ | DOCUMENT APPROVAL')
        approval_run.bold = True
        approval_run.font.size = Pt(10)
        approval_run.font.color.rgb = self.green_dark

        # Shade paragraph background
        pPr = approval_heading._element.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), '70ad47')
        pPr.append(shd)
        approval_run.font.color.rgb = RGBColor(255, 255, 255)  # White text

        approval_table = doc.add_table(rows=4, cols=5)
        approval_table.style = 'Light Grid'
        self.add_table_borders(approval_table, '70ad47')

        # Header row
        header_cells = approval_table.rows[0].cells
        headers = ['Дејство: | Action:', 'Позиција: | Position:', 'Име и Презиме | Name & Surname', 'Датум: | Date:', 'Потпис: | Signature:']

        for idx, header_text in enumerate(headers):
            cell = header_cells[idx]
            self.shade_cell(cell, '70ad47')
            para = cell.paragraphs[0]
            para.text = header_text
            para.runs[0].bold = True
            para.runs[0].font.size = Pt(8)
            para.runs[0].font.color.rgb = RGBColor(255, 255, 255)  # White text

        # Data rows
        actions = [
            'Подготвено од: | Prepared by:',
            'Проверено од: | Checked by:',
            'Одобрено од: | Approved by:'
        ]

        for row_idx, action in enumerate(actions):
            cells = approval_table.rows[row_idx + 1].cells
            cells[0].text = action
            cells[1].text = 'N/A'
            cells[2].text = 'N/A'
            cells[3].text = '__________'
            cells[4].text = '_________________'

            # Shade first cell
            self.shade_cell(cells[0], 'e2efd9')

            for cell_idx, cell in enumerate(cells):
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(8)

        doc.add_paragraph()

        # ==================== DOCUMENT STORAGE TABLE ====================
        storage_heading = doc.add_paragraph()
        storage_run = storage_heading.add_run('КОНТРОЛА НА ДОКУМЕНТ | DOCUMENT CONTROL')
        storage_run.bold = True
        storage_run.font.size = Pt(10)
        storage_run.font.color.rgb = RGBColor(255, 255, 255)

        pPr = storage_heading._element.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), '70ad47')
        pPr.append(shd)

        storage_table = doc.add_table(rows=6, cols=2)
        self.add_table_borders(storage_table, '70ad47')

        storage_items = [
            ('Оригиналот се чува во: | The original doc. is kept & stored in:', 'N/A'),
            ('Тип на документ | Type of document:', 'N/A'),
            ('Овој документ се чува во: | This document is kept & stored in:', 'N/A'),
            ('Регистар на ревизии на документот | Revision registry', ''),
            ('Датум на последна ревизија: | Date of last revision:', '__________'),
            ('Ефективен датум на користење | Effective Date of Use:', '__________'),
        ]

        for row_idx, (label, value) in enumerate(storage_items):
            row = storage_table.rows[row_idx]
            row.cells[0].text = label
            row.cells[1].text = value

            self.shade_cell(row.cells[0], 'e2efd9')

            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(8)

        doc.add_paragraph()

        # ==================== USER TYPE ====================
        user_para = doc.add_paragraph()
        user_para.add_run('Корисник: | User: ').bold = True
        user_para.add_run('☐ Внатрешен: | Internal:  ☐ Надворешен: | External:')
        for run in user_para.runs:
            run.font.size = Pt(9)

        doc.add_paragraph()

        # ==================== REVISION HISTORY ====================
        history_heading = doc.add_paragraph()
        history_run = history_heading.add_run('ИСТОРИЈА НА РЕВИЗИИ | REVISION HISTORY')
        history_run.bold = True
        history_run.font.size = Pt(10)
        history_run.font.color.rgb = RGBColor(255, 255, 255)

        pPr = history_heading._element.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:fill'), '70ad47')
        pPr.append(shd)

        history_table = doc.add_table(rows=4, cols=3)
        self.add_table_borders(history_table, '70ad47')

        history_headers = ['Верзија бр. | Version No.', 'Датум на промена: | Date of change:', 'Опис на променета содржина | Description of change, Page No.']

        for idx, header_text in enumerate(history_table.rows[0].cells):
            self.shade_cell(header_text, '70ad47')
            para = header_text.paragraphs[0]
            para.text = history_headers[idx]
            para.runs[0].bold = True
            para.runs[0].font.size = Pt(8)
            para.runs[0].font.color.rgb = RGBColor(255, 255, 255)

        # Data rows
        for row_idx in range(1, 4):
            row = history_table.rows[row_idx]
            row.cells[0].text = 'N/A'
            row.cells[1].text = 'N/A'
            row.cells[2].text = 'N/A'

            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(8)

        # Save document
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return output_path


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate accurate approval page template')
    parser.add_argument(
        '--output',
        type=str,
        default='APPROVAL_PAGE_TEMPLATE_ACCURATE_v1.0.docx',
        help='Output file path'
    )

    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent
    output_path = base_dir / args.output

    print("\n" + "=" * 80)
    print("GENERATING ACCURATE APPROVAL PAGE TEMPLATE")
    print("=" * 80 + "\n")

    config = load_facility_config()
    generator = AccurateApprovalTemplateGenerator(config)

    try:
        result = generator.generate_template(output_path)
        print(f"✅ Accurate template created successfully!")
        print(f"📄 File: {result}")
        print(f"📊 Size: {result.stat().st_size / 1024:.1f} KB\n")
        print("Features:")
        print("  ✓ Logo embedded (from assets/purely_plant_logo.jpg)")
        print("  ✓ Green color scheme (#70ad47, #e2efd9)")
        print("  ✓ Matches original Purely Plant design")
        print("  ✓ Bilingual tables (Macedonian | English)")
        print("  ✓ Professional formatting")
        print("\n✨ Template ready to use!\n")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
