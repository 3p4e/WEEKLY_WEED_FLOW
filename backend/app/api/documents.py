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
import asyncio
import html
import json
import re
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.api.ai import _letta_message
from app.api.weekwindow import TASK_COLS as _COLS
from app.api.weekwindow import activity_window_sql, fri_thu as _fri_thu, task_row as _task_row
from app.db import rls
from app.deps import dept_scope, is_dept_scoped_role, require_role
from app.roles import ELEVATED_ROLES
from app.roster import roster
from app.worktime import TZ, classify, session_hours

router = APIRouter(prefix="/reports/documents", tags=["documents"])


def _today() -> date:
    """Facility-local 'today' — never the container's naive UTC clock, which
    resolves to the previous day (and thus the previous Fri→Thu week) for the
    hour or two after local midnight."""
    return datetime.now(TZ).date()


def _require_uuid(value) -> None:
    """A malformed (non-uuid) doc_id path param must be a clean 404, not a 500
    from asyncpg trying to cast it to uuid inside the lookup query."""
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, "Document not found")


def _effective_dept_id(user: dict, requested: str | None) -> str | None:
    """Which department a document call operates on. A dept-scoped manager is
    FORCED to their own department (whatever they requested — mirrors
    reports.py's /reports/weekly rule); executives / QP / ADMIN default to the
    org-wide document (None) and may explicitly request any department."""
    scope = dept_scope(user)
    if scope:
        return scope
    # A scoped manager with no department assigned must NOT inherit org-wide
    # authority over the submitted GMP record — refuse until a dept is set.
    if is_dept_scoped_role(user):
        raise HTTPException(403, "No department assigned — ask an admin to set your department")
    if requested:
        try:
            uuid.UUID(str(requested))
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(422, "department_id must be a uuid")
        return str(requested)
    return None


def _scope_guard(user: dict, row) -> None:
    """By-id access guard: a dept-scoped manager may only touch their own
    department's documents — the org-wide record and other departments' docs
    are 403 (they are compiled/locked by executives)."""
    if is_dept_scoped_role(user):
        scope = dept_scope(user)
        # No department assigned, or the row belongs to another dept / the
        # org-wide record → outside this manager's scope.
        if not scope or str(row["department_id"] or "") != scope:
            raise HTTPException(403, "Document is outside your department scope")


async def _resolve_department(c, dept_id: str | None) -> dict | None:
    """The department block stored in content (and used by the PDF header).
    RLS-scoped lookup; a department that doesn't exist in this org is a 404."""
    if dept_id is None:
        return None
    row = await c.fetchrow(
        "SELECT id, code, name, name_mk FROM departments WHERE id=$1", dept_id)
    if row is None:
        raise HTTPException(404, "Department not found")
    return {"id": str(row["id"]), "code": row["code"],
            "name": row["name"], "name_mk": row["name_mk"] or row["name"]}

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


async def _fetch_window_tasks(c, fri: date, thu: date, kind: str,
                              dept_id: str | None = None) -> list[dict]:
    dept_clause = " AND t.department_id=$4 " if dept_id else " "
    if kind == "report":
        args = [fri, thu, TZ.key] + ([dept_id] if dept_id else [])
        rows = await c.fetch(
            f"SELECT {_COLS} FROM tasks t "
            f"WHERE t.is_deleted=false "
            f"AND {activity_window_sql('$1', '$2', '$3')}"
            f"{dept_clause}"
            f"ORDER BY t.department, t.created_at", *args)
    else:  # plan: the target week's still-open work PLUS carryover.
        # A Plan for a given week shows every open (non-completed) task that is
        # due/scheduled on or before the END of that week (thu) — i.e. this
        # week's planned tasks AND all still-open earlier tasks that carried
        # over — plus undated backlog (no week_start and no due_date). Tasks
        # explicitly scheduled for a LATER week are excluded, so different weeks
        # now produce different Plans instead of one identical all-open dump.
        plan_clause = " AND t.department_id=$2 " if dept_id else " "
        args = [thu] + ([dept_id] if dept_id else [])
        rows = await c.fetch(
            f"SELECT {_COLS} FROM tasks t "
            f"WHERE t.is_deleted=false AND t.is_archived=false AND t.status <> 'completed' "
            f"AND (COALESCE(t.week_start, t.due_date) <= $1"
            f"     OR (t.week_start IS NULL AND t.due_date IS NULL))"
            f"{plan_clause}"
            f"ORDER BY t.department, t.created_at", *args)
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


async def _fetch_sessions(c, start: date, end: date, dept_id: str | None = None) -> list:
    """Work sessions whose facility-local start falls in [start, end]."""
    dept_clause = " AND t.department_id=$4" if dept_id else ""
    args = [start, end, TZ.key] + ([dept_id] if dept_id else [])
    return await c.fetch(
        "SELECT ws.id, ws.task_id, ws.user_id, ws.started_at, ws.ended_at, ws.hours,"
        "       t.title, t.reference_code, t.department, t.department_id"
        " FROM work_sessions ws JOIN tasks t ON t.id = ws.task_id"
        " WHERE (ws.started_at AT TIME ZONE $3) >= $1::date"
        "   AND (ws.started_at AT TIME ZONE $3) < ($2::date + 1)"
        f"{dept_clause}",
        *args)


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
        if end > start:  # a session ending exactly at midnight leaves start==end — no phantom
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
    # Single pass over sessions accumulates BOTH the per-SOP and per-department
    # buckets (session_hours computed once each), rounding once at the end so
    # totals don't drift from compounding per-iteration round().
    per_sop: dict[str, dict] = {}
    per_dept: dict[str, dict] = {}
    for s in sessions:
        h = session_hours(s)
        cls = classify(s["started_at"])
        sop = s["reference_code"] or (s["department"] or "—")
        b = per_sop.setdefault(sop, {"sop": sop, "color": _sop_color(sop), "hours": 0.0,
                                     "sessions": 0, "tasks": set(),
                                     "night": 0.0, "weekend": 0.0, "overtime": 0.0,
                                     "prev4_avg_hours": 0.0})
        b["hours"] += h
        b["sessions"] += 1
        b["tasks"].add(str(s["task_id"]))
        if cls in ("night", "weekend", "overtime"):
            b[cls] += h
        dn = s["department"] or "—"
        d = per_dept.setdefault(dn, {"name": dn, "hours": 0.0, "sessions": 0})
        d["hours"] += h
        d["sessions"] += 1
    prior: dict[str, float] = {}
    for s in prior_sessions:
        sop = s["reference_code"] or (s["department"] or "—")
        prior[sop] = prior.get(sop, 0.0) + session_hours(s)
    for sop, b in per_sop.items():
        b["tasks"] = len(b["tasks"])
        b["prev4_avg_hours"] = round(prior.get(sop, 0.0) / 4, 2)
        for k in ("hours", "night", "weekend", "overtime"):
            b[k] = round(b[k], 2)
    for d in per_dept.values():
        d["hours"] = round(d["hours"], 2)

    completed = [t for t in tasks if t["status"] == "completed"]
    # On-time is only meaningful for tasks that HAD a deadline: a no-due-date
    # completion is neither on-time nor late, so it's excluded from both sides
    # (counting it as on-time inflated the rate on the submitted record).
    with_due = [t for t in completed if t["due_date"]]
    on_time = [t for t in with_due if t["completed_date"] and t["completed_date"] <= t["due_date"]]
    today = _today()
    overdue_open = [
        {"id": t["id"], "title": t["title"], "due_date": t["due_date"],
         "age_days": (today - date.fromisoformat(t["due_date"])).days}
        for t in tasks
        if t["due_date"] and t["status"] != "completed" and date.fromisoformat(t["due_date"]) < today
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
        "on_time": {"completed": len(completed), "measured": len(with_due), "on_time": len(on_time),
                    "rate": round(len(on_time) / len(with_due), 2) if with_due else None},
        "overdue_open": sorted(overdue_open, key=lambda o: -o["age_days"]),
        "complexity": complexity[:15],
    }


