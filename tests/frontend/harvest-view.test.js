'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/harvest-view.js — the harvest board's client-side behaviour.

   The server (migration 0051 + app/api/harvest.py) owns the five gates and
   answers 409/403 when they are broken. This view predicts enough of them to
   decide what to render, and two copies of one rule is how a rule drifts, so
   each prediction here has a named counterpart in backend/tests/test_harvest.py:

     - THE PHI ANSWER IS RENDERED, NEVER COMPUTED. Everything shown about an
       interval — the product, days remaining, the clear date — comes from the
       clearance response verbatim. A view that did its own date arithmetic
       would be a second gate that can disagree with the real one.
     - A FAILED CLEARANCE LOOKUP IS NOT "CLEAR". The one wrong answer is the
       permissive one, so an error renders as unknown, not as a green light.
     - THE OVERRIDE BOX IS QA-ONLY. Showing it to a recorder would teach them
       the control is a formality they can type past.
     - EXACTLY ONE LADDER ACTION per lot, the next rung — the same reason the
       destruction board does it.
     - THE YIELD REPORT INTERPRETS `unaccounted` BY PHASE, in one predicate
       shared by the rows and the banner. On a live batch that number is the
       plants still in the room, not a discrepancy, and flagging every healthy
       batch would bury the few that are wrong.

   The view is an IIFE that registers onto window.GF, so these tests load it the
   way index.html does and reach the predicates through rendered output.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE_HARVEST = `
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
    files: ['data.js', 'core.js', 'datepicker.js', 'harvest-view.js'],
    preScript: PRE_HARVEST,
  });
  if (role) h.window.GF.API.user = { role };
  return h;
}

function renderLots(h, lots) {
  h.window.GF.WWF._harv.tab = 'lots';
  h.window.GF.WWF._harv.lots = lots;
  h.window.GF.state.view = 'harvest';
  return h.window.GF.views.harvest();
}

function renderYield(h, batches) {
  h.window.GF.WWF._harv.tab = 'yield';
  h.window.GF.WWF._harv.yield = batches;
  h.window.GF.state.view = 'harvest';
  return h.window.GF.views.harvest();
}

function renderIpm(h, applications) {
  h.window.GF.WWF._harv.tab = 'ipm';
  h.window.GF.WWF._harv.ipm = applications;
  h.window.GF.state.view = 'harvest';
  return h.window.GF.views.harvest();
}

const LOT = (over = {}) => ({
  id: 'h1', batch_id: 'b1', batch_code: 'GP072501', batch_phase: 'flower',
  cultivar_code: 'Bisamber', room_id: 'r1', room_name: 'Flowering 1.1',
  lot_code: 'H-GP072501-01', status: 'wet', harvested_on: '2026-07-30',
  plants_harvested: 2000, wet_weight_g: 1200000,
  dried_on: null, dry_flower_g: null, dry_trim_g: null, dry_waste_g: null,
  dry_total_g: null, moisture_loss_pct: null, implausible_loss: false,
  dry_flower_g_per_plant: null,
  phi_override_at: null, phi_override_by: null, phi_override_reason: null,
  harvested_by: 'u1', closed_at: null, note: null,
  created_at: '2026-07-30T09:00:00Z',
  ...over,
});

const YIELD = (over = {}) => ({
  batch_id: 'b1', code: 'GP072501', phase: 'flower', cultivar_code: 'Bisamber',
  room_name: 'Flowering 1.1', plant_count: 2000,
  plants_harvested: 0, plants_destroyed: 0, unaccounted: 2000,
  lot_count: 0, open_lots: 0, wet_g: null,
  dry_flower_g: null, dry_trim_g: null, dry_waste_g: null, dry_total_g: null,
  moisture_loss_pct: null, implausible_loss: false, dry_flower_g_per_plant: null,
  harvested_without_record: false, over_declared: false,
  ...over,
});

const IPM = (over = {}) => ({
  id: 'i1', room_id: 'r1', room_name: 'Flowering 1.1', batch_id: null,
  batch_code: null, product: 'Spinosad', active_ingredient: 'spinosyn A',
  category: 'biological', method: 'spray', dose: '2 ml/L', target: 'thrips',
  applied_at: '2026-07-28T08:00:00Z', rei_hours: 12, phi_days: 14,
  rei_until: '2026-07-28T20:00:00Z', rei_active: false,
  phi_clear_on: '2026-08-11', note: null,
  ...over,
});

/* ── registration ───────────────────────────────────────────────────────── */

test('the view registers under the harvest key with a read gate above base USER', () => {
  const h = load();
  const spec = h.window.__reg;
  assert.equal(spec.key, 'harvest');
  assert.equal(spec.insertBefore, 'mywork',
    'anchored on a key render.sidebar itself emits, so nav order does not depend on script order');
  h.window.GF.API.user = { role: 'USER' };
  assert.equal(spec.guard(), false, 'base USER must not see the harvest board');
  h.window.GF.API.user = { role: 'QC_MGR' };
  assert.equal(spec.guard(), true, 'any elevated role may READ the board');
  h.window.GF.API.user = { role: null };
  assert.equal(spec.guard(), false);
  h.close();
});

/* ── exactly one ladder action, and it is the next rung ──────────────────── */

const LADDER = [
  ['wet',   'harvestDryForm',   ['harvestCloseForm']],
  ['dried', 'harvestCloseForm', ['harvestDryForm']],
];

for (const [status, expected, forbidden] of LADDER) {
  test(`a ${status} lot offers ONLY ${expected}`, () => {
    const h = load('CU_MGR');
    const html = renderLots(h, [LOT({
      status,
      dried_on: status === 'wet' ? null : '2026-08-10',
      dry_flower_g: status === 'wet' ? null : 260000,
      dry_total_g: status === 'wet' ? null : 290000,
    })]);
    assert.match(html, new RegExp(expected + "\\('h1'\\)"));
    for (const f of forbidden) {
      assert.doesNotMatch(html, new RegExp(f),
        `a ${status} lot must not offer ${f} — the ladder is ordered`);
    }
    h.close();
  });
}

test('a closed lot offers no ladder action at all', () => {
  const h = load('ADMIN');
  const html = renderLots(h, [LOT({
    status: 'closed', dried_on: '2026-08-10', dry_flower_g: 260000,
    dry_total_g: 290000, moisture_loss_pct: 75.8, closed_at: '2026-08-11T10:00:00Z',
  })]);
  for (const f of ['harvestDryForm', 'harvestCloseForm']) {
    assert.doesNotMatch(html, new RegExp(f), `a closed lot must not offer ${f}`);
  }
  h.close();
});

test('a reader sees the lots and none of the actions', () => {
  const h = load('QC_MGR');
  const html = renderLots(h, [LOT()]);
  assert.match(html, /H-GP072501-01/, 'an elevated reader must see the lot');
  for (const f of ['harvestDryForm', 'harvestCloseForm', 'harvestForm']) {
    assert.doesNotMatch(html, new RegExp(f), `a reader must not be offered ${f}`);
  }
  h.close();
});

test('QA is offered the cut but not the yield or the close', () => {
  const h = load('QA_MGR');
  // QA's extra write exists only because the PHI release is written on the
  // harvest row — mirrors _CUTTERS vs _RECORDERS server-side.
  let html = renderLots(h, [LOT()]);
  assert.match(html, /harvestForm\(\)/, 'QA must be able to record the cut it released');
  assert.doesNotMatch(html, /harvestDryForm/, 'recording the yield stays with the crew');
  html = renderLots(h, [LOT({ status: 'dried', dried_on: '2026-08-10', dry_flower_g: 1 })]);
  assert.doesNotMatch(html, /harvestCloseForm/, 'and so does closing the lot');
  h.close();
});

test('a released cut carries the reason on the lot card, not in a note', () => {
  const h = load('CU_MGR');
  const html = renderLots(h, [LOT({
    phi_override_at: '2026-07-30T09:00:00Z', phi_override_by: 'u2',
    phi_override_reason: 'residue screen clear, ref QA-2026-114',
  })]);
  assert.match(html, /released by QA/);
  assert.match(html, /residue screen clear, ref QA-2026-114/);
  h.close();
});

test('an implausible loss is shown as something to check, not as a failure', () => {
  const h = load('CU_MGR');
  const html = renderLots(h, [LOT({
    status: 'dried', dried_on: '2026-08-10', dry_flower_g: 1000000,
    dry_total_g: 1080000, moisture_loss_pct: 10, implausible_loss: true,
  })]);
  assert.match(html, /It is not refused/,
    'outside the band means "look at this number", not "this number is wrong"');
  h.close();
});

/* ── the plant-protection log ────────────────────────────────────────────── */

test('an active re-entry restriction is called out and an elapsed one is not', () => {
  const h = load('CU_MGR');
  const active = renderIpm(h, [IPM({ rei_active: true, rei_until: '2026-07-30T20:00:00Z' })]);
  assert.match(active, /no entry until 2026-07-30 20:00/);
  const done = renderIpm(h, [IPM({ rei_active: false })]);
  assert.match(done, /REI 12 h elapsed/);
  h.close();
});

test('an application with no interval says so rather than showing a blank', () => {
  const h = load('CU_MGR');
  const html = renderIpm(h, [IPM({ rei_hours: null, phi_days: null,
                                   rei_until: null, phi_clear_on: null })]);
  assert.match(html, /no REI stated/);
  assert.match(html, /no PHI stated/,
    'NULL means "no interval declared", which is a statement — a blank cell is not');
  h.close();
});

test('the empty plant-protection log explains why an unlogged treatment matters', () => {
  const h = load('CU_MGR');
  const html = renderIpm(h, []);
  assert.match(html, /an unlogged treatment is a control that cannot act/);
  h.close();
});

test('logging an application is a recorder action, not a QA one', () => {
  let h = load('QA_MGR');
  assert.doesNotMatch(renderIpm(h, []), /ipmForm\(\)/);
  h.close();
  h = load('CU_MGR');
  assert.match(renderIpm(h, []), /ipmForm\(\)/);
  h.close();
});

/* ── the yield report interprets its arithmetic by phase ─────────────────── */

const YIELD_STATES = [
  // [over-riding fields, expected label fragment, expected `bad`]
  [{ over_declared: true }, 'OVER-DECLARED', true],
  [{ phase: 'harvested', harvested_without_record: true, unaccounted: 2000 },
   'harvested, no lot', true],
  [{ phase: 'harvested', plants_harvested: 1800, unaccounted: 200, lot_count: 1 },
   '200 plant(s) unaccounted', true],
  [{ phase: 'harvested', plants_harvested: 2000, unaccounted: 0, lot_count: 1 },
   'balanced', false],
  [{ phase: 'destroyed', plants_destroyed: 2000, unaccounted: 0 }, 'destroyed', false],
  [{ phase: 'flower' }, 'in production', false],
];

for (const [over, label, bad] of YIELD_STATES) {
  test(`the yield report reads ${JSON.stringify(over)} as "${label}"`, () => {
    const h = load('QA_MGR');
    const html = renderYield(h, [YIELD(over)]);
    assert.ok(html.includes(label.replace(/\(/g, '(')),
      `expected the row to be labelled "${label}"\n${html}`);
    // `bad` rows are tinted; healthy ones are not. The tint and the banner count
    // come from the SAME predicate, so this also pins that they agree.
    assert.equal(/rgba\(229,72,77,\.06\)/.test(html), bad,
      bad ? 'a discrepancy must be visibly flagged'
          : 'a healthy batch must not be flagged as a problem');
    h.close();
  });
}

test('a live batch is never counted as a discrepancy, however many plants are standing', () => {
  const h = load('QA_MGR');
  const html = renderYield(h, [
    YIELD({ batch_id: 'b1', code: 'GP-A', phase: 'flower', unaccounted: 2000 }),
    YIELD({ batch_id: 'b2', code: 'GP-B', phase: 'veg', unaccounted: 1500 }),
  ]);
  assert.match(html, /No batch has been closed as harvested yet/,
    'with nothing harvested there is nothing to reconcile — and saying "all clear" '
    + 'would be a clean bill of health for a check that has had nothing to check');
  assert.doesNotMatch(html, /do not reconcile/);
  h.close();
});

test('the banner count and the flagged rows come from the same predicate', () => {
  const h = load('QA_MGR');
  const html = renderYield(h, [
    YIELD({ batch_id: 'b1', code: 'GP-OK', phase: 'harvested',
            plants_harvested: 2000, unaccounted: 0, lot_count: 1 }),
    YIELD({ batch_id: 'b2', code: 'GP-GHOST', phase: 'harvested',
            harvested_without_record: true, unaccounted: 2000 }),
  ]);
  assert.match(html, /1 of 2 harvested batch\(es\) do not reconcile/);
  assert.equal((html.match(/rgba\(229,72,77,\.06\)/g) || []).length, 1,
    'exactly the batch the banner counts is the batch the table tints');
  h.close();
});

/* ── escaping ───────────────────────────────────────────────────────────── */

test('lot codes, room names, override reasons and product names are HTML-escaped', () => {
  const h = load('CU_MGR');
  const lots = renderLots(h, [LOT({
    lot_code: '<img src=x onerror=alert(1)>',
    room_name: '"><script>bad()</script>',
    batch_code: '<svg onload=alert(2)>',
    note: '<b>note</b>',
    phi_override_at: 'x', phi_override_reason: '<i>why</i>',
  })]);
  assert.doesNotMatch(lots, /<img src=x/);
  assert.doesNotMatch(lots, /<script>bad\(\)/);
  assert.doesNotMatch(lots, /<svg onload/);
  assert.doesNotMatch(lots, /<i>why<\/i>/);
  assert.match(lots, /&lt;img src=x/);

  const ipm = renderIpm(h, [IPM({ product: '<img src=y onerror=alert(3)>',
                                  active_ingredient: '<script>x()</script>' })]);
  assert.doesNotMatch(ipm, /<img src=y/);
  assert.doesNotMatch(ipm, /<script>x\(\)/);
  h.close();
});

/* ── the form layer ─────────────────────────────────────────────────────── */

function loadForms(role) {
  const h = loadGF({
    files: ['data.js', 'core.js', 'datepicker.js', 'harvest-view.js'],
    preScript: PRE_HARVEST,
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
  // .value directly, firing no change event. The stub keeps that shape, and
  // records cfg so the onPick wiring can be asserted rather than assumed.
  w.__selCfg = {};
  w.GF.selectField = (id, cfg) => {
    w.__selCfg[id] = cfg;
    return '<input type="hidden" id="' + id + '" value="' + (cfg.value == null ? '' : cfg.value) + '">';
  };
  w.GF.once = async (btnId, fn) => fn();
  w.__batches = [
    { id: 'b1', code: 'GP072501', cultivar_code: 'Bisamber', plant_count: 2000,
      phase: 'flower', room_name: 'Flowering 1.1' },
  ];
  w.__clearance = { batch_id: 'b1', batch_code: 'GP072501', clear: true,
                    terminal: false, blocking: [], rei_active: [] };
  w.GF.API.harvests = async () => ({ harvests: [] });
  w.GF.API.harvestYield = async () => ({ batches: [] });
  w.GF.API.ipmApplications = async () => ({ applications: [] });
  w.GF.API.cultivationBatches = async () => ({ batches: w.__batches });
  w.GF.API.facility = async () => ({ rooms: w.__rooms || [] });
  w.GF.API.harvestClearance = async (id) => {
    w.__clearanceFor = id;
    if (w.__clearanceThrows) throw new Error('network down');
    return w.__clearance;
  };
  // Stubbed here rather than per-test: a spy that only exists in the tests that
  // expect a call makes the "must NOT call" assertions pass vacuously.
  w.GF.API.ipmApply = async (b) => { w.__applied = b; return { id: 'i2' }; };
  w.GF.API.harvest = async () => w.__lot || LOT();
  w.GF.API.harvestCreate = async (b) => { w.__cut = b; return { id: 'hnew' }; };
  w.GF.API.harvestDry = async (id, b) => {
    w.__dry = [id, b];
    return { status: 'dried', dry_total_g: 290000, moisture_loss_pct: 75.8,
             implausible_loss: false };
  };
  w.GF.API.harvestClose = async (id, b) => { w.__closedLot = [id, b]; return { status: 'closed' }; };
  return h;
}

test('the cut form asks the server for clearance before offering the button', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.harvestForm().then(async () => {
    assert.equal(w.__clearanceFor, 'b1',
      'clearance is fetched for the pre-selected batch, not left until submit');
    const box = w.document.getElementById('hv-c-clearance').innerHTML;
    assert.match(box, /Clear to harvest/);
    // And the picker is wired to re-check when the batch changes: selectField
    // renders a hidden input, so onPick is the only hook that ever fires.
    assert.equal(typeof w.__selCfg['hv-c-batch'].onPick, 'function',
      'onPick must be a FUNCTION — chooser.js calls cfg.onPick(v)');
    h.close();
  });
});

test('a blocked batch renders the server’s interval verbatim and offers no override to a recorder', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__clearance = {
    batch_id: 'b1', batch_code: 'GP072501', clear: false, terminal: false,
    blocking: [{ ipm_id: 'i1', product: 'Sulphur dust', active_ingredient: 'sulphur',
                 category: 'chemical', method: 'dust', scope: 'room',
                 room_name: 'Flowering 1.1', applied_at: '2026-07-27T10:00:00Z',
                 phi_days: 14, phi_clear_on: '2026-08-10', days_remaining: 11 }],
    rei_active: [],
  };
  return w.GF.WWF.harvestForm().then(() => {
    const box = w.document.getElementById('hv-c-clearance').innerHTML;
    assert.match(box, /Inside a pre-harvest interval/);
    assert.match(box, /Sulphur dust/);
    assert.match(box, /14 days/, 'the interval comes from the response, not from a local calculation');
    assert.match(box, /2026-08-10/);
    assert.match(box, /11 day\(s\) to go/);

    const ovr = w.document.getElementById('hv-c-override').innerHTML;
    assert.doesNotMatch(ovr, /id="hv-c-ovr"/,
      'a recorder must not be given a box to type past the control');
    assert.match(ovr, /Only QA can release a cut/,
      'and must be told who to go to instead');
    h.close();
  });
});

test('QA gets the release box, and the reason reaches the server', () => {
  const h = loadForms('QA_MGR');
  const w = h.window;
  w.__clearance = {
    batch_id: 'b1', clear: false, terminal: false,
    blocking: [{ ipm_id: 'i1', product: 'Sulphur', phi_days: 21,
                 phi_clear_on: '2026-08-20', days_remaining: 21 }],
    rei_active: [],
  };
  return w.GF.WWF.harvestForm().then(async () => {
    const ovr = w.document.getElementById('hv-c-override').innerHTML;
    assert.match(ovr, /id="hv-c-ovr"/);
    assert.match(ovr, /recorded against your name/,
      'the release is permanent and attributed, and says so before it is given');
    w.document.getElementById('hv-c-lot').value = 'H-GP072501-01';
    w.document.getElementById('hv-c-wet').value = '1200000';
    w.document.getElementById('hv-c-plants').value = '2000';
    w.document.getElementById('hv-c-ovr').value = '  residue screen clear  ';
    await w.GF.WWF.harvestSave();
    assert.equal(w.__cut.phi_override_reason, 'residue screen clear');
    assert.equal(w.__cut.lot_code, 'H-GP072501-01');
    assert.equal(w.__cut.wet_weight_g, 1200000);
    h.close();
  });
});

test('a clearance lookup that fails does NOT read as clear', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__clearanceThrows = true;
  return w.GF.WWF.harvestForm().then(() => {
    const box = w.document.getElementById('hv-c-clearance').innerHTML;
    assert.doesNotMatch(box, /Clear to harvest/,
      'the permissive answer is the one wrong answer when the check did not run');
    assert.match(box, /Could not check pre-harvest intervals/);
    assert.equal(w.GF.WWF._harv.clearance, null);
    h.close();
  });
});

test('a stale clearance response cannot overwrite a newer pick', async () => {
  /* Reproduces the race directly rather than through harvestForm()'s own
     picker/DOM setup: two harvestClearance() calls are put in flight for two
     different batches, and the OLDER one is made to resolve SECOND — the
     out-of-order arrival the sequence guard exists for. Without the guard,
     whichever response lands last always wins, even if it is stale. */
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.document.body.insertAdjacentHTML('beforeend',
    '<input id="hv-c-batch" value="b1"><div id="hv-c-clearance"></div><div id="hv-c-override"></div>');

  const pending = {};
  w.GF.API.harvestClearance = (id) => new Promise((resolve) => { pending[id] = resolve; });

  const firstCheck = w.GF.WWF.harvestClearanceCheck();
  await Promise.resolve();
  assert.ok(pending.b1, 'the first (b1) check must be in flight');

  w.document.getElementById('hv-c-batch').value = 'b2';
  const secondCheck = w.GF.WWF.harvestClearanceCheck();
  await Promise.resolve();
  assert.ok(pending.b2, 'the second (b2) check must be in flight');

  pending.b2({ batch_id: 'b2', clear: true, blocking: [], rei_active: [] });
  await secondCheck;
  pending.b1({
    batch_id: 'b1', clear: false, rei_active: [],
    blocking: [{ ipm_id: 'i1', product: 'STALE PRODUCT', phi_days: 9,
                 phi_clear_on: '2026-08-01', days_remaining: 2 }],
  });
  await firstCheck;

  const box = w.document.getElementById('hv-c-clearance').innerHTML;
  assert.match(box, /Clear to harvest/, 'the box must reflect b2, the current pick');
  assert.doesNotMatch(box, /STALE PRODUCT/,
    'the stale b1 response must not overwrite the newer pick');
  h.close();
});

test('an active re-entry restriction is surfaced on the cut form even when the cut is clear', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__clearance = {
    batch_id: 'b1', clear: true, terminal: false, blocking: [],
    rei_active: [{ ipm_id: 'i1', product: 'Spinosad', room_name: 'Flowering 1.1',
                   applied_at: '2026-07-30T08:00:00Z', rei_hours: 12,
                   rei_until: '2026-07-30T20:00:00Z' }],
  };
  return w.GF.WWF.harvestForm().then(() => {
    const box = w.document.getElementById('hv-c-clearance').innerHTML;
    assert.match(box, /Clear to harvest/, 'REI does not block the cut');
    assert.match(box, /Re-entry restriction still active/,
      'but harvesting a room means entering it, so it belongs on this form');
    h.close();
  });
});

test('terminal batches are never offered in the cut picker', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__batches = [
    { id: 'b1', code: 'GP-DONE', phase: 'harvested', plant_count: 10 },
    { id: 'b2', code: 'GP-GONE', phase: 'destroyed', plant_count: 10 },
  ];
  return w.GF.WWF.harvestForm().then(() => {
    assert.ok(!w.__modals.includes('hv-cut-modal'),
      'a picker listing options the server will reject teaches operators to expect errors');
    assert.match(w.__toasts[0][0], /No open batch/);
    h.close();
  });
});

test('a malformed lot code is refused before the request', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.harvestForm().then(async () => {
    w.document.getElementById('hv-c-lot').value = 'lot with spaces!';
    w.document.getElementById('hv-c-wet').value = '1000';
    await w.GF.WWF.harvestSave();
    assert.equal(w.__cut, undefined);
    assert.match(w.__toasts.at(-1)[0], /Lot code must be/);
    h.close();
  });
});

test('a cut with no wet weight is refused before the request', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.harvestForm().then(async () => {
    w.document.getElementById('hv-c-lot').value = 'H-1';
    w.document.getElementById('hv-c-wet').value = '';
    await w.GF.WWF.harvestSave();
    assert.equal(w.__cut, undefined,
      'the wet weight is the whole point of the record — a cut without it is not a yield record');
    assert.match(w.__toasts.at(-1)[0], /wet weight/);
    h.close();
  });
});

test('a partial-canopy pull with zero plants is allowed through', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.harvestForm().then(async () => {
    w.document.getElementById('hv-c-lot').value = 'H-TOPS';
    w.document.getElementById('hv-c-wet').value = '5000';
    w.document.getElementById('hv-c-plants').value = '0';
    await w.GF.WWF.harvestSave();
    assert.equal(w.__cut.plants_harvested, 0,
      'taking the tops and leaving the plants standing is a real harvest event');
    h.close();
  });
});

test('the yield form restates the wet weight the three figures must fit under', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__lot = LOT({ wet_weight_g: 1200000 });
  return w.GF.WWF.harvestDryForm('h1').then(async () => {
    const body = w.document.getElementById('hv-dry-modal-body').innerHTML;
    assert.match(body, /1,200 kg/, 'the ceiling is on screen while the numbers are entered');
    assert.match(body, /cannot exceed the wet weight/);
    assert.equal(w.__dry, undefined, 'opening the form must not record anything');

    w.document.getElementById('hv-d-flower').value = '260000';
    w.document.getElementById('hv-d-trim').value = '20000';
    w.document.getElementById('hv-d-waste').value = '10000';
    await w.GF.WWF.harvestDrySave('h1');
    const [id, sent] = w.__dry;
    assert.equal(id, 'h1');
    assert.deepEqual(
      [sent.dry_flower_g, sent.dry_trim_g, sent.dry_waste_g],
      [260000, 20000, 10000]);
    h.close();
  });
});

test('a blank trim or waste figure is sent as null, not as zero', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.harvestDryForm('h1').then(async () => {
    w.document.getElementById('hv-d-flower').value = '260000';
    await w.GF.WWF.harvestDrySave('h1');
    const sent = w.__dry[1];
    assert.equal(sent.dry_trim_g, null,
      'not weighed is not the same statement as weighed and found to be nothing');
    assert.equal(sent.dry_waste_g, null);
    h.close();
  });
});

test('a yield with no dry flower figure is refused before the request', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.harvestDryForm('h1').then(async () => {
    w.document.getElementById('hv-d-flower').value = '';
    await w.GF.WWF.harvestDrySave('h1');
    assert.equal(w.__dry, undefined);
    assert.match(w.__toasts.at(-1)[0], /dry flower weight/);
    h.close();
  });
});

test('closing says the weights become final, and only then sends', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF.harvestCloseForm('h1');
  const body = w.document.getElementById('hv-close-modal-body').innerHTML;
  assert.match(body, /cannot be corrected afterwards/);
  assert.equal(w.__closedLot, undefined, 'opening the modal must not close the lot');
  return w.GF.WWF.harvestCloseSave('h1').then(() => {
    assert.equal(w.__closedLot[0], 'h1');
    h.close();
  });
});

test('an IPM application scoped to neither a room nor a batch is refused before the request', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.ipmForm().then(async () => {
    w.document.getElementById('hv-i-product').value = 'Neem oil';
    // Both pickers left on their empty default.
    await w.GF.WWF.ipmSave();
    assert.equal(w.__applied, undefined);
    assert.match(w.__toasts.at(-1)[0], /room or the batch/);
    h.close();
  });
});

test('a blank interval is sent as null and a stated zero is sent as zero', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.ipmForm().then(async () => {
    w.document.getElementById('hv-i-product').value = 'Predatory mites';
    w.document.getElementById('hv-i-room').value = 'r1';
    w.document.getElementById('hv-i-phi').value = '0';
    await w.GF.WWF.ipmSave();
    assert.equal(w.__applied.rei_hours, null,
      'no interval declared is a different statement from an interval of nil');
    assert.equal(w.__applied.phi_days, 0,
      'and a declared zero must survive the round trip as zero, not become null');
    h.close();
  });
});

test('a garbage interval is refused before the request, not silently sent as null', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.ipmForm().then(async () => {
    w.document.getElementById('hv-i-product').value = 'Predatory mites';
    w.document.getElementById('hv-i-room').value = 'r1';
    // A real <input type="number"> sanitizes an assigned non-numeric string
    // back to "" (jsdom matches browser behaviour here), which would mask the
    // very bug under test. Force the underlying value the way a bad-input
    // browser quirk or a paste actually can, so the raw string that reaches
    // ipmSave's num() is really the non-numeric garbage, not "".
    const phi = w.document.getElementById('hv-i-phi');
    phi.setAttribute('type', 'text');
    phi.value = 'abc';
    await w.GF.WWF.ipmSave();
    assert.equal(w.__applied, undefined,
      'a garbage PHI must not reach the API as a silent null — that is indistinguishable from "not stated"');
    assert.match(w.__toasts.at(-1)[0], /whole numbers/);
    h.close();
  });
});

test('a valid interval, including a legitimate 0, still submits (not mistaken for garbage)', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.ipmForm().then(async () => {
    w.document.getElementById('hv-i-product').value = 'Predatory mites';
    w.document.getElementById('hv-i-room').value = 'r1';
    w.document.getElementById('hv-i-rei').value = '0';
    w.document.getElementById('hv-i-phi').value = '3';
    await w.GF.WWF.ipmSave();
    assert.equal(w.__applied.rei_hours, 0,
      'a legitimate zero must still submit, not be mistaken for garbage');
    assert.equal(w.__applied.phi_days, 3);
    h.close();
  });
});

// ── Feeding tab (irrigation, migration 0052) ─────────────────────────────────

function renderFeed(h, feeds) {
  h.window.GF.WWF._harv.tab = 'feed';
  h.window.GF.WWF._harv.feeds = feeds;
  h.window.GF.state.view = 'harvest';
  return h.window.GF.views.harvest();
}

test('the Feeding tab lists a feed and shows a missing reading as a dash, not zero', () => {
  const h = load('CU_MGR');
  const body = renderFeed(h, [
    { id: 'f1', room_name: 'Flowering 1.1', batch_code: null, applied_on: '2026-08-05',
      method: 'drip', water_volume_l: 40, feed_ec: 1.8, feed_ph: 6.1,
      runoff_ec: null, runoff_ph: null, nutrients: 'Base A+B' },
  ]);
  assert.match(body, /Flowering 1\.1/);
  assert.match(body, /EC <b>1\.8/, 'a measured feed EC is shown');
  // A NULL runoff reading must not render a "runoff EC" chip at all — absent is
  // "not measured", never 0.
  assert.doesNotMatch(body, /runoff EC/, 'an unmeasured runoff reading shows no chip');
  assert.match(body, /Base A\+B/);
  h.close();
});

test('the Feeding tab offers Log feed to a recorder and empty-states cleanly', () => {
  const h = load('CU_MGR');
  const body = renderFeed(h, []);
  assert.match(body, /No feeds logged/);
  assert.match(body, /GF\.WWF\.feedForm\(\)/, 'a recorder is offered the Log feed action');
  h.close();
});

function loadFeedForms(role) {
  const h = loadForms(role);
  const w = h.window;
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  w.GF.API.irrigation = async () => ({ feeds: w.__feeds || [] });
  w.GF.API.irrigationLog = async (b) => { w.__feed = b; return { id: 'f9' }; };
  return h;
}

test('a blank feed reading is sent as null, a room is required, and a value round-trips', () => {
  const h = loadFeedForms('CU_MGR');
  const w = h.window;
  return w.GF.WWF.feedForm().then(async () => {
    // no room picked yet → refused before any request
    w.document.getElementById('hv-f-room').value = '';
    await w.GF.WWF.feedSave();
    assert.equal(w.__feed, undefined, 'a feed with no room must not be sent');
    assert.match(w.__toasts.at(-1)[0], /room/i);

    // now a real room + a volume, EC left blank
    w.document.getElementById('hv-f-room').value = 'r1';
    w.document.getElementById('hv-f-vol').value = '40';
    w.document.getElementById('hv-f-fph').value = '6.1';
    await w.GF.WWF.feedSave();
    assert.equal(w.__feed.room_id, 'r1');
    assert.equal(w.__feed.water_volume_l, 40);
    assert.equal(w.__feed.feed_ph, 6.1, 'a decimal pH round-trips, not rounded to int');
    assert.equal(w.__feed.feed_ec, null,
      'a reading left blank is "not measured" (null), never coerced to 0');
    h.close();
  });
});
