"""Import all ORM models so they register on the shared Base.metadata.

Importing every model here guarantees that Base.metadata.create_all()
(called in the app lifespan and the seed script) sees every table.
"""

from app.models.base import BaseModel
from app.models.user import User, UserRole
from app.models.sample import (
    Sample,
    SampleType,
    SampleStatus,
    SamplingPointType,
    PotencyGrade,
)
from app.models.specification import (
    Specification,
    SpecParameter,
    SpecApproval,
    SpecChangeRequest,
    ApprovalRole,
    ApprovalStatusEnum,
    SpecChangeType,
    VariationType,
    SpecStatus,
    SpecParameterType,
    TestLocation,
)
from app.models.certificate import (
    CertificateOfAnalysis,
    TestResult,
    COAStatus,
    BatchDecision,
    CertType,
    TestResultStatus,
)
from app.models.oos import (
    OOSRecord,
    OOSRegisterEntry,
    OOSNotificationRecord,
    OOSType,
    OOSPhase,
    OOSStatus,
    OOSRiskLevel,
    OOSDisposition,
)
from app.models.audit import AuditEntry, AuditAction
from app.models.custody import ChainOfCustody
from app.models.sampling_plan import SamplingPlan
from app.models.sampling_request import SamplingRequest
from app.models.sfr import SampleFieldRecord
from app.models.water import WaterTest
from app.models.stability import StabilityStudy
from app.models.transport import SampleTransport

__all__ = [
    "SampleTransport",
    "BaseModel",
    "User",
    "UserRole",
    "Sample",
    "SampleType",
    "SampleStatus",
    "SamplingPointType",
    "PotencyGrade",
    "Specification",
    "SpecParameter",
    "SpecApproval",
    "SpecChangeRequest",
    "ApprovalRole",
    "ApprovalStatusEnum",
    "SpecChangeType",
    "VariationType",
    "SpecStatus",
    "SpecParameterType",
    "TestLocation",
    "CertificateOfAnalysis",
    "TestResult",
    "COAStatus",
    "BatchDecision",
    "CertType",
    "TestResultStatus",
    "OOSRecord",
    "OOSRegisterEntry",
    "OOSNotificationRecord",
    "OOSType",
    "OOSPhase",
    "OOSStatus",
    "OOSRiskLevel",
    "OOSDisposition",
    "AuditEntry",
    "AuditAction",
    "ChainOfCustody",
    "SamplingPlan",
    "SamplingRequest",
    "SampleFieldRecord",
    "WaterTest",
    "StabilityStudy",
]
