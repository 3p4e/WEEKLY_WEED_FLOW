from app import docengine
from app.db import rls, users_admin_pool
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .certificates import VoidIn, _mint_cert_number
from .common import (_COQ_ROLES, _HOQC, _WRITERS, _evaluate, _uuid_or_404, _uuid_or_422,
                     check_derived_total_units, router)
from .coq_docx import _coq_client, _coq_manifest, _coq_markdown
from .laboratories import _lab_scope_set, _result_in_scope
from .potency import disposition_for
from .specs import _ACID_FACTOR


_COQ_STATUSES = ("DRAFT", "APPROVED", "VOIDED")


_COQ_VOIDABLE = {"DRAFT", "APPROVED"}


_COQ_SOURCE_STATUSES = ("APPROVED", "RELEASED")


_COQ_SOURCE_TYPES = ("ICOA", "ECOA")


def _norm_test(name: str | None) -> str:
    """Fold a test name for comparison — same idiom as ecoa._norm_label /
    laboratories._norm. Both sides of the masked-failure match below are free
    text typed by different people at different times (qc_results.test_name on
    the analytical result, qc_oos_records.test_name on the investigation), so an
    investigation filed as "total  thc" still has to cover a "Total THC"
    failure. Only case and internal whitespace are folded — nothing else, so
    "Total THC" and "Total CBD" stay distinct."""
    return " ".join((name or "").split()).lower()


class CoqIn(BaseModel):
    batch_id: str = Field(max_length=120)
    specification_id: str
    # §6.4.2 batch identification — nullable; an unknown value stays blank for
    # a human, never invented (GxP).
    product_name: str | None = Field(default=None, max_length=300)
    manufacture_date: date | None = None
    batch_size: str | None = Field(default=None, max_length=120)
    comments: str | None = Field(default=None, max_length=4000)
    oos_reference: str | None = Field(default=None, max_length=300)
    # The cultivar this batch is — lets the CoQ grade it on Total Δ9-THC against
    # the cultivar's APPROVED potency ladder (PP-QC-SPEC-001). Optional: without
    # it the CoQ simply carries no grade (never invented).
    cultivar_id: str | None = None


def _coq_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coq_number": r["coq_number"], "batch_id": r["batch_id"],
        "product_name": r["product_name"],
        "manufacture_date": r["manufacture_date"].isoformat() if r["manufacture_date"] else None,
        "batch_size": r["batch_size"],
        "specification_id": str(r["specification_id"]),
        "spec_reference": r["spec_reference"],
        "status": r["status"], "overall_conform": r["overall_conform"],
        "comments": r["comments"], "oos_reference": r["oos_reference"],
        "compiled_by": str(r["compiled_by"]) if r["compiled_by"] else None,
        "compiled_at": r["compiled_at"].isoformat() if r["compiled_at"] else None,
        "reviewed_by": str(r["reviewed_by"]) if r["reviewed_by"] else None,
        "reviewed_at": r["reviewed_at"].isoformat() if r["reviewed_at"] else None,
        "void_reason": r["void_reason"],
        "voided_by": str(r["voided_by"]) if r["voided_by"] else None,
        "voided_at": r["voided_at"].isoformat() if r["voided_at"] else None,
        "coq_document_id": r["coq_document_id"],
        "coq_generated_at": r["coq_generated_at"].isoformat() if r["coq_generated_at"] else None,
        "cultivar_id": str(r["cultivar_id"]) if r.get("cultivar_id") else None,
        "potency_spec_id": str(r["potency_spec_id"]) if r.get("potency_spec_id") else None,
        "updated_at": r["updated_at"].isoformat(),
    }


async def _coq_disposition(c, coq_row: dict) -> dict | None:
    """The batch's potency grade (Spec I…N) — resolved against the ladder version
    FROZEN on the CoQ at compile time (qc_coq.potency_spec_id), read against the
    CoQ's own Total Δ9-THC line. Returns None when the CoQ carries no frozen
    ladder (no cultivar mapped, or none APPROVED at compile). Freezing the ladder
    id keeps the printed grade stable and traceable after later supersession."""
    spec_id = coq_row.get("potency_spec_id")
    if not spec_id:
        return None
    spec = await c.fetchrow(
        "SELECT ps.id, ps.version, ps.floor_pct, ps.status, cv.code AS cultivar_code,"
        " cv.name AS cultivar_name FROM qc_potency_specs ps"
        " JOIN cultivars cv ON cv.id = ps.cultivar_id WHERE ps.id=$1", spec_id)
    if spec is None:
        return None
    ranges = await c.fetch(
        "SELECT tier, range_min, range_max, nominal FROM qc_potency_spec_ranges"
        " WHERE potency_spec_id=$1 ORDER BY tier", spec_id)
    # The batch's Total Δ9-THC is the computed total_thc CoQ line (Ph. Eur. 3028).
    total = await c.fetchval(
        "SELECT l.result_numeric FROM qc_coq_lines l"
        " JOIN qc_spec_parameters p ON p.id = l.parameter_id"
        " WHERE l.coq_id=$1 AND p.computed_kind='total_thc'"
        " AND l.result_numeric IS NOT NULL LIMIT 1", coq_row["id"])
    total_f = float(total) if total is not None else None
    disp = disposition_for(spec["floor_pct"], [dict(r) for r in ranges], total_f)
    return {
        "potency_spec_id": str(spec["id"]), "version": spec["version"],
        "spec_status": spec["status"],
        "cultivar_code": spec["cultivar_code"], "cultivar_name": spec["cultivar_name"],
        "floor_pct": float(spec["floor_pct"]),
        "total_d9_thc": total_f,
        "below_spec": (total_f is not None and disp is None),
        "disposition": disp,
    }


