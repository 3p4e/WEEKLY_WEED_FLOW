"""app/docengine.py — the shared DocEngine client, offline.

Two answers that used to be one (review 2026-09-27, DI-12): a DocEngine that
is DOWN (503 "unavailable") and a DocEngine that is still WORKING past the
proxy's budget (504 "still answering"). The Studio chat cut a real Letta turn
at 150 s and reported the outage message, while DocEngine finished the answer
and threw it away. Also pinned here: the organisation scope header (DI-13)
and query parameters (registry paging, DI-21) reach the upstream request.
"""
import httpx
import pytest
from fastapi import HTTPException

from app import docengine
from app.config import settings

pytestmark = pytest.mark.asyncio


class _Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}
        self.content = b"{}"
        self.headers = {}

    def json(self):
        return self._body


class _FakeClient:
    """Stands in for httpx.AsyncClient: records the request, answers with
    `outcome` (a response, or an exception to raise)."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def request(self, method, path, json=None, headers=None, params=None):
        self.requests.append({"method": method, "path": path, "json": json,
                              "headers": headers, "params": params})
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "docengine_api_key", "test-de-key")
    yield


async def test_a_timeout_is_504_still_answering_not_503_unavailable():
    fake = _FakeClient(httpx.ReadTimeout("read timed out"))
    with pytest.raises(HTTPException) as ei:
        await docengine.de_forward("POST", "/workflows/x/chat", {"question": "q"},
                                   timeout=150.0, client_factory=lambda t: fake)
    assert ei.value.status_code == 504
    assert docengine.DE_TIMED_OUT in ei.value.detail
    assert "150s" in ei.value.detail
    assert docengine.DE_UNAVAILABLE not in ei.value.detail


async def test_a_connect_failure_is_still_503_unavailable():
    fake = _FakeClient(httpx.ConnectError("refused"))
    with pytest.raises(HTTPException) as ei:
        await docengine.de_forward("GET", "/documents", client_factory=lambda t: fake)
    assert ei.value.status_code == 503
    assert ei.value.detail == docengine.DE_UNAVAILABLE


async def test_the_chat_budget_fits_under_the_frontend_proxy_cut():
    """web/nginx.conf gives the request 180 s; the backend must answer first
    or the browser sees a generic failure instead of the 504 above."""
    assert 120.0 < docengine.DE_CHAT_TIMEOUT_S < 180.0


async def test_org_id_travels_as_the_scope_header_and_params_as_query():
    fake = _FakeClient(_Response(200, {"documents": []}))
    r = await docengine.de_forward("GET", "/documents", client_factory=lambda t: fake,
                                   org_id="11111111-1111-1111-1111-111111111111",
                                   params={"limit": 50, "offset": 100})
    assert r.status_code == 200
    req = fake.requests[0]
    assert req["headers"] == {"X-Org-Id": "11111111-1111-1111-1111-111111111111"}
    assert req["params"] == {"limit": 50, "offset": 100}


async def test_without_an_org_no_scope_header_is_invented():
    """DocEngine refuses an unscoped request (400); the client must not
    fabricate a scope to get past that."""
    fake = _FakeClient(_Response(200, {}))
    await docengine.de_forward("GET", "/questionnaires", client_factory=lambda t: fake)
    assert fake.requests[0]["headers"] is None
