#!/usr/bin/env python3
"""
Placeholder Engine for Cannabis EU GMP QMS Creator
Core logic for replacing placeholders in templates with facility data
"""

import re

# Import our utilities
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from document_id_generator import DocumentIDGenerator

sys.path.append(str(Path(__file__).parent))

import yaml
from facility_config import FacilityConfig
from utils.date_calculator import DateCalculator

try:
    from advanced_mapping import AdvancedPlaceholderMapper

    ADVANCED_MAPPING_AVAILABLE = True
except ImportError:
    ADVANCED_MAPPING_AVAILABLE = False


class PlaceholderEngine:
    """Engine for replacing placeholders in template content."""

    def __init__(self, config: FacilityConfig, use_advanced_mapping: bool = True):
        """
        Initialize placeholder engine.

        Args:
            config: Loaded facility configuration
            use_advanced_mapping: Enable context-aware advanced mapping (default: True)
        """
        self.config = config
        self.placeholder_pattern = re.compile(r"\[([A-Z][A-Z0-9_\-\s]*?)\]")
        self.replacements_made = 0
        self.unresolved_placeholders: List[str] = []

        # Initialize advanced mapper if available
        self.use_advanced_mapping = use_advanced_mapping and ADVANCED_MAPPING_AVAILABLE
        if self.use_advanced_mapping:
            self.advanced_mapper = AdvancedPlaceholderMapper(config)
        else:
            self.advanced_mapper = None

        # Initialize document ID generator (used for hierarchical IDs)
        self.id_gen = DocumentIDGenerator()

        # Load additional placeholder mappings
        self.additional_mappings = self._load_additional_mappings()

    def process_content(self, content: str) -> str:
        """
        Process template content and replace all placeholders.

        Args:
            content: Template content with placeholders

        Returns:
            Content with placeholders replaced
        """
        self.replacements_made = 0
        self.unresolved_placeholders = []

        # Find all placeholders with their positions
        matches = list(self.placeholder_pattern.finditer(content))

        # Build replacement map
        replacement_map = {}
        for match in matches:
            placeholder = match.group(1)

            if placeholder not in replacement_map:
                # Try standard replacement first
                replacement = self._get_replacement(placeholder)

                # If not found and advanced mapping enabled, try context-aware resolution
                if replacement is None and self.advanced_mapper:
                    context = self.advanced_mapper.get_context_window(
                        content, placeholder, match.start()
                    )
                    replacement = self.advanced_mapper.resolve_placeholder(
                        placeholder, context
                    )

                replacement_map[placeholder] = replacement

        # Apply replacements
        for placeholder, replacement in replacement_map.items():
            if replacement is not None:
                pattern = re.escape(f"[{placeholder}]")
                count_before = len(re.findall(pattern, content))
                content = re.sub(pattern, replacement, content)
                self.replacements_made += count_before
            else:
                self.unresolved_placeholders.append(placeholder)

        return content

    def _load_additional_mappings(self) -> Dict:
        """Load additional placeholder mappings from YAML file."""
        try:
            mappings_path = (
                Path(__file__).parent.parent
                / "config"
                / "additional_placeholder_mappings.yaml"
            )
            if mappings_path.exists():
                with open(mappings_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        except Exception:
            pass
        return {}

    def _get_replacement(self, placeholder: str) -> Optional[str]:
        """
        Get replacement value for a placeholder.

        Args:
            placeholder: Placeholder name (without brackets)

        Returns:
            Replacement string or None if not found
        """
        # Normalize placeholder
        ph = placeholder.strip()

        # Approval page placeholders
        approval_replacement = self._get_approval_page_replacement(ph)
        if approval_replacement is not None:
            return approval_replacement

        # Check additional mappings first
        if ph in self.additional_mappings:
            value = self.additional_mappings[ph]
            # Handle dict values (take first/default value)
            if isinstance(value, dict):
                if "default" in value:
                    return str(value["default"])
                elif value:
                    return str(list(value.values())[0])
            # Handle list values (join with newlines for multi-line content)
            elif isinstance(value, list):
                return "\n".join(str(v) for v in value)
            return str(value)

        # Special placeholders
        if ph in ["DATE", "INSERT DATE"]:
            return DateCalculator.today()

        if ph == "EFFECTIVE_DATE":
            return self.config.get("metadata.effective_date") or DateCalculator.today()

        if ph == "NEXT_REVIEW_DATE":
            effective_date = (
                self.config.get("metadata.effective_date") or DateCalculator.today()
            )
            return DateCalculator.add_years(effective_date, 1)

        if ph == "LAST_UPDATED":
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if ph == "YEAR":
            return str(datetime.now().year)

        if ph == "YYYYMMDD":
            return datetime.now().strftime("%Y%m%d")

        if ph == "VERSION":
            return self.config.get("metadata.qms_version", "1.0")

        # Company/Facility placeholders
        company_mapping = {
            "LEGAL_ENTITY_NAME": "company.legal_entity_name",
            "FACILITY_NAME": "company.facility_name",
            "REGISTRATION_NUMBER": "company.registration_number",
            "FACILITY_ADDRESS": self._format_full_address,
            "FACILITY_CITY": "company.address.city",
            "FACILITY_REGION": "company.address.region",
            "ADDRESS": self._format_full_address,
        }

        if ph in company_mapping:
            mapping = company_mapping[ph]
            if callable(mapping):
                return mapping()
            return self.config.get(mapping, "")

        # Regulatory placeholders
        regulatory_mapping = {
            "LICENSE_NUMBER": "regulatory.medical_cannabis_license.license_number",
            "REGULATORY_AUTHORITY": "regulatory.regulatory_authority.name",
            "REGULATORY_AUTHORITY_NAME": "regulatory.regulatory_authority.name",
        }

        if ph in regulatory_mapping:
            return self.config.get(regulatory_mapping[ph], "")

        # Personnel placeholders - try to match by pattern
        personnel_replacement = self._get_personnel_replacement(ph)
        if personnel_replacement:
            return personnel_replacement

        # Equipment placeholders
        equipment_replacement = self._get_equipment_replacement(ph)
        if equipment_replacement:
            return equipment_replacement

        # Operational placeholders
        operational_mapping = {
            "OBJECTIVE_1": "operations.quality_objectives.objective_1",
            "OBJECTIVE_2": "operations.quality_objectives.objective_2",
            "OBJECTIVE_3": "operations.quality_objectives.objective_3",
            "RETENTION_PERIOD": "7 years",  # Default
            "TARGET_METRIC": "operations.metrics.target_metric_1",
        }

        if ph in operational_mapping:
            return self.config.get(operational_mapping[ph], "")

        # Location placeholders
        location_mapping = {
            "LOCATION": "company.address.city",
            "REGION": "company.address.region",
            "STORAGE_LOCATION": "facilities.storage.primary_document_storage",
            "ARCHIVE_LOCATION": "facilities.storage.archive_storage",
            "VAULT_LOCATION": "facilities.storage.secure_vault",
            "BACKUP_LOCATION": "facilities.storage.backup_document_storage",
        }

        if ph in location_mapping:
            return self.config.get(location_mapping[ph], "")

        # Generic placeholders that might appear in specific contexts
        if ph in ["MANAGER_NAME", "MANAGER"]:
            return self.config.get_full_name("facility_manager")

        if ph == "QUALITY_MANAGER_NAME":
            return self.config.get_full_name("qa_manager")

        # Contact information
        if ph in ["PHONE", "PHONE_NUMBER"]:
            return self.config.get("personnel.qualified_person.phone", "")

        if ph in ["EMAIL", "EMAIL_ADDRESS"]:
            return self.config.get("personnel.qualified_person.email", "")

        # Return None if no replacement found
        return None

    def _get_personnel_replacement(self, placeholder: str) -> Optional[str]:
        """Get replacement for personnel-related placeholders."""

        # Map placeholder patterns to config paths
        personnel_roles = {
            "FACILITY_MANAGER": "facility_manager",
            "QA_MANAGER": "qa_manager",
            "PRODUCTION_MANAGER": "production_manager",
            "SANITATION_MANAGER": "sanitation_manager",
            "SECURITY_MANAGER": "security_manager",
            "HR_MANAGER": "hr_manager",
            "RECORDS_MANAGER": "records_manager",
            "QUALITY_MANAGER": "qa_manager",
        }

        # Check for exact role match
        for ph_pattern, role in personnel_roles.items():
            if ph_pattern in placeholder:
                if "_NAME" in placeholder:
                    return self.config.get_full_name(role)
                elif "_FIRST_NAME" in placeholder:
                    person = self.config.get_personnel(role)
                    return person.get("first_name", "") if person else ""
                elif "_LAST_NAME" in placeholder:
                    person = self.config.get_personnel(role)
                    return person.get("last_name", "") if person else ""
                elif "_TITLE" in placeholder:
                    person = self.config.get_personnel(role)
                    return person.get("title", "") if person else ""
                elif "_EMAIL" in placeholder:
                    person = self.config.get_personnel(role)
                    return person.get("email", "") if person else ""
                elif "_PHONE" in placeholder:
                    person = self.config.get_personnel(role)
                    return person.get("phone", "") if person else ""

        # Check for generic name placeholders
        if placeholder in ["NAME", "YOUR_NAME", "AUTHOR_NAME"]:
            return self.config.get_full_name("qualified_person")

        return None

    def _get_equipment_replacement(self, placeholder: str) -> Optional[str]:
        """Get replacement for equipment-related placeholders."""

        equipment_mapping = {
            "DRYING_MACHINE_MODEL": ("drying_machine", "model"),
            "TRIMMING_MACHINE_MODEL": ("trimming_machine", "model"),
            "HVAC_SYSTEM": ("hvac_system", "name"),
            "IRRIGATION_SYSTEM": ("irrigation_system", "name"),
            "PACKAGING_EQUIPMENT": ("packaging_equipment", "name"),
            "WASTE_SYSTEM": ("waste_system", "name"),
        }

        if placeholder in equipment_mapping:
            eq_id, field = equipment_mapping[placeholder]
            equipment = self.config.get_equipment(eq_id)
            if equipment:
                return equipment.get(field, "")

        # Generic equipment placeholders
        if "EQUIPMENT" in placeholder:
            # Could be a generic equipment reference
            return "[Equipment Name]"  # Leave as placeholder

        return None

    def _format_full_address(self) -> str:
        """Format full facility address."""
        addr = self.config.get("company.address", {})

        parts = []
        if addr.get("street"):
            parts.append(addr["street"])
        if addr.get("city"):
            parts.append(addr["city"])
        if addr.get("postal_code"):
            parts.append(addr["postal_code"])
        if addr.get("region"):
            parts.append(addr["region"])
        if addr.get("country"):
            parts.append(addr["country"])

        return ", ".join(parts)

    def _get_approval_page_replacement(self, placeholder: str) -> Optional[str]:
        """
        Get replacement for approval page-related placeholders.

        Args:
            placeholder: Placeholder name

        Returns:
            Replacement value or None
        """
        approval_chain = self.config.get("document_control.approval_chain", {})
        storage = self.config.get("document_control.storage", {})
        branding = self.config.get("document_control.branding", {})

        # Hierarchical ID placeholders
        if placeholder.startswith("DOC_ID_"):
            doc_id_str = self.config.get("document_control.current_id")
            if doc_id_str and self.id_gen.is_valid(doc_id_str):
                parsed = self.id_gen.parse(doc_id_str)
                if placeholder == "DOC_ID_DEPT":
                    return parsed.department
                elif placeholder == "DOC_ID_FAMILY":
                    return f"{parsed.family:02d}"
                elif placeholder == "DOC_ID_SOP":
                    return f"{parsed.sop:02d}"
                elif placeholder == "DOC_ID_ANNEX":
                    return f"A{parsed.annex:02d}" if parsed.annex else ""
                elif placeholder == "DOC_ID_VERSION":
                    return str(parsed.version)
                elif placeholder == "DOC_ID_FULL":
                    return str(parsed)

        # Prepared by placeholders
        if placeholder == "PREPARED_BY_NAME":
            role = approval_chain.get("prepared_by", {}).get("role")
            return self.config.get_full_name(role) if role else None
        elif placeholder == "PREPARED_BY_POSITION":
            return approval_chain.get("prepared_by", {}).get("position_en")
        elif placeholder == "PREPARED_BY_POSITION_MK":
            return approval_chain.get("prepared_by", {}).get("position_mk")

        # Checked by placeholders
        elif placeholder == "CHECKED_BY_NAME":
            role = approval_chain.get("checked_by", {}).get("role")
            return self.config.get_full_name(role) if role else None
        elif placeholder == "CHECKED_BY_POSITION":
            return approval_chain.get("checked_by", {}).get("position_en")
        elif placeholder == "CHECKED_BY_POSITION_MK":
            return approval_chain.get("checked_by", {}).get("position_mk")

        # Approved by placeholders
        elif placeholder == "APPROVED_BY_NAME":
            role = approval_chain.get("approved_by", {}).get("role")
            return self.config.get_full_name(role) if role else None
        elif placeholder == "APPROVED_BY_POSITION":
            return approval_chain.get("approved_by", {}).get("position_en")
        elif placeholder == "APPROVED_BY_POSITION_MK":
            return approval_chain.get("approved_by", {}).get("position_mk")

        # Storage location placeholders
        elif placeholder == "ORIGINAL_STORAGE_LOCATION":
            return storage.get("original_location")
        elif placeholder == "CURRENT_STORAGE_LOCATION":
            return storage.get("current_location")
        elif placeholder == "COPY_TYPE":
            copy_type = storage.get("copy_type", "controlled")
            return copy_type.capitalize()

        # Branding placeholders
        elif placeholder == "COMPANY_NAME_MK":
            return branding.get("company_name_mk")
        elif placeholder == "COMPANY_NAME_EN":
            return branding.get("company_name_en")
        elif placeholder == "LOGO_PATH":
            return branding.get("logo_path")
        elif placeholder == "PRIMARY_COLOR":
            return branding.get("primary_color")

        # User type checkboxes
        elif placeholder == "USER_TYPE_INTERNAL":
            user_type = self.config.get(
                "document_control.revision_policy.user_type", "internal"
            )
            return "☒" if user_type == "internal" else "☐"
        elif placeholder == "USER_TYPE_EXTERNAL":
            user_type = self.config.get(
                "document_control.revision_policy.user_type", "internal"
            )
            return "☐" if user_type == "internal" else "☒"

        return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about placeholder replacements.

        Returns:
            Dictionary with replacement statistics
        """
        return {
            "replacements_made": self.replacements_made,
            "unresolved_count": len(set(self.unresolved_placeholders)),
            "unresolved_placeholders": sorted(set(self.unresolved_placeholders)),
        }


def process_template_file(
    template_path: Path, output_path: Path, config: FacilityConfig
) -> Tuple[bool, Dict]:
    """
    Process a single template file.

    Args:
        template_path: Path to template file
        output_path: Path for output file
        config: Facility configuration

    Returns:
        Tuple of (success: bool, statistics: dict)
    """
    try:
        # Read template
        with open(template_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Process placeholders
        engine = PlaceholderEngine(config)
        processed_content = engine.process_content(content)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(processed_content)

        return True, engine.get_statistics()

    except Exception as e:
        return False, {"error": str(e)}


if __name__ == "__main__":
    # Test placeholder engine
    print("Placeholder Engine Test")
    print("=" * 80)

    # Load config
    from facility_config import load_facility_config

    config = load_facility_config()

    if config._loaded:
        engine = PlaceholderEngine(config)

        # Test content with placeholders
        test_content = """
        Facility Name: [FACILITY_NAME]
        Location: [FACILITY_CITY], [FACILITY_REGION]
        Qualified Person: [NAME]
        Date: [DATE]
        Version: [VERSION]
        Equipment: [DRYING_MACHINE_MODEL]
        """

        print("\nOriginal content:")
        print(test_content)

        processed = engine.process_content(test_content)

        print("\nProcessed content:")
        print(processed)

        print("\nStatistics:")
        stats = engine.get_statistics()
        print(f"  Replacements made: {stats['replacements_made']}")
        print(f"  Unresolved: {stats['unresolved_count']}")
        if stats["unresolved_placeholders"]:
            print(
                f"  Unresolved placeholders: {', '.join(stats['unresolved_placeholders'])}"
            )
