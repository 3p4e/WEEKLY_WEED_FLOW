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


# ── Paged listings (DI-19) ──────────────────────────────────────────────────
class _PagedClient(_RecordingClient):
    """Serves /agents/ in pages keyed on the `after` cursor, the way Letta's
    v1 listing does. `total` rows, ids a-0 .. a-(total-1)."""

    def __init__(self, total):
        super().__init__("gf_x")
        self.rows = [{"id": f"a-{i}", "name": f"gf_agent_{i}"} for i in range(total)]

    async def request(self, method, path, **kw):
        self.calls.append((method, path, kw))
        params = kw.get("params") or {}
        limit = int(params.get("limit", 20))
        start = 0
        if params.get("after"):
            start = next(i for i, r in enumerate(self.rows) if r["id"] == params["after"]) + 1
        page = self.rows[start:start + limit]
        resp = _FakeResponse(200, page)
        resp.content = b"[]"
        return resp


async def test_list_agents_follows_the_after_cursor_until_a_short_page():
    """A declared agent on page 2 must be SEEN, or ensure_fleet re-creates it
    on every job. 250 rows -> three requests (100, 100, 50), all returned."""
    fake = _PagedClient(250)
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    rows = await c.list_agents()
    assert [r["id"] for r in rows] == [f"a-{i}" for i in range(250)]
    gets = [call for call in fake.calls if call[1] == "/agents/"]
    assert len(gets) == 3
    assert gets[0][2]["params"] == {"limit": 100}
    assert gets[1][2]["params"] == {"limit": 100, "after": "a-99"}
    assert gets[2][2]["params"] == {"limit": 100, "after": "a-199"}


async def test_list_agents_stops_after_one_full_page_that_ends_the_set():
    """Exactly one page of rows: the second request answers empty and the
    loop stops there — no infinite paging on a boundary-sized tenant."""
    fake = _PagedClient(100)
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    rows = await c.list_agents()
    assert len(rows) == 100
    assert len([call for call in fake.calls if call[1] == "/agents/"]) == 2


async def test_list_agents_passes_the_name_filter_through_every_page():
    fake = _PagedClient(3)
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    await c.list_agents(name="gf_reg_checker")
    assert fake.calls[0][2]["params"] == {"name": "gf_reg_checker", "limit": 100}


# ── Transient retry on send_message (DI-18) ─────────────────────────────────
class _FlakyClient(_RecordingClient):
    """First POST answers with `first` (a status code or an exception class),
    every later request succeeds with a one-message assistant reply."""

    def __init__(self, first):
        super().__init__("gf_x")
        self.first = first
        self.posts = 0

    async def request(self, method, path, **kw):
        self.calls.append((method, path, kw))
        if method == "POST":
            self.posts += 1
            if self.posts == 1:
                if isinstance(self.first, int):
                    r = _FakeResponse(self.first, {})
                    r.text = "upstream unavailable"
                    return r
                raise self.first("boom")
        r = _FakeResponse(200, {"messages": [
            {"message_type": "assistant_message", "content": "Draft text."}]})
        r.content = b"{}"
        return r


@pytest.fixture
def _no_retry_delay(monkeypatch):
    monkeypatch.setattr(letta_module, "_RETRY_DELAY_S", 0)


@pytest.mark.parametrize("first", [502, 503, 504])
async def test_send_message_retries_once_on_a_gateway_error(first, _no_retry_delay):
    """One 502 from LiteLLM used to throw away a 20-40 call job on the last
    section. The message is sent again once, and the job carries on."""
    fake = _FlakyClient(first)
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    assert await c.send_message("agent-1", "Draft section 8.") == "Draft text."
    assert fake.posts == 2


async def test_send_message_retries_once_on_a_connect_error(_no_retry_delay):
    fake = _FlakyClient(letta_module.httpx.ConnectError)
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    assert await c.send_message("agent-1", "Draft section 8.") == "Draft text."
    assert fake.posts == 2


async def test_send_message_gives_up_after_the_single_retry(_no_retry_delay):
    class _AlwaysDown(_RecordingClient):
        async def request(self, method, path, **kw):
            self.calls.append((method, path, kw))
            r = _FakeResponse(503, {})
            r.text = "down"
            return r
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = _AlwaysDown("gf_x")
    with pytest.raises(LettaError) as ei:
        await c.send_message("agent-1", "x")
    assert ei.value.status == 503
    assert len(c._client_instance.calls) == 2


async def test_send_message_does_not_retry_a_read_timeout(_no_retry_delay):
    """The request was delivered and the model may be mid-turn; a second copy
    would double the wait and the spend. A ReadTimeout propagates as is."""
    fake = _FlakyClient(letta_module.httpx.ReadTimeout)
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    with pytest.raises(letta_module.httpx.ReadTimeout):
        await c.send_message("agent-1", "x")
    assert fake.posts == 1


async def test_a_4xx_on_send_message_is_not_retried(_no_retry_delay):
    fake = _FlakyClient(422)
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = fake
    with pytest.raises(LettaError):
        await c.send_message("agent-1", "x")
    assert fake.posts == 1


async def test_listings_and_config_writes_are_never_retried(_no_retry_delay):
    """Only the one-shot message send opts in; a listing 503 is an error."""
    class _Once(_RecordingClient):
        async def request(self, method, path, **kw):
            self.calls.append((method, path, kw))
            r = _FakeResponse(503, {})
            r.text = "down"
            return r
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = _Once("gf_x")
    with pytest.raises(LettaError):
        await c.list_tools()
    assert len(c._client_instance.calls) == 1


async def test_send_message_full_keeps_the_tool_traffic_of_the_turn():
    """DI-14 provenance: which retrievals fed the text. Tool calls and returns
    are reduced to name/arguments/return; nothing from the sandbox env."""
    class _WithTools(_RecordingClient):
        async def request(self, method, path, **kw):
            self.calls.append((method, path, kw))
            r = _FakeResponse(200, {"messages": [
                {"message_type": "tool_call_message",
                 "tool_call": {"tool_call_id": "tc-1", "name": "ragflow_search",
                               "arguments": '{"question": "LOD limit", "datasets": "DB3"}'}},
                {"message_type": "tool_return_message", "tool_call_id": "tc-1",
                 "name": "ragflow_search", "status": "success",
                 "tool_return": '{"ok": true, "hits": [{"document": "QCSOP_004.docx"}]}'},
                {"message_type": "assistant_message", "content": "Body."},
            ]})
            r.content = b"{}"
            return r
    c = LettaClient(base="http://letta.invalid", key="k")
    c._client_instance = _WithTools("gf_x")
    full = await c.send_message_full("agent-1", "Draft.")
    assert full["text"] == "Body."
    assert full["tool_calls"] == [{"id": "tc-1", "name": "ragflow_search",
                                   "arguments": '{"question": "LOD limit", "datasets": "DB3"}'}]
    assert full["tool_returns"][0]["name"] == "ragflow_search"
    assert "QCSOP_004.docx" in full["tool_returns"][0]["return"]
