from app.db import rls
from app.deps import require_role
from app.notify import safe_emit
from app.roles import ELEVATED_ROLES
from datetime import date
from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel, Field
from urllib.parse import quote as _urlquote
import base64
import hashlib

from .certificates import _mint_cert_number
from .common import _HOQC, _WRITERS, _evaluate, _lab_verdict_bool, _uuid_or_404, _uuid_or_422, router
from .laboratories import _resolve_lab


_DOC_STATUSES = ("UPLOADED", "EXTRACTED", "REVIEWED", "PROMOTED", "REJECTED")


_PLACEHOLDER_STATUSES = ("OPEN", "MAPPED", "IGNORED")


_DOC_TRANSITIONS = {
    "UPLOADED": {"EXTRACTED", "REJECTED"},
    "EXTRACTED": {"REVIEWED", "REJECTED"},
    "REVIEWED": {"PROMOTED", "REJECTED"},
    "PROMOTED": set(),
    "REJECTED": set(),
}


def _norm_label(s: str | None) -> str:
    """Canonical form of a field label for cross-document matching / dedup:
    whitespace-collapsed, lowercased. Deliberately conservative — a human maps
    anything this doesn't catch, we never fuzzy-guess a GMP field."""
    return " ".join((s or "").split()).lower()


class CoaDocIn(BaseModel):
    batch_id: str = Field(max_length=200)
    source_institution: str | None = Field(default=None, max_length=200)
    laboratory_id: str | None = None
    material_code: str | None = Field(default=None, max_length=120)
    specification_id: str | None = None
    sample_id: str | None = None
    original_filename: str | None = Field(default=None, max_length=400)
    mime_type: str | None = Field(default=None, max_length=120)
    storage_ref: str | None = Field(default=None, max_length=1000)
    page_count: int | None = None
    report_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CoaDocPatch(BaseModel):
    source_institution: str | None = Field(default=None, max_length=200)
    laboratory_id: str | None = None
    material_code: str | None = Field(default=None, max_length=120)
    specification_id: str | None = None
    sample_id: str | None = None
    report_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    status: str | None = None            # guarded lifecycle transition


class ExtractionIn(BaseModel):
    raw_label: str = Field(max_length=400)
    raw_value: str | None = Field(default=None, max_length=400)
    numeric_value: float | None = None
    unit: str | None = Field(default=None, max_length=60)
    confidence: float | None = None
    source_page: int | None = None
    # The lab's own stated verdict, verbatim as printed on the eCoA
    # ("Pass", "Conforms", "Does not comply", …). Reference-only per QCSOP 012
    # §6.3.2 — conformance of record is always computed in-house.
    lab_verdict: str | None = Field(default=None, max_length=60)


class ExtractionsIn(BaseModel):
    # Cap the batch so one request can't drive an unbounded INSERT loop inside a
    # single transaction (holds a connection open); a real CoA has far fewer rows.
    items: list[ExtractionIn] = Field(max_length=500)


class ExtractionPatch(BaseModel):
    parameter_id: str | None = None
    numeric_value: float | None = None
    unit: str | None = Field(default=None, max_length=60)
    test_name: str | None = Field(default=None, max_length=300)
    lab_verdict: str | None = Field(default=None, max_length=60)


class PlaceholderPatch(BaseModel):
    status: str | None = None                     # MAPPED | IGNORED
    mapped_parameter_id: str | None = None
    suggested_test_name: str | None = Field(default=None, max_length=300)


def _ecoa_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "doc_number": r["doc_number"], "batch_id": r["batch_id"],
        "source_institution": r["source_institution"],
        "laboratory_id": str(r["laboratory_id"]) if r.get("laboratory_id") else None,
        "material_code": r["material_code"],
        "specification_id": str(r["specification_id"]) if r["specification_id"] else None,
        "sample_id": str(r["sample_id"]) if r["sample_id"] else None,
        "original_filename": r["original_filename"], "mime_type": r["mime_type"],
        "storage_ref": r["storage_ref"], "page_count": r["page_count"],
        "report_date": r["report_date"].isoformat() if r["report_date"] else None,
        "status": r["status"],
        "promoted_coa_id": str(r["promoted_coa_id"]) if r["promoted_coa_id"] else None,
        # §6.3.1 review clock
        "review_deadline": r["review_deadline"].isoformat() if r.get("review_deadline") else None,
        "reviewed_at": r["reviewed_at"].isoformat() if r.get("reviewed_at") else None,
        "review_window_met": r.get("review_window_met"),
        # overdue = still awaiting review AND the deadline has passed (computed)
        "review_overdue": bool(
            r.get("review_deadline") and r.get("review_window_met") is None
            and r["status"] in ("UPLOADED", "EXTRACTED")
            and r["review_deadline"] < date.today()),
        "notes": r["notes"],
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    }


