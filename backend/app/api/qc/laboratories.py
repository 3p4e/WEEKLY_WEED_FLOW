from app.db import rls
from app.worktime import SITE_YEAR_SQL
from app.deps import require_role
from app.roles import ELEVATED_ROLES
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .common import _WRITERS, _uuid_or_404, router


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
            f" VALUES ($1, 'PP-LAB-' || {SITE_YEAR_SQL} || '-' ||"  # nosec B608 — SITE_YEAR_SQL is a trusted constant
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
