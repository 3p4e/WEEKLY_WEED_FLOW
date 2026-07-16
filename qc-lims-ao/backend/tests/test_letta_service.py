"""
Tests for LettaService — AC-1.1, AC-1.2, AC-1.3.

Mocks letta_client and httpx to avoid KVM4 dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest
from app.services.letta_service import get_letta_service, LettaService


@pytest.fixture
def mock_settings():
    """Mock settings with test URLs."""
    with patch("app.services.letta_service.settings") as mock:
        mock.letta_base_url = "http://localhost:8283"
        mock.letta_mcp_url = "http://localhost:6507"
        mock.qdrant_url = "http://localhost:6333"
        yield mock


class TestLettaServiceInit:
    """AC-1.2: LettaService singleton with lazy init."""

    def test_init_reads_settings(self, mock_settings) -> None:  # type: ignore[no-untyped-def]
        """AC-1.1: Settings extended with letta_base_url, letta_mcp_url, voyage_api_key."""
        from app.core.config import Settings

        s = Settings()
        # AC-1.1: Verify new fields exist and have string defaults
        assert hasattr(s, "letta_base_url")
        assert hasattr(s, "letta_mcp_url")
        assert hasattr(s, "qdrant_url")
        assert hasattr(s, "voyage_api_key")
        assert isinstance(s.letta_base_url, str)
        assert isinstance(s.letta_mcp_url, str)
        assert isinstance(s.voyage_api_key, str)

    def test_singleton_returns_same_instance(self, mock_settings) -> None:  # type: ignore[no-untyped-def]
        """AC-1.2: Subsequent calls return the same instance."""
        from app.services.letta_service import (
            get_letta_service,
            _singleton as singleton_ref,
        )

        import app.services.letta_service as mod

        # Reset singleton for test isolation
        mod._singleton = None

        svc1 = get_letta_service()
        svc2 = get_letta_service()
        assert svc1 is svc2

    def test_letta_property_lazy_init(
        self, mock_settings  # type: ignore[no-untyped-def]
    ) -> None:
        """AC-1.2: Lazy init Letta client on first access."""
        import app.services.letta_service as mod

        mod._singleton = None
        svc = None

        with patch("letta_client.Letta") as MockLetta:
            mock_client = MagicMock()
            MockLetta.return_value = mock_client

            svc = get_letta_service()
            # Letta client not created until property accessed
            client = svc.letta
            MockLetta.assert_called_once_with(base_url="http://localhost:8283")
            assert client is mock_client
            # Second access returns same client
            client2 = svc.letta
            assert client is client2
            assert MockLetta.call_count == 1  # Still only called once


class TestLettaServiceHealthCheck:
    """AC-1.3: Health check method for Letta API, Qdrant, MCP."""

    def test_health_check_returns_healthy(
        self, mock_settings  # type: ignore[no-untyped-def]
    ) -> None:
        """AC-1.3: Letta health check returns healthy status."""
        import app.services.letta_service as mod

        mod._singleton = None

        with patch("letta_client.Letta") as MockLetta:
            mock_client = MagicMock()
            mock_model = MagicMock()
            mock_model.name = "claude-sonnet-4-5"
            mock_client.models.list.return_value = [mock_model]
            MockLetta.return_value = mock_client

            svc = get_letta_service()
            result = svc.health_check()

            assert result["status"] == "healthy"
            assert "claude-sonnet-4-5" in result["models"]
            assert result["base_url"] == "http://localhost:8283"

    def test_health_check_handles_unreachable(
        self, mock_settings  # type: ignore[no-untyped-def]
    ) -> None:
        """AC-1.3: Graceful handling when Letta is unreachable."""
        import app.services.letta_service as mod

        mod._singleton = None

        with patch("letta_client.Letta") as MockLetta:
            MockLetta.side_effect = ConnectionError("Connection refused")

            svc = get_letta_service()
            result = svc.health_check()

            assert result["status"] == "unreachable"
            assert "Connection refused" in result["error"]

    def test_health_check_mcp_healthy(
        self, mock_settings  # type: ignore[no-untyped-def]
    ) -> None:
        """AC-1.3: MCP health check returns healthy with httpx mock."""
        import app.services.letta_service as mod

        mod._singleton = None

        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            svc = get_letta_service()
            result = svc.health_check_mcp()

            assert result["status"] == "healthy"
            assert result["mcp_url"] == "http://localhost:6507"
            mock_get.assert_called_once_with(
                "http://localhost:6507/health", timeout=5.0
            )

    def test_health_check_mcp_unreachable(
        self, mock_settings  # type: ignore[no-untyped-def]
    ) -> None:
        """AC-1.3: MCP health check handles connection errors."""
        import app.services.letta_service as mod

        mod._singleton = None

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = ConnectionError("Timeout")

            svc = get_letta_service()
            result = svc.health_check_mcp()

            assert result["status"] == "unreachable"
            assert "Timeout" in result["error"]

    def test_health_check_all_aggregates(
        self, mock_settings  # type: ignore[no-untyped-def]
    ) -> None:
        """AC-1.3: health_check_all aggregates Letta + Qdrant + MCP status."""
        import app.services.letta_service as mod

        mod._singleton = None

        with patch("letta_client.Letta") as MockLetta, \
             patch("httpx.get") as mock_httpx_get, \
             patch("app.services.qdrant_service.QdrantService") as MockQdrant:

            # Mock Letta — healthy
            mock_letta_client = MagicMock()
            mock_model = MagicMock()
            mock_model.name = "claude-sonnet-4-5"
            mock_letta_client.models.list.return_value = [mock_model]
            MockLetta.return_value = mock_letta_client

            # Mock Qdrant — healthy
            mock_qdrant = MagicMock()
            mock_qdrant.health_check.return_value = {
                "status": "connected",
                "collections": ["pp_qms_sops"],
            }
            MockQdrant.return_value = mock_qdrant

            # Mock MCP — healthy
            mock_http_response = MagicMock()
            mock_http_response.raise_for_status.return_value = None
            mock_httpx_get.return_value = mock_http_response

            svc = get_letta_service()
            result = svc.health_check_all()

            assert result["letta"]["status"] == "healthy"
            assert result["qdrant"]["status"] == "connected"
            assert result["mcp"]["status"] == "healthy"
            assert result["all_healthy"] is True

    def test_health_check_all_detects_failure(
        self, mock_settings  # type: ignore[no-untyped-def]
    ) -> None:
        """AC-1.3: all_healthy is False when any service is down."""
        import app.services.letta_service as mod

        mod._singleton = None

        with patch("letta_client.Letta") as MockLetta, \
             patch("httpx.get") as mock_httpx_get, \
             patch("app.services.qdrant_service.QdrantService") as MockQdrant:

            # Mock Letta — healthy
            mock_letta_client = MagicMock()
            mock_model = MagicMock()
            mock_model.name = "claude-sonnet-4-5"
            mock_letta_client.models.list.return_value = [mock_model]
            MockLetta.return_value = mock_letta_client

            # Mock Qdrant — unhealthy
            mock_qdrant = MagicMock()
            mock_qdrant.health_check.return_value = {
                "status": "unreachable",
                "error": "Connection refused",
            }
            MockQdrant.return_value = mock_qdrant

            # Mock MCP — healthy
            mock_http_response = MagicMock()
            mock_http_response.raise_for_status.return_value = None
            mock_httpx_get.return_value = mock_http_response

            svc = get_letta_service()
            result = svc.health_check_all()

            assert result["letta"]["status"] == "healthy"
            assert result["qdrant"]["status"] == "unreachable"
            assert result["mcp"]["status"] == "healthy"
            assert result["all_healthy"] is False


class TestLettaServiceListAgents:
    """List agents functionality."""

    def test_list_agents_returns_agent_dicts(
        self, mock_settings  # type: ignore[no-untyped-def]
    ) -> None:
        """List agents returns structured dicts with id, name, model, created_at."""
        import app.services.letta_service as mod

        mod._singleton = None

        with patch("letta_client.Letta") as MockLetta:
            mock_client = MagicMock()
            mock_agent = MagicMock()
            mock_agent.id = "agent-123"
            mock_agent.name = "GMP Expert Agent"
            mock_agent.model = "anthropic/claude-sonnet-4-5"
            mock_agent.created_at = "2026-05-31T12:00:00Z"
            mock_client.agents.list.return_value = [mock_agent]
            MockLetta.return_value = mock_client

            svc = get_letta_service()
            agents = svc.list_agents()

            assert len(agents) == 1
            assert agents[0]["id"] == "agent-123"
            assert agents[0]["name"] == "GMP Expert Agent"
            assert agents[0]["model"] == "anthropic/claude-sonnet-4-5"
