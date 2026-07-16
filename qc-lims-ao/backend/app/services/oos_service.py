"""
OOS Investigation Service — Full lifecycle per QCSOP 019 A01-A04.

Phase IA: Analyst self-review (calculations, method, standards, sample prep, equipment)
Phase IB: Head of QC 7-Step assessment
Phase II: Cross-functional investigation, root cause, CAPA
Disposition: QP non-delegable batch release decision
Notifications: A04 Parts A-D
Register: A03 central log

Risk-based timeline: HIGH=20d, MEDIUM=30d, LOW=15d
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_audit_entry
from app.models.oos import (
    OOSRecord, OOSPhase, OOSStatus, OOSRiskLevel, OOSDisposition,
    PhaseIConclusion
)
from .oos_numbering_service import next_oos_number


RISK_TIMELINE_DAYS = {
    OOSRiskLevel.HIGH.value: 20,
    OOSRiskLevel.MEDIUM.value: 30,
    OOSRiskLevel.LOW.value: 15,
}

PHASE_I_DEADLINE_DAYS = 5  # per QCSOP 019


async def create_oos_record(
    db: AsyncSession,
    test_result_id: uuid.UUID,
    detected_by_id: uuid.UUID,
    specification_value: str,
    obtained_value: str,
    **kwargs
) -> OOSRecord:
    """Create a new OOS record with auto-generated number and timeline."""
    oos_number = await next_oos_number(db)
    risk_level = kwargs.pop("risk_level", OOSRiskLevel.MEDIUM.value)
    kwargs.pop("phase", None)
    kwargs.pop("status", None)
    kwargs.pop("invalidated", None)

    timeline = datetime.now(timezone.utc) + timedelta(days=PHASE_I_DEADLINE_DAYS)

    oos = OOSRecord(
        oos_number=oos_number,
        test_result_id=test_result_id,
        detected_by_id=detected_by_id,
        specification_value=specification_value,
        obtained_value=obtained_value,
        phase=OOSPhase.I.value,
        status=OOSStatus.PHASE_I.value,
        risk_level=risk_level,
        timeline_deadline=timeline,
        **kwargs
    )
    db.add(oos)
    await db.commit()
    await db.refresh(oos)

    await log_audit_entry(db, "CREATE", "oos_record", oos.id, detected_by_id, oos.oos_number)

    return oos


async def submit_phase_ia(
    db: AsyncSession,
    oos_id: uuid.UUID,
    analyst_id: uuid.UUID,
    data: dict
) -> OOSRecord:
    """Phase IA: Analyst self-review per QCSOP 019 §6.2."""
    oos = await db.get(OOSRecord, oos_id)
    if oos is None:
        raise ValueError(f"OOS {oos_id} not found")
    if oos.phase != OOSPhase.I.value:
        raise ValueError("Phase IA only permitted during Phase I")

    oos.phase_ia_data = data
    await db.commit()
    await db.refresh(oos)

    await log_audit_entry(db, "UPDATE", "oos_record", oos.id, analyst_id, "phase_ia_data")

    return oos


async def submit_phase_ib(
    db: AsyncSession,
    oos_id: uuid.UUID,
    head_of_qc_id: uuid.UUID,
    conclusion: str,
    recommendation: str,
    seven_step_data: dict
) -> OOSRecord:
    """Phase IB: 7-Step assessment by Head of QC per QCSOP 019-A01 §7."""
    oos = await db.get(OOSRecord, oos_id)
    if oos is None:
        raise ValueError(f"OOS {oos_id} not found")
    if oos.phase != OOSPhase.I.value:
        raise ValueError("Phase IB only permitted during Phase I")

    oos.phase_ib_7step = seven_step_data
    oos.lab_investigation_result = conclusion

    if conclusion == PhaseIConclusion.LAB_ERROR.value:
        oos.invalidated = True
        oos.status = OOSStatus.CLOSED.value
        oos.phase_i_completed_at = datetime.now(timezone.utc)
        oos.phase_i_completed_by_id = head_of_qc_id
        oos.closed_at = datetime.now(timezone.utc)
        oos.closed_by_id = head_of_qc_id
    elif conclusion == PhaseIConclusion.INCONCLUSIVE.value:
        oos.phase = OOSPhase.II.value
        oos.status = OOSStatus.PHASE_II.value
        risk_days = RISK_TIMELINE_DAYS.get(oos.risk_level, 30)
        oos.timeline_deadline = datetime.now(timezone.utc) + timedelta(days=risk_days)
        oos.phase_i_completed_at = datetime.now(timezone.utc)
        oos.phase_i_completed_by_id = head_of_qc_id

    await db.commit()
    await db.refresh(oos)

    await log_audit_entry(db, "UPDATE", "oos_record", oos.id, head_of_qc_id, "phase_ib_complete")

    return oos


async def submit_phase_ii(
    db: AsyncSession,
    oos_id: uuid.UUID,
    qc_manager_id: uuid.UUID,
    data: dict
) -> OOSRecord:
    """Phase II: Full cross-functional investigation per QCSOP 019 §6.3."""
    oos = await db.get(OOSRecord, oos_id)
    if oos is None:
        raise ValueError(f"OOS {oos_id} not found")
    if oos.phase != OOSPhase.II.value:
        raise ValueError("Phase II submission requires Phase II active")

    fields = [
        "cross_functional_team", "manufacturing_review",
        "cultivation_review", "environmental_review",
        "root_cause_category", "root_cause_description",
        "impact_assessment", "capa_reference",
        "effectiveness_check_date", "effectiveness_check_result"
    ]
    for field in fields:
        if field in data:
            setattr(oos, field, data[field])

    oos.phase_ii_completed_at = datetime.now(timezone.utc)
    oos.phase_ii_completed_by_id = qc_manager_id

    await db.commit()
    await db.refresh(oos)

    await log_audit_entry(db, "UPDATE", "oos_record", oos.id, qc_manager_id, "phase_ii_complete")

    return oos


async def qp_disposition(
    db: AsyncSession,
    oos_id: uuid.UUID,
    qp_id: uuid.UUID,
    disposition: str,
    disposition_reason: str,
    regulatory_notification_required: bool = False
) -> OOSRecord:
    """QP batch disposition — non-delegable per EU GMP Annex 16."""
    if disposition not in [d.value for d in OOSDisposition]:
        raise ValueError(f"Invalid disposition: {disposition}")

    oos = await db.get(OOSRecord, oos_id)
    if oos is None:
        raise ValueError(f"OOS {oos_id} not found")

    oos.disposition = disposition
    oos.disposition_reason = disposition_reason
    oos.qp_approved_by_id = qp_id
    oos.qp_approved_at = datetime.now(timezone.utc)
    oos.regulatory_notification_required = regulatory_notification_required

    if disposition in (OOSDisposition.RELEASE.value, OOSDisposition.REJECT.value):
        oos.status = OOSStatus.CLOSED.value
        oos.closed_at = datetime.now(timezone.utc)
        oos.closed_by_id = qp_id

    await db.commit()
    await db.refresh(oos)

    await log_audit_entry(db, "APPROVE", "oos_record", oos.id, qp_id, f"disposition={disposition}")

    return oos


async def get_oos(db: AsyncSession, oos_id: uuid.UUID) -> OOSRecord | None:
    """Get OOS record by ID."""
    return await db.get(OOSRecord, oos_id)


async def list_all_oos(
    db: AsyncSession,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0
) -> list[OOSRecord]:
    """List OOS records with optional status filter."""
    stmt = select(OOSRecord).order_by(OOSRecord.detection_date.desc())
    if status:
        stmt = stmt.where(OOSRecord.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_overdue(db: AsyncSession) -> list[OOSRecord]:
    """List all overdue OOS records (past timeline, not closed)."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(OOSRecord)
        .where(
            and_(
                OOSRecord.timeline_deadline < now,
                OOSRecord.status != OOSStatus.CLOSED.value
            )
        )
        .order_by(OOSRecord.timeline_deadline)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_risk_level(
    db: AsyncSession,
    oos_id: uuid.UUID,
    risk_level: str,
    user_id: uuid.UUID
) -> OOSRecord:
    """Update risk classification and recalculate timeline."""
    if risk_level not in [r.value for r in OOSRiskLevel]:
        raise ValueError(f"Invalid risk level: {risk_level}")

    oos = await db.get(OOSRecord, oos_id)
    if oos is None:
        raise ValueError(f"OOS {oos_id} not found")

    oos.risk_level = risk_level
    risk_days = RISK_TIMELINE_DAYS[risk_level]
    oos.timeline_deadline = oos.detection_date + timedelta(days=risk_days)

    await db.commit()
    await db.refresh(oos)

    await log_audit_entry(db, "UPDATE", "oos_record", oos.id, user_id,
                         f"risk_level={risk_level}")

    return oos
