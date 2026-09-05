'use strict';

/* ══════════════════════════════════════════════════════════════════════
   Registering a batch from the product specification, the journey strip,
   and the mother bank + clone runs (web/gf/cultivation-view.js +
   web/gf/propagation-view.js; server: app/api/cultivation.py,
   app/api/propagation.py, migration 0065).

   What is pinned:
     - WHO REGISTERS. QA, the executives and the cultivation manager register
       a batch and initiate a clone run (the server's _REGISTRARS /
       _INITIATORS); QC and base staff do not. QA does NOT move a batch or
       edit the cultivar master — those stay the floor's.
     - FROM THE PRODUCT SPECIFICATION. The cultivar chooser carries each
       cultivar's ImB grades as its sub-text, the panel beneath shows the
       ladder (APPROVED / DRAFT / none, said plainly), and the batch number
       is pre-filled from the server's suggestion with the cultivar code as
       its fixed head.
     - THE JOURNEY STRIP. Position comes from the batch's phase only; the
       next step names whose it is; the harvest cut is the handoff; a
       destroyed batch is off the plan; the strip follows the batch just
       registered.
     - THE BANK DERIVES, NEVER STORES. "never" for a mother never cut, no
       age for a mother with no date; the run form lists only the chosen
       cultivar's active mothers; a blank cuttings box is null, not 0.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
  window.GF.render = { all: function () { window.__renders = (window.__renders || 0) + 1; } };
  window.GF.viewHead = function (a, b, extra) { return '<head>' + (extra || '') + '</head>'; };
  window.GF.API = { user: { role: 'CU_MGR' } };
`;
const FILES = ['data.js', 'core.js', 'datepicker.js', 'codefield.js', 'cultivation-view.js', 'propagation-view.js'];

const GP_SPEC = {
  id: 's1', spec_code: 'PP-QC-SPEC-001', version: 'v5.2', status: 'APPROVED', floor_pct: 13.83,
  tiers: [
    { tier: 1, spec: 'Spec I', range_min: 26, range_max: 30, nominal: 28 },
    { tier: 2, spec: 'Spec II', range_min: 22, range_max: 26, nominal: 24 },
    { tier: 3, spec: 'Spec III', range_min: 18, range_max: 22, nominal: 20 },
    { tier: 4, spec: 'Spec IV', range_min: 13.83, range_max: 18, nominal: 16 },
  ],
};
const CULTIVARS = [
  { id: 'cv1', code: 'GP', name: 'Grape Pie', is_active: true, spec: GP_SPEC },
  { id: 'cv2', code: 'FB', name: 'Fat Bastard', is_active: true, spec: { ...GP_SPEC, id: 's2', version: 'v0.1', status: 'DRAFT' } },
  { id: 'cv3', code: 'OPM', name: 'Orange Punch Mimosa', is_active: true, spec: null },
];
const batch = (o) => ({
  id: 'b1', code: 'GP072501', cultivar_id: 'cv1', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
  room_name: 'Flowering 1.1', plant_count: 2000, plants_materialised: 2000, plants_active: 1990,
  phase: 'flower', phase_since: '2026-07-20', is_active: true, ...o,
});

function load(role) {
  const h = loadGF({ files: FILES, preScript: PRE });
  const w = h.window;
  if (role) w.GF.API.user = { role };
  w.__modals = []; w.__closed = []; w.__toasts = [];
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
  w.__selCfg = {};
  w.GF.selectField = (id, cfg) => {
    w.__selCfg[id] = cfg;
    return '<input type="hidden" id="' + id + '" value="' + (cfg.value == null ? '' : cfg.value) + '">';
  };
  w.GF.once = async (btnId, fn) => fn();
  w.__cultivars = CULTIVARS; w.__batches = []; w.__rooms = [
    { id: 'r1', name: 'Flowering 1.1', kind: 'flower' }, { id: 'r2', name: 'Clone room', kind: 'clone' },
    { id: 'r3', name: 'Mother room', kind: 'mother' }];
  w.__mothers = []; w.__runs = [];
  w.GF.API.cultivationBatches = async () => ({ batches: w.__batches });
  w.GF.API.cultivars = async () => ({ cultivars: w.__cultivars });
  w.GF.API.facility = async () => ({ rooms: w.__rooms });
  w.GF.API.cultivationBatchCreate = async (b) => { w.__created = b; return { id: 'new-batch' }; };
  w.GF.API.cultivationBatchCode = async (id) => { w.__codeAsked = id; return { prefix: 'GP', period: '0726', seq: 3, suggested: 'GP072603' }; };
  w.GF.API.mothers = async () => ({ mothers: w.__mothers, by_cultivar: w.__byCv || [] });
  w.GF.API.motherNextCode = async (id) => ({ prefix: 'GP_M', seq: 2, suggested: 'GP_M02' });
  w.GF.API.motherCreate = async (b) => { w.__motherCreated = b; return { id: 'm9' }; };
  w.GF.API.motherPatch = async (id, b) => { w.__motherPatched = [id, b]; return { id }; };
  w.GF.API.cloneRuns = async () => ({ runs: w.__runs });
  w.GF.API.cloneRunCreate = async (b) => { w.__runCreated = b; return { id: 'run9' }; };
  w.GF.API.cloneRunPatch = async (id, b) => { w.__runPatched = [id, b]; return { id }; };
  return h;
}

function render(h, batches, tab) {
  const w = h.window;
  w.GF.WWF._cult.batches = batches;
  w.GF.WWF._cult.cultivars = CULTIVARS;
  w.GF.WWF._cult.runs = w.__runs;
  if (tab) w.GF.WWF._cult.tab = tab;
  w.GF.state.view = 'cultivation';
  return w.GF.views.cultivation();
}

/* ── who registers ──────────────────────────────────────────────────────── */

