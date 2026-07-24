from app.db import rls
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _WRITERS, _uuid_or_404, _uuid_or_422, router


_SPEC_STATUSES = (
    "INITIATED", "DRAFT", "QC_REVIEW", "QA_APPROVED", "NUMBERED",
    "TRAINED", "ACTIVE", "UNDER_CHANGE", "SUPERSEDED", "WITHDRAWN",
)


_THC_GRADES = ("GRADE_I", "GRADE_II", "GRADE_III", "GRADE_IV", "GRADE_V")


_COMPUTED_KINDS = ("total_thc", "total_cbd")


_ACID_FACTOR = 0.877


_SPEC_TRANSITIONS = {
    "INITIATED": {"DRAFT", "WITHDRAWN"},
    "DRAFT": {"QC_REVIEW", "WITHDRAWN"},
    "QC_REVIEW": {"QA_APPROVED", "DRAFT", "WITHDRAWN"},
    "QA_APPROVED": {"NUMBERED", "WITHDRAWN"},
    "NUMBERED": {"TRAINED", "WITHDRAWN"},
    "TRAINED": {"ACTIVE", "WITHDRAWN"},
    "ACTIVE": {"UNDER_CHANGE", "SUPERSEDED"},
    "UNDER_CHANGE": {"ACTIVE", "WITHDRAWN"},
    "SUPERSEDED": set(),
    "WITHDRAWN": set(),
}


_EDITABLE_STATUSES = {"INITIATED", "DRAFT", "QC_REVIEW"}


class SpecIn(BaseModel):
    material_code: str = Field(max_length=120)
    material_name_en: str = Field(max_length=300)
    material_name_mk: str | None = Field(default=None, max_length=300)
    version: int = Field(default=1, ge=1, le=999)
    effective_date: date | None = None
    thc_grade: str | None = None
    thc_acceptance_min: float | None = None
    thc_acceptance_max: float | None = None
    notes: str | None = Field(default=None, max_length=4000)


class SpecPatch(BaseModel):
    material_name_en: str | None = Field(default=None, max_length=300)
    material_name_mk: str | None = Field(default=None, max_length=300)
    effective_date: date | None = None
    thc_grade: str | None = None
    thc_acceptance_min: float | None = None
    thc_acceptance_max: float | None = None
    notes: str | None = Field(default=None, max_length=4000)
    status: str | None = None                    # guarded lifecycle transition


class ParamIn(BaseModel):
    test_name_en: str = Field(max_length=300)
    test_name_mk: str | None = Field(default=None, max_length=300)
    test_method: str | None = Field(default=None, max_length=300)
    spec_type: str | None = Field(default=None, max_length=60)
    lower_limit: float | None = None
    upper_limit: float | None = None
    unit: str | None = Field(default=None, max_length=60)
    pharmacopoeia_ref: str | None = Field(default=None, max_length=200)
    test_location: str | None = Field(default=None, max_length=120)
    sorting_order: int = Field(default=0, ge=0, le=1000)
    # Ph. Eur. 3028 derived parameters: total THC = Δ9-THC + 0.877 × THCA
    # (total CBD analogously). component_a = neutral form, component_b = acid
    # form; the COQ engine computes a + 0.877·b deterministically — a derived
    # value is never transcribed.
    computed_kind: str | None = None                 # total_thc | total_cbd
    component_a_id: str | None = None
    component_b_id: str | None = None


def _check_grade(g: str | None) -> None:
    if g is not None and g not in _THC_GRADES:
        raise HTTPException(422, f"thc_grade must be one of: {', '.join(_THC_GRADES)}")


def _spec_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "spec_id": r["spec_id"], "material_code": r["material_code"],
        "material_name_en": r["material_name_en"], "material_name_mk": r["material_name_mk"],
        "version": r["version"],
        "effective_date": r["effective_date"].isoformat() if r["effective_date"] else None,
        "status": r["status"], "thc_grade": r["thc_grade"],
        "thc_acceptance_min": float(r["thc_acceptance_min"]) if r["thc_acceptance_min"] is not None else None,
        "thc_acceptance_max": float(r["thc_acceptance_max"]) if r["thc_acceptance_max"] is not None else None,
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }


