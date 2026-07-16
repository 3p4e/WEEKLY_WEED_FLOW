#!/usr/bin/env python3
"""
DB2 Knowledgebase Anonymization Script

Permanently anonymizes company names, subsidiary names, and employee names
in DB2 knowledgebase files to prevent bias and protect confidentiality.

Usage:
    # Dry run - preview changes
    python scripts/anonymize_db2.py --entity entity_1 --dry-run

    # Full anonymization with backup
    python scripts/anonymize_db2.py --entity entity_1 --backup

    # Without backup (if you've already backed up)
    python scripts/anonymize_db2.py --entity entity_1
"""

import argparse
import json
import logging
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# python-docx for DOCX processing
try:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError
except ImportError:
    print("ERROR: python-docx not installed. Run: pip install python-docx")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIGS_DIR = SCRIPT_DIR / "entity_configs"


class AnonymizationStats:
    """Track replacement statistics."""

    def __init__(self):
        self.files_processed = 0
        self.files_modified = 0
        self.files_skipped = 0
        self.files_errored = 0
        self.total_replacements = 0
        self.replacements_by_term: Dict[str, int] = defaultdict(int)
        self.replacements_by_file: Dict[str, int] = defaultdict(int)
        self.errors: List[Tuple[str, str]] = []

    def add_replacement(self, term: str, file_path: str, count: int = 1):
        self.total_replacements += count
        self.replacements_by_term[term] += count
        self.replacements_by_file[str(file_path)] += count

    def add_error(self, file_path: str, error: str):
        self.files_errored += 1
        self.errors.append((str(file_path), error))

    def report(self) -> str:
        lines = [
            "",
            "=" * 60,
            "ANONYMIZATION REPORT",
            "=" * 60,
            f"Files processed:  {self.files_processed}",
            f"Files modified:   {self.files_modified}",
            f"Files skipped:    {self.files_skipped}",
            f"Files with errors: {self.files_errored}",
            f"Total replacements: {self.total_replacements}",
            "",
            "--- Replacements by Term ---",
        ]

        for term, count in sorted(
            self.replacements_by_term.items(), key=lambda x: -x[1]
        ):
            lines.append(f"  {term}: {count}")

        if self.errors:
            lines.append("")
            lines.append("--- Errors ---")
            for file_path, error in self.errors:
                lines.append(f"  {file_path}: {error}")

        lines.append("=" * 60)
        return "\n".join(lines)


