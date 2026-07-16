"""
Specification model for LIMS specification management.

Per QCSOP 010 (Specification Issuance).

Specifications define acceptable limits for each test parameter.
Version controlled per EU GMP change management requirements.
When a new version becomes active, the previous is SUPERSEDED.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SpecStatus(StrEnum):
    """Specification lifecycle status per QCSOP 010.
    
    P1-E5: 8-stage lifecycle (INITIATED→DRAFT→QC_REVIEW→QA_APPROVED→NUMBERED→TRAINED→ACTIVE→UNDER_CHANGE)
    Retain legacy statuses for backward compatibility.
    """
    # 8-stage lifecycle
    INITIATED = "INITIATED"
    DRAFT = "DRAFT"
    QC_REVIEW = "QC_REVIEW"
    QA_APPROVED = "QA_APPROVED"
    NUMBERED = "NUMBERED"
    TRAINED = "TRAINED"
    ACTIVE = "ACTIVE"
    UNDER_CHANGE = "UNDER_CHANGE"
    # Legacy statuses for backward compatibility
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"
    
    @classmethod
    def get_stage_order(cls, status: str) -> int:
        """Return numeric stage order for sequential validation (0-7)."""
        stage_map = {
            cls.INITIATED.value: 0,
            cls.DRAFT.value: 1,
            cls.QC_REVIEW.value: 2,
            cls.QA_APPROVED.value: 3,
            cls.NUMBERED.value: 4,
            cls.TRAINED.value: 5,
            cls.ACTIVE.value: 6,
            cls.UNDER_CHANGE.value: 7,
        }
        return stage_map.get(status, -1)


class THCGrade(StrEnum):
    """THC potency grades per PPQCSPECIB001 §4.2.
    
    GRADE_I: 25.0-28.9% (Premium)
    GRADE_II: 21.0-24.9% (High)
    GRADE_III: 17.0-20.9% (Standard)
    GRADE_IV: 13.0-16.9% (Economy)
    GRADE_V: 5.0-12.9% (Low)
    """
    GRADE_I = "GRADE_I"
    GRADE_II = "GRADE_II"
    GRADE_III = "GRADE_III"
    GRADE_IV = "GRADE_IV"
    GRADE_V = "GRADE_V"

    @classmethod
    def from_thc_percentage(cls, thc_pct: float) -> "THCGrade":
        """Determine THC grade from percentage value."""
        if thc_pct >= 25.0:
            return cls.GRADE_I
        elif thc_pct >= 21.0:
            return cls.GRADE_II
        elif thc_pct >= 17.0:
            return cls.GRADE_III
        elif thc_pct >= 13.0:
            return cls.GRADE_IV
        else:
            return cls.GRADE_V


class SpecParameterType(StrEnum):
    """Specification parameter type."""

    NUMERIC_BOUNDED = "NUMERIC_BOUNDED"
    NUMERIC_MAX = "NUMERIC_MAX"
    NUMERIC_MIN = "NUMERIC_MIN"
    CATEGORICAL = "CATEGORICAL"
    TEXT = "TEXT"


class TestLocation(StrEnum):
    """Where the test is performed per QCSOP-010."""

    IN_HOUSE = "IN_HOUSE"
    EXTERNAL = "EXTERNAL"


class Chemotype(StrEnum):
    """Cannabis chemotype classification per P1-E3.
    
    THC-dominant: THC ≥ 5.0%, CBD ≤ 1.0%
    THC-CBD-intermediate: THC 1.0-5.0%, CBD ≥ 1.0%, ratio 0.2-5.0
    CBD-dominant: THC ≤ 1.0%, CBD ≥ 5.0%
    """
    THC_DOMINANT = "THC_DOMINANT"
    THC_CBD_INTERMEDIATE = "THC_CBD_INTERMEDIATE"
    CBD_DOMINANT = "CBD_DOMINANT"

    @classmethod
    def validate_from_percentages(cls, thc_pct: float, cbd_pct: float) -> "Chemotype":
        """Determine chemotype from THC and CBD percentages."""
        ratio = thc_pct / cbd_pct if cbd_pct > 0 else float('inf')
        
        if thc_pct >= 5.0 and cbd_pct <= 1.0:
            return cls.THC_DOMINANT
        elif 1.0 <= thc_pct <= 5.0 and cbd_pct >= 1.0 and 0.2 <= ratio <= 5.0:
            return cls.THC_CBD_INTERMEDIATE
        elif thc_pct <= 1.0 and cbd_pct >= 5.0:
            return cls.CBD_DOMINANT
        else:
            raise ValueError(
                f"Chemotype validation failed: THC={thc_pct}%, CBD={cbd_pct}% "
                f"does not meet any chemotype criteria. "
                "THC-dominant requires THC≥5.0% and CBD≤1.0%; "
                "Intermediate requires THC 1.0-5.0%, CBD≥1.0%, ratio 0.2-5.0; "
                "CBD-dominant requires THC≤1.0% and CBD≥5.0%."
            )


class TestMethodRef(StrEnum):
    """Ph.Eur method references per P1-E4.
    
    References for cannabinoid and related testing.
    """
    PH_EUR_2_2_32 = "Ph.Eur. 2.2.32"  # Loss on Drying
    PH_EUR_2_8_2 = "Ph.Eur. 2.8.2"    # Foreign Matter
    PH_EUR_2_4_27 = "Ph.Eur. 2.4.27"  # Heavy Metals
    PH_EUR_2_8_18 = "Ph.Eur. 2.8.18"  # Pesticide Residues
    PH_EUR_2_8_13 = "Ph.Eur. 2.8.13"  # Mycotoxins (Aflatoxins)
    PH_EUR_2_6_12 = "Ph.Eur. 2.6.12"  # Microbiological Examination (TAMC/TYMC)
    PH_EUR_2_6_13 = "Ph.Eur. 2.6.13"  # Test for Specified Micro-Organisms
    PH_EUR_2_8_10 = "Ph.Eur. 2.8.10"  # Cannabinoid Profile


class Specification(BaseModel):
    """
    Material or product specification.

    Contains version-controlled test parameter limits.
    Only one version per material can be ACTIVE at a time.
    """

    __tablename__ = "specifications"

    spec_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="Human-readable specification identifier (PP-SPEC-YYYY-NNNN)"
    )
    material_code: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        doc="Material code this specification applies to"
    )
    material_name_en: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (English)"
    )
    material_name_mk: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Material name (Macedonian)"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        doc="Specification version number"
    )
    effective_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        doc="Date this specification version becomes active"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SpecStatus.DRAFT.value,
        doc="Specification lifecycle status"
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="User who approved this specification"
    )

    # ── P1-E1: THC Grade Classification (PPQCSPECIB001) ──
    thc_grade: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        doc="THC potency grade: GRADE_I, GRADE_II, GRADE_III, GRADE_IV, GRADE_V"
    )
    thc_acceptance_min: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="THC acceptance range minimum (%) — e.g., 21.0 for GRADE_II"
    )
    thc_acceptance_max: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="THC acceptance range maximum (%) — e.g., 24.9 for GRADE_II"
    )

    # Relationships
    parameters = relationship(
        "SpecParameter",
        back_populates="specification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    approved_by = relationship("User", lazy="joined")

    approvals = relationship(
        "SpecApproval",
        back_populates="specification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    change_requests = relationship(
        "SpecChangeRequest",
        back_populates="specification",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "material_code", "version",
            name="uq_specification_material_version"
        ),
        # Partial unique index: only one ACTIVE spec per material_code
        # Prevents race condition on dual-activation (E1)
        Index(
            "uq_specification_active_material",
            "material_code",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Spec {self.spec_id} v{self.version} [{self.status}]>"


class SpecParameter(BaseModel):
    """
    Single test parameter within a specification.

    Defines acceptable limits, method reference, and pharmacopoeia reference.
    """

    __tablename__ = "spec_parameters"

    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("specifications.id", ondelete="CASCADE"),
        nullable=False,
        doc="Parent specification ID"
    )
    test_name_en: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Test name (English) — e.g., 'Loss on Drying'"
    )
    test_name_mk: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Test name (Macedonian) — e.g., 'Губење при сушење'"
    )
    test_method: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Analytical method reference (e.g., Ph. Eur. 2.02.12)"
    )
    spec_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        doc="Specification type: NUMERIC_BOUNDED, NUMERIC_MAX, etc."
    )
    lower_limit: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Lower acceptable limit"
    )
    upper_limit: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Upper acceptable limit"
    )
    unit: Mapped[str] = mapped_column(
        String(50), nullable=False,
        doc="Unit of measurement (% w/w, CFU/g, µS/cm, etc.)"
    )
    pharmacopoeia_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Pharmacopoeia reference (e.g., Ph. Eur. 2.06.13)"
    )

    # ── QCSOP-010 extensions (ported from CoA_TRACK SpecParameter) ──
    test_location: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TestLocation.IN_HOUSE.value,
        doc="Where the test is performed: IN_HOUSE | EXTERNAL"
    )
    compendial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        doc="Whether this is a compendial method (Ph. Eur. monographs)"
    )
    operational_limit_min: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Operational alert limit minimum — triggers investigation before failure"
    )
    operational_limit_max: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Operational alert limit maximum"
    )
    release_limit_min: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Release specification limit minimum — batch fails if breached"
    )
    release_limit_max: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Release specification limit maximum"
    )
    sorting_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        doc="Display order within the specification list"
    )

    # Relationships
    specification = relationship(
        "Specification", back_populates="parameters"
    )

    def __repr__(self) -> str:
        return f"<SpecParam {self.test_name_en} [{self.spec_type}]>"


# ── Lifecycle & Change Control Models (P1) ──


class ApprovalRole(StrEnum):
    """Roles in the specification approval chain per QCSOP 010 §6.5."""

    AUTHOR = "AUTHOR"          # Person who drafted the spec
    QC_MANAGER = "QC_MANAGER"   # Technical review
    QA = "QA"                   # Final QA approval


class ApprovalStatusEnum(StrEnum):
    """Approval step status."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SpecChangeType(StrEnum):
    """Change classification per QCSOP 010 §6.9 / QAT 043."""

    MAJOR = "MAJOR"  # Significant parameter change, new test, limit tightening
    MINOR = "MINOR"  # Typographical, editorial, non-material


