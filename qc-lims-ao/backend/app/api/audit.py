"""
Audit Trail read API.

Per EU GMP Annex 11 §12. Exposes the immutable audit log (read-only) for the
frontend audit viewer. Records are never modified or deleted.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AuditEntry
from app.models.user import User

router = APIRouter()


@router.get("", summary="List audit trail entries")
async def list_audit(
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return audit entries ordered newest first."""
    result = await db.execute(
        select(AuditEntry)
        .where(AuditEntry.is_deleted == False)  # noqa: E712
        .order_by(AuditEntry.timestamp.desc())
        .limit(limit)
    )
    entries = result.scalars().all()
    return [
        {
            "timestamp": e.timestamp,
            "user_id": str(e.user_id) if e.user_id else None,
            "user_full_name": e.user_full_name,
            "action": e.action,
            "record_type": e.record_type,
            "record_identifier": e.record_identifier,
            "new_value": e.new_value,
        }
        for e in entries
    ]
