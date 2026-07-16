"""
Chain of Custody model for sample tracking.

Per QCSOP 011-A01 and ALCOA++ requirements.
Every custody transfer is logged with timestamp, users, location, and signatures.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ChainOfCustody(BaseModel):
    """
    Chain of custody record for sample transfers.
    
    Tracks every handoff of a sample from collection through testing
to final disposition. Required for ALCOA++ traceability.
    """

    __tablename__ = "chain_of_custody"

    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("samples.id"), nullable=False,
        doc="Sample being transferred"
    )
    from_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="User releasing custody"
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="User receiving custody"
    )
    transferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="Timestamp of custody transfer"
    )
    from_location: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Location where sample was held (e.g., 'QC Lab - Cabinet A', 'Stability Chamber 1')"
    )
    to_location: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="New location for sample storage"
    )
    transfer_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Reason for custody transfer (e.g., 'Testing', 'Storage', 'Disposal')"
    )
    from_signature_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        doc="Digital signature hash of releasing user (re-auth required)"
    )
    to_signature_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        doc="Digital signature hash of receiving user (re-auth required)"
    )

    # ── P2-E5: SFR Linkage ──
    sfr_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
        doc="Reference to SampleFieldRecord (PP-SFR-YYYY-NNNN) for field-to-lab transfers"
    )
    transfer_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        doc="Type of custody transfer: FIELD_TO_LAB, LAB_INTERNAL, LAB_TO_DISPOSAL, STABILITY_TRANSFER"
    )

    # Relationships
    sample = relationship("Sample", lazy="joined", foreign_keys=[sample_id])
    from_user = relationship("User", lazy="joined", foreign_keys=[from_user_id])
    to_user = relationship("User", lazy="joined", foreign_keys=[to_user_id])

    def __repr__(self) -> str:
        return f"<ChainOfCustody {self.sample_id}: {self.from_user_id} → {self.to_user_id}>"
