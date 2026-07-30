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

THE TWO GATES THE PLAN INSISTS ON, ENFORCED HERE, NOT LEFT TO DISCIPLINE:
  1. Steps are IN ORDER, and rinse1_whitecloth must PASS before bleach is
     accepted. "Soiled cloth -> wash again; the bleach does not go on" — a
     failed white-cloth check does not block recording, it reopens
     detergent_wash instead of letting bleach follow a still-dirty surface.
  2. Release requires every step signed AND every swab for the room negative.
     A pending or positive swab blocks it outright — "no room is released on
     a pending result."
"""
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
        if body.ppm_strip_reading < 5000:
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
