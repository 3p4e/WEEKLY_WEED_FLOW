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
  // The real GF.selectField renders a HIDDEN input and GF.pickSel assigns .value
  // directly — it fires NO change event, so onPick is the only hook that runs.
  // The cfg is recorded so a test can drive that callback, which is the only way
  // to catch a regression back to addEventListener('change').
  w.__selCfg = {};
  w.GF.selectField = (id, cfg) => {
    w.__selCfg[id] = cfg;
    return '<input type="hidden" id="' + id + '" value="' + (cfg.value || '') + '">';
  };
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

/* ── Corridor cleaning cadence (§25, migration 0049) ───────────────────────
   A log answers "was it cleaned"; the plan asks "often enough, and after the
   events that demanded it". So what is pinned here is the panel's negative
   cases: a corridor never cleaned reads as OVERDUE rather than blank, the
   interval comes from the SERVER rather than being recomputed here, and a waste
   movement with nothing cleaned after it is named by manifest — a count alone
   would not say which movement went unswept.
   ──────────────────────────────────────────────────────────────────────── */

const COR = (over = {}) => ({
  room_id: 'r1', code: 'c146', name: 'Corridor · C146', name_mk: 'Коридор · C146',
  last_cleaned: '2026-07-30T09:00:00Z', minutes_since: 15, cleanings: 4,
  overdue: false, ...over,
});

function renderCorridors(h, payload) {
  h.window.GF.WWF._decon.cycles = [];
  h.window.GF.WWF._decon.corridors = payload;
  h.window.GF.state.view = 'decon';
  return h.window.GF.views.decon();
}

test('a corridor never cleaned reads as OVERDUE, not as a blank row', () => {
  const h = load('CU_MGR');
  const html = renderCorridors(h, {
    interval_minutes: 240,
    corridors: [COR({ last_cleaned: null, minutes_since: null, cleanings: 0, overdue: true })],
    movements_without_cleaning: [],
  });
  assert.match(html, /never/, 'the absence of a record must be stated, not left empty');
  assert.match(html, /1 of 1 corridors are past the 4-hour interval/);
  h.close();
});

test('the interval comes from the server, not a second copy in the view', () => {
  // If the view hardcoded 4 hours, a server that changed the rule would be
  // silently overruled by the board.
  const h = load('CU_MGR');
  const html = renderCorridors(h, {
    interval_minutes: 120,
    corridors: [COR({ overdue: true, minutes_since: 200 })],
    movements_without_cleaning: [],
  });
  assert.match(html, /past the 2-hour interval/);
  assert.doesNotMatch(html, /4-hour/);
  h.close();
});

