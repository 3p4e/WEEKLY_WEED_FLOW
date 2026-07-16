"""
Out-of-Specification (OOS) investigation model.

Per QCSOP 019 (OOS Investigation) and Appendices A01-A04.

Two-phase workflow:
- Phase I: Laboratory investigation (lab error vs. no lab error)
- Phase II: Full investigation with root cause analysis if no lab error found

CAPA initiated automatically for confirmed OOS.
"""

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OOSType(StrEnum):
    """OOx event types per QCSOP 019."""
    OOS = "OOS"  # Out-of-Specification
    OOT = "OOT"  # Out-of-Trend
    OOE = "OOE"  # Out-of-Expectation
    OOC = "OOC"  # Out-of-Control


class OOSPhase(StrEnum):
    """OOS investigation phase per QCSOP 019."""

    I = "I"   # Laboratory investigation
    II = "II"  # Full investigation


class OOSStatus(StrEnum):
    """OOS record status."""

    OPEN = "OPEN"
    PHASE_I = "PHASE_I"
    PHASE_II = "PHASE_II"
    CLOSED = "CLOSED"


class OOSRiskLevel(StrEnum):
    """Risk classification per QAT 010 FMEA and QCSOP 019."""
    HIGH = "HIGH"      # RPN > 26, 20-day timeline
    MEDIUM = "MEDIUM"  # RPN 11-25, 30-day timeline
    LOW = "LOW"        # RPN ≤ 10, 15-day timeline


class OOSDisposition(StrEnum):
    """Batch disposition decision."""
    RELEASE = "RELEASE"
    REJECT = "REJECT"
    REPROCESS = "REPROCESS"
    RETAIN = "RETAIN"


class PhaseIConclusion(StrEnum):
    """Phase I conclusion."""
    LAB_ERROR = "LAB_ERROR"
    INCONCLUSIVE = "INCONCLUSIVE"


