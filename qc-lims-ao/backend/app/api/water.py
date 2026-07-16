"""
Water Quality Control read API.

Per PP-QC-SOP-014. Exposes water test results in the simplified shape the
frontend Water screen consumes directly (keys match WATER_RESULTS_SEED): a
flat object with date/loc/pass(/ooe) plus the measured parameters spread at
the top level.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.water import WaterTest

router = APIRouter()


def _serialize(w: WaterTest) -> dict:
    """Shape a WaterTest row into the flat dict the Water screen expects.

    Measured parameters (pH, Conductivity, TAMC, ...) are spread to the top
    level alongside date/loc/pass(/ooe), exactly as WATER_RESULTS_SEED.
    """
    out: dict = {
        "date": w.result_date.strftime("%Y-%m-%d") if w.result_date else "",
        "loc": w.location,
    }
    # Spread the variable parameter map first, then the fixed result keys so
    # 'date'/'loc' are never overwritten.
    if w.parameters:
        out.update(w.parameters)
    out["date"] = w.result_date.strftime("%Y-%m-%d") if w.result_date else ""
    out["loc"] = w.location
    out["pass"] = w.passed
    if w.ooe:
        out["ooe"] = w.ooe
    return out


@router.get("", summary="List water quality test results")
async def list_water(
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return non-deleted water test results, oldest first (chronological log)."""
    result = await db.execute(
        select(WaterTest)
        .where(WaterTest.is_deleted == False)  # noqa: E712
        .order_by(WaterTest.result_date.asc())
        .limit(limit)
    )
    return [_serialize(w) for w in result.unique().scalars().all()]
