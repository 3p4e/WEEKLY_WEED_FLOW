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


async def ensure_week(conn, org_id, day: date):
    """id of the ISO (Mon->Sun) calendar week containing *day*, creating the
    row if the org hasn't seeded that far ahead. ON CONFLICT DO UPDATE is a
    no-op field-set purely so RETURNING id works on the existing row."""
    iso_year, iso_week, _ = day.isocalendar()
    monday = day - timedelta(days=day.weekday())
    return await conn.fetchval(
        "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on)"
        " VALUES ($1,$2,$3,$4,$5)"
        " ON CONFLICT (org_id, iso_year, iso_week) DO UPDATE SET iso_year=EXCLUDED.iso_year"
        " RETURNING id",
        org_id, iso_year, iso_week, monday, monday + timedelta(days=6))


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
    created, updated, completed, commented on, (un)assigned, acknowledged, or
    with a progress note / work session / rejected-or-cancelled handoff in the
    window. `start`/`end` are date params, `tz` a text TZ-name param. One
    definition so the report screen and the locked document agree on membership.

    An assignment, acknowledgment, comment, or work session already bumps
    t.updated_at in most code paths, but not every one of them does (e.g. a
    comment never touches the task row itself) — each gets its own EXISTS so a
    week where that was the ONLY activity still counts. An ACCEPTED handoff
    already shows up via the task's own department_id UPDATE (t.updated_at);
    only rejected/cancelled ones leave no other trace on the task, so those are
    the two statuses counted here.
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
        f"  OR EXISTS (SELECT 1 FROM task_comments tc WHERE tc.task_id=t.id "
        f"             AND (tc.created_at AT TIME ZONE {tz}) >= {start}::date AND (tc.created_at AT TIME ZONE {tz}) < ({end}::date + 1))"
        f"  OR EXISTS (SELECT 1 FROM task_assignees ta WHERE ta.task_id=t.id AND ("
        f"             ((ta.assigned_at AT TIME ZONE {tz}) >= {start}::date AND (ta.assigned_at AT TIME ZONE {tz}) < ({end}::date + 1))"
        f"             OR (ta.accepted_at IS NOT NULL AND (ta.accepted_at AT TIME ZONE {tz}) >= {start}::date"
        f"                 AND (ta.accepted_at AT TIME ZONE {tz}) < ({end}::date + 1))))"
        f"  OR EXISTS (SELECT 1 FROM handoffs h WHERE h.task_id=t.id AND h.status IN ('rejected','cancelled')"
        f"             AND h.resolved_at IS NOT NULL"
        f"             AND (h.resolved_at AT TIME ZONE {tz}) >= {start}::date AND (h.resolved_at AT TIME ZONE {tz}) < ({end}::date + 1))"
        f")"
    )
