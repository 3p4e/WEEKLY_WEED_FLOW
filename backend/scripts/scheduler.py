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
"""
import asyncio
import os
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(__file__))

import asyncpg  # noqa: E402
import httpx  # noqa: E402

import planner_prompts  # noqa: E402
import weekly_snapshot as snap  # noqa: E402

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

TZ_NAME = os.environ.get("SNAPSHOT_TZ", "Europe/Skopje")
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


async def _already_ran(since: datetime) -> bool:
    """True if any org already has a weekly_report pin created at/after *since*."""
    dsn = os.environ.get("TASKS_ADMIN_DATABASE_URL", "")  # ai_pins live in the tasks DB
    if not dsn:
        return False
    conn = await asyncpg.connect(dsn)
    try:
        # *since* is tz-aware; asyncpg compares timestamptz by instant, so
        # pass it as-is (converting wall-clock and relabelling the tzinfo
        # would silently shift the boundary by the UTC offset).
        n = await conn.fetchval(
            "SELECT count(*) FROM ai_pins WHERE function_key='weekly_report' AND created_at >= $1",
            since)
        return (n or 0) > 0
    except Exception as e:
        snap.log(f"missed-run check failed: {type(e).__name__} — assuming not run")
        return False
    finally:
        await conn.close()


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


async def main():
    tz = _tz()
    from datetime import timezone
    now = datetime.now(timezone.utc)
    snap.log(f"scheduler start; tz={TZ_NAME}; next fire {next_fire(now, tz).isoformat()}")

    await _startup_selfheal()

    # Missed-run recovery.
    lf = last_fire(now, tz)
    if (now - lf).total_seconds() <= GRACE_HOURS * 3600 and not await _already_ran(lf):
        snap.log(f"missed-run recovery: running now for {lf.date().isoformat()}")
        try:
            await snap.run_all(lf.date())
        except Exception as e:
            snap.log(f"recovery run failed: {type(e).__name__}: {e}")

    while True:
        # Pick the fire target ONCE, then sleep toward it in chunks. The
        # target must stay fixed while we wait: next_fire() always returns a
        # time strictly in the future, so recomputing it after every wake
        # (the previous shape of this loop) means "remaining" never reaches
        # zero and the job never fires.
        fire = next_fire(datetime.now(timezone.utc), tz)
        while (remaining := (fire - datetime.now(timezone.utc)).total_seconds()) > 0:
            await asyncio.sleep(min(1800, remaining))
        snap.log(f"firing weekly snapshot for {fire.astimezone(tz).date().isoformat()}")
        try:
            await snap.run_all(fire.astimezone(tz).date())
        except Exception as e:
            snap.log(f"scheduled run failed: {type(e).__name__}: {e}")
        # Loop continues: now > fire, so next_fire() lands on next Thursday.


if __name__ == "__main__":
    asyncio.run(main())
