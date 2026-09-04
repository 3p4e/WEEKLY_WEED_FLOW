# Build the CoQ tracker workbook from consolidated.json (openpyxl). Fonts Arial; formulas for every derived count.
import json, re, collections
from datetime import datetime, date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.page import PageMargins
from openpyxl.formatting.rule import CellIsRule, FormulaRule

C = json.load(open("consolidated.json"))
batches, register, PARAMS = C["batches"], C["register"], C["params"]
ref = json.load(open("ref_coverage.json"))
BUILT = datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")

NAVY = "2B547E"; LIGHT = "DCE6F1"; GREY = "F2F2F2"; RED = "C00000"; AMBER = "FFF2CC"; GREEN = "E2EFDA"; PINK = "FCE4D6"; BLUEGREY = "DDEBF7"
F = lambda **k: Font(name="Arial", size=k.pop("size", 10), **k)
thin = Side(style="thin", color="BFBFBF"); BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HDR = PatternFill("solid", fgColor=NAVY); SUB = PatternFill("solid", fgColor=LIGHT); BAND = PatternFill("solid", fgColor=GREY)
FILL = {"✓": PatternFill("solid", fgColor=GREEN), "✓ᴿ": PatternFill("solid", fgColor=AMBER), "✓ᴵ": PatternFill("solid", fgColor=BLUEGREY), "✗": PatternFill("solid", fgColor=PINK)}
def dt(s): return datetime.strptime(s, "%d.%m.%Y")
def hdr(ws, row, values, fill=HDR, color="FFFFFF", bold=True, wrap=True, height=None):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=row, column=i, value=v); c.font = F(bold=bold, color=color, size=9); c.fill = fill; c.border = BORDER
        c.alignment = Alignment(wrap_text=wrap, vertical="center", horizontal="center")
    if height: ws.row_dimensions[row].height = height
def cell(ws, r, c, v, **k):
    x = ws.cell(row=r, column=c, value=v); x.font = F(**{kk: vv for kk, vv in k.items() if kk in ("bold","italic","color","size")}); x.border = BORDER
    x.alignment = Alignment(wrap_text=k.get("wrap", False), vertical="top", horizontal=k.get("h", "left")); 
    if "fill" in k and k["fill"]: x.fill = k["fill"]
    if "fmt" in k: x.number_format = k["fmt"]
    return x
def widths(ws, ws_widths):
    for i, w in enumerate(ws_widths, 1): ws.column_dimensions[L(i)].width = w
def print_setup(ws, freeze):
    ws.freeze_panes = freeze; ws.page_setup.orientation = "landscape"; ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"1:{ws.freeze_panes and int(re.sub(r'[A-Z]', '', freeze)) - 1 or 1}"; ws.page_margins = PageMargins(0.3, 0.3, 0.4, 0.4)

