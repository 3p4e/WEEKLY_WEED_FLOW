"""
Pydantic v2 schemas for CoA_TRACK models — ported from /tmp/CoA_TRACK/app/models.py.

All schemas use from_attributes=True for ORM mode (SQLAlchemy → Pydantic).
Enums typed as Python StrEnum or Literal per spec.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────────


class CertTypeEnum(StrEnum):
    """Certificate type per QCSOP-012 classification."""
    ICOA = "icoa"
    ECOA = "ecoa"
    COQ = "coq"
    WATER = "water"
    OTHER = "other"


class ApprovalStatusEnum(StrEnum):
    """Document approval lifecycle."""
    DRAFT = "draft"
    ANALYST_REVIEW = "analyst_review"
    QC_APPROVED = "qc_approved"
    ISSUED = "issued"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class ParameterStatusEnum(StrEnum):
    """Test result compliance status."""
    PASS = "pass"
    FAIL = "fail"
    MARGINAL = "marginal"
    UNKNOWN = "unknown"


class ComplianceStatusEnum(StrEnum):
    """Water report / CoQ compliance conclusion."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"


class CoQStatusEnum(StrEnum):
    """CoQ lifecycle status."""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class BatchCOAStatusEnum(StrEnum):
    """Batch CoA status from catalog."""
    YES = "YES"
    NO = "NO"
    X = "X"
    PENDING = "pending"


class ReleaseStatusEnum(StrEnum):
    """Batch release lifecycle per QCSOP-012."""
    IN_PRODUCTION = "in_production"
    SAMPLING = "sampling"
    TESTING = "testing"
    COQ_PENDING = "coq_pending"
    QP_REVIEW = "qp_review"
    RELEASED = "released"
    REJECTED = "rejected"


class ProductionStageEnum(StrEnum):
    """Production stages per PP-QC-SOP-017 §6.4."""
    SP_01 = "SP-01"
    SP_02 = "SP-02"
    SP_03 = "SP-03"
    SP_04 = "SP-04"
    SP_05 = "SP-05"
    SP_06 = "SP-06"
    SP_07 = "SP-07"
    SP_08 = "SP-08"
    SP_09 = "SP-09"
    SP_10 = "SP-10"
    SP_11 = "SP-11"


class DocTypeEnum(StrEnum):
    """Legacy document type classification."""
    CANNABIS_COA = "cannabis_coa"
    WATER_REPORT_MK = "water_report_mk"
    OTHER = "other"


# ── Base Schema ─────────────────────────────────────────────────────────────


class BaseSchema(BaseModel):
    """Base for all Pydantic v2 schemas — enables ORM mode with extra field rejection."""
    model_config = {"from_attributes": True, "extra": "forbid"}


# ── Document Schemas ────────────────────────────────────────────────────────


class DocumentSchema(BaseSchema):
    """Read schema for Document (CoA PDF document)."""

    id: uuid.UUID
    filename: str
    original_path: Optional[str] = None
    storage_path: Optional[str] = None
    file_hash: str
    file_size: Optional[int] = None
    page_count: int = 1
    doc_type: str
    cert_type: Optional[CertTypeEnum] = None
    source_lab: Optional[str] = None
    certificate_number: Optional[str] = None
    spec_reference: Optional[str] = None
    batch_id: Optional[uuid.UUID] = None
    sampling_point: Optional[str] = None
    analysis_date: Optional[datetime] = None
    sampling_date: Optional[datetime] = None
    sampling_location: Optional[str] = None
    approval_status: ApprovalStatusEnum = ApprovalStatusEnum.DRAFT
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    analyst_name: Optional[str] = None
    extraction_confidence: Optional[float] = None
    ocr_required: bool = False
    ocr_completed: bool = False
    processing_stage: Optional[str] = None
    extracted_by: Optional[str] = None
    processing_error: Optional[str] = None
    language: str = "en"
    ingestion_date: Optional[datetime] = None
    processed_date: Optional[datetime] = None


class DocumentCreate(BaseSchema):
    """Create schema for Document — fields required on creation."""

    filename: str
    file_hash: str
    doc_type: DocTypeEnum = DocTypeEnum.CANNABIS_COA
    cert_type: Optional[CertTypeEnum] = None
    source_lab: Optional[str] = None
    language: str = "en"
    original_path: Optional[str] = None
    storage_path: Optional[str] = None
    file_size: Optional[int] = None
    page_count: int = 1


class DocumentUpdate(BaseSchema):
    """Update schema for Document — all fields optional."""

    doc_type: Optional[str] = None
    cert_type: Optional[CertTypeEnum] = None
    source_lab: Optional[str] = None
    certificate_number: Optional[str] = None
    spec_reference: Optional[str] = None
    batch_id: Optional[uuid.UUID] = None
    sampling_point: Optional[str] = None
    analysis_date: Optional[datetime] = None
    sampling_date: Optional[datetime] = None
    sampling_location: Optional[str] = None
    approval_status: Optional[ApprovalStatusEnum] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    analyst_name: Optional[str] = None
    extraction_confidence: Optional[float] = None
    ocr_required: Optional[bool] = None
    ocr_completed: Optional[bool] = None
    processing_stage: Optional[str] = None
    extracted_by: Optional[str] = None
    processing_error: Optional[str] = None
    language: Optional[str] = None


# ── Parameter (Test Result) Schemas ─────────────────────────────────────────


