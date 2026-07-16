"""
Purely Plant GmbH QC LIMS — FastAPI Application Entry Point

EU GMP Annex 11 compliant computerised system for cannabis flower
API manufacturing quality control laboratory.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import engine, Base
# Import the models package so every ORM model registers on Base.metadata
# BEFORE the lifespan calls create_all() — otherwise zero tables are created.
import app.models  # noqa: F401
from app.api import auth, samples, specifications, coa, oos, audit
from app.api import sampling_requests, transport, capa, water, stability

# Repository root holds the GrowFlow Unified frontend (see /frontend). The React
# app builds to frontend/dist; main.py lives at backend/app/main.py, so the repo
# root is two levels up. In the docker topology nginx serves the build, but
# mounting dist here also lets a single FastAPI process serve the SPA same-origin.
_REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = _REPO_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: startup/shutdown events.

    Startup: Verify database connectivity, create tables if needed.
    Shutdown: Gracefully dispose of the database engine.
    """
    # Startup
    async with engine.begin() as conn:
        # Create all tables (for development; use Alembic in production)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Purely Plant GmbH QC LIMS API",
    description=(
        "EU GMP-compliant Quality Control Laboratory Information Management System "
        "for cannabis flower API manufacturing. Supports sample management, "
        "specifications, Certificate of Analysis (COA) generation, "
        "OOS investigations, and immutable audit trail per Annex 11."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(samples.router, prefix="/samples", tags=["Samples"])
app.include_router(specifications.router, prefix="/specifications", tags=["Specifications"])
app.include_router(coa.router, prefix="/coa", tags=["Certificate of Analysis"])
app.include_router(oos.router, prefix="/oos", tags=["OOS Investigation"])
app.include_router(audit.router, prefix="/audit", tags=["Audit Trail"])
app.include_router(sampling_requests.router, prefix="/sampling-requests", tags=["Sampling Requests"])
app.include_router(transport.router, prefix="/transport", tags=["Transport"])
app.include_router(capa.router, prefix="/capa", tags=["CAPA"])
app.include_router(water.router, prefix="/water", tags=["Water"])
app.include_router(stability.router, prefix="/stability", tags=["Stability"])


# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler for unhandled errors."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred.",
            "type": type(exc).__name__,
        },
    )


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "system": "QC LIMS API"}


# ── GrowFlow Unified frontend ──
# Serve the static SPA (HTML/CSS/JS) from the repo's /frontend directory.
# Mounted last so all API routes (/auth, /samples, /docs, /health, …) take
# precedence; everything else falls through to the frontend, with html=True
# serving index.html at "/". When the frontend is served same-origin the
# client talks to this API directly (no CORS needed); see frontend/README.md.
if FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
