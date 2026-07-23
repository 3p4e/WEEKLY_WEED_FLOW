from app import docengine
from app.db import rls, users_admin_pool
from app.deps import require_role
from app.notify import safe_emit
from fastapi import Depends, HTTPException

from .common import _COQ_ROLES, _evaluate, _uuid_or_404, router
from .laboratories import _lab_scope_set, _result_in_scope
from .signatures import _sig_out
from .specs import _ACID_FACTOR


def _coq_client(timeout: float = 20.0):
    """The seam the COQ tests monkeypatch (mirrors qms.py's _de_client)."""
    return docengine.de_client(timeout)


def _coq_cell(s) -> str:
    """Sanitize a value for a DocEngine table/heading cell — strip the grammar
    separators (| heading split, ||| column split, ~~ MK/EN split)."""
    if s is None:
        return ""
    return str(s).replace("|||", "/").replace("~~", "-").replace("|", "/")


def _coq_manifest(coa: dict, spec: dict, params_by_id: dict, results: list,
                  lab: dict | None) -> list:
    """WHO TRS 1010 (model certificate of analysis) + Annex 16 / QCSOP 012 §9.3
    mandatory-CONTENT manifest: the required elements a Certificate of Quality
    must carry before it can be issued — a content-completeness gate layered on
    top of the house-style (pp_verify) and GxP data/completeness gates. Returns
    the list of absent mandatory elements (empty = ready to issue). Deterministic;
    fabricates nothing — a missing element is reported, never invented."""
    missing = []
    spec = spec or {}
    if not (spec.get("material_name_en") or spec.get("material_name_mk") or spec.get("material_code")):
        missing.append("material / product name")
    if not spec.get("spec_id"):
        missing.append("specification reference")
    if not coa.get("batch_id"):
        missing.append("batch number")
    if not coa.get("report_date"):
        missing.append("report date")
    # A COQ asserts conformance; the disposition of record must say so.
    if coa.get("decision") != "PASS":
        missing.append("recorded PASS disposition")
    if not coa.get("approver_id"):
        missing.append("authorised approver")
    # WHO: an externally-sourced certificate must identify the testing lab.
    if coa.get("cert_type") == "ECOA" and not (lab or coa.get("source_lab")):
        missing.append("testing laboratory")
    # WHO: every reported test needs an analytical-method reference (a computed
    # total already cites its monograph in the source column).
    no_method = []
    for r in results:
        if str(r.get("source_document_code") or "").startswith("Пресметано"):
            continue
        p = params_by_id.get(str(r.get("parameter_id"))) or {}
        if not (p.get("test_method") or p.get("pharmacopoeia_ref")):
            nm = r.get("test_name") or "?"
            if nm not in no_method:
                no_method.append(nm)
    if no_method:
        missing.append("analytical method for: " + ", ".join(no_method[:5]))
    return missing


_COQ_MANUFACTURER = ("Purely Plant DOOEL · Industriska ulica 9, br. 9, s. Kojlija 1043"
                     " · Petrovec-Skopje, North Macedonia")


_COQ_CANNABIS_CERTS = {"ICOA", "ECOA", "COQ"}


_GRADE_LABEL = {"GRADE_I": "Grade I", "GRADE_II": "Grade II", "GRADE_III": "Grade III",
                "GRADE_IV": "Grade IV", "GRADE_V": "Grade V"}


_COQ_SIG_ROLE = {
    "AUTHORED": "Изготвил~~Prepared by", "REVIEWED": "Прегледал~~Reviewed by",
    "APPROVED": "Одобрил~~Approved by", "RELEASED": "Пуштил~~Released by",
    "VERIFIED": "Верификувал~~Verified by", "COQ_ISSUED": "Издал CoQ~~CoQ issued by",
}


def _d(x) -> str:
    """Render a date/None as an ISO string (empty for None)."""
    return x.isoformat() if hasattr(x, "isoformat") else (str(x) if x else "")


