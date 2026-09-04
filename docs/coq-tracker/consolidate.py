# Consolidate per-document extractions into per-batch records, coverage and a flat register.
import json, re, collections
from datetime import datetime

recs = json.load(open("extracted.json"))
ref = json.load(open("ref_coverage.json"))
ref_p2cu = collections.defaultdict(set)
for cu, r in ref.items():
    for p in re.findall(r'P\d{6}', r["p_batch"]): ref_p2cu[p].add(cu)

def dt(s): return datetime.strptime(s, "%d.%m.%Y")

# ---- P batch -> CU batch consensus from the certificates themselves
cands = collections.defaultdict(collections.Counter)
for r in recs:
    if r["p_batch"] and r["cu_text"]: cands[r["p_batch"]][r["cu_text"]] += 1
p2cu, p2cu_src = {}, {}
for p, c in cands.items():
    stems = collections.Counter()
    for name, n in c.items(): stems[re.sub(r'_\d+$', '', name)] += n
    stem = stems.most_common(1)[0][0]
    withsuffix = [nm for nm in c if nm.startswith(stem + "_")]
    p2cu[p] = max(withsuffix, key=lambda nm: (c[nm], len(nm))) if withsuffix else stem
    p2cu_src[p] = "certificate text"
for p, cus in ref_p2cu.items():
    if p not in p2cu and len(cus) == 1:
        p2cu[p] = next(iter(cus)); p2cu_src[p] = "owner's tracker (Batch Coverage)"

# ---- assign every document to a batch key
for r in recs:
    if r["p_batch"]:
        cu = p2cu.get(r["p_batch"])
        r["cu_batch"] = cu or r["p_batch"]
        r["cu_source"] = p2cu_src.get(r["p_batch"], "P batch only (no CU batch found)")
    else:
        r["cu_batch"] = r["file_batch_raw"]
        r["cu_source"] = "filename"
    r["p_batches"] = [r["p_batch"]] if r["p_batch"] else []

# ---- batches
batches = collections.OrderedDict()
for r in sorted(recs, key=lambda r: (r["cu_batch"], dt(r["date"]))):
    b = batches.setdefault(r["cu_batch"], {"cu": r["cu_batch"], "p_batches": set(), "strains": collections.Counter(), "docs": []})
    b["p_batches"].update(r["p_batches"]); b["docs"].append(r)
    if r["strain"]: b["strains"][r["strain"]] += 1
for cu, b in batches.items():
    refrow = ref.get(cu) or ref.get(cu.replace('＊',''))
    if not b["p_batches"] and refrow: b["p_batches"].update(re.findall(r'P\d{6}', refrow["p_batch"]))
    b["p_batch"] = " / ".join(sorted(b["p_batches"])) or ("— not assigned —" if not cu.startswith("P") else cu)
    b["strain"] = (b["strains"].most_common(1)[0][0] if b["strains"] else (refrow["strain"] if refrow else ""))
    b["ref"] = refrow
    owner_names = sorted({cu2 for p in b["p_batches"] for cu2 in ref_p2cu.get(p, ())} | ({cu} if refrow else set()))
    b["owner_name"] = ", ".join(n for n in owner_names if n != cu and n != cu.replace('＊','')) or ""
    first = min(dt(r["date"]) for r in b["docs"] if r["kind"] == "eCoA") if any(r["kind"] == "eCoA" for r in b["docs"]) else min(dt(r["date"]) for r in b["docs"])
    for r in b["docs"]:
        # a laboratory certificate issued 9+ months after the batch's first certificate is a stability time-point, not a release result
        r["stability"] = r["kind"] == "eCoA" and (dt(r["date"]) - first).days >= 270   # any laboratory, not only FHM
        r["kind_full"] = "Stability" if r["stability"] else r["kind"]

