import json, re, sys, uuid, datetime
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
SOP=re.compile(r'\bSOP\b|QASOP|QCSOP', re.I)
is_sop=lambda t: bool(SOP.search(blob(t)))
def annex_ids(t):
    ids=set()
    for tg in (t.get("tags") or []):
        m=re.match(r'annex\s*0?(\d{1,2})$', tg.strip(), re.I)
        if m: ids.add(int(m.group(1)))
    for m in re.finditer(r'\bA0?(\d{1,2})\b', t.get("title") or ""):
        ids.add(int(m.group(1)))
    return sorted(ids)
def annex_num_in_title(title):
    m=re.search(r'\bA0?(\d{1,2})\b', title or ""); return int(m.group(1)) if m else None

DEPT={  # source label -> (key, en, mk)
 "Quality Control":("qc","Quality Control","Контрола на квалитет"),
 "QC":("qc","Quality Control","Контрола на квалитет"),
 "":("qc","Quality Control","Контрола на квалитет"),
 "Tooling":("tooling","Tooling","Алати"),
 "Production":("production","Production","Производство"),
 "Cultivation":("cultivation","Cultivation","Одгледување"),
 "Logistics":("logistics","Logistics","Логистика"),
 "Quality Assurance":("qa","Quality Assurance","Обезбедување квалитет")}
def dept_key(t): return DEPT.get((t.get("department") or "").strip(), DEPT["Quality Control"])[0]
dept_id=lambda key: u5("dept",key)

def end_ts(t):
    base=t.get("completed_date") or t.get("updated_at") or t.get("created_at")
    cre=t.get("created_at")
    if not base: return "NULL"
    # end = max(completed/updated, created) + 1h, so end is always >= start+1h
    return f"(GREATEST(({q(base)})::timestamptz, ({q(cre)})::timestamptz) + interval '1 hour')"
def created_ts(t): return q(t.get("created_at"))

out=[]
W=out.append
W("BEGIN;")
W(f"INSERT INTO app_user(id,username,full_name,role,is_active,password_hash) "
  f"VALUES ({q(QC_USER)},{q('blagoj')},{q('Blagoj Nikolov')},'hod',true,crypt('ChangeMe!23',gen_salt('bf'))) "
  f"ON CONFLICT (username) DO NOTHING;")
seen={}
for t in tasks:
    k,en,mk=DEPT.get((t.get("department") or "").strip(), DEPT["Quality Control"])
    if k not in seen:
        seen[k]=True
        W(f"INSERT INTO planner_department(id,key,name_en,name_mk) VALUES ({q(dept_id(k))},{q(k)},{q(en)},{q(mk)}) ON CONFLICT (key) DO NOTHING;")

def task_row(tid,parent,dept,title,desc,status,priority,wk,days,tags,sop,acount,kind,cat,end):
    return (f"INSERT INTO planner_task(id,parent_id,department_id,owner_id,created_by,title,description,"
            f"status,priority,week_start,days,tags,node_kind,is_sop,annex_count,created_at,started_at,ended_at,updated_at,completed_at) "
            f"VALUES ({q(tid)},{parent},{q(dept)},{q(QC_USER)},{q(QC_USER)},{q(title)},{q(desc)},"
            f"{q(status)},{q(priority)},{q(wk)},{arr(days)},{arr(tags)},{q(kind)},{str(sop).lower()},{acount},"
            f"{cat},{cat},{end},{cat},{('NULL' if status!='done' else cat)}) ON CONFLICT (id) DO NOTHING;")

# 1) source tasks (preserve real parent_id tree: 149 top + 46 subtasks)
annex_nodes=[]   # (annex_task_id, status, week, dept, created, end) to generate steps under
for t in tasks:
    ids=annex_ids(t); kind="task"
    if t.get("parent_id"):
        kind="annex" if re.search(r'annex',(t.get("title") or ""),re.I) else "subtask"
    dep=dept_id(dept_key(t))
    wk=t.get("week_start")
    W(task_row(t["id"], q(t.get("parent_id")), dep, t["title"], t.get("description"),
               st(t.get("status")), pr(t.get("priority")), wk, t.get("days"), t.get("tags"),
               is_sop(t), len(ids), kind, created_ts(t), end_ts(t)))
    if kind=="annex":
        annex_nodes.append((t["id"], st(t.get("status")), wk, dep, created_ts(t), end_ts(t)))
    # progress notes
    for i,pn in enumerate(t.get("progress_notes") or []):
        note=pn if isinstance(pn,str) else (pn.get("note") or pn.get("text") or json.dumps(pn))
        day=None if isinstance(pn,str) else pn.get("day")
        W(f"INSERT INTO planner_progress_note(id,task_id,day,note,author_id) VALUES "
          f"({q(u5('pn',t['id'],i))},{q(t['id'])},{q(day)},{q(note)},{q(QC_USER)});")

# 2) materialize missing annexes under the 25 annex-bearing parents
for t in tasks:
    ids=annex_ids(t)
    if not ids: continue
    existing={annex_num_in_title(c["title"]) for c in children.get(t["id"],[])}
    dep=dept_id(dept_key(t)); wk=t.get("week_start"); cat=created_ts(t); end=end_ts(t); pstat=st(t.get("status"))
    for n in ids:
        if n in existing: continue
        aid=u5("annex",t["id"],n)
        W(task_row(aid, q(t["id"]), dep, f"Annex A{n:02d} — {t['title'][:48]}", f"Annex A{n:02d} derived from task: {t['title']}",
                   pstat, pr(t.get("priority")), wk, [], ["generated-annex","annex"], False, 0, "annex", cat, end))
        annex_nodes.append((aid, pstat, wk, dep, cat, end))

# 3) generate Draft/Review/Approve sub-subtasks under every annex node
def step_status(parent_status, step_idx):
    if parent_status=="done": return "done"
    if parent_status in ("working","review"):
        return ["done","working","pending"][step_idx]
    return "pending"
for (aid,astat,wk,dep,cat,end) in annex_nodes:
    for i,name in enumerate(["Draft","Review","Approve"]):
        W(task_row(u5("step",aid,name), q(aid), dep, f"{name}", f"{name} the annex.",
                   step_status(astat,i), "medium", wk, [], ["generated-step"], False, 0, "step", cat, end))
W("COMMIT;")
print("\n".join(out))
