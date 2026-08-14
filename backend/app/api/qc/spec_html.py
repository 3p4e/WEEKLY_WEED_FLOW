"""Faithful A4 HTML documents — ImB per-strain Product Specification + iCoA.

Owner decision 2026-08-14: these render as **A4 print HTML served by the
backend**, not DocEngine .docx (the CoQ keeps its DocEngine pipeline).

Two documents, two fidelity levels — both deliberate:

* **ImB Product Specification** (`GET /qc/potency-specs/{id}/document?tier=N`)
  renders through the owner's OWN template: `app/data/imb_spec_template.html`
  is the handoff archive's `GP_Grape_Pie_Grade_III.html` with twelve data slots
  tokenized (`__DOC_CODE__`, `__STRAIN_NAME__`, potency row, dates, …) —
  byte-faithful Navy&Gold/Orbitron layout, one A4 page, № everywhere,
  "MK GMP Certified Facility" footer. Data comes from the APPROVED/DRAFT
  ladder row + its cultivar; a non-APPROVED ladder renders with a visible
  DRAFT — NOT APPROVED watermark and em-dash signature dates (a document must
  never look released before its data is).

* **iCoA single-parameter certificate**
  (`GET /qc/certificates/{id}/icoa-html?parameter_id=…`) follows the design
  system's shell (header bar → id strip → sample grid → §01 method → §02
  results → conformance → 3-tier signatures → footer) built from the system's
  tokens (navy #1B3A5C · gold #A67C2E · bronze #8C6B3F, Montserrat + Roboto
  Mono). Signatures are REAL qc_signatures rows only; absent ones render as
  roles-of-record attribution, never as executed signatures (same H5 honesty
  rule as the CoQ).

GxP: every DB value is html-escaped; phenotype is rendered UNSELECTED (the app
carries no verified phenotype data — a gold tag would fabricate genetics);
nothing is invented for missing fields.
"""
import html
from pathlib import Path

from fastapi import Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.db import rls, users_admin_pool
from app.deps import require_role
from app.roles import ELEVATED_ROLES

from .common import _uuid_or_404, _uuid_or_422, router

_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "data" / "imb_spec_template.html"

_ROMAN_EN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}

_HTML_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
                               "font-src https://fonts.gstatic.com; "
                               "style-src-elem 'unsafe-inline' https://fonts.googleapis.com; "
                               "img-src data:",
}


