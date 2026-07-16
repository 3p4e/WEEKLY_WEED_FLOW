"""
OOS Schemas — Pydantic v2 request/response models for OOS Investigation.
Per QCSOP 019 and Appendices A01-A04.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class OOSCreate(BaseSchema):
    """Create a new OOS record."""
    test_result_id: UUID
    specification_value: str
    obtained_value: str
    oos_type: str = "OOS"
    batch_id: Optional[str] = None
    sample_id: Optional[str] = None
    material_code: Optional[str] = None
    material_name_en: Optional[str] = None
    material_name_mk: Optional[str] = None
    test_name: Optional[str] = None
    method_ref: Optional[str] = None


class OOSPhaseIAData(BaseSchema):
    """Phase IA analyst review data."""
    calculations_checked: bool = False
    calculations_notes: Optional[str] = None
    method_followed: bool = False
    method_deviation: Optional[str] = None
    standards_valid: bool = False
    standards_notes: Optional[str] = None
    sample_prep_correct: bool = False
    sample_prep_notes: Optional[str] = None
    equipment_calibrated: bool = False
    equipment_notes: Optional[str] = None
    analyst_notes: Optional[str] = None


class OOSPhaseIB7Step(BaseSchema):
    """Phase IB 7-Step assessment by Head of QC."""
    step1_initial_assessment: Optional[str] = None
    step2_documentation_review: Optional[str] = None
    step3_glassware_equipment: Optional[str] = None
    step4_standards_reagents: Optional[str] = None
    step5_sample_handling: Optional[str] = None
    step6_analyst_technique: Optional[str] = None
    step7_external_factors: Optional[str] = None
    conclusion: Optional[str] = None
    recommendation: Optional[str] = None


class OOSUpdate(BaseSchema):
    """Update OOS record (phase advancement, data entry)."""
    risk_level: Optional[str] = None
    phase_ia_data: Optional[dict] = None
    phase_ib_7step: Optional[dict] = None
    lab_investigation_result: Optional[str] = None
    lab_error_description: Optional[str] = None
    invalidated: Optional[bool] = None
    retest_result: Optional[str] = None
    cross_functional_team: Optional[dict] = None
    manufacturing_review: Optional[str] = None
    cultivation_review: Optional[str] = None
    environmental_review: Optional[str] = None
    root_cause_category: Optional[str] = None
    root_cause_description: Optional[str] = None
    impact_assessment: Optional[str] = None
    capa_reference: Optional[str] = None
    effectiveness_check_date: Optional[datetime] = None
    effectiveness_check_result: Optional[str] = None
    disposition: Optional[str] = None
    disposition_reason: Optional[str] = None
    regulatory_notification_required: Optional[bool] = None


class OOSResponse(BaseSchema):
    """Full OOS record response."""
    id: UUID
    oos_number: str
    test_result_id: UUID
    detection_date: datetime
    detected_by_id: UUID
    oos_type: str
    risk_level: str
    batch_id: Optional[str] = None
    sample_id: Optional[str] = None
    material_code: Optional[str] = None
    material_name_en: Optional[str] = None
    material_name_mk: Optional[str] = None
    test_name: Optional[str] = None
    method_ref: Optional[str] = None
    specification_value: str
    obtained_value: str
    deviation_percentage: Optional[float] = None
    phase: str
    status: str
    timeline_deadline: Optional[datetime] = None
    notification_sent_at: Optional[datetime] = None
    phase_ia_data: Optional[dict] = None
    phase_ib_7step: Optional[dict] = None
    lab_investigation_result: Optional[str] = None
    lab_error_description: Optional[str] = None
    invalidated: bool
    retest_result: Optional[str] = None
    phase_i_completed_at: Optional[datetime] = None
    phase_i_completed_by_id: Optional[UUID] = None
    cross_functional_team: Optional[dict] = None
    manufacturing_review: Optional[str] = None
    cultivation_review: Optional[str] = None
    environmental_review: Optional[str] = None
    root_cause_category: Optional[str] = None
    root_cause_description: Optional[str] = None
    impact_assessment: Optional[str] = None
    capa_reference: Optional[str] = None
    effectiveness_check_date: Optional[datetime] = None
    effectiveness_check_result: Optional[str] = None
    phase_ii_completed_at: Optional[datetime] = None
    phase_ii_completed_by_id: Optional[UUID] = None
    disposition: Optional[str] = None
    disposition_reason: Optional[str] = None
    qp_approved_at: Optional[datetime] = None
    qp_approved_by_id: Optional[UUID] = None
    regulatory_notification_required: bool
    closed_at: Optional[datetime] = None
    closed_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OOSNotificationRequest(BaseSchema):
    """Send an OOS notification (A04 Parts A-D)."""
    part: str = Field(..., pattern=r'^[ABCD]$', description="Notification part: A, B, C, or D")
    recipients: list[str] = Field(..., min_length=1)
    message: Optional[str] = None
