"""Task lifecycle API (RLS-scoped via app_user + per-request identity GUCs).

v2 task model: task_type / reference_code / due_date / blocker_reason /
recurrence / outcome / archive on tasks, plus two child resources —
work_sessions (every sitting of real work; the overtime engine's source of
truth) and task_links (external Drive/SOP references)."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_password_set
from app.worktime import classify, session_hours

router = APIRouter(tags=["tasks"])

Status = Literal["pending", "ongoing", "review", "stuck", "postponed", "completed"]
TaskType = Literal["capa", "sop", "validation", "document", "lab", "meeting", "admin", "other"]


def _ser(rows):
    return [dict(r) for r in rows]


@router.get("/departments")
async def departments(user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        return _ser(await c.fetch("SELECT id,code,name,name_mk,parent_id,is_active FROM departments ORDER BY name"))


@router.get("/weeks")
async def weeks(user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        return _ser(await c.fetch(
            "SELECT id,iso_year,iso_week,starts_on,ends_on FROM calendar_weeks ORDER BY starts_on DESC"))


_TASK_COLS = (
    "t.id,t.user_id,t.parent_id,t.title,t.description,t.status,t.priority,t.workflow_state,"
    "t.task_type,t.reference_code,t.external_ref,t.blocker_reason,t.recurrence,t.outcome,t.is_archived,"
    "t.department,t.department_id,t.week_id,t.week_start,t.days,t.tags,"
    "t.due_date,t.completed_date,t.estimated_hours,t.actual_hours,t.created_at,t.updated_at"
)


@router.get("/tasks")
async def list_tasks(
    week_id: str | None = None,
    department_id: str | None = None,
    parents_only: bool = False,
    include_archived: bool = False,
    user: dict = Depends(require_password_set),
):
    clauses, args = ["t.is_deleted=false"], []
    if not include_archived:
        clauses.append("t.is_archived=false")
    if week_id:
        args.append(week_id); clauses.append(f"t.week_id=${len(args)}")
    if department_id:
        args.append(department_id); clauses.append(f"t.department_id=${len(args)}")
    if parents_only:
        clauses.append("t.parent_id IS NULL")
    where = " AND ".join(clauses)
    async with rls(user) as c:
        return _ser(await c.fetch(
            f"SELECT {_TASK_COLS},"
            # progress_notes has no column of its own — task_progress is the only
            # write path (POST /tasks/{id}/progress), so this reads live from it
            # instead of trusting a denormalized copy that could go stale.
            f"COALESCE((SELECT jsonb_agg(jsonb_build_object("
            f"  'day_label', tp.day_label, 'note', tp.note, 'created_at', tp.created_at"
            f") ORDER BY tp.created_at DESC) FROM (SELECT day_label, note, created_at FROM task_progress"
            f" WHERE task_id=t.id ORDER BY created_at DESC LIMIT 20) tp), '[]'::jsonb) AS progress_notes,"
            # Logged session hours, so cards can show real effort without N+1 calls.
            f"COALESCE((SELECT sum(COALESCE(ws.hours, EXTRACT(EPOCH FROM ws.ended_at-ws.started_at)/3600))"
            f" FROM work_sessions ws WHERE ws.task_id=t.id), 0) AS session_hours,"
            f"(SELECT count(*) FROM tasks s WHERE s.parent_id=t.id AND s.is_deleted=false) AS subtask_count,"
            f"(SELECT count(*) FROM tasks s WHERE s.parent_id=t.id AND s.is_deleted=false"
            f"  AND s.status='completed') AS subtask_done_count,"
            f"COALESCE(array_agg(ta.user_id) FILTER (WHERE ta.user_id IS NOT NULL), '{{}}') AS assignee_ids "
            f"FROM tasks t LEFT JOIN task_assignees ta ON ta.task_id=t.id "
            f"WHERE {where} GROUP BY t.id ORDER BY t.created_at", *args))


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        task = await c.fetchrow("SELECT * FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if task is None:
            raise HTTPException(404, "Task not found or not permitted")
        subs = await c.fetch("SELECT * FROM tasks WHERE parent_id=$1 AND is_deleted=false ORDER BY created_at", task_id)
        prog = await c.fetch("SELECT day_label,note,created_at FROM task_progress WHERE task_id=$1 ORDER BY created_at", task_id)
        sessions = await c.fetch("SELECT * FROM work_sessions WHERE task_id=$1 ORDER BY started_at", task_id)
        links = await c.fetch("SELECT * FROM task_links WHERE task_id=$1 ORDER BY created_at", task_id)
        return {"task": dict(task), "subtasks": _ser(subs), "progress": _ser(prog),
                "sessions": [_session_out(s) for s in sessions], "links": _ser(links)}


class TaskIn(BaseModel):
    title: str
    description: str | None = None
    status: Status = "pending"
    priority: str = "medium"
    task_type: TaskType = "other"
    reference_code: str | None = None
    external_ref: str | None = None
    blocker_reason: str | None = None
    recurrence: dict | None = None
    department: str | None = None
    department_id: str | None = None
    week_id: str | None = None
    week_start: date | None = None
    due_date: date | None = None
    parent_id: str | None = None
    days: list[str] = []
    tags: list[str] = []
    estimated_hours: Decimal | None = Field(default=None, ge=0)


_RECURRENCE_FREQS = {"daily", "weekly", "monthly"}


def _check_recurrence(rec: dict | None) -> None:
    if rec is None:
        return
    if rec.get("freq") not in _RECURRENCE_FREQS:
        raise HTTPException(422, "recurrence.freq must be daily|weekly|monthly")
    if not isinstance(rec.get("interval", 1), int) or rec.get("interval", 1) < 1:
        raise HTTPException(422, "recurrence.interval must be a positive integer")


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, user: dict = Depends(require_password_set)):
    _check_recurrence(body.recurrence)
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO tasks(org_id,user_id,parent_id,title,description,status,priority,"
            " task_type,reference_code,external_ref,blocker_reason,recurrence,"
            " department,department_id,week_id,week_start,due_date,days,tags,estimated_hours,"
            " created_by,updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$2,$2)"
            " RETURNING *",
            user["org_id"], user["id"], body.parent_id, body.title, body.description, body.status,
            body.priority, body.task_type, body.reference_code, body.external_ref, body.blocker_reason,
            body.recurrence, body.department, body.department_id, body.week_id,
            body.week_start, body.due_date, body.days, body.tags, body.estimated_hours,
        )
    return dict(row)


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: Status | None = None
    priority: str | None = None
    workflow_state: str | None = None
    task_type: TaskType | None = None
    reference_code: str | None = None
    external_ref: str | None = None
    blocker_reason: str | None = None
    recurrence: dict | None = None
    outcome: str | None = None
    is_archived: bool | None = None
    days: list[str] | None = None
    tags: list[str] | None = None
    week_id: str | None = None
    week_start: date | None = None
    due_date: date | None = None
    completed_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    actual_hours: Decimal | None = Field(default=None, ge=0)


# Columns a PATCH may set to SQL NULL. exclude_unset (not exclude_none)
# distinguishes "field omitted" from "field explicitly null", so clearing
# logged hours / a week assignment / a due date round-trips; None on a
# NOT NULL column (title, status, ...) is still treated as not-provided.
_NULLABLE_PATCH_COLS = {"description", "week_id", "week_start", "estimated_hours", "actual_hours",
                        "due_date", "completed_date", "reference_code", "external_ref",
                        "blocker_reason", "recurrence", "outcome"}


def _advance(d: date, rec: dict) -> date:
    interval = int(rec.get("interval", 1))
    freq = rec["freq"]
    if freq == "daily":
        return d + timedelta(days=interval)
    if freq == "weekly":
        return d + timedelta(weeks=interval)
    # monthly: same day-of-month, clamped
    month = d.month - 1 + interval
    year, month = d.year + month // 12, month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


async def _materialize_recurrence(c, row) -> dict | None:
    """When a recurring task completes, create its next instance: same
    definition, dates advanced by the recurrence rule, fresh lifecycle.
    Stops silently once `until` is passed."""
    rec = row["recurrence"]
    base = row["due_date"] or row["week_start"] or date.today()
    nxt = _advance(base, rec)
    until = rec.get("until")
    if until and nxt > date.fromisoformat(str(until)):
        return None
    next_week_start = _advance(row["week_start"], rec) if row["week_start"] else None
    new = await c.fetchrow(
        "INSERT INTO tasks(org_id,user_id,parent_id,title,description,status,priority,"
        " task_type,reference_code,recurrence,department,department_id,week_start,due_date,"
        " days,tags,estimated_hours,created_by,updated_by)"
        " SELECT org_id,user_id,parent_id,title,description,'pending',priority,"
        " task_type,reference_code,recurrence,department,department_id,$2,$3,"
        " days,tags,estimated_hours,$4,$4 FROM tasks WHERE id=$1 RETURNING *",
        row["id"], next_week_start, nxt if row["due_date"] else None, row["updated_by"])
    return dict(new) if new else None


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskPatch, user: dict = Depends(require_password_set)):
    patch = body.model_dump(exclude_unset=True)
    if "recurrence" in patch:
        _check_recurrence(patch["recurrence"])
    fields, args = [], []
    for col, val in patch.items():
        if val is None and col not in _NULLABLE_PATCH_COLS:
            continue
        args.append(val); fields.append(f"{col}=${len(args)}")
    if not fields:
        return {"ok": True, "noop": True}
    # Completing a task stamps completed_date unless the caller set one.
    if patch.get("status") == "completed" and "completed_date" not in patch:
        args.append(date.today()); fields.append(f"completed_date=${len(args)}")
    args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
    args.append(task_id)
    async with rls(user) as c:
        row = await c.fetchrow(
            f"UPDATE tasks SET {', '.join(fields)}, updated_at=now() WHERE id=${len(args)}"
            f" AND is_deleted=false RETURNING *", *args)
        if row is None:
            raise HTTPException(404, "Task not found or not permitted")
        out = dict(row)
        # A recurring task that just completed spawns its next instance.
        if patch.get("status") == "completed" and row["recurrence"]:
            nxt = await _materialize_recurrence(c, row)
            if nxt:
                out["next_instance"] = nxt
    return out


class ProgressIn(BaseModel):
    day_label: str
    note: str


@router.post("/tasks/{task_id}/progress", status_code=201)
async def add_progress(task_id: str, body: ProgressIn, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO task_progress(org_id,task_id,user_id,day_label,note)"
            " VALUES ($1,$2,$3,$4,$5) RETURNING day_label,note,created_at",
            user["org_id"], task_id, user["id"], body.day_label, body.note)
    return dict(row)


# ── Work sessions (overtime engine) ─────────────────────────────────────────
class SessionIn(BaseModel):
    started_at: datetime
    ended_at: datetime | None = None
    hours: Decimal | None = Field(default=None, gt=0)
    note: str | None = None
    source: Literal["manual", "timer", "capture"] = "manual"


def _facility_tz(dt: datetime | None) -> datetime | None:
    """Timestamps without an offset mean facility wall-clock (Europe/Skopje)
    — that's how people (and the capture prompt) state when work happened.
    Interpreting them as UTC would shift every overtime/night classification
    by the offset."""
    from app.worktime import TZ
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt


def _session_out(r) -> dict:
    return {
        "id": str(r["id"]), "task_id": str(r["task_id"]), "user_id": str(r["user_id"]),
        "started_at": r["started_at"].isoformat(),
        "ended_at": r["ended_at"].isoformat() if r["ended_at"] else None,
        "hours": round(session_hours(r), 2),
        "note": r["note"], "source": r["source"],
        "classification": classify(r["started_at"]),
    }


@router.post("/tasks/{task_id}/sessions", status_code=201)
async def add_session(task_id: str, body: SessionIn, user: dict = Depends(require_password_set)):
    body.started_at = _facility_tz(body.started_at)
    body.ended_at = _facility_tz(body.ended_at)
    if body.ended_at is None and body.hours is None:
        raise HTTPException(422, "Provide ended_at or hours")
    if body.ended_at is not None and body.ended_at <= body.started_at:
        raise HTTPException(422, "ended_at must be after started_at")
    async with rls(user) as c:
        task = await c.fetchrow("SELECT id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if task is None:
            raise HTTPException(404, "Task not found or not permitted")
        row = await c.fetchrow(
            "INSERT INTO work_sessions(org_id,task_id,user_id,started_at,ended_at,hours,note,source)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
            user["org_id"], task_id, user["id"], body.started_at, body.ended_at,
            body.hours, body.note, body.source)
    return _session_out(row)


@router.get("/tasks/{task_id}/sessions")
async def list_sessions(task_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        task = await c.fetchrow("SELECT id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if task is None:
            raise HTTPException(404, "Task not found or not permitted")
        rows = await c.fetch("SELECT * FROM work_sessions WHERE task_id=$1 ORDER BY started_at", task_id)
    return [_session_out(r) for r in rows]


_ELEVATED = {"ADMIN", "DEPT_HEAD", "PROJECT_LEAD"}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(require_password_set)):
    """Only the person who logged a session (or an elevated role) may remove
    it — sessions are the overtime evidence, so deletion stays narrow (and is
    audit-trailed by the row trigger either way)."""
    async with rls(user) as c:
        row = await c.fetchrow("SELECT user_id FROM work_sessions WHERE id=$1", session_id)
        if row is None:
            raise HTTPException(404, "Session not found")
        if str(row["user_id"]) != str(user["id"]) and user["role"] not in _ELEVATED:
            raise HTTPException(403, "Only the session's author or an elevated role can delete it")
        await c.execute("DELETE FROM work_sessions WHERE id=$1", session_id)
    return {"ok": True}


# ── Task links (external references — Drive docs, SOPs) ─────────────────────
class LinkIn(BaseModel):
    url: str
    label: str | None = None
    kind: Literal["drive", "sop", "doc", "other"] = "other"


@router.post("/tasks/{task_id}/links", status_code=201)
async def add_link(task_id: str, body: LinkIn, user: dict = Depends(require_password_set)):
    url = (body.url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "url must be http(s)")
    async with rls(user) as c:
        task = await c.fetchrow("SELECT id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if task is None:
            raise HTTPException(404, "Task not found or not permitted")
        row = await c.fetchrow(
            "INSERT INTO task_links(org_id,task_id,url,label,kind,created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6) RETURNING *",
            user["org_id"], task_id, url, body.label, body.kind, user["id"])
    return dict(row)


@router.delete("/tasks/{task_id}/links/{link_id}")
async def delete_link(task_id: str, link_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        res = await c.execute("DELETE FROM task_links WHERE id=$1 AND task_id=$2", link_id, task_id)
    if res.split()[-1] == "0":
        raise HTTPException(404, "Link not found")
    return {"ok": True}
