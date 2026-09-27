"""QMS Studio DocEngine façade (app/api/qms.py). Pins: the role gates (base
USER 403, authoring limited to QA/QP/admin), the unconfigured-key 503 (the
local/dev/e2e degradation state), forwarding with the API key injected
server-side, download header passthrough, and traversal guards on ids.

The Phase-1 qms-api proxy this file used to cover was removed with the
retired qms-api service (review 2026-09-27, BC-19); its seven /qms/ routes
must stay gone — see test_legacy_qms_api_proxy_routes_are_gone.
"""
import httpx
import pytest
from fastapi import HTTPException

from app.api import qms as qms_mod
from app.config import settings
from app.docengine import _assert_forwardable
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


# ════════════════════ QMS Studio — DocEngine surface ════════════════════

class _FakeDEClient(_FakeClient):
    """Records every forwarded call in full — (method, path) for the
    existing assertions, plus the JSON body and the headers the proxy
    actually sent, so the org header and the server-stamped identity can be
    pinned per route (review 2026-09-27, DI2-04 / DI2-13)."""
    calls: list = []

    async def request(self, method, path, json=None, headers=None, params=None, **kw):
        self.requests.append((method, path))
        _FakeDEClient.calls.append({"method": method, "path": path, "json": json,
                                    "headers": dict(headers or {}), "params": params})
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.fixture
def de_configured(monkeypatch):
    monkeypatch.setattr(settings, "docengine_api_key", "test-de-key")
    yield


def _stub_de(monkeypatch, response):
    _FakeDEClient.calls = []
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


async def test_studio_presets_read_gate(client, admin_headers, de_configured, monkeypatch):
    """Presets are read-only listings — the same elevated gate as the rest of
    the registry, not the narrower authoring gate /revise itself carries."""
    _stub_de(monkeypatch, _FakeResponse(json_data={"presets": [{"key": "tighten"}]}))
    _, uh = await _actor(client, admin_headers, role="USER")
    assert (await client.get("/qms/studio/presets", headers=uh)).status_code == 403
    _, mh = await _actor(client, admin_headers, role="QC_MGR")
    r = await client.get("/qms/studio/presets", headers=mh)
    assert r.status_code == 200 and r.json()["presets"][0]["key"] == "tighten"


async def test_studio_chat_authoring_gate_and_forward(client, admin_headers, de_configured, monkeypatch):
    _stub_de(monkeypatch, _FakeResponse(json_data={"answer": "Section 2 covers internal QC."}))
    _, mh = await _actor(client, admin_headers, role="QC_MGR")
    r = await client.post("/qms/studio/workflows/j1/chat", json={"question": "what?"}, headers=mh)
    assert r.status_code == 403
    _, qah = await _actor(client, admin_headers, role="QA_MGR")
    r = await client.post("/qms/studio/workflows/j1/chat", json={"question": "what?"}, headers=qah)
    assert r.status_code == 200 and r.json()["answer"].startswith("Section 2")
    assert ("POST", "/workflows/j1/chat") in _FakeDEClient.last.requests


async def test_studio_revise_authoring_gate_and_stamps_requested_by(client, admin_headers, de_configured, monkeypatch):
    """Same authoring gate as /studio/workflows — a direct edit is document
    authoring — and requested_by is stamped from the JWT, never trusted from
    the request body, for the same reason the original workflow POST does."""
    _stub_de(monkeypatch, _FakeResponse(json_data={"job_id": "rev-1", "status": "queued"}))
    _, mh = await _actor(client, admin_headers, role="QC_MGR")
    assert (await client.post("/qms/studio/workflows/j1/revise",
                              json={"preset_key": "tighten"}, headers=mh)).status_code == 403
    _, qah = await _actor(client, admin_headers, role="QA_MGR")
    r = await client.post("/qms/studio/workflows/j1/revise",
                          json={"preset_key": "tighten", "requested_by": "someone-else"},
                          headers=qah)
    assert r.status_code == 200 and r.json()["job_id"] == "rev-1"
    assert ("POST", "/workflows/j1/revise") in _FakeDEClient.last.requests


@pytest.mark.parametrize("path,body", [
    ("/qms/studio/workflows/%2e%2e/chat", {"question": "x"}),
    ("/qms/studio/workflows/a%5Cb/revise", {"preset_key": "tighten"}),
])
async def test_studio_chat_and_revise_reject_traversal_in_id(client, admin_headers, de_configured,
                                                              monkeypatch, path, body):
    """The same H1 guard the GET-based studio routes carry (see
    test_studio_rejects_traversal_in_id) — jid is interpolated into the
    forwarded path here too."""
    _stub_de(monkeypatch, _FakeResponse(json_data={"ok": True}))
    _FakeDEClient.last = None
    r = await client.post(path, json=body, headers=admin_headers)
    assert r.status_code == 400, (path, r.text)
    assert r.json()["detail"] == "Invalid DocEngine path"
    assert _FakeDEClient.last is None or _FakeDEClient.last.requests == []


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


