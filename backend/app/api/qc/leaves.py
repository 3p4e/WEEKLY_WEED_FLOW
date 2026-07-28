from app.db import rls
from app.deps import require_role
from app.roles import ELEVATED_ROLES
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _WRITERS, _uuid_or_404, router


_WATER_GRADES = ("TW", "BW", "TR", "RO")


_STAB_TYPES = ("LT", "ACC", "INT")


_STAB_STATUSES = ("IN_PROGRESS", "CLOSED")


_STAB_TRANSITIONS = {"IN_PROGRESS": {"CLOSED"}, "CLOSED": set()}


_TRN_STATUSES = ("draft", "in_transit", "received")


_TRN_TRANSITIONS = {"draft": {"in_transit"}, "in_transit": {"received"}, "received": set()}


# H5 — a terminal leaf is a closed record. Once a stability study is CLOSED or
# a transport is `received`, its analytical / custody fields are the record of
# what actually happened and must not be silently rewritten afterwards; only a
# note may still be added. Same shape as certificates._frozen_content_edit,
# narrowed to these two leaves. The closing patch itself is unaffected: the
# guard reads the CURRENT status, so setting `report`/`shelf_life` in the same
# PATCH that closes a study still works.
#
# Water tests are DELIBERATELY not frozen. qc_water_tests carries no status or
# lifecycle column at all, so freezing one would mean first inventing a
# lifecycle for it — a new feature, not a bug fix, and out of scope for this
# round. The asymmetry is recorded here so the next reader sees a decision
# rather than an oversight.
_LEAF_ANNOTATION_FIELDS = {"notes"}


def _assert_leaf_open(patch: dict, current: str, terminal: str, what: str) -> None:
    """409 if `patch` would change the frozen record of a terminal leaf."""
    if current != terminal:
        return
    changed = sorted(
        k for k, v in patch.items()
        if k not in _LEAF_ANNOTATION_FIELDS
        and not (k == "status" and (v is None or v == current))   # same-value echo
    )
    if changed:
        raise HTTPException(
            409, f"{what} is {terminal} — {', '.join(changed)} may no longer be changed."
                 " The closed record stands; record a note instead.")


class WaterIn(BaseModel):
    location: str = Field(max_length=120)
    grade: str
    result_date: date | None = None
    parameters: dict = Field(default_factory=dict)
    passed: bool = True
    ooe: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)


class WaterPatch(BaseModel):
    result_date: date | None = None
    parameters: dict | None = None
    passed: bool | None = None
    ooe: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)


class StabilityIn(BaseModel):
    study_type: str
    material_code: str = Field(max_length=120)
    material_name_en: str | None = Field(default=None, max_length=300)
    material_name_mk: str | None = Field(default=None, max_length=300)
    batches: list = Field(default_factory=list)
    started: date | None = None
    protocol: str | None = Field(default=None, max_length=120)
    schedule: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)


class StabilityPatch(BaseModel):
    status: str | None = None
    batches: list | None = None
    protocol: str | None = Field(default=None, max_length=120)
    schedule: str | None = Field(default=None, max_length=120)
    report: str | None = Field(default=None, max_length=120)
    shelf_life: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class TransportIn(BaseModel):
    sample_id: str = Field(max_length=120)
    batch_id: str | None = Field(default=None, max_length=120)
    external_lab: str | None = Field(default=None, max_length=120)
    tests: list = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=4000)


class TransportPatch(BaseModel):
    status: str | None = None
    external_lab: str | None = Field(default=None, max_length=120)
    tests: list | None = None
    form_sar: bool | None = None
    form_moia: bool | None = None
    form_tmcoc: bool | None = None
    form_coo: bool | None = None
    form_fin: bool | None = None
    shipped_date: date | None = None
    expected_date: date | None = None
    tracking: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)


def _water_out(r: dict) -> dict:
    return {"id": str(r["id"]), "water_test_id": r["water_test_id"], "location": r["location"],
            "grade": r["grade"], "result_date": r["result_date"].isoformat() if r["result_date"] else None,
            "parameters": r["parameters"], "passed": r["passed"], "ooe": r["ooe"], "notes": r["notes"]}


def _stab_out(r: dict) -> dict:
    return {"id": str(r["id"]), "study_id": r["study_id"], "study_type": r["study_type"],
            "material_code": r["material_code"], "material_name_en": r["material_name_en"],
            "material_name_mk": r["material_name_mk"], "batches": r["batches"],
            "started": r["started"].isoformat() if r["started"] else None, "status": r["status"],
            "protocol": r["protocol"], "schedule": r["schedule"], "report": r["report"],
            "shelf_life": r["shelf_life"], "notes": r["notes"]}


def _trn_out(r: dict) -> dict:
    return {"id": str(r["id"]), "transport_id": r["transport_id"], "sample_id": r["sample_id"],
            "batch_id": r["batch_id"], "external_lab": r["external_lab"], "tests": r["tests"],
            "status": r["status"], "forms": {"sar": r["form_sar"], "moia": r["form_moia"],
            "tmcoc": r["form_tmcoc"], "coo": r["form_coo"], "fin": r["form_fin"]},
            "shipped_date": r["shipped_date"].isoformat() if r["shipped_date"] else None,
            "expected_date": r["expected_date"].isoformat() if r["expected_date"] else None,
            "tracking": r["tracking"], "notes": r["notes"]}


def _patch_update(patch: dict, nullable: set, date_cols: set = frozenset()):
    """Build (fields, args) for a generic guarded UPDATE — shared by the leaf
    PATCH handlers. Skips None unless the column is explicitly nullable."""
    fields, args = [], []
    for col, val in patch.items():
        if val is None and col not in nullable:
            continue
        if col in date_cols:
            args.append(val); fields.append(f"{col}=${len(args)}::date")
        else:
            args.append(val); fields.append(f"{col}=${len(args)}")
    return fields, args


