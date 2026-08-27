"""HLVd decontamination campaign — per-room signed cycle, bleach log, swab gate.

The record the CEO's eradication plan demands (migration 0046). Distinct from
cultivation (app/api/cultivation.py) — it tracks the room, not the plant, and
precedes the new genetics rather than following them. See
docs/CULTIVATION-DESIGN-2026-07.md §5b.

Access model:
  read      — every role above USER (ELEVATED_ROLES);
  cleaning  — record a step or a bleach-bucket reading: cultivation crew
              (CU_MGR) + executives + ADMIN, the same writers as facility/
              cultivation, since this is who is physically doing the work;
  swabs     — recording a swab and its result is a QA function per the plan
              ("QA ... takes swabs"): QA_MGR + executives + ADMIN;
  release   — "A room is released by the QA Manager, in writing ... Nobody
              else can release a room, and no room is released verbally."
              QA_MGR + executives + ADMIN only, and only against a complete
              record (see release_room below).
  fail      — explicitly failing/abandoning a cycle (e.g. after a positive
              swab) is the mirror-image QA judgement call to release, so it
              is gated the same: QA_MGR + executives + ADMIN only (see
              fail_cycle below).

THE TWO GATES THE PLAN INSISTS ON, ENFORCED HERE, NOT LEFT TO DISCIPLINE:
  1. Steps are IN ORDER, and rinse1_whitecloth must PASS before bleach is
     accepted. "Soiled cloth -> wash again; the bleach does not go on" — a
     failed white-cloth check does not block recording, it reopens
     detergent_wash instead of letting bleach follow a still-dirty surface.
  2. Release requires every step signed AND every swab for the room negative.
     A pending or positive swab blocks it outright — "no room is released on
     a pending result."
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role, uuid_or_404, uuid_or_422
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES, EXECUTIVE_ROLES

router = APIRouter(prefix="/decon", tags=["decon"])

_CLEAN_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR")
_QA_WRITERS = (ADMIN, *EXECUTIVE_ROLES, "QA_MGR")

# Order matters — this list IS the sequence the plan specifies (§12).
_STEPS = ("dry_clean", "detergent_wash", "rinse1_whitecloth", "bleach", "rinse2")
_GATE_STEP = "rinse1_whitecloth"   # must pass before the next step is accepted
_RESULTS = ("pending", "negative", "positive", "inconclusive")
_CONTROL_MATERIALS = ("leaf", "root", "surface_scraping", "other")
# Tools and drains are 10,000 ppm — DOUBLE the 5,000 ppm surface spec.
# Deliberately a separate constant from the bleach log's target: sharing
# one number would silently under-dose the blades, which carry HLVd's
# primary transmission route.
_TOOL_TARGET_PPM = 10000
# The SURFACE specification, half the tool figure. Named rather than left as the
# bare `5000` it used to be inline: 0047's whole point is that surfaces and tools
# are separate targets, and a loose literal is how the two get conflated — the
# failure mode being an under-dosed blade, which carries HLVd's primary route.
_SURFACE_TARGET_PPM = 5000


class CycleIn(BaseModel):
    room_id: str
    campaign: str = Field(max_length=120)
    note: str | None = Field(default=None, max_length=500)


class StepIn(BaseModel):
    step: str
    passed: bool | None = None   # meaningful for rinse1_whitecloth; ignored elsewhere
    note: str | None = Field(default=None, max_length=500)


class BleachIn(BaseModel):
    room_id: str
    cycle_id: str | None = None
    ppm_strip_reading: int = Field(ge=0, le=200000)
    note: str | None = Field(default=None, max_length=500)


class SwabIn(BaseModel):
    room_id: str
    cycle_id: str | None = None
    swab_code: str = Field(max_length=64)
    location_desc: str | None = Field(default=None, max_length=300)
    lab_name: str | None = Field(default=None, max_length=120)


class SwabResultIn(BaseModel):
    result: str
    ct_value: float | None = Field(default=None, ge=0, le=100)
    action_taken: str | None = Field(default=None, max_length=500)


class ReleaseIn(BaseModel):
    release_note: str | None = Field(default=None, max_length=1000)


class CycleFailIn(BaseModel):
    reason: str = Field(max_length=1000)


class PositiveControlIn(BaseModel):
    control_code: str = Field(max_length=64)
    material: str
    room_id: str | None = None
    source_desc: str | None = Field(default=None, max_length=300)
    storage_location: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class ToolLogIn(BaseModel):
    room_id: str
    cycle_id: str | None = None
    tool_set: str = Field(max_length=120)
    ppm_strip_reading: int = Field(ge=0, le=200000)
    soak_minutes: float | None = Field(default=None, ge=0, le=600)
    note: str | None = Field(default=None, max_length=500)


async def _room_or_422(c, room_id: str):
    uuid_or_422(room_id, "Unknown or inactive room")
    room = await c.fetchrow("SELECT id, name FROM rooms WHERE id=$1 AND is_active", room_id)
    if room is None:
        raise HTTPException(422, "Unknown or inactive room")
    return room


async def _cycle_or_404(c, cycle_id: str):
    uuid_or_404(cycle_id, "Cycle not found")
    row = await c.fetchrow(
        "SELECT dc.*, r.name AS room_name FROM decon_room_cycles dc"
        " JOIN rooms r ON r.id = dc.room_id WHERE dc.id=$1", cycle_id)
    if row is None:
        raise HTTPException(404, "Cycle not found")
    return row


def _cycle_out(row, latest_by_step: dict, swab_summary: dict) -> dict:
    return {
        "id": str(row["id"]), "room_id": str(row["room_id"]), "room_name": row["room_name"],
        "campaign": row["campaign"], "status": row["status"],
        "started_on": row["started_on"].isoformat(),
        "sealed_at": row["sealed_at"].isoformat() if row["sealed_at"] else None,
        "released_at": row["released_at"].isoformat() if row["released_at"] else None,
        "release_note": row["release_note"], "note": row["note"],
        "steps": latest_by_step, "swabs": swab_summary,
    }


async def _latest_steps(c, cycle_id: str) -> dict:
    """The current state of each of the 5 steps = its most recent signoff. An
    earlier failed rinse1_whitecloth attempt is superseded by a later pass,
    which is exactly the "wash again" loop the plan describes."""
    rows = await c.fetch(
        "SELECT DISTINCT ON (step) step, passed, signed_by, signed_at, note"
        " FROM decon_step_signoffs WHERE cycle_id=$1 ORDER BY step, signed_at DESC",
        cycle_id)
    by_step = {r["step"]: {"passed": r["passed"],
                          "signed_at": r["signed_at"].isoformat(), "note": r["note"]}
              for r in rows}
    return {s: by_step.get(s) for s in _STEPS}


async def _swab_summary(c, room_id: str, cycle_id: str | None) -> dict:
    rows = await c.fetch(
        "SELECT result, count(*) AS n FROM decon_swabs"
        " WHERE room_id=$1 AND ($2::uuid IS NULL OR cycle_id=$2) GROUP BY result",
        room_id, cycle_id)
    counts = {r["result"]: r["n"] for r in rows}
    return {r: counts.get(r, 0) for r in _RESULTS}


# ── cycles ───────────────────────────────────────────────────────────────────

@router.get("/cycles")
async def list_cycles(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                      campaign: str | None = Query(None)):
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT dc.*, r.name AS room_name FROM decon_room_cycles dc"
            " JOIN rooms r ON r.id = dc.room_id"
            " WHERE ($1::text IS NULL OR dc.campaign=$1)"
            " ORDER BY dc.started_on DESC, r.name", campaign)
        out = []
        for row in rows:
            steps = await _latest_steps(c, row["id"])
            swabs = await _swab_summary(c, row["room_id"], row["id"])
            out.append(_cycle_out(row, steps, swabs))
    return {"cycles": out}


@router.post("/cycles", status_code=201)
async def create_cycle(body: CycleIn, user: dict = Depends(require_role(*_CLEAN_WRITERS))):
    async with rls(user) as c:
        room = await _room_or_422(c, body.room_id)
        # Pre-check rather than relying on the unique index's error: an
        # asyncpg UniqueViolationError would surface as a raw 500, not a clean
        # 409, and this race window (create/create) is not one real crews hit
        # concurrently for the SAME room.
        open_cyc = await c.fetchrow(
            "SELECT id FROM decon_room_cycles WHERE org_id=$1 AND room_id=$2"
            " AND campaign=$3 AND status IN ('in_progress','awaiting_verification')",
            user["org_id"], body.room_id, body.campaign)
        if open_cyc is not None:
            raise HTTPException(
                409, f"an open cycle already exists for this room in campaign {body.campaign!r}")
        row = await c.fetchrow(
            "INSERT INTO decon_room_cycles(org_id, room_id, campaign, note,"
            " created_by, updated_by) VALUES ($1,$2,$3,$4,$5,$5) RETURNING *",
            user["org_id"], body.room_id, body.campaign, body.note, user["id"])
        await safe_emit(c, user, verb="decon_cycle_started", object_type="decon_room_cycle",
                        object_id=row["id"], recipients=[],
                        params={"room": room["name"], "campaign": body.campaign})
    return {"id": str(row["id"]), "room_id": body.room_id, "campaign": row["campaign"],
            "status": row["status"], "started_on": row["started_on"].isoformat()}


@router.get("/cycles/{cycle_id}")
async def get_cycle(cycle_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        row = await _cycle_or_404(c, cycle_id)
        steps = await _latest_steps(c, cycle_id)
        swabs = await _swab_summary(c, row["room_id"], cycle_id)
    return _cycle_out(row, steps, swabs)


@router.post("/cycles/{cycle_id}/steps", status_code=201)
async def record_step(cycle_id: str, body: StepIn,
                      user: dict = Depends(require_role(*_CLEAN_WRITERS))):
    """Record one step attempt. Enforces order and the white-cloth gate:
    - a step may be (re)recorded only if every step BEFORE it in _STEPS has a
      PASSING latest signoff (non-gate steps have passed=NULL, treated as pass);
    - specifically, `bleach` requires the latest `rinse1_whitecloth` to have
      passed=true — a soiled cloth reopens detergent_wash/rinse1, it does not
      let bleach through."""
    if body.step not in _STEPS:
        raise HTTPException(422, f"step must be one of: {', '.join(_STEPS)}")
    async with rls(user) as c:
        cyc = await _cycle_or_404(c, cycle_id)
        if cyc["status"] not in ("in_progress",):
            raise HTTPException(409, f"cycle is {cyc['status']}; no further steps accepted")
        latest = await _latest_steps(c, cycle_id)
        idx = _STEPS.index(body.step)
        for prior in _STEPS[:idx]:
            entry = latest.get(prior)
            if entry is None:
                raise HTTPException(409, f"{prior} must be recorded before {body.step}")
            if prior == _GATE_STEP and entry["passed"] is not True:
                raise HTTPException(
                    409, "rinse1_whitecloth has not passed — wash again; bleach does not go on")
        passed = body.passed if body.step == _GATE_STEP else None
        row = await c.fetchrow(
            "INSERT INTO decon_step_signoffs(org_id, cycle_id, step, passed, signed_by, note)"
            " VALUES ($1,$2,$3,$4,$5,$6) RETURNING *",
            user["org_id"], cycle_id, body.step, passed, user["id"], body.note)
        # All 5 steps recorded, with the gate passing -> awaiting verification.
        latest_after = await _latest_steps(c, cycle_id)
        latest_after[body.step] = {"passed": passed, "signed_at": row["signed_at"].isoformat(),
                                   "note": body.note}
        complete = all(latest_after.get(s) is not None for s in _STEPS) and \
                  latest_after[_GATE_STEP]["passed"] is True
        if complete:
            await c.execute(
                "UPDATE decon_room_cycles SET status='awaiting_verification',"
                " sealed_at=now(), updated_by=$1, updated_at=now() WHERE id=$2",
                user["id"], cycle_id)
        elif body.step == _GATE_STEP and passed is False:
            await c.execute(
                "UPDATE decon_room_cycles SET updated_by=$1, updated_at=now() WHERE id=$2",
                user["id"], cycle_id)
    return {"id": str(row["id"]), "cycle_id": cycle_id, "step": row["step"],
            "passed": row["passed"], "signed_at": row["signed_at"].isoformat(),
            "cycle_complete": complete}


# ── bleach log ───────────────────────────────────────────────────────────────

@router.get("/bleach-log")
async def list_bleach_log(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                          room_id: str | None = Query(None),
                          limit: int = Query(200, ge=1, le=2000)):
    if room_id is not None:
        uuid_or_422(room_id, "room_id must be a uuid")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT id, room_id, cycle_id, mixed_at, ppm_strip_reading, mixed_by, note"
            " FROM decon_bleach_log WHERE ($1::uuid IS NULL OR room_id=$1)"
            " ORDER BY mixed_at DESC LIMIT $2", room_id, limit)
    return {"entries": [
        {"id": str(r["id"]), "room_id": str(r["room_id"]),
         "cycle_id": str(r["cycle_id"]) if r["cycle_id"] else None,
         "mixed_at": r["mixed_at"].isoformat(), "ppm_strip_reading": r["ppm_strip_reading"],
         "note": r["note"]}
        for r in rows]}


@router.post("/bleach-log", status_code=201)
async def record_bleach(body: BleachIn, user: dict = Depends(require_role(*_CLEAN_WRITERS))):
    async with rls(user) as c:
        room = await _room_or_422(c, body.room_id)
        if body.cycle_id is not None:
            await _cycle_or_404(c, body.cycle_id)
        row = await c.fetchrow(
            "INSERT INTO decon_bleach_log(org_id, room_id, cycle_id, ppm_strip_reading,"
            " mixed_by, note) VALUES ($1,$2,$3,$4,$5,$6) RETURNING *",
            user["org_id"], body.room_id, body.cycle_id, body.ppm_strip_reading,
            user["id"], body.note)
        # Below-spec is not an error (below-target buckets are the #1 risk the
        # plan calls out) — it is logged and surfaced via the feed, not blocked.
        if body.ppm_strip_reading < _SURFACE_TARGET_PPM:
            await safe_emit(c, user, verb="decon_bleach_below_spec", object_type="room",
                            object_id=body.room_id, recipients=[],
                            params={"room": room["name"], "ppm": body.ppm_strip_reading})
    return {"id": str(row["id"]), "room_id": body.room_id,
            "ppm_strip_reading": row["ppm_strip_reading"], "mixed_at": row["mixed_at"].isoformat()}


# ── swabs ────────────────────────────────────────────────────────────────────

@router.get("/swabs")
async def list_swabs(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                     room_id: str | None = Query(None),
                     result: str | None = Query(None)):
    if room_id is not None:
        uuid_or_422(room_id, "room_id must be a uuid")
    if result is not None and result not in _RESULTS:
        raise HTTPException(422, f"result must be one of: {', '.join(_RESULTS)}")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT id, room_id, cycle_id, swab_code, location_desc, taken_at, lab_name,"
            " sent_at, result, ct_value, result_at, action_taken FROM decon_swabs"
            " WHERE ($1::uuid IS NULL OR room_id=$1) AND ($2::text IS NULL OR result=$2)"
            " ORDER BY taken_at DESC", room_id, result)
    return {"swabs": [
        {"id": str(r["id"]), "room_id": str(r["room_id"]),
         "cycle_id": str(r["cycle_id"]) if r["cycle_id"] else None,
         "swab_code": r["swab_code"], "location_desc": r["location_desc"],
         "taken_at": r["taken_at"].isoformat(), "lab_name": r["lab_name"],
         "sent_at": r["sent_at"].isoformat() if r["sent_at"] else None,
         "result": r["result"], "ct_value": float(r["ct_value"]) if r["ct_value"] is not None else None,
         "result_at": r["result_at"].isoformat() if r["result_at"] else None,
         "action_taken": r["action_taken"]}
        for r in rows]}


@router.post("/swabs", status_code=201)
async def record_swab(body: SwabIn, user: dict = Depends(require_role(*_QA_WRITERS))):
    async with rls(user) as c:
        await _room_or_422(c, body.room_id)
        if body.cycle_id is not None:
            await _cycle_or_404(c, body.cycle_id)
        dup = await c.fetchrow(
            "SELECT id FROM decon_swabs WHERE org_id=$1 AND swab_code=$2",
            user["org_id"], body.swab_code)
        if dup is not None:
            raise HTTPException(409, f"swab code {body.swab_code} already exists")
        row = await c.fetchrow(
            "INSERT INTO decon_swabs(org_id, room_id, cycle_id, swab_code, location_desc,"
            " taken_by, lab_name) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *",
            user["org_id"], body.room_id, body.cycle_id, body.swab_code,
            body.location_desc, user["id"], body.lab_name)
    return {"id": str(row["id"]), "swab_code": row["swab_code"], "result": row["result"],
            "taken_at": row["taken_at"].isoformat()}


@router.patch("/swabs/{swab_id}/result")
async def record_swab_result(swab_id: str, body: SwabResultIn,
                             user: dict = Depends(require_role(*_QA_WRITERS))):
    uuid_or_404(swab_id, "Swab not found")
    if body.result not in _RESULTS or body.result == "pending":
        raise HTTPException(422, "result must be one of: negative, positive, inconclusive")
    async with rls(user) as c:
        # Wave 3 audit (Low): once a swab's associated cycle has been RELEASED
        # — "no room is released on a pending result", release_room already
        # requires every swab negative at that moment — the room batch record
        # is the QA Manager's terminal, in-writing sign-off (see the module
        # docstring). Nothing domain-level stopped a swab result from being
        # edited after that; only the DB audit trigger caught the change,
        # after the fact. Same terminal-state-freeze shape as record_step's
        # and fail_cycle's own cycle-status checks above, and as samples.py's
        # post-RELEASED field freeze (_assert_leaf_open). A swab with no
        # cycle_id (never tied to a specific cycle) has nothing to freeze
        # against and is unaffected.
        cur = await c.fetchrow("SELECT cycle_id FROM decon_swabs WHERE id=$1", swab_id)
        if cur is None:
            raise HTTPException(404, "Swab not found")
        if cur["cycle_id"] is not None:
            cyc_status = await c.fetchval(
                "SELECT status FROM decon_room_cycles WHERE id=$1", cur["cycle_id"])
            if cyc_status == "released":
                raise HTTPException(
                    409, "cycle is released — the room batch record is frozen;"
                    " its swab results may no longer be edited")
        row = await c.fetchrow(
            "UPDATE decon_swabs SET result=$1, ct_value=$2, action_taken=$3,"
            " result_at=now(), updated_at=now() WHERE id=$4 RETURNING *",
            body.result, body.ct_value, body.action_taken, swab_id)
        if row is None:
            raise HTTPException(404, "Swab not found")
        if body.result == "positive":
            room = await c.fetchrow("SELECT name FROM rooms WHERE id=$1", row["room_id"])
            await safe_emit(c, user, verb="decon_swab_positive", object_type="decon_swab",
                            object_id=swab_id, recipients=[],
                            params={"room": room["name"] if room else "",
                                    "swab_code": row["swab_code"]})
    return {"id": swab_id, "result": row["result"],
            "ct_value": float(row["ct_value"]) if row["ct_value"] is not None else None,
            "result_at": row["result_at"].isoformat()}


# ── release ──────────────────────────────────────────────────────────────────

@router.post("/cycles/{cycle_id}/release")
async def release_room(cycle_id: str, body: ReleaseIn,
                       user: dict = Depends(require_role(*_QA_WRITERS))):
    """"A room is released by the QA Manager, in writing, against a complete
    room batch record: every step signed, all tests within limits ... Nobody
    else can release a room, and no room is released verbally."

    Enforced: cycle must be awaiting_verification (every step signed, the
    white-cloth gate passed — see record_step), and every swab taken for this
    room/cycle must be 'negative'. Any 'pending' or 'positive' swab blocks it."""
    async with rls(user) as c:
        cyc = await _cycle_or_404(c, cycle_id)
        if cyc["status"] != "awaiting_verification":
            raise HTTPException(
                409, f"cycle is {cyc['status']}, not awaiting_verification — "
                "the room cycle is not complete")
        swabs = await _swab_summary(c, cyc["room_id"], cycle_id)
        blocking = swabs["pending"] + swabs["positive"] + swabs["inconclusive"]
        if blocking:
            raise HTTPException(
                409, f"{blocking} swab(s) not negative "
                f"(pending={swabs['pending']} positive={swabs['positive']} "
                f"inconclusive={swabs['inconclusive']}) — room cannot be released")
        if swabs["negative"] == 0:
            raise HTTPException(409, "no negative swab on file — a room is never released on zero verification")
        row = await c.fetchrow(
            "UPDATE decon_room_cycles SET status='released', released_by=$1,"
            " released_at=now(), release_note=$2, updated_by=$1, updated_at=now()"
            " WHERE id=$3 RETURNING *", user["id"], body.release_note, cycle_id)
        await safe_emit(c, user, verb="decon_room_released", object_type="decon_room_cycle",
                        object_id=cycle_id, recipients=[],
                        params={"room": cyc["room_name"], "campaign": cyc["campaign"]})
    return {"id": cycle_id, "status": row["status"], "released_at": row["released_at"].isoformat()}


@router.post("/cycles/{cycle_id}/fail")
async def fail_cycle(cycle_id: str, body: CycleFailIn,
                     user: dict = Depends(require_role(*_QA_WRITERS))):
    """The counterpart to release_room — explicitly fail/abandon a cycle.

    A positive (or otherwise disqualifying) swab result can land on a cycle at
    ANY status, since record_swab_result does not check cycle status. Once a
    cycle reaches awaiting_verification, record_step refuses any further step
    (409) — so without this endpoint a cycle that will never pass is a dead
    end: no re-clean path exists, and create_cycle's duplicate-campaign guard
    keeps treating the room as occupied for that campaign (it only lets a
    fresh cycle start once the old one is no longer 'in_progress' or
    'awaiting_verification' — see the open_cyc query in create_cycle, which
    already excludes 'failed' the same way it excludes 'released').

    Gated to the same QA_MGR-tier writers as release_room and record_swab_
    result: failing a cycle is the QA judgement call that a room did not pass
    verification, the mirror image of releasing one.

    Requires a stated reason — same discipline as biosecurity.py's fail-must-
    have-action_taken gate (`_FAIL_RESULTS`): a failed cycle with no reason on
    file recorded is exactly the kind of undocumented quality call that gate
    exists to prevent."""
    if not body.reason or not body.reason.strip():
        raise HTTPException(422, "a failed cycle must state a reason")
    async with rls(user) as c:
        cyc = await _cycle_or_404(c, cycle_id)
        if cyc["status"] not in ("in_progress", "awaiting_verification"):
            raise HTTPException(
                409, f"cycle is {cyc['status']}; only an open cycle "
                "(in_progress or awaiting_verification) can be failed")
        note = (f"FAILED: {body.reason}" if not cyc["note"]
               else f"{cyc['note']} | FAILED: {body.reason}")
        row = await c.fetchrow(
            "UPDATE decon_room_cycles SET status='failed', note=$1,"
            " updated_by=$2, updated_at=now() WHERE id=$3 RETURNING *",
            note, user["id"], cycle_id)
        await safe_emit(c, user, verb="decon_cycle_failed", object_type="decon_room_cycle",
                        object_id=cycle_id, recipients=[],
                        params={"room": cyc["room_name"], "campaign": cyc["campaign"],
                                "reason": body.reason})
    return {"id": cycle_id, "status": row["status"], "note": row["note"],
            "failed_at": row["updated_at"].isoformat()}


# ── frozen positive controls ─────────────────────────────────────────────────
# "Makes every later negative falsifiable. Free, irreplaceable once plants are
# gone." Taken BEFORE the cull; QA owns them because they are the reference the
# swab results are interpreted against.

@router.get("/positive-controls")
async def list_positive_controls(user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT pc.id, pc.control_code, pc.room_id, pc.material, pc.source_desc,"
            " pc.taken_at, pc.storage_location, pc.frozen, pc.note, r.name AS room_name"
            " FROM decon_positive_controls pc"
            " LEFT JOIN rooms r ON r.id = pc.room_id"
            " ORDER BY pc.taken_at DESC")
    return {"controls": [
        {"id": str(r["id"]), "control_code": r["control_code"],
         "room_id": str(r["room_id"]) if r["room_id"] else None,
         "room_name": r["room_name"], "material": r["material"],
         "source_desc": r["source_desc"], "taken_at": r["taken_at"].isoformat(),
         "storage_location": r["storage_location"], "frozen": r["frozen"],
         "note": r["note"]}
        for r in rows]}


@router.post("/positive-controls", status_code=201)
async def create_positive_control(body: PositiveControlIn,
                                  user: dict = Depends(require_role(*_QA_WRITERS))):
    if body.material not in _CONTROL_MATERIALS:
        raise HTTPException(422, f"material must be one of: {', '.join(_CONTROL_MATERIALS)}")
    async with rls(user) as c:
        if body.room_id is not None:
            await _room_or_422(c, body.room_id)
        dup = await c.fetchrow(
            "SELECT id FROM decon_positive_controls WHERE org_id=$1 AND control_code=$2",
            user["org_id"], body.control_code)
        if dup is not None:
            raise HTTPException(409, f"control code {body.control_code} already exists")
        row = await c.fetchrow(
            "INSERT INTO decon_positive_controls(org_id, control_code, room_id, material,"
            " source_desc, taken_by, storage_location, note)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
            user["org_id"], body.control_code, body.room_id, body.material,
            body.source_desc, user["id"], body.storage_location, body.note)
    return {"id": str(row["id"]), "control_code": row["control_code"],
            "material": row["material"], "taken_at": row["taken_at"].isoformat()}


# ── tool sterilisation log ───────────────────────────────────────────────────

@router.get("/tool-log")
async def list_tool_log(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                        room_id: str | None = Query(None),
                        limit: int = Query(200, ge=1, le=2000)):
    if room_id is not None:
        uuid_or_422(room_id, "room_id must be a uuid")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT id, room_id, cycle_id, tool_set, ppm_strip_reading, soak_minutes,"
            " checked_at, note FROM decon_tool_log"
            " WHERE ($1::uuid IS NULL OR room_id=$1)"
            " ORDER BY checked_at DESC LIMIT $2", room_id, limit)
    return {"target_ppm": _TOOL_TARGET_PPM, "entries": [
        {"id": str(r["id"]), "room_id": str(r["room_id"]),
         "cycle_id": str(r["cycle_id"]) if r["cycle_id"] else None,
         "tool_set": r["tool_set"], "ppm_strip_reading": r["ppm_strip_reading"],
         "soak_minutes": float(r["soak_minutes"]) if r["soak_minutes"] is not None else None,
         "checked_at": r["checked_at"].isoformat(), "note": r["note"]}
        for r in rows]}


@router.post("/tool-log", status_code=201)
async def record_tool_check(body: ToolLogIn,
                            user: dict = Depends(require_role(*_CLEAN_WRITERS))):
    """Below-target is RECORDED, not rejected — same reasoning as the bleach log.
    A refused entry means the crew simply does not log it, and an unlogged weak
    bucket is invisible; a logged one is a finding someone can act on."""
    async with rls(user) as c:
        room = await _room_or_422(c, body.room_id)
        if body.cycle_id is not None:
            await _cycle_or_404(c, body.cycle_id)
        row = await c.fetchrow(
            "INSERT INTO decon_tool_log(org_id, room_id, cycle_id, tool_set,"
            " ppm_strip_reading, soak_minutes, checked_by, note)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
            user["org_id"], body.room_id, body.cycle_id, body.tool_set,
            body.ppm_strip_reading, body.soak_minutes, user["id"], body.note)
        if body.ppm_strip_reading < _TOOL_TARGET_PPM:
            await safe_emit(c, user, verb="decon_tool_below_spec", object_type="room",
                            object_id=body.room_id, recipients=[],
                            params={"room": room["name"], "ppm": body.ppm_strip_reading,
                                    "target": _TOOL_TARGET_PPM})
    return {"id": str(row["id"]), "room_id": body.room_id, "tool_set": row["tool_set"],
            "ppm_strip_reading": row["ppm_strip_reading"],
            "target_ppm": _TOOL_TARGET_PPM,
            "checked_at": row["checked_at"].isoformat()}


# ── corridor cleaning cadence (§25, migration 0049) ──────────────────────────
#
# A LOG ANSWERS "WAS IT CLEANED"; THE PLAN ASKS "OFTEN ENOUGH, AND AFTER THE
# EVENTS THAT DEMAND IT". §25 requires the cultivation corridors cleaned after
# every waste movement, every 4 hours, and at shift changeover. So the write
# endpoint records which of those three rules a cleaning discharges, and the read
# endpoint derives whether the cadence is currently being met — a bare list of
# timestamps would leave that arithmetic to whoever is reading the board at 3am.
#
# The interval is DERIVED at read time rather than stored as a due-date, because a
# stored due-date is a second source of truth that goes stale the moment someone
# cleans early, and because a due-date row implies something will act on it.
# Nothing here enforces the cadence: software cannot make anyone mop a corridor,
# and a board that implied otherwise would show a false green.

_CORRIDOR_TRIGGERS = ("waste_movement", "four_hourly", "shift_change", "other")
_CORRIDOR_INTERVAL_MIN = 240   # the plan's 4 hours, in ONE place


class CorridorCleaningIn(BaseModel):
    room_id: str
    trigger: str
    manifest_id: str | None = None
    campaign: str | None = Field(default=None, max_length=120)
    ppm_strip_reading: int | None = Field(default=None, ge=0, le=200000)
    note: str | None = Field(default=None, max_length=500)


@router.get("/corridors")
async def corridor_cadence(user: dict = Depends(require_role(*ELEVATED_ROLES)),
                           campaign: str | None = Query(None)):
    """Per corridor: when it was last cleaned, how long ago, and whether that is
    inside the 4-hour interval. Plus the join neither table can do alone — a
    DISPOSED waste manifest with no corridor cleaning recorded after it.

    Corridors are identified by the room register, not by a hardcoded list: the
    facility's corridors are C146/C152/C155/C169/C170, but inventing that list
    here would silently ignore a corridor added later. A room counts as a corridor
    if its name says so, which is how the register itself distinguishes them —
    `rooms` has no corridor `kind` (they are `other`), and adding one would be a
    schema change to carry a label this query can already read."""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT r.id, r.code, r.name, r.name_mk,"
            " (SELECT max(cc.cleaned_at) FROM corridor_cleanings cc"
            "  WHERE cc.room_id = r.id"
            "    AND ($1::text IS NULL OR cc.campaign = $1)) AS last_cleaned,"
            " (SELECT count(*) FROM corridor_cleanings cc"
            "  WHERE cc.room_id = r.id"
            "    AND ($1::text IS NULL OR cc.campaign = $1)) AS cleanings"
            " FROM rooms r"
            " WHERE r.is_active AND (r.name ILIKE 'corridor%' OR r.name_mk ILIKE 'коридор%')"
            " ORDER BY r.sort, r.code", campaign)
        # A disposed manifest with no cleaning that CITES IT and happened after it.
        #
        # STRICT ON PURPOSE. An earlier draft also accepted any cleaning with
        # trigger='waste_movement', on the theory that one sweep covers whatever
        # moved. That is a hole: a cleaning attesting to movement A, timed after
        # movement B, would silently discharge B, and nobody ever attested to B.
        # It also made the mandatory manifest citation pointless — if any
        # movement-triggered sweep clears every movement, there is no reason to ask
        # which one it followed. "After EVERY waste movement" means per movement,
        # so one sweep following two movements is two records. That is the record
        # the plan asks for, and it is one extra form submission.
        #
        # A mutation removing the loose clause survived the test suite, which is
        # how the hole was found: nothing failed, because nothing had a reason to
        # depend on the weaker reading.
        open_movements = await c.fetch(
            "SELECT m.id, m.manifest_code, m.disposed_at"
            " FROM waste_manifests m"
            " WHERE m.status = 'disposed' AND m.disposed_at IS NOT NULL"
            "   AND ($1::text IS NULL OR m.campaign = $1)"
            "   AND NOT EXISTS ("
            "     SELECT 1 FROM corridor_cleanings cc"
            "     WHERE cc.manifest_id = m.id AND cc.cleaned_at >= m.disposed_at)"
            " ORDER BY m.disposed_at", campaign)
    now = datetime.now(timezone.utc)
    corridors = []
    for r in rows:
        last = r["last_cleaned"]
        mins = None if last is None else int((now - last).total_seconds() // 60)
        corridors.append({
            "room_id": str(r["id"]), "code": r["code"],
            "name": r["name"], "name_mk": r["name_mk"],
            "last_cleaned": last.isoformat() if last else None,
            "minutes_since": mins,
            "cleanings": r["cleanings"],
            # Never cleaned is overdue, not "unknown": during the campaign a
            # corridor with no record is the case the requirement is aimed at.
            #
            # `>=`, not `>`: "cleaned every 4 hours" makes it DUE at the four-hour
            # mark, not a minute after. The boundary was undefined behaviour until
            # a mutation flipping the operator survived the suite, so it is now
            # decided in one direction and pinned at 239/240/241.
            "overdue": mins is None or mins >= _CORRIDOR_INTERVAL_MIN,
        })
    return {
        "interval_minutes": _CORRIDOR_INTERVAL_MIN,
        "corridors": corridors,
        "movements_without_cleaning": [
            {"manifest_id": str(m["id"]), "manifest_code": m["manifest_code"],
             "disposed_at": m["disposed_at"].isoformat()}
            for m in open_movements],
    }


@router.get("/corridors/{room_id}/cleanings")
async def list_corridor_cleanings(room_id: str,
                                  user: dict = Depends(require_role(*ELEVATED_ROLES)),
                                  limit: int = Query(200, ge=1, le=2000)):
    uuid_or_404(room_id, "Room not found")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT cc.id, cc.trigger, cc.manifest_id, cc.campaign,"
            " cc.ppm_strip_reading, cc.cleaned_at, cc.note, m.manifest_code"
            " FROM corridor_cleanings cc"
            " LEFT JOIN waste_manifests m ON m.id = cc.manifest_id"
            " WHERE cc.room_id=$1 ORDER BY cc.cleaned_at DESC LIMIT $2", room_id, limit)
    return {"room_id": room_id, "cleanings": [
        {"id": str(r["id"]), "trigger": r["trigger"],
         "manifest_id": str(r["manifest_id"]) if r["manifest_id"] else None,
         "manifest_code": r["manifest_code"], "campaign": r["campaign"],
         "ppm_strip_reading": r["ppm_strip_reading"],
         "cleaned_at": r["cleaned_at"].isoformat(), "note": r["note"]}
        for r in rows]}


@router.post("/corridors/cleanings", status_code=201)
async def record_corridor_cleaning(body: CorridorCleaningIn,
                                   user: dict = Depends(require_role(*_CLEAN_WRITERS))):
    """Record one corridor clean and which of §25's rules it discharges.

    A `waste_movement` clean MUST cite the manifest it followed — otherwise it
    cannot discharge "after every waste movement", because there is nothing
    tying it to a movement. The schema enforces the same thing; this is here so
    the refusal carries a sentence instead of a constraint name."""
    if body.trigger not in _CORRIDOR_TRIGGERS:
        raise HTTPException(422, f"trigger must be one of: {', '.join(_CORRIDOR_TRIGGERS)}")
    if body.trigger == "waste_movement" and body.manifest_id is None:
        raise HTTPException(
            422, "a cleaning triggered by a waste movement must cite the manifest it followed")
    async with rls(user) as c:
        room = await _room_or_422(c, body.room_id)
        if body.manifest_id is not None:
            uuid_or_422(body.manifest_id, "Unknown manifest")
            m = await c.fetchrow(
                "SELECT id FROM waste_manifests WHERE id=$1", body.manifest_id)
            if m is None:
                raise HTTPException(422, "Unknown manifest")
        row = await c.fetchrow(
            "INSERT INTO corridor_cleanings(org_id, room_id, campaign, trigger,"
            " manifest_id, ppm_strip_reading, cleaned_by, note)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
            user["org_id"], body.room_id, body.campaign, body.trigger,
            body.manifest_id, body.ppm_strip_reading, user["id"], body.note)
        # Below the surface specification is a finding, not a refusal — same
        # reasoning as the bleach and tool logs above.
        if body.ppm_strip_reading is not None and body.ppm_strip_reading < _SURFACE_TARGET_PPM:
            await safe_emit(c, user, verb="decon_corridor_below_spec", object_type="room",
                            object_id=body.room_id, recipients=[],
                            params={"room": room["name"], "ppm": body.ppm_strip_reading,
                                    "target": _SURFACE_TARGET_PPM})
    return {"id": str(row["id"]), "room_id": body.room_id, "trigger": row["trigger"],
            "cleaned_at": row["cleaned_at"].isoformat(),
            "interval_minutes": _CORRIDOR_INTERVAL_MIN}