def _param_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "test_name_en": r["test_name_en"], "test_name_mk": r["test_name_mk"],
        "test_method": r["test_method"], "spec_type": r["spec_type"],
        "lower_limit": float(r["lower_limit"]) if r["lower_limit"] is not None else None,
        "upper_limit": float(r["upper_limit"]) if r["upper_limit"] is not None else None,
        "unit": r["unit"], "pharmacopoeia_ref": r["pharmacopoeia_ref"],
        "test_location": r["test_location"], "sorting_order": r["sorting_order"],
        "computed_kind": r.get("computed_kind"),
        "component_a_id": str(r["component_a_id"]) if r.get("component_a_id") else None,
        "component_b_id": str(r["component_b_id"]) if r.get("component_b_id") else None,
    }


@router.get("/specifications")
async def list_specs(material_code: str | None = None, status: str | None = None,
                     user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if material_code:
        args.append(material_code); clauses.append(f"material_code=${len(args)}")
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT id, spec_id, material_code, material_name_en, material_name_mk, version,"
            " effective_date, status, thc_grade, thc_acceptance_min, thc_acceptance_max, notes,"
            f" updated_at FROM qc_specifications{where} ORDER BY material_code, version DESC", *args)
    return [_spec_out(dict(r)) for r in rows]


@router.get("/specifications/{spec_id}")
async def get_spec(spec_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(spec_id, "Specification")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT * FROM qc_specifications WHERE id=$1", spec_id)
        if spec is None:
            raise HTTPException(404, "Specification not found")
        params = await c.fetch(
            "SELECT * FROM qc_spec_parameters WHERE spec_id=$1 ORDER BY sorting_order, test_name_en",
            spec_id)
    return {"spec": _spec_out(dict(spec)), "parameters": [_param_out(dict(p)) for p in params]}


@router.post("/specifications", status_code=201)
async def create_spec(body: SpecIn, user: dict = Depends(require_role(*_WRITERS))):
    _check_grade(body.thc_grade)
    async with rls(user) as c:
        try:
            row = await c.fetchrow(
                "INSERT INTO qc_specifications(org_id, spec_id, material_code, material_name_en,"
                " material_name_mk, version, effective_date, thc_grade, thc_acceptance_min,"
                " thc_acceptance_max, notes, created_by, updated_by)"
                " VALUES ($1, 'PP-SPEC-' || to_char(now(),'YYYY') || '-' ||"
                "         lpad(nextval('qc_spec_id_seq')::text, 4, '0'),"
                "         $2,$3,$4,$5,$6::date,$7,$8,$9,$10,$11,$11) RETURNING *",
                user["org_id"], body.material_code, body.material_name_en, body.material_name_mk,
                body.version, body.effective_date, body.thc_grade, body.thc_acceptance_min,
                body.thc_acceptance_max, body.notes, user["id"])
        except Exception as e:
            # UNIQUE(org, material_code, version) collision
            if "qc_specifications_material_version_key" in str(e):
                raise HTTPException(409, "A specification with this material_code + version already exists")
            raise
        await safe_emit(c, user, verb="spec_created", object_type="qc_specification",
                   object_id=row["id"], recipients=[],
                   params={"spec_id": row["spec_id"], "material_code": row["material_code"]})
    return _spec_out(dict(row))


@router.patch("/specifications/{spec_id}")
async def update_spec(spec_id: str, body: SpecPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(spec_id, "Specification")
    patch = body.model_dump(exclude_unset=True)
    _check_grade(patch.get("thc_grade"))
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_specifications WHERE id=$1", spec_id)
        if cur is None:
            raise HTTPException(404, "Specification not found")
        # The pharmaceutically load-bearing fields (acceptance criteria, grade,
        # effective date, identity) are locked once the spec leaves authoring —
        # the same control the child parameters already enforce. Outside the
        # editable states only a lifecycle `status` move + `notes` may change;
        # a substantive revision goes through a new version, not an in-place edit.
        if cur["status"] not in _EDITABLE_STATUSES:
            locked = {k for k in patch if k not in ("status", "notes")}
            if locked:
                raise HTTPException(
                    409, f"Specification is {cur['status']}; {', '.join(sorted(locked))} "
                         "cannot be edited after authoring — supersede with a new version instead")
        # A status change is a guarded lifecycle transition, validated first.
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _SPEC_STATUSES:
                raise HTTPException(422, "Unknown status")
            if target not in _SPEC_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
        fields, args = [], []
        _NULLABLE = {"material_name_mk", "effective_date", "thc_grade",
                     "thc_acceptance_min", "thc_acceptance_max", "notes"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            if col == "effective_date":
                args.append(val); fields.append(f"{col}=${len(args)}::date")
            else:
                args.append(val); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(spec_id)
        try:
            row = await c.fetchrow(
                f"UPDATE qc_specifications SET {', '.join(fields)}, updated_at=now()"
                f" WHERE id=${len(args)} RETURNING *", *args)
        except Exception as e:
            if "qc_specifications_one_active_idx" in str(e):
                raise HTTPException(409, "Another ACTIVE specification already exists for this material")
            raise
    return _spec_out(dict(row))


@router.post("/specifications/{spec_id}/parameters", status_code=201)
async def add_parameter(spec_id: str, body: ParamIn, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(spec_id, "Specification")
    if body.computed_kind is not None and body.computed_kind not in _COMPUTED_KINDS:
        raise HTTPException(422, f"computed_kind must be one of: {', '.join(_COMPUTED_KINDS)}")
    if body.computed_kind is not None and not (body.component_a_id and body.component_b_id):
        raise HTTPException(422, "A computed parameter requires component_a_id and component_b_id")
    if body.computed_kind is None and (body.component_a_id or body.component_b_id):
        raise HTTPException(422, "component ids are only valid with computed_kind")
    _uuid_or_422(body.component_a_id, "component_a_id")
    _uuid_or_422(body.component_b_id, "component_b_id")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT status FROM qc_specifications WHERE id=$1", spec_id)
        if spec is None:
            raise HTTPException(404, "Specification not found")
        if spec["status"] not in _EDITABLE_STATUSES:
            raise HTTPException(409, f"Parameters may only change while the spec is being authored"
                                     f" ({', '.join(sorted(_EDITABLE_STATUSES))})")
        if body.computed_kind is not None:
            comps = await c.fetch(
                "SELECT id, spec_id, computed_kind FROM qc_spec_parameters WHERE id = ANY($1::uuid[])",
                [body.component_a_id, body.component_b_id])
            by_id = {str(r["id"]): r for r in comps}
            for label, cid in (("component_a_id", body.component_a_id),
                               ("component_b_id", body.component_b_id)):
                comp = by_id.get(cid)
                if comp is None or str(comp["spec_id"]) != spec_id:
                    raise HTTPException(422, f"{label} must reference a parameter of the same specification")
                if comp["computed_kind"] is not None:
                    raise HTTPException(422, f"{label} must reference a measured parameter, not a computed one")
            if body.component_a_id == body.component_b_id:
                raise HTTPException(422, "component_a_id and component_b_id must differ")
        row = await c.fetchrow(
            "INSERT INTO qc_spec_parameters(org_id, spec_id, test_name_en, test_name_mk,"
            " test_method, spec_type, lower_limit, upper_limit, unit, pharmacopoeia_ref,"
            " test_location, sorting_order, created_by, computed_kind, component_a_id, component_b_id)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16) RETURNING *",
            user["org_id"], spec_id, body.test_name_en, body.test_name_mk, body.test_method,
            body.spec_type, body.lower_limit, body.upper_limit, body.unit, body.pharmacopoeia_ref,
            body.test_location, body.sorting_order, user["id"],
            body.computed_kind, body.component_a_id, body.component_b_id)
    return _param_out(dict(row))


@router.delete("/specifications/{spec_id}/parameters/{param_id}")
async def delete_parameter(spec_id: str, param_id: str, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(spec_id, "Specification")
    _uuid_or_404(param_id, "Parameter")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT status FROM qc_specifications WHERE id=$1", spec_id)
        if spec is None:
            raise HTTPException(404, "Specification not found")
        if spec["status"] not in _EDITABLE_STATUSES:
            raise HTTPException(409, "Parameters are locked once the spec leaves authoring")
        res = await c.execute(
            "DELETE FROM qc_spec_parameters WHERE id=$1 AND spec_id=$2", param_id, spec_id)
    if res.split()[-1] == "0":
        raise HTTPException(404, "Parameter not found")
    return {"ok": True}
