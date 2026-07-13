"""
LITA (Letta) AI layer — always-on.

Functions are data-driven: each maps to a Letta stateful agent via the
ai_agent_bindings table, so new capabilities are added as rows, not code. Every
call degrades gracefully — if no binding exists or the Letta stack is
unreachable, the endpoint returns {available:false} instead of erroring, so the
UI can fall back.
"""
import json
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.db import rls
from app.deps import require_password_set, require_role
from app.roles import ADMIN
from app.roster import roster

router = APIRouter(prefix="/ai", tags=["ai"])

_FENCE_RE = re.compile(r"```[a-zA-Z]*\s*\n(.*?)\n?\s*```", re.S)
_ENVELOPE_RE = re.compile(r'^\{\s*"[\w.-]+"\s*:\s*"(.*?)"?\s*\}?\s*$', re.S)


def normalize_ai_reply(reply: str) -> str:
    """Peel machine packaging off an agent reply so callers always get human
    prose. Several Letta agents answer in their persona's strict-JSON contract
    ({"weekly_report": "…"}) no matter what the per-message prompt asks —
    sometimes inside a ```json fence (possibly with surrounding prose the
    fence pattern doesn't fully swallow), sometimes truncated mid-envelope —
    all of which would otherwise reach the UI/export as literal JSON. Plain
    prose passes through untouched. Shared by every reader of a Letta reply
    (this module's generic /ai/{function_key} invoke, and documents.py's
    document-compile narratives) so the unwrap logic can't drift between them."""
    text = reply.strip()
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    if text[:1] not in '{["':
        return text
    try:
        data = json.loads(text)
    except ValueError:
        # Truncated envelope (agent hit its token limit mid-string): repair by
        # closing the string/object, else extract the first value by regex and
        # decode the JSON escapes it carries.
        data = None
        for suffix in ('"}', '"]}', "}"):
            try:
                data = json.loads(text + suffix)
                break
            except ValueError:
                continue
        if data is None:
            m = _ENVELOPE_RE.match(text)
            if m:
                raw = m.group(1)
                try:
                    data = json.loads(f'"{raw}"')
                except ValueError:
                    data = raw.replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t")
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, dict):
        # One value per language key is common; join multiple string values
        # with the bilingual separator so a positional EN/MK split keeps
        # working. Preserve insertion order — callers that care about EN-vs-MK
        # ordering rely on the agent emitting EN first, per the prompt contract.
        parts = [v.strip() for v in data.values() if isinstance(v, str) and v.strip()]
        if parts:
            return "\n\n---\n\n".join(parts) if len(parts) > 1 else parts[0]
    if isinstance(data, list):
        parts = [v.strip() for v in data if isinstance(v, str) and v.strip()]
        if parts:
            return "\n\n---\n\n".join(parts)
    return text

# Catalog of user-facing AI functions (bindings activate them per-org).
CATALOG = {
    "weekly_summary":    "Summarize the week, flag blocked/overdue/at-risk tasks.",
    "voice_capture":     "Turn natural-language/voice into structured tasks + subtasks.",
    "task_extract":      "Extract many tasks + subtasks from a pasted document (email, plan).",
    "translate_bilingual":"Translate a task title/description into bilingual Macedonian | English.",
    "dependency_advisor":"Suggest task dependencies and cross-department handoffs.",
    "corpus_qa":         "Answer questions over the task corpus (RAG).",
    "draft_description": "Expand a task title into a full description + subtasks.",
    "progress_digest":   "Daily standup digest from progress notes.",
    "risk_flag":         "Flag at-risk tasks needing attention.",
    "template_narrative":"Prefill per-department document template narratives (bilingual EN/MK).",
}


class InvokeReq(BaseModel):
    input: str
    context: dict | None = None


async def _letta_message(agent_id: str, text: str, timeout: float = 30) -> str | None:
    # timeout defaults to 30s for the quick interactive calls; heavier jobs
    # (e.g. multi-task document extraction) pass a longer one so the reasoning
    # agent isn't cut off mid-answer.
    headers = {}
    if settings.letta_api_key:
        headers["Authorization"] = f"Bearer {settings.letta_api_key}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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


# ── Admin: which Letta agent backs each AI function ─────────────────────────
async def _letta_agents() -> list[dict]:
    headers = {}
    if settings.letta_api_key:
        headers["Authorization"] = f"Bearer {settings.letta_api_key}"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{settings.letta_base_url}/v1/agents/", headers=headers)
        r.raise_for_status()
        data = r.json()
    ags = data if isinstance(data, list) else data.get("agents", [])
    return [{"id": a.get("id"), "name": a.get("name")} for a in ags if a.get("id")]


