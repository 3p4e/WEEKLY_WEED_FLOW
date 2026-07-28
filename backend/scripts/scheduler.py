#!/usr/bin/env python3
"""Durable scheduler: fires the weekly snapshot every Thursday 14:00
(Europe/Skopje by default). Runs as its own container from the backend image
(`python scripts/scheduler.py`), restart=unless-stopped.

Design notes:
- Timing uses timezone-aware datetimes at wall-clock 14:00, so DST is handled
  correctly by zoneinfo (needs the tzdata pip package on slim images).
- Sleeps in <=30-min chunks and recomputes the remaining time each wake, so
  host suspend / clock drift can't make it overshoot badly.
- Missed-run recovery: on boot, if the most recent Thursday-14:00 fire is
  within SNAPSHOT_GRACE_HOURS and no weekly_report pin exists at/after it, it
  runs immediately for that date; otherwise it waits for the next fire.
- Startup also applies the versioned planner prompts and attaches the RAG
  source (both idempotent + failure-tolerant), so a fresh deploy self-heals.
- Liveness: every wake touches HEARTBEAT_PATH. The container healthcheck
  reads its mtime, which is what actually distinguishes "alive" from
  "wedged" — the process staying up proves nothing about the loop, and this
  loop is the only thing that fires the weekly snapshot. The sleep is capped
  at 30 min, so a heartbeat older than ~35 min means the loop has stopped
  turning (H12).
"""
import asyncio
import os
import pathlib
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(__file__))

import asyncpg  # noqa: E402
import httpx  # noqa: E402

import planner_prompts  # noqa: E402
import weekly_snapshot as snap  # noqa: E402

from app import duescan  # noqa: E402  (app pools; init_pools() runs in main)
from app.config import settings  # noqa: E402
from app.db import init_pools  # noqa: E402

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

# Same source as app/worktime.py's TZ (both read settings.snapshot_tz) so the
# snapshot cannot fire against a different week boundary than the reports it
# summarises — they used to resolve SNAPSHOT_TZ independently.
TZ_NAME = settings.snapshot_tz
GRACE_HOURS = float(os.environ.get("SNAPSHOT_GRACE_HOURS", "24"))
FIRE_WEEKDAY = 3   # Thursday (Mon=0)
FIRE_TIME = time(14, 0)


def _tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo(TZ_NAME)
        except Exception:
            snap.log(f"tz {TZ_NAME} unavailable (tzdata missing?) — falling back to UTC")
    from datetime import timezone
    return timezone.utc


def next_fire(now: datetime, tz) -> datetime:
    """Next Thursday 14:00 strictly after *now* (both tz-aware)."""
    local = now.astimezone(tz)
    d = local.date() + timedelta(days=(FIRE_WEEKDAY - local.weekday()) % 7)
    fire = datetime.combine(d, FIRE_TIME, tzinfo=tz)
    if fire <= local:
        fire = datetime.combine(d + timedelta(days=7), FIRE_TIME, tzinfo=tz)
    return fire


def last_fire(now: datetime, tz) -> datetime:
    """Most recent Thursday 14:00 at or before *now*."""
    return next_fire(now, tz) - timedelta(days=7)


async def _already_ran(since: datetime, org_id) -> bool:
    """True if THIS org already has a weekly_report pin created at/after
    *since* — checked per-org so one organization's success can't mask a
    different organization's failure and skip its missed-run recovery."""
    dsn = os.environ.get("TASKS_ADMIN_DATABASE_URL", "")  # ai_pins live in the tasks DB
    if not dsn:
        return False
    conn = await asyncpg.connect(dsn)
    try:
        # *since* is tz-aware; asyncpg compares timestamptz by instant, so
        # pass it as-is (converting wall-clock and relabelling the tzinfo
        # would silently shift the boundary by the UTC offset).
        n = await conn.fetchval(
            "SELECT count(*) FROM ai_pins WHERE function_key='weekly_report' "
            "AND org_id=$1 AND created_at >= $2",
            org_id, since)
        return (n or 0) > 0
    except Exception as e:
        snap.log(f"missed-run check failed: {type(e).__name__} — assuming not run")
        return False
    finally:
        await conn.close()