wb = Workbook()
# ------------------------------------------------------------------ Read Me
ws = wb.active; ws.title = "Read Me"
rows = [
 ("CoQ Parameter Tracker — built from RAGflow eCoA_DB", None),
 (f"Built {BUILT} from the RAGflow dataset eCOA_DB (id dd3ea108a3fd11f1858cf58865604f65): 253 documents, 308 text chunks, every document parsed DONE. This is the corpus the Letta agent gf_app_assistant is granted on letta-6ou3; the workbook is what that corpus can support, read by machine and cross-checked against the owner's CoQ Analysis Master v9.", None),
 ("", None), ("SHEETS", None),
 ("Batch Coverage", "One row per batch. ✓ / ✓ᴿ / ✓ᴵ / ✗ for each of the 12 parameters, the missing list, certificate count, laboratories present, OOS results. Missing (n) and Status are formulas."),
 ("CoQ Parameter Tracker v9", "One block per batch. Row 1 of a block carries the release result per determination (earliest release certificate that reports it); further rows list every other certificate on file — stability time-points (ᴿ), in-house documents (ᴵ), repeat release certificates — in date order, each row showing only its own values. Acceptance criteria in header row 3; out-of-specification results in red."),
 ("Results Register", "One row per batch × determination × certificate: result as printed, numeric value, criterion, verdict, certificate, date, laboratory, kind, file, RAGflow document id. Filterable."),
 ("eCOA Document Index", "One row per document: batch, laboratory, kind, code, date, parameters covered, how the batch name was resolved, filename, RAGflow id."),
 ("Parameters", "The 21 determinations with method, global acceptance criterion, source, tracker column, and which laboratories report each one in this corpus."),
 ("Summary Dashboard", "Coverage totals and missing-parameter frequency — all formulas over Batch Coverage."),
 ("Data Quality", "Everything a person should look at before trusting a cell: page-read conflicts held for review, documents with no extractable value, batches known only by P batch, and every difference against the owner's tracker."),
 ("", None), ("LEGEND", None),
 ("✓", "A release certificate from an accredited laboratory (CNP, IJZ, IJZ-MB, FHM, DFL) reports this determination."),
 ("✓ᴿ", "Only a stability time-point certificate reports it — a laboratory certificate issued 9 months or more after the batch's first certificate. Its value is not a release result."),
 ("✓ᴵ", "Only an in-house document reports it (Purely Plant Report of Analysis, NGP in-process form). Not coverage for a release certificate."),
 ("✗", "No document on file reports this determination."),
 ("—", "Blank / no value held for this determination from that certificate."),
 ("held for review", "The machine read of the certificate disagrees with the certificate's own arithmetic (total = free acid form + 0.877 × acid form). Both figures are in Data Quality; a person must read the page."),
 ("", None), ("RULES APPLIED", None),
 ("Batch names", "CU batch as printed on the certificate (серија / Сериски број / Batch No). Documents filed by P batch are assigned to the CU batch named inside them; when a certificate names only the P batch, the P batch is the row key. The owner's name for the same batch is shown where it differs."),
 ("Kinds", "eCoA = accredited laboratory certificate · Stability = eCoA dated ≥ 270 days after the batch's first certificate · In-house = PP / NGP document."),
 ("Coverage", "A parameter counts as covered (✓) only from an eCoA release certificate. Identification C (HPLC) is credited from any HPLC cannabinoid certificate. Identification A/B and Foreign Matter are credited only where a certificate prints them (2026 CNP full certificates; PP Reports of Analysis as ✓ᴵ)."),
 ("OOS", "A result is flagged only when it provably exceeds the global criterion in the Parameters sheet. ND, BLQ, <LOQ, 'absent', 'Одговара' pass. Microbial counts use the Ph. Eur. 5.1.4 maximum acceptable count (5 × the stated limit). Total Δ⁹-THC has no global criterion (per target grade) and is never flagged."),
 ("Dates", "Real dates (DD.MM.YYYY), sortable. Results keep the certificate's printed precision; numeric columns in the register are numbers."),
 ("Reading", "One machine read per page (RAGflow DeepDOC text). Where the owner's tracker holds a different figure for the same certificate, both are listed in Data Quality; nothing is invented and no value is copied from the owner's file into a result cell."),
]
for i, (a, b) in enumerate(rows, 1):
    c = ws.cell(row=i, column=1, value=a); c.font = F(bold=(b is None and a), size=(14 if i == 1 else 10)); c.alignment = Alignment(wrap_text=True, vertical="top")
    if b: d = ws.cell(row=i, column=2, value=b); d.font = F(); d.alignment = Alignment(wrap_text=True, vertical="top")
widths(ws, [30, 150])

# ------------------------------------------------------------------ Parameters
wp = wb.create_sheet("Parameters")
labs_for = collections.defaultdict(set); n_for = collections.Counter()
for row in register: labs_for[row["key"]].add(row["lab"]); n_for[row["key"]] += 1
# tracker column letters are filled after the tracker layout is known (below)
PCOL = {}
# ------------------------------------------------------------------ Tracker layout
GROUPS = [("BATCH IDENTIFICATION", [("CU Batch",None),("P Batch",None),("STATUS",None)]),
 ("IDENTIFICATION 1–3", [("#1 Identification A\nAppearance · Ph. Eur. mon. 3028","identA"),("#2 Identification B\nMicroscopy · Ph. Eur. 2.8.23","identB"),("#3 Identification C\nHPLC · Ph. Eur. 2.2.29","identC")]),
 ("CANNABINOID ASSAY 4–6", [("#4 Assay — Total Δ⁹-THC\nPh. Eur. 2.2.29 (HPLC)","thc"),("#5 Assay — Total CBD\nPh. Eur. 2.2.29 · CBD + CBDA×0.877","cbd"),("#6 Total CBN\nPh. Eur. 2.2.29 · CBN + CBNA×0.876","cbn")]),
 ("PHYSICAL 7–8", [("#7 Foreign Matter\nPh. Eur. 2.8.2 / in-house","foreign"),("#8 Loss on Drying\nPh. Eur. 2.2.32 · 40 °C, 24 h, 15–25 mbar","lod")]),
 ("MICROBIOLOGY 9", [("#9 Microbiological Purity\nPh. Eur. 2.6.12 / 2.6.13 / 2.6.31 · cat. C", ["tamc","tymc","gnb","salm","ecoli"])]),
 ("CONTAMINANTS 10–12", [("#10 Mycotoxins\nPh. Eur. 2.8.18 / 2.8.22 (HPLC-FLD)", ["afb1","afsum","ota"]),("#11 Heavy Metals\nPh. Eur. 2.4.27 (ICP-MS)", ["pb","cd","as","hg"]),("#12 Pesticide Residues\nPh. Eur. 2.8.13 (LC-MS/MS) · CUMCS equivalency","pest")])]
