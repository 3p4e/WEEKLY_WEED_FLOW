'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/report-view.js — GF.WWF._reportMarkup, the pure task-list markup
   builder behind the Weekly Report / Plan view.

   Regression coverage for two review-round bugs:

   1. d.tasks[].status is the RAW backend status ('ongoing'/'completed'/…),
      never routed through the frontend's S_IN normalization the /tasks
      fetch path applies. GF.STATUS (data.js) only knows pending/working/
      review/stuck/postponed/done, so calling GF.statusLabel directly on the
      raw value rendered the untranslated English DB token instead of a
      proper localized label for the two most common statuses. The fix
      normalizes first, mirroring the reference implementation
      execreport-view.js's xrTasks() already used for the identical
      raw-status shape.

   2. The file used a handful of hardcoded hex literals (close to, but not
      exactly, the real theme tokens) that do not repaint when the app
      switches to the light theme, unlike every sibling view file. The task
      list's status dot/chip is one of those call sites — this also checks
      no raw hex leaks into that markup any more.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// report-view.js assumes GF.WWF/GF.views already exist (integrate.js creates
// them before this file loads in index.html) and calls
// GF.WWF._registerFullPageView + GF.API.pins at load time — stub the minimum
// surface, the same way kpi-badge-rendering.test.js and document-view.test.js
// declare only what the file under test touches on the way up.
const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.render = { all: function () {}, sidebar: function () {} };
  window.GF.API = { user: { id: 'u1' }, pins: function () { return Promise.resolve([]); } };
