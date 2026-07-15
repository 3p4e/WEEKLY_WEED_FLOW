#!/usr/bin/env python3
"""
Approval Page Generator for Cannabis EU GMP QMS Creator
Generates standardized approval page headers in Markdown, PDF, and DOCX formats
following Purely Plant design methodology with bilingual (Macedonian | English) support
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from document_id_generator import DocumentID, DocumentIDGenerator
from facility_config import FacilityConfig


class ApprovalPageGenerator:
    """Generator for Purely Plant approval page headers in multiple formats."""

    def __init__(self, config: FacilityConfig):
        """
        Initialize approval page generator.

        Args:
            config: Loaded facility configuration
        """
        self.config = config
        self.branding = config.get("document_control.branding", {})
        self.approval_chain = config.get("document_control.approval_chain", {})
        self.storage = config.get("document_control.storage", {})
        self.revision_policy = config.get("document_control.revision_policy", {})
        self.id_gen = DocumentIDGenerator()

    def generate_markdown_approval_page(self, doc_metadata: Dict[str, Any]) -> str:
        """
        Generate approval page in Markdown format.

        Args:
            doc_metadata: Document metadata dict with keys:
                - document_id: Document ID (e.g., 'QAS-01.01')
                - version: Version number (e.g., '1.0')
                - title_mk: Macedonian title
                - title_en: English title
                - effective_date: Effective date (YYYY-MM-DD)
                - copy_type: 'original', 'controlled', or 'uncontrolled'
                - document_type: Type of document (e.g., 'SOP')

        Returns:
            Markdown-formatted approval page header
        """
        # Extract metadata
        doc_id_raw = doc_metadata.get("document_id", "UNKNOWN")
        version = doc_metadata.get("version", "1.0")
        title_mk = doc_metadata.get("title_mk", "")
        title_en = doc_metadata.get("title_en", "")

        # Parse hierarchical ID if possible
        doc_id = doc_id_raw
        if self.id_gen.is_valid(doc_id_raw):
            parsed_id = self.id_gen.parse(doc_id_raw)
            doc_id = str(parsed_id)
            version = str(parsed_id.version)
        effective_date_str = doc_metadata.get(
            "effective_date", datetime.now().strftime("%Y-%m-%d")
        )
        copy_type = doc_metadata.get(
            "copy_type", self.storage.get("copy_type", "controlled")
        )
        doc_type = doc_metadata.get("document_type", "SOP")

        # Calculate dates
        effective_date = self._parse_date(effective_date_str)
        next_review = self._add_months(
            effective_date, self.revision_policy.get("default_review_period_months", 12)
        )

        # Format dates
        eff_date_short = effective_date.strftime("%d.%m.%y")
        next_review_short = next_review.strftime("%d.%m.%y")

        # Get approval personnel
        prepared_by_name = self._get_personnel_name("prepared_by")
        prepared_by_pos_mk = self.approval_chain.get("prepared_by", {}).get(
            "position_mk", ""
        )
        prepared_by_pos_en = self.approval_chain.get("prepared_by", {}).get(
            "position_en", ""
        )

        checked_by_name = self._get_personnel_name("checked_by")
        checked_by_pos_mk = self.approval_chain.get("checked_by", {}).get(
            "position_mk", ""
        )
        checked_by_pos_en = self.approval_chain.get("checked_by", {}).get(
            "position_en", ""
        )

        approved_by_name = self._get_personnel_name("approved_by")
        approved_by_pos_mk = self.approval_chain.get("approved_by", {}).get(
            "position_mk", ""
        )
        approved_by_pos_en = self.approval_chain.get("approved_by", {}).get(
            "position_en", ""
        )

        company_name = self.branding.get("company_name_en", "Purely Plant GmbH")
        storage_location = self.storage.get("current_location", "Department Office")

        # Build markdown
        md_lines = []

        # YAML Front Matter
        md_lines.append("---")
        md_lines.append(f'document_id: "{doc_id}"')
        md_lines.append(f'version: "{version}"')
        md_lines.append(f'title_mk: "{title_mk}"')
        md_lines.append(f'title_en: "{title_en}"')
        md_lines.append(f'effective_date: "{effective_date_str}"')
        md_lines.append(f'copy_type: "{copy_type}"')
        md_lines.append(f'document_type: "{doc_type}"')
        md_lines.append("---")
        md_lines.append("")

        # Header with company name and document ID
        md_lines.append(f"# {company_name}")
        md_lines.append("")
        md_lines.append(
            f"**Document ID:** {doc_id} v.{version} | **Effective Date:** {eff_date_short}"
        )
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

        # Title section
        md_lines.append(f"## {title_mk} | {title_en}")
        md_lines.append("")

        # Document Approval Table
        md_lines.append("### ОДОБРУВАЊЕ НА ДОКУМЕНТ | DOCUMENT APPROVAL")
        md_lines.append("")
        md_lines.append(
            "| Дејство / Action | Позиција / Position | Име и Презиме / Name & Surname | Датум / Date | Потпис / Signature |"
        )
        md_lines.append("|---|---|---|---|---|")
        md_lines.append(
            f"| **Подготвено од:** / _Prepared by:_ | {prepared_by_pos_mk} / {prepared_by_pos_en} | {prepared_by_name} | __________ | _________________ |"
        )
        md_lines.append(
            f"| **Проверено од:** / _Checked by:_ | {checked_by_pos_mk} / {checked_by_pos_en} | {checked_by_name} | __________ | _________________ |"
        )
        md_lines.append(
            f"| **Одобрено од:** / _Approved by:_ | {approved_by_pos_mk} / {approved_by_pos_en} | {approved_by_name} | __________ | _________________ |"
        )
        md_lines.append("")

        # Document Control Table
        md_lines.append("---")
        md_lines.append("")
        md_lines.append("### КОНТРОЛА НА ДОКУМЕНТ | DOCUMENT CONTROL")
        md_lines.append("")
        md_lines.append("| Field | Value |")
        md_lines.append("|---|---|")
        md_lines.append(
            f"| **Оригиналот се чува во:** / _The original is kept & stored in:_ | {self.storage.get('original_location', 'Archive')} |"
        )
        md_lines.append(f"| **Тип на документ:** / _Type of document:_ | {doc_type} |")
        md_lines.append(
            f"| **Овој документ се чува во:** / _This document is kept & stored in:_ | {storage_location} |"
        )
        md_lines.append(
            f"| **Тип на копија:** / _Copy type:_ | {copy_type.capitalize()} |"
        )
        md_lines.append("")

        # User type checkboxes
        user_type = self.revision_policy.get("user_type", "internal")
        internal_checked = "☒" if user_type == "internal" else "☐"
        external_checked = "☐" if user_type == "internal" else "☒"

        md_lines.append(
            f"**Корисник:** / _User:_  {internal_checked} Внатрешен / Internal  {external_checked} Надворешен / External"
        )
        md_lines.append("")

        # Revision dates
        md_lines.append(
            f"**Датум на последна ревизија:** / _Date of last revision:_ {eff_date_short}"
        )
        md_lines.append("")
        md_lines.append(
            f"**Ефективен датум на користење:** / _Effective Date of Use:_ {eff_date_short}"
        )
        md_lines.append("")
        md_lines.append(
            f"**Датум на валидност / редовна ревизија:** / _Date of validity / planned revision:_ {next_review_short}"
        )
        md_lines.append("")

        # Revision History
        md_lines.append("---")
        md_lines.append("")
        md_lines.append("### ИСТОРИЈА НА РЕВИЗИИ | REVISION HISTORY")
        md_lines.append("")
        md_lines.append(
            "| Верзија бр. / Version No. | Датум на промена / Date of change | Опис на променета содржина / Description of change |"
        )
        md_lines.append("|---|---|---|")
        md_lines.append(
            f"| {version} | {eff_date_short} | Initial Release / Почетна верзија |"
        )
        md_lines.append("")

        # Separator before content
        md_lines.append("---")
        md_lines.append("")

        return "\n".join(md_lines)

    def get_approval_personnel_names(self) -> Dict[str, str]:
        """
        Get names and positions of approval personnel.

        Returns:
            Dictionary with keys: prepared_by_name, prepared_by_pos_mk, prepared_by_pos_en, etc.
        """
        result = {}

        for action in ["prepared_by", "checked_by", "approved_by"]:
            role = self.approval_chain.get(action, {}).get("role")
            if role:
                person = self.config.get_personnel(role)
                if person:
                    name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                    result[f"{action}_name"] = name
                    result[f"{action}_pos_mk"] = self.approval_chain.get(
                        action, {}
                    ).get("position_mk", "")
                    result[f"{action}_pos_en"] = self.approval_chain.get(
                        action, {}
                    ).get("position_en", "")

        return result

    def parse_hierarchical_id(self, doc_id: str) -> Optional[DocumentID]:
        """
        Parse a hierarchical document ID.

        Args:
            doc_id: The document ID string to parse

        Returns:
            DocumentID object if valid, None otherwise
        """
        if self.id_gen.is_valid(doc_id):
            return self.id_gen.parse(doc_id)
        return None

    def _get_personnel_name(self, action: str) -> str:
        """Get full name of approval personnel for given action."""
        role = self.approval_chain.get(action, {}).get("role")
        if role:
            return self.config.get_full_name(role)
        return "[NAME]"

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string in YYYY-MM-DD format."""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return datetime.now()

    def _add_months(self, date: datetime, months: int) -> datetime:
        """Add months to a date."""
        month = date.month + months
        year = date.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        day = min(date.day, 28)  # Safe day value
        return date.replace(year=year, month=month, day=day)

    def get_statistics(self) -> Dict[str, Any]:
        """Get generator configuration statistics."""
        return {
            "approval_chain": {
                "prepared_by": self.approval_chain.get("prepared_by", {}).get("role"),
                "checked_by": self.approval_chain.get("checked_by", {}).get("role"),
                "approved_by": self.approval_chain.get("approved_by", {}).get("role"),
            },
            "branding": {
                "logo_path": self.branding.get("logo_path"),
                "primary_color": self.branding.get("primary_color"),
                "header_bg_color": self.branding.get("header_bg_color"),
            },
            "storage": self.storage,
            "revision_policy": self.revision_policy,
        }