def _extract_out(r: dict) -> dict:
    lab = _lab_verdict_bool(r.get("lab_verdict"))
    return {
        "id": str(r["id"]), "document_id": str(r["document_id"]), "raw_label": r["raw_label"],
        "raw_value": r["raw_value"], "numeric_value": r["numeric_value"], "unit": r["unit"],
        "parameter_id": str(r["parameter_id"]) if r["parameter_id"] else None,
        "test_name": r["test_name"], "lower_limit": r["lower_limit"], "upper_limit": r["upper_limit"],
        "complies": r["complies"], "grade_status": r["grade_status"],
        "confidence": r["confidence"], "source_page": r["source_page"],
        "lab_verdict": r.get("lab_verdict"),
        # True only when BOTH sides state a verdict and they disagree — the
        # QCSOP 012 §6.3.2 reconciliation surfaced instead of silently dropped.
        "lab_verdict_mismatch": (lab is not None and r["complies"] is not None
                                 and lab != r["complies"]),
    }


def _placeholder_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "raw_label": r["raw_label"], "normalized_label": r["normalized_label"],
        "occurrences": r["occurrences"], "suggested_test_name": r["suggested_test_name"],
        "mapped_parameter_id": str(r["mapped_parameter_id"]) if r["mapped_parameter_id"] else None,
        "status": r["status"],
        "first_seen_document_id": str(r["first_seen_document_id"]) if r["first_seen_document_id"] else None,
    }


