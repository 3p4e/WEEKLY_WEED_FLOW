'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/waste-view.js — the destruction register's client-side behaviour.

   The server (migration 0048 + app/api/waste.py) owns the four gates and
   answers 409 when they are broken. This view predicts the ladder to decide
   which single action to offer, and two copies of one rule is how a rule
   drifts, so each prediction here has a named counterpart in
   backend/tests/test_waste.py:

     - EXACTLY ONE LADDER ACTION per manifest, the next rung. Offering two at
       once would invite reaching past a step the server refuses anyway, and
       would make an ordered ladder look like independent checkboxes.
     - THE WITNESS BUTTON IS QA-ONLY and the seal/dispose buttons are
       recorder-only, so the two-person rule is visible in the UI and not only
       in a 409 after the fact.
     - A SEALED MANIFEST OFFERS NO LINE EDITS. Sealing is what the witness
       signs against; a contents list that still has a delete button after the
       seal misrepresents that.
     - AN EMPTY DRAFT SAYS WHY IT CANNOT PROGRESS, because an empty manifest is
       the one state with no forward path.
     - A DISPOSAL WITHOUT A CARRIER REFERENCE is refused before the request: the
       entire value of that rung is that it points at someone else's document.

   The view is an IIFE that registers onto window.GF, so these tests load it
   the way index.html does and reach the predicates through rendered output.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE_WASTE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
  window.GF.render = { all: function () {} };
  window.GF.viewHead = function (a, b, extra) { return '<head>' + (extra || '') + '</head>'; };
  window.GF.API = { user: { role: 'CU_MGR' } };
