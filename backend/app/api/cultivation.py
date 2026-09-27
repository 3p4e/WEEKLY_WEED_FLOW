"""Cultivation — cultivar master, coded batches, per-plant identity, phase events.

Phase 1 of the cultivation department (docs/CULTIVATION-DESIGN-2026-07.md), the
functional layer over migration 0045. It extends the facility board's occupancy
model into the identity the owner confirmed for the incoming genetics:

  - a `cultivars` master retiring free-text strains;
  - `plant_batches.code` (e.g. GP072501) and `cultivar_id` — one batch is one
    cultivar in one flowering room;
  - individual `plants` with an id `<clone-date>_<batch code>_<seq>` when no
    mother is known, or the owner's clone id `<mother>-<cutting>.<clone>`;
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

THE BATCH NUMBER. GP072501 = <cultivar code><MMYY><nn>: the owner's "strain
name abbreviation, mmyy, the nth cloning batch of that strain in that month"
(2026-09-05). GET /batch-code suggests the next one — MMYY is the CLONING
month, nn is one past the highest sequence already on file for that head and
month (max, not count: a gap in the numbers is not a free number), and 99 is
the last. The head is enforced on save: a batch code must start with its
cultivar's code, because the strain of a tested lot is later read off exactly
that head (the CoQ tracker keys BG1024 to Blue Gelato that way).

THE PHASE PATH, AND WHO MAY LEAVE IT. The production path is clone -> nursery
-> veg -> flower -> drying -> harvested, walked one stop at a time; nursery
and drying are optional stops, `destroyed` is reachable from anywhere, and
mother stock is not on the path at all. A move to the SAME phase is a room
change and keeps the phase clock — moving a flowering batch F1 -> F2 on day 30
does not restart its harvest window. A move BACKWARDS is a correction: only
QA authority (QA_MGR, the executives, ADMIN) may record one, with a reason,
because it rewrites what the record says happened. Flowering happens "in one
of the 6 available flowering rooms" (owner), so a move into `flower` refuses a
room whose kind is not `flower`. Every move takes a row lock on the batch,
so two moves recorded at once serialise rather than one landing on a batch
the other already closed.

DATES ARE BOUNDED BY THE FACILITY CLOCK. A move dated after the facility's
today, or before the batch's latest phase event, is refused: the PHI gate in
harvest.py resolves the batch's room on the application date from these
events, and a backdated room move used to lift a room-scoped spray block
(review CS-01). Phase events are therefore monotonic by construction.

THE AUDIT-LOCK RULE, enforced here rather than in the schema. app.fn_audit_row()
holds one global advisory lock per audited write until commit. A ~2000-plant
room therefore must never be created, moved, or closed as 2000 audited row
writes in one transaction — it would freeze every other audited write in the
database for the duration. So:
  - phase moves are ONE plant_batches update + ONE phase event (never per plant);
  - generating the individual plant rows is a SEPARATE, CHUNKED, RESUMABLE
    endpoint (POST /batches/{id}/plants) that commits ~_PLANT_CHUNK at a time,
    so other writers interleave between chunks and an interrupted fill resumes
    from the last seq rather than restarting;
  - closing a batch settles its plants in ONE or TWO bulk updates: the plants
    a waste manifest declared destroyed become `destroyed`, the rest of the
    still-active ones `harvested` (or all of them `destroyed`), never a row
    per plant.
"""
import json
import re
from datetime import date, timedelta

from asyncpg.exceptions import UniqueViolationError

from app.worktime import SITE_TODAY_SQL, facility_today

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.plantids import MAX_BATCH_SEQ, MAX_CLONE_NO, clone_code, legacy_plant_code
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
# The production path in order (see the module header). Forward moves go to
# the next stop, or past an optional one; `destroyed` is reachable from any
# phase; `mother` is off the path (mother stock is kept, not grown out).
_PATH = ("clone", "nursery", "veg", "flower", "drying", "harvested")
_OPTIONAL_STOPS = ("nursery", "drying")
# Who may move a batch BACKWARDS along the path (a correction of the record):
# QA authority, the same set that releases a PHI block in harvest.py.
_CORRECTORS = (ADMIN, *EXECUTIVE_ROLES, "QA_MGR")
# The room kinds a phase is tied to. Only flowering is tied — the owner said
# it happens "in one of the 6 available flowering rooms"; the other phases
# were given no such rule, so none is invented for them.
_PHASE_ROOM_KINDS = {"flower": ("flower",)}

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
    # to_phase == the batch's current phase is a ROOM CHANGE (to_room_id
    # required, phase clock kept); anything else is a phase transition.
    to_phase: str
    to_room_id: str | None = None
    occurred_on: date | None = None
    # min_length so `reason: ""` cannot pass as a stated reason where one is
    # required (a terminal or a backward move) — same rule as the PHI override.
    reason: str | None = Field(default=None, min_length=1, max_length=500)


