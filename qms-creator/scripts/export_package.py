#!/usr/bin/env python3
"""
Export Package Creator for Cannabis EU GMP QMS Creator
Creates a deliverable package with all generated documents and reports
"""

import shutil
import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console
import zipfile

console = Console()


def create_export_package(base_dir: Path, output_name: str = None):
    """Create export package with all generated documents."""

    console.print("\n[bold cyan]📦 Creating Export Package[/bold cyan]")
    console.print("=" * 80 + "\n")

    # Determine output filename
    if not output_name:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_name = f"Purely_Plant_QMS_Documents_{timestamp}"

    export_dir = base_dir / 'export' / output_name
    export_dir.mkdir(parents=True, exist_ok=True)

    # Copy customized documents
    customized_dir = base_dir / 'output' / 'customized'
    if customized_dir.exists():
        console.print("[cyan]Copying customized documents...[/cyan]")
        shutil.copytree(customized_dir, export_dir / 'documents', dirs_exist_ok=True)
        doc_count = len(list((export_dir / 'documents').rglob('*.txt')))
        console.print(f"  ✓ {doc_count} documents copied")

    # Copy validation report
    validation_report = base_dir / 'output' / 'validation_report.html'
    if validation_report.exists():
        console.print("[cyan]Copying validation report...[/cyan]")
        shutil.copy(validation_report, export_dir / 'validation_report.html')
        console.print("  ✓ Validation report copied")

    # Copy facility data
    facility_data = base_dir / 'config' / 'facility_data.yaml'
    if facility_data.exists():
        console.print("[cyan]Copying facility configuration...[/cyan]")
        shutil.copy(facility_data, export_dir / 'facility_data.yaml')
        console.print("  ✓ Facility data copied")

    # Copy documentation
    readme = base_dir / 'README_AUTOMATION.md'
    if readme.exists():
        console.print("[cyan]Copying documentation...[/cyan]")
        shutil.copy(readme, export_dir / 'README.md')
        console.print("  ✓ Documentation copied")

    # Create README for package
    package_readme = export_dir / 'PACKAGE_INFO.txt'
    with open(package_readme, 'w', encoding='utf-8') as f:
        f.write(f"""
================================================================================
PURELY PLANT GMBH - QMS DOCUMENT PACKAGE
================================================================================

Facility: Purely Plant Medical Cannabis Production Facility
Location: Skopje, North Macedonia
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
System: Cannabis EU GMP QMS Creator - Automation System v1.0

================================================================================
PACKAGE CONTENTS
================================================================================

1. documents/
   - All customized QMS documents with Purely Plant data
   - Organized by category (Master Documents, SOPs, etc.)
   - {doc_count if 'doc_count' in locals() else 'Multiple'} document files

2. validation_report.html
   - Visual validation report showing document completeness
   - Lists any unfilled placeholders
   - Open in web browser to view

3. facility_data.yaml
   - Source configuration file with all facility information
   - Contains personnel, equipment, regulatory data
   - Can be edited and documents regenerated

4. README.md
   - User guide for the automation system
   - Instructions for updating and regenerating documents
   - Command reference and troubleshooting

================================================================================
USAGE
================================================================================

To view the validation report:
  - Open validation_report.html in your web browser

To review generated documents:
  - Navigate to the documents/ folder
  - Key documents:
    * documents/00_MASTER_DOCUMENTS/QAS-01-001_Quality_Manual_Template.txt
    * documents/00_MASTER_DOCUMENTS/QAS-01-003_Facility_Profile_Master_Template.txt

To regenerate documents (requires automation system):
  1. Edit facility_data.yaml with updated information
  2. Run: python scripts/customize_documents.py --all
  3. New documents generated instantly

================================================================================
DOCUMENT STATUS
================================================================================

All documents have been customized with Purely Plant facility data:
- Company: Purely Plant GmbH
- QP: Blagoj Nikolov (Master Pharmacist)
- Location: Skopje, North Macedonia
- License: MK-MED-CANNABIS-2024-001
- Equipment: CDS24, MT Tumbler, HVAC, etc.
- Personnel: 8 managers with complete information

Some context-specific placeholders may require manual completion.
See validation_report.html for details.

================================================================================
SUPPORT
================================================================================

For questions or assistance:
- Review README.md for complete documentation
- Check validation_report.html for document status
- Contact QP: Blagoj Nikolov

================================================================================
CONFIDENTIALITY
================================================================================

This package contains confidential proprietary information of Purely Plant GmbH.
Distribution is restricted to authorized personnel only.

Classification: CONFIDENTIAL - INTERNAL USE ONLY

================================================================================
""")

    console.print("  ✓ Package info created")

    # Create ZIP archive
    console.print("\n[cyan]Creating ZIP archive...[/cyan]")
    zip_path = base_dir / 'export' / f'{output_name}.zip'

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in export_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(export_dir.parent)
                zipf.write(file_path, arcname)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    console.print(f"  ✓ ZIP archive created ({zip_size_mb:.2f} MB)")

    # Print summary
    console.print("\n" + "=" * 80)
    console.print("[bold green]✓ Export Package Created Successfully![/bold green]")
    console.print("=" * 80 + "\n")

    console.print(f"📁 Package directory: [cyan]{export_dir}[/cyan]")
    console.print(f"📦 ZIP archive: [cyan]{zip_path}[/cyan]")
    console.print(f"📊 Archive size: [cyan]{zip_size_mb:.2f} MB[/cyan]")

    console.print("\n[bold]Package Contents:[/bold]")
    console.print(f"  • {doc_count if 'doc_count' in locals() else 'Multiple'} customized documents")
    console.print("  • Validation report (HTML)")
    console.print("  • Facility configuration (YAML)")
    console.print("  • Documentation (Markdown)")
    console.print("  • Package information")

    console.print("\n[bold yellow]Next Steps:[/bold yellow]")
    console.print("  1. Extract ZIP or use folder directly")
    console.print("  2. Open validation_report.html in browser")
    console.print("  3. Review generated documents")
    console.print("  4. Fill any remaining placeholders")
    console.print("  5. Ready for regulatory submission\n")

    return export_dir, zip_path


def main():
    """Main export function."""
    base_dir = Path(__file__).parent.parent

    # Check if documents exist
    customized_dir = base_dir / 'output' / 'customized'
    if not customized_dir.exists() or not list(customized_dir.rglob('*.txt')):
        console.print("[bold red]✗[/bold red] No documents found. Run customize_documents.py first.")
        sys.exit(1)

    # Create export package
    export_dir, zip_path = create_export_package(base_dir)


if __name__ == "__main__":
    main()