def test_approval_page_generator():
    """Test the approval page generator."""
    from facility_config import load_facility_config

    print("Testing Approval Page Generator")
    print("=" * 80)

    config = load_facility_config()

    if config._loaded:
        generator = ApprovalPageGenerator(config)

        # Test metadata with hierarchical ID
        test_metadata = {
            "document_id": "QA_00.06_v1",
            "version": "1",
            "title_mk": "Систем за Корективни и Превентивни Активности",
            "title_en": "Corrective and Preventive Action (CAPA) System",
            "effective_date": "2024-01-15",
            "copy_type": "controlled",
            "document_type": "SOP",
        }

        print("\nGenerating Markdown Approval Page...")
        md_page = generator.generate_markdown_approval_page(test_metadata)

        print("\nFirst 500 characters of output:")
        print(md_page[:500])

        print("\n\nApproval Personnel:")
        personnel = generator.get_approval_personnel_names()
        for key, value in personnel.items():
            print(f"  {key}: {value}")

        print("\n\nGenerator Statistics:")
        stats = generator.get_statistics()
        for section, data in stats.items():
            print(f"\n  {section}:")
            for key, value in data.items():
                print(f"    {key}: {value}")

    else:
        print("Failed to load configuration")


if __name__ == "__main__":
    test_approval_page_generator()