class VariationType(StrEnum):
    """EU variation classification for regulatory notification."""

    IA = "IA"    # Do-and-tell minor variation
    IB = "IB"    # Tell-and-wait minor variation
    II = "II"    # Major variation requiring approval


class SpecApproval(BaseModel):
    """
    Approval record for a specification lifecycle step.

    Per QCSOP 010 v02 §6.5: Self-review → QC Manager technical review → QA approval.
    Each step captures who approved/rejected, when, and any comments.
    """

    __tablename__ = "spec_approvals"

    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("specifications.id", ondelete="CASCADE"),
        nullable=False, index=True,
        doc="Specification being approved"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        doc="Approval role: AUTHOR, QC_MANAGER, QA"
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="User performing this approval step"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ApprovalStatusEnum.PENDING.value,
        doc="Approval status: PENDING, APPROVED, REJECTED"
    )
    comments: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        doc="Reviewer comments or rejection reason"
    )
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when approval/rejection was signed"
    )
    signature_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        doc="Digital signature hash (SHA-256) of the approval action"
    )

    # Relationships
    specification = relationship("Specification", back_populates="approvals")
    user = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<SpecApproval {self.role} [{self.status}] on spec={self.spec_id}>"


class SpecChangeRequest(BaseModel):
    """
    Change control request for specification revision.

    Per QCSOP 010 §6.9: All spec changes go through formal change control (QAT 043).
    Linked to CAPA reference for traceability.
    """

    __tablename__ = "spec_change_requests"

    spec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("specifications.id", ondelete="CASCADE"),
        nullable=False, index=True,
        doc="Specification being changed"
    )
    change_type: Mapped[str] = mapped_column(
        String(10), nullable=False,
        doc="Change classification: MAJOR | MINOR"
    )
    variation_type: Mapped[str | None] = mapped_column(
        String(5), nullable=True,
        doc="EU variation type: IA | IB | II"
    )
    impact_assessment: Mapped[str | None] = mapped_column(
        String(2000), nullable=True,
        doc="Impact assessment of the proposed change on product quality"
    )
    regulatory_notification_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="Whether this change requires notifying regulatory authorities"
    )
    capa_reference: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Linked CAPA record reference (YY-NNN format per QAT 043)"
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="User who requested the change"
    )

    # ── P1-E6: QAT 043 Change Workflow Extensions ──
    change_request_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True,
        doc="Human-readable change request ID (PP-SCR-YYYY-NNNN)"
    )
    technical_justification: Mapped[str | None] = mapped_column(
        String(4000), nullable=True,
        doc="Technical justification for the proposed change"
    )
    regulatory_classification: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        doc="Regulatory variation classification: TYPE_IB / TYPE_II"
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="SUBMITTED",
        doc="Change request status: SUBMITTED, UNDER_REVIEW, APPROVED, IMPLEMENTED, REJECTED"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when change request was submitted"
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="User who reviewed the change request"
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when change request was reviewed"
    )
    implemented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Timestamp when change was implemented"
    )

    # Relationships
    specification = relationship("Specification", back_populates="change_requests")
    requested_by = relationship("User", lazy="joined", foreign_keys=[requested_by_id])
    reviewed_by = relationship("User", lazy="joined", foreign_keys=[reviewed_by_id])

    def __repr__(self) -> str:
        return f"<SpecChangeRequest {self.change_request_number or self.change_type} [{self.status}]>"
