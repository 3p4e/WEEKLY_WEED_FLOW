'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qcpotency-view.js — the product catalogue (QCSP 001).

   The server owns the rules (explicit windows, the ±10 % ceiling, second-
   person approval, one live specification version per strain, the
   out-of-grade verdict); this view renders stored state and never invents
   data: products list under their cultivar with status chips, DRAFT
   products offer Approve only to HoQC roles, imports run as a dry run
   before a real one, the A4 page is fetched with the bearer token (a plain
   link carried none — FE-09), and the retired ladders are read-only.
   No data rides inside an inline handler: controls carry data attributes
   and one delegated listener dispatches (qcPotAct).
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
  window.GF.API = { user: { role: 'QC_MGR' }, token: 'tok-123' };
`;

function load(role) {
  const h = loadGF({ files: ['data.js', 'core.js', 'api.js', 'qcpotency-view.js'], preScript: PRE });
  h.window.GF.API.user = { role: role || 'QC_MGR' };
  h.window.GF.API.token = 'tok-123';
  return h;
}

const GP26 = {
  id: 'p26', cultivar_id: 'cv-gp', cultivar_code: 'GP', cultivar_name: 'Grape Pie',
  product_code: 'GP_THC26:CBD1', grade: 26, nominal_pct: 26, window_min: 23.4, window_max: 28.59,
  doc_code: 'QCSP 001', doc_version: 'v.03', source: 'Tran02 p.13 (QCSP 001 v.03)', status: 'DRAFT',
  effective_date: null, approved_by: null, notes: 'Imported from the owner\'s ImB pages.',
  updated_at: '2026-09-27T08:00:00+00:00', tested: { n: 0, avg: null, min: null, max: null },
};
const GP24 = { ...GP26, id: 'p24', product_code: 'GP_THC24:CBD1', grade: 24, nominal_pct: 24,
               window_min: 21.6, window_max: 26.39, status: 'APPROVED', effective_date: '2026-09-20',
               tested: { n: 2, avg: 23.5, min: 23.1, max: 23.9 } };
const CJ28 = { ...GP26, id: 'c28', cultivar_id: 'cv-cj', cultivar_code: 'CJ', cultivar_name: 'Cap Junky',
               product_code: 'CJ_THC28:CBD1', grade: 28, nominal_pct: 28, window_min: 26.4, window_max: 29.59,
               doc_version: 'fitted 2026-09-15', status: 'DRAFT' };
const LADDER = { id: 'ps1', cultivar_code: 'GP', cultivar_name: 'Grape Pie', version: 'v5.2',
                 variant: 'BASE_SPCs', status: 'SUPERSEDED', floor_pct: 13.83, data_supported: false };

function state(w, over) {
  w.GF.WWF._qcpot = Object.assign(w.GF.WWF._qcpot, {
    products: [GP26, GP24, CJ28], ladders: [LADDER], sel: null, detail: null, detailError: null,
    ladderSel: null, ladderDetail: null, q: '', status: '', cultivar: '', loading: false, error: null,
    importing: false, imbPreview: null, fittedPreview: null, fittedText: '', fittedVersion: '',
    conf: null, confValue: '',
  }, over || {});
  return w.GF.views.qcpotency();
}

test('products list under their cultivar with window, version and status chips', () => {
  const h = load();
  const html = state(h.window);
  assert.ok(html.includes('Grape Pie') && html.includes('Cap Junky'), 'both cultivars head a group');
  assert.ok(html.includes('GP_THC26:CBD1') && html.includes('CJ_THC28:CBD1'));
  assert.ok(html.includes('23.40 – 28.59 %'), 'the stored window, never a derived one');
  assert.ok(html.includes('26.40 – 29.59 %'), 'a fitted window prints as stored');
  assert.ok(html.includes('fitted 2026-09-15'), 'document version shown');
  assert.match(html, /Draft|Нацрт/);
  assert.match(html, /Approved|Одобрено/);
  assert.ok(html.includes('tested') && html.includes('23.50'), 'tested-so-far summary on the row');
  // rows carry data attributes, not inline handlers with data in them
  assert.ok(html.includes('data-qcp-act="pick" data-id="p26"'));
  assert.ok(!html.includes("onclick=\"GF.WWF.qcPotPick('p26')\""), 'no data inside an inline handler');
  // the retired ladders are collapsed at the bottom, read-only
  assert.ok(html.includes('data-qcp-act="ladder-pick" data-id="ps1"'));
  assert.ok(!html.includes('qcPotLadderApprove') && !html.includes('data-qcp-act="ladder-approve"'),
    'no approve on a ladder');
});

test('the selected product shows nominal ± tolerance, provenance, history and the A4 button', () => {
  const h = load();
  const html = state(h.window, {
    sel: 'p24',
    detail: { product: GP24,
              tested: { n: 2, avg: 23.5, min: 23.1, max: 23.9,
                        values: [{ id: 'q1', number: 'CoQ-PP-2026-0005', lot_code: 'GP072501', total_thc: 23.1,
                                   on: '2026-09-21T10:00:00+00:00', conforms: true }] },
              cultivar_level: { n: 0, avg: null, min: null, max: null, values: [] },
              certificate_level: { n: 1, avg: 19.0, min: 19.0, max: 19.0,
                                   values: [{ id: 'c1', number: 'iCoA-1', lot_code: 'GP062401', total_thc: 19.0,
                                              on: '2026-08-01', conforms: false }] } },
  });
  assert.ok(html.includes('24.00 %') && html.includes('± 2.40 %'), 'nominal ± tolerance from the window');
  assert.ok(html.includes('21.60 – 26.39 %'));
  assert.ok(html.includes('QCSP 001 v.03'));
  assert.ok(html.includes('Tran02 p.13'), 'source printed');
  assert.ok(html.includes('GP072501') && html.includes('23.10 %'), 'history value chips');
  assert.ok(html.includes('GP062401') && html.includes('19.00 %'), 'certificate-level evidence kept apart');
  assert.ok(html.includes('data-qcp-act="doc" data-id="p24"'), 'A4 page is a fetch, not a plain link');
  assert.ok(!html.includes('href="/qc/products/p24/document"'), 'no unauthenticated link');
  assert.ok(html.includes('id="qcp-conf-val"'), 'conformance lookup offered');
});

test('DRAFT offers Approve to HoQC; APPROVED offers Supersede; CU_MGR gets neither nor imports', () => {
  let h = load();
  let html = state(h.window, { sel: 'p26', detail: { product: GP26, tested: { n: 0, values: [] } } });
  assert.ok(html.includes('data-qcp-act="approve" data-id="p26"'), 'approve on DRAFT');
  assert.ok(!html.includes('data-qcp-act="supersede"'));
  html = state(h.window, { sel: 'p24', detail: { product: GP24, tested: { n: 0, values: [] } } });
  assert.ok(html.includes('data-qcp-act="supersede" data-id="p24"'), 'supersede on APPROVED');
  assert.ok(!html.includes('data-qcp-act="approve"'));
  assert.ok(html.includes('id="qcp-fitted-json"') && html.includes('data-qcp-act="import-dry"'), 'HoQC sees imports');

  h = load('CU_MGR');
  html = state(h.window, { sel: 'p26', detail: { product: GP26, tested: { n: 0, values: [] } } });
  assert.ok(html.includes('Grape Pie'), 'registry readable');
  assert.ok(!html.includes('data-qcp-act="approve"') && !html.includes('data-qcp-act="supersede"'));
  assert.ok(!html.includes('qcp-fitted-json') && !html.includes('data-qcp-act="import"'), 'no import panel');
  assert.ok(html.includes('data-qcp-act="doc"'), 'the A4 page stays readable');
});

test('the legacy ladder import is offered only while no product exists', () => {
  const h = load();
  let html = state(h.window);
  assert.ok(!html.includes('data-qcp-act="ladders-import"'), 'hidden once products exist');
  html = state(h.window, { products: [], ladders: [] });
  assert.ok(html.includes('data-qcp-act="ladders-import"'), 'offered on an empty catalogue');
  assert.match(html, /No products yet|Сè уште нема производи/);
});

test('ImB import runs as a dry run first, then for real, and shows the preview', async () => {
  const h = load();
  const w = h.window;
  state(w);
  const calls = [];
  w.GF.API.qcImportProducts = async (b) => {
    calls.push(b);
    return { dry_run: b.dry_run, doc_code: 'QCSP 001', doc_version: 'v.03',
             created: [{ product_code: 'GP_THC26:CBD1' }], skipped: [], conflicts: [],
             cultivars_created: [{ code: 'GP', name: 'Grape Pie' }],
             cultivars_renamed: [{ code: 'PUM', from: 'Pure Michigan', to: 'Pure Michigen' }] };
  };
  w.GF.API.qcProducts = async () => [GP26];
  w.GF.API.qcPotencySpecs = async () => [];
  w.GF.toast = () => {};
  // Objects from the jsdom realm carry another Object prototype, and
  // deepEqual compares prototypes — round-trip through JSON to compare values.
  const plain = (x) => JSON.parse(JSON.stringify(x));
  await w.GF.WWF.qcPotImport(true);
  assert.deepEqual(plain(calls), [{ dry_run: true }]);
  let html = w.GF.views.qcpotency();
  assert.match(html, /Dry run|Пробно/);
  assert.ok(html.includes('PUM Pure Michigan → Pure Michigen'), 'a planned rename is shown');
  assert.match(html, /Nothing was written|Ништо не е запишано/);
  await w.GF.WWF.qcPotImport(false);
  assert.deepEqual(plain(calls[1]), { dry_run: false });
  html = w.GF.views.qcpotency();
  assert.match(html, /Imported|Внесено/);
});

test('the fitted import takes the service export as pasted JSON and needs a document version', async () => {
  const h = load();
  const w = h.window;
  state(w);
  const exportJson = JSON.stringify({ specs: [{ id: 'GP', name: 'Grape Pie', status: 'finished',
    ranges: [{ nominal: 24, tol: 2, lo: 22, hi: 25.99 }] }] });
  const fields = { 'qcp-fitted-json': exportJson, 'qcp-fitted-version': '' };
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  const sent = [];
  w.GF.API.qcImportFittedProducts = async (b) => { sent.push(b); return { dry_run: b.dry_run, created: [], skipped: [], conflicts: [], cultivars_created: [] }; };
  w.GF.API.qcProducts = async () => [GP26];
  w.GF.API.qcPotencySpecs = async () => [];
  const toasts = [];
  w.GF.toast = (m, k) => toasts.push([m, k]);
  await w.GF.WWF.qcPotImportFitted(true);
  assert.equal(sent.length, 0, 'nothing sent without a document version');
  assert.equal(toasts[0][1], 'error');
  fields['qcp-fitted-version'] = 'v.04';
  await w.GF.WWF.qcPotImportFitted(true);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].dry_run, true);
  assert.equal(sent[0].doc_version, 'v.04');
  assert.equal(sent[0].specs[0].id, 'GP');
  // a bare list is accepted too; junk is refused before any call
  assert.deepEqual(JSON.parse(JSON.stringify(w.GF.WWF.qcPotParseFitted('[{"id":"GP"}]').specs)), [{ id: 'GP' }]);
  assert.ok(w.GF.WWF.qcPotParseFitted('not json').error);
  assert.ok(w.GF.WWF.qcPotParseFitted('{"specs":[]}').error);
});

test('the conformance lookup asks about the selected product and renders the verdict and regrade', async () => {
  const h = load();
  const w = h.window;
  state(w, { sel: 'p26', detail: { product: GP26, tested: { n: 0, values: [] } } });
  w.document.getElementById = (id) => (id === 'qcp-conf-val' ? { value: '22,10' } : null);
  let asked = null;
  w.GF.API.qcProductConformance = async (q) => {
    asked = q;
    return { matching: ['GP_THC24:CBD1'], nearest: 'GP_THC24:CBD1',
             product: { product_code: 'GP_THC26:CBD1', conforms: false, regrade_to: 'GP_THC24:CBD1' } };
  };
  w.GF.refocus = () => {};
  await w.GF.WWF.qcPotConform();
  assert.deepEqual(JSON.parse(JSON.stringify(asked)), { cultivar_id: 'cv-gp', total_d9_thc: 22.1, product_id: 'p26' });
  const html = w.GF.views.qcpotency();
  assert.match(html, /outside|надвор од/);
  assert.match(html, /falls to|паѓа на/);
  assert.ok(html.includes('GP_THC24:CBD1'), 'regrade target shown');
  assert.ok(html.includes('value="22.10"'), 'the typed value is kept, comma decimal normalised');
});

test('the A4 page is fetched with the bearer token and opened from a blob URL', async () => {
  const h = load();
  const w = h.window;
  state(w);
  let fetched = null, opened = null, created = null;
  w.fetch = async (url, opts) => { fetched = { url, opts }; return { ok: true, blob: async () => new w.Blob(['<html>']) }; };
  w.URL.createObjectURL = (b) => { created = b; return 'blob:doc-1'; };
  w.URL.revokeObjectURL = () => {};
  w.open = (href) => { opened = href; return {}; };
  w.GF.toast = () => {};
  await w.GF.WWF.qcPotOpenDoc(w.GF.API.qcProductDocumentUrl('p26'), 'GP_THC26:CBD1');
  assert.equal(fetched.url, '/qc/products/p26/document');
  assert.equal(fetched.opts.headers.Authorization, 'Bearer tok-123');
  assert.ok(created instanceof w.Blob);
  assert.equal(opened, 'blob:doc-1');
  // a ladder page goes the same way, tier and all
  const el = w.document.createElement('button');
  el.setAttribute('data-qcp-act', 'ladder-doc'); el.setAttribute('data-id', 'ps1'); el.setAttribute('data-tier', '2');
  await w.GF.WWF.qcPotAct(el);
  assert.equal(fetched.url, '/qc/potency-specs/ps1/document?tier=2');
});

test('one delegated click handler dispatches by data attributes', async () => {
  const h = load();
  const w = h.window;
  w.document.body.innerHTML = state(w);
  let picked = null;
  w.GF.WWF.qcPotPick = async (id) => { picked = id; };
  const row = w.document.querySelector('[data-qcp-act="pick"][data-id="p26"]');
  row.querySelector('.qms-code').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  assert.equal(picked, 'p26', 'a click inside the row reaches the row\'s action');
  const el = w.document.createElement('button');
  el.setAttribute('data-qcp-act', 'approve'); el.setAttribute('data-id', 'p26');
  let approved = null;
  w.GF.WWF.qcPotApprove = async (id) => { approved = id; };
  await w.GF.WWF.qcPotAct(el);
  assert.equal(approved, 'p26');
});

test('a failed detail fetch shows an error + retry row, not an endless skeleton', async () => {
  const h = load();
  const w = h.window;
  let html = state(w, { sel: 'p26', detail: null, detailError: 'network down' });
  assert.ok(html.includes('network down'));
  assert.ok(html.includes('data-qcp-act="retry" data-id="p26"'));
  w.GF.WWF._qcpot.sel = null; w.GF.WWF._qcpot.detailError = null;
  w.GF.API.qcProduct = async () => { throw new Error('network down'); };
  let toastMsg = null;
  w.GF.toast = (m) => { toastMsg = m; };
  await w.GF.WWF.qcPotPick('p26');
  assert.equal(w.GF.WWF._qcpot.detailError, 'network down');
  assert.equal(toastMsg, 'network down');
  w.GF.API.qcProduct = async () => ({ product: GP26, tested: { n: 0, values: [] } });
  w.GF.WWF.qcPotRetry('p26');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(w.GF.WWF._qcpot.detailError, null);
  assert.equal(w.GF.WWF._qcpot.detail.product.id, 'p26');
  html = w.GF.views.qcpotency();
  assert.ok(html.includes('GP_THC26:CBD1'));
});

test('the status filter reloads and refocuses; search and cultivar filters narrow the list', async () => {
  const h = load();
  const w = h.window;
  state(w);
  w.GF.API.qcProducts = async (q) => { assert.equal(q.status, 'APPROVED'); return [GP24]; };
  w.GF.API.qcPotencySpecs = async () => [];
  let refocused = null;
  w.GF.refocus = (id) => { refocused = id; };
  await w.GF.WWF.qcPotStatus('APPROVED');
  assert.equal(w.GF.WWF._qcpot.status, 'APPROVED');
  assert.equal(refocused, 'qcp-status');
  let html = state(w, { q: 'cap' });
  assert.ok(html.includes('CJ_THC28:CBD1') && !html.includes('GP_THC26:CBD1'));
  html = state(w, { cultivar: 'cv-gp' });
  assert.ok(html.includes('GP_THC26:CBD1') && !html.includes('CJ_THC28:CBD1'));
  assert.ok(html.includes('<option value="cv-gp" selected>'));
});

test('hostile data is escaped everywhere it prints', () => {
  const h = load();
  const bad = { ...GP26, id: 'x"y', cultivar_name: '<img src=x onerror=alert(1)>', notes: '<script>1</script>',
                source: '"><b>' };
  const html = state(h.window, { products: [bad], sel: 'x"y', detail: { product: bad, tested: { n: 0, values: [] } } });
  assert.ok(!html.includes('<img src=x'), 'cultivar name escaped');
  assert.ok(!html.includes('<script>1</script>'), 'notes escaped');
  assert.ok(html.includes('data-id="x&quot;y"'), 'ids are escaped inside attributes');
});

test('the nav registration is the product catalogue, still under the qcpotency key', () => {
  const h = load();
  const reg = h.window.__reg;
  assert.equal(reg.key, 'qcpotency');
  assert.match(reg.label(), /Product catalogue|Каталог на производи/);
  h.window.GF.API.user = { role: 'USER' };
  assert.equal(reg.guard(), false);
  h.window.GF.API.user = { role: 'CU_MGR' };
  assert.equal(reg.guard(), true);
});
