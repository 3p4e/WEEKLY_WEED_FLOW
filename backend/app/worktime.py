"""Work-session time classification — the overtime engine's rules.

Stored work_sessions rows are plain facts (started_at/ended_at/hours);
whether a session counts as regular / overtime / night / weekend is computed
HERE at read time, so the rules can evolve without rewriting history.

Rules (facility wall-clock, Europe/Skopje):
  weekend  — starts on Saturday or Sunday (any hour)
  night    — starts 22:00–05:59 on a weekday
  regular  — starts 08:00–16:59 Monday–Friday
  overtime — everything else on a weekday (06:00–07:59, 17:00–21:59)
Precedence weekend > night > overtime matches how the facility talks about
these hours; a Saturday 02:00 session is "weekend work", not "night work".
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("SNAPSHOT_TZ", "Europe/Skopje"))

BUCKETS = ("regular", "overtime", "night", "weekend")


def classify(started_at: datetime) -> str:
    local = started_at.astimezone(TZ)
    if local.weekday() >= 5:
        return "weekend"
    if local.hour >= 22 or local.hour < 6:
        return "night"
    if 8 <= local.hour < 17:
        return "regular"
    return "overtime"


def session_hours(row) -> float:
    """Duration of a session row: explicit hours wins, else ended-started."""
    if row["hours"] is not None:
        return float(row["hours"])
    if row["ended_at"] is not None:
        return (row["ended_at"] - row["started_at"]).total_seconds() / 3600.0
    return 0.0
