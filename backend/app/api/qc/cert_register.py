from app.db import rls
from app.deps import require_role
from app.roles import ELEVATED_ROLES
from fastapi import Depends, HTTPException, Query

from .certificates import _CERT_TYPES, _coa_sop_status
from .common import _uuid_or_422, router


_RETENTION_MODES = ("expiring", "expired")


@router.get("/register")
async def certificate_register(
        year: int | None = None, quarter: int | None = None,
        cert_type: str | None = None, laboratory_id: str | None = None,
        pending: bool = False, oos_linked: bool = False,
        retention: str | None = None, within_days: int = 90,
        user: dict = Depends(require_role(*ELEVATED_ROLES))):
    if cert_type is not None and cert_type not in _CERT_TYPES:
        raise HTTPException(422, f"cert_type must be one of: {', '.join(_CERT_TYPES)}")
    if retention is not None and retention not in _RETENTION_MODES:
        raise HTTPException(422, f"retention must be one of: {', '.join(_RETENTION_MODES)}")
    if quarter is not None and quarter not in (1, 2, 3, 4):
        raise HTTPException(422, "quarter must be 1–4")
    _uuid_or_422(laboratory_id, "laboratory_id")
    within_days = max(0, min(within_days, 3650))
    clauses, args = [], []
    if year is not None:
        args.append(str(year)); clauses.append(f"split_part(coa_number, '-', 3) = ${len(args)}")
    if quarter is not None:
        args.append(quarter)
        clauses.append(f"report_date IS NOT NULL AND extract(quarter FROM report_date) = ${len(args)}")
    if cert_type is not None:
        args.append(cert_type); clauses.append(f"cert_type = ${len(args)}")
    if laboratory_id is not None:
        args.append(laboratory_id); clauses.append(f"laboratory_id = ${len(args)}")
    if pending:
        clauses.append("status NOT IN ('RELEASED', 'SUPERSEDED', 'VOIDED')")
    if oos_linked:
        clauses.append("EXISTS (SELECT 1 FROM qc_oos_records o WHERE o.batch_id = qc_certificates.batch_id)")
    if retention == "expired":
        clauses.append("retention_expiry IS NOT NULL AND retention_expiry < CURRENT_DATE")
    elif retention == "expiring":
        args.append(within_days)
        clauses.append(f"retention_expiry IS NOT NULL AND retention_expiry >= CURRENT_DATE"
                       f" AND retention_expiry <= CURRENT_DATE + ${len(args)}::int")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            f"SELECT * FROM qc_certificates{where} ORDER BY coa_number DESC", *args)
        rows = [dict(r) for r in rows]
        ids = [r["id"] for r in rows]
        batches = list({r["batch_id"] for r in rows if r["batch_id"]})
        lab_ids = list({r["laboratory_id"] for r in rows if r["laboratory_id"]})
        # bulk enrich (avoid N+1): open-OOS per batch, superseded-by per id, lab names
        oos_open = {}
        if batches:
            for o in await c.fetch(
                    "SELECT batch_id, count(*) n FROM qc_oos_records"
                    " WHERE batch_id = ANY($1) AND status <> 'CLOSED' GROUP BY batch_id", batches):
                oos_open[o["batch_id"]] = o["n"]
        superseded_by = {}
        if ids:
            for s in await c.fetch(
                    "SELECT supersedes_id, coa_number FROM qc_certificates"
                    " WHERE supersedes_id = ANY($1) AND status IN ('RELEASED', 'SUPERSEDED')", ids):
                superseded_by[str(s["supersedes_id"])] = s["coa_number"]
        lab_names = {}
        if lab_ids:
            for l in await c.fetch(
                    "SELECT id, name FROM qc_laboratories WHERE id = ANY($1)", lab_ids):
                lab_names[str(l["id"])] = l["name"]
    out = []
    for r in rows:
        out.append({
            "id": str(r["id"]), "coa_number": r["coa_number"], "batch_id": r["batch_id"],
            "cert_type": r["cert_type"], "status": r["status"], "decision": r["decision"],
            "sop_status": _coa_sop_status(r["status"], r["supersedes_id"]),
            "report_date": r["report_date"].isoformat() if r["report_date"] else None,
            "laboratory": lab_names.get(str(r["laboratory_id"])) if r["laboratory_id"] else None,
            "retention_start": r["retention_start"].isoformat() if r["retention_start"] else None,
            "retention_expiry": r["retention_expiry"].isoformat() if r["retention_expiry"] else None,
            "archive_ref": r["archive_ref"],
            "supersedes_id": str(r["supersedes_id"]) if r["supersedes_id"] else None,
            "superseded_by": superseded_by.get(str(r["id"])),
            "open_oos": oos_open.get(r["batch_id"], 0),
            "coq_document_id": r["coq_document_id"],
        })
    return out


