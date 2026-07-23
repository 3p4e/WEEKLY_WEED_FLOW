"""QMS Studio federation proxy — Phase 1 of the GrowFlow unification.

The QMS Creator (imported at qms-creator/) runs as an INTERNAL container
(`qms-api`, never published) whose only client is this router: GrowFlow JWT
auth and role gates are enforced here, then the request is forwarded with
the qms-api X-API-Key injected server-side. The key never reaches a browser,
and no auth code had to be added to the QMS codebase — this is the strangler
façade from docs/UNIFICATION-ANALYSIS-2026-07.md §7 Phase 1.

Scope is deliberately read + search only (registry, stats, hierarchy,
knowledge search, file download). Generation endpoints arrive with the
QMS Studio wizard in Phase 3, on the platform's own data model.

Governance note (docs/SCOPE.md): this router serves the QMS *Studio* zone —
the document-authoring side. Nothing here writes into the ops zone; the two
zones reference each other only by pointer (SOP code).
"""
import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response

from app import docengine
from app.config import settings
from app.deps import require_password_set

router = APIRouter(prefix="/qms", tags=["qms"])

_UNAVAILABLE = "QMS service unavailable"
# The frontend keys on this exact detail string for its graceful state.

# (local path suffix) -> upstream path on qms-api. An explicit allowlist —
# never a catch-all — so qms-api's unauthenticated surface (workflow, file
# listing, enhance-text, …) is NOT reachable through the platform until the
# corresponding feature ships with proper role design.
_GET_MAP = {
    "documents": "/api/documents",
    "stats": "/api/stats",
    "hierarchy": "/api/hierarchy",
    "families": "/api/document-families",
}


def _require_elevated(user: dict = Depends(require_password_set)) -> dict:
    # Same read gate as /facility and /reports/analytics: every role above
    # base USER (executives, QP, department managers).
    if user["role"] == "USER":
        raise HTTPException(status_code=403, detail="Managers and executives only")
    return user


def _client() -> httpx.AsyncClient:
    """One place builds the upstream client so tests can monkeypatch it."""
    return httpx.AsyncClient(
        base_url=settings.qms_api_url,
        headers={"X-API-Key": settings.qms_api_key},
        timeout=httpx.Timeout(15.0),
    )


async def _forward_get(path: str, params: dict | None = None):
    if not settings.qms_api_key:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    try:
        async with _client() as c:
            r = await c.get(path, params=params)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    if r.status_code >= 500:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail="QMS request failed")
    return r


@router.get("/documents")
async def documents(user: dict = Depends(_require_elevated)):
    return (await _forward_get(_GET_MAP["documents"])).json()


@router.get("/stats")
async def stats(user: dict = Depends(_require_elevated)):
    return (await _forward_get(_GET_MAP["stats"])).json()


@router.get("/hierarchy")
async def hierarchy(user: dict = Depends(_require_elevated)):
    return (await _forward_get(_GET_MAP["hierarchy"])).json()


@router.get("/families")
async def families(user: dict = Depends(_require_elevated)):
    return (await _forward_get(_GET_MAP["families"])).json()


@router.get("/documents/{code}")
async def document(code: str, user: dict = Depends(_require_elevated)):
    if len(code) > 64:
        raise HTTPException(status_code=422, detail="Code too long")
    return (await _forward_get(f"/api/documents/{code}")).json()


@router.post("/rag-query")
async def rag_query(body: dict = Body(...), user: dict = Depends(_require_elevated)):
    """Knowledge search across the QMS regulatory + facility archives.

    Longer timeout: the upstream fans out to Letta archival search."""
    if not settings.qms_api_key:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    if len(str(body)) > 8_192:
        raise HTTPException(status_code=422, detail="Query too large")
    try:
        async with _client() as c:
            r = await c.post("/api/rag-query", json=body,
                             timeout=httpx.Timeout(60.0))
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    if r.status_code >= 500:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail="QMS request failed")
    return r.json()


@router.get("/download/{path:path}")
async def download(path: str, user: dict = Depends(_require_elevated)):
    """Stream a generated SOP file. qms-api already confines the path to its
    output/ directory; length-cap here keeps abuse out of the upstream."""
    if len(path) > 512:
        raise HTTPException(status_code=422, detail="Path too long")
    # M2: {path:path} allows slashes, and httpx RFC-3986 joins collapse `../`, so
    # an un-validated path (e.g. `../../api/workflows`) would reach arbitrary
    # internal qms-api endpoints the allowlist exists to block. Reject traversal
    # and absolute paths before forwarding — this download is confined to the
    # upstream's output/ directory.
    if path.startswith(("/", "\\")) or "\\" in path or ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    r = await _forward_get(f"/api/download/{path}")
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "application/octet-stream"),
        headers={k: v for k, v in r.headers.items()
                 if k.lower() == "content-disposition"},
    )


