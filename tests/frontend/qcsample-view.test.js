'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qcsample-view.js — GF.WWF.qcPlanCreate client-side validation.

   A sampling plan's min/max sample size drives real sample-size decisions
   once the plan is active, so a transposed range (min > max) is a real
   defect, not a cosmetic one — mirrors the same guard already added to
   qcSpecAddParam (qcspec-view.js) for spec parameter limits.
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
  return loadGF({ files: ['data.js', 'core.js', 'qcsample-view.js'], preScript: PRE });
}

function setup(h, fields) {
  const w = h.window;
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  w.__created = null;
  w.GF.API.qcCreateSamplingPlan = async (body) => { w.__created = body; return { id: 'p1', plan_id: 'PP-SPL-0001' }; };
  w.GF.API.qcSamplingPlans = async () => [];
  w.__toasts = [];
  w.GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  return w;
}

const FIELDS = (min, max, over = {}) => ({
  'qsp-mat': 'MAT-1', 'qsp-freq': 'EVERY_BATCH', 'qsp-formula': '',
  'qsp-min': min, 'qsp-max': max, ...over,
});

test('a transposed range (min > max) is refused before the request, with an EN/MK toast', async () => {
  const h = load();
  const w = setup(h, FIELDS('10', '5'));
  await w.GF.WWF.qcPlanCreate();
  assert.equal(w.__created, null, 'qcCreateSamplingPlan must not be called');
  assert.equal(w.__toasts.length, 1, 'exactly one toast shown');
  const [msg, kind] = w.__toasts[0];
  assert.equal(kind, 'error');
  assert.match(msg, /min sample size cannot exceed max sample size/i);
});

test('a valid range (min <= max) still calls the API, with both sizes sent', async () => {
  const h = load();
  const w = setup(h, FIELDS('5', '10'));
  await w.GF.WWF.qcPlanCreate();
  assert.ok(w.__created, 'qcCreateSamplingPlan must be called');
  assert.equal(w.__created.min_sample_size, 5);
  assert.equal(w.__created.max_sample_size, 10);
  // A success toast ("PP-SPL-... created") is expected here — only an error
  // toast would indicate the range guard misfired.
  assert.ok(!w.__toasts.some((t) => t[1] === 'error'), 'no error toast on a valid range');
});

test('an equal min and max is a valid (fixed-size) plan', async () => {
  const h = load();
  const w = setup(h, FIELDS('8', '8'));
  await w.GF.WWF.qcPlanCreate();
  assert.ok(w.__created, 'qcCreateSamplingPlan must be called when min === max');
});

test('only one of min/max present never trips the range guard', async () => {
  const h = load();
  const w = setup(h, FIELDS('10', ''));
  await w.GF.WWF.qcPlanCreate();
  assert.ok(w.__created, 'qcCreateSamplingPlan must be called; only one bound is present');
  assert.equal(w.__created.min_sample_size, 10);
  assert.equal(w.__created.max_sample_size, undefined);
});

test('material code is still required, and that check runs before the range guard', async () => {
  const h = load();
  const w = setup(h, FIELDS('10', '5', { 'qsp-mat': '  ' }));
  await w.GF.WWF.qcPlanCreate();
  assert.equal(w.__created, null);
  assert.match(w.__toasts[0][0], /material code is required/i);
});

/* ══════════════════════════════════════════════════════════════════════
   GF.WWF.qcSampleSubOf — opening "Add sub-sample" must start the create
   form CLEAN. Before the fix, the seed line spread the existing st.draft
   (`{ ...(st.draft || {}), batch, mat }`), so any field left behind by an
   earlier, abandoned "Collect sample" draft (type/loc/qty/unit/kind/notes/
   retention/plan) silently rode along into the sub-sample submission.
   ════════════════════════════════════════════════════════════════════ */

const PARENT = { id: 's1', sample_id: 'PP-SMP-0001', batch_id: 'B-1', material_code: 'MAT-1' };
// Round-trips a jsdom-realm object/array into this realm's plain Object/Array
// prototypes — deepStrictEqual (assert/strict) compares prototypes too, and a
// cross-realm value fails that even with identical own properties (same idiom
// as dept-attrs.test.js's local `plain` helper).
const plain = (o) => JSON.parse(JSON.stringify(o));

test('qcSampleSubOf resets the draft to just the parent prefill — no stale fields survive', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qcsm.samples = [PARENT];
  // Simulate an abandoned "Collect sample" draft: unrelated fields typed and
  // never submitted, still sitting in st.draft when "Add sub-sample" is clicked.
  w.GF.WWF._qcsm.draft = {
    batch: 'STALE-BATCH', mat: 'STALE-MAT', type: 'PC', loc: 'Room 3',
    qty: '5', unit: 'g', kind: 'RET', retexp: '2027-01-01',
    notes: 'leftover note', ret: true, plan: 'some-plan-id',
  };
  w.GF.WWF.qcSampleSubOf('s1');
  assert.deepEqual(plain(w.GF.WWF._qcsm.draft), { batch: 'B-1', mat: 'MAT-1' },
    'draft must contain ONLY the genealogy prefill — every stale field dropped');
  assert.deepEqual(plain(w.GF.WWF._qcsm.parent), {
    id: 's1', sample_id: 'PP-SMP-0001', batch_id: 'B-1', material_code: 'MAT-1',
  });
});

test('qcSampleSubOf starts clean even with no prior draft at all', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qcsm.samples = [PARENT];
  w.GF.WWF._qcsm.draft = null;
  w.GF.WWF.qcSampleSubOf('s1');
  assert.deepEqual(plain(w.GF.WWF._qcsm.draft), { batch: 'B-1', mat: 'MAT-1' });
});
