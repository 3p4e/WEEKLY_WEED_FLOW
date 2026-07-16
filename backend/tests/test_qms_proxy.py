"""QMS Studio federation proxy (app/api/qms.py) — Phase 1 of the GrowFlow
unification. Pins: the role gate (base USER 403), the unconfigured-key 503
(the local/dev/e2e degradation state), upstream-down → 503 with the exact
detail string the frontend keys on, forwarding with the X-API-Key injected
server-side, and download header passthrough.
"""
import httpx
import pytest

from app.api import qms as qms_mod
from app.config import settings
from tests.conftest import create_user, login_and_set_password


async def _actor(client, admin_headers, role="USER"):
    u, otp = await create_user(client, admin_headers, role=role)
    token = await login_and_set_password(client, u["username"], otp)
    return u, {"Authorization": f"Bearer {token}"}


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._json


class _FakeClient:
    """Stands in for httpx.AsyncClient; records the constructed headers so
    the key-injection assertion can see them."""
    last = None

    def __init__(self, response):
        self._response = response
        self.requests = []
        _FakeClient.last = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, path, params=None, **kw):
        self.requests.append(("GET", path))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def post(self, path, json=None, **kw):
        self.requests.append(("POST", path))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.fixture
def qms_configured(monkeypatch):
    monkeypatch.setattr(settings, "qms_api_key", "test-qms-key")
    yield


def _stub_client(monkeypatch, response):
    monkeypatch.setattr(qms_mod, "_client", lambda: _FakeClient(response))


async def test_base_user_gets_403(client, admin_headers, qms_configured):
    _, uh = await _actor(client, admin_headers)
    assert (await client.get("/qms/stats", headers=uh)).status_code == 403


async def test_unconfigured_key_degrades_to_503(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "qms_api_key", "")
    r = await client.get("/qms/stats", headers=admin_headers)
    assert r.status_code == 503
    assert r.json()["detail"] == "QMS service unavailable"


async def test_upstream_down_is_a_friendly_503(client, admin_headers, qms_configured, monkeypatch):
    _stub_client(monkeypatch, httpx.ConnectError("refused"))
    r = await client.get("/qms/documents", headers=admin_headers)
    assert r.status_code == 503
    assert r.json()["detail"] == "QMS service unavailable"


async def test_forwarding_returns_upstream_payload(client, admin_headers, qms_configured, monkeypatch):
    _stub_client(monkeypatch, _FakeResponse(json_data={"documents": [{"code": "QA_00.02"}]}))
    r = await client.get("/qms/documents", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["documents"][0]["code"] == "QA_00.02"
    assert _FakeClient.last.requests == [("GET", "/api/documents")]


async def test_real_client_injects_api_key(qms_configured):
    # the un-stubbed factory must carry the server-side key header
    c = qms_mod._client()
    try:
        assert c.headers["X-API-Key"] == "test-qms-key"
        assert str(c.base_url).startswith(settings.qms_api_url)
    finally:
        await c.aclose()


async def test_rag_query_forwards_and_caps_size(client, admin_headers, qms_configured, monkeypatch):
    _stub_client(monkeypatch, _FakeResponse(json_data={"db1_results": [], "db2_results": []}))
    r = await client.post("/qms/rag-query", json={"query": "cleaning validation"},
                          headers=admin_headers)
    assert r.status_code == 200
    assert ("POST", "/api/rag-query") in _FakeClient.last.requests
    big = {"query": "x" * 9000}
    assert (await client.post("/qms/rag-query", json=big,
                              headers=admin_headers)).status_code == 422


async def test_download_passes_through_content_headers(client, admin_headers, qms_configured, monkeypatch):
    _stub_client(monkeypatch, _FakeResponse(
        content=b"PK\x03\x04fake-docx",
        headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 "content-disposition": 'attachment; filename="QA_00.02.docx"'}))
    r = await client.get("/qms/download/generated_sops/QA_00.02.docx", headers=admin_headers)
    assert r.status_code == 200
    assert r.content.startswith(b"PK")
    assert "wordprocessingml" in r.headers["content-type"]
    assert "QA_00.02.docx" in r.headers["content-disposition"]


