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

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.weekwindow import TASK_COLS as _COLS
from app.api.weekwindow import activity_window_sql, fri_thu as _fri_thu, task_row as _task_row
from app.db import rls
from app.deps import dept_scope, require_password_set
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

# "normal" is the wire value the GrowFlow UI sends for medium (see tasks.py's
# Priority literal + integrate.js P_OUT) — it must rank alongside "medium",
# not fall through to the ELSE tier below every real priority, or every
# default-priority task created in the UI sorts last in the weekly report.
_PRIORITY_RANK = ("CASE t.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
                  "WHEN 'medium' THEN 2 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 4 END")


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

    # A dept-scoped manager's report/plan covers ONLY their department — the
    # existing department_id filter is forced to theirs regardless of what the
    # caller passed. Executives / QP / ADMIN keep free choice (org-wide or any
    # single department).
    scope = dept_scope(user)
    if scope:
        department_id = scope

    hours_by_person: dict[str, dict] = {}
    overdue: list[dict] = []

    async with rls(user) as c:
        # Resolve the department breakdown by the canonical department_id → name,
        # not the denormalized free-text `department` column (which historically
        # stored codes and could split one department across code/name variants).
        dept_names = {str(r["id"]): r["name"] for r in await c.fetch("SELECT id, name FROM departments")}
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
                f"AND {activity_window_sql('$1', '$2', '$3')} "
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
            # $3 = TZ.key: same facility-local-time conversion the main tasks
            # query above applies — without it these two feeds compare in the
            # session's (UTC) TimeZone GUC and miscount events within ~1-3h of
            # local midnight into the wrong day/week, so the report's task list
            # and its own hours/time-band would disagree near week boundaries.
            band_args: list = [fri, thu, TZ.key]
            who = ""
            if not elevated:
                band_args.append(user["id"]); who = f" AND user_id = ${len(band_args)}"
            dept_sub = ""
            if department_id:
                band_args.append(department_id)
                dept_sub = f" AND task_id IN (SELECT id FROM tasks WHERE department_id=${len(band_args)})"

            events = await c.fetch(
                "SELECT created_at AS at FROM task_progress "
                f"WHERE (created_at AT TIME ZONE $3) >= $1::date AND (created_at AT TIME ZONE $3) < ($2::date + 1){who}{dept_sub} "
                "UNION ALL "
                "SELECT started_at AS at FROM work_sessions "
                f"WHERE (started_at AT TIME ZONE $3) >= $1::date AND (started_at AT TIME ZONE $3) < ($2::date + 1){who}{dept_sub} "
                "ORDER BY at",
                *band_args,
            )

            # Per-person regular/overtime/night/weekend from work sessions.
            sess = await c.fetch(
                "SELECT user_id, started_at, ended_at, hours FROM work_sessions "
                f"WHERE (started_at AT TIME ZONE $3) >= $1::date AND (started_at AT TIME ZONE $3) < ($2::date + 1){who}{dept_sub}",
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
        dn = dept_names.get(str(t.get("department_id"))) or t["department"] or "Unassigned"
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


@router.get("/analytics")
async def analytics(
    weeks: int = Query(8, ge=4, le=16),
    user: dict = Depends(require_password_set),
):
    """Cross-week trends for managers and executives — task throughput,
    on-time delivery, activity, and a current department snapshot.

    Deliberately hour-free (owner: hour sums are not a meaningful metric
    here): weekly buckets count tasks and logged sessions, never durations.
    Buckets are the same Fri→Thu windows as the weekly report, oldest first,
    ending with the current window. Dept-scoped managers are pinned to their
    department exactly like /reports/weekly.
    """
    if user["role"] == "USER":
        raise HTTPException(status_code=403, detail="Managers and executives only")
    tz = str(TZ)
    today = date.today()
    fri0, _ = _fri_thu(today)
    start = fri0 - timedelta(days=7 * (weeks - 1))
    scope = dept_scope(user)
    dept_sql = " AND t.department_id = $4::uuid" if scope else ""

    async with rls(user) as c:
        created = await c.fetch(
            "SELECT ((t.created_at AT TIME ZONE $2)::date - $1::date) / 7 AS wk, count(*) AS n"
            " FROM tasks t WHERE t.is_deleted=false"
            " AND (t.created_at AT TIME ZONE $2)::date >= $1"
            " AND (t.created_at AT TIME ZONE $2)::date < $1::date + $3::int" + dept_sql +
            " GROUP BY 1",
            start, tz, weeks * 7, *([scope] if scope else []))
        completed = await c.fetch(
            "SELECT (t.completed_date - $1::date) / 7 AS wk, count(*) AS n,"
            " count(*) FILTER (WHERE t.due_date IS NULL OR t.completed_date <= t.due_date) AS on_time"
            " FROM tasks t WHERE t.is_deleted=false"
            " AND t.completed_date >= $1 AND t.completed_date < $1::date + $2::int"
            + (" AND t.department_id = $3::uuid" if scope else "") +
            " GROUP BY 1",
            start, weeks * 7, *([scope] if scope else []))
        # Join through tasks so task-visibility RLS bounds what sessions are
        # counted (work_sessions RLS alone is org-wide — see /weekly's note).
        sessions = await c.fetch(
            "SELECT ((ws.started_at AT TIME ZONE $2)::date - $1::date) / 7 AS wk,"
            " count(*) AS n, count(DISTINCT ws.user_id) AS people"
            " FROM work_sessions ws JOIN tasks t ON t.id = ws.task_id"
            " WHERE t.is_deleted=false"
            " AND (ws.started_at AT TIME ZONE $2)::date >= $1"
            " AND (ws.started_at AT TIME ZONE $2)::date < $1::date + $3::int" + dept_sql +
            " GROUP BY 1",
            start, tz, weeks * 7, *([scope] if scope else []))
        dept_rows = await c.fetch(
            "SELECT t.department_id,"
            " count(*) FILTER (WHERE t.status <> 'completed') AS open,"
            " count(*) FILTER (WHERE t.status = 'stuck') AS stuck,"
            " count(*) FILTER (WHERE t.status <> 'completed' AND t.due_date < $1) AS overdue,"
            " count(*) FILTER (WHERE t.status = 'completed' AND t.completed_date >= $2) AS completed"
            " FROM tasks t WHERE t.is_deleted=false AND t.is_archived=false"
            + (" AND t.department_id = $3::uuid" if scope else "") +
            " GROUP BY 1",
            today, start, *([scope] if scope else []))
        types = await c.fetch(
            "SELECT t.task_type, count(*) AS n FROM tasks t"
            " WHERE t.is_deleted=false AND t.is_archived=false AND t.status <> 'completed'"
            + (" AND t.department_id = $1::uuid" if scope else "") +
            " GROUP BY 1 ORDER BY 2 DESC",
            *([scope] if scope else []))
        dept_names = {str(r["id"]): {"code": r["code"], "name": r["name"], "name_mk": r["name_mk"]}
                      for r in await c.fetch("SELECT id, code, name, name_mk FROM departments")}

    c_by = {r["wk"]: r["n"] for r in created}
    d_by = {r["wk"]: (r["n"], r["on_time"]) for r in completed}
    s_by = {r["wk"]: (r["n"], r["people"]) for r in sessions}
    week_series = []
    for i in range(weeks):
        done, on_time = d_by.get(i, (0, 0))
        sess, people = s_by.get(i, (0, 0))
        week_series.append({
            "week_start": (start + timedelta(days=7 * i)).isoformat(),
            "created": c_by.get(i, 0), "completed": done, "on_time": on_time,
            "sessions": sess, "active_people": people,
        })

    departments = []
    for r in dept_rows:
        did = str(r["department_id"]) if r["department_id"] else None
        meta = dept_names.get(did, {})
        departments.append({
            "id": did, "code": meta.get("code"),
            "name": meta.get("name") or "—", "name_mk": meta.get("name_mk"),
            "open": r["open"], "stuck": r["stuck"], "overdue": r["overdue"],
            "completed": r["completed"],
        })
    departments.sort(key=lambda d: -d["open"])

    return {
        "range": {"start": start.isoformat(), "end": (fri0 + timedelta(days=6)).isoformat(),
                  "weeks": weeks},
        "weeks": week_series,
        "departments": departments,
        "task_types": [{"task_type": r["task_type"], "count": r["n"]} for r in types],
    }
