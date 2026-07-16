"""
Document Code Service - Auto-assigns document codes based on SOP title analysis

This service analyzes SOP titles using AI to determine the appropriate department
and family, then queries the document registry to find the next available code.
"""

import os
import re
import json
import logging
import yaml
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class DocumentCodeSuggestion:
    """Represents a suggested document code with metadata"""
    code: str
    department: str
    department_name: str
    family: str
    family_name: str
    sop_number: int
    confidence: float
    reasoning: str

# Department and family definitions
DEPARTMENT_FAMILIES = {
    "QAS_01": {
        "name": "Quality Management & Policy",
        "keywords": ["quality manual", "quality policy", "organization chart", "sop for writing sops", "site master file", "management review", "product quality review", "qms"]
    },
    "QAS_02": {
        "name": "Documentation Control",
        "keywords": ["document control", "document management", "records management", "good documentation practice", "gdp", "logbook control"]
    },
    "QAS_03": {
        "name": "Validation & Qualification",
        "keywords": ["validation", "qualification", "iq", "oq", "pq", "validation master plan", "process validation", "cleaning validation", "method validation"]
    },
    "QAS_04": {
        "name": "Risk Management",
        "keywords": ["risk management", "fmea", "risk assessment", "hazard analysis"]
    },
    "QAS_05": {
        "name": "CAPA & Deviations",
        "keywords": ["capa", "corrective", "preventive", "deviation", "non-conformance", "investigation", "root cause"]
    },
    "SAN_01": {
        "name": "Cleaning Procedures",
        "keywords": ["cleaning", "sanitation", "sanitization", "disinfection", "hygiene", "gmp areas", "logbook", "cleaning checklist"]
    },
    "SAN_02": {
        "name": "Gowning & Material Transfer",
        "keywords": ["gowning", "personnel hygiene", "material transfer", "white zone", "black zone", "airlock", "changing room"]
    },
    "PRO_01": {
        "name": "Cultivation Processes",
        "keywords": ["cultivation", "growing", "mother plants", "cloning", "veg", "flower", "flowering", "harvest", "trimming", "plant health"]
    },
    "PRO_02": {
        "name": "IPM & Plant Nutrition",
        "keywords": ["ipm", "pest management", "nutrition", "fertilizer", "irrigation", "pesticides", "biological control"]
    },
    "PRO_03": {
        "name": "Processing Operations",
        "keywords": ["processing", "production", "drying", "curing", "packaging", "labeling", "extraction", "formulation"]
    },
    "SEC_01": {
        "name": "Facility Security",
        "keywords": ["security", "access control", "visitor", "limited access", "alarm", "surveillance", "cctv"]
    },
    "REC_01": {
        "name": "Inventory & Procurement",
        "keywords": ["inventory", "stock", "warehouse", "procurement", "receiving", "shipping", "reconciliation"]
    },
    "HRM_01": {
        "name": "Personnel & Training",
        "keywords": ["hr", "personnel", "training", "hiring", "induction", "staff", "competency", "qualification"]
    },
    "EQU_01": {
        "name": "Equipment Operation",
        "keywords": ["equipment", "machine", "operating", "instrument", "startup", "shutdown"]
    },
    "EQU_02": {
        "name": "Calibration & Maintenance",
        "keywords": ["calibration", "maintenance", "preventative maintenance", "repair", "service", "metrology"]
    }
}