async def test_studio_build_stamps_requested_by_and_writes_the_feed(client, admin_headers, org,
                                                                   de_configured, monkeypatch):
    """Review 2026-09-27, DI2-04. /studio/build forwarded the browser's
    `requested_by` unchanged, so a Studio direct build was registered as
    whoever the client claimed (usually nobody), and no event recorded that a
    controlled document had been built. The identity now comes from the JWT
    like /studio/workflows and /revise, and the registered document lands in
    the audited event feed as `studio_build` naming the same person."""
    _stub_de(monkeypatch, _FakeResponse(json_data={
        "ok": True, "document_id": "d-42", "bytes": 10, "verify": "RESULT: PASS",
        "audited": False,
        "registered": {"code": "QCSOP-999", "version": "1.0", "doctype": "SOP",
                       "title_mk": "а", "title_en": "Test SOP", "created_by": "ignored"}}))
    qa, qah = await _actor(client, admin_headers, role="QA_MGR")
    r = await client.post("/qms/studio/build",
                          json={"markdown": "<!--HEADERDATA\n-->\n# x|y\nтело|body",
                                "requested_by": "qp.someone-else"},
                          headers=qah)
    assert r.status_code == 200, r.text
    sent = [c for c in _FakeDEClient.calls if c["path"] == "/build"]
    assert len(sent) == 1
    assert sent[0]["json"]["requested_by"] == qa["username"], "the browser's claim must be overwritten"
    assert sent[0]["headers"]["X-Org-Id"] == org["org_id"]
    feed = (await client.get("/activity", headers=admin_headers)).json()
    ev = next((e for e in feed if e["verb"] == "studio_build"), None)
    assert ev is not None, feed
    assert ev["params"]["document_id"] == "d-42" and ev["params"]["code"] == "QCSOP-999"
    assert ev["params"]["audited"] is False
    assert str(ev["actor_id"]) == qa["id"]


_STUDIO_ROUTES = [
    ("get", "/qms/studio/questionnaires", None),
    ("get", "/qms/studio/questionnaires/sop_qc", None),
    ("post", "/qms/studio/workflows", {"questionnaire": "sop_qc", "answers": {}, "meta": {}}),
    ("get", "/qms/studio/workflows/j1", None),
    ("get", "/qms/studio/presets", None),
    ("post", "/qms/studio/workflows/j1/chat", {"question": "what?"}),
    ("post", "/qms/studio/workflows/j1/revise", {"preset_key": "tighten"}),
    ("post", "/qms/studio/build", {"markdown": "<!--HEADERDATA\n-->\n# x|y\nтело|body"}),
    ("get", "/qms/studio/documents", None),
    ("get", "/qms/studio/documents/abc", None),
    ("get", "/qms/studio/documents/abc/download", None),
    ("get", "/qms/studio/documents/abc/pdf", None),
]


@pytest.mark.parametrize("method,path,body", _STUDIO_ROUTES)
async def test_every_studio_route_sends_the_callers_organisation(client, admin_headers, org,
                                                                 de_configured, monkeypatch,
                                                                 method, path, body):
    """Review 2026-09-27, DI2-13. DocEngine scopes every read and write by
    X-Org-Id and answers 400 without it; dropping `org_id=user["org_id"]`
    from one qms.py route passed this suite and would 400 in production.
    Pinned on the fake client's captured headers, route by route."""
    _stub_de(monkeypatch, _FakeResponse(json_data={"job_id": "j1", "document_id": "d1",
                                                   "documents": [], "answer": "x"},
                                        headers={"content-type": "application/octet-stream"}))
    r = await getattr(client, method)(path, json=body, headers=admin_headers) if body is not None \
        else await getattr(client, method)(path, headers=admin_headers)
    assert r.status_code == 200, (path, r.text)
    assert _FakeDEClient.calls, path
    for call in _FakeDEClient.calls:
        assert call["headers"].get("X-Org-Id") == org["org_id"], (path, call)


def test_every_de_forward_call_site_passes_the_organisation():
    """Static companion: every `_de_forward(` / `_de_stream(` call in qms.py
    carries an org argument, so a new route cannot forget it silently."""
    import re
    from pathlib import Path
    src = (Path(qms_mod.__file__)).read_text()
    calls = re.findall(r"await _de_forward\((?:[^()]|\([^()]*\))*\)", src)
    assert len(calls) >= 10, f"only {len(calls)} call sites found — the regex is broken"
    for c in calls:
        assert "org_id=" in c, c
    streams = re.findall(r"_de_stream\([^)]*\)", src)
    assert all("org_id" in c or 'user["org_id"]' in c for c in streams), streams


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


