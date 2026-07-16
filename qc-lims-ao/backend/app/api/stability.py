"""
Stability Programme read API.

Per QCSOP 018. Exposes stability studies in the simplified shape the frontend
Stability screen consumes directly (keys match SEED_STAB).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.stability import StabilityStudy
from app.models.user import User

router = APIRouter()


def _serialize(s: StabilityStudy) -> dict:
    """Shape a StabilityStudy row into the dict the Stability screen expects."""
    out = {
        "id": s.study_id,
        "type": s.study_type,
        "material": s.material_code,
        "material_name_en": s.material_name_en,
        "material_name_mk": s.material_name_mk,
        "batches": s.batches or [],
        "started": s.started.strftime("%Y-%m-%d") if s.started else "",
        "status": s.status,
        "protocol": s.protocol,
        "schedule": s.schedule,
    }
    if s.report:
        out["report"] = s.report
    if s.shelf_life:
        out["shelf_life"] = s.shelf_life
    return out


@router.get("", summary="List stability studies")
async def list_stability(
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return non-deleted stability studies, newest first, in the UI shape."""
    result = await db.execute(
        select(StabilityStudy)
        .where(StabilityStudy.is_deleted == False)  # noqa: E712
        .order_by(StabilityStudy.started.desc())
        .limit(limit)
    )
    return [_serialize(s) for s in result.unique().scalars().all()]
