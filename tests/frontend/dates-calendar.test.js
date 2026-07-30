'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/core.js — GF.localDateStr / GF.todayISO / GF.todayDay
                    and the load-time calendar generator (GF.calendar)

   Date handling is where this app has already been bitten. core.js carries a
   six-line comment explaining that GF.localDateStr must use LOCAL getters and
   not toISOString(), because the facility runs at a positive UTC offset
   (Europe/Skopje) and a local midnight converted through UTC lands on the
   previous day — silently shifting every due date and week_start by one day.
   report-view.js repeats the same warning at two more call sites. That is
   three places relying on one four-line function that had no test.

   Everything below runs against a frozen clock (Thursday 2026-07-30 09:15
   local) and a pinned TZ, both set up by the harness — see helpers/gf-window.js
   for why the timezone is pinned rather than left to the runner.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// integrate.js ends with a bare `GF.WWF.install()`, so merely loading the file
// runs it, and install() assigns onto GF.voice — which voice.js owns. Declaring
// that one global is far less brittle than loading the other 50 scripts to unit
// test a single function, and it names the dependency out loud.
const PRE_INTEGRATE = 'window.GF = window.GF || {}; window.GF.voice = window.GF.voice || {};';

test('GF.localDateStr reads LOCAL calendar components, not the UTC ones', () => {
  const h = loadGF();
  const D = h.window.Date;

  // The exact regression the source comment describes: 00:30 local on July 1
  // is 22:30 UTC on June 30. toISOString() would report the wrong DAY.
  const justAfterMidnight = new D(2026, 6, 1, 0, 30, 0);
  assert.equal(justAfterMidnight.toISOString().slice(0, 10), '2026-06-30',
    'sanity: under TZ=Europe/Skopje the UTC day really is the previous one here');
  assert.equal(h.GF.localDateStr(justAfterMidnight), '2026-07-01');

  // And the same at the other end of the day, so a naive +offset "fix" fails too.
  assert.equal(h.GF.localDateStr(new D(2026, 6, 1, 23, 30, 0)), '2026-07-01');
  h.close();
});

test('GF.localDateStr zero-pads month and day to the ISO-8601 date shape', () => {
  const h = loadGF();
  const D = h.window.Date;
  // The output is compared as a STRING against due dates from the API
  // (`t.due < GF.todayISO()` in render.js and myday-view.js), so a missing pad
  // does not just look wrong — it breaks the overdue comparison outright:
  // '2026-9-5' sorts after '2026-12-01'.
  assert.equal(h.GF.localDateStr(new D(2026, 0, 5, 12, 0)), '2026-01-05');
  assert.equal(h.GF.localDateStr(new D(2026, 8, 9, 12, 0)), '2026-09-09');
  assert.equal(h.GF.localDateStr(new D(2026, 11, 31, 12, 0)), '2026-12-31');
  h.close();
});

test('GF.localDateStr is stable across the spring DST transition', () => {
  const h = loadGF();
  const D = h.window.Date;
  // Europe/Skopje jumps 02:00 -> 03:00 on 2026-03-29. Both the day the clocks
  // change and the days either side must report their own local date.
  assert.equal(h.GF.localDateStr(new D(2026, 2, 28, 23, 0)), '2026-03-28');
  assert.equal(h.GF.localDateStr(new D(2026, 2, 29, 4, 0)), '2026-03-29');
  assert.equal(h.GF.localDateStr(new D(2026, 2, 30, 0, 30)), '2026-03-30');
  h.close();
});

test('GF.todayISO and GF.todayDay agree with the frozen clock', () => {
  const h = loadGF();
  assert.equal(h.GF.todayISO(), '2026-07-30');
  // GF.DAYS is Monday-first, JS getDay() is Sunday-first — the (+6)%7 rotation
  // is the conversion, and getting it wrong shifts the whole day-pill row.
  assert.equal(h.GF.todayDay, 'Thu');
  h.close();
});

test('GF.todayDay rotates Sunday to the END of the Monday-first week', () => {
  // Sunday is index 0 in getDay() and index 6 in GF.DAYS — the only day the
  // rotation can get wrong without also breaking an adjacent day.
  const h = loadGF({ now: '2026-08-02T12:00:00+02:00' });   // a Sunday
  assert.equal(h.GF.todayDay, 'Sun');
  h.close();
  const mon = loadGF({ now: '2026-08-03T12:00:00+02:00' });  // the next Monday
  assert.equal(mon.GF.todayDay, 'Mon');
  mon.close();
});

