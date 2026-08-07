"""Per-cultivar THC potency ladders — PP-QC-SPEC-001 (owner decision 2026-08-07).

A batch is graded on **Total Δ9-THC** (= Δ9-THC + 0.877 × Δ9-THCA, the same
Ph. Eur. 3028 sum the CoQ already computes) against a ladder that is specific
to each cultivar — NOT a single global grade table. Per strain: a floor (the
strain's lowest observed batch − ~1.00 pp), and the span [floor, 30 %] cut into
2–4 named specifications; **Spec I is the top range (up to 30 %)**, descending
II/III/IV. Each tier carries a 2-decimal range, an optional width (pp) and a
declared nominal.

The owner's decision is that these ladders are **stored, approved spec data** —
authored and APPROVED by a human, then read as-is when a certificate is issued —
NOT recomputed on the fly. So this models them the controlled way
`qc_specifications` models material specs: a versioned parent
(`qc_potency_specs`, one APPROVED row per cultivar at a time) with child tier
rows (`qc_potency_spec_ranges`). Disposition — which Spec a batch falls in — is a
pure read against the APPROVED ladder (`disposition_for`), exposed here and
consumed by the certificate pipeline.

Segregation of duties mirrors the eCoA control (M5): the person who APPROVES a
ladder must not be the person who authored it.
"""
from datetime import date

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from app.worktime import SITE_TODAY_SQL

from .common import _HOQC, _WRITERS, _uuid_or_404, _uuid_or_422, router

# The full span every ladder tops out at — Spec I always reaches 30 %.
_CEILING = 30.0
# Float comparison slack: ranges are authored to 2 decimals, so a boundary that
# should "meet" (26.00 == 26.00) must survive numeric round-tripping.
_EPS = 1e-6

# Roman labels for tiers 1..6 (Spec I = the top range). Tier 1 is highest.
_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}


class RangeIn(BaseModel):
    tier: int = Field(ge=1, le=6)
    range_min: float = Field(ge=0, le=30)
    range_max: float = Field(gt=0, le=30)
    nominal: float = Field(ge=0, le=30)
    width_pp: float | None = Field(default=None, ge=0, le=30)
    n_batches: int = Field(default=0, ge=0)


class PotencySpecIn(BaseModel):
    cultivar_id: str
    version: str = Field(max_length=60)
    variant: str | None = Field(default=None, max_length=60)
    floor_pct: float = Field(ge=0, le=30)
    observed_min: float | None = Field(default=None, ge=0, le=100)
    observed_max: float | None = Field(default=None, ge=0, le=100)
    n_batches: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=4000)
    ranges: list[RangeIn] = Field(min_length=1, max_length=6)


class PotencySpecPatch(BaseModel):
    """DRAFT-only edits. `ranges`, when present, REPLACES the whole ladder (a
    ladder is only meaningful validated as a contiguous whole, never row-by-row)."""
    version: str | None = Field(default=None, max_length=60)
    variant: str | None = Field(default=None, max_length=60)
    floor_pct: float | None = Field(default=None, ge=0, le=30)
    observed_min: float | None = Field(default=None, ge=0, le=100)
    observed_max: float | None = Field(default=None, ge=0, le=100)
    n_batches: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)
    ranges: list[RangeIn] | None = Field(default=None, min_length=1, max_length=6)


def _validate_ladder(floor_pct: float, ranges: list[RangeIn]) -> None:
    """A ladder must TILE [floor, 30 %] with no gap and no overlap — that total
    coverage is exactly what makes a batch's disposition unambiguous. Enforced:
    tiers are 1..N contiguous; Spec I (tier 1) tops at 30 %; adjacent tiers meet
    at a shared boundary; the bottom tier bottoms at the floor; each nominal sits
    inside its own range. Raises 422 on any violation."""
    tiers = sorted(r.tier for r in ranges)
    if tiers != list(range(1, len(ranges) + 1)):
        raise HTTPException(
            422, "tiers must be a contiguous run starting at 1 (1 = Spec I, the top range);"
                 f" got {tiers}")
    ordered = sorted(ranges, key=lambda r: r.tier)  # tier 1 first = highest range
    for r in ranges:
        if not (r.range_max > r.range_min):
            raise HTTPException(422, f"Spec {_ROMAN[r.tier]}: range_max must exceed range_min")
        if not (r.range_min - _EPS <= r.nominal <= r.range_max + _EPS):
            raise HTTPException(
                422, f"Spec {_ROMAN[r.tier]}: nominal {r.nominal} is outside its range"
                     f" [{r.range_min}, {r.range_max}]")
    if abs(ordered[0].range_max - _CEILING) > _EPS:
        raise HTTPException(
            422, f"Spec I (tier 1) must top out at {_CEILING:.0f} % — got {ordered[0].range_max}")
    for hi, lo in zip(ordered, ordered[1:]):
        if abs(hi.range_min - lo.range_max) > _EPS:
            raise HTTPException(
                422, f"Spec {_ROMAN[hi.tier]} and Spec {_ROMAN[lo.tier]} do not meet:"
                     f" {hi.range_min} vs {lo.range_max} — the ladder must tile [floor, 30] with no gap")
    if abs(ordered[-1].range_min - floor_pct) > _EPS:
        raise HTTPException(
            422, f"the bottom tier (Spec {_ROMAN[ordered[-1].tier]}) must start at the floor"
                 f" {floor_pct} — got {ordered[-1].range_min}")


