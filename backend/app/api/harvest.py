"""Harvest / yield, and the IPM applications the harvest gate reads (migration 0051).

Phase 2 item 1 of the cultivation build (docs/CULTIVATION-DESIGN-2026-07.md §5).
This is the module that closes cultivation into the QC chain: creating a harvest
writes a `qc_batch_genealogy` edge `batch code → lot code` with
`relation='CULTIVATION'`, which is the slot migration 0036 has had waiting since
before cultivation had any identifier to put in it.

Routes hang off the `/cultivation` prefix (a second router on the same prefix as
cultivation.py) because a harvest and a spray record ARE cultivation records —
they simply live in their own module, since together they carry one interlocking
control that is easier to get wrong when split across files.

Access model (owner's model of where the work changes hands, 2026-09-05):
  read      — every role above base USER (ELEVATED_ROLES);
  IPM       — applications are a cultivation-floor record: cultivation crew
              (CU_MGR) + executives + ADMIN (_RECORDERS);
  the cut   — cultivation records it, then hands over: _RECORDERS PLUS QA
              authority (QA_MGR), for the reason below (_CUTTERS);
  after it  — the dry weights and closing the lot belong to PRODUCTION
              (PR_MGR) + executives + ADMIN (_POST_HARVEST). The cut is the
              handoff: cultivation runs the plant from seed, import or clone up
              to and including the cut; production takes the lot from the dry
              room onward. Before this, cultivation held both sides and
              PR_MGR appeared in no gate anywhere in the codebase;
  override  — releasing a harvest that a pre-harvest interval blocks: QA
              authority (QA_MGR) + executives + ADMIN, never the recorder alone.

WHY QA CAN RECORD A CUT BUT NOT A DRY WEIGHT. The PHI override is expressed ON
the harvest row (that is what makes it evidence rather than a note), so whoever
releases the block has to be the one who writes the record carrying the release —
otherwise the recorder would be signing someone else's decision. That gives
QA_MGR exactly one extra write: creating a harvest. Recording the yield and
closing the lot are production's, so the widened surface is the minimum the
control needs and not a general QA write into the floor's records.

THE FIVE GATES

  1. PRE-HARVEST INTERVAL. A batch whose room or batch had an IPM application
     with a `phi_days` that has not elapsed by the harvest date cannot be cut.
     This is the interaction the design doc insisted be built WITH harvest rather
     than bolted on after, and it is the reason `ipm_applications` ships in the
     same migration: a gate with no evidence source is a gate nobody can test.

     Overridable, but only by QA authority and only with a written reason, both
     recorded on the harvest row (migration 0051's `harvests_phi_override_check`
     makes the three override columns arrive together or not at all). A recorder
     cannot wave away their own block — if they could, the gate would be
     decoration.

  2. HEADCOUNT. Plants harvested plus plants declared destroyed may not exceed
     the batch's plant count, summed across EVERY harvest and EVERY waste
     manifest. Checking either register alone lets both be individually valid and
     jointly impossible — 2000 plants harvested and the same 2000 destroyed.
     `waste.add_line` carries the mirror of this check for the same reason —
     AND the mirror of the batch-scoped `pg_advisory_xact_lock` this gate takes
     before reading its sums. The arithmetic alone is not enough: under READ
     COMMITTED, two concurrent requests touching the same batch (a harvest and
     a waste line, or two waste lines on different manifests) can each read
     pre-commit sums and jointly over-declare it unless something actually
     serializes them. The lock is keyed `headcount:{batch_id}` in both places —
     it must be the identical key or the two transactions block on different
     locks and never contend at all.

  3. YIELD ARITHMETIC. Dry output cannot exceed wet input; nothing gains mass in
     a dry room. Pre-checked here for a clean 409 with the numbers in it, and
     backstopped by `harvests_yield_check` in the schema so no route into the
     table can bypass it.

  4. CLOSING NEEDS A YIELD. A lot cannot be closed before its dry weights are
     recorded — a closed yield record with no yield in it is worse than an open
     one, because it looks finished.

  5. TERMINAL BATCHES. Nothing can be harvested from a batch already closed as
     harvested or destroyed. The manager closes the batch AFTER the final pull.

WHAT IS DELIBERATELY *NOT* GATED: closing a lot needs no second person. The
destruction register's two-person witness exists because destroyed material stops
being auditable the moment it leaves; a harvest lot is still physically present
and still re-weighable, so the same friction buys far less here and a control
that buys little is a control people route around. If a second signature is
wanted later it belongs on the CoA, where it already exists.

LOCK ORDERING — READ BEFORE ADDING A WRITE TO create_harvest. This handler takes
the per-org genealogy advisory lock as its FIRST statement, before any audited
write. That is not cosmetic. `app.fn_audit_row()` takes a global advisory lock on
every audited write and holds it to commit; qc/genealogy.py takes the genealogy
lock and then writes (audit lock). If this handler wrote the harvest row first it
would hold the audit lock while waiting for the genealogy lock, which is the exact
inversion of genealogy.py's order — two concurrent transactions would deadlock.
Genealogy lock first, always.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/cultivation", tags=["cultivation"])

_RECORDERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR")
# Whoever records the cut must not be able to release their own PHI block, so the
# override set is QA authority — the same asymmetry as the destruction witness.
_PHI_OVERRIDERS = (ADMIN, *EXECUTIVE_ROLES, "QA_MGR")
# Creating a harvest is open to both sets because the override lives on the row
# being created (see the module header). Ordering is irrelevant to the guard but
# dict.fromkeys keeps the tuple stable and duplicate-free as either set changes.
_CUTTERS = tuple(dict.fromkeys((*_RECORDERS, *_PHI_OVERRIDERS)))
# From the cut onward the lot is production's: the dry weights and the close.
# Deliberately NOT a superset of _RECORDERS — the cultivation manager who cut
# the plant does not also dry and close it; that is the handoff.
_POST_HARVEST = (ADMIN, *EXECUTIVE_ROLES, "PR_MGR")

# Must stay in step with the CHECK constraints in migration 0051.
_IPM_CATEGORIES = ("biological", "botanical", "chemical", "mechanical", "other")
_IPM_METHODS = ("spray", "drench", "fog", "dust", "release", "other")
_HARVEST_STATUSES = ("wet", "dried", "closed")
# Batch phases a harvest cannot be recorded against (cultivation.py's _TERMINAL).
_TERMINAL_PHASES = ("harvested", "destroyed")

# Moisture loss outside this band is REPORTED, never refused. Fresh cannabis is
# roughly three-quarters water and dries to ~10-12% moisture, so a lot normally
# loses 70-80% of its wet weight. The band is deliberately wider than that:
# outside it means "look at this number", not "this number is wrong", and a
# report that cries wolf on ordinary variation gets ignored on the day it is
# right. One constant, used by both the per-lot field and the batch roll-up.
_LOSS_PLAUSIBLE_MIN_PCT = 60.0
_LOSS_PLAUSIBLE_MAX_PCT = 92.0

# The zone a calendar-day interval is counted in. A pre-harvest interval is N
# CALENDAR DAYS AT THE SITE, so the application timestamp is rendered in the
# facility zone explicitly rather than left to whatever TimeZone the reading
# session happens to carry. Leaving it to the session is precisely the bug
# migration 0050 was written to fix in the audit chain.
def _site_tz() -> str:
    return settings.snapshot_tz or "UTC"


async def _site_today(c) -> date:
    """Today's date AT THE SITE, resolved by Postgres.

    Not `date.today()`: that renders under the *container's* zone (UTC), while
    every PHI comparison in this module renders `applied_at` under the site zone.
    Mixing the two means that for a couple of hours each evening "today" and the
    interval it is compared against disagree by a day — which is a gate that
    opens early, i.e. wrong in the permissive direction.

    Resolved in SQL rather than with `zoneinfo` so the zone database doing the
    conversion is the SAME one doing it inside `_PHI_BLOCK_SQL`. Two tzdata
    copies that could drift apart is exactly the class of bug migration 0050
    exists because of."""
    return await c.fetchval("SELECT (now() AT TIME ZONE $1)::date", _site_tz())


class IpmIn(BaseModel):
    product: str = Field(min_length=1, max_length=200)
    category: str
    room_id: str | None = None
    batch_id: str | None = None
    active_ingredient: str | None = Field(default=None, max_length=200)
    method: str | None = None
    dose: str | None = Field(default=None, max_length=120)
    target: str | None = Field(default=None, max_length=200)
    applied_at: datetime | None = None
    rei_hours: int | None = Field(default=None, ge=0, le=8760)
    phi_days: int | None = Field(default=None, ge=0, le=365)
    note: str | None = Field(default=None, max_length=1000)


class HarvestIn(BaseModel):
    batch_id: str
    lot_code: str = Field(max_length=64, pattern=r"^[A-Za-z0-9_/-]{1,64}$")
    plants_harvested: int = Field(ge=0, le=1000000)
    wet_weight_g: float = Field(ge=0, le=100000000)
    harvested_on: date | None = None
    room_id: str | None = None
    note: str | None = Field(default=None, max_length=1000)
    # Presence of a reason is what makes this an override attempt. min_length so
    # `phi_override_reason: ""` cannot pass as a stated reason — Pydantic accepts
    # "" for a plain `str`, and a blank reason is the same as no reason.
    phi_override_reason: str | None = Field(default=None, min_length=1, max_length=500)


class DryIn(BaseModel):
    dry_flower_g: float = Field(ge=0, le=100000000)
    dry_trim_g: float | None = Field(default=None, ge=0, le=100000000)
    dry_waste_g: float | None = Field(default=None, ge=0, le=100000000)
    dried_on: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class CloseIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


def _iso(v):
    return v.isoformat() if v is not None else None


def _num(v):
    return float(v) if v is not None else None


def _loss_pct(wet, dry_total):
    """Moisture loss as a percentage of wet weight. None when it cannot be
    computed rather than 0 — a lot with no dry weight yet has an UNKNOWN loss,
    and reporting that as 0% would put every drying lot at the wrong end of the
    plausible band."""
    if wet is None or dry_total is None or float(wet) <= 0:
        return None
    return round((float(wet) - float(dry_total)) / float(wet) * 100.0, 1)


def _implausible(loss_pct) -> bool:
    """Outside the band is a prompt to look, never a refusal — see the constants."""
    return loss_pct is not None and (
        loss_pct < _LOSS_PLAUSIBLE_MIN_PCT or loss_pct > _LOSS_PLAUSIBLE_MAX_PCT)


async def _room_or_422(c, room_id: str):
    uuid_or_422(room_id, "Unknown or inactive room")
    room = await c.fetchrow("SELECT id, name FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


async def _batch_or_422(c, batch_id: str):
    uuid_or_422(batch_id, "Unknown batch")
    b = await c.fetchrow(
        "SELECT b.id, b.code, b.phase, b.plant_count, b.room_id, b.cultivar_id,"
        " cv.code AS cultivar_code, r.name AS room_name"
        " FROM plant_batches b"
        " LEFT JOIN cultivars cv ON cv.id=b.cultivar_id"
        " LEFT JOIN rooms r ON r.id=b.room_id"
        " WHERE b.id=$1", batch_id)
    if b is None:
        raise HTTPException(422, "Unknown batch")
    return b


async def _harvest_or_404(c, harvest_id: str):
    uuid_or_404(harvest_id, "Harvest not found")
    row = await c.fetchrow(
        "SELECT h.*, b.code AS batch_code, b.phase AS batch_phase, b.plant_count,"
        " cv.code AS cultivar_code, r.name AS room_name"
        " FROM harvests h"
        " JOIN plant_batches b ON b.id=h.batch_id"
        " LEFT JOIN cultivars cv ON cv.id=b.cultivar_id"
        " LEFT JOIN rooms r ON r.id=h.room_id"
        " WHERE h.id=$1", harvest_id)
    if row is None:
        raise HTTPException(404, "Harvest not found")
    return row


def _harvest_out(r) -> dict:
    dry_total = None
    parts = [r["dry_flower_g"], r["dry_trim_g"], r["dry_waste_g"]]
    if any(p is not None for p in parts):
        dry_total = sum(float(p) for p in parts if p is not None)
    plants = r["plants_harvested"] or 0
    # Computed once and used twice: two calls could be edited apart, and a row
    # whose reported loss and "implausible" flag disagree is worse than either.
    loss = _loss_pct(r["wet_weight_g"], dry_total)
    return {
        "id": str(r["id"]), "batch_id": str(r["batch_id"]),
        "batch_code": r["batch_code"], "batch_phase": r["batch_phase"],
        "cultivar_code": r["cultivar_code"],
        "room_id": str(r["room_id"]) if r["room_id"] else None,
        "room_name": r["room_name"],
        "lot_code": r["lot_code"], "status": r["status"],
        "harvested_on": _iso(r["harvested_on"]),
        "plants_harvested": plants,
        "wet_weight_g": _num(r["wet_weight_g"]),
        "dried_on": _iso(r["dried_on"]),
        "dry_flower_g": _num(r["dry_flower_g"]),
        "dry_trim_g": _num(r["dry_trim_g"]),
        "dry_waste_g": _num(r["dry_waste_g"]),
        "dry_total_g": dry_total,
        "moisture_loss_pct": loss,
        "implausible_loss": _implausible(loss),
        # The metric the floor actually manages a room by. Only meaningful once
        # the lot is dry, and only when the pull retired plants at all (a
        # partial-canopy pull retires none, and dividing by zero would invent a
        # number where there is none).
        "dry_flower_g_per_plant": (
            round(float(r["dry_flower_g"]) / plants, 1)
            if r["dry_flower_g"] is not None and plants > 0 else None),
        "phi_override_at": _iso(r["phi_override_at"]),
        "phi_override_by": str(r["phi_override_by"]) if r["phi_override_by"] else None,
        "phi_override_reason": r["phi_override_reason"],
        "harvested_by": str(r["harvested_by"]) if r["harvested_by"] else None,
        "closed_at": _iso(r["closed_at"]),
        "note": r["note"],
        "created_at": _iso(r["created_at"]),
    }


# ── IPM applications ─────────────────────────────────────────────────────────

@router.get("/ipm")
async def list_ipm(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                   batch_id: str | None = Query(None),
                   room_id: str | None = Query(None),
                   limit: int = Query(100, ge=1, le=500)):
    if batch_id is not None:
        uuid_or_422(batch_id, "batch_id must be a uuid")
    if room_id is not None:
        uuid_or_422(room_id, "room_id must be a uuid")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT a.*, r.name AS room_name, b.code AS batch_code,"
            "  (a.applied_at + make_interval(hours => a.rei_hours)) AS rei_until,"
            "  ((a.applied_at AT TIME ZONE $3)::date + a.phi_days) AS phi_clear_on"
            " FROM ipm_applications a"
            " LEFT JOIN rooms r ON r.id=a.room_id"
            " LEFT JOIN plant_batches b ON b.id=a.batch_id"
            " WHERE ($1::uuid IS NULL OR a.batch_id=$1)"
            "   AND ($2::uuid IS NULL OR a.room_id=$2)"
            " ORDER BY a.applied_at DESC LIMIT $4",
            batch_id, room_id, _site_tz(), limit)
    now = datetime.now(timezone.utc)
    return {"applications": [{
        "id": str(r["id"]),
        "room_id": str(r["room_id"]) if r["room_id"] else None,
        "room_name": r["room_name"],
        "batch_id": str(r["batch_id"]) if r["batch_id"] else None,
        "batch_code": r["batch_code"],
        "product": r["product"], "active_ingredient": r["active_ingredient"],
        "category": r["category"], "method": r["method"], "dose": r["dose"],
        "target": r["target"],
        "applied_at": _iso(r["applied_at"]),
        "rei_hours": r["rei_hours"], "phi_days": r["phi_days"],
        "rei_until": _iso(r["rei_until"]),
        # A room under re-entry restriction right now is a personnel control, not
        # a product one, but it belongs on the same board: harvesting means people
        # going into that room.
        "rei_active": bool(r["rei_until"] is not None and r["rei_until"] > now),
        "phi_clear_on": _iso(r["phi_clear_on"]),
        "note": r["note"],
    } for r in rows]}


@router.post("/ipm", status_code=201)
async def create_ipm(body: IpmIn, user: dict = Depends(require_role(*_RECORDERS))):
    if body.category not in _IPM_CATEGORIES:
        raise HTTPException(422, f"category must be one of: {', '.join(_IPM_CATEGORIES)}")
    if body.method is not None and body.method not in _IPM_METHODS:
        raise HTTPException(422, f"method must be one of: {', '.join(_IPM_METHODS)}")
    # Mirrors ipm_applications_target_scope_check. Pre-checked so the refusal
    # explains itself instead of surfacing as an asyncpg 500.
    if body.room_id is None and body.batch_id is None:
        raise HTTPException(
            422, "state the room or the batch this was applied to — an application"
                 " scoped to neither cannot feed the re-entry or pre-harvest control")
    async with rls(user) as c:
        if body.room_id is not None:
            await _room_or_422(c, body.room_id)
        if body.batch_id is not None:
            await _batch_or_422(c, body.batch_id)
        row = await c.fetchrow(
            "INSERT INTO ipm_applications(org_id, room_id, batch_id, product,"
            " active_ingredient, category, method, dose, target,"
            " applied_at, rei_hours, phi_days, applied_by, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,COALESCE($10::timestamptz, now()),"
            " $11,$12,$13,$14,$13,$13) RETURNING *",
            user["org_id"], body.room_id, body.batch_id, body.product,
            body.active_ingredient, body.category, body.method, body.dose, body.target,
            body.applied_at, body.rei_hours, body.phi_days, user["id"], body.note)
        await safe_emit(c, user, verb="ipm_applied", object_type="ipm_application",
                        object_id=row["id"], recipients=[],
                        params={"product": row["product"], "category": row["category"],
                                "rei_hours": row["rei_hours"], "phi_days": row["phi_days"]})
    return {"id": str(row["id"]), "product": row["product"], "category": row["category"],
            "applied_at": _iso(row["applied_at"]),
            "rei_hours": row["rei_hours"], "phi_days": row["phi_days"]}


# ── the pre-harvest interval gate ────────────────────────────────────────────

# The blocking query, shared by the clearance report and by create_harvest so the
# two can never disagree about what is blocked. $1 batch id, $2 the batch's
# CURRENT room, $3 the site timezone, $4 the harvest date.
#
# ROOM SCOPE IS RESOLVED AS OF THE APPLICATION DATE, not as of now. A room-scoped
# spray restricts whatever was standing in that room when it was sprayed; a batch
# that moved in afterwards was never treated and a batch that moved out still
# carries the interval. `plant_phase_events` already records every move with a
# date, so the batch's room on the application date is a lookup rather than a
# guess. The COALESCE falls back to the batch's current room for a batch with no
# room events at all (cultivation.create_batch always writes one, so this is the
# legacy/imported case rather than the normal one).
_PHI_BLOCK_SQL = """
SELECT a.id, a.product, a.active_ingredient, a.category, a.method,
       a.applied_at, a.phi_days, a.room_id, a.batch_id,
       r.name AS room_name,
       ((a.applied_at AT TIME ZONE $3)::date + a.phi_days) AS phi_clear_on,
       ((a.applied_at AT TIME ZONE $3)::date + a.phi_days) - $4::date AS days_remaining
