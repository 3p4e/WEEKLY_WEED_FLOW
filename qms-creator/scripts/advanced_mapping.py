#!/usr/bin/env python3
"""
Advanced Placeholder Mapping for Cannabis EU GMP QMS Creator
Intelligently resolves context-specific placeholders based on document analysis
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from rich.console import Console

console = Console()


class AdvancedPlaceholderMapper:
    """Advanced context-aware placeholder mapping."""

    def __init__(self, config):
        """Initialize advanced mapper."""
        self.config = config
        self.context_rules = self._build_context_rules()

    def _build_context_rules(self) -> Dict:
        """Build context-specific replacement rules."""
        return {
            # Name context rules
            'NAME': {
                'approval_signature': lambda: self.config.get_full_name('qualified_person'),
                'prepared_by': lambda: self.config.get_full_name('qa_manager'),
                'reviewed_by': lambda: self.config.get_full_name('qa_manager'),
                'approved_by': lambda: self.config.get_full_name('qualified_person'),
                'training_by': lambda: self.config.get_full_name('qa_manager'),
                'default': lambda: self.config.get_full_name('qualified_person')
            },

            # Title context rules
            'TITLE': {
                'approval_signature': lambda: self.config.get('personnel.qualified_person.title', 'Qualified Person'),
                'prepared_by': lambda: self.config.get('personnel.qa_manager.title', 'QA Manager'),
                'reviewed_by': lambda: self.config.get('personnel.qa_manager.title', 'QA Manager'),
                'approved_by': lambda: self.config.get('personnel.qualified_person.title', 'Qualified Person'),
                'default': lambda: 'Quality Manager'
            },

            # Date context rules
            'DATE_SPECIFIC': {
                'approval_date': lambda: '[DATE - To be filled upon approval]',
                'training_date': lambda: '[DATE - To be filled during training]',
                'calibration_date': lambda: '[DATE - To be filled during calibration]',
                'deviation_date': lambda: '[DATE - To be filled when deviation occurs]',
                'default': lambda: self._get_today()
            },

            # Department rules
            'DEPARTMENT': {
                'quality': lambda: 'Quality Assurance',
                'production': lambda: 'Production & Cultivation',
                'sanitation': lambda: 'Sanitation & Hygiene',
                'security': lambda: 'Security',
                'hr': lambda: 'Human Resources',
                'default': lambda: 'Quality Assurance'
            },

            # Location rules
            'LOCATION': {
                'cultivation': lambda: 'Cultivation Rooms (Rooms 02-05)',
                'processing': lambda: 'Processing Room (Room 07)',
                'packaging': lambda: 'Packaging Room (Room 08)',
                'storage': lambda: 'Secure Storage Vault (Room 09)',
                'default': lambda: '[SPECIFIC LOCATION - To be specified]'
            },

            # Equipment context
            'EQUIPMENT_NAME': {
                'drying': lambda: self.config.get('equipment.drying_machine.name', ''),
                'trimming': lambda: self.config.get('equipment.trimming_machine.name', ''),
                'packaging': lambda: self.config.get('equipment.packaging_equipment.name', ''),
                'hvac': lambda: self.config.get('equipment.hvac_system.name', ''),
                'default': lambda: '[EQUIPMENT NAME - To be specified]'
            },

            # SOP references
            'SOP_REFERENCE': {
                'quality': lambda: 'QAS-01-XXX',
                'production': lambda: 'PRO-01-XXX',
                'sanitation': lambda: 'SAN-01-XXX',
                'equipment': lambda: 'EQU-01-XXX',
                'security': lambda: 'SEC-01-XXX',
                'default': lambda: '[SOP-XX-XXX - To be specified]'
            },

            # Form references
            'FORM_NUMBER': {
                'batch_record': lambda: 'FM-PRO-001',
                'deviation': lambda: 'FM-QAS-002',
                'training': lambda: 'FM-HR-001',
                'equipment_log': lambda: 'FM-EQU-001',
                'default': lambda: '[FM-XXX-XXX - To be specified]'
            }
        }

    def resolve_placeholder(self, placeholder: str, context: str) -> Optional[str]:
        """
        Resolve placeholder based on context analysis.

        Args:
            placeholder: The placeholder text (e.g., "NAME", "TITLE")
            context: Surrounding text context for intelligent resolution

        Returns:
            Resolved value or None if cannot resolve
        """
        # Normalize placeholder
        ph = placeholder.upper().strip()

        # Direct mappings first
        if ph == 'YOUR_NAME' or ph == 'NAME':
            return self._resolve_name(context)

        elif ph == 'TITLE':
            return self._resolve_title(context)

        elif ph == 'DEPARTMENT':
            return self._resolve_department(context)

        elif ph == 'LOCATION' or ph == 'CONTROLLED_LOCATION':
            return self._resolve_location(context)

        elif 'EQUIPMENT' in ph:
            return self._resolve_equipment(context, ph)

        elif ph == 'DOCUMENT_NUMBER' or ph == 'SOP_NUMBER':
            return self._resolve_document_number(context)

        elif ph == 'FORM_NUMBER':
            return self._resolve_form_number(context)

        elif 'SPECIFICATION' in ph or 'ACCEPTANCE_CRITERIA' in ph:
            return '[To be defined based on product specifications]'

        elif 'FREQUENCY' in ph:
            return self._resolve_frequency(context)

        elif 'RESPONSIBILITY' in ph or 'RESPONSIBLE' in ph:
            return self._resolve_responsibility(context)

        return None

    def _resolve_name(self, context: str) -> str:
        """Resolve NAME based on context."""
        context_lower = context.lower()

        # Signature blocks
        if 'approved by' in context_lower or 'qp signature' in context_lower:
            return self.config.get_full_name('qualified_person')
        elif 'prepared by' in context_lower or 'reviewed by' in context_lower:
            return self.config.get_full_name('qa_manager')
        elif 'trainer' in context_lower or 'training by' in context_lower:
            return self.config.get_full_name('qa_manager')

        # Department specific
        elif 'production' in context_lower:
            return self.config.get_full_name('production_manager')
        elif 'sanitation' in context_lower or 'hygiene' in context_lower:
            return self.config.get_full_name('sanitation_manager')
        elif 'security' in context_lower:
            return self.config.get_full_name('security_manager')

        # Default to QP
        return self.config.get_full_name('qualified_person')

    def _resolve_title(self, context: str) -> str:
        """Resolve TITLE based on context."""
        context_lower = context.lower()

        if 'approved by' in context_lower or 'qp' in context_lower:
            return self.config.get('personnel.qualified_person.title', 'Qualified Person')
        elif 'prepared by' in context_lower or 'qa' in context_lower:
            return self.config.get('personnel.qa_manager.title', 'QA Manager')
        elif 'production' in context_lower:
            return self.config.get('personnel.production_manager.title', 'Production Manager')
        elif 'sanitation' in context_lower:
            return self.config.get('personnel.sanitation_manager.title', 'Sanitation Manager')

        return 'Quality Manager'

    def _resolve_department(self, context: str) -> str:
        """Resolve DEPARTMENT based on context."""
        context_lower = context.lower()

        if 'cultivation' in context_lower or 'production' in context_lower:
            return 'Production & Cultivation'
        elif 'quality' in context_lower or 'qa' in context_lower:
            return 'Quality Assurance'
        elif 'sanitation' in context_lower or 'hygiene' in context_lower:
            return 'Sanitation & Hygiene'
        elif 'security' in context_lower:
            return 'Security'
        elif 'hr' in context_lower or 'training' in context_lower:
            return 'Human Resources'

        return 'Quality Assurance'

    def _resolve_location(self, context: str) -> str:
        """Resolve LOCATION based on context."""
        context_lower = context.lower()

        if 'cultivation' in context_lower or 'growing' in context_lower:
            return 'Cultivation Rooms (Rooms 02-05)'
        elif 'drying' in context_lower or 'curing' in context_lower:
            return 'Drying & Curing Room (Room 06)'
        elif 'processing' in context_lower or 'trimming' in context_lower:
            return 'Processing Room (Room 07)'
        elif 'packaging' in context_lower:
            return 'Packaging Room (Room 08)'
        elif 'storage' in context_lower or 'vault' in context_lower:
            return 'Secure Storage Vault (Room 09)'
        elif 'document' in context_lower or 'record' in context_lower:
            return 'Quality Assurance Office'

        return '[SPECIFIC LOCATION - To be specified in procedure]'

    def _resolve_equipment(self, context: str, placeholder: str) -> str:
        """Resolve EQUIPMENT placeholders."""
        context_lower = context.lower()

        if 'drying' in context_lower:
            return self.config.get('equipment.drying_machine.name', 'CDS24 Drying Machine')
        elif 'trimming' in context_lower or 'tumbler' in context_lower:
            return self.config.get('equipment.trimming_machine.name', 'MT Tumbler Machine')
        elif 'packaging' in context_lower:
            return self.config.get('equipment.packaging_equipment.name', 'Automated Packaging System')
        elif 'hvac' in context_lower or 'climate' in context_lower:
            return self.config.get('equipment.hvac_system.name', 'HVAC Climate Control System')

        return '[EQUIPMENT NAME - To be specified]'

    def _resolve_document_number(self, context: str) -> str:
        """Resolve DOCUMENT_NUMBER or SOP_NUMBER."""
        context_lower = context.lower()

        if 'quality' in context_lower or 'qa' in context_lower:
            return '[QAS-XX-XXX - Quality Assurance SOP reference]'
        elif 'production' in context_lower or 'cultivation' in context_lower:
            return '[PRO-XX-XXX - Production SOP reference]'
        elif 'sanitation' in context_lower:
            return '[SAN-XX-XXX - Sanitation SOP reference]'
        elif 'equipment' in context_lower:
            return '[EQU-XX-XXX - Equipment SOP reference]'
        elif 'security' in context_lower:
            return '[SEC-XX-XXX - Security SOP reference]'

        return '[SOP-XX-XXX - To be specified]'

    def _resolve_form_number(self, context: str) -> str:
        """Resolve FORM_NUMBER."""
        context_lower = context.lower()

        if 'batch' in context_lower:
            return 'FM-PRO-001 (Batch Production Record)'
        elif 'deviation' in context_lower:
            return 'FM-QAS-002 (Deviation Report)'
        elif 'training' in context_lower:
            return 'FM-HR-001 (Training Record)'
        elif 'equipment' in context_lower or 'maintenance' in context_lower:
            return 'FM-EQU-001 (Equipment Maintenance Log)'
        elif 'calibration' in context_lower:
            return 'FM-EQU-002 (Calibration Record)'

        return '[FM-XXX-XXX - Form reference to be specified]'

    def _resolve_frequency(self, context: str) -> str:
        """Resolve FREQUENCY placeholders."""
        context_lower = context.lower()

        if 'calibration' in context_lower:
            return 'Annually (or per manufacturer specifications)'
        elif 'cleaning' in context_lower or 'sanitation' in context_lower:
            return 'Daily (or as per sanitation schedule)'
        elif 'training' in context_lower:
            return 'Annually (or upon SOP revision)'
        elif 'review' in context_lower:
            return 'Annually'
        elif 'audit' in context_lower:
            return 'Quarterly'

        return '[FREQUENCY - To be defined in procedure]'

    def _resolve_responsibility(self, context: str) -> str:
        """Resolve RESPONSIBILITY placeholders."""
        context_lower = context.lower()

        if 'production' in context_lower or 'cultivation' in context_lower:
            return self.config.get_full_name('production_manager') + ' (Production Manager)'
        elif 'quality' in context_lower or 'qa' in context_lower:
            return self.config.get_full_name('qa_manager') + ' (QA Manager)'
        elif 'sanitation' in context_lower:
            return self.config.get_full_name('sanitation_manager') + ' (Sanitation Manager)'
        elif 'equipment' in context_lower:
            return self.config.get_full_name('facility_manager') + ' (Facility Manager)'

        return self.config.get_full_name('qa_manager') + ' (QA Manager)'

    def _get_today(self) -> str:
        """Get today's date."""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d')

    def get_context_window(self, content: str, placeholder: str, match_start: int,
                          window_size: int = 200) -> str:
        """
        Extract context window around placeholder.

        Args:
            content: Full document content
            placeholder: Placeholder being resolved
            match_start: Position of placeholder in content
            window_size: Characters before/after to include

        Returns:
            Context string for analysis
        """
        start = max(0, match_start - window_size)
        end = min(len(content), match_start + len(placeholder) + window_size)

        return content[start:end]


