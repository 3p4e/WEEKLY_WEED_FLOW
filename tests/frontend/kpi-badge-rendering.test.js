'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/analytics-view.js + web/gf/auditprep-view.js — KPI-tile badges.

   Regression coverage for the bug where GF.kpiTile started escaping its
   `sub` argument (see escaping.test.js), but three call sites here still
   built a raw `<span style="color:...">...</span>` string and passed it as
   `sub`, expecting it to render as live markup. Once GF.esc ran on it, the
   tile showed the literal escaped tag text instead of a colored badge — a
   common, everyday state (any non-zero overdue/missing count), not an edge
   case. The fix moved the coloring inside GF.kpiTile via a `subTone`
   keyword; these tests render the REAL call sites (not just the helper in
   isolation — see escaping.test.js for that) to prove the fix actually
   reaches the dashboards.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
  window.GF.render = { all: function () {} };
  window.GF.viewHead = function () { return ''; };
  window.GF.API = { user: { role: 'MANAGER' } };
`;

function loadAnalytics() {
  return loadGF({ files: ['data.js', 'core.js', 'analytics-view.js'], preScript: PRE });
}

function loadAuditPrep() {
  return loadGF({ files: ['data.js', 'core.js', 'auditprep-view.js'], preScript: PRE });
}

test('analytics "Open tasks now" tile renders a real overdue badge, not escaped markup', () => {
  const h = loadAnalytics();
  h.window.GF.WWF._ana = {
    loading: false, error: null, weeks: 8,
    data: {
      weeks: [{ week_start: '2026-07-20', created: 6, completed: 5, on_time: 4, active_people: 3, sessions: 5 }],
      departments: [{ name: 'Cultivation', open: 4, overdue: 3, stuck: 0 }],
      task_types: [],
      range: { weeks: 8 },
    },
  };
  // Yield band pre-satisfied (empty, no dried lots) so it doesn't try to fetch.
  h.window.GF.WWF._anaY = { loading: false, error: null, data: { harvests: [] } };

  const html = h.window.GF.views.analytics();
  assert.equal(html.includes('&lt;span'), false, 'sub-line is not escaped-away markup');
  assert.equal(html.includes('<span style'), false, 'no raw inline-styled span leaked from the call site');
  assert.ok(/3\s*overdue/i.test(html), 'the overdue count is visible text');
  assert.equal(html.includes('ana-ts--bad'), true, 'the sub-line gets the red/bad badge class');
  h.close();
});

test('analytics "Open tasks now" tile has no colored sub-line when nothing is overdue', () => {
  const h = loadAnalytics();
  h.window.GF.WWF._ana = {
    loading: false, error: null, weeks: 8,
    data: {
      weeks: [{ week_start: '2026-07-20', created: 6, completed: 5, on_time: 4, active_people: 3, sessions: 5 }],
      departments: [{ name: 'Cultivation', open: 4, overdue: 0, stuck: 0 }],
      task_types: [],
      range: { weeks: 8 },
    },
  };
  h.window.GF.WWF._anaY = { loading: false, error: null, data: { harvests: [] } };

  const html = h.window.GF.views.analytics();
  assert.equal(html.includes('ana-ts--bad'), false);
  assert.equal(html.includes('&lt;span'), false);
  h.close();
});

test('auditprep "Audit-prep tasks" and "Outcome traceability" tiles render real badges, not escaped markup', () => {
  const h = loadAuditPrep();
  h.window.GF.WWF._ap = {
    loading: false, error: null,
    data: {
      programs: [{ program: 'MK-GMP', total: 10, completed: 6, overdue: 2, ongoing: 1, stuck: 0, pending: 3 }],
      traceability: { completed: 6, with_outcome: 4, without_outcome: 2, rate: 4 / 6 },
      busiest_day: { day: 'Mon', count: 3 },
      timeline: [],
    },
  };

  const html = h.window.GF.views.auditprep();
  assert.equal(html.includes('&lt;span'), false, 'sub-line is not escaped-away markup');
  assert.equal(html.includes('<span style="color:var(--red-fg'), false, 'no raw red span from the call site');
  assert.equal(html.includes('<span style="color:var(--orange)'), false, 'no raw orange span from the call site');
  assert.ok(/2\s*overdue/i.test(html), 'overdue count is visible text');
  assert.ok(/2\s*missing outcome/i.test(html), 'missing-outcome count is visible text');
  assert.equal(html.includes('ana-ts--bad'), true, 'overdue sub-line gets the red/bad badge class');
  assert.equal(html.includes('ana-ts--warn'), true, 'missing-outcome sub-line gets the amber/warn badge class');
  h.close();
});

test('auditprep tiles have no colored sub-line when there is nothing to flag', () => {
  const h = loadAuditPrep();
  h.window.GF.WWF._ap = {
    loading: false, error: null,
    data: {
      programs: [{ program: 'MK-GMP', total: 10, completed: 10, overdue: 0, ongoing: 0, stuck: 0, pending: 0 }],
      traceability: { completed: 6, with_outcome: 6, without_outcome: 0, rate: 1 },
      busiest_day: null,
      timeline: [],
    },
  };

  const html = h.window.GF.views.auditprep();
  assert.equal(html.includes('ana-ts--bad'), false);
  assert.equal(html.includes('ana-ts--warn'), false);
  assert.equal(html.includes('&lt;span'), false);
  h.close();
});

/* ══════════════════════════════════════════════════════════════════════
   Wave 3 LOW fixes — analytics-view.js / auditprep-view.js.

   Bug 1: GF.views.analytics()/auditprep() dereferenced d.weeks, d.departments,
   d.task_types, d.programs, d.timeline (and fields on their items) with no
   fallback, so a malformed-but-200 /reports/analytics or /reports/audit-prep
   response (a field missing, null, or of the wrong shape) threw a TypeError
   out of the render function and blanked the whole view instead of showing
   the view's own dash/zero/empty state. Fixed with `?.`/`?? `/Array.isArray
   guards at every one of those sites; these tests render with a deliberately
   malformed response and assert the view still renders instead of throwing.

   Bug 2 (analytics only): the "Moisture loss" KPI ((wetDried - dryTotalG) /
   wetDried * 100) was not floored at 0, so a dry weight recorded greater than
   the wet weight (an upstream data-entry error) showed a negative percentage
   on a metric that can only ever be a loss. Fixed with Math.max(0, ...).
   ════════════════════════════════════════════════════════════════════ */

test('analytics view does not throw on a malformed API response and shows dash/empty fallbacks (bug 1)', () => {
  const h = loadAnalytics();
  h.window.GF.WWF._ana = {
    loading: false, error: null, weeks: 8,
    // Every top-level field the view reads is absent, and the arrays that
    // are present carry null/incomplete entries — the shape a backend bug
    // or a bad JSON payload could plausibly still return with a 200.
    data: {},
  };
  h.window.GF.WWF._anaY = { loading: false, error: null, data: { harvests: [] } };

  let html;
  assert.doesNotThrow(() => { html = h.window.GF.views.analytics(); }, 'a malformed response must not throw out of the render function');
  assert.equal(typeof html, 'string');
  assert.ok(html.includes('No tasks here yet.'), 'missing departments/task_types degrade to the empty-state note');
  assert.ok(html.includes('>0<') || html.includes('>—<'), 'KPIs fall back to 0/dash instead of crashing before rendering them');
  h.close();
});

test('analytics view tolerates null/partial entries inside otherwise-present weeks/departments/task_types arrays (bug 1)', () => {
  const h = loadAnalytics();
  h.window.GF.WWF._ana = {
    loading: false, error: null, weeks: 8,
    data: {
      weeks: [null, { week_start: '2026-07-20' }],   // missing created/completed/on_time
      departments: [null, { name: 'QC' }],            // missing open/overdue/stuck
      task_types: [null, { task_type: 'watering' }],  // missing count
      // range omitted entirely — falls back to st.weeks
    },
  };
  h.window.GF.WWF._anaY = { loading: false, error: null, data: { harvests: [] } };

  let html;
  assert.doesNotThrow(() => { html = h.window.GF.views.analytics(); });
  assert.ok(/8\s*w/.test(html), 'missing d.range.weeks falls back to the requested st.weeks range');
  h.close();
});

test('auditprep view does not throw on a malformed API response and shows dash/empty fallbacks (bug 1/bug 3)', () => {
  const h = loadAuditPrep();
  h.window.GF.WWF._ap = {
    loading: false, error: null,
    // Missing programs/timeline/traceability entirely, plus a null entry
    // inside programs once it is present in a later case below.
    data: {},
  };

  let html;
  assert.doesNotThrow(() => { html = h.window.GF.views.auditprep(); }, 'a malformed response must not throw out of the render function');
  assert.equal(typeof html, 'string');
  assert.ok(html.includes('—'), 'readiness/traceability KPIs fall back to a dash instead of crashing before rendering them');
  h.close();
});

test('auditprep view tolerates a null entry inside an otherwise-present programs array (bug 3)', () => {
  const h = loadAuditPrep();
  h.window.GF.WWF._ap = {
    loading: false, error: null,
    data: {
      programs: [null, { program: 'MK-GMP', total: 10, completed: 6, overdue: 2 }],
      traceability: { completed: 6, with_outcome: 4, without_outcome: 2, rate: 4 / 6 },
      busiest_day: null,
      timeline: [null, { title: 'x', status: 'ongoing' }],   // missing due_date
    },
  };

  let html;
  assert.doesNotThrow(() => { html = h.window.GF.views.auditprep(); });
  assert.ok(html.includes('MK-GMP'), 'the well-formed sibling entry still renders normally');
  h.close();
});

test('analytics "Moisture loss" KPI is floored at 0, never negative, when dry weight exceeds wet weight (bug 2)', () => {
  const h = loadAnalytics();
  h.window.GF.WWF._ana = {
    loading: false, error: null, weeks: 8,
    data: {
      weeks: [{ week_start: '2026-07-20', created: 6, completed: 5, on_time: 4, active_people: 3, sessions: 5 }],
      departments: [], task_types: [], range: { weeks: 8 },
    },
  };
  // Data-entry error upstream: dry_flower_g alone already exceeds wet_weight_g,
  // which would compute to (100 - 150) / 100 * 100 = -50% without the floor.
  h.window.GF.WWF._anaY = {
    loading: false, error: null,
    data: { harvests: [{
      id: 'h1', batch_code: 'B1', cultivar_code: 'C1', room_name: 'R1', status: 'closed',
      dried_on: '2026-07-18', wet_weight_g: 100, dry_flower_g: 150, dry_trim_g: 0, dry_waste_g: 0,
      plants_harvested: 10,
    }] },
  };

  const html = h.window.GF.views.analytics();
  assert.equal(html.includes('-50'), false, 'moisture loss must never render as negative');
  assert.ok(html.includes('0.0%'), 'the clamped value (0%) is what actually renders');
  h.close();
});