def _coq_line_out(r: dict) -> dict:
    return {
        "id": str(r["id"]),
        "parameter_id": str(r["parameter_id"]) if r["parameter_id"] else None,
        "parameter_name": r["parameter_name"], "test_method": r["test_method"],
        "acceptance_criterion": r["acceptance_criterion"],
        "result_value": r["result_value"],
        "result_numeric": float(r["result_numeric"]) if r["result_numeric"] is not None else None,
        "unit": r["unit"], "complies": r["complies"], "testing_lab": r["testing_lab"],
        "source_coa_id": str(r["source_coa_id"]) if r["source_coa_id"] else None,
        "source_coa_number": r["source_coa_number"],
        "sorting_order": r["sorting_order"],
    }


def _coq_source_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coa_id": str(r["coa_id"]),
        "coa_number": r["coa_number"], "cert_type": r["cert_type"],
        "issue_date": r["issue_date"].isoformat() if r["issue_date"] else None,
    }


def _coq_criterion(lo, hi, unit) -> str | None:
    """Human acceptance-criterion snapshot from the spec limits — empty stays
    None (an absent limit is absent, never invented)."""
    if lo is None and hi is None:
        return None
    s = f"{'' if lo is None else lo} … {'' if hi is None else hi}".strip()
    return f"{s} {unit}".strip() if unit else s


