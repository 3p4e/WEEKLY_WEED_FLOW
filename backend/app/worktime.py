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
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings

# Through Settings, not a bare os.environ read — scripts/scheduler.py resolved
# the same SNAPSHOT_TZ independently, so the two could disagree about which
# wall-clock the week boundary sits on with nothing to flag it.
TZ = ZoneInfo(settings.snapshot_tz)

BUCKETS = ("regular", "overtime", "night", "weekend")


# The SAME rule for SQL. `CURRENT_DATE` (and `x::date` on a timestamptz)
# render under the DATABASE's zone — UTC everywhere this app runs — so a query
# defaulting a column to CURRENT_DATE has the identical nightly off-by-one as
# naive Python. These fragments carry the facility zone as a SQL literal; the
# zone is a config constant (settings.snapshot_tz), never user input, and the
# quote-doubling below keeps even a misconfigured value from breaking out of
# the literal. tests/test_facility_clock.py bans CURRENT_DATE app-wide.
SITE_TZ_SQL = "'" + settings.snapshot_tz.replace("'", "''") + "'"
SITE_TODAY_SQL = f"(now() AT TIME ZONE {SITE_TZ_SQL})::date"
# The year for document numbers (CoQ-PP-YYYY-NNNN, PP-SPEC-YYYY-NNNN, ...) —
# the FACILITY's year, not the database's UTC year. A certificate issued
# between facility-midnight and UTC-midnight on 31 Dec would otherwise carry
# the previous year in its number (same nightly off-by-one as SITE_TODAY_SQL).
SITE_YEAR_SQL = f"to_char(now() AT TIME ZONE {SITE_TZ_SQL},'YYYY')"


def facility_today():
    """Today as the FACILITY sees it — never `date.today()`.

    `date.today()` renders under the process's zone (UTC in every container
    and in CI), while the SQL side of this codebase converts timestamps at
    settings.snapshot_tz (see harvest._site_today and the audit views). The
    two disagree every night between facility-midnight and UTC-midnight —
    for Europe/Skopje that is a standing 1–2 h window in which "today" is
    Friday to the database and still Thursday to naive Python, weekly
    windows point at the wrong week, and the CI suite fails if it happens
    to run then (it did, 2026-07-30 22:30 UTC). Every "what day is it"
    question in this codebase must go through here or through SQL at
    snapshot_tz; tests/test_facility_clock.py enforces the app side."""
    from datetime import datetime
    return datetime.now(TZ).date()


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
