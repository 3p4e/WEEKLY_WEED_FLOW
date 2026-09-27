"""QMS Studio — the DocEngine façade.

The dedicated Letta-powered document engine (docengine/) runs as an INTERNAL
container whose only client is this router: GrowFlow JWT auth and role gates
are enforced here, then the request is forwarded with the DocEngine API key
injected server-side. The key never reaches a browser, and no auth code had
to be added to the engine — the strangler façade from
docs/UNIFICATION-ANALYSIS-2026-07.md §7.

The Phase-1 proxy to the legacy `qms-api` container (registry, stats,
hierarchy, families, knowledge search, file download — seven routes under
/qms/) is gone: qms-api was retired platform-wide (web/gf/qmsregistry-view.js,
qmsknow-view.js) and nothing called those routes any more, so they were an
unauthenticated-upstream surface kept alive for no reader (review
2026-09-27, BC-19). The DocEngine registry at /qms/studio/documents is the
successor.

Governance note (docs/SCOPE.md): this router serves the QMS *Studio* zone —
the document-authoring side. Nothing here writes into the ops zone; the two
zones reference each other only by pointer (SOP code).
"""
import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response

from app import demo_org, docengine
from app.db import rls
from app.deps import require_password_set
from app.notify import safe_emit
from app.roles import ADMIN, ELEVATED_ROLES

router = APIRouter(prefix="/qms", tags=["qms"])


def _require_elevated(user: dict = Depends(require_password_set)) -> dict:
    # Same read gate as /facility and /reports/analytics: every role above
    # base USER (executives, QP, department managers).
    if user["role"] not in ELEVATED_ROLES:
        raise HTTPException(status_code=403, detail="Managers and executives only")
    return user


# ════════════════════════ QMS Studio — DocEngine ════════════════════════
# questionnaire → agent-fleet generation → regulatory check → pp-document-suite
# formatting with the hard `RESULT: PASS` gate. Internal container, key
# injected here, explicit endpoint surface only.

# Controlled-document AUTHORING is a quality function: QP, QA manager, ADMIN
# (and OWNER — the site's top authority). Reading stays at elevated.
_AUTHOR_ROLES = (ADMIN, "OWNER", "QP", "QA_MGR")


async def _require_author(user: dict = Depends(_require_elevated)) -> dict:
    if user["role"] not in _AUTHOR_ROLES:
        raise HTTPException(status_code=403,
                            detail="Document authoring is limited to QA/QP/admin")
    # The public demo's visitor token is the demo cast's ADMIN. Authoring a
    # controlled document spends real Letta turns and writes a row into the
    # facility's document registry, so the demo org may read the Studio but
    # never author in it (review 2026-09-27, DI-13).
    demo_id = await demo_org.get_demo_org_id()
    if demo_id is not None and str(user["org_id"]) == str(demo_id):
        raise HTTPException(status_code=403, detail="Document authoring is not available in the demo")
    return user


def _de_client(timeout: float = 20.0) -> httpx.AsyncClient:
    """DocEngine upstream client; separate hook for tests to monkeypatch."""
    return docengine.de_client(timeout)


async def _de_forward(method: str, path: str, json_body: dict | None = None,
                      timeout: float = 20.0, *, org_id: str | None = None,
                      params: dict | None = None) -> httpx.Response:
    # Delegates to the shared client but keeps `_de_client` as the seam the
    # proxy tests monkeypatch (resolved at call time via the module global).
    # DocEngine scopes jobs and the document registry by organisation and
    # refuses a call that names none (review 2026-09-27, DI-13), so every
    # route passes the signed-in user's org through here.
    return await docengine.de_forward(method, path, json_body, timeout,
                                      client_factory=_de_client, org_id=org_id,
                                      params=params)


@router.get("/studio/questionnaires")
async def studio_questionnaires(user: dict = Depends(_require_elevated)):
    return (await _de_forward("GET", "/questionnaires", org_id=user["org_id"])).json()


@router.get("/studio/questionnaires/{key}")
async def studio_questionnaire(key: str, user: dict = Depends(_require_elevated)):
    if len(key) > 64:
        raise HTTPException(status_code=422, detail="Key too long")
    return (await _de_forward("GET", f"/questionnaires/{key}", org_id=user["org_id"])).json()


@router.post("/studio/workflows")
async def studio_start_workflow(body: dict = Body(...),
                                user: dict = Depends(_require_author)):
    if len(str(body)) > 65_536:
        raise HTTPException(status_code=422, detail="Payload too large")
    body["requested_by"] = user["username"]
    return (await _de_forward("POST", "/workflows", body, org_id=user["org_id"])).json()