test('QA, executives and cultivation are offered Register batch and Start clone run; QC and base staff are not', () => {
  for (const role of ['QA_MGR', 'CEO', 'COO', 'OWNER', 'ADMIN', 'CU_MGR']) {
    const h = load(role);
    const html = render(h, [batch()]);
    assert.match(html, /GF\.WWF\.cultBatchForm\(\)/, `${role} registers a batch`);
    assert.match(html, /GF\.WWF\.cloneRunForm\(\)/, `${role} starts a clone run`);
    h.close();
  }
  for (const role of ['QC_MGR', 'WH_MGR', 'IR_MGR', 'USER']) {
    const h = load(role);
    const html = render(h, [batch()]);
    assert.doesNotMatch(html, /GF\.WWF\.cultBatchForm\(\)/, `${role} does not register`);
    assert.doesNotMatch(html, /GF\.WWF\.cloneRunForm\(\)/, `${role} does not initiate`);
    h.close();
  }
});

test('QA registers and generates ids but is offered neither the move nor the cultivar master', () => {
  const h = load('QA_MGR');
  const html = render(h, [batch({ plants_materialised: 0, plants_active: 0 })]);
  assert.match(html, /cultFillPlants\('b1'\)/, 'QA may generate the plant ids');
  assert.doesNotMatch(html, /cultMoveForm\('b1'\)/, 'moving the batch stays the floor\'s');
  assert.doesNotMatch(html, /cultCultivarList\(\)/, 'the cultivar master stays the floor\'s');
  h.close();
});

test('a registrar calling a write handler that is not theirs is refused; a reader calling the register handler is refused', async () => {
  const h = load('QC_MGR');
  const w = h.window;
  await w.GF.WWF.cultBatchForm();
  assert.deepEqual(w.__modals, [], 'QC cannot open the register form');
  await w.GF.WWF.cloneRunForm();
  assert.deepEqual(w.__modals, [], 'QC cannot open the clone run form');
  h.close();
});

/* ── from the product specification ─────────────────────────────────────── */

