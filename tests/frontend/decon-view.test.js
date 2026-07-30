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

/* ── The modal data-entry layer (replaced prompt()/confirm()) ──────────────
   The white-cloth check and the QA release each got their own modal. The
   white-cloth one matters most: with confirm(), "Cancel" recorded a FAILED
   check, so anyone dismissing the dialog — or expecting Cancel to mean "abort,
   I mis-tapped" — wrote a failure into a GxP record. There is no safe default,
   so the operator must pick one of two explicit buttons and dismissing writes
   nothing.
   ──────────────────────────────────────────────────────────────────────── */

// The forms call GF.WWF._ensureModal / GF.openModal / GF.$ / GF.t / GF.once /
// GF.selectField. These are stubbed AFTER the sources load, not via preScript:
// core.js defines its own openModal/closeModal, so a preScript stub would be
// overwritten by the real thing and every assertion here would pass vacuously.
function loadForms(role) {
  const h = loadGF({
    files: ['data.js', 'core.js', 'decon-view.js'],
    preScript: PRE_DECON,
  });
  const w = h.window;
  if (role) w.GF.API.user = { role };
  w.__modals = []; w.__closed = []; w.__toasts = [];
  // core.js defines GF.toast too — stub it here, after load, for the same
  // reason as openModal above.
  w.GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  w.GF.WWF._ensureModal = function (id) {
    if (w.document.getElementById(id)) return;
    const wrap = w.document.createElement('div');
    wrap.id = id;
    wrap.innerHTML = '<div id="' + id + '-title"></div><div id="' + id + '-body"></div>';
    w.document.body.appendChild(wrap);
  };
  w.GF.openModal = (id) => { w.__modals.push(id); };
  w.GF.closeModal = (id) => { w.__closed.push(id); };
  w.GF.t = (k) => k;
  w.GF.selectField = (id, cfg) =>
    '<input type="hidden" id="' + id + '" value="' + (cfg.value || '') + '">';
  // GF.once wraps every submit for re-entry safety; here it just runs the body.
  w.GF.once = async (btnId, fn) => fn();
  w.GF.API.deconStep       = async (cid, body) => { w.__step = [cid, body]; return {}; };
  w.GF.API.deconSwabResult = async (id, body)  => { w.__res  = [id, body];  return {}; };
  w.GF.API.deconRelease    = async (id, body)  => { w.__rel  = [id, body];  return {}; };
  w.GF.API.deconCycles     = async () => ({ cycles: [] });
  return h;
}

test('signing the white-cloth step opens a modal instead of submitting straight away', async () => {
  const h = loadForms('CU_MGR');
  await h.window.GF.WWF.deconSignStep('c1', 'rinse1_whitecloth');
  assert.equal(h.window.__step, undefined,
    'the gate step must NOT be submitted without an explicit pass/fail choice');
  assert.ok(h.window.__modals.includes('dc-wc-modal'), 'the white-cloth modal must open');
  h.close();
});

test('the white-cloth modal offers BOTH outcomes explicitly', () => {
  const h = loadForms('CU_MGR');
  h.window.GF.WWF.deconWhiteClothForm('c1');
  const body = h.window.document.getElementById('dc-wc-modal-body').innerHTML;
  assert.match(body, /deconWhiteClothSave\('c1', true\)/,  'a PASS button must exist');
  assert.match(body, /deconWhiteClothSave\('c1', false\)/, 'a SOILED button must exist');
  h.close();
});

test('each white-cloth outcome submits that exact verdict', async () => {
  for (const verdict of [true, false]) {
    const h = loadForms('CU_MGR');
    h.window.GF.WWF.deconWhiteClothForm('c1');
    await h.window.GF.WWF.deconWhiteClothSave('c1', verdict);
    const [cid, body] = h.window.__step;
    assert.equal(cid, 'c1');
    assert.equal(body.step, 'rinse1_whitecloth');
    assert.equal(body.passed, verdict, `passed must be ${verdict}, verbatim`);
    h.close();
  }
});

