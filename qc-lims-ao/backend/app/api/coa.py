"""
Certificate of Analysis (CoA) read API.

Per QCSOP 012. Provides list/detail read endpoints the frontend consumes,
plus a best-effort sign action that approves/releases a CoA and writes an
audit-trail entry per EU GMP Annex 11 §12.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AuditAction, AuditEntry
from app.models.certificate import CertificateOfAnalysis, COAStatus
from app.models.user import User

router = APIRouter()


def _serialize_coa(coa: CertificateOfAnalysis) -> dict:
    """Shape a CoA ORM row into the dict the frontend expects."""
    return {
        "coa_number": coa.coa_number,
        "batch_id": coa.batch_id,
        "status": coa.status,
        "decision": coa.decision,
        "report_date": coa.report_date,
        "analyst_id": str(coa.analyst_id) if coa.analyst_id else None,
    }


@router.get("", summary="List Certificates of Analysis")
async def list_coa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return all non-deleted CoAs, newest report_date first."""
    result = await db.execute(
        select(CertificateOfAnalysis)
        .where(CertificateOfAnalysis.is_deleted == False)  # noqa: E712
        .order_by(CertificateOfAnalysis.report_date.desc())
    )
    return [_serialize_coa(c) for c in result.scalars().all()]


@router.get("/{coa_number}", summary="Get a single CoA")
async def get_coa(
    coa_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return one CoA by its coa_number (PP-COA-...)."""
    result = await db.execute(
        select(CertificateOfAnalysis).where(
            CertificateOfAnalysis.coa_number == coa_number,
            CertificateOfAnalysis.is_deleted == False,  # noqa: E712
        )
    )
    coa = result.scalar_one_or_none()
    if coa is None:
        raise HTTPException(status_code=404, detail="CoA not found")
    return _serialize_coa(coa)


@router.post("/{coa_number}/sign", summary="Sign (approve/release) a CoA")
async def sign_coa(
    coa_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Sign a CoA: set status to APPROVED then RELEASED and record the approver.

    Writes an audit entry (best effort) per Annex 11 §12.
    """
    result = await db.execute(
        select(CertificateOfAnalysis).where(
            CertificateOfAnalysis.coa_number == coa_number,
            CertificateOfAnalysis.is_deleted == False,  # noqa: E712
        )
    )
    coa = result.scalar_one_or_none()
    if coa is None:
        raise HTTPException(status_code=404, detail="CoA not found")

    old_status = coa.status
    # Advance the lifecycle: DRAFT/REVIEWED -> APPROVED -> RELEASED.
    coa.status = (
        COAStatus.RELEASED.value
        if old_status == COAStatus.APPROVED.value
        else COAStatus.APPROVED.value
    )
    coa.approver_id = current_user.id

    # Best-effort audit entry.
    try:
        db.add(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                user_id=current_user.id,
                user_full_name=current_user.full_name or current_user.username,
                action=AuditAction.SIGN.value,
                record_type="coa",
                record_id=str(coa.id),
                record_identifier=coa.coa_number,
                field_name="status",
                old_value=old_status,
                new_value=coa.status,
                reason="CoA electronically signed",
                ip_address="127.0.0.1",
                session_id="api",
            )
        )
    except Exception:
        pass

    await db.flush()
    return _serialize_coa(coa)
