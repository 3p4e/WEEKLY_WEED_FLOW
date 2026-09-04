# Parse the eCOA_DB certificate text (RAGflow chunks) into per-document determinations. v2
import json, re, collections

NAME_RE = re.compile(r'^(?:eCoA_DATABASE/)?(?P<batch>[A-Z0-9]+[＊*]?(?:_\d{1,2}V?)?)_(?P<code>[^,]+), (?P<date>\d{2}\.\d{2}\.\d{4})_(?P<lab>[A-Z\-]+)\.pdf$')
SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
# Cyrillic look-alikes inside Latin abbreviations (ТАМС -> TAMC, СВD -> CBD ...)
LOOK = str.maketrans("АВСЕНКМОРТХУ", "ABCEHKMOPTXY")
def latinize(s):
    return re.sub(r'[A-Za-zА-Я]{2,}', lambda m: m.group(0).translate(LOOK) if re.search(r'[A-Za-z]', m.group(0)) or m.group(0) in ("ТАМС","ТУМС","ТАМC","ТYМС","СВD","ТНС") else m.group(0), s)

def clean(v):
    if v is None: return None
    v = re.sub(r'<br\s*/?>|&nbsp;', ' ', v)
    return re.sub(r'\s+', ' ', v).strip(' |').replace('**','').replace('*','').strip()

def num(s):
    if s is None: return None
    t = str(s).replace('%','').replace(' ','').replace(' ','').replace(' ', '')
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)', t)
    return float(m.group(1).replace(',', '.')) if m else None

def rows(t):
    """table rows from lines containing '|' (with or without border pipes)"""
    for line in t.split('\n'):
        if '|' in line and not re.match(r'^\s*\|?\s*-{2,}', line):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) >= 2: yield cells

RES_TOKEN = r'(\d+[.,]\d+\s*%?|BLQ|ND|\(Одговара\)|Одговара|/)'
LINE_TOKEN = re.compile(r'^\s*(\d+[.,]\d+\s*%|BLQ|ND|\(Одговара\)|Одговара|/)\s*$', re.M)

