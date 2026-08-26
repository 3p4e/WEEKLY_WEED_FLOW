'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qcpotency-view.js — per-cultivar potency ladders (QCSP 001).

   The server owns the rules (approval second-person, ladder validation,
   disposition); this view renders stored state and never invents data:
   provisional ladders say so, DRAFT ladders offer Approve only to HoQC
   roles, and each tier links its A4 Product-Specification document.
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

function load(role) {
  const h = loadGF({ files: ['data.js', 'core.js', 'qcpotency-view.js'], preScript: PRE });
  if (role) h.window.GF.API.user = { role };
  return h;
}

const SPEC = {
  id: 'ps1', cultivar_code: 'GP', cultivar_name: 'Grape Pie', version: 'v5.2',
  variant: 'BASE_SPCs', status: 'DRAFT', floor_pct: 13.83, data_supported: false,
  effective_date: null, notes: 'Imported from the owner catalogue',
};
const RANGES = [
  { id: 'r1', tier: 1, range_min: 26, range_max: 30, nominal: 28, width_pp: 2 },
  { id: 'r2', tier: 2, range_min: 22, range_max: 26, nominal: 24, width_pp: 2 },
];

function render(h, spec, ranges) {
  const w = h.window;
  w.GF.API.qcSpecDocumentUrl = (id, tier) => `/qc/potency-specs/${id}/document?tier=${tier}`;
  w.GF.WWF._qcpot = {
    specs: [spec], sel: spec.id, detail: { spec, ranges }, q: '', status: '',
    loading: false, error: null, importing: false,
  };
  return w.GF.views.qcpotency();
}

test('ladder detail renders tiers, provisional badge and document links', () => {
  const h = load();
  const html = render(h, SPEC, RANGES);
  assert.ok(html.includes('Grape Pie'), 'cultivar name');
  assert.ok(html.includes('Spec I') && html.includes('Spec II'), 'roman tiers');
  assert.ok(html.includes('26 – 30%'), 'range rendered');
  assert.match(html, /provisional|привремено/);
  assert.ok(html.includes('/qc/potency-specs/ps1/document?tier=1'), 'A4 doc link per tier');
});

test('DRAFT ladder offers Approve to HoQC; APPROVED offers Supersede instead', () => {
  const h = load();
  let html = render(h, SPEC, RANGES);
  assert.ok(html.includes('qcPotApprove'), 'approve offered on DRAFT');
  html = render(h, { ...SPEC, status: 'APPROVED', effective_date: '2026-08-14' }, RANGES);
  assert.ok(!html.includes('qcPotApprove'), 'no approve on APPROVED');
  assert.ok(html.includes('qcPotSupersede'), 'supersede offered');
});

test('a CU_MGR sees the registry but no approve/import controls', () => {
  const h = load('CU_MGR');
  const html = render(h, SPEC, RANGES);
  assert.ok(html.includes('Grape Pie'));
  assert.ok(!html.includes('qcPotApprove'), 'no approve button');
  assert.ok(!html.includes('qcPotImport'), 'no import panel');
});

test('empty registry points at the catalogue import', () => {
  const h = load();
  h.window.GF.WWF._qcpot = { specs: [], sel: null, detail: null, q: '', status: '',
                             loading: false, error: null, importing: false };
  const html = h.window.GF.views.qcpotency();
  assert.match(html, /No potency ladders yet|Сè уште нема скали/);
});

/* ══════════════════════════════════════════════════════════════════════
   GF.WWF.qcPotPick / qcPotRetry — a failed detail fetch must surface an
   error + retry affordance, matching every sibling QC view (qcsample,
   qccustody, qclab, qcspec), instead of leaving the row selected with
   st.detail permanently null (an endless loading skeleton).
   ════════════════════════════════════════════════════════════════════ */

test('_qcpot initializes detailError alongside detail (mirrors sibling QC views)', () => {
  const h = load();
  assert.ok('detailError' in h.window.GF.WWF._qcpot, 'detailError present in initial state');
  assert.equal(h.window.GF.WWF._qcpot.detailError, null);
});

test('a failed detail fetch shows an error + retry row, not an endless skeleton', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qcpot = {
    specs: [SPEC], sel: SPEC.id, detail: null, detailError: 'network down',
    q: '', status: '', loading: false, error: null, importing: false,
  };
  const html = w.GF.views.qcpotency();
  assert.ok(html.includes('network down'), 'error message rendered');
  assert.ok(html.includes(`qcPotRetry('${SPEC.id}')`), 'retry button targets this row');
  assert.match(html, /Failed|Неуспешно/);
});

test('qcPotPick records detailError and toasts on a failed fetch', async () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qcpot.specs = [SPEC];
  w.GF.API.qcPotencySpec = async () => { throw new Error('network down'); };
  let toastMsg = null, toastKind = null;
  w.GF.toast = (m, k) => { toastMsg = m; toastKind = k; };
  await w.GF.WWF.qcPotPick(SPEC.id);
  assert.equal(w.GF.WWF._qcpot.detail, null, 'no detail on a failed fetch');
  assert.equal(w.GF.WWF._qcpot.detailError, 'network down');
  assert.equal(toastMsg, 'network down');
  assert.equal(toastKind, 'error');
});

test('qcPotRetry clears the error and re-fetches the same row', async () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qcpot.specs = [SPEC];
  w.GF.API.qcPotencySpec = async () => { throw new Error('network down'); };
  w.GF.toast = () => {};
  await w.GF.WWF.qcPotPick(SPEC.id);
  assert.equal(w.GF.WWF._qcpot.detailError, 'network down');

  w.GF.API.qcPotencySpec = async () => ({ spec: SPEC, ranges: RANGES });
  // qcPotRetry (like its qcSampleRetry sibling) fires qcPotPick without
  // awaiting it — flush the microtask queue via a macrotask so the retried
  // fetch has resolved before asserting on it.
  w.GF.WWF.qcPotRetry(SPEC.id);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(w.GF.WWF._qcpot.detailError, null, 'error cleared after a successful retry');
  assert.ok(w.GF.WWF._qcpot.detail, 'detail populated after the retry succeeds');
  assert.equal(w.GF.WWF._qcpot.detail.spec.id, SPEC.id);
});