def disposition_for(floor_pct, ranges, value):
    """Resolve a Total Δ9-THC `value` to its tier against an APPROVED ladder.

    Returns a dict {tier, spec, nominal, range_min, range_max} or None when the
    value is below the floor (below spec). Boundary values belong to the UPPER
    tier (26.00 → Spec I, not Spec II): pick the tier with the largest range_min
    ≤ value. A value at or above 30 stays Spec I (the top range is open upward in
    practice). `ranges` are dicts (DB rows) or RangeIn; floats throughout."""
    if value is None:
        return None
    v = float(value)
    if v < float(floor_pct) - _EPS:
        return None
    best = None
    for r in ranges:
        rmin = float(r["range_min"] if isinstance(r, dict) else r.range_min)
        rmax = float(r["range_max"] if isinstance(r, dict) else r.range_max)
        tier = int(r["tier"] if isinstance(r, dict) else r.tier)
        nominal = float(r["nominal"] if isinstance(r, dict) else r.nominal)
        if v + _EPS >= rmin and (best is None or rmin > best["range_min"]):
            best = {"tier": tier, "spec": f"Spec {_ROMAN.get(tier, tier)}",
                    "nominal": nominal, "range_min": rmin, "range_max": rmax}
    return best


def _f(v):
    return float(v) if v is not None else None


def _spec_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "cultivar_id": str(r["cultivar_id"]),
        "spec_code": r["spec_code"], "version": r["version"], "variant": r["variant"],
        "basis": r["basis"], "floor_pct": _f(r["floor_pct"]),
        "observed_min": _f(r["observed_min"]), "observed_max": _f(r["observed_max"]),
        "n_batches": r["n_batches"], "data_supported": r["data_supported"],
        "status": r["status"],
        "effective_date": r["effective_date"].isoformat() if r["effective_date"] else None,
        "approved_by": str(r["approved_by"]) if r["approved_by"] else None,
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }


def _range_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "tier": r["tier"], "spec": f"Spec {_ROMAN.get(r['tier'], r['tier'])}",
        "range_min": _f(r["range_min"]), "range_max": _f(r["range_max"]),
        "nominal": _f(r["nominal"]), "width_pp": _f(r["width_pp"]), "n_batches": r["n_batches"],
    }


async def _insert_ranges(c, org_id, spec_id, ranges: list[RangeIn], user_id) -> None:
    for r in ranges:
        await c.execute(
            "INSERT INTO qc_potency_spec_ranges(org_id, potency_spec_id, tier, range_min,"
            " range_max, nominal, width_pp, n_batches, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$9)",
            org_id, spec_id, r.tier, r.range_min, r.range_max, r.nominal,
            r.width_pp, r.n_batches, user_id)