CRIT = {p[3]: p[5] for p in PARAMS}; DETNAME = {p[3]: p[2] for p in PARAMS}; PNUM = {p[3]: p[0] for p in PARAMS}
SHORT = {"tamc":"TAMC","tymc":"TYMC","gnb":"GNB","salm":"Salm.","ecoli":"E. coli","afb1":"AfB₁","afsum":"ΣAf","ota":"OTA","pb":"Pb","cd":"Cd","as":"As","hg":"Hg"}
wt = wb.create_sheet("CoQ Parameter Tracker v9")
col = 1; layout = []   # (key(s), result cols, cert col, mark col)
r1, r2, r3, r4 = {}, {}, {}, {}
for band, items in GROUPS:
    start = col
    for title, key in items:
        if key is None: r2[col] = title; r4[col] = title; col += 1; continue
        keys = key if isinstance(key, list) else [key]
        rescols = {}
        for k in keys:
            r4[col] = SHORT.get(k, "Result"); r3[col] = "A.C.: " + CRIT[k]; rescols[k] = col; PCOL[k] = L(col); col += 1
        r4[col] = "[eCOA code], (date) [Lab]"; certcol = col; col += 1
        r4[col] = "✓ ✗"; markcol = col; col += 1
        r2[rescols[keys[0]]] = title; layout.append((keys, rescols, certcol, markcol, rescols[keys[0]], col - 1))
    r1[start] = band; r1[(start, col - 1)] = band
NCOL = col - 1
# write header rows
for (a, b), band in [(k, v) for k, v in r1.items() if isinstance(k, tuple)]:
    wt.merge_cells(start_row=1, start_column=a, end_row=1, end_column=b)
    c = wt.cell(row=1, column=a, value=band); c.font = F(bold=True, color="FFFFFF"); c.fill = HDR; c.alignment = Alignment(horizontal="center", vertical="center")
for c_ in range(1, NCOL + 1): wt.cell(row=1, column=c_).fill = HDR; wt.cell(row=1, column=c_).border = BORDER
for keys, rescols, certcol, markcol, first, last in layout:
    wt.merge_cells(start_row=2, start_column=first, end_row=2, end_column=last)
for c_ in range(1, NCOL + 1):
    x = wt.cell(row=2, column=c_, value=r2.get(c_)); x.font = F(bold=True, size=9); x.fill = SUB; x.border = BORDER; x.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    y = wt.cell(row=3, column=c_, value=r3.get(c_)); y.font = F(italic=True, size=8); y.fill = BAND; y.border = BORDER; y.alignment = Alignment(wrap_text=True, vertical="center")
    z = wt.cell(row=4, column=c_, value=r4.get(c_)); z.font = F(bold=True, size=9); z.fill = SUB; z.border = BORDER; z.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
wt.row_dimensions[2].height = 54; wt.row_dimensions[3].height = 60; wt.row_dimensions[4].height = 28

def cite(row): return f"{row['code']}, ({row['date']}) [{row['lab']}]" + (" ᴿ" if row["kind"] == "Stability" else " ᴵ" if row["kind"] == "In-house" else "")
def res_style(row):
    k = {}
    if row["verdict"] == "OOS": k.update(bold=True, color=RED)
    if row["result"] == "held for review": k.update(fill=PatternFill("solid", fgColor=AMBER))
    if row["kind"] == "Stability": k.update(italic=True)
    return k

