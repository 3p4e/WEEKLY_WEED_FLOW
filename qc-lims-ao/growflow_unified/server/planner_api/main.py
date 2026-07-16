"""Planner API entry point (FastAPI)."""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .routers import ai, auth, governance, health, reports, tasks
from .routers import exec as exec_router


def _next_weekly_run(now: datetime) -> datetime:
    """Next Thursday 18:00 UTC at or after `now` (the Fri→Thu work week just ends)."""
    target = now.replace(hour=18, minute=0, second=0, microsecond=0)
    target += timedelta(days=(3 - now.weekday()) % 7)  # Thursday = weekday 3
    if target <= now:
        target += timedelta(days=7)
    return target


async def _weekly_scheduler() -> None:
    """Run the Fri→Thu snapshot export (JSON + digest + Letta push) every Thursday."""
    from .jobs import weekly_export
    while True:
        now = datetime.now(timezone.utc)
        await asyncio.sleep(max(1.0, (_next_weekly_run(now) - now).total_seconds()))
        try:
            await asyncio.to_thread(weekly_export.main, [])
        except Exception as e:  # noqa: BLE001 — a failed run must not kill the loop
            print(f"[weekly_scheduler] run failed: {e}")
        await asyncio.sleep(120)  # don't re-fire within the same minute


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    task: asyncio.Task | None = None
    if get_settings().enable_weekly_scheduler:
        task = asyncio.create_task(_weekly_scheduler())
        print("[weekly_scheduler] enabled — Thursday 18:00 UTC")
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


app = FastAPI(
    title="GrowFlow Unified API",
    version=__version__,
    summary="Converged EU-GMP/ISO-17025 task manager: adaptive task tree, governed "
            "change-control, stateful AI agents, RLS-hardened auth.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(reports.router)
app.include_router(exec_router.router)
app.include_router(governance.router)
app.include_router(ai.router)


def run() -> None:
    s = get_settings()
    uvicorn.run(app, host=s.bind_host, port=s.bind_port)


if __name__ == "__main__":
    run()