async def _orgs_needing_recovery(since: datetime) -> list:
    """Org ids/names that don't yet have a weekly_report pin at/after *since*."""
    dsn = os.environ.get("USERS_ADMIN_DATABASE_URL", "")
    if not dsn:
        return []
    uconn = await asyncpg.connect(dsn)
    try:
        # Exclude the live demo org (slug 'demo') — same rule as run_all.
        orgs = await uconn.fetch("SELECT id, name FROM organizations WHERE slug <> 'demo'")
    except Exception as e:
        snap.log(f"org list fetch failed: {type(e).__name__} — skipping recovery")
        return []
    finally:
        await uconn.close()
    return [o for o in orgs if not await _already_ran(since, o["id"])]


async def _startup_selfheal():
    """Idempotent: apply versioned prompts + attach RAG source. Never fatal."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await planner_prompts.apply(client, {
                os.environ.get("LETTA_WEEKLY_REPORT_AGENT_ID", ""): planner_prompts.WEEKLY_REPORT_SYSTEM,
                os.environ.get("LETTA_NEXT_WEEK_PLAN_AGENT_ID", ""): planner_prompts.NEXT_WEEK_PLAN_SYSTEM,
            })
    except Exception as e:
        snap.log(f"prompt apply skipped: {type(e).__name__}")
    try:
        await snap.attach_source_once()
    except Exception as e:
        snap.log(f"source attach skipped: {type(e).__name__}")


HEARTBEAT_PATH = pathlib.Path(os.environ.get("SCHEDULER_HEARTBEAT",
                                             "/tmp/wwf-scheduler-heartbeat"))  # nosec B108


def _beat() -> None:
    """Stamp liveness for the container healthcheck. Never raises: a scheduler
    that cannot write its heartbeat must still fire the weekly snapshot."""
    try:
        HEARTBEAT_PATH.touch()
    except OSError as e:
        snap.log(f"heartbeat touch failed: {type(e).__name__}: {e}")


async def main():
    tz = _tz()
    from datetime import timezone
    now = datetime.now(timezone.utc)
    snap.log(f"scheduler start; tz={TZ_NAME}; next fire {next_fire(now, tz).isoformat()}")

    await _startup_selfheal()

    # Missed-run recovery — per-org, so one org's success doesn't mask a
    # different org's failure and skip its retry.
    lf = last_fire(now, tz)
    if (now - lf).total_seconds() <= GRACE_HOURS * 3600:
        for o in await _orgs_needing_recovery(lf):
            snap.log(f"missed-run recovery: running now for org {o['name']} {lf.date().isoformat()}")
            try:
                await snap.run_all(lf.date(), only_org=o["id"])
            except Exception as e:
                snap.log(f"recovery run failed for org {o['name']}: {type(e).__name__}: {e}")

    # Daily due-soon/overdue scan (research matrix v1.x). Fires once per
    # local day after 06:00; duescan itself is idempotent within a day (it
    # skips tasks that already produced today's event), so container
    # restarts never re-ping.
    await init_pools()
    last_due_scan: date | None = None

    async def due_tick():
        nonlocal last_due_scan
        local = datetime.now(timezone.utc).astimezone(tz)
        if local.hour >= 6 and last_due_scan != local.date():
            try:
                counts = await duescan.run_all(local.date())
                snap.log(f"due scan {local.date().isoformat()}: {counts}")
                last_due_scan = local.date()
            except Exception as e:
                snap.log(f"due scan failed: {type(e).__name__}: {e}")

    await due_tick()
    _beat()

    while True:
        # Pick the fire target ONCE, then sleep toward it in chunks. The
        # target must stay fixed while we wait: next_fire() always returns a
        # time strictly in the future, so recomputing it after every wake
        # (the previous shape of this loop) means "remaining" never reaches
        # zero and the job never fires.
        fire = next_fire(datetime.now(timezone.utc), tz)
        while (remaining := (fire - datetime.now(timezone.utc)).total_seconds()) > 0:
            await asyncio.sleep(min(1800, remaining))
            await due_tick()
            _beat()
        snap.log(f"firing weekly snapshot for {fire.astimezone(tz).date().isoformat()}")
        try:
            await snap.run_all(fire.astimezone(tz).date())
        except Exception as e:
            snap.log(f"scheduled run failed: {type(e).__name__}: {e}")
        # Loop continues: now > fire, so next_fire() lands on next Thursday.


if __name__ == "__main__":
    asyncio.run(main())
