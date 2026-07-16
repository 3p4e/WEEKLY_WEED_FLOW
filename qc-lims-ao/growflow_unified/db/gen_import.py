import json, re, sys, uuid
D=sys.argv[1]
tasks=json.load(open(f"{D}/all_tasks.json"))["tasks"]
by_id={t["id"]:t for t in tasks}
children={}
for t in tasks:
    if t.get("parent_id"): children.setdefault(t["parent_id"],[]).append(t)

NS=uuid.UUID("b1b1b1b1-0000-4000-8000-0000000000ff")
QC_USER="b1b1b1b1-0000-4000-8000-0000000000a1"
def u5(*p): return str(uuid.uuid5(NS, ":".join(map(str,p))))
def q(s): return "NULL" if s is None else "'"+str(s).replace("'","''")+"'"
def arr(xs):
    xs=xs or []
    return "ARRAY[]::text[]" if not xs else "ARRAY["+",".join(q(x) for x in xs)+"]::text[]"

STATUS={"ongoing":"working","working":"working","completed":"done","done":"done","pending":"pending",
        "review":"review","stuck":"stuck","postponed":"postponed","blocked":"stuck","in_progress":"working"}
PRIORITY={"critical":"critical","high":"high","normal":"medium","medium":"medium","low":"low"}
st=lambda s:STATUS.get((s or "").lower(),"pending")
pr=lambda p:PRIORITY.get((p or "").lower(),"medium")
def blob(t): return " ".join([t.get("title") or "", t.get("description") or "", " ".join(t.get("tags") or [])])
is_sop=lambda t: bool(re.search(r'\bSOP\b|QASOP|QCSOP', blob(t), re.I))
def annex_ids(t):
    ids=set()
    for tg in (t.get("tags") or []):
        m=re.match(r'annex\s*0?(\d{1,2})$', tg.strip(), re.I)
        if m: ids.add(int(m.group(1)))
    for m in re.finditer(r'\bA0?(\d{1,2})\b', t.get("title") or ""): ids.add(int(m.group(1)))
    return sorted(ids)
def annex_num(title):
    m=re.search(r'\bA0?(\d{1,2})\b', title or ""); return int(m.group(1)) if m else None

def attrs(t):
    a={}
    tg=t.get("tags") or []
    prov=[x for x in tg if x.split(":")[0] in ("source","capture-batch-0000") or x.startswith(("source:","capture-v","drive-","consolidation","home-sweep","gap-reconcile"))]
    if prov: a["provenance"]=prov
    ws=[x.split("ws:")[1] for x in tg if x.startswith("ws:")]
    if ws: a["workstream"]=ws[0]
    eq=[x for x in tg if re.match(r'(EQP|EQ)[-_]', x)]
    if eq: a["equipment_id"]=eq[0]
    if "est-hours-unverified" in tg: a["est_hours_unverified"]=True
    ids=annex_ids(t)
    if ids: a["annex_ids"]=ids
    if t.get("estimated_hours") is not None: a["estimated_hours"]=t["estimated_hours"]
    return json.dumps(a, ensure_ascii=False)

DEPT={"Quality Control":("qc","Quality Control","Контрола на квалитет"),"QC":("qc","Quality Control","Контрола на квалитет"),
 "":("qc","Quality Control","Контрола на квалитет"),"Tooling":("tooling","Tooling","Алати"),
 "Production":("production","Production","Производство"),"Cultivation":("cultivation","Cultivation","Одгледување"),
 "Logistics":("logistics","Logistics","Логистика"),"Quality Assurance":("qa","Quality Assurance","Обезбедување квалитет")}
dkey=lambda t:DEPT.get((t.get("department") or "").strip(),DEPT["Quality Control"])[0]
dept_id=lambda k:u5("dept",k)
cre=lambda t:q(t.get("created_at"))
def end(t):
    base=t.get("completed_date") or t.get("updated_at") or t.get("created_at")
    return "NULL" if not base else f"(GREATEST(({q(base)})::timestamptz,({cre(t)})::timestamptz)+interval '1 hour')"

def row(tid,parent,dep,title,desc,status,priority,wk,days,tags,sop,ac,kind,c,e,attr):
    return (f"INSERT INTO planner_task(id,parent_id,department_id,owner_id,created_by,title,description,status,priority,"
            f"week_start,days,tags,node_kind,is_sop,annex_count,attributes,created_at,started_at,ended_at,updated_at,completed_at) VALUES "
            f"({q(tid)},{parent},{q(dep)},{q(QC_USER)},{q(QC_USER)},{q(title)},{q(desc)},{q(status)},{q(priority)},"
            f"{q(wk)},{arr(days)},{arr(tags)},{q(kind)},{str(sop).lower()},{ac},{q(attr)}::jsonb,{c},{c},{e},{c},"
            f"{('NULL' if status!='done' else c)}) ON CONFLICT (id) DO NOTHING;")

