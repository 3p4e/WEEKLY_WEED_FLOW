'use strict';

/* ══════════════════════════════════════════════════════════════════════
   Every printed instant is rendered in the FACILITY zone — review
   2026-09-27, FE-05.

   The backend serialises timestamptz in UTC. Views printed that string as
   it came (`slice(0,16).replace('T',' ')`, `slice(11,16)`, or the browser's
   toLocaleString), so every clock in the app read 1–2 hours early in Skopje:
   a session typed 08:00 listed back as 06:00, e-signature and custody times
   two hours off, and the inbox grouping a 00:30 item under "Yesterday"
   because its UTC day was the day before.

   core.js's GF.fmtDateTime / fmtTime / fmtDate are the one way to print an
   instant. These tests pin them in the facility zone, drive two real views
   through them, and guard the retired patterns out of the files this fix
   owns. The harness clock is Thu 2026-07-30 09:15 Europe/Skopje (UTC+2).
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF, GF_DIR } = require('./helpers/gf-window.js');

const SKOPJE = { facility_tz: 'Europe/Skopje' };

test('fmtDateTime / fmtTime / fmtDate render a UTC stamp in the facility zone', () => {
  const h = loadGF({ files: ['data.js', 'core.js'] });
  const GF = h.GF;
  GF.API = { user: SKOPJE };
  assert.equal(GF.fmtDateTime('2026-07-30T12:00:00+00:00'), '2026-07-30 14:00', 'CEST is UTC+2');
  assert.equal(GF.fmtTime('2026-07-30T12:00:00Z'), '14:00');
  assert.equal(GF.fmtDateTime('2026-01-15T12:00:00Z'), '2026-01-15 13:00', 'CET is UTC+1');
  // A stamp with no offset is UTC (asyncpg's isoformat of a UTC-aware value
  // always carries one; a bare one must never be read as local).
  assert.equal(GF.fmtDateTime('2026-07-30T12:00:00'), '2026-07-30 14:00');
  // The day of the instant, in the facility zone: 22:30 UTC on the 29th is
  // already the 30th in Skopje.
  assert.equal(GF.fmtDate('2026-07-29T22:30:00Z'), '2026-07-30');
  assert.equal(GF.fmtDate('2026-07-30'), '2026-07-30', 'a bare date is returned as it is');
  assert.equal(GF.fmtDateTime(''), '');
  assert.equal(GF.fmtDateTime(null), '');
  // A bare date is a day, not an instant: printed as it is, with no time
  // (a date-only certificate result used to read "2026-07-30 02:00" — R2-FE-16).
  assert.equal(GF.fmtDateTime('2026-07-30'), '2026-07-30');
  assert.equal(GF.fmtTime('2026-07-30'), '');
  assert.equal(GF.fmtDate('2026-07-30'), '2026-07-30');
  h.close();
});

test('the reader\'s browser zone does not leak into a printed instant', () => {
  // A manager reading from UTC+14 must still see the facility's clock.
  const h = loadGF({ files: ['data.js', 'core.js'] });
  h.GF.API = { user: { facility_tz: 'Pacific/Kiritimati' } };
  assert.equal(h.GF.fmtDateTime('2026-07-30T12:00:00Z'), '2026-07-31 02:00');
  h.close();
});

/* ── The inbox: row time and day grouping ─────────────────────────────── */
const PRE_NOTIF = `
  window.setInterval = function () { return 0; };
  window.setTimeout = function () { return 0; };
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.PEOPLE = { u1: { name: 'Ana' } };
  window.GF.icon = function () { return ''; };
  window.GF.avatar = function () { return ''; };
  window.GF.state = { user: 'me', lang: 'en' };
  window.GF.API = { token: 'tok', user: { id: 'me', facility_tz: 'Europe/Skopje' } };
  window.GF.render = { all: function () {}, sidebar: function () {} };
  window.GF.viewHead = function () { return ''; };
`;

