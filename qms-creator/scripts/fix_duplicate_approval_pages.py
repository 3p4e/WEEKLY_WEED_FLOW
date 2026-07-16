#!/usr/bin/env python3
"""
Fix Duplicate Approval Pages Script
===================================

This script identifies and fixes duplicate approval page sections in markdown files.
It addresses issues where the approval page generator was run multiple times,
creating duplicate approval headers in the same document.

Usage:
    python fix_duplicate_approval_pages.py --dry-run   # Show what would be fixed
    python fix_duplicate_approval_pages.py              # Apply fixes

Features:
    - Detects duplicate approval pages by counting YAML front matter sections
    - Removes duplicates while keeping the first valid approval page
    - Extracts proper document ID from filename
    - Updates YAML front matter with correct document ID
    - Creates backups before making changes
    - Provides detailed reports of fixes applied
"""

import argparse
import datetime
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ApprovalPageFixer:
    """Fix duplicate approval pages in markdown documents."""

    def __init__(self, base_dir: Path = None):
        """Initialize the fixer with base directory."""
        self.base_dir = base_dir or Path.cwd()
        self.stats = {
            "total_files": 0,
            "files_with_duplicates": 0,
            "files_fixed": 0,
            "files_skipped": 0,
            "errors": [],
            "backups_created": [],
        }

    def count_approval_pages(self, content: str) -> int:
        """
        Count approval pages in content by detecting YAML front matter sections.

        An approval page is defined by:
        1. YAML front matter block (--- ... ---)
        2. Followed by "# Purely Plant GmbH" header

        Returns: Number of approval page sections found.
        """
        # Pattern to match YAML front matter blocks
        yaml_pattern = r"^---\s*\n(?:.*?\n)*?---\s*\n"
        matches = re.findall(yaml_pattern, content, re.MULTILINE)

        # Count only those that are followed by Purely Plant header
        approval_page_count = 0
        for match in matches:
            # Check if this YAML block is followed by Purely Plant header
            start_pos = content.find(match) + len(match)
            remaining = content[start_pos : start_pos + 200]  # Look ahead 200 chars
            if re.search(r"^#\s+Purely Plant GmbH", remaining, re.MULTILINE):
                approval_page_count += 1

        return approval_page_count

    def extract_document_id(self, filename: str) -> str:
        """
        Extract document ID from filename.

        Handles formats like:
        - QA_00.06_CAPA_System_SOP_v1.0_EN.md → QA_00.06
        - QAS-00-006_CAPA_System_SOP_v1.0_EN.md → QAS-00.06
        - PRO_01.01_Mother_Plant_Management_v1.0_EN.md → PRO_01.01
        """
        # Remove extension
        basename = os.path.splitext(filename)[0]

        # Try QA_00.06 pattern
        match = re.match(r"^([A-Z]{2,3}_\d{2}\.\d{2})", basename)
        if match:
            return match.group(1)

        # Try QAS-00-006 pattern (convert to QAS-00.06)
        match = re.match(r"^([A-Z]{3})-(\d{2})-(\d{3})", basename)
        if match:
            prefix = match.group(1)
            first_num = match.group(2)
            second_num = match.group(3).lstrip("0") or "0"
            return f"{prefix}-{first_num}.{second_num}"

        # Try PRO_01.01 pattern (already has dot)
        match = re.match(r"^([A-Z]{3}_\d{2}\.\d{2})", basename)
        if match:
            return match.group(1)

        # Fallback: use first part before first underscore
        parts = basename.split("_")
        if len(parts) >= 2:
            return parts[0]

        return "UNKNOWN"

    def extract_version(self, filename: str) -> str:
        """Extract version from filename."""
        # Look for _v1.0, _v2, etc.
        match = re.search(r"_v(\d+(?:\.\d+)?)", filename)
        return match.group(1) if match else "1.0"

    def extract_title(self, filename: str) -> Tuple[str, str]:
        """Extract title from filename."""
        basename = os.path.splitext(filename)[0]

        # Remove version suffix
        basename = re.sub(r"_v\d+(?:\.\d+)?", "", basename)

        # Try to extract descriptive title
        # Pattern: CODE_TITLE_rest or CODE-TITLE-rest
        # Use a safer regex without ambiguous backreferences
        # Match patterns like: QA_00.06_CAPA_System_SOP_EN
        # Group 1: code, Group 2: title (rest until _EN or _MK or end)
        # Use verbose regex for clarity
        pattern = r"""
            ^                    # start of string
            [A-Z]{2,3}           # 2-3 letter code
            [_-]                 # separator
            \d{2}                # first number
            [._]                 # dot or underscore
            \d{2}                # second number
            [_-]                 # separator
            (.+?)                # title (capture group 1)
            (?:                  # non-capturing group for language suffix
                _EN|_MK          # _EN or _MK
            )?                   # optional
            $                    # end of string
        """
        match = re.match(pattern, basename, re.VERBOSE)
        if match:
            title = match.group(1).replace("_", " ").replace("-", " ")
            # Capitalize first letter of each word
            title = " ".join(word.capitalize() for word in title.split())
            return title, title  # Same for English and Macedonian for now

        # Fallback: use the part after the code
        parts = basename.split("_")
        if len(parts) >= 3:
            title = " ".join(parts[2:])
            title = title.replace("_", " ").replace("-", " ")
            return title, title

        return "Standard Operating Procedure", "Стандардна оперативна процедура"

    def remove_duplicate_approval_pages(
        self, content: str, file_path: Path
    ) -> Tuple[str, int]:
        """
        Remove duplicate approval pages from content.

        Returns: (cleaned_content, duplicates_removed)
        """
        # Find all YAML front matter blocks
        yaml_pattern = r"^---\s*\n(?:.*?\n)*?---\s*\n"
        yaml_matches = list(re.finditer(yaml_pattern, content, re.MULTILINE))

        if len(yaml_matches) <= 1:
            return content, 0  # No duplicates

        # Find which YAML blocks are followed by Purely Plant header
        approval_page_starts = []
        for match in yaml_matches:
            start_pos = match.start()
            end_pos = match.end()
            # Check if followed by Purely Plant header
            next_chars = content[end_pos : end_pos + 100]
            if re.search(r"^#\s+Purely Plant GmbH", next_chars, re.MULTILINE):
                # Find the end of this approval page (next major section or next YAML)
                next_yaml = None
                for other_match in yaml_matches:
                    if other_match.start() > end_pos:
                        next_yaml = other_match
                        break

                if next_yaml:
                    # Approval page ends at start of next YAML
                    approval_page_starts.append((start_pos, next_yaml.start()))
                else:
                    # Approval page continues to end of content with another page
                    # Look for next major section marker
                    section_pattern = r"\n#{1,6}\s+[A-Z]"
                    section_match = re.search(
                        section_pattern, content[end_pos:], re.MULTILINE
                    )
                    if section_match:
                        page_end = end_pos + section_match.start()
                        approval_page_starts.append((start_pos, page_end))
                    else:
                        # Whole rest of document is approval page (shouldn't happen)
                        approval_page_starts.append((start_pos, len(content)))

        if len(approval_page_starts) <= 1:
            return content, 0  # Only one approval page found

        # Keep the first approval page, remove duplicates
        first_start, first_end = approval_page_starts[0]
        result_parts = []

        # Add content before first approval page
        if first_start > 0:
            result_parts.append(content[:first_start])

        # Add first approval page
        result_parts.append(content[first_start:first_end])

        # Skip duplicate approval pages, keep content after them
        for i in range(1, len(approval_page_starts)):
            current_start, current_end = approval_page_starts[i]
            # Find the next approval page start (or end of content)
            next_start = (
                approval_page_starts[i + 1][0]
                if i + 1 < len(approval_page_starts)
                else len(content)
            )

            # If there's content between this duplicate and the next one, keep it
            if next_start > current_end:
                result_parts.append(content[current_end:next_start])

        # Add any remaining content after last approval page
        last_end = approval_page_starts[-1][1]
        if last_end < len(content):
            result_parts.append(content[last_end:])

        cleaned_content = "".join(result_parts)
        duplicates_removed = len(approval_page_starts) - 1

        return cleaned_content, duplicates_removed

    def update_yaml_front_matter(self, content: str, file_path: Path) -> str:
        """
        Update YAML front matter with correct document ID and metadata.

        Returns: Updated content with corrected YAML front matter.
        """
        # Find YAML front matter
        yaml_pattern = r"^(---\s*\n)(.*?)(\n---\s*\n)"
        match = re.search(yaml_pattern, content, re.MULTILINE | re.DOTALL)

        if not match:
            return content  # No YAML front matter found

        yaml_start = match.group(1)
        yaml_content = match.group(2)
        yaml_end = match.group(3)

        # Extract filename metadata
        doc_id = self.extract_document_id(file_path.name)
        version = self.extract_version(file_path.name)
        title_en, title_mk = self.extract_title(file_path.name)

        # Today's date for effective_date
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        # Update YAML content
        yaml_lines = yaml_content.split("\n")
        updated_yaml = []

        # Track which fields we've updated
        fields_updated = set()

        for line in yaml_lines:
            if line.startswith("document_id:"):
                updated_yaml.append(f'document_id: "{doc_id}"')
                fields_updated.add("document_id")
            elif line.startswith("version:"):
                updated_yaml.append(f'version: "{version}"')
                fields_updated.add("version")
            elif line.startswith("title_en:"):
                updated_yaml.append(f'title_en: "{title_en}"')
                fields_updated.add("title_en")
            elif line.startswith("title_mk:"):
                updated_yaml.append(f'title_mk: "{title_mk}"')
                fields_updated.add("title_mk")
            elif line.startswith("effective_date:"):
                updated_yaml.append(f'effective_date: "{today}"')
                fields_updated.add("effective_date")
            else:
                updated_yaml.append(line)

        # Add missing fields
        if "document_id" not in fields_updated:
            updated_yaml.append(f'document_id: "{doc_id}"')
        if "version" not in fields_updated:
            updated_yaml.append(f'version: "{version}"')
        if "title_en" not in fields_updated:
            updated_yaml.append(f'title_en: "{title_en}"')
        if "title_mk" not in fields_updated:
            updated_yaml.append(f'title_mk: "{title_mk}"')
        if "effective_date" not in fields_updated:
            updated_yaml.append(f'effective_date: "{today}"')

        # Ensure required fields are present
        required_fields = ["copy_type", "document_type"]
        for field in required_fields:
            if not any(line.startswith(f"{field}:") for line in updated_yaml):
                if field == "copy_type":
                    updated_yaml.append('copy_type: "controlled"')
                elif field == "document_type":
                    updated_yaml.append('document_type: "SOP"')

        # Reconstruct content
        new_yaml_content = "\n".join(updated_yaml)
        new_content = (
            content[: match.start()]
            + yaml_start
            + new_yaml_content
            + yaml_end
            + content[match.end() :]
        )

        return new_content

    def update_document_id_in_header(self, content: str, file_path: Path) -> str:
        """
        Update document ID in the header section after approval page.

        Looks for: **Document ID:** UNKNOWN v.1.0
        Updates to: **Document ID:** [correct_id] v.[version]
        """
        doc_id = self.extract_document_id(file_path.name)
        version = self.extract_version(file_path.name)

        # Pattern for header with UNKNOWN - use named groups to avoid backreference issues
        # Escape the doc_id for regex special characters
        safe_doc_id = re.escape(doc_id)
        safe_version = re.escape(version)

        # First, fix UNKNOWN
        pattern1 = re.compile(
            r"(\*\*Document ID:\*\*\s*)UNKNOWN(\s*v\.\d+(?:\.\d+)?)", re.MULTILINE
        )
        content = pattern1.sub(rf"\g<1>{doc_id}\g<2>", content)

        # Also fix if it has wrong version
        pattern2 = re.compile(
            r"(\*\*Document ID:\*\*\s*[A-Z0-9._-]+)(\s*v\.)\d+(?:\.\d+)?", re.MULTILINE
        )
        content = pattern2.sub(rf"\g<1>\g<2>{version}", content)

        return content

    def process_file(self, file_path: Path, dry_run: bool = False) -> Dict:
        """
        Process a single markdown file.

        Returns: Dictionary with processing results.
        """
        result = {
            "file": str(file_path),
            "has_duplicates": False,
            "duplicates_removed": 0,
            "document_id_updated": False,
            "backup_created": False,
            "error": None,
        }

        try:
            # Read content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for duplicates
            approval_page_count = self.count_approval_pages(content)
            result["has_duplicates"] = approval_page_count > 1

            if not result["has_duplicates"]:
                # Still check if document ID needs updating
                if (
                    "UNKNOWN" in content
                    or self.extract_document_id(file_path.name) != "UNKNOWN"
                ):
                    # Update YAML and header
                    new_content = self.update_yaml_front_matter(content, file_path)
                    new_content = self.update_document_id_in_header(
                        new_content, file_path
                    )

                    if new_content != content and not dry_run:
                        # Create backup
                        backup_path = file_path.with_suffix(
                            f".backup.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                        )
                        shutil.copy2(file_path, backup_path)
                        result["backup_created"] = True
                        self.stats["backups_created"].append(str(backup_path))

                        # Write updated content
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        result["document_id_updated"] = True

                return result

            # Has duplicates - fix them
            result["duplicates_removed"] = approval_page_count - 1

            if dry_run:
                return result

            # Create backup
            backup_path = file_path.with_suffix(
                f".backup.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            )
            shutil.copy2(file_path, backup_path)
            result["backup_created"] = True
            self.stats["backups_created"].append(str(backup_path))

            # Remove duplicate approval pages
            cleaned_content, duplicates_removed = self.remove_duplicate_approval_pages(
                content, file_path
            )

            # Update YAML front matter
            cleaned_content = self.update_yaml_front_matter(cleaned_content, file_path)

            # Update document ID in header
            cleaned_content = self.update_document_id_in_header(
                cleaned_content, file_path
            )

            # Write cleaned content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cleaned_content)

            result["duplicates_removed"] = duplicates_removed
            result["document_id_updated"] = True

            return result

        except Exception as e:
            error_msg = f"Error processing {file_path.name}: {str(e)}"
            result["error"] = error_msg
            self.stats["errors"].append(error_msg)
            return result

    def scan_directory(self, directory: Path, pattern: str = "*.md") -> List[Path]:
        """Scan directory for markdown files."""
        files = []
        if directory.exists():
            for file_path in directory.rglob(pattern):
                # Skip backup files
                if "backup" in file_path.name.lower():
                    continue
                files.append(file_path)
        return files

    def run(self, directories: List[str] = None, dry_run: bool = False) -> Dict:
        """
        Run the duplicate approval page fixer.

        Args:
            directories: List of directory paths to scan (relative to base_dir)
            dry_run: If True, only show what would be fixed without making changes

        Returns:
            Statistics dictionary
        """
        if directories is None:
            directories = ["01_QUALITY_ASSURANCE", "04_QUALITY_TESTING", "sops_created"]

        print(f"\n{'=' * 80}")
        print("DUPLICATE APPROVAL PAGE FIXER")
        print(f"{'=' * 80}\n")

        if dry_run:
            print("⚠️  DRY RUN MODE - No changes will be made\n")

        print("Scanning directories:")
        for dir_name in directories:
            dir_path = self.base_dir / dir_name
            if dir_path.exists():
                print(f"  - {dir_name}")
            else:
                print(f"  - {dir_name} (NOT FOUND)")

        print()

        # Scan for files
        all_files = []
        for dir_name in directories:
            dir_path = self.base_dir / dir_name
            if dir_path.exists():
                files = self.scan_directory(dir_path)
                all_files.extend(files)

        self.stats["total_files"] = len(all_files)
        print(f"Found {len(all_files)} markdown files to check\n")

        # Process files
        for i, file_path in enumerate(all_files, 1):
            print(
                f"[{i}/{len(all_files)}] Processing: {file_path.relative_to(self.base_dir)}"
            )

            result = self.process_file(file_path, dry_run)

            if result["error"]:
                print(f"  ✗ Error: {result['error']}")
                self.stats["files_skipped"] += 1
            elif result["has_duplicates"]:
                if dry_run:
                    print(
                        f"  ⚠️  Would remove {result['duplicates_removed']} duplicate approval page(s)"
                    )
                    self.stats["files_with_duplicates"] += 1
                else:
                    print(
                        f"  ✓ Removed {result['duplicates_removed']} duplicate approval page(s)"
                    )
                    self.stats["files_with_duplicates"] += 1
                    self.stats["files_fixed"] += 1
            elif result["document_id_updated"]:
                if dry_run:
                    print(f"  ⚠️  Would update document ID")
                else:
                    print(f"  ✓ Updated document ID")
                    self.stats["files_fixed"] += 1
            else:
                print(f"  ✓ OK (no duplicates)")
                self.stats["files_skipped"] += 1

        return self.stats

    def print_report(self):
        """Print processing report."""
        print(f"\n{'=' * 80}")
        print("PROCESSING REPORT")
        print(f"{'=' * 80}\n")

        print(f"Total files scanned:      {self.stats['total_files']}")
        print(f"Files with duplicates:    {self.stats['files_with_duplicates']}")
        print(f"Files fixed:              {self.stats['files_fixed']}")
        print(f"Files skipped (no issues): {self.stats['files_skipped']}")
        print(f"Backups created:          {len(self.stats['backups_created'])}")
        print(f"Errors encountered:       {len(self.stats['errors'])}\n")

        if self.stats["backups_created"]:
            print("Backup files created:")
            for backup in self.stats["backups_created"][:5]:  # Show first 5
                print(f"  - {backup}")
            if len(self.stats["backups_created"]) > 5:
                print(f"  ... and {len(self.stats['backups_created']) - 5} more")
            print()

        if self.stats["errors"]:
            print("Errors:")
            for error in self.stats["errors"][:5]:  # Show first 5
                print(f"  - {error}")
            if len(self.stats["errors"]) > 5:
                print(f"  ... and {len(self.stats['errors']) - 5} more")
            print()

        if self.stats["files_with_duplicates"] > 0:
            print("✅ Duplicate approval pages have been fixed!")
            print("   Each file now has exactly one approval page at the beginning.")
        else:
            print("✅ No duplicate approval pages found.")

        print(f"\n{'=' * 80}")
        print("DONE")
        print(f"{'=' * 80}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fix duplicate approval pages in markdown documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run           # Show what would be fixed
  %(prog)s                     # Apply fixes to all directories
  %(prog)s --dirs 01_QUALITY_ASSURANCE  # Only fix specific directory
  %(prog)s --help              # Show this help message
        """,
    )

    parser.add_argument(
        "--dirs",
        nargs="+",
        default=["01_QUALITY_ASSURANCE", "04_QUALITY_TESTING", "sops_created"],
        help="Directories to scan (default: all QMS directories)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes",
    )

    parser.add_argument(
        "--base-dir", default=".", help="Base directory (default: current directory)"
    )

    args = parser.parse_args()

    # Set up fixer
    base_dir = Path(args.base_dir).resolve()
    fixer = ApprovalPageFixer(base_dir)

    # Run fixer
    try:
        stats = fixer.run(args.dirs, args.dry_run)
        fixer.print_report()

        # Exit code
        if not args.dry_run and stats["files_fixed"] > 0:
            sys.exit(0)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
