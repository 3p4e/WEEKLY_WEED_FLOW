"""Task lifecycle API (RLS-scoped via app_user + per-request identity GUCs).

v2 task model: task_type / reference_code / due_date / blocker_reason /
recurrence / outcome / archive on tasks, plus two child resources —
work_sessions (every sitting of real work; the overtime engine's source of
truth) and task_links (external Drive/SOP references)."""
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.automation import canned_recipients
from app.db import rls
from app.deps import dept_scope, require_password_set, require_role
from app.notify import emit, participants
from app.roles import ADMIN, ELEVATED_ROLES
from app.worktime import classify, session_hours

router = APIRouter(tags=["tasks"])

Status = Literal["pending", "ongoing", "review", "stuck", "postponed", "completed"]
TaskType = Literal["capa", "sop", "validation", "document", "lab", "meeting", "admin", "other"]
# node_kind is the task's ROLE in the tree (harvested from qc-lims-ao), distinct
# from task_type (the domain category): a 'task' is ordinary work; an 'annex' is
# a document/form node under a parent; a 'step' is an execution step under one.
NodeKind = Literal["task", "annex", "step"]
# "normal" is the wire value the GrowFlow UI sends for medium (P_OUT in
# integrate.js); the capture path uses "medium". Both are accepted; anything
# else is a clean 422 instead of silently sorting last in priority views.
Priority = Literal["low", "normal", "medium", "high", "critical"]

# FK-bearing columns whose bad/non-existent value should be a 422, not a 500.
_FK_ERRORS = (asyncpg.ForeignKeyViolationError, asyncpg.DataError, asyncpg.InvalidTextRepresentationError)



_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _uuid_or_422(val: str | None, name: str) -> None:
    """Malformed uuids on raw-SQL read paths otherwise surface as asyncpg
    cast errors -> 500; the write paths already map them via _FK_ERRORS."""
    if val is not None and not _UUID_RE.match(str(val)):
        raise HTTPException(422, f"{name} must be a uuid")

def _ser(rows):
    return [dict(r) for r in rows]


async def _assert_scope_visible(c, task_id: str, user: dict) -> None:
    """THE single in-scope guard for department-scoped managers. RLS alone is
    NOT a department boundary — app.is_elevated() grants every manager role
    org-wide row access (department scoping is an app-layer concept, see
    app/roles.DEPT_SCOPED_ROLES), so every task read/mutation and sub-resource
    endpoint whose access could otherwise reach org-wide must call this.

    In-scope = own dept, personally owned, assigned, a subtask delegated into
    my dept, or a child whose parent lives in my dept. Org-wide roles
    (dept_scope is None) are unaffected. Raises 404 rather than 403 to avoid
    confirming a foreign task's existence.

    get_task and every guarded write path call THIS function (not a re-derived
    copy of the rule) so read-scope and write-scope can never drift apart —
    the drift that silently reopens this exact bypass class. When adding a new
    endpoint that touches a task (or its sub-resources) by id, call this."""
    scope = dept_scope(user)
    if not scope:
        return
    visible = await c.fetchval(
        "SELECT EXISTS (SELECT 1 FROM tasks t WHERE t.id=$1 AND t.is_deleted=false AND ("
        " t.department_id=$2 OR t.user_id=$3"
        " OR EXISTS (SELECT 1 FROM task_assignees a WHERE a.task_id=t.id AND a.user_id=$3)"
        " OR EXISTS (SELECT 1 FROM tasks ch WHERE ch.parent_id=t.id AND ch.department_id=$2 AND ch.is_deleted=false)"
        " OR EXISTS (SELECT 1 FROM tasks pa WHERE pa.id=t.parent_id AND pa.department_id=$2)"
        "))",
        task_id, scope, str(user["id"]))
    if not visible:
        raise HTTPException(404, "Task not found or not permitted")