/* ── The load-time calendar generator ─────────────────────────────────
   core.js builds GF.calendar.weeks in an IIFE at script-load time, off
   `new Date()`. Every view indexes into that array, and GF.state.selWeek is
   seeded from it, so the shape is a load-bearing contract. */

test('the calendar is a 14-week window starting 4 weeks before the current one', () => {
  const h = loadGF();
  const { weeks, todayId } = h.GF.calendar;
  assert.equal(weeks.length, 14);
  assert.equal(todayId, 4, '4 weeks back means the current week is index 4');
  assert.equal(h.GF.state.selWeek, todayId, 'the initial selection must be the current week');
  // ids are the array positions the views pass around as weekId. Array.from()
  // re-homes the jsdom-realm array into this realm — deepStrictEqual compares
  // prototypes, and a cross-realm Array.prototype is not the same object.
  assert.deepEqual(Array.from(weeks, w => w.id), [...Array(14).keys()]);
  h.close();
});

test('every generated week runs Monday 00:00 local through the following Sunday', () => {
  const h = loadGF();
  for (const w of h.GF.calendar.weeks) {
    assert.equal(w.start.getDay(), 1, `week ${w.id} must start on a Monday`);
    assert.equal(w.end.getDay(), 0, `week ${w.id} must end on a Sunday`);
    // setHours(0,0,0,0) is applied once to the anchor Monday and carried by
    // setDate(); if it were ever replaced by ms arithmetic the DST-crossing
    // weeks would land at 23:00 or 01:00 and week_start would be off by a day.
    assert.equal(w.start.getHours(), 0, `week ${w.id} must start at local midnight`);
    assert.equal(w.start.getMinutes(), 0);
    assert.equal(w.start.getSeconds(), 0);
    assert.equal(w.start.getMilliseconds(), 0);
    assert.equal(h.GF.localDateStr(w.end),
      h.GF.localDateStr(new h.window.Date(w.start.getFullYear(), w.start.getMonth(), w.start.getDate() + 6)),
      `week ${w.id} must span exactly 7 days`);
  }
  h.close();
});

test('the current week actually contains the frozen "now"', () => {
  const h = loadGF();
  const { weeks, todayId } = h.GF.calendar;
  const cur = weeks[todayId];
  assert.equal(h.GF.localDateStr(cur.start), '2026-07-27');
  assert.equal(h.GF.localDateStr(cur.end), '2026-08-02');
  assert.equal(h.GF.todayISO() >= h.GF.localDateStr(cur.start), true);
  assert.equal(h.GF.todayISO() <= h.GF.localDateStr(cur.end), true);
  h.close();
});

test('the week window survives a spring-DST week without gaining or losing a day', () => {
  // 2026-03-29 is the Europe/Skopje spring-forward date, and it falls inside
  // this window (weeks[4] is Mar 23-29, weeks[5] starts Mar 30). A generator
  // built on `+7*86400000` instead of setDate() would drift an hour here and
  // eventually roll a Monday back into Sunday.
  const h = loadGF({ now: '2026-03-26T09:15:00+01:00' });
  const weeks = h.GF.calendar.weeks;
  assert.equal(h.GF.localDateStr(weeks[4].start), '2026-03-23');
  assert.equal(h.GF.localDateStr(weeks[5].start), '2026-03-30');
  assert.equal(weeks[5].start.getHours(), 0);
  assert.equal(weeks[5].weekNum, weeks[4].weekNum + 1);
  h.close();
});

test('week labels are "Mon d – Mon d" with an en dash, crossing month boundaries', () => {
  const h = loadGF();
  const weeks = h.GF.calendar.weeks;
  assert.equal(weeks[4].label, 'Jul 27 – Aug 2');   // en dash U+2013, not a hyphen
  assert.equal(weeks[4].short, 'W30');
  assert.equal(weeks[3].label, 'Jul 20 – Jul 26');
  assert.equal(weeks[0].label, 'Jun 29 – Jul 5');
  // monthIndex/year come from the START of the week, which is what the calendar
  // view groups by — a week straddling a month belongs to the earlier month.
  assert.equal(weeks[4].monthIndex, 6);
  assert.equal(weeks[4].year, 2026);
  h.close();
});

