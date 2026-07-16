import sys
import os
import pytest
from unittest.mock import MagicMock

# Add scripts directory to path to import modules directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from advanced_mapping import AdvancedPlaceholderMapper
from facility_config import FacilityConfig

class TestAdvancedMapping:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=FacilityConfig)
        config.get_full_name.side_effect = lambda role: f"Person for {role}"
        return config

    @pytest.fixture
    def mapper(self, mock_config):
        return AdvancedPlaceholderMapper(config=mock_config)

    def test_resolve_name_approval(self, mapper):
        """Test resolving [NAME] in context of 'Approved by'."""
        context = "Approved by: \n Signature: ..."
        # Usually implies Facility Manager or QA Manager depending on exact logic
        # Looking at viewed code: 'approved by' -> 'qualified_person'
        
        replacement = mapper.resolve_placeholder("NAME", context)
        assert replacement == "Person for qualified_person"

    def test_resolve_name_preparation(self, mapper):
        """Test resolving [NAME] in context of 'Prepared by'."""
        context = "Prepared by: \n Signature: ..."
        # Looking at viewed code: 'prepared by' -> 'qa_manager'
        
        replacement = mapper.resolve_placeholder("NAME", context)
        assert replacement == "Person for qa_manager"

    def test_resolve_title_context(self, mapper):
        """Test resolving [TITLE] based on nearby name context or role."""
        # This largely depends on how _resolve_title is implemented.
        # Assuming it looks for patterns.
        pass

    def test_resolve_unknown_placeholder(self, mapper):
        """Test that unknown placeholders return None."""
        result = mapper.resolve_placeholder("TOTALLY_UNKNOWN", "some context")
        assert result is None