by_batch = collections.defaultdict(list)
for row in register: by_batch[row["cu"]].append(row)
r = 5
for b in batches:
    cu = b["cu"]; rows_b = by_batch[cu]
    # release row: for every key, the earliest release-eCoA row reporting it
    release = {}
    for row in sorted(rows_b, key=lambda x: dt(x["date"])):
        if row["kind"] == "eCoA" and row["key"] not in release: release[row["key"]] = row
    used = {id(v) for v in release.values()}
    others = collections.OrderedDict()   # (code,date,lab) -> rows
    for row in sorted(rows_b, key=lambda x: (dt(x["date"]), x["code"])):
        if id(row) not in used: others.setdefault((row["code"], row["date"], row["lab"], row["kind"]), []).append(row)
    miss = b["missing"]; n_miss = len(miss)
    status = ("✅ COMPLETE" if n_miss == 0 else f"{'⚠' if n_miss <= 3 else '❌'} {n_miss} MISSING: " + "; ".join("#" + m for m in miss))
    if b["oos"]: status += " • OOS: " + "; ".join(b["oos"])
    stab = [k for k, v in others.items() if k[3] == "Stability"]
    if stab: status += f" • {len(stab)} stability time-point certificate(s)"
    top = r
    cell(wt, r, 1, cu, bold=True); cell(wt, r, 2, b["p_batch"]); cell(wt, r, 3, status, wrap=True)
    for keys, rescols, certcol, markcol, first, last in layout:
        got = [release[k] for k in keys if k in release]
        for k in keys:
            if k in release: cell(wt, r, rescols[k], release[k]["result"], h="center", **res_style(release[k]))
            else: cell(wt, r, rescols[k], "— MISSING —" if b["flags"][PNUM[k].split(".")[0]] == "✗" else "—", color="808080", h="center")
        cell(wt, r, certcol, "; ".join(sorted({cite(x) for x in got})) if got else "— no certificate —", wrap=True, size=8)
        flag = b["flags"][PNUM[keys[0]].split(".")[0]]
        cell(wt, r, markcol, flag, h="center", fill=FILL[flag], bold=True)
    r += 1
    for (code, dte, lab, kind), rws in others.items():
        cell(wt, r, 1, cu, color="808080"); cell(wt, r, 2, ""); cell(wt, r, 3, {"Stability":"stability time-point ᴿ","In-house":"in-house document ᴵ"}.get(kind, "additional release certificate"), italic=True, color="595959")
        byk = {x["key"]: x for x in rws}
        for keys, rescols, certcol, markcol, first, last in layout:
            hit = [byk[k] for k in keys if k in byk]
            for k in keys:
                if k in byk: cell(wt, r, rescols[k], byk[k]["result"], h="center", **res_style(byk[k]))
                else: cell(wt, r, rescols[k], "")
            cell(wt, r, certcol, cite(hit[0]) if hit else "", wrap=True, size=8); cell(wt, r, markcol, "")
        r += 1
    for c_ in range(1, NCOL + 1): wt.cell(row=r - 1, column=c_).border = Border(left=thin, right=thin, top=thin, bottom=Side(style="medium", color=NAVY))
TR_LAST = r - 1
wt.column_dimensions["A"].width = 14; wt.column_dimensions["B"].width = 16; wt.column_dimensions["C"].width = 46
for keys, rescols, certcol, markcol, first, last in layout:
    for k in keys: wt.column_dimensions[L(rescols[k])].width = 11
    wt.column_dimensions[L(certcol)].width = 26; wt.column_dimensions[L(markcol)].width = 5
wt.auto_filter.ref = f"A4:{L(NCOL)}{TR_LAST}"; print_setup(wt, "D5")

# ------------------------------------------------------------------ Parameters (now that PCOL is known)
hdr(wp, 1, ["#","Parameter","Determination","Method","Acceptance criterion (global)","Source","Tracker column","Laboratories reporting it in eCoA_DB","Certificates with a value (n)"], height=30)
for i, p in enumerate(PARAMS, 2):
    src = "In-house (iCoA)" if p[3] in ("identA","identB","foreign") else "Outsourced certificate (eCoA)"
    for j, v in enumerate([p[0], p[1], p[2], p[4], p[5], src, PCOL.get(p[3], ""), ", ".join(sorted(labs_for[p[3]])), n_for[p[3]]], 1): cell(wp, i, j, v, wrap=True)
widths(wp, [6, 26, 30, 34, 40, 24, 9, 30, 12]); print_setup(wp, "A2")

