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

// The official ImB catalogue: one product per page, window = nominal ±10 %.
const GP26 = { id: 'p1', product_code: 'GP_THC26:CBD1', grade: 26, nominal_pct: 26,
               window_min: 23.40, window_max: 28.59, status: 'APPROVED' };
const GP18 = { id: 'p2', product_code: 'GP_THC18:CBD1', grade: 18, nominal_pct: 18,
               window_min: 16.20, window_max: 19.79, status: 'APPROVED' };
const FB18_DRAFT = { id: 'p3', product_code: 'FB_THC18:CBD1', grade: 18, nominal_pct: 18,
                     window_min: 16.20, window_max: 19.79, status: 'DRAFT' };
const CULTIVARS = [
  { id: 'cv1', code: 'GP', name: 'Grape Pie', is_active: true, products: [GP26, GP18] },
  { id: 'cv2', code: 'FB', name: 'Fat Bastard', is_active: true, products: [FB18_DRAFT] },
  { id: 'cv3', code: 'OPM', name: 'Orange Punch Mimosa', is_active: true, products: [] },
];
const CAMPAIGNS = [{ id: 'sc1', seq: 1, label: 'S1', started_on: '2026-06-01',
                     material: 'seeds', cultivar_id: 'cv1', cultivar_code: 'GP',
                     description: 'first selection', mothers_count: 2 }];
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
  w.GF.API.campaigns = async () => ({ campaigns: w.__campaigns || CAMPAIGNS });
  w.GF.API.campaignCreate = async (b) => { w.__campaignCreated = b; return { id: 'sc9', seq: 2, label: 'S2' }; };
  w.GF.API.qcProducts = async (q) => { w.__productsAsked = q; return [GP26, GP18]; };
  w.GF.API.motherNextCode = async (q) => { w.__nextAsked = q;
    return { acronym: 'GP', grade: 26, product_code: 'GP_THC26:CBD1', campaign_seq: 1,
             head: 'GP26_S1M02-1_', mother_no: 2, next_mother_no: 2, generation: 1,
             next_stock_no: 1, suggested: 'GP26_S1M02-1_001' }; };
  w.GF.API.motherPotency = async (id) => w.__potency || {
    mother_id: id, code: 'GP26_S1M01-1_001', product_code: 'GP_THC26:CBD1', window: [23.40, 28.59],
    product: { n: 2, avg: 24.5, min: 23.98, max: 25.02,
               values: [{ coq_number: 'CoQ-1', lot_code: 'L-1', total_thc: 23.98, on: '2026-08-01' },
                        { coq_number: 'CoQ-2', lot_code: 'L-2', total_thc: 25.02, on: '2026-08-20' }] },
    traced: { n: 0, avg: null, min: null, max: null, values: [] } };
  w.GF.API.motherCreate = async (b) => { w.__motherCreated = b; return { id: 'm9' }; };
  w.GF.API.motherPatch = async (id, b) => { w.__motherPatched = [id, b]; return { id }; };
  w.GF.API.cloneRuns = async () => ({ runs: w.__runs });
  w.GF.API.cloneRunCreate = async (b) => { w.__runCreated = b; return { id: 'run9' }; };
  w.GF.API.cloneRunPatch = async (id, b) => { w.__runPatched = [id, b]; return { id }; };
  w.GF.API.trichomeCheck = async (b) => { w.__trichome = b; return { id: 'tc9' }; };
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

test('QA is a floor writer: it registers, moves and edits the master data', () => {
  // The owner's amendment of 2026-09-05: "QA should be able to move a batch
  // through its phases or edit the cultivar master".
  const h = load('QA_MGR');
  const html = render(h, [batch({ plants_materialised: 0, plants_active: 0 })]);
  assert.match(html, /cultFillPlants\('b1'\)/, 'QA generates the plant ids');
  assert.match(html, /cultMoveForm\('b1'\)/, 'QA moves the batch');
  assert.match(html, /cultCultivarList\(\)/, 'QA edits the cultivar master');
  h.close();
  const q = load('QC_MGR');
  const qh = render(q, [batch()]);
  assert.doesNotMatch(qh, /cultMoveForm\('b1'\)/, 'QC is still not a floor role');
  q.close();
});

test('a registrar calling a write handler that is not theirs is refused', async () => {
  const h = load('QC_MGR');
  const w = h.window;
  await w.GF.WWF.cultBatchForm();
  assert.deepEqual(w.__modals, [], 'QC cannot open the register form');
  await w.GF.WWF.cloneRunForm();
  assert.deepEqual(w.__modals, [], 'QC cannot open the clone run form');
  h.close();
});