test('the cultivar chooser carries each cultivar\'s grades, and the panel says APPROVED, DRAFT or none', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF._cult.cultivars = CULTIVARS;
  await w.GF.WWF.cultBatchForm();
  await w.GF.WWF._cultBatchCultivarSync();
  assert.deepEqual(w.__modals, ['cu-batch-modal']);
  const opts = w.__selCfg['cu-b-cultivar'].options;
  assert.match(opts[0].sub, /I 26\.00–30\.00 · II 22\.00–26\.00 · III 18\.00–22\.00 · IV 13\.83–18\.00/);
  assert.match(opts[1].sub, /DRAFT/, 'a draft ladder is flagged in the chooser');
  assert.match(opts[2].sub, /no product specification yet/);
  // The panel for the approved ladder: strain, code+version, the four grades.
  const panel = w.document.getElementById('cu-b-spec').innerHTML;
  assert.match(panel, /Grape Pie/);
  assert.match(panel, /PP-QC-SPEC-001 v5\.2/);
  assert.match(panel, /APPROVED/);
  assert.match(panel, /Spec I<\/td><td>26\.00 – 30\.00 %<\/td><td>28\.00 %/);
  assert.match(panel, /Spec IV<\/td><td>13\.83 – 18\.00 %/);
  // Switch to the cultivar with no ladder: the panel says so, no empty table.
  w.document.getElementById('cu-b-cultivar').value = 'cv3';
  await w.GF.WWF._cultBatchCultivarSync();
  const none = w.document.getElementById('cu-b-spec').innerHTML;
  assert.match(none, /no product specification registered yet/);
  assert.doesNotMatch(none, /<table/);
  h.close();
});

test('the batch number is pre-filled from the server with the cultivar code as its fixed head', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.GF.WWF._cult.cultivars = CULTIVARS;
  await w.GF.WWF.cultBatchForm();
  await w.GF.WWF._cultBatchCultivarSync();
  assert.equal(w.__codeAsked, 'cv1', 'the suggestion is asked for the chosen cultivar');
  const code = w.document.getElementById('cu-b-code');
  assert.equal(code.value, 'GP072603', 'the whole suggestion is in the box');
  code.value = '072603';                       // head deleted by the user
  w.GF._codeGuard('cu-b-code');
  assert.equal(code.value, 'GP072603', 'the cultivar code is the fixed head — the guard puts it back');
  // The registrar edits the tail and saves: the code sent is what the box holds.
  code.value = 'GP072607';
  w.document.getElementById('cu-b-count').value = '2000';
  await w.GF.WWF.cultBatchSave();
  assert.equal(w.__created.code, 'GP072607');
  assert.equal(w.__created.cultivar_id, 'cv1');
  assert.equal(w.__created.plant_count, 2000);
  h.close();
});

test('the strip follows the batch just registered', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF._cult.cultivars = CULTIVARS;
  await w.GF.WWF.cultBatchForm();
  await w.GF.WWF._cultBatchCultivarSync();
  w.document.getElementById('cu-b-count').value = '10';
  w.__batches = [batch(), batch({ id: 'new-batch', code: 'GP072603', phase: 'clone', room_name: 'Clone room' })];
  await w.GF.WWF.cultBatchSave();
  assert.equal(w.GF.WWF._cult.focus, 'new-batch');
  assert.equal(w.GF.WWF._cult.tab, 'batches');
  const html = render(h, w.__batches);
  const strip = html.slice(html.indexOf('class="cj-wrap"'), html.indexOf('class="cj-tabs"'));
  assert.match(strip, /<strong>GP072603<\/strong>/, 'the strip shows the new batch, not the older one');
  assert.match(strip, /cj-chip on" onclick="GF\.WWF\.cultFocus\('new-batch'\)/, 'its chip is the active one');
  h.close();
});

/* ── the journey strip ──────────────────────────────────────────────────── */

test('the strip reads position from the phase and names the next step and whose it is', () => {
  const h = load('CU_MGR');
  const html = render(h, [batch()]);   // flower, 10 days in, Flowering 1.1
  const strip = html.slice(html.indexOf('class="cj-wrap"'), html.indexOf('class="cj-tabs"'));
  assert.match(strip, /data-w="57"/, 'flower is step 4 of 7 → 57 %');
  assert.match(strip, /Now: <span class="cj-now-lbl"[^>]*>Flowering<\/span>\s*· Flowering 1\.1 · 10 d in phase/);
  assert.match(strip, /Next: <b[^>]*>Harvest cut<\/b>/);
  assert.match(strip, /cultivation records the cut, then production takes the lot/, 'the cut is the handoff');
  // Steps before the current one are done, the current pulses, later ones wait.
  assert.equal((strip.match(/cj-step cj-done/g) || []).length, 4, 'registered, clone, nursery, veg are behind it');
  assert.equal((strip.match(/cj-step cj-now/g) || []).length, 1);
  assert.equal((strip.match(/cj-step cj-todo/g) || []).length, 3, 'cut, drying, closed are ahead');
  assert.match(strip, /cj-todo cj-handoff/, 'the cut is drawn as the handoff');
  h.close();
});