def parse_cnp(t, v):
    tt = latinize(t)
    got = {}
    labels = [("Губиток (?:при|со) сушење","lod"), ("Содржина на CBDA","cbda"), ("Содржина на CBN","cbn"), ("Содржина на Δ9-THCA","thca"),
              ("Содржина на Δ9-THC","thc_raw"), ("Содржина на CBD","cbd_raw"), ("Вкупно CBD","cbd"), ("Вкупно Δ9-THC","thc"), ("Вкупно CBN","cbn"),
              ("Макроскопија","identA"), ("Микроскопија","identB"), ("Страни материи","foreign")]
    # 1. table rows — a cell may pack several bullet labels separated by <br>; expand them in order
    cbd_seen = 0
    expanded = []
    for cells in rows(tt):
        if '<br' in cells[0]:
            labs_ = [re.sub(r'^[•\s]+', '', x).strip() for x in re.split(r'<br\s*/?>', cells[0])]
            labs_ = [x for x in labs_ if x and not re.match(r'^(Идентификација|Содржина на канабиноиди|\(изразено)', x)]
            ress_ = [x.strip() for x in re.split(r'<br\s*/?>', cells[-1]) if x.strip()]
            if len(labs_) == len(ress_):
                expanded += [[a, b] for a, b in zip(labs_, ress_)]; continue
        expanded.append(cells)
    for cells in expanded:
        label = cells[0]; res = next((c for c in reversed(cells[1:]) if c.strip()), None)
        if not res: continue
        for lab, key in labels:
            if re.match(lab, label):
                if key == "cbd_raw":
                    cbd_seen += 1
                    if cbd_seen == 1 and not any(re.match("Содржина на CBDA", c[0]) for c in rows(tt)): key = "cbda"
                got[key] = clean(res); break
    # 2. inline lines (no pipes): "Вкупно Δ9-THC*   мин. 5.00 %    21.92 %"
    if "thc" not in got:
        for lab, key in labels:
            for m in re.finditer(r'^[ \t•]*' + lab + r'[^\n]*?' + RES_TOKEN + r'\s*$', tt, re.M):
                line = m.group(0)
                if re.search(r'(макс|мин|≤)\.?\s*\d+[.,]\d+\s*%?\s*$', line): continue   # limit only, no result
                got.setdefault(key, clean(m.group(1)))
    # 3. stacked layout: results block after the limits block
    if "thc" not in got:
        seg = tt[tt.find("Параметар"):] if "Параметар" in tt else tt
        seg = seg.split("Аналитичар")[0]
        toks = [m.group(1).strip() for m in LINE_TOKEN.finditer(seg)]
        labs = [k for k, pat in [("identA","Макроскопија"),("identB","Микроскопија"),("foreign","Страни материи"),("lod","Губиток (?:при|со) сушење"),
                                  ("cbn","Вкупно CBN"),("cbd","Вкупно CBD"),("thc","Вкупно Δ9-THC")] if re.search(pat, seg)]
        # foreign matter may produce two tokens ('/' and '(Одговара)')
        if "foreign" in labs and "/" in toks and "(Одговара)" in toks:
            toks = [x for x in toks if x != "/"]
        if len(toks) == len(labs):
            for k, x in zip(labs, toks): got.setdefault(k, clean(x))
    for k, x in got.items():
        v[k] = x
    for k in ("identA","identB"):
        if v.get(k) == "Одговара": v[k] = "Conforms"
    if v.get("foreign") in ("(Одговара)", "/ (Одговара)", "Одговара"): v["foreign"] = "Conforms"
    v["notes"] = []
    for tot, free, acid in (("thc","thc_raw","thca"), ("cbd","cbd_raw","cbda")):
        if tot in v and free in v and acid in v:
            f, a, tv = num(v[free]) or 0.0, num(v[acid]), num(v[tot])
            if a is not None and tv is not None:
                calc = f + 0.877 * a
                if tv < 0.877 * a - 0.5:
                    # the printed total cannot be lower than what its own acid component implies: a digit was lost in the page read
                    v["notes"].append(f"{tot}: HELD — page read {v[tot]} is below what the certificate's components imply ({v[free]} + 0.877 x {v[acid]} = {calc:.2f})")
                    v[tot + "_pageread"] = v[tot]; v[tot + "_computed"] = f"{calc:.2f}"; v[tot] = "held for review"
                elif abs(calc - tv) > 0.5:
                    v["notes"].append(f"{tot}: total {v[tot]} kept; the components as read ({v[free]}, {v[acid]}) do not reproduce it ({calc:.2f}) — component cells are unreliable, total matches the printed figure")
                    v[tot + "_pageread"] = v[tot]; v[tot + "_computed"] = f"{calc:.2f}"
    if not v["notes"]: del v["notes"]
    if "thc" in v or "cbd" in v: v["identC"] = "Conforms"