/* ── registering against the official product ──────────────────────────── */

test('the batch form offers the strain\'s APPROVED products with their windows', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF._cult.cultivars = CULTIVARS;
  await w.GF.WWF.cultBatchForm();
  await w.GF.WWF._cultBatchCultivarSync();
  assert.deepEqual(w.__modals, ['cu-batch-modal']);
  // the cultivar's sub-line lists its grades, drafts flagged
  const opts = w.__selCfg['cu-b-cultivar'].options;
  assert.match(opts[0].sub, /THC 26 · THC 18/);
  assert.match(opts[1].sub, /DRAFT/);
  assert.match(opts[2].sub, /no product specification yet/);
  // only APPROVED products may be a target: a draft's nominal can still change
  const prods = w.__selCfg['cu-b-product'].options;
  assert.deepEqual(Array.from(prods, o => o.label),
    ['— no target product —', 'GP · Grape Pie — THC 26', 'GP · Grape Pie — THC 18']);
  assert.equal(prods[1].sub, '23.40–28.59 %');
  const panel = w.document.getElementById('cu-b-spec').innerHTML;
  assert.match(panel, /GP_THC26:CBD1/);
  assert.match(panel, /23\.40 – 28\.59 %/);
  assert.match(panel, /QCSP 001 v\.03/);
  h.close();
});

test('a strain with no page says so, and the batch sends its product and clone source', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.GF.WWF._cult.cultivars = CULTIVARS;
  await w.GF.WWF.cultBatchForm();
  w.document.getElementById('cu-b-cultivar').value = 'cv3';
  await w.GF.WWF._cultBatchCultivarSync();
  const none = w.document.getElementById('cu-b-spec').innerHTML;
  assert.match(none, /no product specification registered yet/);
  assert.doesNotMatch(none, /<table/);

  w.document.getElementById('cu-b-cultivar').value = 'cv1';
  await w.GF.WWF._cultBatchCultivarSync();
  w.document.getElementById('cu-b-code').value = 'GP092603';
  w.document.getElementById('cu-b-count').value = '2000';
  w.document.getElementById('cu-b-product').value = 'p1';
  w.document.getElementById('cu-b-source').value = 'imported';
  await w.GF.WWF.cultBatchSave();
  assert.equal(w.__created.product_id, 'p1');
  assert.equal(w.__created.clone_source, 'imported');
  h.close();
});

/* ── the lanes ─────────────────────────────────────────────────────────── */