def _check_phase(phase: str | None) -> None:
    if phase is not None and phase not in _PHASES:
        raise HTTPException(422, f"phase must be one of: {', '.join(_PHASES)}")


def _transition(from_phase: str, to_phase: str) -> str:
    """Classify a move: 'room' (same phase), 'forward', 'backward' or
    'terminal' — or refuse it with a 422 that names the path."""
    if to_phase == from_phase:
        return "room"
    if to_phase == "destroyed":
        return "terminal"
    if from_phase == "mother" or to_phase == "mother":
        raise HTTPException(
            422, "mother stock is not on the production path — it is kept in the mother"
                 " bank, not moved through phases; a batch grown out of it is registered"
                 " as its own batch")
    fi, ti = _PATH.index(from_phase), _PATH.index(to_phase)
    if ti < fi:
        return "backward"
    # The next stop, plus whatever lies past an optional stop that is skipped.
    allowed, i = [], fi + 1
    while i < len(_PATH):
        allowed.append(_PATH[i])
        if _PATH[i] not in _OPTIONAL_STOPS:
            break
        i += 1
    if to_phase not in allowed:
        raise HTTPException(
            422, f"{from_phase} -> {to_phase} skips a stop; the plan goes"
                 f" {' -> '.join(_PATH)} one stop at a time (nursery and drying may be"
                 " skipped), and destroyed is reachable from anywhere")
    return "terminal" if to_phase in _TERMINAL else "forward"


def _check_room_for_phase(room, phase: str) -> None:
    """Flowering is tied to the flowering rooms (owner, 2026-09-05)."""
    kinds = _PHASE_ROOM_KINDS.get(phase)
    if kinds and room["kind"] not in kinds:
        raise HTTPException(
            422, f"{room['name']} is a {room['kind']} room — a batch in {phase} belongs in a"
                 f" {' / '.join(kinds)} room")


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


async def _batch_or_404(c, batch_id: str, lock: bool = False):
    """The batch with its cultivar code and room. `lock=True` takes the row
    lock a move needs (FOR UPDATE OF b — the joins are outer, and a bare FOR
    UPDATE cannot lock the nullable side of one)."""
    uuid_or_404(batch_id, "Batch not found")
    row = await c.fetchrow(
        "SELECT b.*, cv.code AS cultivar_code, cv.name AS cultivar_name,"
        " r.name AS room_name, r.kind AS room_kind"
        " FROM plant_batches b"
        " LEFT JOIN cultivars cv ON cv.id = b.cultivar_id"
        " LEFT JOIN rooms r ON r.id = b.room_id"
        " WHERE b.id=$1" + (" FOR UPDATE OF b" if lock else ""), batch_id)
    if row is None:
        raise HTTPException(404, "Batch not found")
    return row