class DocumentCodeService:
    """Service for auto-assigning document codes based on SOP title analysis"""

    def __init__(self, registry_path: str = None, llm_client = None):
        """
        Initialize the document code service.

        Args:
            registry_path: Path to the document_registry.yaml file
            llm_client: Optional LLMClient instance for AI-based classification
        """
        if registry_path is None:
            base_dir = Path(__file__).parent.parent
            registry_path = base_dir / "config" / "document_registry.yaml"

        self.registry_path = Path(registry_path)
        self.llm_client = llm_client
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict:
        """Load the document registry from YAML file"""
        try:
            if self.registry_path.exists():
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            else:
                logger.warning(f"Registry file not found at {self.registry_path}")
                return {"families": {}}
        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            return {"families": {}}

    def _get_existing_codes(self, family: str) -> List[int]:
        """Get all existing SOP numbers for a given family"""
        existing_numbers = []

        families = self.registry.get("families", {})
        if family in families:
            sops = families[family].get("sops", {})
            for code in sops.keys():
                # Extract the SOP number from codes like "QC_01.08"
                match = re.match(rf"{re.escape(family)}\.(\d+)", code)
                if match:
                    existing_numbers.append(int(match.group(1)))

        return sorted(existing_numbers)

    def _get_next_available_number(self, family: str) -> int:
        """Get the next available SOP number for a family"""
        existing = self._get_existing_codes(family)
        if not existing:
            return 1
        return max(existing) + 1

    def _keyword_match_score(self, title: str, keywords: List[str]) -> float:
        """Calculate keyword match score for title against a list of keywords"""
        title_lower = title.lower()
        matches = 0
        total_weight = 0

        for keyword in keywords:
            keyword_lower = keyword.lower()
            weight = len(keyword.split())  # Multi-word keywords have higher weight
            total_weight += weight

            if keyword_lower in title_lower:
                matches += weight

        return matches / total_weight if total_weight > 0 else 0

    def analyze_title_local(self, title: str, keywords: List[str] = None) -> Tuple[str, float, str]:
        """
        Analyze title using local keyword matching (no LLM required).

        Args:
            title: The SOP title to analyze
            keywords: Optional additional keywords to consider

        Returns:
            Tuple of (family, confidence, reasoning)
        """
        combined_text = title
        if keywords:
            combined_text += " " + " ".join(keywords)

        scores = {}
        for family, info in DEPARTMENT_FAMILIES.items():
            score = self._keyword_match_score(combined_text, info["keywords"])
            scores[family] = score

        # Get the best match
        best_family = max(scores, key=scores.get)
        best_score = scores[best_family]

        # Calculate confidence (scale 0-1)
        if best_score > 0.3:
            confidence = min(0.95, 0.6 + best_score)
        elif best_score > 0.1:
            confidence = 0.5 + best_score
        else:
            confidence = 0.3 + best_score

        # Build reasoning
        matched_keywords = []
        for kw in DEPARTMENT_FAMILIES[best_family]["keywords"]:
            if kw.lower() in combined_text.lower():
                matched_keywords.append(kw)

        reasoning = f"Matched keywords: {', '.join(matched_keywords[:5])}" if matched_keywords else "No strong keyword matches"

        return best_family, confidence, reasoning

    async def analyze_title_with_ai(self, title: str, keywords: List[str] = None) -> Tuple[str, float, str]:
        """
        Analyze title using AI for more accurate classification.

        Args:
            title: The SOP title to analyze
            keywords: Optional additional keywords to consider

        Returns:
            Tuple of (family, confidence, reasoning)
        """
        if not self.llm_client:
            return self.analyze_title_local(title, keywords)

        # Build the family options for the prompt
        family_options = "\n".join([
            f"- {family}: {info['name']}"
            for family, info in DEPARTMENT_FAMILIES.items()
        ])

        system_prompt = """You are a QMS document specialist for Cannabis EU GMP facilities.
Your task is to classify SOP titles into the appropriate department family.

Available families:
""" + family_options + """

Respond with a JSON object only, no other text:
{"family": "XX_NN", "confidence": 0.0-1.0, "reasoning": "explanation"}"""

        user_prompt = f"""Classify this SOP title: "{title}"
Additional keywords: {', '.join(keywords) if keywords else 'None'}

Return JSON only."""

        try:
            response = self.llm_client.generate_text(system_prompt, user_prompt, temperature=0.3)

            # Parse JSON response
            json_match = re.search(r'\{[^{}]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                family = result.get("family", "QA_00")
                confidence = float(result.get("confidence", 0.7))
                reasoning = result.get("reasoning", "AI classification")

                # Validate family exists
                if family not in DEPARTMENT_FAMILIES:
                    logger.warning(f"AI returned unknown family {family}, falling back to local")
                    return self.analyze_title_local(title, keywords)

                return family, confidence, reasoning
            else:
                logger.warning("Could not parse AI response, falling back to local")
                return self.analyze_title_local(title, keywords)

        except Exception as e:
            logger.error(f"AI classification failed: {e}, falling back to local")
            return self.analyze_title_local(title, keywords)

    def suggest_document_code(self, title: str, keywords: List[str] = None, use_ai: bool = False) -> DocumentCodeSuggestion:
        """
        Suggest a document code for the given SOP title.

        Args:
            title: The SOP title
            keywords: Optional list of keywords to help with classification
            use_ai: Whether to use AI for classification (requires llm_client)

        Returns:
            DocumentCodeSuggestion with the suggested code and metadata
        """
        # For now, always use local keyword matching to avoid async issues
        # AI classification can be added later with proper async handling
        family, confidence, reasoning = self.analyze_title_local(title, keywords)

        # Get the next available number
        next_number = self._get_next_available_number(family)

        # Build the code: Purely Plant standard: PREFIX - XX.YY.00
        dept_prefix, family_num = family.split("_")
        code = f"{dept_prefix} - {family_num}.{next_number:02d}.00"

        # Get department info
        dept_code = family.split("_")[0]
        family_info = DEPARTMENT_FAMILIES.get(family, {"name": "Unknown"})

        return DocumentCodeSuggestion(
            code=code,
            department=dept_code,
            department_name=family_info["name"],
            family=family,
            family_name=family_info["name"],
            sop_number=next_number,
            confidence=confidence,
            reasoning=reasoning
        )

    def validate_code_format(self, code: str) -> bool:
        """Validate that a code follows the expected format"""
        # Pattern like QAS - 01.01.00 or QAS_01.01
        pattern = r'^([A-Z]{2,4}\s-\s\d{2}\.\d{2}\.\d{2}|[A-Z]{2,4}_\d{2}\.\d{2})$'
        return bool(re.match(pattern, code))

    def code_exists(self, code: str) -> bool:
        """Check if a code already exists in the registry"""
        families = self.registry.get("families", {})
        for family_data in families.values():
            if code in family_data.get("sops", {}):
                return True
        return False

    def get_all_families(self) -> Dict[str, str]:
        """Get all available families and their names"""
        return {family: info["name"] for family, info in DEPARTMENT_FAMILIES.items()}

    def get_family_codes(self, family: str) -> List[str]:
        """Get all existing codes for a family"""
        codes = []
        families = self.registry.get("families", {})
        if family in families:
            codes = list(families[family].get("sops", {}).keys())
        return sorted(codes)


# Convenience function for API usage
def suggest_code(title: str, keywords: List[str] = None,
                 registry_path: str = None, llm_client = None) -> Dict:
    """
    Convenience function to suggest a document code.

    Args:
        title: SOP title
        keywords: Optional keywords
        registry_path: Optional path to registry YAML
        llm_client: Optional LLMClient instance

    Returns:
        Dictionary with code suggestion data
    """
    service = DocumentCodeService(registry_path=registry_path, llm_client=llm_client)
    suggestion = service.suggest_document_code(title, keywords, use_ai=llm_client is not None)

    return {
        "code": suggestion.code,
        "department": suggestion.department,
        "department_name": suggestion.department_name,
        "family": suggestion.family,
        "family_name": suggestion.family_name,
        "sop_number": suggestion.sop_number,
        "confidence": suggestion.confidence,
        "reasoning": suggestion.reasoning
    }
