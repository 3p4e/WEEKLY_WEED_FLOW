#!/usr/bin/env python3
"""
Regulatory Auditor for Cannabis EU GMP QMS
Uses LLM to perform semantic validation of generated SOPs against regulatory frameworks

Author: QMS Development Team
Date: 2025-01-22
Version: 1.0
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests
from glossary_manager import GlossaryManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RegulatoryAuditor:
    """AI-powered regulatory auditor for QMS documents"""

    def __init__(
        self,
        glossary_path: Optional[str] = None,
    ):
        # Initialize unified LLM Client
        from llm_client import LLMClient
        self.llm_client = LLMClient()

        # Initialize glossary manager for terminology consistency
        if glossary_path is None:
            # Default to cannabis glossary in glossaries directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            glossary_path = os.path.join(
                current_dir, "glossaries", "cannabis_glossary.yaml"
            )

        try:
            self.glossary = GlossaryManager(glossary_path)
            logger.info(f"Loaded glossary with {len(self.glossary.terms)} terms")
        except Exception as e:
            logger.warning(
                f"Could not load glossary: {e}. Translation will use LLM only."
            )
            self.glossary = None

    def audit_sop(self, content: str, framework_details: List[Dict]) -> Dict[str, Any]:
        """Perform a regulatory audit of the SOP content"""

        framework_text = ""
        framework_names = []
        for f in framework_details:
            framework_names.append(f.get("framework", "General GMP"))
            framework_text += (
                f"\n- {f.get('framework')}: {', '.join(f.get('requirements', []))}"
            )

        system_prompt = "You are a Senior GMP Regulatory Auditor specializing in EU GMP (EudraLex Volume 4) and ICH quality guidelines."
        user_prompt = f"""
Your task is to review the following Standard Operating Procedure (SOP) content for compliance and quality.

### SOP CONTENT:
{content}

### REGULATORY FRAMEWORK:
{framework_text}

### AUDIT CRITERIA:
1. Is the Purpose clearly defined and aligned with GMP?
2. Is the Scope appropriate and covers necessary interfaces?
3. Are Responsibilities clearly assigned to specific roles?
4. Is the Procedure detailed enough for consistent execution (operator-friendly)?
5. Does it meet specific requirements of {", ".join(framework_names)}?
6. Are there clear references to other QMS documents and forms?
7. Is the technical language accurate for a pharmaceutical/cannabis manufacturing environment?

### RESPONSE FORMAT:
Return a JSON object with the following fields:
- "compliance_score": (Integer 0-100)
- "critical_gaps": (List of strings)
- "minor_observations": (List of strings)
- "strengths": (List of strings)
- "verdict": ("PASS", "FAIL", or "CONDITIONAL PASS")
- "summary": (Short string)

Ensure the output is strictly valid JSON.
"""

        try:
            # Use LLMClient for generation
            result_text = self.llm_client.generate_text(system_prompt, user_prompt)
            
            # Extract JSON from response if needed (sometimes LLMs add markdown boxes)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            return json.loads(result_text)

        except Exception as e:
            logger.error(f"Audit Exception: {e}")
            return self._get_error_report(str(e))

    def translate(self, text: str, target_lang: str = "Macedonian") -> str:
        """
        Translate text while preserving Markdown structure and technical terms.
        Uses glossary-first approach for consistent terminology.
        """

        # Map language names to codes
        lang_code_map = {"Macedonian": "mk", "English": "en", "mk": "mk", "en": "en"}
        target_lang_code = lang_code_map.get(target_lang, "mk")

        # Step 1: Apply glossary translations for known terms
        if self.glossary:
            logger.info(
                "Applying glossary-based translation for consistent terminology"
            )
            glossary_translated = self.glossary.translate_text(
                text,
                source_lang="en",
                target_lang=target_lang_code,
                preserve_technical=True,
            )
        else:
            glossary_translated = text
            logger.info("Glossary not available, proceeding with LLM-only translation")

        # Step 2: LLM translation for non-glossary content
        system_prompt = "You are a professional translator specializing in pharmaceutical and GMP documentation."
        user_prompt = f"""
Translate the following pharmaceutical/GMP document content into {target_lang}.
IMPORTANT: Some technical terms have already been translated. Do NOT re-translate terms that are already in {target_lang}.
Ensure that:
1. Already-translated technical terms (often in bold or quotes) are kept as-is
2. Markdown structure (headings, lists, bold text) is PRESERVED exactly
3. The tone remains professional and formal
4. Only translate English text that remains

CONTENT TO TRANSLATE:
{glossary_translated}

Only return the translated text. Do not add any introductory or concluding remarks.
"""
        try:
            final_text = self.llm_client.generate_text(system_prompt, user_prompt)
        except Exception as e:
            logger.warning(
                f"LLM translation exception: {e}. Using glossary-only translation."
            )
            final_text = glossary_translated

        # Step 3: Validate terminology consistency
        if self.glossary:
            validation = self.glossary.validate_terminology(
                final_text, target_lang_code
            )
            consistency_score = validation["consistency_score"]

            if consistency_score < 95:
                logger.warning(
                    f"Translation consistency below threshold: {consistency_score:.1f}/100. "
                    f"Issues: {validation['issues']}"
                )
            else:
                logger.info(
                    f"Translation consistency validated: {consistency_score:.1f}/100"
                )

        return final_text

    def _get_error_report(self, message: str) -> Dict[str, Any]:
        """Return a basic error report if audit fails"""
        return {
            "compliance_score": 0,
            "critical_gaps": [f"Audit failed: {message}"],
            "minor_observations": [],
            "strengths": [],
            "verdict": "FAIL",
            "summary": "Technical error during regulatory audit.",
        }


if __name__ == "__main__":
    # Test Auditor
    auditor = RegulatoryAuditor()
    test_content = """
# SOP for Cleaning
Purpose: To clean things.
Scope: All areas.
Responsibilities: Everyone.
Procedure: Use soap and water.
"""
    test_framework = [
        {
            "framework": "EU GMP Annex 15",
            "requirements": ["Validated cleaning procedures", "Residue limits"],
        }
    ]

    report = auditor.audit_sop(test_content, test_framework)
    print(json.dumps(report, indent=2))
