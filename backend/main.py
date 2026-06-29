"""
GrowFlow AI Gateway
===================
A dedicated FastAPI service that bridges the GrowFlow task-manager front-end
with **Letta stateful agents** running in a Docker container on the KVM4 cloud
server.

Why a gateway (instead of the browser calling Letta directly)?
  * Keeps the Letta server URL / admin token off the client.
  * Gives the browser a small, stable, CORS-friendly API shaped around the
    app's needs (paraphrase / parse-voice / weekly-summary / chat).
  * Maps each GrowFlow user to *their own* persistent Letta agent, so the
    agent remembers that operator's department, blockers and weekly context
    across sessions — that is the whole point of "stateful".

Run:
    uvicorn main:app --host 0.0.0.0 --port 8080 --reload

Configuration is via environment variables (see .env.example).
"""

from __future__ import annotations

import os
import json
import re
from functools import lru_cache
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from letta_service import LettaService, LettaConfig

# ──────────────────────────────────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("GROWFLOW_ALLOWED_ORIGINS", "*").split(",") if o.strip()
]

app = FastAPI(
    title="GrowFlow AI Gateway",
    version="1.0.0",
    description="Bridges GrowFlow with Letta stateful agents (KVM4 Docker).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,          # set to your app origin(s) in prod
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_service() -> LettaService:
    """Single shared Letta client / agent-cache for the process."""
    cfg = LettaConfig(
        base_url=os.getenv("LETTA_BASE_URL", "http://localhost:8283"),
        token=os.getenv("LETTA_TOKEN") or None,
        model=os.getenv("LETTA_MODEL", "openai/gpt-4o-mini"),
        embedding=os.getenv("LETTA_EMBEDDING", "openai/text-embedding-3-small"),
        agent_prefix=os.getenv("LETTA_AGENT_PREFIX", "growflow"),
    )
    return LettaService(cfg)


# ──────────────────────────────────────────────────────────────────────────
#  Request / response models
# ──────────────────────────────────────────────────────────────────────────
class User(BaseModel):
    id: str = Field(..., description="Stable GrowFlow user id (maps 1:1 to a Letta agent)")
    name: Optional[str] = None
    role: Optional[str] = None            # operator | hod | qa | qp ...
    department: Optional[str] = None
    lang: str = "en"                       # 'en' | 'mk'


class ParaphraseReq(BaseModel):
    user: User
    text: str


class ParseVoiceReq(BaseModel):
    user: User
    transcript: str
    departments: list[str] = []
    people: list[str] = []


class SummaryReq(BaseModel):
    user: User
    kind: str = "report"                   # 'report' (this week) | 'plan' (next week)
    week_label: str = ""
    tasks: list[dict[str, Any]] = []


class ChatReq(BaseModel):
    user: User
    message: str


class TextOut(BaseModel):
    text: str


# ──────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────
def _lang_clause(lang: str) -> str:
    return "Reply in Macedonian." if lang == "mk" else "Reply in English."


def _extract_json(raw: str) -> dict:
    """Letta agents wrap replies in prose; pull the first JSON object out."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


# ──────────────────────────────────────────────────────────────────────────
#  Routes
# ──────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    svc = get_service()
    return {"status": "ok", "letta": svc.ping()}


@app.post("/ai/paraphrase", response_model=TextOut)
def paraphrase(req: ParaphraseReq) -> TextOut:
    """Clean up a dictated / rough task note into one professional sentence."""
    svc = get_service()
    prompt = (
        "Rewrite the following production task note as one clear, professional "
        "sentence for a GMP medical-cannabis facility. Keep it concise and keep "
        f"any batch/room/equipment IDs. {_lang_clause(req.user.lang)}\n\n"
        f"Note: {req.text}"
    )
    try:
        out = svc.ask(req.user.model_dump(), prompt)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Letta error: {exc}") from exc
    return TextOut(text=out.strip())


@app.post("/ai/parse-voice")
def parse_voice(req: ParseVoiceReq) -> dict:
    """Turn a spoken sentence into a structured GrowFlow task."""
    svc = get_service()
    depts = ", ".join(req.departments) or "Cultivation, Irrigation, Production, QC, QA/QP, Warehouse, Maintenance"
    people = ", ".join(req.people) or "any teammate"
    prompt = (
        "You convert a spoken instruction into a structured task. "
        "Return ONLY a JSON object with keys: title, department, priority, "
        "assignee, due, days (array of weekday names). "
        f"Valid departments: {depts}. Valid assignees: {people}. "
        "priority is one of critical|high|medium|low. "
        "If a field is not stated, use an empty string (or [] for days).\n\n"
        f"Spoken instruction: \"{req.transcript}\""
    )
    try:
        raw = svc.ask(req.user.model_dump(), prompt)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Letta error: {exc}") from exc
    data = _extract_json(raw)
    data.setdefault("title", req.transcript.strip().capitalize())
    data.setdefault("department", "")
    data.setdefault("priority", "medium")
    data.setdefault("assignee", "")
    data.setdefault("due", "")
    data.setdefault("days", [])
    return data


@app.post("/ai/weekly-summary", response_model=TextOut)
def weekly_summary(req: SummaryReq) -> TextOut:
    """Generate a status report (this week) or a planning analysis (next week)."""
    svc = get_service()
    lines = []
    for t in req.tasks:
        lines.append(
            f"- [{t.get('status','pending')}] {t.get('title','')} "
            f"(dept={t.get('dept','')}, owner={t.get('owner','')}, "
            f"priority={t.get('pr','')}, days={','.join(t.get('days',[]))})"
        )
    body = "\n".join(lines) or "(no tasks)"

    if req.kind == "plan":
        role = (
            "You are a production planning advisor. Analyse next week's tasks and "
            "give: Priorities, Dependency / cross-department risks, Workload balance, "
            "and 2-3 concrete recommendations. Use short bullet points."
        )
    else:
        role = (
            "You are a weekly status-report writer for a GMP cannabis facility. "
            "Summarise: Completed, In progress, Blockers (call out STUCK tasks), "
            "and Pending sign-offs. Use short bullet points."
        )
    prompt = (
        f"{role} {_lang_clause(req.user.lang)}\n\n"
        f"Week: {req.week_label}\nUser: {req.user.name} ({req.user.role}, {req.user.department})\n\n"
        f"Tasks:\n{body}"
    )
    try:
        out = svc.ask(req.user.model_dump(), prompt)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Letta error: {exc}") from exc
    return TextOut(text=out.strip())


@app.post("/ai/chat", response_model=TextOut)
def chat(req: ChatReq) -> TextOut:
    """Free-form chat with the user's own stateful agent (remembers context)."""
    svc = get_service()
    try:
        out = svc.ask(req.user.model_dump(), req.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Letta error: {exc}") from exc
    return TextOut(text=out.strip())


@app.post("/agents/reset")
def reset_agent(user: User) -> dict:
    """Drop the cached agent mapping for a user (next call re-creates it)."""
    svc = get_service()
    svc.forget(user.id)
    return {"ok": True}
