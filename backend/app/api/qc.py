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
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import docengine
from app.db import rls
from app.deps import require_role
from app.notify import emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/qc", tags=["qc"])

# QC manager owns the domain; QP certifies; execs + ADMIN org-wide.
_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "QC_MGR", "QP")
# Release / reject are a Qualified-Person decision (Annex 16) — narrower gate.
_QP_ROLES = (ADMIN, *EXECUTIVE_ROLES, "QP")

_SPEC_STATUSES = (
    "INITIATED", "DRAFT", "QC_REVIEW", "QA_APPROVED", "NUMBERED",
    "TRAINED", "ACTIVE", "UNDER_CHANGE", "SUPERSEDED", "WITHDRAWN",
)
_THC_GRADES = ("GRADE_I", "GRADE_II", "GRADE_III", "GRADE_IV", "GRADE_V")

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
    patch = body.model_dump(exclude_unset=True)
    _check_grade(patch.get("thc_grade"))
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_specifications WHERE id=$1", spec_id)
        if cur is None:
            raise HTTPException(404, "Specification not found")
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
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT status FROM qc_specifications WHERE id=$1", spec_id)
        if spec is None:
            raise HTTPException(404, "Specification not found")
        if spec["status"] not in _EDITABLE_STATUSES:
            raise HTTPException(409, f"Parameters may only change while the spec is being authored"
                                     f" ({', '.join(sorted(_EDITABLE_STATUSES))})")
        row = await c.fetchrow(
            "INSERT INTO qc_spec_parameters(org_id, spec_id, test_name_en, test_name_mk,"
            " test_method, spec_type, lower_limit, upper_limit, unit, pharmacopoeia_ref,"
            " test_location, sorting_order, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING *",
            user["org_id"], spec_id, body.test_name_en, body.test_name_mk, body.test_method,
            body.spec_type, body.lower_limit, body.upper_limit, body.unit, body.pharmacopoeia_ref,
            body.test_location, body.sorting_order, user["id"])
    return _param_out(dict(row))


@router.delete("/specifications/{spec_id}/parameters/{param_id}")
async def delete_parameter(spec_id: str, param_id: str, user: dict = Depends(require_role(*_WRITERS))):
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
    parent_id: str | None = None
    sampling_plan_id: str | None = None
    notes: str | None = Field(default=None, max_length=2000)


class SamplePatch(BaseModel):
    location: str | None = Field(default=None, max_length=200)
    quantity: float | None = None
    quantity_unit: str | None = Field(default=None, max_length=40)
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
    async with rls(user) as c:
        s = await c.fetchrow("SELECT * FROM qc_samples WHERE id=$1", sample_id)
        if s is None:
            raise HTTPException(404, "Sample not found")
        kids = await c.fetch(
            "SELECT * FROM qc_samples WHERE parent_id=$1 ORDER BY created_at", sample_id)
    return {"sample": _sample_out(dict(s)), "children": [_sample_out(dict(k)) for k in kids]}


@router.post("/samples", status_code=201)
async def create_sample(body: SampleIn, user: dict = Depends(require_role(*_WRITERS))):
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
            " retention_sample, parent_id, sampling_plan_id, notes, created_by, updated_by)"
            " VALUES ($1, 'PP-SMP-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_sample_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7::date,$8,$9,$10,$11,$12,$13,$14,$15,$15) RETURNING *",
            user["org_id"], body.batch_id, body.material_code, body.sample_type,
            body.material_name_en, body.material_name_mk, body.sampling_date, body.location,
            body.quantity, body.quantity_unit, body.retention_sample, body.parent_id,
            body.sampling_plan_id, body.notes, user["id"])
        try:
            await emit(c, user, verb="sample_collected", object_type="qc_sample",
                       object_id=row["id"], recipients=[],
                       params={"sample_id": row["sample_id"], "batch_id": row["batch_id"]})
        except Exception:
            pass
    return _sample_out(dict(row))


