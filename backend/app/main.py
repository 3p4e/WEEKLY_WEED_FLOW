"""WEEKLY_WEED_FLOW API entrypoint."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, approvals, audit, auth, capture, collab, demo, documents, facility, intake, notifications, qc, qms, reports, tasks
from app.config import docs_kwargs, settings
from app.db import close_pools, init_pools
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


@app.middleware("http")
async def log_requests(request: Request, call_next):
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
app.include_router(approvals.router)
app.include_router(qms.router)
app.include_router(qc.router)
app.include_router(demo.router)


@app.get("/health")
async def health():
    # `demo_enabled` lets the splash decide whether to surface the "Try the
    # demo" button — off in production, on where DEMO_ENABLED=true is set.
    return {"status": "healthy", "system": "WEEKLY_WEED_FLOW API",
            "demo_enabled": settings.demo_enabled}