@router.get("/coq")
async def list_coq(batch_id: str | None = None, status: str | None = None,
                   user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if batch_id:
        args.append(batch_id); clauses.append(f"batch_id=${len(args)}")
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(f"SELECT * FROM qc_coq{where} ORDER BY created_at DESC", *args)
    return [_coq_out(dict(r)) for r in rows]


@router.get("/coq/{coq_id}")
async def get_coq(coq_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        row = await c.fetchrow("SELECT * FROM qc_coq WHERE id=$1", coq_id)
        if row is None:
            raise HTTPException(404, "CoQ not found")
        lines = await c.fetch(
            "SELECT * FROM qc_coq_lines WHERE coq_id=$1 ORDER BY sorting_order, created_at", coq_id)
        sources = await c.fetch(
            "SELECT * FROM qc_coq_sources WHERE coq_id=$1 ORDER BY coa_number", coq_id)
        disposition = await _coq_disposition(c, dict(row))
    return {"coq": _coq_out(dict(row)),
            "lines": [_coq_line_out(dict(r)) for r in lines],
            "sources": [_coq_source_out(dict(r)) for r in sources],
            "potency": disposition}


@router.post("/coq", status_code=201)
async def compile_coq(body: CoqIn, user: dict = Depends(require_role(*_WRITERS))):
    """§6.4.1 — compile the per-batch Certificate of Quality: consolidate every
    usable iCoA/eCoA result for the batch against the specification, one line
    per spec parameter (the LATEST result wins when a parameter was re-tested;
    Ph. Eur. 3028 derived totals are computed from components, never
    transcribed), each line citing its source certificate + testing lab.
    Aggregation only — no value is invented; a non-conforming line is recorded
    (overall_conform=false), never hidden."""
    _uuid_or_422(body.specification_id, "specification_id")
    _uuid_or_422(body.cultivar_id, "cultivar_id")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT * FROM qc_specifications WHERE id=$1",
                                body.specification_id)
        if spec is None:
            raise HTTPException(422, "Unknown specification")
        # Optional cultivar grade: validate the cultivar, then FREEZE the ladder
        # version APPROVED right now — the printed grade must stay stable and
        # traceable even after the ladder is later superseded. No approved ladder
        # yet → the CoQ carries the cultivar but no grade (never invented).
        potency_spec_id = None
        if body.cultivar_id:
            cv = await c.fetchrow(
                "SELECT id FROM cultivars WHERE id=$1 AND is_active", body.cultivar_id)
            if cv is None:
                raise HTTPException(422, "Unknown or inactive cultivar")
            potency_spec_id = await c.fetchval(
                "SELECT id FROM qc_potency_specs WHERE cultivar_id=$1 AND status='APPROVED'",
                body.cultivar_id)
        certs = await c.fetch(
            "SELECT * FROM qc_certificates WHERE batch_id=$1 AND specification_id=$2"
            " AND cert_type = ANY($3::text[]) AND status = ANY($4::text[])"
            " ORDER BY created_at",
            body.batch_id, body.specification_id,
            list(_COQ_SOURCE_TYPES), list(_COQ_SOURCE_STATUSES))
        if not certs:
            raise HTTPException(
                409, "No usable source certificate (APPROVED/RELEASED iCoA or eCoA)"
                     " exists for this batch and specification (§6.4.2)")
        cert_ids = [c_["id"] for c_ in certs]
        # §6.3.2 — an eCoA source promoted from an ingested document feeds a CoQ
        # only after its QCT 018 review checklist is ACCEPTED. Matched through
        # the WHOLE supersession chain: a revised certificate carries the same
        # transcribed external data as the promoted original it corrects, so a
        # routine revise→release cycle must not slip past the checklist gate.
        bad_docs = await c.fetch(
            """
            WITH RECURSIVE chain AS (
                SELECT id, supersedes_id FROM qc_certificates WHERE id = ANY($1::uuid[])
                UNION ALL
                SELECT p.id, p.supersedes_id FROM qc_certificates p
                JOIN chain ch ON p.id = ch.supersedes_id
            )
            SELECT d.doc_number, cl.outcome FROM qc_coa_documents d
            LEFT JOIN qc_ecoa_checklist cl ON cl.document_id = d.id
            WHERE d.promoted_coa_id IN (SELECT id FROM chain)
              AND (cl.outcome IS NULL OR cl.outcome <> 'ACCEPTED')
            """,
            cert_ids)
        if bad_docs:
            names = ", ".join(f"{d['doc_number']} ({d['outcome'] or 'no checklist'})"
                              for d in bad_docs[:5])
            raise HTTPException(
                409, f"eCoA source(s) lack an ACCEPTED QCT 018 review checklist: {names}"
                     " (QCSOP 012 §6.3.2)")
        params = await c.fetch(
            "SELECT * FROM qc_spec_parameters WHERE spec_id=$1 ORDER BY sorting_order, created_at",
            body.specification_id)
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id = ANY($1::uuid[]) ORDER BY created_at",
            cert_ids)
        open_oos = await c.fetchval(
            "SELECT count(*) FROM qc_oos_records WHERE batch_id=$1 AND status <> 'CLOSED'",
            body.batch_id)
        row = None
        if not open_oos:
            row = await _compile_coq_tx(c, user, body, spec, certs, params, results,
                                        potency_spec_id)
    if open_oos:
        # §6.16 (C8) — an attempted CoQ compile on an open-OOS batch is itself a
        # reportable deviation, recorded in its own transaction so the 409
        # cannot roll the event back.
        async with rls(user) as c2:
            await safe_emit(c2, user, verb="qc_deviation", object_type="qc_specification",
                       object_id=str(spec["id"]), recipients=[],
                       params={"reason": "coq_compile_on_open_oos", "batch_id": body.batch_id,
                               "open_oos": open_oos, "sop": "QCSOP 012 §6.16"})
        raise HTTPException(
            409, f"{open_oos} open OOS investigation(s) on batch {body.batch_id}"
                 " — the CoQ is compiled only on the investigation-confirmed result set"
                 " (QCSOP 012 §6.4.1; attempt recorded as a deviation, §6.16)")
    return _coq_out(dict(row))


