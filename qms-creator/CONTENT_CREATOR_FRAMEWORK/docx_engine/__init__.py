"""
Professional DOCX Generation Module

Creates professional Word documents with Purely Plant corporate styles,
RACI matrices, embedded diagrams, and complete SOP formatting.

Includes both legacy engine (purely_plant_engine) and workflow integration (workflow_to_docx).
"""

from .purely_plant_engine import (
    PurelyPlantDocxEngine,
    PurelyPlantColors,
    create_purely_plant_docx,
)
from .workflow_to_docx import (
    DocxAssembler,
    generate_docx_from_sections,
)

__all__ = [
    "PurelyPlantDocxEngine",
    "PurelyPlantColors",
    "create_purely_plant_docx",
    "DocxAssembler",
    "generate_docx_from_sections",
]