test('inbox rows print the facility time and group by the facility day', () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'notifications-view.js'], preScript: PRE_NOTIF });
  const w = h.window;
  // core.js re-creates GF.state at load (from localStorage), so the session
  // user is set AFTER the sources ran, or the view sees a user mismatch and
  // resets the inbox to its loading state.
  w.GF.state.user = 'me';
  const st = w.GF.WWF._notif;
  st.loaded = true; st.user = 'me';
  st.items = [
    // 12:00 UTC today → 14:00 facility, Today
    { id: 'n1', verb: 'created', actor_id: 'u1', params: { title: 'A' }, reason: 'status', read: true, created_at: '2026-07-30T12:00:00+00:00' },
    // 22:30 UTC on the 29th → 00:30 on the 30th in Skopje: still TODAY.
    { id: 'n2', verb: 'created', actor_id: 'u1', params: { title: 'B' }, reason: 'status', read: true, created_at: '2026-07-29T22:30:00+00:00' },
    // 23:00 UTC on the 28th → 01:00 on the 29th: Yesterday.
    { id: 'n3', verb: 'created', actor_id: 'u1', params: { title: 'C' }, reason: 'status', read: true, created_at: '2026-07-28T23:00:00+00:00' },
  ];
  const html = w.GF.views.inbox();
  assert.match(html, /<span class="ntf-ts">14:00<\/span>/, 'the row time is the facility clock');
  assert.match(html, /<span class="ntf-ts">00:30<\/span>/);
  const days = [...html.matchAll(/<div class="ntf-day">([^<]*)<\/div>/g)].map(m => m[1]);
  assert.deepEqual(days, ['Today', 'Yesterday'],
    'the 00:30 item belongs to today; a UTC-day grouping would have opened a Yesterday group before it');
  h.close();
});

/* ── The decon board: signed-step times ───────────────────────────────── */
test('a signed decon step shows the facility time, not the UTC stamp', () => {
  const PRE = `
    window.GF = window.GF || {};
    window.GF.views = window.GF.views || {};
    window.GF.WWF = window.GF.WWF || {};
    window.GF.WWF._registerFullPageView = function () {};
    window.GF.render = { all: function () {} };
    window.GF.viewHead = function () { return ''; };
    window.GF.API = { user: { role: 'CU_MGR', facility_tz: 'Europe/Skopje' } };
  `;
  const h = loadGF({ files: ['data.js', 'core.js', 'decon-view.js'], preScript: PRE });
  const w = h.window;
  w.GF.WWF._decon.cycles = [{
    id: 'c1', room_id: 'r1', room_name: 'Flowering 1.1', campaign: 'hlvd', status: 'in_progress',
    started_on: '2026-07-30', released_at: null,
    steps: { dry_clean: { passed: null, signed_at: '2026-07-30T06:05:00+00:00' } },
    swabs: {},
  }];
  w.GF.state.view = 'decon';
  const html = w.GF.views.decon();
  assert.match(html, /2026-07-30 08:05/, 'signed at 06:05 UTC is 08:05 on the facility clock');
  assert.doesNotMatch(html, /06:05/);
  h.close();
});

/* ── The rule, over the files this fix owns ───────────────────────────
   Files the product-catalogue workstream owns are listed as theirs; the
   cultivation, propagation, harvest, irrigation and facility views were
   converted in the second fix round (R2-FE-02) and are guarded here like
   every other file. core.js keeps the raw slice only as fmtDateTime's
   last-resort fallback for an engine without Intl. */
const OTHER_WORKSTREAMS = new Set([
  'qcpotency-view.js', 'qccoa-view.js',
]);
const RETIRED = /slice\(0, ?16\)\.replace\('T', ?' '\)|replace\('T', ?' '\)\.slice\(0, ?16\)|\.toLocaleString\(\)|toLocaleTimeString\(|created_at\.slice\(11, ?16\)/;

test('no owned view prints an instant by slicing the UTC string or via the browser locale', () => {
  const offenders = [];
  for (const f of fs.readdirSync(GF_DIR).filter(n => n.endsWith('.js'))) {
    if (OTHER_WORKSTREAMS.has(f) || f === 'core.js') continue;
    fs.readFileSync(path.join(GF_DIR, f), 'utf8').split('\n').forEach((line, i) => {
      // Number formatting (`(1.5).toLocaleString()`) is not a timestamp.
      if (RETIRED.test(line) && !/Math\.round\([^)]*\)\s*\/\s*100\)\.toLocaleString/.test(line)) {
        offenders.push(`${f}:${i + 1}: ${line.trim()}`);
      }
    });
  }
  assert.deepEqual(offenders, [], 'timestamp printed outside GF.fmtDateTime:\n' + offenders.join('\n'));
});
