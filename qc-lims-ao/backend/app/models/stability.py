"""
Stability Programme study model for LIMS.

Per QCSOP 018 (Stability) and Appendices A01-A10.
Each StabilityStudy row is one stability study (Long-Term / Accelerated /
Intermediate) covering a material and a set of batches, shaped to match the
SEED_STAB objects the frontend Stability screen consumes directly.
"""

from datetime import date as date_type

from sqlalchemy import Date, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class StabilityStudy(BaseModel):
    """
    Stability study record (QCSOP 018).

    Study type (LT/ACC/INT) drives temperature/RH/duration and time-points on
    the frontend via its STAB_TYPE table, so only the study-level fields are
    persisted here.
    """

    __tablename__ = "stability_studies"

    study_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="Human-readable study identifier (frontend 'id'), e.g. LT-2026-001"
    )
    study_type: Mapped[str] = mapped_column(
        String(10), nullable=False,
        doc="Study type (frontend 'type'): LT / ACC / INT"
    )
    material_code: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        doc="Material code (frontend 'material'), e.g. TD1-DF400"
    )
    material_name_en: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (English)"
    )
    material_name_mk: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (Macedonian)"
    )
    batches: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        doc="List of batch identifiers on study (frontend 'batches')"
    )
    started: Mapped[date_type] = mapped_column(
        Date, nullable=False,
        doc="Date the study was started (frontend 'started')"
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="IN_PROGRESS",
        doc="Study status: IN_PROGRESS, CLOSED"
    )
    protocol: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Protocol document reference (frontend 'protocol')"
    )
    schedule: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Schedule document reference (frontend 'schedule')"
    )
    report: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Final report document reference (frontend 'report'), set when CLOSED"
    )
    shelf_life: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        doc="Assigned shelf life (frontend 'shelf_life'), set when CLOSED"
    )

    def __repr__(self) -> str:
        return f"<StabilityStudy {self.study_id} [{self.study_type}/{self.status}]>"
