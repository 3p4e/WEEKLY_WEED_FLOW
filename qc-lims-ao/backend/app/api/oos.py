"""
OOS Investigation API Router

Per QCSOP 019 and Appendices A01-A04.
Endpoints for OOS lifecycle: creation, Phase I/II investigation,
QP disposition, notifications, register, and management.
All endpoints require authentication. Role-based access enforced.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.oos import OOSRecord, OOSStatus
from app.models.user import User
from app.schemas.oos import OOSCreate, OOSResponse, OOSUpdate, OOSNotificationRequest, OOSPhaseIAData
from app.services import oos_service

router = APIRouter()


def _map_phase(record: OOSRecord) -> str:
    """Collapse the OOS status/phase into one of PHASE_I / PHASE_II / CLOSED."""
    if record.status == OOSStatus.CLOSED.value:
        return "CLOSED"
    if record.status == OOSStatus.PHASE_II.value or record.phase == "II":
        return "PHASE_II"
    return "PHASE_I"


def _serialize_oos_simple(record: OOSRecord) -> dict:
    """Shape an OOS record into the simplified dict the frontend UI expects."""
    return {
        "id": record.oos_number,
        "sample_id": record.sample_id,
        "batch_id": record.batch_id,
        "phase": _map_phase(record),
        "param": record.test_name,
        "result": record.obtained_value,
        "spec": record.specification_value,
        "opened": record.detection_date,
        "opened_by": str(record.detected_by_id) if record.detected_by_id else None,
    }


@router.post("/", response_model=OOSResponse, status_code=status.HTTP_201_CREATED)
async def create_oos(
    payload: OOSCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new OOS record. 
    Auto-generates PP-OOS-YYYY-NNNN number and Phase I timeline.
    Initial status: PHASE_I.
    """
    try:
        oos = await oos_service.create_oos_record(
            db=db,
            test_result_id=payload.test_result_id,
            detected_by_id=current_user.id,
            specification_value=payload.specification_value,
            obtained_value=payload.obtained_value,
            oos_type=payload.oos_type,
            batch_id=payload.batch_id,
            sample_id=payload.sample_id,
            material_code=payload.material_code,
            material_name_en=payload.material_name_en,
            material_name_mk=payload.material_name_mk,
            test_name=payload.test_name,
            method_ref=payload.method_ref,
        )
        return oos
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/overdue", response_model=list[OOSResponse])
async def list_overdue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all overdue OOS records (past timeline, not closed).

    Declared BEFORE /{oos_id} so the literal path is not swallowed by the
    UUID path-parameter route.
    """
    return await oos_service.list_overdue(db=db)


@router.get("/{oos_id}", response_model=OOSResponse)
async def get_oos(
    oos_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an OOS record by ID."""
    oos = await oos_service.get_oos(db=db, oos_id=oos_id)
    if oos is None:
        raise HTTPException(status_code=404, detail="OOS record not found")
    return oos


@router.get("")
async def list_oos(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """
    List OOS records in the SIMPLIFIED shape the frontend UI consumes.

    Excludes soft-deleted rows. Newest detection first.
    """
    stmt = (
        select(OOSRecord)
        .where(OOSRecord.is_deleted == False)  # noqa: E712
        .order_by(OOSRecord.detection_date.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter:
        stmt = stmt.where(OOSRecord.status == status_filter)

    result = await db.execute(stmt)
    return [_serialize_oos_simple(r) for r in result.scalars().all()]


@router.patch("/{oos_id}/phase-ia", response_model=OOSResponse)
async def submit_phase_ia(
    oos_id: uuid.UUID,
    data: OOSPhaseIAData,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Phase IA: Analyst self-review.
    Submit phase_ia_data (calculations, method, standards, sample prep, equipment).
    """
    try:
        oos = await oos_service.submit_phase_ia(
            db=db, oos_id=oos_id, analyst_id=current_user.id, data=data.model_dump()
        )
        return oos
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{oos_id}/phase-ib", response_model=OOSResponse)
async def submit_phase_ib(
    oos_id: uuid.UUID,
    conclusion: str = Query(..., description="LAB_ERROR or INCONCLUSIVE"),
    recommendation: str = Query("", description="Head of QC recommendation"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Phase IB: Head of QC 7-Step Assessment.
    If LAB_ERROR -> OOS invalidated and closed.
    If INCONCLUSIVE -> move to Phase II with risk-based timeline.
    Seven-step data must be submitted via OOSUpdate before calling this.
    """
    # The seven_step_data should already be in the record; we just set conclusion.
    # In practice, the request would include the full seven_step; for simplicity we accept conclusion.
    try:
        oos = await oos_service.submit_phase_ib(
            db=db,
            oos_id=oos_id,
            head_of_qc_id=current_user.id,
            conclusion=conclusion,
            recommendation=recommendation,
            seven_step_data={},  # placeholder; actual data is fetched from record if already set
        )
        return oos
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{oos_id}/phase-ii", response_model=OOSResponse)
async def submit_phase_ii(
    oos_id: uuid.UUID,
    update: OOSUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Phase II: Submit cross-functional investigation findings.
    Sets root cause, impact, CAPA, and marks Phase II complete.
    """
    try:
        oos = await oos_service.submit_phase_ii(
            db=db,
            oos_id=oos_id,
            qc_manager_id=current_user.id,
            data=update.model_dump(exclude_unset=True),
        )
        return oos
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{oos_id}/qp-disposition", response_model=OOSResponse)
async def qp_disposition(
    oos_id: uuid.UUID,
    disposition: str = Query(..., pattern=r'^(RELEASE|REJECT|REPROCESS|RETAIN)$'),
    disposition_reason: str = Query(..., min_length=1),
    regulatory_notification_required: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    QP disposition — non-delegable per EU GMP Annex 16.
    If RELEASE or REJECT, OOS is closed.
    If REPROCESS or RETAIN, remains open for further action.
    """
    try:
        oos = await oos_service.qp_disposition(
            db=db,
            oos_id=oos_id,
            qp_id=current_user.id,
            disposition=disposition,
            disposition_reason=disposition_reason,
            regulatory_notification_required=regulatory_notification_required,
        )
        return oos
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{oos_id}/risk-level", response_model=OOSResponse)
async def update_risk_level(
    oos_id: uuid.UUID,
    risk_level: str = Query(..., pattern=r'^(HIGH|MEDIUM|LOW)$'),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update risk classification and recalculate timeline."""
    try:
        oos = await oos_service.update_risk_level(
            db=db, oos_id=oos_id, risk_level=risk_level, user_id=current_user.id
        )
        return oos
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{oos_id}/notify", status_code=status.HTTP_202_ACCEPTED)
async def send_notification(
    oos_id: uuid.UUID,
    payload: OOSNotificationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Send OOS notification (A04). Parts: A (Initial), B (Escalation), C (External), D (Regulatory).
    Stub — actual email/SMS integration to be implemented.
    """
    # Placeholder
    return {"detail": f"Notification Part {payload.part} queued for {len(payload.recipients)} recipient(s)"}


@router.get("/{oos_id}/register", response_model=dict)
async def get_register_events(
    oos_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Get OOS Register (A03) events — immutable chronological log.
    """
    # Placeholder — register entries are created via audit trail; fetch from OOSRegisterEntry
    return {"oos_id": str(oos_id), "events": []}
