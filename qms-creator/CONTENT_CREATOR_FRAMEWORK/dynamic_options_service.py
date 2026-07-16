"""
Dynamic Options Service - Generates context-aware options for questionnaire dropdowns

This service provides smart options for questionnaire fields based on:
- Historical SOPs (what was used before)
- Facility model (rooms, equipment available)
- Cannabis GMP best practices database
- AI-generated options when needed
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DynamicOptions:
    """Container for dynamic options with source tracking"""
    options: List[str] = field(default_factory=list)
    sources: Dict[str, List[str]] = field(default_factory=dict)  # source_name -> options from that source


class DynamicOptionsService:
    """Service for generating context-aware dropdown options"""

    def __init__(self,
                 gmp_options_path: str = None,
                 facility_model_path: str = None,
                 llm_client = None):
        """
        Initialize the dynamic options service.

        Args:
            gmp_options_path: Path to cannabis_gmp_options.json
            facility_model_path: Path to facility_model.json
            llm_client: Optional LLMClient for AI option generation
        """
        base_dir = Path(__file__).parent

        if gmp_options_path is None:
            gmp_options_path = base_dir / "data" / "cannabis_gmp_options.json"
        if facility_model_path is None:
            facility_model_path = base_dir.parent / "data" / "facility_model.json"

        self.gmp_options_path = Path(gmp_options_path)
        self.facility_model_path = Path(facility_model_path)
        self.llm_client = llm_client

        self.gmp_options = self._load_gmp_options()
        self.facility_model = self._load_facility_model()

    def _load_gmp_options(self) -> Dict:
        """Load the GMP options database"""
        try:
            if self.gmp_options_path.exists():
                with open(self.gmp_options_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"GMP options file not found at {self.gmp_options_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading GMP options: {e}")
            return {}

    def _load_facility_model(self) -> Dict:
        """Load the facility model"""
        try:
            if self.facility_model_path.exists():
                with open(self.facility_model_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.info(f"Facility model not found at {self.facility_model_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading facility model: {e}")
            return {}

    def get_gmp_options(self, category: str, subcategory: str = None) -> List[str]:
        """
        Get predefined GMP options for a category.

        Args:
            category: Main category (e.g., 'equipment_types', 'ppe_types')
            subcategory: Optional subcategory (e.g., 'laboratory', 'cultivation')

        Returns:
            List of options
        """
        if category not in self.gmp_options:
            return []

        data = self.gmp_options[category]

        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if subcategory and subcategory in data:
                return data[subcategory]
            # Return all subcategory options combined
            all_options = []
            for sub_data in data.values():
                if isinstance(sub_data, list):
                    all_options.extend(sub_data)
            return all_options

        return []

    def get_facility_options(self, option_type: str) -> List[str]:
        """
        Get options from the facility model.

        Args:
            option_type: Type of facility data ('rooms', 'equipment', 'zones', 'hvac')

        Returns:
            List of options from facility model
        """
        if not self.facility_model:
            return []

        options = []

        if option_type == 'rooms':
            rooms = self.facility_model.get('rooms', [])
            for room in rooms:
                if isinstance(room, dict):
                    name = room.get('name', room.get('room_name', ''))
                    room_id = room.get('id', room.get('room_id', ''))
                    if name:
                        options.append(f"{name} ({room_id})" if room_id else name)
                elif isinstance(room, str):
                    options.append(room)

        elif option_type == 'equipment':
            equipment = self.facility_model.get('equipment', [])
            for eq in equipment:
                if isinstance(eq, dict):
                    name = eq.get('name', eq.get('equipment_name', ''))
                    eq_id = eq.get('id', eq.get('equipment_id', ''))
                    if name:
                        options.append(f"{name} ({eq_id})" if eq_id else name)
                elif isinstance(eq, str):
                    options.append(eq)

        elif option_type == 'zones':
            zones = self.facility_model.get('zones', self.facility_model.get('hvac_zones', []))
            for zone in zones:
                if isinstance(zone, dict):
                    options.append(zone.get('name', zone.get('zone_name', str(zone))))
                elif isinstance(zone, str):
                    options.append(zone)

        elif option_type == 'hvac':
            hvac = self.facility_model.get('hvac_systems', self.facility_model.get('hvac', []))
            for system in hvac:
                if isinstance(system, dict):
                    options.append(system.get('name', str(system)))
                elif isinstance(system, str):
                    options.append(system)

        return options

    def _match_question_to_category(self, question_text: str, question_id: str) -> Dict[str, str]:
        """
        Match a question to the appropriate GMP options category.

        Args:
            question_text: The question text
            question_id: The question ID

        Returns:
            Dict with 'category' and optional 'subcategory'
        """
        text_lower = question_text.lower()
        id_lower = question_id.lower()

        # Equipment matching
        if any(word in text_lower for word in ['equipment', 'instrument', 'device', 'apparatus']):
            if any(word in text_lower for word in ['lab', 'laboratory', 'analytical', 'testing']):
                return {'category': 'equipment_types', 'subcategory': 'laboratory'}
            elif any(word in text_lower for word in ['cultivation', 'grow', 'plant']):
                return {'category': 'equipment_types', 'subcategory': 'cultivation'}
            elif any(word in text_lower for word in ['production', 'packaging', 'drying']):
                return {'category': 'equipment_types', 'subcategory': 'production'}
            elif any(word in text_lower for word in ['monitor', 'logger', 'sensor']):
                return {'category': 'equipment_types', 'subcategory': 'monitoring'}
            elif any(word in text_lower for word in ['storage', 'cold', 'freez']):
                return {'category': 'equipment_types', 'subcategory': 'storage'}
            return {'category': 'equipment_types'}

        # PPE matching
        if any(word in text_lower for word in ['ppe', 'protective', 'gown', 'glove', 'safety gear']):
            return {'category': 'ppe_types'}

        # Testing methods
        if any(word in text_lower for word in ['test', 'method', 'analysis', 'analytical']):
            if any(word in text_lower for word in ['potency', 'cannabinoid', 'thc', 'cbd']):
                return {'category': 'testing_methods', 'subcategory': 'potency'}
            elif any(word in text_lower for word in ['terpene', 'volatile']):
                return {'category': 'testing_methods', 'subcategory': 'terpenes'}
            elif any(word in text_lower for word in ['microbial', 'bacteria', 'yeast', 'mold']):
                return {'category': 'testing_methods', 'subcategory': 'microbial'}
            elif any(word in text_lower for word in ['contaminant', 'pesticide', 'heavy metal', 'mycotoxin']):
                return {'category': 'testing_methods', 'subcategory': 'contaminants'}
            elif any(word in text_lower for word in ['physical', 'moisture', 'particle']):
                return {'category': 'testing_methods', 'subcategory': 'physical'}
            return {'category': 'testing_methods'}

        # Regulatory references
        if any(word in text_lower for word in ['regulatory', 'guideline', 'regulation', 'reference', 'eudralex', 'ich']):
            if 'ich' in text_lower:
                return {'category': 'regulatory_references', 'subcategory': 'ich'}
            elif 'eu' in text_lower or 'eudralex' in text_lower or 'gmp' in text_lower:
                return {'category': 'regulatory_references', 'subcategory': 'eu_gmp'}
            return {'category': 'regulatory_references'}

        # Environmental parameters
        if any(word in text_lower for word in ['environmental', 'temperature', 'humidity', 'condition']):
            if any(word in text_lower for word in ['cultivation', 'grow']):
                return {'category': 'environmental_parameters', 'subcategory': 'cultivation_rooms'}
            elif any(word in text_lower for word in ['dry', 'curing']):
                return {'category': 'environmental_parameters', 'subcategory': 'drying_rooms'}
            elif any(word in text_lower for word in ['storage', 'warehouse']):
                return {'category': 'environmental_parameters', 'subcategory': 'storage_areas'}
            elif any(word in text_lower for word in ['lab', 'laboratory']):
                return {'category': 'environmental_parameters', 'subcategory': 'laboratory'}
            return {'category': 'environmental_parameters'}

        # Training
        if any(word in text_lower for word in ['training', 'qualification', 'competency']):
            return {'category': 'training_types'}

        # Documentation
        if any(word in text_lower for word in ['document', 'record', 'log', 'batch record']):
            return {'category': 'documentation_types'}

        # Validation
        if any(word in text_lower for word in ['validation', 'validated']):
            return {'category': 'validation_types'}

        # Qualification
        if any(word in text_lower for word in ['qualification', 'iq', 'oq', 'pq']):
            return {'category': 'qualification_types'}

        # Risk assessment
        if any(word in text_lower for word in ['risk', 'assessment', 'fmea', 'haccp']):
            return {'category': 'risk_assessment_tools'}

        # Departments
        if any(word in text_lower for word in ['department', 'area', 'personnel', 'audience']):
            return {'category': 'departments'}

        # Retention periods
        if any(word in text_lower for word in ['retention', 'keep', 'archive', 'years']):
            return {'category': 'retention_periods'}

        # Product types
        if any(word in text_lower for word in ['product', 'type', 'form']):
            return {'category': 'product_types'}

        # Areas/locations
        if any(word in text_lower for word in ['area', 'room', 'location', 'facility']):
            return {'category': 'areas_locations'}

        return {}

    def enrich_question_options(self, question: Dict, sop_request: Dict = None) -> Dict:
        """
        Enrich a question with dynamic options.

        Args:
            question: Question dict with id, text, type, options, etc.
            sop_request: Optional SOP request context

        Returns:
            Enriched question with additional options and source tracking
        """
        question_id = question.get('id', '')
        question_text = question.get('text', question.get('description', ''))
        current_options = question.get('options', [])

        # Create dynamic options container
        dynamic = DynamicOptions()

        # Keep existing options
        if current_options:
            dynamic.options.extend(current_options)
            dynamic.sources['predefined'] = list(current_options)

        # Match question to category
        category_match = self._match_question_to_category(question_text, question_id)

        if category_match:
            category = category_match.get('category')
            subcategory = category_match.get('subcategory')

            # Get GMP options
            gmp_opts = self.get_gmp_options(category, subcategory)
            if gmp_opts:
                new_opts = [opt for opt in gmp_opts if opt not in dynamic.options]
                dynamic.options.extend(new_opts[:15])  # Limit to 15 new options
                if new_opts:
                    dynamic.sources['gmp_database'] = new_opts[:15]

        # Get facility options for location/equipment questions
        if any(word in question_text.lower() for word in ['area', 'room', 'location', 'where']):
            facility_opts = self.get_facility_options('rooms')
            if facility_opts:
                new_opts = [opt for opt in facility_opts if opt not in dynamic.options]
                dynamic.options.extend(new_opts)
                if new_opts:
                    dynamic.sources['facility_model'] = new_opts

        if any(word in question_text.lower() for word in ['equipment', 'device', 'instrument']):
            facility_eq = self.get_facility_options('equipment')
            if facility_eq:
                new_opts = [opt for opt in facility_eq if opt not in dynamic.options]
                dynamic.options.extend(new_opts[:10])
                if new_opts:
                    dynamic.sources.setdefault('facility_model', []).extend(new_opts[:10])

        # Remove duplicates while preserving order
        seen = set()
        unique_options = []
        for opt in dynamic.options:
            if opt not in seen:
                seen.add(opt)
                unique_options.append(opt)

        # Update question
        question['options'] = unique_options
        question['option_sources'] = dynamic.sources
        question['dynamic_options_applied'] = True

        return question

    def enrich_schema_options(self, schema: Dict, sop_request: Dict = None) -> Dict:
        """
        Enrich all questions in a schema with dynamic options.

        Args:
            schema: Full questionnaire schema
            sop_request: Optional SOP request context

        Returns:
            Enriched schema
        """
        enriched = dict(schema)

        for section_key, section_data in enriched.items():
            if section_key in ['metadata', 'output_config']:
                continue

            if isinstance(section_data, list):
                for i, question in enumerate(section_data):
                    if isinstance(question, dict):
                        enriched[section_key][i] = self.enrich_question_options(question, sop_request)

            elif isinstance(section_data, dict):
                for q_key, q_data in section_data.items():
                    if isinstance(q_data, dict) and 'type' in q_data:
                        q_data['id'] = q_key
                        enriched[section_key][q_key] = self.enrich_question_options(q_data, sop_request)

        return enriched

    async def generate_ai_options(self, question: Dict, sop_request: Dict, num_options: int = 5) -> List[str]:
        """
        Generate additional options using AI.

        Args:
            question: Question dict
            sop_request: SOP context
            num_options: Number of options to generate

        Returns:
            List of AI-generated options
        """
        if not self.llm_client:
            return []

        question_text = question.get('text', question.get('description', ''))
        current_options = question.get('options', [])

        system_prompt = """You are a QMS expert for Cannabis EU GMP facilities.
