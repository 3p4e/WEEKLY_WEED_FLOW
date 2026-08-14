from app.db import rls
from app.worktime import SITE_YEAR_SQL
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _QP_ROLES, _SAMPLE_KINDS, _WRITERS, _uuid_or_404, _uuid_or_422, router


_SAMPLE_STATUSES = (
    "COLLECTED", "IN_TRANSIT", "RECEIVED", "IN_TEST", "TESTED",
    "REVIEWED", "APPROVED", "RELEASED", "REJECTED", "QUARANTINE",
)


_FREQUENCIES = ("EVERY_BATCH", "PERIODIC", "RANDOM")


_SAMPLE_TRANSITIONS = {
    "COLLECTED": {"IN_TRANSIT", "RECEIVED", "QUARANTINE", "REJECTED"},
    "IN_TRANSIT": {"RECEIVED", "REJECTED"},
    "RECEIVED": {"IN_TEST", "REJECTED"},
    "IN_TEST": {"TESTED", "QUARANTINE"},
    "TESTED": {"REVIEWED", "QUARANTINE", "REJECTED"},
    "REVIEWED": {"APPROVED", "REJECTED"},
    "APPROVED": {"RELEASED", "REJECTED"},
    "QUARANTINE": {"IN_TEST", "REJECTED"},
    "RELEASED": set(),
    "REJECTED": set(),
}


_QP_TRANSITION_TARGETS = {"RELEASED", "REJECTED"}


class PlanIn(BaseModel):
    material_code: str = Field(max_length=120)
    sampling_frequency: str = "EVERY_BATCH"
    sample_size_formula: str | None = Field(default=None, max_length=200)
    min_sample_size: int | None = Field(default=None, ge=0, le=100000)
    max_sample_size: int | None = Field(default=None, ge=0, le=100000)


class SampleIn(BaseModel):
    batch_id: str = Field(max_length=120)
    material_code: str = Field(max_length=120)
    sample_type: str | None = Field(default=None, max_length=60)
    material_name_en: str | None = Field(default=None, max_length=300)
    material_name_mk: str | None = Field(default=None, max_length=300)
    sampling_date: date | None = None
    location: str | None = Field(default=None, max_length=200)
    quantity: float | None = None
    quantity_unit: str | None = Field(default=None, max_length=40)
    retention_sample: bool = False
    sample_kind: str | None = None              # QCSOP 011 §6.2.1 taxonomy
    retention_expiry: date | None = None        # QCSOP 011 §7.0 retention
    parent_id: str | None = None
    sampling_plan_id: str | None = None
    notes: str | None = Field(default=None, max_length=2000)


class SamplePatch(BaseModel):
    location: str | None = Field(default=None, max_length=200)
    quantity: float | None = None
    quantity_unit: str | None = Field(default=None, max_length=40)
    sample_kind: str | None = None
    retention_expiry: date | None = None
    non_conforming: bool | None = None          # QCSOP 011 §6.7 flag
    non_conforming_reason: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    status: str | None = None                   # guarded lifecycle transition


def _plan_out(r: dict) -> dict:
    return {"id": str(r["id"]), "plan_id": r["plan_id"], "material_code": r["material_code"],
            "sampling_frequency": r["sampling_frequency"], "sample_size_formula": r["sample_size_formula"],
            "min_sample_size": r["min_sample_size"], "max_sample_size": r["max_sample_size"],
            "active": r["active"]}