def parse_ijz(t, v):
    tt = latinize(t)
    for cells in rows(tt):
        lab = cells[0].replace('*','').strip().lower(); res = cells[1] if len(cells) > 1 else ""
        for k, key in (("олово","pb"),("кадмиум","cd"),("арсен","as"),("жива","hg")):
            if lab.startswith(k) and res: v[key] = clean(res)
        if re.search(r'вкупни афлатоксини|total aflatox', lab) and res: v["afsum"] = clean(res)
        elif re.search(r'афлатоксин\s*b\s*1|aflatoxin b1', lab) and res: v["afb1"] = clean(res)
        elif re.search(r'охратоксин|ochratoxin', lab) and res: v["ota"] = clean(res)
    if "pb" not in v:
        for k, key in (("олово","pb"),("кадмиум","cd"),("арсен","as"),("жива","hg")):
            m = re.search(r'\*?\s*' + k + r'\s+([<]?\s*\d+[.,]\d+|н\.д\.)', tt, re.I)
            if m: v[key] = clean(m.group(1))
    if "afsum" not in v:
        m = re.search(r'Вкупни афлатоксини[^\n|]*?\|?\s*([<≤]\s*\d+[.,]?\d*|\d+[.,]\d+|н\.д\.|ND)\s*\|?\s*[μµ]g/kg', tt, re.I)
        if m: v["afsum"] = clean(m.group(1))
    # pesticides: section from ПЕСТИЦИДИ to МЕТАЛИ/МИКОТОКСИНИ; count compound rows
    comp = []
    sec = re.split(r'ТЕШКИ МЕТАЛИ|МЕТАЛИ\n|МИКОТОКСИНИ', tt)[0] if "ПЕСТИЦИДИ" in tt else tt
    for cells in rows(sec):
        if len(cells) >= 3 and re.search(r'mg/[kK]g', " ".join(cells)) and re.match(r'[A-Za-z0-9]', cells[0].replace('*','').strip()):
            comp.append((cells[0].replace('*','').strip(), cells[1].strip()))
    comp += re.findall(r'^\s*\*?\s*([A-Za-z][A-Za-z0-9 ,\'\(\)\-\+\.]+?)\s{1,}(н\.д\.|Н\.д\.|Н\.Д\.|ND|<\s*\d+[.,]\d+|\d+[.,]\d+)\s+mg/[kK]g', tt, re.M)
    comp = [(a, b) for a, b in comp if not re.match(r'(Резултат|vkupno|вкупно)', a, re.I)]
    if comp:
        nd = [c for c in comp if re.match(r'(н\.д\.|Н\.д\.|Н\.Д\.|ND|<)', c[1].strip())]
        det = [c for c in comp if c not in nd and num(c[1]) is not None]
        v["pest_n"] = str(len(comp))
        v["pest"] = f"≤ LOQ (all {len(comp)} compounds)" if not det else "DETECTED: " + "; ".join(f"{a} {b} mg/kg" for a, b in det)
    conf = re.findall(r'(?:ОДГОВАРА НА|СОГЛАСНОСТ со барањата на):\s*\n?\s*(Ph\.? ?Eur\.?[^\n]*)', tt)
    if conf: v["conformity"] = "; ".join(sorted(set(c.strip() for c in conf)))

def parse_ijzmb(t, v):
    tt = latinize(t).translate(SUB)
    m = re.search(r'Параметар(.*?)ЗАКЛУЧОК', tt, re.S)
    body = m.group(1) if m else tt
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    inline = [l for l in lines if re.search(r'CFU/g.*CFU/g|отсутна/\s*g\s+\S|отсутна/\s*25\s*g\s+\S', l)]
    if len(inline) >= 3:
        flat = " ".join(lines)
        def grab(label_re):
            mm = re.search(label_re + r'.*?-\s*[<≤]?\s*10[⁰-⁹\d^]*\s*CFU/g\s*\|?\s*(.*?CFU/g)', flat)
            return clean(mm.group(1)) if mm else None
        x = grab(r'TAMC|аеробни'); v["tamc"] = x or v.get("tamc")
        x = grab(r'TYMC|габи'); v["tymc"] = x or v.get("tymc")
        x = grab(r'грам-негативни'); v["gnb"] = x or v.get("gnb")
        mm = re.search(r'Escherichia coli\s*\|?\s*-\s*отсутна/\s*g\s*\|?\s*(\S+)', flat); v["ecoli"] = clean(mm.group(1)) if mm else v.get("ecoli")
        mm = re.search(r'Salmonella\s*\|?\s*-\s*отсутна/\s*25\s*g\s*\|?\s*(\S+)', flat); v["salm"] = clean(mm.group(1)) if mm else v.get("salm")
    else:
        # stacked or interleaved: classify every line as label / specification / result
        body_lines = [l for l in lines if not re.match(r'^(Параметар|Спецификација|Резултат)\s*$', l)]
        res = []
        for l in body_lines:
            if re.search(r'бактери|габи|мувли|грам-негативни|Escherichia|Salmonella', l): continue      # label
            if re.match(r'^-\s', l): continue   # specification lines always start with '-'
            res.append(l)
        if len(res) == 5:
            for k, x in zip(("tamc","tymc","gnb","ecoli","salm"), res): v[k] = clean(x)
    v = {k: x for k, x in v.items() if x}
    if re.search(r'(ОДГОВАРА на барањата|СЕ ВО СОГЛАСНОСТ)', tt): v["conformity"] = "Conforms Ph.Eur. 5.1.8 cat. C"
    elif re.search(r'НЕ ОДГОВАРА|НЕ СЕ ВО СОГЛАСНОСТ', tt): v["conformity"] = "DOES NOT CONFORM"
    return v

