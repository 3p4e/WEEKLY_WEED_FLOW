from app.db import rls
from app.worktime import SITE_YEAR_SQL
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _QP_ROLES, _WRITERS, _uuid_or_404, _uuid_or_422, router, splice_stamps


_OOS_TYPES = ("OOS", "OOT", "OOE", "OOC")


_OOS_RISK = ("HIGH", "MEDIUM", "LOW")


_OOS_PHASES = ("I", "II")


_OOS_STATUSES = ("OPEN", "PHASE_I", "PHASE_II", "CLOSED")


_OOS_DISPOSITIONS = ("RELEASE", "REJECT", "REPROCESS", "RETAIN")


_OOS_NOTIF_PARTS = ("A", "B", "C", "D")


_OOS_TRANSITIONS = {
    "OPEN": {"PHASE_I", "CLOSED"},
    "PHASE_I": {"PHASE_II", "CLOSED"},
    "PHASE_II": {"CLOSED"},
    "CLOSED": set(),
}


_OOS_QP_TARGETS = {"CLOSED"}


class OosIn(BaseModel):
    batch_id: str = Field(max_length=120)
    result_id: str | None = None
    sample_id: str | None = None
    material_code: str | None = Field(default=None, max_length=120)
    test_name: str | None = Field(default=None, max_length=300)
    method_ref: str | None = Field(default=None, max_length=300)
    specification_value: str | None = Field(default=None, max_length=200)
    obtained_value: str | None = Field(default=None, max_length=200)
    oos_type: str = "OOS"
    risk_level: str | None = None
    detection_date: date | None = None
    timeline_deadline: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class OosPatch(BaseModel):
    status: str | None = None            # guarded lifecycle transition
    phase: str | None = None
    risk_level: str | None = None
    # Phase I
    lab_investigation_result: str | None = Field(default=None, max_length=4000)
    lab_error: bool | None = None
    invalidated: bool | None = None
    retest_result: str | None = Field(default=None, max_length=2000)
    # Phase II
    root_cause_category: str | None = Field(default=None, max_length=120)
    root_cause_description: str | None = Field(default=None, max_length=4000)
    impact_assessment: str | None = Field(default=None, max_length=4000)
    capa_reference: str | None = Field(default=None, max_length=120)
    effectiveness_check_date: date | None = None
    effectiveness_check_result: str | None = Field(default=None, max_length=2000)
    # Disposition (QP)
    disposition: str | None = None
    disposition_reason: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)


class OosRegisterIn(BaseModel):
    action: str = Field(max_length=120)
    details: str | None = Field(default=None, max_length=2000)


class OosNotifyIn(BaseModel):
    part: str = "A"
    recipients: list[str] = Field(default_factory=list)
    message: str | None = Field(default=None, max_length=2000)


def _oos_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "oos_number": r["oos_number"],
        "result_id": str(r["result_id"]) if r["result_id"] else None,
        "sample_id": str(r["sample_id"]) if r["sample_id"] else None,
        "batch_id": r["batch_id"], "material_code": r["material_code"],
        "test_name": r["test_name"], "method_ref": r["method_ref"],
        "specification_value": r["specification_value"], "obtained_value": r["obtained_value"],
        "oos_type": r["oos_type"], "risk_level": r["risk_level"],
        "phase": r["phase"], "status": r["status"],
        "detection_date": r["detection_date"].isoformat() if r["detection_date"] else None,
        "detected_by_id": str(r["detected_by_id"]) if r["detected_by_id"] else None,
        "timeline_deadline": r["timeline_deadline"].isoformat() if r["timeline_deadline"] else None,
        "lab_investigation_result": r["lab_investigation_result"], "lab_error": r["lab_error"],
        "invalidated": r["invalidated"], "retest_result": r["retest_result"],
        "root_cause_category": r["root_cause_category"],
        "root_cause_description": r["root_cause_description"],
        "impact_assessment": r["impact_assessment"], "capa_reference": r["capa_reference"],
        "effectiveness_check_date":
            r["effectiveness_check_date"].isoformat() if r["effectiveness_check_date"] else None,
        "effectiveness_check_result": r["effectiveness_check_result"],
        "disposition": r["disposition"], "disposition_reason": r["disposition_reason"],
        "qp_approved_by_id": str(r["qp_approved_by_id"]) if r["qp_approved_by_id"] else None,
        "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }


def _register_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "action": r["action"],
        "actor_id": str(r["actor_id"]) if r["actor_id"] else None,
        "details": r["details"], "created_at": r["created_at"].isoformat(),
    }


