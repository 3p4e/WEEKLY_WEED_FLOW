# docengine.app.letta — thin DIRECT-REST Letta client.
#
# Deliberately not the Rust MCP bridge: the handover-documented decode bug
# ("missing field `package`" on tool get, config writes rejected) reproduced
# in this project — plain REST against /v1 works and is what the live tools
# themselves assume. Only the endpoints the DocEngine needs, nothing more.
from __future__ import annotations

from typing import Any

import httpx

from .config import settings


class LettaError(RuntimeError):
    """Carries the HTTP status when there was one, because "absent" and "the
    server had a bad moment" are different answers and one caller acts on the
    difference (fleet._reconcile_blocks creates a block when one is missing)."""

    def __init__(self, *args, status: int | None = None):
        super().__init__(*args)
        self.status = status


class LettaClient:
    """Async Letta v1 REST client. All fleet mutations are ADDITIVE and
    namespaced gf_* — existing agents are never modified (handover caution)."""

    def __init__(self, base: str | None = None, key: str | None = None, timeout: httpx.Timeout | None = None):
        self.base = (base if base is not None else settings.letta_base).rstrip("/")
        self.key = key if key is not None else settings.letta_key
        # Short connect (fail fast if the server is down) + long read (one
        # agent generation can take minutes). A single float would force the
        # generous read window onto the connect step too.
        self.timeout = timeout or httpx.Timeout(
            settings.letta_read_timeout,
            connect=settings.letta_connect_timeout,
        )
        # Lazily created, then held for this instance's lifetime. A single
        # document workflow threads ONE LettaClient through the whole run
        # (pipeline.run_workflow does `client = client or LettaClient()` once,
        # then passes that same instance to ensure_fleet/spawn_ephemeral/
        # send_message/... throughout — see pipeline.py, fleet.py) and makes
        # 50-70 separate REST calls on it. Building a brand-new
        # httpx.AsyncClient (fresh TCP+TLS connection) per call paid full
        # connection setup 50-70 times over; one shared, pooled client reuses
        # the underlying connection across calls instead. httpx.AsyncClient's
        # connection pooling is safe for this — the calls here are sequential
        # awaits on one job, never concurrent on the same instance.
        self._client_instance: httpx.AsyncClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self.base and self.key)

    def _client(self) -> httpx.AsyncClient:
        if self._client_instance is None or self._client_instance.is_closed:
            self._client_instance = httpx.AsyncClient(
                base_url=self.base + "/v1",
                headers={"Authorization": f"Bearer {self.key}"},
                timeout=self.timeout,
            )
        return self._client_instance

    async def aclose(self) -> None:
        """Release the pooled connection(s). Callers that own a LettaClient
        for a bounded span of work (e.g. pipeline.run_workflow, one job) must
        call this when done so file descriptors don't accumulate across many
        requests/jobs, each of which constructs its own LettaClient."""
        if self._client_instance is not None and not self._client_instance.is_closed:
            await self._client_instance.aclose()

    async def _req(self, method: str, path: str, **kw) -> Any:
        if not self.configured:
            raise LettaError("Letta not configured")
        c = self._client()
        r = await c.request(method, path, **kw)
        if r.status_code >= 400:
            raise LettaError(f"{method} {path} -> {r.status_code}: {r.text[:300]}",
                             status=r.status_code)
        if not r.content:
            return None
        return r.json()

    # ---- reads ----
    async def list_agents(self, name: str | None = None) -> list[dict]:
        params = {"name": name} if name else None
        out = await self._req("GET", "/agents/", params=params)
        return out or []

    async def list_sources(self) -> list[dict]:
        return await self._req("GET", "/sources/") or []

    async def list_tools(self) -> list[dict]:
        return await self._req("GET", "/tools/") or []

    async def list_models(self) -> list[dict]:
        """LLM handles the server will accept. Note this is a registry, not a
        live probe: Letta adds a handle when a provider syncs and never prunes
        it, so a handle listed here can still belong to a route the upstream
        gateway no longer serves."""
        return await self._req("GET", "/models/") or []

    async def list_embedding_models(self) -> list[dict]:
        return await self._req("GET", "/models/embedding") or []

    # ---- additive fleet ops (gf_* only; guarded) ----
    @staticmethod
    def _guard_gf(name: str) -> None:
        if not name.startswith("gf_"):
            raise LettaError(f"refusing to touch non-gf_ agent: {name!r}")

    async def create_agent(self, spec: dict) -> dict:
        self._guard_gf(spec.get("name", ""))
        return await self._req("POST", "/agents/", json=spec)

    async def attach_source(self, agent_id: str, source_id: str) -> None:
        await self._req(
            "PATCH", f"/agents/{agent_id}/sources/attach/{source_id}"
        )

    async def create_tool(self, source_code: str, description: str = "") -> dict:
        """Register a Python source tool. Name is taken from the def by Letta."""
        body: dict[str, Any] = {"source_code": source_code}
        if description:
            body["description"] = description
        return await self._req("POST", "/tools/", json=body)

    async def update_tool(self, tool_id: str, source_code: str, description: str = "") -> dict:
        """Replace a registered tool's source in place.

        The tool is a shared server object, not per-agent state, so nothing in
        the create-if-missing path ever revisits it: once registered, an edit to
        the committed source could not reach the server at all. That is exactly
        wrong for this one, because the tool is where the dataset scoping is
        actually enforced."""
        body: dict[str, Any] = {"source_code": source_code}
        if description:
            body["description"] = description
        return await self._req("PATCH", f"/tools/{tool_id}", json=body)

    async def attach_tool(self, agent_id: str, tool_id: str) -> None:
        await self._req("PATCH", f"/agents/{agent_id}/tools/attach/{tool_id}")

    async def get_block(self, agent_id: str, label: str) -> dict | None:
        """The block, or None if the agent genuinely does not have it.

        Only a 404 means absent. Swallowing everything here used to be
        harmless — the caller just logged — but fleet._reconcile_blocks now
        CREATES and attaches a block when this returns None, so a transient 5xx
        or a proxy hiccup would have it manufacture a duplicate label on a live
        agent. Anything that is not a 404 is re-raised for the caller's own
        non-fatal handler to log."""
        try:
            return await self._req("GET", f"/agents/{agent_id}/core-memory/blocks/{label}")
        except LettaError as e:
            if e.status == 404:
                return None
            raise

    async def update_block(
        self, agent_id: str, label: str, value: str | None = None, read_only: bool | None = None
    ) -> None:
        """Rewrite one core-memory block's value and/or its read_only flag.

        This is a memory write, not a config write — the handover's "never edit
        an existing agent" caution is about POST/PATCH of llm_config, which this
        server rejects over the legacy provider enum. Callers must keep it to
        blocks they own on gf_* agents.

        read_only is the agent-facing flag: it stops the agent editing the block
        with its own memory_replace/memory_insert tools. It does NOT lock this
        API out — verified live against letta-6ou3: a block set read_only still
        accepts a value PATCH here, which is what lets fleet.py keep governance
        blocks both agent-immutable and declaratively reconcilable."""
        body: dict[str, Any] = {}
        if value is not None:
            body["value"] = value
        if read_only is not None:
            body["read_only"] = read_only
        if not body:
            return
        await self._req("PATCH", f"/agents/{agent_id}/core-memory/blocks/{label}", json=body)

    async def create_block(
        self, label: str, value: str, read_only: bool = False, limit: int = 100_000
    ) -> dict:
        """Create a standalone memory block, for attaching to an agent below.

        Needed for the block an agent does not have yet: an agent created before
        a block was declared simply has no such label, and the per-label PATCH
        route 404s on it. Blocks are created then attached (two calls) because
        that is the only route the server exposes for adding one to a live
        agent — memory_blocks is create-time only."""
        return await self._req(
            "POST",
            "/blocks/",
            json={"label": label, "value": value, "read_only": read_only, "limit": limit},
        )

    async def attach_block(self, agent_id: str, block_id: str) -> None:
        await self._req("PATCH", f"/agents/{agent_id}/core-memory/blocks/attach/{block_id}")

    async def update_agent_config(self, agent_id: str, body: dict) -> dict:
        """PATCH an existing agent's own config, after the gf_ namespace check.

        Deliberately narrow in what callers pass: fleet.py sends only
        context_window_limit / max_tokens. The model handle is NOT reconciled —
        fleet.yaml documents that as a standing decision, not an oversight, and
        this method does not change it."""
        agent = await self.get_agent(agent_id)
        self._guard_gf((agent or {}).get("name", ""))
        return await self._req("PATCH", f"/agents/{agent_id}", json=body)

    async def reset_messages(self, agent_id: str) -> None:
        """Drop an agent's accumulated message buffer, after the gf_ check.

        `message_buffer_autoclear` only stops FUTURE growth. An agent that has
        already accumulated stays slow until its existing buffer goes —
        gf_qa_auditor was at 78k of its 128k window, which is what the 300s read
        timeout was — so the reconciler clears it once, at the moment it turns
        autoclear on."""
        agent = await self.get_agent(agent_id)
        self._guard_gf((agent or {}).get("name", ""))
        # The body is REQUIRED — the route 422s without one (seen live).
        # add_default_initial_messages stays false: these agents are driven by
        # the pipeline, which supplies the whole prompt every turn, so a
        # re-seeded greeting would just be tokens nobody reads.
        await self._req(
            "PATCH",
            f"/agents/{agent_id}/reset-messages",
            json={"add_default_initial_messages": False},
        )

    async def get_agent(self, agent_id: str) -> dict:
        """Fetch one agent's full record by id. Used by delete_agent's guard
        below (it needs the name to check); also handy standalone."""
        return await self._req("GET", f"/agents/{agent_id}")

    async def delete_agent(self, agent_id: str) -> None:
        """Delete an agent by id, after confirming its name is one this
        client is allowed to touch.

        Every caller today only ever passes ids of agents it created itself
        (e.g. spawn_ephemeral's short-lived clones) — true in practice, but
        previously nothing enforced it: this took a bare id and issued the
        DELETE unconditionally, so a future caller passing a wrong/stale/
        unrelated id would silently delete whatever agent that id happened to
        name. Guard it the same way create_agent guards its way in (see
        _guard_gf — the gf_* namespace every agent this client manages,
        fleet or ephemeral, is created under): look the agent up first and
        refuse to delete anything outside that namespace."""
        agent = await self.get_agent(agent_id)
        self._guard_gf((agent or {}).get("name", ""))
        await self._req("DELETE", f"/agents/{agent_id}")

    # ---- conversation ----
    async def send_message(self, agent_id: str, text: str) -> str:
        """Send one user message; return the agent's assistant text reply."""
        out = await self._req(
            "POST",
            f"/agents/{agent_id}/messages",
            json={"messages": [{"role": "user", "content": text}]},
        )
        # v1 returns {"messages": [...]} with assistant_message entries
        msgs = (out or {}).get("messages", [])
        parts: list[str] = []
        for m in msgs:
            t = m.get("message_type") or m.get("role")
            if t in ("assistant_message", "assistant"):
                c = m.get("content")
                if isinstance(c, str):
                    parts.append(c)
                elif isinstance(c, list):
                    parts.extend(
                        x.get("text", "") for x in c if isinstance(x, dict)
                    )
        return "\n".join(p for p in parts if p).strip()
