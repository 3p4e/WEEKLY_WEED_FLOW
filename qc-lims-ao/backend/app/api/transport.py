"""
Sample Transport / Chain-of-Custody read API.

Per PP-QC-SOP-012. Exposes SampleTransport rows in the shape the frontend
Transport screen consumes directly (keys match SEED_TRANSPORTS). Backed by the
dedicated SampleTransport model, so the external-lab, annex-form and shipping
fields are real data (not placeholders).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.transport import SampleTransport
from app.models.user import User

router = APIRouter()


def _date(d) -> str:
    """Format a date to an ISO date string, or '' if missing."""
    return d.strftime("%Y-%m-%d") if d else ""


def _serialize(t: SampleTransport) -> dict:
    """Shape a SampleTransport row into the dict the Transport screen expects."""
    return {
        "id": t.transport_id,
        "sample_id": t.sample_id,
        "batch_id": t.batch_id or "",
        "lab": t.external_lab or "",
        "tests": t.tests or [],
        "status": t.status or "draft",
        "sar": bool(t.form_sar),
        "moia": bool(t.form_moia),
        "tmcoc": bool(t.form_tmcoc),
        "coo": bool(t.form_coo),
        "fin": bool(t.form_fin),
        "created": _date(t.created_date),
        "shipped": _date(t.shipped_date),
        "expected": _date(t.expected_date),
        "tracking": t.tracking or "",
    }


@router.get("", summary="List sample transports (external-lab chain of custody)")
async def list_transports(
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return non-deleted sample transports in the Transport UI shape."""
    result = await db.execute(
        select(SampleTransport)
        .where(SampleTransport.is_deleted == False)  # noqa: E712
        .order_by(SampleTransport.created_date.desc().nullslast())
        .limit(limit)
    )
    return [_serialize(t) for t in result.scalars().all()]
