from app.db import rls
from app.worktime import SITE_YEAR_SQL
from app.deps import require_role
from app.roles import ELEVATED_ROLES
from datetime import datetime
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _QC_REGISTRAR, _QP_ROLES, _WRITERS, _uuid_or_404, _uuid_or_422, router


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


_RQS_TESTS = ("POTENCY", "LOD", "FM", "MICRO", "HEAVY_METALS", "PESTICIDES",
              "MYCOTOXINS", "OTHER")


_RQS_PRIORITIES = ("ROUTINE", "URGENT")


_RQS_MATERIAL_STATUSES = ("QUARANTINE", "IN_PROCESS", "OTHER")


_RQS_MANDATORY = ("batch_id", "num_samples", "required_tests", "storage_location",
                  "material_status", "spec_reference")


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
        yr = await c.fetchval(f"SELECT {SITE_YEAR_SQL}")  # facility year, not UTC  # nosec B608
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
        # §6.1.2 segregation of duties — the release-related flag is what forces
        # QP registration, so a non-QP writer must not be able to LOWER it (which
        # would demote the request out of the QP's remit). Raising it is fine.
        if (patch.get("release_related") is False and cur["release_related"]
                and user["role"] not in _QP_ROLES):
            raise HTTPException(403, "only the Qualified Person may clear the release-related"
                                     " flag on a sampling request (§6.1.2)")
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
                # release-related request (§6.1.2) escalates to the QP. Evaluate
                # the flag against the current OR patched value so it cannot be
                # dropped in the same PATCH to dodge the escalation.
                if cur["release_related"] or eff("release_related"):
                    if user["role"] not in _QP_ROLES:
                        raise HTTPException(403, "a release-related RQS is registered by the"
                                                 " Qualified Person (§6.1.2)")
                elif user["role"] not in _QC_REGISTRAR:
                    raise HTTPException(403, "RQS registration into the MLL is a QC function"
                                             " (QC Manager / QP) — §6.1.6")
                # §6.1.6(b) completeness gate — an incomplete RQS is not
                # registered. A blank value is null, empty, or whitespace-only;
                # the sample count must be a positive integer.
                def _blank(v):
                    if v is None or v == [] or v == {}:
                        return True
                    return isinstance(v, str) and not v.strip()
                missing = [m for m in _RQS_MANDATORY if _blank(eff(m))]
                if "num_samples" not in missing and (eff("num_samples") or 0) <= 0:
                    missing.append("num_samples")
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
                    # the literal underscore is escaped so LIKE treats it as a
                    # character, not the single-char wildcard.
                    " AND qc_control_number LIKE '%/' || $2 || '\\_RQS'", user["org_id"], yy)
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
            f" VALUES ($1, 'PP-SFR-' || {SITE_YEAR_SQL} || '-' ||"  # nosec B608 — SITE_YEAR_SQL is a trusted constant
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


@router.get("/samples/{sample_id}/custody")
async def list_custody(sample_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(sample_id, "Sample")
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", sample_id) is None:
            raise HTTPException(404, "Sample not found")
        rows = await c.fetch(
            "SELECT * FROM qc_chain_of_custody WHERE sample_id=$1 ORDER BY transferred_at", sample_id)
    return [_custody_out(dict(r)) for r in rows]


def _norm_loc(s: str | None) -> str:
    """Fold a custody location for comparison — same idiom as ecoa._norm_label.
    Both sides are free text typed by different people in the field and in the
    lab, so case and internal whitespace must not manufacture a chain break."""
    return " ".join((s or "").split()).lower()


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
        # A custody entry with neither a recipient nor a location is "transferred
        # to nobody, nowhere" — it records no destination at all. The continuity
        # guard below trusts the PREVIOUS entry's to_user_id/to_location to
        # anchor the NEXT entry's declared origin; a vacuous entry makes both
        # halves of that check no-op (both previous values are falsy), so the
        # entry after a vacuous one could declare any origin unchecked — exactly
        # the gap-in-the-chain this guard exists to close. At least one of the
        # two is required; which one is a legitimate domain choice (e.g. an
        # internal same-location handoff between people needs only to_user_id, a
        # location-only drop needs only to_location), so both are not required.
        if body.to_user_id is None and body.to_location is None:
            raise HTTPException(422, "a custody transfer must record a destination — at minimum a"
                                     " recipient or a location")
        if body.sfr_id:
            if await c.fetchrow("SELECT id FROM qc_sample_field_records WHERE id=$1", body.sfr_id) is None:
                raise HTTPException(422, "Unknown field record")
        from_user = body.from_user_id or user["id"]
        # Serialize custody writes per-sample: the continuity check below reads
        # the chain's last entry, then the INSERT commits a new one — two
        # concurrent transfers would each see the same pre-insert last entry
        # and could both pass the continuity check (same pattern as the
        # genealogy cycle-check / cert numbering elsewhere in this package).
        await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"custody:{user['org_id']}:{sample_id}")
        # Append-only continuity, on BOTH axes — who held it and where it was.
        prev = await c.fetchrow(
            "SELECT to_user_id, to_location FROM qc_chain_of_custody WHERE sample_id=$1"
            " ORDER BY transferred_at DESC LIMIT 1", sample_id)
        if prev is not None:
            # WHO — this handoff must start with whoever the chain last
            # recorded as having custody, or a transfer silently skips a
            # custodian (a break in the field-to-lab chain).
            if prev["to_user_id"] is not None:
                if str(prev["to_user_id"]) != str(from_user):
                    raise HTTPException(
                        409, "Custody continuity broken: the last recorded transfer for this"
                             " sample ended with a different custodian than this entry's"
                             " from_user_id")
            # to_user_id is optional (a sample can be left at a place rather
            # than handed to a person), and that used to mean NO check ran at
            # all — so a chain could drop personal custody entirely just by
            # omitting it. An entry that ended at a place must at least be
            # continued FROM that place.
            elif prev["to_location"] and not body.from_location:
                raise HTTPException(
                    409, f"Custody continuity broken: the sample was last left at"
                         f" '{prev['to_location']}' with no named custodian — this entry must"
                         f" state the from_location it is being collected from")
            # WHERE — independently of who: a stated origin must match where
            # the sample was actually last left. Never checked before.
            if (prev["to_location"] and body.from_location
                    and _norm_loc(body.from_location) != _norm_loc(prev["to_location"])):
                raise HTTPException(
                    409, f"Custody continuity broken: the sample was last left at"
                         f" '{prev['to_location']}', not '{body.from_location}'")
        row = await c.fetchrow(
            "INSERT INTO qc_chain_of_custody(org_id, sample_id, from_user_id, to_user_id,"
            " from_location, to_location, transfer_reason, transfer_type, sfr_id,"
            " sample_condition, condition_ok, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING *",
            user["org_id"], sample_id, from_user, body.to_user_id,
            body.from_location, body.to_location, body.transfer_reason, body.transfer_type,
            body.sfr_id, body.sample_condition, body.condition_ok, user["id"])
    return _custody_out(dict(row))