def parse_fhm(t, v, code):
    tt = latinize(t).translate(SUB)
    kind = None
    for cells in rows(tt):
        first = cells[0].lower(); res = cells[2] if len(cells) > 2 else ""
        if re.search(r'tetrahydro|thc', first): v["thc"] = clean(res); kind = "K"
        elif re.search(r'cannabidiol', first): v["cbd"] = clean(res); kind = "K"
        elif re.search(r'cannabinol', first): v["cbn"] = clean(res); kind = "K"
        elif re.search(r'aflatoxin b1', first): v["afb1"] = clean(cells[1]); kind = "M"
        elif re.search(r'aflatoxin b2', first): v["afb2"] = clean(cells[1])
        elif re.search(r'aflatoxin g1', first): v["afg1"] = clean(cells[1])
        elif re.search(r'aflatoxin g2', first): v["afg2"] = clean(cells[1])
        elif re.search(r'ochratoxin', first): v["ota"] = clean(cells[1]); kind = "M"
        elif re.search(r'губитоци при сушење|\(lod\)', first): v["lod"] = clean(cells[1]); kind = "LoD"
    if kind is None:   # whitespace-aligned layouts (no pipes)
        tt2 = tt.replace('∆', 'Δ')
        for pat, key in ((r'Tetrahydrocannabinol\s+Total\s*Δ9-?\s*THC\s+(<\s*LOQ|ND|\d+[.,]\d+)', "thc"), (r'Cannabidiol\s+Total CBD\s+(<\s*LOQ|ND|\d+[.,]\d+)', "cbd"),
                         (r'Cannabinol\s+Total CBN\s+(<\s*LOQ|ND|\d+[.,]\d+)', "cbn")):
            m = re.search(pat, tt2)
            if m: v[key] = clean(m.group(1)); kind = "K"
        for pat, key in ((r'Aflatoxin B1\s+(ND|<\s*LOQ|\d+[.,]\d+)', "afb1"), (r'Aflatoxin B2\s+(ND|<\s*LOQ|\d+[.,]\d+)', "afb2"), (r'Aflatoxin G1\s+(ND|<\s*LOQ|\d+[.,]\d+)', "afg1"),
                         (r'Aflatoxin G2\s+(ND|<\s*LOQ|\d+[.,]\d+)', "afg2"), (r'Ochratoxin A\s+(ND|<\s*LOQ|\d+[.,]\d+)', "ota")):
            m = re.search(pat, tt2)
            if m: v[key] = clean(m.group(1)); kind = "M"
        m = re.search(r'сушење \(LoD\)\s+(\d+[.,]\d+)', tt2)
        if m: v["lod"] = clean(m.group(1)); kind = "LoD"
    if kind == "M":
        parts = [v.get(k) for k in ("afb1","afb2","afg1","afg2")]
        if parts[0] and all(p and re.match(r'ND|<', p) for p in parts if p): v["afsum"] = "ND"
        elif any(p and num(p) is not None for p in parts): v["afsum"] = str(round(sum(num(p) or 0 for p in parts), 3))
    if kind == "K": v["identC"] = "Conforms"
    if kind is None:
        kind = "K" if re.search(r'-K-?\d*$', code) else "M" if re.search(r'-M-?\d*$', code) else "LoD" if "LoD" in code else None
    return kind