# ------------------------------------------------------------------ Batch Coverage
wc = wb.create_sheet("Batch Coverage", 1)
PNAMES = ["1 Identification A — Appearance","2 Identification B — Microscopy","3 Identification C — HPLC","4 Assay — Total Δ⁹-THC","5 Assay — Total CBD","6 Total CBN","7 Foreign Matter","8 Loss on Drying","9 Microbiological Purity","10 Mycotoxins","11 Heavy Metals","12 Pesticide Residues"]
hdr(wc, 1, ["CU Batch","P Batch","Strain","Status"] + PNAMES + ["Missing (n)","Missing parameters","Certificates (n)","Labs present","OOS results (release + stability)","Stability certificates (n)","Name in owner's tracker","Batch key source"], height=44)
SHORTP = {"1":"#1 Ident. A","2":"#2 Ident. B","3":"#3 Ident. C","4":"#4 Δ⁹-THC","5":"#5 CBD","6":"#6 CBN","7":"#7 Foreign matter","8":"#8 LoD","9":"#9 Microbiology","10":"#10 Mycotoxins","11":"#11 Heavy metals","12":"#12 Pesticides"}
for i, b in enumerate(batches, 2):
    cell(wc, i, 1, b["cu"], bold=True); cell(wc, i, 2, b["p_batch"]); cell(wc, i, 3, b["strain"])
    wc.cell(row=i, column=4, value=f'=IF(Q{i}=0,"✅ COMPLETE",IF(Q{i}<=3,"⚠ "&Q{i}&" MISSING","❌ "&Q{i}&" MISSING"))').font = F(bold=True); wc.cell(row=i, column=4).border = BORDER
    for j, g in enumerate([str(n) for n in range(1, 13)], 5):
        fl = b["flags"][g]; cell(wc, i, j, fl, h="center", fill=FILL[fl], bold=True)
    wc.cell(row=i, column=17, value=f'=COUNTIF(E{i}:P{i},"✗")').border = BORDER; wc.cell(row=i, column=17).font = F(); wc.cell(row=i, column=17).alignment = Alignment(horizontal="center")
    cell(wc, i, 18, "; ".join(SHORTP[m] for m in b["missing"]), wrap=True)
    cell(wc, i, 19, len(b["docs"]), h="center")
    cell(wc, i, 20, "; ".join(f"[{k}] {v}" for k, v in sorted(b["labs"].items())), wrap=True)
    cell(wc, i, 21, "; ".join(b["oos"]), wrap=True, color=RED if b["oos"] else None)
    cell(wc, i, 22, sum(1 for d_ in b["docs"] if d_["kind_full"] == "Stability"), h="center")
    cell(wc, i, 23, b.get("owner_name", ""))
    cell(wc, i, 24, collections.Counter(d_["cu_source"] for d_ in b["docs"]).most_common(1)[0][0])
BC_LAST = len(batches) + 1
widths(wc, [14, 20, 20, 16] + [11] * 12 + [9, 34, 9, 30, 40, 10, 16, 22]); wc.auto_filter.ref = f"A1:X{BC_LAST}"; print_setup(wc, "E2")

# ------------------------------------------------------------------ Results Register
wr = wb.create_sheet("Results Register")
hdr(wr, 1, ["CU Batch","P Batch","Strain","#","Parameter","Determination","Result (as printed)","Value","Unit","Acceptance criterion","Verdict","Certificate","Date","Lab","Kind","File","RAGflow doc id"], height=30)
UNIT = {"thc":"% w/w","cbd":"% w/w","cbn":"% w/w","lod":"%","tamc":"CFU/g","tymc":"CFU/g","gnb":"CFU/g","afb1":"µg/kg","afsum":"µg/kg","ota":"µg/kg","pb":"mg/kg","cd":"mg/kg","as":"mg/kg","hg":"mg/kg"}
for i, row in enumerate(sorted(register, key=lambda x: (x["cu"], float(x["num"].split(".")[0]) + (float("0." + x["num"].split(".")[1]) if "." in x["num"] else 0), dt(x["date"]))), 2):
    vals = [row["cu"], row["p_batch"], row["strain"], row["num"], row["parameter"], row["determination"], row["result"], row["value"], UNIT.get(row["key"], ""), row["criterion"], row["verdict"], row["code"], dt(row["date"]), row["lab"], row["kind"], row["file"], row["doc_id"]]
    for j, v in enumerate(vals, 1):
        c = cell(wr, i, j, v, **({"color": RED, "bold": True} if row["verdict"] == "OOS" and j in (7, 8, 11) else {}))
        if j == 13: c.number_format = "DD.MM.YYYY"
        if j == 8 and isinstance(v, float): c.number_format = "0.####"
