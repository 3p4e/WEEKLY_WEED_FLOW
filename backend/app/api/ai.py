"""
LITA (Letta) AI layer — always-on.

Functions are data-driven: each maps to a Letta stateful agent via the
ai_agent_bindings table, so new capabilities are added as rows, not code. Every
call degrades gracefully — if no binding exists or the Letta stack is
unreachable, the endpoint returns {available:false} instead of erroring, so the
UI can fall back.
"""
import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.config import settings
from app.db import rls
from app.deps import require_password_set

router = APIRouter(prefix="/ai", tags=["ai"])

# Catalog of user-facing AI functions (bindings activate them per-org).
CATALOG = {
    "weekly_summary":    "Summarize the week, flag blocked/overdue/at-risk tasks.",
    "voice_capture":     "Turn natural-language/voice into structured tasks + subtasks.",
    "dependency_advisor":"Suggest task dependencies and cross-department handoffs.",
    "corpus_qa":         "Answer questions over the task corpus (RAG).",
    "draft_description": "Expand a task title into a full description + subtasks.",
    "progress_digest":   "Daily standup digest from progress notes.",
    "risk_flag":         "Flag at-risk tasks needing attention.",
}


class InvokeReq(BaseModel):
    input: str
    context: dict | None = None


async def _letta_message(agent_id: str, text: str) -> str | None:
    headers = {}
    if settings.letta_api_key:
        headers["Authorization"] = f"Bearer {settings.letta_api_key}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{settings.letta_base_url}/v1/agents/{agent_id}/messages",
                headers=headers,
                json={"messages": [{"role": "user", "content": text}]},
            )
            r.raise_for_status()
            data = r.json()
        # Letta returns a list of messages; pull the assistant text.
        msgs = data.get("messages", data if isinstance(data, list) else [])
        for m in reversed(msgs):
            if m.get("message_type") in ("assistant_message", "tool_call_message") and m.get("content"):
                return m["content"] if isinstance(m["content"], str) else str(m["content"])
        return None
    except Exception:
        return None


@router.get("/functions")
async def functions(user: dict = Depends(require_password_set)):
    async with rls(user) as c:
        bound = await c.fetch(
            "SELECT function_key, scope, is_active FROM ai_agent_bindings WHERE is_active=true")
    active = {b["function_key"] for b in bound}
    return {
        "catalog": CATALOG,
        "active": sorted(active),
        "letta_base_url": settings.letta_base_url,
    }


@router.get("/pins")
async def list_pins(
    function_key: str | None = None,
    week_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    user: dict = Depends(require_password_set),
):
    """Read the archived AI outputs (weekly report / next-week plan / snapshot
    digest) the scheduler writes to ai_pins. Newest first. Visibility is the
    RLS policy's: org-scoped, and per-user pins (subject_user_id set) only to
    their subject or elevated roles."""
    clauses, args = [], []
    if function_key:
        args.append(function_key); clauses.append(f"function_key=${len(args)}")
    if week_id:
        args.append(week_id); clauses.append(f"week_id=${len(args)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(limit)
    async with rls(user) as c:
        rows = await c.fetch(
            "SELECT id, function_key, task_id, week_id, title, body, created_at, subject_user_id, prompt_version"
            f" FROM ai_pins{where} ORDER BY created_at DESC LIMIT ${len(args)}", *args)
    return [
        {"id": str(r["id"]), "function_key": r["function_key"],
         "task_id": str(r["task_id"]) if r["task_id"] else None,
         "week_id": str(r["week_id"]) if r["week_id"] else None,
         "title": r["title"], "body": r["body"],
         "created_at": r["created_at"].isoformat(),
         "subject_user_id": str(r["subject_user_id"]) if r["subject_user_id"] else None,
         "prompt_version": r["prompt_version"]}
        for r in rows
    ]


# Functions that should be grounded in the live task corpus.
_DATA_FUNCS = {"weekly_summary", "dependency_advisor", "corpus_qa", "risk_flag", "progress_digest"}


_CTX_COLS = ("t.id, t.title, t.status, t.priority, t.department, t.week_start, t.tags,"
             " t.estimated_hours, t.actual_hours, t.completed_date, p.username AS owner")


async def _task_context(conn, week_id: str | None = None, limit: int = 200) -> str:
    if week_id:
        rows = await conn.fetch(
            f"SELECT {_CTX_COLS} FROM tasks t LEFT JOIN profiles p ON p.id=t.user_id"
            " WHERE t.is_deleted=false AND t.week_id=$1 ORDER BY t.created_at DESC LIMIT $2", week_id, limit)
    else:
        rows = await conn.fetch(
            f"SELECT {_CTX_COLS} FROM tasks t LEFT JOIN profiles p ON p.id=t.user_id"
            " WHERE t.is_deleted=false ORDER BY t.week_start DESC NULLS LAST, t.created_at DESC LIMIT $1", limit)
    if not rows:
        return ""

    def _hrs(v):
        return "-" if v is None else f"{float(v):g}"

    lines = []
    for r in rows:
        done = f", done={r['completed_date']}" if r["completed_date"] else ""
        lines.append(
            f"- [task:{str(r['id'])[:8]}] [{r['status']}/{r['priority']}] {r['title']} "
            f"(dept={r['department']}, owner={r['owner']}, week={r['week_start']}, "
            f"hours={_hrs(r['actual_hours'])}/{_hrs(r['estimated_hours'])}, "
            f"tags={list(r['tags'] or [])}{done})"
        )
    return f"TASK DATA ({len(rows)} tasks, most recent first):\n" + "\n".join(lines)


@router.post("/{function_key}")
async def invoke(function_key: str, body: InvokeReq, user: dict = Depends(require_password_set)):
    if function_key not in CATALOG:
        return {"available": False, "reason": "unknown_function"}
    week_id = (body.context or {}).get("week_id")
    async with rls(user) as c:
        binding = await c.fetchrow(
            "SELECT letta_agent_id FROM ai_agent_bindings"
            " WHERE function_key=$1 AND is_active=true ORDER BY scope LIMIT 1", function_key)
        context = await _task_context(c, week_id=week_id) if function_key in _DATA_FUNCS else ""
    if binding is None:
        return {"available": False, "reason": "not_configured", "function": function_key}
    prompt = f"{context}\n\nREQUEST: {body.input}" if context else body.input
    reply = await _letta_message(binding["letta_agent_id"], prompt)
    if reply is None:
        return {"available": False, "reason": "letta_unreachable", "function": function_key}
    return {"available": True, "function": function_key, "output": reply}
