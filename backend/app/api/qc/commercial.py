"""Batch commercial identities — per-batch Original→Neu rename, brand, label.

The owner's Portfolio Master renames strains **per batch** (the same original
cultivar maps to different commercial names on different batches), each with a
brand (STEADY/CAYN), a final label, the declared THC% and a commercial THC
bracket. Migration 0059 models this as `batch_commercial_identities`, keyed by
the batch-code string — the same free-text code QC rows carry in
`qc_certificates.batch_id` / `qc_coq.batch_id`.

The identity NEVER alters certificate content: the CoQ certifies the batch as
tested (original cultivar, measured potency). The commercial identity is
carried alongside for labeling/deliverable generation (T1_rename-style
exports), and the CoQ detail surfaces it read-only.

Import note (handoff §6): the Portfolio Master's THC% values are the
original/intake values, NOT retest values — the two are intentionally
different data sources; nothing here reconciles them.
"""
import json
from pathlib import Path

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES

from .common import _HOQC, _WRITERS, router

_PORTFOLIO_PATH = Path(__file__).resolve().parents[2] / "data" / "portfolio_master.json"


class CommercialIn(BaseModel):
    tranche: int | None = Field(default=None, ge=1, le=99)
    original_name: str | None = Field(default=None, max_length=200)
    neu_name: str = Field(max_length=200)
    brand: str | None = Field(default=None, max_length=60)
    final_label: str | None = Field(default=None, max_length=200)
    thc_declared: float | None = Field(default=None, ge=0, le=100)
    thc_bracket: str | None = Field(default=None, max_length=40)
    volume_kg: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


def _out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "batch_code": r["batch_code"], "tranche": r["tranche"],
        "original_name": r["original_name"], "neu_name": r["neu_name"],
        "brand": r["brand"], "final_label": r["final_label"],
        "thc_declared": float(r["thc_declared"]) if r["thc_declared"] is not None else None,
        "thc_bracket": r["thc_bracket"],
        "volume_kg": float(r["volume_kg"]) if r["volume_kg"] is not None else None,
        "notes": r["notes"], "updated_at": r["updated_at"].isoformat(),
    }


@router.get("/commercial-identities")
async def list_commercial(batch_code: str | None = None, tranche: int | None = None,
                          brand: str | None = None,
                          user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if batch_code:
        args.append(batch_code); clauses.append(f"batch_code=${len(args)}")
    if tranche is not None:
        args.append(tranche); clauses.append(f"tranche=${len(args)}")
    if brand:
        args.append(brand); clauses.append(f"brand=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT * FROM batch_commercial_identities"
            f"{where} ORDER BY tranche NULLS LAST, batch_code", *args)
    return [_out(dict(r)) for r in rows]


@router.put("/commercial-identities/{batch_code:path}")
async def upsert_commercial(batch_code: str, body: CommercialIn,
                            user: dict = Depends(require_role(*_WRITERS))):
    batch_code = batch_code.strip()
    if not batch_code or len(batch_code) > 120:
        raise HTTPException(422, "batch_code must be 1–120 characters")
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO batch_commercial_identities(org_id, batch_code, tranche,"
            " original_name, neu_name, brand, final_label, thc_declared, thc_bracket,"
            " volume_kg, notes, created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12)"
            " ON CONFLICT (org_id, batch_code) DO UPDATE SET"
            "   tranche=EXCLUDED.tranche, original_name=EXCLUDED.original_name,"
            "   neu_name=EXCLUDED.neu_name, brand=EXCLUDED.brand,"
            "   final_label=EXCLUDED.final_label, thc_declared=EXCLUDED.thc_declared,"
            "   thc_bracket=EXCLUDED.thc_bracket, volume_kg=EXCLUDED.volume_kg,"
            "   notes=EXCLUDED.notes, updated_by=EXCLUDED.updated_by, updated_at=now()"
            " RETURNING *",
            user["org_id"], batch_code, body.tranche, body.original_name, body.neu_name,
            body.brand, body.final_label, body.thc_declared, body.thc_bracket,
            body.volume_kg, body.notes, user["id"])
        await safe_emit(c, user, verb="commercial_identity_upserted",
                        object_type="batch_commercial_identity", object_id=row["id"],
                        recipients=[], params={"batch_code": batch_code,
                                               "neu_name": body.neu_name})
    return _out(dict(row))


@router.delete("/commercial-identities/{batch_code:path}")
async def delete_commercial(batch_code: str, user: dict = Depends(require_role(*_HOQC))):
    async with rls(user) as c:
        res = await c.execute(
            "DELETE FROM batch_commercial_identities WHERE batch_code=$1", batch_code)
    if res.split()[-1] == "0":
        raise HTTPException(404, "No commercial identity for that batch code")
    return {"ok": True}


@router.post("/commercial-identities/import")
async def import_portfolio(user: dict = Depends(require_role(*_HOQC))):
    """Load the packaged Portfolio Master (78 batches). Idempotent upsert by
    batch code — re-running refreshes rows to the packaged values."""
    try:
        with open(_PORTFOLIO_PATH, encoding="utf-8") as f:
            rows = json.load(f)
    except FileNotFoundError:
        raise HTTPException(503, "The packaged portfolio master is missing from this build")
    imported = 0
    async with rls(user) as c:
        last_id = None
        for r in rows:
            batch = (r.get("batch") or "").strip()
            neu = (r.get("neu") or "").strip()
            if not batch or not neu:
                continue
            thc = r.get("thc_frac")
            # the sheet stores THC as a fraction (0.218); the app stores percent
            thc_pct = round(float(thc) * 100, 2) if thc is not None else None
            row = await c.fetchrow(
                "INSERT INTO batch_commercial_identities(org_id, batch_code, tranche,"
                " original_name, neu_name, brand, final_label, thc_declared, thc_bracket,"
                " volume_kg, notes, created_by, updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12)"
                " ON CONFLICT (org_id, batch_code) DO UPDATE SET"
                "   tranche=EXCLUDED.tranche, original_name=EXCLUDED.original_name,"
                "   neu_name=EXCLUDED.neu_name, brand=EXCLUDED.brand,"
                "   final_label=EXCLUDED.final_label, thc_declared=EXCLUDED.thc_declared,"
                "   thc_bracket=EXCLUDED.thc_bracket, volume_kg=EXCLUDED.volume_kg,"
                "   notes=EXCLUDED.notes, updated_by=EXCLUDED.updated_by, updated_at=now()"
                " RETURNING id",
                user["org_id"], batch, r.get("tranche"), r.get("original"), neu,
                r.get("brand"), r.get("final_label"), thc_pct, r.get("thc_bracket"),
                r.get("volume_kg"),
                "Imported from Portfolio Master (01_Portfolio_Master) — intake THC%, "
                "not retest (handoff: the two are intentionally distinct).",
                user["id"])
            last_id = row["id"]
            imported += 1
        if imported:
            await safe_emit(c, user, verb="portfolio_master_imported",
                            object_type="batch_commercial_identity", object_id=last_id,
                            recipients=[], params={"imported": imported})
    return {"imported": imported}