FROM ipm_applications a
LEFT JOIN rooms r ON r.id = a.room_id
WHERE a.phi_days IS NOT NULL
  AND (
    a.batch_id = $1
    OR (a.room_id IS NOT NULL AND a.room_id = COALESCE((
          SELECT e.to_room_id FROM plant_phase_events e
          WHERE e.batch_id = $1 AND e.to_room_id IS NOT NULL
            AND e.occurred_on <= (a.applied_at AT TIME ZONE $3)::date
          ORDER BY e.occurred_on DESC, e.created_at DESC LIMIT 1), $2::uuid))
  )
  AND ((a.applied_at AT TIME ZONE $3)::date + a.phi_days) > $4::date
ORDER BY ((a.applied_at AT TIME ZONE $3)::date + a.phi_days) DESC
"""


async def _phi_blocks(c, batch, on: date):
    return await c.fetch(_PHI_BLOCK_SQL, batch["id"], batch["room_id"], _site_tz(), on)


def _block_out(r) -> dict:
    return {
        "ipm_id": str(r["id"]), "product": r["product"],
        "active_ingredient": r["active_ingredient"], "category": r["category"],
        "method": r["method"],
        "scope": "batch" if r["batch_id"] is not None else "room",
        "room_name": r["room_name"],
        "applied_at": _iso(r["applied_at"]), "phi_days": r["phi_days"],
        "phi_clear_on": _iso(r["phi_clear_on"]),
        "days_remaining": r["days_remaining"],
    }


@router.get("/harvest-clearance/{batch_id}")
async def harvest_clearance(batch_id: str,
                            user: dict = Depends(require_role(*ELEVATED_ROLES)),
                            on: date | None = Query(None)):
    """Can this batch be cut on this date, and if not, what is holding it.

    The board calls this BEFORE offering the harvest button, so the operator sees
    the interval and the date it clears rather than discovering the refusal as a
    409 after filling in a form. The server still enforces it in create_harvest —
    this endpoint is the explanation, never the gate."""
    async with rls(user) as c:
        b = await _batch_or_422(c, batch_id)
        when = on or await _site_today(c)
        blocks = await _phi_blocks(c, b, when)
        # Re-entry is a separate control with a separate clock (hours, not days)
        # and it restricts PEOPLE rather than product. It is reported alongside
        # because harvesting a room means entering it, but it is NOT a harvest
        # block and is never counted into `clear`.
        rei = await c.fetch(
            "SELECT a.id, a.product, a.applied_at, a.rei_hours, r.name AS room_name,"
            "  (a.applied_at + make_interval(hours => a.rei_hours)) AS rei_until"
            " FROM ipm_applications a LEFT JOIN rooms r ON r.id=a.room_id"
            " WHERE a.rei_hours IS NOT NULL"
            "   AND (a.batch_id=$1 OR (a.room_id IS NOT NULL AND a.room_id=$2::uuid))"
            "   AND (a.applied_at + make_interval(hours => a.rei_hours)) > now()"
            " ORDER BY (a.applied_at + make_interval(hours => a.rei_hours)) DESC",
            b["id"], b["room_id"])
    # The trichome record the owner's rule makes the real decider of a cut
    # (0066). Reported beside the interval blocks and NEVER counted into
    # `clear`: a pre-harvest interval is a control, a maturation reading is an
    # observation, and conflating them would either invent a gate nobody asked
    # for or quietly weaken one that exists.
    async with rls(user) as c:
        tc = await c.fetchrow(
            "SELECT checked_on, verdict, pct_amber, instrument FROM trichome_checks"
            " WHERE batch_id=$1 ORDER BY checked_on DESC, created_at DESC LIMIT 1", b["id"])
    return {
        "latest_trichome": None if tc is None else {
            "checked_on": tc["checked_on"].isoformat(), "verdict": tc["verdict"],
            "pct_amber": float(tc["pct_amber"]) if tc["pct_amber"] is not None else None,
            "instrument": tc["instrument"]},
        "batch_id": str(b["id"]), "batch_code": b["code"],
        "cultivar_code": b["cultivar_code"], "room_name": b["room_name"],
        "phase": b["phase"], "on": when.isoformat(),
        "clear": not blocks,
        "terminal": b["phase"] in _TERMINAL_PHASES,
        "blocking": [_block_out(r) for r in blocks],
        "rei_active": [{
            "ipm_id": str(r["id"]), "product": r["product"],
            "room_name": r["room_name"], "applied_at": _iso(r["applied_at"]),
            "rei_hours": r["rei_hours"], "rei_until": _iso(r["rei_until"]),
        } for r in rei],
    }


# ── harvests ─────────────────────────────────────────────────────────────────

@router.get("/harvests")
async def list_harvests(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                        batch_id: str | None = Query(None),
                        status: str | None = Query(None)):
    if status is not None and status not in _HARVEST_STATUSES:
        raise HTTPException(422, f"status must be one of: {', '.join(_HARVEST_STATUSES)}")
    if batch_id is not None:
        uuid_or_422(batch_id, "batch_id must be a uuid")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT h.*, b.code AS batch_code, b.phase AS batch_phase, b.plant_count,"
            " cv.code AS cultivar_code, r.name AS room_name"
            " FROM harvests h"
            " JOIN plant_batches b ON b.id=h.batch_id"
            " LEFT JOIN cultivars cv ON cv.id=b.cultivar_id"
            " LEFT JOIN rooms r ON r.id=h.room_id"
            " WHERE ($1::uuid IS NULL OR h.batch_id=$1)"
            "   AND ($2::text IS NULL OR h.status=$2)"
            " ORDER BY h.harvested_on DESC, h.created_at DESC",
            batch_id, status)
    return {"harvests": [_harvest_out(r) for r in rows]}


@router.get("/harvests/{harvest_id}")
async def get_harvest(harvest_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        row = await _harvest_or_404(c, harvest_id)
    return _harvest_out(row)


@router.post("/harvests", status_code=201)
async def create_harvest(body: HarvestIn, user: dict = Depends(require_role(*_CUTTERS))):
    """Record a cut. Gates 1, 2 and 5, plus the genealogy edge that is the whole
    point of this record existing (see the module header on lock ordering)."""
    async with rls(user) as c:
        # FIRST STATEMENT, before any audited write — see LOCK ORDERING in the
        # module header. Also closes the race against a concurrent
        # qc/genealogy.py edge insert that would slip a node in between the
        # collision checks below and this handler's own edge.
        await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))",
                        f"genealogy:{user['org_id']}")
        b = await _batch_or_422(c, body.batch_id)

        # Gate 5 — a closed batch has no more plants to cut.
        if b["phase"] in _TERMINAL_PHASES:
            raise HTTPException(
                409, f"batch {b['code'] or b['id']} is {b['phase']};"
                     " close the batch after the final pull, not before")
        # The lot code becomes a node in the genealogy graph, so it needs the
        # batch code to hang off. A batch with no code cannot be traced forward
        # and silently skipping the edge would leave a harvest that looks linked
        # and is not.
        if not b["code"]:
            raise HTTPException(
                422, "this batch has no batch code, so a harvest lot cannot be linked"
                     " to it — give the batch a code first")

        lot = body.lot_code.strip()
        if lot == b["code"]:
            raise HTTPException(422, "the harvest lot code must differ from the batch code")
        dup = await c.fetchval("SELECT 1 FROM harvests WHERE org_id=$1 AND lot_code=$2",
                               user["org_id"], lot)
        if dup:
            raise HTTPException(409, f"lot code {lot} already exists")
        # A lot code that is already a node in the graph (another batch's code, or
        # a processing/packaging lot) would fuse two different physical things
        # into one traceability node — which is also how a cycle gets created two
        # edges later.
        clash = await c.fetchval(
            "SELECT 1 FROM plant_batches WHERE org_id=$1 AND code=$2"
            " UNION ALL SELECT 1 FROM qc_batch_genealogy"
            " WHERE org_id=$1 AND (parent_batch_id=$2 OR child_batch_id=$2) LIMIT 1",
            user["org_id"], lot)
        if clash:
            raise HTTPException(
                409, f"{lot} is already used as a batch or lot identifier;"
                     " a harvest lot code must be its own node in the genealogy")

        room_id = body.room_id
        if room_id is not None:
            await _room_or_422(c, room_id)
        elif b["room_id"] is not None:
            room_id = str(b["room_id"])

        when = body.harvested_on or await _site_today(c)

        # Gate 2 — the headcount invariant, across BOTH registers. Either one
        # alone can be satisfied while the two together are impossible.
        if body.plants_harvested:
            # Batch-scoped lock, held for the rest of this transaction. The
            # org-scoped genealogy lock taken above serializes concurrent
            # create_harvest calls within an org, but says nothing about a
            # concurrent waste.add_line for THIS batch — without this, the two
            # can each read pre-commit sums under READ COMMITTED and jointly
            # over-declare the batch. waste.add_line takes the identical lock,
            # keyed off the same batch id, before its own sums.
            await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))",
                            f"headcount:{b['id']}")
            already_cut = await c.fetchval(
                "SELECT COALESCE(sum(plants_harvested), 0) FROM harvests WHERE batch_id=$1",
                b["id"]) or 0
            already_destroyed = await c.fetchval(
                "SELECT COALESCE(sum(plant_qty), 0) FROM waste_manifest_lines WHERE batch_id=$1",
                b["id"]) or 0
            planned = b["plant_count"] or 0
            if already_cut + already_destroyed + body.plants_harvested > planned:
                raise HTTPException(
                    409,
                    f"batch {b['code']} holds {planned} plants;"
                    f" {already_cut} are already harvested and {already_destroyed}"
                    f" declared destroyed, so {body.plants_harvested} more would"
                    " over-declare the batch")

        # Gate 1 — the pre-harvest interval.
        blocks = await _phi_blocks(c, b, when)
        override_at = None
        if blocks:
            worst = blocks[0]
            if not body.phi_override_reason:
                raise HTTPException(
                    409,
                    f"batch {b['code']} is inside a pre-harvest interval:"
                    f" {worst['product']} carries a {worst['phi_days']}-day PHI and"
                    f" clears on {worst['phi_clear_on'].isoformat()}"
                    f" ({worst['days_remaining']} day(s) to go)")
            # An override is a QA release, not a recorder's own decision.
            if user["role"] not in _PHI_OVERRIDERS:
                raise HTTPException(
                    403,
                    "releasing a harvest inside a pre-harvest interval is a QA"
                    " decision — the person recording the cut cannot clear their own block")
            override_at = datetime.now(timezone.utc)

        row = await c.fetchrow(
            "INSERT INTO harvests(org_id, batch_id, room_id, lot_code, harvested_on,"
            " plants_harvested, wet_weight_g, phi_override_at, phi_override_by,"
            " phi_override_reason, harvested_by, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$11,$11) RETURNING *",
            user["org_id"], b["id"], room_id, lot, when,
            body.plants_harvested, body.wet_weight_g,
            override_at, user["id"] if override_at else None,
            body.phi_override_reason if override_at else None,
            user["id"], body.note)

        # THE EDGE. This is what the whole record exists for: from here a CoA
        # issued against the lot traces back to the cultivation batch, the
        # cultivar and the individual plants. ON CONFLICT DO NOTHING because the
        # edge is derived data — a re-run must not 500 on a row it would have
        # written identically.
        await c.execute(
            "INSERT INTO qc_batch_genealogy(org_id, parent_batch_id, child_batch_id,"
            " relation, quantity, unit, notes, created_by)"
            " VALUES ($1,$2,$3,'CULTIVATION',$4,'g',$5,$6)"
            " ON CONFLICT (org_id, parent_batch_id, child_batch_id) DO NOTHING",
            user["org_id"], b["code"], lot, body.wet_weight_g,
            f"harvest {when.isoformat()}", user["id"])

        await safe_emit(c, user, verb="harvest_recorded", object_type="harvest",
                        object_id=row["id"], recipients=[],
                        params={"lot_code": lot, "batch": b["code"],
                                "plants": body.plants_harvested,
                                "wet_weight_g": body.wet_weight_g,
                                "phi_override": bool(override_at)})
    return {"id": str(row["id"]), "lot_code": row["lot_code"], "status": row["status"],
            "batch_id": str(row["batch_id"]), "batch_code": b["code"],
            "harvested_on": _iso(row["harvested_on"]),
            "plants_harvested": row["plants_harvested"],
            "wet_weight_g": _num(row["wet_weight_g"]),
            "phi_override": bool(override_at),
            "genealogy_edge": {"parent_batch_id": b["code"], "child_batch_id": lot,
                               "relation": "CULTIVATION"}}


@router.post("/harvests/{harvest_id}/dry")
async def record_dry(harvest_id: str, body: DryIn,
                     user: dict = Depends(require_role(*_POST_HARVEST))):
    """Record what came out of the dry room. Gate 3 lives here.

    Re-recordable while the lot is open, because correcting a mis-keyed weight
    before the lot closes is ordinary and the alternative is a permanent wrong
    number. Once closed it is final."""
    async with rls(user) as c:
        h = await _harvest_or_404(c, harvest_id)
        if h["status"] == "closed":
            raise HTTPException(
                409, f"lot {h['lot_code']} is closed; its yield is final")
        total = body.dry_flower_g + (body.dry_trim_g or 0) + (body.dry_waste_g or 0)
        wet = float(h["wet_weight_g"])
        # Gate 3. Pre-checked for a message with the numbers in it; the schema's
        # harvests_yield_check is the backstop for any other route into the table.
        if total > wet:
            raise HTTPException(
                409,
                f"lot {h['lot_code']} came in at {wet:g} g wet and the dry weights"
                f" total {total:g} g — nothing gains mass in a dry room, so one of"
                " the two figures is wrong")
        row = await c.fetchrow(
            # Site-zone date, not CURRENT_DATE: CURRENT_DATE renders under the
            # session's TimeZone, so the same lot dried at 01:00 local would be
            # dated the previous day. Same reasoning as _site_today().
            "UPDATE harvests SET status='dried',"
            " dried_on=COALESCE($1::date, (now() AT TIME ZONE $2)::date),"
            " dry_flower_g=$3, dry_trim_g=$4, dry_waste_g=$5,"
            " note=COALESCE($6, note), updated_by=$7, updated_at=now()"
            " WHERE id=$8 RETURNING *",
            body.dried_on, _site_tz(), body.dry_flower_g, body.dry_trim_g,
            body.dry_waste_g, body.note, user["id"], harvest_id)
        loss = _loss_pct(wet, total)
        await safe_emit(c, user, verb="harvest_dried", object_type="harvest",
                        object_id=harvest_id, recipients=[],
                        params={"lot_code": h["lot_code"], "dry_total_g": total,
                                "loss_pct": loss})
    return {"id": harvest_id, "status": row["status"], "dried_on": _iso(row["dried_on"]),
            "dry_total_g": total, "moisture_loss_pct": loss,
            "implausible_loss": _implausible(loss)}


@router.post("/harvests/{harvest_id}/close")
async def close_harvest(harvest_id: str, body: CloseIn,
                        user: dict = Depends(require_role(*_POST_HARVEST))):
    """Gate 4: a lot cannot be closed before its yield is recorded. A closed
    record with no yield in it looks finished, which is worse than an open one."""
    async with rls(user) as c:
        h = await _harvest_or_404(c, harvest_id)
        if h["status"] == "closed":
            raise HTTPException(409, f"lot {h['lot_code']} is already closed")
        if h["status"] != "dried" or h["dry_flower_g"] is None:
            raise HTTPException(
                409, f"lot {h['lot_code']} has no dry weight yet — record the yield"
                     " before closing it")
        row = await c.fetchrow(
            "UPDATE harvests SET status='closed', closed_at=now(), closed_by=$1,"
            " note=COALESCE($2, note), updated_by=$1, updated_at=now()"
            " WHERE id=$3 RETURNING *", user["id"], body.note, harvest_id)
        await safe_emit(c, user, verb="harvest_closed", object_type="harvest",
                        object_id=harvest_id, recipients=[],
                        params={"lot_code": h["lot_code"]})
    return {"id": harvest_id, "status": row["status"], "closed_at": _iso(row["closed_at"]),
            "lot_code": row["lot_code"]}


# ── the yield report ─────────────────────────────────────────────────────────

@router.get("/yield")
async def yield_report(user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Per batch: what was planted, what came off, what was destroyed, and what is
    still standing — plus the two discrepancies neither module sees alone.

    `harvested_without_record` is the mirror of the destruction register's
    `unmanifested_destruction`: a batch CLOSED as harvested in cultivation with no
    harvest lot recorded against it. Cultivation says the crop came off; the yield
    register says nothing did, and there is no lot for a CoA to be issued against.

    `unaccounted` is arithmetic — planted minus harvested minus destroyed — and it
    is a DISCREPANCY only for a batch in a terminal phase. On a live batch it is
    simply the plants still in the room. The caller must interpret it by phase;
    `web/gf/harvest-view.js` does that in one predicate shared by the rows and the
    banner, the same way the destruction board does."""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT b.id, b.code, b.phase, b.plant_count, b.phase_since,"
            " cv.code AS cultivar_code, r.name AS room_name,"
            " COALESCE((SELECT sum(h.plants_harvested) FROM harvests h"
            "           WHERE h.batch_id=b.id), 0) AS plants_harvested,"
            " COALESCE((SELECT sum(l.plant_qty) FROM waste_manifest_lines l"
            "           WHERE l.batch_id=b.id), 0) AS plants_destroyed,"
            " (SELECT count(*) FROM harvests h WHERE h.batch_id=b.id) AS lot_count,"
            " (SELECT count(*) FROM harvests h WHERE h.batch_id=b.id"
            "         AND h.status <> 'closed') AS open_lots,"
            " (SELECT sum(h.wet_weight_g) FROM harvests h WHERE h.batch_id=b.id) AS wet_g,"
            " (SELECT sum(h.dry_flower_g) FROM harvests h WHERE h.batch_id=b.id) AS dry_flower_g,"
            " (SELECT sum(h.dry_trim_g) FROM harvests h WHERE h.batch_id=b.id) AS dry_trim_g,"
            " (SELECT sum(h.dry_waste_g) FROM harvests h WHERE h.batch_id=b.id) AS dry_waste_g,"
            # Only DRIED lots may enter the loss calculation. Including a wet lot
            # would divide a partial dry weight by the whole wet weight and report
            # a batch mid-dry-down as catastrophic loss.
            " (SELECT sum(h.wet_weight_g) FROM harvests h WHERE h.batch_id=b.id"
            "         AND h.dry_flower_g IS NOT NULL) AS wet_g_dried,"
            " (SELECT sum(h.plants_harvested) FROM harvests h WHERE h.batch_id=b.id"
            "         AND h.dry_flower_g IS NOT NULL) AS plants_dried"
            " FROM plant_batches b"
            " LEFT JOIN cultivars cv ON cv.id=b.cultivar_id"
            " LEFT JOIN rooms r ON r.id=b.room_id"
            " ORDER BY b.phase_since DESC NULLS LAST, b.code")
    out = []
    for r in rows:
        planned = r["plant_count"] or 0
        harvested = int(r["plants_harvested"] or 0)
        destroyed = int(r["plants_destroyed"] or 0)
        flower = _num(r["dry_flower_g"])
        trim = _num(r["dry_trim_g"])
        waste = _num(r["dry_waste_g"])
        dry_total = None
        if any(v is not None for v in (flower, trim, waste)):
            dry_total = sum(v for v in (flower, trim, waste) if v is not None)
        loss = _loss_pct(r["wet_g_dried"], dry_total)
        plants_dried = int(r["plants_dried"] or 0)
        out.append({
            "batch_id": str(r["id"]), "code": r["code"], "phase": r["phase"],
            "cultivar_code": r["cultivar_code"], "room_name": r["room_name"],
            "plant_count": planned,
            "plants_harvested": harvested,
            "plants_destroyed": destroyed,
            "unaccounted": max(0, planned - harvested - destroyed),
            "lot_count": int(r["lot_count"] or 0),
            "open_lots": int(r["open_lots"] or 0),
            "wet_g": _num(r["wet_g"]),
            "dry_flower_g": flower, "dry_trim_g": trim, "dry_waste_g": waste,
            "dry_total_g": dry_total,
            "moisture_loss_pct": loss,
            "implausible_loss": _implausible(loss),
            "dry_flower_g_per_plant": (
                round(flower / plants_dried, 1)
                if flower is not None and plants_dried > 0 else None),
            # Closed as harvested with no lot — the discrepancy this report exists
            # to surface, and invisible to cultivation and QC on their own.
            "harvested_without_record": r["phase"] == "harvested" and not r["lot_count"],
            # Should be impossible (create_harvest and waste.add_line both refuse
            # it); reported anyway, because a guard nobody checks against the data
            # is a guard nobody notices has been bypassed by a direct SQL fix.
            "over_declared": harvested + destroyed > planned,
        })
    return {"batches": out}