async def test_upstream_4xx_is_not_masked_as_503(client, admin_headers, qms_configured, monkeypatch):
    _stub_client(monkeypatch, _FakeResponse(status_code=404))
    r = await client.get("/qms/documents/NOPE_00.00", headers=admin_headers)
    assert r.status_code == 404


# ════════════════════ QMS Studio — DocEngine surface ════════════════════

class _FakeDEClient(_FakeClient):
    async def request(self, method, path, json=None, **kw):
        self.requests.append((method, path))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.fixture
def de_configured(monkeypatch):
    monkeypatch.setattr(settings, "docengine_api_key", "test-de-key")
    yield


def _stub_de(monkeypatch, response):
    monkeypatch.setattr(qms_mod, "_de_client",
                        lambda timeout=20.0: _FakeDEClient(response))


async def test_studio_base_user_403_and_manager_read_ok(client, admin_headers, de_configured, monkeypatch):
    _stub_de(monkeypatch, _FakeResponse(json_data={"questionnaires": []}))
    _, uh = await _actor(client, admin_headers, role="USER")
    assert (await client.get("/qms/studio/questionnaires", headers=uh)).status_code == 403
    _, mh = await _actor(client, admin_headers, role="QC_MGR")
    assert (await client.get("/qms/studio/questionnaires", headers=mh)).status_code == 200


async def test_studio_authoring_gate(client, admin_headers, de_configured, monkeypatch):
    """Workflows/build are QA/QP/OWNER/ADMIN only — a dept manager can read
    the registry but cannot author controlled documents."""
    _stub_de(monkeypatch, _FakeResponse(json_data={"job_id": "j1", "status": "queued"}))
    body = {"questionnaire": "sop_qc", "answers": {},
            "meta": {"title_mk": "а", "title_en": "a", "code": "X-1"}}
    _, mh = await _actor(client, admin_headers, role="QC_MGR")
    assert (await client.post("/qms/studio/workflows", json=body,
                              headers=mh)).status_code == 403
    _, qah = await _actor(client, admin_headers, role="QA_MGR")
    r = await client.post("/qms/studio/workflows", json=body, headers=qah)
    assert r.status_code == 200 and r.json()["job_id"] == "j1"
    # requested_by is stamped server-side from the JWT identity
    assert ("POST", "/workflows") in _FakeDEClient.last.requests


async def test_studio_unconfigured_degrades_503(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "docengine_api_key", "")
    r = await client.get("/qms/studio/documents", headers=admin_headers)
    assert r.status_code == 503
    assert r.json()["detail"] == "DocEngine unavailable"


async def test_studio_verify_fail_detail_surfaces(client, admin_headers, de_configured, monkeypatch):
    """A pp_verify FAIL must reach the author as 422 with the report —
    never masked, never a shipped document."""
    _stub_de(monkeypatch, _FakeResponse(
        status_code=422,
        json_data={"detail": {"verify": "RESULT: FAIL", "error": "verify FAILED"}}))
    r = await client.post("/qms/studio/build",
                          json={"markdown": "<!--HEADERDATA\n-->\n# x|y\nтело|body"},
                          headers=admin_headers)
    assert r.status_code == 422
    assert r.json()["detail"]["verify"] == "RESULT: FAIL"


async def test_studio_download_streams(client, admin_headers, de_configured, monkeypatch):
    _stub_de(monkeypatch, _FakeResponse(
        content=b"PK\x03\x04de-docx",
        headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 "content-disposition": 'attachment; filename="QCSOP-999.docx"'}))
    r = await client.get("/qms/studio/documents/abc/download", headers=admin_headers)
    assert r.status_code == 200 and r.content.startswith(b"PK")
    assert "QCSOP-999.docx" in r.headers["content-disposition"]


async def test_studio_real_client_injects_key(de_configured):
    c = qms_mod._de_client()
    try:
        assert c.headers["X-API-Key"] == "test-de-key"
        assert str(c.base_url).startswith(settings.docengine_url)
    finally:
        await c.aclose()