async def _compile_coq_tx(c, user: dict, body: CoqIn, spec, certs, params, results,
                          potency_spec_id=None):
    """The aggregation itself — runs INSIDE the caller's transaction, so the
    validation reads, the advisory-locked number mint, and the inserts are one
    atomic unit (no window for a source to be voided or an OOS to open between
    validation and insert)."""
    certs = [dict(x) for x in certs]
    by_cert = {str(x["id"]): x for x in certs}
    # Latest result per spec parameter across ALL source certificates — a
    # re-test supersedes for reporting; the earlier result stays on its own
    # certificate (nothing is deleted). "Latest" is by result_date (the date
    # the measurement was actually available), falling back to entry order.
    latest: dict[str, dict] = {}
    for r in sorted(results, key=lambda x: (x["result_date"] or date.min, x["created_at"])):
        if r["parameter_id"]:
            latest[str(r["parameter_id"])] = dict(r)
    # §6.4.1 — the CoQ is compiled only on the INVESTIGATION-CONFIRMED result
    # set. A failing result superseded by a later passing re-test must not
    # silently vanish from the batch record: EACH masked failure needs its own
    # OOS trail — a CLOSED investigation on this batch raised against that same
    # result, or against that same test.
    masked_fails = [dict(r) for r in results
                    if r["complies"] is False and r["parameter_id"]
                    and latest.get(str(r["parameter_id"]), {}).get("id") != r["id"]]
    if masked_fails:
        # An explicitly cited reference is ALWAYS authenticated, whatever else
        # the batch carries. This check used to sit nested under `if not
        # closed_oos:`, which the caller's own open-OOS gate (compile_coq, just
        # above) made unreachable: it already 409s while ANY non-CLOSED OOS
        # exists, so by the time control arrives here every OOS on the batch is
        # CLOSED — meaning any OOS history at all skipped the authenticity check
        # and a fabricated oos_reference sailed straight through.
        if body.oos_reference:
            cited = await c.fetchval(
                "SELECT 1 FROM qc_oos_records WHERE org_id=$1 AND batch_id=$2"
                " AND oos_number=$3 AND status='CLOSED'",
                user["org_id"], body.batch_id, body.oos_reference)
            if not cited:
                raise HTTPException(
                    409, f"oos_reference '{body.oos_reference}' does not match a CLOSED OOS"
                         " record on this batch — cite an existing closed investigation's"
                         " OOS number, or close the investigation (QCSOP 012 §6.4.1)")
        # Cover is per-PARAMETER, not per-batch. Batch scope was too loose: a
        # closed microbial investigation would otherwise silently license
        # dropping a masked potency failure, because the old counter asked only
        # "does this batch have ANY closed OOS?". An OOS carries result_id
        # (exact result it was raised on) and/or test_name; either binds it.
        oos_rows = await c.fetch(
            "SELECT result_id, test_name FROM qc_oos_records"
            " WHERE org_id=$1 AND batch_id=$2 AND status='CLOSED'",
            user["org_id"], body.batch_id)
        covered_ids = {str(o["result_id"]) for o in oos_rows if o["result_id"]}
        covered_tests = {_norm_test(o["test_name"]) for o in oos_rows if o["test_name"]}
        uncovered = sorted({r["test_name"] for r in masked_fails
                            if str(r["id"]) not in covered_ids
                            and _norm_test(r["test_name"]) not in covered_tests})
        if uncovered:
            raise HTTPException(
                409, f"{len(uncovered)} test(s) ({', '.join(uncovered[:5])}) had a failing result"
                     " superseded by a re-test with no closed OOS investigation naming that same"
                     " test — the CoQ compiles only the investigation-confirmed result set"
                     " (QCSOP 012 §6.4.1; close an OOS against that test, or cite one via"
                     " oos_reference)")
    lines, cited_cert_ids, missing = [], set(), []
    for i, p in enumerate(params):
        pid = str(p["id"])
        crit = _coq_criterion(
            float(p["lower_limit"]) if p["lower_limit"] is not None else None,
            float(p["upper_limit"]) if p["upper_limit"] is not None else None,
            p["unit"])
        if p["computed_kind"]:
            # Ph. Eur. 3028 derived total — computed here from the latest
            # component results (total = neutral + 0.877 × acid).
            ra = latest.get(str(p["component_a_id"])) if p["component_a_id"] else None
            rb = latest.get(str(p["component_b_id"])) if p["component_b_id"] else None
            if not (ra and rb and ra["result_numeric"] is not None
                    and rb["result_numeric"] is not None):
                missing.append(p["test_name_en"] or p["test_name_mk"] or "?")
                continue
            check_derived_total_units(dict(p), ra, rb)
            val = round(float(ra["result_numeric"]) + _ACID_FACTOR * float(rb["result_numeric"]), 2)
            lo = float(p["lower_limit"]) if p["lower_limit"] is not None else None
            hi = float(p["upper_limit"]) if p["upper_limit"] is not None else None
            complies, _st = _evaluate(val, lo, hi)
            for comp in (ra, rb):
                cited_cert_ids.add(str(comp["coa_id"]))
            lines.append({
                "parameter_id": p["id"],
                "parameter_name": p["test_name_en"] or p["test_name_mk"] or "?",
                "test_method": p["test_method"] or p["pharmacopoeia_ref"],
                "acceptance_criterion": crit, "result_value": None,
                "result_numeric": val, "unit": p["unit"], "complies": complies,
                "testing_lab": None, "source_coa_id": None,
                "source_coa_number": "Computed — Ph. Eur. 3028", "sorting_order": i,
            })
            continue
        r = latest.get(pid)
        if r is None:
            missing.append(p["test_name_en"] or p["test_name_mk"] or "?")
            continue
        src = by_cert.get(str(r["coa_id"])) or {}
        cited_cert_ids.add(str(r["coa_id"]))
        lines.append({
            "parameter_id": p["id"],
            "parameter_name": p["test_name_en"] or p["test_name_mk"] or "?",
            "test_method": p["test_method"] or p["pharmacopoeia_ref"],
            "acceptance_criterion": crit, "result_value": r["result_value"],
            "result_numeric": float(r["result_numeric"]) if r["result_numeric"] is not None else None,
            "unit": r["unit"] or p["unit"], "complies": r["complies"],
            "testing_lab": r["source_institution"] or src.get("source_lab"),
            "source_coa_id": r["coa_id"], "source_coa_number": src.get("coa_number"),
            "sorting_order": i,
        })
    if missing:
        names = ", ".join(missing[:5])
        raise HTTPException(
            409, f"{len(missing)} specification parameter(s) have no result ({names}"
                 f"{'…' if len(missing) > 5 else ''}) — the batch is not fully"
                 " tested, the CoQ cannot be compiled (§6.4.1)")
    if not lines:
        # GxP: an empty results table must never yield a vacuous conformance
        # assertion — there is literally nothing to certify.
        raise HTTPException(409, "the specification has no parameters — nothing to certify")
    # Overall conformance: asserted only when every line complies; a single
    # FAIL makes it false; an unknown (unmeasured verdict) stays null.
    verdicts = [ln["complies"] for ln in lines]
    if any(v is False for v in verdicts):
        overall = False
    elif all(v is True for v in verdicts):
        overall = True
    else:
        overall = None
    spec_ref = spec["spec_id"] or ""
    if spec["version"]:
        spec_ref = f"{spec_ref} · v{spec['version']}".strip(" ·")
    coq_number = await _mint_cert_number(c, user["org_id"], "COQ")
    row = await c.fetchrow(
        "INSERT INTO qc_coq(org_id, coq_number, batch_id, product_name, manufacture_date,"
        " batch_size, specification_id, spec_reference, overall_conform, comments,"
        " oos_reference, compiled_by, compiled_at, created_by, updated_by,"
        " cultivar_id, potency_spec_id)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,now(),$12,$12,$13,$14) RETURNING *",
        user["org_id"], coq_number, body.batch_id, body.product_name,
        body.manufacture_date, body.batch_size, body.specification_id, spec_ref,
        overall, body.comments, body.oos_reference, user["id"],
        body.cultivar_id, potency_spec_id)
    for src_id in sorted(cited_cert_ids):
        src = by_cert[src_id]
        await c.execute(
            "INSERT INTO qc_coq_sources(org_id, coq_id, coa_id, coa_number, cert_type,"
            " issue_date) VALUES ($1,$2,$3,$4,$5,$6)",
            user["org_id"], row["id"], src["id"], src["coa_number"], src["cert_type"],
            src["report_date"])
    for ln in lines:
        await c.execute(
            "INSERT INTO qc_coq_lines(org_id, coq_id, parameter_id, parameter_name,"
            " test_method, acceptance_criterion, result_value, result_numeric, unit,"
            " complies, testing_lab, source_coa_id, source_coa_number, sorting_order)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
            user["org_id"], row["id"], ln["parameter_id"], ln["parameter_name"],
            ln["test_method"], ln["acceptance_criterion"], ln["result_value"],
            ln["result_numeric"], ln["unit"], ln["complies"], ln["testing_lab"],
            ln["source_coa_id"], ln["source_coa_number"], ln["sorting_order"])
    await safe_emit(c, user, verb="coq_compiled", object_type="qc_coq",
               object_id=str(row["id"]), recipients=[],
               params={"coq_number": coq_number, "batch_id": body.batch_id,
                       "overall_conform": overall, "sources": len(cited_cert_ids)})
    return row