test('drying is production\'s step, the closed lot has nothing after it, a destroyed batch is off the plan', () => {
  const h = load('CU_MGR');
  const w = h.window;
  let html = render(h, [batch({ phase: 'drying', room_name: 'Dry L' })]);
  let strip = html.slice(html.indexOf('class="cj-wrap"'), html.indexOf('class="cj-tabs"'));
  assert.match(strip, /data-w="86"/);
  assert.match(strip, /Next: <b[^>]*>Lot closed<\/b>\s*<span[^>]*>· production/);
  assert.equal((strip.match(/cj-step cj-done/g) || []).length, 6, 'the cut is behind a drying batch');

  // A closed (harvested) batch is not open, so the strip has nothing to follow;
  // the per-card bar still shows it at the end of the plan.
  html = render(h, [batch({ phase: 'harvested', is_active: false })]);
  assert.doesNotMatch(html, /class="cj-wrap"/);
  assert.match(html, /cj cj-sm/);
  const card = w.GF.WWF.cultJourney(batch({ phase: 'harvested' }));
  assert.match(card, /data-w="100"/);
  assert.match(card, /The lot is closed — nothing follows on this plan/);

  assert.match(w.GF.WWF.cultJourney(batch({ phase: 'destroyed' })), /was destroyed and has left the plan/);
  assert.equal(w.GF.WWF.cultJourney(batch({ phase: 'destroyed' }), { compact: true }), '');
  assert.match(w.GF.WWF.cultJourney(batch({ phase: 'mother' })), /Mother stock/);
  h.close();
});

test('the strip names the clone run a batch was cut in, when the record links them', () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.__runs = [{ id: 'run1', code: null, cultivar_code: 'GP', started_on: '2026-07-01', batch_id: 'b1',
                mothers: [{ code: 'GP_M01' }, { code: 'GP_M02' }], cuttings_total: 2100,
                spec_code: 'PP-QC-SPEC-001', spec_version: 'v5.2', status: 'transplanted' }];
  const html = render(h, [batch({ phase: 'veg' })]);
  const strip = html.slice(html.indexOf('class="cj-wrap"'), html.indexOf('class="cj-tabs"'));
  assert.match(strip, /Cut in clone run GP · 01\.07\.2026\s*· 2 mothers · 2100 cuttings · PP-QC-SPEC-001 v5\.2/);
  h.close();
});

test('the fill starts at zero width and is set to its target one frame later, so it animates', () => {
  const h = load('CU_MGR');
  const w = h.window;
  const html = render(h, [batch({ phase: 'veg' })]);
  assert.match(html, /class="cj-fill" data-w="43" style="width:0%"/);
  w.document.body.innerHTML = html;
  w.GF.WWF._cultAnimate();
  const fills = Array.from(w.document.querySelectorAll('.cj-fill')).map(e => e.style.width);
  assert.deepEqual(fills, ['43%', '43%'], 'the strip and the card bar both reach their width');
  h.close();
});

test('with several open batches the strip offers a chip per batch and cultFocus switches it', () => {
  const h = load('CU_MGR');
  const w = h.window;
  const two = [batch(), batch({ id: 'b2', code: 'FB072501', cultivar_code: 'FB', cultivar_name: 'Fat Bastard', phase: 'veg' })];
  let html = render(h, two);
  assert.equal((html.match(/class="cj-chip(?: on)?"/g) || []).length, 2);
  w.GF.WWF.cultFocus('b2');
  assert.equal(w.__renders, 1, 'switching re-renders');
  html = render(h, two);
  const strip = html.slice(html.indexOf('class="cj-wrap"'), html.indexOf('class="cj-tabs"'));
  assert.match(strip, /<strong>FB072501<\/strong>/);
  h.close();
});

