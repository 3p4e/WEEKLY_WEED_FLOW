"""
Sampling Plan model for LIMS sampling management.

Per QCSOP 011 (Sampling) and QCSOP 011-A01.

Defines sampling parameters for materials including sample sizes,
test requirements, and sampling frequencies.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SamplingFrequency(StrEnum):
    """Sampling frequency per QCSOP 011."""

    EVERY_BATCH = "EVERY_BATCH"
    PERIODIC = "PERIODIC"
    RANDOM = "RANDOM"


class SamplingPlan(BaseModel):
    """
    Sampling plan for materials.

    Defines how samples are collected, their size, and what tests are required.
    Supports automatic sample size calculation per ROUNDUP(√N×1.5) formula.
    """

    __tablename__ = "sampling_plans"

    plan_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="Human-readable sampling plan identifier (PP-SPL-YYYY-NNNN)"
    )
    material_code: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        doc="Material code this plan applies to"
    )
    material_name_en: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (English)"
    )
    material_name_mk: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (Macedonian)"
    )
    sampling_frequency: Mapped[str] = mapped_column(
        String(30), nullable=False,
        doc="Sampling frequency: EVERY_BATCH, PERIODIC, RANDOM"
    )
    sample_size_formula: Mapped[str] = mapped_column(
        String(100), nullable=False, default="ROUNDUP(SQRT(N)*1.5)",
        doc="Formula for calculating sample size from batch size N"
    )
    min_sample_size: Mapped[int] = mapped_column(
        nullable=False, default=1,
        doc="Minimum sample size regardless of formula calculation"
    )
    max_sample_size: Mapped[int] = mapped_column(
        nullable=False, default=50,
        doc="Maximum sample size regardless of formula calculation"
    )
    sp_07_required: Mapped[bool] = mapped_column(
        nullable=False, default=True,
        doc="Whether SP-07 (in-process during drying) samples are created"
    )
    sp_08_required: Mapped[bool] = mapped_column(
        nullable=False, default=True,
        doc="Whether SP-08 (in-process during curing) samples are created"
    )
    sp_09_required: Mapped[bool] = mapped_column(
        nullable=False, default=True,
        doc="Whether SP-09 (finished product) samples are created"
    )
    active: Mapped[bool] = mapped_column(
        nullable=False, default=True,
        doc="Whether this sampling plan is currently active"
    )

    def __repr__(self) -> str:
        return f"<SamplingPlan {self.plan_id} [{self.material_code}]>"