RR_LAST = len(register) + 1
widths(wr, [13, 18, 18, 5, 22, 30, 22, 9, 8, 30, 8, 18, 11, 8, 10, 46, 34]); wr.auto_filter.ref = f"A1:Q{RR_LAST}"; print_setup(wr, "A2")

# ------------------------------------------------------------------ eCOA Document Index
wi = wb.create_sheet("eCOA Document Index")
hdr(wi, 1, ["CU Batch","P Batch","Strain","Lab","Kind","Certificate code","Date","Parameters covered","Values held (n)","Chunks","Filename","RAGflow doc id","Batch key source","Notes"], height=30)
covered = collections.defaultdict(set)
for row in register: covered[row["doc_id"]].add("#" + row["num"].split(".")[0])
i = 2
for b in batches:
    for d_ in sorted(b["docs"], key=lambda x: dt(x["date"])):
        notes = "; ".join(d_["values"].get("notes", [])) if isinstance(d_["values"].get("notes"), list) else ""
        if not [k for k in d_["values"] if k not in ("notes","conformity","pest_n")]: notes = (notes + "; " if notes else "") + "no determination could be read from the text"
        vals = [b["cu"], b["p_batch"], b["strain"], d_["sub"] if d_["lab"] == "FHM" else d_["lab"], d_["kind_full"], d_["code"], dt(d_["date"]),
                ", ".join(sorted(covered[d_["doc_id"]], key=lambda s: int(s[1:]))), sum(1 for k in d_["values"] if k not in ("notes","conformity","pest_n","thc_pageread","thc_computed","cbd_pageread","cbd_computed")),
                d_.get("chunks", ""), d_["name"].split("/")[-1], d_["doc_id"], d_["cu_source"], notes]
        for j, v in enumerate(vals, 1):
            c = cell(wi, i, j, v, wrap=(j == 14))
            if j == 7: c.number_format = "DD.MM.YYYY"
        i += 1
DI_LAST = i - 1
widths(wi, [13, 18, 18, 8, 10, 22, 11, 22, 8, 7, 52, 34, 26, 50]); wi.auto_filter.ref = f"A1:N{DI_LAST}"; print_setup(wi, "A2")

# ------------------------------------------------------------------ Summary Dashboard
wd = wb.create_sheet("Summary Dashboard")
cell(wd, 1, 1, "eCOA DATABASE — CoQ PARAMETER COVERAGE DASHBOARD", bold=True, size=13)
cell(wd, 3, 1, "OVERVIEW", bold=True)
ov = [("Total batches", f"=COUNTA('Batch Coverage'!A2:A{BC_LAST})", None), ("Total eCOA documents", f"=COUNTA('eCOA Document Index'!A2:A{DI_LAST})", None),
      ("✅ COMPLETE (all 12 params)", f"=COUNTIF('Batch Coverage'!Q2:Q{BC_LAST},0)", "=IF(B4=0,0,B6/B4)"),
      ("⚠ PARTIAL (1–3 missing)", f"=COUNTIFS('Batch Coverage'!Q2:Q{BC_LAST},\">=1\",'Batch Coverage'!Q2:Q{BC_LAST},\"<=3\")", "=IF(B4=0,0,B7/B4)"),
      ("❌ INCOMPLETE (4+ missing)", f"=COUNTIF('Batch Coverage'!Q2:Q{BC_LAST},\">=4\")", "=IF(B4=0,0,B8/B4)"),
      ("Batches with an OOS result", f"=COUNTIF('Batch Coverage'!U2:U{BC_LAST},\"?*\")", None),
      ("Register rows (batch × determination × certificate)", f"=COUNTA('Results Register'!A2:A{RR_LAST})", None),
      ("Results held for review (page-read conflict)", f"=COUNTIF('Results Register'!G2:G{RR_LAST},\"held for review\")", None)]
for k, (lab, f1, f2) in enumerate(ov, 4):
    cell(wd, k, 1, lab); c = cell(wd, k, 2, f1, h="center")
    if f2: cell(wd, k, 3, f2, fmt="0%", h="center")