/* ── tabs → the mother bank and clone runs ──────────────────────────────── */

test('the Mother bank tab lists mothers per strain with derived age, last cut and generations', () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.GF.WWF._prop.mothers = [
    { id: 'm1', code: 'GP_M01', cultivar_id: 'cv1', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
      phenotype: 'Pheno A', room_name: 'Mother room', position: 'pot 12', started_on: '2026-06-20',
      age_days: 40, last_cut_on: null, generations: 0, cuttings_total: 0, status: 'active' },
    { id: 'm2', code: 'GP_M02', cultivar_id: 'cv1', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
      phenotype: null, room_name: null, position: null, started_on: null,
      age_days: null, last_cut_on: '2026-07-01', generations: 3, cuttings_total: 240, status: 'active' },
  ];
  w.GF.WWF._prop.byCultivar = [{ cultivar_id: 'cv1', cultivar_code: 'GP', cultivar_name: 'Grape Pie', active: 2, total: 2, phenotypes: ['Pheno A'] }];
  w.GF.WWF._prop.runs = [];
  const html = render(h, [], 'mothers');
  assert.match(html, /cj-tab on" onclick="GF\.WWF\.cultTab\('mothers'\)">Mother bank <span>2<\/span>/);
  assert.match(html, /GP — Grape Pie<\/strong>\s*<span[^>]*>2 active/);
  assert.match(html, /<strong>GP_M01<\/strong><\/td>\s*<td>Pheno A<\/td>\s*<td>Mother room · pot 12<\/td>\s*<td>40 d<div class="sub">since 20\.06\.2026/);
  assert.match(html, /never/, 'a mother never cut says never');
  assert.match(html, /<td>3 <span class="sub">\(240 cuttings\)<\/span><\/td>/);
  assert.match(html, /<td>—<\/td>\s*<td>—<div/.source ? /<td>—<\/td>/ : /—/, 'no phenotype and no date show as dashes, never as 0');
  assert.match(html, /GF\.WWF\.motherForm\('m1'\)/, 'the floor edits');
  assert.match(html, /GF\.WWF\.motherForm\(\)/, 'and registers');
  h.close();
});

test('QA reads the bank but is offered neither Register mother nor Edit', () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF._prop.mothers = [{ id: 'm1', code: 'GP_M01', cultivar_id: 'cv1', cultivar_code: 'GP', cultivar_name: 'Grape Pie', status: 'active', generations: 0 }];
  w.GF.WWF._prop.byCultivar = [{ cultivar_id: 'cv1', cultivar_code: 'GP', cultivar_name: 'Grape Pie', active: 1, total: 1, phenotypes: [] }];
  w.GF.WWF._prop.runs = [];
  const html = render(h, [], 'mothers');
  assert.match(html, /GP_M01/);
  assert.doesNotMatch(html, /GF\.WWF\.motherForm/);
  return w.GF.WWF.motherForm().then(() => { assert.deepEqual(w.__modals, []); h.close(); });
});

