"""AI Intake — paste a document (a CEO email, a plan, meeting notes), let a
Letta agent extract every actionable task + subtask from it, and return them as
CANDIDATES for the user to review, edit, and adopt.

Extraction only — nothing is persisted here. The user picks which candidates to
keep in the review UI, and the frontend adopts the selected ones through the
existing POST /capture/import path (owned by the caller, dept kept as-is). This
endpoint is available to any authenticated user, org-scoped by RLS.
"""
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.ai import _letta_message
from app.db import rls
from app.deps import require_password_set

router = APIRouter(prefix="/intake", tags=["intake"])

_PRIORITIES = {"low", "medium", "high", "critical"}
_TYPES = {"capa", "sop", "validation", "document", "lab", "meeting", "admin", "other"}
# Loose synonyms the model tends to emit → our canonical values.
_PRIORITY_SYN = {"urgent": "critical", "highest": "critical", "normal": "medium",
                 "med": "medium", "moderate": "medium", "minor": "low"}
_TYPE_SYN = {"corrective": "capa", "deviation": "capa", "procedure": "sop",
             "validation report": "validation", "laboratory": "lab", "testing": "lab",
             "documentation": "document", "administrative": "admin", "task": "other"}

_MAX_TEXT = 20000  # a very long email; keep the Letta prompt bounded


class ExtractReq(BaseModel):
    text: str


def _clamp(v, allowed, syn, default):
    s = str(v or "").strip().lower()
    if s in allowed:
        return s
    if s in syn:
        return syn[s]
    return default


def _norm_candidate(raw: dict, dept_by_key: dict) -> dict | None:
    """Validate/normalize one model-emitted task; None if it has no usable title."""
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    # Department: the model may give a code ("PP-QC") or a name ("Quality
    # Control") or an id — resolve to a known CODE, else leave unset.
    dept = raw.get("department") or raw.get("department_code") or raw.get("dept")
    dept_code = dept_by_key.get(str(dept or "").strip().lower())
    subs = []
    for st in (raw.get("subtasks") or []):
        if isinstance(st, str):
            st_title = st.strip()
            st_desc = None
        elif isinstance(st, dict):
            st_title = str(st.get("title") or "").strip()
            st_desc = (str(st.get("description")).strip() or None) if st.get("description") else None
        else:
            continue
        if st_title:
            subs.append({"title": st_title[:300], "description": st_desc})
    due = str(raw.get("due_date") or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", due):
        due = None
    try:
        est = float(raw.get("estimated_hours")) if raw.get("estimated_hours") not in (None, "") else None
        if est is not None and est < 0:
            est = None
    except (TypeError, ValueError):
        est = None
    return {
        "title": title[:500],
        "description": (str(raw.get("description")).strip() or None) if raw.get("description") else None,
        "priority": _clamp(raw.get("priority"), _PRIORITIES, _PRIORITY_SYN, "medium"),
        "task_type": _clamp(raw.get("task_type") or raw.get("type"), _TYPES, _TYPE_SYN, "other"),
        "reference_code": (str(raw.get("reference_code")).strip() or None) if raw.get("reference_code") else None,
        "department": dept_code,          # canonical code (or None)
        "due_date": due,
        "estimated_hours": est,
        "subtasks": subs,
    }


def _parse_candidates(reply: str, dept_by_key: dict) -> list[dict]:
    """Pull the first JSON array out of the model reply and normalize it. The
    model is asked for pure JSON but often wraps it in prose / code fences."""
    if not reply:
        return []
    m = re.search(r"\[[\s\S]*\]", reply)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(arr, list):
        return []
    out = []
    for raw in arr:
        c = _norm_candidate(raw, dept_by_key)
        if c:
            out.append(c)
    return out


def _prompt(text: str, depts: list[dict]) -> str:
    dept_list = ", ".join(f"{d['code']} ({d['name']})" for d in depts) or "(none configured)"
    return (
        "You extract actionable tasks from a document for a GMP cannabis company's task tracker.\n"
        "Read the text below and return EVERY distinct actionable task it implies — across ALL "
        "departments, not just one. For each task give a short imperative title, a 1-3 sentence "
        "description, the most likely department, a priority, a type, and any concrete sub-steps "
        "as subtasks (each with its own short description).\n\n"
        f"Valid departments (use the CODE): {dept_list}\n"
        "priority: one of critical|high|medium|low\n"
        "task_type: one of capa|sop|validation|document|lab|meeting|admin|other\n\n"
        "Return ONLY a JSON array, no prose, no code fence. Each element:\n"
        '{"title": str, "description": str, "department": <code or null>, '
        '"priority": str, "task_type": str, "reference_code": str|null, '
        '"due_date": "YYYY-MM-DD"|null, "estimated_hours": number|null, '
        '"subtasks": [{"title": str, "description": str}]}\n\n'
        f"DOCUMENT:\n{text}"
    )


@router.post("/extract")
async def extract_tasks(body: ExtractReq, user: dict = Depends(require_password_set)):
    text = (body.text or "").strip()
    if len(text) < 12:
        raise HTTPException(422, "Provide more text to extract tasks from")
    text = text[:_MAX_TEXT]

    async with rls(user) as c:
        dept_rows = await c.fetch("SELECT id, code, name FROM departments ORDER BY name")
        # task_extract is the purpose-built binding; fall back to voice_capture
        # (already bound in prod, same 'text → structured tasks' agent) so the
        # feature works without a new binding.
        binding = await c.fetchrow(
            "SELECT letta_agent_id FROM ai_agent_bindings"
            " WHERE function_key = ANY($1::text[]) AND is_active=true"
            " ORDER BY CASE function_key WHEN 'task_extract' THEN 0 ELSE 1 END LIMIT 1",
            ["task_extract", "voice_capture"])
    if binding is None:
        return {"available": False, "reason": "not_configured"}

    depts = [{"code": r["code"], "name": r["name"]} for r in dept_rows]
    dept_by_key = {}
    for r in dept_rows:
        dept_by_key[r["code"].lower()] = r["code"]
        dept_by_key[r["name"].lower()] = r["code"]

    # Multi-task extraction over a long document is a heavy reasoning job — give
    # the agent more room than the 30s default or it gets cut off mid-answer.
    reply = await _letta_message(binding["letta_agent_id"], _prompt(text, depts), timeout=150)
    if reply is None:
        return {"available": False, "reason": "letta_unreachable"}
    candidates = _parse_candidates(reply, dept_by_key)
    return {"available": True, "count": len(candidates), "candidates": candidates,
            "departments": depts}
