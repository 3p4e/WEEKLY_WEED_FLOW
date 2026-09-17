"""FastAPI app for the Potency Spec Builder.

Serves:
  * the static single-page app from ``STATIC_DIR`` (default ``web``) at ``/``
  * a JSON REST API for potency specs under ``/api/specs``
  * a liveness probe at ``/health``

No auth lives in the app itself — it is expected to run behind Traefik on the
host (TLS termination + host routing), same-origin with the SPA so the SPA can
call ``/api/...`` with relative URLs.

Environment:
  DB_PATH      SQLite file path (default ``/data/specs.db``)
  STATIC_DIR   directory of static files to serve (default ``web``)
  DATABASE_URL optional; only ``sqlite://`` is implemented (see app.db)
"""

from __future__ import annotations

import os
import re

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .catalogue import build_spec, extract_data_array
from .db import VALID_STATUS, build_store

# id is the strain abbreviation, uppercased.
ID_RE = re.compile(r"^[A-Z0-9_]{1,12}$")

app = FastAPI(title="Potency Spec Service", version="1.0.0")


@app.middleware("http")
async def _revalidate_cache(request, call_next):
    """Never let a browser serve a stale copy of the SPA.

    StaticFiles sends ETag/Last-Modified but no ``Cache-Control``; without it a
    browser may reuse a cached page heuristically and never revalidate — so a
    redeploy that renames or removes assets leaves the visitor on a broken old
    page. ``no-cache`` means "store it, but revalidate every load": the ETag makes
    that a cheap 304 when nothing changed, and a guaranteed fresh page when it
    did. API responses are never cached at all.
    """
    resp = await call_next(request)
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    else:
        resp.headers.setdefault("Cache-Control", "no-cache")
    return resp


# The store is built (and the DB initialized) once at import time.
store = build_store()


def _auto_seed(store) -> None:
    """On boot, insert every catalogue spec the DB does not hold yet.

    Parses the ``const DATA`` (Purely Plant) and ``const VERSA`` (Tetra Hip →
    Versa) arrays out of the served ``index.html`` — the live artifact — so the
    shared database is ready the moment the stack comes up, and a catalogue
    extended by a later release seeds its new strains on the next start. A spec
    already in the DB is never touched: edits, finished status and deletions of
    its nominals all win over the catalogue. Set ``SEED_ON_EMPTY=0`` to disable.
    """
    if os.getenv("SEED_ON_EMPTY", "1") == "0":
        return
    try:
        have = {str(spec.get("id", "")).upper() for spec in store.list()}
    except Exception:  # noqa: BLE001 - best-effort seed, never block startup
        return
    path = os.path.join(os.getenv("STATIC_DIR", "web"), "index.html")
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        entries = [(e[0], e[1], e[3]) for e in extract_data_array(html, "DATA")]
        try:
            entries += [(e[0], e[1], e[4]) for e in extract_data_array(html, "VERSA")]
        except ValueError:
            pass  # a page without the Versa catalogue
    except Exception as exc:  # noqa: BLE001
        print(f"[auto-seed] could not read catalogue from {path}: {exc}")
        return
    seeded = 0
    for abbr, name, nominals in entries:
        try:
            spec = build_spec(abbr, name, nominals)
            if spec["id"] in have:
                continue
            store.upsert(spec["id"], spec)
            seeded += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[auto-seed] skipped an entry: {exc}")
    if seeded:
        print(f"[auto-seed] inserted {seeded} catalogue specs from {path}")


_auto_seed(store)


def _require_valid_id(spec_id: str) -> str:
    if not ID_RE.match(spec_id):
        raise HTTPException(
            status_code=422,
            detail=f"invalid spec id {spec_id!r}: must match ^[A-Z0-9_]{{1,12}}$",
        )
    return spec_id


def _read_app_version() -> str:
    """Read ``window.__APP_VERSION`` back out of the served index.html.

    Keeping the version in one place (the page) means the value the server
    reports at ``/api/version`` always matches the freshly deployed page, so a
    browser holding a stale cached copy sees server != page and is told to
    hard-refresh — with no second constant to keep in sync.
    """
    path = os.path.join(os.getenv("STATIC_DIR", "web"), "index.html")
    try:
        with open(path, encoding="utf-8") as fh:
            m = re.search(r'window\.__APP_VERSION\s*=\s*"([^"]+)"', fh.read())
            if m:
                return m.group(1)
    except Exception:  # noqa: BLE001 - version is best-effort, never block startup
        pass
    return "unknown"


APP_VERSION = _read_app_version()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/version")
def version():
    return {"version": APP_VERSION}


@app.get("/api/specs")
def list_specs(status: str | None = Query(default=None)):
    if status is not None and status not in VALID_STATUS:
        raise HTTPException(
            status_code=422,
            detail=f"invalid status filter {status!r}: must be one of {list(VALID_STATUS)}",
        )
    return {"specs": store.list(status)}


@app.get("/api/specs/{spec_id}")
def get_spec(spec_id: str):
    _require_valid_id(spec_id)
    spec = store.get(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"spec {spec_id!r} not found")
    return spec


@app.put("/api/specs/{spec_id}")
def put_spec(spec_id: str, body: dict = Body(...)):
    _require_valid_id(spec_id)
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="request body must be a JSON object")
    status = body.get("status", "draft")
    if status not in VALID_STATUS:
        raise HTTPException(
            status_code=422,
            detail=f"invalid status {status!r}: must be one of {list(VALID_STATUS)}",
        )
    # The URL is the resource key; the path id is authoritative over any body id.
    body["id"] = spec_id
    return store.upsert(spec_id, body)


@app.post("/api/specs/{spec_id}/finish")
def finish_spec(spec_id: str):
    _require_valid_id(spec_id)
    spec = store.finish(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"spec {spec_id!r} not found")
    return spec


@app.post("/api/specs/{spec_id}/reopen")
def reopen_spec(spec_id: str):
    _require_valid_id(spec_id)
    spec = store.reopen(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"spec {spec_id!r} not found")
    return spec


@app.delete("/api/specs/{spec_id}")
def delete_spec(spec_id: str):
    # Idempotent: 200 with {"deleted": true} whether or not the spec existed.
    _require_valid_id(spec_id)
    store.delete(spec_id)
    return {"deleted": True}


# Static SPA mount LAST so the explicit API/health routes above take precedence.
# html=True serves web/index.html at "/". Guarded so a missing dir doesn't break
# the API (useful in bare test runs).
_static_dir = os.getenv("STATIC_DIR", "web")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