@router.get("/register/gaps")
async def register_numbering_gaps(year: int = Query(..., ge=2000, le=2100),
                                  cert_type: str | None = None,
                                  user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Numbering-gap data-integrity report (§6.13). Certificate numbering is
    per-(org, cert_type, year) since the QCSOP 012 alignment (C2); certificates
    minted before that change instead share one legacy 'PP-COA-' sequence. Each
    independent numbering SERIES — identified by its own prefix, e.g. 'PP-COA',
    'iCoA-PP', 'eCoA-PP', 'CoQ-PP' — is gapped separately, so the format
    transition never produces a false "hundreds of certificates missing"
    reading from mixing two unrelated counters. Pass cert_type to scope to one
    certificate type; omit to see every series present that year. A gap is a
    flag to investigate against the archive — NOT proof of a missing record:
    numbering is shared across tenants on this database, so a gap may simply
    belong to another organisation (RLS hides it)."""
    if cert_type is not None and cert_type not in _CERT_TYPES:
        raise HTTPException(422, f"cert_type must be one of: {', '.join(_CERT_TYPES)}")
    args = [str(year)]
    where = "split_part(coa_number, '-', 3) = $1"
    if cert_type is not None:
        args.append(cert_type)
        where += " AND cert_type = $2"
    async with rls(user) as c:
        rows = await c.fetch(
            f"SELECT coa_number, cert_type FROM qc_certificates WHERE {where}", *args)
        # The CoQ-PP series is SHARED with the per-batch aggregation records
        # (qc_coq, C5) — their numbers must join the scan or every aggregation
        # CoQ would read as a false gap in the certificate-side series.
        if cert_type is None or cert_type == "COQ":
            rows = list(rows) + list(await c.fetch(
                "SELECT coq_number AS coa_number, 'COQ'::text AS cert_type"
                " FROM qc_coq WHERE split_part(coq_number, '-', 3) = $1", str(year)))
    series: dict[str, dict] = {}
    for r in rows:
        seq = r["coa_number"].rsplit("-", 1)[-1]
        if not seq.isdigit():
            continue
        prefix = r["coa_number"].rsplit("-", 2)[0]
        series.setdefault(prefix, {"cert_type": r["cert_type"], "nums": []})["nums"].append(int(seq))
    if not series:
        return {"year": year, "issued": 0, "min": None, "max": None, "gaps": [],
                "by_series": {}, "note": "No certificates issued in this year."}
    by_series, all_gaps, total = {}, [], 0
    for prefix, entry in series.items():
        nums = sorted(entry["nums"])
        present = set(nums)
        missing = [n for n in range(nums[0], nums[-1] + 1) if n not in present]
        gaps = [f"{prefix}-{year}-{n:04d}" for n in missing]
        by_series[prefix] = {"cert_type": entry["cert_type"], "issued": len(nums),
                             "min": nums[0], "max": nums[-1], "gaps": gaps}
        all_gaps.extend(gaps)
        total += len(nums)
    only = next(iter(by_series.values())) if len(by_series) == 1 else None
    return {
        "year": year, "issued": total,
        "min": only["min"] if only else None, "max": only["max"] if only else None,
        "gaps": all_gaps, "by_series": by_series,
        "note": ("Numbering is per certificate-type series since the QCSOP 012 §6.13"
                 " alignment; each series (prefix) is gapped independently. The sequence is"
                 " shared across tenants on this database, so a gap may reflect a certificate"
                 " issued to another organisation rather than a missing record — investigate"
                 " each against the archive."),
    }