Generate appropriate dropdown options for questionnaire questions.
Options should be practical, specific, and industry-standard."""

        user_prompt = f"""Question: {question_text}
SOP Context: {sop_request.get('sop_name', 'Unknown')} ({sop_request.get('sop_type', 'SOP')})

Existing options: {current_options[:5] if current_options else 'None'}

Generate {num_options} additional relevant options that are NOT already in the list.
Return as a JSON array of strings only, no other text."""

        try:
            response = self.llm_client.generate_text(system_prompt, user_prompt, temperature=0.5)

            # Parse JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                options = json.loads(json_match.group())
                if isinstance(options, list):
                    return [str(opt) for opt in options if opt and str(opt) not in current_options]

        except Exception as e:
            logger.error(f"AI option generation failed: {e}")

        return []


# Convenience function
def get_options_for_question(question_text: str, question_id: str = "",
                             sop_request: Dict = None) -> Dict[str, List[str]]:
    """
    Get all available options for a question.

    Args:
        question_text: The question text
        question_id: Optional question ID
        sop_request: Optional SOP context

    Returns:
        Dict with 'options' list and 'sources' dict
    """
    service = DynamicOptionsService()
    question = {
        'id': question_id,
        'text': question_text,
        'options': []
    }
    enriched = service.enrich_question_options(question, sop_request)
    return {
        'options': enriched.get('options', []),
        'sources': enriched.get('option_sources', {})
    }
