#!/usr/bin/env python3
"""
Validation Engine for Progressive Feedback

Provides real-time validation of questionnaire answers and generated content
with progressive feedback during document creation.

Features:
- Section-by-section validation with immediate feedback
- Rule-based validation for consistency and completeness
- Cannabis-specific compliance checks
- Quality score estimation
- Actionable error messages and warnings

Author: QMS Development Team
Date: 2026-01-23
Version: 1.0
"""

import logging
import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation severity levels"""

    ERROR = "error"  # Blocks document generation
    WARNING = "warning"  # Should be addressed but non-blocking
    INFO = "info"  # Informational guidance


class ValidationRule(ABC):
    """Base class for validation rules"""

    def __init__(self, rule_id: str, description: str, severity: ValidationSeverity):
        self.rule_id = rule_id
        self.description = description
        self.severity = severity

    @abstractmethod
    def validate(self, data: Dict) -> Tuple[bool, str]:
        """
        Validate data against rule

        Args:
            data: Data to validate

        Returns:
            Tuple of (is_valid, message)
        """
        pass

    def applies_to_section(self, section_name: str) -> bool:
        """
        Check if rule applies to a specific section

        Args:
            section_name: Section name

        Returns:
            True if rule applies, False otherwise
        """
        return True  # Default: applies to all sections


class RequiredFieldRule(ValidationRule):
    """Validate required fields are filled"""

    def __init__(self, field_name: str, friendly_name: Optional[str] = None):
        super().__init__(
            f"required_{field_name}",
            f"Field '{friendly_name or field_name}' is required",
            ValidationSeverity.ERROR,
        )
        self.field_name = field_name
        self.friendly_name = friendly_name or field_name

    def validate(self, data: Dict) -> Tuple[bool, str]:
        value = data.get(self.field_name)

        if value is None:
            return False, f"Missing required field: {self.friendly_name}"

        # Check for empty strings
        if isinstance(value, str) and not value.strip():
            return False, f"Field '{self.friendly_name}' cannot be empty"

        # Check for empty lists
        if isinstance(value, list) and len(value) == 0:
            return False, f"Field '{self.friendly_name}' must have at least one item"

        return True, ""


class MinLengthRule(ValidationRule):
    """Validate minimum text length"""

    def __init__(
        self, field_name: str, min_length: int, friendly_name: Optional[str] = None
    ):
        super().__init__(
            f"minlength_{field_name}",
            f"Field '{friendly_name or field_name}' must be at least {min_length} characters",
            ValidationSeverity.WARNING,
        )
        self.field_name = field_name
        self.min_length = min_length
        self.friendly_name = friendly_name or field_name

    def validate(self, data: Dict) -> Tuple[bool, str]:
        value = data.get(self.field_name, "")

        if isinstance(value, str) and len(value) < self.min_length:
            return (
                False,
                f"Field '{self.friendly_name}' is too short (minimum {self.min_length} characters)",
            )

        return True, ""


class CannabisComplianceRule(ValidationRule):
    """Validate cannabis-specific compliance requirements"""

    def __init__(self):
        super().__init__(
            "cannabis_compliance",
            "Cannabis SOP compliance requirements",
            ValidationSeverity.ERROR,
        )

    def validate(self, data: Dict) -> Tuple[bool, str]:
        is_cannabis = data.get("is_cannabis", False)

        if not is_cannabis:
            return True, ""  # Rule doesn't apply

        # Check THC limit specification
        thc_limit = data.get("thc_limit", "")
        if not thc_limit:
            return (
                False,
                "Cannabis SOP missing THC limit specification (EU requires < 0.2% THC)",
            )

        # Validate THC limit value
        if "0.2%" not in thc_limit and "0.3%" not in thc_limit:
            return (
                False,
                f"THC limit '{thc_limit}' may not comply with EU regulations (typically 0.2%)",
            )

        return True, ""

    def applies_to_section(self, section_name: str) -> bool:
        # Only applies to scope and regulatory sections
        return section_name in ["scope", "regulatory", "compliance"]


class EnvironmentalControlRule(ValidationRule):
    """Validate environmental control specifications for cannabis"""

    def __init__(self):
        super().__init__(
            "environmental_controls",
            "Environmental control specifications required",
            ValidationSeverity.WARNING,
        )

    def validate(self, data: Dict) -> Tuple[bool, str]:
        is_cannabis = data.get("is_cannabis", False)

        if not is_cannabis:
            return True, ""

        # Check for environmental specifications
        procedure_text = data.get("procedure", "")
        scope_text = data.get("scope", "")
        combined_text = f"{procedure_text} {scope_text}".lower()

        required_controls = {
            "temperature": ["temperature", "temp", "°c"],
            "humidity": ["humidity", "rh", "%"],
            "light": ["light", "lighting", "photoperiod"],
        }

        missing_controls = []

        for control_name, keywords in required_controls.items():
            if not any(kw in combined_text for kw in keywords):
                missing_controls.append(control_name)

        if missing_controls:
            return (
                False,
                f"Missing environmental control specifications: {', '.join(missing_controls)}",
            )

        return True, ""

    def applies_to_section(self, section_name: str) -> bool:
        return section_name in ["procedure", "scope", "environmental"]


class ResponsibilityAssignmentRule(ValidationRule):
    """Validate responsibilities are clearly assigned"""

    def __init__(self):
        super().__init__(
            "responsibility_assignment",
            "Clear responsibility assignments required",
            ValidationSeverity.WARNING,
        )

    def validate(self, data: Dict) -> Tuple[bool, str]:
        responsibilities = data.get("responsibilities", "")

        if not responsibilities:
            return False, "Responsibilities section is empty"

        # Check for role assignments (e.g., "QA Manager:", "Operator:")
        role_pattern = r"([A-Z][a-zA-Z\s]+):\s*"
        roles = re.findall(role_pattern, responsibilities)

        if len(roles) < 2:
            return (
                False,
                "At least 2 distinct roles should be assigned responsibilities",
            )

        return True, ""

    def applies_to_section(self, section_name: str) -> bool:
        return section_name == "responsibilities"


class EquipmentSpecificationRule(ValidationRule):
    """Validate equipment specifications are detailed"""

    def __init__(self):
        super().__init__(
            "equipment_specification",
            "Equipment specifications should be detailed",
            ValidationSeverity.INFO,
        )

    def validate(self, data: Dict) -> Tuple[bool, str]:
        equipment = data.get("equipment", [])

        if not equipment:
            return True, ""  # Not an error if no equipment

        # Check if equipment entries have sufficient detail
        incomplete_equipment = []

        for item in equipment:
            if isinstance(item, dict):
                name = item.get("name", "")
                specs = item.get("specifications", "")

                if name and len(specs) < 20:  # Arbitrary threshold
                    incomplete_equipment.append(name)

        if incomplete_equipment:
            return (
                False,
                f"Equipment lacks detailed specifications: {', '.join(incomplete_equipment[:3])}",
            )

        return True, ""

    def applies_to_section(self, section_name: str) -> bool:
        return section_name in ["equipment", "materials", "procedure"]


class ValidationEngine:
    """Main validation engine for questionnaire and content validation"""

    def __init__(self):
        """Initialize validation engine with rule set"""
        self.rules = self._load_validation_rules()

    def _load_validation_rules(self) -> List[ValidationRule]:
        """Load all validation rules"""
        rules = [
            # Required field rules
            RequiredFieldRule("sop_name", "SOP Name"),
            RequiredFieldRule("purpose", "Purpose"),
            RequiredFieldRule("scope", "Scope"),
            RequiredFieldRule("responsibilities", "Responsibilities"),
            RequiredFieldRule("procedure", "Procedure"),
            # Min length rules
            MinLengthRule("purpose", 50, "Purpose"),
            MinLengthRule("scope", 50, "Scope"),
            MinLengthRule("procedure", 200, "Procedure"),
            # Domain-specific rules
            CannabisComplianceRule(),
            EnvironmentalControlRule(),
            ResponsibilityAssignmentRule(),
            EquipmentSpecificationRule(),
        ]

        return rules

    def validate_section(self, section_data: Dict, section_name: str) -> Dict[str, Any]:
        """
        Validate a single questionnaire section

        Args:
            section_data: Section data to validate
            section_name: Name of the section

        Returns:
            Validation results with errors, warnings, info, and completion score
        """
        results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "info": [],
            "completion_score": 0.0,
            "validated_fields": 0,
            "total_fields": 0,
        }

        # Run applicable rules
        for rule in self.rules:
            if rule.applies_to_section(section_name):
                is_valid, message = rule.validate(section_data)

                if not is_valid and message:
                    if rule.severity == ValidationSeverity.ERROR:
                        results["errors"].append(message)
                        results["is_valid"] = False
                    elif rule.severity == ValidationSeverity.WARNING:
                        results["warnings"].append(message)
                    else:  # INFO
                        results["info"].append(message)

        # Calculate completion score
        total_fields = len(section_data)
        filled_fields = sum(
            1
            for v in section_data.values()
            if v and (not isinstance(v, str) or v.strip())
        )

        results["total_fields"] = total_fields
        results["validated_fields"] = filled_fields
        results["completion_score"] = (
            (filled_fields / total_fields) * 100 if total_fields > 0 else 0
        )

        return results

    def validate_generated_content(
        self, content: str, metadata: Dict
    ) -> Dict[str, Any]:
        """
        Validate generated SOP content before formatting

        Args:
            content: Generated markdown content
            metadata: Metadata about the document

        Returns:
            Validation results with quality score and issues
        """
        from quality_metrics_engine import QualityMetricsCalculator

        results = {
            "is_valid": True,
            "quality_score": 0,
            "errors": [],
            "warnings": [],
            "regulatory_issues": [],
            "improvement_areas": [],
            "first_pass_approval_likelihood": 0.0,
        }

        # Use quality metrics engine for comprehensive assessment
        try:
            calculator = QualityMetricsCalculator()
            assessment = calculator.assess_document(
                content,
                is_cannabis=metadata.get("is_cannabis", False),
                sop_type=metadata.get("sop_type"),
            )

            results["quality_score"] = assessment.weighted_score
            results["regulatory_issues"] = assessment.regulatory_issues
            results["improvement_areas"] = assessment.improvement_areas
            results["first_pass_approval_likelihood"] = (
                assessment.first_pass_approval_likelihood
            )

            # Mark as invalid if quality score is below threshold
            if assessment.weighted_score < 60:
                results["is_valid"] = False
                results["errors"].append(
                    f"Quality score ({assessment.weighted_score:.1f}) below minimum threshold (60)"
                )

            # Add warnings for moderate quality
            if 60 <= assessment.weighted_score < 75:
                results["warnings"].append(
                    f"Quality score ({assessment.weighted_score:.1f}) could be improved"
                )

        except Exception as e:
            logger.error(f"Content validation failed: {e}")
            results["is_valid"] = False
            results["errors"].append(f"Validation error: {str(e)}")

        return results

    def validate_questionnaire_complete(
        self, all_answers: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """
        Validate entire questionnaire for completeness

        Args:
            all_answers: Dictionary of all section answers

        Returns:
            Overall validation results
        """
        overall_results = {
            "is_valid": True,
            "section_results": {},
            "total_errors": 0,
            "total_warnings": 0,
            "overall_completion": 0.0,
        }

        section_scores = []

        for section_name, section_data in all_answers.items():
            section_result = self.validate_section(section_data, section_name)
            overall_results["section_results"][section_name] = section_result

            if not section_result["is_valid"]:
                overall_results["is_valid"] = False

            overall_results["total_errors"] += len(section_result["errors"])
            overall_results["total_warnings"] += len(section_result["warnings"])
            section_scores.append(section_result["completion_score"])

        # Calculate overall completion
        if section_scores:
            overall_results["overall_completion"] = sum(section_scores) / len(
                section_scores
            )

        return overall_results


# Convenience functions for API integration


def validate_section(section_data: Dict, section_name: str) -> Dict[str, Any]:
    """
    Convenience function to validate a section

    Args:
        section_data: Section data
        section_name: Section name

    Returns:
        Validation results
    """
    engine = ValidationEngine()
    return engine.validate_section(section_data, section_name)


def validate_content(content: str, metadata: Dict) -> Dict[str, Any]:
    """
    Convenience function to validate generated content

    Args:
        content: Generated content
        metadata: Document metadata

    Returns:
        Validation results
    """
    engine = ValidationEngine()
    return engine.validate_generated_content(content, metadata)


if __name__ == "__main__":
    # Test the validation engine
    print("Validation Engine - Test Mode\n")

    engine = ValidationEngine()

    # Test 1: Section validation (valid)
    print("1. Testing valid section...")
    valid_section = {
        "sop_name": "Cleaning and Sanitation",
        "purpose": "To establish procedures for cleaning and sanitizing production areas to maintain GMP standards",
        "scope": "Applies to all production areas including cleanrooms and storage facilities",
    }
    result = engine.validate_section(valid_section, "scope")
    print(f"   Valid: {result['is_valid']}")
    print(f"   Completion: {result['completion_score']:.1f}%")
    print(f"   Errors: {len(result['errors'])}")

    # Test 2: Section validation (invalid)
    print("\n2. Testing invalid section...")
    invalid_section = {"sop_name": "", "purpose": "Too short"}
    result = engine.validate_section(invalid_section, "scope")
    print(f"   Valid: {result['is_valid']}")
    print(f"   Errors: {result['errors']}")

    # Test 3: Cannabis compliance
    print("\n3. Testing cannabis compliance...")
    cannabis_section = {
        "is_cannabis": True,
        "scope": "Cannabis cultivation procedures",
    }
    result = engine.validate_section(cannabis_section, "scope")
    print(f"   Valid: {result['is_valid']}")
    print(f"   Errors: {result['errors']}")

    # Test 4: Content validation
    print("\n4. Testing content validation...")
    test_content = """
## 1. Purpose
This SOP establishes procedures for change control.

## 2. Scope
Applies to all quality systems.

## 3. Responsibilities
QA Manager: Approves changes
QC Analyst: Reviews changes

## 4. Procedure
1. Submit change request
2. Review by QA
3. Implement if approved
"""
    result = engine.validate_generated_content(
        test_content, {"is_cannabis": False, "sop_type": "QA"}
    )
    print(f"   Valid: {result['is_valid']}")
    print(f"   Quality Score: {result['quality_score']:.1f}")
    print(f"   Approval Likelihood: {result['first_pass_approval_likelihood']:.1%}")

    print("\n✅ Validation Engine test complete")
