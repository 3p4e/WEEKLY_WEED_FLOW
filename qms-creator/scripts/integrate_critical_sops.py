#!/usr/bin/env python3
"""
Critical Foundation SOPs Integration Script
==========================================

This script integrates the 3 critical foundation SOPs into the automation system:

1. Document Control (QAS-00-002)
2. Change Control (QAS-00-005)
3. CAPA System (QAS-00-006)

The script performs:
- Applies proper bilingual approval pages
- Updates placeholders with facility data
- Generates PDF and DOCX versions
- Moves files to appropriate directories
- Updates project tracker

Usage:
    python integrate_critical_sops.py --dry-run   # Show what would be done
    python integrate_critical_sops.py              # Apply integration
"""

import argparse
import datetime
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import project modules
try:
    from scripts.approval_page_generator import ApprovalPageGenerator
    from scripts.facility_config import load_facility_config
    from scripts.placeholder_engine import PlaceholderEngine
    from scripts.professional_pdf_generator import ProfessionalPDFGenerator
    from scripts.purely_plant_docx_generator import PurelyPlantDocxGenerator
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Make sure you're running from the project root directory.")
    sys.exit(1)


class CriticalSOPsIntegrator:
    """Integrate critical foundation SOPs into automation system."""

    def __init__(self, base_dir: Path = None):
        """Initialize integrator with base directory."""
        self.base_dir = base_dir or Path.cwd()
        self.config = load_facility_config(self.base_dir / "config")
        self.approval_gen = ApprovalPageGenerator(self.config)
        self.placeholder_engine = PlaceholderEngine(self.config)

        # Define critical SOPs with their metadata
        self.critical_sops = {
            "document_control": {
                "code": "QAS-00-002",
                "filename": "QA_00.02_Document_Control_v1.0_EN.md",
                "title_en": "Document Control",
                "title_mk": "Контрола на документи",
                "annexes": [
                    "QA_00.02_A01_Document_Templates_v1.0_EN.md",
                    "QA_00.02_A02_Approval_Matrix_v1.0_EN.md",
                    "QA_00.02_A03_Change_Request_Form_v1.0_EN.md",
                    "QA_00.02_A04_Obsolete_Handling_v1.0_EN.md",
                ],
            },
            "change_control": {
                "code": "QAS-00-005",
                "filename": "QA_00.05_Change_Control_v1.0_EN.md",
                "title_en": "Change Control",
                "title_mk": "Контрола на промени",
                "annexes": [
                    "QA_00.05_A01_Change_Control_Request_Form_v1.0_EN.md",
                    "QA_00.05_A02_Risk_Assessment_Templates_v1.0_EN.md",
                    "QA_00.05_A03_Impact_Assessment_Form_v1.0_EN.md",
                ],
            },
            "capa_system": {
                "code": "QAS-00-006",
                "filename": "QA_00.06_CAPA_System_v1.0_EN.md",
                "title_en": "Corrective and Preventive Action (CAPA) System",
                "title_mk": "Систем за Корективни и Превентивни Активности",
                "annexes": [
                    "QA_00.06_A01_CAPA_Request_Form_v1.0_EN.md",
                    "QA_00.06_A02_RCA_Templates_v1.0_EN.md",
                    "QA_00.06_A03_Effectiveness_Review_v1.0_EN.md",
                ],
            },
        }

        # Setup logging
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

        # Statistics
        self.stats = {
            "sops_processed": 0,
            "annexes_processed": 0,
            "pdfs_generated": 0,
            "docx_generated": 0,
            "files_moved": 0,
            "errors": [],
        }

    def ensure_approval_page(self, content: str, metadata: Dict) -> str:
        """
        Ensure document has proper bilingual approval page.

        Args:
            content: Original markdown content
            metadata: SOP metadata including document_id, titles, etc.

        Returns:
            Content with proper approval page
        """
        # Check if content already has Purely Plant approval page
        if "# Purely Plant GmbH" in content and "ОДОБРУВАЊЕ НА ДОКУМЕНТ" in content:
            self.logger.debug("Document already has Purely Plant approval page")
            return content

        # Generate approval page metadata
        approval_metadata = {
            "document_id": metadata["code"],
            "version": "1.0",
            "title_en": metadata["title_en"],
            "title_mk": metadata["title_mk"],
            "effective_date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "copy_type": "controlled",
            "document_type": "SOP",
        }

        # Generate approval page
        try:
            approval_page = self.approval_gen.generate_markdown_approval_page(
                approval_metadata
            )

            # Remove any existing YAML front matter or old approval sections
            lines = content.split("\n")
            cleaned_lines = []
            in_yaml = False
            yaml_ended = False

            for line in lines:
                if line.strip() == "---":
                    if not in_yaml:
                        in_yaml = True
                        continue
                    else:
                        in_yaml = False
                        yaml_ended = True
                        continue

                if in_yaml:
                    continue

                if yaml_ended and line.strip().startswith("# "):
                    # Found first header after YAML, stop cleaning
                    break

                if not in_yaml and not yaml_ended:
                    cleaned_lines.append(line)

            cleaned_content = "\n".join(cleaned_lines).strip()

            # Combine approval page with cleaned content
            return approval_page + "\n" + cleaned_content

        except Exception as e:
            self.logger.error(f"Error generating approval page: {e}")
            return content

    def update_placeholders(self, content: str) -> str:
        """
        Update placeholders with facility data.

        Args:
            content: Document content

        Returns:
            Content with placeholders replaced
        """
        try:
            return self.placeholder_engine.replace_placeholders(content)
        except Exception as e:
            self.logger.warning(f"Error updating placeholders: {e}")
            return content

    def generate_pdf(self, markdown_path: Path, output_dir: Path) -> bool:
        """
        Generate PDF version of document.

        Args:
            markdown_path: Path to markdown file
            output_dir: Directory to save PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            pdf_generator = ProfessionalPDFGenerator()

            # Read markdown content
            with open(markdown_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Generate PDF filename
            pdf_filename = markdown_path.stem + ".pdf"
            pdf_path = output_dir / pdf_filename

            # Generate PDF
            success = pdf_generator.generate_pdf(
                content=content,
                output_path=str(pdf_path),
                title=markdown_path.stem.replace("_", " ").replace("-", " "),
            )

            if success:
                self.stats["pdfs_generated"] += 1
                self.logger.info(f"Generated PDF: {pdf_path}")
                return True
            else:
                self.logger.error(f"Failed to generate PDF: {markdown_path}")
                return False

        except Exception as e:
            self.logger.error(f"Error generating PDF for {markdown_path}: {e}")
            self.stats["errors"].append(
                f"PDF generation failed for {markdown_path}: {str(e)}"
            )
            return False

    def generate_docx(self, markdown_path: Path, output_dir: Path) -> bool:
        """
        Generate DOCX version of document.

        Args:
            markdown_path: Path to markdown file
            output_dir: Directory to save DOCX

        Returns:
            True if successful, False otherwise
        """
        try:
            docx_generator = PurelyPlantDocxGenerator()

            # Read markdown content
            with open(markdown_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Generate DOCX filename
            docx_filename = markdown_path.stem + ".docx"
            docx_path = output_dir / docx_filename

            # Generate DOCX
            success = docx_generator.generate_docx(
                content=content,
                output_path=str(docx_path),
                title=markdown_path.stem.replace("_", " ").replace("-", " "),
            )

            if success:
                self.stats["docx_generated"] += 1
                self.logger.info(f"Generated DOCX: {docx_path}")
                return True
            else:
                self.logger.error(f"Failed to generate DOCX: {markdown_path}")
                return False

        except Exception as e:
            self.logger.error(f"Error generating DOCX for {markdown_path}: {e}")
            self.stats["errors"].append(
                f"DOCX generation failed for {markdown_path}: {str(e)}"
            )
            return False

    def move_to_quality_assurance(self, source_path: Path, sop_code: str) -> bool:
        """
        Move SOP file to 01_QUALITY_ASSURANCE directory.

        Args:
            source_path: Source file path
            sop_code: SOP code (e.g., QAS-00-002)

        Returns:
            True if successful, False otherwise
        """
        try:
            target_dir = self.base_dir / "01_QUALITY_ASSURANCE"
            target_dir.mkdir(exist_ok=True)

            # Convert SOP code to filename format (QAS-00-002 -> QAS-00-002_)
            # Actually keep original filename for now
            target_path = target_dir / source_path.name

            if source_path != target_path:
                shutil.copy2(source_path, target_path)
                self.stats["files_moved"] += 1
                self.logger.info(f"Moved to Quality Assurance: {target_path}")
                return True
            return True  # Already in target location

        except Exception as e:
            self.logger.error(f"Error moving file {source_path}: {e}")
            self.stats["errors"].append(f"File move failed for {source_path}: {str(e)}")
            return False

    def process_sop(self, sop_key: str, sop_info: Dict, dry_run: bool = False) -> bool:
        """
        Process a single SOP and its annexes.

        Args:
            sop_key: SOP key (document_control, change_control, capa_system)
            sop_info: SOP information dictionary
            dry_run: If True, only show what would be done

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(
            f"Processing {sop_key.replace('_', ' ').title()}: {sop_info['code']}"
        )

        success = True

        # Process main SOP
        sop_filename = sop_info["filename"]
        sop_path = self.base_dir / "sops_created" / sop_filename

        if not sop_path.exists():
            self.logger.error(f"SOP file not found: {sop_path}")
            self.stats["errors"].append(f"SOP file not found: {sop_path}")
            return False

        if dry_run:
            self.logger.info(f"Would process: {sop_filename}")
            self.stats["sops_processed"] += 1
        else:
            # Read content
            with open(sop_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Ensure approval page
            content = self.ensure_approval_page(content, sop_info)

            # Update placeholders
            content = self.update_placeholders(content)

            # Write updated content
            with open(sop_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Generate PDF and DOCX
            pdf_success = self.generate_pdf(sop_path, sop_path.parent)
            docx_success = self.generate_docx(sop_path, sop_path.parent)

            # Move to Quality Assurance directory
            move_success = self.move_to_quality_assurance(sop_path, sop_info["code"])

            self.stats["sops_processed"] += 1

            if not (pdf_success and docx_success and move_success):
                success = False

        # Process annexes
        for annex_filename in sop_info.get("annexes", []):
            annex_path = self.base_dir / "sops_created" / annex_filename

            if not annex_path.exists():
                self.logger.warning(f"Annex file not found: {annex_path}")
                continue

            if dry_run:
                self.logger.info(f"Would process annex: {annex_filename}")
                self.stats["annexes_processed"] += 1
            else:
                # Read content
                with open(annex_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Ensure approval page (annexes may have simpler headers)
                content = self.ensure_approval_page(content, sop_info)

                # Update placeholders
                content = self.update_placeholders(content)

                # Write updated content
                with open(annex_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # Generate PDF and DOCX for annexes
                self.generate_pdf(annex_path, annex_path.parent)
                self.generate_docx(annex_path, annex_path.parent)

                # Move annex to Quality Assurance directory
                self.move_to_quality_assurance(annex_path, sop_info["code"])

                self.stats["annexes_processed"] += 1

        return success

    def update_project_tracker(self) -> bool:
        """
        Update project tracker with integration status.

        Returns:
            True if successful, False otherwise
        """
        try:
            tracker_path = self.base_dir / "PROJECT_MASTER_TRACKER.md"
            if not tracker_path.exists():
                self.logger.warning("Project tracker not found")
                return False

            with open(tracker_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Update critical SOPs status
            updates = {
                "QAS-00-002": "✅ Integrated",
                "QAS-00-005": "✅ Integrated",
                "QAS-00-006": "✅ Integrated",
            }

            for code, status in updates.items():
                # Find and replace status in tracker
                pattern = rf"(\| {code}.*?\| ).*?(\|.*)"
                replacement = rf"\1{status}\2"
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

            # Write updated content
            with open(tracker_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info("Updated project tracker")
            return True

        except Exception as e:
            self.logger.error(f"Error updating project tracker: {e}")
            self.stats["errors"].append(f"Tracker update failed: {str(e)}")
            return False

    def run(self, dry_run: bool = False) -> Dict:
        """
        Run integration for all critical SOPs.

        Args:
            dry_run: If True, only show what would be done

        Returns:
            Statistics dictionary
        """
        self.logger.info("=" * 80)
        self.logger.info("CRITICAL FOUNDATION SOPS INTEGRATION")
        self.logger.info("=" * 80)

        if dry_run:
            self.logger.info("DRY RUN MODE - No changes will be made")

        # Process each critical SOP
        all_success = True
        for sop_key, sop_info in self.critical_sops.items():
            success = self.process_sop(sop_key, sop_info, dry_run)
            if not success:
                all_success = False

        # Update project tracker if not dry run
        if not dry_run and all_success:
            self.update_project_tracker()

        # Print summary
        self.logger.info("=" * 80)
        self.logger.info("INTEGRATION SUMMARY")
        self.logger.info("=" * 80)
        self.logger.info(f"SOPs Processed: {self.stats['sops_processed']}")
        self.logger.info(f"Annexes Processed: {self.stats['annexes_processed']}")
        self.logger.info(f"PDFs Generated: {self.stats['pdfs_generated']}")
        self.logger.info(f"DOCX Generated: {self.stats['docx_generated']}")
        self.logger.info(f"Files Moved: {self.stats['files_moved']}")

        if self.stats["errors"]:
            self.logger.error(f"Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats["errors"][:5]:  # Show first 5 errors
                self.logger.error(f"  - {error}")

        if all_success:
            self.logger.info("✅ Integration completed successfully")
        else:
            self.logger.error("❌ Integration completed with errors")

        return self.stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Integrate critical foundation SOPs into automation system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run           # Show what would be done
  %(prog)s                     # Apply integration
  %(prog)s --help              # Show this help message
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    parser.add_argument(
        "--base-dir", default=".", help="Base directory (default: current directory)"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run integrator
    base_dir = Path(args.base_dir).resolve()
    integrator = CriticalSOPsIntegrator(base_dir)

    try:
        stats = integrator.run(args.dry_run)

        # Exit with appropriate code
        if stats["errors"]:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        integrator.logger.info("Integration interrupted by user")
        sys.exit(1)
    except Exception as e:
        integrator.logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
