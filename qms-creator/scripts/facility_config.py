#!/usr/bin/env python3
"""
Facility Configuration Loader for Cannabis EU GMP QMS Creator
Loads and validates facility data from YAML configuration
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema
import yaml


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    is_valid: bool
    errors: list
    warnings: list


class FacilityConfig:
    """Facility configuration loader and validator."""

    def __init__(self, config_path: Path, schema_path: Optional[Path] = None):
        """
        Initialize facility configuration.

        Args:
            config_path: Path to facility_data.yaml
            schema_path: Optional path to validation_schema.json
        """
        self.config_path = config_path
        self.schema_path = schema_path
        self.data: Dict[str, Any] = {}
        self._loaded = False

    def load(self) -> bool:
        """
        Load configuration from YAML file.

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.data = yaml.safe_load(f) or {}
                self.data = self._normalize_nan_values(self.data)
                self._loaded = True
                return True
        except FileNotFoundError:
            print(f"Error: Configuration file not found: {self.config_path}")
            return False
        except yaml.YAMLError as e:
            print(f"Error: Invalid YAML syntax: {e}")
            return False
        except Exception as e:
            print(f"Error: Could not load configuration: {e}")
            return False

    def _normalize_nan_values(self, value: Any) -> Any:
        """Normalize NaN-like values to empty strings for safe document output."""
        if isinstance(value, dict):
            return {k: self._normalize_nan_values(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._normalize_nan_values(v) for v in value]
        if isinstance(value, float) and math.isnan(value):
            return ""
        if isinstance(value, str) and value.strip().lower() in {"nan", ".nan"}:
            return ""
        return value

    def validate(self, strict: bool = False) -> ValidationResult:
        """
        Validate configuration against schema.

        Args:
            strict: If True, treat warnings as errors.

        Returns:
            ValidationResult with validation status and messages
        """
        errors = []
        warnings = []

        if not self._loaded:
            errors.append("Configuration not loaded. Call load() first.")
            return ValidationResult(False, errors, warnings)

        # Check if schema exists
        if self.schema_path and self.schema_path.exists():
            try:
                with open(self.schema_path, "r", encoding="utf-8") as f:
                    schema = json.load(f)

                # Validate against JSON schema
                jsonschema.validate(instance=self.data, schema=schema)

            except jsonschema.ValidationError as e:
                errors.append(f"Schema validation error: {e.message}")
            except Exception as e:
                warnings.append(f"Could not validate schema: {e}")

        # Custom validation rules
        # Check for empty required fields
        required_fields = [
            ("company", "legal_entity_name"),
            ("company", "facility_name"),
            ("company", "address", "city"),
            ("company", "address", "country"),
            ("personnel", "qualified_person", "first_name"),
            ("personnel", "qualified_person", "last_name"),
        ]

        for field_path in required_fields:
            value = self._get_nested_value(field_path)
            if not value or (isinstance(value, str) and value.strip() == ""):
                warnings.append(f"Required field is empty: {' -> '.join(field_path)}")

        # Check for placeholder patterns that weren't filled
        self._check_for_unfilled_placeholders(self.data, [], warnings)

        if strict and warnings:
            errors.extend(warnings)
            warnings = []

        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)

    def _get_nested_value(self, keys: tuple) -> Any:
        """Get value from nested dictionary structure."""
        value = self.data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    def _check_for_unfilled_placeholders(self, data: Any, path: list, warnings: list):
        """Recursively check for unfilled placeholder patterns like [PLACEHOLDER]."""
        if isinstance(data, dict):
            for key, value in data.items():
                self._check_for_unfilled_placeholders(value, path + [key], warnings)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._check_for_unfilled_placeholders(item, path + [f"[{i}]"], warnings)
        elif isinstance(data, str):
            # Check for placeholder pattern [SOMETHING]
            import re

            placeholders = re.findall(r"\[([A-Z][A-Z0-9_\-\s]*?)\]", data)
            if placeholders:
                path_str = " -> ".join(str(p) for p in path)
                warnings.append(f"Unfilled placeholder in {path_str}: {data}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation path.

        Args:
            key_path: Dot-separated path like 'company.facility_name'
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split(".")
        value = self.data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_personnel(self, role: str) -> Optional[Dict[str, str]]:
        """
        Get personnel information by role.

        Args:
            role: Role name like 'qualified_person', 'facility_manager', etc.

        Returns:
            Personnel dict with first_name, last_name, etc.
        """
        return self.get(f"personnel.{role}")

    def get_full_name(self, role: str) -> str:
        """
        Get full name of person by role.

        Args:
            role: Role name like 'qualified_person'

        Returns:
            Full name like 'Blagoj Nikolov'
        """
        person = self.get_personnel(role)
        if person:
            first = person.get("first_name", "").strip()
            last = person.get("last_name", "").strip()
            if first and last:
                return f"{first} {last}"
            elif first:
                return first
            elif last:
                return last
        return ""

    def get_equipment(self, equipment_id: str) -> Optional[Dict[str, Any]]:
        """Get equipment information by ID."""
        equipment = self.get("equipment", {})
        return equipment.get(equipment_id)

    def get_all_equipment(self) -> Dict[str, Any]:
        """Get all equipment."""
        return self.get("equipment", {})

    def get_room(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Get room information by ID."""
        rooms = self.get("facilities.rooms", [])
        for room in rooms:
            if room.get("room_id") == room_id:
                return room
        return None

    def get_all_rooms(self) -> list:
        """Get all rooms."""
        return self.get("facilities.rooms", [])

    def to_dict(self) -> Dict[str, Any]:
        """Return full configuration as dictionary."""
        return self.data.copy()

    def __repr__(self) -> str:
        """String representation."""
        status = "loaded" if self._loaded else "not loaded"
        return f"FacilityConfig(path={self.config_path}, status={status})"


def load_facility_config(
    config_dir: Optional[Path] = None, strict: bool = False
) -> FacilityConfig:
    """
    Convenience function to load facility configuration.

    Args:
        config_dir: Optional config directory path. If None, uses default.

    Returns:
        Loaded FacilityConfig instance
    """
    if config_dir is None:
        # Assume script is in scripts/ directory
        base_dir = Path(__file__).parent.parent
        config_dir = base_dir / "config"

    config_path = config_dir / "facility_data.yaml"
    schema_path = config_dir / "validation_schema.json"

    if not schema_path.exists():
        schema_path = None

    config = FacilityConfig(config_path, schema_path)

    if config.load():
        validation = config.validate(strict=strict)

        if not validation.is_valid:
            print("\n⚠️  Configuration validation failed:")
            for error in validation.errors:
                print(f"  ❌ {error}")

        if validation.warnings:
            print("\n⚠️  Configuration warnings:")
            for warning in validation.warnings:
                print(f"  ⚠️  {warning}")

        if validation.is_valid and not validation.warnings:
            print("✅ Configuration loaded and validated successfully")

    return config


if __name__ == "__main__":
    # Test configuration loader
    print("Facility Configuration Loader Test")
    print("=" * 80)

    config = load_facility_config()

    if config._loaded:
        print(f"\nConfiguration: {config}")
        print(f"\nFacility Name: {config.get('company.facility_name')}")
        print(f"Legal Entity: {config.get('company.legal_entity_name')}")
        print(f"City: {config.get('company.address.city')}")
        print(f"Country: {config.get('company.address.country')}")

        print(f"\nQualified Person: {config.get_full_name('qualified_person')}")
        print(f"QP Title: {config.get('personnel.qualified_person.title')}")

        print(f"\nTotal Rooms: {len(config.get_all_rooms())}")
        print(f"Equipment Count: {len(config.get_all_equipment())}")