`;

function load(role) {
  const h = loadGF({
    files: ['data.js', 'core.js', 'waste-view.js'],
    preScript: PRE_WASTE,
  });
  if (role) h.window.GF.API.user = { role };
  return h;
}

function renderManifests(h, manifests) {
  h.window.GF.WWF._waste.tab = 'manifests';
  h.window.GF.WWF._waste.manifests = manifests;
  h.window.GF.state.view = 'waste';
  return h.window.GF.views.waste();
}

function renderRecon(h, batches) {
  h.window.GF.WWF._waste.tab = 'recon';
  h.window.GF.WWF._waste.recon = batches;
  h.window.GF.state.view = 'waste';
  return h.window.GF.views.waste();
}

const MAN = (over = {}) => ({
  id: 'm1', manifest_code: 'WM-2026-0731-01', waste_type: 'plant_material',
  reason: 'hlvd_eradication', status: 'draft', campaign: 'hlvd-2026-07',
  origin_room_id: 'r1', origin_room_name: 'Flowering 1.1 · C180 · Room 1',
  destination: 'Licensed incinerator', carrier_name: null, carrier_ref: null,
  gross_weight_kg: null, weighed_at: null, weighed_by: null, sealed_at: null,
  witnessed_at: null, witnessed_by: null, disposed_at: null, note: null,
  line_count: 3, plant_qty_total: 1200, weight_kg_total: 2100,
  ...over,
});

const RECON = (over = {}) => ({
  batch_id: 'b1', code: 'GP072501', phase: 'flower', cultivar_code: 'Bisamber',
  room_name: 'Flowering 1.1', plant_count: 2000, plants_materialised: 2000,
  plants_active: 2000, declared_destroyed: 0, disposed_destroyed: 0,
  unaccounted: 2000, unmanifested_destruction: false, over_declared: false,
  ...over,
});

/* ── registration ───────────────────────────────────────────────────────── */

test('the view registers under the waste key with a read gate above base USER', () => {
  const h = load();
  const spec = h.window.__reg;
  assert.equal(spec.key, 'waste');
  assert.equal(spec.insertBefore, 'mywork',
    'anchored on a key render.sidebar itself emits, so nav order does not depend on script order');
  h.window.GF.API.user = { role: 'USER' };
  assert.equal(spec.guard(), false, 'base USER must not see the destruction register');
  h.window.GF.API.user = { role: 'QC_MGR' };
  assert.equal(spec.guard(), true, 'any elevated role may READ the register');
  h.window.GF.API.user = { role: null };
  assert.equal(spec.guard(), false);
  h.close();
});

/* ── exactly one ladder action, and it is the next rung ──────────────────── */

const LADDER = [
  ['draft',     'wasteSealForm',     ['wasteWitnessForm', 'wasteDisposeForm'], 'CU_MGR'],
  ['sealed',    'wasteWitnessForm',  ['wasteSealForm', 'wasteDisposeForm'],    'QA_MGR'],
  ['witnessed', 'wasteDisposeForm',  ['wasteSealForm', 'wasteWitnessForm'],    'CU_MGR'],
];

for (const [status, expected, forbidden, role] of LADDER) {
  test(`a ${status} manifest offers ONLY ${expected}`, () => {
    const h = load(role);
    const html = renderManifests(h, [MAN({
      status,
      sealed_at: status === 'draft' ? null : '2026-07-31T09:00:00Z',
      gross_weight_kg: status === 'draft' ? null : 2100,
      witnessed_at: status === 'witnessed' ? '2026-07-31T10:00:00Z' : null,
    })]);
    assert.match(html, new RegExp(expected + "\\('m1'\\)"));
    for (const f of forbidden) {
      assert.doesNotMatch(html, new RegExp(f),
        `a ${status} manifest must not offer ${f} — the ladder is ordered`);
    }
    h.close();
  });
}

test('a disposed manifest offers no ladder action at all', () => {
  const h = load('ADMIN');
  const html = renderManifests(h, [MAN({
    status: 'disposed', sealed_at: '2026-07-31T09:00:00Z', gross_weight_kg: 2100,
    witnessed_at: '2026-07-31T10:00:00Z', disposed_at: '2026-07-31T11:00:00Z',
    carrier_ref: 'CARRIER-2026-0731-004', carrier_name: 'Licensed incinerator',
  })]);
  for (const f of ['wasteSealForm', 'wasteWitnessForm', 'wasteDisposeForm']) {
    assert.doesNotMatch(html, new RegExp(f), `a closed chain must not offer ${f}`);
  }
  assert.match(html, /CARRIER-2026-0731-004/, 'the carrier reference is the closing evidence');
  h.close();
});

/* ── the two-person rule, visible in the UI ──────────────────────────────── */

test('the cultivation crew is never offered the witness button', () => {
  const h = load('CU_MGR');
  const html = renderManifests(h, [MAN({
    status: 'sealed', sealed_at: '2026-07-31T09:00:00Z', gross_weight_kg: 2100,
  })]);
  assert.doesNotMatch(html, /wasteWitnessForm/,
    'whoever loads and weighs must not be offered the witness signature');
  // And it says what the load is waiting for, rather than showing a dead card.
  assert.match(html, /waiting on a QA witness/);
  h.close();
});

test('QA is not offered the recorder actions', () => {
  const h = load('QA_MGR');
  let html = renderManifests(h, [MAN({ status: 'draft' })]);
  assert.doesNotMatch(html, /wasteSealForm/, 'sealing is a recorder action');
  assert.doesNotMatch(html, /wasteManifestForm/, 'so is opening a manifest');
  html = renderManifests(h, [MAN({
    status: 'witnessed', sealed_at: '2026-07-31T09:00:00Z', gross_weight_kg: 1,
    witnessed_at: '2026-07-31T10:00:00Z',
  })]);
  assert.doesNotMatch(html, /wasteDisposeForm/, 'and so is closing out the carrier reference');
  assert.match(html, /waiting on the carrier reference/);
  h.close();
});

test('a reader sees the register and none of the actions', () => {
  const h = load('QC_MGR');
  const html = renderManifests(h, [MAN()]);
  assert.match(html, /WM-2026-0731-01/, 'an elevated reader must see the manifest');
  assert.match(html, /wasteDetail/, 'and may open its contents');
  for (const f of ['wasteSealForm', 'wasteWitnessForm', 'wasteDisposeForm', 'wasteManifestForm']) {
    assert.doesNotMatch(html, new RegExp(f), `a reader must not be offered ${f}`);
  }
  h.close();
});

/* ── the empty draft, which has no forward path ──────────────────────────── */

test('an empty draft says why it cannot progress', () => {
  const h = load('CU_MGR');
  const html = renderManifests(h, [MAN({ line_count: 0, plant_qty_total: 0, weight_kg_total: 0 })]);
  assert.match(html, /cannot be sealed until you add what is in the load/);
  h.close();
});

test('sealing an empty manifest is stopped before the request and opens its contents', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.API.wasteManifest = async () => MAN({ line_count: 0, plant_qty_total: 0, weight_kg_total: 0 });
  return w.GF.WWF.wasteSealForm('m1').then(() => {
    assert.equal(w.__sealed, undefined, 'no seal request may be made for an empty load');
    assert.ok(!w.__modals.includes('wa-seal-modal'), 'and the seal modal must not open');
    assert.ok(w.__modals.includes('wa-detail-modal'),
      'the operator is taken to the contents, which is the only way forward');
    h.close();
  });
});

/* ── escaping ───────────────────────────────────────────────────────────── */

test('manifest codes, room names and carrier references are HTML-escaped', () => {
  const h = load('CU_MGR');
  const html = renderManifests(h, [MAN({
    manifest_code: '<img src=x onerror=alert(1)>',
    origin_room_name: '"><script>bad()</script>',
    campaign: '<svg onload=alert(2)>',
    status: 'disposed', sealed_at: 'x', gross_weight_kg: 1, witnessed_at: 'y',
    disposed_at: 'z', carrier_ref: '<b>ref</b>', carrier_name: '<i>who</i>',
  })]);
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<script>bad\(\)/);
  assert.doesNotMatch(html, /<svg onload/);
  assert.doesNotMatch(html, /<b>ref<\/b>/);
  assert.match(html, /&lt;img src=x/);
  h.close();
});

/* ── the reconciliation report ───────────────────────────────────────────── */

test('a batch closed as destroyed with nothing manifested is flagged', () => {
  const h = load('QA_MGR');
  const html = renderRecon(h, [RECON({
    code: 'GP-GHOST', phase: 'destroyed', plant_count: 50,
    declared_destroyed: 0, unaccounted: 50, unmanifested_destruction: true,
  })]);
  assert.match(html, /destroyed, not manifested/);
  assert.match(html, /1 of 1 destroyed batch\(es\) do not reconcile/);
  assert.match(html, /material left with no record of where it went/);
  h.close();
});

test('a destroyed batch only PARTLY manifested is flagged too, not just a zero', () => {
  // The manifests exist but do not cover the batch: 30 of 100 plants have a
  // record of leaving and 70 do not. Reporting only the all-or-nothing case
  // would let this through as "has a manifest, therefore fine".
  const h = load('QA_MGR');
  const html = renderRecon(h, [RECON({
    code: 'GP-PART', phase: 'destroyed', plant_count: 100,
    declared_destroyed: 30, unaccounted: 70,
  })]);
  assert.match(html, /only 30 of 100 manifested/);
  assert.match(html, /1 of 1 destroyed batch\(es\) do not reconcile/);
  h.close();
});

test('an over-declared batch is flagged, whatever phase it is in', () => {
  const h = load('QA_MGR');
  const html = renderRecon(h, [
    RECON({ code: 'GP-OVER', phase: 'flower', declared_destroyed: 2500,
            plant_count: 2000, unaccounted: 0, over_declared: true }),
  ]);
  assert.match(html, /OVER-DECLARED/);
  assert.match(html, /1 of 0 destroyed batch\(es\) do not reconcile/);
  h.close();
});

// THE REGRESSION THIS PINS: `unaccounted` from the API is planned minus declared
// destroyed, which for a live batch is the WHOLE batch. Rendering that as "2000
// unaccounted" on every healthy row buries the few that are genuinely wrong,
// which is the only thing this report is for.
test('a live batch with no destruction is not reported as a discrepancy', () => {
  const h = load('QA_MGR');
  const html = renderRecon(h, [
    RECON({ code: 'GP-LIVE', phase: 'flower', plant_count: 2000,
            declared_destroyed: 0, unaccounted: 2000 }),
  ]);
  assert.doesNotMatch(html, /2000 unaccounted/,
    'a batch still in the room is not missing');
  assert.doesNotMatch(html, /do not reconcile/);
  assert.match(html, /in production/);
  // And the row shows culls-to-date rather than a planned-total denominator.
  assert.doesNotMatch(html, /0\/2000/);
  h.close();
});

test('a harvested batch is not reported as a discrepancy either', () => {
  const h = load('QA_MGR');
  const html = renderRecon(h, [
    RECON({ code: 'GP-HARV', phase: 'harvested', plant_count: 1800,
            declared_destroyed: 12, unaccounted: 1788 }),
  ]);
  assert.doesNotMatch(html, /do not reconcile/);
  assert.match(html, /harvested/);
  assert.match(html, /12 <span[^>]*>culled/, 'the 12 culls are the useful number here');
  h.close();
});

test('a fully reconciled register says so rather than showing nothing', () => {
  const h = load('QA_MGR');
  const html = renderRecon(h, [
    RECON({ code: 'GP-OK', phase: 'destroyed', plant_count: 100,
            declared_destroyed: 100, disposed_destroyed: 100, unaccounted: 0 }),
  ]);
  assert.match(html, /All 1 destroyed batch\(es\) are covered by manifests/);
  assert.match(html, /balanced/);
  assert.doesNotMatch(html, /do not reconcile/);
  h.close();
});

test('a register with nothing destroyed yet does not claim a clean bill of health', () => {
  // "Everything reconciles" for a check that has had nothing to check reads as
  // reassurance that was never earned.
  const h = load('QA_MGR');
  const html = renderRecon(h, [RECON({ code: 'GP-LIVE', phase: 'flower' })]);
  assert.match(html, /nothing to reconcile/);
  assert.doesNotMatch(html, /are covered by manifests/);
  assert.doesNotMatch(html, /do not reconcile/);
  h.close();
});

test('the banner count and the row flags are derived from ONE predicate', () => {
  // Two independent predicates over the same data is how a "3 problems" banner
  // comes to sit above four red rows.
  const h = load('QA_MGR');
  const html = renderRecon(h, [
    RECON({ code: 'A', phase: 'destroyed', plant_count: 10, declared_destroyed: 0 }),
    RECON({ code: 'B', phase: 'destroyed', plant_count: 10, declared_destroyed: 4 }),
    RECON({ code: 'C', phase: 'destroyed', plant_count: 10, declared_destroyed: 10 }),
    RECON({ code: 'D', phase: 'flower', plant_count: 99, declared_destroyed: 0 }),
  ]);
  assert.match(html, /2 of 3 destroyed batch\(es\) do not reconcile/);
  // Exactly two rows carry the red row background.
  const flagged = (html.match(/rgba\(229,72,77,\.06\)/g) || []).length;
  assert.equal(flagged, 2, 'the highlighted row count must equal the banner count');
  h.close();
});

/* ── the form layer ─────────────────────────────────────────────────────── */

function loadForms(role) {
  const h = loadGF({
    files: ['data.js', 'core.js', 'waste-view.js'],
    preScript: PRE_WASTE,
  });
  const w = h.window;
  if (role) w.GF.API.user = { role };
  w.__modals = []; w.__closed = []; w.__toasts = [];
  // Stubbed AFTER the sources load: core.js defines its own openModal/
  // closeModal/toast, so a preScript stub would be overwritten and every
  // assertion here would pass vacuously.
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
  // The real GF.selectField renders a HIDDEN input and GF.pickSel assigns
  // .value directly, firing no change event. The stub keeps that shape.
  w.__selCfg = {};
  w.GF.selectField = (id, cfg) => {
    w.__selCfg[id] = cfg;
    return '<input type="hidden" id="' + id + '" value="' + (cfg.value == null ? '' : cfg.value) + '">';
  };
  w.GF.once = async (btnId, fn) => fn();
  w.GF.API.wasteManifests = async () => ({ manifests: [] });
  w.GF.API.wasteReconciliation = async () => ({ batches: [] });
  w.GF.API.wasteManifest = async () => MAN();
  w.GF.API.facility = async () => ({ rooms: w.__rooms || [] });
  w.GF.API.cultivationBatches = async () => ({ batches: w.__batches || [] });
  w.GF.API.wasteManifestCreate = async (b) => { w.__created = b; return { id: 'mnew' }; };
  w.GF.API.wasteLineAdd = async (id, b) => { w.__line = [id, b]; return { id: 'l1' }; };
  w.GF.API.wasteLineDelete = async (id, l) => { w.__lineDel = [id, l]; return { ok: true }; };
  w.GF.API.wasteSeal = async (id, b) => { w.__sealed = [id, b]; return { status: 'sealed' }; };
  w.GF.API.wasteWitness = async (id, b) => { w.__witnessed = [id, b]; return { status: 'witnessed' }; };
  w.GF.API.wasteDispose = async (id, b) => { w.__disposed = [id, b]; return { status: 'disposed' }; };
  return h;
}

test('the seal modal restates the contents being fixed, and sends the gross weight', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.wasteSealForm('m1').then(async () => {
    const body = w.document.getElementById('wa-seal-modal-body').innerHTML;
    // Sealing cannot be undone, so the numbers being frozen are on screen at
    // the moment of freezing them.
    assert.match(body, /3 line\(s\)/);
    assert.match(body, /1200 plants/);
    assert.match(body, /Nothing can be added or removed afterwards/);
    assert.equal(w.__sealed, undefined, 'opening the modal must not seal anything');
    w.document.getElementById('wa-s-kg').value = '2145.5';
    await w.GF.WWF.wasteSealSave('m1');
    const [id, sent] = w.__sealed;
    assert.equal(id, 'm1');
    assert.equal(sent.gross_weight_kg, 2145.5);
    h.close();
  });
});

test('sealing without a gross weight is refused before the request', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.wasteSealForm('m1').then(async () => {
    w.document.getElementById('wa-s-kg').value = '';
    await w.GF.WWF.wasteSealSave('m1');
    assert.equal(w.__sealed, undefined, 'a blank weight must not be sent as NaN');
    assert.ok(w.__toasts.some(t => /gross weight/i.test(t[0])));
    h.close();
  });
});

test('the witness modal names the two-person rule before the button is pressed', () => {
  const h = loadForms('QA_MGR');
  const w = h.window;
  w.GF.WWF.wasteWitnessForm('m1');
  const body = w.document.getElementById('wa-wit-modal-body').innerHTML;
  assert.match(body, /cannot also witness it/,
    'the control must be explained here, not discovered as a 409');
  assert.equal(w.__witnessed, undefined, 'opening the modal must not sign anything');
  h.close();
});

test('a disposal with no carrier reference is refused before the request', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF.wasteDisposeForm('m1');
  return (async () => {
    w.document.getElementById('wa-d-ref').value = '   ';
    await w.GF.WWF.wasteDisposeSave('m1');
    assert.equal(w.__disposed, undefined,
      'this rung exists to point at someone else’s document — a blank one asserts nothing');
    assert.ok(w.__toasts.some(t => /carrier reference/i.test(t[0])));
    w.document.getElementById('wa-d-ref').value = 'CARRIER-2026-0731-004';
    await w.GF.WWF.wasteDisposeSave('m1');
    assert.equal(w.__disposed[1].carrier_ref, 'CARRIER-2026-0731-004');
    h.close();
  })();
});

test('a line with neither a count nor a weight is refused before the request', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__batches = [];
  return w.GF.WWF.wasteLineForm('m1').then(async () => {
    w.document.getElementById('wa-l-qty').value = '';
    w.document.getElementById('wa-l-kg').value = '';
    await w.GF.WWF.wasteLineSave('m1');
    assert.equal(w.__line, undefined, 'a line that quantifies nothing is not a record');
    assert.ok(w.__toasts.some(t => /plant count or a weight/i.test(t[0])));
    h.close();
  });
});

test('unattributed is the FIRST batch option, not something to work around', () => {
  // Corridor sweepings and spent medium are legitimately not from one batch. A
  // wrong batch attribution corrupts the reconciliation; a blank one does not.
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__batches = [{ id: 'b1', code: 'GP072501', cultivar_code: 'Bisamber',
                   plant_count: 2000, room_name: 'Flowering 1.1' }];
  return w.GF.WWF.wasteLineForm('m1').then(() => {
    const opts = w.__selCfg['wa-l-batch'].options;
    assert.equal(opts[0].v, '', 'the not-from-a-batch option must come first');
    assert.equal(w.__selCfg['wa-l-batch'].value, '', 'and be the default');
    assert.equal(opts[1].v, 'b1');
    h.close();
  });
});

test('a line sends null for an unattributed batch, and separates count from weight', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__batches = [];
  return w.GF.WWF.wasteLineForm('m1').then(async () => {
    w.document.getElementById('wa-l-qty').value = '';
    w.document.getElementById('wa-l-kg').value = '412.5';
    await w.GF.WWF.wasteLineSave('m1');
    const [, sent] = w.__line;
    assert.equal(sent.batch_id, null, 'an empty selection is null, not an empty string');
    assert.equal(sent.plant_qty, null, 'a blank count is null, not 0 and not NaN');
    assert.equal(sent.weight_kg, 412.5);
    h.close();
  });
});

test('a bad manifest code is rejected before the request, matching the server pattern', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  return w.GF.WWF.wasteManifestForm().then(async () => {
    for (const bad of ['', 'WM 001', 'WM#001', 'x'.repeat(65)]) {
      w.__created = undefined;
      w.document.getElementById('wa-n-code').value = bad;
      await w.GF.WWF.wasteManifestSave();
      assert.equal(w.__created, undefined, `"${bad}" must not be sent`);
    }
    // Slashes ARE allowed: carrier dockets are routinely written this way.
    w.document.getElementById('wa-n-code').value = 'WM/2026/0731-04';
    await w.GF.WWF.wasteManifestSave();
    assert.equal(w.__created.manifest_code, 'WM/2026/0731-04');
    h.close();
  });
});

test('a new manifest opens straight into its contents, since an empty one cannot progress', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  return w.GF.WWF.wasteManifestForm().then(async () => {
    w.document.getElementById('wa-n-code').value = 'WM-NEW';
    await w.GF.WWF.wasteManifestSave();
    assert.ok(w.__modals.includes('wa-detail-modal'),
      'leaving the operator on the list would strand a manifest that cannot be sealed');
    h.close();
  });
});

test('the contents modal drops the line-delete button once the manifest is sealed', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  const LINES = [{ id: 'l1', batch_id: 'b1', batch_code: 'GP072501', room_id: 'r1',
                   room_name: 'Flowering 1.1', plant_qty: 1200, weight_kg: 2100,
                   note: null, created_at: '2026-07-31T08:00:00Z' }];
  w.GF.API.wasteManifest = async () => MAN({ status: 'draft', lines: LINES });
  return w.GF.WWF.wasteDetail('m1').then(async () => {
    let body = w.document.getElementById('wa-detail-modal-body').innerHTML;
    assert.match(body, /wasteLineRemove\('m1','l1'\)/, 'a draft may be edited');
    assert.match(body, /wasteLineForm/);

    w.GF.API.wasteManifest = async () => MAN({
      status: 'sealed', sealed_at: '2026-07-31T09:00:00Z', gross_weight_kg: 2145,
      lines: LINES });
    await w.GF.WWF.wasteDetail('m1');
    body = w.document.getElementById('wa-detail-modal-body').innerHTML;
    assert.doesNotMatch(body, /wasteLineRemove/,
      'a sealed manifest is what the witness signs against — it must not look editable');
    assert.doesNotMatch(body, /wasteLineForm/);
    assert.match(body, /fixed when this manifest was sealed/);
    h.close();
  });
});

test('the contents modal shows only the rungs the manifest has actually reached', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.API.wasteManifest = async () => MAN({
    status: 'sealed', sealed_at: '2026-07-31T09:00:00Z', gross_weight_kg: 2145, lines: [] });
  return w.GF.WWF.wasteDetail('m1').then(async () => {
    let body = w.document.getElementById('wa-detail-modal-body').innerHTML;
    assert.match(body, /Weighed/, 'a sealed manifest shows the seal');
    assert.doesNotMatch(body, /Witnessed:/, 'and must not imply a signature it does not have');
    assert.doesNotMatch(body, /Disposed:/);

    w.GF.API.wasteManifest = async () => MAN({
      status: 'disposed', sealed_at: '2026-07-31T09:00:00Z', gross_weight_kg: 2145,
      witnessed_at: '2026-07-31T10:00:00Z', disposed_at: '2026-07-31T11:00:00Z',
      carrier_ref: 'C-1', lines: [] });
    await w.GF.WWF.wasteDetail('m1');
    body = w.document.getElementById('wa-detail-modal-body').innerHTML;
    assert.match(body, /Witnessed:/);
    assert.match(body, /Disposed:/);
    h.close();
  });
});

test('a reader calling a write handler directly is refused', async () => {
  const h = loadForms('QC_MGR');
  const w = h.window;
  await w.GF.WWF.wasteSealForm('m1');
  assert.ok(!w.__modals.includes('wa-seal-modal'));
  w.GF.WWF.wasteWitnessForm('m1');
  assert.ok(!w.__modals.includes('wa-wit-modal'));
  w.GF.WWF.wasteDisposeForm('m1');
  assert.ok(!w.__modals.includes('wa-disp-modal'));
  await w.GF.WWF.wasteManifestForm();
  assert.ok(!w.__modals.includes('wa-new-modal'));
  await w.GF.WWF.wasteLineForm('m1');
  assert.ok(!w.__modals.includes('wa-line-modal'));
  await w.GF.WWF.wasteLineRemove('m1', 'l1');
  assert.equal(w.__lineDel, undefined, 'hiding the button is not the gate — the handler checks too');
  h.close();
});