@router.get("/studio/workflows/{jid}")
async def studio_workflow(jid: str, user: dict = Depends(_require_author)):
    if len(jid) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    return (await _de_forward("GET", f"/workflows/{jid}", org_id=user["org_id"])).json()


@router.get("/studio/presets")
async def studio_presets(user: dict = Depends(_require_elevated)):
    """The direct-edit chat UI's one-click instructions. Read gate only —
    picking a preset does nothing by itself; sending it through /revise is
    what requires author role."""
    return (await _de_forward("GET", "/presets", org_id=user["org_id"])).json()


@router.post("/studio/workflows/{jid}/chat")
async def studio_chat(jid: str, body: dict = Body(...),
                      user: dict = Depends(_require_author)):
    """Ask a question about a finished document. Read-only upstream — see
    docengine's own /workflows/{jid}/chat docstring — so this proxies with no
    side effects of its own either. The same generous timeout as /studio/build:
    the answer is a real Letta turn, not a DB read."""
    if len(jid) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    if len(str(body)) > 8_000:
        raise HTTPException(status_code=422, detail="Payload too large")
    return (await _de_forward("POST", f"/workflows/{jid}/chat", body,
                              timeout=docengine.DE_CHAT_TIMEOUT_S, org_id=user["org_id"])).json()


@router.post("/studio/workflows/{jid}/revise")
async def studio_revise(jid: str, body: dict = Body(...),
                        user: dict = Depends(_require_author)):
    """Start a direct-edit job (chat instruction or preset) against a
    finished document. Fires and returns a job id exactly like
    /studio/workflows does — poll the returned id at /studio/workflows/{id}
    the same way. requested_by is stamped server-side, never trusted from
    the caller, for the same reason /studio/workflows stamps it."""
    if len(jid) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    if len(str(body)) > 8_000:
        raise HTTPException(status_code=422, detail="Payload too large")
    body["requested_by"] = user["username"]
    return (await _de_forward("POST", f"/workflows/{jid}/revise", body, org_id=user["org_id"])).json()


@router.post("/studio/build")
async def studio_build(body: dict = Body(...),
                       user: dict = Depends(_require_author)):
    """Direct Markdown -> verified .docx (Mode B/C). Long timeout: the
    build+verify run in-process upstream. A verify FAIL comes back as 422
    with the pp_verify report in the detail.

    requested_by is stamped from the JWT identity like /studio/workflows and
    /revise do — it used to be forwarded as the browser sent it, so a Studio
    build registered a controlled document as whoever the client claimed
    (usually nobody), and nothing in the facility's own trail recorded that
    a build happened (review 2026-09-27, DI2-04). The registered document is
    written to the event feed as `studio_build` so the registry row and the
    audited feed name the same person and the same document id."""
    if len(str(body)) > 450_000:
        raise HTTPException(status_code=422, detail="Payload too large")
    body["requested_by"] = user["username"]
    out = (await _de_forward("POST", "/build", body, timeout=120.0, org_id=user["org_id"])).json()
    doc_id = out.get("document_id") if isinstance(out, dict) else None
    if doc_id:
        registered = out.get("registered") or {}
        async with rls(user) as c:
            await safe_emit(c, user, verb="studio_build", object_type="docengine_document",
                            object_id=str(doc_id), recipients=[],
                            params={"document_id": str(doc_id),
                                    "code": registered.get("code") or (body.get("meta") or {}).get("code") or "",
                                    "version": registered.get("version") or "",
                                    "title_en": registered.get("title_en") or "",
                                    "audited": bool(out.get("audited", False))})
    return out


@router.get("/studio/documents")
async def studio_documents(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                           user: dict = Depends(_require_elevated)):
    """The organisation's document registry, paged (review 2026-09-27,
    DI-21): DocEngine answers {documents, total, limit, offset}."""
    return (await _de_forward("GET", "/documents", org_id=user["org_id"],
                              params={"limit": limit, "offset": offset})).json()


@router.get("/studio/documents/{did}")
async def studio_document(did: str, user: dict = Depends(_require_elevated)):
    if len(did) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    return (await _de_forward("GET", f"/documents/{did}", org_id=user["org_id"])).json()


async def _de_stream(path: str, org_id: str, timeout: float = 120.0) -> Response:
    r = await _de_forward("GET", path, timeout=timeout, org_id=org_id)
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
    return await _de_stream(f"/documents/{did}/download", user["org_id"])


@router.get("/studio/documents/{did}/pdf")
async def studio_pdf(did: str, user: dict = Depends(_require_elevated)):
    if len(did) > 64:
        raise HTTPException(status_code=422, detail="Id too long")
    return await _de_stream(f"/documents/{did}/pdf", user["org_id"])
