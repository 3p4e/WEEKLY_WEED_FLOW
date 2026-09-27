import asyncpg
from app.db import rls
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import (ACID_FACTOR, _HOQC, _WRITERS, _dec, _uuid_or_404, _uuid_or_422,
                     mint_series_number, router)


_SPEC_STATUSES = (
    "INITIATED", "DRAFT", "QC_REVIEW", "QA_APPROVED", "NUMBERED",
    "TRAINED", "ACTIVE", "UNDER_CHANGE", "SUPERSEDED", "WITHDRAWN",
)


_THC_GRADES = ("GRADE_I", "GRADE_II", "GRADE_III", "GRADE_IV", "GRADE_V")


_COMPUTED_KINDS = ("total_thc", "total_cbd")


# The Ph. Eur. 3028 factor lives in common.ACID_FACTOR (Decimal) next to
# derived_total(), the ONE computation of a derived total — review 2026-09-27
# QC-10/QC-20 found two float copies of it here and a third path that skipped
# the computation altogether. This float alias only remains until the last
# caller has moved to derived_total(); nothing new may use it.
_ACID_FACTOR = float(ACID_FACTOR)


def _looks_acidic(*names: str | None) -> bool:
    """Heuristic: does a parameter name denote the ACID form of a cannabinoid?

    The data model carries no explicit neutral/acid flag on a spec parameter,
    so the strongest signal available is the name itself: acid forms are
    abbreviated with a trailing 'A' (THCA, CBDA, CBGA, …) or spell out
    'acid' / 'киселина'; the neutral forms (THC, CBD, Δ9-THC, …) do neither.
    Best-effort — used ONLY to catch a confidently-swapped A/B assignment
    below, never to hard-require a match, so a name the heuristic cannot
    classify is treated as non-acidic and left alone."""
    for name in names:
        if not name:
            continue
        n = name.strip().lower()
        if "acid" in n or "киселина" in n:
            return True
        compact = "".join(ch for ch in n if ch.isalnum())
        if compact.endswith("a"):
            return True
    return False


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


