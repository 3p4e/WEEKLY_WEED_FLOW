"""Task lifecycle API (RLS-scoped via app_user + per-request identity GUCs)."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import rls
from app.deps import require_password_set

router = APIRouter(tags=["tasks"])


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


@router.get("/tasks")
async def list_tasks(
    week_id: str | None = None,
    department_id: str | None = None,
    parents_only: bool = False,
    user: dict = Depends(require_password_set),
):
    clauses, args = ["t.is_deleted=false"], []
    if week_id:
        args.append(week_id); clauses.append(f"t.week_id=${len(args)}")
    if department_id:
        args.append(department_id); clauses.append(f"t.department_id=${len(args)}")
    if parents_only:
        clauses.append("t.parent_id IS NULL")
    where = " AND ".join(clauses)
    async with rls(user) as c:
        return _ser(await c.fetch(
            f"SELECT t.id,t.user_id,t.parent_id,t.title,t.description,t.status,t.priority,t.workflow_state,"
            f"t.department,t.department_id,t.week_id,t.week_start,t.days,t.tags,t.deps,t.progress_notes,"
            f"t.due_date,t.completed_date,t.estimated_hours,t.actual_hours,t.created_at,t.updated_at,"
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
        return {"task": dict(task), "subtasks": _ser(subs), "progress": _ser(prog)}


class TaskIn(BaseModel):
    title: str
    description: str | None = None
    status: str = "pending"
    priority: str = "medium"
    department: str | None = None
    department_id: str | None = None
    week_id: str | None = None
    week_start: date | None = None
    parent_id: str | None = None
    days: list[str] = []
    tags: list[str] = []
    estimated_hours: Decimal | None = Field(default=None, ge=0)


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO tasks(org_id,user_id,parent_id,title,description,status,priority,"
            " department,department_id,week_id,week_start,days,tags,estimated_hours,created_by,updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$2,$2) RETURNING *",
            user["org_id"], user["id"], body.parent_id, body.title, body.description, body.status,
            body.priority, body.department, body.department_id, body.week_id,
            body.week_start, body.days, body.tags, body.estimated_hours,
        )
    return dict(row)


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    workflow_state: str | None = None
    days: list[str] | None = None
    tags: list[str] | None = None
    week_id: str | None = None
    week_start: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    actual_hours: Decimal | None = Field(default=None, ge=0)


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskPatch, user: dict = Depends(require_password_set)):
    fields, args = [], []
    for col, val in body.model_dump(exclude_none=True).items():
        args.append(val); fields.append(f"{col}=${len(args)}")
    if not fields:
        return {"ok": True, "noop": True}
    args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
    args.append(task_id)
    async with rls(user) as c:
        row = await c.fetchrow(
            f"UPDATE tasks SET {', '.join(fields)}, updated_at=now() WHERE id=${len(args)}"
            f" AND is_deleted=false RETURNING *", *args)
    if row is None:
        raise HTTPException(404, "Task not found or not permitted")
    return dict(row)


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