test('every open batch gets a lane on one axis, and the focused lane opens in full', () => {
  const h = load('CU_MGR');
  const w = h.window;
  const three = [
    batch({ id: 'b1', code: 'GP092601', phase: 'flower', product_code: 'GP_THC26:CBD1' }),
    batch({ id: 'b2', code: 'FB092601', phase: 'veg', room_name: 'Veg 2' }),
    batch({ id: 'b3', code: 'OPM092601', phase: 'clone', room_name: 'Clone room' }),
  ];
  const html = render(h, three);
  assert.equal((html.match(/class="cj-lane(?: on)?"/g) || []).length, 3, 'one lane per open batch');
  assert.equal((html.match(/class="cj-lane on"/g) || []).length, 1, 'exactly one is focused');
  assert.match(html, /class="cj-axis"/);
  assert.match(html, /GP092601[\s\S]*FB092601[\s\S]*OPM092601/, 'all three are drawn at once');
  // a closed batch is not on the plan any more
  const withClosed = render(h, three.concat([batch({ id: 'b4', code: 'X', phase: 'harvested' })]));
  assert.equal((withClosed.match(/class="cj-lane(?: on)?"/g) || []).length, 3);
  w.GF.WWF.cultFocus('b2');
  const after = render(h, three);
  const lane2 = after.slice(after.indexOf('FB092601'));
  assert.match(after, /class="cj-lane on"[^>]*onclick="GF\.WWF\.cultFocus\('b2'\)/);
  h.close();
});

test('a lane shows the expected window the SERVER computed, coloured by its state', () => {
  const h = load('CU_MGR');
  const w = h.window;
  const html = render(h, [
    batch({ id: 'b1', code: 'A', phase: 'veg', expected_next_phase: 'flower',
            expected_from: '2026-09-10', expected_to: '2026-09-13', window_state: 'early' }),
    batch({ id: 'b2', code: 'B', phase: 'flower', expected_next_phase: 'harvest',
            expected_from: '2026-09-01', expected_to: '2026-09-22', window_state: 'in_window',
            harvest_window_from: '2026-09-01', harvest_window_to: '2026-09-22',
            latest_trichome: { checked_on: '2026-09-03', verdict: 'approaching', pct_amber: 12 } }),
    batch({ id: 'b3', code: 'C', phase: 'flower', expected_from: '2026-08-01',
            expected_to: '2026-08-20', window_state: 'late', latest_trichome: null }),
  ]);
  assert.match(html, /class="cj-x-early">→ Flowering expected 10\.09–13\.09</);
  assert.match(html, /class="cj-x-in">harvest window 01\.09–22\.09<\/span> · <span class="cj-x-t">trichomes: <b>approaching<\/b> · 03\.09/);
  assert.match(html, /class="cj-x-late">harvest window 01\.08–20\.08/);
  assert.match(html, /class="cj-x-none">no trichome check recorded/);
  h.close();
});

test('the fills start at zero width and are set to their targets one frame later', () => {
  const h = load('CU_MGR');
  const w = h.window;
  const html = render(h, [batch({ id: 'b1', code: 'A', phase: 'veg' }),
                          batch({ id: 'b2', code: 'B', phase: 'flower' })]);
  assert.match(html, /class="cj-fill" data-w="43" style="width:0%"/);
  assert.match(html, /class="cj-fill" data-w="57" style="width:0%"/);
  w.document.body.innerHTML = html;
  w.GF.WWF._cultAnimate();
  const fills = Array.from(w.document.querySelectorAll('.cj-fill')).map(e => e.style.width);
  assert.ok(fills.length >= 3 && fills.every(x => x !== ''), 'every lane and the detail animate');
  h.close();
});

test('the detail block names the next step, whose it is, and the clone run', () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.__runs = [{ id: 'run1', code: null, cultivar_code: 'GP', started_on: '2026-07-01', batch_id: 'b1',
                mothers: [{ code: 'GP26_S1M01-1_001' }, { code: 'GP26_S1M02-1_001' }],
                cuttings_total: 2100, product_code: 'GP_THC26:CBD1', status: 'transplanted' }];
  const html = render(h, [batch({ id: 'b1', phase: 'flower' })]);
  assert.match(html, /Next: <b[^>]*>Harvest · cure · defoliation<\/b>/);
  assert.match(html, /cultivation records the cut, then production takes the lot/);
  assert.match(html, /Cut in clone run GP · 01\.07\.2026\s*· 2 mothers · 2100 cuttings · GP_THC26:CBD1/);
  h.close();
});

/* ── the trichome check ─────────────────────────────────────────────────── */

test('a flowering batch offers the trichome check to a writer and nobody else', () => {
  const h = load('CU_MGR');
  assert.match(render(h, [batch({ phase: 'flower' })]), /GF\.WWF\.trichomeForm\('b1'/);
  assert.doesNotMatch(render(h, [batch({ phase: 'veg' })]), /trichomeForm/,
    'the check belongs to flowering, where the harvest date is decided');
  h.close();
  const q = load('QC_MGR');
  assert.doesNotMatch(render(q, [batch({ phase: 'flower' })]), /trichomeForm/);
  q.close();
});

test('the check refuses a split that is not one field of view, and sends blanks as null', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF.trichomeForm('b1', 'GP092601');
  assert.deepEqual(w.__modals, ['tc-modal']);
  w.document.getElementById('tc-clear').value = '10';
  w.document.getElementById('tc-cloudy').value = '10';
  w.document.getElementById('tc-amber').value = '10';
  w.GF.WWF._tcSum();
  assert.match(w.document.getElementById('tc-sum').textContent, /Total 30 %/);
  await w.GF.WWF.trichomeSave('b1');
  assert.equal(w.__trichome, undefined, 'a split that is not 100 % is refused before the request');
  assert.match(w.__toasts.at(-1)[0], /about 100 %/);

  w.document.getElementById('tc-cloudy').value = '75';
  w.document.getElementById('tc-amber').value = '15';
  w.document.getElementById('tc-verdict').value = 'ready';
  w.document.getElementById('tc-mag').value = '60x';
  await w.GF.WWF.trichomeSave('b1');
  assert.equal(w.__trichome.pct_cloudy, 75);
  assert.equal(w.__trichome.verdict, 'ready');
  assert.equal(w.__trichome.magnification, '60x');
  assert.equal(w.__trichome.sample_sites, null, 'a blank count is "not counted", never 0');
  assert.deepEqual(Array.from(w.__closed), ['tc-modal']);
  h.close();
});