test('weekNum is a day-of-year/7 count that deliberately diverges from the ISO week', () => {
  const h = loadGF();
  const weeks = h.GF.calendar.weeks;
  // The formula is ceil((dayOfYear + 1) / 7) against the week's own January 1.
  // For 2026 that is consistently ONE LESS than the ISO-8601 week number:
  // Mon 2026-07-27 is ISO W31 but is labelled W30 here. This number is not
  // cosmetic — it ends up in the export filename and in the CSV/JSON header
  // ("GrowFlow_report_W30_marko.csv"), so it is pinned as the shipped
  // behaviour. It is recorded as a divergence, not endorsed as correct: any
  // change toward real ISO weeks will fail here and should, because it
  // renumbers every previously issued export.
  assert.deepEqual(Array.from(weeks, w => w.weekNum),
    [26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]);
  h.close();
});

test('weekNum restarts against each week\'s own January 1, so it can never reach 53 here', () => {
  // A window spanning the year boundary. 2026 has 53 ISO weeks (2026-12-31 is
  // a Thursday), and the ISO week of Mon 2026-12-28 is W53 — this generator
  // calls it W52 and then restarts at W1 for Mon 2027-01-04. Two consecutive
  // weeks in the SAME array therefore carry numbers 52 and 1, which is exactly
  // the case any consumer sorting or diffing on weekNum has to handle.
  const h = loadGF({ now: '2027-01-14T09:15:00+01:00' });
  const weeks = h.GF.calendar.weeks;
  assert.equal(h.GF.localDateStr(weeks[2].start), '2026-12-28');
  assert.equal(weeks[2].weekNum, 52);
  assert.equal(weeks[2].year, 2026);
  assert.equal(h.GF.localDateStr(weeks[3].start), '2027-01-04');
  assert.equal(weeks[3].weekNum, 1);
  assert.equal(weeks[3].year, 2027);
  assert.equal(weeks.some(w => w.weekNum === 53), false);
  h.close();
});

test('GF.people.initials builds a two-letter monogram from any name shape', () => {
  const h = loadGF();
  const initials = h.GF.people.initials;
  assert.equal(initials('Marko Petrov'), 'MP');
  assert.equal(initials('marko petrov'), 'MP');
  // Only the first TWO words, however many there are.
  assert.equal(initials('Ana Marija Nikolova Stojanovska'), 'AM');
  assert.equal(initials('Marko'), 'M');
  // Collapsed whitespace: split(/\s+/) after trim(), so double spaces and
  // stray tabs do not turn into an empty-string word and then `undefined`.
  assert.equal(initials('  Marko   Petrov  '), 'MP');
  assert.equal(initials('Marko\tPetrov'), 'MP');
  // Bilingual roster: Cyrillic names must uppercase, not be dropped.
  assert.equal(initials('Ана Николова'), 'АН');
  h.close();
});

test('GF.people.initials never returns an empty badge', () => {
  const h = loadGF();
  const initials = h.GF.people.initials;
  // The result is rendered inside a fixed-size circle; an empty string leaves a
  // blank disc, which is why the function ends in `|| '?'`.
  assert.equal(initials(''), '?');
  assert.equal(initials('   '), '?');
  assert.equal(initials(null), '?');
  assert.equal(initials(undefined), '?');
  h.close();
});

/* ── The Sunday off-by-one (regression) ─────────────────────────────────
   Two independent copies of the same mistake, both found by review rather
   than by anyone noticing the app misbehaving.

   A week's `end` was the SEVENTH DAY AT MIDNIGHT, not the end of that day, so
   the `now >= s && now <= e` containment test was false for every instant of
   Sunday except its first millisecond. No week matched, `todayId` kept its
   initial 0, and the app silently opened on the wrong week — all day, every
   Sunday. `end` is also what the date->week lookups in execreport-view.js and
   integrate.js compare against with `d <= w.end`, so they inherited it.
   ──────────────────────────────────────────────────────────────────────── */

