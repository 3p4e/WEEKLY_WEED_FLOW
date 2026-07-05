"""Weekly report + plan — Fri→Thu rolling window with activity time band.

Report mode: tasks that had activity (created, updated, completed, or received
progress notes / work sessions) during the Fri→Thu window. Includes:
  • a 7-day time band bucketed by hour from real task_progress AND
    work_session timestamps — no fabrication;
  • per-person hours split into regular / overtime / night / weekend from
    work_sessions (see app/worktime.py for the rules) — this is what makes
    the Thursday report actually evidence off-hours commitment;
  • overdue tasks (due_date passed, not completed);
  • a task_type breakdown.

Plan mode: active/incomplete tasks that carry forward into the next week.
"""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import rls
from app.deps import require_password_set
from app.roles import ELEVATED_ROLES
from app.roster import roster
from app.worktime import TZ, classify, session_hours

router = APIRouter(prefix="/reports", tags=["reports"])

# work_sessions/task_progress RLS is org-scoped only (no owner/assignee
# restriction like tasks_read), so a non-elevated caller must be filtered to
# their own rows here — otherwise the per-person hours and activity time
# band leak every colleague's sessions regardless of task visibility.
# app.roles.ELEVATED_ROLES is the single source of truth.
_ELEVATED = ELEVATED_ROLES

_PRIORITY_RANK = ("CASE t.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
                  "WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END")


def _fri_thu(ref: date) -> tuple[date, date]:
    """Return the Friday→Thursday window containing *ref*."""
    days_since_fri = (ref.weekday() - 4) % 7
    fri = ref - timedelta(days=days_since_fri)
    return fri, fri + timedelta(days=6)


def _num(v) -> float:
    if v is None:
        return 0.0
    return float(v) if isinstance(v, Decimal) else float(v)


def _task_row(r) -> dict:
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
        "estimated_hours": _num(r["estimated_hours"]),
        "actual_hours": _num(r["actual_hours"]),
        "days": list(r["days"] or []),
        "tags": list(r["tags"] or []),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


_COLS = (
    "t.id, t.title, t.description, t.status, t.priority, t.task_type, "
    "t.reference_code, t.blocker_reason, t.department, t.department_id, "
    "t.week_start, t.due_date, t.completed_date, "
    "t.estimated_hours, t.actual_hours, t.days, t.tags, "
    "t.created_at, t.updated_at"
)