@router.get("/departments")
async def departments(user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        return _ser(await c.fetch("SELECT id,code,name,name_mk,parent_id,is_active FROM departments ORDER BY name"))


class DepartmentIn(BaseModel):
    # Backend codes are the stable keys the frontend templates hang off
    # (web/gf/dept-templates.js) — same charset rule as attribute keys.
    code: str = Field(max_length=64, pattern=r"^[a-z0-9_]{1,64}$")
    name: str = Field(max_length=120)
    name_mk: str | None = Field(default=None, max_length=120)


@router.post("/departments", status_code=201)
async def create_department(body: DepartmentIn, user: dict = Depends(require_role(ADMIN))):
    """ADMIN-only, idempotent department creation. Until now live departments
    were seeded out-of-band; the test-account provisioning script
    (backend/scripts/provision_test_accounts.py) needs a first-class API path
    that keeps the audit trail intact. Managers (who may provision USER staff)
    and executives deliberately may NOT create departments — org structure is
    a system-administration concern. Idempotent: re-POSTing an existing code
    returns the existing row (UNIQUE (org_id, code) + DO NOTHING), so reruns
    are safe. Inside rls(user) so the audit_departments trigger attributes the
    actor and RLS pins the org."""
    async with rls(user) as c:
        row = await c.fetchrow(
            "INSERT INTO departments(org_id, code, name, name_mk) VALUES ($1,$2,$3,$4)"
            " ON CONFLICT (org_id, code) DO NOTHING RETURNING *",
            user["org_id"], body.code, body.name, body.name_mk)
        if row is None:  # already existed — return it unchanged
            row = await c.fetchrow(
                "SELECT * FROM departments WHERE org_id=$1 AND code=$2",
                user["org_id"], body.code)
    return dict(row)


@router.get("/weeks")
async def weeks(user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        return _ser(await c.fetch(
            "SELECT id,iso_year,iso_week,starts_on,ends_on FROM calendar_weeks ORDER BY starts_on DESC"))


_TASK_COLS = (
    "t.id,t.user_id,t.parent_id,t.title,t.description,t.status,t.priority,t.workflow_state,"
    "t.task_type,t.node_kind,t.reference_code,t.external_ref,t.blocker_reason,t.recurrence,t.outcome,t.is_archived,"
    "t.department,t.department_id,t.week_id,t.week_start,t.days,t.tags,t.attributes,t.progress,"
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
    _uuid_or_422(week_id, "week_id")
    _uuid_or_422(department_id, "department_id")
    clauses, args = ["t.is_deleted=false"], []
    if not include_archived:
        clauses.append("t.is_archived=false")
    if week_id:
        args.append(week_id); clauses.append(f"t.week_id=${len(args)}")
    if department_id:
        args.append(department_id); clauses.append(f"t.department_id=${len(args)}")
    if parents_only:
        clauses.append("t.parent_id IS NULL")
    # Department managers see their own department's tasks plus anything they
    # personally own or are assigned (so cross-department handoffs they're on
    # never vanish). Executives / QP / ADMIN stay org-wide (scope is None).
    # Multi-departmental families stay visible IN FULL to every side involved:
    # a parent task whose subtask is delegated to my department, and a subtask
    # whose parent lives in my department, both match.
    scope = dept_scope(user)
    if scope:
        args.append(scope); d = len(args)
        args.append(str(user["id"])); u = len(args)
        clauses.append(
            f"(t.department_id=${d} OR t.user_id=${u}"
            f" OR EXISTS (SELECT 1 FROM task_assignees sa WHERE sa.task_id=t.id AND sa.user_id=${u})"
            f" OR EXISTS (SELECT 1 FROM tasks ch WHERE ch.parent_id=t.id"
            f"            AND ch.department_id=${d} AND ch.is_deleted=false)"
            f" OR EXISTS (SELECT 1 FROM tasks pa WHERE pa.id=t.parent_id AND pa.department_id=${d}))")
    where = " AND ".join(clauses)
    async with rls(user) as c:
        return _ser(await c.fetch(
            f"SELECT {_TASK_COLS},"
            # progress_notes has no column of its own — task_progress is the only
            # write path (POST /tasks/{id}/progress), so this reads live from it
            # instead of trusting a denormalized copy that could go stale.
            f"COALESCE((SELECT jsonb_agg(jsonb_build_object("
            # user_id rides along so the UI can attribute notes — executive
            # (OWNER/CEO/COO) input is visually highlighted on the cards.
            f"  'day_label', tp.day_label, 'note', tp.note, 'created_at', tp.created_at, 'user_id', tp.user_id"
            f") ORDER BY tp.created_at DESC) FROM (SELECT day_label, note, created_at, user_id FROM task_progress"
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


def _scope_clause(user: dict, args: list) -> str:
    """The department-manager visibility predicate shared by list/tree — own
    department, personally owned/assigned, or either side of a multi-dept
    family. Executives / QP / ADMIN have scope None → no clause (org-wide).
    Appends its bind params to `args` and returns the SQL fragment (or '')."""
    scope = dept_scope(user)
    if not scope:
        return ""
    args.append(scope); d = len(args)
    args.append(str(user["id"])); u = len(args)
    return (
        f" AND (t.department_id=${d} OR t.user_id=${u}"
        f" OR EXISTS (SELECT 1 FROM task_assignees sa WHERE sa.task_id=t.id AND sa.user_id=${u})"
        f" OR EXISTS (SELECT 1 FROM tasks ch WHERE ch.parent_id=t.id AND ch.department_id=${d} AND ch.is_deleted=false)"
        f" OR EXISTS (SELECT 1 FROM tasks pa WHERE pa.id=t.parent_id AND pa.department_id=${d}))")


@router.get("/tasks/tree")
async def task_tree(include_archived: bool = False, user: dict = Depends(require_password_set)):
    """The task hierarchy as a flat, scoped list the client nests by parent_id.
    Lightweight columns only (id/parent_id/title/node_kind/status/priority/
    task_type/department_id/due_date/dep counts) — the board renders a
    document→annex→step spine without pulling every task's full detail. Ordered
    parent-first then created_at so a simple client fold reconstructs the tree.
    (Declared before /tasks/{task_id} so 'tree' isn't captured as a task id.)"""
    args: list = []
    arch = "" if include_archived else " AND t.is_archived=false"
    where = "t.is_deleted=false" + arch + _scope_clause(user, args)
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT t.id,t.parent_id,t.title,t.node_kind,t.status,t.priority,t.task_type,"
            "t.department_id,t.due_date,t.progress,"
            "(SELECT count(*) FROM task_dependencies dd WHERE dd.task_id=t.id) AS blocked_by_count "
            f"FROM tasks t WHERE {where} ORDER BY t.parent_id NULLS FIRST, t.created_at", *args)
    return _ser(rows)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: dict = Depends(require_password_set)):
    if not _UUID_RE.match(str(task_id)):
        raise HTTPException(404, "Task not found")
    async with rls(user) as c:
        task = await c.fetchrow("SELECT * FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if task is None:
            raise HTTPException(404, "Task not found or not permitted")
        # By-id reads honour the same department scoping as every write path —
        # ONE shared rule (_assert_scope_visible) so read-scope and write-scope
        # can never drift apart. (A department-less manager has scope None →
        # org-wide read, same as their board — intentional.)
        await _assert_scope_visible(c, task_id, user)
        subs = await c.fetch("SELECT * FROM tasks WHERE parent_id=$1 AND is_deleted=false ORDER BY created_at", task_id)
        prog = await c.fetch("SELECT day_label,note,created_at,user_id FROM task_progress WHERE task_id=$1 ORDER BY created_at", task_id)
        sessions = await c.fetch("SELECT * FROM work_sessions WHERE task_id=$1 ORDER BY started_at", task_id)
        links = await c.fetch("SELECT * FROM task_links WHERE task_id=$1 ORDER BY created_at", task_id)
        # Dependency edges: what this task is blocked_by, and (reverse) what it
        # blocks. Each carries the depended-on task's title + status so the UI
        # can render "blocked by X (ongoing)" without a second round trip.
        blocked_by = await c.fetch(
            "SELECT d.depends_on_task_id AS id, t.title, t.status FROM task_dependencies d"
            " JOIN tasks t ON t.id=d.depends_on_task_id AND t.is_deleted=false"
            " WHERE d.task_id=$1 ORDER BY t.created_at", task_id)
        blocks = await c.fetch(
            "SELECT d.task_id AS id, t.title, t.status FROM task_dependencies d"
            " JOIN tasks t ON t.id=d.task_id AND t.is_deleted=false"
            " WHERE d.depends_on_task_id=$1 ORDER BY t.created_at", task_id)
        return {"task": dict(task), "subtasks": _ser(subs), "progress": _ser(prog),
                "sessions": [_session_out(s) for s in sessions], "links": _ser(links),
                "blocked_by": _ser(blocked_by), "blocks": _ser(blocks)}


class TaskIn(BaseModel):
    # max_length bounds are DoS hygiene, not business rules — no field here has
    # a legitimate form anywhere near these caps.
    title: str = Field(max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    status: Status = "pending"
    priority: Priority = "medium"
    task_type: TaskType = "other"
    node_kind: NodeKind = "task"
    reference_code: str | None = Field(default=None, max_length=80)
    external_ref: str | None = Field(default=None, max_length=200)
    blocker_reason: str | None = Field(default=None, max_length=2000)
    recurrence: dict | None = None
    department: str | None = Field(default=None, max_length=120)
    department_id: str | None = None
    week_id: str | None = None
    week_start: date | None = None
    due_date: date | None = None
    parent_id: str | None = None
    days: list[str] = []
    tags: list[str] = []
    attributes: dict | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    progress: int = Field(default=0, ge=0, le=100)


_RECURRENCE_FREQS = {"daily", "weekly", "monthly"}
# L3: an unbounded interval sails through the positive-int check but then
# overflows date arithmetic at rollover — a 500 that rolls back (and so
# permanently blocks) the completion that triggers it. 1000 covers every real
# cadence (every 1000 months ≈ 83y) while keeping base+interval*unit in range.
_RECUR_INTERVAL_MAX = 1000
# L5: DoS hygiene on the free-form tag list (bounds, not a business rule).
_TAGS_MAX = 32
_TAG_MAX_LEN = 64

# The UI writes 3-letter capitalized tokens (GF.DAYS in web/gf/data.js);
# anything else in days text[] is a typo or an API caller inventing values
# every consumer (board columns, per-day chips) would silently fail to show.
_DAY_TOKENS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}


def _check_days(days: list[str] | None) -> None:
    if not days:
        return
    bad = [d for d in days if d not in _DAY_TOKENS]
    if bad:
        raise HTTPException(422, f"days must be Mon..Sun tokens, got: {', '.join(map(str, bad[:3]))}")


def _check_tags(tags: list[str] | None) -> None:
    if not tags:
        return
    if len(tags) > _TAGS_MAX:
        raise HTTPException(422, f"tags: at most {_TAGS_MAX}")
    if any(not isinstance(t, str) or len(t) > _TAG_MAX_LEN for t in tags):
        raise HTTPException(422, f"tags: each tag must be a string of at most {_TAG_MAX_LEN} chars")


# Department-template metadata (room, strain, sample_ref, equipment_ref, …).
# Shape-only validation — WHICH keys a department uses is a frontend template
# concern (web/gf/dept-templates.js), so new fields never need a backend
# change. Bounds are abuse hygiene: snake_case keys, scalar values, small map.
_ATTR_KEY_RE = re.compile(r"^[a-z0-9_]{1,48}$")
_ATTR_MAX_KEYS = 24
_ATTR_MAX_STR = 500
_ATTR_MAX_BYTES = 8192


def _check_attributes(attrs: dict | None) -> None:
    if attrs is None:
        return
    if len(attrs) > _ATTR_MAX_KEYS:
        raise HTTPException(422, f"attributes: at most {_ATTR_MAX_KEYS} keys")
    for k, v in attrs.items():
        if not isinstance(k, str) or not _ATTR_KEY_RE.match(k):
            raise HTTPException(422, "attributes: keys must match ^[a-z0-9_]{1,48}$")
        if isinstance(v, str):
            if len(v) > _ATTR_MAX_STR:
                raise HTTPException(422, f"attributes.{k}: strings are capped at {_ATTR_MAX_STR} chars")
        elif not isinstance(v, (int, float, bool)) or v is None:
            raise HTTPException(422, f"attributes.{k}: values must be scalar (string, number, boolean)")
    if len(json.dumps(attrs)) > _ATTR_MAX_BYTES:
        raise HTTPException(422, f"attributes: serialized size is capped at {_ATTR_MAX_BYTES} bytes")


def _check_recurrence(rec: dict | None) -> None:
    if rec is None:
        return
    if rec.get("freq") not in _RECURRENCE_FREQS:
        raise HTTPException(422, "recurrence.freq must be daily|weekly|monthly")
    iv = rec.get("interval", 1)
    if not isinstance(iv, int) or isinstance(iv, bool) or iv < 1 or iv > _RECUR_INTERVAL_MAX:
        raise HTTPException(422, f"recurrence.interval must be an integer in 1..{_RECUR_INTERVAL_MAX}")
    # `until` is only parsed later, inside the completion transaction — validate
    # it here so a bad value is a clean 422 at write time, not a 500 that rolls
    # back (and permanently blocks) the completion that triggers it.
    until = rec.get("until")
    if until not in (None, ""):
        try:
            date.fromisoformat(str(until))
        except ValueError:
            raise HTTPException(422, "recurrence.until must be an ISO date (YYYY-MM-DD)")


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, user: dict = Depends(require_password_set)):
    _check_recurrence(body.recurrence)
    _check_days(body.days)
    _check_attributes(body.attributes)
    _check_tags(body.tags)
    # A dept-scoped manager creates TOP-LEVEL tasks in their own department
    # only; an omitted department defaults to theirs instead of landing
    # unassigned (which their scoped list could then never show them again).
    # SUBTASKS may target ANY department when the parent is the manager's own
    # (or personally theirs) — that delegation is exactly how a task becomes
    # multi-departmental, visible in full to every side involved.
    scope = dept_scope(user)
    if scope and not body.parent_id:
        if body.department_id and str(body.department_id) != scope:
            raise HTTPException(403, "Managers may create tasks only in their own department")
        if not body.department_id:
            body.department_id = scope
    async with rls(user) as c:
        if scope and body.parent_id:
            parent = await c.fetchrow(
                "SELECT department_id, user_id FROM tasks WHERE id=$1 AND is_deleted=false",
                body.parent_id)
            if parent is None:
                raise HTTPException(422, "Unknown department, week, or parent task")
            mine = (parent["department_id"] and str(parent["department_id"]) == scope) \
                or str(parent["user_id"]) == str(user["id"])
            if not mine:
                # A foreign parent is attachable ONLY if it is ALREADY visible
                # to this manager (existing multi-departmental family / own or
                # assigned task). Without this, attaching a child in their own
                # department to ANY org task uuid would grant them the family
                # visibility clause on that task — a self-served scope
                # escalation (_assert_scope_visible counts existing children,
                # so the check runs before the new child exists).
                await _assert_scope_visible(c, str(body.parent_id), user)
            if not mine and body.department_id and str(body.department_id) != scope:
                raise HTTPException(403, "Managers may delegate subtasks only under their own department's tasks")
            if not body.department_id:
                # Inherit the parent's department ONLY when the parent is the
                # manager's own — otherwise an omitted department_id under a
                # FOREIGN parent would silently plant the child in that other
                # department. Default to the manager's own scope in that case.
                body.department_id = str(parent["department_id"]) if (mine and parent["department_id"]) else scope
        try:
            row = await c.fetchrow(
                "INSERT INTO tasks(org_id,user_id,parent_id,title,description,status,priority,"
                " task_type,node_kind,reference_code,external_ref,blocker_reason,recurrence,"
                " department,department_id,week_id,week_start,due_date,days,tags,attributes,"
                " estimated_hours,progress,created_by,updated_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$2,$2)"
                " RETURNING *",
                user["org_id"], user["id"], body.parent_id, body.title, body.description, body.status,
                body.priority, body.task_type, body.node_kind, body.reference_code, body.external_ref,
                body.blocker_reason, body.recurrence, body.department, body.department_id, body.week_id,
                body.week_start, body.due_date, body.days, body.tags, body.attributes or {},
                body.estimated_hours, body.progress,
            )
        except _FK_ERRORS:
            raise HTTPException(422, "Unknown department, week, or parent task")
        # Feed-only awareness (NO recipients): creation never notifies —
        # Slack/Linear defaults — but the shared activity stream shows it,
        # which is what makes exec-created work visible to the org.
        try:
            await emit(c, user, verb="created", object_type="task", object_id=row["id"],
                       recipients=[], task_id=row["id"], department_id=row["department_id"],
                       params={"title": row["title"]})
        except Exception:
            pass
    return dict(row)


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    status: Status | None = None
    priority: Priority | None = None
    workflow_state: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,32}$")
    task_type: TaskType | None = None
    node_kind: NodeKind | None = None
    department: str | None = Field(default=None, max_length=120)
    department_id: str | None = None
    reference_code: str | None = Field(default=None, max_length=80)
    external_ref: str | None = Field(default=None, max_length=200)
    blocker_reason: str | None = Field(default=None, max_length=2000)
    recurrence: dict | None = None
    outcome: str | None = Field(default=None, max_length=2000)
    is_archived: bool | None = None
    days: list[str] | None = None
    tags: list[str] | None = None
    attributes: dict | None = None
    week_id: str | None = None
    week_start: date | None = None
    due_date: date | None = None
    completed_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    actual_hours: Decimal | None = Field(default=None, ge=0)
    progress: int | None = Field(default=None, ge=0, le=100)


# Columns a PATCH may set to SQL NULL. exclude_unset (not exclude_none)
# distinguishes "field omitted" from "field explicitly null", so clearing
# logged hours / a week assignment / a due date round-trips; None on a
# NOT NULL column (title, status, ...) is still treated as not-provided.
_NULLABLE_PATCH_COLS = {"description", "week_id", "week_start", "estimated_hours", "actual_hours",
                        "due_date", "completed_date", "reference_code", "external_ref",
                        "blocker_reason", "recurrence", "outcome",
                        # department_id is a nullable FK (ON DELETE SET NULL) and
                        # department is its nullable text label — an explicit
                        # PATCH {"department_id": null} must clear the assignment,
                        # not be silently dropped as "field omitted".
                        "department", "department_id"}


def _advance(d: date, rec: dict) -> date:
    interval = int(rec.get("interval", 1))
    freq = rec["freq"]
    if freq == "daily":
        return d + timedelta(days=interval)
    if freq == "weekly":
        return d + timedelta(weeks=interval)
    # monthly: same day-of-month, clamped. anchor_day (RFC-5545 semantics)
    # remembers the ORIGINAL day so a Jan-31 monthly task clamped to Feb-28
    # springs back to Mar-31 instead of drifting to the 28th forever.
    month = d.month - 1 + interval
    year, month = d.year + month // 12, month % 12 + 1
    anchor = int(rec.get("anchor_day") or d.day)
    day = min(anchor, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


async def _materialize_recurrence(c, row) -> dict | None:
    """When a recurring task completes, create its next instance: same
    definition, dates advanced by the recurrence rule, fresh lifecycle.
    Stops silently once `until` is passed."""
    rec = dict(row["recurrence"])
    base = row["due_date"] or row["week_start"] or date.today()
    # Pin the monthly day anchor on first materialization (before any clamp
    # rewrites it) so the cadence never drifts off the original day-of-month.
    if rec.get("freq") == "monthly" and not rec.get("anchor_day"):
        rec["anchor_day"] = base.day
    nxt = _advance(base, rec)
    until = rec.get("until")
    if until and nxt > date.fromisoformat(str(until)):
        return None
    next_week_start = _advance(row["week_start"], rec) if row["week_start"] else None
    # Resolve the next instance's calendar week so it still shows up in
    # ?week_id= week views (it lands in a different week than the completed one).
    next_week_id = None
    if next_week_start is not None:
        next_week_id = await c.fetchval(
            "SELECT id FROM calendar_weeks WHERE org_id=$1 AND starts_on=$2",
            row["org_id"], next_week_start)
    new = await c.fetchrow(
        "INSERT INTO tasks(org_id,user_id,parent_id,title,description,status,priority,"
        " task_type,node_kind,reference_code,recurrence,department,department_id,week_id,week_start,due_date,"
        " days,tags,attributes,estimated_hours,created_by,updated_by)"
        " SELECT org_id,user_id,parent_id,title,description,'pending',priority,"
        " task_type,node_kind,reference_code,$6,department,department_id,$2,$3,$4,"
        " days,tags,attributes,estimated_hours,$5,$5 FROM tasks WHERE id=$1 RETURNING *",
        row["id"], next_week_id, next_week_start, nxt if row["due_date"] else None,
        row["updated_by"], rec)
    return dict(new) if new else None


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskPatch, user: dict = Depends(require_password_set)):
    patch = body.model_dump(exclude_unset=True)
    if "recurrence" in patch:
        _check_recurrence(patch["recurrence"])
    if "days" in patch:
        _check_days(patch["days"])
    if "tags" in patch:
        _check_tags(patch["tags"])
    if "attributes" in patch:
        _check_attributes(patch["attributes"])
        # The column is NOT NULL DEFAULT '{}' — an explicit null means "clear",
        # which is the empty map (recurrence, by contrast, genuinely nulls out).
        if patch["attributes"] is None:
            patch["attributes"] = {}
    scope = dept_scope(user)
    fields, args = [], []
    for col, val in patch.items():
        if val is None and col not in _NULLABLE_PATCH_COLS:
            continue
        args.append(val); fields.append(f"{col}=${len(args)}")
    # Completing a task stamps completed_date unless the caller set one;
    # reopening it (status moves away from completed) clears the stale stamp
    # unless the caller is explicitly setting completed_date themselves.
    if patch.get("status") == "completed" and "completed_date" not in patch:
        args.append(date.today()); fields.append(f"completed_date=${len(args)}")
    elif patch.get("status") not in (None, "completed") and "completed_date" not in patch:
        args.append(None); fields.append(f"completed_date=${len(args)}")
    # Completing forward-fills the completion bar unless the caller set one.
    # Deliberately one-directional: progress=100 never forces status (the
    # research rule — never hard-enforce completion), and reopening keeps the
    # percentage (work done stays done; the user adjusts it if it regressed).
    if patch.get("status") == "completed" and "progress" not in patch:
        args.append(100); fields.append(f"progress=${len(args)}")
    noop = not fields  # nothing to apply once null-drops are accounted for
    if not noop:
        args.append(user["id"]); fields.append(f"updated_by=${len(args)}")
        args.append(task_id)
    async with rls(user) as c:
        # A dept-scoped manager may only mutate a task already in their scope
        # (own dept, personally owned, assigned, or a linked family member) —
        # this runs for EVERY patch (including a no-op) so an out-of-scope or
        # nonexistent task returns 404, never a misleading noop-success; scope
        # must be enforced on writes exactly as it already is on reads.
        await _assert_scope_visible(c, task_id, user)
        if noop:
            return {"ok": True, "noop": True}
        # A dept-scoped manager can't move a task into another department (or
        # unassign it into the no-department pool their scoped list can't
        # see) — EXCEPT re-targeting a subtask whose parent is in their own
        # department (or personally theirs): that's the delegation move that
        # makes a task multi-departmental.
        if scope and "department_id" in patch:
            cur_t = await c.fetchrow(
                "SELECT department_id, user_id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
            cur_dept = str(cur_t["department_id"]) if cur_t and cur_t["department_id"] else None
            if cur_t is not None and str(patch["department_id"] or "") != (cur_dept or ""):
                fam = await c.fetchrow(
                    "SELECT p.department_id AS pd, p.user_id AS pu FROM tasks t"
                    " JOIN tasks p ON p.id=t.parent_id"
                    " WHERE t.id=$1 AND t.is_deleted=false", task_id)
                delegable = fam is not None and (
                    (fam["pd"] and str(fam["pd"]) == scope) or str(fam["pu"]) == str(user["id"]))
                owns = str(cur_t["user_id"]) == str(user["id"])
                # Both directions are guarded: OUT of their department (the
                # original rule) and IN to it — without src_ok a scoped
                # manager could hijack any task they can merely see (e.g. as
                # assignee) onto their own board by setting department_id to
                # their scope, which the old !=scope condition never checked.
                src_ok = cur_dept == scope or owns or delegable
                dst_ok = str(patch["department_id"] or "") == scope or delegable
                if not (src_ok and dst_ok):
                    raise HTTPException(403, "Managers may not move tasks outside their own department")
        # Capture the pre-update status so a repeated/retried PATCH that sets
        # status='completed' on an ALREADY-completed recurring task doesn't
        # re-materialize a duplicate next instance (recurrence isn't cleared
        # on completion, so this check is the only idempotency guard).
        # FOR UPDATE: two concurrent completion PATCHes otherwise both read the
        # pre-completion status and each materializes a "next" recurring
        # instance (the read is the only idempotency guard, so it must hold
        # the row lock until this transaction commits).
        prev_status = await c.fetchval(
            "SELECT status FROM tasks WHERE id=$1 AND is_deleted=false FOR UPDATE", task_id)
        try:
            row = await c.fetchrow(
                f"UPDATE tasks SET {', '.join(fields)}, updated_at=now() WHERE id=${len(args)}"
                f" AND is_deleted=false RETURNING *", *args)
        except _FK_ERRORS:
            raise HTTPException(422, "Unknown department, week, or parent task")
        if row is None:
            raise HTTPException(404, "Task not found or not permitted")
        out = dict(row)
        # A recurring task that just completed (and wasn't already completed)
        # spawns its next instance.
        if patch.get("status") == "completed" and prev_status != "completed" and row["recurrence"]:
            nxt = await _materialize_recurrence(c, row)
            if nxt:
                out["next_instance"] = nxt
        # Status-change awareness: participants (creator/owner/assignees/
        # commenters) get notified; the actor never is (emit guards that).
        if "status" in patch and prev_status != row["status"]:
            try:
                who = await participants(c, task_id)
                # Canned automation recipients go FIRST: emit()'s recipient
                # dedup keeps the first (user_id, reason) pair it sees, so a
                # quality manager who is also a participant still gets the
                # more specific "capa_stuck"/"validation_stuck" reason
                # instead of the generic "status" one.
                canned = await canned_recipients(user, row["task_type"], row["status"])
                recipients = canned + [(u, "status") for u in who]
                await emit(c, user, verb="status_changed", object_type="task", object_id=task_id,
                           recipients=recipients, task_id=task_id,
                           department_id=row["department_id"],
                           params={"title": row["title"], "old": prev_status, "new": row["status"]})
            except Exception:
                pass
    return out


class ProgressIn(BaseModel):
    day_label: str = PydField(max_length=40)
    note: str = PydField(max_length=10_000)


@router.post("/tasks/{task_id}/progress", status_code=201)
async def add_progress(task_id: str, body: ProgressIn, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        task = await c.fetchrow("SELECT id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if task is None:
            raise HTTPException(404, "Task not found or not permitted")
        await _assert_scope_visible(c, task_id, user)
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
    note: str | None = Field(default=None, max_length=10_000)
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
        await _assert_scope_visible(c, task_id, user)
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
        # A dept-scoped manager must not read a foreign task's sessions by id —
        # RLS grants elevated roles org-wide SELECT, so scope is app-enforced
        # here exactly as on the write sibling add_session.
        await _assert_scope_visible(c, task_id, user)
        rows = await c.fetch("SELECT * FROM work_sessions WHERE task_id=$1 ORDER BY started_at", task_id)
    return [_session_out(r) for r in rows]


_ELEVATED = ELEVATED_ROLES


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(require_password_set)):
    """Only the person who logged a session (or an elevated role) may remove
    it — sessions are the overtime evidence, so deletion stays narrow (and is
    audit-trailed by the row trigger either way)."""
    async with rls(user) as c:
        row = await c.fetchrow("SELECT user_id, task_id FROM work_sessions WHERE id=$1", session_id)
        if row is None:
            raise HTTPException(404, "Session not found")
        # 'elevated' includes every dept-scoped manager role, so the role check
        # below alone would let a manager delete session evidence org-wide (this
        # endpoint takes only a session_id — no task in the path). Resolve the
        # session's task and enforce department scope on it first, so a manager
        # can only delete sessions on tasks they can actually see.
        await _assert_scope_visible(c, str(row["task_id"]), user)
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
        await _assert_scope_visible(c, task_id, user)
        row = await c.fetchrow(
            "INSERT INTO task_links(org_id,task_id,url,label,kind,created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6) RETURNING *",
            user["org_id"], task_id, url, body.label, body.kind, user["id"])
    return dict(row)


@router.delete("/tasks/{task_id}/links/{link_id}")
async def delete_link(task_id: str, link_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        # Look the task up under RLS first — task_links' only policy is
        # org_isolation, so without this any org member who knows a link id
        # could delete links on a task they can't see (same guard add_link,
        # add_session and add_progress all use).
        task = await c.fetchrow("SELECT id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if task is None:
            raise HTTPException(404, "Task not found or not permitted")
        await _assert_scope_visible(c, task_id, user)
        res = await c.execute("DELETE FROM task_links WHERE id=$1 AND task_id=$2", link_id, task_id)
    if res.split()[-1] == "0":
        raise HTTPException(404, "Link not found")
    return {"ok": True}


# ── Task dependencies (the blocker graph) ───────────────────────────────────
class DependencyIn(BaseModel):
    depends_on_task_id: str


@router.post("/tasks/{task_id}/dependencies", status_code=201)
async def add_dependency(task_id: str, body: DependencyIn, user: dict = Depends(require_password_set)):
    """Record 'task_id is blocked by depends_on_task_id'. Both tasks must be
    visible to the caller. Rejects a self-edge (also a DB CHECK) and any edge
    that would introduce a CYCLE — if the prospective blocker is already
    (transitively) blocked by this task, adding the edge would deadlock the
    graph, so it's a 422."""
    dep = body.depends_on_task_id
    if dep == task_id:
        raise HTTPException(422, "A task cannot depend on itself")
    async with rls(user) as c:
        for tid in (task_id, dep):
            t = await c.fetchrow("SELECT id FROM tasks WHERE id=$1 AND is_deleted=false", tid)
            if t is None:
                raise HTTPException(404, "Task not found or not permitted")
            await _assert_scope_visible(c, tid, user)
        # Cycle guard: can `dep` already reach `task_id` through the graph? If
        # so, task_id -> dep would close a loop. Walk the edges from dep.
        reaches = await c.fetchval(
            "WITH RECURSIVE reach(id) AS ("
            "  SELECT depends_on_task_id FROM task_dependencies WHERE task_id=$1"
            "  UNION"
            "  SELECT d.depends_on_task_id FROM task_dependencies d JOIN reach r ON d.task_id=r.id"
            ") SELECT EXISTS (SELECT 1 FROM reach WHERE id=$2)", dep, task_id)
        if reaches:
            raise HTTPException(422, "That dependency would create a cycle")
        try:
            await c.execute(
                "INSERT INTO task_dependencies(org_id,task_id,depends_on_task_id,created_by)"
                " VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                user["org_id"], task_id, dep, user["id"])
        except _FK_ERRORS:
            raise HTTPException(422, "Unknown task")
    return {"ok": True, "task_id": task_id, "depends_on_task_id": dep}


@router.delete("/tasks/{task_id}/dependencies/{dep_id}")
async def delete_dependency(task_id: str, dep_id: str, user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        t = await c.fetchrow("SELECT id FROM tasks WHERE id=$1 AND is_deleted=false", task_id)
        if t is None:
            raise HTTPException(404, "Task not found or not permitted")
        await _assert_scope_visible(c, task_id, user)
        res = await c.execute(
            "DELETE FROM task_dependencies WHERE task_id=$1 AND depends_on_task_id=$2", task_id, dep_id)
    if res.split()[-1] == "0":
        raise HTTPException(404, "Dependency not found")
    return {"ok": True}
