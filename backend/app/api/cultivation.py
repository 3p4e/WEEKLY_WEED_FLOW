"""Cultivation — cultivar master, coded batches, per-plant identity, phase events.

Phase 1 of the cultivation department (docs/CULTIVATION-DESIGN-2026-07.md), the
functional layer over migration 0045. It extends the facility board's occupancy
model into the identity the owner confirmed for the incoming genetics:

  - a `cultivars` master retiring free-text strains;
  - `plant_batches.code` (e.g. GP072501) and `cultivar_id` — one batch is one
    cultivar in one flowering room;
  - individual `plants` with an id `<clone-date>_<cultivar>_<seq>`;
  - dated batch-level `plant_phase_events`.

Access model, same shape as facility.py:
  read   — every role above base USER (ELEVATED_ROLES);
  write  — cultivation manager (CU_MGR), QA manager (QA_MGR), executives and
           ADMIN (_WRITERS): the cultivar master, registering a batch,
           materialising its plant ids, and moving it through its phases.
           The owner's model (2026-09-05) is that "the QA manager, the CEO and
           COO as well as the cultivation manager can register a batch" and
           that "QA should be able to move a batch through its phases or edit
           the cultivar master" — so QA is a floor writer here, not a reader.
           _REGISTRARS is kept as an alias of _WRITERS because the two sets
           were once different and the distinction is worth naming at the
           routes that register rather than move.

REGISTERING AGAINST A PRODUCT. A batch is grown to one of the official ImB
products (qc_products — GP_THC26:CBD1 and its window), chosen at registration
and carried as plant_batches.product_id. It is a TARGET, not a verdict: what
the lot turns out to be is decided by the Certificate of Quality against the
product's printed window, not here.

THE PLAN'S EXPECTED DATES. The owner stated the plan's legs on 2026-09-05:
cloning 7-14 days (imported clones may stay some days more for quarantine and
acclimatisation, but leave at roughly the same time), vegetation 14-17 days,
flowering 6-9 weeks with the harvest date set by progressive trichome
maturation tracking under a microscope. _PHASE_PLAN encodes exactly that and
nothing more: the server computes the expected window for the phase a batch is
in and the board renders it verbatim, the same discipline the pre-harvest
interval already uses. No date is a promise — a window is guidance, and the
trichome record is what actually decides a cut.

REGISTERING FROM THE PRODUCT SPECIFICATION. The batch form chooses its cultivar
from the ImB Product Specifications — the per-strain potency ladders in
qc_potency_specs, which carry the strain name and its potency grades — so
GET /cultivars returns each cultivar WITH its current specification (APPROVED
if there is one, else the newest DRAFT, flagged as such). GET /batch-code
suggests the next batch number for a cultivar: the constant head is the
cultivar code (GP072501 = GP + period + sequence), and the tail is derived
from what the org already has.

THE AUDIT-LOCK RULE, enforced here rather than in the schema. app.fn_audit_row()
holds one global advisory lock per audited write until commit. A ~2000-plant
room therefore must never be created, moved, or closed as 2000 audited row
writes in one transaction — it would freeze every other audited write in the
database for the duration. So:
  - phase moves are ONE plant_batches update + ONE phase event (never per plant);
  - generating the individual plant rows is a SEPARATE, CHUNKED, RESUMABLE
    endpoint (POST /batches/{id}/plants) that commits ~_PLANT_CHUNK at a time,
    so other writers interleave between chunks and an interrupted fill resumes
    from the last seq rather than restarting.
"""
import json
from datetime import date, timedelta

from app.worktime import SITE_TODAY_SQL, facility_today

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/cultivation", tags=["cultivation"])

_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR", "QA_MGR")
# The same set, named at the routes that REGISTER a batch rather than move it:
# registering and materialising plant ids are two halves of one act, and the
# owner asked for both (plus the moves) to be open to QA.
_REGISTRARS = _WRITERS
# Widened vs facility's set: nursery split from clone, plus the terminal states.
# Must stay in step with plant_batches_phase_check in migration 0045.
_PHASES = ("nursery", "clone", "veg", "flower", "mother", "drying", "harvested", "destroyed")
_TERMINAL = ("harvested", "destroyed")

# How many plant rows are committed per transaction when materialising a batch.
# Small enough that the audit chain lock is released frequently (other writers
# interleave), large enough that filling a 2000-plant room is not thousands of
# round trips. Each chunk is its own transaction, so a failure leaves a valid
# partial fill the next call resumes.
_PLANT_CHUNK = 50
_MAX_PLANTS = 100000