# ---- determinations, acceptance criteria and OOS evaluation
PARAMS = [  # (#, parameter, determination, key, method, criterion text, criterion evaluator)
 ("1","Identification A — Appearance","Identification A, Appearance · Macroscopic","identA","Ph. Eur. mon. 3028","Conforms to Ph. Eur. monograph 3028 (Cannabis flos)"),
 ("2","Identification B — Microscopy","Identification B · Microscopic","identB","Ph. Eur. 2.8.23 (microscopy)","Conforms to Ph. Eur. monograph 3028 (Cannabis flos)"),
 ("3","Identification C — HPLC","Identification C · HPLC/HPTLC","identC","Ph. Eur. 2.2.29 (3028)","Conforms to Ph. Eur. monograph 3028 (Cannabis flos)"),
 ("4","Assay — Total Δ⁹-THC","Assay — Total Δ⁹-THC","thc","Ph. Eur. 2.2.29 (HPLC)","Per target grade (CoQ §01)"),
 ("5","Assay — Total CBD","Assay — Total CBD","cbd","Ph. Eur. 2.2.29 (HPLC) · CBD + CBDA x 0.877","≤ 1.0 % w/w"),
 ("6","Total CBN","Total CBN","cbn","Ph. Eur. 2.2.29 (HPLC) · CBN + CBNA x 0.876","≤ 1.0 % w/w"),
 ("7","Foreign Matter","Foreign Matter","foreign","Ph. Eur. 2.8.2 · In-house","≤ 2.0 % (25–50 g); leaves < 1 cm; no seeds"),
 ("8","Loss on Drying","Loss on Drying","lod","Ph. Eur. 2.2.32 (3028) · at 40 °C, 24 h, 15–25 mbar","≤ 12.0 %"),
 ("9.1","Microbiological Purity","TAMC","tamc","Ph. Eur. 2.6.12 cat. C","≤ 10⁵ CFU/g (max. acceptable count 2 × 10⁵, Ph. Eur. 5.1.4)"),
 ("9.2","Microbiological Purity","TYMC","tymc","Ph. Eur. 2.6.12 cat. C","≤ 10⁴ CFU/g (max. acceptable count 2 × 10⁴, Ph. Eur. 5.1.4)"),
 ("9.3","Microbiological Purity","Bile-tolerant gram-negative bacteria","gnb","Ph. Eur. 2.6.31 cat. C","≤ 10⁴ CFU/g"),
 ("9.4","Microbiological Purity","Salmonella","salm","Ph. Eur. 2.6.31 cat. C","Absence / 25 g"),
 ("9.5","Microbiological Purity","Escherichia coli","ecoli","Ph. Eur. 2.6.13 cat. C","Absence / 1 g"),
 ("10.1","Mycotoxins","Aflatoxin B₁","afb1","Ph. Eur. 2.8.18 (HPLC-FLD)","≤ 2 µg/kg"),
 ("10.2","Mycotoxins","Aflatoxins ∑ (B₁+B₂+G₁+G₂)","afsum","Ph. Eur. 2.8.18 (HPLC-FLD)","≤ 4 µg/kg"),
 ("10.3","Mycotoxins","Ochratoxin A","ota","Ph. Eur. 2.8.22 (HPLC-FLD)","≤ 20 µg/kg"),
 ("11.1","Heavy Metals","Lead (Pb)","pb","Ph. Eur. 2.4.27 (ICP-MS)","≤ 0.5 mg/kg"),
 ("11.2","Heavy Metals","Cadmium (Cd)","cd","Ph. Eur. 2.4.27 (ICP-MS)","≤ 0.3 mg/kg"),
 ("11.3","Heavy Metals","Arsenic (As)","as","Ph. Eur. 2.4.27 (ICP-MS)","≤ 0.2 mg/kg"),
 ("11.4","Heavy Metals","Mercury (Hg)","hg","Ph. Eur. 2.4.27 (ICP-MS)","≤ 0.1 mg/kg"),
 ("12","Pesticide Residues","Pesticide Residues","pest","Ph. Eur. 2.8.13 (LC-MS/MS) · CUMCS Equivalency","≤ LOQ (Ph. Eur. 2.8.13 / CUMCS equivalency)"),
]
LIMITS = {"cbd":1.0,"cbn":1.0,"lod":12.0,"tamc":2e5,"tymc":2e4,"gnb":1e4,"afb1":2,"afsum":4,"ota":20,"pb":0.5,"cd":0.3,"as":0.2,"hg":0.1}
SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")

def to_number(key, raw):
    """numeric value or None; CFU strings like '1,6 x 10⁴ CFU/g' -> 16000"""
    if raw is None: return None
    s = str(raw).translate(SUPER).replace('CFU/g','').replace('%','').replace('µg/kg','').replace('μg/kg','').replace('mg/kg','').strip()
    s = s.replace('х','x').replace('×','x').replace('•','x').replace('·','x').replace('^','')
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*x\s*10\s*(\d+)', s)
    if m: return float(m.group(1).replace(',', '.')) * 10 ** int(m.group(2))
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)', s)
    if m: return float(m.group(1).replace(',', '.'))
    return None

