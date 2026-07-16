#!/usr/bin/env python3
"""
Template Scanner for Cannabis EU GMP QMS Creator
Finds and categorizes template files for processing
"""

from pathlib import Path
from typing import List, Dict, Set
import re


class TemplateScanner:
    """Scanner for finding template files to process."""

    def __init__(self, base_dir: Path):
        """
        Initialize template scanner.

        Args:
            base_dir: Base directory to scan for templates
        """
        self.base_dir = base_dir
        self.templates: List[Path] = []
        self.categories: Dict[str, List[Path]] = {}

    def scan(self, file_pattern: str = "*.txt", exclude_dirs: List[str] = None) -> List[Path]:
        """
        Scan for template files.

        Args:
            file_pattern: Glob pattern for files (default: *.txt)
            exclude_dirs: List of directory names to exclude

        Returns:
            List of template file paths
        """
        if exclude_dirs is None:
            exclude_dirs = ['output', 'venv', 'venv_work', '__pycache__', '.git', 'data']

        self.templates = []

        for file_path in self.base_dir.rglob(file_pattern):
            # Skip excluded directories
            if any(excl in file_path.parts for excl in exclude_dirs):
                continue

            # Skip non-template files
            if self._is_template_file(file_path):
                self.templates.append(file_path)

        # Sort by path for consistent ordering
        self.templates.sort()

        return self.templates

    def _is_template_file(self, file_path: Path) -> bool:
        """
        Check if file is a template (contains placeholders).

        Args:
            file_path: Path to file

        Returns:
            True if file contains placeholders
        """
        # Skip certain file types
        skip_files = [
            'README', 'CHANGELOG', 'LICENSE', 'HISTORY',
            '_scan_results', '_status', '_review', '_index'
        ]

        filename_upper = file_path.stem.upper()
        if any(skip in filename_upper for skip in skip_files):
            return False

        # Quick check: does file contain any [PLACEHOLDER] patterns?
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read first 5000 characters to check for placeholders
                content = f.read(5000)
                return bool(re.search(r'\[([A-Z][A-Z0-9_\-\s]+)\]', content))
        except Exception:
            return False

    def categorize(self) -> Dict[str, List[Path]]:
        """
        Categorize templates by their location/type.

        Returns:
            Dictionary of category name -> list of template paths
        """
        self.categories = {
            'master_documents': [],
            'quality_assurance': [],
            'sanitation_hygiene': [],
            'production_cultivation': [],
            'security': [],
            'records_management': [],
            'human_resources': [],
            'equipment_management': [],
            'premises_management': [],
            'customization_guides': [],
            'forms_templates': [],
            'other': []
        }

        for template in self.templates:
            rel_path = template.relative_to(self.base_dir)
            path_parts = [p.upper() for p in rel_path.parts]

            # Categorize based on directory structure
            if '00_MASTER_DOCUMENTS' in path_parts:
                self.categories['master_documents'].append(template)
            elif '01_QUALITY_ASSURANCE' in path_parts:
                self.categories['quality_assurance'].append(template)
            elif '02_SANITATION_HYGIENE' in path_parts:
                self.categories['sanitation_hygiene'].append(template)
            elif '03_PRODUCTION_CULTIVATION' in path_parts:
                self.categories['production_cultivation'].append(template)
            elif '04_SECURITY' in path_parts:
                self.categories['security'].append(template)
            elif '05_RECORDS_MANAGEMENT' in path_parts:
                self.categories['records_management'].append(template)
            elif '06_HUMAN_RESOURCES' in path_parts:
                self.categories['human_resources'].append(template)
            elif '07_EQUIPMENT_MANAGEMENT' in path_parts:
                self.categories['equipment_management'].append(template)
            elif '08_PREMISES_MANAGEMENT' in path_parts:
                self.categories['premises_management'].append(template)
            elif 'CUSTOMIZATION_GUIDE' in path_parts:
                self.categories['customization_guides'].append(template)
            elif 'FORMS_TEMPLATES' in path_parts:
                self.categories['forms_templates'].append(template)
            else:
                self.categories['other'].append(template)

        return self.categories

    def get_templates_by_category(self, category: str) -> List[Path]:
        """
        Get templates for a specific category.

        Args:
            category: Category name

        Returns:
            List of template paths in category
        """
        if not self.categories:
            self.categorize()

        return self.categories.get(category, [])

    def get_priority_templates(self) -> List[Path]:
        """
        Get priority templates (master documents and key SOPs).

        Returns:
            List of priority template paths
        """
        priority = []

        # Master documents are high priority
        priority.extend(self.get_templates_by_category('master_documents'))

        # Key QA documents
        priority.extend(self.get_templates_by_category('quality_assurance'))

        return priority

    def get_template_count_by_category(self) -> Dict[str, int]:
        """Get count of templates in each category."""
        if not self.categories:
            self.categorize()

        return {cat: len(templates) for cat, templates in self.categories.items()}

    def print_summary(self):
        """Print summary of discovered templates."""
        if not self.categories:
            self.categorize()

        print("\n" + "=" * 80)
        print("Template Scanner Summary")
        print("=" * 80)
        print(f"\nBase directory: {self.base_dir}")
        print(f"Total templates found: {len(self.templates)}\n")

        print("Templates by category:")
        print("-" * 80)

        for category, templates in sorted(self.categories.items()):
            if templates:
                print(f"  {category.replace('_', ' ').title()}: {len(templates)} templates")

        print("\n" + "=" * 80)


def find_templates(base_dir: Path = None, file_pattern: str = "*.txt") -> List[Path]:
    """
    Convenience function to find all template files.

    Args:
        base_dir: Base directory to scan (default: project root)
        file_pattern: File pattern to match (default: *.txt)

    Returns:
        List of template file paths
    """
    if base_dir is None:
        # Assume script is in scripts/utils/ directory
        base_dir = Path(__file__).parent.parent.parent

    scanner = TemplateScanner(base_dir)
    templates = scanner.scan(file_pattern)

    return templates


if __name__ == "__main__":
    # Test template scanner
    print("Template Scanner Test")
    print("=" * 80)

    # Get base directory (project root)
    base_dir = Path(__file__).parent.parent.parent
    print(f"Scanning from: {base_dir}\n")

    scanner = TemplateScanner(base_dir)
    templates = scanner.scan()

    scanner.print_summary()

    # Show sample templates
    if templates:
        print("\nSample templates (first 5):")
        print("-" * 80)
        for template in templates[:5]:
            rel_path = template.relative_to(base_dir)
            print(f"  - {rel_path}")

    # Show priority templates
    priority = scanner.get_priority_templates()
    if priority:
        print(f"\nPriority templates: {len(priority)}")
        for template in priority[:3]:
            rel_path = template.relative_to(base_dir)
            print(f"  - {rel_path}")
