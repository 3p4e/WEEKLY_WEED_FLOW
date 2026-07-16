"""
CAPA Register read API.

CAPA records are DERIVED from OOS rows that carry CAPA / root-cause data
(per QCSOP 019). Exposed in the simplified shape the frontend CAPA screen
consumes directly (keys match SEED_CAPA).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.oos import OOSRecord, OOSStatus
from app.models.user import User

router = APIRouter()


def _date(dt) -> str:
    """Format a datetime to an ISO date string, or '' if missing."""
    return dt.strftime("%Y-%m-%d") if dt else ""


def _capa_status(record: OOSRecord) -> str:
    """Map the parent OOS status onto a CAPA lifecycle status.

    CAPA lifecycle: OPEN -> IN_PROGRESS -> EFFECTIVE -> CLOSED.
    """
    if record.status == OOSStatus.CLOSED.value or record.closed_at is not None:
        return "CLOSED"
    if record.effectiveness_check_date is not None:
        return "EFFECTIVE"
    if record.status == OOSStatus.PHASE_II.value or record.root_cause_description:
        return "IN_PROGRESS"
    return "OPEN"


def _serialize(record: OOSRecord) -> dict:
    """Shape an OOS record into the CAPA dict the frontend expects."""
    owner = str(record.phase_ii_completed_by_id) if record.phase_ii_completed_by_id else (
        str(record.detected_by_id) if record.detected_by_id else ""
    )
    title = record.root_cause_description or (
        f"{record.test_name} — {record.material_name_en}"
        if record.test_name else (record.material_name_en or record.oos_number)
    )

    # Derive an action plan from the available investigation/CAPA fields.
    actions: list[dict] = []
    aid = 1
    if record.root_cause_description:
        actions.append({
            "id": aid, "what": f"Address root cause: {record.root_cause_description}",
            "who": owner, "due": _date(record.timeline_deadline), "done": True,
        })
        aid += 1
    if record.impact_assessment:
        actions.append({
            "id": aid, "what": f"Complete impact assessment: {record.impact_assessment}",
            "who": owner, "due": _date(record.timeline_deadline), "done": True,
        })
        aid += 1
    if record.effectiveness_check_date is not None:
        actions.append({
            "id": aid, "what": "Effectiveness check — confirm corrective action",
            "who": owner, "due": _date(record.effectiveness_check_date),
            "done": record.effectiveness_check_result is not None,
        })
        aid += 1
    if not actions:
        actions.append({
            "id": 1, "what": "Investigate and define corrective/preventive actions",
            "who": owner, "due": _date(record.timeline_deadline), "done": False,
        })

    result = {
        "id": record.capa_reference or f"CAPA-{record.oos_number}",
        "oos": record.oos_number,
        "status": _capa_status(record),
        "opened": _date(record.detection_date),
        "owner": owner,
        "due": _date(record.timeline_deadline),
        "title": title,
        "actions": actions,
    }
    if record.closed_at is not None:
        result["closed"] = _date(record.closed_at)
    return result


@router.get("", summary="List CAPA records (derived from OOS)")
async def list_capa(
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return CAPA records derived from non-deleted OOS rows, newest first."""
    result = await db.execute(
        select(OOSRecord)
        .where(OOSRecord.is_deleted == False)  # noqa: E712
        .order_by(OOSRecord.detection_date.desc())
        .limit(limit)
    )
    return [_serialize(r) for r in result.unique().scalars().all()]