/* ── the mother bank ───────────────────────────────────────────────────── */

test('the bank shows the id\'s segments, times cut, and what the strain has tested', () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.GF.WWF._prop.mothers = [
    { id: 'm1', code: 'GP26_S1M01-1_001', product_id: 'p1', product_code: 'GP_THC26:CBD1',
      campaign_label: 'S1', generation: 1, parent_code: null, cultivar_id: 'cv1',
      cultivar_code: 'GP', cultivar_name: 'Grape Pie', phenotype: 'Pheno A',
      room_name: 'Mother room', position: 'pot 12', started_on: '2026-06-20', age_days: 40,
      last_cut_on: null, times_cut: 0, cuttings_total: 0, status: 'active',
      tested: { n: 2, avg: 24.5, min: 23.98, max: 25.02 } },
    { id: 'm2', code: 'GP26_S1M01-2_001', product_id: 'p1', product_code: 'GP_THC26:CBD1',
      campaign_label: 'S1', generation: 2, parent_code: 'GP26_S1M01-1_001', cultivar_id: 'cv1',
      cultivar_code: 'GP', cultivar_name: 'Grape Pie', phenotype: null, room_name: null,
      position: null, started_on: null, age_days: null, last_cut_on: '2026-07-01',
      times_cut: 3, cuttings_total: 240, status: 'active',
      tested: { n: 0, avg: null, min: null, max: null } },
  ];
  w.GF.WWF._prop.byCultivar = [{ cultivar_id: 'cv1', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
                                 active: 2, total: 2, phenotypes: ['Pheno A'],
                                 products: ['GP_THC26:CBD1'] }];
  w.GF.WWF._prop.runs = [];
  const html = render(h, [], 'mothers');
  assert.match(html, /GP26_S1M01-1_001/);
  assert.match(html, /S1 · gen\. 2 · of GP26_S1M01-1_001/, 'the second-generation mother names its parent');
  assert.match(html, /<td>3 <span class="sub">\(240 cuttings\)<\/span><\/td>/, 'times cut, not generations');
  assert.match(html, /<b>24\.50 %<\/b> <span class="sub">of 2<\/span>/, 'what the strain has tested');
  assert.match(html, /not tested yet/);
  assert.match(html, /GF\.WWF\.motherPotency\('m1'\)/);
  assert.match(html, /GF\.WWF\.campaignList\(\)/);
  h.close();
});

test('QA edits the bank too; QC reads it', () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF._prop.mothers = [{ id: 'm1', code: 'GP26_S1M01-1_001', product_code: 'GP_THC26:CBD1',
    campaign_label: 'S1', generation: 1, cultivar_id: 'cv1', cultivar_code: 'GP',
    cultivar_name: 'Grape Pie', status: 'active', times_cut: 0, tested: { n: 0 } }];
  w.GF.WWF._prop.byCultivar = [{ cultivar_id: 'cv1', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
                                 active: 1, total: 1, phenotypes: [], products: ['GP_THC26:CBD1'] }];
  w.GF.WWF._prop.runs = [];
  assert.match(render(h, [], 'mothers'), /GF\.WWF\.motherForm/);
  h.close();
  const q = load('QC_MGR');
  q.window.GF.WWF._prop.mothers = w.GF.WWF._prop.mothers;
  q.window.GF.WWF._prop.byCultivar = w.GF.WWF._prop.byCultivar;
  q.window.GF.WWF._prop.runs = [];
  const qh = render(q, [], 'mothers');
  assert.match(qh, /GP26_S1M01-1_001/);
  assert.doesNotMatch(qh, /GF\.WWF\.motherForm/);
  return q.window.GF.WWF.motherForm().then(() => {
    assert.deepEqual(Array.from(q.window.__modals), []);
    q.close();
  });
});

