"""WEEKLY_WEED_FLOW API entrypoint."""
import logging
import time
from contextlib import asynccontextmanager

from asyncpg.exceptions import UniqueViolationError
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, approvals, audit, auth, biosecurity, capture, collab, cultivation, decon, demo, documents, facility, facility_layout, harvest, intake, irrigation, notifications, propagation, qc, qms, reports, tasks, trichome, waste
from app.config import docs_kwargs, settings
from app.db import close_pools, init_pools, tasks_admin_pool, users_admin_pool
from app.logging_config import configure_logging

configure_logging()
request_logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pools()
    yield
    await close_pools()


app = FastAPI(title="WEEKLY_WEED_FLOW API", version="0.1.0", lifespan=lifespan,
              **docs_kwargs(settings.environment))

# A unique-violation from the sample-claim indexes is a RACE, not a bug: the
# pre-check in api/qc/custody.py reads "free" and a concurrent request commits
# the same link before this one does. Migration 0063's partial unique indexes
# are the actual control and one of the two loses there — but asyncpg raises,
# and an unhandled UniqueViolationError is a 500. The caller who lost a race
# deserves the same answer as the caller who was merely second, so it is mapped
# onto the identical 409. Registered centrally rather than wrapped around each
# write, so a future write path cannot forget it.
_SAMPLE_CLAIM_INDEXES = {"qc_sfr_sample_active_uniq", "qc_rqs_sample_active_uniq"}


@app.exception_handler(UniqueViolationError)
async def _unique_violation(request: Request, exc: UniqueViolationError) -> Response:
    if getattr(exc, "constraint_name", "") in _SAMPLE_CLAIM_INDEXES:
        return JSONResponse(
            status_code=409,
            content={"detail": "that sample is already linked to another active record"
                               " — one physical sample carries one active custody record;"
                               " cancel that record first"},
        )
    raise exc


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else [o.strip() for o in settings.cors_origins.split(",")],
    # No cookie-based auth (bearer tokens only), so credentialed cross-origin
    # requests are never needed — keep this off rather than pairing it with a
    # wildcard origin.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Defence-in-depth request-body ceiling (M9). The per-endpoint limits (the eCoA
# original's Pydantic max_length + its 20 MB decoded cap, the 8 KB task-attribute
# cap, …) only run AFTER Starlette has buffered the whole body into memory, so a
# pathological multi-hundred-MB body would already be resident before any of them
# fire. Reject by the declared Content-Length up front instead. nginx caps this at
# the edge too; this guard also holds when the app is reached without the proxy.
# The ceiling sits just above the largest legitimate body — a base64 eCoA original
# (~27 MB for the 20 MB decoded cap) — so it never trips a real request.
_MAX_REQUEST_BYTES = 32 * 1024 * 1024