@router.get("/potency-specs")
async def list_potency_specs(cultivar_id: str | None = None, status: str | None = None,
                             user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if cultivar_id:
        _uuid_or_422(cultivar_id, "cultivar_id")
        args.append(cultivar_id); clauses.append(f"ps.cultivar_id=${len(args)}")
    if status:
        args.append(status); clauses.append(f"ps.status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT ps.*, cv.code AS cultivar_code, cv.name AS cultivar_name"
            " FROM qc_potency_specs ps JOIN cultivars cv ON cv.id = ps.cultivar_id"
            f"{where} ORDER BY cv.code, ps.version DESC", *args)
    out = []
    for r in rows:
        d = _spec_out(dict(r))
        d["cultivar_code"] = r["cultivar_code"]; d["cultivar_name"] = r["cultivar_name"]
        out.append(d)
    return out


@router.get("/potency-specs/{spec_id}")
async def get_potency_spec(spec_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(spec_id, "Potency specification")
    async with rls(user) as c:
        spec = await c.fetchrow(
            "SELECT ps.*, cv.code AS cultivar_code, cv.name AS cultivar_name"
            " FROM qc_potency_specs ps JOIN cultivars cv ON cv.id = ps.cultivar_id"
            " WHERE ps.id=$1", spec_id)
        if spec is None:
            raise HTTPException(404, "Potency specification not found")
        ranges = await c.fetch(
            "SELECT * FROM qc_potency_spec_ranges WHERE potency_spec_id=$1 ORDER BY tier", spec_id)
    d = _spec_out(dict(spec))
    d["cultivar_code"] = spec["cultivar_code"]; d["cultivar_name"] = spec["cultivar_name"]
    return {"spec": d, "ranges": [_range_out(dict(r)) for r in ranges]}


@router.post("/potency-specs", status_code=201)
async def create_potency_spec(body: PotencySpecIn, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_422(body.cultivar_id, "cultivar_id")
    _validate_ladder(body.floor_pct, body.ranges)
    # A strain is "data-supported" once it has ≥3 batches; below that the ladder
    # is provisional (PP-QC-SPEC-001), to be reviewed when a third batch exists.
    data_supported = body.n_batches >= 3
    async with rls(user) as c:
        cv = await c.fetchrow(
            "SELECT id FROM cultivars WHERE id=$1 AND is_active", body.cultivar_id)
        if cv is None:
            raise HTTPException(422, "Unknown or inactive cultivar")
        try:
            row = await c.fetchrow(
                "INSERT INTO qc_potency_specs(org_id, cultivar_id, version, variant, floor_pct,"
                " observed_min, observed_max, n_batches, data_supported, notes, created_by, updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$11) RETURNING *",
                user["org_id"], body.cultivar_id, body.version, body.variant, body.floor_pct,
                body.observed_min, body.observed_max, body.n_batches, data_supported,
                body.notes, user["id"])
        except Exception as e:
            if "qc_potency_specs_version_key" in str(e):
                raise HTTPException(409, "A potency ladder with this cultivar + version already exists")
            raise
        await _insert_ranges(c, user["org_id"], row["id"], body.ranges, user["id"])
        await safe_emit(c, user, verb="potency_spec_created", object_type="qc_potency_spec",
                        object_id=row["id"], recipients=[],
                        params={"version": row["version"], "cultivar_id": str(row["cultivar_id"])})
    return _spec_out(dict(row))


@router.patch("/potency-specs/{spec_id}")
async def update_potency_spec(spec_id: str, body: PotencySpecPatch,
                              user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(spec_id, "Potency specification")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT id, floor_pct, n_batches, status FROM qc_potency_specs WHERE id=$1", spec_id)
        if cur is None:
            raise HTTPException(404, "Potency specification not found")
        # Approved ladders are read-as-is when certificates issue; a change goes
        # through a new version, never an in-place edit (mirrors qc_specifications).
        if cur["status"] != "DRAFT":
            raise HTTPException(
                409, f"Potency ladder is {cur['status']}; supersede with a new version"
                     " instead of editing in place")
        new_ranges = body.ranges
        if "ranges" in patch or "floor_pct" in patch:
            floor = patch.get("floor_pct", float(cur["floor_pct"]))
            if new_ranges is None:
                rows = await c.fetch(
                    "SELECT tier, range_min, range_max, nominal, width_pp, n_batches"
                    " FROM qc_potency_spec_ranges WHERE potency_spec_id=$1", spec_id)
                new_ranges = [RangeIn(tier=r["tier"], range_min=float(r["range_min"]),
                                      range_max=float(r["range_max"]), nominal=float(r["nominal"]),
                                      width_pp=_f(r["width_pp"]), n_batches=r["n_batches"])
                              for r in rows]
            _validate_ladder(floor, new_ranges)
        fields, args = [], []
        _NULLABLE = {"variant", "observed_min", "observed_max", "notes"}
        for col, val in patch.items():
            if col == "ranges":
                continue
            if val is None and col not in _NULLABLE:
                continue
            args.append(val); fields.append(f"{col}=${len(args)}")
        if "n_batches" in patch and patch["n_batches"] is not None:
            args.append(patch["n_batches"] >= 3); fields.append(f"data_supported=${len(args)}")
        if fields:
            args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
            args.append(spec_id)
            try:
                # `fields` are `col=$n` fragments; every `col` is a fixed Pydantic
                # field name (a closed allowlist), and all user data travels in the
                # bound positional parameters — no value is interpolated into SQL.
                await c.execute(
                    f"UPDATE qc_potency_specs SET {', '.join(fields)}, updated_at=now()"  # nosec B608
                    f" WHERE id=${len(args)}", *args)
            except Exception as e:
                if "qc_potency_specs_version_key" in str(e):
                    raise HTTPException(409, "A potency ladder with this cultivar + version already exists")
                raise
        if "ranges" in patch and body.ranges is not None:
            await c.execute("DELETE FROM qc_potency_spec_ranges WHERE potency_spec_id=$1", spec_id)
            await _insert_ranges(c, user["org_id"], spec_id, body.ranges, user["id"])
        row = await c.fetchrow("SELECT * FROM qc_potency_specs WHERE id=$1", spec_id)
    return _spec_out(dict(row))


@router.post("/potency-specs/{spec_id}/approve")
async def approve_potency_spec(spec_id: str, user: dict = Depends(require_role(*_HOQC))):
    """DRAFT → APPROVED. Approving a new ladder auto-supersedes the cultivar's
    current APPROVED one (one-approved-per-cultivar). Segregation of duties: the
    approver must not be the author (M5)."""
    _uuid_or_404(spec_id, "Potency specification")
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT id, cultivar_id, status, created_by, updated_by FROM qc_potency_specs"
            " WHERE id=$1", spec_id)
        if cur is None:
            raise HTTPException(404, "Potency specification not found")
        if cur["status"] != "DRAFT":
            raise HTTPException(409, f"Only a DRAFT ladder can be approved (is {cur['status']})")
        if str(user["id"]) in (str(cur["created_by"]), str(cur["updated_by"])):
            raise HTTPException(
                403, "The person approving a potency ladder must be different from the person who"
                     " authored it (segregation of duties, PP-QC-SPEC-001)")
        # Supersede the current APPROVED ladder for this cultivar FIRST — the
        # partial unique index allows only one APPROVED row per (org, cultivar)
        # and is checked at statement end, not deferred.
        await c.execute(
            "UPDATE qc_potency_specs SET status='SUPERSEDED', updated_by=$1, updated_at=now()"
            " WHERE cultivar_id=$2 AND status='APPROVED' AND id<>$3",
            user["id"], cur["cultivar_id"], spec_id)
        row = await c.fetchrow(
            # SITE_TODAY_SQL is the facility-timezone "today" (not naive CURRENT_DATE,
            # which renders under the DB's UTC zone) — a trusted constant, no input.
            f"UPDATE qc_potency_specs SET status='APPROVED', approved_by=$1,"  # nosec B608
            f" effective_date=COALESCE(effective_date, {SITE_TODAY_SQL}), updated_by=$1, updated_at=now()"
            f" WHERE id=$2 RETURNING *", user["id"], spec_id)
        await safe_emit(c, user, verb="potency_spec_approved", object_type="qc_potency_spec",
                        object_id=spec_id, recipients=[],
                        params={"version": row["version"], "cultivar_id": str(row["cultivar_id"])})
    return _spec_out(dict(row))


@router.post("/potency-specs/{spec_id}/supersede")
async def supersede_potency_spec(spec_id: str, user: dict = Depends(require_role(*_HOQC))):
    """APPROVED → SUPERSEDED (retire a ladder without an immediate replacement)."""
    _uuid_or_404(spec_id, "Potency specification")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_potency_specs WHERE id=$1", spec_id)
        if cur is None:
            raise HTTPException(404, "Potency specification not found")
        if cur["status"] != "APPROVED":
            raise HTTPException(409, f"Only an APPROVED ladder can be superseded (is {cur['status']})")
        row = await c.fetchrow(
            "UPDATE qc_potency_specs SET status='SUPERSEDED', updated_by=$1, updated_at=now()"
            " WHERE id=$2 RETURNING *", user["id"], spec_id)
    return _spec_out(dict(row))


@router.get("/potency-disposition")
async def get_potency_disposition(cultivar_id: str, total_d9_thc: float,
                                  user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Resolve a Total Δ9-THC value to its grade against the cultivar's APPROVED
    ladder. Returns the tier (Spec I..N) or below_spec=true when under the floor;
    approved=false when the cultivar has no APPROVED ladder yet."""
    _uuid_or_422(cultivar_id, "cultivar_id")
    async with rls(user) as c:
        spec = await c.fetchrow(
            "SELECT * FROM qc_potency_specs WHERE cultivar_id=$1 AND status='APPROVED'", cultivar_id)
        if spec is None:
            return {"approved": False, "cultivar_id": cultivar_id, "total_d9_thc": total_d9_thc}
        ranges = await c.fetch(
            "SELECT tier, range_min, range_max, nominal FROM qc_potency_spec_ranges"
            " WHERE potency_spec_id=$1 ORDER BY tier", spec["id"])
    disp = disposition_for(spec["floor_pct"], [dict(r) for r in ranges], total_d9_thc)
    return {
        "approved": True, "cultivar_id": cultivar_id, "total_d9_thc": total_d9_thc,
        "potency_spec_id": str(spec["id"]), "version": spec["version"],
        "floor_pct": _f(spec["floor_pct"]),
        "below_spec": disp is None, "disposition": disp,
    }
