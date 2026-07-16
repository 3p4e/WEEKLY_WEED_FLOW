import sys
import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

# Add scripts directory to path to import modules directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from placeholder_engine import PlaceholderEngine
from facility_config import FacilityConfig

class TestPlaceholderEngine:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=FacilityConfig)
        config.get.return_value = "Test Value"
        config.get_full_name.return_value = "Test Person"
        return config

    @pytest.fixture
    def engine(self, mock_config):
        return PlaceholderEngine(
            config=mock_config,
            use_advanced_mapping=True
        )

    def test_basic_replacement(self, engine):
        """Test replacing a simple placeholder."""
        content = "This is a [TEST_PLACEHOLDER]."
        # Manually inject mapping for test
        engine.additional_mappings = {"TEST_PLACEHOLDER": "replacement"}
        
        result = engine.process_content(content)
        assert "This is a replacement." in result
        assert engine.replacements_made > 0

    def test_date_placeholder(self, engine):
        """Test DATE placeholder replacement."""
        content = "Today is [DATE]."
        result = engine.process_content(content)
        assert "[DATE]" not in result
        # Check if it looks like a date (YYYY-MM-DD or DD.MM.YYYY)
        import re
        assert re.search(r"(\d{2}[./-]\d{2}[./-]\d{4})|(\d{4}-\d{2}-\d{2})", result)

    def test_facility_name_placeholder(self, engine):
        """Test FACILITY_NAME from config."""
        engine.config.get.return_value = "Purely Plant"
        content = "Welcome to [FACILITY_NAME]."
        result = engine.process_content(content)
        assert "Welcome to Purely Plant." in result

    def test_unresolved_placeholder(self, engine):
        """Test that unresolved placeholders are tracked."""
        content = "This is [UNKNOWN_PLACEHOLDER]."
        result = engine.process_content(content)
        # Should remain unchanged or be handled specific way? 
        # Based on code, it keeps it but tracks it.
        # Wait, process_content in viewed code:
        # if replacement is not None: replace
        # else: append to unresolved
        
        assert "[UNKNOWN_PLACEHOLDER]" in result
        assert "UNKNOWN_PLACEHOLDER" in engine.unresolved_placeholders

    def test_multiple_occurrences(self, engine):
        """Test replacing multiple occurrences of the same placeholder."""
        engine.additional_mappings = {"TEST": "Success"}
        content = "[TEST] and [TEST] again."
        result = engine.process_content(content)
        assert "Success and Success again." in result