# The cultivation plan's legs, in days, as the owner stated them (2026-09-05).
# Code constants rather than a settings table for the same reason the phase
# task templates are: the plan asks for something real to be shown, not for a
# new configuration surface. Nursery has no leg of its own — it is a stop
# INSIDE the cloning leg, so both are measured from the day the batch entered
# the clone rooms.
_PHASE_PLAN = {"clone": (7, 14), "nursery": (7, 14), "veg": (14, 17), "flower": (42, 63)}
_CLONE_LEG = ("clone", "nursery")
# Imported clones "can stay some days more for the quarantine and
# accommodation period" — the earliest they leave is unchanged, the latest
# stretches. Applied to the cloning leg only.
_IMPORT_QUARANTINE_DAYS = 7
_CLONE_SOURCES = ("own_stock", "imported")
# What the batch is expected to do next, for the board's "Next" line.
_NEXT_PHASE = {"clone": "veg", "nursery": "veg", "veg": "flower", "flower": "harvest"}


class CultivarIn(BaseModel):
    code: str = Field(max_length=64, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(max_length=120)
    name_mk: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)


class CultivarPatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    name_mk: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class BatchIn(BaseModel):
    room_id: str
    cultivar_id: str
    # The official product this batch is grown to (qc_products). Optional: a
    # strain whose catalogue page is not approved yet still gets a batch.
    product_id: str | None = None
    # own_stock | imported — imported clones carry a quarantine allowance, so
    # this changes the expected date, which is why it is an enum and not a note.
    clone_source: str | None = None
    code: str = Field(max_length=64, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    plant_count: int = Field(ge=0, le=_MAX_PLANTS)  # the target/planned headcount
    phase: str = "clone"
    clone_date: date | None = None
    phase_since: date | None = None
    note: str | None = Field(default=None, max_length=500)


class BatchPatch(BaseModel):
    """What may be corrected on a registered batch. Deliberately narrow: the
    code, cultivar, room, phase and count are the batch's identity and its
    lifecycle, and each already has its own route or is immutable."""
    product_id: str | None = None
    clone_source: str | None = None
    note: str | None = Field(default=None, max_length=500)


class MoveIn(BaseModel):
    to_phase: str
    to_room_id: str | None = None
    occurred_on: date | None = None
    reason: str | None = Field(default=None, max_length=500)


def _check_phase(phase: str | None) -> None:
    if phase is not None and phase not in _PHASES:
        raise HTTPException(422, f"phase must be one of: {', '.join(_PHASES)}")


# ── Phase 3: phase-transition task generation (docs/CULTIVATION-DESIGN-2026-07.md §5) ──
#
#     "Phase transitions generate the per-phase task sets, and tasks reference
#      the batch they act on, so the batch record accumulates from work
#      actually performed. This is the half that makes the two existing
#      halves one department."
#
# Static, code-defined templates — the same posture as the dept-template
# quick-add presets (web/gf/dept-templates.js) that already name this exact
# vocabulary for the cultivation department (Watering, Defoliation, IPM check,
# Transplanting), so a generated task reads like one a grower would have typed
# by hand rather than a new, unfamiliar list. An admin-editable template TABLE
# was considered and dropped: the design doc asks the transition to generate
# something real, not for a new configuration surface, and a static list costs
# nothing to revisit later if the owner wants it editable.
#
# Bilingual titles use the platform's stored convention, "Македонски |
# English" (see GF.ai.bilingual in web/gf/integrate.js: "the bilingual МК | EN
# format the platform stores everything in") — so a generated task is
# indistinguishable in the UI from one a human typed and ran through the AI
# bilingual pass.
_PHASE_TASK_TEMPLATES: dict = {
    "veg": [
        ("Трансплантирање — потврда дека е засадено", "Transplanting — confirm settled in"),
        ("ИПМ — скаутинг", "IPM — scouting check"),
        ("Наводнување — преглед на распоред", "Feeding schedule review"),
    ],
    "flower": [
        # The owner's rule: the harvest date is set by progressive trichome
        # maturation tracking under a stereo or digital microscope, WITH
        # DOCUMENTED RECORDS. The task is the prompt; trichome_checks is the
        # record (app/api/trichome.py).
        ("Проверка на зрелост на трихоми — микроскоп, документиран запис",
         "Trichome maturation check — microscope, documented record"),
        ("Дефолијација — долен балдахин", "Defoliation — lower canopy"),
        ("ИПМ — скаутинг пред жетва", "IPM — pre-harvest scouting check"),
        ("Наводнување — премин на цветна исхрана", "Feeding schedule review — bloom transition"),
    ],
}


async def _generate_phase_tasks(c, user: dict, batch, to_phase: str, occurred_on) -> list:
    """Auto-generate the per-phase task set for a batch entering `to_phase`.

    IDEMPOTENT PER (batch, phase): each generated task is tagged
    `attributes.phase_gen = <phase>`, checked before generating again — a
    batch that moves veg -> flower -> veg -> flower (a correction, not the
    common case) gets the flower set exactly once, not once per visit. Two
    copies of a plausible-reads-as-real task set would be worse than none.

    Returns the ids it created (empty if the phase has no template, the batch
    already has this phase's set, or the org has no cultivation department or
    no calendar week covering `occurred_on` — every one of those is a reason
    to generate NOTHING, never a reason to fail the move itself: the phase
    transition is the load-bearing write; this is a convenience layered on
    top of it, and a convenience that can 500 the record it rides on is not
    one worth having."""
    template = _PHASE_TASK_TEMPLATES.get(to_phase)
    if not template:
        return []
    already = await c.fetchval(
        "SELECT 1 FROM tasks WHERE batch_id=$1 AND attributes->>'phase_gen'=$2 LIMIT 1",
        batch["id"], to_phase)
    if already:
        return []
    dept = await c.fetchrow(
        "SELECT id, name FROM departments WHERE org_id=$1 AND code='cultivation'", user["org_id"])
    if dept is None:
        return []
    week = await c.fetchrow(
        "SELECT id, starts_on FROM calendar_weeks WHERE org_id=$1 AND starts_on<=$2 AND ends_on>=$2",
        user["org_id"], occurred_on)
    if week is None:
        return []
    ids = []
    for title_mk, title_en in template:
        row = await c.fetchrow(
            "INSERT INTO tasks(org_id,user_id,title,status,priority,task_type,department,"
            " department_id,week_id,week_start,attributes,batch_id,created_by,updated_by)"
            " VALUES ($1,$2,$3,'pending','medium','other',$4,$5,$6,$7,$8,$9,$2,$2) RETURNING id",
            user["org_id"], user["id"], f"{title_mk} | {title_en}", dept["name"], dept["id"],
            week["id"], week["starts_on"], {"phase_gen": to_phase}, batch["id"])
        ids.append(str(row["id"]))
    return ids


async def _site_today(c):
    """Today as POSTGRES sees the facility — the same clock SITE_TODAY_SQL
    stamps rows with, so an expected date computed here can never be a day off
    from the date the record carries (harvest.py resolves it the same way)."""
    return await c.fetchval(f"SELECT {SITE_TODAY_SQL}")  # nosec B608


async def _product_or_422(c, product_id, cultivar_id):
    """The product a batch is grown to: it must exist, be APPROVED, and belong
    to the batch's own cultivar — a GP batch targeting an OPM product would
    print a wrong grade on everything downstream."""
    uuid_or_422(product_id, "Unknown product")
    row = await c.fetchrow(
        "SELECT id, product_code, status, cultivar_id FROM qc_products WHERE id=$1", product_id)
    if row is None:
        raise HTTPException(422, "Unknown product")
    if row["status"] != "APPROVED":
        raise HTTPException(422, f"{row['product_code']} is {row['status']} — a batch is"
                                 " registered against an APPROVED product specification")
    if str(row["cultivar_id"]) != str(cultivar_id):
        raise HTTPException(422, f"{row['product_code']} is not this cultivar's product")
    return row


def _check_clone_source(v) -> None:
    if v is not None and v not in _CLONE_SOURCES:
        raise HTTPException(422, f"clone_source must be one of: {', '.join(_CLONE_SOURCES)}")


def _plan_out(r, today) -> dict:
    """Where the batch is against the plan, computed here so the board renders
    dates rather than deriving them (two copies of an interval is how a board
    and a record come to disagree — the same rule the PHI clearance keeps).

    A phase with no stated leg (mother, drying, terminal) yields nothing rather
    than a guess. `window_state` compares TODAY with the expected window:
    early = still inside it, in_window = the window is open now, late = past it.
    Late is not a fault: flowering ends when the trichomes say so."""
    phase, since = r["phase"], r["phase_since"]
    out = {"days_in_phase": (today - since).days if since else None,
           "expected_next_phase": _NEXT_PHASE.get(phase),
           "expected_from": None, "expected_to": None, "window_state": None,
           "harvest_window_from": None, "harvest_window_to": None}
    leg = _PHASE_PLAN.get(phase)
    if leg is None or since is None:
        return out
    lo, hi = leg
    # The cloning leg is measured from the day the batch ENTERED it, so a batch
    # that moved clone -> nursery does not restart the count.
    start = since
    if phase in _CLONE_LEG:
        start = r.get("clone_leg_started_on") or since
        if r.get("clone_source") == "imported":
            hi += _IMPORT_QUARANTINE_DAYS
    frm, to = start + timedelta(days=lo), start + timedelta(days=hi)
    out["expected_from"], out["expected_to"] = frm.isoformat(), to.isoformat()
    out["window_state"] = "early" if today < frm else ("in_window" if today <= to else "late")
    if phase == "flower":
        out["harvest_window_from"], out["harvest_window_to"] = out["expected_from"], out["expected_to"]
    return out


async def _batch_or_404(c, batch_id: str):
    uuid_or_404(batch_id, "Batch not found")
    row = await c.fetchrow(
        "SELECT b.*, cv.code AS cultivar_code, r.name AS room_name"
        " FROM plant_batches b"
        " LEFT JOIN cultivars cv ON cv.id = b.cultivar_id"
        " LEFT JOIN rooms r ON r.id = b.room_id"
        " WHERE b.id=$1", batch_id)
    if row is None:
        raise HTTPException(404, "Batch not found")
    return row


async def _room_or_422(c, room_id: str):
    uuid_or_422(room_id, "Unknown or inactive room")
    room = await c.fetchrow("SELECT id, name FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


async def _cultivar_or_422(c, cultivar_id: str):
    uuid_or_422(cultivar_id, "Unknown or inactive cultivar")
    cv = await c.fetchrow(
        "SELECT id, code, name FROM cultivars WHERE id=$1 AND is_active", cultivar_id)
    if cv is None:
        raise HTTPException(422, "Unknown or inactive cultivar")
    return cv


# ── cultivars ────────────────────────────────────────────────────────────────

_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}


def _spec_out(r) -> dict | None:
    """The cultivar's product specification as the batch form shows it: the
    ladder's identity and its grades (Spec I is the top range). None when the
    cultivar has no ladder at all — the form then says so instead of showing
    an empty table."""
    if r["spec_id"] is None:
        return None
    tiers = r["spec_tiers"]
    tiers = json.loads(tiers) if isinstance(tiers, str) else (tiers or [])
    return {
        "id": str(r["spec_id"]), "spec_code": r["spec_code"], "version": r["spec_version"],
        "status": r["spec_status"],
        "floor_pct": float(r["spec_floor"]) if r["spec_floor"] is not None else None,
        "tiers": [{"tier": t["tier"], "spec": f"Spec {_ROMAN.get(t['tier'], t['tier'])}",
                   "range_min": t["range_min"], "range_max": t["range_max"],
                   "nominal": t["nominal"]} for t in tiers],
    }


@router.get("/cultivars")
async def list_cultivars(user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Every cultivar WITH its product specification — the APPROVED potency
    ladder if one exists, else the newest DRAFT (its status says which), else
    none. One query: the lateral picks the ladder, the sub-select folds its
    grades, so the batch form can show strain + grades without a round trip
    per cultivar."""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT cv.id, cv.code, cv.name, cv.name_mk, cv.note, cv.is_active,"
            " ps.id AS spec_id, ps.spec_code, ps.version AS spec_version,"
            " ps.status AS spec_status, ps.floor_pct AS spec_floor,"
            " (SELECT json_agg(json_build_object('tier', g.tier, 'range_min', g.range_min,"
            "     'range_max', g.range_max, 'nominal', g.nominal) ORDER BY g.tier)"
            "   FROM qc_potency_spec_ranges g WHERE g.potency_spec_id = ps.id) AS spec_tiers"
            " FROM cultivars cv"
            " LEFT JOIN LATERAL ("
            "   SELECT s.id, s.spec_code, s.version, s.status, s.floor_pct"
            "   FROM qc_potency_specs s WHERE s.cultivar_id = cv.id"
            "   AND s.status IN ('APPROVED','DRAFT')"
            "   ORDER BY (s.status = 'APPROVED') DESC, s.updated_at DESC LIMIT 1) ps ON true"
            " ORDER BY cv.is_active DESC, cv.code")
    return {"cultivars": [
        {"id": str(r["id"]), "code": r["code"], "name": r["name"],
         "name_mk": r["name_mk"], "note": r["note"], "is_active": r["is_active"],
         "spec": _spec_out(r)}
        for r in rows]}


@router.post("/cultivars", status_code=201)
async def create_cultivar(body: CultivarIn, user: dict = Depends(require_role(*_WRITERS))):
    """Idempotent on (org, code), same contract as POST /facility/rooms."""
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO cultivars(org_id, code, name, name_mk, note, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$6)"
            " ON CONFLICT (org_id, code) DO NOTHING RETURNING *",
            user["org_id"], body.code, body.name, body.name_mk, body.note, user["id"])
        if row is None:
            row = await c.fetchrow(
                "SELECT * FROM cultivars WHERE org_id=$1 AND code=$2",
                user["org_id"], body.code)
    return {"id": str(row["id"]), "code": row["code"], "name": row["name"],
            "name_mk": row["name_mk"], "note": row["note"], "is_active": row["is_active"]}


@router.patch("/cultivars/{cultivar_id}")
async def update_cultivar(cultivar_id: str, body: CultivarPatch,
                          user: dict = Depends(require_role(*_WRITERS))):
    uuid_or_404(cultivar_id, "Cultivar not found")
    patch = body.model_dump(exclude_unset=True)
    fields, args = [], []
    for col, val in patch.items():
        if val is None and col not in ("name_mk", "note"):
            continue
        args.append(val); fields.append(f"{col}=${len(args)}")
    if not fields:
        return {"ok": True, "noop": True}
    args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
    args.append(cultivar_id)
    async with rls(user) as c:
        row = await c.fetchrow(
            f"UPDATE cultivars SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING id", *args)
    if row is None:
        raise HTTPException(404, "Cultivar not found")
    return {"ok": True}


# ── batches ──────────────────────────────────────────────────────────────────

@router.get("/batch-code")
async def next_batch_code(cultivar_id: str = Query(...),
                          user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Suggest the next batch number for a cultivar.

    The owner's example GP072501 reads as <cultivar code> <period> <sequence>:
    the cultivar code is the constant head (the same head every plant id in
    the batch carries), the period is taken here as MMYY of the facility's
    today, and the sequence is one past the batches this org already holds
    for that cultivar in that period. The code field is pre-filled with the
    whole suggestion and stays editable; only the head is fixed. If the
    facility's period convention turns out to differ (ISO week, YYMM), it is
    this one rule that changes."""
    async with rls(user) as c:
        cv = await _cultivar_or_422(c, cultivar_id)
        period = facility_today().strftime("%m%y")
        n = await c.fetchval(
            "SELECT count(*) FROM plant_batches WHERE org_id=$1 AND code LIKE $2",
            user["org_id"], f"{cv['code']}{period}%")
    seq = int(n or 0) + 1
    return {"prefix": cv["code"], "period": period, "seq": seq,
            "suggested": f"{cv['code']}{period}{seq:02d}"}


@router.get("/batches")
async def list_batches(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                       active: bool = Query(True)):
    async with rls(user) as c:
        today = await _site_today(c)
        rows = await c.fetch(
            "SELECT b.id, b.code, b.room_id, b.cultivar_id, b.strain, b.plant_count,"
            " b.phase, b.phase_since, b.note, b.is_active, b.product_id, b.clone_source,"
            " cv.code AS cultivar_code, cv.name AS cultivar_name, r.name AS room_name,"
            " pr.product_code, pr.grade AS product_grade,"
            " pr.window_min AS product_window_min, pr.window_max AS product_window_max,"
            " (SELECT count(*) FROM plants p WHERE p.batch_id=b.id) AS plants_materialised,"
            " (SELECT count(*) FROM plants p WHERE p.batch_id=b.id AND p.status='active') AS plants_active,"
            # The day the batch entered the cloning leg — nursery is a stop
            # inside it, so the expected date must not restart on the move.
            " (SELECT min(e.occurred_on) FROM plant_phase_events e"
            "   WHERE e.batch_id=b.id AND e.to_phase = ANY($2::text[])) AS clone_leg_started_on,"
            " tc.checked_on AS tc_on, tc.verdict AS tc_verdict, tc.pct_amber AS tc_amber,"
            " tc.instrument AS tc_instrument"
            " FROM plant_batches b"
            " LEFT JOIN cultivars cv ON cv.id=b.cultivar_id"
            " LEFT JOIN rooms r ON r.id=b.room_id"
            " LEFT JOIN qc_products pr ON pr.id=b.product_id"
            " LEFT JOIN LATERAL (SELECT checked_on, verdict, pct_amber, instrument"
            "   FROM trichome_checks t WHERE t.batch_id=b.id"
            "   ORDER BY t.checked_on DESC, t.created_at DESC LIMIT 1) tc ON true"
            " WHERE ($1::bool IS FALSE OR b.is_active)"
            " ORDER BY b.phase_since DESC, b.code",
            active, list(_CLONE_LEG))
    return {"batches": [
        {"id": str(r["id"]), "code": r["code"],
         "room_id": str(r["room_id"]) if r["room_id"] else None, "room_name": r["room_name"],
         "cultivar_id": str(r["cultivar_id"]) if r["cultivar_id"] else None,
         "cultivar_code": r["cultivar_code"], "cultivar_name": r["cultivar_name"],
         "strain": r["strain"], "plant_count": r["plant_count"], "phase": r["phase"],
         "phase_since": r["phase_since"].isoformat() if r["phase_since"] else None,
         "note": r["note"], "is_active": r["is_active"],
         "product_id": str(r["product_id"]) if r["product_id"] else None,
         "product_code": r["product_code"],
         "product_grade": float(r["product_grade"]) if r["product_grade"] is not None else None,
         "product_window": ([float(r["product_window_min"]), float(r["product_window_max"])]
                            if r["product_window_min"] is not None else None),
         "clone_source": r["clone_source"],
         "plants_materialised": r["plants_materialised"],
         "plants_active": r["plants_active"],
         # A check that was never taken is absent, never a neutral verdict.
         "latest_trichome": ({"checked_on": r["tc_on"].isoformat(), "verdict": r["tc_verdict"],
                              "pct_amber": float(r["tc_amber"]) if r["tc_amber"] is not None else None,
                              "instrument": r["tc_instrument"]} if r["tc_on"] else None),
         **_plan_out(r, today)}
        for r in rows]}


@router.post("/batches", status_code=201)
async def create_batch(body: BatchIn, user: dict = Depends(require_role(*_REGISTRARS))):
    """Create the batch RECORD only — fast and atomic. The individual plant rows
    are materialised separately via POST /batches/{id}/plants, because ~2000
    audited inserts must not ride in one transaction (see module header)."""
    _check_phase(body.phase)
    if body.phase in _TERMINAL:
        raise HTTPException(422, "a new batch cannot start in a terminal phase")
    _check_clone_source(body.clone_source)
    async with rls(user) as c:
        await _room_or_422(c, body.room_id)
        cv = await _cultivar_or_422(c, body.cultivar_id)
        product = None
        if body.product_id:
            product = await _product_or_422(c, body.product_id, cv["id"])
        dup = await c.fetchrow(
            "SELECT id FROM plant_batches WHERE org_id=$1 AND code=$2",
            user["org_id"], body.code)
        if dup is not None:
            raise HTTPException(409, f"batch code {body.code} already exists")
        row = await c.fetchrow(
            # SITE_TODAY_SQL is a module constant rendered at import; data is bound.
            "INSERT INTO plant_batches(org_id, room_id, cultivar_id, code, strain,"  # nosec B608
            " plant_count, phase, phase_since, note, product_id, clone_source,"
            " created_by, updated_by)"
            f" VALUES ($1,$2,$3,$4,$5,$6,$7,COALESCE($8::date,{SITE_TODAY_SQL}),$9,$10,$11,$12,$12)"
            " RETURNING *",
            user["org_id"], body.room_id, body.cultivar_id, body.code, cv["name"],
            body.plant_count, body.phase, body.phase_since, body.note,
            product["id"] if product else None, body.clone_source, user["id"])
        await c.execute(
            # The only interpolation is SITE_TODAY_SQL — a module constant
            # rendered from settings.snapshot_tz at import, quote-doubled;
            # user data travels exclusively in the bound parameters.
            "INSERT INTO plant_phase_events(org_id, batch_id, event, to_phase, qty,"  # nosec B608
            " to_room_id, occurred_on, created_by)"
            f" VALUES ($1,$2,'create',$3,$4,$5,COALESCE($6::date,{SITE_TODAY_SQL}),$7)",
            user["org_id"], row["id"], body.phase, body.plant_count, body.room_id,
            body.clone_date or body.phase_since, user["id"])
        await safe_emit(c, user, verb="batch_added", object_type="plant_batch",
                        object_id=row["id"], recipients=[],
                        params={"code": row["code"], "cultivar": cv["code"],
                                "plant_count": row["plant_count"], "phase": row["phase"],
                                "product_code": product["product_code"] if product else None})
    return {"id": str(row["id"]), "code": row["code"], "cultivar_id": body.cultivar_id,
            "room_id": body.room_id, "plant_count": row["plant_count"],
            "phase": row["phase"], "phase_since": row["phase_since"].isoformat(),
            "product_id": str(row["product_id"]) if row["product_id"] else None,
            "product_code": product["product_code"] if product else None,
            "clone_source": row["clone_source"]}


@router.patch("/batches/{batch_id}")
async def update_batch(batch_id: str, body: BatchPatch,
                       user: dict = Depends(require_role(*_WRITERS))):
    """Correct a registered batch's target product, clone source or note.

    Narrow on purpose: the code, cultivar, room, phase and count are the
    batch's identity and its lifecycle, and each has its own route or is
    immutable. This exists because the product catalogue arrives after the
    batches do — an open batch has to be able to name the product it is
    grown to without being re-registered."""
    patch = body.model_dump(exclude_unset=True)
    _check_clone_source(patch.get("clone_source"))
    async with rls(user) as c:
        b = await _batch_or_404(c, batch_id)
        if "product_id" in patch and patch["product_id"] is not None:
            await _product_or_422(c, patch["product_id"], b["cultivar_id"])
        fields, args = [], []
        for col, val in patch.items():
            # An explicit null CLEARS these three; an absent key leaves them.
            args.append(val); fields.append(f"{col}=${len(args)}")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(batch_id)
        await c.execute(
            # Column names come from BatchPatch's own fields; values are bound.
            f"UPDATE plant_batches SET {', '.join(fields)}, updated_at=now()"  # nosec B608
            f" WHERE id=${len(args)}", *args)
        row = await c.fetchrow(
            "SELECT b.*, pr.product_code FROM plant_batches b"
            " LEFT JOIN qc_products pr ON pr.id=b.product_id WHERE b.id=$1", batch_id)
    return {"id": batch_id, "code": row["code"],
            "product_id": str(row["product_id"]) if row["product_id"] else None,
            "product_code": row["product_code"], "clone_source": row["clone_source"],
            "note": row["note"]}


@router.post("/batches/{batch_id}/plants")
async def generate_plants(batch_id: str, user: dict = Depends(require_role(*_REGISTRARS))):
    """Materialise the individual plant rows up to the batch's plant_count.

    CHUNKED and RESUMABLE: it starts from the highest existing seq and inserts in
    _PLANT_CHUNK-sized transactions, so an interrupted fill is completed by
    calling again, and each chunk releases the audit chain lock. Plant id is
    `<clone-date>_<cultivar-code>_<seq>` with seq zero-padded to 4."""
    async with rls(user) as c:
        b = await _batch_or_404(c, batch_id)
        if b["cultivar_id"] is None:
            raise HTTPException(422, "batch has no cultivar; cannot form plant ids")
        target = b["plant_count"]
        have = await c.fetchval(
            "SELECT COALESCE(max(seq), 0) FROM plants WHERE batch_id=$1", batch_id)
        clone_ev = await c.fetchval(
            "SELECT occurred_on FROM plant_phase_events WHERE batch_id=$1 AND event='create'"
            " ORDER BY created_at LIMIT 1", batch_id)
        cultivar_code = b["cultivar_code"] or "NA"
        prefix = (clone_ev or b["phase_since"] or facility_today()).strftime("%Y%m%d")

    if have >= target:
        return {"batch_id": batch_id, "target": target, "created": 0,
                "materialised": have, "complete": True}

    created = 0
    seq = have + 1
    while seq <= target:
        top = min(seq + _PLANT_CHUNK - 1, target)
        rows = [
            (user["org_id"], batch_id, b["room_id"], b["cultivar_id"],
             f"{prefix}_{cultivar_code}_{n:04d}", clone_ev, n, user["id"])
            for n in range(seq, top + 1)
        ]
        # Fresh rls() per chunk = fresh transaction = the audit lock is taken and
        # released per chunk, not held across the whole fill.
        async with rls(user) as c:
            await c.executemany(
                "INSERT INTO plants(org_id, batch_id, room_id, cultivar_id, plant_code,"
                " clone_date, seq, created_by, updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$8)"
                " ON CONFLICT (batch_id, seq) DO NOTHING", rows)
        created += len(rows)
        seq = top + 1

    async with rls(user) as c:
        materialised = await c.fetchval(
            "SELECT count(*) FROM plants WHERE batch_id=$1", batch_id)
    return {"batch_id": batch_id, "target": target, "created": created,
            "materialised": materialised, "complete": materialised >= target}


@router.get("/batches/{batch_id}/plants")
async def list_plants(batch_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES)),
                      limit: int = Query(200, ge=1, le=2000),
                      offset: int = Query(0, ge=0),
                      status: str | None = Query(None)):
    uuid_or_404(batch_id, "Batch not found")
    async with rls(user) as c:
        total = await c.fetchval(
            "SELECT count(*) FROM plants WHERE batch_id=$1"
            " AND ($2::text IS NULL OR status=$2)", batch_id, status)
        rows = await c.fetch(
            "SELECT id, plant_code, seq, status, status_since, clone_date, reason"
            " FROM plants WHERE batch_id=$1 AND ($2::text IS NULL OR status=$2)"
            " ORDER BY seq LIMIT $3 OFFSET $4", batch_id, status, limit, offset)
    return {"batch_id": batch_id, "total": total, "limit": limit, "offset": offset,
            "plants": [
                {"id": str(r["id"]), "plant_code": r["plant_code"], "seq": r["seq"],
                 "status": r["status"],
                 "status_since": r["status_since"].isoformat() if r["status_since"] else None,
                 "clone_date": r["clone_date"].isoformat() if r["clone_date"] else None,
                 "reason": r["reason"]}
                for r in rows]}


