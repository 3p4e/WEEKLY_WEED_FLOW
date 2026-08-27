'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/workload-view.js — GF.views.workload, crew capacity for the
   selected week.

   Regression coverage: the "every known person renders, even with zero
   load" seeding step used to run over ALL of GF.PEOPLE, including
   deactivated/removed accounts — unlike views.js's team() and dash()'s
   crewN computation, which both explicitly filter with
   `.filter(id => !GF.PEOPLE[id].inactive)`. That meant:
     - an inactive person still showed up as a workload row AND a live
       drag-and-drop assignment target, and
     - they still counted in `people.length` for the KPI band, diluting the
       average load and inflating the "Available" count.
   The fix applies the identical `.filter(id => !GF.PEOPLE[id].inactive)`.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// workload-view.js calls GF.viewHead (views.js) and GF.avatar (render.js) —
// neither is loaded here, so both are stubbed to a no-op the same way
// kpi-badge-rendering.test.js stubs GF.viewHead for an unrelated view file.
const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.viewHead = function () { return ''; };
  window.GF.avatar = function () { return ''; };
`;

function loadWorkload() {
  const h = loadGF({ files: ['data.js', 'core.js', 'workload-view.js'], preScript: PRE });
  const { GF } = h;
  GF.PEOPLE = {
    u1: { name: 'Marko Petrov', roleLabel: 'Operator' },
    u2: { name: 'Ana Ivanova', roleLabel: 'Operator' },
    u3: { name: 'Zoran Deactivated', roleLabel: 'Operator', inactive: true },
  };
  // A single open (non-done) task this week, owned solely by u1, critical
  // priority (weight 3) → u1.pts = 3, rawPct = 3/12*100 = 25%. u2 has no
  // tasks at all → pts = 0, rawPct = 0%. u3 is inactive and has no tasks —
  // if the seeding bug were present they'd still show up as a third,
  // zero-load row and shift kAvg/kFree.
  // weekId must match core.js's load-time `GF.state.selWeek = GF.calendar.todayId`
  // (not a bare 0) — GF.weekTasks/scopedTasks filter on t.weekId === selWeek.
  const wk = GF.calendar.todayId;
  GF.state.tasks = [
    { id: 't1', weekId: wk, parentId: null, owner: 'u1', helpers: [], status: 'working', pr: 'critical', title: 'Critical task', days: [] },
  ];
  return h;
}

test('an inactive person does not get a workload row or drop target', () => {
  const h = loadWorkload();
  const { GF } = h;
  const html = GF.views.workload();

  assert.ok(html.includes('Marko Petrov'), 'the active owner must have a row');
  assert.ok(html.includes('Ana Ivanova'), 'an active person with zero load must still render as a drop target');
  assert.equal(html.includes('Zoran Deactivated'), false, 'a deactivated person must not render a row at all');
  assert.equal(html.includes('u3'), false, 'a deactivated person\'s id must not appear anywhere (e.g. as a drop-target ondrop id)');
  h.close();
});

test('an inactive person is excluded from the KPI averages (Available / Avg Load)', () => {
  const h = loadWorkload();
  const { GF } = h;
  const html = GF.views.workload();

  // Only u1 (25%) and u2 (0%) may count: avg = (25+0)/2 = 12.5 -> rounds to 13,
  // both are under 70% so kFree = 2. If u3 (inactive, 0%) were wrongly
  // included the average would be (25+0+0)/3 = 8.33 -> 8, and kFree would be 3.
  const avgMatch = html.match(/Avg Load[\s\S]{0,80}?ana-tv[^>]*>(\d+)%</);
  assert.ok(avgMatch, 'Avg Load tile must be present');
  assert.equal(avgMatch[1], '13', 'avg load must be computed over active people only (2), not all 3');

  const freeMatch = html.match(/Available[\s\S]{0,80}?ana-tv[^>]*>(\d+)</);
  assert.ok(freeMatch, 'Available tile must be present');
  assert.equal(freeMatch[1], '2', '"Available" must count only the 2 active people, not the inactive one too');
  h.close();
});

test('an inactive person who IS actually assigned to a task still shows (only the zero-load seeding is filtered)', () => {
  const h = loadWorkload();
  const { GF } = h;
  // u3 is inactive but was left assigned to a real task from before they were
  // deactivated — the fix only strips the "every known person" zero-load
  // seed, it must not hide someone with real, already-assigned work.
  GF.state.tasks.push({ id: 't2', weekId: GF.calendar.todayId, parentId: null, owner: 'u3', helpers: [], status: 'working', pr: 'low', title: 'Legacy task', days: [] });

  const html = GF.views.workload();
  assert.ok(html.includes('Zoran Deactivated'), 'a real, existing assignment for an inactive person must still render');
  h.close();
});

test('the Macedonian capacity hint no longer claims estimated hours take precedence', () => {
  const h = loadWorkload();
  const { GF } = h;
  GF.state.lang = 'mk';
  const html = GF.views.workload();
  assert.equal(html.includes('проценетите часови имаат предност'), false,
    'load() is purely priority-weighted (t.est is never read) — the MK hint must not claim otherwise');
  h.close();
});