# ════════════════════════ QMS Studio — DocEngine ════════════════════════
# The dedicated Letta-powered document engine (docengine/): questionnaire →
# agent-fleet generation → regulatory check → pp-document-suite formatting
# with the hard `RESULT: PASS` gate. Same façade pattern: internal container,
# key injected here, explicit endpoint surface only.

_DE_UNAVAILABLE = docengine.DE_UNAVAILABLE
# Controlled-document AUTHORING is a quality function: QP, QA manager, ADMIN
# (and OWNER — the site's top authority). Reading stays at elevated.
_AUTHOR_ROLES = ("ADMIN", "OWNER", "QP", "QA_MGR")


def _require_author(user: dict = Depends(_require_elevated)) -> dict:
    if user["role"] not in _AUTHOR_ROLES:
        raise HTTPException(status_code=403,
                            detail="Document authoring is limited to QA/QP/admin")
    return user


def _de_client(timeout: float = 20.0) -> httpx.AsyncClient:
    """DocEngine upstream client; separate hook for tests to monkeypatch."""
    return docengine.de_client(timeout)


async def _de_forward(method: str, path: str, json_body: dict | None = None,
                      timeout: float = 20.0) -> httpx.Response:
    # Delegates to the shared client but keeps `_de_client` as the seam the
    # proxy tests monkeypatch (resolved at call time via the module global).
    return await docengine.de_forward(method, path, json_body, timeout,
                                      client_factory=_de_client)


@router.get("/studio/questionnaires")
async def studio_questionnaires(user: dict = Depends(_require_elevated)):
    return (await _de_forward("GET", "/questionnaires")).json()


@router.get("/studio/questionnaires/{key}")
async def studio_questionnaire(key: str, user: dict = Depends(_require_elevated)):
    if len(key) > 64:
        raise HTTPException(status_code=422, detail="Key too long")
    return (await _de_forward("GET", f"/questionnaires/{key}")).json()


@router.post("/studio/workflows")
async def studio_start_workflow(body: dict = Body(...),
                                user: dict = Depends(_require_author)):
    if len(str(body)) > 65_536:
        raise HTTPException(status_code=422, detail="Payload too large")
    body["requested_by"] = user["username"]
    return (await _de_forward("POST", "/workflows", body)).json()


@router.get("/studio/workflows/{jid}")
async def studio_workflow(jid: str, user: dict = Depends(_require_author)):
    if len(jid) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    return (await _de_forward("GET", f"/workflows/{jid}")).json()


@router.post("/studio/build")
async def studio_build(body: dict = Body(...),
                       user: dict = Depends(_require_author)):
    """Direct Markdown -> verified .docx (Mode B/C). Long timeout: the
    build+verify run in-process upstream. A verify FAIL comes back as 422
    with the pp_verify report in the detail."""
    if len(str(body)) > 450_000:
        raise HTTPException(status_code=422, detail="Payload too large")
    return (await _de_forward("POST", "/build", body, timeout=120.0)).json()


@router.get("/studio/documents")
async def studio_documents(user: dict = Depends(_require_elevated)):
    return (await _de_forward("GET", "/documents")).json()


@router.get("/studio/documents/{did}")
async def studio_document(did: str, user: dict = Depends(_require_elevated)):
    if len(did) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    return (await _de_forward("GET", f"/documents/{did}")).json()


async def _de_stream(path: str, timeout: float = 120.0) -> Response:
    r = await _de_forward("GET", path, timeout=timeout)
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "application/octet-stream"),
        headers={k: v for k, v in r.headers.items()
                 if k.lower() == "content-disposition"},
    )


@router.get("/studio/documents/{did}/download")
async def studio_download(did: str, user: dict = Depends(_require_elevated)):
    if len(did) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    return await _de_stream(f"/documents/{did}/download")


@router.get("/studio/documents/{did}/pdf")
async def studio_pdf(did: str, user: dict = Depends(_require_elevated)):
    if len(did) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    return await _de_stream(f"/documents/{did}/pdf")
