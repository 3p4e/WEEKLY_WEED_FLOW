'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/decon-view.js — the two routes that let a stuck record move on.

   Review 2026-09-27, FE-03 / FE-10 / BC-10:
     - No button called POST /decon/cycles/{id}/fail. A cycle with a positive
       or inconclusive swab could not be released, could not take more steps,
       and blocked a new cycle for its room in the campaign — the room was
       stuck in the app until someone called the API by hand.
     - The biosecurity panel fetched open failures only, so a check logged
       as pending (a contact plate read days later) vanished the moment it
       was saved, and no screen could record its result.
   And FE-16 / FE-20: the board had no stale-response guard, and the check
   form sent no date, so a check logged the next morning landed on the wrong
   day.

   These tests drive the real view and the real submit handlers.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// Objects built inside the jsdom realm are not reference-equal to Node's
// prototypes, so structural comparisons go through a JSON round-trip (the
// same idiom as modules.test.js).
const toJS = (v) => JSON.parse(JSON.stringify(v));

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.render = { all: function () { window.__renders = (window.__renders || 0) + 1; } };
  window.GF.viewHead = function (a, b, extra) { return '<head>' + (extra || '') + '</head>'; };
  window.GF.API = { user: { role: 'QA_MGR', facility_tz: 'Europe/Skopje' } };
