"""
Sampling Requests (RQS) read API.

Per PP-QC-SOP-017. Exposes sampling requests in the simplified shape the
frontend RQS screen consumes directly (keys match SEED_RQS).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.sampling_request import SamplingRequest
from app.models.user import User

router = APIRouter()


def _fmt(dt) -> str:
    """Format a datetime to 'YYYY-MM-DD HH:MM' (frontend expects this shape)."""
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _username(rel) -> str:
    """Resolve a related User's username (frontend uses it as the person key)."""
    return rel.username if rel is not None else ""


def _serialize(r: SamplingRequest) -> dict:
    """Shape a SamplingRequest into the dict the frontend RQS list expects."""
    due = r.registration_deadline
    return {
        "id": r.rqs_id,
        "rqs_id": r.rqs_id,
        "material_code": r.material_code,
        "material_name_en": r.material_name_en,
        "material_name_mk": r.material_name_mk,
        "batch_id": r.batch_id or "",
        "dept": r.originating_department,
        "requested_by": _username(r.requested_by),
        "requested_at": _fmt(r.requested_at),
        "assigned_sp": r.assigned_sp_type or "",
        "status": r.status,
        "registered_by": _username(r.registered_by),
        "due": _fmt(due),
    }


@router.get("", summary="List sampling requests (RQS)")
async def list_sampling_requests(
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return non-deleted sampling requests, newest first, in the RQS UI shape."""
    result = await db.execute(
        select(SamplingRequest)
        .where(SamplingRequest.is_deleted == False)  # noqa: E712
        .order_by(SamplingRequest.requested_at.desc())
        .limit(limit)
    )
    return [_serialize(r) for r in result.unique().scalars().all()]
