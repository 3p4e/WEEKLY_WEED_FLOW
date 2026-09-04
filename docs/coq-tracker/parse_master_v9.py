# Read CoQ_Analysis_Master_v9.xlsx (the owner's layout) into a canonical model: batches, labs, parameters, certificates, results.
import json, re, sys, collections
from datetime import datetime, date
from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string as CI, get_column_letter as L

SRC = sys.argv[1] if len(sys.argv) > 1 else "/w/CoQ_Analysis_Master_v9.xlsx"
wb = load_workbook(SRC, data_only=True)

# ---- Parameters sheet -> 21 determinations with the tracker column letter
P = wb["Parameters"]; params = []
for r in range(2, P.max_row + 1):
    if not P.cell(row=r, column=1).value: break
    params.append({"num": str(P.cell(row=r, column=1).value).strip(), "parameter": P.cell(row=r, column=2).value, "determination": P.cell(row=r, column=3).value,
                   "method": P.cell(row=r, column=4).value, "criterion": P.cell(row=r, column=5).value, "source": P.cell(row=r, column=6).value, "col": (P.cell(row=r, column=7).value or "").strip()})
# ---- Batch Coverage -> batch master
BC = wb["Batch Coverage"]; hdr = [BC.cell(row=1, column=c).value for c in range(1, BC.max_column + 1)]
batches = []
for r in range(2, BC.max_row + 1):
    cu = BC.cell(row=r, column=1).value
    if not cu: break
    row = {hdr[c-1]: BC.cell(row=r, column=c).value for c in range(1, BC.max_column + 1)}
    batches.append({"cu": str(cu).strip(), "p_batch": row.get("P Batch"), "strain": row.get("Strain"), "status": row.get("Status"),
                    "flags": {str(i): row.get(h) for i, h in enumerate(hdr[4:16], 1)}, "missing_n": row.get("Missing (n)"), "missing": row.get("Missing parameters"),
                    "certs_n": row.get("Certificates (n)"), "labs": row.get("Labs present")})

# ---- Tracker: column map from header row 4 (Result / citation / mark) and row 2 (#n); group columns for 9/10/11
T = wb["CoQ Parameter Tracker v9"]
r2 = {c: T.cell(row=2, column=c).value for c in range(1, T.max_column + 1)}
r4 = {c: T.cell(row=4, column=c).value for c in range(1, T.max_column + 1)}
groups = []   # {num, cols:{det_key: col}, cite_col, mark_col, cite_in_next_row}
c = 4
while c <= T.max_column:
    h2 = r2.get(c)
    if h2 and str(h2).startswith("#"):
        num = re.match(r'#(\d+)', str(h2)).group(1)
        cols = {}; cc = c
        while cc <= T.max_column and (r4.get(cc) not in ("[eCOA code],[date],[Lab] ", "✓   ✗")):
            cols[str(r4.get(cc)).strip()] = cc; cc += 1
        cite_col = cc if r4.get(cc) == "[eCOA code],[date],[Lab] " else None
        if cite_col: cc += 1
        mark_col = cc if r4.get(cc) == "✓   ✗" else None
        groups.append({"num": num, "cols": cols, "cite_col": cite_col, "mark_col": mark_col, "first": c}); c = cc + 1
    else:
        c += 1
DET = {"1": {"Result": "identA"}, "2": {"Result": "identB"}, "3": {"Result": "identC"}, "4": {"Result": "thc"}, "5": {"Result": "cbd"}, "6": {"Result": "cbn"}, "7": {"Result": "foreign"}, "8": {"Result": "lod"},
       "9": {"TAMC": "tamc", "TYMC": "tymc", "GNB": "gnb", "Salm.": "salm", "E. coli": "ecoli"}, "10": {"AfB₁": "afb1", "ΣAf": "afsum", "OTA": "ota"}, "11": {"Pb": "pb", "Cd": "cd", "As": "as", "Hg": "hg"}, "12": {"Result": "pest"}}
CITE = re.compile(r'^\s*(?P<code>.+?),\s*\((?P<date>\d{2}\.\d{2}\.\d{4})\)\s*\[(?P<lab>[A-Za-z\-]+)\](?P<extra>.*)$')
def parse_cite(v):
    if not v: return None
    m = CITE.match(str(v))
    if not m: return {"raw": str(v)}
    d = m.groupdict(); d["extra"] = d["extra"].strip(" ·"); return d

