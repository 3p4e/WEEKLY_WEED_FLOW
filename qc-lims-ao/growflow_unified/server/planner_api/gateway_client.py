"""Client to the planner Letta gateway (the dedicated FastAPI container in the Letta stack).

All planner AI flows go through the gateway, which holds the Letta agent map + credentials
and is the only path to the agents. Every call degrades gracefully (returns None / False)
when PLANNER_GATEWAY_URL is unset or the gateway/agent errors, so the planner stays fully
usable without AI.
"""
from __future__ import annotations

import httpx

from .config import get_settings

# Logical planner agents the gateway exposes (allow-list; the gateway enforces it too).
SUITABLE_AGENTS: set[str] = {
    "weekly-report",
    "next-week-plan",
    "task-rewrite",
    "executive-analytics",
}


class GatewayClient:
    def __init__(self) -> None:
        s = get_settings()
        self._base = s.gateway_url.rstrip("/")
        self._token = s.gateway_token

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def invoke(self, agent: str, message: str, context: dict | None = None) -> dict | None:
        """Call a planner agent through the gateway; returns its parsed JSON, or None on any
        failure / when the gateway is unconfigured (graceful degradation)."""
        if not self.configured or agent not in SUITABLE_AGENTS:
            return None
        try:
            async with httpx.AsyncClient(timeout=70) as c:
                r = await c.post(
                    f"{self._base}/agents/{agent}/invoke",
                    json={"message": message, "context": context},
                    headers=self._headers(),
                )
                r.raise_for_status()
                return r.json()
        except Exception:  # network/auth/agent error ⇒ graceful fallback
            return None

    async def record_exec_report(self, payload: dict) -> bool:
        """Persist a submitted report into the executive agent's durable memory (best-effort)."""
        if not self.configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=70) as c:
                r = await c.post(
                    f"{self._base}/memory/exec/report", json=payload, headers=self._headers()
                )
                r.raise_for_status()
                return True
        except Exception:
            return False
