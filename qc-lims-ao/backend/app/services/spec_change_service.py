"""
Specification Change Service for LIMS.

Per P1-E6: QAT 043 change workflow implementation.
Manages specification change requests with regulatory classification
and traceable audit trail.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.specification import SpecChangeRequest, SpecStatus, Specification
from app.models.audit import AuditEntry, AuditAction


class ChangeWorkflowError(Exception):
    """Raised when change workflow validation fails."""
    pass


async def submit_change_request(
    db: AsyncSession,
    change_request_number: str,
    spec_id: str,
    change_type: str,
    technical_justification: str,
    requested_by_id: uuid.UUID,
    regulatory_classification: Optional[str] = None,
    variation_type: Optional[str] = None,
    capa_reference: Optional[str] = None,
    impact_assessment: Optional[str] = None,
) -> SpecChangeRequest:
    """
    Submit a new specification change request.
    
    Args:
        db: Database session
        change_request_number: Human-readable ID (PP-SCR-YYYY-NNNN)
        spec_id: Specification being changed
        change_type: MAJOR or MINOR
        technical_justification: Technical reason for change
        requested_by_id: User submitting the request
        regulatory_classification: TYPE_IB or TYPE_II
        variation_type: IA, IB, or II
        capa_reference: Linked CAPA if applicable
        impact_assessment: Impact on product quality
    
    Returns:
        Created SpecChangeRequest
    """
    # Get specification
    stmt = select(Specification).where(Specification.spec_id == spec_id)
    result = await db.execute(stmt)
    spec = result.scalar_one_or_none()
    
    if spec is None:
        raise ValueError(f"Specification {spec_id} not found")
    
    # Validate current status allows change request
    if spec.status not in (SpecStatus.ACTIVE.value, SpecStatus.NUMBERED.value, SpecStatus.TRAINED.value):
        raise ChangeWorkflowError(
            f"Cannot submit change request for spec with status {spec.status}. "
            "Spec must be ACTIVE, NUMBERED, or TRAINED."
        )
    
    now = datetime.now(timezone.utc)
    
    cr = SpecChangeRequest(
        spec_id=spec.id,
        change_request_number=change_request_number,
        change_type=change_type,
        technical_justification=technical_justification,
        regulatory_classification=regulatory_classification,
        variation_type=variation_type,
        capa_reference=capa_reference,
        impact_assessment=impact_assessment,
        requested_by_id=requested_by_id,
        submitted_at=now,
        status="SUBMITTED",
    )
    
    db.add(cr)
    await db.flush()
    
    # Update spec status to UNDER_CHANGE
    spec.status = SpecStatus.UNDER_CHANGE.value
    
    return cr


async def review_change_request(
    db: AsyncSession,
    change_request_number: str,
    reviewed_by_id: uuid.UUID,
    approved: bool,
    review_comments: Optional[str] = None,
) -> SpecChangeRequest:
    """
    Review a submitted change request.
    
    Args:
        db: Database session
        change_request_number: Change request ID
        reviewed_by_id: User performing review
        approved: Whether change is approved
        review_comments: Review comments or rejection reason
    
    Returns:
        Updated SpecChangeRequest
    """
    stmt = select(SpecChangeRequest).where(
        SpecChangeRequest.change_request_number == change_request_number
    )
    result = await db.execute(stmt)
    cr = result.scalar_one_or_none()
    
    if cr is None:
        raise ValueError(f"Change request {change_request_number} not found")
    
    if cr.status != "SUBMITTED":
        raise ChangeWorkflowError(
            f"Cannot review change request with status {cr.status}"
        )
    
    cr.reviewed_by_id = reviewed_by_id
    cr.reviewed_at = datetime.now(timezone.utc)
    cr.status = "APPROVED" if approved else "REJECTED"
    
    if review_comments:
        cr.comments = review_comments
    
    await db.flush()
    
    return cr


async def implement_change_request(
    db: AsyncSession,
    change_request_number: str,
    new_spec_version_id: Optional[uuid.UUID] = None,
) -> SpecChangeRequest:
    """
    Mark change request as implemented.
    
    Args:
        db: Database session
        change_request_number: Change request ID
        new_spec_version_id: Optional reference to new spec version created
    
    Returns:
        Updated SpecChangeRequest
    """
    stmt = select(SpecChangeRequest).where(
        SpecChangeRequest.change_request_number == change_request_number
    )
    result = await db.execute(stmt)
    cr = result.scalar_one_or_none()
    
    if cr is None:
        raise ValueError(f"Change request {change_request_number} not found")
    
    if cr.status != "APPROVED":
        raise ChangeWorkflowError(
            f"Cannot implement change request with status {cr.status}. Must be APPROVED."
        )
    
    cr.status = "IMPLEMENTED"
    cr.implemented_at = datetime.now(timezone.utc)
    
    await db.flush()
    
    return cr


async def get_change_request(
    db: AsyncSession,
    change_request_number: str,
) -> Optional[SpecChangeRequest]:
    """Get change request by number."""
    stmt = select(SpecChangeRequest).where(
        SpecChangeRequest.change_request_number == change_request_number
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_change_requests(
    db: AsyncSession,
    spec_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[SpecChangeRequest]:
    """List change requests with optional filtering."""
    from sqlalchemy import select
    
    stmt = select(SpecChangeRequest)
    
    if spec_id:
        # Get spec UUID first
        spec_stmt = select(Specification.id).where(Specification.spec_id == spec_id)
        spec_result = await db.execute(spec_stmt)
        spec_uuid = spec_result.scalar_one_or_none()
        if spec_uuid:
            stmt = stmt.where(SpecChangeRequest.spec_id == spec_uuid)
    
    if status:
        stmt = stmt.where(SpecChangeRequest.status == status)
    
    stmt = stmt.order_by(SpecChangeRequest.submitted_at.desc())
    stmt = stmt.limit(limit)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())