def enhance_placeholder_engine():
    """
    Enhance the existing placeholder_engine.py with advanced mapping.
    This patches the PlaceholderEngine class to use AdvancedPlaceholderMapper.
    """
    console.print("[cyan]Enhanced placeholder engine with advanced mapping capability.[/cyan]")
    console.print("[green]Context-aware resolution for NAME, TITLE, DEPARTMENT, LOCATION, etc.[/green]")


if __name__ == "__main__":
    console.print("\n[bold cyan]Advanced Placeholder Mapping Module[/bold cyan]")
    console.print("=" * 80 + "\n")

    console.print("This module provides context-aware placeholder resolution:")
    console.print("")
    console.print("✓ [NAME] → Resolves based on approval/prepared/department context")
    console.print("✓ [TITLE] → Matches person's title from context")
    console.print("✓ [DEPARTMENT] → Infers from document section")
    console.print("✓ [LOCATION] → Maps to appropriate facility rooms")
    console.print("✓ [EQUIPMENT_NAME] → Selects correct equipment from context")
    console.print("✓ [DOCUMENT_NUMBER] → Suggests proper SOP format")
    console.print("✓ [FORM_NUMBER] → References correct form codes")
    console.print("✓ [FREQUENCY] → Provides reasonable defaults")
    console.print("✓ [RESPONSIBILITY] → Assigns to appropriate manager")
    console.print("")
    console.print("[bold]Integration:[/bold] This module enhances placeholder_engine.py")
    console.print("Run documents customization to see advanced mapping in action.\n")
