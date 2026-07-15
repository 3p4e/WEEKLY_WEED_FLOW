#!/usr/bin/env python3
"""
Glossary Manager for Bilingual Cannabis & GMP Documentation

Provides consistent terminology translation and validation across all documents.
Supports English ↔ Macedonian with cannabis-specific and GMP pharmaceutical terms.

Features:
- Load and manage YAML glossary files
- Translate individual terms with context awareness
- Translate full text with glossary preservation
- Validate terminology consistency
- Autocomplete suggestions
- Export glossary as appendix

Author: QMS Development Team
Date: 2026-01-23
Version: 1.0
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


class GlossaryManager:
    """
    Manages bilingual glossary for consistent terminology translation

    Supports:
    - English ↔ Macedonian translation
    - Cannabis-specific terminology
    - GMP pharmaceutical terms
    - Technical abbreviations preservation
    """

    def __init__(self, glossary_path: Optional[str] = None):
        """
        Initialize glossary manager

        Args:
            glossary_path: Path to YAML glossary file.
                          Defaults to CONTENT_CREATOR_FRAMEWORK/glossaries/cannabis_glossary.yaml
        """
        if glossary_path is None:
            glossary_path = os.path.join(
                os.path.dirname(__file__), "glossaries", "cannabis_glossary.yaml"
            )

        self.glossary_path = Path(glossary_path)
        self.terms = {}
        self.metadata = {}
        self._load_glossary()

    def _load_glossary(self) -> None:
        """Load glossary from YAML file"""
        if not self.glossary_path.exists():
            logger.error(f"Glossary file not found: {self.glossary_path}")
            return

        try:
            with open(self.glossary_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            self.metadata = data.get("metadata", {})
            terms_list = data.get("terms", [])

            # Index terms by English and Macedonian for fast lookup
            for term in terms_list:
                english = term.get("english", "").lower()
                macedonian = term.get("macedonian", "").lower()

                if english:
                    self.terms[english] = term
                if macedonian and macedonian != english:
                    # Also index by Macedonian for reverse lookup
                    self.terms[macedonian] = term

            logger.info(f"Loaded {len(terms_list)} terms from glossary")

        except Exception as e:
            logger.error(f"Error loading glossary: {e}")

    def get_translation(
        self, term: str, source_lang: str, target_lang: str, preserve_case: bool = True
    ) -> str:
        """
        Get translation of a single term

        Args:
            term: Term to translate
            source_lang: Source language code ('en' or 'mk')
            target_lang: Target language code ('en' or 'mk')
            preserve_case: Preserve original capitalization

        Returns:
            Translated term, or original if not found
        """
        if source_lang == target_lang:
            return term

        term_lower = term.lower()

        # Check if term exists in glossary
        if term_lower not in self.terms:
            return term

        glossary_entry = self.terms[term_lower]

        # Get translation based on target language
        if target_lang == "mk":
            translation = glossary_entry.get("macedonian", term)
        elif target_lang == "en":
            translation = glossary_entry.get("english", term)
        else:
            logger.warning(f"Unsupported target language: {target_lang}")
            return term

        # Preserve case if requested
        if preserve_case:
            if term.isupper():
                translation = translation.upper()
            elif term[0].isupper():
                translation = translation.capitalize()

        return translation

    def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        preserve_technical: bool = True,
    ) -> str:
        """
        Translate full text using glossary terms

        Args:
            text: Text to translate
            source_lang: Source language code ('en' or 'mk')
            target_lang: Target language code ('en' or 'mk')
            preserve_technical: Keep technical abbreviations (THC, CBD, HPLC) unchanged

        Returns:
            Translated text with glossary terms replaced
        """
        if source_lang == target_lang:
            return text

        translated = text

        # Sort terms by length (longest first) to avoid partial replacements
        sorted_terms = sorted(self.terms.items(), key=lambda x: len(x[0]), reverse=True)

        for term_key, term_data in sorted_terms:
            # Determine source and target terms
            if source_lang == "en":
                source_term = term_data.get("english", "")
                target_term = term_data.get("macedonian", source_term)
            else:
                source_term = term_data.get("macedonian", "")
                target_term = term_data.get("english", source_term)

            if not source_term or not target_term:
                continue

            # Check if we should preserve technical terms
            if preserve_technical:
                # Preserve abbreviations (all caps, 2-5 letters)
                if source_term.isupper() and 2 <= len(source_term) <= 5:
                    continue

            # Replace with word boundaries to avoid partial matches
            pattern = r"\b" + re.escape(source_term) + r"\b"

            # Case-insensitive replacement with case preservation
            def replace_with_case(match):
                matched_text = match.group(0)
                if matched_text.isupper():
                    return target_term.upper()
                elif matched_text[0].isupper():
                    return target_term.capitalize()
                else:
                    return target_term

            translated = re.sub(
                pattern, replace_with_case, translated, flags=re.IGNORECASE
            )

        return translated

    def get_terms_by_category(self, category: str) -> List[Dict]:
        """
        Get all terms in a specific category

        Args:
            category: Category name (e.g., 'cannabinoids', 'gmp_pharmaceutical')

        Returns:
            List of term dictionaries
        """
        terms = []
        for term_data in self.terms.values():
            if term_data.get("category") == category:
                # Avoid duplicates (terms indexed by both languages)
                if term_data not in terms:
                    terms.append(term_data)

        return sorted(terms, key=lambda x: x.get("english", ""))

    def validate_terminology(self, text: str, language: str = "mk") -> Dict:
        """
        Validate terminology consistency in text

        Args:
            text: Text to validate
            language: Language of text ('en' or 'mk')

        Returns:
            Dictionary with validation results:
            - consistency_score: 0-100
            - term_count: Number of glossary terms found
            - non_standard: List of terms not in glossary
            - issues: List of consistency issues
        """
        text_lower = text.lower()

        # Find all glossary terms in text
        found_terms = []
        for term_key, term_data in self.terms.items():
            if language == "en":
                check_term = term_data.get("english", "").lower()
            else:
                check_term = term_data.get("macedonian", "").lower()

            if check_term and check_term in text_lower:
                found_terms.append(term_data)

        # Identify non-standard terms (cannabis/GMP words not in glossary)
        cannabis_keywords = [
            "cannabis",
            "cannabinoid",
            "thc",
            "cbd",
            "terpene",
            "канабис",
            "канабиноид",
        ]
        gmp_keywords = [
            "batch",
            "validation",
            "qualification",
            "gmp",
            "партија",
            "валидација",
            "квалификација",
        ]

        non_standard = []
        for keyword in cannabis_keywords + gmp_keywords:
            if keyword in text_lower:
                # Check if it's in glossary
                if keyword not in self.terms:
                    non_standard.append(keyword)

        # Calculate consistency score
        # Base score: 100 if using glossary terms
        # Penalty: -10 per non-standard term
        base_score = 100 if found_terms else 80
        penalty = min(len(non_standard) * 10, 50)
        consistency_score = max(0, base_score - penalty)

        return {
            "consistency_score": consistency_score,
            "term_count": len(found_terms),
            "non_standard": non_standard[:10],  # Limit to 10
            "issues": [f"Non-standard term: {term}" for term in non_standard[:5]],
        }

    def suggest_terms(
        self, partial_term: str, language: str = "en", max_suggestions: int = 10
    ) -> List[str]:
        """
        Provide autocomplete suggestions for partial term

        Args:
            partial_term: Partial term to match
            language: Language for suggestions ('en' or 'mk')
            max_suggestions: Maximum number of suggestions

        Returns:
            List of suggested terms
        """
        partial_lower = partial_term.lower()
        suggestions = []

        for term_data in self.terms.values():
            if language == "en":
                term = term_data.get("english", "")
            else:
                term = term_data.get("macedonian", "")

            if term and term.lower().startswith(partial_lower):
                if term not in suggestions:
                    suggestions.append(term)

        return sorted(suggestions)[:max_suggestions]

    def export_glossary(
        self, format: str = "markdown", categories: Optional[List[str]] = None
    ) -> str:
        """
        Generate glossary appendix for SOPs

        Args:
            format: Export format ('markdown', 'html', 'pdf')
            categories: Specific categories to export (None = all)

        Returns:
            Formatted glossary text
        """
        if format != "markdown":
            logger.warning(f"Format {format} not yet implemented, using markdown")

        output = ["# Glossary of Terms / Речник на термини\n"]

        # Get categories to export
        all_categories = self.metadata.get("categories", [])
        export_categories = categories if categories else all_categories

        for category in export_categories:
            terms = self.get_terms_by_category(category)
            if not terms:
                continue

            # Category header
            category_title = category.replace("_", " ").title()
            output.append(f"\n## {category_title}\n")

            # Terms in this category
            for term in terms:
                english = term.get("english", "")
                macedonian = term.get("macedonian", "")
                definition_en = term.get("definition_en", "")
                definition_mk = term.get("definition_mk", "")

                if not english or not macedonian:
                    continue

                output.append(f"**{english}** / **{macedonian}**")

                # Add full names if available
                full_name_en = term.get("full_name_en")
                full_name_mk = term.get("full_name_mk")
                if full_name_en and full_name_mk:
                    output.append(f"  - *{full_name_en}* / *{full_name_mk}*")

                # Add definitions
                if definition_en and definition_mk:
                    output.append(f"  - {definition_en}")
                    output.append(f"  - {definition_mk}")

                output.append("")  # Blank line

        return "\n".join(output)

    def get_term_details(self, term: str, language: str = "en") -> Optional[Dict]:
        """
        Get complete details for a specific term

        Args:
            term: Term to look up
            language: Language of term ('en' or 'mk')

        Returns:
            Term dictionary with all fields, or None if not found
        """
        term_lower = term.lower()

        if term_lower in self.terms:
            return self.terms[term_lower]

        # Also try searching by full name
        for term_data in self.terms.values():
            if language == "en":
                full_name = term_data.get("full_name_en", "").lower()
            else:
                full_name = term_data.get("full_name_mk", "").lower()

            if full_name == term_lower:
                return term_data

        return None

    def get_abbreviations(self) -> List[Dict]:
        """
        Get all terms with abbreviations

        Returns:
            List of terms that have abbreviations
        """
        abbreviations = []

        for term_data in self.terms.values():
            if "abbreviation_en" in term_data or "abbreviation_mk" in term_data:
                if term_data not in abbreviations:
                    abbreviations.append(term_data)

        return sorted(
            abbreviations, key=lambda x: x.get("abbreviation_en", x.get("english", ""))
        )

    def generate_abbreviations_list(self) -> str:
        """
        Generate abbreviations section for SOP

        Returns:
            Formatted abbreviations list
        """
        abbreviations = self.get_abbreviations()

        output = ["## Abbreviations / Скратеници\n"]

        for term in abbreviations:
            abbr_en = term.get("abbreviation_en", "")
            abbr_mk = term.get("abbreviation_mk", "")
            full_en = term.get("full_name_en", term.get("english", ""))
            full_mk = term.get("full_name_mk", term.get("macedonian", ""))

            if abbr_en and abbr_mk:
                output.append(f"**{abbr_en}** / **{abbr_mk}**")
                output.append(f"  - {full_en}")
                output.append(f"  - {full_mk}\n")
            elif abbr_en:
                output.append(f"**{abbr_en}**")
                output.append(f"  - {full_en}")
                if full_mk:
                    output.append(f"  - {full_mk}\n")

        return "\n".join(output)

    def get_statistics(self) -> Dict:
        """
        Get glossary statistics

        Returns:
            Dictionary with statistics
        """
        # Count unique terms (avoid double-counting indexed terms)
        unique_terms = set()
        category_counts = {}

        for term_data in self.terms.values():
            english = term_data.get("english")
            if english:
                unique_terms.add(english)

                category = term_data.get("category", "uncategorized")
                category_counts[category] = category_counts.get(category, 0) + 1

        return {
            "total_terms": len(unique_terms),
            "total_indexed": len(self.terms),
            "categories": len(category_counts),
            "category_breakdown": category_counts,
            "languages": self.metadata.get("languages", []),
            "version": self.metadata.get("version", "Unknown"),
        }


# Convenience functions


def translate_term(term: str, source_lang: str = "en", target_lang: str = "mk") -> str:
    """
    Quick translation of single term

    Args:
        term: Term to translate
        source_lang: Source language
        target_lang: Target language

    Returns:
        Translated term
    """
    manager = GlossaryManager()
    return manager.get_translation(term, source_lang, target_lang)


def translate_document(
    text: str,
    source_lang: str = "en",
    target_lang: str = "mk",
    preserve_technical: bool = True,
) -> str:
    """
    Quick translation of document text

    Args:
        text: Text to translate
        source_lang: Source language
        target_lang: Target language
        preserve_technical: Preserve technical abbreviations

    Returns:
        Translated text
    """
    manager = GlossaryManager()
    return manager.translate_text(text, source_lang, target_lang, preserve_technical)


def validate_document_terminology(text: str, language: str = "mk") -> Dict:
    """
    Quick terminology validation

    Args:
        text: Text to validate
        language: Language of text

    Returns:
        Validation results dictionary
    """
    manager = GlossaryManager()
    return manager.validate_terminology(text, language)


if __name__ == "__main__":
    # Test glossary manager
    manager = GlossaryManager()

    # Print statistics
    stats = manager.get_statistics()
    print("Glossary Statistics:")
    print(f"  Total Terms: {stats['total_terms']}")
    print(f"  Categories: {stats['categories']}")
    print(f"  Version: {stats['version']}")
    print("\nCategory Breakdown:")
    for category, count in stats["category_breakdown"].items():
        print(f"  {category}: {count}")

    # Test translation
    print("\n--- Translation Tests ---")
    test_terms = ["THC", "cannabinoid", "Batch", "harvest"]
    for term in test_terms:
        translated = manager.get_translation(term, "en", "mk")
        print(f"{term} → {translated}")

    # Test text translation
    print("\n--- Text Translation Test ---")
    test_text = "The THC cannabinoid profile must be validated using HPLC testing."
    translated_text = manager.translate_text(test_text, "en", "mk")
    print(f"Original: {test_text}")
    print(f"Translated: {translated_text}")