def _sample_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "sample_id": r["sample_id"], "batch_id": r["batch_id"],
        "sample_type": r["sample_type"], "material_code": r["material_code"],
        "material_name_en": r["material_name_en"], "material_name_mk": r["material_name_mk"],
        "sampling_date": r["sampling_date"].isoformat() if r["sampling_date"] else None,
        "status": r["status"], "location": r["location"],
        "quantity": float(r["quantity"]) if r["quantity"] is not None else None,
        "quantity_unit": r["quantity_unit"], "retention_sample": r["retention_sample"],
        "sample_kind": r["sample_kind"],
        "retention_expiry": r["retention_expiry"].isoformat() if r["retention_expiry"] else None,
        "non_conforming": r["non_conforming"], "non_conforming_reason": r["non_conforming_reason"],
        "parent_id": str(r["parent_id"]) if r["parent_id"] else None,
        "sampling_plan_id": str(r["sampling_plan_id"]) if r["sampling_plan_id"] else None,
        "tested_by": str(r["tested_by"]) if r.get("tested_by") else None,
        "reviewed_by": str(r["reviewed_by"]) if r.get("reviewed_by") else None,
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }


@router.get("/sampling-plans")
async def list_plans(material_code: str | None = None,
                     user: dict = Depends(require_role(*ELEVATED_ROLES))):
    args, where = [], ""
    if material_code:
        args.append(material_code); where = " WHERE material_code=$1 AND active"
    else:
        where = " WHERE active"
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_sampling_plans{where} ORDER BY material_code", *args)
    return [_plan_out(dict(r)) for r in rows]


