"""Task lifecycle API (RLS-scoped via app_user + per-request identity GUCs)."""
from datetime import date
from fastapi import APIRouter, Depends
from pydantic import BaseModel

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
    clauses, args = ["is_deleted=false"], []
    if week_id:
        args.append(week_id); clauses.append(f"week_id=${len(args)}")
    if department_id:
        args.append(department_id); clauses.append(f"department_id=${len(args)}")
    if parents_only:
        clauses.append("parent_id IS NULL")
    where = " AND ".join(clauses)
    async with rls(user) as c:
        return _ser(await c.fetch(
            f"SELECT id,parent_id,title,description,status,priority,workflow_state,department,"
            f"department_id,week_id,week_start,days,tags,deps,progress_notes,due_date,"
            f"completed_date,created_at,updated_at FROM tasks WHERE {where} ORDER BY created_at", *args))


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        task = await c.fetchrow("SELECT * FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if task is None:
            return {"error": "not_found"}
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


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO tasks(org_id,user_id,parent_id,title,description,status,priority,"
            " department,department_id,week_id,week_start,days,tags,created_by,updated_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$2,$2) RETURNING *",
            user["org_id"], user["id"], body.parent_id, body.title, body.description, body.status,
            body.priority, body.department, body.department_id, body.week_id,
            body.week_start, body.days, body.tags,
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
    return dict(row) if row else {"error": "not_found_or_forbidden"}


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