cell(wd, 13, 1, "MISSING PARAMETER FREQUENCY", bold=True); hdr(wd, 14, ["Parameter","Batches missing it (✗)","% of batches","Covered by release eCoA (✓)","Only stability (✓ᴿ)","Only in-house (✓ᴵ)"])
for k, name in enumerate(PNAMES, 15):
    colL = L(4 + k - 14)
    cell(wd, k, 1, name); cell(wd, k, 2, f"=COUNTIF('Batch Coverage'!{colL}2:{colL}{BC_LAST},\"✗\")", h="center"); cell(wd, k, 3, f"=IF($B$4=0,0,B{k}/$B$4)", fmt="0%", h="center")
    cell(wd, k, 4, f"=COUNTIF('Batch Coverage'!{colL}2:{colL}{BC_LAST},\"✓\")", h="center"); cell(wd, k, 5, f"=COUNTIF('Batch Coverage'!{colL}2:{colL}{BC_LAST},\"✓ᴿ\")", h="center"); cell(wd, k, 6, f"=COUNTIF('Batch Coverage'!{colL}2:{colL}{BC_LAST},\"✓ᴵ\")", h="center")
cell(wd, 28, 1, "CERTIFICATES BY LABORATORY", bold=True); hdr(wd, 29, ["Laboratory","Documents (n)","Stability time-points (n)"])
for k, lab in enumerate(["CNP","IJZ","IJZ-MB","FHM-K","FHM-M","FHM-LoD","DFL","NGP","PP"], 30):
    cell(wd, k, 1, lab); cell(wd, k, 2, f"=COUNTIF('eCOA Document Index'!D2:D{DI_LAST},\"{lab}\")", h="center"); cell(wd, k, 3, f"=COUNTIFS('eCOA Document Index'!D2:D{DI_LAST},\"{lab}\",'eCOA Document Index'!E2:E{DI_LAST},\"Stability\")", h="center")
widths(wd, [44, 18, 12, 24, 16, 16])

# ------------------------------------------------------------------ Data Quality
wq = wb.create_sheet("Data Quality")
i = 1
cell(wq, i, 1, "A. Page-read conflicts — HELD rows have no usable total; the others keep the printed total but their component cells are unreliable", bold=True); i += 1
hdr(wq, i, ["CU Batch","Certificate","Date","Lab","Determination","Page read","Computed from components","Note","File"]); i += 1
for b in batches:
    for d_ in b["docs"]:
        for note in d_["values"].get("notes", []):
            k = note.split(":")[0]
            for j, v in enumerate([b["cu"], d_["code"], d_["date"], d_["lab"], DETNAME.get(k, k), d_["values"].get(k + "_pageread"), d_["values"].get(k + "_computed"), note, d_["name"].split("/")[-1]], 1): cell(wq, i, j, v, wrap=(j == 8))
            i += 1
i += 1; cell(wq, i, 1, "B. Documents with no determination readable from the text", bold=True); i += 1
hdr(wq, i, ["CU Batch","Certificate","Date","Lab","File","What to do"]); i += 1
for b in batches:
    for d_ in b["docs"]:
        if not [k for k in d_["values"] if k not in ("notes","conformity","pest_n")]:
            for j, v in enumerate([b["cu"], d_["code"], d_["date"], d_["lab"], d_["name"].split("/")[-1], "Re-extract the page (300 DPI) or read it by hand; until then the batch has no value from this certificate."], 1): cell(wq, i, j, v, wrap=(j == 6))
            i += 1
i += 1; cell(wq, i, 1, "C. Batches known only by P batch (no CU batch printed on any certificate on file)", bold=True); i += 1
hdr(wq, i, ["Row key","Strain","Certificates (n)","Labs"]); i += 1
for b in batches:
    if b["cu"].startswith("P") and re.match(r'P\d{6}$', b["cu"]):
        for j, v in enumerate([b["cu"], b["strain"], len(b["docs"]), "; ".join(f"[{k}] {v}" for k, v in sorted(b["labs"].items()))], 1): cell(wq, i, j, v)
        i += 1
i += 1; cell(wq, i, 1, "D. Batch names — differences against the owner's Batch Coverage (v9)", bold=True); i += 1
hdr(wq, i, ["In this workbook","In the owner's tracker","P batch","Comment"]); i += 1
mine = {b["cu"] for b in batches} | {b["cu"].replace('＊','') for b in batches}
for b in batches:
    if b.get("owner_name"): 
        for j, v in enumerate([b["cu"], b["owner_name"], b["p_batch"], "Same P batch, different name — the certificate prints the name in column A."], 1): cell(wq, i, j, v, wrap=(j == 4))
        i += 1
