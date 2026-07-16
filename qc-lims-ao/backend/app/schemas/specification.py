"""
Pydantic v2 schemas for Specification management (P1).

Covers: CRUD, approval chain, validation responses, A03 checklist generation.
All schemas use from_attributes=True and extra=forbid for ALCOA++ data integrity.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field
from pydantic import model_validator


# ── Base Schema ─────────────────────────────────────────────────────────────

class BaseSchema(BaseModel):
    """Base for all Pydantic v2 schemas — enables ORM mode with extra field rejection."""
    model_config = {"from_attributes": True, "extra": "forbid"}


# ── Re-export enums for convenience ─────────────────────────────────────────

class SpecStatusEnum(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class SpecParameterTypeEnum(StrEnum):
    NUMERIC_BOUNDED = "NUMERIC_BOUNDED"
    NUMERIC_MAX = "NUMERIC_MAX"
    NUMERIC_MIN = "NUMERIC_MIN"
    CATEGORICAL = "CATEGORICAL"
    TEXT = "TEXT"


class TestLocationEnum(StrEnum):
    IN_HOUSE = "IN_HOUSE"
    EXTERNAL = "EXTERNAL"


class ApprovalRoleEnum(StrEnum):
    AUTHOR = "AUTHOR"
    QC_MANAGER = "QC_MANAGER"
    QA = "QA"


class ApprovalStatusEnum(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ValidationTierEnum(StrEnum):
    PASS = "pass"
    ALERT = "alert"
    FAIL = "fail"
    ERROR = "error"


class SpecChangeTypeEnum(StrEnum):
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class VariationTypeEnum(StrEnum):
    IA = "IA"
    IB = "IB"
    II = "II"


# ── SpecParameter Schemas ───────────────────────────────────────────────────

class SpecParameterCreate(BaseSchema):
    """Create schema for a specification parameter."""
    test_name_en: str = Field(..., min_length=1, max_length=255)
    test_name_mk: str = Field(..., min_length=1, max_length=255)
    test_method: str = Field(..., min_length=1, max_length=255)
    spec_type: SpecParameterTypeEnum
    lower_limit: Optional[float] = None
    upper_limit: Optional[float] = None
    unit: str = Field(..., min_length=1, max_length=50)
    pharmacopoeia_ref: Optional[str] = Field(None, max_length=255)
    test_location: TestLocationEnum = TestLocationEnum.IN_HOUSE
    compendial: bool = True
    operational_limit_min: Optional[float] = None
    operational_limit_max: Optional[float] = None
    release_limit_min: Optional[float] = None
    release_limit_max: Optional[float] = None
    sorting_order: int = 0


class SpecParameterResponse(BaseSchema):
    """Read schema for a specification parameter."""
    id: uuid.UUID
    spec_id: uuid.UUID
    test_name_en: str
    test_name_mk: str
    test_method: str
    spec_type: str
    lower_limit: Optional[float] = None
    upper_limit: Optional[float] = None
    unit: str
    pharmacopoeia_ref: Optional[str] = None
    test_location: str
    compendial: bool
    operational_limit_min: Optional[float] = None
    operational_limit_max: Optional[float] = None
    release_limit_min: Optional[float] = None
    release_limit_max: Optional[float] = None
    sorting_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Specification CRUD Schemas ──────────────────────────────────────────────

class SpecCreate(BaseSchema):
    """Create schema for a new specification."""
    material_code: str = Field(..., min_length=1, max_length=50)
    material_name_en: str = Field(..., min_length=1, max_length=255)
    material_name_mk: str = Field(..., min_length=1, max_length=255)
    effective_date: date


class SpecUpdate(BaseSchema):
    """Update schema for a specification — all fields optional."""
    material_name_en: Optional[str] = Field(None, max_length=255)
    material_name_mk: Optional[str] = Field(None, max_length=255)
    effective_date: Optional[date] = None


class SpecResponse(BaseSchema):
    """Read schema for a specification with nested parameters."""
    id: uuid.UUID
    spec_id: str
    material_code: str
    material_name_en: str
    material_name_mk: str
    version: int
    effective_date: date
    status: str
    approved_by_id: Optional[uuid.UUID] = None
    parameters: list[SpecParameterResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SpecListResponse(BaseSchema):
    """List schema for specifications (without nested parameters — lighter)."""
    id: uuid.UUID
    spec_id: str
    material_code: str
    material_name_en: str
    material_name_mk: str
    version: int
    effective_date: date
    status: str
    parameter_count: int = 0
    created_at: Optional[datetime] = None


# ── State Transition Schema ─────────────────────────────────────────────────

class SpecStateTransition(BaseSchema):
    """Request body for transitioning a specification to a new status."""
    target_status: SpecStatusEnum
    reason: str = Field(..., min_length=1, max_length=1000)


# ── Approval Schemas ────────────────────────────────────────────────────────

class SpecApprovalCreate(BaseSchema):
    """Create schema for a specification approval step."""
    role: ApprovalRoleEnum
    user_id: uuid.UUID


class SpecApprovalResponse(BaseSchema):
    """Read schema for a specification approval step."""
    id: uuid.UUID
    spec_id: uuid.UUID
    role: str
    user_id: uuid.UUID
    status: str
    comments: Optional[str] = None
    signed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SpecApprovalAction(BaseSchema):
    """Action schema for approving/rejecting a step."""
    approval_role: ApprovalRoleEnum
    comments: Optional[str] = Field(None, max_length=1000)


# ── Validation Request / Response Schemas ───────────────────────────────────

class ValidationRequest(BaseSchema):
    """Request body for validating a test result against a specification."""
    test_name: str = Field(..., min_length=1, max_length=255, description="Name of the test to validate")
    result_value: Optional[str] = Field(None, description="String representation of the result")
    result_numeric: Optional[float] = Field(None, description="Numeric result value for quantitative tests")
    parameter_id: Optional[uuid.UUID] = Field(None, description="Optional: validate against a specific parameter; otherwise uses all matching parameters")


class ValidationResponse(BaseSchema):
    """Response after validating a test result."""
    complies: Optional[bool] = Field(None, description="True=pass, False=fail, None=error/no spec")
    status: str = Field(..., description="pass | alert | fail | error")
    limit_type: Optional[str] = Field(None, description="within_operational | operational_breach | release_breach | categorical_match | etc.")
    spec_parameter_id: Optional[str] = None
    spec_parameter_name: Optional[str] = None
    alert_message: Optional[str] = None
    result_value: Optional[str] = None
    spec_limit_display: Optional[str] = None


class BatchValidationRequest(BaseSchema):
    """Request body for batch validating multiple test results against a spec."""
    spec_id: uuid.UUID = Field(..., description="Specification ID to validate against")
    results: list[ValidationRequest]


class BatchValidationResponse(BaseSchema):
    """Response for batch validation."""
    spec_id: uuid.UUID
    results: list[ValidationResponse]
    summary: dict = Field(default_factory=dict, description="pass/alert/fail/error counts")


# ── Annex A03 Checklist Schema ──────────────────────────────────────────────

class AnnexA03ChecklistItem(BaseSchema):
    """Single checklist item for Annex A03 COA review (per QCSOP 012 §A01.2)."""
    parameter_name: str = Field(..., description="Test parameter name (English)")
    parameter_name_mk: str = Field(..., description="Test parameter name (Macedonian)")
    method_reference: str = Field(..., description="Analytical method reference (e.g., Ph. Eur. 2.02.12)")
    spec_limit: str = Field(..., description="Specification limit as human-readable string")
    unit: str = Field(..., description="Unit of measurement")


class AnnexA03ChecklistResponse(BaseSchema):
    """Complete Annex A03 checklist for a specification."""
    spec_id: uuid.UUID
    spec_number: str
    effective_date: date
    checklist_items: list[AnnexA03ChecklistItem]
    generated_at: datetime


# ── Change Request Schemas ──────────────────────────────────────────────────

class SpecChangeRequestCreate(BaseSchema):
    """Create schema for a specification change request."""
    change_type: SpecChangeTypeEnum
    variation_type: Optional[VariationTypeEnum] = None
    impact_assessment: Optional[str] = Field(None, max_length=2000)
    regulatory_notification_required: bool = False
    capa_reference: Optional[str] = Field(None, max_length=50)


class SpecChangeRequestResponse(BaseSchema):
    """Read schema for a specification change request."""
    id: uuid.UUID
    spec_id: uuid.UUID
    change_type: str
    variation_type: Optional[str] = None
    impact_assessment: Optional[str] = None
    regulatory_notification_required: bool
    capa_reference: Optional[str] = None
    requested_by_id: uuid.UUID
    created_at: Optional[datetime] = None


# ── Re-exports ──────────────────────────────────────────────────────────────

__all__ = [
    # Enums
    "SpecStatusEnum",
    "SpecParameterTypeEnum",
    "TestLocationEnum",
    "ApprovalRoleEnum",
    "ApprovalStatusEnum",
    "ValidationTierEnum",
    "SpecChangeTypeEnum",
    "VariationTypeEnum",
    # SpecParameter
    "SpecParameterCreate",
    "SpecParameterResponse",
    # Specification CRUD
    "SpecCreate",
    "SpecUpdate",
    "SpecResponse",
    "SpecListResponse",
    # State Transition
    "SpecStateTransition",
    # Approval
    "SpecApprovalCreate",
    "SpecApprovalResponse",
    "SpecApprovalAction",
    # Validation
    "ValidationRequest",
    "ValidationResponse",
    "BatchValidationRequest",
    "BatchValidationResponse",
    # A03 Checklist
    "AnnexA03ChecklistItem",
    "AnnexA03ChecklistResponse",
    # Change Request
    "SpecChangeRequestCreate",
    "SpecChangeRequestResponse",
]