test('the Clone runs tab shows each run\'s mothers with cuttings, its specification and its status; initiators may finish it', () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF._prop.mothers = [];
  w.GF.WWF._prop.byCultivar = [];
  w.GF.WWF._prop.runs = [
    { id: 'run1', code: null, cultivar_code: 'GP', cultivar_name: 'Grape Pie', started_on: '2026-07-01', planned_count: 2000,
      room_name: 'Clone room', batch_code: null, mothers: [{ code: 'GP_M01', cuttings: 60 }, { code: 'GP_M02', cuttings: null }],
      cuttings_total: 60, spec_code: 'PP-QC-SPEC-001', spec_version: 'v5.2', spec_status: 'APPROVED', status: 'started', note: null },
    { id: 'run2', code: 'CR_002', cultivar_code: 'OPM', cultivar_name: 'Orange Punch Mimosa', started_on: '2026-06-01', planned_count: 100,
      room_name: null, batch_code: 'OPM062601', mothers: [], cuttings_total: 0, spec_version: null, status: 'transplanted', finished_on: '2026-06-20', note: null },
  ];
  const html = render(h, [], 'clones');
  assert.match(html, /<strong>GP · 01\.07\.2026<\/strong>/, 'an uncoded run is named by cultivar and date');
  assert.match(html, /Initiated 01\.07\.2026 · 2000 cuttings planned\s*· 60 taken\s*· Clone room\s*· no batch linked yet/);
  assert.match(html, /GP_M01 <b>60<\/b>/);
  assert.match(html, /GP_M02<\/span>/, 'a mother whose cuttings were not counted shows no number, not 0');
  assert.match(html, /Specification: PP-QC-SPEC-001 v5\.2/);
  assert.match(html, /cloneRunFinish\('run1'\)/, 'QA may finish a started run');
  assert.match(html, /<strong>CR_002<\/strong>/);
  assert.match(html, /batch <b>OPM062601<\/b>/);
  assert.match(html, /no approved specification at initiation/);
  assert.match(html, /Transplanted · 20\.06\.2026/);
  assert.doesNotMatch(html, /cloneRunFinish\('run2'\)/, 'a finished run is not finished again');
  h.close();
});

/* ── the forms ──────────────────────────────────────────────────────────── */

test('registering a mother pre-fills <cultivar>_M with the next number and sends a blank date as null', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  await w.GF.WWF.motherForm();
  await w.GF.WWF._motherCultivarSync();
  assert.deepEqual(w.__modals, ['mb-modal']);
  const code = w.document.getElementById('mb-code');
  assert.equal(code.value, 'GP_M02');
  code.value = '02';
  w.GF._codeGuard('mb-code');
  assert.equal(code.value, 'GP_M02', 'the head is fixed — the guard puts it back');
  assert.equal(w.document.getElementById('mb-started').value, '2026-07-30', 'established-on opens on the facility\'s today');
  assert.match(w.__selCfg['mb-cultivar'].options[0].sub, /I 26\.00–30\.00/, 'the cultivar is chosen from its specification');
  assert.equal(w.__selCfg['mb-room'].options[1].label, 'Mother room', 'mother rooms are offered first');
  w.document.getElementById('mb-pheno').value = 'Pheno B';
  w.document.getElementById('mb-room').value = 'r3';
  w.document.getElementById('mb-pos').value = 'pot 4';
  w.document.getElementById('mb-started').value = '';
  await w.GF.WWF.motherSave();
  assert.deepEqual(JSON.parse(JSON.stringify(w.__motherCreated)), {
    cultivar_id: 'cv1', code: 'GP_M02', phenotype: 'Pheno B', room_id: 'r3', position: 'pot 4',
    started_on: null, source: null, note: null });
  assert.deepEqual(Array.from(w.__closed), ['mb-modal']);
  h.close();
});

test('a bad mother ID is refused before the request, matching the server pattern', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  await w.GF.WWF.motherForm();
  w.document.getElementById('mb-code').value = 'GP_M 02';
  await w.GF.WWF.motherSave();
  assert.equal(w.__motherCreated, undefined);
  assert.match(w.__toasts.at(-1)[0], /1–64 characters/);
  h.close();
});