@router.post("/sampling-plans", status_code=201)
async def create_plan(body: PlanIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.sampling_frequency not in _FREQUENCIES:
        raise HTTPException(422, f"sampling_frequency must be one of: {', '.join(_FREQUENCIES)}")
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO qc_sampling_plans(org_id, plan_id, material_code, sampling_frequency,"
            " sample_size_formula, min_sample_size, max_sample_size, created_by, updated_by)"
            f" VALUES ($1, 'PP-SPL-' || {SITE_YEAR_SQL} || '-' ||"  # nosec B608 — SITE_YEAR_SQL is a trusted constant
            "         lpad(nextval('qc_sampling_plan_id_seq')::text, 4, '0'),"
            "         $2,$3,COALESCE($4,'ROUNDUP(SQRT(N)*1.5)'),$5,$6,$7,$7) RETURNING *",
            user["org_id"], body.material_code, body.sampling_frequency, body.sample_size_formula,
            body.min_sample_size, body.max_sample_size, user["id"])
    return _plan_out(dict(row))


@router.get("/samples")
async def list_samples(batch_id: str | None = None, status: str | None = None,
                       user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if batch_id:
        args.append(batch_id); clauses.append(f"batch_id=${len(args)}")
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_samples{where} ORDER BY created_at DESC", *args)
    return [_sample_out(dict(r)) for r in rows]


@router.get("/samples/{sample_id}")
async def get_sample(sample_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(sample_id, "Sample")
    async with rls(user) as c:
        s = await c.fetchrow("SELECT * FROM qc_samples WHERE id=$1", sample_id)
        if s is None:
            raise HTTPException(404, "Sample not found")
        kids = await c.fetch(
            "SELECT * FROM qc_samples WHERE parent_id=$1 ORDER BY created_at", sample_id)
    return {"sample": _sample_out(dict(s)), "children": [_sample_out(dict(k)) for k in kids]}


@router.post("/samples", status_code=201)
async def create_sample(body: SampleIn, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_422(body.parent_id, "parent_id")
    _uuid_or_422(body.sampling_plan_id, "sampling_plan_id")
    if body.sample_kind is not None and body.sample_kind not in _SAMPLE_KINDS:
        raise HTTPException(422, f"sample_kind must be one of: {', '.join(_SAMPLE_KINDS)} (QCSOP 011 §6.2.1)")
    async with rls(user) as c:
        if body.parent_id:
            p = await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", body.parent_id)
            if p is None:
                raise HTTPException(422, "Unknown parent sample")
        if body.sampling_plan_id:
            pl = await c.fetchrow("SELECT id FROM qc_sampling_plans WHERE id=$1", body.sampling_plan_id)
            if pl is None:
                raise HTTPException(422, "Unknown sampling plan")
        row = await c.fetchrow(
            "INSERT INTO qc_samples(org_id, sample_id, batch_id, material_code, sample_type,"
            " material_name_en, material_name_mk, sampling_date, location, quantity, quantity_unit,"
            " retention_sample, sample_kind, retention_expiry, parent_id, sampling_plan_id, notes,"
            " created_by, updated_by)"
            f" VALUES ($1, 'PP-SMP-' || {SITE_YEAR_SQL} || '-' ||"  # nosec B608 — SITE_YEAR_SQL is a trusted constant
            "         lpad(nextval('qc_sample_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7::date,$8,$9,$10,$11,$12,$13::date,$14,$15,$16,$17,$17) RETURNING *",
            user["org_id"], body.batch_id, body.material_code, body.sample_type,
            body.material_name_en, body.material_name_mk, body.sampling_date, body.location,
            body.quantity, body.quantity_unit, body.retention_sample, body.sample_kind,
            body.retention_expiry, body.parent_id, body.sampling_plan_id, body.notes, user["id"])
        await safe_emit(c, user, verb="sample_collected", object_type="qc_sample",
                   object_id=row["id"], recipients=[],
                   params={"sample_id": row["sample_id"], "batch_id": row["batch_id"]})
    return _sample_out(dict(row))


@router.patch("/samples/{sample_id}")
async def update_sample(sample_id: str, body: SamplePatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(sample_id, "Sample")
    patch = body.model_dump(exclude_unset=True)
    stamp: list[tuple[str, object]] = []
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT status, batch_id, tested_by FROM qc_samples WHERE id=$1", sample_id)
        if cur is None:
            raise HTTPException(404, "Sample not found")
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _SAMPLE_STATUSES:
                raise HTTPException(422, "Unknown status")
            if target not in _SAMPLE_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            # release / reject are a QP-level decision
            if target in _QP_TRANSITION_TARGETS and user["role"] not in _QP_ROLES:
                raise HTTPException(403, f"{target} is a Qualified-Person decision")
            # H2 (second person): the reviewer of test results must not be the
            # analyst who produced them — mirrors the certificate reviewer≠analyst
            # control. Stamp who tested (→TESTED) and who reviewed (→REVIEWED).
            if target == "TESTED":
                stamp.append(("tested_by", user["id"]))
            if target == "REVIEWED":
                if cur["tested_by"] and str(cur["tested_by"]) == str(user["id"]):
                    raise HTTPException(
                        403, "The reviewer of a tested sample must differ from the"
                             " analyst who tested it (second-person review)")
                stamp.append(("reviewed_by", user["id"]))
            # H2 (batch-release OOS gate): a sample cannot be RELEASED while an OOS
            # investigation on its batch is still open — the exact condition every
            # CoQ path already blocks. A failing result auto-quarantines, but the
            # QUARANTINE→…→RELEASED path was otherwise reachable with an OOS OPEN.
            if target == "RELEASED" and cur["batch_id"]:
                open_oos = await c.fetchval(
                    "SELECT count(*) FROM qc_oos_records WHERE batch_id=$1 AND status <> 'CLOSED'",
                    cur["batch_id"])
                if open_oos:
                    raise HTTPException(
                        409, f"{open_oos} open OOS investigation(s) on batch {cur['batch_id']}"
                             " — the sample cannot be released until they are closed")
        if patch.get("sample_kind") is not None and patch["sample_kind"] not in _SAMPLE_KINDS:
            raise HTTPException(422, f"sample_kind must be one of: {', '.join(_SAMPLE_KINDS)} (QCSOP 011 §6.2.1)")
        fields, args = [], []
        _NULLABLE = {"location", "quantity", "quantity_unit", "notes",
                     "sample_kind", "retention_expiry", "non_conforming_reason"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            args.append(val); fields.append(f"{col}=${len(args)}")
        for col, val in stamp:
            args.append(val); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(sample_id)
        row = await c.fetchrow(
            f"UPDATE qc_samples SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
    return _sample_out(dict(row))
