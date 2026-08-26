'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/execreport-view.js — GF.WWF.xrStatusChips, the status-pill
   renderer shared by the Executive Report board and document-view.js's
   lifecycle strip.

   Regression coverage: XR_STATUS_STYLE used to hardcode the chip's
   background and border as raw rgba() hex-derived literals
   (`rgba(255,77,94,.12)` / `rgba(255,77,94,.3)` for "missing", etc.) instead
   of the theme's CSS custom properties — a lower-impact sibling of the
   report-view.js finding that file's SC/SC_BG maps already fixed (see
   report-view.test.js). A hardcoded literal does not repaint when the app
   switches to the light theme (or a Mass Weed skin), unlike every other
   status chip in the app. The fix maps bg/fg/bd to the matching
   var(--red-soft)/var(--red-fg)/etc. tokens.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// execreport-view.js declares its own GF.WWF/GF.views (`GF.WWF = GF.WWF ||
// {}`) but calls GF.WWF._registerFullPageView unconditionally at load time —
// stub the minimum surface, the same way report-view.test.js does for its
// sibling full-page view.
const PRE = `
  window.GF = window.GF || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.API = { user: { id: 'u1', role: 'OWNER' } };
`;

function loadExecReport() {
  return loadGF({ files: ['data.js', 'core.js', 'execreport-view.js'], preScript: PRE });
}

test('status chips use theme CSS custom properties, not hardcoded hex/rgba literals', () => {
  const h = loadExecReport();
  const { GF } = h;
  const html = GF.WWF.xrStatusChips({
    org_wide: { status: 'locked', updated_at: '2026-07-01T10:00:00Z' },
    departments: [
      { id: 'qc', status: 'missing', updated_at: null },
      { id: 'prod', status: 'draft', updated_at: null },
    ],
  });

  assert.equal(/#[0-9a-fA-F]{3,6}/.test(html), false, 'no hardcoded hex color literal anywhere in the chip markup');
  assert.equal(html.includes('rgba('), false, 'no hardcoded rgba() literal — bg/bd must be var(--x-soft) tokens');

  assert.ok(html.includes('background:var(--red-soft)') && html.includes('color:var(--red-fg)'),
    'the "missing" chip must use the red-soft/red-fg tokens');
  assert.ok(html.includes('background:var(--amber-soft)') && html.includes('color:var(--amber-fg)'),
    'the "draft" chip must use the amber-soft/amber-fg tokens');
  assert.ok(html.includes('background:var(--primary-soft)') && html.includes('color:var(--primary)'),
    'the "locked" chip must use the primary-soft/primary tokens');
  h.close();
});

test('an unrecognized/absent status falls back to the "missing" style, still token-based', () => {
  const h = loadExecReport();
  const { GF } = h;
  const html = GF.WWF.xrStatusChips({ org_wide: { status: 'not_a_real_status', updated_at: null }, departments: [] });
  assert.ok(html.includes('background:var(--red-soft)'), 'an unknown status defaults to the missing/red style');
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(html), false);
  h.close();
});