_ASK = {
    "weekly_summary": "Write the executive narrative for this document: what happened, what stands out, what deserves leadership attention. Be concrete and reference tasks/SOPs by name. LENGTH BUDGET: at most 120 words per language.",
    "risk_flag": "Identify concrete risks, blockers and deviations visible in this data. For each: what, why it matters, suggested action. LENGTH BUDGET: at most 8 one-line bullets per language.",
    "progress_digest": "Write per-SOP observations for the TOP 6 SOPs by hours only: what was done, anomalies vs the 4-week average, off-hours concentration. LENGTH BUDGET: at most 50 words per SOP per language.",
    "dependency_advisor": "Given these carried-over tasks, lay out sequencing and dependency advice for next week: what must precede what, conflicts to watch. LENGTH BUDGET: at most 8 one-line bullets per language.",
}

# Every document section is BILINGUAL: one Letta call produces both languages
# (cheaper + atomic vs two calls that could diverge or half-fail).
_BILINGUAL_SUFFIX = (
    "\n\nOUTPUT FORMAT: Write the answer in ENGLISH first, then a line containing"
    " only \"---\", then the SAME content in MACEDONIAN (македонски, кирилица)."
    " No preamble, no markdown fences.")

_SPLIT_RE = None  # compiled lazily below


def _split_bilingual(reply: str) -> tuple[str, str]:
    """EN/MK halves of a `EN --- MK` reply. A model that ignores the protocol
    degrades gracefully: everything lands in body_en, body_mk stays empty (the
    reviewer edits/translates by hand — every section is editable in draft)."""
    global _SPLIT_RE
    if _SPLIT_RE is None:
        import re
        _SPLIT_RE = re.compile(r"\n\s*-{3,}\s*\n")
    parts = _SPLIT_RE.split(reply, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return reply.strip(), ""

# (function_key, section title) per document kind. The prompt is looked up in
# _ASK by key so weekly_summary can carry a kind-specific title.
_AI_SECTIONS = {
    "report": [("weekly_summary", "Executive summary"),
               ("risk_flag", "Risks & blockers"),
               ("progress_digest", "SOP observations")],
    "plan": [("weekly_summary", "Plan narrative"),
             ("dependency_advisor", "Dependencies & sequencing")],
}


# ── Per-department GMP template sections (owner's report structure) ──────────
# The physical facility metrics the owner's weekly-report structure asks for
# (plant counts by genetics, kg through drying/curing, HVAC state, EM…) have NO
# home in the task data model yet — these sections are MANUALLY EDITABLE metric
# grids + a bilingual narrative, persisted only inside content JSONB. Field
# values start empty; AI prefill of the narrative is optional (the
# `template_narrative` binding); everything is reviewer-editable while draft.
def _f(key, en, mk, unit=""):
    return {"key": key, "label_en": en, "label_mk": mk, "value": "", "unit": unit}


_TEMPLATE_REGISTRY = [
    {"key": "cultivation_status", "codes": ("cultivation", "vegetation"),
     "title_en": "Cultivation Status", "title_mk": "Статус на одгледување",
     "fields": [
         _f("mother_plants", "Mother plants (by genetics)", "Мајки растенија (по генетика)"),
         _f("clones_started", "Clones started / rooted", "Започнати / вкоренети резници"),
         _f("plants_per_room", "Plants per room", "Растенија по просторија"),
         _f("flowering_week_by_room", "Flowering week per room", "Недела на цветање по просторија"),
         _f("expected_harvest", "Expected harvest date(s) & yield", "Очекувана берба и принос"),
         _f("room_utilization", "Room / facility utilization", "Искористеност на простории", "%"),
     ]},
    {"key": "production_overview", "codes": ("production",),
     "title_en": "Production Overview", "title_mk": "Преглед на производство",
     "fields": [
         _f("harvest_kg", "Harvested this week", "Собрано оваа недела", "kg"),
         _f("drying_kg", "In drying", "Во сушење", "kg"),
         _f("curing_kg", "In curing", "Во зреење", "kg"),
         _f("awaiting_qc_kg", "Awaiting QC release", "Чека QC ослободување", "kg"),
         _f("released_kg", "Released", "Ослободено", "kg"),
         _f("inventory_by_batch", "Inventory by batch", "Залиха по серија"),
     ]},
    {"key": "quality_gmp", "codes": ("qc", "quality_control", "quality_assurance"),
     "title_en": "Quality & GMP", "title_mk": "Квалитет и GMP",
     "fields": [
         _f("visual_inspections", "Visual inspections", "Визуелни инспекции"),
         _f("lab_testing", "Lab testing status", "Статус на лабораториски тестови"),
         _f("em_excursions", "Environmental monitoring excursions", "Отстапувања од мониторинг на средина"),
         _f("deviations_open", "Open deviations", "Отворени отстапувања"),
         _f("capas_open", "Open CAPAs", "Отворени CAPA"),
         _f("batches_released", "Batches released / on hold", "Ослободени / задржани серии"),
         _f("sops_validation", "SOPs & validation activities", "SOP и валидациски активности"),
     ]},
    {"key": "technical_status", "codes": ("tooling",),
     "title_en": "Technical Status", "title_mk": "Технички статус",
     "fields": [
         _f("hvac_status", "HVAC & compressors", "HVAC и компресори"),
         _f("drying_room_controls", "Drying room controls", "Контроли на сушара"),
         _f("dehumidifiers", "Dehumidifiers", "Одвлажнувачи"),
         _f("filters_valves", "Filters & valves", "Филтри и вентили"),
         _f("calibrations_due", "Calibrations due", "Претстојни калибрации"),
         _f("maintenance_backlog", "Maintenance backlog", "Заостанати одржувања"),
     ]},
    {"key": "inventory_logistics", "codes": ("logistics",),
     "title_en": "Inventory & Logistics", "title_mk": "Залихи и логистика",
     "fields": [
         _f("finished_stock", "Finished goods stock", "Залиха на готов производ", "kg"),
         _f("packaging_stock", "Packaging materials", "Пакувачки материјали"),
         _f("shipments_out", "Shipments out", "Испораки"),
         _f("deliveries_in", "Deliveries in", "Приеми"),
         _f("storage_capacity", "Storage capacity used", "Искористеност на складиште", "%"),
     ]},
    {"key": "site_security", "codes": ("security",),
     "title_en": "Site & Security", "title_mk": "Локација и обезбедување",
     "fields": [
         _f("incidents", "Incidents", "Инциденти"),
         _f("alarm_events", "Alarm events", "Алармни настани"),
         _f("access_changes", "Access changes", "Промени на пристап"),
         _f("visitors", "Visitors on site", "Посетители"),
     ]},
]

# Org-wide documents additionally carry the cross-facility sections.
_ORG_WIDE_SECTIONS = [
    {"key": "transition_plan", "codes": (),
     "title_en": "Transition Plan", "title_mk": "План за транзиција",
     "fields": [
         _f("rooms_transitioning", "Rooms transitioning", "Простории во транзиција"),
         _f("next_harvest_eta", "Next harvest ETA", "Следна берба (проценка)"),
         _f("headcount_changes", "Headcount / staffing changes", "Промени во персонал"),
     ]},
    {"key": "production_forecast", "codes": (),
     "title_en": "Production Forecast (rolling)", "title_mk": "Прогноза на производство",
     "fields": [
         _f("next_week_kg", "Next week forecast", "Прогноза за следна недела", "kg"),
         _f("month_kg", "4-week forecast", "Прогноза за 4 недели", "kg"),
         _f("confidence_note", "Confidence / assumptions", "Сигурност / претпоставки"),
     ]},
]

_CODE_TO_TEMPLATE = {code: t for t in _TEMPLATE_REGISTRY for code in t["codes"]}


def _template_instance(t: dict) -> dict:
    """A fresh, editable copy of a registry entry for one document."""
    return {"key": t["key"], "title_en": t["title_en"], "title_mk": t["title_mk"],
            "department_codes": list(t["codes"]),
            "fields": [dict(f) for f in t["fields"]],
            "narrative": {"en": "", "mk": ""}, "approved": False}


def _generic_template(code: str, name: str, name_mk: str) -> dict:
    """A department without a dedicated template still gets a section — a new
    department must never break compile."""
    return {"key": f"dept_status_{code}", "title_en": f"{name} Status",
            "title_mk": f"Статус — {name_mk or name}", "department_codes": [code],
            "fields": [_f("highlights", "Highlights", "Клучни моменти"),
                       _f("issues", "Issues / needs", "Проблеми / потреби")],
            "narrative": {"en": "", "mk": ""}, "approved": False}


def _template_sections(department: dict | None, org_depts, tasks: list[dict]) -> list[dict]:
    """The document's template sections. Per-department doc → that department's
    section only; org-wide doc → one section per active department (deduped by
    template key — QC and QA share quality_gmp) + the org-wide sections."""
    if department is not None:
        t = _CODE_TO_TEMPLATE.get(department.get("code"))
        return [_template_instance(t) if t else
                _generic_template(department.get("code") or "dept",
                                  department.get("name") or "Department",
                                  department.get("name_mk") or "")]
    out, seen = [], set()
    for d in org_depts:
        t = _CODE_TO_TEMPLATE.get(d["code"])
        if t is None:
            out.append(_generic_template(d["code"], d["name"], d["name_mk"] or ""))
            continue
        if t["key"] in seen:
            continue
        seen.add(t["key"])
        out.append(_template_instance(t))
    out.extend(_template_instance(t) for t in _ORG_WIDE_SECTIONS)
    return out


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


async def _ai_bindings(c, kind: str) -> dict:
    """One query for all of this kind's bindings (was N+1 fetchrow per section).
    Deterministic scope tie-break, mirroring the old ORDER BY scope LIMIT 1."""
    # template_narrative rides along: the optional bilingual prefill for the
    # per-department template sections (unbound → sections stay manual).
    keys = [key for key, _title in _AI_SECTIONS[kind]] + ["template_narrative"]
    rows = await c.fetch(
        "SELECT DISTINCT ON (function_key) function_key, letta_agent_id"
        " FROM ai_agent_bindings WHERE function_key = ANY($1::text[]) AND is_active=true"
        " ORDER BY function_key, scope", keys)
    return {r["function_key"]: r["letta_agent_id"] for r in rows}


async def _ai_sections(kind: str, context: str, bindings: dict) -> list[dict]:
    """Draft the AI sections. Runs the Letta calls CONCURRENTLY and — critically
    — the caller invokes this OUTSIDE the rls() DB connection, so a slow/hung
    agent can't pin an asyncpg pool connection (and its open transaction) for
    the ~30s-per-call it would otherwise hold, exhausting the pool."""
    async def one(key: str, title: str) -> dict:
        agent = bindings.get(key)
        base = {"key": key, "title": title, "body": "", "body_en": "", "body_mk": "", "approved": False}
        if agent is None:
            return {**base, "status": "not_configured"}
        reply = await _letta_message(agent, f"{context}\n\nREQUEST: {_ASK[key]}{_BILINGUAL_SUFFIX}")
        if reply is None:
            return {**base, "status": "unavailable"}
        body_en, body_mk = _split_bilingual(reply)
        # `body` mirrors body_en for old readers (pre-v2 frontend/PDF code paths).
        return {**base, "body": body_en, "body_en": body_en, "body_mk": body_mk, "status": "draft"}

    return list(await asyncio.gather(*(one(key, title) for key, title in _AI_SECTIONS[kind])))


class CompileReq(BaseModel):
    kind: str = "report"  # report | plan
    ref_date: str | None = None
    department_id: str | None = None  # None = org-wide (managers are forced to theirs)


def _doc_row(r) -> dict:
    content = r["content"]
    if isinstance(content, str):  # defensive: jsonb codec normally decodes
        content = json.loads(content)
    return {
        "id": str(r["id"]), "kind": r["kind"], "status": r["status"],
        "week_start": _iso(r["week_start"]), "week_end": _iso(r["week_end"]),
        "department_id": str(r["department_id"]) if r["department_id"] else None,
        "content": content,
        "created_by": str(r["created_by"]) if r["created_by"] else None,
        "locked_by": str(r["locked_by"]) if r["locked_by"] else None,
        "locked_at": _iso(r["locked_at"]),
        "created_at": _iso(r["created_at"]), "updated_at": _iso(r["updated_at"]),
    }


def _period(start: date, end: date, custom: bool) -> dict:
    """Period header for the compiled content. A scheduled week keeps its
    ISO-week label; a custom range reads as an explicit date interval. `days`
    is the row count the ribbon renderers use (7 for a week)."""
    span = (end - start).days + 1
    iso_week = start.isocalendar()[1]
    if custom:
        label = f"{start.strftime('%a %b %d')} → {end.strftime('%a %b %d, %Y')} ({span} days)"
    else:
        label = f"W{iso_week} {start.year} ({start.strftime('%a %b %d')} → {end.strftime('%a %b %d')})"
    return {"start": start.isoformat(), "end": end.isoformat(), "iso_week": iso_week,
            "days": span, "label": label}


async def _prefill_template_narratives(sections: list[dict], tasks: list[dict],
                                       bindings: dict) -> None:
    """Optional AI prefill of the template-section narratives — only when a
    template_narrative binding exists, and only for sections whose department
    actually had tasks in the window (no point asking about an idle
    department). Runs concurrently, OUTSIDE any rls() connection (caller
    guarantees it). Failures leave the narrative empty — every section is
    manually editable in draft, so nothing blocks."""
    agent = bindings.get("template_narrative")
    if agent is None:
        return
    by_code: dict[str, list[dict]] = {}
    for t in tasks:
        # tasks carry the free-text department label; sections carry codes —
        # match loosely on either the code list or the label.
        by_code.setdefault((t.get("department") or "").lower(), []).append(t)

    def section_tasks(sec: dict) -> list[dict]:
        codes = set(sec.get("department_codes") or [])
        if not codes:      # org-wide sections (transition plan / forecast) see everything
            return tasks
        out = []
        for t in tasks:
            label = (t.get("department") or "").lower()
            if label in codes or any(c in label for c in codes):
                out.append(t)
        return out

    async def one(sec: dict) -> None:
        st = section_tasks(sec)
        if not st:
            return
        lines = "\n".join(f"- [{t['status']}] {t['title']}" for t in st[:25])
        reply = await _letta_message(agent, (
            f"Section: {sec['title_en']}. Facility weekly document.\n"
            f"Tasks in scope:\n{lines}\n\n"
            f"REQUEST: Draft a factual narrative for this section grounded ONLY in the tasks above."
            f" LENGTH BUDGET: at most 80 words per language.{_BILINGUAL_SUFFIX}"))
        if reply:
            en, mk = _split_bilingual(reply)
            sec["narrative"] = {"en": en, "mk": mk}

    await asyncio.gather(*(one(s) for s in sections))


async def _compile_content(user: dict, kind: str, start: date, end: date, custom: bool,
                           dept_id: str | None = None) -> dict:
    """Assemble the full document content for [start, end]. Shared by the
    persisted week compile and the non-persisted custom-range preview: gathers
    from the DB, RELEASES the connection before the (slow, external) Letta
    calls, then computes metrics + AI sections. The prior-window baseline scales
    with the span (4 equal-length windows before `start`) so the per-SOP trend
    stays meaningful for a range as well as a 7-day week. With dept_id, every
    input (tasks, sessions, prior baseline) is confined to that department —
    the per-department document a scoped manager compiles and submits."""
    span = (end - start).days + 1
    async with rls(user) as c:
        department = await _resolve_department(c, dept_id)
        org_depts = await c.fetch(
            "SELECT id, code, name, name_mk FROM departments WHERE is_active=true ORDER BY name")
        tasks = await _fetch_window_tasks(c, start, end, kind, dept_id)
        await _attach_notes(c, tasks)
        sessions = await _fetch_sessions(c, start, end, dept_id) if kind == "report" else []
        prior = await _fetch_sessions(c, start - timedelta(days=4 * span),
                                      start - timedelta(days=1), dept_id) if kind == "report" else []
        bindings = await _ai_bindings(c, kind)

    metrics = _metrics(tasks, sessions, prior) if kind == "report" else {}
    period = _period(start, end, custom)
    template_sections = _template_sections(department, org_depts, tasks)
    await _prefill_template_narratives(template_sections, tasks, bindings)
    return {
        "content_version": 2,
        "kind": kind, "period": period,
        "department": department,          # null = org-wide document
        "tasks": tasks,
        "ribbon": _ribbon_segments(sessions) if kind == "report" else [],
        "metrics": metrics,
        "template_sections": template_sections,
        "ai_sections": await _ai_sections(kind, _ai_context(kind, period, tasks, metrics), bindings),
    }


@router.post("/compile")
async def compile_document(body: CompileReq, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    if body.kind not in ("report", "plan"):
        raise HTTPException(422, "kind must be 'report' or 'plan'")
    try:
        ref = date.fromisoformat(body.ref_date) if body.ref_date else _today()
    except ValueError:
        raise HTTPException(422, "ref_date must be ISO format YYYY-MM-DD")
    fri, thu = _fri_thu(ref)
    if body.kind == "plan":
        fri, thu = fri + timedelta(days=7), thu + timedelta(days=7)

    dept_id = _effective_dept_id(user, body.department_id)
    content = await _compile_content(user, body.kind, fri, thu, custom=False, dept_id=dept_id)
    async with rls(user) as c:
        row = await _upsert_document(c, user, body.kind, fri, thu, content, dept_id)
        if row is None:
            raise HTTPException(409, "Document for this week is locked — it is the submitted record")
    return _doc_row(row)


async def _upsert_document(c, user: dict, kind: str, fri: date, thu: date,
                           content: dict, dept_id: str | None):
    """One draft row per scope per week. The two partial unique indexes
    (migration 0010) need matching inference predicates — a plain ON CONFLICT
    (org_id, kind, week_start) no longer matches any constraint and would raise
    at runtime. Returns None when the existing row is locked (WHERE status
    ='draft' makes the UPDATE match nothing)."""
    if dept_id is None:
        return await c.fetchrow(
            "INSERT INTO weekly_documents(org_id, kind, week_start, week_end, content, created_by, department_id)"
            " VALUES ($1,$2,$3,$4,$5,$6, NULL)"
            " ON CONFLICT (org_id, kind, week_start) WHERE department_id IS NULL DO UPDATE"
            "   SET content=EXCLUDED.content, updated_at=now()"
            "   WHERE weekly_documents.status='draft'"
            " RETURNING *",
            user["org_id"], kind, fri, thu, content, user["id"])
    return await c.fetchrow(
        "INSERT INTO weekly_documents(org_id, kind, week_start, week_end, content, created_by, department_id)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7)"
        " ON CONFLICT (org_id, kind, week_start, department_id) WHERE department_id IS NOT NULL DO UPDATE"
        "   SET content=EXCLUDED.content, updated_at=now()"
        "   WHERE weekly_documents.status='draft'"
        " RETURNING *",
        user["org_id"], kind, fri, thu, content, user["id"], dept_id)


class PreviewReq(BaseModel):
    kind: str = "report"  # report | plan
    start: str            # YYYY-MM-DD
    end: str              # YYYY-MM-DD
    department_id: str | None = None  # None = org-wide (managers are forced to theirs)


_MAX_RANGE_DAYS = 92  # bound the ribbon (one row per day) + the compile cost


@router.post("/preview")
async def preview_document(body: PreviewReq, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Draft a report/plan for an ARBITRARY date interval WITHOUT persisting it —
    for looking ahead / back before the scheduled submission day. Deliberately
    not written to weekly_documents: the stored record is keyed one row per
    Fri→Thu week (UNIQUE org_id,kind,week_start) and only the scheduled week is
    the submitted record. This returns the same content shape as a compiled doc
    (so the panel renders it identically) with a synthetic 'preview' envelope;
    export it via POST /export-range.pdf. Locking is intentionally unavailable."""
    if body.kind not in ("report", "plan"):
        raise HTTPException(422, "kind must be 'report' or 'plan'")
    try:
        start = date.fromisoformat(body.start)
        end = date.fromisoformat(body.end)
    except ValueError:
        raise HTTPException(422, "start and end must be ISO format YYYY-MM-DD")
    if end < start:
        raise HTTPException(422, "end must be on or after start")
    if (end - start).days + 1 > _MAX_RANGE_DAYS:
        raise HTTPException(422, f"range too long (max {_MAX_RANGE_DAYS} days)")

    dept_id = _effective_dept_id(user, body.department_id)
    content = await _compile_content(user, body.kind, start, end, custom=True, dept_id=dept_id)
    return {
        "id": None, "kind": body.kind, "status": "preview",
        "week_start": start.isoformat(), "week_end": end.isoformat(),
        "department_id": dept_id,
        "content": content,
        "created_by": str(user["id"]), "locked_by": None, "locked_at": None,
        "created_at": None, "updated_at": None,
    }


@router.get("")
async def get_document(kind: str = "report", ref_date: str | None = None,
                       department_id: str | None = None,
                       user: dict = Depends(require_role(*ELEVATED_ROLES))):
    # Elevated-only: the compiled document is an org-wide snapshot (every task's
    # description + notes, and every user's session times). A base USER must not
    # read it — tasks_read RLS and reports.py's per-user filtering both hide that
    # data from them, and this pre-compiled blob would otherwise bypass both.
    try:
        ref = date.fromisoformat(ref_date) if ref_date else _today()
    except ValueError:
        raise HTTPException(422, "ref_date must be ISO format YYYY-MM-DD")
    fri, _thu = _fri_thu(ref)
    if kind == "plan":
        fri = fri + timedelta(days=7)
    dept_id = _effective_dept_id(user, department_id)
    async with rls(user) as c:
        # IS NOT DISTINCT FROM matches NULL (org-wide) and a uuid in one statement.
        row = await c.fetchrow(
            "SELECT * FROM weekly_documents WHERE kind=$1 AND week_start=$2"
            " AND department_id IS NOT DISTINCT FROM $3::uuid", kind, fri, dept_id)
    if row is None:
        raise HTTPException(404, "No document compiled for this week")
    return _doc_row(row)


class PatchReq(BaseModel):
    content: dict


@router.patch("/{doc_id}")
async def patch_document(doc_id: str, body: PatchReq,
                         user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _require_uuid(doc_id)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT id, status, department_id FROM weekly_documents WHERE id=$1", doc_id)
        if cur is None:
            raise HTTPException(404, "Document not found")
        _scope_guard(user, cur)
        if cur["status"] == "locked":
            raise HTTPException(409, "Locked documents are immutable")
        row = await c.fetchrow(
            "UPDATE weekly_documents SET content=$2, updated_at=now()"
            " WHERE id=$1 AND status='draft' RETURNING *", doc_id, body.content)
        if row is None:
            raise HTTPException(404, "Document not found")
    return _doc_row(row)


class SectionReq(BaseModel):
    approved: bool | None = None
    body: str | None = None            # legacy alias: sets body_en (+ mirrored body)
    body_en: str | None = None
    body_mk: str | None = None
    # template sections only:
    fields: dict[str, str] | None = None   # {field_key: value}
    narrative_en: str | None = None
    narrative_mk: str | None = None


@router.patch("/{doc_id}/sections/{key}")
async def patch_section(doc_id: str, key: str, body: SectionReq,
                        user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """Approve/edit a single AI section. The reviewer's per-checkbox action now
    sends a few bytes instead of round-tripping the whole compiled document
    (tasks + ribbon + metrics + every AI body) — and the server mutates the
    CURRENT stored content, so a concurrent edit can't be clobbered by a stale
    full-document upload."""
    _require_uuid(doc_id)
    async with rls(user) as c:
        row = await c.fetchrow(
            "SELECT * FROM weekly_documents WHERE id=$1 AND status='draft'", doc_id)
        if row is None:
            exists = await c.fetchval("SELECT status FROM weekly_documents WHERE id=$1", doc_id)
            if exists == "locked":
                raise HTTPException(409, "Locked documents are immutable")
            raise HTTPException(404, "Document not found")
        _scope_guard(user, row)
        content = row["content"]
        if isinstance(content, str):
            content = json.loads(content)
        target = next((s for s in content.get("ai_sections", []) if s.get("key") == key), None)
        if target is not None:
            if body.approved is not None:
                target["approved"] = body.approved
            # body_en/body_mk are the bilingual v2 fields; plain `body` is the
            # legacy alias meaning body_en. `body` is always kept mirrored to
            # body_en so pre-v2 readers of stored drafts keep working.
            if body.body_en is not None or body.body is not None:
                target["body_en"] = body.body_en if body.body_en is not None else body.body
                target["body"] = target["body_en"]
            if body.body_mk is not None:
                target["body_mk"] = body.body_mk
        else:
            target = next((s for s in content.get("template_sections", [])
                           if s.get("key") == key), None)
            if target is None:
                raise HTTPException(404, "Section not found")
            if body.approved is not None:
                target["approved"] = body.approved
            if body.fields:
                known = {f["key"]: f for f in target.get("fields", [])}
                unknown = [k for k in body.fields if k not in known]
                if unknown:
                    raise HTTPException(422, f"Unknown field key(s): {', '.join(sorted(unknown))}")
                for k, v in body.fields.items():
                    known[k]["value"] = str(v)
            narrative = target.setdefault("narrative", {"en": "", "mk": ""})
            if body.narrative_en is not None:
                narrative["en"] = body.narrative_en
            if body.narrative_mk is not None:
                narrative["mk"] = body.narrative_mk
        upd = await c.fetchrow(
            "UPDATE weekly_documents SET content=$2, updated_at=now()"
            " WHERE id=$1 AND status='draft' RETURNING *", doc_id, content)
    return _doc_row(upd)


@router.post("/{doc_id}/lock")
async def lock_document(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _require_uuid(doc_id)
    async with rls(user) as c:
        cur = await c.fetchrow("SELECT id, status, department_id FROM weekly_documents WHERE id=$1", doc_id)
        if cur is None:
            raise HTTPException(404, "Document not found")
        _scope_guard(user, cur)
        if cur["status"] == "locked":
            raise HTTPException(409, "Already locked")
        row = await c.fetchrow(
            "UPDATE weekly_documents SET status='locked', locked_by=$2, locked_at=now(), updated_at=now()"
            " WHERE id=$1 AND status='draft' RETURNING *", doc_id, user["id"])
        if row is None:
            raise HTTPException(404, "Document not found")
    return _doc_row(row)


# ── PDF export ───────────────────────────────────────────────────────────────

def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{3,8}$|^[A-Za-z]{1,20}$|^rgba?\([\d.,%\s]{1,40}\)$")


def _color(v, fallback: str = "#8A99B0") -> str:
    """Sanitise a client-supplied CSS color before it lands in PDF markup —
    content.ribbon[].color / per_sop[].color come from a PATCH body and would
    otherwise inject SVG/CSS. Only a hex, a bare color name, or rgb()/rgba() is
    allowed; anything else falls back to a neutral grey."""
    s = str(v or "").strip()
    return s if _COLOR_RE.match(s) else fallback


def _numf(v, nd: int = 1) -> str:
    """Format a client-supplied number for PDF interpolation without a 500 on a
    non-numeric value (a hostile/legacy field never crashes the export)."""
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "0" if nd == 0 else "0." + "0" * nd


def _numi(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _ribbon_svg(segments: list[dict], week_start: str, days: int = 7) -> str:
    """Server-rendered N×24h ribbon for the PDF (light, static, WeasyPrint-safe
    concrete colors). N is 7 for the scheduled Fri→Thu week and the span of a
    custom range otherwise. The live panel has a SECOND, theme-adaptive renderer
    (GF.WWF._ribbonSvg in web/gf/document-view.js) — two renderers on purpose:
    one static print target, one interactive themed DOM. They must stay aligned
    on the RECORD-critical geometry only (which day-row, x = start_h·hour_w,
    width = max(2, (end_h−start_h)·hour_w), SOP color), and both derive that
    purely from the shared `content.ribbon` segments, so the submitted record
    cannot drift from the reviewed one — only cosmetic chrome differs."""
    n = max(1, min(int(days or 7), 92))  # cap rows defensively for oversized input
    W, ROW, LEFT, TOP = 780, 34, 64, 22
    H = TOP + n * ROW + 14
    hour_w = (W - LEFT - 10) / 24
    start = date.fromisoformat(week_start)
    day_dates = [(start + timedelta(days=i)) for i in range(n)]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="DejaVu Sans, sans-serif">']
    for h in range(0, 25, 3):
        x = LEFT + h * hour_w
        parts.append(f'<line x1="{x:.1f}" y1="{TOP - 4}" x2="{x:.1f}" y2="{H - 12}" stroke="#DCE3EC" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{TOP - 8}" font-size="8" fill="#8A99B0" text-anchor="middle">{h:02d}</text>')
    for i, d in enumerate(day_dates):
        y = TOP + i * ROW
        parts.append(f'<text x="4" y="{y + ROW / 2 + 3:.1f}" font-size="9" fill="#16233B">{d.strftime("%a %d.%m")}</text>')
        parts.append(f'<rect x="{LEFT}" y="{y + 4}" width="{W - LEFT - 10}" height="{ROW - 8}" rx="4" fill="#F3F6FA"/>')
        for s in segments:
            if str(s.get("date") or "") != d.isoformat():
                continue
            try:
                sh, eh = float(s.get("start_h") or 0), float(s.get("end_h") or 0)
            except (TypeError, ValueError):
                continue  # a non-numeric segment never crashes the export
            x = LEFT + sh * hour_w
            w = max(2.0, (eh - sh) * hour_w)
            parts.append(
                f'<rect x="{x:.1f}" y="{y + 6}" width="{w:.1f}" height="{ROW - 12}" rx="3"'
                f' fill="{_color(s.get("color"))}" fill-opacity="0.9"><title>{_e(s.get("title"))} · {_e(s.get("sop"))}'
                f' · {_e(s.get("hours"))}h</title></rect>')
    parts.append("</svg>")
    return "".join(parts)


# ── A4 bilingual GMP document template (WeasyPrint) ─────────────────────────
# Every interpolated value passes through _e() (html.escape); multi-line
# narrative text is escaped FIRST, then newlines become <br>.

_PDF_CSS = """
    @page { size: A4 portrait; margin: 12mm 12mm 18mm 12mm;
      @bottom-right { content: "Page " counter(page) " / " counter(pages); font-size: 8px; color: #5D6B7E; }
      @bottom-left  { content: string(doctag); font-size: 8px; color: #5D6B7E; } }
    body { font-family: 'DejaVu Sans', sans-serif; color: #16233B; font-size: 9.5px; }
    h1 { font-size: 19px; margin: 0; line-height: 1.15; }
    .h1mk { font-size: 12px; color: #3D6B54; font-weight: 600; margin: 1px 0 0; }
    h2 { font-size: 12.5px; margin: 16px 0 6px; border-bottom: 2px solid #15A86B; padding-bottom: 3px; string-set: doctag content(); }
    h2 .mk { font-size: 10px; color: #3D6B54; font-weight: 600; margin-left: 6px; }
    h3 { font-size: 10.5px; margin: 9px 0 3px; }
    h4 { font-size: 10px; margin: 0 0 2px; }
    .sub { color: #5D6B7E; margin: 2px 0 0; }
    .badge { background: #FFF4E5; color: #B45309; font-size: 7.5px; padding: 1px 6px; border-radius: 8px; }
    .chip { font-size: 8px; font-weight: 700; letter-spacing: .4px; padding: 2px 8px; border-radius: 9px; }
    .chip.locked { background: #E7F6EE; color: #0E7A4A; } .chip.draft { background: #FFF4E5; color: #B45309; }
    .cover { border-bottom: 3px solid #15A86B; padding-bottom: 9px; }
    .cover-row { display: flex; justify-content: space-between; align-items: flex-start; }
    .meta { margin-top: 7px; width: 100%; border-collapse: collapse; font-size: 9px; }
    .meta td { border: none; padding: 1.5px 14px 1.5px 0; color: #16233B; }
    .meta td.k { color: #5D6B7E; white-space: nowrap; }
    table.grid { border-collapse: collapse; width: 100%; font-size: 9px; }
    table.grid td, table.grid th { border: 1px solid #E2E8F0; padding: 3px 6px; text-align: left; vertical-align: top; }
    table.grid th { background: #F3F6FA; }
    .dot { display: inline-block; width: 8px; height: 8px; border-radius: 4px; margin-right: 4px; }
    .trow-sub { color: #5D6B7E; font-size: 8px; }
    .trow-sub ul { margin: 2px 0 0 12px; padding: 0; }
    .ai { background: #F8FAF9; border: 1px solid #DFE9E4; border-radius: 4px; padding: 7px 9px; }
    .lang-lbl { font-size: 7.5px; font-weight: 700; letter-spacing: .6px; color: #3D6B54; margin: 5px 0 2px; }
    .lg { margin-right: 10px; font-size: 8px; white-space: nowrap; }
    .sec { page-break-inside: avoid; margin-bottom: 8px; }
    .tsec { page-break-inside: avoid; margin-bottom: 10px; }
    .tsec table.grid td.k { width: 42%; color: #46566B; }
    .wm { position: fixed; top: 42%; left: 6%; transform: rotate(-24deg); font-size: 64px; font-weight: 800;
          color: rgba(180, 83, 9, .07); letter-spacing: 6px; }
    .signs { margin-top: 22px; page-break-inside: avoid; width: 100%; border-collapse: collapse; font-size: 9px; }
    .signs td { border: none; padding: 14px 24px 2px 0; width: 50%; }
    .signs .line { border-top: 1px solid #9AA8B8; padding-top: 3px; color: #5D6B7E; }
"""


def _nl(text: str) -> str:
    """Escape then newline→<br> — the only sanctioned way multi-line user/AI
    text reaches the PDF markup."""
    return _e(text).replace("\n", "<br>")


def _sec_body_en(s: dict) -> str:
    # v2 sections carry body_en/body_mk; v1 locked documents only `body`.
    return s.get("body_en") or s.get("body") or ""


def _pdf_cover(doc: dict, c: dict, who) -> str:
    kind = c.get("kind", "report")
    period = c.get("period", {})
    dept = c.get("department")
    is_locked = doc["status"] == "locked"
    title_en = "Weekly Report" if kind == "report" else "Weekly Plan"
    title_mk = "Неделен извештај" if kind == "report" else "Неделен план"
    dept_line = (f'{_e(dept["name"])} / {_e(dept.get("name_mk") or dept["name"])}'
                 if dept else "All departments / Сите оддели")
    status_chip = ('<span class="chip locked">LOCKED · SUBMITTED RECORD</span>' if is_locked
                   else '<span class="chip draft">DRAFT / НАЦРТ</span>')
    lock_row = (f'<tr><td class="k">Approved / Одобрил</td><td>{_e(who(doc.get("locked_by")))}'
                f' — {_e((doc.get("locked_at") or "")[:16].replace("T", " "))}</td></tr>'
                if is_locked else "")
    return f"""
    <div class="cover">
      <div class="cover-row">
        <div><h1>{title_en}</h1><div class="h1mk">{title_mk}</div></div>
        <div style="text-align:right"><b style="color:#15A86B;font-size:13px">PURELY<span style="color:#16233B">PLANT</span></b><br>
          <span class="sub">Purely Plant GmbH · GrowFlow</span><br>{status_chip}</div>
      </div>
      <table class="meta">
        <tr><td class="k">Period / Период</td><td>{_e(period.get("label", ""))}</td></tr>
        <tr><td class="k">Department / Оддел</td><td>{dept_line}</td></tr>
        <tr><td class="k">Prepared / Изготвил</td><td>{_e(who(doc.get("created_by")))}</td></tr>
        {lock_row}
        <tr><td class="k">Generated / Генерирано</td><td>{datetime.now(TZ).strftime("%Y-%m-%d %H:%M")} {_e(TZ.key)}</td></tr>
      </table>
    </div>"""


def _pdf_template_sections(c: dict, is_locked: bool) -> str:
    out = ""
    for sec in c.get("template_sections", []):
        rows = "".join(
            f'<tr><td class="k">{_e(f.get("label_en", ""))}<br><span class="sub">{_e(f.get("label_mk", ""))}</span></td>'
            f'<td>{_nl(f.get("value") or "—")}{(" " + _e(f["unit"])) if f.get("unit") and f.get("value") else ""}</td></tr>'
            for f in sec.get("fields", []))
        nar = sec.get("narrative") or {}
        nar_html = ""
        # Locked rule: the metric grid is ALWAYS part of the record; an
        # unapproved narrative is dropped from the locked export (mirrors the
        # ai_sections rule). Drafts include it with a badge.
        if (nar.get("en") or nar.get("mk")) and not (is_locked and not sec.get("approved")):
            badge = "" if sec.get("approved") else ' <span class="badge">DRAFT — not approved</span>'
            nar_html = f'<div class="ai">{badge}'
            if nar.get("en"):
                nar_html += f'<div class="lang-lbl">EN</div><div>{_nl(nar["en"])}</div>'
            if nar.get("mk"):
                nar_html += f'<div class="lang-lbl">МК</div><div>{_nl(nar["mk"])}</div>'
            nar_html += "</div>"
        out += (f'<div class="tsec"><h3>{_e(sec.get("title_en", ""))}'
                f' <span class="sub">/ {_e(sec.get("title_mk", ""))}</span></h3>'
                f'<table class="grid">{rows}</table>{nar_html}</div>')
    return f'<h2>Department status <span class="mk">Статус по оддели</span></h2>{out}' if out else ""


def _pdf_ai_sections(c: dict, is_locked: bool) -> str:
    out = ""
    for s in c.get("ai_sections", []):
        if s.get("status") in ("not_configured", "unavailable"):
            continue
        if is_locked and not s.get("approved"):
            continue
        body_en, body_mk = _sec_body_en(s), s.get("body_mk") or ""
        if not body_en and not body_mk:
            continue
        badge = "" if s.get("approved") else '<span class="badge">DRAFT — not approved</span>'
        out += f'<div class="sec"><h3>{_e(s["title"])} {badge}</h3><div class="ai">'
        if body_en:
            out += f'<div class="lang-lbl">EN</div><div>{_nl(body_en)}</div>'
        if body_mk:
            out += f'<div class="lang-lbl">МК</div><div>{_nl(body_mk)}</div>'
        out += "</div></div>"
    return f'<h2>Narrative <span class="mk">Наративен дел</span></h2>{out}' if out else ""


def _pdf_task_tables(c: dict, who) -> str:
    """Per-department task tables — the GMP evidence listing, grouped instead
    of dumped. tasks arrive ORDER BY department, so grouping is a single pass."""
    groups: dict[str, list[dict]] = {}
    for t in c.get("tasks", []):
        groups.setdefault(t.get("department") or "—", []).append(t)
    out = ""
    for dept_label, tasks in groups.items():
        rows = ""
        for t in tasks:
            notes = "".join(f'<li><b>{_e(n.get("day") or "")}</b> {_e(n.get("note", ""))}'
                            + (f' <i>— {_e(who(n.get("user_id")))}</i>' if n.get("user_id") else "")
                            + "</li>" for n in t.get("notes", []))
            days = "/".join(_e(d) for d in (t.get("days") or []))
            sub = ""
            if t.get("description") or notes or days:
                sub = (f'<tr class="trow-sub"><td colspan="6">'
                       + (f'<span class="sub">Days: {days}</span> ' if days else "")
                       + (f'{_nl(t["description"])}' if t.get("description") else "")
                       + (f'<ul>{notes}</ul>' if notes else "") + "</td></tr>")
            hours = f'{t.get("estimated_hours") or "—"} / {t.get("actual_hours") or "—"}'
            rows += (f'<tr><td>{_e(t.get("title", ""))}</td><td>{_e(t.get("reference_code") or "—")}</td>'
                     f'<td>{_e(t.get("status", ""))}</td><td>{_e(t.get("priority", ""))}</td>'
                     f'<td>{_e(hours)}</td><td>{_e(t.get("due_date") or "—")}</td></tr>{sub}')
        out += (f'<h3>{_e(dept_label)} <span class="sub">({len(tasks)})</span></h3>'
                f'<table class="grid"><tr><th>Task / Задача</th><th>Ref</th><th>Status</th>'
                f'<th>Priority</th><th>Est/Act h</th><th>Due</th></tr>{rows}</table>')
    n = len(c.get("tasks", []))
    return f'<h2>Tasks ({n}) <span class="mk">Задачи</span></h2>{out}' if out else ""


def _pdf_metrics(c: dict) -> str:
    # .get() defaults + sanitised color: a v1-shape / hostile metrics bucket
    # missing a key (or carrying an injected color) must never 500 the export.
    sop_rows = "".join(
        f'<tr><td><span class="dot" style="background:{_color(b.get("color"))}"></span>{_e(b.get("sop"))}</td>'
        f'<td>{_e(b.get("hours", 0))}</td><td>{_e(b.get("prev4_avg_hours", 0))}</td><td>{_e(b.get("tasks", 0))}</td>'
        f'<td>{_e(b.get("sessions", 0))}</td><td>{_e(b.get("night", 0))}</td><td>{_e(b.get("weekend", 0))}</td><td>{_e(b.get("overtime", 0))}</td></tr>'
        for b in c.get("metrics", {}).get("per_sop", []))
    if not sop_rows:
        return ""
    ot = c.get("metrics", {}).get("on_time") or {}
    rate = f" ({round(100 * (ot.get('rate') or 0))}%)" if ot.get("rate") is not None else ""
    return (f'<h2>Metrics <span class="mk">Показатели</span></h2>'
            f'<table class="grid"><tr><th>SOP / area</th><th>Hours</th><th>4-wk avg</th><th>Tasks</th>'
            f'<th>Sessions</th><th>Night</th><th>Weekend</th><th>Overtime</th></tr>{sop_rows}</table>'
            f'<p class="sub">On-time completion / Навремено завршени: {ot.get("on_time", "—")}/{ot.get("measured", "—")}'
            f' with deadlines{rate} · {ot.get("completed", "—")} completed total</p>')


def _pdf_signatures(doc: dict, who) -> str:
    approved = who(doc.get("locked_by")) if doc["status"] == "locked" else ""
    return f"""
    <table class="signs"><tr>
      <td><div class="line">Prepared by / Изготвил: {_e(who(doc.get("created_by")))}</div></td>
      <td><div class="line">Approved by / Одобрил: {_e(approved) or "&nbsp;"}</div></td>
    </tr><tr>
      <td><div class="line">Date / Датум</div></td>
      <td><div class="line">Date / Датум</div></td>
    </tr></table>"""


def _pdf_html(doc: dict, people: dict) -> str:
    c = doc["content"]
    kind = c.get("kind", "report")
    period = c.get("period", {})
    is_locked = doc["status"] == "locked"
    who = lambda uid: (people.get(uid or "", {}) or {}).get("full_name") or (people.get(uid or "", {}) or {}).get("username") or ""

    ribbon = _ribbon_svg(c.get("ribbon", []), period.get("start", _today().isoformat()),
                         period.get("days", 7)) if c.get("ribbon") else ""
    legend = "".join(f'<span class="lg"><span class="dot" style="background:{_color(b.get("color"))}"></span>{_e(b.get("sop"))}</span>'
                     for b in c.get("metrics", {}).get("per_sop", [])[:12])
    watermark = "" if is_locked else '<div class="wm">DRAFT · НАЦРТ</div>'
    doctag = f'{"Weekly Report" if kind == "report" else "Weekly Plan"} · {period.get("label", "")}'

    return f"""<html><head><meta charset="utf-8"><style>{_PDF_CSS}
    h2:first-of-type {{ string-set: doctag "{_e(doctag)}"; }}
    </style></head><body>
    {watermark}
    {_pdf_cover(doc, c, who)}
    {_pdf_template_sections(c, is_locked)}
    {_pdf_ai_sections(c, is_locked)}
    {f'<h2>Week ribbon — logged work by SOP <span class="mk">Работа по SOP</span></h2>{ribbon}<div>{legend}</div>' if ribbon else ''}
    {_pdf_metrics(c) if kind == "report" else ''}
    {_pdf_task_tables(c, who)}
    {_pdf_signatures(doc, who)}
    </body></html>"""


@router.get("/{doc_id}/export.pdf")
async def export_pdf(doc_id: str, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    _require_uuid(doc_id)
    async with rls(user) as c:
        row = await c.fetchrow("SELECT * FROM weekly_documents WHERE id=$1", doc_id)
    if row is None:
        raise HTTPException(404, "Document not found")
    _scope_guard(user, row)
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


class RangeExportReq(BaseModel):
    content: dict
    kind: str = "report"


@router.post("/export-range.pdf")
async def export_range_pdf(body: RangeExportReq, user: dict = Depends(require_role(*ELEVATED_ROLES))):
    """PDF for a non-persisted custom-range preview. The reviewed content is
    posted back (there is no stored row to read) and rendered through the same
    _pdf_html — every field is HTML-escaped there, so client-supplied content
    cannot inject markup or a server-side fetch. Always a DRAFT (a preview is
    never a locked submitted record)."""
    content = body.content or {}
    kind = content.get("kind") or body.kind or "report"
    period = content.get("period") or {}
    doc = {"content": content, "status": "preview", "kind": kind,
           "week_start": period.get("start") or _today().isoformat(),
           "locked_by": None, "locked_at": None}
    people = await roster(user)
    try:
        from weasyprint import HTML
    except Exception:
        raise HTTPException(501, "PDF engine not available on this server")
    pdf = HTML(string=_pdf_html(doc, people)).write_pdf()
    name = f"wwf-{kind}-{doc['week_start']}-PREVIEW.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