def _notif_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "part": r["part"], "recipients": r["recipients"],
        "message": r["message"], "acknowledged": r["acknowledged"],
        "acknowledged_at": r["acknowledged_at"].isoformat() if r["acknowledged_at"] else None,
        "acknowledged_by_id": str(r["acknowledged_by_id"]) if r.get("acknowledged_by_id") else None,
        "sent_by_id": str(r["sent_by_id"]) if r["sent_by_id"] else None,
        "sent_at": r["sent_at"].isoformat(),
    }


def _capa_from_oos(r: dict) -> dict:
    """Derive a CAPA-register entry from an OOS row (read-time; no CAPA table).
    Mirrors qc-lims-ao api/capa.py:_capa_status — OPEN→IN_PROGRESS→EFFECTIVE→
    CLOSED from OOS state, never fabricating fields the OOS doesn't carry."""
    if r["status"] == "CLOSED":
        status = "CLOSED"
    elif r["effectiveness_check_date"] is not None:
        status = "EFFECTIVE"
    elif r["status"] == "PHASE_II" or r["root_cause_description"]:
        status = "IN_PROGRESS"
    else:
        status = "OPEN"
    return {
        "id": r["capa_reference"] or f"CAPA-{r['oos_number']}",
        "oos_number": r["oos_number"], "oos_id": str(r["id"]),
        "status": status,
        "owner_id": str(r["phase_ii_completed_by_id"] or r["detected_by_id"] or "") or None,
        "opened": (r["detection_date"] or r["created_at"]).isoformat()
            if (r["detection_date"] or r["created_at"]) else None,
        "due": r["timeline_deadline"].isoformat() if r["timeline_deadline"] else None,
        "title": r["root_cause_description"] or r["test_name"] or r["batch_id"],
        "root_cause_category": r["root_cause_category"],
        "effectiveness_check_date":
            r["effectiveness_check_date"].isoformat() if r["effectiveness_check_date"] else None,
    }