def _check_range(lo: float | None, hi: float | None, what: str) -> None:
    """A caller-supplied min/max (or lower/upper) pair must not be inverted.
    Only judged when BOTH bounds are present in the same request — an
    open-ended range (either side null) is never a violation."""
    if lo is not None and hi is not None and lo > hi:
        raise HTTPException(
            422, f"{what}: the lower/min bound ({lo}) must not exceed the upper/max bound ({hi})")


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
    _check_range(body.thc_acceptance_min, body.thc_acceptance_max,
                "thc_acceptance_min/thc_acceptance_max")
    async with rls(user) as c:
        # per-(org, year) register series, never the old cross-tenant sequence (QC-28)
        spec_no = await mint_series_number(c, user["org_id"], "qc_specifications", "spec_id", "PP-SPEC")
        try:
            row = await c.fetchrow(
                "INSERT INTO qc_specifications(org_id, spec_id, material_code, material_name_en,"
                " material_name_mk, version, effective_date, thc_grade, thc_acceptance_min,"
                " thc_acceptance_max, notes, created_by, updated_by)"
                " VALUES ($1, $12, $2,$3,$4,$5,$6::date,$7,$8,$9,$10,$11,$11) RETURNING *",
                user["org_id"], body.material_code, body.material_name_en, body.material_name_mk,
                body.version, body.effective_date, body.thc_grade, _dec(body.thc_acceptance_min),
                _dec(body.thc_acceptance_max), body.notes, user["id"], spec_no)
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
        cur = await c.fetchrow(
            "SELECT status, created_by, updated_by, thc_acceptance_min, thc_acceptance_max"
            " FROM qc_specifications WHERE id=$1", spec_id)
        if cur is None:
            raise HTTPException(404, "Specification not found")
        # Judged on the EFFECTIVE pair (review 2026-09-27 QC-08): a partial
        # patch of one bound used to slip past the check and store min > max.
        eff_min = patch["thc_acceptance_min"] if "thc_acceptance_min" in patch else cur["thc_acceptance_min"]
        eff_max = patch["thc_acceptance_max"] if "thc_acceptance_max" in patch else cur["thc_acceptance_max"]
        _check_range(_dec(eff_min), _dec(eff_max), "thc_acceptance_min/thc_acceptance_max")
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
            # QC_REVIEW -> QA_APPROVED is the GMP sign-off, not just another
            # lifecycle move: it requires the tighter Head-of-QC role (no
            # executives — the blanket _WRITERS gate on this endpoint is too
            # wide for a QA release decision) AND segregation of duties — the
            # approver must be a different person than whoever authored
            # (created_by) or last edited (updated_by) the spec. Mirrors
            # potency.py's approve_potency_spec (PP-QC-SPEC-001) exactly.
            if cur["status"] == "QC_REVIEW" and target == "QA_APPROVED":
                if user["role"] not in _HOQC:
                    raise HTTPException(
                        403, "Only Head of QC (ADMIN/QC_MGR/QP) may approve a specification")
                if str(user["id"]) in (str(cur["created_by"]), str(cur["updated_by"])):
                    raise HTTPException(
                        403, "The person approving a specification must be different from the"
                             " person who authored it (segregation of duties)")
                # Review 2026-09-27 QC-11: the acceptance criteria ARE the
                # parameters, so whoever authored any of them is a co-author of
                # the specification and may not approve it either.
                authored = await c.fetchval(
                    "SELECT 1 FROM qc_spec_parameters WHERE spec_id=$1 AND created_by=$2 LIMIT 1",
                    spec_id, user["id"])
                if authored:
                    raise HTTPException(
                        403, "The person approving a specification must not have authored any of"
                             " its parameters (segregation of duties)")
                # Review 2026-09-27 QC-08: the header THC window printed on the
                # CoQ must be the window the batch is graded against — the
                # computed Total THC parameter's limits. A header that names a
                # range no parameter enforces is a third grade vocabulary
                # nothing checks; it is refused at the GMP sign-off.
                await _assert_header_window_backed(c, spec_id, eff_min, eff_max)
        fields, args = [], []
        _NULLABLE = {"material_name_mk", "effective_date", "thc_grade",
                     "thc_acceptance_min", "thc_acceptance_max", "notes"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            if col == "effective_date":
                args.append(val); fields.append(f"{col}=${len(args)}::date")
            elif col in ("thc_acceptance_min", "thc_acceptance_max"):
                args.append(_dec(val)); fields.append(f"{col}=${len(args)}")
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


async def _assert_header_window_backed(c, spec_id, eff_min, eff_max) -> None:
    """409 unless the specification header's THC acceptance window (when set)
    equals the limits of its computed total_thc parameter — the parameter the
    CoQ's Total Δ9-THC line is graded by (QC-08)."""
    if eff_min is None and eff_max is None:
        return
    total = await c.fetchrow(
        "SELECT lower_limit, upper_limit FROM qc_spec_parameters"
        " WHERE spec_id=$1 AND computed_kind='total_thc'", spec_id)
    if total is None:
        raise HTTPException(
            409, "the specification header states a THC acceptance window but has no computed"
                 " Total THC parameter to enforce it — add the Ph. Eur. 3028 total_thc"
                 " parameter carrying these limits, or clear thc_acceptance_min/max")
    if _dec(eff_min) != _dec(total["lower_limit"]) or _dec(eff_max) != _dec(total["upper_limit"]):
        raise HTTPException(
            409, f"the header THC window {eff_min}–{eff_max} differs from the computed Total THC"
                 f" parameter's limits {total['lower_limit']}–{total['upper_limit']} — the CoQ grades"
                 " the batch against the parameter, so the header must state the same window")


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
    _check_range(body.lower_limit, body.upper_limit, "lower_limit/upper_limit")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT status FROM qc_specifications WHERE id=$1", spec_id)
        if spec is None:
            raise HTTPException(404, "Specification not found")
        if spec["status"] not in _EDITABLE_STATUSES:
            raise HTTPException(409, f"Parameters may only change while the spec is being authored"
                                     f" ({', '.join(sorted(_EDITABLE_STATUSES))})")
        if body.computed_kind is not None:
            comps = await c.fetch(
                "SELECT id, spec_id, computed_kind, test_name_en, test_name_mk"
                " FROM qc_spec_parameters WHERE id = ANY($1::uuid[])",
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
            # Ph. Eur. 3028 defines the derived total as neutral + 0.877 × acid,
            # so the ACID form must occupy component_b and the NEUTRAL form
            # component_a. Nothing above checks the ORDER — only that both slots
            # are filled — so a swapped assignment (acid in A, neutral in B)
            # would silently compute neutral + 0.877 × neutral, a wrong result
            # that still looks in-range. The model has no form flag, so guard
            # with the strongest signal the data carries (_looks_acidic): reject
            # only a CONFIDENTLY-swapped pair — A clearly the acid, B clearly not.
            comp_a, comp_b = by_id[body.component_a_id], by_id[body.component_b_id]
            a_acidic = _looks_acidic(comp_a["test_name_en"], comp_a["test_name_mk"])
            b_acidic = _looks_acidic(comp_b["test_name_en"], comp_b["test_name_mk"])
            if a_acidic and not b_acidic:
                raise HTTPException(
                    422, "component_a_id must be the NEUTRAL form and component_b_id the ACID form"
                         " (Ph. Eur. 3028: total = neutral + 0.877 × acid) — they appear swapped")
        row = await c.fetchrow(
            "INSERT INTO qc_spec_parameters(org_id, spec_id, test_name_en, test_name_mk,"
            " test_method, spec_type, lower_limit, upper_limit, unit, pharmacopoeia_ref,"
            " test_location, sorting_order, created_by, computed_kind, component_a_id, component_b_id)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16) RETURNING *",
            user["org_id"], spec_id, body.test_name_en, body.test_name_mk, body.test_method,
            # bound as Decimal: a float binds into `numeric` as its binary
            # expansion, and a limit of 23.4 stored as 23.3999999… then fails
            # a value of exactly 23.4 (review 2026-09-27 QC-05 / common._dec)
            body.spec_type, _dec(body.lower_limit), _dec(body.upper_limit), body.unit,
            body.pharmacopoeia_ref, body.test_location, body.sorting_order, user["id"],
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
        # component_a_id/component_b_id (the computed-total FKs) carry no
        # ON DELETE clause (default NO ACTION) — deleting a parameter another
        # parameter still cites as a component otherwise raises an uncaught
        # asyncpg.ForeignKeyViolationError -> 500. Map it to a clean 409
        # instead (same idiom as tasks.py's _FK_ERRORS handling).
        try:
            res = await c.execute(
                "DELETE FROM qc_spec_parameters WHERE id=$1 AND spec_id=$2", param_id, spec_id)
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(
                409, "parameter is used as a component of a computed total; remove the"
                     " computed parameter first.")
    if res.split()[-1] == "0":
        raise HTTPException(404, "Parameter not found")
    return {"ok": True}
