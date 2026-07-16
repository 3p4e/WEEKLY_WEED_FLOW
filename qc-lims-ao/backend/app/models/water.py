"""
Water Quality Control result model for LIMS.

Per PP-QC-SOP-014 (Water Quality Control) and Appendices A01-A08.
Each WaterTest row is one water-quality result for a sampling location
(SL code format: <GRADE>_<ROOM>_<NNN>) on a given date, with the measured
parameters and pass/OOE outcome that the frontend Water screen renders.
"""

from datetime import date as date_type

from sqlalchemy import Boolean, Date, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WaterTest(BaseModel):
    """
    Water quality test result (PP-QC-SOP-014-A02 results log).

    The variable parameter set (pH, Conductivity, TAMC, TOC, Endotoxin,
    E.coli, ...) differs by water grade, so the measured values are stored
    as a JSONB map keyed exactly like WATER_RESULTS_SEED expects.
    """

    __tablename__ = "water_tests"

    # Business key — composite of location + date, but a stable string key
    # keeps the idempotent seed guard simple.
    water_test_id: Mapped[str] = mapped_column(
        String(80), unique=True, nullable=False, index=True,
        doc="Human-readable water test key (e.g., WT-RO_F97_001-2026-05-15)"
    )
    result_date: Mapped[date_type] = mapped_column(
        Date, nullable=False, index=True,
        doc="Date the water sample was tested (frontend 'date')"
    )
    location: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True,
        doc="Sampling location SL code (frontend 'loc'): <GRADE>_<ROOM>_<NNN>"
    )
    grade: Mapped[str] = mapped_column(
        String(4), nullable=False,
        doc="Water grade derived from the SL code prefix: TW / BW / TR / RO"
    )
    parameters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        doc="Measured parameters keyed as the frontend expects "
            "(pH, Conductivity, TAMC, TOC, Endotoxin, 'E.coli', ...)"
    )
    passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        doc="Whether all parameters met spec (frontend 'pass')"
    )
    ooe: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Out-of-Expectation note when passed is False (frontend 'ooe')"
    )

    def __repr__(self) -> str:
        return f"<WaterTest {self.location} {self.result_date}>"