@router.get("/oos")
async def list_oos(batch_id: str | None = None, status: str | None = None,
                   oos_type: str | None = None, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    for col, val in (("batch_id", batch_id), ("status", status), ("oos_type", oos_type)):
        if val:
            args.append(val); clauses.append(f"{col}=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_oos_records{where} ORDER BY created_at DESC", *args)
    return [_oos_out(dict(r)) for r in rows]


@router.get("/oos/{oos_id}")
async def get_oos(oos_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(oos_id, "OOS record")
    async with rls(user) as c:
        oos = await c.fetchrow("SELECT * FROM qc_oos_records WHERE id=$1", oos_id)
        if oos is None:
            raise HTTPException(404, "OOS record not found")
        reg = await c.fetch(
            "SELECT * FROM qc_oos_register WHERE oos_id=$1 ORDER BY created_at", oos_id)
        notifs = await c.fetch(
            "SELECT * FROM qc_oos_notifications WHERE oos_id=$1 ORDER BY sent_at", oos_id)
    return {"oos": _oos_out(dict(oos)),
            "register": [_register_out(dict(x)) for x in reg],
            "notifications": [_notif_out(dict(x)) for x in notifs]}


@router.post("/oos", status_code=201)
async def create_oos(body: OosIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.oos_type not in _OOS_TYPES:
        raise HTTPException(422, f"oos_type must be one of: {', '.join(_OOS_TYPES)}")
    if body.risk_level is not None and body.risk_level not in _OOS_RISK:
        raise HTTPException(422, f"risk_level must be one of: {', '.join(_OOS_RISK)}")
    _uuid_or_422(body.result_id, "result_id")
    _uuid_or_422(body.sample_id, "sample_id")
    async with rls(user) as c:
        if body.result_id:
            if await c.fetchrow("SELECT id FROM qc_results WHERE id=$1", body.result_id) is None:
                raise HTTPException(422, "Unknown result")
        if body.sample_id:
            if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", body.sample_id) is None:
                raise HTTPException(422, "Unknown sample")
        row = await c.fetchrow(
            "INSERT INTO qc_oos_records(org_id, oos_number, result_id, sample_id, batch_id,"
            " material_code, test_name, method_ref, specification_value, obtained_value, oos_type,"
            " risk_level, detection_date, detected_by_id, timeline_deadline, notes, created_by, updated_by)"
            f" VALUES ($1, 'PP-OOS-' || {SITE_YEAR_SQL} || '-' ||"  # nosec B608 — SITE_YEAR_SQL is a trusted constant
            "         lpad(nextval('qc_oos_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$16) RETURNING *",
            user["org_id"], body.result_id, body.sample_id, body.batch_id, body.material_code,
            body.test_name, body.method_ref, body.specification_value, body.obtained_value,
            body.oos_type, body.risk_level, body.detection_date, user["id"], body.timeline_deadline,
            body.notes, user["id"])
        await c.execute(
            "INSERT INTO qc_oos_register(org_id, oos_id, action, actor_id, details)"
            " VALUES ($1,$2,'opened',$3,$4)",
            user["org_id"], row["id"], user["id"], f"{row['oos_type']} opened for batch {row['batch_id']}")
        await safe_emit(c, user, verb="oos_opened", object_type="qc_oos_record",
                   object_id=row["id"], recipients=[],
                   params={"oos_number": row["oos_number"], "batch_id": row["batch_id"]})
    return _oos_out(dict(row))


@router.patch("/oos/{oos_id}")
async def update_oos(oos_id: str, body: OosPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(oos_id, "OOS record")
    patch = body.model_dump(exclude_unset=True)
    if patch.get("risk_level") is not None and patch["risk_level"] not in _OOS_RISK:
        raise HTTPException(422, "Unknown risk_level")
    if patch.get("phase") is not None and patch["phase"] not in _OOS_PHASES:
        raise HTTPException(422, "Unknown phase")
    if patch.get("disposition") is not None and patch["disposition"] not in _OOS_DISPOSITIONS:
        raise HTTPException(422, "Unknown disposition")
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT status, disposition, root_cause_description, impact_assessment"
            " FROM qc_oos_records WHERE id=$1", oos_id)
        if cur is None:
            raise HTTPException(404, "OOS record not found")
        # Setting a batch disposition is a Qualified-Person decision.
        if patch.get("disposition") is not None and user["role"] not in _QP_ROLES:
            raise HTTPException(403, "Disposition is a Qualified-Person decision")
        extra_sql, extra_args = [], []
        reg_action = None
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _OOS_STATUSES:
                raise HTTPException(422, "Unknown status")
            if target not in _OOS_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            if target in _OOS_QP_TARGETS and user["role"] not in _QP_ROLES:
                raise HTTPException(403, f"{target} is a Qualified-Person decision")
            reg_action = f"status:{cur['status']}->{target}"
            if target == "PHASE_II":
                extra_args.append(user["id"])
                extra_sql.append("phase_i_completed_by_id=$PLACEHOLDER")
                extra_sql.append("phase_i_completed_at=now()")
            if target == "CLOSED":
                # §6.x — an OOS is not closed until it is investigated: a batch
                # disposition and a documented root cause are mandatory, and a
                # Phase-II close additionally needs its impact assessment. The
                # effective value is the patch's, or the already-stored one.
                eff_disp = patch.get("disposition", cur["disposition"])
                eff_rc = patch.get("root_cause_description", cur["root_cause_description"])
                eff_impact = patch.get("impact_assessment", cur["impact_assessment"])
                if not (eff_disp and str(eff_disp).strip()):
                    raise HTTPException(409, "an OOS cannot be closed without a batch disposition"
                                             " (RELEASE/REJECT/REPROCESS/RETAIN) — §6.x")
                if not (eff_rc and str(eff_rc).strip()):
                    raise HTTPException(409, "an OOS cannot be closed without a documented root cause")
                if cur["status"] == "PHASE_II" and not (eff_impact and str(eff_impact).strip()):
                    raise HTTPException(409, "a Phase-II OOS cannot be closed without an impact assessment")
                extra_args.append(user["id"])
                extra_sql.append("closed_by_id=$PLACEHOLDER")
                extra_sql.append("closed_at=now()")
                extra_args.append(user["id"])
                extra_sql.append("qp_approved_by_id=$PLACEHOLDER")
                extra_sql.append("qp_approved_at=now()")
                if cur["status"] == "PHASE_II":
                    extra_args.append(user["id"])
                    extra_sql.append("phase_ii_completed_by_id=$PLACEHOLDER")
                    extra_sql.append("phase_ii_completed_at=now()")
        fields, args = [], []
        _NULLABLE = {"risk_level", "lab_investigation_result", "retest_result",
                     "root_cause_category", "root_cause_description", "impact_assessment",
                     "capa_reference", "effectiveness_check_result", "disposition",
                     "disposition_reason", "notes"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            args.append(val); fields.append(f"{col}=${len(args)}")
        splice_stamps(fields, args, extra_sql, extra_args)
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(oos_id)
        row = await c.fetchrow(
            f"UPDATE qc_oos_records SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
        if reg_action is not None:
            await c.execute(
                "INSERT INTO qc_oos_register(org_id, oos_id, action, actor_id, details)"
                " VALUES ($1,$2,$3,$4,$5)",
                user["org_id"], oos_id, reg_action, user["id"], None)
    return _oos_out(dict(row))


@router.post("/oos/{oos_id}/register", status_code=201)
async def add_register_event(oos_id: str, body: OosRegisterIn,
                             user: dict = Depends(require_role(*_WRITERS))):
    """Append an event to the OOS register. Append-only — the register is never
    modified or deleted (the qc-lims-ao 'ONCE WRITTEN, NEVER MODIFIED' rule)."""
    _uuid_or_404(oos_id, "OOS record")
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_oos_records WHERE id=$1", oos_id) is None:
            raise HTTPException(404, "OOS record not found")
        row = await c.fetchrow(
            "INSERT INTO qc_oos_register(org_id, oos_id, action, actor_id, details)"
            " VALUES ($1,$2,$3,$4,$5) RETURNING *",
            user["org_id"], oos_id, body.action, user["id"], body.details)
    return _register_out(dict(row))


@router.post("/oos/{oos_id}/notifications", status_code=201)
async def add_oos_notification(oos_id: str, body: OosNotifyIn,
                               user: dict = Depends(require_role(*_WRITERS))):
    if body.part not in _OOS_NOTIF_PARTS:
        raise HTTPException(422, f"part must be one of: {', '.join(_OOS_NOTIF_PARTS)}")
    _uuid_or_404(oos_id, "OOS record")
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_oos_records WHERE id=$1", oos_id) is None:
            raise HTTPException(404, "OOS record not found")
        # recipients is jsonb; the connection has a global jsonb codec (app/db.py)
        # so the Python list is encoded directly — never json.dumps() it here or
        # it double-encodes into a JSON string.
        row = await c.fetchrow(
            "INSERT INTO qc_oos_notifications(org_id, oos_id, part, recipients, message, sent_by_id)"
            " VALUES ($1,$2,$3,$4,$5,$6) RETURNING *",
            user["org_id"], oos_id, body.part, body.recipients, body.message, user["id"])
    return _notif_out(dict(row))


def _ack_authorized(user: dict, recipients) -> bool:
    """M9: a GxP acknowledgement must be made by an addressed recipient. ADMIN
    (the system administrator, a QP-equivalent QC writer) may always ack; an
    unaddressed notification (empty recipients) has no membership to enforce.
    Otherwise the caller must match a recipient by username, full name, or role
    (case-insensitive; an email-style recipient also matches on its local part)."""
    if user.get("role") == ADMIN or not recipients:
        return True
    ident = {str(v).strip().lower() for v in
             (user.get("username"), user.get("full_name"), user.get("role")) if v}
    for r in recipients:
        rl = str(r).strip().lower()
        if rl and (rl in ident or rl.split("@")[0] in ident):
            return True
    return False


@router.post("/oos/{oos_id}/notifications/{notif_id}/ack")
async def ack_oos_notification(oos_id: str, notif_id: str,
                               user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(oos_id, "OOS record")
    _uuid_or_404(notif_id, "Notification")
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT recipients FROM qc_oos_notifications WHERE id=$1 AND oos_id=$2",
            notif_id, oos_id)
        if cur is None:
            raise HTTPException(404, "Notification not found")
        # M9: enforce recipient membership + attribute WHO acknowledged — an
        # acknowledgement that records neither the recipient nor the acknowledger
        # is a forgeable GxP act.
        if not _ack_authorized(user, cur["recipients"]):
            raise HTTPException(403, "Only an addressed recipient may acknowledge this notification")
        row = await c.fetchrow(
            "UPDATE qc_oos_notifications SET acknowledged=true, acknowledged_at=now(),"
            " acknowledged_by_id=$3 WHERE id=$1 AND oos_id=$2 RETURNING *",
            notif_id, oos_id, user["id"])
    return _notif_out(dict(row))


@router.get("/capa")
async def list_capa(status: str | None = None, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        rows = await c.fetch("SELECT * FROM qc_oos_records ORDER BY created_at DESC")
    capa = [_capa_from_oos(dict(r)) for r in rows]
    if status:
        capa = [x for x in capa if x["status"] == status]
    return capa