async def _room_or_422(c, room_id: str):
    uuid_or_422(room_id, "Unknown or inactive room")
    room = await c.fetchrow("SELECT id, name, kind FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


def _not_after_today(value, today, what: str) -> None:
    """A recorder-supplied date may not lie in the future: every gate that
    reads one (the PHI clearance, the phase clock) is bounded by the facility's
    own today, or the recorder could date their way past it."""
    if value is not None and value > today:
        raise HTTPException(422, f"{what} {value.isoformat()} is after today"
                                 f" ({today.isoformat()}) — a record cannot be dated in the future")


async def _cultivar_or_422(c, cultivar_id: str):
    uuid_or_422(cultivar_id, "Unknown or inactive cultivar")
    cv = await c.fetchrow(
        "SELECT id, code, name FROM cultivars WHERE id=$1 AND is_active", cultivar_id)
    if cv is None:
        raise HTTPException(422, "Unknown or inactive cultivar")
    return cv


# ── cultivars ────────────────────────────────────────────────────────────────

@router.get("/cultivars")
async def list_cultivars(user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Every cultivar WITH the official products it is grown to (qc_products,
    approved first, drafts flagged) — the ImB pages the batch form registers
    against. One query: the sub-select folds the products, so the form shows
    strain + grades without a round trip per cultivar. The legacy potency
    ladder used to ride along as `spec`; nothing read it, and the ladders are
    superseded by the catalogue, so it is gone (review CS-18)."""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT cv.id, cv.code, cv.name, cv.name_mk, cv.note, cv.is_active,"
            " (SELECT json_agg(json_build_object('id', p.id, 'product_code', p.product_code,"
            "     'grade', p.grade, 'nominal_pct', p.nominal_pct, 'window_min', p.window_min,"
            "     'window_max', p.window_max, 'status', p.status)"
            "     ORDER BY (p.status='APPROVED') DESC, p.grade DESC)"
            "   FROM qc_products p WHERE p.cultivar_id = cv.id"
            "   AND p.status IN ('APPROVED','DRAFT')) AS products"
            " FROM cultivars cv"
            " ORDER BY cv.is_active DESC, cv.code")
    return {"cultivars": [
        {"id": str(r["id"]), "code": r["code"], "name": r["name"],
         "name_mk": r["name_mk"], "note": r["note"], "is_active": r["is_active"],
         "products": [{"id": str(x["id"]), "product_code": x["product_code"],
                       "grade": float(x["grade"]), "nominal_pct": float(x["nominal_pct"]),
                       "window_min": float(x["window_min"]), "window_max": float(x["window_max"]),
                       "status": x["status"]}
                      for x in (json.loads(r["products"]) if isinstance(r["products"], str)
                                else (r["products"] or []))]}
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
                          clone_date: date | None = Query(None),
                          user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Suggest the next batch number for a cultivar: <cultivar code><MMYY><nn>.

    MMYY is the month of the CLONING date when the form has one (the owner
    defines nn as "the nth cloning batch of that strain in that month"), else
    the facility's today. nn is one past the HIGHEST sequence already on file
    for that head and month — max, not count, because GP092601 and GP092603
    on file must suggest 04, not the 03 that already exists. Codes that do not
    fit the <head><MMYY><nn> shape are ignored rather than counted. Past 99
    there is no next number, and the response says so (422)."""
    async with rls(user) as c:
        cv = await _cultivar_or_422(c, cultivar_id)
        period = (clone_date or facility_today()).strftime("%m%y")
        head = f"{cv['code']}{period}"
        codes = await c.fetch(
            "SELECT code FROM plant_batches WHERE org_id=$1 AND left(code, $2) = $3",
            user["org_id"], len(head), head)
    shape = re.compile(r"^" + re.escape(head) + r"(\d{2})$")
    used = [int(m.group(1)) for m in (shape.match(r["code"] or "") for r in codes) if m]
    seq = max(used, default=0) + 1
    if seq > MAX_BATCH_SEQ:
        raise HTTPException(
            422, f"{cv['code']} already has batch {MAX_BATCH_SEQ:02d} for {period} — the batch"
                 " number has no room for another cloning batch of this strain this month")
    return {"prefix": cv["code"], "period": period, "seq": seq,
            "suggested": f"{head}{seq:02d}"}


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
            " tc.id AS tc_id, tc.checked_on AS tc_on, tc.verdict AS tc_verdict,"
            " tc.pct_amber AS tc_amber, tc.instrument AS tc_instrument"
            " FROM plant_batches b"
            " LEFT JOIN cultivars cv ON cv.id=b.cultivar_id"
            " LEFT JOIN rooms r ON r.id=b.room_id"
            " LEFT JOIN qc_products pr ON pr.id=b.product_id"
            # The latest check AS OF TODAY: a row dated ahead (from before
            # trichome.py bounded the date) must not stay "latest" for a year.
            " LEFT JOIN LATERAL (SELECT id, checked_on, verdict, pct_amber, instrument"
            "   FROM trichome_checks t WHERE t.batch_id=b.id AND t.checked_on <= $3::date"
            "   ORDER BY t.checked_on DESC, t.created_at DESC LIMIT 1) tc ON true"
            " WHERE ($1::bool IS FALSE OR b.is_active)"
            " ORDER BY b.phase_since DESC, b.code",
            active, list(_CLONE_LEG), today)
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
         # `id` is what the board's "Correct" action patches (trichome.py).
         "latest_trichome": ({"id": str(r["tc_id"]),
                              "checked_on": r["tc_on"].isoformat(), "verdict": r["tc_verdict"],
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
        today = await _site_today(c)
        _not_after_today(body.clone_date, today, "clone date")
        _not_after_today(body.phase_since, today, "phase start")
        room = await _room_or_422(c, body.room_id)
        _check_room_for_phase(room, body.phase)
        cv = await _cultivar_or_422(c, body.cultivar_id)
        # The head of the batch number is the cultivar code, and the strain of
        # a lot is later read off that head — so a code with another head is
        # not this cultivar's batch number.
        if not body.code.startswith(cv["code"]):
            raise HTTPException(
                422, f"batch code {body.code} does not start with the cultivar code"
                     f" {cv['code']} — the owner's batch number is <cultivar><MMYY><nn>")
        product = None
        if body.product_id:
            product = await _product_or_422(c, body.product_id, cv["id"])
        dup = await c.fetchrow(
            "SELECT id FROM plant_batches WHERE org_id=$1 AND code=$2",
            user["org_id"], body.code)
        if dup is not None:
            raise HTTPException(409, f"batch code {body.code} already exists")
        try:
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
        except UniqueViolationError:
            # Two saves of one suggestion at the same moment: the pre-check above
            # read "free" for both, and the partial unique index decided. The
            # loser deserves the same answer as a caller who was merely second.
            raise HTTPException(409, f"batch code {body.code} already exists")
        await c.execute(
            # The only interpolation is SITE_TODAY_SQL — a module constant
            # rendered from settings.snapshot_tz at import, quote-doubled;
            # user data travels exclusively in the bound parameters.
            "INSERT INTO plant_phase_events(org_id, batch_id, event, to_phase, qty,"  # nosec B608
            " to_room_id, occurred_on, created_by)"
            f" VALUES ($1,$2,'create',$3,$4,$5,COALESCE($6::date,{SITE_TODAY_SQL}),$7)",
            user["org_id"], row["id"], body.phase, body.plant_count, body.room_id,
            body.clone_date or body.phase_since, user["id"])
        # The params are the CONTRACT with the activity sentences
        # (notifications-view.js, views.js): `strain` is the cultivar's NAME
        # and `room` the room's NAME, because that is what the sentence
        # prints — "added 96 × Grape Pie to Flowering 1.1 (flower)". The
        # older keys stay for anything that read them (review CS2-02).
        await safe_emit(c, user, verb="batch_added", object_type="plant_batch",
                        object_id=row["id"], recipients=[],
                        params={"code": row["code"], "cultivar": cv["code"],
                                "strain": cv["name"], "room": room["name"],
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

    CHUNKED and RESUMABLE: it starts from the highest existing seq and inserts
    in _PLANT_CHUNK-sized transactions, so an interrupted fill is completed by
    calling again, and each chunk releases the audit chain lock.

    THE ID A PLANT GETS DEPENDS ON WHETHER ITS MOTHER IS KNOWN. When the batch
    was fed by clone runs that named their mothers, each plant carries the
    owner's clone id — `<mother>-<cutting>.<clone>`, e.g.
    GP26_S1M03-2_020-03.147 — and points at the mother it was cut from. A plant
    with no known mother (imported clones, seed, or the remainder when the runs
    account for fewer cuttings than the batch plans) keeps the legacy
    `<clone-date>_<batch code>_<seq>` — the BATCH code, so two batches of one
    cultivar cloned the same day cannot compute the same id (review CS-02).

    THE ALLOCATION IS A PURE FUNCTION OF seq. Segments are laid end to end in a
    fixed order (run, then mother code), so plant number 61 belongs to the same
    mother and carries the same id whether it is written in the first call or a
    resumed one. That is what makes an interrupted fill safe to finish — and it
    is why the batch's run membership is FROZEN once any plant exists
    (propagation.py refuses to link or relink a run, 409): a run added later
    would shift every segment after it and rename plants already printed. A
    run that FAILED (its cuttings did not root) contributes no plants, unless
    plants already carry its lineage from a fill that ran before it failed —
    those ids stand, because a plant that exists keeps its name.

    A mother whose cuttings were not counted contributes no ids: numbering
    clones 1..n needs an n, and inventing one would name plants that may not
    exist. A closed batch gets no new plants at all (409).

    THE PLAN READ AND THE FIRST CHUNK SHARE ONE LOCKED TRANSACTION. The
    freeze above is a count of plants; between reading the plan and writing
    the first row that count is still zero, and a run committing in that
    window would pass the freeze and change the plan the ids were numbered
    from. So the plan is read under `pg_advisory_xact_lock('fill:<batch>')`
    — the key propagation.py takes before it counts — and chunk 1 is written
    before the lock is released, so the count is non-zero for the next
    reader (review CS2-04). Later chunks keep their own transactions."""
    async with rls(user) as c:
        b = await _batch_or_404(c, batch_id)
        if b["cultivar_id"] is None:
            raise HTTPException(422, "batch has no cultivar; cannot form plant ids")
        if not b["code"]:
            raise HTTPException(422, "batch has no code; a plant id is built from it")
        if b["phase"] in _TERMINAL or not b["is_active"]:
            raise HTTPException(
                409, f"batch {b['code']} is {b['phase']} — a closed batch has no plants to number")
        # THE FILL LOCK. The plan is read and the FIRST chunk is written under
        # one advisory lock per batch — the same key propagation.py takes
        # before it counts plants to decide whether a run may still join,
        # move or leave the batch. Without it a run could commit between this
        # read and the first insert (the count was still 0, so the freeze
        # check let it through), and the plan on file would no longer be the
        # plan the ids were numbered from (review CS2-04). Writing chunk 1
        # here is what makes the freeze real the moment the lock is released:
        # the batch then has plants, and the count says so to everyone.
        await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"fill:{batch_id}")
        target = b["plant_count"]
        have = await c.fetchval(
            "SELECT COALESCE(max(seq), 0) FROM plants WHERE batch_id=$1", batch_id)
        clone_ev = await c.fetchval(
            "SELECT occurred_on FROM plant_phase_events WHERE batch_id=$1 AND event='create'"
            " ORDER BY created_at LIMIT 1", batch_id)
        day = clone_ev or b["phase_since"] or facility_today()
        # The mothers this batch was cut from, in a stable order. A failed run
        # is left out — unless plants already carry its lineage, in which case
        # its segment must stay where it was.
        segs = await c.fetch(
            "SELECT cm.mother_plant_id, cm.cutting_no, cm.cuttings, mp.code"
            " FROM clone_run_mothers cm"
            " JOIN clone_runs cr ON cr.id = cm.run_id"
            " JOIN mother_plants mp ON mp.id = cm.mother_plant_id"
            " WHERE cr.batch_id = $1"
            "   AND (cr.status <> 'failed' OR EXISTS ("
            "        SELECT 1 FROM plants p WHERE p.batch_id = $1"
            "          AND p.mother_plant_id = cm.mother_plant_id AND p.cutting_no = cm.cutting_no))"
            " ORDER BY cr.started_on, cr.created_at, mp.code", batch_id)

        # Lay the segments end to end: [(first_seq, last_seq, mother_id, code, cutting_no)].
        plan, at = [], 1
        for sg in segs:
            n = sg["cuttings"]
            if not n:
                continue
            if n > MAX_CLONE_NO:
                raise HTTPException(
                    422, f"mother {sg['code']} cutting {sg['cutting_no']:02d}: {n} clones exceeds"
                         f" the {MAX_CLONE_NO} a clone id can number — split the cutting")
            if at > target:
                break
            take = min(int(n), target - at + 1)
            plan.append((at, at + take - 1, sg["mother_plant_id"], sg["code"], sg["cutting_no"]))
            at += take
        capped = at <= sum(int(sg["cuttings"] or 0) for sg in segs)

        def _row(n: int):
            """The id and lineage of plant number n — the same answer every call."""
            for first, last, mid, code, cutting in plan:
                if first <= n <= last:
                    return (clone_code(code, cutting, n - first + 1), mid, cutting, n - first + 1)
            return (legacy_plant_code(day, b["code"], n), None, None, None)

        def _report(created, materialised):
            return {"batch_id": batch_id, "target": target, "created": created,
                    "materialised": materialised, "complete": materialised >= target,
                    "per_mother": [{"mother_code": c_, "cutting_no": cn, "count": last - first + 1}
                                   for first, last, _m, c_, cn in plan],
                    "legacy": max(0, target - (at - 1)), "capped": capped}

        _INSERT = (
            # SITE_TODAY_SQL only; every value travels in the parameters.
            "INSERT INTO plants(org_id, batch_id, room_id, cultivar_id, plant_code,"  # nosec B608
            " clone_date, seq, mother_plant_id, cutting_no, clone_no, status_since,"
            " created_by, updated_by)"
            f" VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,{SITE_TODAY_SQL},$11,$11)"
            " ON CONFLICT (batch_id, seq) DO NOTHING")

        def _chunk(seq: int, top: int):
            rows = []
            for n in range(seq, top + 1):
                code, mid, cutting, clone_no = _row(n)
                rows.append((user["org_id"], batch_id, b["room_id"], b["cultivar_id"],
                             code, clone_ev, n, mid, cutting, clone_no, user["id"]))
            return rows

        def _conflict(e, created):
            # (org, plant_code) is taken by a plant of ANOTHER batch. The ids
            # above are unique by construction, so this means a mother's run
            # was relinked or a batch code reused; say which id, and stop —
            # the fill is still resumable once the record is put right.
            return HTTPException(
                409, "a plant id in this chunk already names a plant of another batch"
                     f" ({getattr(e, 'detail', None) or e}); {created} plant(s) of this call"
                     " were written and the fill resumes from there once the conflict is resolved")

        if have >= target:
            return _report(0, have)

        # Chunk 1, under the lock, in the plan's own transaction.
        created = 0
        seq = have + 1
        top = min(seq + _PLANT_CHUNK - 1, target)
        rows = _chunk(seq, top)
        try:
            await c.executemany(_INSERT, rows)
        except UniqueViolationError as e:
            raise _conflict(e, created)
        created += len(rows)
        seq = top + 1

    while seq <= target:
        top = min(seq + _PLANT_CHUNK - 1, target)
        rows = _chunk(seq, top)
        # Fresh rls() per chunk = fresh transaction = the audit lock is taken and
        # released per chunk, not held across the whole fill.
        try:
            async with rls(user) as c:
                await c.executemany(_INSERT, rows)
        except UniqueViolationError as e:
            raise _conflict(e, created)
        created += len(rows)
        seq = top + 1

    async with rls(user) as c:
        materialised = await c.fetchval(
            "SELECT count(*) FROM plants WHERE batch_id=$1", batch_id)
    return _report(created, materialised)


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
            "SELECT p.id, p.plant_code, p.seq, p.status, p.status_since, p.clone_date,"
            " p.reason, p.mother_plant_id, p.cutting_no, p.clone_no, mp.code AS mother_code"
            " FROM plants p LEFT JOIN mother_plants mp ON mp.id = p.mother_plant_id"
            " WHERE p.batch_id=$1 AND ($2::text IS NULL OR p.status=$2)"
            " ORDER BY p.seq LIMIT $3 OFFSET $4", batch_id, status, limit, offset)
    return {"batch_id": batch_id, "total": total, "limit": limit, "offset": offset,
            "plants": [
                {"id": str(r["id"]), "plant_code": r["plant_code"], "seq": r["seq"],
                 "status": r["status"],
                 "status_since": r["status_since"].isoformat() if r["status_since"] else None,
                 "clone_date": r["clone_date"].isoformat() if r["clone_date"] else None,
                 "reason": r["reason"],
                 "mother_plant_id": str(r["mother_plant_id"]) if r["mother_plant_id"] else None,
                 "mother_code": r["mother_code"], "cutting_no": r["cutting_no"],
                 "clone_no": r["clone_no"]}
                for r in rows]}


@router.post("/batches/{batch_id}/move")
async def move_batch(batch_id: str, body: MoveIn,
                     user: dict = Depends(require_role(*_WRITERS))):
    """Record a whole-batch phase transition or room change: ONE plant_batches
    update + ONE phase event. Never touches individual plant rows, except the
    bulk settle at end of life (see module header).

    The rules, in the order they are checked: the batch is open; the date is
    not in the future and not before the batch's latest event; the move is
    one the path allows (or a QA correction with a reason); a terminal move
    states its reason; the room fits the phase. All under a row lock, so a
    move that lands after a concurrent terminal move sees the closed batch and
    is refused, rather than reopening it."""
    _check_phase(body.to_phase)
    async with rls(user) as c:
        b = await _batch_or_404(c, batch_id, lock=True)
        if b["phase"] in _TERMINAL:
            raise HTTPException(409, f"batch is {b['phase']}; it cannot move again")
        today = await _site_today(c)
        occurred = body.occurred_on or today
        _not_after_today(occurred, today, "move date")
        last = await c.fetchval(
            "SELECT max(occurred_on) FROM plant_phase_events WHERE batch_id=$1", batch_id)
        floor = max(d for d in (last, b["phase_since"]) if d is not None)
        if occurred < floor:
            raise HTTPException(
                422, f"move date {occurred.isoformat()} is before the batch's latest phase"
                     f" event ({floor.isoformat()}) — phase events are recorded in order; a"
                     " backdated room move would rewrite where the batch stood on a spray date")
        kind = _transition(b["phase"], body.to_phase)
        if kind == "room":
            if body.to_room_id is None or str(body.to_room_id) == str(b["room_id"]):
                raise HTTPException(
                    422, f"batch is already in {b['phase']}"
                         f"{' in ' + b['room_name'] if b['room_name'] else ''} — a move to the"
                         " same phase is a room change and needs a different room")
        if kind == "backward":
            if user["role"] not in _CORRECTORS:
                raise HTTPException(
                    403, f"{b['phase']} -> {body.to_phase} moves the batch backwards along the"
                         " plan — a correction of the record, which QA authority records with"
                         " a reason")
            if not body.reason:
                raise HTTPException(
                    422, f"{b['phase']} -> {body.to_phase} is a correction — state the reason")
        if kind == "terminal" and not body.reason:
            raise HTTPException(
                422, f"closing a batch as {body.to_phase} needs a stated reason — it settles"
                     " every plant in it and cannot be undone")
        if kind == "terminal" and body.to_phase == "harvested":
            # A DRAFT manifest line is a declaration nobody has sealed: its
            # count may still change or the line be removed, and a plant
            # settled from it would say "destroyed on WM-9" for a manifest
            # that may end up listing none (review CS2-03). Settling only
            # from sealed lines and IGNORING a draft would drift the other
            # way once it is sealed. So the close waits for the record to be
            # settled first: seal the manifest, or take the line off it.
            drafts = await c.fetch(
                "SELECT DISTINCT m.manifest_code FROM waste_manifest_lines l"
                " JOIN waste_manifests m ON m.id = l.manifest_id"
                " WHERE l.batch_id=$1 AND m.status='draft' ORDER BY m.manifest_code", batch_id)
            if drafts:
                codes = ", ".join(r["manifest_code"] for r in drafts)
                raise HTTPException(
                    409, f"waste manifest {codes} still names this batch on a DRAFT line — seal"
                         " the manifest (or remove the line) before closing the batch, so the"
                         " plants it declares destroyed are settled from a fixed declaration")
        to_room, to_room_name = b["room_id"], b["room_name"]
        if body.to_room_id is not None:
            room = await _room_or_422(c, body.to_room_id)
            _check_room_for_phase(room, body.to_phase)
            to_room, to_room_name = room["id"], room["name"]
        elif kind != "room" and b["room_kind"] is not None:
            _check_room_for_phase({"name": b["room_name"], "kind": b["room_kind"]}, body.to_phase)
        row = await c.fetchrow(
            # A room change keeps the phase clock; a phase change restarts it.
            "UPDATE plant_batches SET phase=$1, room_id=$2,"
            " phase_since=CASE WHEN $7::bool THEN phase_since ELSE $3::date END,"
            " updated_by=$4, updated_at=now(),"
            " is_active = CASE WHEN $1 = ANY($5::text[]) THEN false ELSE is_active END"
            " WHERE id=$6 RETURNING *",
            body.to_phase, to_room, occurred, user["id"],
            list(_TERMINAL), batch_id, kind == "room")
        await c.execute(
            "INSERT INTO plant_phase_events(org_id, batch_id, event, from_phase, to_phase,"
            " qty, to_room_id, occurred_on, reason, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
            user["org_id"], batch_id,
            ("harvest" if body.to_phase == "harvested"
             else "destroy" if body.to_phase == "destroyed" else "move"),
            b["phase"], body.to_phase, b["plant_count"], to_room,
            occurred, body.reason, user["id"])
        # A batch reaching a terminal phase settles its still-active plants —
        # bulk UPDATEs bounded by plant count, run once per batch at end of
        # life, never on an ordinary move. The plants a waste manifest declared
        # destroyed are settled as `destroyed`, not `harvested`: the manifest
        # does not name plants, so the count is taken off the top of the seq
        # order and the reason says so, and only the remainder is harvested.
        # Only SEALED declarations count (sealed, witnessed or disposed — the
        # manifest's own ladder in waste.py): a draft's lines can still be
        # changed or removed, and the close above refuses while one exists.
        settled = {"harvested": 0, "destroyed": 0}
        if kind == "terminal":
            destroyed_n = 0
            if body.to_phase == "harvested":
                destroyed_n = int(await c.fetchval(
                    "SELECT COALESCE(sum(l.plant_qty), 0) FROM waste_manifest_lines l"
                    " JOIN waste_manifests m ON m.id = l.manifest_id"
                    " WHERE l.batch_id=$1 AND m.status <> 'draft'", batch_id) or 0)
                if destroyed_n:
                    manifests = await c.fetch(
                        "SELECT DISTINCT m.manifest_code FROM waste_manifest_lines l"
                        " JOIN waste_manifests m ON m.id = l.manifest_id"
                        " WHERE l.batch_id=$1 AND m.status <> 'draft' ORDER BY m.manifest_code",
                        batch_id)
                    codes = ", ".join(r["manifest_code"] for r in manifests)
                    settled["destroyed"] = int((await c.execute(
                        "UPDATE plants SET status='destroyed', status_since=$2, reason=$3,"
                        " updated_by=$4, updated_at=now()"
                        " WHERE id IN (SELECT id FROM plants WHERE batch_id=$1 AND status='active'"
                        "              ORDER BY seq DESC LIMIT $5)",
                        batch_id, occurred,
                        f"declared destroyed on sealed waste manifest {codes}; plants not"
                        " individually identified, counted off the end of the batch",
                        user["id"], destroyed_n)
                    ).split()[-1])
                    await c.execute(
                        "INSERT INTO plant_phase_events(org_id, batch_id, event, from_phase,"
                        " to_phase, qty, to_room_id, occurred_on, reason, created_by)"
                        " VALUES ($1,$2,'destroy',$3,'destroyed',$4,$5,$6,$7,$8)",
                        user["org_id"], batch_id, b["phase"], destroyed_n, to_room, occurred,
                        f"waste manifest {codes}", user["id"])
            final = "harvested" if body.to_phase == "harvested" else "destroyed"
            settled[final] += int((await c.execute(
                "UPDATE plants SET status=$1, status_since=$2, updated_by=$3, updated_at=now()"
                " WHERE batch_id=$4 AND status='active'",
                final, occurred, user["id"], batch_id)).split()[-1])
        # Phase 3: the per-phase task set, generated on the SAME transition
        # that just committed — see _generate_phase_tasks for why it never
        # raises (a template miss / no department / no week is a reason to
        # generate nothing, never a reason to fail the move that already
        # happened above). A room change enters no phase, so it generates nothing.
        generated = []
        if kind != "room":
            generated = await _generate_phase_tasks(
                c, user, {"id": batch_id}, body.to_phase, occurred)
        # Same contract as batch_added: the sentence prints the strain NAME,
        # the plant count and both room NAMES (review CS2-02).
        await safe_emit(c, user, verb="batch_moved", object_type="plant_batch",
                        object_id=batch_id, recipients=[],
                        params={"code": b["code"], "old_phase": b["phase"],
                                "phase": body.to_phase, "room_change": kind == "room",
                                "strain": b["cultivar_name"] or b["strain"],
                                "plant_count": b["plant_count"],
                                "old_room": b["room_name"], "room": to_room_name,
                                "generated_tasks": len(generated)})
    return {"id": batch_id, "code": row["code"], "phase": row["phase"],
            "room_id": str(row["room_id"]) if row["room_id"] else None,
            "phase_since": row["phase_since"].isoformat(), "is_active": row["is_active"],
            "kind": kind, "occurred_on": occurred.isoformat(),
            "plants_settled": settled if kind == "terminal" else None,
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