test('registering a mother composes the id from segments and sends them, not a string', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  await w.GF.WWF.motherForm();
  assert.deepEqual(Array.from(w.__modals), ['mb-modal']);
  assert.deepEqual(JSON.parse(JSON.stringify(w.__productsAsked)), { status: 'APPROVED' },
    'only approved pages may name a plant');
  assert.deepEqual(JSON.parse(JSON.stringify(w.__nextAsked)),
    { product_id: 'p1', campaign_id: 'sc1', generation: 1 });
  assert.equal(w.document.getElementById('mb-preview').textContent, 'GP26_S1M02-1_001');
  assert.equal(w.document.getElementById('mb-started').value, '2026-07-30',
    "established-on opens on the facility's today");

  w.document.getElementById('mb-pheno').value = 'Pheno B';
  w.document.getElementById('mb-pos').value = 'pot 4';
  w.document.getElementById('mb-started').value = '';
  w.document.getElementById('mb-stock').value = '7';
  await w.GF.WWF.motherSave();
  const sent = JSON.parse(JSON.stringify(w.__motherCreated));
  assert.equal(sent.product_id, 'p1');
  assert.equal(sent.campaign_id, 'sc1');
  assert.equal(sent.generation, 1);
  assert.equal(sent.stock_no, 7, 'a number the user typed is kept');
  assert.equal(sent.mother_no, null, 'an untouched number is left to the server');
  assert.equal(sent.started_on, null);
  assert.equal(sent.phenotype, 'Pheno B');
  assert.equal(sent.code, undefined, 'the id is composed by the server, never typed here');
  h.close();
});

test('a second-generation mother may name the plant it was cut from', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.GF.WWF._prop.mothers = [
    { id: 'm1', code: 'GP26_S1M01-1_001', product_id: 'p1', generation: 1 },
    { id: 'm2', code: 'GP26_S1M01-1_002', product_id: 'p1', generation: 1 },
    { id: 'm3', code: 'GP18_S1M01-1_001', product_id: 'p2', generation: 1 },
  ];
  await w.GF.WWF.motherForm();
  assert.equal(w.document.getElementById('mb-parent-wrap').style.display, 'none');
  w.document.getElementById('mb-gen').value = '2';
  await w.GF.WWF._motherSync();
  assert.equal(w.document.getElementById('mb-parent-wrap').style.display, '');
  assert.deepEqual(Array.from(w.__selCfg['mb-parent'].options, o => o.label),
    ['— not in the bank —', 'GP26_S1M01-1_001', 'GP26_S1M01-1_002'],
    'only first-generation mothers of the same product');
  h.close();
});

test('a mother\'s potency panel separates the strain\'s results from those traced to the plant', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  await w.GF.WWF.motherPotency('m1');
  assert.deepEqual(Array.from(w.__modals), ['mp-modal']);
  const body = w.document.getElementById('mp-modal-body').innerHTML;
  assert.match(body, /GP_THC26:CBD1 ·\s*window 23\.40–28\.59 %/);
  assert.match(body, /average <b>24\.50 %<\/b>/);
  assert.match(body, /2 results · 23\.98–25\.02 %/);
  assert.match(body, /CoQ-1<\/td><td>L-1<\/td>\s*<td><b>23\.98 %/);
  assert.match(body, /Nothing yet links a tested lot back to this mother/);
  h.close();
});

/* ── campaigns and clone runs ───────────────────────────────────────────── */

test('a campaign is opened by describing the event; the facility numbers it', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  await w.GF.WWF.campaignList();
  const list = w.document.getElementById('sc-modal-body').innerHTML;
  assert.match(list, /S1/);
  assert.match(list, /first selection/);
  assert.match(list, /2 mothers/);
  await w.GF.WWF.campaignForm();
  w.document.getElementById('sc-material').value = 'phenotypes';
  w.document.getElementById('sc-desc').value = 'pheno hunt';
  await w.GF.WWF.campaignSave();
  const sent = JSON.parse(JSON.stringify(w.__campaignCreated));
  assert.equal(sent.material, 'phenotypes');
  assert.equal(sent.description, 'pheno hunt');
  assert.equal(sent.seq, undefined, 'the number is the facility\'s running count, not a field');
  h.close();
});

