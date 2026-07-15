"""Due-soon / overdue notification scan — the research matrix's v1.x row.

Runs once per local day (scheduler tick): tasks due TODAY notify their
owner + assignees (`due_soon`); tasks past their due date additionally
notify the department's manager(s) (`overdue`). Both feed the activity
stream. Idempotent within a day: a task that already produced its event
today is skipped, so scheduler restarts don't re-ping; across days the
inbox coalesce index keeps an unread row from duplicating, while a READ
row re-notifies the next day — a daily reminder, not a storm.

The actor is the org's system ADMIN profile (events.actor_id is NOT NULL;
"the system noticed" is an admin-attributed observation, and emit()'s
self-notify guard is a no-op for it).
"""
from datetime import date

from app.db import rls, rls_users, users_admin_pool
from app.notify import emit


async def _admin_users() -> list[dict]:
    """One system-ADMIN identity per organization (seeded at bootstrap)."""
    rows = await users_admin_pool().fetch(
        "SELECT DISTINCT ON (org_id) id, org_id, role FROM profiles"
        " WHERE role='ADMIN' AND is_deleted=false ORDER BY org_id, created_at")
    return [{"id": r["id"], "org_id": r["org_id"], "role": r["role"]} for r in rows]


async def _dept_managers(admin: dict, department_id) -> list[str]:
    if not department_id:
        return []
    async with rls_users(admin) as uc:
        rows = await uc.fetch(
            "SELECT id FROM profiles WHERE org_id=$1 AND department_id=$2"
            " AND is_deleted=false AND is_active AND role LIKE '%\\_MGR' ESCAPE '\\'",
            admin["org_id"], department_id)
    return [str(r["id"]) for r in rows]


async def run_for_org(admin: dict, today: date) -> dict:
    counts = {"due_soon": 0, "overdue": 0}
    async with rls(admin) as c:
        already = {(r["verb"], r["object_id"]) for r in await c.fetch(
            "SELECT verb, object_id FROM events"
            " WHERE verb IN ('due_soon','overdue') AND created_at::date=$1", today)}
        rows = await c.fetch(
            "SELECT t.id, t.title, t.user_id, t.department_id, t.due_date,"
            " COALESCE(array_agg(ta.user_id) FILTER (WHERE ta.user_id IS NOT NULL), '{}') AS assignees"
            " FROM tasks t LEFT JOIN task_assignees ta ON ta.task_id=t.id"
            " WHERE t.is_deleted=false AND t.is_archived=false"
            " AND t.status <> 'completed' AND t.due_date IS NOT NULL AND t.due_date <= $1"
            " GROUP BY t.id", today)
        for t in rows:
            verb = "due_soon" if t["due_date"] == today else "overdue"
            if (verb, str(t["id"])) in already:
                continue
            recipients = [(str(u), "due") for u in [t["user_id"], *t["assignees"]] if u]
            if verb == "overdue":
                recipients += [(m, "due") for m in await _dept_managers(admin, t["department_id"])]
            await emit(c, admin, verb=verb, object_type="task", object_id=t["id"],
                       recipients=recipients, task_id=t["id"],
                       department_id=t["department_id"],
                       params={"title": t["title"], "due": t["due_date"].isoformat()})
            counts[verb] += 1
    return counts


async def run_all(today: date) -> dict:
    total = {"due_soon": 0, "overdue": 0}
    for admin in await _admin_users():
        c = await run_for_org(admin, today)
        total["due_soon"] += c["due_soon"]
        total["overdue"] += c["overdue"]
    return total