def evaluate(key, raw):
    """'PASS' / 'OOS' / 'n.e.' (not evaluable) against the global criterion"""
    if raw is None: return None
    s = str(raw).strip()
    if key in ("identA","identB","identC","foreign"): return "PASS" if re.search(r'conform|одговара|confirm', s, re.I) else "n.e."
    if key in ("salm","ecoli"): return "PASS" if re.search(r'одговара|отсутна|absent|absen|conform|negative|не е', s, re.I) else ("OOS" if re.search(r'присутна|present|detected|positive', s, re.I) else "n.e.")
    if key == "pest": return "OOS" if s.startswith("DETECTED") else "PASS"
    if key == "thc": return "n.e."
    if s == "held for review": return "n.e."
    if re.match(r'^(ND|N\.D\.|BLQ|<|≤|н\.д\.|Н\.Д\.|Н\.д\.)', s, re.I): return "PASS"
    n = to_number(key, s)
    if n is None: return "n.e."
    return "OOS" if n > LIMITS.get(key, float('inf')) else "PASS"

register = []
for cu, b in batches.items():
    for r in b["docs"]:
        for p in PARAMS:
            key = p[3]
            if key in r["values"]:
                raw = r["values"][key]
                register.append({"cu": cu, "p_batch": b["p_batch"], "strain": b["strain"], "num": p[0], "parameter": p[1], "determination": p[2], "key": key,
                                 "result": raw, "value": to_number(key, raw), "criterion": p[5], "verdict": evaluate(key, raw),
                                 "code": r["code"], "date": r["date"], "lab": r["sub"] if r["lab"]=="FHM" else r["lab"], "kind": r["kind_full"], "file": r["name"].split("/")[-1], "doc_id": r["doc_id"]})

# ---- coverage per batch: ✓ (release eCoA), ✓ᴿ (stability only), ✓ᴵ (in-house only), ✗
GROUPS = [("1",["identA"]),("2",["identB"]),("3",["identC"]),("4",["thc"]),("5",["cbd"]),("6",["cbn"]),("7",["foreign"]),("8",["lod"]),
          ("9",["tamc","tymc","gnb","salm","ecoli"]),("10",["afb1","afsum","ota"]),("11",["pb","cd","as","hg"]),("12",["pest"])]
for cu, b in batches.items():
    b["flags"] = {}
    for g, keys in GROUPS:
        kinds = {row["kind"] for row in register if row["cu"] == cu and row["key"] in keys}
        b["flags"][g] = "✓" if "eCoA" in kinds else "✓ᴿ" if "Stability" in kinds else "✓ᴵ" if "In-house" in kinds else "✗"
    b["missing"] = [g for g, _ in GROUPS if b["flags"][g] == "✗"]
    b["oos"] = sorted({f"#{row['num']} {row['determination']} = {row['result']} ({row['code']})" for row in register if row["cu"] == cu and row["verdict"] == "OOS"})
    b["labs"] = collections.Counter((r["sub"] if r["lab"]=="FHM" else r["lab"]) for r in b["docs"])

out = {"batches": [{k: (sorted(v) if isinstance(v, set) else v) for k, v in b.items() if k not in ("strains",)} for b in batches.values()],
       "register": register, "params": PARAMS, "p2cu": p2cu, "p2cu_src": p2cu_src}
for b in out["batches"]:
    b["docs"] = [{k: v for k, v in r.items() if k != "values"} | {"values": r["values"]} for r in b["docs"]]
json.dump(out, open("consolidated.json","w"), ensure_ascii=False, indent=1, default=list)
print("batches:", len(batches), "| register rows:", len(register))
print("stability-flagged docs:", sum(1 for r in recs if r.get("stability")))
C = collections.Counter(len(b["missing"]) for b in batches.values()); print("missing-count distribution:", dict(sorted(C.items())))
print("OOS batches:", [(b["cu"], b["oos"]) for b in batches.values() if b["oos"]])
print("batches by key:", ", ".join(f"{cu}[{b['p_batch']}]" for cu, b in batches.items()))
notref = [cu for cu in batches if cu not in ref and cu.replace('＊','') not in ref]; print("batches not in owner's coverage:", notref)
notmine = [cu for cu in ref if cu not in batches and cu + "＊" not in batches]; print("owner batches not derived from eCoA_DB:", notmine)
