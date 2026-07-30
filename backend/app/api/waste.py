"""Destruction / waste manifests — the reconciliation record (migration 0048).

Destruction is the one phase transition where the material stops being auditable
afterwards. A missing harvest record can be reconstructed from the lot; a missing
destruction record cannot be reconstructed from anything, which is why the design
doc (§5c) calls this the regulatory invariant and why the gates below are refusals
rather than warnings.

Access model:
  read     — every role above USER (ELEVATED_ROLES);
  record   — draft a manifest, add/remove lines, seal it, close it out against
             the carrier reference: cultivation crew (CU_MGR) + executives +
             ADMIN. They are the people physically loading the consignment;
  witness  — QA_MGR + executives + ADMIN, and NEVER the person who weighed it.

THE FOUR GATES, all enforced here rather than left to discipline:

  1. A manifest cannot be SEALED EMPTY. A sealed manifest asserts "this is what
     left the building"; with no lines it asserts nothing while looking complete.
  2. A sealed manifest is APPEND-NOTHING. Lines cannot be added, changed or
     removed after the seal — that is the whole meaning of sealing, and without
     it the witness signed something that can still change underneath them.
  3. The WITNESS MUST BE A DIFFERENT PERSON from the weigher. The two-person rule
     is the entire point of a destruction witness; one person doing both is not a
     witnessed destruction no matter what their role is. This is checked here and
     not as a schema CHECK because weighed_by is null until the seal, so a
     row-level `<>` would silently permit the equal-and-null case.
  4. DISPOSAL FOLLOWS WITNESSING. The carrier reference closes a chain that has
     to exist first; recording disposal on an unwitnessed load would produce a
     complete-looking record with the control step missing.

THE RECONCILIATION INVARIANT lives here too: the plant quantities declared
destroyed for a batch, summed across every manifest, may not exceed the batch's
plant count. Over-declaring is not a harmless typo — it is the arithmetic that
makes the whole register stop balancing, and it is far cheaper to refuse at entry
than to unpick later. Deliberately NOT a trigger or CHECK: it spans two tables,
and the alternative (a counter column on plant_batches) would be a second source
of truth for a number already derivable. See migration 0048's docstring.

GET /waste/reconciliation is the report that closes the loop: per batch, planned
headcount vs plants declared destroyed vs plants still unaccounted for, and it
flags the case that matters most — a batch CLOSED as destroyed with nothing ever
manifested. That combination is invisible to both modules on their own.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/waste", tags=["waste"])

_RECORDERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR")
_WITNESSES = (ADMIN, *EXECUTIVE_ROLES, "QA_MGR")

# Must stay in step with the CHECK constraints in migration 0048.
_WASTE_TYPES = ("plant_material", "root_substrate", "growing_medium",
                "trim", "packaging", "other")
_REASONS = ("hlvd_eradication", "routine_cull", "failed_qc", "expired",
            "spillage", "other")
# The ladder, in order. Index in this tuple IS the ordering used by the gates.
_STATUSES = ("draft", "sealed", "witnessed", "disposed")


class ManifestIn(BaseModel):
    manifest_code: str = Field(max_length=64, pattern=r"^[A-Za-z0-9_/-]{1,64}$")
    waste_type: str
    reason: str
    campaign: str | None = Field(default=None, max_length=120)
    origin_room_id: str | None = None
    destination: str | None = Field(default=None, max_length=300)
    carrier_name: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


class LineIn(BaseModel):
    batch_id: str | None = None
    room_id: str | None = None
    plant_qty: int | None = Field(default=None, ge=0, le=1000000)
    weight_kg: float | None = Field(default=None, ge=0, le=1000000)
    note: str | None = Field(default=None, max_length=500)


class SealIn(BaseModel):
    gross_weight_kg: float = Field(ge=0, le=1000000)
    note: str | None = Field(default=None, max_length=1000)


class WitnessIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class DisposeIn(BaseModel):
    # min_length, not just max: the whole value of this rung is that it points at
    # a document someone else holds. An empty carrier_ref would produce a
    # 'disposed' manifest asserting nothing, and Pydantic accepts "" for a plain
    # `str` — so without this the UI would be the only thing stopping it, and the
    # UI is never the gate.
    carrier_ref: str = Field(min_length=1, max_length=200)
    carrier_name: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


def _iso(v):
    return v.isoformat() if v is not None else None


def _manifest_out(row, lines=None) -> dict:
    out = {
        "id": str(row["id"]), "manifest_code": row["manifest_code"],
        "waste_type": row["waste_type"], "reason": row["reason"],
        "status": row["status"], "campaign": row["campaign"],
        "origin_room_id": str(row["origin_room_id"]) if row["origin_room_id"] else None,
        "origin_room_name": row["origin_room_name"],
        "destination": row["destination"], "carrier_name": row["carrier_name"],
        "carrier_ref": row["carrier_ref"],
        "gross_weight_kg": float(row["gross_weight_kg"]) if row["gross_weight_kg"] is not None else None,
        "weighed_at": _iso(row["weighed_at"]),
        "weighed_by": str(row["weighed_by"]) if row["weighed_by"] else None,
        "sealed_at": _iso(row["sealed_at"]),
        "witnessed_at": _iso(row["witnessed_at"]),
        "witnessed_by": str(row["witnessed_by"]) if row["witnessed_by"] else None,
        "disposed_at": _iso(row["disposed_at"]),
        "note": row["note"],
        "line_count": row["line_count"],
        "plant_qty_total": int(row["plant_qty_total"] or 0),
        "weight_kg_total": float(row["weight_kg_total"] or 0),
    }
    if lines is not None:
        out["lines"] = lines
    return out


async def _manifest_or_404(c, manifest_id: str):
    uuid_or_404(manifest_id, "Manifest not found")
    row = await c.fetchrow(
        "SELECT m.*, r.name AS origin_room_name,"
        " (SELECT count(*) FROM waste_manifest_lines l WHERE l.manifest_id=m.id) AS line_count,"
        " (SELECT sum(l.plant_qty) FROM waste_manifest_lines l WHERE l.manifest_id=m.id) AS plant_qty_total,"
        " (SELECT sum(l.weight_kg) FROM waste_manifest_lines l WHERE l.manifest_id=m.id) AS weight_kg_total"
        " FROM waste_manifests m LEFT JOIN rooms r ON r.id = m.origin_room_id"
        " WHERE m.id=$1", manifest_id)
    if row is None:
        raise HTTPException(404, "Manifest not found")
    return row


async def _room_or_422(c, room_id: str):
    uuid_or_422(room_id, "Unknown or inactive room")
    room = await c.fetchrow("SELECT id, name FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


async def _batch_or_422(c, batch_id: str):
    uuid_or_422(batch_id, "Unknown batch")
    b = await c.fetchrow(
        "SELECT b.id, b.code, b.plant_count, b.room_id FROM plant_batches b WHERE b.id=$1",
        batch_id)
    if b is None:
        raise HTTPException(422, "Unknown batch")
    return b


def _require_draft(row) -> None:
    """Gate 2: a sealed manifest is what the witness signed, so its contents are
    frozen. Naming the current status in the message matters — "cannot edit" with
    no state is the kind of error people retry rather than understand."""
    if row["status"] != "draft":
        raise HTTPException(
            409, f"manifest {row['manifest_code']} is {row['status']};"
                 " its lines were fixed when it was sealed")


# ── manifests ────────────────────────────────────────────────────────────────

@router.get("/manifests")
async def list_manifests(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                         status: str | None = Query(None),
                         campaign: str | None = Query(None)):
    if status is not None and status not in _STATUSES:
        raise HTTPException(422, f"status must be one of: {', '.join(_STATUSES)}")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT m.*, r.name AS origin_room_name,"
            " (SELECT count(*) FROM waste_manifest_lines l WHERE l.manifest_id=m.id) AS line_count,"
            " (SELECT sum(l.plant_qty) FROM waste_manifest_lines l WHERE l.manifest_id=m.id) AS plant_qty_total,"
            " (SELECT sum(l.weight_kg) FROM waste_manifest_lines l WHERE l.manifest_id=m.id) AS weight_kg_total"
            " FROM waste_manifests m LEFT JOIN rooms r ON r.id = m.origin_room_id"
            " WHERE ($1::text IS NULL OR m.status=$1)"
            "   AND ($2::text IS NULL OR m.campaign=$2)"
            " ORDER BY m.created_at DESC", status, campaign)
    return {"manifests": [_manifest_out(r) for r in rows]}


@router.get("/manifests/{manifest_id}")
async def get_manifest(manifest_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        row = await _manifest_or_404(c, manifest_id)
        lines = await c.fetch(
            "SELECT l.id, l.batch_id, l.room_id, l.plant_qty, l.weight_kg, l.note,"
            " l.created_at, b.code AS batch_code, r.name AS room_name"
            " FROM waste_manifest_lines l"
            " LEFT JOIN plant_batches b ON b.id = l.batch_id"
            " LEFT JOIN rooms r ON r.id = l.room_id"
            " WHERE l.manifest_id=$1 ORDER BY l.created_at", manifest_id)
    return _manifest_out(row, [
        {"id": str(l["id"]),
         "batch_id": str(l["batch_id"]) if l["batch_id"] else None,
         "batch_code": l["batch_code"],
         "room_id": str(l["room_id"]) if l["room_id"] else None,
         "room_name": l["room_name"],
         "plant_qty": l["plant_qty"],
         "weight_kg": float(l["weight_kg"]) if l["weight_kg"] is not None else None,
         "note": l["note"], "created_at": _iso(l["created_at"])}
        for l in lines])


@router.post("/manifests", status_code=201)
async def create_manifest(body: ManifestIn, user: dict = Depends(require_role(*_RECORDERS))):
    if body.waste_type not in _WASTE_TYPES:
        raise HTTPException(422, f"waste_type must be one of: {', '.join(_WASTE_TYPES)}")
    if body.reason not in _REASONS:
        raise HTTPException(422, f"reason must be one of: {', '.join(_REASONS)}")
    async with rls(user) as c:
        if body.origin_room_id is not None:
            await _room_or_422(c, body.origin_room_id)
        # Pre-checked rather than relying on the unique index, so a duplicate
        # docket number is a clean 409 instead of an asyncpg 500.
        dup = await c.fetchrow(
            "SELECT id FROM waste_manifests WHERE org_id=$1 AND manifest_code=$2",
            user["org_id"], body.manifest_code)
        if dup is not None:
            raise HTTPException(409, f"manifest code {body.manifest_code} already exists")
        row = await c.fetchrow(
            "INSERT INTO waste_manifests(org_id, manifest_code, waste_type, reason,"
            " campaign, origin_room_id, destination, carrier_name, note,"
            " created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10) RETURNING *",
            user["org_id"], body.manifest_code, body.waste_type, body.reason,
            body.campaign, body.origin_room_id, body.destination, body.carrier_name,
            body.note, user["id"])
    return {"id": str(row["id"]), "manifest_code": row["manifest_code"],
            "status": row["status"], "waste_type": row["waste_type"],
            "reason": row["reason"]}


# ── lines ────────────────────────────────────────────────────────────────────

@router.post("/manifests/{manifest_id}/lines", status_code=201)
async def add_line(manifest_id: str, body: LineIn,
                   user: dict = Depends(require_role(*_RECORDERS))):
    if body.plant_qty is None and body.weight_kg is None:
        raise HTTPException(422, "a line must state a plant count or a weight")
    async with rls(user) as c:
        m = await _manifest_or_404(c, manifest_id)
        _require_draft(m)
        room_id = body.room_id
        if body.batch_id is not None:
            b = await _batch_or_422(c, body.batch_id)
            # Default the line's room to the batch's own, so the physical origin
            # is recorded even when the person entering it does not restate it.
            if room_id is None and b["room_id"] is not None:
                room_id = str(b["room_id"])
            if body.plant_qty:
                # THE RECONCILIATION INVARIANT. Counts every line for this batch
                # on every OTHER manifest — including drafts, because a draft that
                # over-declares must be caught before it is sealed, not after.
                already = await c.fetchval(
                    "SELECT COALESCE(sum(plant_qty), 0) FROM waste_manifest_lines"
                    " WHERE batch_id=$1", body.batch_id) or 0
                # ...AND every plant already harvested off the batch (migration
                # 0051). Checking destruction alone let the two registers each be
                # individually valid and jointly impossible: 2000 plants cut into
                # harvest lots and the same 2000 declared destroyed. harvest.py
                # carries the mirror of this check, and the two must agree.
                harvested = await c.fetchval(
                    "SELECT COALESCE(sum(plants_harvested), 0) FROM harvests"
                    " WHERE batch_id=$1", body.batch_id) or 0
                if already + harvested + body.plant_qty > (b["plant_count"] or 0):
                    raise HTTPException(
                        409,
                        f"batch {b['code']} has {b['plant_count']} plants;"
                        f" {already} are already declared destroyed and"
                        f" {harvested} harvested, so {body.plant_qty} more"
                        " would over-declare it")
        if room_id is not None:
            await _room_or_422(c, room_id)
        row = await c.fetchrow(
            "INSERT INTO waste_manifest_lines(org_id, manifest_id, batch_id, room_id,"
            " plant_qty, weight_kg, note, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id",
            user["org_id"], manifest_id, body.batch_id, room_id,
            body.plant_qty, body.weight_kg, body.note, user["id"])
    return {"id": str(row["id"]), "manifest_id": manifest_id}


@router.delete("/manifests/{manifest_id}/lines/{line_id}")
async def delete_line(manifest_id: str, line_id: str,
                      user: dict = Depends(require_role(*_RECORDERS))):
    uuid_or_404(line_id, "Line not found")
    async with rls(user) as c:
        m = await _manifest_or_404(c, manifest_id)
        _require_draft(m)
        row = await c.fetchrow(
            "DELETE FROM waste_manifest_lines WHERE id=$1 AND manifest_id=$2 RETURNING id",
            line_id, manifest_id)
    if row is None:
        raise HTTPException(404, "Line not found")
    return {"ok": True}


# ── the ladder ───────────────────────────────────────────────────────────────

@router.post("/manifests/{manifest_id}/seal")
async def seal_manifest(manifest_id: str, body: SealIn,
                        user: dict = Depends(require_role(*_RECORDERS))):
    """Fix the contents and record the gross weight. Gate 1 lives here: a sealed
    manifest with no lines asserts nothing while looking complete."""
    async with rls(user) as c:
        m = await _manifest_or_404(c, manifest_id)
        _require_draft(m)
        if not m["line_count"]:
            raise HTTPException(
                409, "an empty manifest cannot be sealed — add what is in the load first")
        now = datetime.now(timezone.utc)
        row = await c.fetchrow(
            "UPDATE waste_manifests SET status='sealed', gross_weight_kg=$1,"
            " weighed_at=$2, weighed_by=$3, sealed_at=$2,"
            " note=COALESCE($4, note), updated_by=$3, updated_at=now()"
            " WHERE id=$5 RETURNING *",
            body.gross_weight_kg, now, user["id"], body.note, manifest_id)
        await safe_emit(c, user, verb="waste_manifest_sealed", object_type="waste_manifest",
                        object_id=manifest_id, recipients=[],
                        params={"code": m["manifest_code"],
                                "gross_weight_kg": body.gross_weight_kg,
                                "lines": m["line_count"]})
    return {"id": manifest_id, "status": row["status"], "sealed_at": _iso(row["sealed_at"]),
            "gross_weight_kg": float(row["gross_weight_kg"])}


@router.post("/manifests/{manifest_id}/witness")
async def witness_manifest(manifest_id: str, body: WitnessIn,
                           user: dict = Depends(require_role(*_WITNESSES))):
    """Gate 3: the two-person rule. Whoever weighed the load cannot also witness
    it — that is not a witnessed destruction regardless of their role."""
    async with rls(user) as c:
        m = await _manifest_or_404(c, manifest_id)
        if m["status"] == "draft":
            raise HTTPException(409, "manifest is not sealed yet; there is nothing to witness")
        if m["status"] in ("witnessed", "disposed"):
            raise HTTPException(409, f"manifest is already {m['status']}")
        if m["weighed_by"] is not None and str(m["weighed_by"]) == str(user["id"]):
            raise HTTPException(
                409, "the person who weighed and sealed this load cannot also witness it")
        now = datetime.now(timezone.utc)
        row = await c.fetchrow(
            "UPDATE waste_manifests SET status='witnessed', witnessed_at=$1,"
            " witnessed_by=$2, note=COALESCE($3, note), updated_by=$2, updated_at=now()"
            " WHERE id=$4 RETURNING *", now, user["id"], body.note, manifest_id)
        await safe_emit(c, user, verb="waste_manifest_witnessed", object_type="waste_manifest",
                        object_id=manifest_id, recipients=[],
                        params={"code": m["manifest_code"]})
    return {"id": manifest_id, "status": row["status"],
            "witnessed_at": _iso(row["witnessed_at"])}


@router.post("/manifests/{manifest_id}/dispose")
async def dispose_manifest(manifest_id: str, body: DisposeIn,
                           user: dict = Depends(require_role(*_RECORDERS))):
    """Gate 4: the carrier reference closes a chain that must already exist, so
    an unwitnessed load cannot be closed out."""
    async with rls(user) as c:
        m = await _manifest_or_404(c, manifest_id)
        if m["status"] != "witnessed":
            raise HTTPException(
                409, f"manifest is {m['status']}; it must be witnessed before disposal is recorded")
        now = datetime.now(timezone.utc)
        # Whitespace-only would pass min_length but assert as little as empty.
        ref = body.carrier_ref.strip()
        if not ref:
            raise HTTPException(422, "carrier_ref is required — it is what ties our record to theirs")
        row = await c.fetchrow(
            "UPDATE waste_manifests SET status='disposed', carrier_ref=$1,"
            " carrier_name=COALESCE($2, carrier_name), disposed_at=$3, disposed_by=$4,"
            " note=COALESCE($5, note), updated_by=$4, updated_at=now()"
            " WHERE id=$6 RETURNING *",
            ref, body.carrier_name, now, user["id"], body.note, manifest_id)
        await safe_emit(c, user, verb="waste_manifest_disposed", object_type="waste_manifest",
                        object_id=manifest_id, recipients=[],
                        params={"code": m["manifest_code"], "carrier_ref": ref})
    return {"id": manifest_id, "status": row["status"], "disposed_at": _iso(row["disposed_at"]),
            "carrier_ref": row["carrier_ref"]}


# ── reconciliation ───────────────────────────────────────────────────────────

@router.get("/reconciliation")
async def reconciliation(user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Per batch: planned headcount, how many plants are declared destroyed on
    manifests, and what remains unaccounted for.

    `unmanifested_destruction` is the row that matters and neither module can see
    on its own: a batch CLOSED as destroyed in cultivation with nothing ever
    manifested. Cultivation says the plants are gone; the waste register says
    nothing left the building. Only the join notices.

    READ `unaccounted` CAREFULLY. It is plain arithmetic — `plant_count` minus
    what has been declared destroyed — and it is a DISCREPANCY only for a batch in
    the `destroyed` phase. For a live batch it equals the whole batch, because the
    plants are in the room; for a harvested batch the remainder went to the lot.
    Treating it as a discrepancy unconditionally labels every healthy batch a
    problem and buries the few real ones, so the caller must interpret it by
    phase. `web/gf/waste-view.js` does that in one predicate (`reconState`) shared
    by the row rendering and the summary count, so the two cannot disagree."""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT b.id, b.code, b.phase, b.plant_count, cv.code AS cultivar_code,"
            " r.name AS room_name,"
            " COALESCE((SELECT sum(l.plant_qty) FROM waste_manifest_lines l"
            "           WHERE l.batch_id=b.id), 0) AS declared_destroyed,"
            " COALESCE((SELECT sum(l.plant_qty) FROM waste_manifest_lines l"
            "           JOIN waste_manifests m ON m.id=l.manifest_id"
            "           WHERE l.batch_id=b.id AND m.status='disposed'), 0) AS disposed_destroyed,"
            " (SELECT count(*) FROM plants p WHERE p.batch_id=b.id) AS plants_materialised,"
            " (SELECT count(*) FROM plants p WHERE p.batch_id=b.id AND p.status='active')"
            "   AS plants_active"
            " FROM plant_batches b"
            " LEFT JOIN cultivars cv ON cv.id=b.cultivar_id"
            " LEFT JOIN rooms r ON r.id=b.room_id"
            " ORDER BY b.phase_since DESC NULLS LAST, b.code")
    out = []
    for r in rows:
        planned = r["plant_count"] or 0
        declared = int(r["declared_destroyed"] or 0)
        out.append({
            "batch_id": str(r["id"]), "code": r["code"], "phase": r["phase"],
            "cultivar_code": r["cultivar_code"], "room_name": r["room_name"],
            "plant_count": planned,
            "plants_materialised": r["plants_materialised"],
            "plants_active": r["plants_active"],
            "declared_destroyed": declared,
            "disposed_destroyed": int(r["disposed_destroyed"] or 0),
            "unaccounted": max(0, planned - declared),
            # Closed as destroyed, nothing manifested — the discrepancy this
            # report exists to surface.
            "unmanifested_destruction": r["phase"] == "destroyed" and declared == 0,
            # Should be impossible (add_line refuses it); reported anyway, because
            # a guard that is never checked against the data is a guard nobody
            # notices has been bypassed — e.g. by a direct SQL fix.
            "over_declared": declared > planned,
        })
    return {"batches": out}
