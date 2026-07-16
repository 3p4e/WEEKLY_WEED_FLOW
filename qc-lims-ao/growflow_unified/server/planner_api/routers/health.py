"""Liveness endpoint (unauthenticated)."""
from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..schemas import Health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health(service="planner-api", version=__version__)
