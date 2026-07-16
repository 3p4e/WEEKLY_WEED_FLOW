"""AI layer — data-driven invocation of the stateful Letta agent roster (P2).

Each function maps to an agent via the ai_agent_bindings table, so capabilities
are added as ROWS, not code. Every call degrades gracefully: if no binding exists
or the Letta stack is unreachable, the endpoint returns {available:false} and the
UI falls back (3-tier resilience). Data functions are grounded in the live task
corpus (RAG-lite).
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth_deps import rls_session
from ..config import get_settings
from ..schemas import AiFunctionsOut, AiInvokeRequest, AiInvokeResult

router = APIRouter(prefix="/ai", tags=["ai"])

# User-facing catalog (a binding row activates each one).
CATALOG = {
    "weekly_summary":      "Summarize the week; flag blocked/overdue/at-risk tasks.",
    "next_week_plan":      "Propose next week's plan from the task corpus.",
    "weekly_report":       "Draft a weekly report.",
    "draft_description":   "Expand a task title into a description + subtasks.",
    "executive_analytics": "Cross-department executive analytics.",
    "schema_advisor":      "Propose governed schema/workflow changes (change-control).",
    "qms_architect":       "Architectural guidance and design-of-record memory.",
    "gmp_compliance":      "EU GMP (Annex 1-19) compliance guidance.",
    "gmp_audit":           "Validate documents/records against EU GMP annexes.",
}

# Functions grounded in the live task corpus.
_DATA_FUNCS = {"weekly_summary", "next_week_plan", "weekly_report", "executive_analytics"}


async def _letta_message(agent_id: str, text_in: str) -> str | None:
    s = get_settings()
    if not s.letta_base_url:
        return None
    headers = {"Authorization": f"Bearer {s.letta_api_key}"} if s.letta_api_key else {}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                f"{s.letta_base_url.rstrip('/')}/v1/agents/{agent_id}/messages",
                headers=headers,
                json={"messages": [{"role": "user", "content": text_in}]},
            )
            r.raise_for_status()
            data = r.json()
        msgs = data.get("messages", data if isinstance(data, list) else [])
        for m in reversed(msgs):
            if m.get("message_type") == "assistant_message" and m.get("content"):
                c_ = m["content"]
                return c_ if isinstance(c_, str) else str(c_)
        return None
    except Exception:
        return None


async def _corpus(session: AsyncSession, limit: int = 200) -> str:
    rows = (
        await session.execute(
            text("SELECT title, status, priority, node_kind, week_start, is_sop "
                 "FROM planner_task ORDER BY week_start DESC NULLS LAST, created_at DESC LIMIT :n"),
            {"n": limit},
        )
    ).mappings().all()
    if not rows:
        return ""
    lines = [
        f"- [{r['status']}/{r['priority']}] {r['title']} "
        f"(kind={r['node_kind']}, week={r['week_start']}, sop={r['is_sop']})"
        for r in rows
    ]
    return f"TASK CORPUS ({len(rows)} most-recent nodes):\n" + "\n".join(lines)


@router.get("/functions", response_model=AiFunctionsOut)
async def functions(session: AsyncSession = Depends(rls_session)) -> AiFunctionsOut:
    rows = (
        await session.execute(
            text("SELECT function_key FROM ai_agent_bindings WHERE is_active")
        )
    ).mappings().all()
    active = sorted({r["function_key"] for r in rows} & set(CATALOG))
    return AiFunctionsOut(catalog=CATALOG, active=active)


@router.post("/{function_key}", response_model=AiInvokeResult)
async def invoke(
    function_key: str, body: AiInvokeRequest, session: AsyncSession = Depends(rls_session)
) -> AiInvokeResult:
    if function_key not in CATALOG:
        return AiInvokeResult(available=False, reason="unknown_function")
    binding = (
        await session.execute(
            text("SELECT letta_agent_id FROM ai_agent_bindings "
                 "WHERE function_key = :k AND is_active ORDER BY scope LIMIT 1"),
            {"k": function_key},
        )
    ).mappings().first()
    if binding is None:
        return AiInvokeResult(available=False, function=function_key, reason="not_configured")
    context = await _corpus(session) if function_key in _DATA_FUNCS else ""
    prompt = f"{context}\n\nREQUEST: {body.input}" if context else body.input
    reply = await _letta_message(binding["letta_agent_id"], prompt)
    if reply is None:
        return AiInvokeResult(available=False, function=function_key, reason="letta_unreachable")
    return AiInvokeResult(available=True, function=function_key, output=reply)
