"""
Sample model for LIMS sample management.

Per QCSOP 011 (Sampling) and QCSOP 001 (Department Activities).
Supports all sample types: raw materials, IPC, finished product,
stability, water system, and environmental monitoring.

ALCOA++ 'Complete' principle: full chain of custody from collection to disposal.
"""

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SampleType(StrEnum):
    """Sample types per QCSOP 011."""

    RAW_MATERIAL = "RAW_MATERIAL"
    IPC = "IPC"  # In-Process Control
    FINISHED_PRODUCT = "FINISHED_PRODUCT"
    STABILITY = "STABILITY"
    WATER = "WATER"
    ENVIRONMENTAL = "ENVIRONMENTAL"


class SamplingPointType(StrEnum):
    """Sampling point types per PP-QC-SOP-017 (P2-E1).
    
    SP-01: Raw material / API arrival
    SP-02: Packaging material arrival
    SP-03: Water system sampling
    SP-04: Environmental monitoring
    SP-05: In-process (production IPC)
    SP-06: Reception/arrival sampling (cannabis flower)
    SP-07: In-process control (during drying)
    SP-08: In-process control (during curing)
    SP-09: Finished product (packaging day 1)
    SP-10: Finished product (packaging day 2+)
    SP-11: Stability study pull point
    """
    SP_01 = "SP_01"
    SP_02 = "SP_02"
    SP_03 = "SP_03"
    SP_04 = "SP_04"
    SP_05 = "SP_05"
    SP_06 = "SP_06"
    SP_07 = "SP_07"
    SP_08 = "SP_08"
    SP_09 = "SP_09"
    SP_10 = "SP_10"
    SP_11 = "SP_11"


class PotencyGrade(StrEnum):
    """Potency grades per QCSP 003."""
    GRADE_A = "A"  # Premium (>110% of target)
    GRADE_B = "B"  # Standard (90-110% of target)
    GRADE_C = "C"  # Extracts (<90% of target)


class SampleStatus(StrEnum):
    """Sample lifecycle status."""

    COLLECTED = "COLLECTED"
    IN_TEST = "IN_TEST"
    TESTED = "TESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Sample(BaseModel):
    """
    Laboratory sample record.

    Tracks every sample from collection through testing to final disposition.
    Chain of custody is maintained via audit trail.
    """

    __tablename__ = "samples"

    sample_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="Human-readable sample identifier (PP-SMP-YYYY-NNNN)"
    )
    batch_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
        doc="Associated production batch identifier"
    )
    sample_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        doc="Sample type per QCSOP 011"
    )
    material_name_en: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (English)"
    )
    material_name_mk: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (Macedonian)"
    )
    material_code: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        doc="Internal material code"
    )
    sampling_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="Date and time of sample collection"
    )
    sampled_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="User who collected the sample"
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SampleStatus.COLLECTED.value,
        doc="Current sample lifecycle status"
    )
    location: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Storage location (e.g., sample cabinet, stability chamber)"
    )
    quantity: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Sample quantity collected"
    )
    quantity_unit: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        doc="Unit of quantity (g, mL, etc.)"
    )
    retention_sample: Mapped[bool] = mapped_column(
        nullable=False, default=False,
        doc="Whether this is a retention sample per QCSOP 011"
    )
    retention_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Date retention sample expires"
    )
    
    # P2 Sample Lifecycle fields per QCSOP 011-A01
    sp_type: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        doc="Sampling point type: SP_06, SP_07, SP_08, SP_09"
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("samples.id"), nullable=True,
        doc="Parent sample ID for SP-07/08/09 (linked to SP-06)"
    )
    sub_batch_code: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        doc="Sub-batch division code: D1, D2, ... D26, DD1..."
    )
    potency_grade: Mapped[str | None] = mapped_column(
        String(1), nullable=True,
        doc="Potency grade: A (Premium), B (Standard), C (Extracts)"
    )
    planned_quantity: Mapped[int | None] = mapped_column(
        nullable=True,
        doc="Planned sample size per sampling formula (ROUNDUP(√N×1.5))"
    )
    sampling_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sampling_plans.id"), nullable=True,
        doc="Reference to the sampling plan used"
    )

    # ── P2-E2: Foreign Matter Pre-test Gate ──
    fm_pretest_passed: Mapped[bool | None] = mapped_column(
        nullable=True,
        doc="Foreign Matter pre-test result: True=pass (≤2.0%), False=fail (>2.0%)"
    )
    fm_pretest_value: Mapped[float | None] = mapped_column(
        nullable=True,
        doc="Foreign Matter pre-test result value (% w/w)"
    )
    fm_pretest_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when FM pre-test was performed"
    )

    # ── P2-E3: Multi-day Packaging Fields ──
    packaging_day: Mapped[int | None] = mapped_column(
        nullable=True,
        doc="Packaging day number (1, 2, 3, ...) for multi-day packaging"
    )
    hma_pretest_passed: Mapped[bool | None] = mapped_column(
        nullable=True,
        doc="HMA (High Moisture Alert) pre-gate: True=all LOD readings ≤10.0%"
    )
    reduced_panel_applied: Mapped[bool | None] = mapped_column(
        nullable=True, default=False,
        doc="Whether reduced analytical panel applied (Day 2+ with LOD≤10.0%)"
    )

    # Relationships
    sampled_by = relationship("User", lazy="joined")
    # Self-referential genealogy: a sample has one parent and many children.
    # Pair them with back_populates so SQLAlchemy knows they're two sides of the
    # same FK (otherwise it warns about both writing samples.parent_id).
    parent = relationship(
        "Sample",
        remote_side="Sample.id",
        back_populates="children",
        lazy="joined",
    )
    children = relationship(
        "Sample",
        back_populates="parent",
        lazy="selectin",
    )
    sampling_plan = relationship("SamplingPlan", lazy="joined")

    def __repr__(self) -> str:
        return f"<Sample {self.sample_id} [{self.status}]>"
