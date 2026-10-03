'use strict';

/* ══════════════════════════════════════════════════════════════════════
   Stale-response guards on the cultivation, propagation, facility and
   irrigation loaders — second review 2026-09-27b, R2-FE-13.

   Each of these loaders is fired by a toggle, a retry or the reload after a
   save, so two can be in flight at once. Without a sequence guard the one
   that ANSWERS last wins, not the one that was ASKED last: a slow first load
   landing after the reload that follows a save puts back the list from
   before the save. waste-view.js already carried the guard (FE-16); these
   four did not.

   Every test starts two loads, answers the second first and the first last,
   and asserts the view keeps the second answer.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.WWF._ensureModal = function () {};
  window.GF.render = { all: function () {} };
  window.GF.viewHead = function () { return ''; };
  window.GF.openModal = function () {};
  window.GF.closeModal = function () {};
  window.GF.API = { user: { role: 'ADMIN' } };
`;

// A promise the test answers by hand, in the order it chooses.
function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

// Hand out one deferred per call, in call order.
function queue() {
  const calls = [];
  const fn = () => { const d = deferred(); calls.push(d); return d.promise; };
  fn.calls = calls;
  return fn;
}

test('loadCultivation keeps the answer to the LAST request', async () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'codefield.js', 'cultivation-view.js'], preScript: PRE });
  const GF = h.window.GF;
  const batches = queue();
  GF.API.cultivationBatches = batches;
  GF.API.cultivars = () => Promise.resolve({ cultivars: [] });
  GF.API.cloneRuns = () => Promise.resolve({ runs: [] });
  const first = GF.WWF.loadCultivation();
  const second = GF.WWF.loadCultivation();
  batches.calls[1].resolve({ batches: [{ id: 'new' }] });
  await second;
  batches.calls[0].resolve({ batches: [{ id: 'old' }] });
  await first;
  assert.deepEqual(GF.WWF._cult.batches.map(b => b.id), ['new']);
  assert.equal(GF.WWF._cult.loading, false);
  h.close();
});

test('a stale FAILURE does not overwrite a newer answer either', async () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'codefield.js', 'cultivation-view.js'], preScript: PRE });
  const GF = h.window.GF;
  const batches = queue();
  GF.API.cultivationBatches = batches;
  GF.API.cultivars = () => Promise.resolve({ cultivars: [] });
  GF.API.cloneRuns = () => Promise.resolve({ runs: [] });
  const first = GF.WWF.loadCultivation();
  const second = GF.WWF.loadCultivation();
  batches.calls[1].resolve({ batches: [{ id: 'new' }] });
  await second;
  batches.calls[0].reject(new Error('timed out'));
  await first;
  assert.equal(GF.WWF._cult.error, null, 'the older request\'s failure is not shown over the newer answer');
  assert.deepEqual(GF.WWF._cult.batches.map(b => b.id), ['new']);
  h.close();
});

test('loadPropagation keeps the answer to the LAST request', async () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'codefield.js', 'cultivation-view.js', 'propagation-view.js'], preScript: PRE });
  const GF = h.window.GF;
  const mothers = queue();
  GF.API.mothers = mothers;
  GF.API.cloneRuns = () => Promise.resolve({ runs: [] });
  GF.API.campaigns = () => Promise.resolve({ campaigns: [] });
  const first = GF.WWF.loadPropagation();
  const second = GF.WWF.loadPropagation();
  mothers.calls[1].resolve({ mothers: [{ id: 'new' }], by_cultivar: [] });
  await second;
  mothers.calls[0].resolve({ mothers: [{ id: 'old' }], by_cultivar: [] });
  await first;
  assert.deepEqual(GF.WWF._prop.mothers.map(m => m.id), ['new']);
  assert.equal(GF.WWF._prop.loading, false);
  h.close();
});

test('loadFacility keeps the answer to the LAST request', async () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'chooser.js', 'datepicker.js', 'codefield.js', 'facility-view.js'], preScript: PRE });
  const GF = h.window.GF;
  const facility = queue();
  GF.API.facility = facility;
  const first = GF.WWF.loadFacility();
  const second = GF.WWF.loadFacility();
  facility.calls[1].resolve({ rooms: [{ id: 'new' }] });
  await second;
  facility.calls[0].resolve({ rooms: [{ id: 'old' }] });
  await first;
  assert.deepEqual(GF.WWF._fac.data.rooms.map(r => r.id), ['new']);
  assert.equal(GF.WWF._fac.loading, false);
  h.close();
});

test('loadIrrigation keeps the answer to the LAST request', async () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js', 'irrigation-view.js'], preScript: PRE });
  const GF = h.window.GF;
  const irrigation = queue();
  GF.API.irrigation = irrigation;
  const first = GF.WWF.loadIrrigation();
  const second = GF.WWF.loadIrrigation();
  irrigation.calls[1].resolve({ feeds: [{ id: 'new' }] });
  await second;
  irrigation.calls[0].resolve({ feeds: [{ id: 'old' }] });
  await first;
  assert.deepEqual(GF.WWF._irr.feeds.map(f => f.id), ['new'],
    'the feed just recorded stays listed when the older load answers late');
  assert.equal(GF.WWF._irr.loading, false);
  h.close();
});
