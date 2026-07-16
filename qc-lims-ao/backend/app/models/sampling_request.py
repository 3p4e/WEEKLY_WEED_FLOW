"""
Sampling Request (RQS) model for LIMS.

Per P2-E4: PP-QC-SOP-017 sampling request workflow.
RQS transitions from originating department through QC registration
to sampling completion within 24-hour window.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class RQSStatus(StrEnum):
    """RQS lifecycle status per PP-QC-SOP-017."""
    
    OPEN = "OPEN"
    REGISTERED = "REGISTERED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SamplingRequest(BaseModel):
    """
    Sampling Request (RQS) record.
    
    Tracks sampling requests from originating departments through
    QC registration, assignment, and completion.
    """
    
    __tablename__ = "sampling_requests"
    
    rqs_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="Human-readable RQS identifier (PP-RQS-YYYY-NNNN)"
    )
    material_code: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        doc="Material code to be sampled"
    )
    material_name_en: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (English)"
    )
    material_name_mk: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (Macedonian)"
    )
    batch_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
        doc="Associated production batch identifier"
    )
    
    # Request origin
    originating_department: Mapped[str] = mapped_column(
        String(100), nullable=False,
        doc="Department requesting the sampling (e.g., 'Production', 'Packaging')"
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="User who submitted the sampling request"
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="Timestamp when request was submitted"
    )
    
    # Sampling point assignment
    assigned_sp_type: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        doc="Assigned sampling point: SP_01 through SP_11"
    )
    
    # Status and lifecycle
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RQSStatus.OPEN.value,
        doc="RQS status: OPEN, REGISTERED, IN_PROGRESS, COMPLETED, CANCELLED"
    )
    
    # Registration by QC
    registered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="QC user who registered the request"
    )
    registered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when QC registered the request"
    )
    
    # 24-hour registration window tracking
    registration_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Deadline for QC registration (requested_at + 24 hours)"
    )
    registration_window_met: Mapped[bool | None] = mapped_column(
        nullable=True,
        doc="Whether registration occurred within 24-hour window"
    )
    
    # Assignment
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="QC analyst assigned to perform sampling"
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when sampling was assigned"
    )
    
    # Completion
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when sampling was completed"
    )
    sample_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Reference to created sample (PP-SMP-YYYY-NNNN)"
    )
    
    # Cancellation
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="User who cancelled the request"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when request was cancelled"
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        doc="Reason for cancellation"
    )
    
    # Notes
    notes: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        doc="Additional notes or special instructions"
    )
    
    # Relationships
    requested_by = relationship("User", lazy="joined", foreign_keys=[requested_by_id])
    registered_by = relationship("User", lazy="joined", foreign_keys=[registered_by_id])
    assigned_to = relationship("User", lazy="joined", foreign_keys=[assigned_to_id])
    cancelled_by = relationship("User", lazy="joined", foreign_keys=[cancelled_by_id])
    
    def __repr__(self) -> str:
        return f"<SamplingRequest {self.rqs_id} [{self.status}]>"