# ──────────────────── H1: forwarded-path traversal guard ────────────────────
# The five studio routes below interpolate a caller-supplied segment into the
# forwarded path with only a length cap. `..` is a single path segment, so it
# satisfies FastAPI's `[^/]+` matching and arrives intact — and httpx's
# RFC-3986 join then collapses the dot segments, landing the request on an
# internal DocEngine endpoint the explicit route surface exists to bound. The
# guard lives at the shared choke point (app/docengine.de_forward) so all five
# inherit it, rather than five copies of the per-route predicate api/qms.py
# already carries in document() and download().

_STUDIO_ID_ROUTES = [
    "/qms/studio/questionnaires/{}",
    "/qms/studio/workflows/{}",
    "/qms/studio/documents/{}",
    "/qms/studio/documents/{}/download",
    "/qms/studio/documents/{}/pdf",
]

# `%2e%2e` rather than a literal `..`: httpx (the test client) applies dot-segment
# removal to the request URL itself, so a literal `..` never leaves the client.
# Percent-encoded, it survives to the ASGI layer, which unquotes it back to `..`
# — exactly the shape a non-normalizing HTTP client sends.
@pytest.mark.parametrize("route", _STUDIO_ID_ROUTES)
@pytest.mark.parametrize("payload", ["%2e%2e", "a%5Cb", "%5C%5Cevil.example"])
async def test_studio_rejects_traversal_in_id(client, admin_headers, de_configured,
                                              monkeypatch, route, payload):
    _stub_de(monkeypatch, _FakeResponse(json_data={"ok": True}))
    _FakeDEClient.last = None
    r = await client.get(route.format(payload), headers=admin_headers)
    assert r.status_code == 400, (route, payload, r.text)
    assert r.json()["detail"] == "Invalid DocEngine path"
    # rejected before the upstream is contacted at all
    assert _FakeDEClient.last is None or _FakeDEClient.last.requests == []


_GOOD_DE_PATHS = ["/documents", "/documents/abc", "/documents/abc/download",
                  "/documents/abc/pdf", "/questionnaires/sop_qc", "/build",
                  "/workflows", "/workflows/j1"]

# Includes shapes no route can produce today but a future caller could: a
# relative path (httpx would resolve it against base_url's directory) and a
# `//` network-path reference, which re-points the request at another host
# entirely, past base_url.
_BAD_DE_PATHS = ["/documents/..", "/..", "/../etc", "documents/abc",
                 "//evil.example/x", "/documents//abc", "/documents/a\\b",
                 "/documents/..%2f/x".replace("%2f", "/")]


@pytest.mark.parametrize("path", _GOOD_DE_PATHS)
def test_forwardable_allows_real_paths(path):
    _assert_forwardable(path)              # must not raise


@pytest.mark.parametrize("path", _BAD_DE_PATHS)
def test_forwardable_rejects_escapes(path):
    with pytest.raises(HTTPException) as ei:
        _assert_forwardable(path)
    assert ei.value.status_code == 400
    assert ei.value.detail == "Invalid DocEngine path"


def test_build_path_of_certificate_pipeline_is_forwardable():
    """The two QC callers (coq_aggregation, coq_docx) forward a fixed '/build'.
    Pinned so the guard can never regress the certificate pipeline."""
    _assert_forwardable("/build")


def test_legacy_qms_api_proxy_routes_are_gone():
    """qms-api is retired platform-wide and nothing in web/gf called its
    proxy any more; the routes were an authenticated door onto an upstream
    that no longer exists, kept alive for no reader (review 2026-09-27,
    BC-19). The DocEngine registry (/qms/studio/documents) is the successor.
    Pinned by path so a copy-paste revival is a red test, not a silent one."""
    from app.main import app
    from tests.conftest import iter_routes
    live = {getattr(r, "path", "") for r in iter_routes(app)}
    for gone in ("/qms/documents", "/qms/stats", "/qms/hierarchy", "/qms/families",
                 "/qms/documents/{code}", "/qms/rag-query", "/qms/download/{path:path}",
                 "/tasks/tree"):
        assert gone not in live, f"{gone} is a retired route"
    # the successor surface is still there
    assert "/qms/studio/documents" in live
    # and the settings the proxy read are gone with it (BC-19 also names them)
    from app.config import Settings
    for field in ("qms_api_url", "qms_api_key", "letta_mcp_url", "qdrant_url",
                  "remember_device_expire_days"):
        assert field not in Settings.model_fields, f"dead setting {field} still declared"