def parse_ngp(t, v):
    m = re.search(r'Total THC \(w/w\):\s*([\d.,]+)', t)
    if m: v["thc"] = m.group(1)
    m = re.search(r'Total CBD \(w/w\):\s*([\d.,]+)', t)
    if m: v["cbd"] = m.group(1)
    m = re.search(r'Average LOD \(%\)\s*\n?\s*([\d.,]+)', t)
    if m: v["lod"] = m.group(1)
    v["cbn"] = "held for review"   # the F3 form's per-cannabinoid column order is ambiguous in the page read; owner's tracker holds it for review too
    if v.get("thc"): v["identC"] = "Conforms"

def parse_pp(t, v):
    flat = re.sub(r'[ \t]+', ' ', t)
    def cell(label):
        m = re.search(r'\|\s*' + label + r'[^|]*\|[^|]*\|\s*([^|]+?)\s*\|', flat)
        return clean(m.group(1)) if m else None
    for label, key in ((r'Appearance','identA'), (r'Identification','identC'), (r'Foreign matter','foreign'), (r'- Total Δ⁹-tetrahydrocannabinol\*?','thc'),
                       (r'- Total Cannabidiol','cbd'), (r'- Cannabinol','cbn'), (r'- Total aflatoxines','afsum')):
        x = cell(label)
        if x: v[key] = x
    for lab, key in (("Cadmium","cd"),("Lead","pb"),("Mercury","hg"),("Arsenic","as")):
        m = re.search(r'-\s*' + lab + r'\s*<\s*[\d.]+ mg/kg\s*([\d.]+|N\.D\.|ND)\s*mg/kg', flat)
        if m: v[key] = m.group(1)
    m = re.search(r'\(TAMC\)[^\n]*?CFU/g\s*([\d.,•x×·]+\s*10[⁰-⁹\d^]*)\s*CFU/g', flat)
    if m: v["tamc"] = clean(m.group(1))
    m = re.search(r'\(TYMC\)[^\n]*?CFU/g\s*([\d.,•x×·]+\s*10[⁰-⁹\d^]*)\s*CFU/g', flat)
    if m: v["tymc"] = clean(m.group(1))
    m = re.search(r'gram-negative bacteria\s*<10[⁰-⁹\d^]*\s*CFU/g\s*([^\n]+?CFU/g)', flat)
    if m: v["gnb"] = clean(m.group(1))
    m = re.search(r'Escherichia coli/g To be absent\s*(\w+)', flat)
    if m: v["ecoli"] = m.group(1)
    m = re.search(r'Salmonella/25g To be absent\s*(\w+)', flat)
    if m: v["salm"] = m.group(1)
    nd = len(re.findall(r'N\.D\.', flat))
    if nd: v["pest"] = f"N.D. (all {nd} compounds listed)"; v["pest_n"] = str(nd)
    m = re.search(r'Loss on drying[^|]*\|[^|]*\|\s*([^|]+?)\s*\|', flat, re.I)
    if m: v["lod"] = clean(m.group(1))
    for k in ("identA","identC","foreign"):
        if v.get(k, "").lower().startswith("confirm"): v[k] = "Conforms"

def parse_dfl(t, v):
    if re.search(r'Нема пронајдено ниту еден пестицид над LOQ|No pesticide[^\n]*above (the )?LOQ|not (been )?detected above|None of the pesticides', t, re.I): v["pest"] = "<LOQ (471 residues screened)"; v["pest_n"] = "471"
    else:
        m = re.search(r'\|\s*\d+\s*\|\s*([A-Za-z][^|]+?)\s*\|[^|]*\|[^|]*\|\s*([\d.,]+)\s*\|', t)
        if m: v["pest"] = f"DETECTED: {m.group(1)} {m.group(2)} mg/kg"

CU_TOKEN = r'([A-Z]{2,4})\s?(\d{4,6})((?:_\d{1,2})?)'
def cu_from_text(t):
    tt = latinize(t)
    pats = [r'[Сс]ер[иј]+а:\s*' + CU_TOKEN, r'Сериски број:\s*' + CU_TOKEN, r'Batch [Nn]o\.?[^\n]*\n?\s*' + CU_TOKEN, r'Batch No:\s*' + CU_TOKEN,
            r'\|\s*[A-Za-z][A-Za-z ]+?\s' + CU_TOKEN + r'\s*\|', r'^\s*[A-Za-z][A-Za-z ]+?\s' + CU_TOKEN + r'\s*$', r'([A-Z]{2,4})\s(\d{6})()\s*\n']
    for p in pats:
        m = re.search(p, tt, re.M)
        if m:
            return (m.group(1) + m.group(2) + m.group(3)).replace('＊','')
    return None