out=["BEGIN;"]
out.append(f"INSERT INTO app_user(id,username,full_name,role,is_active,password_hash) VALUES "
           f"({q(QC_USER)},{q('blagoj')},{q('Blagoj Nikolov')},'hod',true,crypt('ChangeMe!23',gen_salt('bf'))) ON CONFLICT (username) DO NOTHING;")
seen=set()
for t in tasks:
    k,en,mk=DEPT.get((t.get("department") or "").strip(),DEPT["Quality Control"])
    if k not in seen:
        seen.add(k); out.append(f"INSERT INTO planner_department(id,key,name_en,name_mk) VALUES ({q(dept_id(k))},{q(k)},{q(en)},{q(mk)}) ON CONFLICT (key) DO NOTHING;")

# annex_nodes: (annex_id, status, wk, dep, created, end, parent_is_sop)
annex_nodes=[]
for t in tasks:
    kind="task"
    if t.get("parent_id"):
        kind="annex" if re.search(r'annex',(t.get("title") or ""),re.I) else "task"
    dep=dept_id(dkey(t)); wk=t.get("week_start"); ids=annex_ids(t)
    out.append(row(t["id"],q(t.get("parent_id")),dep,t["title"],t.get("description"),st(t.get("status")),pr(t.get("priority")),
                   wk,t.get("days"),t.get("tags"),is_sop(t),len(ids),kind,cre(t),end(t),attrs(t)))
    if kind=="annex":
        psop=is_sop(by_id.get(t.get("parent_id"),{}))
        annex_nodes.append((t["id"],st(t.get("status")),wk,dep,cre(t),end(t),psop))
    for i,pn in enumerate(t.get("progress_notes") or []):
        note=pn if isinstance(pn,str) else (pn.get("note") or pn.get("text") or json.dumps(pn)); day=None if isinstance(pn,str) else pn.get("day")
        out.append(f"INSERT INTO planner_progress_note(id,task_id,day,note,author_id) VALUES ({q(u5('pn',t['id'],i))},{q(t['id'])},{q(day)},{q(note)},{q(QC_USER)}) ON CONFLICT (id) DO NOTHING;")

# materialize missing annexes (depth = real need: annexes are real)
for t in tasks:
    ids=annex_ids(t)
    if not ids: continue
    exist={annex_num(c["title"]) for c in children.get(t["id"],[])}
    dep=dept_id(dkey(t)); wk=t.get("week_start"); c=cre(t); e=end(t); psop=is_sop(t); pstat=st(t.get("status"))
    for n in ids:
        if n in exist: continue
        aid=u5("annex",t["id"],n)
        out.append(row(aid,q(t["id"]),dep,f"Annex A{n:02d} — {t['title'][:48]}",f"Annex A{n:02d} of: {t['title']}",pstat,pr(t.get("priority")),
                       wk,[],["generated-annex","annex"],False,0,"annex",c,e,json.dumps({"annex_no":n})))
        annex_nodes.append((aid,pstat,wk,dep,c,e,psop))

# ADAPTIVE depth (1..3 by the NATURE of the node, never forced uniform):
#   - a task with no annexes stays a leaf            -> depth 1
#   - a non-SOP annex is an attachment, stays a leaf -> depth 2
#   - an SOP annex is a CONTROLLED DOCUMENT, so it carries the GMP document
#     lifecycle Draft -> Review -> Approve (author / reviewer / QP)  -> depth 3
# Completion does not delete the lifecycle; it sets the step STATUS, so a
# completed annex keeps a full, done audit trail (ALCOA+ / 21 CFR Part 11).
LIFECYCLE=[("Draft","Author the controlled annex document."),
           ("Review","Independent review of the annex."),
           ("Approve","QP/Manager approval and effective release.")]
steps=0
def sstat(p,i): return "done" if p=="done" else (["done","working","pending"][i] if p in ("working","review") else "pending")
for (aid,astat,wk,dep,c,e,psop) in annex_nodes:
    if not psop: continue
    steps+=1
    for i,(name,desc) in enumerate(LIFECYCLE):
        out.append(row(u5("step",aid,name),q(aid),dep,name,desc,sstat(astat,i),"medium",wk,[],
                       ["generated-step","lifecycle"],False,0,"step",c,e,
                       json.dumps({"lifecycle":name.lower(),"position":i})))
# Link the Head of QC to the Quality Control department (for report headers etc.).
out.append("UPDATE app_user SET dept_id=(SELECT id FROM planner_department WHERE key='qc') WHERE username='blagoj' AND dept_id IS NULL;")
out.append("COMMIT;")
import sys as _s; _s.stderr.write(f"annexes with steps: {steps}\n")
print("\n".join(out))