test('a non-gate step still submits directly, with no passed flag', async () => {
  const h = loadForms('CU_MGR');
  await h.window.GF.WWF.deconSignStep('c1', 'dry_clean');
  const [, body] = h.window.__step;
  assert.equal(body.step, 'dry_clean');
  assert.equal('passed' in body, false, 'only the white-cloth step carries a verdict');
  h.close();
});

test('a POSITIVE swab result is refused without a stated action', async () => {
  // The plan's action-on-positive is immediate re-clean and re-test; a positive
  // recorded with no action is an incomplete record.
  const h = loadForms('QA_MGR');
  h.window.GF.WWF.deconSwabResultForm('s1', 'RR-01-001');
  h.window.document.getElementById('dc-res-val').value = 'positive';
  h.window.document.getElementById('dc-res-action').value = '';
  await h.window.GF.WWF.deconSwabResultSave('s1');
  assert.equal(h.window.__res, undefined, 'a positive with no action must not be submitted');
  assert.ok((h.window.__toasts || []).some(t => /action/i.test(t[0])));
  h.close();
});

test('a POSITIVE swab result with an action is submitted, Ct included', async () => {
  const h = loadForms('QA_MGR');
  h.window.GF.WWF.deconSwabResultForm('s1', 'RR-01-001');
  h.window.document.getElementById('dc-res-val').value = 'positive';
  h.window.document.getElementById('dc-res-ct').value = '28.4';
  h.window.document.getElementById('dc-res-action').value = 're-clean and re-test';
  await h.window.GF.WWF.deconSwabResultSave('s1');
  const [id, body] = h.window.__res;
  assert.equal(id, 's1');
  assert.equal(body.result, 'positive');
  assert.equal(body.ct_value, 28.4);
  assert.equal(body.action_taken, 're-clean and re-test');
  h.close();
});

test('a NEGATIVE result needs no action, and an empty Ct is sent as null', async () => {
  const h = loadForms('QA_MGR');
  h.window.GF.WWF.deconSwabResultForm('s2', 'RR-01-002');
  h.window.document.getElementById('dc-res-val').value = 'negative';
  await h.window.GF.WWF.deconSwabResultSave('s2');
  const [, body] = h.window.__res;
  assert.equal(body.result, 'negative');
  assert.equal(body.ct_value, null, 'a blank Ct must be null, not NaN');
  h.close();
});

test('the release modal requires an explicit button and sends the note', async () => {
  const h = loadForms('QA_MGR');
  h.window.GF.WWF.deconRelease('c9');
  assert.ok(h.window.__modals.includes('dc-rel-modal'));
  assert.equal(h.window.__rel, undefined, 'opening the modal must not release anything');
  h.window.document.getElementById('dc-rel-note').value = 'swabs negative, HVAC confirmed';
  await h.window.GF.WWF.deconReleaseSave('c9');
  const [id, body] = h.window.__rel;
  assert.equal(id, 'c9');
  assert.equal(body.release_note, 'swabs negative, HVAC confirmed');
  h.close();
});

test('the cleaning crew cannot open the release or swab-result forms', () => {
  const h = loadForms('CU_MGR');
  h.window.GF.WWF.deconRelease('c9');
  h.window.GF.WWF.deconSwabResultForm('s1', 'RR-01-001');
  assert.equal(h.window.__modals.length, 0,
    'role gating must hold on the form entry points, not only on the buttons');
  h.close();
});

test('swab results are reachable whenever swabs exist, so pending is not a dead number', () => {
  const h = loadForms('QA_MGR');
  const html = renderCycle(h, CYCLE({
    status: 'awaiting_verification',
    swabs: { pending: 2, negative: 0, positive: 0, inconclusive: 0 },
  }));
  assert.match(html, /deconSwabList\('r1','c1'\)/,
    'a pending swab must be openable for result entry');
  h.close();
});