# batch blocks: a block starts at a row with a CU batch in col A; ends before the next
starts = [r for r in range(5, T.max_row + 1) if T.cell(row=r, column=1).value not in (None, "")]
results, certs, block_rows = [], {}, []
NONE_VALUES = {"— MISSING —", "— no certificate —", "not on this certificate", "not ingested", "held for review", "•", "", None}
for i, s in enumerate(starts):
    e = starts[i + 1] - 1 if i + 1 < len(starts) else T.max_row
    cu = str(T.cell(row=s, column=1).value).strip(); pb = T.cell(row=s, column=2).value; status = T.cell(row=s, column=3).value
    nrows = 0
    for r in range(s, e + 1):
        if all(T.cell(row=r, column=c).value in (None, "") for c in range(1, T.max_column + 1)): continue
        nrows += 1
        for g in groups:
            cite_v = T.cell(row=r, column=g["cite_col"]).value if g["cite_col"] else None
            # groups 9/10/11 carry the citation on the NEXT non-empty row under the first result column
            if not g["cite_col"]:
                below = T.cell(row=r + 1, column=g["first"]).value
                cite_v = below if below and CITE.match(str(below)) else None
            cite = parse_cite(cite_v)
            mark = T.cell(row=r, column=g["mark_col"]).value if g["mark_col"] else None
            for label, col in g["cols"].items():
                v = T.cell(row=r, column=col).value
                if v in NONE_VALUES: continue
                if isinstance(v, str) and CITE.match(v): continue   # a citation sitting in a result column (rows below)
                key = DET[g["num"]].get(label)
                sval = str(v).strip()
                flags = {"stability": "ᴿ" in sval, "derived": "ᴰ" in sval}
                sval_clean = sval.replace("ᴿ", "").replace("ᴰ", "").strip()
                results.append({"cu": cu, "p_batch": pb, "num": g["num"], "det": key, "label": label, "value": sval_clean, "flags": flags,
                                "cert": cite, "mark": mark if mark in ("✓", "✗", "•") else None, "row": r, "block_row": s})
                if cite and "code" in cite:
                    k = (cite["code"], cite["date"], cite["lab"]); certs.setdefault(k, {"code": cite["code"], "date": cite["date"], "lab": cite["lab"], "batches": set(), "dets": set()})
                    certs[k]["batches"].add(cu); certs[k]["dets"].add(key)
    block_rows.append({"cu": cu, "p_batch": pb, "status": status, "rows": nrows, "first_row": s})

# ---- Mikro sheet (physical + microbiology tracker) — count blocks only for now
MK = wb["Mikro CoQ Parameter"]; mk_blocks = [r for r in range(5, MK.max_row + 1) if MK.cell(row=r, column=1).value not in (None, "")]
# ---- Work Order / Credit Corrections / Credit Audit sizes
def n_rows(ws): return sum(1 for r in range(2, ws.max_row + 1) if ws.cell(row=r, column=1).value not in (None, ""))
out = {"source": SRC, "params": params, "batches": batches, "blocks": block_rows, "results": results,
       "certificates": [{**v, "batches": sorted(v["batches"]), "dets": sorted(d for d in v["dets"] if d)} for v in certs.values()],
       "columns": {g["num"]: {"cols": {k: L(c) for k, c in g["cols"].items()}, "cite": L(g["cite_col"]) if g["cite_col"] else None, "mark": L(g["mark_col"]) if g["mark_col"] else None} for g in groups},
       "sheets": {"mikro_blocks": len(mk_blocks), "credit_audit": n_rows(wb["Credit Audit"]), "credit_corrections": n_rows(wb["Credit Corrections"]), "work_order": n_rows(wb["Work Order"])}}
json.dump(out, open("/w/master_v9.json", "w"), ensure_ascii=False, indent=1, default=str)
C = collections.Counter
print("params:", len(params), "| coverage batches:", len(batches), "| tracker blocks:", len(block_rows), "| results:", len(results), "| certificates cited:", len(certs))
print("columns:", json.dumps(out["columns"]))
print("results per det:", dict(sorted(C(r["det"] for r in results).items(), key=lambda x: str(x[0]))))
print("results without a parsable citation:", sum(1 for r in results if not r["cert"] or "code" not in r["cert"]))
print("labs:", dict(C(v["lab"] for v in certs.values())))
print("stability-marked results:", sum(1 for r in results if r["flags"]["stability"]), "| derived-marked:", sum(1 for r in results if r["flags"]["derived"]))
print("marks:", dict(C(r["mark"] for r in results)))
print("sheets:", out["sheets"])
print("sample BG1024:", [(r["det"], r["value"], r["cert"] and r["cert"].get("code"), r["mark"]) for r in results if r["cu"] == "BG1024"][:12])
print("blocks with >4 rows:", [(b["cu"], b["rows"]) for b in block_rows if b["rows"] > 4][:10])
tracker_cus = {b["cu"] for b in block_rows}; cov_cus = {b["cu"] for b in batches}
print("in coverage not tracker:", sorted(cov_cus - tracker_cus)[:20]); print("in tracker not coverage:", sorted(tracker_cus - cov_cus)[:20])
