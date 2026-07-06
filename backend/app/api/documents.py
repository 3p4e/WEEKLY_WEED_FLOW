"""Weekly Plan & Report DOCUMENTS — compile → review → lock → export.

The weekly report stops being a transient screen: POST /compile assembles a
stored document for the Fri→Thu week — the full task listing (complete
descriptions, parameters, start date+hour, progress notes), the work-session
RIBBON (7 days × 24h, every logged session stretched over its real local-time
extent, color-keyed by SOP reference code), metrics derived from it (per-SOP
hours + 4-week trend, off-hours split, on-time rate, complexity signals), and
AI-drafted narrative sections from the org's bound Letta agents. The user
reviews the draft (PATCH: edits + approves AI sections), then LOCKS it as the
submitted record — immutable at the app layer, covered by the audit trigger —
and exports a PDF at any point (draft exports watermark unapproved content).

Evidence rule: the report ribbon only ever shows REAL logged work sessions —
nothing is fabricated from schedules. The plan document carries the task
listing and AI plan sections; a scheduled-projection ribbon is future work.
"""
import html
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.api.ai import _letta_message
from app.api.reports import _COLS, _fri_thu, _task_row
from app.db import rls
from app.deps import require_password_set, require_role
from app.roles import ADMIN, ELEVATED_ROLES
from app.roster import roster
from app.worktime import TZ, classify, session_hours

router = APIRouter(prefix="/reports/documents", tags=["documents"])

_ELEVATED = ELEVATED_ROLES

# Stable SOP color palette (hash-assigned, mirrors the frontend's) — the color
# coding IS the metric key: everything per-SOP hangs off reference_code.
_PALETTE = ["#15A86B", "#2F6BFF", "#FF7A1A", "#7A5BE0", "#D6336C", "#0EA5A5",
            "#C2410C", "#0891B2", "#8B5CF6", "#F59E0B", "#10B981", "#EF4444"]


def _sop_color(sop: str) -> str:
    h = 7
    for ch in sop:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return _PALETTE[h % len(_PALETTE)]


def _iso(v) -> str | None:
    return v.isoformat() if v is not None else None


async def _fetch_window_tasks(c, fri: date, thu: date, kind: str) -> list[dict]:
    if kind == "report":
        rows = await c.fetch(
            f"SELECT {_COLS} FROM tasks t "
            f"WHERE t.is_deleted=false "
            f"AND ("
            f"  ((t.created_at AT TIME ZONE $3) >= $1::date AND (t.created_at AT TIME ZONE $3) < ($2::date + 1))"
            f"  OR ((t.updated_at AT TIME ZONE $3) >= $1::date AND (t.updated_at AT TIME ZONE $3) < ($2::date + 1))"
            f"  OR (t.completed_date >= $1 AND t.completed_date <= $2)"
            f"  OR EXISTS (SELECT 1 FROM task_progress tp WHERE tp.task_id=t.id "
            f"             AND (tp.created_at AT TIME ZONE $3) >= $1::date AND (tp.created_at AT TIME ZONE $3) < ($2::date + 1))"
            f"  OR EXISTS (SELECT 1 FROM work_sessions ws WHERE ws.task_id=t.id "
            f"             AND (ws.started_at AT TIME ZONE $3) >= $1::date AND (ws.started_at AT TIME ZONE $3) < ($2::date + 1))"
            f") ORDER BY t.department, t.created_at",
            fri, thu, TZ.key)
    else:  # plan: everything active/incomplete carrying into the week
        rows = await c.fetch(
            f"SELECT {_COLS} FROM tasks t "
            f"WHERE t.is_deleted=false AND t.is_archived=false AND t.status <> 'completed' "
            f"ORDER BY t.department, t.created_at")
    return [_task_row(r) for r in rows]


async def _attach_notes(c, tasks: list[dict]) -> None:
    ids = [t["id"] for t in tasks]
    if not ids:
        return
    notes = await c.fetch(
        "SELECT task_id, day_label, note, user_id, created_at FROM task_progress"
        " WHERE task_id = ANY($1::uuid[]) ORDER BY created_at", ids)
    by_task: dict[str, list] = {}
    for n in notes:
        by_task.setdefault(str(n["task_id"]), []).append({
            "day": n["day_label"], "note": n["note"],
            "user_id": str(n["user_id"]) if n["user_id"] else None,
            "at": _iso(n["created_at"]),
        })
    for t in tasks:
        t["notes"] = by_task.get(t["id"], [])