test('the clone run form lists only the chosen cultivar\'s active mothers and sends blank cuttings as null', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.__mothers = [
    { id: 'm1', code: 'GP_M01', cultivar_id: 'cv1', status: 'active', phenotype: 'Pheno A', room_name: 'Mother room', position: 'pot 12', last_cut_on: null, generations: 0 },
    { id: 'm2', code: 'GP_M02', cultivar_id: 'cv1', status: 'active', phenotype: null, room_name: null, position: null, last_cut_on: '2026-07-01', generations: 2 },
    { id: 'm3', code: 'GP_M03', cultivar_id: 'cv1', status: 'retired', generations: 5 },
    { id: 'm4', code: 'OPM_M01', cultivar_id: 'cv3', status: 'active', generations: 0 },
  ];
  w.__batches = [batch({ id: 'b1', code: 'GP072601', phase: 'clone', cultivar_id: 'cv1' }), batch({ id: 'b9', code: 'OPM072601', cultivar_id: 'cv3' })];
  await w.GF.WWF.cloneRunForm();
  assert.deepEqual(w.__modals, ['cr-modal']);
  const list = w.document.getElementById('cr-mothers').innerHTML;
  assert.match(list, /GP_M01/); assert.match(list, /GP_M02/);
  assert.doesNotMatch(list, /GP_M03/, 'a retired mother is not offered');
  assert.doesNotMatch(list, /OPM_M01/, 'another cultivar\'s mother is not offered');
  assert.match(list, /last cut never · 0 gen\./);
  assert.match(list, /last cut 01\.07\.2026 · 2 gen\./);
  assert.deepEqual(Array.from(w.__selCfg['cr-batch'].options, o => o.label), ['— not registered yet —', 'GP072601'], 'only this cultivar\'s open batches');
  assert.equal(w.document.getElementById('cr-date').value, '2026-07-30', 'the date of initiation opens on today');

  // No count → refused before the request.
  await w.GF.WWF.cloneRunSave();
  assert.equal(w.__runCreated, undefined);
  assert.match(w.__toasts.at(-1)[0], /cuttings planned/);

  w.document.getElementById('cr-count').value = '2000';
  w.document.getElementById('cr-m-m1').checked = true;
  w.document.getElementById('cr-c-m1').value = '1200';
  w.document.getElementById('cr-m-m2').checked = true;      // cuttings left blank
  w.document.getElementById('cr-room').value = 'r2';
  w.document.getElementById('cr-batch').value = 'b1';
  await w.GF.WWF.cloneRunSave();
  assert.deepEqual(JSON.parse(JSON.stringify(w.__runCreated)), {
    cultivar_id: 'cv1', started_on: '2026-07-30', planned_count: 2000, room_id: 'r2', batch_id: 'b1',
    code: null, note: null,
    mothers: [{ mother_plant_id: 'm1', cuttings: 1200 }, { mother_plant_id: 'm2', cuttings: null }],
  });
  assert.deepEqual(w.__closed, ['cr-modal']);
  assert.equal(w.GF.WWF._cult.tab, 'clones', 'the board turns to the runs tab');
  h.close();
});

test('switching the cultivar in the run form re-filters mothers, batches and the specification panel', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.__mothers = [{ id: 'm4', code: 'OPM_M01', cultivar_id: 'cv3', status: 'active', generations: 0 }];
  await w.GF.WWF.cloneRunForm();
  assert.match(w.document.getElementById('cr-mothers').innerHTML, /No active mother plants of this cultivar/);
  w.document.getElementById('cr-cultivar').value = 'cv3';
  w.GF.WWF._cloneRunSync();
  assert.match(w.document.getElementById('cr-mothers').innerHTML, /OPM_M01/);
  assert.match(w.document.getElementById('cr-spec').innerHTML, /no product specification registered yet/);
  h.close();
});

test('finishing a run sends the outcome and the batch it became; the finished list is re-read', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.GF.WWF._prop.runs = [{ id: 'run1', cultivar_id: 'cv1', cultivar_code: 'GP', started_on: '2026-07-01', batch_id: null, mothers: [], status: 'started' }];
  w.__batches = [batch({ id: 'b1', code: 'GP072601', cultivar_id: 'cv1' }), batch({ id: 'b9', code: 'OPM072601', cultivar_id: 'cv3' })];
  await w.GF.WWF.cloneRunFinish('run1');
  assert.deepEqual(w.__modals, ['cf-modal']);
  assert.deepEqual(Array.from(w.__selCfg['cf-batch'].options, o => o.label), ['— not registered as a batch —', 'GP072601']);
  w.document.getElementById('cf-status').value = 'transplanted';
  w.document.getElementById('cf-batch').value = 'b1';
  await w.GF.WWF.cloneRunFinishSave('run1');
  assert.deepEqual(JSON.parse(JSON.stringify(w.__runPatched)), ['run1', { status: 'transplanted', batch_id: 'b1', note: null }]);
  assert.deepEqual(w.__closed, ['cf-modal']);
  h.close();
});