@router.get("/weekly")
async def weekly_report(
    mode: str = Query("report", pattern="^(report|plan)$"),
    ref_date: str | None = None,
    department_id: str | None = None,
    user: dict = Depends(require_password_set),
):
    if ref_date:
        try:
            ref = date.fromisoformat(ref_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="ref_date must be ISO format YYYY-MM-DD")
    else:
        ref = date.today()
    fri, thu = _fri_thu(ref)

    if mode == "plan":
        fri = fri + timedelta(days=7)
        thu = thu + timedelta(days=7)

    hours_by_person: dict[str, dict] = {}
    overdue: list[dict] = []

    async with rls(user) as c:
        if mode == "report":
            # $3 = TZ.key (e.g. "Europe/Skopje"): every timestamptz column is
            # converted to facility-local wall-clock time BEFORE comparing
            # against the plain fri/thu dates below — otherwise Postgres
            # resolves the date casts in the session's (UTC) TimeZone GUC,
            # miscounting events within ~1-3 hours of local midnight into the
            # wrong day/week. completed_date is already a plain `date` column
            # (no timezone involved), so it's compared as-is.
            args: list = [fri, thu, TZ.key]
            dept_clause = ""
            if department_id:
                args.append(department_id)
                dept_clause = f" AND t.department_id=${len(args)}"
            rows = await c.fetch(
                f"SELECT {_COLS} FROM tasks t "
                f"WHERE t.is_deleted=false{dept_clause} "
                f"AND ("
                f"  ((t.created_at AT TIME ZONE $3) >= $1::date AND (t.created_at AT TIME ZONE $3) < ($2::date + 1))"
                f"  OR ((t.updated_at AT TIME ZONE $3) >= $1::date AND (t.updated_at AT TIME ZONE $3) < ($2::date + 1))"
                f"  OR (t.completed_date >= $1 AND t.completed_date <= $2)"
                f"  OR EXISTS (SELECT 1 FROM task_progress tp "
                f"             WHERE tp.task_id=t.id "
                f"             AND (tp.created_at AT TIME ZONE $3) >= $1::date AND (tp.created_at AT TIME ZONE $3) < ($2::date + 1))"
                f"  OR EXISTS (SELECT 1 FROM work_sessions ws "
                f"             WHERE ws.task_id=t.id "
                f"             AND (ws.started_at AT TIME ZONE $3) >= $1::date AND (ws.started_at AT TIME ZONE $3) < ($2::date + 1))"
                f") "
                f"ORDER BY CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END, "
                f"{_PRIORITY_RANK}, t.created_at",
                *args,
            )

            # Non-elevated callers only ever see their OWN sessions/notes here:
            # work_sessions/task_progress RLS is org-scoped only, not
            # owner/assignee-scoped like tasks_read, so without this filter a
            # regular user would get every colleague's hours and activity.
            elevated = user["role"] in _ELEVATED
            # Build the shared window/who/department scoping once so the events
            # feed and the per-person hours agree. department_id filters
            # task_progress/work_sessions by their task's department (neither
            # table carries department_id itself) — without it a dept-filtered
            # report mixed in every department's hours.
            band_args: list = [fri, thu]
            who = ""
            if not elevated:
                band_args.append(user["id"]); who = f" AND user_id = ${len(band_args)}"
            dept_sub = ""
            if department_id:
                band_args.append(department_id)
                dept_sub = f" AND task_id IN (SELECT id FROM tasks WHERE department_id=${len(band_args)})"

            events = await c.fetch(
                "SELECT created_at AS at FROM task_progress "
                f"WHERE created_at >= $1::date AND created_at < ($2::date + 1){who}{dept_sub} "
                "UNION ALL "
                "SELECT started_at AS at FROM work_sessions "
                f"WHERE started_at >= $1::date AND started_at < ($2::date + 1){who}{dept_sub} "
                "ORDER BY at",
                *band_args,
            )

            # Per-person regular/overtime/night/weekend from work sessions.
            sess = await c.fetch(
                "SELECT user_id, started_at, ended_at, hours FROM work_sessions "
                f"WHERE started_at >= $1::date AND started_at < ($2::date + 1){who}{dept_sub}",
                *band_args,
            )
            for s in sess:
                uid = str(s["user_id"])
                b = hours_by_person.setdefault(
                    uid, {"user_id": uid, "regular": 0.0, "overtime": 0.0,
                          "night": 0.0, "weekend": 0.0, "total": 0.0})
                h = session_hours(s)
                b[classify(s["started_at"])] += h
                b["total"] += h

            over_args: list = [thu + timedelta(days=1)]
            over_clause = ""
            if department_id:
                over_args.append(department_id)
                over_clause = " AND t.department_id=$2"
            over_rows = await c.fetch(
                f"SELECT {_COLS} FROM tasks t "
                f"WHERE t.is_deleted=false AND t.is_archived=false{over_clause} "
                f"AND t.due_date IS NOT NULL AND t.due_date < $1 "
                f"AND t.status <> 'completed' ORDER BY t.due_date",
                *over_args,
            )
            overdue = [_task_row(r) for r in over_rows]

            buckets: dict[str, list[int]] = {}
            for d in range(7):
                day = fri + timedelta(days=d)
                buckets[day.isoformat()] = [0] * 24
            for ev in events:
                ts = ev["at"]
                if ts is None:
                    continue
                local = ts.astimezone(TZ)
                dk = local.date().isoformat()
                if dk in buckets:
                    buckets[dk][local.hour] += 1

            time_band = []
            for d in range(7):
                day = fri + timedelta(days=d)
                time_band.append({
                    "date": day.isoformat(),
                    "dow": day.weekday(),
                    "day_name": day.strftime("%a"),
                    "hours": buckets[day.isoformat()],
                })
        else:
            args = []
            dept_clause = ""
            if department_id:
                args.append(department_id)
                dept_clause = f" AND t.department_id=${len(args)}"
            rows = await c.fetch(
                f"SELECT {_COLS} FROM tasks t "
                f"WHERE t.is_deleted=false AND t.is_archived=false{dept_clause} "
                f"AND t.status <> 'completed' "
                f"ORDER BY {_PRIORITY_RANK}, t.department, t.created_at",
                *args,
            )
            time_band = []

    # Attach names to per-person hours (usernames live in the users database).
    if hours_by_person:
        names = await roster(user)
        for uid, b in hours_by_person.items():
            p = names.get(uid) or {}
            b["username"] = p.get("username")
            b["full_name"] = p.get("full_name")
            for k in ("regular", "overtime", "night", "weekend", "total"):
                b[k] = round(b[k], 2)

    tasks_out = [_task_row(r) for r in rows]

    statuses: dict[str, int] = {}
    types: dict[str, int] = {}
    est_h, act_h = 0.0, 0.0
    for t in tasks_out:
        s = t["status"] or "pending"
        statuses[s] = statuses.get(s, 0) + 1
        tt = t["task_type"] or "other"
        types[tt] = types.get(tt, 0) + 1
        est_h += t["estimated_hours"]
        act_h += t["actual_hours"]

    dept_map: dict[str, dict] = {}
    for t in tasks_out:
        dn = t["department"] or "Unassigned"
        if dn not in dept_map:
            dept_map[dn] = {"name": dn, "total": 0, "completed": 0}
        dept_map[dn]["total"] += 1
        if t["status"] == "completed":
            dept_map[dn]["completed"] += 1

    iso_week = fri.isocalendar()[1]
    return {
        "period": {
            "start": fri.isoformat(),
            "end": thu.isoformat(),
            "label": (
                f"W{iso_week} {fri.year} "
                f"({fri.strftime('%a %b %d')} → {thu.strftime('%a %b %d')})"
            ),
        },
        "mode": mode,
        "summary": {
            "total": len(tasks_out),
            "completed": statuses.get("completed", 0),
            "in_progress": statuses.get("ongoing", 0),
            "stuck": statuses.get("stuck", 0),
            "pending": statuses.get("pending", 0),
            "review": statuses.get("review", 0),
            "postponed": statuses.get("postponed", 0),
            "estimated_hours": round(est_h, 1),
            "actual_hours": round(act_h, 1),
        },
        "task_types": types,
        "hours_by_person": sorted(hours_by_person.values(), key=lambda b: -b["total"]),
        "overdue": overdue,
        "departments": sorted(dept_map.values(), key=lambda x: x["total"], reverse=True),
        "tasks": tasks_out,
        "time_band": time_band,
    }
