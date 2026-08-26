'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/myday-view.js — GF.views.myday, the personal "today" screen.

   Regression coverage for doneToday(): a completed task used to be treated
   as "completed today" whenever completed_date was missing at all
   (`completed_date ? completed_date === todayISO() : true`), not only when
   it genuinely matched today. A task that finished days ago but never had a
   completed_date recorded (a data-quality gap, or an older import) would
   permanently show up under "Completed earlier" on My Day. The fix drops
   the fallback: a done task with no completed_date belongs in neither the
   "open" bucket (status is done) nor the "done today" bucket (no date match)
   — it is excluded from the today view entirely, the same "no date → not
   today" convention isToday() already applies to a task with no `due`.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF, FROZEN_LOCAL_ISO } = require('./helpers/gf-window.js');

// myday-view.js assumes GF.WWF/GF.views already exist and calls
// GF.WWF._registerFullPageView at load time, plus fires an async
// GF.API.approvalsPending() the first time GF.views.myday() runs — stub the
// minimum surface, the same way report-view.test.js does for its sibling
// full-page view.
const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.render = { all: function () {} };
  window.GF.API = { user: { id: 'u1' }, approvalsPending: function () { return Promise.resolve({ mine: [] }); } };
  // GF.progress is render.js's, not loaded here — row() calls it to decide
  // whether to show a progress percentage; a simple stand-in is enough.
  window.GF.progress = function (t) { return t.progressPct || 0; };
`;

function loadMyday() {
  const h = loadGF({ files: ['data.js', 'core.js', 'myday-view.js'], preScript: PRE });
  const { GF } = h;
  GF.PEOPLE = { u1: { name: 'Marko Petrov', role: 'operator' } };
  GF.state.user = 'u1';
  // The frozen clock (helpers/gf-window.js) is 2026-07-30, a Thursday.
  GF.state.tasks = [];
  return h;
}

// weekId must match core.js's load-time `GF.state.selWeek = GF.calendar.todayId`
// (not a bare 0) — GF.weekTasks (myTasks() here) filters on t.weekId === that
// id, same gotcha workload-view.test.js documents.
function baseTask(GF, over) {
  return Object.assign({
    id: 'T-1', title: 'Trim batch P160012', dept: 'prod', owner: 'u1', helpers: [],
    status: 'done', pr: 'medium', days: ['Thu'], weekId: GF.calendar.todayId,
  }, over || {});
}

test('a done task with NO completed_date is excluded from today\'s done bucket, not defaulted into it', () => {
  const h = loadMyday();
  const { GF } = h;
  GF.state.tasks = [baseTask(GF, { completed_date: undefined })];
  const html = GF.views.myday();

  assert.equal(html.includes('Trim batch P160012'), false,
    'a done task with no completed_date must not surface anywhere on My Day (neither open — it is done — nor done-today — no date match)');
  h.close();
});

test('a done task WITH completed_date === today renders under "Completed earlier"', () => {
  const h = loadMyday();
  const { GF } = h;
  assert.equal(GF.todayISO(), '2026-07-30', 'sanity: frozen clock is 2026-07-30 (' + FROZEN_LOCAL_ISO + ')');
  GF.state.tasks = [baseTask(GF, { id: 'T-2', title: 'Calibrate pH meter', completed_date: '2026-07-30' })];
  const html = GF.views.myday();

  assert.ok(html.includes('Calibrate pH meter'), 'a task genuinely completed today must still render');
  h.close();
});

test('a done task completed on an earlier day (not today) is still excluded — unaffected by the fix', () => {
  const h = loadMyday();
  const { GF } = h;
  GF.state.tasks = [baseTask(GF, { id: 'T-3', title: 'Old finished job', completed_date: '2026-07-20' })];
  const html = GF.views.myday();

  assert.equal(html.includes('Old finished job'), false,
    'a task completed on a different day must not appear under today\'s completed group');
  h.close();
});

test('an open (not-done) task scheduled for today still renders, unaffected by doneToday', () => {
  const h = loadMyday();
  const { GF } = h;
  GF.state.tasks = [baseTask(GF, { id: 'T-4', title: 'Swab room 3', status: 'working', completed_date: undefined })];
  const html = GF.views.myday();

  assert.ok(html.includes('Swab room 3'), 'an open task for today must still appear in the Today list');
  h.close();
});