for cu, rr in ref.items():
    if cu not in mine and cu + "＊" not in mine and not any(cu == b.get("owner_name") for b in batches):
        for j, v in enumerate(["—", cu, rr["p_batch"], "Row in the owner's tracker with no matching certificate in eCoA_DB under this name."], 1): cell(wq, i, j, v, wrap=(j == 4))
        i += 1
for b in batches:
    if b["cu"] not in ref and b["cu"].replace('＊','') not in ref and not b.get("owner_name"):
        for j, v in enumerate([b["cu"], "—", b["p_batch"], "Certificates on file in eCoA_DB; no row under this name in the owner's tracker."], 1): cell(wq, i, j, v, wrap=(j == 4))
        i += 1
i += 1; cell(wq, i, 1, "E. Values — differences against the owner's tracker for the same certificate (cannabinoids and LoD only; the owner's micro/metal cells could not be aligned automatically)", bold=True); i += 1
hdr(wq, i, ["CU Batch","Certificate","Date","Lab","Determination","This workbook (machine read)","Owner's tracker","File"]); i += 1
oracle = json.load(open("ref_oracle.json"))
def norm(x): return str(x).replace('%','').replace(' ','').replace('\\<','<').replace(',', '.').replace('ᴰ','').replace('ᴿ','').replace('**','').strip()
okeys = {tuple(k.split("|")): [norm(v) for v in oracle[k]] for k in oracle}
for b in batches:
    for d_ in b["docs"]:
        if d_["sub"] not in ("CNP","FHM-K","FHM-LoD"): continue
        key = (d_["code"], d_["date"], d_["sub"] if d_["lab"] == "FHM" else d_["lab"])
        if key not in okeys: continue
        ov = [o for o in okeys[key] if o and o not in ("Conforms","notonthiscertificate","notingested","heldforreview")]
        for k in ("thc","cbd","cbn","lod"):
            if k not in d_["values"]: continue
            n = norm(d_["values"][k])
            hit = n in ov or (n in ("BLQ","ND","<LOQ") and any(o in ("<LOQ","ND","BLQ") for o in ov)) or n == "heldforreview"
            if not hit and ov:
                for j, v in enumerate([b["cu"], d_["code"], d_["date"], key[2], DETNAME[k], d_["values"][k], " | ".join(ov), d_["name"].split("/")[-1]], 1): cell(wq, i, j, v)
                i += 1
i += 1; cell(wq, i, 1, "F. Agent spot-checks — gf_app_assistant (letta-6ou3, granted eCoA_DB) asked three questions on 04.09.2026; its cited answers against this workbook", bold=True); i += 1
hdr(wq, i, ["CU Batch","Certificate","Question","Agent answer (cited document)","This workbook","Agreement"]); i += 1
CHECKS = [
 ("BG1024","ППК25050 (CNP)","Total Δ⁹-THC, Total CBD, loss on drying","21,80 % · 0,04 % · 5,73 % — BG1024_ППК25050, 26.02.2025_CNP.pdf","21.80 · 0.04 · 5.73","✓ identical"),
 ("GP092501","88/2026 (IJZ)","Pb, Cd, As, Hg","0,022 · Н.д. · Н.д. · 0,007 mg/kg — P060092_88-2026, 03.02.2026_IJZ.pdf","0,022 · Н.д. · Н.д. · 0,007","✓ identical"),
 ("SCR112501","305-0549-26 (IJZ-MB)","TAMC, TYMC, conformity","2,3 x 10³ · 4,3 x 10³ CFU/g · conforms Ph.Eur. 5.1.8 cat. C — SCR112501_305-0549-26, 28.04.2026_IJZ-MB.pdf","2,3 x 10³ CFU/g · 4,3 x 10³ CFU/g · PASS","✓ identical"),
]
for row_ in CHECKS:
    for j, v in enumerate(row_, 1): cell(wq, i, j, v, wrap=True)
    i += 1
widths(wq, [16, 18, 30, 60, 40, 60, 52]); print_setup(wq, "A1")

wb.calculation.fullCalcOnLoad = True
wb.save("CoQ_Parameter_Tracker_eCoA_DB.xlsx")
print("saved; tracker rows", TR_LAST, "| coverage rows", BC_LAST - 1, "| register", RR_LAST - 1, "| index", DI_LAST - 1, "| tracker cols", NCOL)
