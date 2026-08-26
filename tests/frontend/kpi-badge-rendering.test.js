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
