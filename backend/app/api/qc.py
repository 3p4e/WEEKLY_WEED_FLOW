"""QC LIMS — quality-control laboratory records (GMP zone).

Phase 2 native rebuild of the qc-lims-ao domain on the WWF spine. Unit 1 is the
Specification master data (this file grows per unit: samples, CoA, ...).

Access model (role gating here; org isolation via RLS as everywhere):
  read   — every role above base USER (elevated), so managers/execs/QP can
           consult specs;
  write  — QC manager (QC_MGR) owns the domain, the Qualified Person (QP)
           certifies across departments, plus executives + ADMIN.

GMP guardrails: acceptance limits are NEVER fabricated — an unknown limit is
stored NULL for a human to fill. Every table is audited by the shared
hash-chained trigger. Human ids are `PP-SPEC-YYYY-NNNN`, stamped server-side
from a Postgres sequence so the audit trail attributes the number.
"""
import base64
import hashlib
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app import docengine
from app.db import rls, users_admin_pool
from app.deps import require_role
from app.notify import emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES
from app.security import verify_password

router = APIRouter(prefix="/qc", tags=["qc"])

# QC manager owns the domain; QP certifies; execs + ADMIN org-wide.
_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "QC_MGR", "QP")
# Batch release/reject, CoA approve/release, and OOS disposition are a
# Qualified-Person decision (Annex 16) — the QP (or ADMIN as system operator)
# ONLY. Executives are business leadership, not a GMP quality role, and are
# deliberately excluded here even though they're org-wide writers elsewhere.
_QP_ROLES = (ADMIN, "QP")
# Issuing the Certificate of Quality is a QC Manager function (the QC Manager
# signs it), not an Annex-16 release decision — QP may also issue one (QP
# outranks QC_MGR on the quality side) and ADMIN as system operator.
# Issuing the COQ is a QC act: compiled and approved within QC (QCSOP 012
# §6.4) — the Qualified Person RECEIVES the approved COQ as an input to the
# separate Annex 16 release decision and does not sign or issue it (Head-of-QC
# URS, docs/URS-COQ-GAP-ANALYSIS-2026-07.md).
_COQ_ROLES = (ADMIN, "QC_MGR")

_SPEC_STATUSES = (
    "INITIATED", "DRAFT", "QC_REVIEW", "QA_APPROVED", "NUMBERED",
    "TRAINED", "ACTIVE", "UNDER_CHANGE", "SUPERSEDED", "WITHDRAWN",
)
_THC_GRADES = ("GRADE_I", "GRADE_II", "GRADE_III", "GRADE_IV", "GRADE_V")
# Ph. Eur. 3028 derived totals: total = neutral (a) + 0.877 × acid (b).
_COMPUTED_KINDS = ("total_thc", "total_cbd")
_ACID_FACTOR = 0.877

# The prototype's spec lifecycle transition map (spec_lifecycle_service.py):
# forward chain + the two allowed reversals; WITHDRAWN is reachable from any
# non-terminal state (a spec can always be abandoned). SUPERSEDED is set by the
# system when a newer version activates, not by a manual PATCH.
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
# Structure/parameters may only change while the spec is still being authored.
_EDITABLE_STATUSES = {"INITIATED", "DRAFT", "QC_REVIEW"}


def _uuid_or_404(value, what: str = "Resource") -> None:
    """A malformed {id} path segment must be a clean 404, not a 500 from asyncpg
    trying to cast it to a uuid inside the lookup query (mirrors auth._require_uuid)."""
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, f"{what} not found")


def _uuid_or_422(value, field: str) -> None:
    """A user-supplied uuid BODY field (cross-DB actor refs have no FK to catch a
    bad value) must 422 on a malformed id rather than 500 on the insert."""
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(422, f"{field} must be a valid id")


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


# ── Specifications ──────────────────────────────────────────────────────────
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
        try:
            await emit(c, user, verb="spec_created", object_type="qc_specification",
                       object_id=row["id"], recipients=[],
                       params={"spec_id": row["spec_id"], "material_code": row["material_code"]})
        except Exception:
            pass
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


# ── Spec parameters (acceptance criteria) ───────────────────────────────────
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


# ════════════════════════════════════════════════════════════════════════════
# QC LIMS U2 — sampling plans + samples (physical-sample cluster)
# ════════════════════════════════════════════════════════════════════════════
_SAMPLE_STATUSES = (
    "COLLECTED", "IN_TRANSIT", "RECEIVED", "IN_TEST", "TESTED",
    "REVIEWED", "APPROVED", "RELEASED", "REJECTED", "QUARANTINE",
)
_FREQUENCIES = ("EVERY_BATCH", "PERIODIC", "RANDOM")

# The vision's sample state machine (QC_LIMS vision doc §4). REVIEWED is the
# GxP second-person gate; QUARANTINE is the OOS branch; RELEASED/REJECTED are
# terminal. Legal transitions only — anything else is a 409.
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
# Release / reject the batch — a QP decision, gated tighter than other moves.
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
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }


# ── Sampling plans ──────────────────────────────────────────────────────────
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
            " VALUES ($1, 'PP-SPL-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_sampling_plan_id_seq')::text, 4, '0'),"
            "         $2,$3,COALESCE($4,'ROUNDUP(SQRT(N)*1.5)'),$5,$6,$7,$7) RETURNING *",
            user["org_id"], body.material_code, body.sampling_frequency, body.sample_size_formula,
            body.min_sample_size, body.max_sample_size, user["id"])
    return _plan_out(dict(row))


# ── Samples ─────────────────────────────────────────────────────────────────
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
            " VALUES ($1, 'PP-SMP-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_sample_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7::date,$8,$9,$10,$11,$12,$13::date,$14,$15,$16,$17,$17) RETURNING *",
            user["org_id"], body.batch_id, body.material_code, body.sample_type,
            body.material_name_en, body.material_name_mk, body.sampling_date, body.location,
            body.quantity, body.quantity_unit, body.retention_sample, body.sample_kind,
            body.retention_expiry, body.parent_id, body.sampling_plan_id, body.notes, user["id"])
        try:
            await emit(c, user, verb="sample_collected", object_type="qc_sample",
                       object_id=row["id"], recipients=[],
                       params={"sample_id": row["sample_id"], "batch_id": row["batch_id"]})
        except Exception:
            pass
    return _sample_out(dict(row))