`;

function load(role) {
  const h = loadGF({ files: ['data.js', 'core.js', 'decon-view.js'], preScript: PRE });
  const w = h.window;
  if (role) w.GF.API.user = { role, facility_tz: 'Europe/Skopje' };
  w.__toasts = []; w.__closed = [];
  w.GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  w.GF.WWF._ensureModal = function (id) {
    if (w.document.getElementById(id)) return;
    const wrap = w.document.createElement('div');
    wrap.id = id;
    wrap.innerHTML = '<div id="' + id + '-title"></div><div id="' + id + '-body"></div>';
    w.document.body.appendChild(wrap);
  };
  w.GF.openModal = () => {};
  w.GF.closeModal = (id) => { w.__closed.push(id); };
  w.GF.t = (k) => k;
  w.__selCfg = {};
  w.GF.selectField = (id, cfg) => { w.__selCfg[id] = cfg; return '<input type="hidden" id="' + id + '" value="' + (cfg.value || '') + '">'; };
  w.GF.once = async (btnId, fn) => fn();
  w.GF.API.deconCycles = async () => ({ cycles: [] });
  w.GF.API.deconCorridors = async () => null;
  w.GF.API.biosecurity = async () => ({ events: [] });
  w.GF.API.facility = async () => ({ rooms: [] });
  return h;
}

const CYCLE = (over = {}) => ({
  id: 'c1', room_id: 'r1', room_name: 'Flowering 1.1', campaign: 'hlvd', status: 'awaiting_verification',
  started_on: '2026-07-30', released_at: null, steps: {},
  swabs: { pending: 0, negative: 2, positive: 1, inconclusive: 0 }, ...over,
});

function renderCycle(h, cyc) {
  h.window.GF.WWF._decon.cycles = [cyc];
  h.window.GF.state.view = 'decon';
  return h.window.GF.views.decon();
}

/* ── Fail cycle ──────────────────────────────────────────────────────── */

test('QA is offered "Fail cycle" on an open cycle with a positive or inconclusive swab', () => {
  for (const bad of ['positive', 'inconclusive']) {
    const h = load('QA_MGR');
    const swabs = { pending: 0, negative: 2, positive: 0, inconclusive: 0 };
    swabs[bad] = 1;
    assert.match(renderCycle(h, CYCLE({ swabs })), /deconFailForm\('c1'\)/, `offered on a ${bad} swab`);
    assert.doesNotMatch(renderCycle(h, CYCLE({ swabs })), /deconRelease\(/, 'and release is not');
    h.close();
  }
});

test('"Fail cycle" is not offered when every swab is negative, pending, or the cycle is closed', () => {
  const h = load('QA_MGR');
  assert.doesNotMatch(renderCycle(h, CYCLE({ swabs: { pending: 1, negative: 2, positive: 0, inconclusive: 0 } })), /deconFailForm/,
    'a pending swab is not a verdict — wait for the result');
  assert.doesNotMatch(renderCycle(h, CYCLE({ swabs: { pending: 0, negative: 3, positive: 0, inconclusive: 0 } })), /deconFailForm/);
  assert.doesNotMatch(renderCycle(h, CYCLE({ status: 'failed' })), /deconFailForm/, 'already failed');
  assert.doesNotMatch(renderCycle(h, CYCLE({ status: 'released' })), /deconFailForm/);
  h.close();
});

test('the cleaning crew is never offered the fail decision — it is QA\'s, like the release', () => {
  const h = load('CU_MGR');
  assert.doesNotMatch(renderCycle(h, CYCLE()), /deconFailForm/);
  h.close();
});

test('failing a cycle needs a reason, then calls the fail route and reloads', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  const calls = [];
  w.GF.API.deconFail = async (id, body) => { calls.push([id, body]); return { status: 'failed' }; };
  let reloads = 0;
  w.GF.WWF.loadDecon = async () => { reloads++; };

  w.GF.WWF.deconFailForm('c1');
  assert.ok(w.document.getElementById('dc-fail-reason'), 'the form opens with a reason field');

  await w.GF.WWF.deconFailSave('c1');
  assert.deepEqual(calls, [], 'a blank reason never reaches the server');
  assert.equal(w.__toasts.at(-1)[1], 'error');

  w.document.getElementById('dc-fail-reason').value = '  swab RR-01-003 positive — full re-clean ordered ';
  await w.GF.WWF.deconFailSave('c1');
  assert.deepEqual(toJS(calls), [['c1', { reason: 'swab RR-01-003 positive — full re-clean ordered' }]]);
  assert.ok(w.__closed.includes('dc-fail-modal'));
  assert.equal(reloads, 1, 'the board reloads so the room shows as failed and a new cycle can start');
  h.close();
});

/* ── Biosecurity: pending checks get a result ────────────────────────── */

const EVENTS = [
  { id: 'e-fail', kind: 'ahu_filter', subject: 'AHU-3', occurred_on: '2026-07-29', result: 'fail', action_taken: 'filter replaced' },
  { id: 'e-pend', kind: 'contact_plate', subject: 'Cure bench 2', occurred_on: '2026-07-28', result: 'pending', action_taken: null },
  { id: 'e-null', kind: 'sentinel_bioassay', subject: 'Sentinel 1', occurred_on: '2026-07-27', result: null, action_taken: null },
  { id: 'e-pass', kind: 'gowning', subject: 'J. Doe', occurred_on: '2026-07-30', result: 'pass', action_taken: null },
];

test('the board loads biosecurity events unfiltered and lists failures AND checks awaiting a result', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  let q = null;
  w.GF.API.biosecurity = async (query) => { q = query; return { events: EVENTS }; };
  await w.GF.WWF.loadDecon();
  assert.equal(q.open_only, undefined, 'open_only would drop every pending check from the board');

  w.GF.state.view = 'decon';
  const html = w.GF.views.decon();
  assert.match(html, /1 open failure/);
  assert.match(html, /AHU-3/);
  assert.match(html, /2 check\(s\) awaiting a result/, 'pending and not-yet-read both count');
  assert.match(html, /Cure bench 2/);
  assert.match(html, /Sentinel 1/);
  assert.doesNotMatch(html, /J\. Doe/, 'a passing check is routine and gets no place on the board');
  // The action carries the id as data, never inside a handler.
  assert.match(html, /data-act="bio-result" data-id="e-pend"/);
  assert.doesNotMatch(html, /onclick="[^"]*e-pend/);
  h.close();
});

test('a reader without record rights sees the awaiting list but no action', async () => {
  const h = load('QC_MGR');
  const w = h.window;
  w.GF.API.biosecurity = async () => ({ events: EVENTS });
  await w.GF.WWF.loadDecon();
  w.GF.state.view = 'decon';
  const html = w.GF.views.decon();
  assert.match(html, /Cure bench 2/);
  assert.doesNotMatch(html, /data-act="bio-result"/);
  h.close();
});

test('"Enter result" is delegated: clicking the rendered row opens the result form for that event', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.API.biosecurity = async () => ({ events: EVENTS });
  await w.GF.WWF.loadDecon();
  w.GF.state.view = 'decon';
  w.document.body.innerHTML = w.GF.views.decon();
  w.document.querySelector('[data-act="bio-result"][data-id="e-pend"]').click();
  assert.match(w.document.getElementById('dc-bres-modal-title').textContent, /Cure bench 2/);
  assert.ok(w.__selCfg['dc-bres-val'], 'the result chooser is rendered');
  assert.deepEqual(toJS(w.__selCfg['dc-bres-val'].options.map(o => o.v)), ['pass', 'fail', 'below_spec'],
    'pending is not a result a read can resolve to');
  h.close();
});

test('a failing biosecurity result needs the action taken; a pass does not', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  w.GF.WWF._decon.biosecurity = { events: EVENTS };
  const calls = [];
  w.GF.API.biosecurityResult = async (id, body) => { calls.push([id, body]); return {}; };
  w.GF.WWF.loadDecon = async () => {};

  w.GF.WWF.bioResultForm('e-pend');
  w.document.getElementById('dc-bres-val').value = 'fail';
  await w.GF.WWF.bioResultSave('e-pend');
  assert.deepEqual(calls, [], 'a failure with no response never reaches the server');
  assert.equal(w.__toasts.at(-1)[1], 'error');

  w.document.getElementById('dc-bres-action').value = 'bench re-sanitised, re-plated';
  await w.GF.WWF.bioResultSave('e-pend');
  assert.deepEqual(toJS(calls), [['e-pend', { result: 'fail', action_taken: 'bench re-sanitised, re-plated' }]]);

  w.GF.WWF.bioResultForm('e-null');
  w.document.getElementById('dc-bres-val').value = 'pass';
  await w.GF.WWF.bioResultSave('e-null');
  assert.deepEqual(toJS(calls[1]), ['e-null', { result: 'pass', action_taken: null }]);
  h.close();
});

/* ── The check form carries its date ─────────────────────────────────── */

test('logging a check sends occurred_on, pre-filled with the facility today', async () => {
  const h = load('CU_MGR');
  const w = h.window;
  let sent = null;
  w.GF.API.biosecurityLog = async (body) => { sent = body; return {}; };
  w.GF.WWF.loadDecon = async () => {};
  await w.GF.WWF.bioForm();
  const date = w.document.getElementById('dc-bio-date');
  assert.ok(date, 'the form has a date');
  assert.equal(date.value, w.GF.facilityToday(), 'pre-filled with the facility day, never the browser\'s');
  w.document.getElementById('dc-bio-kind').value = 'contact_plate';
  w.document.getElementById('dc-bio-subject').value = 'Cure bench 2';
  w.document.getElementById('dc-bio-result').value = 'pending';
  await w.GF.WWF.bioSave();
  assert.equal(sent.occurred_on, w.GF.facilityToday());
  assert.equal(sent.result, 'pending');
  // A backdated check is sent as typed.
  await w.GF.WWF.bioForm();
  w.document.getElementById('dc-bio-date').value = '2026-07-28';
  w.document.getElementById('dc-bio-kind').value = 'gowning';
  await w.GF.WWF.bioSave();
  assert.equal(sent.occurred_on, '2026-07-28');
  h.close();
});

/* ── Stale responses never overwrite a newer load ─────────────────────── */

test('an older loadDecon response landing last does not overwrite the newer one', async () => {
  const h = load('QA_MGR');
  const w = h.window;
  const pending = [];
  w.GF.API.deconCycles = () => new Promise(res => pending.push(res));
  w.GF.API.deconCorridors = async () => null;
  w.GF.API.biosecurity = async () => null;
  const first = w.GF.WWF.loadDecon();    // campaign A, slow
  const second = w.GF.WWF.loadDecon();   // campaign B, fast
  pending[1]({ cycles: [{ id: 'B' }] });
  await second;
  pending[0]({ cycles: [{ id: 'A' }] });
  await first;
  assert.deepEqual(w.GF.WWF._decon.cycles.map(c => c.id), ['B'], 'the newest load wins');
  h.close();
});