@router.get("/agents")
async def list_agents(actor: dict = Depends(require_role(ADMIN))):
    """The Letta agents available to bind functions to (drives the Settings AI tab)."""
    try:
        return {"agents": await _letta_agents()}
    except Exception as e:
        raise HTTPException(502, f"Letta unreachable: {type(e).__name__}")


class BindingReq(BaseModel):
    letta_agent_id: str
    is_active: bool = True


@router.get("/bindings")
async def list_bindings(actor: dict = Depends(require_role(ADMIN))):
    async with rls(actor) as c:
        rows = await c.fetch(
            "SELECT function_key, letta_agent_id, scope, is_active FROM ai_agent_bindings"
            " WHERE org_id=$1 AND scope='org' ORDER BY function_key", actor["org_id"])
    return [{"function_key": r["function_key"], "letta_agent_id": r["letta_agent_id"],
             "is_active": r["is_active"]} for r in rows]


@router.put("/bindings/{function_key}")
async def set_binding(function_key: str, body: BindingReq, actor: dict = Depends(require_role(ADMIN))):
    """Point an AI function at a Letta agent (org-scoped upsert). Atomic via
    the partial unique index on (org_id, function_key) WHERE scope='org'
    (migration 0006) — a plain UNIQUE(...,scope_id) doesn't dedupe org-scoped
    rows since scope_id is NULL there and Postgres treats NULLs as distinct."""
    if function_key not in CATALOG:
        raise HTTPException(422, f"Unknown function '{function_key}'")
    agent = (body.letta_agent_id or "").strip()
    if not agent:
        raise HTTPException(422, "letta_agent_id is required")
    async with rls(actor) as c:
        await c.execute(
            "INSERT INTO ai_agent_bindings(org_id, function_key, letta_agent_id, scope, is_active)"
            " VALUES ($1,$2,$3,'org',$4)"
            " ON CONFLICT (org_id, function_key) WHERE scope='org'"
            " DO UPDATE SET letta_agent_id=EXCLUDED.letta_agent_id, is_active=EXCLUDED.is_active",
            actor["org_id"], function_key, agent, body.is_active)
    return {"ok": True, "function_key": function_key, "letta_agent_id": agent, "is_active": body.is_active}


@router.delete("/bindings/{function_key}")
async def delete_binding(function_key: str, actor: dict = Depends(require_role(ADMIN))):
    async with rls(actor) as c:
        await c.execute(
            "DELETE FROM ai_agent_bindings WHERE org_id=$1 AND function_key=$2 AND scope='org'",
            actor["org_id"], function_key)
    return {"ok": True}


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
             " t.estimated_hours, t.actual_hours, t.completed_date, t.user_id")


async def _task_context(conn, names: dict, week_id: str | None = None, limit: int = 200) -> str:
    """*names* is the app-side roster map (owner usernames live in the users
    database — no SQL join possible)."""
    if week_id:
        rows = await conn.fetch(
            f"SELECT {_CTX_COLS} FROM tasks t"
            " WHERE t.is_deleted=false AND t.week_id=$1 ORDER BY t.created_at DESC LIMIT $2", week_id, limit)
    else:
        rows = await conn.fetch(
            f"SELECT {_CTX_COLS} FROM tasks t"
            " WHERE t.is_deleted=false ORDER BY t.week_start DESC NULLS LAST, t.created_at DESC LIMIT $1", limit)
    if not rows:
        return ""

    def _hrs(v):
        return "-" if v is None else f"{float(v):g}"

    lines = []
    for r in rows:
        done = f", done={r['completed_date']}" if r["completed_date"] else ""
        owner = (names.get(str(r["user_id"])) or {}).get("username")
        lines.append(
            f"- [task:{str(r['id'])[:8]}] [{r['status']}/{r['priority']}] {r['title']} "
            f"(dept={r['department']}, owner={owner}, week={r['week_start']}, "
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
        if function_key in _DATA_FUNCS:
            context = await _task_context(c, await roster(user), week_id=week_id)
        else:
            context = ""
    if binding is None:
        return {"available": False, "reason": "not_configured", "function": function_key}
    prompt = f"{context}\n\nREQUEST: {body.input}" if context else body.input
    reply = await _letta_message(binding["letta_agent_id"], prompt)
    if reply is None:
        return {"available": False, "reason": "letta_unreachable", "function": function_key}
    return {"available": True, "function": function_key, "output": normalize_ai_reply(reply)}