class OOSRecord(BaseModel):
    """
    Out-of-Specification investigation record.

    Tracks the entire OOS lifecycle from detection through investigation
    to closure. Phase I determines if lab error occurred. Phase II
    performs root cause analysis and initiates CAPA.

    Per QCSOP 019: Phase I must be completed within 1 working day.
    """

    __tablename__ = "oos_records"

    oos_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="OOS record identifier (PP-OOS-YYYY-NNNN)"
    )
    test_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_results.id"), nullable=False,
        doc="Test result that triggered the OOS"
    )
    detection_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="Date and time the OOS was detected"
    )
    detected_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="Analyst who identified the OOS"
    )
    oos_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default=OOSType.OOS.value,
        doc="OOx event type per QCSOP 019"
    )
    risk_level: Mapped[str] = mapped_column(
        String(10), nullable=False, default=OOSRiskLevel.MEDIUM.value,
        doc="Risk classification per QAT 010 FMEA (HIGH/MEDIUM/LOW)"
    )
    batch_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Affected batch identifier"
    )
    sample_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
        doc="Affected sample identifier (PP-SMP-YYYY-NNNN)"
    )
    material_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Material code under test"
    )
    material_name_en: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Material name (English)"
    )
    material_name_mk: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Material name (Macedonian)"
    )
    test_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Test performed (e.g., Cannabinoid Profile, Microbial Limits)"
    )
    method_ref: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        doc="Test method/SOP reference"
    )
    specification_value: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Specification limit that was exceeded"
    )
    obtained_value: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Actual result obtained"
    )
    deviation_percentage: Mapped[float | None] = mapped_column(
        nullable=True,
        doc="Deviation from specification (%)"
    )
    phase: Mapped[str] = mapped_column(
        String(10), nullable=False, default=OOSPhase.I.value,
        doc="Current investigation phase (I or II)"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OOSStatus.OPEN.value,
        doc="OOS record status"
    )
    timeline_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Investigation completion deadline per risk level"
    )
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="When initial notification (A04 Part A) was sent"
    )

    # Phase I fields
    phase_ia_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        doc="Phase IA analyst review (calculations, method, standards, sample prep)"
    )
    phase_ib_7step: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        doc="Phase IB 7-Step Assessment by Head of QC"
    )
    lab_investigation_result: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        doc="Result of Phase I: LAB_ERROR or NO_LAB_ERROR"
    )
    lab_error_description: Mapped[str | None] = mapped_column(
        String, nullable=True,
        doc="Description of the identified lab error (if any)"
    )
    invalidated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="Whether the OOS was invalidated due to lab error"
    )
    retest_result: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Result of retest after Phase I invalidation"
    )
    phase_i_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Date Phase I was completed"
    )
    phase_i_completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="Head of Lab who completed Phase I"
    )

    # Phase II fields
    cross_functional_team: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        doc="Cross-functional team members (QC, QA, Production, Cultivation, Engineering)"
    )
    manufacturing_review: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Manufacturing batch record review findings"
    )
    cultivation_review: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Cultivation/GACP review findings"
    )
    environmental_review: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Environmental monitoring review findings"
    )
    root_cause_category: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        doc="Root cause category (e.g., EQUIPMENT, METHOD, MATERIAL)"
    )
    root_cause_description: Mapped[str | None] = mapped_column(
        String, nullable=True,
        doc="Detailed root cause description"
    )
    impact_assessment: Mapped[str | None] = mapped_column(
        String, nullable=True,
        doc="Impact assessment on other batches/products"
    )
    capa_reference: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="CAPA record reference number"
    )
    effectiveness_check_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Date CAPA effectiveness check is due"
    )
    effectiveness_check_result: Mapped[str | None] = mapped_column(
        String, nullable=True,
        doc="Result of CAPA effectiveness check"
    )
    phase_ii_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Date Phase II was completed"
    )
    phase_ii_completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="QC Manager who completed Phase II"
    )

    # Disposition
    disposition: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        doc="Batch disposition: RELEASE, REJECT, REPROCESS, RETAIN"
    )
    disposition_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Rationale for batch disposition decision"
    )
    qp_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Date QP approved the disposition (non-delegable)"
    )
    qp_approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="QP who approved the disposition"
    )
    regulatory_notification_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="Whether regulatory notification is required (A04 Part D)"
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Date the OOS was closed"
    )
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="User who closed the OOS"
    )

    # Relationships
    test_result = relationship("TestResult", lazy="joined")
    detected_by = relationship("User", foreign_keys=[detected_by_id], lazy="joined")
    phase_i_completed_by = relationship("User", foreign_keys=[phase_i_completed_by_id], lazy="joined")
    phase_ii_completed_by = relationship("User", foreign_keys=[phase_ii_completed_by_id], lazy="joined")
    qp_approved_by = relationship("User", foreign_keys=[qp_approved_by_id], lazy="joined")
    closed_by = relationship("User", foreign_keys=[closed_by_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<OOS {self.oos_number} [{self.status}]>"


class OOSRegisterEntry(BaseModel):
    """
    OOS Register entry (A03).
    Immutable central log of all OOS records.
    ONCE WRITTEN, NEVER MODIFIED — full ALCOA++ compliance.
    """
    __tablename__ = "oos_register"

    oos_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oos_records.id"), nullable=False, unique=True
    )
    events: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        doc="Chronological events: [{timestamp, action, user, details}]"
    )

    oos_record = relationship("OOSRecord", lazy="joined")

    def __repr__(self) -> str:
        return f"<OOSRegister {self.oos_id}>"


class OOSNotificationRecord(BaseModel):
    """
    OOS Notification record (A04).
    Tracks all notification parts (A/B/C/D).
    """
    __tablename__ = "oos_notifications"

    oos_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oos_records.id"), nullable=False, index=True
    )
    part: Mapped[str] = mapped_column(
        String(1), nullable=False,
        doc="Notification part: A (Initial), B (Escalation), C (External), D (Regulatory)"
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    sent_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    recipients: Mapped[dict] = mapped_column(JSONB, nullable=False, default=[])
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    oos_record = relationship("OOSRecord", lazy="joined")
    sent_by = relationship("User", foreign_keys=[sent_by_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<OOSNotification {self.id} part={self.part}>"
