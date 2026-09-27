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
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'codefield.js', 'qccoa-view.js'], preScript: PRE });
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

/* ── Fix round 2: the iCoA numeric box, the facility clock, the Void gate ── */

test('the numeric box is never parseFloat-ed: a comma is refused, a point number travels as text too (QR-13)', async () => {
  const h = load('QC_MGR');
  const w = h.window;
  renderCoaDetail(h, BASE);
  const fields = { 'qcr-param': '', 'qcr-name': 'Lead', 'qcr-val': '', 'qcr-num': '22,61', 'qcr-unit': '%',
                   'qcr-labv': '', 'qcr-lo': '', 'qcr-hi': '' };
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  let sent = null, toast = null;
  w.GF.API.qcAddResult = async (id, b) => { sent = b; return {}; };
  w.GF.API.qcCoa = async () => ({ coa: BASE, results: [], signatures: [] });
  w.GF.toast = (m) => { toast = m; };
  await w.GF.WWF.qcCoaAddResult('a1');
  assert.equal(sent, null, '22,61 is not silently sent as 22');
  assert.match(toast, /decimal/);
  fields['qcr-num'] = '22.61';
  await w.GF.WWF.qcCoaAddResult('a1');
  assert.equal(sent.result_numeric, 22.61);
  assert.equal(sent.result_value, '22.61', 'the typed number is sent as text so the server reconciles it');
  fields['qcr-val'] = '< LOQ'; fields['qcr-num'] = '';
  await w.GF.WWF.qcCoaAddResult('a1');
  assert.equal(sent.result_value, '< LOQ');
  assert.equal(sent.result_numeric, null);
  const src = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', '..', 'web', 'gf', 'qccoa-view.js'), 'utf8');
  assert.doesNotMatch(src, /parseFloat\(/, "no client-side number parsing left in the view");
});

test('a certificate signature and the CoQ preview print on the facility clock (R2-FE-02)', () => {
  const h = load('QC_MGR');
  const w = h.window;
  const coa = { ...BASE, status: 'RELEASED', decision: 'PASS', coq_generated_at: '2026-07-30T22:30:00+00:00' };
  w.GF.WWF._qccoa = Object.assign(w.GF.WWF._qccoa || {}, {
    coas: [coa], loading: false, error: null, specs: [], samples: [], labs: [], q: '', status: '',
    sel: coa.id, preview: coa.id,
    detail: { coa, results: [], signatures: [{ meaning: 'RELEASED', signer_name: 'Q', signer_role: 'QP',
                                               signed_at: '2026-07-30T06:05:00+00:00' }] },
  });
  w.GF.WWF._qccoq = { list: [], sel: null, loading: false, error: null, detail: null, cultivars: [] };
  const html = w.GF.views.qccoa();
  assert.match(html, /2026-07-30 08:05/, 'signature: 06:05 UTC is 08:05 at the facility');
  assert.doesNotMatch(html, /2026-07-30 06:05/);
  assert.match(html, /2026-07-31 00:30/, 'issued: 22:30 UTC is the next facility day');
});

test('the QP sees Void on a certificate; a CU manager does not (R2-FE-10)', () => {
  let html = renderCoaDetail(load('QP'), { ...BASE, status: 'APPROVED' });
  assert.match(html, /GF\.WWF\.qcCoaVoid\('a1'\)/);
  html = renderCoaDetail(load('QC_MGR'), { ...BASE, status: 'APPROVED' });
  assert.match(html, /GF\.WWF\.qcCoaVoid\('a1'\)/);
  html = renderCoaDetail(load('CU_MGR'), { ...BASE, status: 'APPROVED' });
  assert.doesNotMatch(html, /GF\.WWF\.qcCoaVoid\(/);
});
