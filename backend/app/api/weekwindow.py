"""Shared Fri→Thu week-window primitives.

Both the live weekly report (reports.py) and the compiled weekly document
(documents.py) select "tasks with activity in the Fri→Thu window" and shape
task rows the same way. These lived as underscore-private symbols in reports.py
that documents.py reached across for — promoted here with public names so the
two endpoints can never disagree about what a week's tasks, columns, or
activity predicate are.
"""
from datetime import date, timedelta
from decimal import Decimal

# Column list every task-row query selects (kept in sync with task_row below).
TASK_COLS = (
    "t.id, t.title, t.description, t.status, t.priority, t.task_type, "
    "t.reference_code, t.blocker_reason, t.department, t.department_id, "
    "t.week_start, t.due_date, t.completed_date, "
    "t.estimated_hours, t.actual_hours, t.days, t.tags, "
    "t.created_at, t.updated_at"
)


def fri_thu(ref: date) -> tuple[date, date]:
    """The Friday→Thursday window containing *ref*."""
    days_since_fri = (ref.weekday() - 4) % 7
    fri = ref - timedelta(days=days_since_fri)
    return fri, fri + timedelta(days=6)


def num(v) -> float:
    if v is None:
        return 0.0
    return float(v) if isinstance(v, Decimal) else float(v)


def task_row(r) -> dict:
    return {
        "id": str(r["id"]),
        "title": r["title"],
        "description": r["description"] or "",
        "status": r["status"],
        "priority": r["priority"],
        "task_type": r["task_type"],
        "reference_code": r["reference_code"],
        "blocker_reason": r["blocker_reason"],
        "department": r["department"],
        "department_id": str(r["department_id"]) if r["department_id"] else None,
        "due_date": r["due_date"].isoformat() if r["due_date"] else None,
        "completed_date": r["completed_date"].isoformat() if r["completed_date"] else None,
        "estimated_hours": num(r["estimated_hours"]),
        "actual_hours": num(r["actual_hours"]),
        "days": list(r["days"] or []),
        "tags": list(r["tags"] or []),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


def activity_window_sql(start: str = "$1", end: str = "$2", tz: str = "$3") -> str:
    """The 'task had activity in [start, end] facility-local' predicate — a task
    created, updated, completed, or with a progress note / work session in the
    window. `start`/`end` are date params, `tz` a text TZ-name param. One
    definition so the report screen and the locked document agree on membership.
    """
    return (
        f"("
        f"  ((t.created_at AT TIME ZONE {tz}) >= {start}::date AND (t.created_at AT TIME ZONE {tz}) < ({end}::date + 1))"
        f"  OR ((t.updated_at AT TIME ZONE {tz}) >= {start}::date AND (t.updated_at AT TIME ZONE {tz}) < ({end}::date + 1))"
        f"  OR (t.completed_date >= {start} AND t.completed_date <= {end})"
        f"  OR EXISTS (SELECT 1 FROM task_progress tp WHERE tp.task_id=t.id "
        f"             AND (tp.created_at AT TIME ZONE {tz}) >= {start}::date AND (tp.created_at AT TIME ZONE {tz}) < ({end}::date + 1))"
        f"  OR EXISTS (SELECT 1 FROM work_sessions ws WHERE ws.task_id=t.id "
        f"             AND (ws.started_at AT TIME ZONE {tz}) >= {start}::date AND (ws.started_at AT TIME ZONE {tz}) < ({end}::date + 1))"
        f")"
    )