@router.patch("/samples/{sample_id}")
async def update_sample(sample_id: str, body: SamplePatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(sample_id, "Sample")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_samples WHERE id=$1", sample_id)
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
        if patch.get("sample_kind") is not None and patch["sample_kind"] not in _SAMPLE_KINDS:
            raise HTTPException(422, f"sample_kind must be one of: {', '.join(_SAMPLE_KINDS)} (QCSOP 011 §6.2.1)")
        fields, args = [], []
        _NULLABLE = {"location", "quantity", "quantity_unit", "notes",
                     "sample_kind", "retention_expiry", "non_conforming_reason"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            args.append(val); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(sample_id)
        row = await c.fetchrow(
            f"UPDATE qc_samples SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
    return _sample_out(dict(row))


# ════════════════════════════════════════════════════════════════════════════
# Laboratories — accredited external labs (master data, URS Chapter 7)
# ════════════════════════════════════════════════════════════════════════════
# The structured replacement for the free-text source_institution/source_lab
# provenance strings: accreditation body/number, ISO 17025 scope (so a result
# run on a method the lab is NOT accredited for can be flagged), the quality-
# agreement reference, and the lab's decimal separator (the decimal-comma
# defence — a German lab writes 1,5 for 1.5). Reference master data, so the
# lifecycle is the simple ACTIVE/INACTIVE pair.
_LAB_STATUSES = ("ACTIVE", "INACTIVE")
_DECIMAL_SEPS = (".", ",")


class LabIn(BaseModel):
    name: str = Field(max_length=300)
    accreditation_body: str | None = Field(default=None, max_length=200)
    accreditation_number: str | None = Field(default=None, max_length=200)
    # ISO 17025 accredited scope — the method / test tokens the lab is
    # accredited to run. A result whose method is absent is flagged out of
    # scope (advisory; never fabricated, never auto-failed).
    iso17025_scope: list[str] = Field(default_factory=list, max_length=200)
    quality_agreement_ref: str | None = Field(default=None, max_length=200)
    locale: str | None = Field(default=None, max_length=20)
    decimal_separator: str = "."
    country: str | None = Field(default=None, max_length=120)
    contact: str | None = Field(default=None, max_length=400)
    notes: str | None = Field(default=None, max_length=4000)


class LabPatch(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    accreditation_body: str | None = Field(default=None, max_length=200)
    accreditation_number: str | None = Field(default=None, max_length=200)
    iso17025_scope: list[str] | None = Field(default=None, max_length=200)
    quality_agreement_ref: str | None = Field(default=None, max_length=200)
    locale: str | None = Field(default=None, max_length=20)
    decimal_separator: str | None = None
    country: str | None = Field(default=None, max_length=120)
    contact: str | None = Field(default=None, max_length=400)
    status: str | None = None                 # ACTIVE | INACTIVE
    notes: str | None = Field(default=None, max_length=4000)


def _lab_out(r: dict) -> dict:
    scope = r["iso17025_scope"]
    if isinstance(scope, str):
        import json as _json
        scope = _json.loads(scope or "[]")
    return {
        "id": str(r["id"]), "lab_code": r["lab_code"], "name": r["name"],
        "accreditation_body": r["accreditation_body"],
        "accreditation_number": r["accreditation_number"],
        "iso17025_scope": scope or [],
        "quality_agreement_ref": r["quality_agreement_ref"],
        "locale": r["locale"], "decimal_separator": r["decimal_separator"],
        "country": r["country"], "contact": r["contact"],
        "status": r["status"], "notes": r["notes"],
        "updated_at": r["updated_at"].isoformat(),
    }


def _lab_scope_set(scope) -> set:
    """Normalised set of the lab's accredited method/test tokens (empty when the
    lab declares no scope — then nothing is flagged, since we cannot judge)."""
    if isinstance(scope, str):
        import json as _json
        scope = _json.loads(scope or "[]")
    return {_norm(s) for s in (scope or []) if _norm(s)}


def _norm(s) -> str:
    return " ".join((s or "").split()).lower()


def _result_in_scope(scope_set: set, method, test_name) -> bool:
    """A result is in the lab's ISO 17025 scope when the lab declares no scope
    (unjudgeable → not flagged) OR its method / test name is an accredited
    token. Advisory only — an out-of-scope result is a quality signal, never an
    automatic OOS, and is never fabricated away."""
    if not scope_set:
        return True
    return _norm(method) in scope_set or _norm(test_name) in scope_set


async def _resolve_lab(c, org_id, lab_id):
    """422 unless the lab exists in this org; returns its row (or None if no id)."""
    if not lab_id:
        return None
    lab = await c.fetchrow("SELECT * FROM qc_laboratories WHERE id=$1", lab_id)
    if lab is None:
        raise HTTPException(422, "Unknown laboratory")
    return lab


@router.get("/laboratories")
async def list_labs(status: str | None = None, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_laboratories{where} ORDER BY name", *args)
    return [_lab_out(dict(r)) for r in rows]


@router.get("/laboratories/{lab_id}")
async def get_lab(lab_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(lab_id, "Laboratory")
    async with rls(user) as c:
        lab = await c.fetchrow("SELECT * FROM qc_laboratories WHERE id=$1", lab_id)
    if lab is None:
        raise HTTPException(404, "Laboratory not found")
    return _lab_out(dict(lab))


@router.post("/laboratories", status_code=201)
async def create_lab(body: LabIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.decimal_separator not in _DECIMAL_SEPS:
        raise HTTPException(422, "decimal_separator must be '.' or ','")
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO qc_laboratories(org_id, lab_code, name, accreditation_body,"
            " accreditation_number, iso17025_scope, quality_agreement_ref, locale,"
            " decimal_separator, country, contact, notes, created_by, updated_by)"
            " VALUES ($1, 'PP-LAB-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_lab_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12) RETURNING *",
            user["org_id"], body.name, body.accreditation_body, body.accreditation_number,
            [s for s in body.iso17025_scope if s], body.quality_agreement_ref, body.locale,
            body.decimal_separator, body.country, body.contact, body.notes, user["id"])
    return _lab_out(dict(row))


@router.patch("/laboratories/{lab_id}")
async def update_lab(lab_id: str, body: LabPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(lab_id, "Laboratory")
    patch = body.model_dump(exclude_unset=True)
    if patch.get("status") is not None and patch["status"] not in _LAB_STATUSES:
        raise HTTPException(422, f"status must be one of: {', '.join(_LAB_STATUSES)}")
    if patch.get("decimal_separator") is not None and patch["decimal_separator"] not in _DECIMAL_SEPS:
        raise HTTPException(422, "decimal_separator must be '.' or ','")
    if "iso17025_scope" in patch and patch["iso17025_scope"] is not None:
        patch["iso17025_scope"] = [s for s in patch["iso17025_scope"] if s]
    # name is NOT nullable; everything else may be cleared to null.
    _NULLABLE = {"accreditation_body", "accreditation_number", "quality_agreement_ref",
                 "locale", "country", "contact", "notes"}
    sets, args = [], []
    for col, val in patch.items():
        if val is None and col not in _NULLABLE:
            continue
        args.append(val); sets.append(f"{col}=${len(args)}")
    if not sets:
        raise HTTPException(422, "No fields to update")
    args.append(user["id"]); sets.append(f"updated_by=${len(args)}")
    sets.append("updated_at=now()")
    args.append(lab_id)
    async with rls(user) as c:
        row = await c.fetchrow(
            f"UPDATE qc_laboratories SET {', '.join(sets)} WHERE id=${len(args)} RETURNING *", *args)
    if row is None:
        raise HTTPException(404, "Laboratory not found")
    return _lab_out(dict(row))


# ════════════════════════════════════════════════════════════════════════════
# QC LIMS U3 — certificates of analysis + test results (certification cluster)
# ════════════════════════════════════════════════════════════════════════════
_COA_STATUSES = ("DRAFT", "REVIEWED", "APPROVED", "RELEASED", "SUPERSEDED")
_CERT_TYPES = ("ICOA", "ECOA", "COQ", "WATER", "OTHER")
# CoA lifecycle: author → second-person review → QP approve → release.
_COA_TRANSITIONS = {
    "DRAFT": {"REVIEWED"},
    "REVIEWED": {"APPROVED", "DRAFT"},   # kick back to DRAFT on review findings
    "APPROVED": {"RELEASED"},
    "RELEASED": set(),
    # Terminal. Reached ONLY via the revise flow (releasing a revision flips
    # its origin RELEASED→SUPERSEDED); never a direct PATCH target.
    "SUPERSEDED": set(),
}
# Approve + release the certificate — Qualified-Person decisions (Annex 16).
_COA_QP_TARGETS = {"APPROVED", "RELEASED"}
# A sample in one of these states is quarantined when a result fails.
_QUARANTINABLE = {"IN_TEST", "TESTED", "RECEIVED", "COLLECTED"}


class CoaIn(BaseModel):
    batch_id: str = Field(max_length=120)
    specification_id: str
    sample_id: str | None = None
    cert_type: str = "ICOA"
    report_date: date | None = None
    source_lab: str | None = Field(default=None, max_length=200)
    # The accredited laboratory that issued the source data (URS Chapter 7);
    # the structured replacement for the free-text source_lab, kept alongside it.
    laboratory_id: str | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CoaPatch(BaseModel):
    source_lab: str | None = Field(default=None, max_length=200)
    laboratory_id: str | None = None
    report_date: date | None = None
    # QCLB 020 §6.13 register fields — where the original is filed + the
    # retention window. Nullable; never back-filled with an invented value.
    retention_start: date | None = None
    retention_expiry: date | None = None
    archive_ref: str | None = Field(default=None, max_length=300)
    # CoQ house-template metadata (CoQ_Template_v02_VariationF meta grid). All
    # nullable — the CoQ renderer surfaces each when present, omits it when not;
    # GxP: an unknown value stays blank for a human, never fabricated.
    cultivation_batch: str | None = Field(default=None, max_length=120)
    product_code: str | None = Field(default=None, max_length=120)
    packaging: str | None = Field(default=None, max_length=200)
    packaging_date: date | None = None
    manufacture_date: date | None = None
    expiry_date: date | None = None
    retest_date: date | None = None
    botanical_type: str | None = Field(default=None, max_length=120)
    chemotype: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)
    status: str | None = None            # guarded lifecycle transition
    decision: str | None = None          # PASS | FAIL


class ResultIn(BaseModel):
    parameter_id: str | None = None
    test_name: str = Field(max_length=300)
    result_value: str | None = Field(default=None, max_length=200)
    result_numeric: float | None = None
    unit: str | None = Field(default=None, max_length=60)
    lower_limit: float | None = None
    upper_limit: float | None = None
    result_date: date | None = None
    # provenance — the source iCoA/eCoA this result was transcribed from; the
    # COQ maps every line back to its source document (unknown stays blank).
    source_document_code: str | None = Field(default=None, max_length=120)
    source_document_date: date | None = None
    source_institution: str | None = Field(default=None, max_length=200)
    # The lab's OWN stated pass/fail as printed on the source certificate —
    # captured verbatim for the reconciliation record, reference-only. Purely
    # Plant's in-house `complies` is the determination; this never feeds it
    # (QCSOP 012 §6.3.2). A disagreement is surfaced, never silently discarded.
    lab_verdict: str | None = Field(default=None, max_length=60)


def _coa_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coa_number": r["coa_number"], "batch_id": r["batch_id"],
        "specification_id": str(r["specification_id"]),
        "sample_id": str(r["sample_id"]) if r["sample_id"] else None,
        "report_date": r["report_date"].isoformat() if r["report_date"] else None,
        "status": r["status"], "decision": r["decision"], "cert_type": r["cert_type"],
        "source_lab": r["source_lab"],
        "laboratory_id": str(r["laboratory_id"]) if r.get("laboratory_id") else None,
        "analyst_id": str(r["analyst_id"]) if r["analyst_id"] else None,
        "reviewer_id": str(r["reviewer_id"]) if r["reviewer_id"] else None,
        "approver_id": str(r["approver_id"]) if r["approver_id"] else None,
        "coq_document_id": r["coq_document_id"],
        "coq_generated_at": r["coq_generated_at"].isoformat() if r["coq_generated_at"] else None,
        "supersedes_id": str(r["supersedes_id"]) if r.get("supersedes_id") else None,
        "revision_reason": r.get("revision_reason"),
        "retention_start": r["retention_start"].isoformat() if r.get("retention_start") else None,
        "retention_expiry": r["retention_expiry"].isoformat() if r.get("retention_expiry") else None,
        "archive_ref": r.get("archive_ref"),
        # CoQ house-template metadata (mig 0038) — surfaced on the certificate
        # record and the rendered Certificate of Quality.
        "cultivation_batch": r.get("cultivation_batch"),
        "product_code": r.get("product_code"),
        "packaging": r.get("packaging"),
        "packaging_date": r["packaging_date"].isoformat() if r.get("packaging_date") else None,
        "manufacture_date": r["manufacture_date"].isoformat() if r.get("manufacture_date") else None,
        "expiry_date": r["expiry_date"].isoformat() if r.get("expiry_date") else None,
        "retest_date": r["retest_date"].isoformat() if r.get("retest_date") else None,
        "botanical_type": r.get("botanical_type"),
        "chemotype": r.get("chemotype"),
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }


def _result_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "parameter_id": str(r["parameter_id"]) if r["parameter_id"] else None,
        "test_name": r["test_name"], "result_value": r["result_value"],
        "result_numeric": float(r["result_numeric"]) if r["result_numeric"] is not None else None,
        "unit": r["unit"],
        "lower_limit": float(r["lower_limit"]) if r["lower_limit"] is not None else None,
        "upper_limit": float(r["upper_limit"]) if r["upper_limit"] is not None else None,
        "complies": r["complies"], "status": r["status"],
        "analyst_id": str(r["analyst_id"]) if r["analyst_id"] else None,
        "result_date": r["result_date"].isoformat() if r["result_date"] else None,
        "source_document_code": r["source_document_code"],
        "source_document_date":
            r["source_document_date"].isoformat() if r["source_document_date"] else None,
        "source_institution": r["source_institution"],
        # Lab's stated verdict (reference) + the reconciliation flag: True only
        # when the lab's own pass/fail disagrees with our determination — a
        # signal for the reviewer, never a change to `complies`.
        "lab_verdict": r.get("lab_verdict"),
        "lab_verdict_mismatch": (
            _lab_verdict_bool(r.get("lab_verdict")) is not None and r["complies"] is not None
            and _lab_verdict_bool(r.get("lab_verdict")) != r["complies"]),
    }


def _evaluate(value: float | None, lo: float | None, hi: float | None):
    """Return (complies, status). Unknown when there's no numeric value to
    judge — GxP: we never invent a verdict for a missing measurement."""
    if value is None:
        return None, "unknown"
    ok = (lo is None or value >= lo) and (hi is None or value <= hi)
    return ok, ("pass" if ok else "fail")


# ── Certificates of analysis ────────────────────────────────────────────────
@router.get("/certificates")
async def list_coas(batch_id: str | None = None, status: str | None = None,
                    user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if batch_id:
        args.append(batch_id); clauses.append(f"batch_id=${len(args)}")
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_certificates{where} ORDER BY created_at DESC", *args)
    return [_coa_out(dict(r)) for r in rows]


@router.get("/certificates/{coa_id}")
async def get_coa(coa_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", coa_id)
        lab = await c.fetchrow("SELECT * FROM qc_laboratories WHERE id=$1",
                               coa["laboratory_id"]) if coa["laboratory_id"] else None
        sigs = await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_certificate' AND object_id=$1"
            " ORDER BY signed_at", coa_id)
        # method per cited spec parameter, for the scope check below
        pmethods = {}
        pids = [r["parameter_id"] for r in results if r["parameter_id"]]
        if pids:
            prows = await c.fetch(
                "SELECT id, test_method FROM qc_spec_parameters WHERE id = ANY($1::uuid[])", pids)
            pmethods = {str(p["id"]): p["test_method"] for p in prows}
    # ISO 17025 scope flag: when the issuing lab declares an accredited scope,
    # mark each result whose method/test is not accredited (advisory, per URS
    # Chapter 7 — surfaced for the reviewer, never an automatic OOS).
    scope = _lab_scope_set(lab["iso17025_scope"]) if lab else set()
    out_results = []
    for r in results:
        d = _result_out(dict(r))
        method = pmethods.get(str(r["parameter_id"])) if r["parameter_id"] else None
        d["in_scope"] = _result_in_scope(scope, method, r["test_name"]) if scope else None
        out_results.append(d)
    return {"coa": _coa_out(dict(coa)),
            "laboratory": _lab_out(dict(lab)) if lab else None,
            "results": out_results,
            "signatures": [_sig_out(dict(s)) for s in sigs]}


@router.post("/certificates", status_code=201)
async def create_coa(body: CoaIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.cert_type not in _CERT_TYPES:
        raise HTTPException(422, f"cert_type must be one of: {', '.join(_CERT_TYPES)}")
    _uuid_or_422(body.specification_id, "specification_id")
    _uuid_or_422(body.sample_id, "sample_id")
    _uuid_or_422(body.laboratory_id, "laboratory_id")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1", body.specification_id)
        if spec is None:
            raise HTTPException(422, "Unknown specification")
        if body.sample_id:
            s = await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", body.sample_id)
            if s is None:
                raise HTTPException(422, "Unknown sample")
        await _resolve_lab(c, user["org_id"], body.laboratory_id)
        row = await c.fetchrow(
            "INSERT INTO qc_certificates(org_id, coa_number, batch_id, specification_id, sample_id,"
            " cert_type, report_date, source_lab, laboratory_id, notes, analyst_id,"
            " created_by, updated_by)"
            " VALUES ($1, 'PP-COA-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_coa_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6::date,$7,$8,$9,$10,$10,$10) RETURNING *",
            user["org_id"], body.batch_id, body.specification_id, body.sample_id, body.cert_type,
            body.report_date, body.source_lab, body.laboratory_id, body.notes, user["id"])
    return _coa_out(dict(row))


@router.post("/certificates/{coa_id}/results", status_code=201)
async def add_result(coa_id: str, body: ResultIn, user: dict = Depends(require_role(*_WRITERS))):
    """Record a measured result. `complies` is computed from the numeric value
    vs the limits — never typed by hand. If the result FAILS and the CoA links
    a sample that is still in a testable state, the sample is quarantined (the
    OOS hook). Results may only be entered while the CoA is DRAFT."""
    _uuid_or_404(coa_id, "Certificate")
    _uuid_or_422(body.parameter_id, "parameter_id")
    async with rls(user) as c:
        coa = await c.fetchrow(
            "SELECT id, status, sample_id, specification_id FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        if coa["status"] != "DRAFT":
            raise HTTPException(409, "Results may only be entered while the CoA is DRAFT")
        lo, hi = body.lower_limit, body.upper_limit
        # A cited spec parameter must exist and belong to THIS certificate's
        # specification (an unknown or cross-spec/cross-org id must 422, never a
        # dangling FK / 500). When cited and limits weren't supplied, snapshot the
        # parameter's limits (the spec is the single source of truth).
        if body.parameter_id:
            p = await c.fetchrow(
                "SELECT spec_id, lower_limit, upper_limit, unit, computed_kind"
                " FROM qc_spec_parameters WHERE id=$1",
                body.parameter_id)
            if p is None:
                raise HTTPException(422, "Unknown spec parameter")
            if coa["specification_id"] is not None and p["spec_id"] != coa["specification_id"]:
                raise HTTPException(422, "Parameter does not belong to this certificate's specification")
            # Ph. Eur. 3028: a derived total is COMPUTED by the engine at COQ
            # time from its component results — transcribing one is forbidden.
            if p["computed_kind"] is not None:
                raise HTTPException(422, "This parameter is computed (Ph. Eur. 3028 derived total)"
                                         " — enter its component results instead")
            # Snapshot EACH side independently: a caller who supplies only one
            # limit must still inherit the spec's other bound, or a partial
            # override would silently disable it (an over-limit value passing as
            # compliant — a fabricated conformance, which GxP forbids).
            if lo is None and p["lower_limit"] is not None:
                lo = float(p["lower_limit"])
            if hi is None and p["upper_limit"] is not None:
                hi = float(p["upper_limit"])
        complies, status = _evaluate(body.result_numeric, lo, hi)
        row = await c.fetchrow(
            "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value,"
            " result_numeric, unit, lower_limit, upper_limit, complies, status, analyst_id,"
            " result_date, source_document_code, source_document_date, source_institution,"
            " lab_verdict, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$12) RETURNING *",
            user["org_id"], coa_id, body.parameter_id, body.test_name, body.result_value,
            body.result_numeric, body.unit, lo, hi, complies, status, user["id"], body.result_date,
            body.source_document_code, body.source_document_date, body.source_institution,
            body.lab_verdict)
        # OOS hook: a failing result quarantines the linked sample.
        if complies is False and coa["sample_id"]:
            smp = await c.fetchrow("SELECT id, status FROM qc_samples WHERE id=$1", coa["sample_id"])
            if smp is not None and smp["status"] in _QUARANTINABLE:
                await c.execute(
                    "UPDATE qc_samples SET status='QUARANTINE', updated_by=$1, updated_at=now() WHERE id=$2",
                    user["id"], coa["sample_id"])
                try:
                    await emit(c, user, verb="sample_quarantined", object_type="qc_sample",
                               object_id=coa["sample_id"], recipients=[],
                               params={"test_name": body.test_name})
                except Exception:
                    pass
    return _result_out(dict(row))


@router.patch("/certificates/{coa_id}")
async def update_coa(coa_id: str, body: CoaPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(coa_id, "Certificate")
    patch = body.model_dump(exclude_unset=True)
    if "decision" in patch and patch["decision"] is not None and patch["decision"] not in ("PASS", "FAIL"):
        raise HTTPException(422, "decision must be PASS or FAIL")
    if patch.get("laboratory_id") is not None:
        _uuid_or_422(patch["laboratory_id"], "laboratory_id")
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT status, analyst_id, supersedes_id FROM qc_certificates WHERE id=$1", coa_id)
        if cur is None:
            raise HTTPException(404, "Certificate not found")
        if patch.get("laboratory_id") is not None:
            await _resolve_lab(c, user["org_id"], patch["laboratory_id"])
        extra_sql, extra_args = [], []
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _COA_STATUSES:
                raise HTTPException(422, "Unknown status")
            if target == "SUPERSEDED":
                # only the revise flow retires a certificate (QCSOP 012 §6.7)
                raise HTTPException(409, "SUPERSEDED is set by releasing a revision, not directly")
            if target not in _COA_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            if target in _COA_QP_TARGETS and user["role"] not in _QP_ROLES:
                raise HTTPException(403, f"{target} is a Qualified-Person decision")
            # GxP second-person review: the reviewer must not be anyone who
            # produced the data — neither the CoA's analyst-of-record NOR any
            # analyst who entered a result on it (each qc_results row stamps its
            # own analyst_id, so checking only the certificate's would let a
            # second data-enterer sign off their own measurements).
            if target == "REVIEWED":
                entered = await c.fetchval(
                    "SELECT 1 FROM qc_results WHERE coa_id=$1 AND analyst_id=$2 LIMIT 1",
                    coa_id, user["id"])
                if entered or (cur["analyst_id"] and str(cur["analyst_id"]) == str(user["id"])):
                    raise HTTPException(403, "The reviewer must be a different person than the analyst")
                extra_args.append(user["id"]); extra_sql.append(f"reviewer_id=${'PLACEHOLDER'}")
            if target == "APPROVED":
                extra_args.append(user["id"]); extra_sql.append(f"approver_id=${'PLACEHOLDER'}")
        fields, args = [], []
        _NULLABLE = {"source_lab", "laboratory_id", "report_date", "retention_start",
                     "retention_expiry", "archive_ref", "notes", "decision",
                     "cultivation_batch", "product_code", "packaging", "packaging_date",
                     "manufacture_date", "expiry_date", "retest_date",
                     "botanical_type", "chemotype"}
        _DATE_COLS = {"report_date", "retention_start", "retention_expiry",
                      "packaging_date", "manufacture_date", "expiry_date", "retest_date"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            if col in _DATE_COLS:
                args.append(val); fields.append(f"{col}=${len(args)}::date")
            else:
                args.append(val); fields.append(f"{col}=${len(args)}")
        # splice reviewer_id/approver_id stamps with correct positional params
        for frag, val in zip(extra_sql, extra_args):
            args.append(val); fields.append(frag.replace("PLACEHOLDER", str(len(args))))
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(coa_id)
        row = await c.fetchrow(
            f"UPDATE qc_certificates SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
        # Releasing a revision retires its origin: RELEASED → SUPERSEDED in the
        # same transaction, so the register never shows two live certificates
        # for the same correction chain (QCSOP 012 §6.7). Status-guarded so a
        # replayed release can't touch an already-superseded origin.
        if patch.get("status") == "RELEASED" and cur["supersedes_id"]:
            await c.execute(
                "UPDATE qc_certificates SET status='SUPERSEDED', updated_by=$1, updated_at=now()"
                " WHERE id=$2 AND status='RELEASED'", user["id"], cur["supersedes_id"])
    return _coa_out(dict(row))


class ReviseIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


@router.post("/certificates/{coa_id}/revise", status_code=201)
async def revise_certificate(coa_id: str, body: ReviseIn,
                             user: dict = Depends(require_role(*_WRITERS))):
    """QCSOP 012 §6.7: an approved certificate is immutable — a correction is a
    NEW certificate with a NEW number, carrying "Supersedes [n] — reason".
    The revision starts as a DRAFT copy (results included, so the compiler
    corrects from the current state); the original stays RELEASED until the
    revision is itself RELEASED, at which point it flips to SUPERSEDED."""
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if cur is None:
            raise HTTPException(404, "Certificate not found")
        if cur["status"] != "RELEASED":
            raise HTTPException(409, f"Only a RELEASED certificate is revised — this one is"
                                     f" {cur['status']} (edit or re-review it directly)")
        open_rev = await c.fetchval(
            "SELECT coa_number FROM qc_certificates WHERE supersedes_id=$1"
            " AND status <> 'SUPERSEDED' LIMIT 1", coa_id)
        if open_rev:
            raise HTTPException(409, f"A revision already exists ({open_rev})")
        row = await c.fetchrow(
            "INSERT INTO qc_certificates(org_id, coa_number, batch_id, specification_id,"
            " sample_id, cert_type, report_date, source_lab, laboratory_id, notes, analyst_id,"
            " supersedes_id, revision_reason, created_by, updated_by)"
            " VALUES ($1, 'PP-COA-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_coa_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$10,$10) RETURNING *",
            user["org_id"], cur["batch_id"], cur["specification_id"], cur["sample_id"],
            cur["cert_type"], cur["report_date"], cur["source_lab"], cur["laboratory_id"],
            cur["notes"], user["id"], coa_id, body.reason)
        # carry the result set forward so the correction edits the real state
        await c.execute(
            "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value,"
            " result_numeric, unit, lower_limit, upper_limit, complies, status, analyst_id,"
            " result_date, source_document_code, source_document_date, source_institution,"
            " created_by)"
            " SELECT org_id, $1, parameter_id, test_name, result_value, result_numeric,"
            " unit, lower_limit, upper_limit, complies, status, analyst_id, result_date,"
            " source_document_code, source_document_date, source_institution, $2"
            " FROM qc_results WHERE coa_id=$3", row["id"], user["id"], coa_id)
    return _coa_out(dict(row))


# ── Certificate of Quality (COQ) generation — Phase 3 U1 ────────────────────
# A COQ is a RELEASED qc_certificate rendered to a bilingual house-style .docx
# by the DocEngine (POST /build → pp_verify RESULT: PASS gate). TWO gates apply:
# a DATA gate here — every result must comply; a FAIL or an unmeasured value
# blocks, so a conformant COQ is never fabricated for a non-conforming or
# incomplete batch (GxP) — and the DocEngine's own house-style PASS gate.
# Issuing a COQ is a Qualified-Person act.
def _coq_client(timeout: float = 20.0):
    """The seam the COQ tests monkeypatch (mirrors qms.py's _de_client)."""
    return docengine.de_client(timeout)


def _coq_cell(s) -> str:
    """Sanitize a value for a DocEngine table/heading cell — strip the grammar
    separators (| heading split, ||| column split, ~~ MK/EN split)."""
    if s is None:
        return ""
    return str(s).replace("|||", "/").replace("~~", "-").replace("|", "/")


def _coq_manifest(coa: dict, spec: dict, params_by_id: dict, results: list,
                  lab: dict | None) -> list:
    """WHO TRS 1010 (model certificate of analysis) + Annex 16 / QCSOP 012 §9.3
    mandatory-CONTENT manifest: the required elements a Certificate of Quality
    must carry before it can be issued — a content-completeness gate layered on
    top of the house-style (pp_verify) and GxP data/completeness gates. Returns
    the list of absent mandatory elements (empty = ready to issue). Deterministic;
    fabricates nothing — a missing element is reported, never invented."""
    missing = []
    spec = spec or {}
    if not (spec.get("material_name_en") or spec.get("material_name_mk") or spec.get("material_code")):
        missing.append("material / product name")
    if not spec.get("spec_id"):
        missing.append("specification reference")
    if not coa.get("batch_id"):
        missing.append("batch number")
    if not coa.get("report_date"):
        missing.append("report date")
    # A COQ asserts conformance; the disposition of record must say so.
    if coa.get("decision") != "PASS":
        missing.append("recorded PASS disposition")
    if not coa.get("approver_id"):
        missing.append("authorised approver")
    # WHO: an externally-sourced certificate must identify the testing lab.
    if coa.get("cert_type") == "ECOA" and not (lab or coa.get("source_lab")):
        missing.append("testing laboratory")
    # WHO: every reported test needs an analytical-method reference (a computed
    # total already cites its monograph in the source column).
    no_method = []
    for r in results:
        if str(r.get("source_document_code") or "").startswith("Пресметано"):
            continue
        p = params_by_id.get(str(r.get("parameter_id"))) or {}
        if not (p.get("test_method") or p.get("pharmacopoeia_ref")):
            nm = r.get("test_name") or "?"
            if nm not in no_method:
                no_method.append(nm)
    if no_method:
        missing.append("analytical method for: " + ", ".join(no_method[:5]))
    return missing


# CoQ house constants (CoQ_Template_v02_VariationF) — the manufacturer identity
# and the internal-QC lab wording are fixed facility facts, not per-certificate
# data. House disposition wording is 'MK GMP Certified Facility' (never EU GMP).
_COQ_MANUFACTURER = ("Purely Plant DOOEL · Industriska ulica 9, br. 9, s. Kojlija 1043"
                     " · Petrovec-Skopje, North Macedonia")
# Cannabis-flower certificate types — only these carry the Cannabis flos species
# line + Ph. Eur. monograph 3028 conformance. A WATER/OTHER CoQ must not assert a
# botanical identity or monograph it doesn't have (GxP: never fabricated).
_COQ_CANNABIS_CERTS = {"ICOA", "ECOA", "COQ"}
_GRADE_LABEL = {"GRADE_I": "Grade I", "GRADE_II": "Grade II", "GRADE_III": "Grade III",
                "GRADE_IV": "Grade IV", "GRADE_V": "Grade V"}
# maps a captured e-signature meaning to its CoQ signing-role label (mk~~en)
_COQ_SIG_ROLE = {
    "AUTHORED": "Изготвил~~Prepared by", "REVIEWED": "Прегледал~~Reviewed by",
    "APPROVED": "Одобрил~~Approved by", "RELEASED": "Пуштил~~Released by",
    "VERIFIED": "Верификувал~~Verified by", "COQ_ISSUED": "Издал CoQ~~CoQ issued by",
}


def _d(x) -> str:
    """Render a date/None as an ISO string (empty for None)."""
    return x.isoformat() if hasattr(x, "isoformat") else (str(x) if x else "")


def _coq_potency(spec: dict) -> str:
    """The cannabinoid strength line from the specification's THC acceptance
    window + grade. Empty when the spec carries neither — never invented."""
    parts = []
    lo, hi = spec.get("thc_acceptance_min"), spec.get("thc_acceptance_max")
    if lo is not None and hi is not None:
        parts.append(f"THC {lo}–{hi}%")
    elif lo is not None:
        parts.append(f"THC ≥ {lo}%")
    elif hi is not None:
        parts.append(f"THC ≤ {hi}%")
    g = _GRADE_LABEL.get(spec.get("thc_grade") or "")
    if g:
        parts.append(g)
    return " · ".join(parts)


def _coq_sources(results: list, lab: dict | None):
    """Derive the §02 Laboratory & CoA cross-reference from the results' cited
    provenance, and the per-row source letter for §01. Each distinct external
    source (institution + document code + issue date) gets a letter A, B, C…;
    results measured in-house carry 'Q'; a Ph. Eur. derived total carries '∑'.
    Derivation only — a source with no cited document simply shows blanks; no
    lab, accreditation, code, or date is ever fabricated.

    Returns (letters, crossref_rows, has_internal, has_computed)."""
    lab_name = ((lab or {}).get("name") or "").strip()
    lab_accr = " · ".join(x for x in ((lab or {}).get("accreditation_body"),
                                      (lab or {}).get("accreditation_number")) if x)

    def classify(r):
        code = str(r.get("source_document_code") or "").strip()
        inst = str(r.get("source_institution") or "").strip()
        if code.startswith("Пресметано") or code.startswith("Computed"):
            return "computed", None
        if not inst and not code:
            return "internal", ("Q",)
        return "external", ("E", inst, code, _d(r.get("source_document_date")))

    ext_order, groups, has_internal = [], {}, False
    for idx, r in enumerate(results):
        kind, key = classify(r)
        if kind == "computed":
            continue
        if kind == "internal":
            has_internal = True
        if key not in groups:
            groups[key] = {"kind": kind, "params": [], "r": r}
            if kind == "external":
                ext_order.append(key)
        groups[key]["params"].append(idx + 1)          # 1-based §01 row №

    keyletter = {}
    if has_internal:
        keyletter[("Q",)] = "Q"
    for i, k in enumerate(ext_order):
        keyletter[k] = chr(ord("A") + i)               # A, B, C…

    letters = []
    for r in results:
        kind, key = classify(r)
        letters.append("∑" if kind == "computed" else keyletter.get(key, "—"))

    def pstr(ps):
        return ", ".join(str(p) for p in ps)

    crossref = []
    if has_internal:
        # the only row whose lab/accreditation carry a PRE-BUILT bilingual mk~~en
        # pair — flagged raw so the renderer passes it through un-sanitized. Every
        # external row's lab/accreditation is user free-text and must be sanitized.
        crossref.append({
            "letter": "Q", "raw": True,
            "lab": "Внатрешна QC лабораторија, Purely Plant~~Purely Plant in-house QC Laboratory",
            "accreditation": "МК ГМП · внатрешна контрола~~MK GMP · internal release control",
            "code": "—", "issued": "—", "params": pstr(groups[("Q",)]["params"]),
        })
    for k in ext_order:
        g = groups[k]
        r = g["r"]
        inst = str(r.get("source_institution") or "").strip() or "—"
        # attach the certificate's structured ISO-17025 credential only when this
        # source's name matches the certificate's registered lab (best-effort).
        accr = lab_accr if (lab_name and inst.lower() == lab_name.lower()) else "—"
        crossref.append({
            "letter": keyletter[k], "lab": inst, "accreditation": accr,
            "code": str(r.get("source_document_code") or "—"),
            "issued": _d(r.get("source_document_date")) or "—",
            "params": pstr(g["params"]),
        })
    return letters, crossref, has_internal, any(x == "∑" for x in letters)


def _coq_markdown(coa: dict, spec: dict, params_by_id: dict, results: list,
                  lab: dict | None = None, scope_note: str | None = None,
                  sigs: list | None = None, signer_names: dict | None = None) -> str:
    """Assemble the Certificate of Quality as DocEngine bilingual Markdown in the
    approved house layout (CoQ_Template_v02_VariationF): product/identity meta
    grid → §01 Analytical Results (№ · parameter · method · acceptance · result ·
    source-letter) → §02 Laboratory & CoA cross-reference (each source traced
    once) → batch disposition → QC compliance statement → e-signatures. The
    doctype is FORM, so the DocEngine annex renderer supplies the logo header,
    navy #2B547E section banners, and the 'MK GMP Certified Facility' footer.
    GxP: no value is fabricated — an unknown field is omitted, an unknown result
    renders '—'; the caller's data / completeness / manifest gates run first."""
    c = _coq_cell
    material = " / ".join(x for x in (spec.get("material_name_mk"),
                                      spec.get("material_name_en") or spec.get("material_code")) if x)
    decision = coa.get("decision") or ""
    v_mk = "СЕРИЈАТА ЗАДОВОЛУВА — Одобрено за пуштање" if decision == "PASS" \
        else "СЕРИЈАТА НЕ ЗАДОВОЛУВА"
    v_en = "Conforms to Specification — Approved for Release" if decision == "PASS" \
        else "This batch does NOT conform"
    head = ("<!--HEADERDATA\n"
            "doctype: FORM\n"
            f"code: {c(coa['coa_number'])}\n"
            "version: 01\n"
            "mk_title: Сертификат за квалитет\n"
            "en_title: Certificate of Quality\n"
            "-->\n\n")
    title = "# Сертификат за квалитет|Certificate of Quality\n\n"

    # ── product / identity meta grid ────────────────────────────────────────
    cannabis = coa.get("cert_type") in _COQ_CANNABIS_CERTS
    bot = [x for x in (coa.get("botanical_type"),) if x]
    if cannabis:
        bot += ["Flos Cannabis Sativae L.", "Ph. Eur. mon. 3028 (Cannabis flos)"]
    bot += [x for x in (coa.get("chemotype"),) if x]
    spec_ref = spec.get("spec_id") or ""
    if spec.get("version"):
        spec_ref = f"{spec_ref} · v{spec['version']}".strip(" ·")
    if lab:
        lab_line = lab.get("name") or ""
        accr = " · ".join(x for x in (lab.get("accreditation_body"),
                                      lab.get("accreditation_number")) if x)
        lab_line = f"{lab_line} ({accr})" if accr else lab_line
    else:
        lab_line = coa.get("source_lab") or ""
    grid_rows = [
        ("№ на сертификат", "Certificate №", coa.get("coa_number"), True),
        ("Материјал", "Material", material, True),
        ("Ботаничко потекло", "Botanical origin", " · ".join(bot), False),
        ("Јачина", "Potency", _coq_potency(spec), False),
        ("Производна серија", "Production batch", coa.get("batch_id"), True),
        ("Серија на одгледување", "Cultivation batch", coa.get("cultivation_batch"), False),
        ("Код на производ", "Product code", coa.get("product_code"), False),
        ("Спецификација", "Specification", spec_ref, True),
        ("Пакување", "Packaging", coa.get("packaging"), False),
        ("Датум на пакување", "Packaging date", _d(coa.get("packaging_date")), False),
        ("Датум на производство", "Mfg. date", _d(coa.get("manufacture_date")), False),
        ("Рок на употреба", "Expiry date", _d(coa.get("expiry_date")), False),
        ("Датум на ретест", "Retest date", _d(coa.get("retest_date")), False),
        ("Датум на извештај", "Report date", _d(coa.get("report_date")), True),
        ("Лабораторија", "Laboratory", lab_line, False),
        ("Производител", "Manufacturer", _COQ_MANUFACTURER, True),
    ]
    grid = "[[FORM:grid]]\n"
    for mk, en, val, required in grid_rows:
        sval = (str(val).strip() if val is not None else "")
        if sval or required:
            grid += f"{mk}~~{en} ||| {c(sval) or '—'}\n"
    grid += "[[/FORM]]\n\n"

    # ── §01 analytical results (№ · parameter · method · acceptance · result · src) ──
    letters, crossref, has_internal, has_computed = _coq_sources(results, lab)
    s01 = ("# 01 Аналитички резултати|01 Analytical Results\n\n"
           "[[TABLE:data]]\n"
           "№~~№ ||| Параметар~~Parameter ||| Метод~~Method ||| "
           "Спецификација~~Acceptance ||| Резултат~~Result ||| Извор~~Src\n")
    for i, r in enumerate(results):
        p = params_by_id.get(str(r.get("parameter_id"))) or {}
        method = p.get("test_method") or p.get("pharmacopoeia_ref") or ""
        lo, hi = r.get("lower_limit"), r.get("upper_limit")
        limits = "—" if lo is None and hi is None else \
            f"{'' if lo is None else lo} … {'' if hi is None else hi}"
        val = r.get("result_value") or ("" if r.get("result_numeric") is None
                                        else str(r["result_numeric"]))
        val = (f"{val} {r.get('unit') or ''}").strip() or "—"
        s01 += (f"{i + 1} ||| {c(r.get('test_name'))} ||| {c(method)} ||| "
                f"{c(limits)} ||| {c(val)} ||| {letters[i]}\n")
    s01 += "[[/TABLE]]\n\n"
    if has_computed:
        s01 += ("_∑ — Вкупен THC/CBD е пресметан како збир на киселинската и"
                " декарбоксилираната форма (Ph. Eur. 2.2.29)._"
                "|||_∑ — Total THC/CBD is computed as the sum of the acidic and"
                " decarboxylated forms (Ph. Eur. 2.2.29)._\n\n")
    if has_internal:
        s01 += ("_Q — Странска материја и макроскопска идентификација ги изведува"
                " внатрешната QC служба на Purely Plant пред земање мостра за"
                " финалното QC пуштање (QCSOP-005 v.02)._"
                "|||_Q — Foreign Matter and Macroscopic Identification are performed"
                " by the in-house Purely Plant QC Department prior to sampling for"
                " final QC release testing (QCSOP-005 v.02)._\n\n")

    # ── §02 laboratory & CoA cross-reference (each source traced once) ───────
    s02 = ("# 02 Лаборатории и вкрстена референца на CoA|"
           "02 Laboratory & Certificate of Analysis Cross-Reference\n\n"
           "[[TABLE:data]]\n"
           "Извор~~Src ||| Лабораторија~~Laboratory ||| Акредитација~~Accreditation ||| "
           "Код на CoA~~CoA code ||| Издадено~~Issued ||| Параметри №~~Params №\n")
    for x in crossref:
        # ONLY the flagged internal-QC row carries a pre-built mk~~en pair; every
        # external value is user free-text and is sanitized (a raw ||| / ~~ / | in
        # a lab name must never inject a column or fabricate a bilingual split).
        lab_cell = x["lab"] if x.get("raw") else c(x["lab"])
        accr_cell = x["accreditation"] if x.get("raw") else c(x["accreditation"])
        s02 += (f"{x['letter']} ||| {lab_cell} ||| {accr_cell} ||| "
                f"{c(x['code'])} ||| {c(x['issued'])} ||| {c(x['params'])}\n")
    s02 += "[[/TABLE]]\n\n"

    # ── disposition + QC compliance statement ───────────────────────────────
    verdict = (f"**Севкупна диспозиција на серијата: {v_mk}.**"
               f"|||**Overall Batch Disposition: {v_en}.**\n\n")
    # the Ph. Eur. 3028 monograph clause is asserted only for cannabis-flower
    # certificates (a water/other CoQ conforms to its own spec, not to 3028).
    mono_mk = " и со Ph. Eur. монографија 3028" if cannabis else ""
    mono_en = " and Ph. Eur. Monograph 3028" if cannabis else ""
    comp = ("**Изјава за усогласеност на QC.** Оваа серија е произведена, спакувана и"
            " тестирана во согласност со одобрението за ставање на пазар и МК ГМП"
            " прописите на Република Северна Македонија (МАЛМЕД). Сите аналитички"
            " резултати од внатрешната QC служба и од надворешни ISO/IEC 17025"
            " акредитирани лаборатории се усогласени со критериумите за прифаќање"
            f"{mono_mk}."
            "|||**QC Compliance Statement.** This batch was manufactured, packaged and"
            " tested in compliance with the Marketing Authorisation and MK GMP"
            " regulations of the Republic of North Macedonia (MALMED). All analytical"
            " results from the in-house QC Department and from outsourced ISO/IEC 17025"
            f" accredited laboratories conform to the acceptance criteria{mono_en}.\n\n")
    note = (f"_{scope_note}_\n\n") if scope_note else ""

    # ── e-signatures (Annex 11) ─────────────────────────────────────────────
    sig = "# Потписи|Signatures\n\n"
    sig_rows = []
    for s in (sigs or []):
        role = _COQ_SIG_ROLE.get(s.get("meaning"), s.get("meaning") or "—")
        sig_rows.append((role, s.get("signer_name") or "—", s.get("signer_role") or "—",
                         (s.get("signed_at") or "")[:10] or "—"))
    if not sig_rows and signer_names:
        # no captured e-signatures — fall back to the certificate's roles of
        # record (name resolved; the exact per-role date isn't stored → '—').
        for label, key in (("Изготвил~~Prepared by", "analyst"),
                           ("Прегледал~~Reviewed by", "reviewer"),
                           ("Одобрил~~Approved by", "approver")):
            nm = signer_names.get(key)
            if nm:
                sig_rows.append((label, nm, "—", "—"))
    if sig_rows:
        sig += ("[[TABLE:data]]\n"
                "Улога~~Role ||| Потписник~~Signatory ||| Функција~~Function ||| Датум~~Date\n")
        for role, name, fn, dt in sig_rows:
            sig += f"{role} ||| {c(name)} ||| {c(fn)} ||| {c(dt)}\n"
        sig += "[[/TABLE]]\n\n"
    else:
        sig += ("_Потпишано и пуштено во GrowFlow (Annex 11 ревизиона трага)._"
                "|||_Signed and released in GrowFlow (Annex 11 audit trail)._\n\n")

    footer = "МК ГМП сертифицирано постројение|||MK GMP Certified Facility\n"
    return head + title + grid + s01 + s02 + verdict + comp + note + sig + footer


@router.post("/certificates/{coa_id}/coq", status_code=201)
async def generate_coq(coa_id: str, user: dict = Depends(require_role(*_COQ_ROLES))):
    """Render a Certificate of Quality (.docx) from a RELEASED certificate via
    the DocEngine's PASS-gated formatter. Data gate: every result must comply
    (a FAIL or unmeasured result blocks). Issuing the COQ is a QC Manager
    function (QP may also issue one)."""
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        if coa["status"] != "RELEASED":
            raise HTTPException(409, "A COQ is issued only from a RELEASED certificate")
        # QCSOP 012 §6.4.1/§6.6 (URS gate): no COQ for a batch with an open OOS
        # investigation — the COQ is compiled only on the investigation-
        # confirmed result set. Explicit, logged reason; never a silent pass.
        open_oos = await c.fetchval(
            "SELECT count(*) FROM qc_oos_records WHERE batch_id=$1 AND status <> 'CLOSED'",
            coa["batch_id"])
        if open_oos:
            raise HTTPException(
                409, f"{open_oos} open OOS investigation(s) on batch {coa['batch_id']}"
                     " — a COQ cannot be issued until the investigation is closed"
                     " (QCSOP 012 §6.4.1)")
        spec = await c.fetchrow("SELECT * FROM qc_specifications WHERE id=$1",
                                coa["specification_id"])
        params = await c.fetch(
            "SELECT * FROM qc_spec_parameters WHERE spec_id=$1", coa["specification_id"])
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", coa_id)
        lab = await c.fetchrow("SELECT * FROM qc_laboratories WHERE id=$1",
                               coa["laboratory_id"]) if coa["laboratory_id"] else None
        # Annex 11 e-signatures captured on this certificate — rendered in the
        # CoQ signature block (name · function · meaning · date).
        sigs = await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_certificate' AND object_id=$1"
            " ORDER BY signed_at", coa_id)
    results = [dict(r) for r in results]
    sigs = [_sig_out(dict(s)) for s in sigs]
    # Resolve the certificate's roles-of-record (analyst / reviewer / approver)
    # to names, so the signature block has a truthful fallback when no explicit
    # e-signature was captured. Names live in the separate users DB.
    signer_names = {}
    _role_ids = {k: coa.get(f"{k}_id") for k in ("analyst", "reviewer", "approver")}
    _uids = [str(v) for v in _role_ids.values() if v]
    if _uids:
        prows = await users_admin_pool().fetch(
            "SELECT id, full_name FROM profiles WHERE id = ANY($1::uuid[]) AND is_deleted=false",
            _uids)
        _by_id = {str(p["id"]): p["full_name"] for p in prows}
        signer_names = {k: _by_id.get(str(v)) for k, v in _role_ids.items() if v and _by_id.get(str(v))}
    if not results:
        raise HTTPException(409, "The certificate has no results to certify")
    # Ph. Eur. 3028 derived totals: a computed parameter's value is derived HERE
    # from its two component results (total = neutral + 0.877 × acid) — never
    # transcribed. The synthetic row joins the same comply/completeness gates
    # below and renders on the COQ marked as computed. A missing component
    # simply leaves the total uncovered, so the completeness gate names it.
    by_param = {str(r["parameter_id"]): r for r in results if r["parameter_id"]}
    for p in params:
        if not p["computed_kind"] or str(p["id"]) in by_param:
            continue
        ra = by_param.get(str(p["component_a_id"])) if p["component_a_id"] else None
        rb = by_param.get(str(p["component_b_id"])) if p["component_b_id"] else None
        if not (ra and rb and ra["result_numeric"] is not None and rb["result_numeric"] is not None):
            continue
        val = round(float(ra["result_numeric"]) + _ACID_FACTOR * float(rb["result_numeric"]), 2)
        lo = float(p["lower_limit"]) if p["lower_limit"] is not None else None
        hi = float(p["upper_limit"]) if p["upper_limit"] is not None else None
        complies, _st = _evaluate(val, lo, hi)
        results.append({
            "parameter_id": p["id"], "test_name": p["test_name_en"] or p["test_name_mk"],
            "result_value": None, "result_numeric": val, "unit": p["unit"],
            "lower_limit": lo, "upper_limit": hi, "complies": complies,
            "source_document_code": "Пресметано / Computed — Ph. Eur. 3028",
            "source_institution": None,
        })
    # GxP data gate: never issue a conformant COQ over a FAIL or an unmeasured
    # (complies is None → 'unknown') result.
    unmet = [r for r in results if r["complies"] is not True]
    if unmet:
        raise HTTPException(
            409, f"{len(unmet)} result(s) do not comply or are unmeasured — cannot certify")
    # GxP completeness gate (COQ_GEN guard parity): every parameter of the
    # certificate's specification must be covered by a result — passing the
    # results-comply gate alone would let a COQ certify a partially-tested
    # batch (spec says 5 tests, only 3 entered, all 3 pass → certified).
    covered = {str(r["parameter_id"]) for r in results if r["parameter_id"]}
    missing = [p for p in params if str(p["id"]) not in covered]
    if missing:
        names = ", ".join((p["test_name_en"] or p["test_name_mk"] or "?") for p in missing[:5])
        raise HTTPException(
            409, f"{len(missing)} specification parameter(s) have no result ({names}"
                 f"{'…' if len(missing) > 5 else ''}) — batch is not fully tested")
    params_by_id = {str(p["id"]): dict(p) for p in params}
    # WHO TRS 1010 / Annex 16 §9.3 mandatory-content gate: refuse to issue a
    # certificate missing a required content element (never silently emit an
    # incomplete GMP record).
    manifest_missing = _coq_manifest(dict(coa), dict(spec) if spec else {},
                                     params_by_id, results, lab)
    if manifest_missing:
        raise HTTPException(
            409, "Certificate is missing WHO/Annex-16 mandatory content: "
                 + "; ".join(manifest_missing))
    # ISO 17025 scope advisory (URS Chapter 7): a result whose method is outside
    # the issuing lab's accredited scope is a quality signal for the reviewer.
    # Non-blocking — it is surfaced as a COQ footnote and in the response, never
    # an automatic OOS (that would fabricate a verdict the data doesn't support).
    scope = _lab_scope_set(lab["iso17025_scope"]) if lab else set()
    out_of_scope = []
    if scope:
        for r in results:
            p = params_by_id.get(str(r.get("parameter_id"))) or {}
            if not _result_in_scope(scope, p.get("test_method"), r.get("test_name")):
                out_of_scope.append(r.get("test_name") or "?")
    scope_note = None
    if out_of_scope:
        names = ", ".join(out_of_scope[:5])
        scope_note = (f"Тестови надвор од ISO 17025 опсегот на лабораторијата: {names}"
                      f"|||Tests outside the laboratory's ISO 17025 scope: {names}")
    md = _coq_markdown(dict(coa), dict(spec) if spec else {}, params_by_id, results,
                       lab=dict(lab) if lab else None, scope_note=scope_note,
                       sigs=sigs, signer_names=signer_names)
    # DocEngine build (house-style PASS gate). A pp_verify FAIL surfaces as 422.
    build = (await docengine.de_forward(
        "POST", "/build",
        {"markdown": md, "out_name": coa["coa_number"],
         "meta": {"code": coa["coa_number"], "title_mk": "Сертификат за квалитет",
                  "title_en": "Certificate of Quality", "version": "01"}},
        timeout=120.0, client_factory=_coq_client)).json()
    doc_id = build.get("document_id")
    async with rls(user) as c:
        # Re-assert RELEASED when stamping the artifact — the certificate could
        # have transitioned during the (up-to-120s) DocEngine build (TOCTOU).
        stamped = await c.fetchrow(
            "UPDATE qc_certificates SET coq_document_id=$1, coq_generated_at=now(),"
            " updated_by=$2, updated_at=now() WHERE id=$3 AND status='RELEASED' RETURNING id",
            doc_id, user["id"], coa_id)
        if stamped is None:
            raise HTTPException(409, "Certificate is no longer RELEASED — COQ not recorded")
        try:
            await emit(c, user, verb="coq_generated", object_type="qc_certificate",
                       object_id=coa_id, recipients=[],
                       params={"coa_number": coa["coa_number"], "document_id": doc_id})
        except Exception:
            pass
    return {"coa_number": coa["coa_number"], "document_id": doc_id,
            "verify": build.get("verify"), "bytes": build.get("bytes"),
            "out_of_scope": out_of_scope}


# ── Certificate register (QCLB 020 §6.13) ───────────────────────────────────
# A read layer over qc_certificates — no new table. Serves the §6.13 canned
# queries (by quarter / type / lab; pending; OOS-linked; end-of-retention) with
# each row enriched by its OOS + supersession cross-references and retention
# window, plus a numbering-gap data-integrity report. The register year is the
# YYYY embedded in the certificate number (PP-COA-YYYY-NNNN) — the authoritative
# issue year, independent of an editable report_date.
_RETENTION_MODES = ("expiring", "expired")


@router.get("/register")
async def certificate_register(
        year: int | None = None, quarter: int | None = None,
        cert_type: str | None = None, laboratory_id: str | None = None,
        pending: bool = False, oos_linked: bool = False,
        retention: str | None = None, within_days: int = 90,
        user: dict = Depends(require_role(*ELEVATED_ROLES))):
    if cert_type is not None and cert_type not in _CERT_TYPES:
        raise HTTPException(422, f"cert_type must be one of: {', '.join(_CERT_TYPES)}")
    if retention is not None and retention not in _RETENTION_MODES:
        raise HTTPException(422, f"retention must be one of: {', '.join(_RETENTION_MODES)}")
    if quarter is not None and quarter not in (1, 2, 3, 4):
        raise HTTPException(422, "quarter must be 1–4")
    _uuid_or_422(laboratory_id, "laboratory_id")
    within_days = max(0, min(within_days, 3650))
    clauses, args = [], []
    if year is not None:
        args.append(str(year)); clauses.append(f"split_part(coa_number, '-', 3) = ${len(args)}")
    if quarter is not None:
        args.append(quarter)
        clauses.append(f"report_date IS NOT NULL AND extract(quarter FROM report_date) = ${len(args)}")
    if cert_type is not None:
        args.append(cert_type); clauses.append(f"cert_type = ${len(args)}")
    if laboratory_id is not None:
        args.append(laboratory_id); clauses.append(f"laboratory_id = ${len(args)}")
    if pending:
        clauses.append("status NOT IN ('RELEASED', 'SUPERSEDED')")
    if oos_linked:
        clauses.append("EXISTS (SELECT 1 FROM qc_oos_records o WHERE o.batch_id = qc_certificates.batch_id)")
    if retention == "expired":
        clauses.append("retention_expiry IS NOT NULL AND retention_expiry < CURRENT_DATE")
    elif retention == "expiring":
        args.append(within_days)
        clauses.append(f"retention_expiry IS NOT NULL AND retention_expiry >= CURRENT_DATE"
                       f" AND retention_expiry <= CURRENT_DATE + ${len(args)}::int")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            f"SELECT * FROM qc_certificates{where} ORDER BY coa_number DESC", *args)
        rows = [dict(r) for r in rows]
        ids = [r["id"] for r in rows]
        batches = list({r["batch_id"] for r in rows if r["batch_id"]})
        lab_ids = list({r["laboratory_id"] for r in rows if r["laboratory_id"]})
        # bulk enrich (avoid N+1): open-OOS per batch, superseded-by per id, lab names
        oos_open = {}
        if batches:
            for o in await c.fetch(
                    "SELECT batch_id, count(*) n FROM qc_oos_records"
                    " WHERE batch_id = ANY($1) AND status <> 'CLOSED' GROUP BY batch_id", batches):
                oos_open[o["batch_id"]] = o["n"]
        superseded_by = {}
        if ids:
            for s in await c.fetch(
                    "SELECT supersedes_id, coa_number FROM qc_certificates"
                    " WHERE supersedes_id = ANY($1) AND status IN ('RELEASED', 'SUPERSEDED')", ids):
                superseded_by[str(s["supersedes_id"])] = s["coa_number"]
        lab_names = {}
        if lab_ids:
            for l in await c.fetch(
                    "SELECT id, name FROM qc_laboratories WHERE id = ANY($1)", lab_ids):
                lab_names[str(l["id"])] = l["name"]
    out = []
    for r in rows:
        out.append({
            "id": str(r["id"]), "coa_number": r["coa_number"], "batch_id": r["batch_id"],
            "cert_type": r["cert_type"], "status": r["status"], "decision": r["decision"],
            "report_date": r["report_date"].isoformat() if r["report_date"] else None,
            "laboratory": lab_names.get(str(r["laboratory_id"])) if r["laboratory_id"] else None,
            "retention_start": r["retention_start"].isoformat() if r["retention_start"] else None,
            "retention_expiry": r["retention_expiry"].isoformat() if r["retention_expiry"] else None,
            "archive_ref": r["archive_ref"],
            "supersedes_id": str(r["supersedes_id"]) if r["supersedes_id"] else None,
            "superseded_by": superseded_by.get(str(r["id"])),
            "open_oos": oos_open.get(r["batch_id"], 0),
            "coq_document_id": r["coq_document_id"],
        })
    return out


@router.get("/register/gaps")
async def register_numbering_gaps(year: int, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Numbering-gap data-integrity report (§6.13): within a year's issued
    PP-COA-YYYY-NNNN range, which numbers are absent. A gap is a flag to
    investigate against the archive — NOT proof of a missing record: the
    PP-COA sequence is shared across tenants on this database, so a gap may
    simply be a certificate issued to another organisation (RLS hides it)."""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT coa_number FROM qc_certificates WHERE split_part(coa_number, '-', 3) = $1",
            str(year))
    nums = sorted(int(r["coa_number"].rsplit("-", 1)[-1]) for r in rows
                  if r["coa_number"].rsplit("-", 1)[-1].isdigit())
    if not nums:
        return {"year": year, "issued": 0, "min": None, "max": None, "gaps": [],
                "note": "No certificates issued in this year."}
    present = set(nums)
    missing = [n for n in range(nums[0], nums[-1] + 1) if n not in present]
    return {
        "year": year, "issued": len(nums), "min": nums[0], "max": nums[-1],
        "gaps": [f"PP-COA-{year}-{n:04d}" for n in missing],
        "note": ("The PP-COA sequence is shared across tenants on this database; a gap may"
                 " reflect a certificate issued to another organisation rather than a missing"
                 " record. Investigate each gap against the archive."),
    }


# ════════════════════════════════════════════════════════════════════════════
# QC LIMS U4 — out-of-specification investigations + CAPA (deviation cluster)
# ════════════════════════════════════════════════════════════════════════════
# A failing qc_results row (U3) is the trigger: an OOS investigation runs the
# GxP two-phase flow — Phase I laboratory investigation → Phase II full/root-
# cause investigation → QP disposition → close. CAPA is NOT a table: it is
# derived at read time from the OOS rows (matching qc-lims-ao's api/capa.py).
_OOS_TYPES = ("OOS", "OOT", "OOE", "OOC")
_OOS_RISK = ("HIGH", "MEDIUM", "LOW")
_OOS_PHASES = ("I", "II")
_OOS_STATUSES = ("OPEN", "PHASE_I", "PHASE_II", "CLOSED")
_OOS_DISPOSITIONS = ("RELEASE", "REJECT", "REPROCESS", "RETAIN")
_OOS_NOTIF_PARTS = ("A", "B", "C", "D")
# Status lifecycle. OPEN can be closed directly (e.g. a data-entry OOE resolved
# without an investigation); Phase I can close on a confirmed lab error.
_OOS_TRANSITIONS = {
    "OPEN": {"PHASE_I", "CLOSED"},
    "PHASE_I": {"PHASE_II", "CLOSED"},
    "PHASE_II": {"CLOSED"},
    "CLOSED": set(),
}
# Closing an OOS is a Qualified-Person decision (it dispositions the batch).
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


# ── OOS records ─────────────────────────────────────────────────────────────
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
            " VALUES ($1, 'PP-OOS-' || to_char(now(),'YYYY') || '-' ||"
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
        try:
            await emit(c, user, verb="oos_opened", object_type="qc_oos_record",
                       object_id=row["id"], recipients=[],
                       params={"oos_number": row["oos_number"], "batch_id": row["batch_id"]})
        except Exception:
            pass
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
        cur = await c.fetchrow("SELECT status FROM qc_oos_records WHERE id=$1", oos_id)
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
        for frag in extra_sql:
            if "PLACEHOLDER" in frag:
                args.append(extra_args.pop(0)); fields.append(frag.replace("PLACEHOLDER", str(len(args))))
            else:
                fields.append(frag)
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


@router.post("/oos/{oos_id}/notifications/{notif_id}/ack")
async def ack_oos_notification(oos_id: str, notif_id: str,
                               user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(oos_id, "OOS record")
    _uuid_or_404(notif_id, "Notification")
    async with rls(user) as c:
        row = await c.fetchrow(
            "UPDATE qc_oos_notifications SET acknowledged=true, acknowledged_at=now()"
            " WHERE id=$1 AND oos_id=$2 RETURNING *", notif_id, oos_id)
        if row is None:
            raise HTTPException(404, "Notification not found")
    return _notif_out(dict(row))


# ── CAPA (read-time view over OOS; no CAPA table) ───────────────────────────
@router.get("/capa")
async def list_capa(status: str | None = None, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        rows = await c.fetch("SELECT * FROM qc_oos_records ORDER BY created_at DESC")
    capa = [_capa_from_oos(dict(r)) for r in rows]
    if status:
        capa = [x for x in capa if x["status"] == status]
    return capa


# ── eCOA ingestion (Phase 3 U2 — the "CoA in" half of the pipeline) ─────────
# A supplier / contract-lab CoA (a PDF) is registered, its fields transcribed
# into `qc_coa_extractions`, GRADED by the server against the material spec,
# unknown labels queued in `qc_field_placeholders` for a human, and a reviewed
# document PROMOTED into a native DRAFT qc_certificate + qc_results (U3) — which
# then flows on to the U1 COQ. GxP: the server never invents a value; an
# unmapped label is queued (never guessed or dropped); an unmeasured value stays
# NULL / `complies` unknown. Transcription itself is done upstream (an LLM or a
# human); this module is the system of record, the grader, and the promoter.
_DOC_STATUSES = ("UPLOADED", "EXTRACTED", "REVIEWED", "PROMOTED", "REJECTED")
_PLACEHOLDER_STATUSES = ("OPEN", "MAPPED", "IGNORED")
_DOC_TRANSITIONS = {
    "UPLOADED": {"EXTRACTED", "REJECTED"},
    "EXTRACTED": {"REVIEWED", "REJECTED"},
    "REVIEWED": {"PROMOTED", "REJECTED"},
    "PROMOTED": set(),
    "REJECTED": set(),
}


def _norm_label(s: str | None) -> str:
    """Canonical form of a field label for cross-document matching / dedup:
    whitespace-collapsed, lowercased. Deliberately conservative — a human maps
    anything this doesn't catch, we never fuzzy-guess a GMP field."""
    return " ".join((s or "").split()).lower()


class CoaDocIn(BaseModel):
    batch_id: str = Field(max_length=200)
    source_institution: str | None = Field(default=None, max_length=200)
    laboratory_id: str | None = None
    material_code: str | None = Field(default=None, max_length=120)
    specification_id: str | None = None
    sample_id: str | None = None
    original_filename: str | None = Field(default=None, max_length=400)
    mime_type: str | None = Field(default=None, max_length=120)
    storage_ref: str | None = Field(default=None, max_length=1000)
    page_count: int | None = None
    report_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CoaDocPatch(BaseModel):
    source_institution: str | None = Field(default=None, max_length=200)
    laboratory_id: str | None = None
    material_code: str | None = Field(default=None, max_length=120)
    specification_id: str | None = None
    sample_id: str | None = None
    report_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    status: str | None = None            # guarded lifecycle transition


class ExtractionIn(BaseModel):
    raw_label: str = Field(max_length=400)
    raw_value: str | None = Field(default=None, max_length=400)
    numeric_value: float | None = None
    unit: str | None = Field(default=None, max_length=60)
    confidence: float | None = None
    source_page: int | None = None
    # The lab's own stated verdict, verbatim as printed on the eCoA
    # ("Pass", "Conforms", "Does not comply", …). Reference-only per QCSOP 012
    # §6.3.2 — conformance of record is always computed in-house.
    lab_verdict: str | None = Field(default=None, max_length=60)


class ExtractionsIn(BaseModel):
    # Cap the batch so one request can't drive an unbounded INSERT loop inside a
    # single transaction (holds a connection open); a real CoA has far fewer rows.
    items: list[ExtractionIn] = Field(max_length=500)


class ExtractionPatch(BaseModel):
    parameter_id: str | None = None
    numeric_value: float | None = None
    unit: str | None = Field(default=None, max_length=60)
    test_name: str | None = Field(default=None, max_length=300)
    lab_verdict: str | None = Field(default=None, max_length=60)


class PlaceholderPatch(BaseModel):
    status: str | None = None                     # MAPPED | IGNORED
    mapped_parameter_id: str | None = None
    suggested_test_name: str | None = Field(default=None, max_length=300)


def _ecoa_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "doc_number": r["doc_number"], "batch_id": r["batch_id"],
        "source_institution": r["source_institution"],
        "laboratory_id": str(r["laboratory_id"]) if r.get("laboratory_id") else None,
        "material_code": r["material_code"],
        "specification_id": str(r["specification_id"]) if r["specification_id"] else None,
        "sample_id": str(r["sample_id"]) if r["sample_id"] else None,
        "original_filename": r["original_filename"], "mime_type": r["mime_type"],
        "storage_ref": r["storage_ref"], "page_count": r["page_count"],
        "report_date": r["report_date"].isoformat() if r["report_date"] else None,
        "status": r["status"],
        "promoted_coa_id": str(r["promoted_coa_id"]) if r["promoted_coa_id"] else None,
        # §6.3.1 review clock
        "review_deadline": r["review_deadline"].isoformat() if r.get("review_deadline") else None,
        "reviewed_at": r["reviewed_at"].isoformat() if r.get("reviewed_at") else None,
        "review_window_met": r.get("review_window_met"),
        # overdue = still awaiting review AND the deadline has passed (computed)
        "review_overdue": bool(
            r.get("review_deadline") and r.get("review_window_met") is None
            and r["status"] in ("UPLOADED", "EXTRACTED")
            and r["review_deadline"] < date.today()),
        "notes": r["notes"],
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    }


def _lab_verdict_bool(v: str | None) -> bool | None:
    """Best-effort reading of the lab's stated verdict for the reconciliation
    flag. Deliberately conservative: anything ambiguous returns None and no
    mismatch is computed — the flag must never manufacture a disagreement."""
    if not v:
        return None
    t = v.strip().lower()
    if t in ("no", "не") or any(n in t for n in ("not", "non", "fail", "oos", "не ")):
        return False
    if any(p in t for p in ("pass", "conform", "compl", "задоволува", "соодветств")):
        return True
    return None


def _extract_out(r: dict) -> dict:
    lab = _lab_verdict_bool(r.get("lab_verdict"))
    return {
        "id": str(r["id"]), "document_id": str(r["document_id"]), "raw_label": r["raw_label"],
        "raw_value": r["raw_value"], "numeric_value": r["numeric_value"], "unit": r["unit"],
        "parameter_id": str(r["parameter_id"]) if r["parameter_id"] else None,
        "test_name": r["test_name"], "lower_limit": r["lower_limit"], "upper_limit": r["upper_limit"],
        "complies": r["complies"], "grade_status": r["grade_status"],
        "confidence": r["confidence"], "source_page": r["source_page"],
        "lab_verdict": r.get("lab_verdict"),
        # True only when BOTH sides state a verdict and they disagree — the
        # QCSOP 012 §6.3.2 reconciliation surfaced instead of silently dropped.
        "lab_verdict_mismatch": (lab is not None and r["complies"] is not None
                                 and lab != r["complies"]),
    }


def _placeholder_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "raw_label": r["raw_label"], "normalized_label": r["normalized_label"],
        "occurrences": r["occurrences"], "suggested_test_name": r["suggested_test_name"],
        "mapped_parameter_id": str(r["mapped_parameter_id"]) if r["mapped_parameter_id"] else None,
        "status": r["status"],
        "first_seen_document_id": str(r["first_seen_document_id"]) if r["first_seen_document_id"] else None,
    }


@router.get("/coa-documents")
async def list_coa_documents(status: str | None = None, batch_id: str | None = None,
                             user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    if batch_id:
        args.append(batch_id); clauses.append(f"batch_id=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            f"SELECT * FROM qc_coa_documents{where} ORDER BY created_at DESC", *args)
    return [_ecoa_out(dict(r)) for r in rows]


@router.get("/coa-documents/{doc_id}")
async def get_coa_document(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(doc_id, "eCoA document")
    async with rls(user) as c:
        doc = await c.fetchrow("SELECT * FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "eCoA document not found")
        rows = await c.fetch(
            "SELECT * FROM qc_coa_extractions WHERE document_id=$1 ORDER BY created_at", doc_id)
        files = await c.fetch(
            "SELECT id, org_id, object_type, object_id, filename, content_type, size_bytes,"
            " sha256, uploaded_by, uploaded_at FROM qc_document_files"
            " WHERE object_type='qc_coa_document' AND object_id=$1 ORDER BY uploaded_at", doc_id)
    return {"document": _ecoa_out(dict(doc)),
            "extractions": [_extract_out(dict(r)) for r in rows],
            "originals": [_file_out(dict(f)) for f in files]}


# ── Source-document custody (item 12): store the original with a SHA-256 ─────
_MAX_FILE_BYTES = 20 * 1024 * 1024   # 20 MB decoded — a scanned CoA fits easily


class FileUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    content_type: str | None = Field(default=None, max_length=120)
    content_b64: str = Field(min_length=1)


def _file_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "object_type": r["object_type"], "object_id": str(r["object_id"]),
        "filename": r["filename"], "content_type": r["content_type"],
        "size_bytes": r["size_bytes"], "sha256": r["sha256"],
        "uploaded_by": str(r["uploaded_by"]) if r["uploaded_by"] else None,
        "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
    }


@router.post("/coa-documents/{doc_id}/originals", status_code=201)
async def upload_coa_original(doc_id: str, body: FileUploadIn,
                             user: dict = Depends(require_role(*_WRITERS))):
    """Store the ORIGINAL source document (the supplier eCoA PDF) alongside the
    transcribed record with a server-computed SHA-256 (ALCOA+ 'Original'). The
    file is written once and never mutated; its digest is recorded in the global
    audit chain via emit(), so a later re-hash on download detects tampering."""
    _uuid_or_404(doc_id, "eCoA document")
    try:
        raw = base64.b64decode(body.content_b64, validate=True)
    except Exception:
        raise HTTPException(422, "content_b64 is not valid base64")
    if not raw:
        raise HTTPException(422, "The uploaded file is empty")
    if len(raw) > _MAX_FILE_BYTES:
        raise HTTPException(413, f"File exceeds the {_MAX_FILE_BYTES // (1024 * 1024)} MB limit")
    digest = hashlib.sha256(raw).hexdigest()
    async with rls(user) as c:
        doc = await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "eCoA document not found")
        row = await c.fetchrow(
            "INSERT INTO qc_document_files(org_id, object_type, object_id, filename,"
            " content_type, size_bytes, sha256, content, uploaded_by)"
            " VALUES ($1,'qc_coa_document',$2,$3,$4,$5,$6,$7,$8)"
            " RETURNING id, org_id, object_type, object_id, filename, content_type,"
            "           size_bytes, sha256, uploaded_by, uploaded_at",
            user["org_id"], doc_id, body.filename, body.content_type, len(raw), digest,
            raw, user["id"])
        try:
            await emit(c, user, verb="coa_original_stored", object_type="qc_coa_document",
                       object_id=doc_id, recipients=[],
                       params={"filename": body.filename, "sha256": digest, "size": len(raw)})
        except Exception:
            pass
    return _file_out(dict(row))


@router.get("/coa-documents/{doc_id}/originals")
async def list_coa_originals(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(doc_id, "eCoA document")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT id, org_id, object_type, object_id, filename, content_type, size_bytes,"
            " sha256, uploaded_by, uploaded_at FROM qc_document_files"
            " WHERE object_type='qc_coa_document' AND object_id=$1 ORDER BY uploaded_at", doc_id)
    return [_file_out(dict(r)) for r in rows]


@router.get("/document-files/{file_id}/download")
async def download_document_file(file_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Return the stored original bytes. Re-hashes on the way out and reports the
    integrity verdict in an `X-Integrity` header (OK / MISMATCH) — a MISMATCH
    means the stored bytes no longer match the SHA-256 recorded at upload."""
    _uuid_or_404(file_id, "Document file")
    async with rls(user) as c:
        row = await c.fetchrow(
            "SELECT filename, content_type, sha256, content FROM qc_document_files WHERE id=$1",
            file_id)
    if row is None:
        raise HTTPException(404, "Document file not found")
    data = bytes(row["content"])
    integrity = "OK" if hashlib.sha256(data).hexdigest() == row["sha256"] else "MISMATCH"
    safe_name = (row["filename"] or "download").replace('"', "").replace("\\", "").replace("\n", "")
    return Response(
        content=data, media_type=row["content_type"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"',
                 "X-Integrity": integrity, "X-Content-SHA256": row["sha256"]})


# ── Batch genealogy (item 5, D2 = blending → m:n) ────────────────────────────
# variety → cultivation (AB…) → processing (P…) → packaging, with blending
# (multiple parents). Directed edges between batch codes; the app guards cycles.
_GENEALOGY_RELATIONS = ("CULTIVATION", "PROCESSING", "PACKAGING", "BLEND", "GENERIC")


class GenealogyIn(BaseModel):
    parent_batch_id: str = Field(min_length=1, max_length=120)
    child_batch_id: str = Field(min_length=1, max_length=120)
    relation: str = "GENERIC"
    quantity: float | None = None
    unit: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)


def _edge_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "parent_batch_id": r["parent_batch_id"],
        "child_batch_id": r["child_batch_id"], "relation": r["relation"],
        "quantity": float(r["quantity"]) if r["quantity"] is not None else None,
        "unit": r["unit"], "notes": r["notes"],
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    }


@router.post("/genealogy", status_code=201)
async def add_genealogy_edge(body: GenealogyIn, user: dict = Depends(require_role(*_WRITERS))):
    """Link a parent batch to a child batch (variety→cultivation→processing→
    packaging; BLEND for a multi-parent merge). Refuses an edge that would close
    a cycle (a batch cannot be its own ancestor)."""
    parent, child = body.parent_batch_id.strip(), body.child_batch_id.strip()
    if not parent or not child:
        raise HTTPException(422, "parent_batch_id and child_batch_id are required")
    if parent == child:
        raise HTTPException(422, "A batch cannot be its own parent")
    if body.relation not in _GENEALOGY_RELATIONS:
        raise HTTPException(422, f"relation must be one of: {', '.join(_GENEALOGY_RELATIONS)}")
    async with rls(user) as c:
        # cycle guard: parent must NOT already be a descendant of child
        cyc = await c.fetchval(
            "WITH RECURSIVE d AS ("
            "  SELECT child_batch_id AS b FROM qc_batch_genealogy WHERE parent_batch_id=$1"
            "  UNION"
            "  SELECT g.child_batch_id FROM qc_batch_genealogy g JOIN d ON g.parent_batch_id=d.b)"
            " SELECT 1 FROM d WHERE b=$2 LIMIT 1", child, parent)
        if cyc:
            raise HTTPException(409, "That edge would create a cycle in the genealogy")
        try:
            row = await c.fetchrow(
                "INSERT INTO qc_batch_genealogy(org_id, parent_batch_id, child_batch_id, relation,"
                " quantity, unit, notes, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
                user["org_id"], parent, child, body.relation, body.quantity, body.unit,
                body.notes, user["id"])
        except Exception as e:
            if "qc_batch_genealogy_edge_key" in str(e):
                raise HTTPException(409, "That parent→child edge already exists")
            raise
    return _edge_out(dict(row))


@router.delete("/genealogy/{edge_id}", status_code=204)
async def delete_genealogy_edge(edge_id: str, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(edge_id, "Genealogy edge")
    async with rls(user) as c:
        tag = await c.execute("DELETE FROM qc_batch_genealogy WHERE id=$1", edge_id)
    if tag == "DELETE 0":
        raise HTTPException(404, "Genealogy edge not found")
    return Response(status_code=204)


@router.get("/genealogy/{batch_id}")
async def get_genealogy(batch_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """The lineage around a batch: its ancestors (recursively up), descendants
    (recursively down), and the direct parent/child edges."""
    async with rls(user) as c:
        parents = await c.fetch(
            "SELECT * FROM qc_batch_genealogy WHERE child_batch_id=$1 ORDER BY created_at", batch_id)
        children = await c.fetch(
            "SELECT * FROM qc_batch_genealogy WHERE parent_batch_id=$1 ORDER BY created_at", batch_id)
        ancestors = await c.fetch(
            "WITH RECURSIVE a AS ("
            "  SELECT parent_batch_id AS b, 1 AS depth FROM qc_batch_genealogy WHERE child_batch_id=$1"
            "  UNION"
            "  SELECT g.parent_batch_id, a.depth+1 FROM qc_batch_genealogy g JOIN a ON g.child_batch_id=a.b)"
            " SELECT b, min(depth) AS depth FROM a GROUP BY b ORDER BY depth, b", batch_id)
        descendants = await c.fetch(
            "WITH RECURSIVE d AS ("
            "  SELECT child_batch_id AS b, 1 AS depth FROM qc_batch_genealogy WHERE parent_batch_id=$1"
            "  UNION"
            "  SELECT g.child_batch_id, d.depth+1 FROM qc_batch_genealogy g JOIN d ON g.parent_batch_id=d.b)"
            " SELECT b, min(depth) AS depth FROM d GROUP BY b ORDER BY depth, b", batch_id)
    return {
        "batch_id": batch_id,
        "parents": [_edge_out(dict(r)) for r in parents],
        "children": [_edge_out(dict(r)) for r in children],
        "ancestors": [{"batch_id": r["b"], "depth": r["depth"]} for r in ancestors],
        "descendants": [{"batch_id": r["b"], "depth": r["depth"]} for r in descendants],
    }


@router.get("/genealogy/{batch_id}/inherited-results")
async def get_inherited_results(batch_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """CoQ-level inheritance (QCSOP 012 D3): the RELEASED-certificate results of
    this batch's ANCESTOR batches, available for a finished-product CoQ to inherit
    from its intermediate/bulk lots. Advisory — surfaced for the compiler, never
    auto-copied into a certificate (a human decides what a blend carries forward)."""
    async with rls(user) as c:
        anc = await c.fetch(
            "WITH RECURSIVE a AS ("
            "  SELECT parent_batch_id AS b FROM qc_batch_genealogy WHERE child_batch_id=$1"
            "  UNION"
            "  SELECT g.parent_batch_id FROM qc_batch_genealogy g JOIN a ON g.child_batch_id=a.b)"
            " SELECT DISTINCT b FROM a", batch_id)
        ancestor_ids = [r["b"] for r in anc]
        inherited = []
        if ancestor_ids:
            certs = await c.fetch(
                "SELECT * FROM qc_certificates WHERE batch_id = ANY($1::text[])"
                " AND status='RELEASED' ORDER BY batch_id, created_at", ancestor_ids)
            for cert in certs:
                results = await c.fetch(
                    "SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", cert["id"])
                inherited.append({
                    "from_batch_id": cert["batch_id"],
                    "coa_number": cert["coa_number"],
                    "decision": cert["decision"],
                    "results": [_result_out(dict(r)) for r in results],
                })
    return {"batch_id": batch_id, "ancestors": ancestor_ids, "inherited": inherited}


@router.post("/coa-documents", status_code=201)
async def create_coa_document(body: CoaDocIn, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_422(body.specification_id, "specification_id")
    _uuid_or_422(body.sample_id, "sample_id")
    _uuid_or_422(body.laboratory_id, "laboratory_id")
    async with rls(user) as c:
        if body.specification_id:
            if await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1", body.specification_id) is None:
                raise HTTPException(422, "Unknown specification")
        if body.sample_id:
            if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", body.sample_id) is None:
                raise HTTPException(422, "Unknown sample")
        await _resolve_lab(c, user["org_id"], body.laboratory_id)
        row = await c.fetchrow(
            "INSERT INTO qc_coa_documents(org_id, doc_number, source_institution, laboratory_id,"
            " batch_id, material_code, specification_id, sample_id, original_filename, mime_type,"
            " storage_ref, page_count, report_date, notes, review_deadline, uploaded_by,"
            " created_by, updated_by)"
            " VALUES ($1, 'PP-ECOA-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_ecoa_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::date,$13,"
            # QCSOP 012 §6.3.1: 5 working days to review. From any weekday that
            # is exactly 7 calendar days (5 business days always cross one
            # weekend); a weekend registration rolls to Monday first (lenient —
            # the clock never starts on a non-working day).
            "         (CURRENT_DATE + CASE extract(isodow FROM CURRENT_DATE)::int"
            "            WHEN 6 THEN 2 WHEN 7 THEN 1 ELSE 0 END + 7)::date,"
            "         $14,$14,$14) RETURNING *",
            user["org_id"], body.source_institution, body.laboratory_id, body.batch_id,
            body.material_code, body.specification_id, body.sample_id, body.original_filename,
            body.mime_type, body.storage_ref, body.page_count, body.report_date, body.notes,
            user["id"])
    return _ecoa_out(dict(row))


@router.patch("/coa-documents/{doc_id}")
async def update_coa_document(doc_id: str, body: CoaDocPatch,
                              user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(doc_id, "eCoA document")
    patch = body.model_dump(exclude_unset=True)
    _uuid_or_422(patch.get("specification_id"), "specification_id")
    _uuid_or_422(patch.get("sample_id"), "sample_id")
    _uuid_or_422(patch.get("laboratory_id"), "laboratory_id")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_coa_documents WHERE id=$1", doc_id)
        if cur is None:
            raise HTTPException(404, "eCoA document not found")
        if patch.get("laboratory_id") is not None:
            await _resolve_lab(c, user["org_id"], patch["laboratory_id"])
        if cur["status"] in ("PROMOTED", "REJECTED"):
            # A promoted document is the source-of-record for a minted
            # certificate — rebinding its spec/sample/metadata afterwards would
            # break the provenance the verify loop reconciles against.
            raise HTTPException(409, f"Document is {cur['status']} — locked")
        review_stamp = False
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _DOC_STATUSES:
                raise HTTPException(422, "Unknown status")
            # PROMOTED is reached only via the promote endpoint (it must mint a
            # certificate) — never by a bare status PATCH.
            if target == "PROMOTED":
                raise HTTPException(409, "Use POST /coa-documents/{id}/promote to promote")
            if target not in _DOC_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            review_stamp = (target == "REVIEWED")
        if body.specification_id:
            if await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1", body.specification_id) is None:
                raise HTTPException(422, "Unknown specification")
        fields, args = [], []
        _NULLABLE = {"source_institution", "laboratory_id", "material_code", "specification_id",
                     "sample_id", "report_date", "notes"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            if col == "report_date":
                args.append(val); fields.append(f"{col}=${len(args)}::date")
            else:
                args.append(val); fields.append(f"{col}=${len(args)}")
        # §6.3.1: stamp the review timestamp + whether it landed inside the
        # 5-working-day window (met iff reviewed on/before the deadline).
        if review_stamp:
            fields.append("reviewed_at=now()")
            fields.append("review_window_met=(CURRENT_DATE <= review_deadline)")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(doc_id)
        row = await c.fetchrow(
            f"UPDATE qc_coa_documents SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
    return _ecoa_out(dict(row))


@router.post("/coa-documents/{doc_id}/extractions", status_code=201)
async def submit_extractions(doc_id: str, body: ExtractionsIn,
                             user: dict = Depends(require_role(*_WRITERS))):
    """Bulk-submit the transcribed fields for a document. Each field is
    auto-mapped to a spec parameter (by an existing human mapping, then by
    name), server-graded against that parameter's limits, and — when no
    mapping is found — queued in `qc_field_placeholders` for a human. Sets the
    document status to EXTRACTED."""
    async with rls(user) as c:
        doc = await c.fetchrow("SELECT * FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "eCoA document not found")
        if doc["status"] in ("PROMOTED", "REJECTED"):
            raise HTTPException(409, f"Document is {doc['status']} — extractions are closed")
        # candidate parameters: the doc's spec, matched by canonical name…
        by_name: dict[str, dict] = {}
        if doc["specification_id"]:
            for p in await c.fetch(
                    "SELECT * FROM qc_spec_parameters WHERE spec_id=$1", doc["specification_id"]):
                pd = dict(p)
                for key in (pd.get("test_name_en"), pd.get("test_name_mk")):
                    n = _norm_label(key)
                    if n:
                        by_name.setdefault(n, pd)
        # …plus any label a human has already mapped (org-wide, cross-document).
        ph_rows = await c.fetch(
            "SELECT normalized_label, mapped_parameter_id FROM qc_field_placeholders"
            " WHERE status='MAPPED' AND mapped_parameter_id IS NOT NULL")
        mapped_by_label = {r["normalized_label"]: r["mapped_parameter_id"] for r in ph_rows}
        param_by_id: dict[str, dict] = {}
        if mapped_by_label:
            for p in await c.fetch(
                    "SELECT * FROM qc_spec_parameters WHERE id = ANY($1::uuid[])",
                    list(mapped_by_label.values())):
                param_by_id[str(p["id"])] = dict(p)

        out, unmapped = [], 0
        for item in body.items:
            nlabel = _norm_label(item.raw_label)
            param = None
            if nlabel in mapped_by_label:
                param = param_by_id.get(str(mapped_by_label[nlabel]))
            if param is None:
                param = by_name.get(nlabel)
            if param is not None:
                lo, hi = param.get("lower_limit"), param.get("upper_limit")
                complies, _ = _evaluate(item.numeric_value, lo, hi)
                grade = "graded" if item.numeric_value is not None else "unknown"
                test_name = param.get("test_name_en") or param.get("test_name_mk")
                pid = param["id"]
            else:
                lo = hi = complies = None
                grade, test_name, pid = "unmapped", None, None
                unmapped += 1
                # adaptive discovery: surface the unknown label for a human,
                # deduped per org, occurrences counted.
                await c.execute(
                    "INSERT INTO qc_field_placeholders(org_id, raw_label, normalized_label,"
                    " suggested_test_name, first_seen_document_id, created_by, updated_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$6)"
                    " ON CONFLICT (org_id, normalized_label) DO UPDATE"
                    "   SET occurrences = qc_field_placeholders.occurrences + 1, updated_at=now()",
                    user["org_id"], item.raw_label, nlabel, item.raw_label, doc_id, user["id"])
            row = await c.fetchrow(
                "INSERT INTO qc_coa_extractions(org_id, document_id, raw_label, raw_value,"
                " numeric_value, unit, parameter_id, test_name, lower_limit, upper_limit,"
                " complies, grade_status, confidence, source_page, lab_verdict,"
                " created_by, updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$16) RETURNING *",
                user["org_id"], doc_id, item.raw_label, item.raw_value, item.numeric_value,
                item.unit, pid, test_name, lo, hi, complies, grade, item.confidence,
                item.source_page, item.lab_verdict, user["id"])
            out.append(_extract_out(dict(row)))
        if doc["status"] == "UPLOADED":
            await c.execute(
                "UPDATE qc_coa_documents SET status='EXTRACTED', updated_by=$1, updated_at=now()"
                " WHERE id=$2", user["id"], doc_id)
    return {"extractions": out, "count": len(out), "unmapped": unmapped}


@router.patch("/coa-documents/{doc_id}/extractions/{eid}")
async def update_extraction(doc_id: str, eid: str, body: ExtractionPatch,
                            user: dict = Depends(require_role(*_WRITERS))):
    """Reviewer fix: map an extraction to a spec parameter (re-grades against
    that parameter's limits) and/or correct the value/unit."""
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        doc = await c.fetchrow(
            "SELECT status, specification_id FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "Document not found")
        if doc["status"] in ("PROMOTED", "REJECTED"):
            # Once a certificate has been minted (or the doc rejected) the
            # source-of-record is closed — editing an extraction afterwards
            # would silently desync it from the already-created qc_results.
            raise HTTPException(409, f"Document is {doc['status']} — extractions are locked")
        cur = await c.fetchrow(
            "SELECT * FROM qc_coa_extractions WHERE id=$1 AND document_id=$2", eid, doc_id)
        if cur is None:
            raise HTTPException(404, "Extraction not found")
        row = dict(cur)
        numeric = patch["numeric_value"] if "numeric_value" in patch else row["numeric_value"]
        pid = row["parameter_id"]
        lo, hi, test_name = row["lower_limit"], row["upper_limit"], row["test_name"]
        if "parameter_id" in patch:
            pid = patch["parameter_id"]
            if pid:
                _uuid_or_422(pid, "parameter_id")
                # Same guard add_result has: the cited parameter must belong to
                # THIS document's specification, else a reviewer could re-grade
                # a value against another spec's limits and promote fabricated
                # conformance onto the certificate.
                p = await c.fetchrow("SELECT * FROM qc_spec_parameters WHERE id=$1", pid)
                if p is None:
                    raise HTTPException(422, "Unknown parameter")
                if doc["specification_id"] is None or p["spec_id"] != doc["specification_id"]:
                    raise HTTPException(422, "Parameter does not belong to this document's specification")
                lo, hi = p["lower_limit"], p["upper_limit"]
                test_name = patch.get("test_name") or p["test_name_en"] or p["test_name_mk"]
            else:
                lo = hi = None
        if "test_name" in patch and patch["test_name"]:
            test_name = patch["test_name"]
        unit = patch["unit"] if "unit" in patch else row["unit"]
        if pid:
            complies, _ = _evaluate(numeric, lo, hi)
            grade = "graded" if numeric is not None else "unknown"
        else:
            complies, grade = None, "unmapped"
        lab_verdict = patch["lab_verdict"] if "lab_verdict" in patch else row["lab_verdict"]
        row = await c.fetchrow(
            "UPDATE qc_coa_extractions SET parameter_id=$1, test_name=$2, numeric_value=$3,"
            " unit=$4, lower_limit=$5, upper_limit=$6, complies=$7, grade_status=$8,"
            " lab_verdict=$9, updated_by=$10, updated_at=now()"
            " WHERE id=$11 AND document_id=$12 RETURNING *",
            pid, test_name, numeric, unit, lo, hi, complies, grade, lab_verdict,
            user["id"], eid, doc_id)
    return _extract_out(dict(row))


@router.get("/coa-placeholders")
async def list_placeholders(status: str | None = None,
                            user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            f"SELECT * FROM qc_field_placeholders{where} ORDER BY occurrences DESC, created_at", *args)
    return [_placeholder_out(dict(r)) for r in rows]


@router.patch("/coa-placeholders/{ph_id}")
async def update_placeholder(ph_id: str, body: PlaceholderPatch,
                             user: dict = Depends(require_role(*_WRITERS))):
    """Resolve a discovered field: MAP it to a spec parameter (future CoAs then
    auto-map that label) or IGNORE it."""
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_field_placeholders WHERE id=$1", ph_id)
        if cur is None:
            raise HTTPException(404, "Placeholder not found")
        target = patch.get("status")
        if target is not None and target not in _PLACEHOLDER_STATUSES:
            raise HTTPException(422, "status must be OPEN, MAPPED or IGNORED")
        if target == "MAPPED" and not patch.get("mapped_parameter_id"):
            raise HTTPException(422, "MAPPED requires mapped_parameter_id")
        # Validate the referenced parameter whenever it is supplied (not only on a
        # MAPPED transition), so a bad/cross-org id 422s instead of hitting a raw
        # FK violation (500) or persisting a dangling reference.
        if patch.get("mapped_parameter_id"):
            if await c.fetchrow("SELECT id FROM qc_spec_parameters WHERE id=$1",
                                patch["mapped_parameter_id"]) is None:
                raise HTTPException(422, "Unknown parameter")
        fields, args = [], []
        for col in ("status", "mapped_parameter_id", "suggested_test_name"):
            if col in patch:
                args.append(patch[col]); fields.append(f"{col}=${len(args)}")
        if target in ("MAPPED", "IGNORED"):
            args.append(user["id"]); fields.append(f"resolved_by=${len(args)}")
            fields.append("resolved_at=now()")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(ph_id)
        row = await c.fetchrow(
            f"UPDATE qc_field_placeholders SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
    return _placeholder_out(dict(row))


@router.post("/coa-documents/{doc_id}/promote", status_code=201)
async def promote_coa_document(doc_id: str, user: dict = Depends(require_role(*_WRITERS))):
    """Promote a reviewed eCoA into a native DRAFT qc_certificate + qc_results
    (U3). One result per MAPPED extraction, each carrying its source document
    (feeds the U1 COQ's per-line provenance). Unmapped extractions are left in
    the review queue and reported — never fabricated into a result."""
    async with rls(user) as c:
        doc = await c.fetchrow("SELECT * FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "eCoA document not found")
        if doc["status"] not in ("EXTRACTED", "REVIEWED"):
            raise HTTPException(409, "Only an EXTRACTED or REVIEWED document can be promoted")
        if doc["promoted_coa_id"]:
            raise HTTPException(409, "Document already promoted")
        if not doc["specification_id"]:
            raise HTTPException(409, "Promotion needs a specification to certify against")
        rows = await c.fetch(
            "SELECT * FROM qc_coa_extractions WHERE document_id=$1 ORDER BY created_at", doc_id)
        mapped = [dict(r) for r in rows if r["parameter_id"] is not None]
        if not mapped:
            raise HTTPException(409, "No mapped results to promote — map the discovered fields first")
        coa = await c.fetchrow(
            "INSERT INTO qc_certificates(org_id, coa_number, batch_id, specification_id, sample_id,"
            " cert_type, report_date, source_lab, laboratory_id, notes, analyst_id,"
            " created_by, updated_by)"
            " VALUES ($1, 'PP-COA-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_coa_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,'ECOA',$5::date,$6,$7,$8,$9,$9,$9) RETURNING *",
            user["org_id"], doc["batch_id"], doc["specification_id"], doc["sample_id"],
            doc["report_date"], doc["source_institution"], doc["laboratory_id"],
            f"Promoted from {doc['doc_number']}", user["id"])
        for m in mapped:
            _, st = _evaluate(m["numeric_value"], m["lower_limit"], m["upper_limit"])
            await c.execute(
                "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value,"
                " result_numeric, unit, lower_limit, upper_limit, complies, status, analyst_id,"
                " source_document_code, source_institution, lab_verdict, created_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$12)",
                user["org_id"], coa["id"], m["parameter_id"],
                m["test_name"] or m["raw_label"], m["raw_value"], m["numeric_value"], m["unit"],
                m["lower_limit"], m["upper_limit"], m["complies"], st, user["id"],
                doc["doc_number"], doc["source_institution"], m["lab_verdict"])
        # Optimistic re-assert (same TOCTOU defense generate_coq uses): the
        # promoted_coa_id IS NULL predicate makes concurrent promotes race-safe
        # — the loser's UPDATE matches 0 rows and the whole transaction (its
        # duplicate certificate + results included) rolls back with a 409.
        tag = await c.execute(
            "UPDATE qc_coa_documents SET status='PROMOTED', promoted_coa_id=$1,"
            " updated_by=$2, updated_at=now()"
            " WHERE id=$3 AND promoted_coa_id IS NULL", coa["id"], user["id"], doc_id)
        if tag == "UPDATE 0":
            raise HTTPException(409, "Document was already promoted")
        try:
            await emit(c, user, verb="ecoa_promoted", object_type="qc_coa_document",
                       object_id=doc_id, recipients=[],
                       params={"doc_number": doc["doc_number"], "coa_number": coa["coa_number"],
                               "results": len(mapped)})
        except Exception:
            pass
    return {"coa_id": str(coa["id"]), "coa_number": coa["coa_number"],
            "results_created": len(mapped), "skipped_unmapped": len(rows) - len(mapped)}


# ── Verify loop (Phase 3 U3) — reconcile a promoted certificate vs its source ─
# A certificate minted from an ingested eCoA (U2) is reconciled against that
# source document: every promoted qc_result is matched (by spec parameter) to
# the qc_coa_extraction it came from and the value / verdict / limits compared.
# The outcome is an auditable qc_coa_verifications record — a GxP second check
# that the promoted data still agrees with the source. Nothing is recomputed or
# "corrected" here; a mismatch is surfaced, never silently reconciled.
def _num_eq(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= 1e-9


def _verify_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coa_id": str(r["coa_id"]),
        "source_document_id": str(r["source_document_id"]) if r["source_document_id"] else None,
        "verdict": r["verdict"], "checked": r["checked"], "mismatches": r["mismatches"],
        "details": r["details"],
        "verified_at": r["verified_at"].isoformat() if r.get("verified_at") else None,
    }


@router.get("/certificates/{coa_id}/verifications")
async def list_verifications(coa_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT * FROM qc_coa_verifications WHERE coa_id=$1 ORDER BY verified_at DESC", coa_id)
    return [_verify_out(dict(r)) for r in rows]


@router.post("/certificates/{coa_id}/verify", status_code=201)
async def verify_certificate(coa_id: str, user: dict = Depends(require_role(*_WRITERS))):
    """Reconcile a promoted certificate against its source eCoA and record the
    verdict. 409 if the certificate was not promoted from an ingested document
    (nothing to reconcile against)."""
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT id FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        doc = await c.fetchrow(
            "SELECT * FROM qc_coa_documents WHERE promoted_coa_id=$1", coa_id)
        if doc is None:
            raise HTTPException(409, "Certificate was not promoted from an ingested eCoA")
        results = await c.fetch("SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", coa_id)
        exts = await c.fetch(
            "SELECT * FROM qc_coa_extractions WHERE document_id=$1 AND parameter_id IS NOT NULL",
            doc["id"])
        by_param = {str(e["parameter_id"]): dict(e) for e in exts}
        details, mismatches = [], 0
        for r in results:
            pid = str(r["parameter_id"]) if r["parameter_id"] else None
            src = by_param.get(pid) if pid else None
            if src is None:
                match, reason = False, "no matching source line"
            else:
                num_ok = _num_eq(r["result_numeric"], src["numeric_value"])
                comply_ok = (r["complies"] == src["complies"])
                lim_ok = _num_eq(r["lower_limit"], src["lower_limit"]) and _num_eq(r["upper_limit"], src["upper_limit"])
                match = num_ok and comply_ok and lim_ok
                reason = "" if match else ", ".join(
                    x for x, ok in (("value", num_ok), ("verdict", comply_ok), ("limits", lim_ok)) if not ok)
            if not match:
                mismatches += 1
            _f = lambda v: None if v is None else float(v)   # jsonb can't take Decimal
            details.append({
                "parameter_id": pid, "test_name": r["test_name"],
                "result_numeric": _f(r["result_numeric"]),
                "source_numeric": _f(src["numeric_value"]) if src else None,
                "result_complies": r["complies"], "source_complies": src["complies"] if src else None,
                "match": match, "reason": reason})
        verdict = "VERIFIED" if mismatches == 0 else "DISCREPANCY"
        row = await c.fetchrow(
            "INSERT INTO qc_coa_verifications(org_id, coa_id, source_document_id, verdict,"
            " checked, mismatches, details, verified_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
            user["org_id"], coa_id, doc["id"], verdict, len(results), mismatches, details, user["id"])
        try:
            await emit(c, user, verb="coa_verified", object_type="qc_certificate",
                       object_id=coa_id, recipients=[],
                       params={"verdict": verdict, "checked": len(results), "mismatches": mismatches})
        except Exception:
            pass
    return _verify_out(dict(row))


# ── Annex 11 electronic signatures (URS §14 / item 11) ──────────────────────
# A deliberate, re-authenticated attestation on a certificate, carrying the
# signer's name, the MEANING of the signature, the date/time, and a permanent
# link to the record. Distinct from audit_log (which records the mutation) —
# this is the signing ACT. The signer re-enters their password at sign time
# (Annex 11 §14: executed by the signer), the role gate matches the writers,
# and the certificate's own lifecycle/second-person gates are unchanged.
_SIG_MEANINGS = ("AUTHORED", "REVIEWED", "APPROVED", "RELEASED", "VERIFIED", "COQ_ISSUED")


class SignIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    meaning: str
    statement: str | None = Field(default=None, max_length=500)


def _sig_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "object_type": r["object_type"],
        "object_id": str(r["object_id"]), "signer_id": str(r["signer_id"]),
        "signer_name": r["signer_name"], "signer_role": r["signer_role"],
        "meaning": r["meaning"], "statement": r["statement"],
        "signed_at": r["signed_at"].isoformat() if r["signed_at"] else None,
    }


@router.get("/certificates/{coa_id}/signatures")
async def list_signatures(coa_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_certificate' AND object_id=$1"
            " ORDER BY signed_at", coa_id)
    return [_sig_out(dict(r)) for r in rows]


@router.post("/certificates/{coa_id}/sign", status_code=201)
async def sign_certificate(coa_id: str, body: SignIn,
                           user: dict = Depends(require_role(*_WRITERS))):
    """Apply an Annex 11 electronic signature to a certificate. The signer
    RE-AUTHENTICATES (their account password) at the moment of signing; the
    signature records the name, role, meaning, and time, permanently linked to
    the certificate. Reference/attestation — it does not itself drive the
    lifecycle (the role + second-person gates on the transitions stand)."""
    _uuid_or_404(coa_id, "Certificate")
    if body.meaning not in _SIG_MEANINGS:
        raise HTTPException(422, f"meaning must be one of: {', '.join(_SIG_MEANINGS)}")
    # Re-authenticate against the signer's own account (Annex 11 §14) — the
    # profile (and its password hash) lives in the separate users DB.
    prof = await users_admin_pool().fetchrow(
        "SELECT full_name, password_hash FROM profiles WHERE id=$1 AND is_deleted=false", user["id"])
    if prof is None or not verify_password(body.password, prof["password_hash"]):
        raise HTTPException(401, "Signature not applied — re-authentication failed")
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT id FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        row = await c.fetchrow(
            "INSERT INTO qc_signatures(org_id, object_type, object_id, signer_id, signer_name,"
            " signer_role, meaning, statement) VALUES ($1,'qc_certificate',$2,$3,$4,$5,$6,$7)"
            " RETURNING *",
            user["org_id"], coa_id, user["id"],
            prof["full_name"] or user.get("username") or "—", user["role"], body.meaning,
            body.statement)
        try:
            await emit(c, user, verb="coa_signed", object_type="qc_certificate",
                       object_id=coa_id, recipients=[], params={"meaning": body.meaning})
        except Exception:
            pass
    return _sig_out(dict(row))


# ── Custody cluster (U5) — sampling requests (RQS) + field records (SFR) + ───
# chain of custody. Field-to-lab traceability (ALCOA++). A department raises an
# RQS; QC registers it within a 24-hour window (PP-QC-SOP-017), assigns, and
# completes it (producing a sample). Field sampling is captured on an SFR
# (barrels, destination, transport times). Every custody handoff of a sample is
# appended to the chain of custody.
_RQS_STATUSES = ("OPEN", "REGISTERED", "IN_PROGRESS", "COMPLETED", "CANCELLED")
_RQS_TRANSITIONS = {
    "OPEN": {"REGISTERED", "CANCELLED"},
    "REGISTERED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(), "CANCELLED": set(),
}
_SFR_STATUSES = ("CREATED", "IN_FIELD", "COMPLETED", "CANCELLED")
_SFR_TRANSITIONS = {
    "CREATED": {"IN_FIELD", "CANCELLED"},
    "IN_FIELD": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(), "CANCELLED": set(),
}
_TRANSFER_TYPES = ("FIELD_TO_LAB", "LAB_INTERNAL", "LAB_TO_DISPOSAL", "STABILITY_TRANSFER")
# QCSOP 011 v3 vocabularies. Required-tests menu (§6.1.4), request priority
# (§6.1.4: ROUTINE 5–10 wd / URGENT ≤3 wd with written justification), and the
# current-material-status enumeration.
_RQS_TESTS = ("POTENCY", "LOD", "FM", "MICRO", "HEAVY_METALS", "PESTICIDES",
              "MYCOTOXINS", "OTHER")
_RQS_PRIORITIES = ("ROUTINE", "URGENT")
_RQS_MATERIAL_STATUSES = ("QUARANTINE", "IN_PROCESS", "OTHER")
# §6.1.4 fields that must be present before the QC Head may REGISTER an RQS into
# the MLL — the completeness gate (§6.1.6b: an incomplete RQS is not registered).
_RQS_MANDATORY = ("batch_id", "num_samples", "required_tests", "storage_location",
                  "material_status", "spec_reference")
# §6.2.1 sample-type taxonomy (the code embedded in the SFR sample id).
_SAMPLE_KINDS = ("PC", "MB", "EXT", "RET", "STAB", "RT", "CC")
# §3 / §6.1.6: RQS registration into the MLL is a QC-Head act (not any writer);
# a release-related request (§6.1.2) escalates to the Qualified Person.
_QC_REGISTRAR = (ADMIN, "QC_MGR", "QP")
# An RQS must be registered (past OPEN, not cancelled) before a sampling act may
# be recorded against it — §6.1.1: no sampling without a registered RQS.
_RQS_REGISTERED = ("REGISTERED", "IN_PROGRESS", "COMPLETED")


def _iso(v):
    return v.isoformat() if v is not None else None


class RqsIn(BaseModel):
    material_code: str = Field(max_length=120)
    material_name_en: str | None = Field(default=None, max_length=300)
    material_name_mk: str | None = Field(default=None, max_length=300)
    batch_id: str | None = Field(default=None, max_length=120)
    originating_department: str = Field(max_length=120)
    assigned_sp_type: str | None = Field(default=None, max_length=20)
    # §6.1.4 mandatory RQS fields (a draft may be incomplete; completeness is
    # enforced at registration per §6.1.6, not at submission).
    num_samples: int | None = Field(default=None, ge=0, le=100000)
    required_tests: list | None = None
    priority: str | None = None
    priority_justification: str | None = Field(default=None, max_length=1000)
    storage_location: str | None = Field(default=None, max_length=300)
    material_status: str | None = None
    specification_id: str | None = None
    spec_reference: str | None = Field(default=None, max_length=200)
    release_related: bool = False
    notes: str | None = Field(default=None, max_length=4000)


class RqsPatch(BaseModel):
    status: str | None = None                     # guarded lifecycle transition
    assigned_sp_type: str | None = Field(default=None, max_length=20)
    assigned_to_id: str | None = None
    sample_id: str | None = None
    # §6.1.4 fields remain editable while the RQS is a draft (OPEN)
    num_samples: int | None = Field(default=None, ge=0, le=100000)
    required_tests: list | None = None
    priority: str | None = None
    priority_justification: str | None = Field(default=None, max_length=1000)
    storage_location: str | None = Field(default=None, max_length=300)
    material_status: str | None = None
    specification_id: str | None = None
    spec_reference: str | None = Field(default=None, max_length=200)
    release_related: bool | None = None
    cancellation_reason: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)


class SfrIn(BaseModel):
    # §6.1.1: a sampling act may not be recorded without a REGISTERED RQS — the
    # link is required and validated to be registered.
    rqs_id: str
    sampling_location: str = Field(max_length=300)
    sampling_coordinates: str | None = Field(default=None, max_length=120)
    barrel_numbers: list = Field(default_factory=list)
    num_containers: int | None = None
    destination_facility: str = Field(max_length=300)
    destination_location: str | None = Field(default=None, max_length=300)
    planned_departure: datetime | None = None
    planned_arrival: datetime | None = None
    sampled_by_id: str | None = None
    escort_id: str | None = None
    sample_id: str | None = None
    # §6.2.3 equipment record
    sampling_equipment: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=4000)


class SfrPatch(BaseModel):
    status: str | None = None
    actual_departure: datetime | None = None
    actual_arrival: datetime | None = None
    received_by_id: str | None = None
    sample_id: str | None = None
    sampling_equipment: str | None = Field(default=None, max_length=300)
    # §6.3.2 receipt: ambient conditions + condition of the sample at receipt
    ambient_conditions: str | None = Field(default=None, max_length=300)
    received_condition: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=4000)


class CustodyIn(BaseModel):
    from_user_id: str | None = None
    to_user_id: str | None = None
    from_location: str | None = Field(default=None, max_length=300)
    to_location: str | None = Field(default=None, max_length=300)
    transfer_reason: str | None = Field(default=None, max_length=1000)
    transfer_type: str | None = None
    sfr_id: str | None = None
    # §6.3.1: the condition of the sample confirmed at the transfer, and whether
    # it was found intact (a broken/compromised custody event is a MAJOR signal).
    sample_condition: str | None = Field(default=None, max_length=300)
    condition_ok: bool | None = None


def _rqs_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "rqs_number": r["rqs_number"],
        "qc_control_number": r.get("qc_control_number"), "material_code": r["material_code"],
        "material_name_en": r["material_name_en"], "material_name_mk": r["material_name_mk"],
        "batch_id": r["batch_id"], "originating_department": r["originating_department"],
        "assigned_sp_type": r["assigned_sp_type"], "status": r["status"],
        "num_samples": r.get("num_samples"), "required_tests": r.get("required_tests") or [],
        "priority": r.get("priority"), "priority_justification": r.get("priority_justification"),
        "storage_location": r.get("storage_location"), "material_status": r.get("material_status"),
        "specification_id": str(r["specification_id"]) if r.get("specification_id") else None,
        "spec_reference": r.get("spec_reference"), "release_related": r.get("release_related"),
        "requested_at": _iso(r["requested_at"]), "registered_at": _iso(r["registered_at"]),
        "registration_deadline": _iso(r["registration_deadline"]),
        "registration_window_met": r["registration_window_met"],
        "assigned_to_id": str(r["assigned_to_id"]) if r["assigned_to_id"] else None,
        "assigned_at": _iso(r["assigned_at"]), "completed_at": _iso(r["completed_at"]),
        "sample_id": str(r["sample_id"]) if r["sample_id"] else None,
        "cancellation_reason": r["cancellation_reason"], "notes": r["notes"],
    }


def _sfr_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "sfr_number": r["sfr_number"],
        "rqs_id": str(r["rqs_id"]) if r["rqs_id"] else None,
        "sampling_location": r["sampling_location"], "sampling_coordinates": r["sampling_coordinates"],
        "barrel_numbers": r["barrel_numbers"], "num_containers": r["num_containers"],
        "destination_facility": r["destination_facility"], "destination_location": r["destination_location"],
        "planned_departure": _iso(r["planned_departure"]), "actual_departure": _iso(r["actual_departure"]),
        "planned_arrival": _iso(r["planned_arrival"]), "actual_arrival": _iso(r["actual_arrival"]),
        "status": r["status"],
        "sampled_by_id": str(r["sampled_by_id"]) if r["sampled_by_id"] else None,
        "escort_id": str(r["escort_id"]) if r["escort_id"] else None,
        "received_by_id": str(r["received_by_id"]) if r["received_by_id"] else None,
        "sample_id": str(r["sample_id"]) if r["sample_id"] else None,
        "sampling_equipment": r.get("sampling_equipment"),
        "ambient_conditions": r.get("ambient_conditions"),
        "received_condition": r.get("received_condition"), "notes": r["notes"],
    }


def _custody_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "sample_id": str(r["sample_id"]),
        "from_user_id": str(r["from_user_id"]) if r["from_user_id"] else None,
        "to_user_id": str(r["to_user_id"]) if r["to_user_id"] else None,
        "transferred_at": _iso(r["transferred_at"]),
        "from_location": r["from_location"], "to_location": r["to_location"],
        "transfer_reason": r["transfer_reason"], "transfer_type": r["transfer_type"],
        "sample_condition": r.get("sample_condition"), "condition_ok": r.get("condition_ok"),
        "sfr_id": str(r["sfr_id"]) if r["sfr_id"] else None,
    }


# ── Sampling requests (RQS) ──────────────────────────────────────────────────
@router.get("/sampling-requests")
async def list_rqs(status: str | None = None, batch_id: str | None = None,
                   user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    if batch_id:
        args.append(batch_id); clauses.append(f"batch_id=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_sampling_requests{where} ORDER BY created_at DESC", *args)
    return [_rqs_out(dict(r)) for r in rows]


@router.get("/sampling-requests/{rqs_id}")
async def get_rqs(rqs_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(rqs_id, "Sampling request")
    async with rls(user) as c:
        row = await c.fetchrow("SELECT * FROM qc_sampling_requests WHERE id=$1", rqs_id)
        if row is None:
            raise HTTPException(404, "Sampling request not found")
    return _rqs_out(dict(row))


def _validate_rqs_fields(body):
    """Validate the §6.1.4 enumerated RQS fields (shared by create + patch)."""
    if body.required_tests is not None:
        bad = [t for t in body.required_tests if t not in _RQS_TESTS]
        if bad:
            raise HTTPException(422, f"unknown required_tests: {', '.join(map(str, bad))}"
                                     f" — allowed: {', '.join(_RQS_TESTS)}")
    if body.priority is not None and body.priority not in _RQS_PRIORITIES:
        raise HTTPException(422, f"priority must be one of: {', '.join(_RQS_PRIORITIES)}")
    if body.material_status is not None and body.material_status not in _RQS_MATERIAL_STATUSES:
        raise HTTPException(422, f"material_status must be one of: {', '.join(_RQS_MATERIAL_STATUSES)}")
    # §6.1.4: an URGENT request carries a written justification.
    if body.priority == "URGENT" and not (body.priority_justification or "").strip():
        raise HTTPException(422, "an URGENT request requires a written priority_justification (§6.1.4)")


@router.post("/sampling-requests", status_code=201)
async def create_rqs(body: RqsIn, user: dict = Depends(require_role(*_WRITERS))):
    _validate_rqs_fields(body)
    _uuid_or_422(body.specification_id, "specification_id")
    async with rls(user) as c:
        if body.specification_id:
            if await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1",
                                body.specification_id) is None:
                raise HTTPException(422, "Unknown specification")
        # §6.1.3 Request Ordinal PP-QC-F-001.A01/YYYY-NNN — per-year 3-digit,
        # reset on 01 January. The advisory xact-lock serialises concurrent
        # inserts for this org+year so NNN is gap-free; issued numbers are never
        # reused. Legacy PP-RQS-* rows don't match the pattern and are ignored.
        yr = await c.fetchval("SELECT to_char(now(),'YYYY')")
        await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"rqsord:{user['org_id']}:{yr}")
        seq = await c.fetchval(
            "SELECT coalesce(max((regexp_match(rqs_number, '-([0-9]+)$'))[1]::int), 0) + 1"
            " FROM qc_sampling_requests WHERE org_id=$1"
            " AND rqs_number LIKE 'PP-QC-F-001.A01/' || $2 || '-%'", user["org_id"], yr)
        rqs_number = f"PP-QC-F-001.A01/{yr}-{seq:03d}"
        row = await c.fetchrow(
            "INSERT INTO qc_sampling_requests(org_id, rqs_number, material_code, material_name_en,"
            " material_name_mk, batch_id, originating_department, assigned_sp_type, num_samples,"
            " required_tests, priority, priority_justification, storage_location, material_status,"
            " specification_id, spec_reference, release_related, notes, requested_by_id,"
            " registration_deadline, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,COALESCE($11,'ROUTINE'),$12,$13,$14,$15,$16,"
            "         $17,$18,$19, now() + interval '24 hours', $19,$19) RETURNING *",
            user["org_id"], rqs_number, body.material_code, body.material_name_en,
            body.material_name_mk, body.batch_id, body.originating_department, body.assigned_sp_type,
            body.num_samples, body.required_tests or [], body.priority, body.priority_justification,
            body.storage_location, body.material_status, body.specification_id, body.spec_reference,
            body.release_related, body.notes, user["id"])
    return _rqs_out(dict(row))


@router.patch("/sampling-requests/{rqs_id}")
async def update_rqs(rqs_id: str, body: RqsPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(rqs_id, "Sampling request")
    patch = body.model_dump(exclude_unset=True)
    _uuid_or_422(patch.get("assigned_to_id"), "assigned_to_id")
    _uuid_or_422(patch.get("sample_id"), "sample_id")
    _uuid_or_422(patch.get("specification_id"), "specification_id")
    _validate_rqs_fields(body)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT * FROM qc_sampling_requests WHERE id=$1", rqs_id)
        if cur is None:
            raise HTTPException(404, "Sampling request not found")
        if patch.get("sample_id"):
            if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", patch["sample_id"]) is None:
                raise HTTPException(422, "Unknown sample")
        if patch.get("specification_id"):
            if await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1",
                                patch["specification_id"]) is None:
                raise HTTPException(422, "Unknown specification")
        # the effective value of a mandatory field = this patch's value if it is
        # being set, else the value already on the record.
        def eff(col):
            return patch[col] if col in patch else cur[col]
        fields, args = [], []
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _RQS_STATUSES:
                raise HTTPException(422, "Unknown status")
            if target not in _RQS_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            args.append(target); fields.append(f"status=${len(args)}")
            if target == "REGISTERED":
                # §3 / §6.1.6 — registration into the MLL is a QC-Head act; a
                # release-related request (§6.1.2) escalates to the QP.
                if eff("release_related"):
                    if user["role"] not in _QP_ROLES:
                        raise HTTPException(403, "a release-related RQS is registered by the"
                                                 " Qualified Person (§6.1.2)")
                elif user["role"] not in _QC_REGISTRAR:
                    raise HTTPException(403, "RQS registration into the MLL is a QC function"
                                             " (QC Manager / QP) — §6.1.6")
                # §6.1.6(b) completeness gate — an incomplete RQS is not registered.
                missing = [m for m in _RQS_MANDATORY
                           if eff(m) in (None, "", []) or (m == "required_tests" and not eff(m))]
                if missing:
                    raise HTTPException(422, "RQS is incomplete — cannot register (§6.1.6):"
                                             f" missing {', '.join(missing)}")
                # §6.1.1/§6.1.6 — assign the QC Internal Control Number NNN/YY_RQS
                # in the MLL (per-year, advisory-locked, gap-free).
                yy = await c.fetchval("SELECT to_char(now(),'YY')")
                await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))",
                                f"rqsctl:{user['org_id']}:{yy}")
                cseq = await c.fetchval(
                    "SELECT coalesce(max((regexp_match(qc_control_number, '^([0-9]+)/'))[1]::int), 0) + 1"
                    " FROM qc_sampling_requests WHERE org_id=$1"
                    " AND qc_control_number LIKE '%/' || $2 || '_RQS'", user["org_id"], yy)
                args.append(f"{cseq:03d}/{yy}_RQS"); fields.append(f"qc_control_number=${len(args)}")
                args.append(user["id"]); fields.append(f"registered_by_id=${len(args)}")
                fields.append("registered_at=now()")
                # window met iff QC registered on/before the 24-hour deadline
                fields.append("registration_window_met=(now() <= registration_deadline)")
            elif target == "IN_PROGRESS":
                fields.append("assigned_at=now()")
                if not patch.get("assigned_to_id"):
                    args.append(user["id"]); fields.append(f"assigned_to_id=${len(args)}")
            elif target == "COMPLETED":
                fields.append("completed_at=now()")
            elif target == "CANCELLED":
                args.append(user["id"]); fields.append(f"cancelled_by_id=${len(args)}")
                fields.append("cancelled_at=now()")
        # editable columns — the §6.1.4 fields plus assignment/notes. jsonb
        # required_tests passes straight through the global codec.
        _NULLABLE = {"assigned_sp_type", "cancellation_reason", "notes", "assigned_to_id",
                     "sample_id", "num_samples", "priority_justification", "storage_location",
                     "material_status", "specification_id", "spec_reference"}
        for col in ("assigned_sp_type", "assigned_to_id", "sample_id", "cancellation_reason",
                    "notes", "num_samples", "required_tests", "priority", "priority_justification",
                    "storage_location", "material_status", "specification_id", "spec_reference",
                    "release_related"):
            if col in patch and (patch[col] is not None or col in _NULLABLE):
                args.append(patch[col]); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(rqs_id)
        row = await c.fetchrow(
            f"UPDATE qc_sampling_requests SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
    return _rqs_out(dict(row))


# ── Sample field records (SFR) ───────────────────────────────────────────────
@router.get("/field-records")
async def list_sfr(status: str | None = None, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_sample_field_records{where} ORDER BY created_at DESC", *args)
    return [_sfr_out(dict(r)) for r in rows]


@router.get("/field-records/{sfr_id}")
async def get_sfr(sfr_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(sfr_id, "Field record")
    async with rls(user) as c:
        row = await c.fetchrow("SELECT * FROM qc_sample_field_records WHERE id=$1", sfr_id)
        if row is None:
            raise HTTPException(404, "Field record not found")
    return _sfr_out(dict(row))


@router.post("/field-records", status_code=201)
async def create_sfr(body: SfrIn, user: dict = Depends(require_role(*_WRITERS))):
    for _f in ("rqs_id", "sample_id", "sampled_by_id", "escort_id"):
        _uuid_or_422(getattr(body, _f), _f)
    async with rls(user) as c:
        # §6.1.1 (MAJOR) — a sampling act may not be recorded without a
        # REGISTERED, accepted RQS. The linked RQS must exist and be past OPEN
        # (registered in the MLL), and not cancelled.
        rqs = await c.fetchrow(
            "SELECT status FROM qc_sampling_requests WHERE id=$1", body.rqs_id)
        if rqs is None:
            raise HTTPException(422, "Unknown sampling request")
        if rqs["status"] not in _RQS_REGISTERED:
            raise HTTPException(409, "the sampling request is not registered — no sampling may"
                                     " commence without a registered RQS (QCSOP 011 §6.1.1)")
        if body.sample_id:
            if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", body.sample_id) is None:
                raise HTTPException(422, "Unknown sample")
        row = await c.fetchrow(
            "INSERT INTO qc_sample_field_records(org_id, sfr_number, rqs_id, sampling_location,"
            " sampling_coordinates, barrel_numbers, num_containers, destination_facility,"
            " destination_location, planned_departure, planned_arrival, sampled_by_id, escort_id,"
            " sample_id, sampling_equipment, notes, created_by, updated_by)"
            " VALUES ($1, 'PP-SFR-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_sfr_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$16) RETURNING *",
            user["org_id"], body.rqs_id, body.sampling_location, body.sampling_coordinates,
            body.barrel_numbers, body.num_containers, body.destination_facility,
            body.destination_location, body.planned_departure, body.planned_arrival,
            body.sampled_by_id, body.escort_id, body.sample_id, body.sampling_equipment,
            body.notes, user["id"])
    return _sfr_out(dict(row))


@router.patch("/field-records/{sfr_id}")
async def update_sfr(sfr_id: str, body: SfrPatch, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(sfr_id, "Field record")
    patch = body.model_dump(exclude_unset=True)
    _uuid_or_422(patch.get("sample_id"), "sample_id")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_sample_field_records WHERE id=$1", sfr_id)
        if cur is None:
            raise HTTPException(404, "Field record not found")
        _uuid_or_422(patch.get("received_by_id"), "received_by_id")
        if patch.get("sample_id"):
            if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", patch["sample_id"]) is None:
                raise HTTPException(422, "Unknown sample")
        fields, args = [], []
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _SFR_STATUSES:
                raise HTTPException(422, "Unknown status")
            if target not in _SFR_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            args.append(target); fields.append(f"status=${len(args)}")
        _NULLABLE = {"received_by_id", "sample_id", "notes",
                     "sampling_equipment", "ambient_conditions", "received_condition"}
        for col in ("actual_departure", "actual_arrival", "received_by_id", "sample_id", "notes",
                    "sampling_equipment", "ambient_conditions", "received_condition"):
            if col in patch and (patch[col] is not None or col in _NULLABLE):
                args.append(patch[col]); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(sfr_id)
        row = await c.fetchrow(
            f"UPDATE qc_sample_field_records SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
    return _sfr_out(dict(row))


# ── Chain of custody (per-sample, append-only) ───────────────────────────────
@router.get("/samples/{sample_id}/custody")
async def list_custody(sample_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(sample_id, "Sample")
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", sample_id) is None:
            raise HTTPException(404, "Sample not found")
        rows = await c.fetch(
            "SELECT * FROM qc_chain_of_custody WHERE sample_id=$1 ORDER BY transferred_at", sample_id)
    return [_custody_out(dict(r)) for r in rows]


@router.post("/samples/{sample_id}/custody", status_code=201)
async def add_custody(sample_id: str, body: CustodyIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.transfer_type is not None and body.transfer_type not in _TRANSFER_TYPES:
        raise HTTPException(422, f"transfer_type must be one of: {', '.join(_TRANSFER_TYPES)}")
    _uuid_or_404(sample_id, "Sample")
    for _f in ("from_user_id", "to_user_id", "sfr_id"):
        _uuid_or_422(getattr(body, _f), _f)
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", sample_id) is None:
            raise HTTPException(404, "Sample not found")
        if body.sfr_id:
            if await c.fetchrow("SELECT id FROM qc_sample_field_records WHERE id=$1", body.sfr_id) is None:
                raise HTTPException(422, "Unknown field record")
        row = await c.fetchrow(
            "INSERT INTO qc_chain_of_custody(org_id, sample_id, from_user_id, to_user_id,"
            " from_location, to_location, transfer_reason, transfer_type, sfr_id,"
            " sample_condition, condition_ok, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING *",
            user["org_id"], sample_id, body.from_user_id or user["id"], body.to_user_id,
            body.from_location, body.to_location, body.transfer_reason, body.transfer_type,
            body.sfr_id, body.sample_condition, body.condition_ok, user["id"])
    return _custody_out(dict(row))


# ── QC leaves (U6) — water tests, stability studies, sample transports ───────
# Three self-contained record types with no cross-dependencies. Water QC
# (PP-QC-SOP-014), the stability programme (QCSOP 018), and external-lab sample
# transport (PP-QC-SOP-012). The variable measured-parameter sets live in jsonb.
_WATER_GRADES = ("TW", "BW", "TR", "RO")
_STAB_TYPES = ("LT", "ACC", "INT")
_STAB_STATUSES = ("IN_PROGRESS", "CLOSED")
_TRN_STATUSES = ("draft", "in_transit", "received")


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


# Water tests
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


# Stability studies
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
    patch = body.model_dump(exclude_unset=True)
    if "status" in patch and patch["status"] is not None and patch["status"] not in _STAB_STATUSES:
        raise HTTPException(422, f"status must be one of: {', '.join(_STAB_STATUSES)}")
    fields, args = _patch_update(patch, {"protocol", "schedule", "report", "shelf_life", "notes"})
    if not fields:
        return {"ok": True, "noop": True}
    args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
    args.append(sid)
    async with rls(user) as c:
        row = await c.fetchrow(
            f"UPDATE qc_stability_studies SET {', '.join(fields)}, updated_at=now() WHERE id=${len(args)} RETURNING *", *args)
        if row is None:
            raise HTTPException(404, "Stability study not found")
    return _stab_out(dict(row))


# Sample transports
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
    patch = body.model_dump(exclude_unset=True)
    if "status" in patch and patch["status"] is not None and patch["status"] not in _TRN_STATUSES:
        raise HTTPException(422, f"status must be one of: {', '.join(_TRN_STATUSES)}")
    fields, args = _patch_update(
        patch, {"external_lab", "tracking", "notes"}, {"shipped_date", "expected_date"})
    if not fields:
        return {"ok": True, "noop": True}
    args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
    args.append(tid)
    async with rls(user) as c:
        row = await c.fetchrow(
            f"UPDATE qc_sample_transports SET {', '.join(fields)}, updated_at=now() WHERE id=${len(args)} RETURNING *", *args)
        if row is None:
            raise HTTPException(404, "Transport not found")
    return _trn_out(dict(row))


# ── RAG Q&A over ingested CoAs (Phase 3 U4) ─────────────────────────────────
# An ingested CoA (U2) is chunked into qc_coa_chunks; a Postgres full-text
# tsvector makes the chunks searchable. `coa-qa` retrieves the top-ranked
# passages for a question and returns them CITED (doc_number + chunk_index).
# GxP: the answer is grounded strictly in retrieved document text — the server
# never invents an answer. Semantic synthesis (if wanted) is the DocEngine /
# Letta fleet's job over these cited passages, not fabricated here.
class ChunksIn(BaseModel):
    # list[str] or list[{content, chunk_index?}]; capped so one (re)index can't
    # drive an unbounded INSERT loop in a single transaction.
    chunks: list = Field(default_factory=list, max_length=2000)


class QaIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


def _chunk_out(r: dict) -> dict:
    return {"id": str(r["id"]), "document_id": str(r["document_id"]),
            "chunk_index": r["chunk_index"], "content": r["content"]}


@router.get("/coa-documents/{doc_id}/chunks")
async def list_chunks(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id) is None:
            raise HTTPException(404, "eCoA document not found")
        rows = await c.fetch(
            "SELECT * FROM qc_coa_chunks WHERE document_id=$1 ORDER BY chunk_index", doc_id)
    return [_chunk_out(dict(r)) for r in rows]


@router.post("/coa-documents/{doc_id}/chunks", status_code=201)
async def index_chunks(doc_id: str, body: ChunksIn, user: dict = Depends(require_role(*_WRITERS))):
    """(Re)index a document's text chunks for retrieval. Replaces any existing
    chunks for the document so re-indexing is idempotent."""
    norm = []
    for i, ch in enumerate(body.chunks):
        if isinstance(ch, str):
            content, idx = ch, i
        elif isinstance(ch, dict):
            content, idx = ch.get("content") or "", ch.get("chunk_index", i)
        else:
            continue
        content = str(content).strip()
        if content:
            norm.append((idx, content))
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id) is None:
            raise HTTPException(404, "eCoA document not found")
        await c.execute("DELETE FROM qc_coa_chunks WHERE document_id=$1", doc_id)
        for idx, content in norm:
            await c.execute(
                "INSERT INTO qc_coa_chunks(org_id, document_id, chunk_index, content, created_by)"
                " VALUES ($1,$2,$3,$4,$5)", user["org_id"], doc_id, idx, content, user["id"])
    return {"document_id": doc_id, "indexed": len(norm)}


@router.post("/coa-qa")
async def coa_qa(body: QaIn, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Retrieve the top-ranked CoA passages for a question (full-text), org-scoped
    (and document-scoped if `document_id` is given). Returns the cited passages
    and a grounded answer assembled strictly from them — never fabricated."""
    args = [body.question]
    doc_clause = ""
    if body.document_id:
        args.append(body.document_id)
        doc_clause = f" AND ch.document_id=${len(args)}"
    args.append(body.top_k)
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT ch.document_id, ch.chunk_index, ch.content, d.doc_number,"
            " ts_rank(ch.tsv, websearch_to_tsquery('english', $1)) AS score"
            " FROM qc_coa_chunks ch JOIN qc_coa_documents d ON d.id = ch.document_id"
            " WHERE ch.tsv @@ websearch_to_tsquery('english', $1)" + doc_clause +
            f" ORDER BY score DESC, ch.chunk_index LIMIT ${len(args)}", *args)
    passages = [{"document_id": str(r["document_id"]), "doc_number": r["doc_number"],
                 "chunk_index": r["chunk_index"], "content": r["content"],
                 "score": round(float(r["score"]), 4)} for r in rows]
    # Grounded answer: the retrieved passages themselves (cited), never invented.
    if passages:
        answer = "\n\n".join(f"[{p['doc_number']}#{p['chunk_index']}] {p['content']}" for p in passages[:3])
    else:
        answer = ""
    return {"question": body.question, "grounded": bool(passages),
            "answer": answer, "passages": passages}
