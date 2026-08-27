"""Shared DocEngine upstream client.

The GrowFlow DocEngine (docengine/) is an internal-only container: the WWF
backend is its sole caller and injects the `X-API-Key` server-side (the key
never reaches the browser). Both the QMS Studio proxy (app/api/qms.py) and the
certificate pipeline (app/api/qc/coq_docx.py + coq_aggregation.py — COQ
generation) talk to it, so the client
+ the "surface the upstream's own detail, mask 5xx as 503" behaviour live here
once. `client_factory` is the seam tests monkeypatch to stand in a fake client.
"""
import httpx
from fastapi import HTTPException

from app.config import settings

DE_UNAVAILABLE = "DocEngine unavailable"


def de_client(timeout: float = 20.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.docengine_url,
        headers={"X-API-Key": settings.docengine_api_key},
        timeout=httpx.Timeout(timeout),
    )


def _assert_forwardable(path: str) -> None:
    """Reject a forwarded path that could escape DocEngine's intended surface.

    Every caller builds `path` by interpolating a caller-supplied id or key into
    a fixed template — `/documents/{did}`, `/workflows/{jid}`,
    `/questionnaires/{key}`. Those segments come straight off the URL, and `..`
    is a single path segment, so it satisfies FastAPI's `[^/]+` route matching
    and arrives here intact; httpx's RFC-3986 join then collapses the dot
    segments and the request lands on an internal endpoint the explicit route
    surface exists to bound. `//` is worse: a network-path reference re-points
    the request at another host entirely, past `base_url`.

    This is the same predicate api/qms.py already applies per-route in
    document() and download(). Putting it at the shared choke point means all
    five studio routes and both certificate-pipeline callers inherit it —
    and so does anything added later, which per-route copies would not."""
    if (not path.startswith("/") or "//" in path or "\\" in path
            or ".." in path.split("/")):
        raise HTTPException(status_code=400, detail="Invalid DocEngine path")


async def de_forward(method: str, path: str, json_body: dict | None = None,
                     timeout: float = 20.0, client_factory=None) -> httpx.Response:
    """Forward to DocEngine. 503 when unconfigured or the upstream is down/5xx;
    a 4xx (e.g. a pp_verify FAIL 422) is surfaced verbatim with its own detail
    so the author sees the verify report — never masked, never shipped."""
    _assert_forwardable(path)
    if not settings.docengine_api_key:
        raise HTTPException(status_code=503, detail=DE_UNAVAILABLE)
    factory = client_factory or de_client
    try:
        async with factory(timeout) as c:
            r = await c.request(method, path, json=json_body)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail=DE_UNAVAILABLE)
    if r.status_code >= 500:
        raise HTTPException(status_code=503, detail=DE_UNAVAILABLE)
    if r.status_code >= 400:
        detail = "DocEngine request failed"
        try:
            detail = r.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=r.status_code, detail=detail)
    return r