class DocxAnonymizer:
    """Anonymize DOCX files by replacing sensitive terms."""

    def __init__(self, config: Dict[str, Any], dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.stats = AnonymizationStats()

        # Build replacement map (sorted by length descending to avoid partial matches)
        self.replacements = self._build_replacement_map()
        self.unknown_employee_counter = len(config.get("known_employees", {})) + 1

    def _build_replacement_map(self) -> List[Tuple[str, str]]:
        """Build sorted list of (original, replacement) tuples."""
        replacements = {}

        # Company replacements
        for original, replacement in self.config.get("company_replacements", {}).items():
            replacements[original] = replacement

        # Employee replacements
        for original, replacement in self.config.get("known_employees", {}).items():
            replacements[original] = replacement

        # Sort by length descending (longer matches first)
        sorted_replacements = sorted(replacements.items(), key=lambda x: -len(x[0]))
        return sorted_replacements

    def _replace_text(self, text: str) -> Tuple[str, int]:
        """Replace all sensitive terms in text. Returns (new_text, replacement_count)."""
        if not text:
            return text, 0

        count = 0
        new_text = text

        for original, replacement in self.replacements:
            if original in new_text:
                occurrences = new_text.count(original)
                new_text = new_text.replace(original, replacement)
                count += occurrences
                self.stats.add_replacement(original, "", occurrences)

        return new_text, count

    def _process_paragraph(self, paragraph) -> int:
        """Process a single paragraph. Returns replacement count."""
        if not paragraph.text:
            return 0

        original_text = paragraph.text
        new_text, count = self._replace_text(original_text)

        if count > 0 and new_text != original_text:
            # Preserve formatting by processing runs
            if len(paragraph.runs) == 1:
                paragraph.runs[0].text = new_text
            elif len(paragraph.runs) > 1:
                # Complex case: multiple runs with formatting
                # Clear all runs and set text on first run
                full_text = original_text
                new_full_text, _ = self._replace_text(full_text)

                # Strategy: preserve first run's formatting, clear others
                if paragraph.runs:
                    paragraph.runs[0].text = new_full_text
                    for run in paragraph.runs[1:]:
                        run.text = ""

        return count

    def _process_table(self, table) -> int:
        """Process all cells in a table. Returns replacement count."""
        count = 0
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    count += self._process_paragraph(paragraph)
        return count

    def _process_header_footer(self, section) -> int:
        """Process headers and footers in a section."""
        count = 0

        # Header
        if section.header:
            for paragraph in section.header.paragraphs:
                count += self._process_paragraph(paragraph)
            for table in section.header.tables:
                count += self._process_table(table)

        # Footer
        if section.footer:
            for paragraph in section.footer.paragraphs:
                count += self._process_paragraph(paragraph)
            for table in section.footer.tables:
                count += self._process_table(table)

        return count

    def process_file(self, file_path: Path) -> int:
        """Process a single DOCX file. Returns total replacement count."""
        self.stats.files_processed += 1

        try:
            doc = Document(str(file_path))
        except PackageNotFoundError:
            self.stats.add_error(file_path, "Not a valid DOCX file")
            return 0
        except Exception as e:
            self.stats.add_error(file_path, str(e))
            return 0

        total_count = 0

        # Process main body paragraphs
        for paragraph in doc.paragraphs:
            total_count += self._process_paragraph(paragraph)

        # Process tables
        for table in doc.tables:
            total_count += self._process_table(table)

        # Process headers and footers
        for section in doc.sections:
            total_count += self._process_header_footer(section)

        if total_count > 0:
            self.stats.files_modified += 1
            self.stats.replacements_by_file[str(file_path)] = total_count

            if not self.dry_run:
                doc.save(str(file_path))
                logger.info(f"Modified: {file_path.name} ({total_count} replacements)")
            else:
                logger.info(f"[DRY RUN] Would modify: {file_path.name} ({total_count} replacements)")
        else:
            self.stats.files_skipped += 1
            logger.debug(f"Skipped (no matches): {file_path.name}")

        return total_count

    def process_folder(self, folder_path: Path) -> AnonymizationStats:
        """Process all DOCX files in folder recursively."""
        docx_files = list(folder_path.rglob("*.docx"))
        doc_files = list(folder_path.rglob("*.doc"))

        # Filter out temp files (start with ~$)
        docx_files = [f for f in docx_files if not f.name.startswith("~$")]
        doc_files = [f for f in doc_files if not f.name.startswith("~$")]

        logger.info(f"Found {len(docx_files)} .docx files and {len(doc_files)} .doc files")
        logger.info(f"Processing .docx files only (.doc files require conversion)")

        if self.dry_run:
            logger.info("=" * 40)
            logger.info("DRY RUN MODE - No files will be modified")
            logger.info("=" * 40)

        for i, file_path in enumerate(sorted(docx_files), 1):
            logger.info(f"[{i}/{len(docx_files)}] Processing: {file_path.relative_to(folder_path)}")
            self.process_file(file_path)

        return self.stats


def create_backup(source_folder: Path) -> Path:
    """Create timestamped backup of the folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{source_folder.name}_BACKUP_{timestamp}"
    backup_path = source_folder.parent / backup_name

    logger.info(f"Creating backup: {backup_path}")
    shutil.copytree(source_folder, backup_path)
    logger.info(f"Backup complete: {backup_path}")

    return backup_path


def load_config(entity_id: str) -> Dict[str, Any]:
    """Load entity configuration from JSON file."""
    config_path = CONFIGS_DIR / f"{entity_id}.json"

    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        logger.info(f"Available configs: {list(CONFIGS_DIR.glob('*.json'))}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Anonymize DB2 knowledgebase files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--entity",
        required=True,
        help="Entity ID (e.g., entity_1). Must have matching config in scripts/entity_configs/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create timestamped backup before processing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    logger.info(f"Loading config for entity: {args.entity}")
    config = load_config(args.entity)

    # Resolve folder path
    folder_path = PROJECT_ROOT / config["folder_path"]
    if not folder_path.exists():
        logger.error(f"Folder not found: {folder_path}")
        sys.exit(1)

    logger.info(f"Target folder: {folder_path}")
    logger.info(f"Company terms to replace: {len(config.get('company_replacements', {}))}")
    logger.info(f"Employee names to replace: {len(config.get('known_employees', {}))}")

    # Create backup if requested
    if args.backup and not args.dry_run:
        backup_path = create_backup(folder_path)
        logger.info(f"Backup created at: {backup_path}")

    # Process files
    anonymizer = DocxAnonymizer(config, dry_run=args.dry_run)
    stats = anonymizer.process_folder(folder_path)

    # Print report
    print(stats.report())

    # Write report to file
    report_name = f"anonymization_report_{args.entity}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_path = SCRIPT_DIR / report_name
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(stats.report())
    logger.info(f"Report saved to: {report_path}")

    if args.dry_run:
        logger.info("")
        logger.info("This was a DRY RUN. To apply changes, run without --dry-run flag.")
        logger.info("Recommended: python scripts/anonymize_db2.py --entity entity_1 --backup")


if __name__ == "__main__":
    main()