async def _fetch_sessions(c, start: date, end: date) -> list:
    """Work sessions whose facility-local start falls in [start, end]."""
    return await c.fetch(
        "SELECT ws.id, ws.task_id, ws.user_id, ws.started_at, ws.ended_at, ws.hours,"
        "       t.title, t.reference_code, t.department, t.department_id"
        " FROM work_sessions ws JOIN tasks t ON t.id = ws.task_id"
        " WHERE (ws.started_at AT TIME ZONE $3) >= $1::date"
        "   AND (ws.started_at AT TIME ZONE $3) < ($2::date + 1)",
        start, end, TZ.key)


def _ribbon_segments(sessions) -> list[dict]:
    """Local-time segments for the 7×24h ribbon; split at midnight so every
    segment lives inside one day row. SOP falls back to the department name
    so unreferenced work still lands on the ribbon (colored, legend-labeled)."""
    segs = []
    for s in sessions:
        start = s["started_at"].astimezone(TZ)
        if s["ended_at"] is not None:
            end = s["ended_at"].astimezone(TZ)
        elif s["hours"] is not None:
            end = start + timedelta(hours=float(s["hours"]))
        else:
            end = start + timedelta(minutes=30)
        if end <= start:
            end = start + timedelta(minutes=15)
        sop = s["reference_code"] or (s["department"] or "—")
        while start.date() != end.date() and end > start:
            day_end = datetime.combine(start.date() + timedelta(days=1), datetime.min.time(), tzinfo=start.tzinfo)
            segs.append(_seg(s, sop, start, day_end))
            start = day_end
        segs.append(_seg(s, sop, start, end))
    return segs


def _seg(s, sop: str, start, end) -> dict:
    return {
        "task_id": str(s["task_id"]), "title": s["title"], "sop": sop,
        "color": _sop_color(sop), "dept": s["department"],
        "user_id": str(s["user_id"]) if s["user_id"] else None,
        "date": start.date().isoformat(),
        "start_h": round(start.hour + start.minute / 60, 2),
        "end_h": round(min(24.0, end.hour + end.minute / 60 + (24.0 if end.date() > start.date() else 0)), 2),
        "start": start.isoformat(), "end": end.isoformat(),
        "hours": round((end - start).total_seconds() / 3600, 2),
    }


def _metrics(tasks: list[dict], sessions, prior_sessions) -> dict:
    per_sop: dict[str, dict] = {}
    for s in sessions:
        sop = s["reference_code"] or (s["department"] or "—")
        b = per_sop.setdefault(sop, {"sop": sop, "color": _sop_color(sop), "hours": 0.0,
                                     "sessions": 0, "tasks": set(),
                                     "night": 0.0, "weekend": 0.0, "overtime": 0.0,
                                     "prev4_avg_hours": 0.0})
        h = session_hours(s)
        b["hours"] += h
        b["sessions"] += 1
        b["tasks"].add(str(s["task_id"]))
        cls = classify(s["started_at"])
        if cls in ("night", "weekend", "overtime"):
            b[cls] += h
    prior: dict[str, float] = {}
    for s in prior_sessions:
        sop = s["reference_code"] or (s["department"] or "—")
        prior[sop] = prior.get(sop, 0.0) + session_hours(s)
    for sop, b in per_sop.items():
        b["tasks"] = len(b["tasks"])
        b["prev4_avg_hours"] = round(prior.get(sop, 0.0) / 4, 2)
        for k in ("hours", "night", "weekend", "overtime"):
            b[k] = round(b[k], 2)

    per_dept: dict[str, dict] = {}
    for s in sessions:
        dn = s["department"] or "—"
        d = per_dept.setdefault(dn, {"name": dn, "hours": 0.0, "sessions": 0})
        d["hours"] = round(d["hours"] + session_hours(s), 2)
        d["sessions"] += 1

    completed = [t for t in tasks if t["status"] == "completed"]
    on_time = [t for t in completed
               if not t["due_date"] or (t["completed_date"] and t["completed_date"] <= t["due_date"])]
    overdue_open = [
        {"id": t["id"], "title": t["title"], "due_date": t["due_date"],
         "age_days": (date.today() - date.fromisoformat(t["due_date"])).days}
        for t in tasks
        if t["due_date"] and t["status"] != "completed" and date.fromisoformat(t["due_date"]) < date.today()
    ]

    complexity = []
    sess_by_task: dict[str, int] = {}
    for s in sessions:
        sess_by_task[str(s["task_id"])] = sess_by_task.get(str(s["task_id"]), 0) + 1
    for t in tasks:
        ratio = (round(t["actual_hours"] / t["estimated_hours"], 2)
                 if t["estimated_hours"] and t["actual_hours"] else None)
        complexity.append({
            "id": t["id"], "title": t["title"],
            "est_ratio": ratio, "sessions": sess_by_task.get(t["id"], 0),
            "notes": len(t.get("notes", [])),
        })
    complexity.sort(key=lambda x: -(x["est_ratio"] or 0))

    return {
        "per_sop": sorted(per_sop.values(), key=lambda b: -b["hours"]),
        "per_dept": sorted(per_dept.values(), key=lambda d: -d["hours"]),
        "on_time": {"completed": len(completed), "on_time": len(on_time),
                    "rate": round(len(on_time) / len(completed), 2) if completed else None},
        "overdue_open": sorted(overdue_open, key=lambda o: -o["age_days"]),
        "complexity": complexity[:15],
    }


