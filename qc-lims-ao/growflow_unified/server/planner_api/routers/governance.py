"""Governance — the GMP change-control loop (P2) exposed over HTTP.

Agents (e.g. wwf_schema_advisor) propose schema/workflow changes into
change_proposal; a human approver (reviewer/qp/manager/hod/admin) decides here.
Approval is the gate — the actual migration is applied as a controlled, audited
DB operation, never silently by an agent. RLS enforces the approver role at the
database layer too (see db/0006_auth_rls.sql).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .. import audit
from ..auth_deps import CurrentUser, require_role, rls_session
from ..schemas import ChangeProposalOut, FieldRegistryOut, ProposalDecision

router = APIRouter(prefix="/governance", tags=["governance"])

_APPROVERS = ("reviewer", "manager", "qp", "hod", "admin")


def _jsond(v) -> dict:
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v:
        try:
            return json.loads(v)
        except ValueError:
            return {}
    return {}


def _to_out(r) -> ChangeProposalOut:
    return ChangeProposalOut(
        id=str(r["id"]), proposed_by=r["proposed_by"], kind=r["kind"],
        target=r["target"], payload=_jsond(r["payload"]), rationale=r["rationale"],
        evidence=_jsond(r["evidence"]), status=r["status"],
        reviewed_by=str(r["reviewed_by"]) if r["reviewed_by"] else None,
        reviewed_at=r["reviewed_at"], created_at=r["created_at"],
    )


@router.get("/proposals", response_model=list[ChangeProposalOut])
async def list_proposals(
    status: str | None = None, session: AsyncSession = Depends(rls_session)
) -> list[ChangeProposalOut]:
    where, params = "", {}
    if status:
        where = " WHERE status = :st"; params["st"] = status
    rows = (
        await session.execute(
            text("SELECT id, proposed_by, kind, target, payload, rationale, evidence, status, "
                 "reviewed_by, reviewed_at, created_at FROM change_proposal" + where +
                 " ORDER BY created_at DESC"),
            params,
        )
    ).mappings().all()
    return [_to_out(r) for r in rows]


@router.post("/proposals/{proposal_id}/decision", response_model=ChangeProposalOut)
async def decide(
    proposal_id: str,
    body: ProposalDecision,
    user: CurrentUser = Depends(require_role(*_APPROVERS)),
    session: AsyncSession = Depends(rls_session),
) -> ChangeProposalOut:
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'rejected'")
    res = await session.execute(
        text("UPDATE change_proposal SET status = :st, reviewed_by = :uid, reviewed_at = :ts "
             "WHERE id = :id AND status = 'pending' RETURNING id, proposed_by, kind, target, "
             "payload, rationale, evidence, status, reviewed_by, reviewed_at, created_at"),
        {"st": body.decision, "uid": user.id, "ts": datetime.now(timezone.utc), "id": proposal_id},
    )
    row = res.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="proposal not found or already decided")
    await audit.record_event(
        session, actor_id=user.id, action=f"proposal_{body.decision}", entity_type="change_proposal",
        entity_id=proposal_id, payload={"kind": row["kind"], "target": row["target"], "note": body.note},
    )
    await session.commit()
    return _to_out(row)


@router.get("/field-registry", response_model=list[FieldRegistryOut])
async def field_registry(session: AsyncSession = Depends(rls_session)) -> list[FieldRegistryOut]:
    rows = (
        await session.execute(
            text("SELECT key, label_en, label_mk, data_type, applies_to, status, promoted "
                 "FROM field_registry ORDER BY key")
        )
    ).mappings().all()
    return [
        FieldRegistryOut(
            key=r["key"], label_en=r["label_en"], label_mk=r["label_mk"],
            data_type=r["data_type"], applies_to=r["applies_to"],
            status=r["status"], promoted=r["promoted"],
        )
        for r in rows
    ]
