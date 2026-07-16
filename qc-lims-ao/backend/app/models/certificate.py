"""
Certificate of Analysis (COA) and TestResult models.

Per QCSOP 012 (Certificate of Analysis) and QCCoA 001 (COA Template).

COA is the official document that certifies a batch meets specifications.
It requires 2nd person verification and QP approval for release.
"""

import uuid
from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class COAStatus(StrEnum):
    """COA lifecycle status per QCSOP 012."""

    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    RELEASED = "RELEASED"


class BatchDecision(StrEnum):
    """Batch release decision."""

    PASS = "PASS"
    FAIL = "FAIL"


class CertType(StrEnum):
    """Certificate type per QCSOP-012 classification."""

    ICOA = "ICOA"  # internal Certificate of Analysis
    ECOA = "ECOA"  # external CoA from contract lab
    COQ = "COQ"    # Certificate of Quality
    WATER = "WATER"  # Water quality report
    OTHER = "OTHER"  # Other document type


class CertificateOfAnalysis(BaseModel):
    """
    Certificate of Analysis for a batch.

    Contains all test results, comparison against specification,
    and final batch disposition (pass/fail).

    Requires QP approval per EU GMP Annex 16 before release.
    """

    __tablename__ = "certificates_of_analysis"

    coa_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="COA number (PP-COA-YYYY-NNNN)"
    )
    batch_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        doc="Production batch identifier"
    )
    specification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("specifications.id"), nullable=False,
        doc="Specification version used for this COA"
    )
    report_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        doc="Date the COA was issued"
    )
    analyst_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="Analyst who performed the testing"
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="2nd person reviewer (required before approval)"
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="QP who approved the COA for release"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=COAStatus.DRAFT.value,
        doc="COA lifecycle status"
    )
    decision: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        doc="Batch release decision (PASS/FAIL)"
    )

    # ── eCoA fields (ported from CoA_TRACK Document model per QCSOP-012) ──
    cert_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default=CertType.ICOA.value,
        doc="Certificate type: ICOA | ECOA | COQ | WATER | OTHER"
    )
    source_lab: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        doc="External lab name if cert_type is ECOA"
    )
    filename: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Original filename of uploaded CoA PDF"
    )
    storage_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        doc="Server storage path for CoA PDF"
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        doc="SHA-256 file hash for tamper detection"
    )
    file_size: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        doc="File size in bytes"
    )
    page_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        doc="Number of pages in PDF"
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en",
        doc="Primary language of the CoA (en, mk)"
    )
    sampling_point: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        doc="Production sampling point per PP-QC-SOP-017 (SP-01..SP-11)"
    )
    analysis_date: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        doc="Date analysis was performed"
    )
    sampling_date: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        doc="Date sample was collected"
    )
    sampling_location: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        doc="Location where sample was collected"
    )
    extraction_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Confidence score of text extraction pipeline (0-1)"
    )
    ocr_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="Whether OCR was needed for this document"
    )
    ocr_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="Whether OCR has been completed"
    )
    processing_stage: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        doc="Current processing stage in the extraction pipeline"
    )
    processing_error: Mapped[str | None] = mapped_column(
        String(300), nullable=True,
        doc="Error message if processing failed"
    )
    analyst_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        doc="Denormalized analyst name for document readability"
    )

    # Relationships
    specification = relationship("Specification", lazy="joined")
    analyst = relationship("User", foreign_keys=[analyst_id], lazy="joined")
    reviewer = relationship("User", foreign_keys=[reviewer_id], lazy="joined")
    approver = relationship("User", foreign_keys=[approver_id], lazy="joined")
    results = relationship(
        "TestResult", back_populates="coa", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<COA {self.coa_number} [{self.status}]>"


class TestResultStatus(StrEnum):
    """Test result compliance status — ported from CoA_TRACK Parameter.status."""
    PASS = "pass"
    FAIL = "fail"
    MARGINAL = "marginal"
    UNKNOWN = "unknown"


class TestResult(BaseModel):
    """
    Single analytical test result within a COA.

    Dual result_value (string) and result_numeric (float, nullable) fields
    preserve both original text and machine-readable values.
    Ported from CoA_TRACK Parameter model per QCSOP-012.
    """

    __tablename__ = "test_results"

    coa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certificates_of_analysis.id", ondelete="CASCADE"),
        nullable=False,
        doc="Parent COA ID"
    )
    parameter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spec_parameters.id"), nullable=False,
        doc="Specification parameter this result corresponds to"
    )
    # ── Dual result fields (ported from CoA_TRACK Parameter) ──
    result_value: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Raw result value — preserved as string for 'n.d.', '<0.1', etc."
    )
    result_numeric: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Parsed numeric value if applicable, null for non-numeric results"
    )
    name_local: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        doc="Parameter name in local language (e.g., Macedonian)"
    )
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Category: microbiology, physical, chemical, potency, heavy_metal"
    )
    unit: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Unit of measurement"
    )
    min_limit: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Minimum specification limit (string, e.g., '<10')"
    )
    max_limit: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        doc="Maximum specification limit (string)"
    )
    limit_numeric_min: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Numeric minimum limit for automated compliance checks"
    )
    limit_numeric_max: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Numeric maximum limit for automated compliance checks"
    )
    method_reference: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        doc="Method reference (e.g., Ph. Eur. 2.02.12)"
    )
    standard_ref: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        doc="Regulation standard reference"
    )
    complies: Mapped[bool] = mapped_column(
        Boolean, nullable=False,
        doc="Whether the result complies with specification limits"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TestResultStatus.UNKNOWN.value,
        doc="Result status: pass | fail | marginal | unknown"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        doc="Extraction confidence score (0-1)"
    )
    result_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="Date and time the result was obtained"
    )
    analyst_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        doc="Analyst who entered this result"
    )
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
        doc="2nd person verifier for this result (ALCOA++ Accurate)"
    )

    # Relationships
    coa = relationship("CertificateOfAnalysis", back_populates="results")
    parameter = relationship("SpecParameter", lazy="joined")
    analyst = relationship("User", foreign_keys=[analyst_id], lazy="joined")
    verified_by = relationship("User", foreign_keys=[verified_by_id], lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<TestResult {self.parameter.test_name_en if self.parameter else '?'} "
            f"={self.result_value} {'PASS' if self.complies else 'FAIL'}>"
        )
