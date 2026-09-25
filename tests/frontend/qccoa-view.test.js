'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qccoa-view.js — signaturesPanel gating.

   The Annex 11 signing form must not render on a VOIDED/SUPERSEDED
   certificate (mirrors coqMetaPanel's exact status gate), and the
   `meaning` dropdown it offers must be filtered by the caller's role and
   the certificate's lifecycle position — the same defense-in-depth style
   as the Advance button's QP_TARGETS / canCoq() / canQP() gating.
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
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'qccoa-view.js'], preScript: PRE });
  if (role) h.window.GF.API.user = { role };
  return h;
}

// Render the certificate detail with one selected CoA. _qccoq is pre-seeded
// with a non-null list so GF.views.qccoa() doesn't kick off its own
// (unstubbed) loadQcCoqs() fetch.
function renderCoaDetail(h, coa) {
  const w = h.window;
  w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
    coas: [coa], loading: false, error: null, specs: [], samples: [], labs: [],
    q: '', status: '', sel: coa.id, preview: null,
    detail: { coa, results: [], signatures: [] },
  });
  w.GF.WWF._qccoq = { list: [], sel: null, loading: false, error: null, detail: null, cultivars: [] };
  return w.GF.views.qccoa();
}

const BASE = { id: 'a1', coa_number: 'iCoA-PP-2026-0001', batch_id: 'B1', cert_type: 'ICOA', status: 'DRAFT', decision: null };

// The page also renders a page-level status FILTER dropdown
// (<select id="qco-status">) whose <option>s are the exact same ST enum
// names (DRAFT/REVIEWED/APPROVED/RELEASED/SUPERSEDED/VOIDED) — a bare
// html.includes('value="APPROVED"') would false-positive off THAT dropdown
// regardless of the signing form. Scope every meaning assertion to the
// #qcsig-meaning select's own option list. Returns null when the sign form
// (and therefore the select) isn't rendered at all.
function sigMeaningValues(html) {
  const m = html.match(/<select id="qcsig-meaning">([\s\S]*?)<\/select>/);
  if (!m) return null;
  return [...m[1].matchAll(/<option value="([^"]+)">/g)].map((x) => x[1]);
}

test('signaturesPanel renders no signing form on a VOIDED certificate', () => {
  const h = load('QC_MGR');
  const html = renderCoaDetail(h, { ...BASE, status: 'VOIDED' });
  assert.equal(sigMeaningValues(html), null, 'no meaning select on a voided cert');
  assert.ok(!html.includes("qcCoaSign('a1')"), 'no sign button on a voided cert');
});

test('signaturesPanel renders no signing form on a SUPERSEDED certificate', () => {
  const h = load('QC_MGR');
  const html = renderCoaDetail(h, { ...BASE, status: 'SUPERSEDED' });
  assert.equal(sigMeaningValues(html), null, 'no meaning select on a superseded cert');
  assert.ok(!html.includes("qcCoaSign('a1')"), 'no sign button on a superseded cert');
});

test('a DRAFT certificate offers AUTHORED/REVIEWED but not APPROVED/RELEASED/COQ_ISSUED', () => {
  const h = load('QC_MGR');
  const html = renderCoaDetail(h, { ...BASE, status: 'DRAFT' });
  const values = sigMeaningValues(html) || [];
  assert.ok(values.includes('AUTHORED'));
  assert.ok(values.includes('REVIEWED'));
  assert.ok(!values.includes('APPROVED'), 'not reachable yet — cert is still DRAFT');
  assert.ok(!values.includes('RELEASED'));
  assert.ok(!values.includes('COQ_ISSUED'));
});

test('business-leadership roles (OWNER/CEO/COO) never see APPROVED/RELEASED, on either cert type', () => {
  for (const role of ['OWNER', 'CEO', 'COO']) {
    const h = load(role);
    const icoaValues = sigMeaningValues(renderCoaDetail(h, { ...BASE, cert_type: 'ICOA', status: 'REVIEWED' })) || [];
    assert.ok(!icoaValues.includes('APPROVED'), `${role} must not see APPROVED on an ICOA (HoQC-only)`);
    const ecoaValues = sigMeaningValues(renderCoaDetail(h, { ...BASE, cert_type: 'ECOA', status: 'APPROVED' })) || [];
    assert.ok(!ecoaValues.includes('RELEASED'), `${role} must not see RELEASED on an ECOA (QP-only)`);
  }
});

test('QC_MGR (Head of QC) sees APPROVED on a REVIEWED ICOA but not on a REVIEWED ECOA', () => {
  const h = load('QC_MGR');
  const icoaValues = sigMeaningValues(renderCoaDetail(h, { ...BASE, cert_type: 'ICOA', status: 'REVIEWED' })) || [];
  assert.ok(icoaValues.includes('APPROVED'), 'HoQC approves internal CoAs (_COQ_ROLES mirror)');
  const ecoaValues = sigMeaningValues(renderCoaDetail(h, { ...BASE, cert_type: 'ECOA', status: 'REVIEWED' })) || [];
  assert.ok(!ecoaValues.includes('APPROVED'), 'external CoA approval is QP-only, not QC_MGR');
});

test('QP sees APPROVED on a REVIEWED ECOA but not on a REVIEWED ICOA', () => {
  const h = load('QP');
  const ecoaValues = sigMeaningValues(renderCoaDetail(h, { ...BASE, cert_type: 'ECOA', status: 'REVIEWED' })) || [];
  assert.ok(ecoaValues.includes('APPROVED'));
  const icoaValues = sigMeaningValues(renderCoaDetail(h, { ...BASE, cert_type: 'ICOA', status: 'REVIEWED' })) || [];
  assert.ok(!icoaValues.includes('APPROVED'), 'ICOA approval is HoQC-only, not QP');
});

test('COQ_ISSUED is offered to QC_MGR on a RELEASED certificate, never to QP', () => {
  const h1 = load('QC_MGR');
  const values1 = sigMeaningValues(renderCoaDetail(h1, { ...BASE, status: 'RELEASED' })) || [];
  assert.ok(values1.includes('COQ_ISSUED'), 'QC Manager issues the CoQ');
  const h2 = load('QP');
  const values2 = sigMeaningValues(renderCoaDetail(h2, { ...BASE, status: 'RELEASED' })) || [];
  assert.ok(!values2.includes('COQ_ISSUED'), 'QP is deliberately excluded from issuing the CoQ');
});

test('VERIFIED is only offered while an EN-MK certificate is unverified', () => {
  const h = load('QC_MGR');
  const unverified = sigMeaningValues(renderCoaDetail(h, { ...BASE, status: 'RELEASED', issue_language: 'EN-MK', translation_verified_at: null })) || [];
  assert.ok(unverified.includes('VERIFIED'));
  const verified = sigMeaningValues(renderCoaDetail(h, { ...BASE, status: 'RELEASED', issue_language: 'EN-MK', translation_verified_at: '2026-08-20T10:00:00' })) || [];
  assert.ok(!verified.includes('VERIFIED'), 'already verified — no reason to offer it again');
  const english = sigMeaningValues(renderCoaDetail(h, { ...BASE, status: 'RELEASED', issue_language: 'EN', translation_verified_at: null })) || [];
  assert.ok(!english.includes('VERIFIED'), 'no translation to verify on an EN-only issue');
});
