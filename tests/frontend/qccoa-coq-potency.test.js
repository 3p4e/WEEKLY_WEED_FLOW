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
  return loadGF({ files: ['data.js', 'core.js', 'qccoa-view.js'], preScript: PRE });
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