test('core.js: on a SUNDAY the generated calendar still selects the current week', () => {
  // Sunday 2026-08-02, mid-afternoon. Anchor Monday is 2026-07-27; the table
  // starts four weeks earlier (2026-06-29), so the current week is index 4.
  const h = loadGF({ now: '2026-08-02T15:00:00+02:00' });
  const cal = h.GF.calendar;

  assert.equal(cal.todayId, 4,
    'Sunday must resolve to the week that contains it, not fall back to index 0');
  assert.equal(h.GF.localDateStr(cal.weeks[cal.todayId].start), '2026-07-27');
  assert.equal(h.GF.localDateStr(cal.weeks[cal.todayId].end), '2026-08-02');
  assert.equal(h.GF.state.selWeek, 4, 'selWeek is seeded from todayId');

  // The precise cause: the end boundary must cover the whole final day.
  const end = cal.weeks[cal.todayId].end;
  assert.ok(end.getHours() === 23 && end.getMinutes() === 59,
    'week.end must be the END of its last day, not that day at 00:00');
  h.close();
});

test('core.js: every day of one week maps to that same week', () => {
  // Walks Mon->Sun so a fix that special-cases Sunday, or shifts the window by
  // a day, cannot pass. Monday is the boundary that a naive `setHours` on the
  // START would break instead.
  // The table is REGENERATED relative to `now` (four weeks back, 14 forward), so
  // the current week is always index 4. The invariant worth pinning is therefore
  // not the index but that the selected week actually CONTAINS the clock's day,
  // measured on the real Date boundaries. Monday and Sunday are the two ends a
  // naive setHours on the wrong side of the range breaks.
  const days = ['2026-07-27', '2026-07-28', '2026-07-29', '2026-07-30',
                '2026-07-31', '2026-08-01', '2026-08-02', '2026-08-03'];
  for (const day of days) {
    for (const clock of ['00:00:00', '12:00:00', '23:59:00']) {
      const h = loadGF({ now: `${day}T${clock}+02:00` });
      const cal = h.GF.calendar;
      const w = cal.weeks[cal.todayId];
      assert.equal(cal.todayId, 4, `${day} ${clock}: current week is always index 4`);
      assert.ok(h.GF.localDateStr(w.start) <= day && day <= h.GF.localDateStr(w.end),
        `${day} ${clock}: selected week ${h.GF.localDateStr(w.start)}..` +
        `${h.GF.localDateStr(w.end)} does not contain it`);
      h.close();
    }
  }
});

test('integrate.js buildCalendar: a bare YYYY-MM-DD end date still covers all of Sunday', () => {
  // This is the path that actually runs in production: buildCalendar REPLACES
  // core.js's generated weeks with the backend's rows. calendar_weeks.ends_on is
  // a DATE column, so the API sends '2026-08-02'; `new Date('2026-08-02')` is
  // parsed as UTC midnight = 02:00 LOCAL at UTC+2. The old code therefore broke
  // from 02:00 every Sunday and fell back to index 0 — and because the rows are
  // re-sorted ASCENDING, index 0 is the OLDEST week in the table, not a recent
  // one. That is the user-visible bug: the app opened on ancient data.
  const h = loadGF({
    now: '2026-08-02T15:00:00+02:00',
    files: ['data.js', 'core.js', 'integrate.js'],
    preScript: PRE_INTEGRATE,
  });

  h.GF.WWF.buildCalendar([
    { id: 'w1', iso_week: 27, starts_on: '2026-06-29', ends_on: '2026-07-05' },
    { id: 'w2', iso_week: 30, starts_on: '2026-07-27', ends_on: '2026-08-02' },
    { id: 'w3', iso_week: 31, starts_on: '2026-08-03', ends_on: '2026-08-09' },
  ]);

  assert.equal(h.GF.calendar.todayId, 1,
    'Sunday 2026-08-02 is inside w2 (index 1); 0 would mean the oldest-week fallback');
  assert.equal(h.GF.calendar.weeks[1].realId, 'w2');
  assert.equal(h.GF.state.selWeek, 1);

  // 02:00 local is the exact instant the UTC-midnight parse used to fail at.
  const h2 = loadGF({
    now: '2026-08-02T02:30:00+02:00',
    files: ['data.js', 'core.js', 'integrate.js'],
    preScript: PRE_INTEGRATE,
  });
  h2.GF.WWF.buildCalendar([
    { id: 'w1', iso_week: 27, starts_on: '2026-06-29', ends_on: '2026-07-05' },
    { id: 'w2', iso_week: 30, starts_on: '2026-07-27', ends_on: '2026-08-02' },
  ]);
  assert.equal(h2.GF.calendar.todayId, 1, '02:30 local on Sunday must still match w2');
  h.close(); h2.close();
});
