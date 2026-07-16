"""Tests for LettaService external-agent resolution (hybrid strategy).

Uses a fake letta_client so no server or real SDK is needed.
"""
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Provide a stub letta_client BEFORE importing letta_service.
stub = types.ModuleType("letta_client")
stub.Letta = object  # constructor is monkeypatched away below
sys.modules["letta_client"] = stub

import CONTENT_CREATOR_FRAMEWORK.letta_service as ls  # noqa: E402


class _Agent:
    def __init__(self, name, id):
        self.name = name
        self.id = id


class _Msg:
    def __init__(self, text):
        self.content = text


class _Resp:
    def __init__(self, texts):
        self.messages = [_Msg(t) for t in texts]


class FakeClient:
    def __init__(self, agents):
        self._agents_list = agents
        self.sent = []

        outer = self

        class _Messages:
            def create(self, agent_id, input):
                outer.sent.append((agent_id, input))
                return _Resp([f"reply from {agent_id}"])

        class _Agents:
            def list(self_inner):
                return outer._agents_list
            messages = _Messages()

        self.agents = _Agents()


def _service(agents):
    svc = ls.LettaService.__new__(ls.LettaService)
    svc._agents = {}
    svc._archives = {}
    svc._tools = {}
    svc._external_agents = {}
    svc.client = FakeClient(agents)
    return svc


def test_resolve_external_agent_found_and_cached():
    svc = _service([_Agent("eu_gmp_compliance_expert", "agent-123")])
    a = svc.resolve_external_agent("eu_gmp_compliance_expert")
    assert a is not None and a.id == "agent-123"
    # cached: mutate the underlying list, still returns cached value
    svc.client._agents_list = []
    assert svc.resolve_external_agent("eu_gmp_compliance_expert").id == "agent-123"


def test_resolve_external_agent_missing_returns_none():
    svc = _service([_Agent("some_other_agent", "agent-9")])
    assert svc.resolve_external_agent("gmp_rag_agent") is None


def test_send_to_external_sends_and_extracts_text():
    svc = _service([_Agent("gmp_rag_agent", "agent-777")])
    out = svc.send_to_external("gmp_rag_agent", "retrieve X")
    assert out == "reply from agent-777"
    assert svc.client.sent == [("agent-777", "retrieve X")]


def test_send_to_external_missing_agent_returns_empty():
    svc = _service([])
    assert svc.send_to_external("gmp_rag_agent", "hi") == ""
    assert svc.client.sent == []
