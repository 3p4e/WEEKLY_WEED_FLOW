'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qcecoa-view.js — Promote button gating.

   workbench() already computes and displays three promotion gates
   (unmapped === 0, mappedCount > 0, the §6.3.2 checklist outcome ===
   'ACCEPTED') as a red/amber/green block. canPromote must require the
   same three conditions — otherwise a writer can click Promote at the
   exact moment the adjacent panel is showing a red block message.
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
  return loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'qcecoa-view.js'], preScript: PRE });
}

const DOC = { id: 'd1', doc_number: 'ECOA-0001', batch_id: 'B1', source_institution: 'Lab X',
              status: 'EXTRACTED', specification_id: 'spec1' };

// Render the document detail. `checklist` seeds st.checklist[doc.id] directly
// (an object, even {}), which is important: leaving it undefined would make
// checklistPanel() kick off its own (unstubbed) qcEcoaChecklistLoad fetch.
function renderDocDetail(h, doc, extractions, checklist) {
  const w = h.window;
  w.GF.WWF._qcecoa = Object.assign(w.GF.WWF._qcecoa || {}, {
    docs: [doc], ph: [], specs: [], loading: false, error: null,
    q: '', status: '', tab: 'docs', sel: doc.id, detailError: null, editEx: null,
    verify: {}, vhist: {}, qa: {}, chunks: {}, chunksOpen: {}, exParams: {}, mapParams: {},
    checklist: { [doc.id]: checklist },
    detail: { document: doc, extractions, originals: [] },
  });
  return w.GF.views.qcecoa();
}

const promoteBtn = (docId) => `GF.WWF.qcEcoaPromote('${docId}')`;

test('an unresolved placeholder hides Promote even though status + spec would otherwise allow it', () => {
  const h = load();
  const html = renderDocDetail(h, DOC, [
    { id: 'e1', raw_label: 'THC (unmapped)', grade_status: 'unmapped', parameter_id: null },
    { id: 'e2', raw_label: 'CBD', grade_status: 'graded', parameter_id: 'p1', complies: true },
  ], { outcome: 'ACCEPTED' });
  assert.ok(!html.includes(promoteBtn(DOC.id)), 'Promote must be hidden while an extraction is unmapped');
});

test('no mapped results hides Promote even with zero unmapped and an accepted checklist', () => {
  const h = load();
  const html = renderDocDetail(h, DOC, [], { outcome: 'ACCEPTED' });
  assert.ok(!html.includes(promoteBtn(DOC.id)), 'Promote must be hidden with nothing mapped to promote');
});

test('an unaccepted §6.3.2 checklist hides Promote even with clean, fully-mapped extractions', () => {
  const h = load();
  const clean = [{ id: 'e2', raw_label: 'CBD', grade_status: 'graded', parameter_id: 'p1', complies: true }];
  assert.ok(!renderDocDetail(h, DOC, clean, {}).includes(promoteBtn(DOC.id)), 'no outcome yet');
  assert.ok(!renderDocDetail(h, DOC, clean, { outcome: 'REJECTED' }).includes(promoteBtn(DOC.id)), 'checklist rejected');
});

test('Promote appears once every gate clears: mapped, nothing unmapped, checklist ACCEPTED', () => {
  const h = load();
  const clean = [{ id: 'e2', raw_label: 'CBD', grade_status: 'graded', parameter_id: 'p1', complies: true }];
  const html = renderDocDetail(h, DOC, clean, { outcome: 'ACCEPTED' });
  assert.ok(html.includes(promoteBtn(DOC.id)), 'Promote should render once all three gates are satisfied');
});

test('the same gates apply on a REVIEWED document, not only EXTRACTED', () => {
  const h = load();
  const reviewedDoc = { ...DOC, status: 'REVIEWED' };
  const withUnmapped = [
    { id: 'e1', raw_label: 'THC', grade_status: 'unmapped', parameter_id: null },
  ];
  assert.ok(!renderDocDetail(h, reviewedDoc, withUnmapped, { outcome: 'ACCEPTED' }).includes(promoteBtn(reviewedDoc.id)),
    'REVIEWED does not bypass the unmapped-placeholder gate');
  const clean = [{ id: 'e2', raw_label: 'CBD', grade_status: 'graded', parameter_id: 'p1', complies: true }];
  assert.ok(renderDocDetail(h, reviewedDoc, clean, { outcome: 'ACCEPTED' }).includes(promoteBtn(reviewedDoc.id)),
    'REVIEWED + all gates clear still offers Promote');
});