`;

function loadReportView() {
  return loadGF({ files: ['data.js', 'core.js', 'report-view.js'], preScript: PRE });
}

function baseReportData(tasks) {
  return {
    mode: 'report',
    period: { label: 'Jul 27 – Aug 2', start: '2026-07-27' },
    summary: { total: tasks.length, completed: 0, in_progress: 0, stuck: 0, pending: 0 },
    departments: [],
    task_types: {},
    time_band: null,
    overdue: [],
    tasks,
  };
}

test('task list translates raw backend statuses ("ongoing"/"completed"), not the literal DB token', () => {
  const h = loadReportView();
  const { GF } = h;
  GF.WWF._report.data = baseReportData([
    { id: 't1', title: 'Prune row 4', status: 'ongoing', department: 'Cultivation' },
    { id: 't2', title: 'Log irrigation cycle', status: 'completed', department: 'Irrigation' },
  ]);

  const html = GF.WWF._reportMarkup();

  // The real translated labels (GF.STATUS.working / GF.STATUS.done in en).
  assert.ok(html.includes(GF.statusLabel('working')), 'raw "ongoing" must render as the "Working on it" label');
  assert.ok(html.includes(GF.statusLabel('done')), 'raw "completed" must render as the "Done" label');

  // The untranslated raw DB tokens must not appear as rendered label text.
  assert.equal(/>ongoing</.test(html), false, 'the raw "ongoing" token must not leak into the pill text');
  assert.equal(/>completed</.test(html), false, 'the raw "completed" token must not leak into the pill text');
  h.close();
});

test('task list translates raw statuses in Macedonian too', () => {
  const h = loadReportView();
  const { GF } = h;
  GF.state.lang = 'mk';
  GF.WWF._report.data = baseReportData([
    { id: 't1', title: 'Задача', status: 'ongoing', department: '' },
    { id: 't2', title: 'Друга задача', status: 'completed', department: '' },
  ]);

  const html = GF.WWF._reportMarkup();
  assert.ok(html.includes(GF.STATUS.working.mk), 'raw "ongoing" must render as the MK "Во тек" label');
  assert.ok(html.includes(GF.STATUS.done.mk), 'raw "completed" must render as the MK "Завршено" label');
  h.close();
});

test('already-normalized statuses ("working"/"done"/"stuck") still render their own label unchanged', () => {
  const h = loadReportView();
  const { GF } = h;
  GF.WWF._report.data = baseReportData([
    { id: 't1', title: 'A', status: 'working', department: '' },
    { id: 't2', title: 'B', status: 'done', department: '' },
    { id: 't3', title: 'C', status: 'stuck', department: '' },
  ]);

  const html = GF.WWF._reportMarkup();
  assert.ok(html.includes(GF.statusLabel('working')));
  assert.ok(html.includes(GF.statusLabel('done')));
  assert.ok(html.includes(GF.statusLabel('stuck')));
  h.close();
});

test('an unset/undefined status falls back to "pending", never crashes or renders blank', () => {
  const h = loadReportView();
  const { GF } = h;
  GF.WWF._report.data = baseReportData([{ id: 't1', title: 'No status task', status: undefined, department: '' }]);

  const html = GF.WWF._reportMarkup();
  assert.ok(html.includes(GF.statusLabel('pending')));
  h.close();
});

test('the rendered report carries no hardcoded hex colors — every color is a theme token', () => {
  const h = loadReportView();
  const { GF } = h;
  GF.WWF._report.data = baseReportData([
    { id: 't1', title: 'Prune row 4', status: 'ongoing', department: 'Cultivation' },
    { id: 't2', title: 'Log irrigation cycle', status: 'completed', department: 'Irrigation' },
  ]);
  GF.WWF._report.data.summary = { total: 2, completed: 1, in_progress: 1, stuck: 0, pending: 0, review: 1, postponed: 1 };

  const html = GF.WWF._reportMarkup();
  assert.equal(/#[0-9A-Fa-f]{6}/.test(html), false,
    'no hardcoded hex literal may appear — the light theme cannot repaint what is not a var(--token)');
  assert.ok(html.includes('var(--red)'), 'the Stuck/red semantic must use the theme token');
  h.close();
});

/* ──────────────────────────────────────────────────────────────────────
   3. The boot-time pin prefetch must not fire before authentication.

   report-view.js ends with a module-scope setTimeout(...,0) that calls
   _checkNewReportPin() -> GET /ai/pins, to light the "new AI report" nav
   badge. Unguarded, that runs while the LOGIN screen is showing: there is
   no token yet, so the request can only ever 401 — on every anonymous page
   load, logging a console error before anyone has signed in.

   Caught by driving the real app as ADMIN: /ai/pins?function_key=
   weekly_report&limit=1 was the FIRST request of the session, ahead of
   /auth/login. approvals-view.js's sibling prefetch already guards on
   GF.API.token for exactly this reason (and its comment cites this very
   line as the pattern it mirrors) — this file had never grown the guard.
   ────────────────────────────────────────────────────────────────────── */
test('the boot pin-prefetch is skipped when no token exists (anonymous page load)', async () => {
  const h = loadGF({
    files: ['data.js', 'core.js', 'report-view.js'],
    preScript: `
      window.GF = window.GF || {}; window.GF.views = window.GF.views || {};
      window.GF.WWF = window.GF.WWF || {};
      window.GF.WWF._registerFullPageView = function (s) { window.__reg = s; };
      window.GF.state = { view: 'mywork', lang: 'en' };
      window.GF.render = { all(){}, sidebar(){} };
      window.__pinCalls = 0;
      window.GF.API = { user: null, token: '',
        pins: function () { window.__pinCalls++; return Promise.resolve([]); } };
    `,
  });
  await new Promise((r) => setTimeout(r, 30));   // let the setTimeout(...,0) fire
  assert.equal(h.window.__pinCalls, 0,
    'GET /ai/pins must not be issued on an anonymous (pre-login) page load');
});

test('the boot pin-prefetch still runs when a session token is already present', async () => {
  const h = loadGF({
    files: ['data.js', 'core.js', 'report-view.js'],
    preScript: `
      window.GF = window.GF || {}; window.GF.views = window.GF.views || {};
      window.GF.WWF = window.GF.WWF || {};
      window.GF.WWF._registerFullPageView = function (s) { window.__reg = s; };
      window.GF.state = { view: 'mywork', lang: 'en' };
      window.GF.render = { all(){}, sidebar(){} };
      window.__pinCalls = 0;
      window.GF.API = { user: { role: 'ADMIN' }, token: 'tok123',
        pins: function () { window.__pinCalls++; return Promise.resolve([]); } };
    `,
  });
  await new Promise((r) => setTimeout(r, 30));
  assert.equal(h.window.__pinCalls, 1,
    'a persisted session must still get the new-report badge prefetch');
});
