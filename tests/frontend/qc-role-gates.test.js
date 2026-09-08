'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/core.js — GF.QC_WRITERS / GF.QC_QP / GF.QC_HOQC.

   Ten QC/LIMS view files (qcsample, qccustody, qcspec, qcpotency, qccoa,
   qcecoa, qcoos, qclab, qcgenealogy, qcleaves) used to each carry their own
   copy-pasted `_WRITERS` / `_QP` / `_HOQC` local role array. They now all
   read these three shared core.js constants instead. This file pins the
   constants' values and proves two of the ten actually consult the SAME
   array at render time — not independent copies frozen when each file
   loaded (the bug this refactor removes).
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
  // chooser.js is not loaded here — stub the same way document-view.test.js
  // does; neither test below reads the sampling-plan picker's own markup.
  window.GF.selectField = function () { return ''; };
  window.GF.API = { user: { role: 'QC_MGR' } };
`;

test('GF.QC_WRITERS / GF.QC_QP / GF.QC_HOQC carry the expected role sets', () => {
  const h = loadGF({ files: ['data.js', 'core.js'], preScript: PRE });
  // Array.from re-homes the jsdom-realm array into this realm — deepStrictEqual
  // (assert/strict) compares prototypes too, and a cross-realm Array fails that
  // even with identical elements (see dates-calendar.test.js for the same idiom).
  assert.deepEqual(Array.from(h.window.GF.QC_WRITERS), ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP']);
  assert.deepEqual(Array.from(h.window.GF.QC_QP), ['ADMIN', 'QP']);
  assert.deepEqual(Array.from(h.window.GF.QC_HOQC), ['ADMIN', 'QC_MGR', 'QP']);
});

function load() {
  return loadGF({
    files: ['data.js', 'core.js', 'datepicker.js', 'qcsample-view.js', 'qccustody-view.js'],
    preScript: PRE,
  });
}

function render(w) {
  w.GF.WWF._qcsm.samples = []; w.GF.WWF._qcsm.plans = [];
  w.GF.WWF._qccus.rqs = []; w.GF.WWF._qccus.sfr = [];
  return { sample: w.GF.views.qcsample(), custody: w.GF.views.qccustody() };
}

test('qcsample and qccustody both show their create form to a GF.QC_WRITERS role', () => {
  const h = load();
  const { sample, custody } = render(h.window);
  assert.ok(sample.includes('id="qsm-batch"'), 'QC_MGR (in GF.QC_WRITERS) sees the sample create form');
  assert.ok(custody.includes('id="qcu-mat"'), 'QC_MGR (in GF.QC_WRITERS) sees the RQS create form');
});

test('a role outside GF.QC_WRITERS sees neither create form', () => {
  const h = load();
  h.window.GF.API.user = { role: 'CU_MGR' };
  const { sample, custody } = render(h.window);
  assert.ok(!sample.includes('id="qsm-batch"'), 'CU_MGR (not in GF.QC_WRITERS) has no sample create form');
  assert.ok(!custody.includes('id="qcu-mat"'), 'CU_MGR (not in GF.QC_WRITERS) has no RQS create form');
});

test('qcsample and qccustody read the SAME shared array, not independent copies', () => {
  const h = load();
  const w = h.window;
  let seen = render(w);
  assert.ok(seen.sample.includes('id="qsm-batch"') && seen.custody.includes('id="qcu-mat"'),
    'both visible for QC_MGR before the mutation');
  // Removing QC_MGR from the ONE shared array must hide it in BOTH views at
  // once — proof this is a single source of truth. Before the refactor each
  // file held its own `_WRITERS` array, so this mutation could only ever
  // have affected one file at a time.
  const idx = w.GF.QC_WRITERS.indexOf('QC_MGR');
  w.GF.QC_WRITERS.splice(idx, 1);
  seen = render(w);
  assert.ok(!seen.sample.includes('id="qsm-batch"'), 'sample create form now hidden');
  assert.ok(!seen.custody.includes('id="qcu-mat"'), 'custody create form now hidden');
  w.GF.QC_WRITERS.splice(idx, 0, 'QC_MGR'); // restore for any later assertions
});