@router.patch("/samples/{sample_id}")
async def update_sample(sample_id: str, body: SamplePatch, user: dict = Depends(require_role(*_WRITERS))):
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
        fields, args = [], []
        _NULLABLE = {"location", "quantity", "quantity_unit", "notes"}
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
# QC LIMS U3 — certificates of analysis + test results (certification cluster)
# ════════════════════════════════════════════════════════════════════════════
_COA_STATUSES = ("DRAFT", "REVIEWED", "APPROVED", "RELEASED")
_CERT_TYPES = ("ICOA", "ECOA", "COQ", "WATER", "OTHER")
# CoA lifecycle: author → second-person review → QP approve → release.
_COA_TRANSITIONS = {
    "DRAFT": {"REVIEWED"},
    "REVIEWED": {"APPROVED", "DRAFT"},   # kick back to DRAFT on review findings
    "APPROVED": {"RELEASED"},
    "RELEASED": set(),
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
    notes: str | None = Field(default=None, max_length=4000)


class CoaPatch(BaseModel):
    source_lab: str | None = Field(default=None, max_length=200)
    report_date: date | None = None
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


def _coa_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coa_number": r["coa_number"], "batch_id": r["batch_id"],
        "specification_id": str(r["specification_id"]),
        "sample_id": str(r["sample_id"]) if r["sample_id"] else None,
        "report_date": r["report_date"].isoformat() if r["report_date"] else None,
        "status": r["status"], "decision": r["decision"], "cert_type": r["cert_type"],
        "source_lab": r["source_lab"],
        "analyst_id": str(r["analyst_id"]) if r["analyst_id"] else None,
        "reviewer_id": str(r["reviewer_id"]) if r["reviewer_id"] else None,
        "approver_id": str(r["approver_id"]) if r["approver_id"] else None,
        "coq_document_id": r["coq_document_id"],
        "coq_generated_at": r["coq_generated_at"].isoformat() if r["coq_generated_at"] else None,
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
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", coa_id)
    return {"coa": _coa_out(dict(coa)), "results": [_result_out(dict(r)) for r in results]}


@router.post("/certificates", status_code=201)
async def create_coa(body: CoaIn, user: dict = Depends(require_role(*_WRITERS))):
    if body.cert_type not in _CERT_TYPES:
        raise HTTPException(422, f"cert_type must be one of: {', '.join(_CERT_TYPES)}")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1", body.specification_id)
        if spec is None:
            raise HTTPException(422, "Unknown specification")
        if body.sample_id:
            s = await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", body.sample_id)
            if s is None:
                raise HTTPException(422, "Unknown sample")
        row = await c.fetchrow(
            "INSERT INTO qc_certificates(org_id, coa_number, batch_id, specification_id, sample_id,"
            " cert_type, report_date, source_lab, notes, analyst_id, created_by, updated_by)"
            " VALUES ($1, 'PP-COA-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_coa_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6::date,$7,$8,$9,$9,$9) RETURNING *",
            user["org_id"], body.batch_id, body.specification_id, body.sample_id, body.cert_type,
            body.report_date, body.source_lab, body.notes, user["id"])
    return _coa_out(dict(row))


@router.post("/certificates/{coa_id}/results", status_code=201)
async def add_result(coa_id: str, body: ResultIn, user: dict = Depends(require_role(*_WRITERS))):
    """Record a measured result. `complies` is computed from the numeric value
    vs the limits — never typed by hand. If the result FAILS and the CoA links
    a sample that is still in a testable state, the sample is quarantined (the
    OOS hook). Results may only be entered while the CoA is DRAFT."""
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT id, status, sample_id FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        if coa["status"] != "DRAFT":
            raise HTTPException(409, "Results may only be entered while the CoA is DRAFT")
        lo, hi = body.lower_limit, body.upper_limit
        # If a spec parameter is cited and limits weren't supplied, snapshot the
        # parameter's limits (the spec is the single source of truth).
        if body.parameter_id and lo is None and hi is None:
            p = await c.fetchrow(
                "SELECT lower_limit, upper_limit, unit FROM qc_spec_parameters WHERE id=$1",
                body.parameter_id)
            if p is not None:
                lo = float(p["lower_limit"]) if p["lower_limit"] is not None else None
                hi = float(p["upper_limit"]) if p["upper_limit"] is not None else None
        complies, status = _evaluate(body.result_numeric, lo, hi)
        row = await c.fetchrow(
            "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value,"
            " result_numeric, unit, lower_limit, upper_limit, complies, status, analyst_id,"
            " result_date, source_document_code, source_document_date, source_institution, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$12) RETURNING *",
            user["org_id"], coa_id, body.parameter_id, body.test_name, body.result_value,
            body.result_numeric, body.unit, lo, hi, complies, status, user["id"], body.result_date,
            body.source_document_code, body.source_document_date, body.source_institution)
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
    patch = body.model_dump(exclude_unset=True)
    if "decision" in patch and patch["decision"] is not None and patch["decision"] not in ("PASS", "FAIL"):
        raise HTTPException(422, "decision must be PASS or FAIL")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status, analyst_id FROM qc_certificates WHERE id=$1", coa_id)
        if cur is None:
            raise HTTPException(404, "Certificate not found")
        extra_sql, extra_args = [], []
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _COA_STATUSES:
                raise HTTPException(422, "Unknown status")
            if target not in _COA_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            if target in _COA_QP_TARGETS and user["role"] not in _QP_ROLES:
                raise HTTPException(403, f"{target} is a Qualified-Person decision")
            # GxP second-person review: the reviewer must not be the analyst who
            # entered the results.
            if target == "REVIEWED":
                if cur["analyst_id"] and str(cur["analyst_id"]) == str(user["id"]):
                    raise HTTPException(403, "The reviewer must be a different person than the analyst")
                extra_args.append(user["id"]); extra_sql.append(f"reviewer_id=${'PLACEHOLDER'}")
            if target == "APPROVED":
                extra_args.append(user["id"]); extra_sql.append(f"approver_id=${'PLACEHOLDER'}")
        fields, args = [], []
        _NULLABLE = {"source_lab", "report_date", "notes", "decision"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            if col == "report_date":
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


def _coq_markdown(coa: dict, spec: dict, params_by_id: dict, results: list) -> str:
    """Assemble the Certificate of Quality as DocEngine bilingual Markdown
    (doctype: FORM → the annex renderer: navy banners, [[FORM:grid]] metadata,
    [[TABLE]] results). Every result line carries its source document. House
    wording is 'MK GMP Certified Facility' (never 'EU GMP'); no value is
    fabricated — an unknown result renders '—'."""
    c = _coq_cell
    material = f"{spec.get('material_name_mk') or ''} / {spec.get('material_name_en') or spec.get('material_code') or ''}"
    decision = coa.get("decision") or ""
    v_mk = "СЕРИЈАТА ЗАДОВОЛУВА" if decision == "PASS" else "СЕРИЈАТА НЕ ЗАДОВОЛУВА"
    v_en = "This batch CONFORMS" if decision == "PASS" else "This batch does NOT conform"
    head = ("<!--HEADERDATA\n"
            "doctype: FORM\n"
            f"code: {c(coa['coa_number'])}\n"
            "version: 01\n"
            "mk_title: Сертификат за квалитет\n"
            "en_title: Certificate of Quality\n"
            "-->\n\n")
    title = "# Сертификат за квалитет|Certificate of Quality\n\n"
    def frow(mk, en, val):
        return f"{mk}~~{en} ||| {c(val)}\n"
    grid = ("[[FORM:grid]]\n"
            + frow("Број на сертификат", "Certificate number", coa["coa_number"])
            + frow("Серија", "Batch", coa["batch_id"])
            + frow("Материјал", "Material", material)
            + frow("Спецификација", "Specification", spec.get("spec_id"))
            + frow("Датум на извештај", "Report date", coa.get("report_date") or "")
            + frow("Извор (лабораторија)", "Source lab", coa.get("source_lab") or "")
            + frow("Одлука", "Disposition", f"{v_mk} / {v_en}")
            + "[[/FORM]]\n\n")
    tbl = ("[[TABLE:data]]\n"
           "Тест~~Test ||| Метод~~Method ||| Граници~~Acceptance ||| "
           "Резултат~~Result ||| Статус~~Status ||| Извор~~Source\n")
    for r in results:
        p = params_by_id.get(str(r.get("parameter_id"))) or {}
        lo, hi = r.get("lower_limit"), r.get("upper_limit")
        limits = "—" if lo is None and hi is None else \
            f"{'' if lo is None else lo} … {'' if hi is None else hi}"
        val = r.get("result_value") or ("" if r.get("result_numeric") is None
                                        else str(r["result_numeric"]))
        val = (f"{val} {r.get('unit') or ''}").strip() or "—"
        st = {True: "PASS", False: "OOS"}.get(r.get("complies"), "—")
        src = r.get("source_document_code") or r.get("source_institution") \
            or coa.get("source_lab") or "—"
        tbl += (f"{c(r.get('test_name'))} ||| {c(p.get('test_method') or '')} ||| "
                f"{c(limits)} ||| {c(val)} ||| {st} ||| {c(src)}\n")
    tbl += "[[/TABLE]]\n\n"
    conform = f"**{v_mk}** според одобрената спецификација.|||**{v_en}** against the approved specification.\n\n"
    footer = "МК ГМП сертифицирано постројение|||MK GMP Certified Facility\n"
    return head + title + grid + tbl + conform + footer


@router.post("/certificates/{coa_id}/coq", status_code=201)
async def generate_coq(coa_id: str, user: dict = Depends(require_role(*_QP_ROLES))):
    """Render a Certificate of Quality (.docx) from a RELEASED certificate via
    the DocEngine's PASS-gated formatter. Data gate: every result must comply
    (a FAIL or unmeasured result blocks). Certifying is a QP act."""
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        if coa["status"] != "RELEASED":
            raise HTTPException(409, "A COQ is issued only from a RELEASED certificate")
        spec = await c.fetchrow("SELECT * FROM qc_specifications WHERE id=$1",
                                coa["specification_id"])
        params = await c.fetch(
            "SELECT * FROM qc_spec_parameters WHERE spec_id=$1", coa["specification_id"])
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", coa_id)
    if not results:
        raise HTTPException(409, "The certificate has no results to certify")
    # GxP data gate: never issue a conformant COQ over a FAIL or an unmeasured
    # (complies is None → 'unknown') result.
    unmet = [r for r in results if r["complies"] is not True]
    if unmet:
        raise HTTPException(
            409, f"{len(unmet)} result(s) do not comply or are unmeasured — cannot certify")
    params_by_id = {str(p["id"]): dict(p) for p in params}
    md = _coq_markdown(dict(coa), dict(spec) if spec else {}, params_by_id,
                       [dict(r) for r in results])
    # DocEngine build (house-style PASS gate). A pp_verify FAIL surfaces as 422.
    build = (await docengine.de_forward(
        "POST", "/build",
        {"markdown": md, "out_name": coa["coa_number"],
         "meta": {"code": coa["coa_number"], "title_mk": "Сертификат за квалитет",
                  "title_en": "Certificate of Quality", "version": "01"}},
        timeout=120.0, client_factory=_coq_client)).json()
    doc_id = build.get("document_id")
    async with rls(user) as c:
        await c.execute(
            "UPDATE qc_certificates SET coq_document_id=$1, coq_generated_at=now(),"
            " updated_by=$2, updated_at=now() WHERE id=$3", doc_id, user["id"], coa_id)
        try:
            await emit(c, user, verb="coq_generated", object_type="qc_certificate",
                       object_id=coa_id, recipients=[],
                       params={"coa_number": coa["coa_number"], "document_id": doc_id})
        except Exception:
            pass
    return {"coa_number": coa["coa_number"], "document_id": doc_id,
            "verify": build.get("verify"), "bytes": build.get("bytes")}


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
