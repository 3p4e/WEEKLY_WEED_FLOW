"""
Letta integration for the GrowFlow AI Gateway.

Wraps the official `letta-client` SDK. One **stateful agent per GrowFlow user**
is created on first use and reused thereafter, so the agent accumulates memory
about that operator / head-of-department (their department, recurring blockers,
preferences) across weeks.

Letta runs in a Docker container on KVM4 — point LETTA_BASE_URL at it
(e.g. http://10.0.0.4:8283 on the private network, or via an SSH tunnel in dev).
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Optional

from letta_client import Letta


@dataclass
class LettaConfig:
    base_url: str = "http://localhost:8283"
    token: Optional[str] = None                       # set if your server requires auth
    model: str = "openai/gpt-4o-mini"                 # must match a provider configured in Letta
    embedding: str = "openai/text-embedding-3-small"
    agent_prefix: str = "growflow"


PERSONA = (
    "You are GrowFlow Assistant, an operations co-pilot embedded in a workflow "
    "task manager for a GMP-licensed medical-cannabis production facility. You "
    "help heads of department, operators and QA/QP staff write clear tasks, "
    "summarise weekly progress, and coordinate hand-offs between departments "
    "(Cloning & Nursery, Vegetation, Flowering, Irrigation, Production, QC, "
    "QA/QP, Warehouse In/Out, Security, Maintenance). Be concise and precise. "
    "When asked for JSON, return only JSON."
)


class LettaService:
    def __init__(self, cfg: LettaConfig):
        self.cfg = cfg
        # token is optional for self-hosted servers without auth
        self.client = Letta(base_url=cfg.base_url, token=cfg.token) if cfg.token \
            else Letta(base_url=cfg.base_url)
        self._agents: dict[str, str] = {}            # user_id -> agent_id
        self._lock = Lock()

    # ── connectivity ────────────────────────────────────────────────────
    def ping(self) -> bool:
        try:
            self.client.agents.list(limit=1)
            return True
        except Exception:  # noqa: BLE001
            return False

    # ── agent lifecycle ─────────────────────────────────────────────────
    def _agent_name(self, user_id: str) -> str:
        return f"{self.cfg.agent_prefix}-{user_id}"

    def _human_block(self, user: dict) -> str:
        return (
            f"Name: {user.get('name','Unknown')}\n"
            f"Role: {user.get('role','operator')}\n"
            f"Department: {user.get('department','General')}\n"
            f"Preferred language: {'Macedonian' if user.get('lang')=='mk' else 'English'}"
        )

    def get_or_create_agent(self, user: dict) -> str:
        uid = str(user["id"])
        if uid in self._agents:
            return self._agents[uid]

        with self._lock:
            if uid in self._agents:           # double-checked after acquiring lock
                return self._agents[uid]

            name = self._agent_name(uid)

            # Reuse an existing agent for this user if the server already has one
            try:
                existing = self.client.agents.list(name=name, limit=1)
                if existing:
                    self._agents[uid] = existing[0].id
                    return existing[0].id
            except Exception:  # noqa: BLE001
                pass

            agent = self.client.agents.create(
                name=name,
                memory_blocks=[
                    {"label": "persona", "value": PERSONA},
                    {"label": "human", "value": self._human_block(user)},
                ],
                model=self.cfg.model,
                embedding=self.cfg.embedding,
                tags=["growflow", f"user:{uid}"],
            )
            self._agents[uid] = agent.id
            return agent.id

    def forget(self, user_id: str) -> None:
        self._agents.pop(str(user_id), None)

    # ── messaging ───────────────────────────────────────────────────────
    def ask(self, user: dict, message: str) -> str:
        """Send a message to the user's stateful agent and return its reply text."""
        agent_id = self.get_or_create_agent(user)
        resp = self.client.agents.messages.create(
            agent_id=agent_id,
            messages=[{"role": "user", "content": message}],
        )
        return self._reply_text(resp)

    @staticmethod
    def _reply_text(resp) -> str:
        """Extract the assistant's natural-language reply from a Letta response."""
        parts: list[str] = []
        for msg in getattr(resp, "messages", []) or []:
            mtype = getattr(msg, "message_type", None)
            if mtype == "assistant_message":
                content = getattr(msg, "content", "")
                if isinstance(content, list):           # some SDK versions return blocks
                    content = "".join(getattr(c, "text", "") for c in content)
                if content:
                    parts.append(content)
        return "\n".join(parts).strip()
