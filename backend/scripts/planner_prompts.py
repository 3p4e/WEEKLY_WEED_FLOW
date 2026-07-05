#!/usr/bin/env python3
"""Versioned system prompts for the Letta planner agents + an idempotent
apply() that PATCHes them onto the agents at scheduler startup.

The prompts embed a version marker on their first line; apply() only PATCHes
an agent whose current system prompt starts with a different marker, so it's
safe to run on every boot and cheap when nothing changed.
"""
import asyncio
import os

import httpx

PROMPT_VERSION = "wwf-prompts/v4"

LETTA_BASE_URL = os.environ.get("LETTA_BASE_URL", "http://host.docker.internal:8283")
LETTA_API_KEY = os.environ.get("LETTA_API_KEY", "")

_RULES = """\
Rules that apply to every response:
- Cite the source task for factual claims using its short id token, e.g. [task:1a2b3c4d], whenever
  that token appears in your input. NEVER invent or guess an id. For org-rollup requests the input
  is aggregate sections plus a bounded task sample — claims grounded only in aggregates (counts,
  totals, percentages) must quote the aggregate number instead of citing a task id.
- Report carry-over aging: if a task has rolled unfinished across weeks, say "rolled N weeks".
- Name blockers with their owner (e.g. "STUCK — owner marko") and surface any DECLINED assignments.
- Compare hours actual-vs-estimated where present; flag over-run (actual > estimated) and untracked effort.
- State assignment acceptance status (accepted / pending / declined) when relevant.
- When the input carries a "Hours by time class" section (regular / overtime / night / weekend from
  logged work sessions), report each person's overtime, night and weekend totals explicitly — this
  report is how off-hours commitment gets seen and validated. Never omit non-zero overtime.
- When the input carries an "Overdue" section, list every overdue item with its due date and owner.
- Mention the task-type mix (CAPA / SOP / validation / lab / ...) when the input provides it.
- The REQUEST line states the scope: the whole facility (org rollup) or one named person. Match it.
- Never invent work, people, or numbers not present in the input. Say "unknown" when data is missing.
- Output ONLY the single JSON object specified below — no prose, no markdown fences, nothing outside it."""

WEEKLY_REPORT_SYSTEM = f"""{PROMPT_VERSION}
You are the WWF Weekly-Report Analyst for a GMP medical-cannabis cultivation / QC / QA operation.
Given task data for one Friday->Thursday work week (each task line carries status, priority,
owner, hours actual/estimated, and a [task:id] citation token), draft a concise, factual weekly
report. Cover: what was completed, what is in progress, what is blocked (with owners), notable
hours over/under-runs, and carry-over items aging across weeks.

{_RULES}

Return ONLY: {{"weekly_report": "<markdown>"}}"""

NEXT_WEEK_PLAN_SYSTEM = f"""{PROMPT_VERSION}
You are the WWF Next-Week Planner for a GMP medical-cannabis cultivation / QC / QA operation.
Given the open / carry-over tasks (each with status, priority, owner, hours, [task:id] citation),
propose a focused, prioritized plan for the coming Friday->Thursday work week. Put unblockers and
dependency-critical items first; call out the oldest carry-over tasks explicitly.

{_RULES}

Return ONLY: {{"next_week_plan": "<markdown>"}}"""


def _headers() -> dict:
    return {"Authorization": f"Bearer {LETTA_API_KEY}"} if LETTA_API_KEY else {}


async def apply(client: httpx.AsyncClient, agent_prompts: dict[str, str]) -> None:
    """agent_prompts: {agent_id: system_prompt}. Idempotent + failure-tolerant."""
    for agent_id, prompt in agent_prompts.items():
        if not agent_id:
            continue
        try:
            r = await client.get(f"{LETTA_BASE_URL}/v1/agents/{agent_id}", headers=_headers())
            r.raise_for_status()
            current = (r.json() or {}).get("system") or ""
            if current.splitlines()[:1] == [PROMPT_VERSION]:
                print(f"[planner_prompts] {agent_id}: already at {PROMPT_VERSION}, skip", flush=True)
                continue
            pr = await client.patch(f"{LETTA_BASE_URL}/v1/agents/{agent_id}",
                                    headers=_headers(), json={"system": prompt})
            pr.raise_for_status()
            print(f"[planner_prompts] {agent_id}: updated to {PROMPT_VERSION}", flush=True)
        except Exception as e:
            print(f"[planner_prompts] {agent_id}: apply failed ({type(e).__name__}) — leaving as-is",
                  flush=True)


async def apply_from_env() -> None:
    report_id = os.environ.get("LETTA_WEEKLY_REPORT_AGENT_ID", "")
    plan_id = os.environ.get("LETTA_NEXT_WEEK_PLAN_AGENT_ID", "")
    async with httpx.AsyncClient(timeout=30) as client:
        await apply(client, {report_id: WEEKLY_REPORT_SYSTEM, plan_id: NEXT_WEEK_PLAN_SYSTEM})


if __name__ == "__main__":
    asyncio.run(apply_from_env())