@router.post("/batches/{batch_id}/move")
async def move_batch(batch_id: str, body: MoveIn,
                     user: dict = Depends(require_role(*_WRITERS))):
    """Record a whole-batch phase transition: ONE plant_batches update + ONE
    phase event. Never touches individual plant rows (see module header)."""
    _check_phase(body.to_phase)
    async with rls(user) as c:
        b = await _batch_or_404(c, batch_id)
        if b["phase"] in _TERMINAL:
            raise HTTPException(409, f"batch is {b['phase']}; it cannot move again")
        to_room = b["room_id"]
        if body.to_room_id is not None:
            room = await _room_or_422(c, body.to_room_id)
            to_room = room["id"]
        row = await c.fetchrow(
            "UPDATE plant_batches SET phase=$1, room_id=$2,"
            f" phase_since=COALESCE($3::date, {SITE_TODAY_SQL}), updated_by=$4, updated_at=now(),"
            " is_active = CASE WHEN $1 = ANY($5::text[]) THEN false ELSE is_active END"
            " WHERE id=$6 RETURNING *",
            body.to_phase, to_room, body.occurred_on, user["id"],
            list(_TERMINAL), batch_id)
        await c.execute(
            # Same shape as above: SITE_TODAY_SQL only, parameters carry the data.
            "INSERT INTO plant_phase_events(org_id, batch_id, event, from_phase, to_phase,"  # nosec B608
            " qty, to_room_id, occurred_on, reason, created_by)"
            f" VALUES ($1,$2,$3,$4,$5,$6,$7,COALESCE($8::date,{SITE_TODAY_SQL}),$9,$10)",
            user["org_id"], batch_id,
            ("harvest" if body.to_phase == "harvested"
             else "destroy" if body.to_phase == "destroyed" else "move"),
            b["phase"], body.to_phase, b["plant_count"], to_room,
            body.occurred_on, body.reason, user["id"])
        # A batch reaching a terminal phase settles its still-active plants to the
        # matching terminal status — a SINGLE bulk UPDATE (bounded by plant count,
        # and only ever run once per batch at end of life, not on every move).
        if body.to_phase in _TERMINAL:
            await c.execute(
                # Same shape as above: SITE_TODAY_SQL only, parameters carry the data.
                f"UPDATE plants SET status=$1, status_since=COALESCE($2::date, {SITE_TODAY_SQL}),"  # nosec B608
                " updated_by=$3, updated_at=now()"
                " WHERE batch_id=$4 AND status='active'",
                "harvested" if body.to_phase == "harvested" else "destroyed",
                body.occurred_on, user["id"], batch_id)
        # Phase 3: the per-phase task set, generated on the SAME transition
        # that just committed — see _generate_phase_tasks for why it never
        # raises (a template miss / no department / no week is a reason to
        # generate nothing, never a reason to fail the move that already
        # happened above).
        generated = await _generate_phase_tasks(
            c, user, {"id": batch_id}, body.to_phase,
            body.occurred_on or facility_today())
        await safe_emit(c, user, verb="batch_moved", object_type="plant_batch",
                        object_id=batch_id, recipients=[],
                        params={"code": b["code"], "old_phase": b["phase"],
                                "phase": body.to_phase, "generated_tasks": len(generated)})
    return {"id": batch_id, "code": row["code"], "phase": row["phase"],
            "phase_since": row["phase_since"].isoformat(), "is_active": row["is_active"],
            "generated_task_ids": generated}


@router.get("/batches/{batch_id}/tasks")
async def batch_tasks(batch_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """The batch record accumulating from work actually performed (§5, Phase
    3) — every task, auto-generated or hand-linked, that carries this batch's
    id. Read-only; linking a task to a batch happens through the ordinary
    task create/patch endpoints (tasks.py), not here."""
    async with rls(user) as c:
        await _batch_or_404(c, batch_id)
        rows = await c.fetch(
            "SELECT id, title, status, priority, task_type, due_date, completed_date,"
            " attributes->>'phase_gen' AS phase_gen, created_at"
            " FROM tasks WHERE batch_id=$1 AND is_deleted=false ORDER BY created_at DESC",
            batch_id)
    return {"tasks": [{
        "id": str(r["id"]), "title": r["title"], "status": r["status"],
        "priority": r["priority"], "task_type": r["task_type"],
        "due_date": r["due_date"].isoformat() if r["due_date"] else None,
        "completed_date": r["completed_date"].isoformat() if r["completed_date"] else None,
        "phase_gen": r["phase_gen"],
        "created_at": r["created_at"].isoformat(),
    } for r in rows]}
