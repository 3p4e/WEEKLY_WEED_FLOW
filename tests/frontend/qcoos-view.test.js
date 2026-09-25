'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qcoos-view.js — closing an OOS requires a disposition first.

   Neither "Advance to Closed" nor the "Close (QP)" shortcut checked that
   o.disposition was set before enabling — contrast qccoa-view.js's Advance
   button, disabled until a decision is recorded (QP_TARGETS[nxt] &&
   !c.decision). Closing an OOS without recording RELEASE/REJECT/REPROCESS/
   RETAIN would leave a QP "decision" with nothing behind it.
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
  window.GF.API = { user: { role: 'QP' } };
`;

function load(role) {
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'qcoos-view.js'], preScript: PRE });
  if (role) h.window.GF.API.user = { role };
  return h;
}

function renderOosDetail(h, oos) {
  const w = h.window;
  w.GF.WWF._qcoos = {
    rows: [oos], capa: [], loading: false, error: null,
    q: '', status: '', tab: 'oos', sel: oos.id,
    detail: { oos, register: [], notifications: [] },
  };
  return w.GF.views.qcoos();
}

const advanceToClosed = (id) => `GF.WWF.qcOosAdvance('${id}','CLOSED')`;

test('Advance to Closed is disabled (with an explanatory title) while disposition is unset', () => {
  const h = load('QP');
  const html = renderOosDetail(h, { id: 'o1', oos_number: 'OOS-0001', batch_id: 'B1', oos_type: 'OOS', status: 'PHASE_II', disposition: null });
  assert.ok(!html.includes(`onclick="${advanceToClosed('o1')}"`), 'no live onclick while disposition is unset');
  // A disabled button with the same label must still be present, not omitted
  // outright, so the writer sees why it's blocked.
  assert.match(html, /<button[^>]*disabled[^>]*>[^<]*(Advance to|Напредувај до)/);
  assert.match(html, /Set a disposition before closing|Поставете диспозиција пред затворање/);
});

test('Advance to Closed is enabled once a disposition is recorded', () => {
  const h = load('QP');
  const html = renderOosDetail(h, { id: 'o1', oos_number: 'OOS-0001', batch_id: 'B1', oos_type: 'OOS', status: 'PHASE_II', disposition: 'RELEASE' });
  assert.ok(html.includes(`onclick="${advanceToClosed('o1')}"`), 'Advance to Closed fires once disposition is set');
});

test('the "Close (QP)" shortcut is disabled while disposition is unset', () => {
  const h = load('QP');
  const html = renderOosDetail(h, { id: 'o1', oos_number: 'OOS-0001', batch_id: 'B1', oos_type: 'OOS', status: 'PHASE_I', disposition: null });
  assert.ok(!html.includes(`onclick="${advanceToClosed('o1')}"`), 'no live onclick on the shortcut while disposition is unset');
  assert.match(html, /<button[^>]*disabled[^>]*>[^<]*(Close \(QP\)|Затвори \(КЛ\))/);
});

test('the "Close (QP)" shortcut is enabled once a disposition is recorded', () => {
  const h = load('QP');
  const html = renderOosDetail(h, { id: 'o1', oos_number: 'OOS-0001', batch_id: 'B1', oos_type: 'OOS', status: 'PHASE_I', disposition: 'REJECT' });
  assert.ok(html.includes(`onclick="${advanceToClosed('o1')}"`), 'the shortcut fires once disposition is set');
});

test('a non-QP writer never sees either close affordance regardless of disposition', () => {
  const h = load('QC_MGR');
  const html = renderOosDetail(h, { id: 'o1', oos_number: 'OOS-0001', batch_id: 'B1', oos_type: 'OOS', status: 'PHASE_II', disposition: 'RELEASE' });
  assert.ok(!html.includes(advanceToClosed('o1')), 'closing is a QP/ADMIN-only decision');
});