def _coq_potency(spec: dict) -> str:
    """The cannabinoid strength line from the specification's THC acceptance
    window + grade. Empty when the spec carries neither — never invented."""
    parts = []
    lo, hi = spec.get("thc_acceptance_min"), spec.get("thc_acceptance_max")
    if lo is not None and hi is not None:
        parts.append(f"THC {lo}–{hi}%")
    elif lo is not None:
        parts.append(f"THC ≥ {lo}%")
    elif hi is not None:
        parts.append(f"THC ≤ {hi}%")
    g = _GRADE_LABEL.get(spec.get("thc_grade") or "")
    if g:
        parts.append(g)
    return " · ".join(parts)


def _coq_sources(results: list, lab: dict | None):
    """Derive the §02 Laboratory & CoA cross-reference from the results' cited
    provenance, and the per-row source letter for §01. Each distinct external
    source (institution + document code + issue date) gets a letter A, B, C…;
    results measured in-house carry 'Q'; a Ph. Eur. derived total carries '∑'.
    Derivation only — a source with no cited document simply shows blanks; no
    lab, accreditation, code, or date is ever fabricated.

    Returns (letters, crossref_rows, has_internal, has_computed)."""
    lab_name = ((lab or {}).get("name") or "").strip()
    lab_accr = " · ".join(x for x in ((lab or {}).get("accreditation_body"),
                                      (lab or {}).get("accreditation_number")) if x)

    def classify(r):
        code = str(r.get("source_document_code") or "").strip()
        inst = str(r.get("source_institution") or "").strip()
        if code.startswith("Пресметано") or code.startswith("Computed"):
            return "computed", None
        if not inst and not code:
            return "internal", ("Q",)
        return "external", ("E", inst, code, _d(r.get("source_document_date")))

    ext_order, groups, has_internal = [], {}, False
    for idx, r in enumerate(results):
        kind, key = classify(r)
        if kind == "computed":
            continue
        if kind == "internal":
            has_internal = True
        if key not in groups:
            groups[key] = {"kind": kind, "params": [], "r": r}
            if kind == "external":
                ext_order.append(key)
        groups[key]["params"].append(idx + 1)          # 1-based §01 row №

    keyletter = {}
    if has_internal:
        keyletter[("Q",)] = "Q"
    for i, k in enumerate(ext_order):
        keyletter[k] = chr(ord("A") + i)               # A, B, C…

    letters = []
    for r in results:
        kind, key = classify(r)
        letters.append("∑" if kind == "computed" else keyletter.get(key, "—"))

    def pstr(ps):
        return ", ".join(str(p) for p in ps)

    crossref = []
    if has_internal:
        # the only row whose lab/accreditation carry a PRE-BUILT bilingual mk~~en
        # pair — flagged raw so the renderer passes it through un-sanitized. Every
        # external row's lab/accreditation is user free-text and must be sanitized.
        crossref.append({
            "letter": "Q", "raw": True,
            "lab": "Внатрешна QC лабораторија, Purely Plant~~Purely Plant in-house QC Laboratory",
            "accreditation": "МК ГМП · внатрешна контрола~~MK GMP · internal release control",
            "code": "—", "issued": "—", "params": pstr(groups[("Q",)]["params"]),
        })
    for k in ext_order:
        g = groups[k]
        r = g["r"]
        inst = str(r.get("source_institution") or "").strip() or "—"
        # attach the certificate's structured ISO-17025 credential only when this
        # source's name matches the certificate's registered lab (best-effort).
        accr = lab_accr if (lab_name and inst.lower() == lab_name.lower()) else "—"
        crossref.append({
            "letter": keyletter[k], "lab": inst, "accreditation": accr,
            "code": str(r.get("source_document_code") or "—"),
            "issued": _d(r.get("source_document_date")) or "—",
            "params": pstr(g["params"]),
        })
    return letters, crossref, has_internal, any(x == "∑" for x in letters)


