'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qccoa-view.js — the batch-CoQ detail shows the frozen potency grade.

   The aggregated Certificate of Quality freezes the cultivar's APPROVED
   PP-QC-SPEC-001 ladder at compile time; GET /qc/coq/{id} returns the resolved
   grade under `potency` (cultivar + tier + measured Total Δ9-THC + version).
   The on-screen detail must show it so the reviewer sees, before export, the
   same grade the issued .docx carries — and, per GxP, show NOTHING when no
   ladder was frozen (never a fabricated grade). The disposition arithmetic is
   the server's (backend/tests/test_potency.py); this view only renders it.
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
  window.GF.viewHead = function () { return '<head></head>'; };
  window.GF.API = { user: { role: 'QC_MGR' } };
`;

function load() {
  return loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'codefield.js', 'qccoa-view.js'], preScript: PRE });
}

// Render the batch-CoQ panel with one selected CoQ whose detail carries `potency`.
function renderCoqDetail(h, potency) {
  const w = h.window;
  w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
    coas: [], loading: false, error: null, specs: [], samples: [], labs: [],
    q: '', status: '', sel: null, detail: null,
  });
  const coq = {
    id: 'coq1', coq_number: 'CoQ-PP-2026-0005', batch_id: 'P0501242',
    status: 'APPROVED', overall_conform: true, spec_reference: 'PP-SPEC-2026-0001',
  };
  w.GF.WWF._qccoq = {
    list: [coq], sel: 'coq1', loading: false, error: null,
    detail: { coq, lines: [], sources: [], potency },
  };
  return w.GF.views.qccoa();
}

test('a frozen ladder shows the Cultivar row and the graded tier', () => {
  const h = load();
  const html = renderCoqDetail(h, {
    potency_spec_id: 'ps1', version: 'v5.2', spec_status: 'APPROVED',
    cultivar_code: 'GP', cultivar_name: 'Grape Pie', floor_pct: 13.83,
    total_d9_thc: 23.98, below_spec: false,
    disposition: { tier: 2, spec: 'Spec II', nominal: 24.0, range_min: 22, range_max: 26 },
  });
  assert.match(html, /Cultivar|Сорта/);
  assert.ok(html.includes('Grape Pie'), 'cultivar name shown');
  assert.ok(html.includes('Spec II'), 'graded tier shown');
  assert.ok(html.includes('24'), 'nominal shown');
  assert.ok(html.includes('23.98'), 'measured Total Δ9-THC shown');
  assert.ok(html.includes('PP-QC-SPEC-001 v5.2'), 'frozen ladder version cited');
});

test('below-floor batch shows "below specification", not a tier', () => {
  const h = load();
  const html = renderCoqDetail(h, {
    potency_spec_id: 'ps1', version: 'v5.2', spec_status: 'APPROVED',
    cultivar_code: 'GP', cultivar_name: 'Grape Pie', floor_pct: 13.83,
    total_d9_thc: 12.0, below_spec: true, disposition: null,
  });
  assert.match(html, /below specification|под спецификација/);
  assert.ok(!html.includes('Spec I'), 'no tier claimed when below the floor');
  assert.ok(html.includes('13.83'), 'floor shown');
});

test('no frozen ladder → no grade is fabricated on the CoQ', () => {
  const h = load();
  const html = renderCoqDetail(h, null);
  assert.ok(!html.includes('PP-QC-SPEC-001'), 'no ladder cited when none was frozen');
  assert.ok(!/>\s*(Grade|Оцена)\s*</.test(html), 'no Grade row rendered');
});

test('commercial identity renders only when present', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
    coas: [], loading: false, error: null, specs: [], samples: [], labs: [],
    q: '', status: '', sel: null, detail: null,
  });
  const coq = { id: 'c2', coq_number: 'CoQ-PP-2026-0009', batch_id: 'GP0824_02',
                status: 'APPROVED', overall_conform: true };
  w.GF.WWF._qccoq = {
    list: [coq], sel: 'c2', loading: false, error: null, cultivars: [],
    detail: { coq, lines: [], sources: [], potency: null,
              commercial: { neu_name: 'Grape Pie', brand: 'STEADY',
                            final_label: 'STEADY GP XY/1', thc_bracket: '22–25%' } },
  };
  let html = w.GF.views.qccoa();
  assert.ok(html.includes('Grape Pie') && html.includes('STEADY GP XY/1'), 'identity shown');
  // absent → the row disappears entirely (never fabricated)
  w.GF.WWF._qccoq.detail.commercial = null;
  html = w.GF.views.qccoa();
  assert.ok(!/Commercial identity|Комерцијален идентитет/.test(html), 'no identity row');
});

test('a product-graded CoQ shows the product, its window and the conformance verdict', () => {
  const h = load();
  let html = renderCoqDetail(h, {
    kind: 'product', product_id: 'p26', product_code: 'GP_THC26:CBD1', product_status: 'APPROVED',
    doc_code: 'QCSP 001', doc_version: 'v.03', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
    nominal: 26, window_min: 23.4, window_max: 28.59, total_d9_thc: 23.98, conforms: true,
    matching: ['GP_THC26:CBD1', 'GP_THC24:CBD1'], nearest: 'GP_THC24:CBD1', regrade_to: null,
  });
  assert.ok(html.includes('Grape Pie'), 'cultivar row');
  assert.ok(html.includes('GP_THC26:CBD1'), 'product code');
  assert.ok(html.includes('23.40–28.59 %') && html.includes('26.00 %'), 'window and nominal');
  assert.ok(html.includes('QCSP 001 v.03'), 'document cited, not the ladder');
  assert.ok(!html.includes('PP-QC-SPEC-001'), 'no ladder cited on a product-graded CoQ');
  assert.match(html, /✓ (conforms|одговара)/);
  assert.ok(html.includes('23.98'), 'measured Total Δ9-THC shown');
  assert.ok(!html.includes('qcq-regrade'), 'no regrade chip when it conforms');

  // outside the window: the owner's out-of-grade rule — flagged, and the
  // product whose window holds the value named
  html = renderCoqDetail(h, {
    kind: 'product', product_id: 'p26', product_code: 'GP_THC26:CBD1', product_status: 'APPROVED',
    doc_code: 'QCSP 001', doc_version: 'v.03', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
    nominal: 26, window_min: 23.4, window_max: 28.59, total_d9_thc: 22.1, conforms: false,
    matching: ['GP_THC24:CBD1'], nearest: 'GP_THC24:CBD1', regrade_to: 'GP_THC24:CBD1',
  });
  assert.match(html, /✗ (does not conform|не одговара)/);
  assert.ok(html.includes('qcq-regrade') && html.includes('GP_THC24:CBD1'), 'REGRADED → chip');
  assert.match(html, /REGRADED|ПРЕКЛАСИРАНО/);

  // outside every window of the strain: no regrade target is invented
  html = renderCoqDetail(h, {
    kind: 'product', product_id: 'p26', product_code: 'GP_THC26:CBD1', product_status: 'APPROVED',
    doc_code: 'QCSP 001', doc_version: 'v.03', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
    nominal: 26, window_min: 23.4, window_max: 28.59, total_d9_thc: 20.29, conforms: false,
    matching: [], nearest: 'GP_THC18:CBD1', regrade_to: null,
  });
  assert.match(html, /fits no grade|не одговара на ниту една класа/);
  assert.ok(!html.includes('→ GP_THC18:CBD1'), 'the nearest window is not presented as a regrade');
});

test('the compile form offers the APPROVED products and sends product_id, not cultivar_id', async () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
    coas: [], loading: false, error: null, specs: [], samples: [], labs: [],
    q: '', status: '', sel: null, detail: null,
  });
  w.GF.WWF._qccoq = { list: [], sel: null, loading: false, error: null, detail: null,
                      cultivars: [{ id: 'cv9', code: 'GP', name: 'Grape Pie', is_active: true }],
                      products: [{ id: 'p26', product_code: 'GP_THC26:CBD1', cultivar_code: 'GP',
                                   cultivar_name: 'Grape Pie', window_min: 23.4, window_max: 28.59,
                                   doc_version: 'v.03', status: 'APPROVED' }] };
  const html = w.GF.views.qccoa();
  assert.ok(html.includes('id="qcq-productid"'), 'product select present');
  assert.ok(html.includes('GP_THC26:CBD1 · Grape Pie · 23.40–28.59 % · v.03'), 'product option rendered');
  const fields = { 'qcq-batch': 'GP0824_02', 'qcq-spec': 'spec1', 'qcq-product': '',
                   'qcq-size': '', 'qcq-mfg': '', 'qcq-cultivar': 'cv9', 'qcq-productid': 'p26' };
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  let sent = null;
  w.GF.API.qcCompileCoq = async (b) => { sent = b; return { id: 'x', coq_number: 'CoQ-PP-2026-0011' }; };
  w.GF.API.qcCoqs = async () => [];
  w.GF.API.qcProducts = async () => [];
  w.GF.toast = () => {};
  await w.GF.WWF.qcCoqCompile();
  assert.ok(sent, 'compile called');
  assert.equal(sent.product_id, 'p26', 'the product grades the batch');
  assert.equal(sent.cultivar_id, undefined, 'the cultivar follows from the product server-side');
});

test('loadQcCoqs fetches the APPROVED products for the compile form once', async () => {
  const h = load();
  const w = h.window;
  const asked = [];
  w.GF.API.qcCoqs = async () => [];
  w.GF.API.qcProducts = async (q) => { asked.push(q); return []; };
  w.GF.API.cultivars = async () => ({ cultivars: [] });
  await w.GF.WWF.loadQcCoqs();
  await w.GF.WWF.loadQcCoqs();
  // JSON round-trip: the objects were made in the jsdom realm, whose Object
  // prototype is not Node's, and deepEqual compares prototypes.
  assert.deepEqual(JSON.parse(JSON.stringify(asked)), [{ status: 'APPROVED' }]);
});

test('the CoQ compile form carries the cultivar picker and sends cultivar_id', async () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
    coas: [], loading: false, error: null, specs: [], samples: [], labs: [],
    q: '', status: '', sel: null, detail: null,
  });
  w.GF.WWF._qccoq = { list: [], sel: null, loading: false, error: null, detail: null,
                      cultivars: [{ id: 'cv9', code: 'GP', name: 'Grape Pie', is_active: true }] };
  const html = w.GF.views.qccoa();
  assert.ok(html.includes('qcq-cultivar'), 'cultivar select present');
  assert.ok(html.includes('GP · Grape Pie'), 'cultivar option rendered');
  // drive qcCoqCompile: stub the DOM getters + API, assert the payload
  const fields = { 'qcq-batch': 'GP0824_02', 'qcq-spec': 'spec1', 'qcq-product': '',
                   'qcq-size': '', 'qcq-mfg': '', 'qcq-cultivar': 'cv9' };
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  let sent = null;
  w.GF.API.qcCompileCoq = async (b) => { sent = b; return { id: 'x', coq_number: 'CoQ-PP-2026-0010' }; };
  w.GF.API.qcCoqs = async () => [];
  w.GF.toast = () => {};
  await w.GF.WWF.qcCoqCompile();
  assert.ok(sent, 'compile called');
  assert.equal(sent.cultivar_id, 'cv9', 'cultivar_id sent → ladder freezes');
});

test('ICOA approve gating is HoQC, other types stay QP', () => {
  const h = load();   // QC_MGR
  const w = h.window;
  const mk = (cert_type) => {
    w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
      coas: [{ id: 'a1', coa_number: 'iCoA-PP-2026-0001', batch_id: 'B', cert_type,
               status: 'REVIEWED', decision: 'PASS' }],
      loading: false, error: null, specs: [], samples: [], labs: [],
      q: '', status: '', sel: 'a1',
      detail: { coa: { id: 'a1', coa_number: 'X', batch_id: 'B', cert_type,
                       status: 'REVIEWED', decision: 'PASS' },
                results: [], signatures: [], laboratory: null },
    });
    w.GF.WWF._qccoq = { list: [], sel: null, loading: false, error: null, detail: null, cultivars: [] };
    return w.GF.views.qccoa();
  };
  // a QC_MGR sees Advance-to-APPROVED on an ICOA (HoQC approves internal CoAs)…
  assert.ok(mk('ICOA').includes("qcCoaAdvance('a1','APPROVED')"), 'ICOA approve offered to QC_MGR');
  // …but NOT on an ECOA (QP-only there; the kick-back-to-draft button remains)
  assert.ok(!mk('ECOA').includes("qcCoaAdvance('a1','APPROVED')"), 'ECOA approve hidden from QC_MGR');
});

/* ── Fix round 2 (review 2026-09-27): the regrade follow-up, the testing
   period, the explicit sources, the strain-filtered product picker, the
   CoQ's own e-signatures and the Void gate. ─────────────────────────── */

function coqState(w, over) {
  w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
    coas: [], loading: false, error: null, specs: [], samples: [], labs: [],
    q: '', status: '', sel: null, detail: null,
  });
  w.GF.WWF._qccoq = Object.assign({ list: [], sel: null, loading: false, error: null, detail: null,
                                    cultivars: [], products: [], batchDraft: '' }, over || {});
  return w.GF.views.qccoa();
}

const PROD = (id, code, cv, lo, hi) => ({ id, product_code: code, cultivar_code: cv, cultivar_name: cv,
                                          window_min: lo, window_max: hi, doc_version: 'v.04', status: 'APPROVED' });

test('a regraded CoQ says whether its formal OOS is still owed, and names it once it exists', () => {
  const base = { kind: 'product', product_code: 'GP_THC26:CBD1', nominal: 26, window_min: 23.4, window_max: 28.59,
                 doc_code: 'QCSP 001', doc_version: 'v.03', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
                 total_d9_thc: 22.1, conforms: false, regrade_to: 'GP_THC24:CBD1' };
  let html = renderCoqDetail(load(), { ...base, regrade_oos: null, regrade_oos_pending: true });
  assert.match(html, /REGRADED/);
  assert.match(html, /formal OOS on the batch disposition: pending/);
  html = renderCoqDetail(load(), { ...base, regrade_oos: 'PP-OOS-2026-0007', regrade_oos_pending: false });
  assert.match(html, /formal OOS<\/?[^>]*>?:? ?PP-OOS-2026-0007|formal OOS: PP-OOS-2026-0007/);
  assert.doesNotMatch(html, /pending/);
});

test('the CoQ list flags an owed regrade OOS and a re-test period', () => {
  const h = load();
  const html = coqState(h.window, { list: [
    { id: 'q1', coq_number: 'CoQ-PP-2026-0012', batch_id: 'GP092601', status: 'APPROVED', overall_conform: true,
      purpose: 'RETEST', timepoint: '6M', regrade_oos_pending: true },
    { id: 'q2', coq_number: 'CoQ-PP-2026-0007', batch_id: 'GP092601', status: 'APPROVED', overall_conform: true,
      purpose: 'INITIAL', timepoint: null, regrade_oos_pending: null }] });
  assert.match(html, /qcq-period[^>]*>Re-test 6M</);
  assert.match(html, /OOS pending/);
  assert.equal((html.match(/qcq-period/g) || []).length, 1, 'an INITIAL CoQ carries no period chip');
});

test('the CoQ detail shows its testing period', () => {
  const h = load();
  const w = h.window;
  const coq = { id: 'c1', coq_number: 'CoQ-PP-2026-0012', batch_id: 'GP092601', status: 'DRAFT',
                overall_conform: true, purpose: 'RETEST', timepoint: '12M' };
  const html = coqState(w, { list: [coq], sel: 'c1', detail: { coq, lines: [], sources: [], signatures: [] } });
  assert.match(html, /Testing period|Период на тестирање/);
  assert.match(html, /Re-test 12M/);
});

test('the compile form sends purpose, timepoint and the chosen source certificates', async () => {
  const h = load();
  const w = h.window;
  coqState(w, {});
  const fields = { 'qcq-batch': 'GP092601', 'qcq-spec': 'spec1', 'qcq-product': '', 'qcq-size': '',
                   'qcq-mfg': '', 'qcq-cultivar': '', 'qcq-productid': '', 'qcq-purpose': 'RETEST',
                   'qcq-timepoint': '' };
  const srcSel = { selectedOptions: [{ value: 'coa-a' }, { value: 'coa-b' }] };
  w.document.getElementById = (id) => (id === 'qcq-sources' ? srcSel : (id in fields ? { value: fields[id] } : null));
  let sent = null, toast = null;
  w.GF.API.qcCompileCoq = async (b) => { sent = b; return { id: 'x', coq_number: 'CoQ-PP-2026-0012' }; };
  w.GF.API.qcCoqs = async () => [];
  w.GF.API.qcProducts = async () => [];
  w.GF.API.qcCoqOne = async () => ({ coq: {}, lines: [], sources: [] });
  w.GF.API.qcCoqSignatures = async () => [];
  w.GF.toast = (m) => { toast = m; };
  await w.GF.WWF.qcCoqCompile();
  assert.equal(sent, null, 'a RETEST without a timepoint is refused before the call');
  assert.match(toast, /timepoint/);
  fields['qcq-timepoint'] = '6M';
  await w.GF.WWF.qcCoqCompile();
  assert.ok(sent);
  assert.equal(sent.purpose, 'RETEST');
  assert.equal(sent.timepoint, '6M');
  assert.deepEqual(JSON.parse(JSON.stringify(sent.source_coa_ids)), ['coa-a', 'coa-b']);
});

test('the compile form offers the explicit source list and the purpose toggle', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qccoa = { coas: [
    { id: 'a1', coa_number: 'iCoA-PP-2026-0001', batch_id: 'GP092601', cert_type: 'ICOA', status: 'RELEASED' },
    { id: 'a2', coa_number: 'eCoA-PP-2026-0002', batch_id: 'GP092601', cert_type: 'ECOA', status: 'DRAFT' },
    { id: 'a3', coa_number: 'iCoA-PP-2026-0003', batch_id: 'CJ092601', cert_type: 'ICOA', status: 'APPROVED' }],
    loading: false, error: null, specs: [], samples: [], labs: [], q: '', status: '', sel: null, detail: null };
  w.GF.WWF._qccoq = { list: [], sel: null, loading: false, error: null, detail: null, cultivars: [],
                      products: [], batchDraft: 'GP092601' };
  const html = w.GF.views.qccoa();
  assert.match(html, /<select id="qcq-purpose"/);
  assert.match(html, /id="qcq-timepoint"/);
  const src = html.match(/<select id="qcq-sources"[^>]*>([\s\S]*?)<\/select>/);
  assert.ok(src, 'the source multi-select is rendered');
  assert.ok(src[1].includes('iCoA-PP-2026-0001'), 'a usable certificate of the batch is offered');
  assert.ok(!src[1].includes('eCoA-PP-2026-0002'), 'a DRAFT certificate is not a source');
  assert.ok(!src[1].includes('iCoA-PP-2026-0003'), 'another batch\'s certificate is not offered');
});

test('the product picker offers only the typed batch\'s strain (INS2-12), by the longest head', () => {
  const h = load();
  const w = h.window;
  const products = [PROD('p1', 'GP_THC26:CBD1', 'GP', 23.4, 28.59), PROD('p2', 'GPX_THC20:CBD1', 'GPX', 18, 21.99),
                    PROD('p3', 'CJ_THC28:CBD1', 'CJ', 26.4, 29.59)];
  const opts = (html) => [...html.match(/<select id="qcq-productid"[^>]*>([\s\S]*?)<\/select>/)[1]
    .matchAll(/<option value="([^"]*)"/g)].map(m => m[1]).filter(Boolean);
  assert.deepEqual(opts(coqState(w, { products, batchDraft: '' })), ['p1', 'p2', 'p3'], 'no batch yet: every product');
  assert.deepEqual(opts(coqState(w, { products, batchDraft: 'gp092601' })), ['p1'], 'GP… is Grape Pie only');
  assert.deepEqual(opts(coqState(w, { products, batchDraft: 'GPX092601' })), ['p2'], 'GPX… is not GP');
  assert.deepEqual(opts(coqState(w, { products, batchDraft: 'L-LEGACY' })), ['p1', 'p2', 'p3'], 'an unknown head filters nothing');
});

test('both certificate-creating batch ids are batch-code fields (INS2-05)', () => {
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', '..', 'web', 'gf', 'qccoa-view.js'), 'utf8');
  for (const id of ['qcq-batch', 'qco-batch']) {
    assert.match(src, new RegExp(`GF\\.batchCodeField\\('${id}'`), `${id} is a batch code field`);
    assert.doesNotMatch(src, new RegExp(`<input id="${id}"`), `${id} is no longer plain text`);
  }
  const h = load();
  const html = coqState(h.window, {});
  assert.match(html, /id="qcq-batch-cv"/, 'the strain chooser is in front of the CoQ batch');
  assert.match(html, /id="qco-batch-cv"/, 'and of the new-certificate batch');
});

const SIGNED_COQ = (status, over) => ({ id: 'c7', coq_number: 'CoQ-PP-2026-0007', batch_id: 'GP092601', status,
                                        overall_conform: true, compiled_by: 'u-comp', reviewed_by: 'u-rev', ...(over || {}) });

function signForm(role, id, coq, sigs) {
  const h = load();
  const w = h.window;
  w.GF.API.user = { role, id };
  const html = coqState(w, { list: [coq], sel: coq.id, detail: { coq, lines: [], sources: [], signatures: sigs || [] } });
  const m = html.match(/<select id="qcqsig-meaning">([\s\S]*?)<\/select>/);
  return { html, meanings: m ? [...m[1].matchAll(/<option value="([^"]+)">/g)].map(x => x[1]) : null };
}

test('the CoQ lists its e-signatures and offers the compiler COMPILED, the reviewer APPROVED (INV-01)', () => {
  const sig = { meaning: 'COMPILED', signer_id: 'u-comp', signer_name: 'Ana Compiler', signer_role: 'QC_MGR',
                signed_at: '2026-07-30T06:05:00+00:00', statement: null };
  let r = signForm('QC_MGR', 'u-comp', SIGNED_COQ('DRAFT'), []);
  assert.deepEqual(r.meanings, ['COMPILED']);
  r = signForm('QC_MGR', 'u-comp', SIGNED_COQ('DRAFT'), [sig]);
  assert.equal(r.meanings, null, 'already signed COMPILED — nothing more to offer');
  assert.match(r.html, /Ana Compiler/);
  assert.match(r.html, /2026-07-30 08:05/, 'the signature time prints on the facility clock');
  r = signForm('QC_MGR', 'u-rev', SIGNED_COQ('DRAFT'), [sig]);
  assert.equal(r.meanings, null, 'the reviewer signs APPROVED only once the CoQ is APPROVED');
  r = signForm('QC_MGR', 'u-rev', SIGNED_COQ('APPROVED'), [sig]);
  assert.deepEqual(r.meanings, ['APPROVED']);
  r = signForm('QC_MGR', 'u-other', SIGNED_COQ('APPROVED'), [sig]);
  assert.equal(r.meanings, null, 'nobody else is a role of record');
  r = signForm('QC_MGR', 'u-comp', SIGNED_COQ('VOIDED'), []);
  assert.equal(r.meanings, null, 'a VOIDED CoQ takes no signature');
});

test('signing a CoQ goes through qcCoqSign with the re-entered password', async () => {
  const h = load();
  const w = h.window;
  w.GF.API.user = { role: 'QC_MGR', id: 'u-comp' };
  coqState(w, { sel: 'c7' });
  const fields = { 'qcqsig-meaning': 'COMPILED', 'qcqsig-pw': 'pw-123', 'qcqsig-stmt': '' };
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  let sent = null;
  w.GF.API.qcCoqSign = async (id, b) => { sent = { id, b }; return { meaning: b.meaning }; };
  w.GF.API.qcCoqSignatures = async () => [];
  w.GF.API.qcCoqs = async () => [];
  w.GF.API.qcProducts = async () => [];
  w.GF.API.cultivars = async () => ({ cultivars: [] });
  w.GF.API.qcCoqOne = async () => ({ coq: SIGNED_COQ('DRAFT'), lines: [], sources: [] });
  w.GF.toast = () => {};
  await w.GF.WWF.qcCoqSign('c7');
  assert.deepEqual(JSON.parse(JSON.stringify(sent)), { id: 'c7', b: { meaning: 'COMPILED', password: 'pw-123', statement: null } });
});

test('the QP may void a CoQ but not approve or render it (R2-FE-10)', () => {
  const h = load();
  const w = h.window;
  w.GF.API.user = { role: 'QP', id: 'u-qp' };
  const coq = SIGNED_COQ('APPROVED', { coq_document_id: null });
  const html = coqState(w, { list: [coq], sel: coq.id, detail: { coq, lines: [], sources: [], signatures: [] } });
  assert.match(html, /GF\.WWF\.qcCoqVoid\('c7'\)/);
  assert.doesNotMatch(html, /GF\.WWF\.qcCoqRender\(/);
  assert.doesNotMatch(html, /GF\.WWF\.qcCoqReview\(/);
});

test('loading the CoQ list marks the regraded CoQs that still owe their formal OOS (INS2-01)', async () => {
  const h = load();
  const w = h.window;
  const asked = [];
  w.GF.API.qcCoqs = async (q) => {
    asked.push(JSON.parse(JSON.stringify(q)));
    if (q && q.regrade_oos_pending === 'true') return [{ id: 'q1' }];
    return [{ id: 'q1', coq_number: 'CoQ-PP-2026-0012', batch_id: 'GP092601', status: 'APPROVED',
              overall_conform: true, regrade_oos_pending: null },
            { id: 'q2', coq_number: 'CoQ-PP-2026-0013', batch_id: 'GP092602', status: 'DRAFT',
              overall_conform: true, regrade_oos_pending: null }];
  };
  w.GF.API.qcProducts = async () => [];
  w.GF.API.cultivars = async () => ({ cultivars: [] });
  await w.GF.WWF.loadQcCoqs();
  assert.deepEqual(asked, [{}, { regrade_oos_pending: 'true' }]);
  const list = w.GF.WWF._qccoq.list;
  assert.equal(list.find(q => q.id === 'q1').regrade_oos_pending, true);
  assert.equal(list.find(q => q.id === 'q2').regrade_oos_pending, null);
  w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
    coas: [], loading: false, error: null, specs: [], samples: [], labs: [], q: '', status: '', sel: null, detail: null });
  const html = w.GF.views.qccoa();
  assert.equal((html.match(/OOS pending/g) || []).length, 1, 'only the CoQ owing an OOS is flagged');
});
