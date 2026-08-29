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
from app.letta import LettaClient, LettaError  # noqa: E402

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


# ── delete_agent's name guard (BUG 2) ───────────────────────────────────────
# delete_agent used to take a bare id and issue DELETE unconditionally, with
# no check that the id actually names an agent this client should be allowed
# to touch. It must now look the agent up first (GET) and refuse to delete
# anything outside the gf_* namespace create_agent's own _guard_gf enforces
# on the way in.
class _RoutedFakeAsyncClient:
    """Like _FakeAsyncClient, but GET /agents/{id} returns a caller-chosen
    agent record instead of the generic {"ok": True} — needed to drive
    delete_agent's name-lookup guard end to end."""

    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.calls: list[tuple[str, str]] = []
        self.is_closed = False

    async def request(self, method, path, **kw):
        self.calls.append((method, path))
        if method == "GET":
            return _FakeResponse(200, {"id": "tmp-1", "name": self.agent_name})
        return _FakeResponse(200, {"ok": True})

    async def aclose(self):
        self.is_closed = True


async def test_delete_agent_looks_up_the_name_then_deletes_a_gf_agent(monkeypatch):
    fake = _RoutedFakeAsyncClient("gf_reg_checker_tmp_abc123_10")
    monkeypatch.setattr(letta_module.httpx, "AsyncClient", lambda *a, **k: fake)
    c = LettaClient(base="http://letta.example", key="test-key")

    await c.delete_agent("tmp-1")

    assert fake.calls == [("GET", "/agents/tmp-1"), ("DELETE", "/agents/tmp-1")]


async def test_delete_agent_refuses_a_non_gf_named_agent(monkeypatch):
    fake = _RoutedFakeAsyncClient("some_unrelated_agent")
    monkeypatch.setattr(letta_module.httpx, "AsyncClient", lambda *a, **k: fake)
    c = LettaClient(base="http://letta.example", key="test-key")

    with pytest.raises(LettaError, match="non-gf_"):
        await c.delete_agent("tmp-1")

    # the guard must fire BEFORE any DELETE is issued
    assert ("DELETE", "/agents/tmp-1") not in fake.calls


class _RecordingClient:
    """Records method/path/kwargs and answers GET /agents/<id> with a name, so
    the gf_ namespace guard has something to check."""

    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.is_closed = False
        self.calls: list[tuple] = []

    async def request(self, method, path, **kw):
        self.calls.append((method, path, kw))
        if method == "GET":
            return _FakeResponse(200, {"name": self.agent_name})
        return _FakeResponse(200, {"ok": True})

    async def aclose(self):
        self.is_closed = True


async def test_reset_messages_sends_the_required_body():
    """The route is a PATCH with a REQUIRED body — calling it bare returns 422.
    Seen live against letta-6ou3 on all six one-shot agents at once: the
    non-fatal handler logged it, the autoclear flag landed, and the already
    accumulated buffers stayed exactly as full as before."""
    fake = _RecordingClient("gf_qa_auditor")
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    await c.reset_messages("agent-1")
    method, path, kwargs = fake.calls[-1]
    assert method == "PATCH"
    assert path.endswith("/reset-messages")
    assert kwargs["json"] == {"add_default_initial_messages": False}


async def test_reset_messages_refuses_a_non_gf_agent():
    """Same namespace guard as delete_agent: this throws conversation history
    away, so it must never reach an agent this client does not own."""
    fake = _RecordingClient("wwf_weekly_report")
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    with pytest.raises(LettaError, match="refusing to touch non-gf_"):
        await c.reset_messages("agent-1")
    assert not [c for c in fake.calls if c[0] == "PATCH"]


async def test_get_block_returns_none_only_for_a_genuine_404():
    """fleet._reconcile_blocks CREATES and attaches a block when this returns
    None, so a transient 5xx must not be reported as "absent" — it would
    manufacture a duplicate label on a live agent."""
    class _Status(_RecordingClient):
        def __init__(self, code):
            super().__init__("gf_x"); self.code = code

        async def request(self, method, path, **kw):
            self.calls.append((method, path, kw))
            return _FakeResponse(self.code, {})

    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = _Status(404)
    assert await c.get_block("agent-1", "persona") is None

    for code in (500, 502, 401):
        c = LettaClient(base="http://letta.invalid", key="k")
        c._client_instance = _Status(code)
        with pytest.raises(LettaError) as ei:
            await c.get_block("agent-1", "persona")
        assert ei.value.status == code