@router.post("/coq/{coq_id}/review")
async def review_coq(coq_id: str, user: dict = Depends(require_role(*_COQ_ROLES))):
    # M2 (URS §3 / QCSOP-012 C5): the CoQ is approved by the Head of QC and carries
    # NO QP signature — the QP receives it. The issuing gate already excludes QP
    # (_COQ_ROLES on render_coq); the approval-of-record here must match, so it is
    # gated on _COQ_ROLES (ADMIN, QC_MGR), not _HOQC (which still admits QP).
    """§6.4.3 — the Head of QC reviews and approves the compiled CoQ. Second
    person: the reviewer must not be the compiler. No QP signature — the
    approved CoQ is an input TO the QP batch-release decision."""
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        cur = await c.fetchrow(
            "SELECT status, compiled_by, batch_id, specification_id FROM qc_coq WHERE id=$1",
            coq_id)
        if cur is None:
            raise HTTPException(404, "CoQ not found")
        if cur["status"] != "DRAFT":
            raise HTTPException(409, f"a {cur['status']} CoQ cannot be approved")
        if cur["compiled_by"] and str(cur["compiled_by"]) == str(user["id"]):
            raise HTTPException(403, "the CoQ is reviewed by a second person —"
                                     " the compiler cannot approve their own compilation (§6.4.3)")
        # one live APPROVED CoQ per (batch, spec) — two divergent approved
        # aggregations would hand the QP conflicting release inputs (a partial
        # unique index in mig 0041 backs this at the DB level).
        dup = await c.fetchval(
            "SELECT coq_number FROM qc_coq WHERE batch_id=$1 AND specification_id=$2"
            " AND status='APPROVED' AND id <> $3 LIMIT 1",
            cur["batch_id"], cur["specification_id"], coq_id)
        if dup:
            raise HTTPException(409, f"an APPROVED CoQ ({dup}) already exists for this batch"
                                     " and specification — void it before approving another")
        # §6.4.1 — the OOS state can change between compile and approval; the
        # HoQC signature must not land on a batch under open investigation.
        open_oos = await c.fetchval(
            "SELECT count(*) FROM qc_oos_records WHERE batch_id=$1 AND status <> 'CLOSED'",
            cur["batch_id"])
        row = None
        if not open_oos:
            row = await c.fetchrow(
                "UPDATE qc_coq SET status='APPROVED', reviewed_by=$1, reviewed_at=now(),"
                " updated_by=$1, updated_at=now() WHERE id=$2 RETURNING *", user["id"], coq_id)
            await safe_emit(c, user, verb="coq_reviewed", object_type="qc_coq",
                       object_id=coq_id, recipients=[],
                       params={"coq_number": row["coq_number"]})
    if open_oos:
        # §6.16 (C8) — recorded in its own transaction so the 409 cannot roll
        # the deviation event back.
        async with rls(user) as c2:
            await safe_emit(c2, user, verb="qc_deviation", object_type="qc_coq",
                       object_id=coq_id, recipients=[],
                       params={"reason": "coq_approve_on_open_oos", "batch_id": cur["batch_id"],
                               "open_oos": open_oos, "sop": "QCSOP 012 §6.16"})
        raise HTTPException(
            409, f"{open_oos} open OOS investigation(s) on batch {cur['batch_id']}"
                 " — the CoQ cannot be approved until the investigation is closed"
                 " (QCSOP 012 §6.4.1; attempt recorded as a deviation, §6.16)")
    return _coq_out(dict(row))


