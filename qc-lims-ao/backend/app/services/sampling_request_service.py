"""
Sampling Request Service for LIMS.

Per P2-E4: RQS (PP-RQS-YYYY-NNNN) CRUD operations.
Manages sampling request lifecycle from OPEN to COMPLETED
with 24-hour registration window tracking.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sampling_request import SamplingRequest, RQSStatus
from app.models.audit import AuditEntry, AuditAction


async def create_sampling_request(
    db: AsyncSession,
    rqs_id: str,
    material_code: str,
    material_name_en: str,
    material_name_mk: str,
    originating_department: str,
    requested_by_id: uuid.UUID,
    batch_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> SamplingRequest:
    """
    Create a new sampling request (RQS).
    
    Args:
        db: Database session
        rqs_id: Human-readable identifier (PP-RQS-YYYY-NNNN)
        material_code: Material to be sampled
        material_name_en: Material name (English)
        material_name_mk: Material name (Macedonian)
        originating_department: Department requesting sampling
        requested_by_id: User creating the request
        batch_id: Optional associated batch
        notes: Optional notes or special instructions
    
    Returns:
        Created SamplingRequest instance
    """
    now = datetime.now(timezone.utc)
    
    rqs = SamplingRequest(
        rqs_id=rqs_id,
        material_code=material_code,
        material_name_en=material_name_en,
        material_name_mk=material_name_mk,
        batch_id=batch_id,
        originating_department=originating_department,
        requested_by_id=requested_by_id,
        requested_at=now,
        status=RQSStatus.OPEN.value,
        registration_deadline=now + timedelta(hours=24),
        notes=notes,
    )
    
    db.add(rqs)
    await db.flush()
    
    return rqs


async def register_sampling_request(
    db: AsyncSession,
    rqs_id: str,
    registered_by_id: uuid.UUID,
    assigned_sp_type: Optional[str] = None,
) -> SamplingRequest:
    """
    Register an OPEN sampling request (QC receives and acknowledges).
    
    Per P2-E4: Registration must occur within 24 hours of request.
    
    Args:
        db: Database session
        rqs_id: RQS identifier
        registered_by_id: QC user registering the request
        assigned_sp_type: Assigned sampling point (SP_01-SP_11)
    
    Returns:
        Updated SamplingRequest
    
    Raises:
        ValueError: If RQS not found or not in OPEN status
    """
    stmt = select(SamplingRequest).where(SamplingRequest.rqs_id == rqs_id)
    result = await db.execute(stmt)
    rqs = result.scalar_one_or_none()
    
    if rqs is None:
        raise ValueError(f"Sampling request {rqs_id} not found")
    
    if rqs.status != RQSStatus.OPEN.value:
        raise ValueError(f"Cannot register RQS with status {rqs.status}")
    
    now = datetime.now(timezone.utc)
    
    # Check 24-hour window
    window_met = now <= rqs.registration_deadline if rqs.registration_deadline else True
    
    rqs.status = RQSStatus.REGISTERED.value
    rqs.registered_by_id = registered_by_id
    rqs.registered_at = now
    rqs.registration_window_met = window_met
    
    if assigned_sp_type:
        rqs.assigned_sp_type = assigned_sp_type
    
    await db.flush()
    
    return rqs


async def assign_sampling_request(
    db: AsyncSession,
    rqs_id: str,
    assigned_to_id: uuid.UUID,
) -> SamplingRequest:
    """
    Assign a registered sampling request to a QC analyst.
    
    Args:
        db: Database session
        rqs_id: RQS identifier
        assigned_to_id: QC analyst to perform sampling
    
    Returns:
        Updated SamplingRequest
    """
    stmt = select(SamplingRequest).where(SamplingRequest.rqs_id == rqs_id)
    result = await db.execute(stmt)
    rqs = result.scalar_one_or_none()
    
    if rqs is None:
        raise ValueError(f"Sampling request {rqs_id} not found")
    
    if rqs.status not in (RQSStatus.REGISTERED.value, RQSStatus.OPEN.value):
        raise ValueError(f"Cannot assign RQS with status {rqs.status}")
    
    rqs.status = RQSStatus.IN_PROGRESS.value
    rqs.assigned_to_id = assigned_to_id
    rqs.assigned_at = datetime.now(timezone.utc)
    
    await db.flush()
    
    return rqs


async def complete_sampling_request(
    db: AsyncSession,
    rqs_id: str,
    sample_id: Optional[str] = None,
) -> SamplingRequest:
    """
    Mark sampling request as completed.
    
    Args:
        db: Database session
        rqs_id: RQS identifier
        sample_id: Optional reference to created sample
    
    Returns:
        Updated SamplingRequest
    """
    stmt = select(SamplingRequest).where(SamplingRequest.rqs_id == rqs_id)
    result = await db.execute(stmt)
    rqs = result.scalar_one_or_none()
    
    if rqs is None:
        raise ValueError(f"Sampling request {rqs_id} not found")
    
    rqs.status = RQSStatus.COMPLETED.value
    rqs.completed_at = datetime.now(timezone.utc)
    
    if sample_id:
        rqs.sample_id = sample_id
    
    await db.flush()
    
    return rqs


async def cancel_sampling_request(
    db: AsyncSession,
    rqs_id: str,
    cancelled_by_id: uuid.UUID,
    reason: str,
) -> SamplingRequest:
    """
    Cancel a sampling request.
    
    Args:
        db: Database session
        rqs_id: RQS identifier
        cancelled_by_id: User cancelling the request
        reason: Cancellation reason
    
    Returns:
        Updated SamplingRequest
    """
    stmt = select(SamplingRequest).where(SamplingRequest.rqs_id == rqs_id)
    result = await db.execute(stmt)
    rqs = result.scalar_one_or_none()
    
    if rqs is None:
        raise ValueError(f"Sampling request {rqs_id} not found")
    
    if rqs.status == RQSStatus.COMPLETED.value:
        raise ValueError("Cannot cancel a completed sampling request")
    
    rqs.status = RQSStatus.CANCELLED.value
    rqs.cancelled_by_id = cancelled_by_id
    rqs.cancelled_at = datetime.now(timezone.utc)
    rqs.cancellation_reason = reason
    
    await db.flush()
    
    return rqs


async def get_sampling_request(
    db: AsyncSession,
    rqs_id: str,
) -> Optional[SamplingRequest]:
    """
    Retrieve a sampling request by ID.
    
    Args:
        db: Database session
        rqs_id: RQS identifier
    
    Returns:
        SamplingRequest or None
    """
    stmt = select(SamplingRequest).where(SamplingRequest.rqs_id == rqs_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_sampling_requests(
    db: AsyncSession,
    status: Optional[str] = None,
    originating_department: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SamplingRequest]:
    """
    List sampling requests with optional filtering.
    
    Args:
        db: Database session
        status: Filter by status
        originating_department: Filter by department
        limit: Maximum results
        offset: Pagination offset
    
    Returns:
        List of SamplingRequest instances
    """
    stmt = select(SamplingRequest)
    
    if status:
        stmt = stmt.where(SamplingRequest.status == status)
    
    if originating_department:
        stmt = stmt.where(SamplingRequest.originating_department == originating_department)
    
    stmt = stmt.order_by(SamplingRequest.requested_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def check_overdue_registrations(
    db: AsyncSession,
) -> list[SamplingRequest]:
    """
    Find all OPEN sampling requests past their 24-hour registration deadline.
    
    Args:
        db: Database session
    
    Returns:
        List of overdue SamplingRequest instances
    """
    now = datetime.now(timezone.utc)
    
    stmt = select(SamplingRequest).where(
        SamplingRequest.status == RQSStatus.OPEN.value,
        SamplingRequest.registration_deadline < now
    )
    
    result = await db.execute(stmt)
    return list(result.scalars().all())