test('the clone runs tab names the product and each mother\'s cutting number', () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF._prop.mothers = [];
  w.GF.WWF._prop.byCultivar = [];
  w.GF.WWF._prop.runs = [
    { id: 'run1', code: null, cultivar_code: 'GP', cultivar_name: 'Grape Pie',
      started_on: '2026-07-01', planned_count: 2000, room_name: 'Clone room', batch_code: null,
      mothers: [{ code: 'GP26_S1M01-1_001', cuttings: 60, cutting_no: 3 },
                { code: 'GP26_S1M02-1_001', cuttings: null, cutting_no: 1 }],
      cuttings_total: 60, product_code: 'GP_THC26:CBD1', product_status: 'APPROVED',
      status: 'started', note: null },
    { id: 'run2', code: 'CR_002', cultivar_code: 'OPM', cultivar_name: 'Orange Punch Mimosa',
      started_on: '2026-06-01', planned_count: 100, room_name: null, batch_code: 'OPM062601',
      mothers: [], cuttings_total: 0, product_code: null, status: 'transplanted',
      finished_on: '2026-06-20', note: null },
  ];
  const html = render(h, [], 'clones');
  assert.match(html, /GP26_S1M01-1_001 ·03 <b>60<\/b>/, 'the cutting number names the clones it produced');
  assert.match(html, /GP26_S1M02-1_001 ·01<\/span>/, 'uncounted cuttings show no number, not 0');
  assert.match(html, /Specification: GP_THC26:CBD1/);
  assert.match(html, /no product named/);
  assert.match(html, /cloneRunFinish\('run1'\)/);
  assert.doesNotMatch(html, /cloneRunFinish\('run2'\)/);
  h.close();
});

test('the clone run form offers the strain\'s products, its active mothers and the next cutting', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.__mothers = [
    { id: 'm1', code: 'GP26_S1M01-1_001', cultivar_id: 'cv1', status: 'active', phenotype: 'Pheno A',
      room_name: 'Mother room', position: 'pot 12', last_cut_on: '2026-07-01', times_cut: 2 },
    { id: 'm2', code: 'GP26_S1M02-1_001', cultivar_id: 'cv1', status: 'active', last_cut_on: null,
      times_cut: 0 },
    { id: 'm3', code: 'GP26_S1M03-1_001', cultivar_id: 'cv1', status: 'retired', times_cut: 5 },
  ];
  w.__batches = [batch({ id: 'b1', code: 'GP092601', phase: 'clone', cultivar_id: 'cv1' })];
  await w.GF.WWF.cloneRunForm();
  assert.deepEqual(Array.from(w.__modals), ['cr-modal']);
  assert.deepEqual(Array.from(w.__selCfg['cr-product'].options, o => o.label),
    ['— no product named —', 'GP_THC26:CBD1', 'GP_THC18:CBD1']);
  const list = w.document.getElementById('cr-mothers').innerHTML;
  assert.match(list, /GP26_S1M01-1_001/);
  assert.doesNotMatch(list, /GP26_S1M03-1_001/, 'a retired mother is not offered');
  assert.match(list, /next cutting 03/, 'the mother cut twice is on its third');
  assert.match(list, /next cutting 01/);

  w.document.getElementById('cr-count').value = '2000';
  w.document.getElementById('cr-product').value = 'p1';
  w.document.getElementById('cr-m-m1').checked = true;
  w.document.getElementById('cr-c-m1').value = '1200';
  w.document.getElementById('cr-m-m2').checked = true;
  await w.GF.WWF.cloneRunSave();
  const sent = JSON.parse(JSON.stringify(w.__runCreated));
  assert.equal(sent.product_id, 'p1');
  assert.deepEqual(sent.mothers, [{ mother_plant_id: 'm1', cuttings: 1200 },
                                  { mother_plant_id: 'm2', cuttings: null }]);
  h.close();
});

test('finishing a run sends the outcome and the batch it became', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.GF.WWF._prop.runs = [{ id: 'run1', cultivar_id: 'cv1', cultivar_code: 'GP',
                           started_on: '2026-07-01', batch_id: null, mothers: [], status: 'started' }];
  w.__batches = [batch({ id: 'b1', code: 'GP092601', cultivar_id: 'cv1' }),
                 batch({ id: 'b9', code: 'OPM092601', cultivar_id: 'cv3' })];
  await w.GF.WWF.cloneRunFinish('run1');
  assert.deepEqual(Array.from(w.__modals), ['cf-modal']);
  assert.deepEqual(Array.from(w.__selCfg['cf-batch'].options, o => o.label),
    ['— not registered as a batch —', 'GP092601']);
  w.document.getElementById('cf-status').value = 'transplanted';
  w.document.getElementById('cf-batch').value = 'b1';
  await w.GF.WWF.cloneRunFinishSave('run1');
  assert.deepEqual(JSON.parse(JSON.stringify(w.__runPatched)),
    ['run1', { status: 'transplanted', batch_id: 'b1', note: null }]);
  h.close();
});
