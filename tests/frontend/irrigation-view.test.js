'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/irrigation-view.js — the irrigation & feeding record's own view.

   Until 2026-09-05 this was a "Feeding" tab inside the harvest view, written
   by the cultivation manager because there was no irrigation role to own it.
   Irrigation is a department of its own at the facility, so the record has
   its own view and its own recorder. The server (app/api/irrigation.py) owns
   the gate — writers are ADMIN / executives / IR_MGR — and this view only
   mirrors it: the Log feed affordance appears for a recorder and for nobody
   else, and a reading that was not taken renders as nothing, never as 0.

   The first two tests were carried over from harvest-view.test.js when the
   tab moved; the gate tests are new, because the gate is.
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
  window.GF.viewHead = function (a, b, extra) { return '<head>' + (extra || '') + '</head>'; };
  window.GF.API = { user: { role: 'IR_MGR' } };
`;

function load(role) {
  const h = loadGF({ files: ['data.js', 'core.js', 'irrigation-view.js'], preScript: PRE });
  if (role) h.window.GF.API.user = { role };
  return h;
}

function render(h, feeds) {
  h.window.GF.WWF._irr.feeds = feeds;
  h.window.GF.state.view = 'irrigation';
  return h.window.GF.views.irrigation();
}

test('lists a feed and shows a missing reading as nothing, not zero', () => {
  const h = load('IR_MGR');
  const body = render(h, [
    { id: 'f1', room_name: 'Flowering 1.1', batch_code: null, applied_on: '2026-08-05',
      method: 'drip', water_volume_l: 40, feed_ec: 1.8, feed_ph: 6.1,
      runoff_ec: null, runoff_ph: null, nutrients: 'Base A+B' },
  ]);
  assert.match(body, /Flowering 1\.1/);
  assert.match(body, /EC <b>1\.8/, 'a measured feed EC is shown');
  // A NULL runoff reading must not render a "runoff EC" chip at all — absent is
  // "not measured", never 0.
  assert.doesNotMatch(body, /runoff EC/, 'an unmeasured runoff reading shows no chip');
  assert.match(body, /Base A\+B/);
  h.close();
});

test('the irrigation manager is offered Log feed, and an empty list says so', () => {
  const h = load('IR_MGR');
  const body = render(h, []);
  assert.match(body, /No feeds logged/);
  assert.match(body, /GF\.WWF\.feedForm\(\)/, 'the recorder is offered the Log feed action');
  h.close();
});

test('the cultivation manager reads the record but is not offered Log feed', () => {
  // The gate that moved: irrigation runs the fertigation plant and its
  // distribution to every room as a department of its own, and cultivation
  // — who used to hold the pen — now reads. Mirrors _RECORDERS in
  // app/api/irrigation.py, where the same request is a 403.
  const h = load('CU_MGR');
  const body = render(h, [
    { id: 'f1', room_name: 'Flowering 1.1', applied_on: '2026-08-05', water_volume_l: 40 },
  ]);
  assert.match(body, /Flowering 1\.1/, 'cultivation still sees the record');
  assert.doesNotMatch(body, /GF\.WWF\.feedForm\(\)/, 'but is not offered the write');
  h.close();
});

test('executives and ADMIN are offered Log feed; QC and base staff are not', () => {
  for (const role of ['ADMIN', 'OWNER', 'CEO', 'COO']) {
    const h = load(role);
    assert.match(render(h, []), /GF\.WWF\.feedForm\(\)/, `${role} may record`);
    h.close();
  }
  for (const role of ['QC_MGR', 'QA_MGR', 'PR_MGR', 'USER']) {
    const h = load(role);
    assert.doesNotMatch(render(h, []), /GF\.WWF\.feedForm\(\)/, `${role} may not`);
    h.close();
  }
});

test('feedForm() is a no-op for a role that may not record', () => {
  // The button is hidden, but the handler is a global — a stale click or a
  // typed call must not open a form the server would refuse to save.
  const h = load('CU_MGR');
  const w = h.window;
  let fetched = false;
  w.GF.API.facility = async () => { fetched = true; return { rooms: [] }; };
  return w.GF.WWF.feedForm().then(() => {
    assert.equal(fetched, false, 'no data is even fetched for a non-recorder');
    h.close();
  });
});

test('registers as a full-page view in the operations rail, readable by every role above USER', () => {
  const h = load('IR_MGR');
  const reg = h.window.__reg;
  assert.equal(reg.key, 'irrigation');
  assert.equal(reg.insertBefore, 'mywork');
  h.window.GF.API.user = { role: 'USER' };
  assert.equal(reg.guard(), false, 'base staff do not see the view');
  h.window.GF.API.user = { role: 'WH_MGR' };
  assert.equal(reg.guard(), true, 'any elevated role reads it');
  h.close();
});

// ── the feed form ─────────────────────────────────────────────────────────────
// Carried over from harvest-view.test.js with the tab; the ids moved from hv-f-*
// to ir-f-* with the view. Stubs are installed AFTER the sources load — core.js
// defines its own openModal/closeModal/toast, so a preScript stub would be
// overwritten and every assertion here would pass vacuously.

function loadForms(role) {
  const h = loadGF({ files: ['data.js', 'core.js', 'irrigation-view.js'], preScript: PRE });
  const w = h.window;
  if (role) w.GF.API.user = { role };
  w.__modals = []; w.__closed = []; w.__toasts = [];
  w.GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  w.GF.WWF._ensureModal = function (id) {
    if (w.document.getElementById(id)) return;
    const wrap = w.document.createElement('div');
    wrap.id = id;
    wrap.innerHTML = '<div id="' + id + '-title"></div><div id="' + id + '-body"></div>';
    w.document.body.appendChild(wrap);
  };
  w.GF.openModal = (id) => { w.__modals.push(id); };
  w.GF.closeModal = (id) => { w.__closed.push(id); };
  // The real GF.selectField renders a HIDDEN input whose .value is assigned
  // directly; the stub keeps that shape.
  w.GF.selectField = (id, cfg) =>
    '<input type="hidden" id="' + id + '" value="' + (cfg.value == null ? '' : cfg.value) + '">';
  w.GF.once = async (btnId, fn) => fn();
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  w.GF.API.facility = async () => ({ rooms: w.__rooms });
  w.GF.API.cultivationBatches = async () => ({ batches: [] });
  w.GF.API.irrigation = async () => ({ feeds: w.__feeds || [] });
  w.GF.API.irrigationLog = async (b) => { w.__feed = b; return { id: 'f9' }; };
  return h;
}

test('a blank feed reading is sent as null, a room is required, and a value round-trips', () => {
  const h = loadForms('IR_MGR');
  const w = h.window;
  return w.GF.WWF.feedForm().then(async () => {
    assert.deepEqual(w.__modals, ['ir-feed-modal'], 'the form opens in its own modal');
    // no room picked yet → refused before any request
    w.document.getElementById('ir-f-room').value = '';
    await w.GF.WWF.feedSave();
    assert.equal(w.__feed, undefined, 'a feed with no room must not be sent');
    assert.match(w.__toasts.at(-1)[0], /room/i);

    // now a real room + a volume, EC left blank
    w.document.getElementById('ir-f-room').value = 'r1';
    w.document.getElementById('ir-f-vol').value = '40';
    w.document.getElementById('ir-f-fph').value = '6.1';
    await w.GF.WWF.feedSave();
    assert.equal(w.__feed.room_id, 'r1');
    assert.equal(w.__feed.water_volume_l, 40);
    assert.equal(w.__feed.feed_ph, 6.1, 'a decimal pH round-trips, not rounded to int');
    assert.equal(w.__feed.feed_ec, null,
      'a reading left blank is "not measured" (null), never coerced to 0');
    assert.deepEqual(w.__closed, ['ir-feed-modal'], 'a saved feed closes the form');
    h.close();
  });
});