test('overdue is taken from the server flag, not recomputed from the minutes', () => {
  // Deliberately inconsistent input: 500 minutes but overdue false. The view must
  // follow the server, because the server owns the rule — and it must do so in
  // EVERY place it renders the state, not just the summary line. A first version
  // of this test only checked the banner, so a mutation that recomputed the row
  // colour client-side survived.
  const h = load('CU_MGR');
  let html = renderCorridors(h, {
    interval_minutes: 240,
    corridors: [COR({ minutes_since: 500, overdue: false })],
    movements_without_cleaning: [],
  });
  assert.match(html, /All 1 corridors are inside/, 'the summary follows the flag');
  assert.match(html, /background:#2BE8A0/, 'and so does the row dot');
  assert.doesNotMatch(html, /background:#E5484D/);
  assert.doesNotMatch(html, /rgba\(229,72,77,\.06\)/, 'and the row highlight');

  // The inverse: 5 minutes but overdue true. Nothing may quietly overrule it.
  html = renderCorridors(h, {
    interval_minutes: 240,
    corridors: [COR({ minutes_since: 5, overdue: true })],
    movements_without_cleaning: [],
  });
  assert.match(html, /1 of 1 corridors are past/);
  assert.match(html, /background:#E5484D/);
  assert.match(html, /rgba\(229,72,77,\.06\)/);
  h.close();
});

test('minutes are rendered as hours and minutes, not a raw count', () => {
  const h = load('CU_MGR');
  const html = renderCorridors(h, {
    interval_minutes: 240,
    corridors: [COR({ minutes_since: 265, overdue: true })],
    movements_without_cleaning: [],
  });
  assert.match(html, /4h 25m/, '"265 minutes" is not how a 4-hourly round is thought about');
  h.close();
});

test('a waste movement with no cleaning after it is named by manifest', () => {
  const h = load('CU_MGR');
  const html = renderCorridors(h, {
    interval_minutes: 240,
    corridors: [COR()],
    movements_without_cleaning: [
      { manifest_id: 'm1', manifest_code: 'WM-2026-0731-01', disposed_at: '2026-07-31T14:20:00Z' },
      { manifest_id: 'm2', manifest_code: 'WM-2026-0731-02', disposed_at: '2026-07-31T16:05:00Z' },
    ],
  });
  assert.match(html, /2 waste movement\(s\) left the site with no corridor cleaning/);
  assert.match(html, /WM-2026-0731-01/);
  assert.match(html, /WM-2026-0731-02/, 'each movement is listed — a count would not say which');
  h.close();
});

test('the corridor panel renders even with no room cycles', () => {
  // The cadence runs throughout the campaign, including before the first room
  // cycle is started and after the last is released.
  const h = load('CU_MGR');
  const html = renderCorridors(h, {
    interval_minutes: 240, corridors: [COR({ overdue: true })], movements_without_cleaning: [],
  });
  assert.match(html, /Corridor cleaning cadence/);
  assert.match(html, /No room cycles yet/, 'and the empty-cycles message still shows');
  h.close();
});

test('a reader sees the cadence and is offered no clean button', () => {
  const h = load('QC_MGR');
  const html = renderCorridors(h, {
    interval_minutes: 240, corridors: [COR()], movements_without_cleaning: [],
  });
  assert.match(html, /Corridor cleaning cadence/, 'the cadence is readable by any elevated role');
  assert.doesNotMatch(html, /deconCorridorForm/, 'recording a clean is a cleaning-crew action');
  h.close();
});

test('corridor names are HTML-escaped', () => {
  const h = load('CU_MGR');
  const html = renderCorridors(h, {
    interval_minutes: 240,
    corridors: [COR({ name: '<img src=x onerror=alert(1)>' })],
    movements_without_cleaning: [
      { manifest_id: 'm1', manifest_code: '"><script>bad()</script>', disposed_at: 'x' }],
  });
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<script>bad\(\)/);
  assert.match(html, /&lt;img src=x/);
  h.close();
});

test('no corridors in the register means no panel, rather than an empty card', () => {
  const h = load('CU_MGR');
  const html = renderCorridors(h, {
    interval_minutes: 240, corridors: [], movements_without_cleaning: [] });
  assert.doesNotMatch(html, /Corridor cleaning cadence/);
  h.close();
});

test('a waste-movement clean is refused without its manifest, before the request', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.API.wasteManifests = async () => ({ manifests: [] });
  w.GF.API.deconCorridorClean = async (b) => { w.__cor = b; return {}; };
  return w.GF.WWF.deconCorridorForm('r1').then(async () => {
    w.document.getElementById('dc-cor-trigger').value = 'waste_movement';
    w.document.getElementById('dc-cor-manifest').value = '';
    await w.GF.WWF.deconCorridorSave('r1');
    assert.equal(w.__cor, undefined,
      '"after every waste movement" cannot be discharged by a clean citing no movement');
    assert.ok(w.__toasts.some(t => /waste movement/i.test(t[0])));
    h.close();
  });
});

test('the manifest hint flips to required through onPick, the only hook that fires', () => {
  // GF.selectField renders a HIDDEN input and GF.pickSel assigns .value directly,
  // firing no change event. A change listener here would never run.
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.API.wasteManifests = async () => ({ manifests: [] });
  return w.GF.WWF.deconCorridorForm('r1').then(() => {
    const hint = w.document.getElementById('dc-cor-man-hint');
    assert.match(hint.textContent, /Optional/);
    w.__selCfg['dc-cor-trigger'].onPick('waste_movement');
    assert.match(hint.textContent, /Required/);
    h.close();
  });
});

test('a clean sends the trigger and a null strip reading when blank', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.API.wasteManifests = async () => ({ manifests: [] });
  w.GF.API.deconCorridorClean = async (b) => { w.__cor = b; return {}; };
  return w.GF.WWF.deconCorridorForm('r1').then(async () => {
    w.document.getElementById('dc-cor-trigger').value = 'shift_change';
    w.document.getElementById('dc-cor-ppm').value = '';
    await w.GF.WWF.deconCorridorSave('r1');
    assert.equal(w.__cor.room_id, 'r1');
    assert.equal(w.__cor.trigger, 'shift_change');
    assert.equal(w.__cor.manifest_id, null);
    assert.equal(w.__cor.ppm_strip_reading, null, 'a blank reading is null, not NaN');
    // cleaned_at is never sent — the server stamps it, so a backdated clean
    // cannot satisfy the cadence on paper.
    assert.equal('cleaned_at' in w.__cor, false);
    h.close();
  });
});

test('the form warns that the time is server-stamped', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.API.wasteManifests = async () => ({ manifests: [] });
  return w.GF.WWF.deconCorridorForm('r1').then(() => {
    const body = w.document.getElementById('dc-cor-modal-body').innerHTML;
    assert.match(body, /stamped by the server/);
    h.close();
  });
});

test('a corridor-endpoint failure degrades to no panel, it does not fail the board', async () => {
  // The cadence endpoint is newer than the cycles endpoint, so a frontend
  // deployed ahead of its backend gets a 404 here. With a bare Promise.all that
  // rejected the whole load and replaced the WORKING room-cycle board with an
  // error page — a new panel taking out an existing board.
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.API.deconCycles = async () => ({ cycles: [{
    id: 'c1', room_id: 'r1', room_name: 'Flowering 1.1', campaign: 'hlvd-2026-07',
    status: 'in_progress', started_on: '2026-07-30', released_at: null,
    steps: { dry_clean: null, detergent_wash: null, rinse1_whitecloth: null,
             bleach: null, rinse2: null },
    swabs: { pending: 0, negative: 0, positive: 0, inconclusive: 0 } }] });
  w.GF.API.deconCorridors = async () => { throw new Error('404 Not Found'); };
  await w.GF.WWF.loadDecon();
  assert.equal(w.GF.WWF._decon.error, null, 'the board must not go to an error state');
  assert.equal(w.GF.WWF._decon.cycles.length, 1, 'the cycles still load');
  w.GF.state.view = 'decon';
  const html = w.GF.views.decon();
  assert.match(html, /Flowering 1\.1/, 'the room cycle still renders');
  assert.doesNotMatch(html, /Corridor cleaning cadence/, 'and the panel is simply absent');
  h.close();
});

test('a reader calling the corridor form directly is refused', async () => {
  const h = loadForms('QC_MGR');
  await h.window.GF.WWF.deconCorridorForm('r1');
  assert.ok(!h.window.__modals.includes('dc-cor-modal'),
    'hiding the button is not the gate — the handler checks too');
  h.close();
});
