"""
Sample Field Record (SFR) model for LIMS.

Per P2-E5: Tracks field sampling data including barrel/container numbers,
destination information, and chain of custody linkage.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SFRStatus(StrEnum):
    """SFR lifecycle status."""
    
    CREATED = "CREATED"
    IN_FIELD = "IN_FIELD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SampleFieldRecord(BaseModel):
    """
    Sample Field Record (SFR) — tracks field sampling operations.
    
    Links to both Sample (laboratory record) and ChainOfCustody
    for complete traceability from field to lab.
    """
    
    __tablename__ = "sample_field_records"
    
    sfr_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="Human-readable SFR identifier (PP-SFR-YYYY-NNNN)"
    )
    
    # Link to sample request
    rqs_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
        doc="Reference to Sampling Request (PP-RQS-YYYY-NNNN)"
    )
    
    # Field sampling details
    sampling_location: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Physical sampling location (field, greenhouse, etc.)"
    )
    sampling_coordinates: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        doc="GPS coordinates if applicable (lat,long)"
    )
    
    # Container/barrel tracking
    barrel_numbers: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        doc="JSON array of barrel/container numbers collected"
    )
    num_containers: Mapped[int | None] = mapped_column(
        nullable=True,
        doc="Number of containers/barrels sampled"
    )
    
    # Destination
    destination_facility: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Destination facility for samples"
    )
    destination_location: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Specific destination location within facility"
    )
    
    # Timestamps
    planned_departure: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Planned departure from field"
    )
    actual_departure: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Actual departure from field"
    )
    planned_arrival: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Planned arrival at destination"
    )
    actual_arrival: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Actual arrival at destination"
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SFRStatus.CREATED.value,
        doc="SFR status: CREATED, IN_FIELD, COMPLETED, CANCELLED"
    )
    
    # Personnel
    sampled_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="User who performed field sampling"
    )
    escort_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="Escort/courier for transport (if required)"
    )
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="User who received samples at destination"
    )
    
    # Chain of custody linkage
    custody_transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chain_of_custody.id"), nullable=True,
        doc="Link to ChainOfCustody record for transport"
    )
    
    # Resulting sample
    sample_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Reference to created lab sample (PP-SMP-YYYY-NNNN)"
    )
    
    # Notes
    field_conditions: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Field conditions, weather, observations"
    )
    deviations: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Any deviations from planned sampling procedure"
    )
    
    # Relationships
    sampled_by = relationship("User", lazy="joined", foreign_keys=[sampled_by_id])
    escort = relationship("User", lazy="joined", foreign_keys=[escort_id])
    received_by = relationship("User", lazy="joined", foreign_keys=[received_by_id])
    custody_transfer = relationship("ChainOfCustody", lazy="joined")
    
    def __repr__(self) -> str:
        return f"<SampleFieldRecord {self.sfr_id} [{self.status}]>"