_AI_SECTIONS = {
    "report": [("weekly_summary", "Executive summary"),
               ("risk_flag", "Risks & blockers"),
               ("progress_digest", "SOP observations")],
    "plan": [("weekly_summary", "Plan narrative"),
             ("dependency_advisor", "Dependencies & sequencing")],
}


def _ai_context(kind: str, period: dict, tasks: list[dict], metrics: dict) -> str:
    lines = [f"WEEKLY {'REPORT' if kind == 'report' else 'PLAN'} {period['label']} — compiled data:"]
    for t in tasks[:60]:
        lines.append(f"- [{t['status']}] {t['title']}"
                     + (f" (SOP {t['reference_code']})" if t.get("reference_code") else "")
                     + (f" dept={t['department']}" if t.get("department") else ""))
    if kind == "report":
        for b in metrics["per_sop"][:10]:
            lines.append(f"SOP {b['sop']}: {b['hours']}h this week (prev 4-wk avg {b['prev4_avg_hours']}h),"
                         f" night {b['night']}h weekend {b['weekend']}h")
        ot = metrics["on_time"]
        lines.append(f"On-time completion: {ot['on_time']}/{ot['completed']}")
    return "\n".join(lines)


async def _ai_sections(c, kind: str, context: str) -> list[dict]:
    out = []
    for key, title in _AI_SECTIONS[kind]:
        binding = await c.fetchrow(
            "SELECT letta_agent_id FROM ai_agent_bindings"
            " WHERE function_key=$1 AND is_active=true ORDER BY scope LIMIT 1", key)
        if binding is None:
            out.append({"key": key, "title": title, "body": "", "approved": False,
                        "status": "not_configured"})
            continue
        ask = {
            "weekly_summary": "Write the executive narrative for this document: what happened, what stands out, what deserves leadership attention. Be concrete and reference tasks/SOPs by name. 2-4 paragraphs.",
            "risk_flag": "Identify concrete risks, blockers and deviations visible in this data. For each: what, why it matters, suggested action. Bullet list.",
            "progress_digest": "Write per-SOP observations: for each SOP with meaningful hours, what was done, any anomalies in effort (vs the 4-week average), off-hours concentration. Short sections per SOP.",
            "dependency_advisor": "Given these carried-over tasks, lay out sequencing and dependency advice for next week: what must precede what, conflicts to watch. Bullet list.",
        }[key]
        reply = await _letta_message(binding["letta_agent_id"], f"{context}\n\nREQUEST: {ask}")
        if reply is None:
            out.append({"key": key, "title": title, "body": "", "approved": False,
                        "status": "unavailable"})
        else:
            out.append({"key": key, "title": title, "body": reply, "approved": False,
                        "status": "draft"})
    return out


class CompileReq(BaseModel):
    kind: str = "report"  # report | plan
    ref_date: str | None = None


def _doc_row(r) -> dict:
    content = r["content"]
    if isinstance(content, str):  # defensive: jsonb codec normally decodes
        content = json.loads(content)
    return {
        "id": str(r["id"]), "kind": r["kind"], "status": r["status"],
        "week_start": _iso(r["week_start"]), "week_end": _iso(r["week_end"]),
        "content": content,
        "created_by": str(r["created_by"]) if r["created_by"] else None,
        "locked_by": str(r["locked_by"]) if r["locked_by"] else None,
        "locked_at": _iso(r["locked_at"]),
        "created_at": _iso(r["created_at"]), "updated_at": _iso(r["updated_at"]),
    }