@router.post("/coq/{coq_id}/void")
async def void_coq(coq_id: str, body: VoidIn, user: dict = Depends(require_role(*_HOQC))):
    """§6.6 — void a fundamentally-invalid CoQ (wrong batch / wrong sources).
    Head-of-QC act, written reason mandatory; the record is retained, never
    deleted (GxP)."""
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_coq WHERE id=$1", coq_id)
        if cur is None:
            raise HTTPException(404, "CoQ not found")
        if cur["status"] not in _COQ_VOIDABLE:
            raise HTTPException(409, f"a {cur['status']} CoQ cannot be voided")
        row = await c.fetchrow(
            "UPDATE qc_coq SET status='VOIDED', void_reason=$1, voided_by=$2, voided_at=now(),"
            " updated_by=$2, updated_at=now() WHERE id=$3 RETURNING *",
            body.reason.strip(), user["id"], coq_id)
        await safe_emit(c, user, verb="coq_voided", object_type="qc_coq",
                   object_id=coq_id, recipients=[],
                   params={"coq_number": row["coq_number"], "reason": body.reason.strip()})
    return _coq_out(dict(row))


@router.post("/coq/{coq_id}/render", status_code=201)
async def render_coq(coq_id: str, user: dict = Depends(require_role(*_COQ_ROLES))):
    """Render the APPROVED aggregation CoQ to the bilingual house-style .docx
    via the DocEngine (same PASS-gated pipeline as the single-certificate CoQ).
    A printable Certificate of Quality asserts conformance — it is issued only
    for a conforming batch (overall_conform=true); a non-conforming CoQ stays
    an in-app record for the QP (GxP: never render a conformant certificate
    over failing data)."""
    _uuid_or_404(coq_id, "CoQ")
    async with rls(user) as c:
        coq = await c.fetchrow("SELECT * FROM qc_coq WHERE id=$1", coq_id)
        if coq is None:
            raise HTTPException(404, "CoQ not found")
        if coq["status"] != "APPROVED":
            raise HTTPException(409, "the CoQ document is rendered only from an APPROVED CoQ")
        if coq["overall_conform"] is not True:
            raise HTTPException(
                409, "the batch does not conform (or conformance is undetermined) —"
                     " a Certificate of Quality asserting conformance cannot be issued")
        # §6.4.1 — re-check at ISSUANCE time: an OOS opened after compile/
        # approval must block the printable conformance document.
        open_oos = await c.fetchval(
            "SELECT count(*) FROM qc_oos_records WHERE batch_id=$1 AND status <> 'CLOSED'",
            coq["batch_id"])
        spec = await c.fetchrow("SELECT * FROM qc_specifications WHERE id=$1",
                                coq["specification_id"])
        params = await c.fetch(
            "SELECT * FROM qc_spec_parameters WHERE spec_id=$1", coq["specification_id"])
        lines = await c.fetch(
            "SELECT * FROM qc_coq_lines WHERE coq_id=$1 ORDER BY sorting_order, created_at",
            coq_id)
        # Ordered by real dates (not the coa_number string — per-type/per-year
        # numbering means lexical order doesn't reliably track issuance order),
        # oldest first so the fallback pick below still means "the newest one".
        sources = await c.fetch(
            "SELECT * FROM qc_coq_sources WHERE coq_id=$1"
            " ORDER BY issue_date NULLS FIRST, created_at", coq_id)
        # primary source certificate — richest identity metadata for the meta
        # grid (prefer the in-house iCoA; fall back to the newest source).
        primary = None
        src_rows = [dict(s) for s in sources]
        if src_rows:
            pick = next((s for s in src_rows if s["cert_type"] == "ICOA"), src_rows[-1])
            primary = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1",
                                       pick["coa_id"])
        # ISO 17025 scope advisory (parity with the single-certificate CoQ, URS
        # Ch. 7): an aggregation CoQ draws each line from a DIFFERENT source
        # certificate — hence a different testing lab — so scope is judged PER
        # SOURCE: each line's method against ITS OWN lab's accredited scope.
        # Advisory only (a footnote), never an OOS, never blocking; a lab that
        # declares no scope is unjudgeable and flags nothing.
        scope_by_source: dict = {}
        src_coa_ids = list({ln["source_coa_id"] for ln in lines if ln["source_coa_id"]})
        if src_coa_ids:
            lab_of = {r["id"]: r["laboratory_id"] for r in await c.fetch(
                "SELECT id, laboratory_id FROM qc_certificates WHERE id = ANY($1)", src_coa_ids)}
            lab_ids = list({v for v in lab_of.values() if v})
            scope_by_lab = {}
            if lab_ids:
                for lr in await c.fetch(
                        "SELECT id, iso17025_scope FROM qc_laboratories WHERE id = ANY($1)", lab_ids):
                    scope_by_lab[lr["id"]] = _lab_scope_set(lr["iso17025_scope"])
            scope_by_source = {cid: scope_by_lab.get(lab_of.get(cid), set()) for cid in src_coa_ids}
    if open_oos:
        # §6.16 (C8) — recorded in its own transaction, before the 409.
        async with rls(user) as c2:
            await safe_emit(c2, user, verb="qc_deviation", object_type="qc_coq",
                       object_id=coq_id, recipients=[],
                       params={"reason": "coq_render_on_open_oos", "batch_id": coq["batch_id"],
                               "open_oos": open_oos, "sop": "QCSOP 012 §6.16"})
        raise HTTPException(
            409, f"{open_oos} open OOS investigation(s) on batch {coq['batch_id']}"
                 " — the CoQ document cannot be issued until the investigation is closed"
                 " (QCSOP 012 §6.4.1; attempt recorded as a deviation, §6.16)")
    params_by_id = {str(p["id"]): dict(p) for p in params}
    issue_by_number = {s["coa_number"]: s["issue_date"] for s in src_rows}
    primary = dict(primary) if primary else {}
    # Synthesize the renderer's certificate dict: CoQ identity + the primary
    # source's product metadata. Unknown fields stay absent — never invented.
    coa_view = {
        "coa_number": coq["coq_number"], "cert_type": "COQ", "decision": "PASS",
        # the CoQ's authorised approver is the HoQC who reviewed/approved it
        # (§6.4.3) — the mandatory-content manifest requires an approver of record.
        "approver_id": coq["reviewed_by"],
        "batch_id": coq["batch_id"],
        "manufacture_date": coq["manufacture_date"] or primary.get("manufacture_date"),
        "report_date": coq["compiled_at"].date() if coq["compiled_at"] else None,
        "botanical_type": primary.get("botanical_type"), "chemotype": primary.get("chemotype"),
        "cultivation_batch": primary.get("cultivation_batch"),
        "product_code": primary.get("product_code") or coq["product_name"],
        "packaging": primary.get("packaging"), "packaging_date": primary.get("packaging_date"),
        "expiry_date": primary.get("expiry_date"), "retest_date": primary.get("retest_date"),
        "source_lab": None,
    }
    results, out_of_scope = [], []
    for ln in lines:
        p = params_by_id.get(str(ln["parameter_id"])) if ln["parameter_id"] else {}
        p = p or {}
        results.append({
            "parameter_id": ln["parameter_id"], "test_name": ln["parameter_name"],
            "result_value": ln["result_value"],
            "result_numeric": float(ln["result_numeric"]) if ln["result_numeric"] is not None else None,
            "unit": ln["unit"],
            "lower_limit": float(p["lower_limit"]) if p.get("lower_limit") is not None else None,
            "upper_limit": float(p["upper_limit"]) if p.get("upper_limit") is not None else None,
            "complies": ln["complies"],
            "source_document_code": ln["source_coa_number"],
            "source_document_date": issue_by_number.get(ln["source_coa_number"]),
            "source_institution": ln["testing_lab"],
        })
        # scope check against THIS line's own source lab (the line records its
        # own test_method; fall back to the spec parameter's method).
        scope = scope_by_source.get(ln["source_coa_id"], set())
        if scope and not _result_in_scope(scope, ln["test_method"] or p.get("test_method"),
                                          ln["parameter_name"]):
            nm = ln["parameter_name"] or "?"
            if nm not in out_of_scope:
                out_of_scope.append(nm)
    # signature block — the CoQ's own two QC signatures (§6.4.3): compiled by /
    # reviewed+approved by HoQC. Names live in the users DB.
    signer_names = {}
    _role_ids = {"analyst": coq["compiled_by"], "reviewer": coq["reviewed_by"]}
    _uids = [str(v) for v in _role_ids.values() if v]
    if _uids:
        prows = await users_admin_pool().fetch(
            # org-scope the BYPASSRLS lookup (see coq_docx): a name from another org
            # must never be resolvable even if a cross-org id slipped in.
            "SELECT id, full_name FROM profiles WHERE id = ANY($1::uuid[]) AND org_id=$2"
            " AND is_deleted=false",
            _uids, user["org_id"])
        _by_id = {str(p["id"]): p["full_name"] for p in prows}
        signer_names = {k: _by_id.get(str(v)) for k, v in _role_ids.items()
                        if v and _by_id.get(str(v))}
    # WHO TRS 1010 / Annex 16 §9.3 mandatory-CONTENT gate (parity with the
    # single-certificate CoQ): never render a certificate missing a required
    # element. cert_type is COQ, so the single-testing-lab element is not
    # required here — the §02 crossref derives each line's lab from its own
    # source certificate instead.
    manifest_missing = _coq_manifest(coa_view, dict(spec) if spec else {},
                                     params_by_id, results, None)
    if manifest_missing:
        raise HTTPException(
            409, "Certificate is missing WHO/Annex-16 mandatory content: "
                 + "; ".join(manifest_missing))
    scope_note = None
    if out_of_scope:
        names = ", ".join(out_of_scope[:5])
        scope_note = (f"Тестови надвор од ISO 17025 опсегот на лабораторијата: {names}"
                      f"|||Tests outside the laboratory's ISO 17025 scope: {names}")
    md = _coq_markdown(coa_view, dict(spec) if spec else {}, params_by_id, results,
                       lab=None, scope_note=scope_note, sigs=None, signer_names=signer_names)
    build = (await docengine.de_forward(
        "POST", "/build",
        {"markdown": md, "out_name": coq["coq_number"],
         "meta": {"code": coq["coq_number"], "title_mk": "Сертификат за квалитет",
                  "title_en": "Certificate of Quality", "version": "01"}},
        timeout=120.0, client_factory=_coq_client)).json()
    doc_id = build.get("document_id")
    async with rls(user) as c:
        # Re-assert APPROVED when stamping — the CoQ could have been voided
        # during the (up-to-120s) DocEngine build (TOCTOU).
        stamped = await c.fetchrow(
            "UPDATE qc_coq SET coq_document_id=$1, coq_generated_at=now(),"
            " updated_by=$2, updated_at=now() WHERE id=$3 AND status='APPROVED' RETURNING id",
            doc_id, user["id"], coq_id)
        if stamped is None:
            raise HTTPException(409, "CoQ is no longer APPROVED — document not recorded")
        await safe_emit(c, user, verb="coq_rendered", object_type="qc_coq",
                   object_id=coq_id, recipients=[],
                   params={"coq_number": coq["coq_number"], "document_id": doc_id})
    return {"coq_number": coq["coq_number"], "document_id": doc_id,
            "verify": build.get("verify"), "bytes": build.get("bytes"),
            "out_of_scope": out_of_scope}
