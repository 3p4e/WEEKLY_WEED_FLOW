#!/usr/bin/env python3
"""
Document ID Migration Tool for Cannabis EU GMP QMS Creator
Migrates legacy document IDs to hierarchical GMP format.

Legacy format: QAS-00-006, QC-01-001
Hierarchical format: QA_00.06_v1, QC_01.01_A01_v1

Usage:
    python migrate_document_ids.py [--dry-run] [--backup]
"""

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml


class DocumentIDMigrator:
    """Migrate document IDs from legacy to hierarchical format."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.registry_path = base_dir / "config" / "document_registry.yaml"
        self.backup_dir = base_dir / "migration_backup"
        self.log_file = base_dir / "migration_report.md"

        # Load registry
        self.registry = self._load_registry()

        # Initialize mapping dictionaries
        self.direct_mappings = {}  # exact filename -> new_id
        self.pattern_mappings = {}  # legacy_pattern -> new_id (e.g., "QAS-00-006_" -> "QA_00.06_v1")
        self.legacy_id_mappings = {}  # legacy_id -> new_id (e.g., "QAS-00-006" -> "QA_00.06_v1")

        # Parse mappings
        self._parse_mappings()

        # Statistics
        self.stats = {
            "files_renamed": 0,
            "files_updated": 0,
            "references_updated": 0,
            "backups_created": 0,
            "errors": 0,
        }

        # Log entries
        self.log_entries: List[str] = []

    def _load_registry(self) -> Dict:
        """Load document registry YAML."""
        if not self.registry_path.exists():
            raise FileNotFoundError(f"Registry not found: {self.registry_path}")

        with open(self.registry_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _parse_mappings(self) -> None:
        """Parse mappings from registry into separate dictionaries."""
        if "file_mapping" in self.registry:
            # Direct mapping from file_mapping section (exact filenames)
            for legacy_path, new_id in self.registry["file_mapping"].items():
                filename = Path(legacy_path).name
                self.direct_mappings[filename] = new_id
                # Also add to legacy_id_mappings for quick lookup
                legacy_id = self.extract_legacy_id_from_filename(filename)
                if legacy_id:
                    self.legacy_id_mappings[legacy_id] = new_id

        # Also extract from families for pattern-based mappings
        if "families" in self.registry:
            for family_id, family_data in self.registry["families"].items():
                if "sops" in family_data:
                    for sop_id, sop_data in family_data["sops"].items():
                        if "original_id" in sop_data:
                            legacy_id = sop_data["original_id"]
                            # Create pattern mapping (legacy_id + underscore)
                            pattern = f"{legacy_id}_"
                            new_id = f"{sop_id}_v1"
                            self.pattern_mappings[pattern] = new_id
                            # Also add to legacy_id_mappings
                            self.legacy_id_mappings[legacy_id] = new_id

                        # Process annexes
                        if "annexes" in sop_data:
                            for annex_id, annex_data in sop_data["annexes"].items():
                                # Derive legacy annex ID from parent
                                if "original_id" in sop_data:
                                    legacy_parent = sop_data["original_id"]
                                    # Find annex number from annex_id (e.g., QA_00.06_A01 -> A01)
                                    annex_match = re.search(
                                        r"A(\d+)$", annex_id.split(".")[-1]
                                    )
                                    if annex_match:
                                        annex_num = annex_match.group(1)
                                        legacy_annex = f"{legacy_parent}_A{annex_num}"
                                        pattern = f"{legacy_annex}_"
                                        new_id = f"{annex_id}_v1"
                                        self.pattern_mappings[pattern] = new_id
                                        # Also add to legacy_id_mappings
                                        self.legacy_id_mappings[legacy_annex] = new_id

    def find_legacy_files(self) -> List[Path]:
        """Find all files with legacy document IDs, excluding backups."""
        legacy_files = []

        # Patterns for legacy document IDs
        legacy_patterns = [
            r"QAS-\d{2}-\d{3}",  # QAS-00-006
            r"QC-\d{2}-\d{3}",  # QC-01-001
            r"QA-\d{2}-\d{3}",  # QA-00-001
            r"PROD-\d{2}-\d{3}",  # PROD-01-001
            r"PRO-CULT-[A-Z]{3}-\d{3}",  # PRO-CULT-CUR-001
            r"PRO-LOG-[A-Z]{3}-\d{3}",  # PRO-LOG-TRN-001
            r"PRO-FACI-[A-Z]{3}-\d{3}",  # PRO-FACI-DRY-001
            r"RES-RND-[A-Z]{3}-\d{3}",  # RES-RND-PHE-001
            r"QCS-QC-[A-Z]{3,4}-\d{3}",  # QCS-QC-OOS-001, QCS-QC-SPEC-001
            r"QAS-DOC-[A-Z]{3}-\d{3}",  # QAS-DOC-MEM-001
            r"MAT-\d{2}-\d{3}",  # MAT-00-004
            r"HRM-\d{2}-\d{3}",  # HRM-00-001
            r"EQU-\d{2}-\d{3}",  # EQU-00-001
            r"SAN-\d{2}-\d{3}",  # SAN-00-001
            r"VAL-\d{2}-\d{3}",  # VAL-00-001
            r"REC-\d{2}-\d{3}",  # REC-00-001
            r"PRO-\d{2}-\d{3}",  # PRO-03-001
            r"QCS-\d{2}-\d{3}",  # QCS-00-003
        ]

        # Search in main document directories (only primary SOP locations)
        search_dirs = [
            self.base_dir / "01_QUALITY_ASSURANCE",
            self.base_dir / "04_QUALITY_TESTING",
            self.base_dir / "sops_created",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for file_path in search_dir.rglob("*.md"):
                filename = file_path.name
                file_path_str = str(file_path)

                # Skip backup files
                if "backup" in filename.lower() or ".backup." in file_path_str.lower():
                    continue

                # Check if filename contains any legacy pattern
                for pattern in legacy_patterns:
                    if re.search(pattern, filename):
                        legacy_files.append(file_path)
                        break

        return legacy_files

    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of a file."""
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(parents=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        self.stats["backups_created"] += 1

        return backup_path

    def extract_legacy_id_from_filename(self, filename: str) -> Optional[str]:
        """Extract legacy document ID from filename."""
        patterns = [
            (r"(QAS-\d{2}-\d{3})", "QAS"),  # QAS-00-006
            (r"(QC-\d{2}-\d{3})", "QC"),  # QC-01-001
            (r"(QA-\d{2}-\d{3})", "QA"),  # QA-00-001
            (r"(PRO-\d{2}-\d{3})", "PRO"),  # PRO-03-001
            (r"(MAT-\d{2}-\d{3})", "MAT"),  # MAT-00-004
            (r"(HRM-\d{2}-\d{3})", "HRM"),  # HRM-00-001
            (r"(EQU-\d{2}-\d{3})", "EQU"),  # EQU-00-001
            (r"(SAN-\d{2}-\d{3})", "SAN"),  # SAN-00-001
            (r"(VAL-\d{2}-\d{3})", "VAL"),  # VAL-00-001
            (r"(REC-\d{2}-\d{3})", "REC"),  # REC-00-001
            (r"(QCS-\d{2}-\d{3})", "QCS"),  # QCS-00-003
            (r"(PROD-\d{2}-\d{3})", "PROD"),  # PROD-01-001
            (r"(PRO-CULT-[A-Z]{3}-\d{3})", "PRO-CULT"),  # PRO-CULT-CUR-001
            (r"(PRO-LOG-[A-Z]{3}-\d{3})", "PRO-LOG"),  # PRO-LOG-TRN-001
            (r"(PRO-FACI-[A-Z]{3}-\d{3})", "PRO-FACI"),  # PRO-FACI-DRY-001
            (r"(RES-RND-[A-Z]{3}-\d{3})", "RES-RND"),  # RES-RND-PHE-001
            (r"(QCS-QC-[A-Z]{3,4}-\d{3})", "QCS-QC"),  # QCS-QC-OOS-001, QCS-QC-SPEC-001
            (r"(QAS-DOC-[A-Z]{3}-\d{3})", "QAS-DOC"),  # QAS-DOC-MEM-001
            (r"([A-Z]{3,4}-\d{2}-\d{3})", "GENERIC"),  # Any XXX-00-000
            (
                r"([A-Z]{3,4}-[A-Z]{3,4}-[A-Z]{3}-\d{3})",
                "EXTENDED",
            ),  # Any XXX-YYY-ZZZ-000
        ]

        for pattern, _ in patterns:
            match = re.search(pattern, filename)
            if match:
                return match.group(1)

        return None

    def generate_legacy_id_variants(self, legacy_id: str) -> List[str]:
        """Generate possible variants of a legacy document ID for matching."""
        variants = []

        # Basic legacy ID (e.g., QAS-00-006)
        variants.append(legacy_id)

        # Generate dot variants (e.g., QAS-00-006 -> QAS-00.6)
        # Pattern: XXX-YY-ZZZ -> XXX-YY.Z
        dot_match = re.match(r"([A-Z]{2,4})-(\d{2})-(\d{3})", legacy_id)
        if dot_match:
            prefix = dot_match.group(1)
            middle = dot_match.group(2)
            last = dot_match.group(3)
            # Convert last 3 digits to single digit (006 -> 6)
            last_digit = str(int(last))
            dot_variant = f"{prefix}-{middle}.{last_digit}"
            variants.append(dot_variant)

            # Also add annex variants for dot format
            if "_A" in legacy_id:
                annex_part = legacy_id.split("_A")[1]
                variants.append(f"{dot_variant}_A{annex_part}")
            else:
                for i in range(1, 10):
                    variants.append(f"{dot_variant}_A{i:02d}")

        # Try to parse for annex
        # Pattern: QAS-00-006_A01
        if "_A" in legacy_id:
            # Already has annex, also add without annex
            base_id = legacy_id.split("_A")[0]
            variants.append(base_id)
        else:
            # No annex, add with annex patterns A01-A99
            for i in range(1, 10):
                variants.append(f"{legacy_id}_A{i:02d}")

        # Add version patterns
        for variant in variants.copy():
            variants.append(f"{variant} v.1.0")
            variants.append(f"{variant}_v1.0")
            variants.append(f"{variant}-V.1.0")

        return list(set(variants))  # Remove duplicates

    def get_new_document_id(self, legacy_id: str, filename: str) -> Optional[str]:
        """Get new hierarchical ID for a legacy document ID."""
        # 1. Try exact filename match in direct mappings
        if filename in self.direct_mappings:
            return self.direct_mappings[filename]

        # 2. Try pattern matching (legacy_id_ pattern in filename)
        # Sort by length descending to ensure longest match (e.g. annex) is found first
        for pattern, new_id in sorted(
            self.pattern_mappings.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if pattern in filename:
                return new_id

        # 3. Try direct legacy ID match
        if legacy_id in self.legacy_id_mappings:
            return self.legacy_id_mappings[legacy_id]

        # 4. Fallback: try to find in registry families (should be covered by mappings)
        if "families" in self.registry:
            for family_id, family_data in self.registry["families"].items():
                if "sops" in family_data:
                    for sop_id, sop_data in family_data["sops"].items():
                        if (
                            "original_id" in sop_data
                            and sop_data["original_id"] == legacy_id
                        ):
                            # Return with version suffix
                            return f"{sop_id}_v1"

        return None

    def generate_new_filename(self, old_path: Path, new_id: str) -> Path:
        """Generate new filename with hierarchical ID using smarter pattern matching."""
        old_name = old_path.name

        # Patterns for legacy document IDs with optional annex
        # QAS-00-006, QAS-00-006_A01, QC-01-001, QC-01-001_A01, etc.
        legacy_patterns = [
            r"([A-Z]{2,4}-\d{2}-\d{3})(?:_A\d{2})?",  # QAS-00-006 or QAS-00-006_A01
        ]

        # Try each pattern
        matched = False
        new_name = old_name

        for pattern in legacy_patterns:
            match = re.search(pattern, old_name)
            if match:
                full_legacy_match = match.group(0)  # The entire matched string
                # Remove version suffix from new_id for replacement
                new_id_base = new_id.split("_v")[0] if "_v" in new_id else new_id
                new_name = old_name.replace(full_legacy_match, new_id_base)
                matched = True
                break

        if not matched:
            # Fallback: extract legacy ID and try simple replacement
            legacy_id = self.extract_legacy_id_from_filename(old_name)
            if legacy_id:
                new_id_base = new_id.split("_v")[0] if "_v" in new_id else new_id
                new_name = old_name.replace(legacy_id, new_id_base)
            else:
                # Final fallback: use new ID as filename
                suffix = old_path.suffix
                new_name = f"{new_id}{suffix}"

        return old_path.parent / new_name

    def update_file_content(self, file_path: Path, legacy_id: str, new_id: str) -> int:
        """Update all references in file content using legacy ID variants."""
        updates_made = 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # Generate all possible variants of the legacy ID
            legacy_variants = self.generate_legacy_id_variants(legacy_id)

            # Update document_id in frontmatter for all variants
            if "document_id:" in content:
                for variant in legacy_variants:
                    pattern = rf'document_id:\s*["\']?{re.escape(variant)}["\']?'
                    if re.search(pattern, content):
                        content = re.sub(pattern, f'document_id: "{new_id}"', content)

            # Update all occurrences of each legacy variant
            for variant in legacy_variants:
                # Pattern for standalone legacy IDs (not in filenames)
                legacy_pattern = re.compile(r"\b" + re.escape(variant) + r"\b")
                content = legacy_pattern.sub(new_id, content)

                # Update references with version numbers
                legacy_with_version = re.compile(
                    r"\b" + re.escape(variant) + r"\s*v\.?\s*\d+\.\d+\b"
                )
                content = legacy_with_version.sub(new_id, content)

                # Update "SOP Reference:" lines
                content = re.sub(
                    rf"SOP Reference:\s*{re.escape(variant)}",
                    f"SOP Reference: {new_id}",
                    content,
                )

                # Update "FORM VERSION:" lines
                content = re.sub(
                    rf"FORM VERSION:\s*{re.escape(variant)}",
                    f"FORM VERSION: {new_id}",
                    content,
                )

            # Check if changes were made
            if content != original_content:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # Count total changes across all variants
                changes = 0
                for variant in legacy_variants:
                    changes += self._count_changes(
                        original_content, content, variant, new_id
                    )
                updates_made += changes

        except Exception as e:
            self.log_entries.append(f"ERROR updating {file_path.name}: {str(e)}")
            self.stats["errors"] += 1

        return updates_made

    def _count_changes(
        self, original: str, updated: str, legacy_id: str, new_id: str
    ) -> int:
        """Count how many replacements were made."""
        original_count = len(re.findall(r"\b" + re.escape(legacy_id) + r"\b", original))
        updated_count = len(re.findall(r"\b" + re.escape(new_id) + r"\b", updated))

        # Also count pattern matches
        patterns = [
            rf'document_id:\s*["\']?{re.escape(legacy_id)}["\']?',
            rf"SOP Reference:\s*{re.escape(legacy_id)}",
            rf"FORM VERSION:\s*{re.escape(legacy_id)}",
        ]

        pattern_changes = 0
        for pattern in patterns:
            original_matches = len(re.findall(pattern, original))
            updated_matches = len(
                re.findall(pattern.replace(legacy_id, new_id), updated)
            )
            pattern_changes += original_matches - updated_matches

        return max(0, pattern_changes)

    def rename_file(self, old_path: Path, new_path: Path) -> bool:
        """Rename a file with conflict resolution."""
        try:
            if new_path.exists():
                # Add timestamp to avoid conflict
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = f"{new_path.stem}_{timestamp}{new_path.suffix}"
                new_path = new_path.parent / new_name

            old_path.rename(new_path)
            return True

        except Exception as e:
            self.log_entries.append(f"ERROR renaming {old_path.name}: {str(e)}")
            self.stats["errors"] += 1
            return False

    def should_rename_file(self, filename: str, legacy_id: str, new_id: str) -> bool:
        """Determine if a file should be renamed based on its content and purpose.

        Some files (like implementation guides, summaries, etc.) should keep their
        descriptive filenames rather than being renamed to the document ID.
        """
        # First check: if this is a direct mapping from file_mapping, always rename
        # These are core SOPs and forms that need hierarchical filenames
        if filename in self.direct_mappings:
            return True

        # Patterns that indicate this is a supporting document, not an SOP
        supporting_patterns = [
            "IMPLEMENTATION_COMPLETE",
            "QUICK_REFERENCE_GUIDE",
            "QMS_READINESS_CHECK",
            "REAL_PRODUCTION_PILOT_TEST",
            "TESTING_SUMMARY",
            "PRODUCTION_READY_SYSTEM_OVERVIEW",
            "IMPLEMENTATION_GUIDE",
            "SUMMARY",
            "OVERVIEW",
            "CHECKLIST",
            "GUIDE",
        ]

        filename_upper = filename.upper()
        for pattern in supporting_patterns:
            if pattern in filename_upper:
                return False

        # Default: rename SOPs and forms
        return True

    def migrate(
        self, dry_run: bool = False, backup: bool = True, should_rename: bool = True
    ) -> Dict:
        """Execute the migration."""
        self.log_entries.append("# Document ID Migration Report")
        self.log_entries.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log_entries.append(f"Dry run: {dry_run}")
        self.log_entries.append(f"Backup: {backup}")
        self.log_entries.append("")

        # Find all legacy files
        legacy_files = self.find_legacy_files()
        print(f"Found {len(legacy_files)} files with legacy document IDs:")
        for i, file_path in enumerate(legacy_files, 1):
            print(f"  {i}. {file_path.name}")
        print()
        self.log_entries.append(f"Found {len(legacy_files)} files with legacy IDs")
        self.log_entries.append("")

        # Process each file
        for file_path in legacy_files:
            legacy_id = self.extract_legacy_id_from_filename(file_path.name)

            if not legacy_id:
                self.log_entries.append(
                    f"SKIP: Could not extract legacy ID from {file_path.name}"
                )
                if dry_run:
                    print(f"SKIP: Could not extract legacy ID from {file_path.name}")
                continue

            new_id = self.get_new_document_id(legacy_id, file_path.name)

            if not new_id:
                self.log_entries.append(
                    f"SKIP: No mapping found for {legacy_id} ({file_path.name})"
                )
                if dry_run:
                    print(f"SKIP: No mapping found for {legacy_id} ({file_path.name})")
                continue

            if dry_run:
                print(f"MAP: {legacy_id} -> {new_id} ({file_path.name})")

            # Create backup
            backup_path = None
            if backup and not dry_run:
                backup_path = self.create_backup(file_path)

            # Determine if this file should be renamed
            file_should_rename = should_rename and self.should_rename_file(
                file_path.name, legacy_id, new_id
            )

            # Generate new filename (only if renaming is enabled and appropriate)
            new_path = None
            if file_should_rename:
                new_path = self.generate_new_filename(file_path, new_id)
            else:
                new_path = file_path  # Keep same path

            if dry_run:
                if file_should_rename:
                    print(f"RENAME: Will rename {file_path.name} -> {new_path.name}")
                else:
                    if not should_rename:
                        print("RENAME: Skipping rename (should_rename=False)")
                    else:
                        print(
                            f"RENAME: Keeping filename {file_path.name} (supporting document)"
                        )

            # Log planned changes
            self.log_entries.append(f"## {file_path.name}")
            self.log_entries.append(f"- Legacy ID: {legacy_id}")
            self.log_entries.append(f"- New ID: {new_id}")
            if file_should_rename:
                self.log_entries.append(f"- New filename: {new_path.name}")
                self.log_entries.append("- Rename: Yes (SOP/Form)")
            else:
                self.log_entries.append(f"- New filename: {file_path.name} (unchanged)")
                self.log_entries.append("- Rename: No (supporting document)")

            if backup_path:
                self.log_entries.append(f"- Backup: {backup_path.name}")

            if not dry_run:
                # Update file content
                updates = self.update_file_content(file_path, legacy_id, new_id)

                if updates > 0:
                    self.stats["references_updated"] += updates
                    self.stats["files_updated"] += 1
                    self.log_entries.append(f"- Content updates: {updates}")

                # Rename file (if enabled and appropriate for this file)
                if file_should_rename:
                    if self.rename_file(file_path, new_path):
                        self.stats["files_renamed"] += 1
                        self.log_entries.append("- Renamed successfully")
                    else:
                        self.log_entries.append("- Rename failed")
                else:
                    if not should_rename:
                        self.log_entries.append(
                            "- Rename skipped (should_rename=False)"
                        )
                    else:
                        self.log_entries.append(
                            "- Rename skipped (supporting document)"
                        )

            self.log_entries.append("")

        # Generate summary
        self._generate_summary()

        # Write log file
        if not dry_run:
            self._write_log_file()

        return self.stats

    def _generate_summary(self):
        """Generate migration summary."""
        self.log_entries.append("## Migration Summary")
        self.log_entries.append("")
        self.log_entries.append(f"- Files renamed: {self.stats['files_renamed']}")
        self.log_entries.append(f"- Files updated: {self.stats['files_updated']}")
        self.log_entries.append(
            f"- References updated: {self.stats['references_updated']}"
        )
        self.log_entries.append(f"- Backups created: {self.stats['backups_created']}")
        self.log_entries.append(f"- Errors: {self.stats['errors']}")

        if self.stats["errors"] == 0:
            self.log_entries.append("\n✅ Migration completed successfully!")
        else:
            self.log_entries.append(
                f"\n⚠️  Migration completed with {self.stats['errors']} errors."
            )

    def _write_log_file(self):
        """Write migration report to file."""
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(self.log_entries))

        print(f"\nMigration report saved to: {self.log_file}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate document IDs from legacy to hierarchical format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backups before making changes (default: True)",
    )
    parser.add_argument(
        "--no-backup", action="store_false", dest="backup", help="Do not create backups"
    )
    parser.add_argument(
        "--no-rename",
        action="store_false",
        dest="should_rename",
        default=True,
        help="Do not rename files, only update content",
    )

    args = parser.parse_args()

    # Get base directory
    base_dir = Path(__file__).parent.parent

    try:
        # Initialize migrator
        migrator = DocumentIDMigrator(base_dir)

        print("=" * 60)
        print("Document ID Migration Tool")
        print("=" * 60)
        print(f"Base directory: {base_dir}")
        print(f"Registry file: {migrator.registry_path}")
        print(f"Dry run: {args.dry_run}")
        print(f"Backup: {args.backup}")
        print("=" * 60)
        print()

        if args.dry_run:
            print("DRY RUN MODE: No changes will be made")
            print()

        # Execute migration
        stats = migrator.migrate(
            dry_run=args.dry_run, backup=args.backup, should_rename=args.should_rename
        )

        # Print summary to console
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"Files renamed: {stats['files_renamed']}")
        print(f"Files updated: {stats['files_updated']}")
        print(f"References updated: {stats['references_updated']}")
        print(f"Backups created: {stats['backups_created']}")
        print(f"Errors: {stats['errors']}")

        if not args.dry_run:
            print(f"\nReport saved to: {migrator.log_file}")

        if stats["errors"] > 0:
            sys.exit(1)

    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