@router.get("/water-tests")
async def list_water(location: str | None = None, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if location:
        args.append(location); clauses.append(f"location=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_water_tests{where} ORDER BY created_at DESC", *args)
    return [_water_out(dict(r)) for r in rows]


@router.post("/water-tests", status_code=201)
async def create_water(body: WaterIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.grade not in _WATER_GRADES:
        raise HTTPException(422, f"grade must be one of: {', '.join(_WATER_GRADES)}")
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO qc_water_tests(org_id, water_test_id, location, grade, result_date,"
            " parameters, passed, ooe, notes, created_by, updated_by)"
            " VALUES ($1, 'PP-WT-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_wt_id_seq')::text, 4, '0'),"
            "         $2,$3,$4::date,$5,$6,$7,$8,$9,$9) RETURNING *",
            user["org_id"], body.location, body.grade, body.result_date, body.parameters,
            body.passed, body.ooe, body.notes, user["id"])
    return _water_out(dict(row))


@router.patch("/water-tests/{wid}")
async def update_water(wid: str, body: WaterPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(wid, "Water test")
    patch = body.model_dump(exclude_unset=True)
    fields, args = _patch_update(patch, {"ooe", "notes"}, {"result_date"})
    if not fields:
        return {"ok": True, "noop": True}
    args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
    args.append(wid)
    async with rls(user) as c:
        row = await c.fetchrow(
            f"UPDATE qc_water_tests SET {', '.join(fields)}, updated_at=now() WHERE id=${len(args)} RETURNING *", *args)
        if row is None:
            raise HTTPException(404, "Water test not found")
    return _water_out(dict(row))


@router.get("/stability-studies")
async def list_stability(status: str | None = None, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_stability_studies{where} ORDER BY created_at DESC", *args)
    return [_stab_out(dict(r)) for r in rows]


@router.post("/stability-studies", status_code=201)
async def create_stability(body: StabilityIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.study_type not in _STAB_TYPES:
        raise HTTPException(422, f"study_type must be one of: {', '.join(_STAB_TYPES)}")
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO qc_stability_studies(org_id, study_id, study_type, material_code,"
            " material_name_en, material_name_mk, batches, started, protocol, schedule, notes,"
            " created_by, updated_by)"
            " VALUES ($1, 'PP-STB-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_stb_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7::date,$8,$9,$10,$11,$11) RETURNING *",
            user["org_id"], body.study_type, body.material_code, body.material_name_en,
            body.material_name_mk, body.batches, body.started, body.protocol, body.schedule,
            body.notes, user["id"])
    return _stab_out(dict(row))


@router.patch("/stability-studies/{sid}")
async def update_stability(sid: str, body: StabilityPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(sid, "Stability study")
    patch = body.model_dump(exclude_unset=True)
    if "status" in patch and patch["status"] is not None and patch["status"] not in _STAB_STATUSES:
        raise HTTPException(422, f"status must be one of: {', '.join(_STAB_STATUSES)}")
    fields, args = _patch_update(patch, {"protocol", "schedule", "report", "shelf_life", "notes"})
    if not fields:
        return {"ok": True, "noop": True}
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_stability_studies WHERE id=$1", sid)
        if cur is None:
            raise HTTPException(404, "Stability study not found")
        _assert_leaf_open(patch, cur["status"], "CLOSED", "Stability study")
        target = patch.get("status")
        if target is not None and target != cur["status"]:
            if target not in _STAB_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(sid)
        row = await c.fetchrow(
            f"UPDATE qc_stability_studies SET {', '.join(fields)}, updated_at=now() WHERE id=${len(args)} RETURNING *", *args)
    return _stab_out(dict(row))


@router.get("/transports")
async def list_transports(status: str | None = None, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_sample_transports{where} ORDER BY created_at DESC", *args)
    return [_trn_out(dict(r)) for r in rows]


@router.post("/transports", status_code=201)
async def create_transport(body: TransportIn, user: dict = Depends(require_role(*_WRITERS))):
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO qc_sample_transports(org_id, transport_id, sample_id, batch_id,"
            " external_lab, tests, notes, created_by, updated_by)"
            " VALUES ($1, 'PP-TRN-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_trn_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7,$7) RETURNING *",
            user["org_id"], body.sample_id, body.batch_id, body.external_lab, body.tests,
            body.notes, user["id"])
    return _trn_out(dict(row))


@router.patch("/transports/{tid}")
async def update_transport(tid: str, body: TransportPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(tid, "Transport")
    patch = body.model_dump(exclude_unset=True)
    if "status" in patch and patch["status"] is not None and patch["status"] not in _TRN_STATUSES:
        raise HTTPException(422, f"status must be one of: {', '.join(_TRN_STATUSES)}")
    fields, args = _patch_update(
        patch, {"external_lab", "tracking", "notes"}, {"shipped_date", "expected_date"})
    if not fields:
        return {"ok": True, "noop": True}
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_sample_transports WHERE id=$1", tid)
        if cur is None:
            raise HTTPException(404, "Transport not found")
        _assert_leaf_open(patch, cur["status"], "received", "Transport")
        target = patch.get("status")
        if target is not None and target != cur["status"]:
            if target not in _TRN_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(tid)
        row = await c.fetchrow(
            f"UPDATE qc_sample_transports SET {', '.join(fields)}, updated_at=now() WHERE id=${len(args)} RETURNING *", *args)
    return _trn_out(dict(row))