class ParameterSchema(BaseSchema):
    """Read schema for Parameter (extracted test result)."""

    id: uuid.UUID
    document_id: uuid.UUID
    name: str
    name_local: Optional[str] = None
    category: Optional[str] = None
    result_value: Optional[str] = None
    result_numeric: Optional[float] = None
    unit: Optional[str] = None
    method_reference: Optional[str] = None
    standard_ref: Optional[str] = None
    min_limit: Optional[str] = None
    max_limit: Optional[str] = None
    limit_numeric_min: Optional[float] = None
    limit_numeric_max: Optional[float] = None
    status: ParameterStatusEnum = ParameterStatusEnum.UNKNOWN
    compliance_note: Optional[str] = None
    confidence: float = 1.0
    extracted_by: str = "auto"


class ParameterCreate(BaseSchema):
    """Create schema for Parameter."""

    document_id: uuid.UUID
    name: str
    name_local: Optional[str] = None
    category: Optional[str] = None
    result_value: Optional[str] = None
    result_numeric: Optional[float] = None
    unit: Optional[str] = None
    method_reference: Optional[str] = None
    standard_ref: Optional[str] = None
    min_limit: Optional[str] = None
    max_limit: Optional[str] = None
    limit_numeric_min: Optional[float] = None
    limit_numeric_max: Optional[float] = None
    status: ParameterStatusEnum = ParameterStatusEnum.UNKNOWN
    compliance_note: Optional[str] = None
    confidence: float = 1.0
    extracted_by: str = "auto"


# ── Water Report Schemas ────────────────────────────────────────────────────


class WaterReportSchema(BaseSchema):
    """Read schema for WaterReport (Macedonian water testing)."""

    id: uuid.UUID
    document_id: uuid.UUID
    report_number: Optional[str] = None
    report_date: Optional[datetime] = None
    sampling_date: Optional[datetime] = None
    sampling_point: Optional[str] = None
    sampling_location_code: Optional[str] = None
    lab_name: Optional[str] = None
    lab_accreditation: Optional[str] = None
    company_name: Optional[str] = None
    company_id: Optional[str] = None
    sample_type: Optional[str] = None
    sample_code: Optional[str] = None
    conclusion: Optional[str] = None
    compliance_status: Optional[ComplianceStatusEnum] = None
    regulation_reference: Optional[str] = None
    hygiene_status: Optional[str] = None
    residual_chlorine: Optional[float] = None


# ── Batch Schemas ───────────────────────────────────────────────────────────


class BatchSchema(BaseSchema):
    """Read schema for Batch (cannabis production batch)."""

    id: uuid.UUID
    strain_id: Optional[uuid.UUID] = None
    strain_name: Optional[str] = None
    batch_code: Optional[str] = None
    production_batch: Optional[str] = None
    customer: Optional[str] = None
    quantity_kg: Optional[float] = None
    thc_percent: Optional[float] = None
    cbd_percent: Optional[float] = None
    microbiology_category: Optional[str] = None
    coa_status: BatchCOAStatusEnum = BatchCOAStatusEnum.PENDING
    has_coa_file: bool = False
    production_stage: Optional[ProductionStageEnum] = None
    release_status: ReleaseStatusEnum = ReleaseStatusEnum.IN_PRODUCTION
    coq_document_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    expiry_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BatchCreate(BaseSchema):
    """Create schema for Batch."""

    strain_name: Optional[str] = None
    batch_code: Optional[str] = None
    production_batch: Optional[str] = None
    customer: Optional[str] = None
    quantity_kg: Optional[float] = None
    thc_percent: Optional[float] = None
    cbd_percent: Optional[float] = None
    microbiology_category: Optional[str] = None
    production_stage: Optional[ProductionStageEnum] = None


# ── Product Spec Schemas ────────────────────────────────────────────────────


class SpecParameterSchema(BaseSchema):
    """Read schema for SpecParameter (parameter in product specification)."""

    id: uuid.UUID
    spec_id: uuid.UUID
    name: str
    category: Optional[str] = None
    unit: Optional[str] = None
    min_limit: Optional[str] = None
    max_limit: Optional[str] = None
    limit_numeric_min: Optional[float] = None
    limit_numeric_max: Optional[float] = None
    method_reference: Optional[str] = None
    sort_order: int = 0


class ProductSpecSchema(BaseSchema):
    """Read schema for ProductSpec (product specification definition)."""

    id: uuid.UUID
    product_name: str
    version: str = "1.0"
    is_active: bool = True
    created_by: str = "system"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── CoQ (Certificate of Quality) Schemas ────────────────────────────────────


class CoQSchema(BaseSchema):
    """Read schema for CoQ (Certificate of Quality)."""

    id: uuid.UUID
    coq_number: str
    batch_id: uuid.UUID
    spec_id: uuid.UUID
    status: CoQStatusEnum = CoQStatusEnum.DRAFT
    overall_compliance: Optional[ComplianceStatusEnum] = None
    notes: Optional[str] = None
    ai_summary: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    is_locked: bool = False
    created_by: str = "system"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CoQCreate(BaseSchema):
    """Create schema for CoQ."""

    coq_number: str
    batch_id: uuid.UUID
    spec_id: uuid.UUID
    notes: Optional[str] = None


# ── Re-export for convenience ───────────────────────────────────────────────

__all__ = [
    # Enums
    "CertTypeEnum",
    "ApprovalStatusEnum",
    "ParameterStatusEnum",
    "ComplianceStatusEnum",
    "CoQStatusEnum",
    "BatchCOAStatusEnum",
    "ReleaseStatusEnum",
    "ProductionStageEnum",
    "DocTypeEnum",
    # Schemas
    "DocumentSchema",
    "DocumentCreate",
    "DocumentUpdate",
    "ParameterSchema",
    "ParameterCreate",
    "SpecParameterSchema",
    "ProductSpecSchema",
    "WaterReportSchema",
    "BatchSchema",
    "BatchCreate",
    "CoQSchema",
    "CoQCreate",
]
