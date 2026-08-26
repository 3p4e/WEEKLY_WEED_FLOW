'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/views.js — GF.views.dash (production overview) and GF.views.exec
   (executive overview).

   Two independent regressions pinned here:

   1. dash()'s alert-feed onclick interpolates a.id and a.task_id (server
      IDs) straight into an inline `onclick="GF.WWF.openNotif(...)"`
      attribute, unlike the identical pattern in notifications-view.js
      (`onclick="GF.WWF.openNotif('${GF.esc(n.id)}','${GF.esc(n.task_id ||
      '')}')"`). IDs are server-generated UUIDs today, so this was never
      exploitable — but it is the one alert-feed call site that skipped the
      app's single XSS boundary (GF.esc, see escaping.test.js), and a future
      alert source with a less trustworthy id would inherit the gap silently.

   2. exec()'s KPI/matrix/pipeline/attention numbers are hand-built from
      `GF.weekTasks(selWeek).filter(t => !t.archived).filter(execDeptShown)`
      rather than calling GF.execTasks (core.js), even though the two look
      interchangeable. They are NOT interchangeable: GF.execTasks (see its
      own pin in task-filters.test.js, "ignores the sidebar filters and
      honours only the hidden-department set") does not filter archived
      tasks at all. Calling it here would let an archived task leak back
      into the executive KPI/risk numbers. This file pins the CURRENT
      (correct) archived-exclusion behaviour so a future "de-duplication"
      that swaps in GF.execTasks fails loudly instead of quietly leaking
      archived rows into the C-suite screen.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

function loadViews() {
  const h = loadGF({ files: ['data.js', 'core.js', 'views.js'] });
  const { GF } = h;
  GF.state.tasks = [];
  GF.PEOPLE = {};
  return h;
}

test('dash() alert-feed onclick escapes the notification id and task id', () => {
  const h = loadViews();
  const { GF } = h;
  // A hostile-looking id: were it interpolated raw, it would close the
  // single-quoted onclick argument and inject a second call.
  const evilId = "n1'); alert(1); GF.WWF.openNotif('";
  GF.WWF = {
    _notif: {
      loaded: true, unread: 1,
      items: [{ id: evilId, task_id: 't-99', verb: 'assigned', actor_id: null,
                params: { title: 'Swab room 3' }, created_at: new Date().toISOString() }],
    },
  };
  const html = GF.views.dash();

  assert.equal(html.includes(`GF.WWF.openNotif('${evilId}'`), false,
    'the raw, unescaped id must not appear inside the onclick attribute');
  assert.ok(html.includes(`GF.WWF.openNotif('${GF.esc(evilId)}','${GF.esc('t-99')}')`),
    'the escaped id/task_id pair must appear, matching notifications-view.js\'s onclick pattern');
  h.close();
});

test('dash() renders an alert row (no task_id) without adding a stray onclick', () => {
  const h = loadViews();
  const { GF } = h;
  GF.WWF = {
    _notif: {
      loaded: true, unread: 0,
      items: [{ id: 'n2', task_id: null, verb: 'report_locked', params: { kind: 'report' }, created_at: new Date().toISOString() }],
    },
  };
  const html = GF.views.dash();
  assert.ok(html.includes('dash-alert'), 'the alert row still renders');
  assert.equal(html.includes('openNotif'), false, 'no onclick is added when the alert has no task_id to jump to');
  h.close();
});

test('exec() excludes archived tasks from the KPI/blocked/overdue counts', () => {
  const h = loadViews();
  const { GF } = h;
  const wk = GF.calendar.todayId;
  GF.state.tasks = [
    { id: 'T-live', title: 'Live stuck task', weekId: wk, dept: 'qc', status: 'stuck', due: '2020-01-01', archived: false, owner: 'u1', helpers: [] },
    { id: 'T-arch', title: 'Archived stuck task', weekId: wk, dept: 'qc', status: 'stuck', due: '2020-01-01', archived: true, owner: 'u1', helpers: [] },
  ];
  const html = GF.views.exec();

  // Blocked KPI tile: exactly 1 (the live task), never 2.
  assert.match(html, /ekpi-v" style="color:var\(--red\)">1<\/div>\s*<div class="ekpi-l">Blocked/,
    'the Blocked KPI must count only the live task, not the archived one');
  // The archived task's own title must not surface in the "Needs attention" list.
  assert.equal(html.includes('Archived stuck task'), false,
    'an archived task must not appear in the needs-attention risk zone');
  assert.ok(html.includes('Live stuck task'), 'the live (non-archived) stuck task must still appear');
  h.close();
});
