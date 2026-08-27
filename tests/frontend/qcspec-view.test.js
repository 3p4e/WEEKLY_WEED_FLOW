'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qcspec-view.js — GF.WWF.qcSpecAddParam client-side validation.

   A spec's test parameters judge every batch CoA once the spec reaches
   ACTIVE, so a transposed lower/upper range (lower_limit > upper_limit) is a
   real compliance defect, not a cosmetic one. qcSpecAddParam must refuse to
   POST such a pair — and must not silently discard a legitimate `0` boundary
   value while parsing the two limit fields.
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
  return loadGF({ files: ['data.js', 'core.js', 'qcspec-view.js'], preScript: PRE });
}

// Stub document.getElementById with the exact ids qcSpecAddParam reads, and
// stub the API + toast so the assertions can see whether the request fired.
function setup(h, fields) {
  const w = h.window;
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  w.__added = null;
  w.GF.API.qcAddSpecParam = async (id, body) => { w.__added = [id, body]; return { id: 'p1' }; };
  w.GF.API.qcSpec = async () => ({ spec: { id: 'spec1', status: 'DRAFT' }, parameters: [] });
  w.__toasts = [];
  w.GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  return w;
}

const FIELDS = (lo, hi, over = {}) => ({
  'qcp-en': 'Total THC', 'qcp-mk': '', 'qcp-method': '', 'qcp-unit': '%',
  'qcp-lo': lo, 'qcp-hi': hi, 'qcp-ref': '', 'qcp-computed': '',
  'qcp-comp-a': '', 'qcp-comp-b': '', ...over,
});

test('a transposed range (lower > upper) is refused before the request, with an EN/MK toast', async () => {
  const h = load();
  const w = setup(h, FIELDS('15', '5'));
  await w.GF.WWF.qcSpecAddParam('spec1');
  assert.equal(w.__added, null, 'qcAddSpecParam must not be called');
  assert.ok(w.__toasts.length === 1, 'exactly one toast shown');
  const [msg, kind] = w.__toasts[0];
  assert.equal(kind, 'error');
  assert.match(msg, /lower limit cannot exceed upper limit/i, 'EN wording present (AL defaults to en)');
  h.close();
});

test('a valid range (lower <= upper) still calls the API, with both limits sent', async () => {
  const h = load();
  const w = setup(h, FIELDS('5', '15'));
  await w.GF.WWF.qcSpecAddParam('spec1');
  assert.ok(w.__added, 'qcAddSpecParam must be called');
  const [id, body] = w.__added;
  assert.equal(id, 'spec1');
  assert.equal(body.lower_limit, 5);
  assert.equal(body.upper_limit, 15);
  assert.equal(w.__toasts.length, 0, 'no error toast on a valid range');
  h.close();
});

test('an equal lower and upper limit is a valid (zero-width) range', async () => {
  const h = load();
  const w = setup(h, FIELDS('10', '10'));
  await w.GF.WWF.qcSpecAddParam('spec1');
  assert.ok(w.__added, 'qcAddSpecParam must be called when lower === upper');
  h.close();
});

test('a legitimate 0 boundary is parsed and sent, not discarded as falsy', async () => {
  const h = load();
  // lower_limit = 0, upper_limit = 5: a real, valid range whose lower bound is
  // exactly zero — must survive parsing and must not falsely trip the range
  // guard (0 is not > 5).
  const w = setup(h, FIELDS('0', '5'));
  await w.GF.WWF.qcSpecAddParam('spec1');
  assert.ok(w.__added, 'qcAddSpecParam must be called');
  const [, body] = w.__added;
  assert.equal(body.lower_limit, 0, 'the 0 boundary must be sent as the number 0, not null/blank');
  assert.equal(w.__toasts.length, 0, 'no error toast when 0 is the legitimate lower bound');
  h.close();
});

test('an upper limit of 0 with no lower limit is still sent as 0, not blank', async () => {
  const h = load();
  const w = setup(h, FIELDS('', '0'));
  await w.GF.WWF.qcSpecAddParam('spec1');
  assert.ok(w.__added, 'qcAddSpecParam must be called (only one bound present, nothing to compare)');
  const [, body] = w.__added;
  assert.equal(body.lower_limit, null);
  assert.equal(body.upper_limit, 0, 'the 0 upper bound must be sent as the number 0, not null');
  h.close();
});

test('a blank limit field never trips the range guard (only a real pair does)', async () => {
  const h = load();
  const w = setup(h, FIELDS('15', ''));
  await w.GF.WWF.qcSpecAddParam('spec1');
  assert.ok(w.__added, 'qcAddSpecParam must be called; only one bound is present');
  const [, body] = w.__added;
  assert.equal(body.lower_limit, 15);
  assert.equal(body.upper_limit, null);
  h.close();
});

test('test name is still required, and that check runs before the range guard', async () => {
  const h = load();
  const w = setup(h, FIELDS('15', '5', { 'qcp-en': '  ' }));
  await w.GF.WWF.qcSpecAddParam('spec1');
  assert.equal(w.__added, null);
  assert.match(w.__toasts[0][0], /test name required/i);
  h.close();
});

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qcspec-view.js — GF.WWF.qcSpecCreate's `version` parsing.

   `parseInt(mk('qcs-ver'), 10) || 1` silently substitutes 1 for a real
   version 0 (0 is falsy). Contrast the correct '' === '' ? null : parseFloat
   pattern used 14 lines later for spec-parameter limits (see the tests
   above) — version must apply the same "only default on a truly blank
   field" rule.
   ════════════════════════════════════════════════════════════════════ */

function setupCreate(h, fields) {
  const w = h.window;
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  w.__created = null;
  w.GF.API.qcCreateSpec = async (body) => { w.__created = body; return { id: 'sp1', spec_id: 'PP-QC-SPEC-0001' }; };
  w.GF.API.qcSpecs = async () => [];
  w.GF.API.qcSpec = async () => ({ spec: { id: 'sp1', status: 'INITIATED' }, parameters: [] });
  w.__toasts = [];
  w.GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  return w;
}

const CREATE_FIELDS = (ver, over = {}) => ({
  'qcs-mat': 'MAT-1', 'qcs-en': 'Test Material', 'qcs-mkn': '', 'qcs-ver': ver, 'qcs-grade': '', ...over,
});

test('a cleared version field ("0") is preserved as 0, not silently defaulted to 1', async () => {
  const h = load();
  const w = setupCreate(h, CREATE_FIELDS('0'));
  await w.GF.WWF.qcSpecCreate();
  assert.ok(w.__created, 'qcCreateSpec must be called');
  assert.equal(w.__created.version, 0, 'a legitimately typed 0 must survive, not become 1');
  h.close();
});

test('a genuinely blank version field defaults to 1', async () => {
  const h = load();
  const w = setupCreate(h, CREATE_FIELDS(''));
  await w.GF.WWF.qcSpecCreate();
  assert.ok(w.__created);
  assert.equal(w.__created.version, 1);
  h.close();
});

test('a whitespace-only version field also defaults to 1', async () => {
  const h = load();
  const w = setupCreate(h, CREATE_FIELDS('   '));
  await w.GF.WWF.qcSpecCreate();
  assert.ok(w.__created);
  assert.equal(w.__created.version, 1);
  h.close();
});

test('a normal positive version is still parsed correctly', async () => {
  const h = load();
  const w = setupCreate(h, CREATE_FIELDS('3'));
  await w.GF.WWF.qcSpecCreate();
  assert.ok(w.__created);
  assert.equal(w.__created.version, 3);
  h.close();
});