def _coq_markdown(coa: dict, spec: dict, params_by_id: dict, results: list,
                  lab: dict | None = None, scope_note: str | None = None,
                  sigs: list | None = None, signer_names: dict | None = None) -> str:
    """Assemble the Certificate of Quality as DocEngine bilingual Markdown in the
    approved house layout (CoQ_Template_v02_VariationF): product/identity meta
    grid → §01 Analytical Results (№ · parameter · method · acceptance · result ·
    source-letter) → §02 Laboratory & CoA cross-reference (each source traced
    once) → batch disposition → QC compliance statement → e-signatures. The
    doctype is FORM, so the DocEngine annex renderer supplies the logo header,
    navy #2B547E section banners, and the 'MK GMP Certified Facility' footer.
    GxP: no value is fabricated — an unknown field is omitted, an unknown result
    renders '—'; the caller's data / completeness / manifest gates run first."""
    c = _coq_cell
    material = " / ".join(x for x in (spec.get("material_name_mk"),
                                      spec.get("material_name_en") or spec.get("material_code")) if x)
    decision = coa.get("decision") or ""
    v_mk = "СЕРИЈАТА ЗАДОВОЛУВА — Одобрено за пуштање" if decision == "PASS" \
        else "СЕРИЈАТА НЕ ЗАДОВОЛУВА"
    v_en = "Conforms to Specification — Approved for Release" if decision == "PASS" \
        else "This batch does NOT conform"
    head = ("<!--HEADERDATA\n"
            "doctype: FORM\n"
            f"code: {c(coa['coa_number'])}\n"
            "version: 01\n"
            "mk_title: Сертификат за квалитет\n"
            "en_title: Certificate of Quality\n"
            "-->\n\n")
    title = "# Сертификат за квалитет|Certificate of Quality\n\n"

    # ── product / identity meta grid ────────────────────────────────────────
    cannabis = coa.get("cert_type") in _COQ_CANNABIS_CERTS
    bot = [x for x in (coa.get("botanical_type"),) if x]
    if cannabis:
        bot += ["Flos Cannabis Sativae L.", "Ph. Eur. mon. 3028 (Cannabis flos)"]
    bot += [x for x in (coa.get("chemotype"),) if x]
    spec_ref = spec.get("spec_id") or ""
    if spec.get("version"):
        spec_ref = f"{spec_ref} · v{spec['version']}".strip(" ·")
    if lab:
        lab_line = lab.get("name") or ""
        accr = " · ".join(x for x in (lab.get("accreditation_body"),
                                      lab.get("accreditation_number")) if x)
        lab_line = f"{lab_line} ({accr})" if accr else lab_line
    else:
        lab_line = coa.get("source_lab") or ""
    grid_rows = [
        ("№ на сертификат", "Certificate №", coa.get("coa_number"), True),
        ("Материјал", "Material", material, True),
        ("Ботаничко потекло", "Botanical origin", " · ".join(bot), False),
        ("Јачина", "Potency", _coq_potency(spec), False),
        ("Производна серија", "Production batch", coa.get("batch_id"), True),
        ("Серија на одгледување", "Cultivation batch", coa.get("cultivation_batch"), False),
        ("Код на производ", "Product code", coa.get("product_code"), False),
        ("Спецификација", "Specification", spec_ref, True),
        ("Пакување", "Packaging", coa.get("packaging"), False),
        ("Датум на пакување", "Packaging date", _d(coa.get("packaging_date")), False),
        ("Датум на производство", "Mfg. date", _d(coa.get("manufacture_date")), False),
        ("Рок на употреба", "Expiry date", _d(coa.get("expiry_date")), False),
        ("Датум на ретест", "Retest date", _d(coa.get("retest_date")), False),
        ("Датум на извештај", "Report date", _d(coa.get("report_date")), True),
        ("Лабораторија", "Laboratory", lab_line, False),
        ("Производител", "Manufacturer", _COQ_MANUFACTURER, True),
    ]
    grid = "[[FORM:grid]]\n"
    for mk, en, val, required in grid_rows:
        sval = (str(val).strip() if val is not None else "")
        if sval or required:
            grid += f"{mk}~~{en} ||| {c(sval) or '—'}\n"
    grid += "[[/FORM]]\n\n"

    # ── §01 analytical results (№ · parameter · method · acceptance · result · src) ──
    letters, crossref, has_internal, has_computed = _coq_sources(results, lab)
    s01 = ("# 01 Аналитички резултати|01 Analytical Results\n\n"
           "[[TABLE:data]]\n"
           "№~~№ ||| Параметар~~Parameter ||| Метод~~Method ||| "
           "Спецификација~~Acceptance ||| Резултат~~Result ||| Извор~~Src\n")
    for i, r in enumerate(results):
        p = params_by_id.get(str(r.get("parameter_id"))) or {}
        method = p.get("test_method") or p.get("pharmacopoeia_ref") or ""
        lo, hi = r.get("lower_limit"), r.get("upper_limit")
        limits = "—" if lo is None and hi is None else \
            f"{'' if lo is None else lo} … {'' if hi is None else hi}"
        val = r.get("result_value") or ("" if r.get("result_numeric") is None
                                        else str(r["result_numeric"]))
        val = (f"{val} {r.get('unit') or ''}").strip() or "—"
        s01 += (f"{i + 1} ||| {c(r.get('test_name'))} ||| {c(method)} ||| "
                f"{c(limits)} ||| {c(val)} ||| {letters[i]}\n")
    s01 += "[[/TABLE]]\n\n"
    if has_computed:
        s01 += ("_∑ — Вкупен THC/CBD е пресметан како збир на киселинската и"
                " декарбоксилираната форма (Ph. Eur. 2.2.29)._"
                "|||_∑ — Total THC/CBD is computed as the sum of the acidic and"
                " decarboxylated forms (Ph. Eur. 2.2.29)._\n\n")
    if has_internal:
        s01 += ("_Q — Странска материја и макроскопска идентификација ги изведува"
                " внатрешната QC служба на Purely Plant пред земање мостра за"
                " финалното QC пуштање (QCSOP-005 v.02)._"
                "|||_Q — Foreign Matter and Macroscopic Identification are performed"
                " by the in-house Purely Plant QC Department prior to sampling for"
                " final QC release testing (QCSOP-005 v.02)._\n\n")

    # ── §02 laboratory & CoA cross-reference (each source traced once) ───────
    s02 = ("# 02 Лаборатории и вкрстена референца на CoA|"
           "02 Laboratory & Certificate of Analysis Cross-Reference\n\n"
           "[[TABLE:data]]\n"
           "Извор~~Src ||| Лабораторија~~Laboratory ||| Акредитација~~Accreditation ||| "
           "Код на CoA~~CoA code ||| Издадено~~Issued ||| Параметри №~~Params №\n")
    for x in crossref:
        # ONLY the flagged internal-QC row carries a pre-built mk~~en pair; every
        # external value is user free-text and is sanitized (a raw ||| / ~~ / | in
        # a lab name must never inject a column or fabricate a bilingual split).
        lab_cell = x["lab"] if x.get("raw") else c(x["lab"])
        accr_cell = x["accreditation"] if x.get("raw") else c(x["accreditation"])
        s02 += (f"{x['letter']} ||| {lab_cell} ||| {accr_cell} ||| "
                f"{c(x['code'])} ||| {c(x['issued'])} ||| {c(x['params'])}\n")
    s02 += "[[/TABLE]]\n\n"

    # ── disposition + QC compliance statement ───────────────────────────────
    verdict = (f"**Севкупна диспозиција на серијата: {v_mk}.**"
               f"|||**Overall Batch Disposition: {v_en}.**\n\n")
    # the Ph. Eur. 3028 monograph clause is asserted only for cannabis-flower
    # certificates (a water/other CoQ conforms to its own spec, not to 3028).
    mono_mk = " и со Ph. Eur. монографија 3028" if cannabis else ""
    mono_en = " and Ph. Eur. Monograph 3028" if cannabis else ""
    comp = ("**Изјава за усогласеност на QC.** Оваа серија е произведена, спакувана и"
            " тестирана во согласност со одобрението за ставање на пазар и МК ГМП"
            " прописите на Република Северна Македонија (МАЛМЕД). Сите аналитички"
            " резултати од внатрешната QC служба и од надворешни ISO/IEC 17025"
            " акредитирани лаборатории се усогласени со критериумите за прифаќање"
            f"{mono_mk}."
            "|||**QC Compliance Statement.** This batch was manufactured, packaged and"
            " tested in compliance with the Marketing Authorisation and MK GMP"
            " regulations of the Republic of North Macedonia (MALMED). All analytical"
            " results from the in-house QC Department and from outsourced ISO/IEC 17025"
            f" accredited laboratories conform to the acceptance criteria{mono_en}.\n\n")
    note = (f"_{scope_note}_\n\n") if scope_note else ""

    # ── e-signatures (Annex 11) ─────────────────────────────────────────────
    sig = "# Потписи|Signatures\n\n"
    sig_rows = []
    for s in (sigs or []):
        role = _COQ_SIG_ROLE.get(s.get("meaning"), s.get("meaning") or "—")
        sig_rows.append((role, s.get("signer_name") or "—", s.get("signer_role") or "—",
                         (s.get("signed_at") or "")[:10] or "—"))
    if sig_rows:
        # ONLY genuine captured Annex-11 e-signatures populate the signatory
        # table — a name in the Signatory column asserts an executed signature.
        sig += ("[[TABLE:data]]\n"
                "Улога~~Role ||| Потписник~~Signatory ||| Функција~~Function ||| Датум~~Date\n")
        for role, name, fn, dt in sig_rows:
            sig += f"{role} ||| {c(name)} ||| {c(fn)} ||| {c(dt)}\n"
        sig += "[[/TABLE]]\n\n"
    else:
        # H5: no e-signature was captured. NEVER fabricate a signatory table from
        # the lifecycle roles-of-record — that would assert Prepared/Reviewed/
        # Approved signatures that were never executed. State honestly that
        # responsibility is attributed via the Annex-11 audit trail (not e-signed),
        # and name the roles of record as an explicit non-signature attribution.
        sig += ("_Оваа серија е обработена во GrowFlow со целосна Annex 11 ревизиона"
                " трага; долунаведените лица се одговорни според евиденцијата, но"
                " документот не носи електронски потпис._"
                "|||_This batch was processed in GrowFlow under a complete Annex 11"
                " audit trail; the persons below are responsible per the record,"
                " but this document carries no electronic signature._\n\n")
        for mk, en, key in (("Изготвил", "Prepared by", "analyst"),
                            ("Прегледал", "Reviewed by", "reviewer"),
                            ("Одобрил", "Approved by", "approver")):
            nm = (signer_names or {}).get(key)
            if nm:
                sig += f"{mk}: {c(nm)}|||{en}: {c(nm)}\n\n"

    footer = "МК ГМП сертифицирано постројение|||MK GMP Certified Facility\n"
    return head + title + grid + s01 + s02 + verdict + comp + note + sig + footer


