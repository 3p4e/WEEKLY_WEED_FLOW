"""Bulk import of the QCSP 001 potency-ladder catalogue (owner handoff 2026-08).

The owner's ImB Product-Specification handoff carries an approved grade ladder
for every strain in the portfolio — 71 strains / 257 grade rows, extracted
verbatim from the per-strain spec documents into
`app/data/imb_grade_ladders.json` (committed alongside the analysis in
docs/spc-handoff/). Three delivery families:

  BASE_SPCs — the 35 CULI-001-approved strains (full grade catalogue)
  NEWs      — new-import strains not yet on CULI-001 (e.g. GG4)
  RENs      — renamed commercial strains (Payday, Cookie Kush, …)

This endpoint loads that catalogue into `qc_potency_specs` as **DRAFT** rows —
never APPROVED: approval is a human act with segregation of duties (the
approver must differ from the importer), exactly as authored ladders. The
catalogue is code-shipped data (like demo_org's fixtures), not an upload: what
gets imported is reviewable in the repo, and the endpoint is idempotent on
UNIQUE(org_id, cultivar_id, version) so re-running it never duplicates.

Missing cultivars are auto-created (owner decision 2026-08-14): code = the
acronym from the product code (`GP_THC20:CBD1` → `GP`), name = the strain name.
A code already used by a DIFFERENT strain name is reported as a conflict and
skipped — never silently reassigned.
"""
import json
import re
from pathlib import Path

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role
from app.notify import safe_emit

from .common import _HOQC, router
from .potency import RangeIn, _insert_ranges, _validate_ladder

_CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "data" / "imb_grade_ladders.json"

_FAMILIES = ("BASE_SPCs", "NEWs", "RENs")

# "28.50% ± 1.50%" → (28.50, 1.50)
_NOMINAL_RE = re.compile(r"^([\d.]+)%\s*±\s*([\d.]+)%$")


class CatalogueImportIn(BaseModel):
    family: str = Field(default="ALL", description="BASE_SPCs | NEWs | RENs | ALL")
    version: str = Field(default="QCSP-001 v.03", max_length=60)
    dry_run: bool = False


def _load_catalogue() -> dict:
    try:
        with open(_CATALOGUE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(503, "The packaged ladder catalogue is missing from this build")


def _parse_rows(strain: str, rows: list[dict]) -> tuple[str, float, list[RangeIn]]:
    """One strain's JSON rows → (acronym, floor, validated RangeIn list).

    Raises 422 with the strain named if the authored data cannot be parsed —
    a malformed catalogue entry must fail loudly, never import half a ladder."""
    acr = (rows[0].get("product_code") or "").split("_THC")[0].strip()
    if not acr:
        raise HTTPException(422, f"{strain}: cannot derive an acronym from the product code")
    ranges: list[RangeIn] = []
    for r in rows:
        m = _NOMINAL_RE.match((r.get("nominal") or "").strip())
        if not m:
            raise HTTPException(422, f"{strain}: unparseable nominal {r.get('nominal')!r}")
        ranges.append(RangeIn(
            tier=r["tier"], range_min=r["range_min"], range_max=r["range_max"],
            nominal=float(m.group(1)), width_pp=float(m.group(2)), n_batches=0))
    floor = min(r.range_min for r in ranges)
    _validate_ladder(floor, ranges)
    return acr, floor, ranges


@router.post("/potency-specs/import")
async def import_potency_catalogue(body: CatalogueImportIn,
                                   user: dict = Depends(require_role(*_HOQC))):
    if body.family != "ALL" and body.family not in _FAMILIES:
        raise HTTPException(422, f"family must be one of: {', '.join(_FAMILIES)}, ALL")
    catalogue = _load_catalogue()
    families = _FAMILIES if body.family == "ALL" else (body.family,)

    created, skipped, conflicts, cultivars_created = [], [], [], []
    async with rls(user) as c:
        for fam in families:
            for strain, rows in (catalogue.get(fam) or {}).items():
                acr, floor, ranges = _parse_rows(strain, rows)
                # ── resolve or create the cultivar ─────────────────────────
                cv = await c.fetchrow(
                    "SELECT id, code, name FROM cultivars WHERE code=$1", acr)
                if cv is not None and cv["name"].strip().lower() != strain.strip().lower():
                    # The acronym is taken by a different strain — never guess.
                    by_name = await c.fetchrow(
                        "SELECT id, code, name FROM cultivars WHERE lower(name)=lower($1)", strain)
                    if by_name is None:
                        conflicts.append({"strain": strain, "code": acr,
                                          "taken_by": cv["name"]})
                        continue
                    cv = by_name
                if cv is None:
                    cv = await c.fetchrow(
                        "SELECT id, code, name FROM cultivars WHERE lower(name)=lower($1)", strain)
                if cv is None:
                    if body.dry_run:
                        cultivars_created.append({"code": acr, "name": strain})
                        cv = None
                    else:
                        cv = await c.fetchrow(
                            "INSERT INTO cultivars(org_id, code, name, created_by, updated_by)"
                            " VALUES ($1,$2,$3,$4,$4)"
                            " ON CONFLICT (org_id, code) DO NOTHING RETURNING id, code, name",
                            user["org_id"], acr, strain, user["id"])
                        if cv is None:   # lost a race — re-read
                            cv = await c.fetchrow(
                                "SELECT id, code, name FROM cultivars WHERE code=$1", acr)
                        cultivars_created.append({"code": acr, "name": strain})
                # ── idempotency: version already present? ──────────────────
                if cv is not None:
                    existing = await c.fetchval(
                        "SELECT id FROM qc_potency_specs WHERE cultivar_id=$1 AND version=$2",
                        cv["id"], body.version)
                    if existing:
                        skipped.append({"strain": strain, "reason": "version exists"})
                        continue
                if body.dry_run:
                    created.append({"strain": strain, "code": acr, "tiers": len(ranges),
                                    "floor": floor})
                    continue
                row = await c.fetchrow(
                    "INSERT INTO qc_potency_specs(org_id, cultivar_id, version, variant,"
                    " floor_pct, n_batches, data_supported, notes, created_by, updated_by)"
                    " VALUES ($1,$2,$3,$4,$5,0,false,$6,$7,$7) RETURNING id",
                    user["org_id"], cv["id"], body.version, fam, floor,
                    f"Imported from the owner's ImB handoff catalogue ({fam}); "
                    "batch counts unknown at import — provisional until reviewed.",
                    user["id"])
                await _insert_ranges(c, user["org_id"], row["id"], ranges, user["id"])
                last_spec_id = row["id"]
                created.append({"strain": strain, "code": acr, "tiers": len(ranges),
                                "floor": floor})
        if not body.dry_run and created:
            # events.object_id is NOT NULL — anchor the batch event on the last
            # created spec; the params carry the whole import's counts.
            await safe_emit(c, user, verb="potency_catalogue_imported",
                            object_type="qc_potency_spec", object_id=last_spec_id,
                            recipients=[],
                            params={"version": body.version, "family": body.family,
                                    "created": len(created), "skipped": len(skipped),
                                    "conflicts": len(conflicts)})
    return {"dry_run": body.dry_run, "version": body.version, "family": body.family,
            "created": created, "skipped": skipped, "conflicts": conflicts,
            "cultivars_created": cultivars_created}