def strain_from_text(t):
    for p in [r'сорта\s+([A-Za-z][A-Za-z ]+?),', r'Примерок:\s*([A-Za-z][A-Za-z ]+?)\s*-', r'Примерок за тестирање:\s*([A-Za-z][A-Za-z ]+?)\s*-',
              r'Variety/Strain:\s*([A-Za-z][A-Za-z ]+)', r'\|\s*([A-Za-z][A-Za-z ]+?)\s[A-Z]{1,4}\s?\d{4,6}', r'Batch no\.[^\n]*\n\s*[A-Z]{2,4}\d{4,6}\s*-\s*([A-Za-z ]+)']:
        m = re.search(p, t)
        if m: return re.sub(r'\s+', ' ', m.group(1)).strip().title()
    return None

KIND = {"CNP":"eCoA","IJZ":"eCoA","IJZ-MB":"eCoA","FHM":"eCoA","DFL":"eCoA","NGP":"In-house","PP":"In-house"}
def parse_doc(x):
    m = NAME_RE.match(x["name"]); assert m, x["name"]
    t = "\n".join(c["content"] for c in x["chunks"])
    lab, code, date, fbatch = m["lab"], m["code"], m["date"], m["batch"]
    v = {}; sub = lab
    if lab == "CNP": parse_cnp(t, v)
    elif lab == "IJZ": parse_ijz(t, v)
    elif lab == "IJZ-MB": v = parse_ijzmb(t, v)
    elif lab == "FHM": k = parse_fhm(t, v, code); sub = f"FHM-{k or '?'}"
    elif lab == "NGP": parse_ngp(t, v)
    elif lab == "PP": parse_pp(t, v)
    elif lab == "DFL": parse_dfl(t, v)
    v = {k: x for k, x in v.items() if x}
    cu = cu_from_text(t)
    p_batch = fbatch if re.match(r'P\d{6}$', fbatch) else None
    if cu and re.match(r'P\d{6}$', cu): cu = None   # certificate names the P batch, not the CU batch
    return {"doc_id": x["doc_id"], "name": x["name"], "file_batch": fbatch.replace('＊',''), "file_batch_raw": fbatch, "cu_text": cu, "p_batch": p_batch,
            "strain": strain_from_text(t), "code": code, "date": date, "lab": lab, "sub": sub, "kind": KIND[lab], "values": v, "chars": len(t)}

if __name__ == "__main__":
    d = json.load(open("ecoa_db_chunks.json"))
    recs = [parse_doc(x) for x in d]
    json.dump(recs, open("extracted.json","w"), ensure_ascii=False, indent=1)
    C = collections.Counter; per = collections.defaultdict(C); n = C()
    for r in recs:
        n[r["sub"]] += 1
        for k in r["values"]: per[r["sub"]][k] += 1
    for s in sorted(per): print(s, n[s], dict(per[s]))
    empty = [r["name"] for r in recs if not r["values"]]
    print("docs with NO values:", len(empty)); print("\n".join(empty))
    print("P-batch docs without CU in text:", sum(1 for r in recs if r["p_batch"] and not r["cu_text"]))
    pmap = collections.defaultdict(C)
    for r in recs:
        if r["p_batch"] and r["cu_text"]: pmap[r["p_batch"]][r["cu_text"]] += 1
    print("P->CU:", {k: dict(v) for k, v in sorted(pmap.items())})
    mism = [(r["name"], r["cu_text"]) for r in recs if not r["p_batch"] and r["cu_text"] and r["cu_text"] != r["file_batch"]]
    print("CU-named docs whose text batch differs:", mism)