@router.post("/compile")
async def compile_document(body: CompileReq, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    if body.kind not in ("report", "plan"):
        raise HTTPException(422, "kind must be 'report' or 'plan'")
    try:
        ref = date.fromisoformat(body.ref_date) if body.ref_date else date.today()
    except ValueError:
        raise HTTPException(422, "ref_date must be ISO format YYYY-MM-DD")
    fri, thu = _fri_thu(ref)
    if body.kind == "plan":
        fri, thu = fri + timedelta(days=7), thu + timedelta(days=7)

    async with rls(user) as c:
        tasks = await _fetch_window_tasks(c, fri, thu, body.kind)
        await _attach_notes(c, tasks)
        sessions = await _fetch_sessions(c, fri, thu) if body.kind == "report" else []
        prior = await _fetch_sessions(c, fri - timedelta(days=28), fri - timedelta(days=1)) if body.kind == "report" else []
        metrics = _metrics(tasks, sessions, prior) if body.kind == "report" else {}
        iso_week = fri.isocalendar()[1]
        period = {"start": fri.isoformat(), "end": thu.isoformat(), "iso_week": iso_week,
                  "label": f"W{iso_week} {fri.year} ({fri.strftime('%a %b %d')} → {thu.strftime('%a %b %d')})"}
        content = {
            "kind": body.kind, "period": period,
            "tasks": tasks,
            "ribbon": _ribbon_segments(sessions) if body.kind == "report" else [],
            "metrics": metrics,
            "ai_sections": await _ai_sections(c, body.kind, _ai_context(body.kind, period, tasks, metrics)),
        }
        row = await c.fetchrow(
            "INSERT INTO weekly_documents(org_id, kind, week_start, week_end, content, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6)"
            " ON CONFLICT (org_id, kind, week_start) DO UPDATE"
            "   SET content=EXCLUDED.content, updated_at=now()"
            "   WHERE weekly_documents.status='draft'"
            " RETURNING *",
            user["org_id"], body.kind, fri, thu, content, user["id"])
        if row is None:
            raise HTTPException(409, "Document for this week is locked — it is the submitted record")
    return _doc_row(row)


@router.get("")
async def get_document(kind: str = "report", ref_date: str | None = None,
                       user: dict = Depends(require_password_set)):
    try:
        ref = date.fromisoformat(ref_date) if ref_date else date.today()
    except ValueError:
        raise HTTPException(422, "ref_date must be ISO format YYYY-MM-DD")
    fri, _thu = _fri_thu(ref)
    if kind == "plan":
        fri = fri + timedelta(days=7)
    async with rls(user) as c:
        row = await c.fetchrow(
            "SELECT * FROM weekly_documents WHERE kind=$1 AND week_start=$2", kind, fri)
    if row is None:
        raise HTTPException(404, "No document compiled for this week")
    return _doc_row(row)


class PatchReq(BaseModel):
    content: dict


@router.patch("/{doc_id}")
async def patch_document(doc_id: str, body: PatchReq,
                         user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        row = await c.fetchrow(
            "UPDATE weekly_documents SET content=$2, updated_at=now()"
            " WHERE id=$1 AND status='draft' RETURNING *", doc_id, body.content)
        if row is None:
            exists = await c.fetchval("SELECT status FROM weekly_documents WHERE id=$1", doc_id)
            if exists == "locked":
                raise HTTPException(409, "Locked documents are immutable")
            raise HTTPException(404, "Document not found")
    return _doc_row(row)


@router.post("/{doc_id}/lock")
async def lock_document(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    async with rls(user) as c:
        row = await c.fetchrow(
            "UPDATE weekly_documents SET status='locked', locked_by=$2, locked_at=now(), updated_at=now()"
            " WHERE id=$1 AND status='draft' RETURNING *", doc_id, user["id"])
        if row is None:
            exists = await c.fetchval("SELECT status FROM weekly_documents WHERE id=$1", doc_id)
            if exists == "locked":
                raise HTTPException(409, "Already locked")
            raise HTTPException(404, "Document not found")
    return _doc_row(row)


# ── PDF export ───────────────────────────────────────────────────────────────

def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _ribbon_svg(segments: list[dict], week_start: str) -> str:
    """Server-rendered 7×24h ribbon (also embedded in the PDF): one row per
    day, hour ticks, sessions as SOP-colored bars over their real extents."""
    W, ROW, LEFT, TOP = 780, 34, 64, 22
    H = TOP + 7 * ROW + 14
    hour_w = (W - LEFT - 10) / 24
    start = date.fromisoformat(week_start)
    days = [(start + timedelta(days=i)) for i in range(7)]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="DejaVu Sans, sans-serif">']
    for h in range(0, 25, 3):
        x = LEFT + h * hour_w
        parts.append(f'<line x1="{x:.1f}" y1="{TOP - 4}" x2="{x:.1f}" y2="{H - 12}" stroke="#DCE3EC" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{TOP - 8}" font-size="8" fill="#8A99B0" text-anchor="middle">{h:02d}</text>')
    for i, d in enumerate(days):
        y = TOP + i * ROW
        parts.append(f'<text x="4" y="{y + ROW / 2 + 3:.1f}" font-size="9" fill="#16233B">{d.strftime("%a %d.%m")}</text>')
        parts.append(f'<rect x="{LEFT}" y="{y + 4}" width="{W - LEFT - 10}" height="{ROW - 8}" rx="4" fill="#F3F6FA"/>')
        for s in segments:
            if s["date"] != d.isoformat():
                continue
            x = LEFT + s["start_h"] * hour_w
            w = max(2.0, (s["end_h"] - s["start_h"]) * hour_w)
            parts.append(
                f'<rect x="{x:.1f}" y="{y + 6}" width="{w:.1f}" height="{ROW - 12}" rx="3"'
                f' fill="{s["color"]}" fill-opacity="0.9"><title>{_e(s["title"])} · {_e(s["sop"])}'
                f' · {s["hours"]}h</title></rect>')
    parts.append("</svg>")
    return "".join(parts)


def _pdf_html(doc: dict, people: dict) -> str:
    c = doc["content"]
    kind = c.get("kind", "report")
    period = c.get("period", {})
    is_locked = doc["status"] == "locked"
    who = lambda uid: (people.get(uid or "", {}) or {}).get("full_name") or (people.get(uid or "", {}) or {}).get("username") or ""

    ai_html = ""
    for s in c.get("ai_sections", []):
        if s.get("status") in ("not_configured", "unavailable"):
            continue
        if is_locked and not s.get("approved"):
            continue
        badge = "" if s.get("approved") else '<span class="badge">DRAFT — not approved</span>'
        ai_html += f'<div class="sec"><h3>{_e(s["title"])} {badge}</h3><div class="ai">{_e(s["body"]).replace(chr(10), "<br>")}</div></div>'

    sop_rows = "".join(
        f'<tr><td><span class="dot" style="background:{b["color"]}"></span>{_e(b["sop"])}</td>'
        f'<td>{b["hours"]}</td><td>{b["prev4_avg_hours"]}</td><td>{b["tasks"]}</td>'
        f'<td>{b["sessions"]}</td><td>{b["night"]}</td><td>{b["weekend"]}</td><td>{b["overtime"]}</td></tr>'
        for b in c.get("metrics", {}).get("per_sop", []))

    task_html = ""
    for t in c.get("tasks", []):
        notes = "".join(f'<li><b>{_e(n["day"] or "")}</b> {_e(n["note"])}'
                        + (f' <i>— {_e(who(n.get("user_id")))}</i>' if n.get("user_id") else "")
                        + "</li>" for n in t.get("notes", []))
        params = " · ".join(filter(None, [
            f'Status: {_e(t["status"])}', f'Priority: {_e(t["priority"])}',
            f'Type: {_e(t["task_type"])}' if t.get("task_type") else None,
            f'SOP: {_e(t["reference_code"])}' if t.get("reference_code") else None,
            f'Dept: {_e(t["department"])}' if t.get("department") else None,
            f'Due: {_e(t["due_date"])}' if t.get("due_date") else None,
            f'Completed: {_e(t["completed_date"])}' if t.get("completed_date") else None,
            f'Days: {"/".join(t.get("days") or [])}' if t.get("days") else None,
            f'Est: {t["estimated_hours"]}h' if t.get("estimated_hours") else None,
            f'Actual: {t["actual_hours"]}h' if t.get("actual_hours") else None,
        ]))
        task_html += (f'<div class="task"><h4>{_e(t["title"])}</h4>'
                      f'<div class="params">{params}</div>'
                      + (f'<p>{_e(t["description"])}</p>' if t.get("description") else "")
                      + (f'<ul class="notes">{notes}</ul>' if notes else "")
                      + "</div>")

    ribbon = _ribbon_svg(c.get("ribbon", []), period.get("start", date.today().isoformat())) if c.get("ribbon") else ""
    legend = "".join(f'<span class="lg"><span class="dot" style="background:{b["color"]}"></span>{_e(b["sop"])}</span>'
                     for b in c.get("metrics", {}).get("per_sop", [])[:12])
    ot = c.get("metrics", {}).get("on_time") or {}
    lock_line = (f'Locked by {_e(who(doc.get("locked_by")))} at {_e((doc.get("locked_at") or "")[:16].replace("T", " "))}'
                 if is_locked else "DRAFT — not yet submitted")

    return f"""<html><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 18mm 14mm; }}
    body {{ font-family: 'DejaVu Sans', sans-serif; color: #16233B; font-size: 10px; }}
    h1 {{ font-size: 20px; margin: 0; }} h2 {{ font-size: 13px; margin: 18px 0 6px; border-bottom: 2px solid #15A86B; padding-bottom: 3px; }}
    h3 {{ font-size: 11px; margin: 10px 0 4px; }} h4 {{ font-size: 10.5px; margin: 0 0 2px; }}
    .sub {{ color: #5D6B7E; margin: 2px 0 0; }} .badge {{ background: #FFF4E5; color: #B45309; font-size: 8px; padding: 1px 6px; border-radius: 8px; }}
    .head {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #15A86B; padding-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 9px; }} td, th {{ border: 1px solid #E2E8F0; padding: 3px 6px; text-align: left; }}
    th {{ background: #F3F6FA; }} .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 4px; margin-right: 4px; }}
    .task {{ border: 1px solid #E2E8F0; border-left: 3px solid #15A86B; border-radius: 4px; padding: 6px 8px; margin: 6px 0; page-break-inside: avoid; }}
    .params {{ color: #5D6B7E; font-size: 8.5px; margin-bottom: 3px; }} .notes {{ margin: 4px 0 0 12px; padding: 0; }}
    .ai {{ background: #F8FAF9; border: 1px solid #DFE9E4; border-radius: 4px; padding: 8px; }}
    .lg {{ margin-right: 10px; font-size: 8.5px; white-space: nowrap; }} .sec {{ page-break-inside: avoid; }}
    </style></head><body>
    <div class="head">
      <div><h1>GrowFlow — Weekly {"Report" if kind == "report" else "Plan"}</h1>
      <p class="sub">{_e(period.get("label", ""))} · Purely Plant GmbH · {_e(lock_line)}</p></div>
      <div style="text-align:right"><b style="color:#15A86B">PURELY<span style="color:#16233B">PLANT</span></b><br>
      <span class="sub">Generated {datetime.now(TZ).strftime("%Y-%m-%d %H:%M")} {TZ.key}</span></div>
    </div>
    {f'<h2>Week ribbon — logged work by SOP</h2>{ribbon}<div>{legend}</div>' if ribbon else ''}
    {f'''<h2>Metrics</h2>
    <table><tr><th>SOP / area</th><th>Hours</th><th>4-wk avg</th><th>Tasks</th><th>Sessions</th><th>Night</th><th>Weekend</th><th>Overtime</th></tr>{sop_rows}</table>
    <p class="sub">On-time completion: {ot.get("on_time", "—")}/{ot.get("completed", "—")}{f" ({round(100 * (ot.get('rate') or 0))}%)" if ot.get("rate") is not None else ""}</p>''' if kind == "report" else ''}
    {f'<h2>AI analysis</h2>{ai_html}' if ai_html else ''}
    <h2>Tasks ({len(c.get("tasks", []))})</h2>
    {task_html}
    </body></html>"""


@router.get("/{doc_id}/export.pdf")
async def export_pdf(doc_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        row = await c.fetchrow("SELECT * FROM weekly_documents WHERE id=$1", doc_id)
    if row is None:
        raise HTTPException(404, "Document not found")
    doc = _doc_row(row)
    people = await roster(user)
    # Imported lazily: weasyprint pulls native libs (pango/cairo) — the app
    # must still boot in environments that lack them (only export would 501).
    try:
        from weasyprint import HTML
    except Exception:
        raise HTTPException(501, "PDF engine not available on this server")
    pdf = HTML(string=_pdf_html(doc, people)).write_pdf()
    name = f"wwf-{doc['kind']}-{doc['week_start']}{'' if doc['status'] == 'locked' else '-DRAFT'}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
