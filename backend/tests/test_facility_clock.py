"""The app must never ask Python what day it is.

`date.today()` renders under the process's zone — UTC in every container and
in CI — while the SQL side of this codebase converts timestamps at
settings.snapshot_tz (Europe/Skopje). The two disagree every night between
facility-midnight and UTC-midnight: a standing 1-2 hour window in which the
database says Friday, naive Python still says Thursday, weekly report windows
point at the wrong week, and the PHI day-arithmetic is off by one.

This is not hypothetical. CI run 356 (2026-07-30, started 22:30 UTC = 00:30
facility time) failed 10 tests for exactly this reason, with zero backend
changes in the diff. The fix routes every "what day is it" through
app.worktime.facility_today(); this test makes the naive call un-reintroducible.
"""
import pathlib
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.worktime import facility_today

APP = pathlib.Path(__file__).resolve().parent.parent / "app"


def test_no_naive_date_today_anywhere_in_the_app():
    offenders = []
    for f in sorted(APP.rglob("*.py")):
        text = f.read_text()
        # strip comments and docstrings: harvest.py's PHI comment NAMES the
        # forbidden call while explaining why it is forbidden, and that must
        # not count against it.
        text = re.sub(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', "", text)
        text = re.sub(r"#[^\n]*", "", text)
        for m in re.finditer(r"date\.today\(\)|datetime\.now\(\)(?!\.astimezone)", text):
            # worktime.facility_today() itself uses datetime.now(TZ) — an
            # AWARE call; the regexes above only match the naive forms.
            offenders.append(f"{f.relative_to(APP.parent)}: {m.group(0)}")
    assert offenders == [], (
        "naive clock calls in the app — during the nightly facility-midnight..UTC-midnight "
        "window these disagree with every SQL date computed at snapshot_tz, which is how CI "
        "run 356 failed 10 tests with no backend diff. Use app.worktime.facility_today(): "
        + "; ".join(offenders)
    )


def test_facility_today_is_the_snapshot_tz_date():
    tz = ZoneInfo(settings.snapshot_tz)
    before = datetime.now(tz).date()
    got = facility_today()
    after = datetime.now(tz).date()
    # sandwich, so the test cannot flake at the exact midnight tick
    assert before <= got <= after


def test_facility_today_differs_from_utc_exactly_when_it_should():
    """Prove facility_today is NOT just date.today() in disguise.

    At most moments the two dates agree, so equality alone proves nothing.
    Instead assert the RELATIONSHIP: facility date == the UTC instant shifted
    by the zone's current offset. For Europe/Skopje (UTC+1/+2) the facility
    date is either the UTC date or one day AHEAD, never behind — the exact
    asymmetry the naive code got wrong nightly.
    """
    tz = ZoneInfo(settings.snapshot_tz)
    now_utc = datetime.now(ZoneInfo("UTC"))
    expected = (now_utc + (tz.utcoffset(now_utc) or timedelta())).date()
    # re-derive rather than compare to a cached facility_today(): the clock
    # may tick between the two calls, so allow the sandwich again
    got = facility_today()
    after = (datetime.now(ZoneInfo("UTC")) + (tz.utcoffset(now_utc) or timedelta())).date()
    assert expected <= got <= after
    assert got - now_utc.date() in (timedelta(0), timedelta(days=1)), (
        "for a UTC-positive facility zone the local date is the UTC date or the day after, "
        "never before — if this fails the zone arithmetic itself is wrong"
    )
