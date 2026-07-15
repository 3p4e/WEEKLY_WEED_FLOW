"""
Test DOCX generation from section dicts (Letta workflow output format).
"""

import pytest
import tempfile
from pathlib import Path
from CONTENT_CREATOR_FRAMEWORK.docx_engine.workflow_to_docx import (
    generate_docx_from_sections,
    DocxAssembler,
    SECTION_DISPLAY,
)


SAMPLE_SECTIONS = {
    "purpose": "This SOP establishes the procedure for document control in cannabis EU GMP facilities.",
    "scope": "This SOP applies to all controlled documents within the Quality Management System.",
    "definitions": "SOP: Standard Operating Procedure\nGMP: Good Manufacturing Practice\nQMS: Quality Management System",
    "raci": "Activity | QA Manager | Production | Compliance\nDocument creation | R | C | I\nReview | A | R | C",
    "regulatory": "This procedure complies with EU GMP Annex 7, EudraLex Volume 4, and ICH Q10.",
    "procedure": "1. Document Initiation\n2. Draft Review\n3. Approval\n4. Distribution\n5. Archival",
    "documentation": "All document control records shall be maintained for a minimum of 5 years.",
    "training": "All personnel must complete document control training before handling controlled documents.",
    "annex": "Annex A: Document Control Form\nAnnex B: Change Request Template",
}


def test_generate_docx_from_sections():
    """Test full DOCX generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = str(Path(tmpdir) / "test_sop.docx")
        result = generate_docx_from_sections(
            sections=SAMPLE_SECTIONS,
            sop_name="Document Control",
            sop_code="QA_00.02",
            department="Quality Assurance",
            output_path=output_path,
        )
        assert Path(result).exists()
        assert result.endswith(".docx")
        assert Path(result).stat().st_size > 1000  # Should be a real DOCX


def test_generate_docx_auto_path():
    """Test DOCX generation with auto-generated path."""
    result = generate_docx_from_sections(
        sections=SAMPLE_SECTIONS,
        sop_name="Test SOP",
        sop_code="QA_99.99",
        department="Quality",
    )
    assert Path(result).exists()
    assert "QA_99.99" in result
    # Cleanup
    Path(result).unlink(missing_ok=True)


def test_assembler_cover_page():
    """Test cover page generation."""
    assembler = DocxAssembler()
    assembler.add_cover_page("Test SOP", "QA_00.01", "Quality")
    # Should have content (title, table, approvals)
    assert len(assembler.doc.paragraphs) > 0


def test_assembler_empty_sections():
    """Test handling of empty sections."""
    assembler = DocxAssembler()
    assembler.add_all_sections({})
    # Should still create headings with placeholder text
    headings = [p.text for p in assembler.doc.paragraphs if p.style.name.startswith("Heading")]
    assert len(headings) == len(SECTION_DISPLAY)