@router.post("/certificates/{coa_id}/coq", status_code=201)
async def generate_coq(coa_id: str, user: dict = Depends(require_role(*_COQ_ROLES))):
    """Render a Certificate of Quality (.docx) from a RELEASED certificate via
    the DocEngine's PASS-gated formatter. Data gate: every result must comply
    (a FAIL or unmeasured result blocks). Issuing the COQ is a QC Manager
    function (QP may also issue one)."""
    _uuid_or_404(coa_id, "Certificate")
    async with rls(user) as c:
        coa = await c.fetchrow("SELECT * FROM qc_certificates WHERE id=$1", coa_id)
        if coa is None:
            raise HTTPException(404, "Certificate not found")
        if coa["status"] != "RELEASED":
            raise HTTPException(409, "A COQ is issued only from a RELEASED certificate")
        # H1 (defense-in-depth): if this certificate was promoted from an ingested
        # eCoA, that source document's §6.3.2 checklist must be ACCEPTED before a
        # CoQ is rendered. The promote path now enforces this too, but this closes
        # the gap for any certificate promoted before the promote-gate landed.
        src_doc = await c.fetchrow(
            "SELECT id, doc_number FROM qc_coa_documents WHERE promoted_coa_id=$1", coa_id)
        if src_doc is not None:
            src_cl = await c.fetchrow(
                "SELECT outcome FROM qc_ecoa_checklist WHERE document_id=$1", src_doc["id"])
            if src_cl is None or src_cl["outcome"] != "ACCEPTED":
                raise HTTPException(
                    409, f"Source eCoA {src_doc['doc_number']} lacks an ACCEPTED §6.3.2"
                         " review checklist (QCT-018) — cannot certify")
        # QCSOP 012 §6.4.1/§6.6 (URS gate): no COQ for a batch with an open OOS
        # investigation — the COQ is compiled only on the investigation-
        # confirmed result set. Explicit, logged reason; never a silent pass.
        open_oos = await c.fetchval(
            "SELECT count(*) FROM qc_oos_records WHERE batch_id=$1 AND status <> 'CLOSED'",
            coa["batch_id"])
    if open_oos:
        # §6.16 (C8) — an attempted CoQ on an open-OOS batch is itself a
        # reportable deviation (QASOP 010). Recorded in its own transaction so
        # the 409 cannot roll the event back.
        async with rls(user) as c2:
            try:
                await safe_emit(c2, user, verb="qc_deviation", object_type="qc_certificate",
                           object_id=coa_id, recipients=[],
                           params={"reason": "coq_on_open_oos", "batch_id": coa["batch_id"],
                                   "open_oos": open_oos, "sop": "QCSOP 012 §6.16"})
            except Exception:
                pass
        raise HTTPException(
            409, f"{open_oos} open OOS investigation(s) on batch {coa['batch_id']}"
                 " — a COQ cannot be issued until the investigation is closed"
                 " (QCSOP 012 §6.4.1; attempt recorded as a deviation, §6.16)")
    async with rls(user) as c:
        spec = await c.fetchrow("SELECT * FROM qc_specifications WHERE id=$1",
                                coa["specification_id"])
        params = await c.fetch(
            "SELECT * FROM qc_spec_parameters WHERE spec_id=$1", coa["specification_id"])
        results = await c.fetch(
            "SELECT * FROM qc_results WHERE coa_id=$1 ORDER BY created_at", coa_id)
        lab = await c.fetchrow("SELECT * FROM qc_laboratories WHERE id=$1",
                               coa["laboratory_id"]) if coa["laboratory_id"] else None
        # Annex 11 e-signatures captured on this certificate — rendered in the
        # CoQ signature block (name · function · meaning · date).
        sigs = await c.fetch(
            "SELECT * FROM qc_signatures WHERE object_type='qc_certificate' AND object_id=$1"
            " ORDER BY signed_at", coa_id)
    results = [dict(r) for r in results]
    sigs = [_sig_out(dict(s)) for s in sigs]
    # Resolve the certificate's roles-of-record (analyst / reviewer / approver)
    # to names, so the signature block has a truthful fallback when no explicit
    # e-signature was captured. Names live in the separate users DB.
    signer_names = {}
    _role_ids = {k: coa.get(f"{k}_id") for k in ("analyst", "reviewer", "approver")}
    _uids = [str(v) for v in _role_ids.values() if v]
    if _uids:
        prows = await users_admin_pool().fetch(
            "SELECT id, full_name FROM profiles WHERE id = ANY($1::uuid[]) AND is_deleted=false",
            _uids)
        _by_id = {str(p["id"]): p["full_name"] for p in prows}
        signer_names = {k: _by_id.get(str(v)) for k, v in _role_ids.items() if v and _by_id.get(str(v))}
    if not results:
        raise HTTPException(409, "The certificate has no results to certify")
    # Ph. Eur. 3028 derived totals: a computed parameter's value is derived HERE
    # from its two component results (total = neutral + 0.877 × acid) — never
    # transcribed. The synthetic row joins the same comply/completeness gates
    # below and renders on the COQ marked as computed. A missing component
    # simply leaves the total uncovered, so the completeness gate names it.
    by_param = {str(r["parameter_id"]): r for r in results if r["parameter_id"]}
    for p in params:
        if not p["computed_kind"] or str(p["id"]) in by_param:
            continue
        ra = by_param.get(str(p["component_a_id"])) if p["component_a_id"] else None
        rb = by_param.get(str(p["component_b_id"])) if p["component_b_id"] else None
        if not (ra and rb and ra["result_numeric"] is not None and rb["result_numeric"] is not None):
            continue
        val = round(float(ra["result_numeric"]) + _ACID_FACTOR * float(rb["result_numeric"]), 2)
        lo = float(p["lower_limit"]) if p["lower_limit"] is not None else None
        hi = float(p["upper_limit"]) if p["upper_limit"] is not None else None
        complies, _st = _evaluate(val, lo, hi)
        results.append({
            "parameter_id": p["id"], "test_name": p["test_name_en"] or p["test_name_mk"],
            "result_value": None, "result_numeric": val, "unit": p["unit"],
            "lower_limit": lo, "upper_limit": hi, "complies": complies,
            "source_document_code": "Пресметано / Computed — Ph. Eur. 3028",
            "source_institution": None,
        })
    # GxP data gate: never issue a conformant COQ over a FAIL or an unmeasured
    # (complies is None → 'unknown') result.
    unmet = [r for r in results if r["complies"] is not True]
    if unmet:
        raise HTTPException(
            409, f"{len(unmet)} result(s) do not comply or are unmeasured — cannot certify")
    # GxP completeness gate (COQ_GEN guard parity): every parameter of the
    # certificate's specification must be covered by a result — passing the
    # results-comply gate alone would let a COQ certify a partially-tested
    # batch (spec says 5 tests, only 3 entered, all 3 pass → certified).
    covered = {str(r["parameter_id"]) for r in results if r["parameter_id"]}
    missing = [p for p in params if str(p["id"]) not in covered]
    if missing:
        names = ", ".join((p["test_name_en"] or p["test_name_mk"] or "?") for p in missing[:5])
        raise HTTPException(
            409, f"{len(missing)} specification parameter(s) have no result ({names}"
                 f"{'…' if len(missing) > 5 else ''}) — batch is not fully tested")
    params_by_id = {str(p["id"]): dict(p) for p in params}
    # WHO TRS 1010 / Annex 16 §9.3 mandatory-content gate: refuse to issue a
    # certificate missing a required content element (never silently emit an
    # incomplete GMP record).
    manifest_missing = _coq_manifest(dict(coa), dict(spec) if spec else {},
                                     params_by_id, results, lab)
    if manifest_missing:
        raise HTTPException(
            409, "Certificate is missing WHO/Annex-16 mandatory content: "
                 + "; ".join(manifest_missing))
    # ISO 17025 scope advisory (URS Chapter 7): a result whose method is outside
    # the issuing lab's accredited scope is a quality signal for the reviewer.
    # Non-blocking — it is surfaced as a COQ footnote and in the response, never
    # an automatic OOS (that would fabricate a verdict the data doesn't support).
    scope = _lab_scope_set(lab["iso17025_scope"]) if lab else set()
    out_of_scope = []
    if scope:
        for r in results:
            p = params_by_id.get(str(r.get("parameter_id"))) or {}
            if not _result_in_scope(scope, p.get("test_method"), r.get("test_name")):
                out_of_scope.append(r.get("test_name") or "?")
    scope_note = None
    if out_of_scope:
        names = ", ".join(out_of_scope[:5])
        scope_note = (f"Тестови надвор од ISO 17025 опсегот на лабораторијата: {names}"
                      f"|||Tests outside the laboratory's ISO 17025 scope: {names}")
    md = _coq_markdown(dict(coa), dict(spec) if spec else {}, params_by_id, results,
                       lab=dict(lab) if lab else None, scope_note=scope_note,
                       sigs=sigs, signer_names=signer_names)
    # DocEngine build (house-style PASS gate). A pp_verify FAIL surfaces as 422.
    build = (await docengine.de_forward(
        "POST", "/build",
        {"markdown": md, "out_name": coa["coa_number"],
         "meta": {"code": coa["coa_number"], "title_mk": "Сертификат за квалитет",
                  "title_en": "Certificate of Quality", "version": "01"}},
        timeout=120.0, client_factory=_coq_client)).json()
    doc_id = build.get("document_id")
    async with rls(user) as c:
        # Re-assert RELEASED when stamping the artifact — the certificate could
        # have transitioned during the (up-to-120s) DocEngine build (TOCTOU).
        stamped = await c.fetchrow(
            "UPDATE qc_certificates SET coq_document_id=$1, coq_generated_at=now(),"
            " updated_by=$2, updated_at=now() WHERE id=$3 AND status='RELEASED' RETURNING id",
            doc_id, user["id"], coa_id)
        if stamped is None:
            raise HTTPException(409, "Certificate is no longer RELEASED — COQ not recorded")
        try:
            await safe_emit(c, user, verb="coq_generated", object_type="qc_certificate",
                       object_id=coa_id, recipients=[],
                       params={"coa_number": coa["coa_number"], "document_id": doc_id})
        except Exception:
            pass
    return {"coa_number": coa["coa_number"], "document_id": doc_id,
            "verify": build.get("verify"), "bytes": build.get("bytes"),
            "out_of_scope": out_of_scope}