@router.get("/coa-documents")
async def list_coa_documents(status: str | None = None, batch_id: str | None = None,
                             user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    if batch_id:
        args.append(batch_id); clauses.append(f"batch_id=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            f"SELECT * FROM qc_coa_documents{where} ORDER BY created_at DESC", *args)
    return [_ecoa_out(dict(r)) for r in rows]


@router.get("/coa-documents/{doc_id}")
async def get_coa_document(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(doc_id, "eCoA document")
    async with rls(user) as c:
        doc = await c.fetchrow("SELECT * FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "eCoA document not found")
        rows = await c.fetch(
            "SELECT * FROM qc_coa_extractions WHERE document_id=$1 ORDER BY created_at", doc_id)
        files = await c.fetch(
            "SELECT id, org_id, object_type, object_id, filename, content_type, size_bytes,"
            " sha256, uploaded_by, uploaded_at FROM qc_document_files"
            " WHERE object_type='qc_coa_document' AND object_id=$1 ORDER BY uploaded_at", doc_id)
    return {"document": _ecoa_out(dict(doc)),
            "extractions": [_extract_out(dict(r)) for r in rows],
            "originals": [_file_out(dict(f)) for f in files]}


_MAX_FILE_BYTES = 20 * 1024 * 1024   # 20 MB decoded — a scanned CoA fits easily


_MAX_B64_LEN = 4 * ((_MAX_FILE_BYTES + 2) // 3) + 4


class FileUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    content_type: str | None = Field(default=None, max_length=120)
    content_b64: str = Field(min_length=1, max_length=_MAX_B64_LEN)


def _file_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "object_type": r["object_type"], "object_id": str(r["object_id"]),
        "filename": r["filename"], "content_type": r["content_type"],
        "size_bytes": r["size_bytes"], "sha256": r["sha256"],
        "uploaded_by": str(r["uploaded_by"]) if r["uploaded_by"] else None,
        "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
    }


@router.post("/coa-documents/{doc_id}/originals", status_code=201)
async def upload_coa_original(doc_id: str, body: FileUploadIn,
                             user: dict = Depends(require_role(*_WRITERS))):
    """Store the ORIGINAL source document (the supplier eCoA PDF) alongside the
    transcribed record with a server-computed SHA-256 (ALCOA+ 'Original'). The
    file is written once and never mutated; its digest is recorded in the global
    audit chain via emit(), so a later re-hash on download detects tampering."""
    _uuid_or_404(doc_id, "eCoA document")
    try:
        raw = base64.b64decode(body.content_b64, validate=True)
    except Exception:
        raise HTTPException(422, "content_b64 is not valid base64")
    if not raw:
        raise HTTPException(422, "The uploaded file is empty")
    if len(raw) > _MAX_FILE_BYTES:
        raise HTTPException(413, f"File exceeds the {_MAX_FILE_BYTES // (1024 * 1024)} MB limit")
    digest = hashlib.sha256(raw).hexdigest()
    async with rls(user) as c:
        doc = await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "eCoA document not found")
        row = await c.fetchrow(
            "INSERT INTO qc_document_files(org_id, object_type, object_id, filename,"
            " content_type, size_bytes, sha256, content, uploaded_by)"
            " VALUES ($1,'qc_coa_document',$2,$3,$4,$5,$6,$7,$8)"
            " RETURNING id, org_id, object_type, object_id, filename, content_type,"
            "           size_bytes, sha256, uploaded_by, uploaded_at",
            user["org_id"], doc_id, body.filename, body.content_type, len(raw), digest,
            raw, user["id"])
        await safe_emit(c, user, verb="coa_original_stored", object_type="qc_coa_document",
                   object_id=doc_id, recipients=[],
                   params={"filename": body.filename, "sha256": digest, "size": len(raw)})
    return _file_out(dict(row))


@router.get("/coa-documents/{doc_id}/originals")
async def list_coa_originals(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(doc_id, "eCoA document")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT id, org_id, object_type, object_id, filename, content_type, size_bytes,"
            " sha256, uploaded_by, uploaded_at FROM qc_document_files"
            " WHERE object_type='qc_coa_document' AND object_id=$1 ORDER BY uploaded_at", doc_id)
    return [_file_out(dict(r)) for r in rows]


@router.get("/document-files/{file_id}/download")
async def download_document_file(file_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Return the stored original bytes. Re-hashes on the way out and reports the
    integrity verdict in an `X-Integrity` header (OK / MISMATCH) — a MISMATCH
    means the stored bytes no longer match the SHA-256 recorded at upload."""
    _uuid_or_404(file_id, "Document file")
    async with rls(user) as c:
        row = await c.fetchrow(
            "SELECT filename, content_type, sha256, content FROM qc_document_files WHERE id=$1",
            file_id)
    if row is None:
        raise HTTPException(404, "Document file not found")
    data = bytes(row["content"])
    integrity = "OK" if hashlib.sha256(data).hexdigest() == row["sha256"] else "MISMATCH"
    raw_name = (row["filename"] or "download").replace('"', "").replace("\\", "").replace("\n", "")
    # M8: Starlette latin-1-encodes header values, so a Cyrillic filename (routine
    # here) in a bare filename="…" raises UnicodeEncodeError → 500. Emit an RFC-5987
    # filename*=UTF-8'' value for the real name plus an ASCII-only fallback for old
    # clients (non-latin-1 chars in the fallback are dropped, never crash).
    ascii_name = raw_name.encode("ascii", "ignore").decode("ascii") or "download"
    disposition = (f"attachment; filename=\"{ascii_name}\"; "
                   f"filename*=UTF-8''{_urlquote(raw_name)}")
    return Response(
        content=data, media_type=row["content_type"] or "application/octet-stream",
        headers={"Content-Disposition": disposition,
                 "X-Integrity": integrity, "X-Content-SHA256": row["sha256"]})


@router.post("/coa-documents", status_code=201)
async def create_coa_document(body: CoaDocIn, user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_422(body.specification_id, "specification_id")
    _uuid_or_422(body.sample_id, "sample_id")
    _uuid_or_422(body.laboratory_id, "laboratory_id")
    async with rls(user) as c:
        if body.specification_id:
            if await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1", body.specification_id) is None:
                raise HTTPException(422, "Unknown specification")
        if body.sample_id:
            if await c.fetchrow("SELECT id FROM qc_samples WHERE id=$1", body.sample_id) is None:
                raise HTTPException(422, "Unknown sample")
        await _resolve_lab(c, user["org_id"], body.laboratory_id)
        row = await c.fetchrow(
            "INSERT INTO qc_coa_documents(org_id, doc_number, source_institution, laboratory_id,"
            " batch_id, material_code, specification_id, sample_id, original_filename, mime_type,"
            " storage_ref, page_count, report_date, notes, review_deadline, uploaded_by,"
            " created_by, updated_by)"
            " VALUES ($1, 'PP-ECOA-' || to_char(now(),'YYYY') || '-' ||"
            "         lpad(nextval('qc_ecoa_id_seq')::text, 4, '0'),"
            "         $2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::date,$13,"
            # QCSOP 012 §6.3.1: 5 working days to review. From any weekday that
            # is exactly 7 calendar days (5 business days always cross one
            # weekend); a weekend registration rolls to Monday first (lenient —
            # the clock never starts on a non-working day).
            "         (CURRENT_DATE + CASE extract(isodow FROM CURRENT_DATE)::int"
            "            WHEN 6 THEN 2 WHEN 7 THEN 1 ELSE 0 END + 7)::date,"
            "         $14,$14,$14) RETURNING *",
            user["org_id"], body.source_institution, body.laboratory_id, body.batch_id,
            body.material_code, body.specification_id, body.sample_id, body.original_filename,
            body.mime_type, body.storage_ref, body.page_count, body.report_date, body.notes,
            user["id"])
    return _ecoa_out(dict(row))


@router.patch("/coa-documents/{doc_id}")
async def update_coa_document(doc_id: str, body: CoaDocPatch,
                              user: dict = Depends(require_role(*_WRITERS))):
    _uuid_or_404(doc_id, "eCoA document")
    patch = body.model_dump(exclude_unset=True)
    _uuid_or_422(patch.get("specification_id"), "specification_id")
    _uuid_or_422(patch.get("sample_id"), "sample_id")
    _uuid_or_422(patch.get("laboratory_id"), "laboratory_id")
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_coa_documents WHERE id=$1", doc_id)
        if cur is None:
            raise HTTPException(404, "eCoA document not found")
        if patch.get("laboratory_id") is not None:
            await _resolve_lab(c, user["org_id"], patch["laboratory_id"])
        if cur["status"] in ("PROMOTED", "REJECTED"):
            # A promoted document is the source-of-record for a minted
            # certificate — rebinding its spec/sample/metadata afterwards would
            # break the provenance the verify loop reconciles against.
            raise HTTPException(409, f"Document is {cur['status']} — locked")
        review_stamp = False
        if "status" in patch and patch["status"] is not None and patch["status"] != cur["status"]:
            target = patch["status"]
            if target not in _DOC_STATUSES:
                raise HTTPException(422, "Unknown status")
            # PROMOTED is reached only via the promote endpoint (it must mint a
            # certificate) — never by a bare status PATCH.
            if target == "PROMOTED":
                raise HTTPException(409, "Use POST /coa-documents/{id}/promote to promote")
            if target not in _DOC_TRANSITIONS.get(cur["status"], set()):
                raise HTTPException(409, f"Illegal transition {cur['status']} -> {target}")
            review_stamp = (target == "REVIEWED")
        if body.specification_id:
            if await c.fetchrow("SELECT id FROM qc_specifications WHERE id=$1", body.specification_id) is None:
                raise HTTPException(422, "Unknown specification")
        fields, args = [], []
        _NULLABLE = {"source_institution", "laboratory_id", "material_code", "specification_id",
                     "sample_id", "report_date", "notes"}
        for col, val in patch.items():
            if val is None and col not in _NULLABLE:
                continue
            if col == "report_date":
                args.append(val); fields.append(f"{col}=${len(args)}::date")
            else:
                args.append(val); fields.append(f"{col}=${len(args)}")
        # §6.3.1: stamp the review timestamp + whether it landed inside the
        # 5-working-day window (met iff reviewed on/before the deadline).
        if review_stamp:
            fields.append("reviewed_at=now()")
            fields.append("review_window_met=(CURRENT_DATE <= review_deadline)")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(doc_id)
        row = await c.fetchrow(
            f"UPDATE qc_coa_documents SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
    return _ecoa_out(dict(row))


_CHECKLIST_OUTCOMES = ("PENDING", "ACCEPTED", "REJECTED")


class ChecklistIn(BaseModel):
    sample_id_match: bool | None = None
    method_per_tqa: bool | None = None
    units_per_spec: bool | None = None
    conformance_by_pp: bool | None = None
    discrepancies: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)


class ChecklistDecision(BaseModel):
    outcome: str                                   # ACCEPTED | REJECTED
    notes: str | None = Field(default=None, max_length=4000)


def _checklist_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "document_id": str(r["document_id"]),
        "sample_id_match": r["sample_id_match"], "method_per_tqa": r["method_per_tqa"],
        "units_per_spec": r["units_per_spec"], "conformance_by_pp": r["conformance_by_pp"],
        "discrepancies": r["discrepancies"], "notes": r["notes"], "outcome": r["outcome"],
        "reviewed_by": str(r["reviewed_by"]) if r["reviewed_by"] else None,
        "reviewed_at": r["reviewed_at"].isoformat() if r["reviewed_at"] else None,
        "updated_at": r["updated_at"].isoformat(),
    }


@router.get("/coa-documents/{doc_id}/checklist")
async def get_checklist(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(doc_id, "eCoA document")
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id) is None:
            raise HTTPException(404, "eCoA document not found")
        row = await c.fetchrow(
            "SELECT * FROM qc_ecoa_checklist WHERE document_id=$1", doc_id)
    return _checklist_out(dict(row)) if row else None


@router.put("/coa-documents/{doc_id}/checklist")
async def upsert_checklist(doc_id: str, body: ChecklistIn,
                           user: dict = Depends(require_role(*_WRITERS))):
    """Fill in / update the §6.3.2 review checklist for an eCoA document. Editable
    until the Head of QC signs the outcome; a decided (ACCEPTED/REJECTED) checklist
    is locked."""
    _uuid_or_404(doc_id, "eCoA document")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id) is None:
            raise HTTPException(404, "eCoA document not found")
        # serialise the read-then-insert so two concurrent PUTs can't both create
        # a checklist for the same document (the UNIQUE(org_id, document_id) is the
        # hard backstop; this avoids a unique-violation 500 on the race).
        await c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", f"ecoacl:{user['org_id']}:{doc_id}")
        cur = await c.fetchrow("SELECT * FROM qc_ecoa_checklist WHERE document_id=$1", doc_id)
        if cur and cur["outcome"] != "PENDING":
            raise HTTPException(409, f"checklist already {cur['outcome']} — locked")
        if cur is None:
            row = await c.fetchrow(
                "INSERT INTO qc_ecoa_checklist(org_id, document_id, sample_id_match,"
                " method_per_tqa, units_per_spec, conformance_by_pp, discrepancies, notes,"
                " created_by, updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$9) RETURNING *",
                user["org_id"], doc_id, patch.get("sample_id_match"), patch.get("method_per_tqa"),
                patch.get("units_per_spec"), patch.get("conformance_by_pp"),
                patch.get("discrepancies"), patch.get("notes"), user["id"])
        else:
            fields, args = [], []
            for col in ("sample_id_match", "method_per_tqa", "units_per_spec",
                        "conformance_by_pp", "discrepancies", "notes"):
                if col in patch:
                    args.append(patch[col]); fields.append(f"{col}=${len(args)}")
            if not fields:
                return _checklist_out(dict(cur))
            args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
            args.append(cur["id"])
            row = await c.fetchrow(
                f"UPDATE qc_ecoa_checklist SET {', '.join(fields)}, updated_at=now()"
                f" WHERE id=${len(args)} RETURNING *", *args)
    return _checklist_out(dict(row))


@router.post("/coa-documents/{doc_id}/checklist/decide")
async def decide_checklist(doc_id: str, body: ChecklistDecision,
                           user: dict = Depends(require_role(*_HOQC))):
    """§6.3.2 — the Head of QC signs the eCoA review outcome. ACCEPTED requires
    every checklist affirmation to be true and no discrepancies; REJECTED records
    the rejection (the eCoA is then voided and replaced by the contract lab). The
    decision stamps the reviewer + time and locks the checklist."""
    _uuid_or_404(doc_id, "eCoA document")
    if body.outcome not in ("ACCEPTED", "REJECTED"):
        raise HTTPException(422, "outcome must be ACCEPTED or REJECTED")
    async with rls(user) as c:
        if await c.fetchrow("SELECT id FROM qc_coa_documents WHERE id=$1", doc_id) is None:
            raise HTTPException(404, "eCoA document not found")
        cur = await c.fetchrow("SELECT * FROM qc_ecoa_checklist WHERE document_id=$1", doc_id)
        if cur is None:
            raise HTTPException(409, "complete the checklist before deciding")
        if cur["outcome"] != "PENDING":
            raise HTTPException(409, f"checklist already {cur['outcome']}")
        if body.outcome == "ACCEPTED":
            # §6.3.2 — accept only a complete, discrepancy-free checklist.
            affirmations = (cur["sample_id_match"], cur["method_per_tqa"],
                            cur["units_per_spec"], cur["conformance_by_pp"])
            if not all(a is True for a in affirmations):
                raise HTTPException(422, "every checklist field must be affirmed (true) to accept")
            if (cur["discrepancies"] or "").strip():
                raise HTTPException(422, "resolve the recorded discrepancies before accepting"
                                         " (they must be cleared in writing per §6.3.2)")
        note = body.notes.strip() if body.notes else None
        row = await c.fetchrow(
            "UPDATE qc_ecoa_checklist SET outcome=$1, reviewed_by=$2, reviewed_at=now(),"
            " notes=COALESCE($3, notes), updated_by=$2, updated_at=now() WHERE id=$4 RETURNING *",
            body.outcome, user["id"], note, cur["id"])
        # H1: a REJECTED review voids the eCoA (its docstring's promise, which the
        # code never fulfilled) — drive the still-open document to REJECTED so it
        # can no longer be promoted. An already-terminal doc (PROMOTED/REJECTED) is
        # left untouched.
        if body.outcome == "REJECTED":
            await c.execute(
                "UPDATE qc_coa_documents SET status='REJECTED', updated_by=$1, updated_at=now()"
                " WHERE id=$2 AND status NOT IN ('PROMOTED','REJECTED')", user["id"], doc_id)
    return _checklist_out(dict(row))


@router.post("/coa-documents/{doc_id}/extractions", status_code=201)
async def submit_extractions(doc_id: str, body: ExtractionsIn,
                             user: dict = Depends(require_role(*_WRITERS))):
    """Bulk-submit the transcribed fields for a document. Each field is
    auto-mapped to a spec parameter (by an existing human mapping, then by
    name), server-graded against that parameter's limits, and — when no
    mapping is found — queued in `qc_field_placeholders` for a human. Sets the
    document status to EXTRACTED."""
    _uuid_or_404(doc_id, "eCoA document")
    async with rls(user) as c:
        doc = await c.fetchrow("SELECT * FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "eCoA document not found")
        if doc["status"] in ("PROMOTED", "REJECTED"):
            raise HTTPException(409, f"Document is {doc['status']} — extractions are closed")
        # candidate parameters: the doc's spec, matched by canonical name…
        by_name: dict[str, dict] = {}
        if doc["specification_id"]:
            for p in await c.fetch(
                    "SELECT * FROM qc_spec_parameters WHERE spec_id=$1", doc["specification_id"]):
                pd = dict(p)
                for key in (pd.get("test_name_en"), pd.get("test_name_mk")):
                    n = _norm_label(key)
                    if n:
                        by_name.setdefault(n, pd)
        # …plus any label a human has already mapped (org-wide, cross-document).
        ph_rows = await c.fetch(
            "SELECT normalized_label, mapped_parameter_id FROM qc_field_placeholders"
            " WHERE status='MAPPED' AND mapped_parameter_id IS NOT NULL")
        mapped_by_label = {r["normalized_label"]: r["mapped_parameter_id"] for r in ph_rows}
        param_by_id: dict[str, dict] = {}
        if mapped_by_label:
            for p in await c.fetch(
                    "SELECT * FROM qc_spec_parameters WHERE id = ANY($1::uuid[])",
                    list(mapped_by_label.values())):
                param_by_id[str(p["id"])] = dict(p)

        out, unmapped = [], 0
        for item in body.items:
            nlabel = _norm_label(item.raw_label)
            param = None
            if nlabel in mapped_by_label:
                candidate = param_by_id.get(str(mapped_by_label[nlabel]))
                # H6 (spec-scoped auto-map): a label previously mapped (org-wide,
                # cross-document) must only auto-apply when its parameter belongs
                # to THIS document's specification. Otherwise a label once mapped
                # to spec A's parameter would grade a spec-B value against spec A's
                # limits, and promote() would insert that wrong `complies` straight
                # onto the certificate — bypassing the same-spec guard the manual
                # add_result / update_extraction paths enforce.
                if (candidate is not None and doc["specification_id"] is not None
                        and str(candidate.get("spec_id")) == str(doc["specification_id"])):
                    param = candidate
            if param is None:
                param = by_name.get(nlabel)
            if param is not None:
                lo, hi = param.get("lower_limit"), param.get("upper_limit")
                complies, _ = _evaluate(item.numeric_value, lo, hi)
                grade = "graded" if item.numeric_value is not None else "unknown"
                test_name = param.get("test_name_en") or param.get("test_name_mk")
                pid = param["id"]
            else:
                lo = hi = complies = None
                grade, test_name, pid = "unmapped", None, None
                unmapped += 1
                # adaptive discovery: surface the unknown label for a human,
                # deduped per org, occurrences counted.
                await c.execute(
                    "INSERT INTO qc_field_placeholders(org_id, raw_label, normalized_label,"
                    " suggested_test_name, first_seen_document_id, created_by, updated_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$6)"
                    " ON CONFLICT (org_id, normalized_label) DO UPDATE"
                    "   SET occurrences = qc_field_placeholders.occurrences + 1, updated_at=now()",
                    user["org_id"], item.raw_label, nlabel, item.raw_label, doc_id, user["id"])
            row = await c.fetchrow(
                "INSERT INTO qc_coa_extractions(org_id, document_id, raw_label, raw_value,"
                " numeric_value, unit, parameter_id, test_name, lower_limit, upper_limit,"
                " complies, grade_status, confidence, source_page, lab_verdict,"
                " created_by, updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$16) RETURNING *",
                user["org_id"], doc_id, item.raw_label, item.raw_value, item.numeric_value,
                item.unit, pid, test_name, lo, hi, complies, grade, item.confidence,
                item.source_page, item.lab_verdict, user["id"])
            out.append(_extract_out(dict(row)))
        if doc["status"] == "UPLOADED":
            await c.execute(
                "UPDATE qc_coa_documents SET status='EXTRACTED', updated_by=$1, updated_at=now()"
                " WHERE id=$2", user["id"], doc_id)
    return {"extractions": out, "count": len(out), "unmapped": unmapped}


@router.patch("/coa-documents/{doc_id}/extractions/{eid}")
async def update_extraction(doc_id: str, eid: str, body: ExtractionPatch,
                            user: dict = Depends(require_role(*_WRITERS))):
    """Reviewer fix: map an extraction to a spec parameter (re-grades against
    that parameter's limits) and/or correct the value/unit."""
    _uuid_or_404(doc_id, "eCoA document"); _uuid_or_404(eid, "Extraction")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        doc = await c.fetchrow(
            "SELECT status, specification_id FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "Document not found")
        if doc["status"] in ("PROMOTED", "REJECTED"):
            # Once a certificate has been minted (or the doc rejected) the
            # source-of-record is closed — editing an extraction afterwards
            # would silently desync it from the already-created qc_results.
            raise HTTPException(409, f"Document is {doc['status']} — extractions are locked")
        cur = await c.fetchrow(
            "SELECT * FROM qc_coa_extractions WHERE id=$1 AND document_id=$2", eid, doc_id)
        if cur is None:
            raise HTTPException(404, "Extraction not found")
        row = dict(cur)
        numeric = patch["numeric_value"] if "numeric_value" in patch else row["numeric_value"]
        pid = row["parameter_id"]
        lo, hi, test_name = row["lower_limit"], row["upper_limit"], row["test_name"]
        if "parameter_id" in patch:
            pid = patch["parameter_id"]
            if pid:
                _uuid_or_422(pid, "parameter_id")
                # Same guard add_result has: the cited parameter must belong to
                # THIS document's specification, else a reviewer could re-grade
                # a value against another spec's limits and promote fabricated
                # conformance onto the certificate.
                p = await c.fetchrow("SELECT * FROM qc_spec_parameters WHERE id=$1", pid)
                if p is None:
                    raise HTTPException(422, "Unknown parameter")
                if doc["specification_id"] is None or p["spec_id"] != doc["specification_id"]:
                    raise HTTPException(422, "Parameter does not belong to this document's specification")
                lo, hi = p["lower_limit"], p["upper_limit"]
                test_name = patch.get("test_name") or p["test_name_en"] or p["test_name_mk"]
            else:
                lo = hi = None
        if "test_name" in patch and patch["test_name"]:
            test_name = patch["test_name"]
        unit = patch["unit"] if "unit" in patch else row["unit"]
        if pid:
            complies, _ = _evaluate(numeric, lo, hi)
            grade = "graded" if numeric is not None else "unknown"
        else:
            complies, grade = None, "unmapped"
        lab_verdict = patch["lab_verdict"] if "lab_verdict" in patch else row["lab_verdict"]
        row = await c.fetchrow(
            "UPDATE qc_coa_extractions SET parameter_id=$1, test_name=$2, numeric_value=$3,"
            " unit=$4, lower_limit=$5, upper_limit=$6, complies=$7, grade_status=$8,"
            " lab_verdict=$9, updated_by=$10, updated_at=now()"
            " WHERE id=$11 AND document_id=$12 RETURNING *",
            pid, test_name, numeric, unit, lo, hi, complies, grade, lab_verdict,
            user["id"], eid, doc_id)
    return _extract_out(dict(row))


@router.get("/coa-placeholders")
async def list_placeholders(status: str | None = None,
                            user: dict = Depends(require_role(*ELEVATED_ROLES))):
    clauses, args = [], []
    if status:
        args.append(status); clauses.append(f"status=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with rls(user) as c:
        rows = await c.fetch(
            f"SELECT * FROM qc_field_placeholders{where} ORDER BY occurrences DESC, created_at", *args)
    return [_placeholder_out(dict(r)) for r in rows]


@router.patch("/coa-placeholders/{ph_id}")
async def update_placeholder(ph_id: str, body: PlaceholderPatch,
                             user: dict = Depends(require_role(*_WRITERS))):
    """Resolve a discovered field: MAP it to a spec parameter (future CoAs then
    auto-map that label) or IGNORE it."""
    _uuid_or_404(ph_id, "Placeholder")
    patch = body.model_dump(exclude_unset=True)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT status FROM qc_field_placeholders WHERE id=$1", ph_id)
        if cur is None:
            raise HTTPException(404, "Placeholder not found")
        target = patch.get("status")
        if target is not None and target not in _PLACEHOLDER_STATUSES:
            raise HTTPException(422, "status must be OPEN, MAPPED or IGNORED")
        if target == "MAPPED" and not patch.get("mapped_parameter_id"):
            raise HTTPException(422, "MAPPED requires mapped_parameter_id")
        # Validate the referenced parameter whenever it is supplied (not only on a
        # MAPPED transition), so a bad/cross-org id 422s instead of hitting a raw
        # FK violation (500) or persisting a dangling reference.
        if patch.get("mapped_parameter_id"):
            if await c.fetchrow("SELECT id FROM qc_spec_parameters WHERE id=$1",
                                patch["mapped_parameter_id"]) is None:
                raise HTTPException(422, "Unknown parameter")
        fields, args = [], []
        for col in ("status", "mapped_parameter_id", "suggested_test_name"):
            if col in patch:
                args.append(patch[col]); fields.append(f"{col}=${len(args)}")
        if target in ("MAPPED", "IGNORED"):
            args.append(user["id"]); fields.append(f"resolved_by=${len(args)}")
            fields.append("resolved_at=now()")
        if not fields:
            return {"ok": True, "noop": True}
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(ph_id)
        row = await c.fetchrow(
            f"UPDATE qc_field_placeholders SET {', '.join(fields)}, updated_at=now()"
            f" WHERE id=${len(args)} RETURNING *", *args)
    return _placeholder_out(dict(row))


@router.post("/coa-documents/{doc_id}/promote", status_code=201)
async def promote_coa_document(doc_id: str, user: dict = Depends(require_role(*_WRITERS))):
    """Promote a reviewed eCoA into a native DRAFT qc_certificate + qc_results
    (U3). One result per MAPPED extraction, each carrying its source document
    (feeds the U1 COQ's per-line provenance). Unmapped extractions are left in
    the review queue and reported — never fabricated into a result."""
    async with rls(user) as c:
        doc = await c.fetchrow("SELECT * FROM qc_coa_documents WHERE id=$1", doc_id)
        if doc is None:
            raise HTTPException(404, "eCoA document not found")
        if doc["status"] not in ("EXTRACTED", "REVIEWED"):
            raise HTTPException(409, "Only an EXTRACTED or REVIEWED document can be promoted")
        if doc["promoted_coa_id"]:
            raise HTTPException(409, "Document already promoted")
        if not doc["specification_id"]:
            raise HTTPException(409, "Promotion needs a specification to certify against")
        # H1 (§6.3.2 QCT-018 gate): an external CoA becomes a native certificate
        # ONLY after its review checklist is signed ACCEPTED by the Head of QC.
        # Without this, a PENDING / absent / explicitly-REJECTED checklist could
        # still be promoted into a DRAFT→…→RELEASED certificate usable standalone
        # and via get_inherited_results — un-vetted external data entering the GMP
        # record. The CoQ-aggregation compile enforced this; single-doc promote did
        # not.
        cl = await c.fetchrow(
            "SELECT outcome FROM qc_ecoa_checklist WHERE document_id=$1", doc_id)
        if cl is None or cl["outcome"] != "ACCEPTED":
            raise HTTPException(
                409, f"eCoA {doc['doc_number']} needs an ACCEPTED §6.3.2 review"
                     " checklist (QCT-018) before promotion")
        rows = await c.fetch(
            "SELECT * FROM qc_coa_extractions WHERE document_id=$1 ORDER BY created_at", doc_id)
        mapped = [dict(r) for r in rows if r["parameter_id"] is not None]
        if not mapped:
            raise HTTPException(409, "No mapped results to promote — map the discovered fields first")
        coa_number = await _mint_cert_number(c, user["org_id"], "ECOA")
        coa = await c.fetchrow(
            "INSERT INTO qc_certificates(org_id, coa_number, batch_id, specification_id, sample_id,"
            " cert_type, report_date, source_lab, laboratory_id, notes, analyst_id,"
            " created_by, updated_by)"
            " VALUES ($1,$2,$3,$4,$5,'ECOA',$6::date,$7,$8,$9,$10,$10,$10) RETURNING *",
            user["org_id"], coa_number, doc["batch_id"], doc["specification_id"], doc["sample_id"],
            doc["report_date"], doc["source_institution"], doc["laboratory_id"],
            f"Promoted from {doc['doc_number']}", user["id"])
        for m in mapped:
            _, st = _evaluate(m["numeric_value"], m["lower_limit"], m["upper_limit"])
            await c.execute(
                "INSERT INTO qc_results(org_id, coa_id, parameter_id, test_name, result_value,"
                " result_numeric, unit, lower_limit, upper_limit, complies, status, analyst_id,"
                " source_document_code, source_institution, lab_verdict, created_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$12)",
                user["org_id"], coa["id"], m["parameter_id"],
                m["test_name"] or m["raw_label"], m["raw_value"], m["numeric_value"], m["unit"],
                m["lower_limit"], m["upper_limit"], m["complies"], st, user["id"],
                doc["doc_number"], doc["source_institution"], m["lab_verdict"])
        # Optimistic re-assert (same TOCTOU defense generate_coq uses): the
        # promoted_coa_id IS NULL predicate makes concurrent promotes race-safe
        # — the loser's UPDATE matches 0 rows and the whole transaction (its
        # duplicate certificate + results included) rolls back with a 409.
        tag = await c.execute(
            "UPDATE qc_coa_documents SET status='PROMOTED', promoted_coa_id=$1,"
            " updated_by=$2, updated_at=now()"
            " WHERE id=$3 AND promoted_coa_id IS NULL", coa["id"], user["id"], doc_id)
        if tag == "UPDATE 0":
            raise HTTPException(409, "Document was already promoted")
        await safe_emit(c, user, verb="ecoa_promoted", object_type="qc_coa_document",
                   object_id=doc_id, recipients=[],
                   params={"doc_number": doc["doc_number"], "coa_number": coa["coa_number"],
                           "results": len(mapped)})
    return {"coa_id": str(coa["id"]), "coa_number": coa["coa_number"],
            "results_created": len(mapped), "skipped_unmapped": len(rows) - len(mapped)}


def _num_eq(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= 1e-9


def _verify_out(r: dict) -> dict:
    return {
        "id": str(r["id"]), "coa_id": str(r["coa_id"]),
        "source_document_id": str(r["source_document_id"]) if r["source_document_id"] else None,
        "verdict": r["verdict"], "checked": r["checked"], "mismatches": r["mismatches"],
        "details": r["details"],
        "verified_at": r["verified_at"].isoformat() if r.get("verified_at") else None,
    }


@router.get("/certificates/{coa_id}/verifications")
async def list_verifications(coa_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT * FROM qc_coa_verifications WHERE coa_id=$1 ORDER BY verified_at DESC", coa_id)
    return [_verify_out(dict(r)) for r in rows]


@router.post("/certificates/{coa_id}/verify", status_code=201)
async def verify_certificate(coa_id: str, user: dict = Depends(require_role(*_WRITERS))):
    """Reconcile a promoted certificate against its source eCoA and record the
    verdict. 409 if the certificate was not promoted from an ingested document
    (nothing to reconcile against)."""
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT id FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        doc = await c.fetchrow(
            "SELECT * FROM qc_coa_documents WHERE promoted_coa_id=$1", coa_id)
        if doc is None:
            raise HTTPException(409, "Certificate was not promoted from an ingested eCoA")
        results = await c.fetch("SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", coa_id)
        exts = await c.fetch(
            "SELECT * FROM qc_coa_extractions WHERE document_id=$1 AND parameter_id IS NOT NULL",
            doc["id"])
        by_param = {str(e["parameter_id"]): dict(e) for e in exts}
        details, mismatches = [], 0
        for r in results:
            pid = str(r["parameter_id"]) if r["parameter_id"] else None
            src = by_param.get(pid) if pid else None
            if src is None:
                match, reason = False, "no matching source line"
            else:
                num_ok = _num_eq(r["result_numeric"], src["numeric_value"])
                comply_ok = (r["complies"] == src["complies"])
                lim_ok = _num_eq(r["lower_limit"], src["lower_limit"]) and _num_eq(r["upper_limit"], src["upper_limit"])
                match = num_ok and comply_ok and lim_ok
                reason = "" if match else ", ".join(
                    x for x, ok in (("value", num_ok), ("verdict", comply_ok), ("limits", lim_ok)) if not ok)
            if not match:
                mismatches += 1
            _f = lambda v: None if v is None else float(v)   # jsonb can't take Decimal
            details.append({
                "parameter_id": pid, "test_name": r["test_name"],
                "result_numeric": _f(r["result_numeric"]),
                "source_numeric": _f(src["numeric_value"]) if src else None,
                "result_complies": r["complies"], "source_complies": src["complies"] if src else None,
                "match": match, "reason": reason})
        verdict = "VERIFIED" if mismatches == 0 else "DISCREPANCY"
        row = await c.fetchrow(
            "INSERT INTO qc_coa_verifications(org_id, coa_id, source_document_id, verdict,"
            " checked, mismatches, details, verified_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
            user["org_id"], coa_id, doc["id"], verdict, len(results), mismatches, details, user["id"])
        await safe_emit(c, user, verb="coa_verified", object_type="qc_certificate",
                   object_id=coa_id, recipients=[],
                   params={"verdict": verdict, "checked": len(results), "mismatches": mismatches})
    return _verify_out(dict(row))