# VERIFIED (Wave 3, audit Low finding "a rejected body never gets a log
# line"): it already does — there is no gap here, and nothing below needed a
# fix. `@app.middleware("http")` is sugar for `add_middleware(BaseHTTPMiddleware,
# dispatch=...)` (fastapi/applications.py), and Starlette's add_middleware
# INSERTS AT POSITION 0 of `user_middleware` (starlette/applications.py) rather
# than appending. Registration order in this file is CORS, then
# limit_body_size, then log_requests, so after all three inserts
# user_middleware = [log_requests, limit_body_size, CORS]. build_middleware_stack
# wraps outward-in over that list (`for cls,... in reversed(middleware): app =
# cls(app, ...)`), which makes the FIRST entry the OUTERMOST layer — so
# log_requests wraps limit_body_size, which wraps CORS, which wraps the router.
# Concretely: log_requests's `response = await call_next(request)` calls
# straight into limit_body_size and receives back whatever it returns —
# including its early-return 400 (bad Content-Length), 413 (declared too
# large), and 413 (streamed-over-cap) responses — and logs every one of them
# via the "request" event below with the real status code. There is no
# early-return path here that raises instead of returning a Response, so
# nothing bypasses log_requests's try/except either. Confirmed against the
# installed starlette==1.3.1 source, not just read here. A redundant log call
# was deliberately NOT added — see log_requests below for the "request" event
# that already covers this.
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            declared = int(cl)
        except ValueError:
            return Response('{"detail":"Invalid Content-Length"}', status_code=400,
                            media_type="application/json")
        if declared > _MAX_REQUEST_BYTES:
            return Response('{"detail":"Request body too large"}', status_code=413,
                            media_type="application/json")

    # Backstop for the case the Content-Length check above can't catch: a
    # request sent with `Transfer-Encoding: chunked` carries no Content-Length
    # at all, and nothing stops a client from declaring a small one and then
    # sending more. Either way Starlette would otherwise buffer the whole body
    # into memory before any per-endpoint cap ever runs — the exact
    # unbounded-memory DoS this guard exists to close. So count the ACTUAL
    # bytes as they arrive from the stream and abort the instant the running
    # total exceeds the ceiling: at most _MAX_REQUEST_BYTES + 1 bytes are ever
    # held, regardless of what Content-Length claimed or omitted.
    #
    # The accumulated body is cached onto `request._body` — exactly what
    # `Request.body()` does — so this is transparent to every downstream
    # reader (JSON/form/multipart parsing, and BaseHTTPMiddleware's own replay
    # into call_next): the body is still read exactly once, just slightly
    # earlier, and ordinary requests are unaffected.
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > _MAX_REQUEST_BYTES:
            request_logger.warning(
                "request_rejected",
                extra={"fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "reason": "body_too_large_streamed",
                    "bytes_read": total,
                }},
            )
            return Response('{"detail":"Request body too large"}', status_code=413,
                            media_type="application/json")
        chunks.append(chunk)
    request._body = b"".join(chunks)

    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Registered AFTER limit_body_size above, which (see the comment there)
    # makes this the OUTER layer — call_next() below invokes limit_body_size
    # directly, so its early-rejection responses (400/413) flow back through
    # here and are logged by the "request" event same as any other response.
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        request_logger.error(
            "request_failed",
            extra={"fields": {
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.monotonic() - start) * 1000, 1),
            }},
            exc_info=True,
        )
        raise
    fields = {
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": round((time.monotonic() - start) * 1000, 1),
        # request.client.host is the real client only when uvicorn trusts the
        # proxy (FORWARDED_ALLOW_IPS = the frontend's IP); otherwise it's the
        # immediate peer. Logging it makes the forwarded-headers config
        # observable and gives every request a client-IP forensic anchor.
        "client": request.client.host if request.client else None,
    }
    level = logging.WARNING if response.status_code >= 500 else logging.INFO
    request_logger.log(level, "request", extra={"fields": fields})
    return response

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(ai.router)
app.include_router(audit.router)
app.include_router(collab.router)
app.include_router(reports.router)
app.include_router(documents.router)
app.include_router(capture.router)
app.include_router(intake.router)
app.include_router(notifications.router)
app.include_router(facility.router)
# The as-built layout register (0068): the building as the architect drew it,
# on the same /facility prefix as the live occupancy board.
app.include_router(facility_layout.router)
app.include_router(cultivation.router)
# Propagation (0065): the mother-plant bank and clone runs — the clone end of
# cultivation's span, on the same /cultivation prefix.
app.include_router(propagation.router)
# Trichome maturation checks (0066): the documented record behind a harvest
# date, a fourth module on the same /cultivation prefix.
app.include_router(trichome.router)
# Second router on the /cultivation prefix: harvest and IPM are cultivation
# records, kept in their own module because together they carry one interlocking
# control (the pre-harvest interval) that is easier to break when split up.
app.include_router(harvest.router)
# Third router on the /cultivation prefix: the irrigation/feeding record (0052),
# the last Phase 2 cultivation record. Standalone because a feed carries no gate.
app.include_router(irrigation.router)
app.include_router(decon.router)
# Second router on the /decon prefix: biosecurity monitoring (AHU filter,
# disinfection mat, contact plate/sentinel bioassay, gowning — migration 0053)
# lives on the decon board where the swabs/bleach/tool logs already are.
app.include_router(biosecurity.router)
app.include_router(waste.router)
app.include_router(approvals.router)
app.include_router(qms.router)
app.include_router(qc.router)
app.include_router(demo.router)


@app.get("/health")
async def health():
    # LIVENESS only — deliberately does not touch the database, so a DB blip
    # cannot take the process out of rotation. Readiness is /health/ready.
    # `demo_enabled` lets the splash decide whether to surface the "Try the
    # demo" button — off in production, on where DEMO_ENABLED=true is set.
    return {"status": "healthy", "system": "WEEKLY_WEED_FLOW API",
            "demo_enabled": settings.demo_enabled}


@app.get("/health/ready")
async def health_ready(response: Response):
    """READINESS — round-trips BOTH databases (H12).

    The container healthcheck needs a signal that separates "process is up"
    from "process can actually serve", and this app is useless without both
    the users DB and the tasks DB. Reports 503 with the failing side named
    rather than raising, so the body stays readable in `docker inspect`."""
    checks: dict[str, str] = {}
    for name, pool in (("users", users_admin_pool), ("tasks", tasks_admin_pool)):
        try:
            await pool().fetchval("SELECT 1")
            checks[name] = "ok"
        except Exception as e:                      # noqa: BLE001 - reported, not raised
            checks[name] = f"{type(e).__name__}: {e}"
    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = 503
    return {"ready": ready, "databases": checks}
