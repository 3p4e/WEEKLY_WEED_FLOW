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
from datetime import datetime, timedelta
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


# The zone NAME, for binding as a query parameter ($n) where a statement
# converts a column rather than asking for today.
SITE_TZ = settings.snapshot_tz


async def site_today(c):
    """Today's date AT THE SITE, resolved by Postgres on connection `c`.

    Use it where the day is compared against a timestamp Postgres converts
    (the PHI gate renders `applied_at` at the site zone in SQL): resolving
    both in SQL means the same tzdata does both conversions, so they cannot
    drift apart — the bug class migration 0050 exists because of. Anywhere
    else facility_today() is the same answer without a round trip. One copy
    for every module (review 2026-09-27b, INV-09: harvest, biosecurity,
    irrigation and cultivation each carried their own)."""
    return await c.fetchval(f"SELECT {SITE_TODAY_SQL}")  # nosec B608 — module constant


def facility_today():
    """Today as the FACILITY sees it — never `date.today()`.

    `date.today()` renders under the process's zone (UTC in every container
    and in CI), while the SQL side of this codebase converts timestamps at
    settings.snapshot_tz (see site_today below and the audit views). The
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
    """The bucket an INSTANT falls in (facility wall-clock). For a whole
    session use split_hours: a session crosses bucket boundaries."""
    local = started_at.astimezone(TZ)
    if local.weekday() >= 5:
        return "weekend"
    if local.hour >= 22 or local.hour < 6:
        return "night"
    if 8 <= local.hour < 17:
        return "regular"
    return "overtime"


# The wall-clock hours at which a weekday changes bucket (06 night→overtime,
# 08 overtime→regular, 17 regular→overtime, 22 overtime→night); midnight is a
# boundary too, because the DAY may change from weekday to weekend.
_BOUNDARY_HOURS = (6, 8, 17, 22)
# A session longer than this is not a sitting of work, it is a typo (80 for
# 8.0) — enforced at the write paths (tasks.SessionIn, capture); the splitter
# itself only bounds its walk so a historical row can never spin it.
MAX_SESSION_HOURS = 24
_MAX_SEGMENTS = 4 * 24 * 8   # far beyond any bounded session, never a loop


def split_hours(started_at: datetime, hours: float) -> dict[str, float]:
    """Hours of a session in each bucket, split at every boundary it crosses
    in facility wall-clock time.

    A session was classified entirely by its START instant: a 07:30–16:00
    weekday shift counted as 8.5 h of OVERTIME, a 16:00–24:00 shift as 8 h of
    REGULAR time (review 2026-09-27, BC-24) — and that fed the Thursday
    report's off-hours evidence. Walking the session across 06:00, 08:00,
    17:00, 22:00 and midnight (the day itself may turn into a weekend) and
    bucketing each segment by its own start is the rule the module docstring
    always stated. Durations are real elapsed seconds, so the buckets sum to
    `hours` exactly, DST transitions included."""
    out = {b: 0.0 for b in BUCKETS}
    if hours is None or hours <= 0:
        return out
    cur = started_at.astimezone(TZ)
    end_ts = cur.timestamp() + float(hours) * 3600.0
    for _ in range(_MAX_SEGMENTS):
        cur_ts = cur.timestamp()
        if cur_ts >= end_ts:
            break
        candidates = [cur.replace(hour=h, minute=0, second=0, microsecond=0) for h in _BOUNDARY_HOURS]
        candidates.append((cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0))
        nxt = min((c for c in candidates if c.timestamp() > cur_ts), key=lambda c: c.timestamp())
        seg_end_ts = min(nxt.timestamp(), end_ts)
        out[classify(cur)] += (seg_end_ts - cur_ts) / 3600.0
        cur = nxt
    return out


def session_hours(row) -> float:
    """Duration of a session row: explicit hours wins, else ended-started."""
    if row["hours"] is not None:
        return float(row["hours"])
    if row["ended_at"] is not None:
        return (row["ended_at"] - row["started_at"]).total_seconds() / 3600.0
    return 0.0


def session_buckets(row) -> dict[str, float]:
    """split_hours over a session row — the one call every per-person and
    per-SOP hours report makes, so they cannot disagree on the split."""
    return split_hours(row["started_at"], session_hours(row))
