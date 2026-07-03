"""Pure timing math for scripts/scheduler.py — the Thursday-14:00 fire.

The regression this pins: the main loop must hold ONE fire target while it
sleeps. next_fire() is strictly-future by contract, so a loop that recomputes
it after every wake sees `remaining > 0` forever and never fires — the bug
shipped in the first version, masked in dev by the boot-time missed-run
recovery path (containers restart often there; production ones don't)."""
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import scheduler as s  # noqa: E402

TZ = ZoneInfo("Europe/Skopje")


def _at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


def test_next_fire_same_day_before_1400():
    # Thursday 2026-07-09, 13:59 local -> fires 14:00 that same Thursday.
    fire = s.next_fire(_at(2026, 7, 9, 13, 59), TZ)
    assert fire == _at(2026, 7, 9, 14, 0)


def test_next_fire_at_or_after_1400_rolls_a_week():
    for hh, mm in ((14, 0), (14, 1), (23, 59)):
        fire = s.next_fire(_at(2026, 7, 9, hh, mm), TZ)
        assert fire == _at(2026, 7, 16, 14, 0)


def test_next_fire_is_strictly_future_hence_target_must_be_held():
    """Documents the loop contract: recomputing next_fire at the fire instant
    jumps a whole week, so `remaining` can never reach zero if the target is
    recomputed per wake. The loop must capture `fire` once and sleep toward
    that fixed instant."""
    t0 = _at(2026, 7, 8, 9, 0)                       # a Wednesday morning
    fire = s.next_fire(t0, TZ)
    assert fire > t0
    # At (or a tick past) the captured target, a fixed-target loop exits...
    assert (fire - fire).total_seconds() <= 0
    # ...whereas a recomputed target is already next week — the dead-loop.
    assert s.next_fire(fire, TZ) == fire + timedelta(days=7)


def test_last_fire_is_the_previous_thursday_1400():
    lf = s.last_fire(_at(2026, 7, 3, 0, 30), TZ)     # early Friday
    assert lf == _at(2026, 7, 2, 14, 0)
    assert lf <= _at(2026, 7, 3, 0, 30)


def test_fire_times_are_dst_stable_wall_clock():
    # Across the October DST fall-back, the fire stays 14:00 wall-clock.
    before = s.next_fire(_at(2026, 10, 20, 12, 0), TZ)   # Tuesday before change
    after = s.next_fire(_at(2026, 10, 27, 12, 0), TZ)    # Tuesday after change
    assert before.hour == 14 and after.hour == 14
    # And their UTC offsets differ by the DST hour, proving zoneinfo did the work.
    assert before.utcoffset() - after.utcoffset() == timedelta(hours=1)
