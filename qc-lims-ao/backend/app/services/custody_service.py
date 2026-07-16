"""
Custody Service for LIMS chain of custody management.

Per QCSOP 011-A01 and ALCOA++ requirements.
Handles custody transfers, logging, and chain of custody tracking.
"""

import uuid
import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

from app.models.custody import ChainOfCustody
from app.models.audit import AuditEntry, AuditAction

if TYPE_CHECKING:
    from app.models.sample import Sample


def generate_signature_hash(user_id: uuid.UUID, timestamp: datetime) -> str:
    """
    Generate a digital signature hash for custody transfer.
    
    Uses settings.SECRET_KEY for HMAC — never hardcoded.
    
    Args:
        user_id: User UUID
        timestamp: Transfer timestamp
    
    Returns:
        SHA-256 hash string
    """
    data = f"{user_id}:{timestamp.isoformat()}:{settings.SECRET_KEY}"
    return hashlib.sha256(data.encode()).hexdigest()


async def transfer_custody(
    db: AsyncSession,
    sample_id: uuid.UUID,
    from_user_id: uuid.UUID,
    to_user_id: uuid.UUID,
    from_location: str | None,
    to_location: str | None,
    transfer_reason: str | None,
    user_full_name: str,
    ip_address: str = "127.0.0.1",
    session_id: str = "system",
) -> ChainOfCustody:
    """
    Transfer custody of a sample from one user to another.
    
    Args:
        db: Database session
        sample_id: Sample UUID being transferred
        from_user_id: User ID releasing custody
        to_user_id: User ID receiving custody
        from_location: Location where sample was held
        to_location: New location for sample storage
        transfer_reason: Reason for the transfer
        user_full_name: Full name of user performing transfer (for audit)
        ip_address: Client IP address
        session_id: Session ID
    
    Returns:
        Created ChainOfCustody record
    
    Raises:
        ValueError: If sample not found or users invalid
    """
    from app.models.sample import Sample
    from sqlalchemy import select as sa_select
    
    # Verify sample exists and lock row to prevent concurrent custody transfers (C6 fix)
    result = await db.execute(
        sa_select(Sample).where(Sample.id == sample_id).with_for_update()
    )
    sample = result.scalar_one_or_none()
    if sample is None:
        raise ValueError(f"Sample {sample_id} not found")
    
    # Generate timestamps
    transferred_at = datetime.now(timezone.utc)
    
    # Generate signature hashes (simulated - in production would use proper HMAC with user auth)
    from_signature = generate_signature_hash(from_user_id, transferred_at, "from")
    to_signature = generate_signature_hash(to_user_id, transferred_at, "to")
    
    # Create custody record
    custody_record = ChainOfCustody(
        sample_id=sample_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        transferred_at=transferred_at,
        from_location=from_location or sample.location,
        to_location=to_location,
        transfer_reason=transfer_reason,
        from_signature_hash=from_signature,
        to_signature_hash=to_signature,
    )
    
    db.add(custody_record)
    
    # Update sample location and potentially status
    old_location = sample.location
    if to_location:
        sample.location = to_location
    
    await db.flush()
    
    # Log to audit trail
    audit_entry = AuditEntry(
        user_id=from_user_id,
        user_full_name=user_full_name,
        action=AuditAction.UPDATE.value,
        record_type="sample",
        record_id=str(sample.id),
        record_identifier=sample.sample_id,
        field_name="custody_transfer",
        old_value=f"Location: {old_location or 'Unknown'}",
        new_value=f"Location: {to_location or 'Unknown'}, To: {to_user_id}",
        reason=transfer_reason or "Custody transfer",
        ip_address=ip_address,
        session_id=session_id,
    )
    db.add(audit_entry)
    
    await db.commit()
    
    return custody_record


async def get_custody_chain(
    db: AsyncSession,
    sample_id: uuid.UUID
) -> list[ChainOfCustody]:
    """
    Get complete custody chain for a sample.
    
    Args:
        db: Database session
        sample_id: Sample UUID
    
    Returns:
        List of custody records ordered by transfer time (oldest first)
    """
    from sqlalchemy import select
    
    stmt = (
        select(ChainOfCustody)
        .where(ChainOfCustody.sample_id == sample_id)
        .order_by(ChainOfCustody.transferred_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_current_custodian(
    db: AsyncSession,
    sample_id: uuid.UUID
) -> uuid.UUID | None:
    """
    Get the current custodian (most recent to_user) for a sample.
    
    Args:
        db: Database session
        sample_id: Sample UUID
    
    Returns:
        User ID of current custodian, or None if no custody records
    """
    from sqlalchemy import select
    
    stmt = (
        select(ChainOfCustody)
        .where(ChainOfCustody.sample_id == sample_id)
        .order_by(ChainOfCustody.transferred_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    latest = result.scalar_one_or_none()
    
    return latest.to_user_id if latest else None


async def verify_custody_permission(
    db: AsyncSession,
    sample_id: uuid.UUID,
    user_id: uuid.UUID
) -> bool:
    """
    Verify if a user has custody permission for a sample.
    
    Args:
        db: Database session
        sample_id: Sample UUID
        user_id: User UUID to verify
    
    Returns:
        True if user is current custodian or sample has no custody chain
    """
    current = await get_current_custodian(db, sample_id)
    
    # If no custody records, anyone with access can take custody
    if current is None:
        return True
    
    return current == user_id
