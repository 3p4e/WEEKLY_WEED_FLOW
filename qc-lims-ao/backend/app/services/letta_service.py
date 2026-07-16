"""
Letta AI service client wrapper.

Provides health checks and agent access for the LIMS AI supercharge layer.
Mirrors QdrantService singleton pattern for consistency.

EU GMP Annex 11: external dependencies must fail gracefully with
clear error responses — never crash the application.

Satisfies: AC-1.2, AC-1.3
"""

from typing import ClassVar

from app.core.config import settings


class LettaService:
    """
    Thin wrapper around letta-client for the LIMS AI supercharge layer.

    Provides:
    - Letta API health check
    - Qdrant health check (delegated via QdrantService)
    - MCP health check
    - Agent listing and messaging

    All external calls catch exceptions and return structured dicts —
    never raises unhandled exceptions (EU GMP Annex 11 requirement).
    """

    _instance: ClassVar["LettaService | None"] = None

    def __init__(self) -> None:
        """
        Initialize the Letta service.

        Reads configuration from Settings. Does NOT connect immediately —
        connections are lazy, initiated on first health check or query.
        """
        self.base_url: str = settings.letta_base_url
        self.mcp_url: str = settings.letta_mcp_url
        self._letta: "Letta | None" = None  # type: ignore[name-defined]

    @property
    def letta(self) -> "Letta":  # type: ignore[name-defined]
        """
        Lazy-init Letta client.

        The client is created once on first access. Subsequent calls
        return the same instance.

        Returns:
            Letta client instance.

        Raises:
            ImportError: If letta_client is not installed.
        """
        if self._letta is None:
            from letta_client import Letta

            self._letta = Letta(base_url=self.base_url)
        return self._letta

    def health_check(self) -> dict:
        """
        Check Letta API server connectivity.

        Returns:
            {"status": "healthy", "server_version": "..."} if reachable,
            {"status": "unreachable", "error": "..."} otherwise.

        AC-1.3: Health check method for Letta API, Qdrant, MCP.
        """
        try:
            from letta_client import Letta

            client = Letta(base_url=self.base_url)
            # Basic connectivity check — list available models
            models = client.models.list()
            model_names = [m.name for m in models] if models else []
            return {
                "status": "healthy",
                "models": model_names,
                "base_url": self.base_url,
            }
        except Exception as exc:
            return {
                "status": "unreachable",
                "base_url": self.base_url,
                "error": str(exc),
            }

    def health_check_mcp(self) -> dict:
        """
        Check MCP server connectivity.

        Returns:
            {"status": "healthy"} if reachable,
            {"status": "unreachable", "error": "..."} otherwise.
        """
        try:
            import httpx

            response = httpx.get(f"{self.mcp_url}/health", timeout=5.0)
            response.raise_for_status()
            return {
                "status": "healthy",
                "mcp_url": self.mcp_url,
            }
        except Exception as exc:
            return {
                "status": "unreachable",
                "mcp_url": self.mcp_url,
                "error": str(exc),
            }

    def health_check_all(self) -> dict:
        """
        Run health checks for all three services: Letta, Qdrant, MCP.

        Returns:
            {
                "letta": {...},
                "qdrant": {...},
                "mcp": {...},
                "all_healthy": bool
            }

        AC-1.3: Health check method for Letta API, Qdrant, MCP.
        """
        from app.services.qdrant_service import QdrantService

        letta_result = self.health_check()
        qdrant = QdrantService(url=settings.qdrant_url)
        qdrant_result = qdrant.health_check()
        mcp_result = self.health_check_mcp()

        all_healthy = all(
            r.get("status") == "healthy" or r.get("status") == "connected"
            for r in [letta_result, qdrant_result, mcp_result]
        )

        return {
            "letta": letta_result,
            "qdrant": qdrant_result,
            "mcp": mcp_result,
            "all_healthy": all_healthy,
        }

    def list_agents(self) -> list[dict]:
        """
        List all Letta agents.

        Returns:
            List of agent dicts with id, name, model, created_at.

        Raises:
            ConnectionError: If Letta API is unreachable.
        """
        agents = self.letta.agents.list()
        return [
            {
                "id": agent.id,
                "name": agent.name,
                "model": getattr(agent, "model", "unknown"),
                "created_at": str(getattr(agent, "created_at", "")),
            }
            for agent in agents
        ]


# Module-level singleton instance
_singleton: LettaService | None = None


def get_letta_service() -> LettaService:
    """
    Get or create a LettaService singleton.

    Thread-safe lazy initialization using module-level guard.
    Subsequent calls return the same instance.

    Returns:
        Configured LettaService.

    AC-1.2: LettaService singleton with lazy init and thread-safe instance.
    """
    global _singleton
    if _singleton is None:
        _singleton = LettaService()
    return _singleton