def _e(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def _ddmmyyyy(d) -> str:
    return d.strftime("%d.%m.%Y") if d else "—"


def _load_template() -> str:
    try:
        return _TEMPLATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(503, "The ImB specification template is missing from this build")


@router.get("/potency-specs/{spec_id}/document", response_class=HTMLResponse)
async def spec_document(spec_id: str, tier: int = Query(ge=1, le=6),
                        user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """One strain × one grade = one A4 page (QCSP 001), from the stored ladder."""
    _uuid_or_404(spec_id, "Potency specification")
    async with rls(user) as c:
        spec = await c.fetchrow(
            "SELECT ps.*, cv.code AS cultivar_code, cv.name AS cultivar_name"
            " FROM qc_potency_specs ps JOIN cultivars cv ON cv.id = ps.cultivar_id"
            " WHERE ps.id=$1", spec_id)
        if spec is None:
            raise HTTPException(404, "Potency specification not found")
        row = await c.fetchrow(
            "SELECT * FROM qc_potency_spec_ranges WHERE potency_spec_id=$1 AND tier=$2",
            spec_id, tier)
        if row is None:
            raise HTTPException(404, f"This ladder has no tier {tier}")

    roman = _ROMAN_EN[tier]
    acr = spec["cultivar_code"]
    name = spec["cultivar_name"]
    rmin, rmax = float(row["range_min"]), float(row["range_max"])
    nominal = float(row["nominal"])
    width = float(row["width_pp"]) if row["width_pp"] is not None else round((rmax - rmin) / 2, 2)
    approved = spec["status"] == "APPROVED"

    doc = _load_template()
    subs = {
        "__TITLE__": f"Purely Plant — Product Specification — {_e(name)} ({_e(acr)}) — Grade {roman}",
        "__DOC_CODE__": f"QCSP 001_{_e(acr)}-{roman}_v.01",
        "__STRAIN_NAME__": _e(name),
        # The app carries no verified phenotype genetics — render the three
        # options UNSELECTED rather than fabricate an Indica/Sativa/Hybrid claim.
        "__PHENOTYPE_CELLS__": ('<span class="ptk-cell"><span class="var-opt">Indica</span>'
                                '<span class="var-opt">Sativa</span>'
                                '<span class="var-opt">Hybrid</span></span>'),
        "__GRADE_EN__": f"Grade {roman}",
        "__GRADE_MK__": f"Класа {roman}",
        "__PRODUCT_CODE__": _e(row["product_code"]) if "product_code" in row and row.get("product_code")
                            else f"{_e(acr)}_THC{nominal:g}:CBD1",
        "__NOMINAL__": f"{nominal:.2f}% ± {width:.2f}%",
        "__RANGE__": f"{rmin:.2f} – {rmax:.2f}%",
        # The two signatories are the spec family's locked roles-of-record
        # (handoff rule: exactly QC Blagoj Nikolov + QA Jovana Romevska
        # Cvetkovski). Their printed date is the ladder's effective date once
        # APPROVED; a DRAFT prints em-dashes + the watermark.
        "__QC_DATE__": _ddmmyyyy(spec["effective_date"]) if approved else "—",
        "__QA_DATE__": _ddmmyyyy(spec["effective_date"]) if approved else "—",
        "__DRAFT_WM__": "" if approved
                        else '<div class="draft-wm">Draft — not approved</div>',
    }
    for token, value in subs.items():
        doc = doc.replace(token, value)
    return HTMLResponse(doc, headers=_HTML_HEADERS)


# ── iCoA single-parameter certificate ────────────────────────────────────────

_ICOA_CSS = """
  :root { --navy:#1B3A5C; --navy-soft:#4A6076; --gold:#A67C2E; --gold-bright:#C9A227;
          --bronze:#8C6B3F; --ink:#1C2A38; --line:#D8DEE6; --tint:#F7FAFC; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Montserrat',sans-serif; color:var(--ink); background:#fff; }
  .mono, .code { font-family:'Roboto Mono',monospace; }
  .page { width:210mm; min-height:297mm; margin:0 auto; position:relative;
          display:flex; flex-direction:column; padding-bottom:0; }
  .header-bar { background:var(--navy); color:#fff; display:flex; align-items:center;
                justify-content:space-between; padding:14px 0.35in; }
  .hb-title { font-size:16px; font-weight:800; letter-spacing:.5px; }
  .hb-sub { font-size:9px; color:#C7D2DE; margin-top:2px; }
  .hb-code { font-family:'Roboto Mono',monospace; font-size:11px; font-weight:700;
             color:var(--gold-bright); }
  .id-strip { background:var(--tint); border-bottom:2px solid var(--gold);
              padding:8px 0.35in; display:flex; justify-content:space-between;
              align-items:baseline; font-size:10px; }
  .id-strip b { color:var(--navy); }
  .grid { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--line);
          border:1px solid var(--line); margin:10px 0.35in; }
  .grid > div { background:#fff; padding:6px 8px; }
  .g-label { font-size:7.5px; font-weight:700; text-transform:uppercase; color:var(--navy-soft); }
  .g-val { font-family:'Roboto Mono',monospace; font-size:10px; font-weight:600; margin-top:2px; }
  .sec-label { background:var(--navy); color:#fff; font-size:10px; font-weight:800;
               letter-spacing:.6px; text-transform:uppercase; padding:5px 0.35in; margin-top:6px; }
  .body-pad { padding:8px 0.35in; font-size:10px; }
  table.res { width:calc(100% - 0.7in); margin:8px 0.35in; border-collapse:collapse; font-size:9.5px; }
  table.res th { background:var(--navy); color:#fff; text-align:left; padding:4px 7px;
                 font-size:8.5px; text-transform:uppercase; letter-spacing:.4px; }
  table.res td { border:1px solid var(--line); padding:4px 7px; vertical-align:middle; }
  table.res tr:nth-child(even) td { background:var(--tint); }
  .pass { color:#1F7A3D; font-weight:700; }
  .fail { color:#B22234; font-weight:700; }
  .conform { margin:10px 0.35in; border:1.5px solid var(--gold); background:#FBF6E9;
             padding:8px 10px; font-size:10px; display:flex; gap:10px; align-items:center; }
  .cs-badge { background:var(--navy); color:#fff; font-weight:800; font-size:9px;
              padding:4px 10px; border-radius:3px; text-transform:uppercase; letter-spacing:.5px; }
  .sig-row { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:14px 0.35in 10px; }
  .sig b { display:block; font-size:8px; text-transform:uppercase; color:var(--navy-soft);
           letter-spacing:.4px; }
  .sig .nm { font-size:10.5px; font-weight:700; color:var(--navy); margin-top:14px;
             border-top:1px solid var(--ink); padding-top:3px; }
  .sig .meta { font-size:8px; color:var(--navy-soft); margin-top:2px; }
  .attn { margin:8px 0.35in; font-size:8.5px; font-style:italic; color:var(--navy-soft); }
  .footer { margin-top:auto; background:var(--navy); color:#C7D2DE; display:flex;
            justify-content:space-between; align-items:center; padding:9px 0.35in; font-size:8px; }
  .footer .r { text-align:right; color:#fff; }
  @media print { body { -webkit-print-color-adjust:exact; print-color-adjust:exact; } }
"""


@router.get("/certificates/{coa_id}/icoa-html", response_class=HTMLResponse)
async def icoa_document(coa_id: str, parameter_id: str = Query(...),
                        user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Single-parameter internal-CoA A4 (design-system shell, real data only)."""
    _uuid_or_404(coa_id, "Certificate")
    _uuid_or_422(parameter_id, "parameter_id")
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        if coa["cert_type"] != "ICOA":
            raise HTTPException(409, "This document renders INTERNAL CoAs only —"
                                     f" this certificate is {coa['cert_type']}")
        param = await c.fetchrow("SELECT * FROM qc_spec_parameters WHERE id=$1", parameter_id)
        if param is None:
            raise HTTPException(404, "Specification parameter not found")
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id=$1 AND parameter_id=$2 ORDER BY created_at",
            coa_id, parameter_id)
        if not results:
            raise HTTPException(409, "No result for that parameter on this certificate")
        sigs = await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_certificate' AND object_id=$1"
            " ORDER BY signed_at", coa_id)
    # roles-of-record names (BYPASSRLS lookup, org-scoped — same as coq_docx)
    ids = [v for v in (coa["analyst_id"], coa["reviewer_id"], coa["approver_id"]) if v]
    names = {}
    if ids:
        rows = await users_admin_pool().fetch(
            "SELECT id, full_name, username FROM profiles WHERE id = ANY($1::uuid[]) AND org_id=$2",
            ids, coa["org_id"])
        names = {str(r["id"]): (r["full_name"] or r["username"]) for r in rows}

    def role_name(uid):
        return _e(names.get(str(uid), "—")) if uid else "—"

    test_name = param["test_name_en"] or param["test_name_mk"] or "—"
    method = param["test_method"] or param["pharmacopoeia_ref"] or "—"
    lo, hi = param["lower_limit"], param["upper_limit"]
    ac = ("—" if lo is None and hi is None else
          f"{'' if lo is None else f'≥ {float(lo):g}'}"
          f"{' – ' if lo is not None and hi is not None else ''}"
          f"{'' if hi is None else f'≤ {float(hi):g}'} {param['unit'] or ''}".strip())

    res_rows = ""
    all_pass = True
    for r in results:
        val = r["result_value"] if r["result_value"] is not None else (
            f"{float(r['result_numeric']):g}" if r["result_numeric"] is not None else "—")
        comp = r["complies"]
        all_pass = all_pass and comp is True
        badge = ('<span class="pass">✓ Conforms</span>' if comp is True else
                 '<span class="fail">✗ Does not conform</span>' if comp is False else "—")
        res_rows += (f"<tr><td>{_e(r['test_name'] or test_name)}</td>"
                     f"<td class='mono'>{_e(ac)}</td>"
                     f"<td class='mono'>{_e(val)} {_e(r['unit'] or '')}</td>"
                     f"<td>{badge}</td>"
                     f"<td class='mono'>{_e(_ddmmyyyy(r['result_date']))}</td></tr>")

    # Real e-signatures per meaning; absent → roles-of-record attribution (H5).
    by_meaning = {}
    for s in sigs:
        by_meaning.setdefault(s["meaning"], s)

    def sig_block(label, meaning, uid):
        s = by_meaning.get(meaning)
        if s is not None:
            return (f"<div class='sig'><b>{label}</b><div class='nm'>{_e(s['signer_name'])}</div>"
                    f"<div class='meta'>{_e(s['signer_role'] or '')} · signed "
                    f"{_e(s['signed_at'].strftime('%d.%m.%Y %H:%M'))} (Annex 11)</div></div>")
        return (f"<div class='sig'><b>{label}</b><div class='nm'>{role_name(uid)}</div>"
                f"<div class='meta'>of record — no electronic signature captured</div></div>")

    verdict = ("Conforms to Specification" if coa["decision"] == "PASS"
               else "Does NOT conform to Specification" if coa["decision"] == "FAIL"
               else "Disposition pending")
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Internal Certificate of Analysis — {_e(coa['coa_number'])}</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&family=Roboto+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>{_ICOA_CSS}</style></head>
<body><div class="page">
  <div class="header-bar">
    <div><div class="hb-title">Internal Certificate of Analysis</div>
         <div class="hb-sub">Интерен сертификат за анализа — Single-parameter report</div></div>
    <div class="hb-code">{_e(coa['coa_number'])}</div>
  </div>
  <div class="id-strip"><span><b>Production Batch №</b> <span class="mono">{_e(coa['batch_id'])}</span></span>
    <span><b>Requested Test</b> {_e(test_name)}</span>
    <span><b>Status</b> {_e(coa['status'])}</span></div>
  <div class="grid">
    <div><div class="g-label">Certificate №</div><div class="g-val">{_e(coa['coa_number'])}</div></div>
    <div><div class="g-label">Report Date</div><div class="g-val">{_e(_ddmmyyyy(coa['report_date']))}</div></div>
    <div><div class="g-label">Method / Reference</div><div class="g-val">{_e(method)}</div></div>
    <div><div class="g-label">Acceptance Criteria</div><div class="g-val">{_e(ac)}</div></div>
  </div>
  <div class="sec-label">01 · Analytical Result — {_e(test_name)}</div>
  <table class="res"><thead><tr><th>Parameter</th><th>Acceptance</th><th>Result</th>
    <th>Complies</th><th>Result date</th></tr></thead><tbody>{res_rows}</tbody></table>
  <div class="conform"><span class="cs-badge">{_e(verdict)}</span>
    <span>All testing performed in-house by the Purely Plant QC Department —
    no analyses outsourced. Judged against the acceptance criteria of the
    certificate's specification of record.</span></div>
  <div class="sec-label">02 · Sign-off — 3-tier chain</div>
  <div class="sig-row">
    {sig_block('Analyst · Изготвил', 'AUTHORED', coa['analyst_id'])}
    {sig_block('Reviewed by · Прегледал', 'REVIEWED', coa['reviewer_id'])}
    {sig_block('Head of QC · Одобрил', 'APPROVED', coa['approver_id'])}
  </div>
  <div class="attn">Internal CoA sign-off is Analyst → Senior Analyst → Head of QC —
    three different persons; the Qualified Person is not part of iCoA sign-off.
    Processed under a complete Annex 11 audit trail.</div>
  <div class="footer"><span>Purely Plant DOOEL · Industriska ulica 9, br. 9, s. Kojlija 1043, Skopje</span>
    <span class="r">MK GMP Certified Facility<br>{_e(coa['coa_number'])} · Page 1 of 1</span></div>
</div></body></html>"""
    return HTMLResponse(doc, headers=_HTML_HEADERS)
