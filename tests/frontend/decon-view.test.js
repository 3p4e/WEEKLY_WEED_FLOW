'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/decon-view.js — the decontamination board's client-side gates.

   The server owns the real rules (migration 0046 + app/api/decon.py) and
   answers 409 when they are broken. This view ALSO predicts them, to decide
   which button to offer and to explain on screen why a room cannot be
   released. Two copies of one rule is exactly how a rule drifts, so the
   predictions are pinned here against the same cases the backend suite pins
   in tests/test_decon.py:

     - nextStep() must send a FAILED white-cloth check back to detergent_wash
       ("soiled cloth -> wash again; the bleach does not go on"), not forward
       to bleach.
     - the release predicate must refuse a pending OR positive OR inconclusive
       swab, and refuse a cycle with zero swabs ("no room is released on a
       pending result", and never on zero verification).

   The view is an IIFE that registers onto window.GF, so these tests exercise
   it the way index.html loads it, then reach the predicates through the
   rendered output — the same real source, no logic copied.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// decon-view.js calls GF.WWF._registerFullPageView at load and uses AL(),
// GF.icon, GF.esc, GF.viewHead. data.js + core.js supply esc/icon/state/AL;
// the rest are declared here so loading the real file does not throw.
const PRE_DECON = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
  window.GF.render = { all: function () {} };
  window.GF.toast = function (m, k) { (window.__toasts = window.__toasts || []).push([m, k]); };
  window.GF.viewHead = function (a, b, extra) { return '<head>' + (extra || '') + '</head>'; };
  window.GF.API = { user: { role: 'CU_MGR' } };
`;

function load(role) {
  const h = loadGF({
    files: ['data.js', 'core.js', 'decon-view.js'],
    preScript: PRE_DECON,
  });
  if (role) h.window.GF.API.user = { role };
  return h;
}

// Render one cycle through the REAL view and hand back the HTML, so what is
// asserted is what an operator would actually see.
function renderCycle(h, cyc) {
  h.window.GF.WWF._decon.cycles = [cyc];
  h.window.GF.state.view = 'decon';
  return h.window.GF.views.decon();
}

const CYCLE = (over = {}) => ({
  id: 'c1', room_id: 'r1', room_name: 'Flowering 1.1', campaign: 'hlvd-2026-07',
  status: 'in_progress', started_on: '2026-07-30', released_at: null,
  steps: { dry_clean: null, detergent_wash: null, rinse1_whitecloth: null,
           bleach: null, rinse2: null },
  swabs: { pending: 0, negative: 0, positive: 0, inconclusive: 0 },
  ...over,
});

const signed = (passed) => ({ passed, signed_at: '2026-07-30T08:00:00Z', note: null });

test('the view registers itself with the decon key and a read gate above base USER', () => {
  const h = load();
  const spec = h.window.__reg;
  assert.equal(spec.key, 'decon');
  h.window.GF.API.user = { role: 'USER' };
  assert.equal(spec.guard(), false, 'base USER must not see the decon board');
  h.window.GF.API.user = { role: 'QC_MGR' };
  assert.equal(spec.guard(), true, 'any elevated role may READ the record');
  h.window.GF.API.user = { role: null };
  assert.equal(spec.guard(), false, 'a logged-out/roleless session must not see it');
  h.close();
});

test('a soiled white-cloth check offers detergent_wash again, never bleach', () => {
  const h = load('CU_MGR');
  const html = renderCycle(h, CYCLE({
    steps: { dry_clean: signed(null), detergent_wash: signed(null),
             rinse1_whitecloth: signed(false), bleach: null, rinse2: null },
  }));
  // The offered action must be the re-wash, and bleach must NOT be offered.
  assert.match(html, /deconSignStep\('c1','detergent_wash'\)/,
    'a failed white-cloth check must send the crew back to the detergent wash');
  assert.doesNotMatch(html, /deconSignStep\('c1','bleach'\)/,
    'bleach must never be offered while the white-cloth gate has not passed');
  // And the failure is visible on the step row, in the plan's own words.
  assert.match(html, /soiled, wash again/);
  h.close();
});

test('a passing white-cloth check is what unlocks bleach', () => {
  const h = load('CU_MGR');
  const html = renderCycle(h, CYCLE({
    steps: { dry_clean: signed(null), detergent_wash: signed(null),
             rinse1_whitecloth: signed(true), bleach: null, rinse2: null },
  }));
  assert.match(html, /deconSignStep\('c1','bleach'\)/);
  h.close();
});

test('steps are offered strictly in order from the start of the cycle', () => {
  const h = load('CU_MGR');
  const html = renderCycle(h, CYCLE());
  assert.match(html, /deconSignStep\('c1','dry_clean'\)/);
  assert.doesNotMatch(html, /deconSignStep\('c1','detergent_wash'\)/);
  assert.doesNotMatch(html, /deconSignStep\('c1','rinse2'\)/);
  h.close();
});

test('release is not offered while the cycle is still in progress', () => {
  const h = load('QA_MGR');
  const html = renderCycle(h, CYCLE({ swabs: { pending: 0, negative: 3, positive: 0, inconclusive: 0 } }));
  assert.doesNotMatch(html, /deconRelease/);
  assert.match(html, /cycle not complete/);
  h.close();
});

test('release is refused on a pending, positive or inconclusive swab', () => {
  for (const blocking of ['pending', 'positive', 'inconclusive']) {
    const h = load('QA_MGR');
    const swabs = { pending: 0, negative: 2, positive: 0, inconclusive: 0 };
    swabs[blocking] = 1;
    const html = renderCycle(h, CYCLE({ status: 'awaiting_verification', swabs }));
    assert.doesNotMatch(html, /deconRelease/,
      `release must not be offered with a ${blocking} swab on file`);
    assert.match(html, /not negative/);
    h.close();
  }
});

test('release is refused when no swab exists at all — never on zero verification', () => {
  const h = load('QA_MGR');
  const html = renderCycle(h, CYCLE({ status: 'awaiting_verification' }));
  assert.doesNotMatch(html, /deconRelease/);
  assert.match(html, /no swab on file/);
  h.close();
});

test('release is offered only on a complete cycle with every swab negative', () => {
  const h = load('QA_MGR');
  const html = renderCycle(h, CYCLE({
    status: 'awaiting_verification',
    swabs: { pending: 0, negative: 4, positive: 0, inconclusive: 0 },
  }));
  assert.match(html, /deconRelease\('c1'\)/);
  h.close();
});

test('the cleaning crew is never offered the release button', () => {
  // "A room is released by the QA Manager ... Nobody else can release a room."
  const h = load('CU_MGR');
  const html = renderCycle(h, CYCLE({
    status: 'awaiting_verification',
    swabs: { pending: 0, negative: 4, positive: 0, inconclusive: 0 },
  }));
  assert.doesNotMatch(html, /deconRelease/,
    'CU_MGR may clean but must never be offered the QA release decision');
  assert.doesNotMatch(html, /deconSwabForm/, 'swabs are a QA function');
  h.close();
});

test('QA is not offered cleaning-crew step signing', () => {
  const h = load('QA_MGR');
  const html = renderCycle(h, CYCLE());
  assert.doesNotMatch(html, /deconSignStep/);
  assert.match(html, /deconSwabForm/);
  h.close();
});

test('a released cycle offers neither step signing nor a second release', () => {
  const h = load('QA_MGR');
  const html = renderCycle(h, CYCLE({
    status: 'released', released_at: '2026-08-03T10:00:00Z',
    steps: { dry_clean: signed(null), detergent_wash: signed(null),
             rinse1_whitecloth: signed(true), bleach: signed(null), rinse2: signed(null) },
    swabs: { pending: 0, negative: 4, positive: 0, inconclusive: 0 },
  }));
  assert.doesNotMatch(html, /deconRelease/);
  assert.doesNotMatch(html, /deconSignStep/);
  assert.match(html, /Released/);
  h.close();
});

test('room names and campaign ids are HTML-escaped', () => {
  // Room names come from the facility registry, which an ADMIN types; the
  // campaign id is free text. Both land in innerHTML.
  const h = load('CU_MGR');
  const html = renderCycle(h, CYCLE({
    room_name: '<img src=x onerror=alert(1)>', campaign: '"><script>bad()</script>',
  }));
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<script>bad\(\)/);
  assert.match(html, /&lt;img src=x/);
  h.close();
});
