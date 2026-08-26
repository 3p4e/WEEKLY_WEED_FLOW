# LettaClient connection reuse. A single document workflow threads ONE
# LettaClient through 50-70 separate REST calls (pipeline.run_workflow does
# `client = client or LettaClient()` once and passes that same instance
# through ensure_fleet/spawn_ephemeral/send_message/... — see pipeline.py,
# fleet.py). _client() used to build a brand-new httpx.AsyncClient (fresh
# TCP+TLS connection) on every one of those calls; it must now hold one
# shared client and reuse it. Offline: httpx.AsyncClient itself is replaced
# with a counting fake, no real network involved.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import letta as letta_module  # noqa: E402
from app.letta import LettaClient  # noqa: E402

pytestmark = pytest.mark.asyncio


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = {} if json_data is None else json_data
        self.content = b"{}"
        self.text = "{}"

    def json(self):
        return self._json


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient: counts how many times IT (the class)
    is instantiated, and how many requests each instance actually serves."""

    instances_created = 0

    def __init__(self, *a, **k):
        _FakeAsyncClient.instances_created += 1
        self.is_closed = False
        self.calls: list[tuple[str, str]] = []

    async def request(self, method, path, **kw):
        if self.is_closed:
            raise RuntimeError("request on a closed client")
        self.calls.append((method, path))
        return _FakeResponse(200, {"ok": True})

    async def aclose(self):
        self.is_closed = True


@pytest.fixture(autouse=True)
def _fake_httpx_async_client(monkeypatch):
    _FakeAsyncClient.instances_created = 0
    monkeypatch.setattr(letta_module.httpx, "AsyncClient", _FakeAsyncClient)
    yield


async def test_one_client_instance_serves_many_req_calls():
    c = LettaClient(base="http://letta.example", key="test-key")
    for _ in range(5):
        out = await c._req("GET", "/agents/")
        assert out == {"ok": True}

    assert _FakeAsyncClient.instances_created == 1, (
        f"httpx.AsyncClient constructed {_FakeAsyncClient.instances_created} "
        "times across 5 _req calls -- expected exactly 1 (reused, not rebuilt)"
    )
    assert len(c._client_instance.calls) == 5


async def test_higher_level_methods_share_the_same_client():
    """Same guarantee through the public API a real workflow actually calls,
    not just the private _req plumbing."""
    c = LettaClient(base="http://letta.example", key="test-key")
    await c.list_agents()
    await c.list_tools()
    await c.list_models()
    await c.list_embedding_models()
    assert _FakeAsyncClient.instances_created == 1


async def test_aclose_closes_the_shared_client():
    c = LettaClient(base="http://letta.example", key="test-key")
    await c._req("GET", "/agents/")
    inst = c._client_instance
    assert inst.is_closed is False

    await c.aclose()
    assert inst.is_closed is True


async def test_client_reinitializes_lazily_after_close():
    """A closed client is not reused -- _client() must notice is_closed and
    build a fresh one rather than handing back a dead connection."""
    c = LettaClient(base="http://letta.example", key="test-key")
    await c._req("GET", "/agents/")
    await c.aclose()

    await c._req("GET", "/agents/")
    assert _FakeAsyncClient.instances_created == 2


async def test_aclose_on_a_never_used_client_is_a_noop():
    c = LettaClient(base="http://letta.example", key="test-key")
    await c.aclose()  # must not raise even though _client() was never called
    assert _FakeAsyncClient.instances_created == 0
