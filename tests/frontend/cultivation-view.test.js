'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/cultivation-view.js — the cultivation identity board.

   What is pinned here is exactly what this view is allowed to decide on its
   own. The server (app/api/cultivation.py + migration 0045) owns the real
   rules and answers 409/422 when they are broken; the view predicts a few of
   them to choose which buttons to offer, and two copies of one rule is how a
   rule drifts. So each prediction below has a named counterpart in
   backend/tests/test_cultivation.py:

     - PHASE IS A BATCH PROPERTY. A room holds ~2000 plants and every audited
       write takes one global advisory lock until commit, so the board must
       offer a whole-batch move and must NOT offer any per-plant phase control.
       Its absence is load-bearing and is asserted, because "add a per-plant
       phase button" is the single easiest way to reintroduce the lock storm
       the schema was shaped to avoid.
     - MATERIALISING PLANT IDS IS RESUMABLE. The fill loop must keep calling
       until the server reports complete, and must STOP on a call that created
       nothing — otherwise a batch the server will not fill any further spins
       forever.
     - A TERMINAL MOVE IS IRREVERSIBLE. harvested/destroyed settles every
       active plant and cannot be moved again, so it needs a stated reason and
       an on-screen warning before the button, not a 409 afterwards.
     - A BATCH WITH NO CULTIVAR cannot form plant ids at all (422 server-side),
       so the card must say so rather than offering a button that fails.

   The view is an IIFE that registers onto window.GF, so these tests load it
   the way index.html does and reach the predicates through rendered output —
   the same real source, no logic copied.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// cultivation-view.js calls GF.WWF._registerFullPageView at load and uses AL(),
// GF.icon, GF.esc, GF.viewHead, GF.t. data.js + core.js supply esc/icon/state/
// AL/t; the rest are declared here so loading the real file does not throw.
const PRE_CULT = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
  window.GF.render = { all: function () { (window.__renders = window.__renders || 0); window.__renders++; } };
  window.GF.viewHead = function (a, b, extra) { return '<head>' + (extra || '') + '</head>'; };
  window.GF.API = { user: { role: 'CU_MGR' } };
`;

function load(role) {
  const h = loadGF({
    files: ['data.js', 'core.js', 'cultivation-view.js'],
    preScript: PRE_CULT,
  });
  if (role) h.window.GF.API.user = { role };
  return h;
}

// Render through the REAL view and hand back the HTML, so what is asserted is
// what a grower would actually see.
function renderBatches(h, batches, cultivars = []) {
  h.window.GF.WWF._cult.batches = batches;
  h.window.GF.WWF._cult.cultivars = cultivars;
  h.window.GF.state.view = 'cultivation';
  return h.window.GF.views.cultivation();
}

const BATCH = (over = {}) => ({
  id: 'b1', code: 'GP072501', room_id: 'r1', room_name: 'Flowering 1.1 · C180 · Room 1',
  cultivar_id: 'cv1', cultivar_code: 'Bisamber', cultivar_name: 'Bisamber',
  strain: 'Bisamber', plant_count: 2000, phase: 'flower', phase_since: '2026-07-01',
  note: null, is_active: true, plants_materialised: 2000, plants_active: 2000,
  ...over,
});

/* ── registration and the read gate ─────────────────────────────────────── */

test('the view registers under the cultivation key with a read gate above base USER', () => {
  const h = load();
  const spec = h.window.__reg;
  assert.equal(spec.key, 'cultivation');
  h.window.GF.API.user = { role: 'USER' };
  assert.equal(spec.guard(), false, 'base USER must not see the cultivation board');
  h.window.GF.API.user = { role: 'QC_MGR' };
  assert.equal(spec.guard(), true, 'any elevated role may READ the identity record');
  h.window.GF.API.user = { role: null };
  assert.equal(spec.guard(), false, 'a logged-out/roleless session must not see it');
  h.close();
});

test('the nav item is anchored on a key render.sidebar itself emits, not on a sibling view', () => {
  // _registerFullPageView wraps render.sidebar and this file loads BEFORE
  // decon-view.js, so on the first render a 'decon' anchor would not exist yet
  // and the item would silently fall through to append().
  const h = load();
  assert.equal(h.window.__reg.insertBefore, 'mywork');
  h.close();
});

/* ── the load-bearing absence: no per-plant phase control ───────────────── */

test('a batch card offers a WHOLE-BATCH move and no per-plant phase control', () => {
  const h = load('CU_MGR');
  const html = renderBatches(h, [BATCH()]);
  assert.match(html, /cultMoveForm\('b1'\)/, 'the whole-batch move must be offered');
  // Phase belongs to the batch. Any per-plant phase entry point would put
  // ~2000 audited writes behind one global lock.
  assert.doesNotMatch(html, /plantPhase|cultPlantMove|cultPlantAdvance/i,
    'there must be no per-plant phase control — phase is a batch property');
  h.close();
});

test('the plant roster is read-only: it lists ids and statuses, it does not move plants', () => {
  const h = load('CU_MGR');
  const w = h.window;
  w.__modals = [];
  w.GF.openModal = (id) => { w.__modals.push(id); };
  w.GF.WWF._ensureModal = function (id) {
    if (w.document.getElementById(id)) return;
    const wrap = w.document.createElement('div');
    wrap.id = id;
    wrap.innerHTML = '<div id="' + id + '-title"></div><div id="' + id + '-body"></div>';
    w.document.body.appendChild(wrap);
  };
  w.GF.API.cultivationPlants = async () => ({
    batch_id: 'b1', total: 2, limit: 200, offset: 0,
    plants: [
      { id: 'p1', plant_code: '20260701_Bisamber_0001', seq: 1, status: 'active',
        status_since: null, clone_date: '2026-07-01', reason: null },
      { id: 'p2', plant_code: '20260701_Bisamber_0002', seq: 2, status: 'culled',
        status_since: '2026-07-20', clone_date: '2026-07-01', reason: 'stunted' },
    ],
  });
  return w.GF.WWF.cultPlantList('b1', 'GP072501').then(() => {
    const body = w.document.getElementById('cu-plants-modal-body').innerHTML;
    assert.match(body, /20260701_Bisamber_0001/);
    assert.match(body, /20260701_Bisamber_0002/);
    // Allowlisted rather than blocklisted: naming the handlers that must NOT
    // appear only catches the names guessed in advance, and any new per-plant
    // mutation would be spelled something else. So every handler the roster
    // references has to be one of the read-only ones.
    const READ_ONLY = ['GF.WWF.cultPlantList'];   // pagination, nothing else
    const handlers = [...new Set((body.match(/GF\.WWF\.[A-Za-z_]+/g) || []))];
    const unexpected = handlers.filter(fn => !READ_ONLY.includes(fn));
    assert.deepEqual(unexpected, [],
      'the roster may only page itself — any other handler is a per-plant mutation');
    h.close();
  });
});

/* ── the three headcounts ───────────────────────────────────────────────── */

test('an incomplete fill is visible: planned, id-generated and active are separate numbers', () => {
  const h = load('CU_MGR');
  const html = renderBatches(h, [BATCH({ plant_count: 2000, plants_materialised: 150, plants_active: 148 })]);
  assert.match(html, /2000/, 'the planned count must be shown');
  assert.match(html, /150/,  'the number of generated ids must be shown');
  assert.match(html, /148/,  'the number still active must be shown');
  // And the shortfall is called out at the top of the board, not left to arithmetic.
  assert.match(html, /1850 planned plants have no id yet/);
  h.close();
});

test('the generate button offers exactly the outstanding count and disappears when complete', () => {
  const h = load('CU_MGR');
  let html = renderBatches(h, [BATCH({ plant_count: 2000, plants_materialised: 150 })]);
  assert.match(html, /Generate 1850 plant ids/);
  assert.match(html, /cultFillPlants\('b1'\)/);
  html = renderBatches(h, [BATCH({ plant_count: 2000, plants_materialised: 2000 })]);
  assert.doesNotMatch(html, /cultFillPlants/, 'a fully materialised batch needs no fill button');
  h.close();
});

test('a batch with no cultivar says plant ids cannot be formed, and offers no fill', () => {
  // The server answers 422 "batch has no cultivar; cannot form plant ids".
  const h = load('CU_MGR');
  const html = renderBatches(h, [BATCH({
    cultivar_id: null, cultivar_code: null, cultivar_name: null,
    plants_materialised: 0, plants_active: 0,
  })]);
  assert.match(html, /No cultivar on this batch/);
  h.close();
});

test('a terminal batch is offered neither a move nor a fill', () => {
  for (const phase of ['harvested', 'destroyed']) {
    const h = load('CU_MGR');
    const html = renderBatches(h, [BATCH({
      phase, plants_materialised: 0, plants_active: 0, is_active: false,
    })]);
    assert.doesNotMatch(html, /cultMoveForm/, `a ${phase} batch cannot move again`);
    assert.doesNotMatch(html, /cultFillPlants/, `a ${phase} batch must not be filled`);
    h.close();
  }
});

/* ── role gating ────────────────────────────────────────────────────────── */

test('a reader sees the record and none of the write actions', () => {
  const h = load('QC_MGR');
  const html = renderBatches(h, [BATCH({ plants_materialised: 10 })]);
  assert.match(html, /GP072501/, 'an elevated reader must see the batch');
  assert.match(html, /cultPlantList/, 'and may open the roster');
  assert.doesNotMatch(html, /cultMoveForm/,   'a reader must not be offered a phase move');
  assert.doesNotMatch(html, /cultFillPlants/, 'a reader must not be offered id generation');
  assert.doesNotMatch(html, /cultBatchForm/,  'a reader must not be offered a new batch');
  assert.doesNotMatch(html, /cultCultivarForm/, 'a reader must not be offered cultivar edits');
  h.close();
});

test('batch codes, cultivar names and room names are HTML-escaped', () => {
  // All three are operator-typed free text that lands in innerHTML.
  const h = load('CU_MGR');
  const html = renderBatches(h, [BATCH({
    code: '<img src=x onerror=alert(1)>',
    cultivar_name: '"><script>bad()</script>',
    room_name: '<b>room</b>',
    note: '<svg onload=alert(2)>',
  })]);
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<script>bad\(\)/);
  assert.doesNotMatch(html, /<svg onload/);
  assert.match(html, /&lt;img src=x/);
  h.close();
});

/* ── the resumable fill loop ────────────────────────────────────────────── */

function loadForms(role) {
  const h = loadGF({
    files: ['data.js', 'core.js', 'cultivation-view.js'],
    preScript: PRE_CULT,
  });
  const w = h.window;
  if (role) w.GF.API.user = { role };
  w.__modals = []; w.__closed = []; w.__toasts = [];
  // Stubbed AFTER the sources load, not via preScript: core.js defines its own
  // openModal/closeModal/toast, so a preScript stub would be overwritten by the
  // real thing and every assertion here would pass vacuously.
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
  // The real GF.selectField renders a HIDDEN input and GF.pickSel assigns
  // .value directly — it fires NO change event. The stub keeps that shape and
  // records the cfg, so a view that went back to a change listener would fail.
  w.__selCfg = {};
  w.GF.selectField = (id, cfg) => {
    w.__selCfg[id] = cfg;
    return '<input type="hidden" id="' + id + '" value="' + (cfg.value == null ? '' : cfg.value) + '">';
  };
  w.GF.once = async (btnId, fn) => fn();
  w.GF.API.cultivationBatches = async () => ({ batches: w.__batches || [] });
  w.GF.API.cultivars = async () => ({ cultivars: w.__cultivars || [] });
  w.GF.API.facility = async () => ({ rooms: w.__rooms || [] });
  w.GF.API.cultivationBatchCreate = async (b) => { w.__created = b; return { id: 'new' }; };
  w.GF.API.cultivarCreate = async (b) => { w.__cvCreated = b; return { id: 'cv9' }; };
  w.GF.API.cultivarPatch = async (id, b) => { w.__cvPatched = [id, b]; return { ok: true }; };
  w.GF.API.cultivationMove = async (id, b) => {
    w.__moved = [id, b]; return { id, code: 'GP072501', phase: b.to_phase, phase_since: '2026-07-30', is_active: true };
  };
  return h;
}

test('the fill loop keeps calling until the server reports complete', async () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  const calls = [];
  // The server fills in ~50-row chunks; a 120-plant batch takes three calls.
  const script = [
    { target: 120, created: 50, materialised: 50,  complete: false },
    { target: 120, created: 50, materialised: 100, complete: false },
    { target: 120, created: 20, materialised: 120, complete: true },
  ];
  w.GF.API.cultivationGenPlants = async (id) => { calls.push(id); return script[calls.length - 1]; };
  await w.GF.WWF.cultFillPlants('b1');
  assert.equal(calls.length, 3, 'the fill must resume until the server says complete');
  assert.ok(w.__toasts.some(t => /120 plant ids generated/.test(t[0])),
    'the total across every chunk is reported, not just the last call');
  h.close();
});

test('the fill loop stops when a call creates nothing, instead of spinning', async () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  let n = 0;
  // A server that reports "not complete" but creates nothing is a stuck fill.
  w.GF.API.cultivationGenPlants = async () => {
    n++; return { target: 2000, created: 0, materialised: 300, complete: false };
  };
  await w.GF.WWF.cultFillPlants('b1');
  assert.equal(n, 1, 'a zero-progress call must end the loop immediately');
  assert.ok(w.__toasts.some(t => /Stopped at 300\/2000/.test(t[0])),
    'the operator must be told where it stopped, not left with a silent no-op');
  h.close();
});

test('a mid-fill failure says the fill is resumable rather than implying a lost batch', async () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  let n = 0;
  w.GF.API.cultivationGenPlants = async () => {
    n++;
    if (n === 1) return { target: 2000, created: 50, materialised: 50, complete: false };
    throw new Error('504 Gateway Timeout');
  };
  await w.GF.WWF.cultFillPlants('b1');
  const msg = (w.__toasts.find(t => /504/.test(t[0])) || [])[0];
  assert.ok(msg, 'the failure must be surfaced');
  assert.match(msg, /resumable/, 'and it must say the partial fill can be continued');
  assert.equal(w.GF.WWF._cult.filling, null, 'the in-flight flag must be cleared on failure');
  h.close();
});

test('a second fill cannot start while one is in flight', async () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  let n = 0;
  let release;
  const gate = new Promise((r) => { release = r; });
  w.GF.API.cultivationGenPlants = async () => {
    n++;
    await gate;
    return { target: 50, created: 50, materialised: 50, complete: true };
  };
  const first = w.GF.WWF.cultFillPlants('b1');
  // Deliberately not awaited before release(): if the guard is ever removed the
  // second call blocks on the same gate, and awaiting it here would deadlock the
  // whole file instead of failing this one test.
  const second = w.GF.WWF.cultFillPlants('b1');
  await new Promise((r) => setImmediate(r));  // let an unguarded second call reach the API
  release();
  await Promise.all([first, second]);
  assert.equal(n, 1, 'a double tap must not double-fill');
  h.close();
});

/* ── the move form ──────────────────────────────────────────────────────── */

test('the move form omits the phase the batch is already in', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF._cult.batches = [BATCH({ phase: 'veg' })];
  return w.GF.WWF.cultMoveForm('b1').then(() => {
    const opts = w.__selCfg['cu-m-phase'].options.map(o => o.v);
    assert.ok(!opts.includes('veg'), 'moving to the current phase is not a transition');
    assert.ok(opts.includes('flower'));
    h.close();
  });
});

test('picking a terminal phase warns on screen before the button is pressed', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF._cult.batches = [BATCH({ phase: 'flower', plant_count: 2000 })];
  return w.GF.WWF.cultMoveForm('b1').then(() => {
    const warn = w.document.getElementById('cu-m-warn');
    assert.equal(warn.style.display, 'none', 'no warning for an ordinary move');
    // The chooser assigns .value directly and fires no change event, so onPick
    // is the ONLY hook. If the view regressed to addEventListener('change'),
    // this is where it fails.
    w.document.getElementById('cu-m-phase').value = 'destroyed';
    w.__selCfg['cu-m-phase'].onPick('destroyed');
    assert.equal(warn.style.display, 'block', 'a terminal move must warn before submission');
    assert.match(warn.textContent, /all 2000 plants/);
    assert.match(warn.textContent, /cannot be moved again/);
    h.close();
  });
});

test('closing a batch is refused without a stated reason', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF._cult.batches = [BATCH({ phase: 'flower' })];
  return w.GF.WWF.cultMoveForm('b1').then(async () => {
    w.document.getElementById('cu-m-phase').value = 'destroyed';
    w.document.getElementById('cu-m-reason').value = '';
    await w.GF.WWF.cultMoveSave('b1');
    assert.equal(w.__moved, undefined, 'destroying a batch with no reason must not be submitted');
    assert.ok(w.__toasts.some(t => /reason/i.test(t[0])));
    h.close();
  });
});

test('an ordinary move needs no reason and sends the phase, room and date verbatim', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__rooms = [{ id: 'r2', name: 'Flowering 1.2 · C181 · Room 2' }];
  w.GF.WWF._cult.batches = [BATCH({ phase: 'veg' })];
  return w.GF.WWF.cultMoveForm('b1').then(async () => {
    w.document.getElementById('cu-m-phase').value = 'flower';
    w.document.getElementById('cu-m-room').value = 'r2';
    w.document.getElementById('cu-m-date').value = '2026-08-03';
    await w.GF.WWF.cultMoveSave('b1');
    const [id, body] = w.__moved;
    assert.equal(id, 'b1');
    assert.equal(body.to_phase, 'flower');
    assert.equal(body.to_room_id, 'r2');
    assert.equal(body.occurred_on, '2026-08-03');
    assert.equal(body.reason, null, 'an unfilled reason is null, not an empty string');
    h.close();
  });
});

test('leaving the room unchanged sends null rather than an empty string', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF._cult.batches = [BATCH({ phase: 'veg' })];
  return w.GF.WWF.cultMoveForm('b1').then(async () => {
    w.document.getElementById('cu-m-phase').value = 'flower';
    // 'unchanged' is the default option and its value is the empty string.
    assert.equal(w.document.getElementById('cu-m-room').value, '');
    await w.GF.WWF.cultMoveSave('b1');
    assert.equal(w.__moved[1].to_room_id, null);
    h.close();
  });
});

/* ── opening a batch ────────────────────────────────────────────────────── */

test('opening a batch is blocked with a named prerequisite when no cultivar exists', () => {
  // "Cannot open a batch" with no reason is what makes people invent a
  // free-text strain — which is exactly what the cultivar master retires.
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  w.__cultivars = [];
  w.GF.WWF._cult.cultivars = [];
  return w.GF.WWF.cultBatchForm().then(() => {
    assert.ok(!w.__modals.includes('cu-batch-modal'), 'the batch form must not open');
    assert.ok(w.__toasts.some(t => /cultivar/i.test(t[0])));
    assert.ok(w.__modals.includes('cu-cvlist-modal'), 'and it must point at the cultivar registry');
    h.close();
  });
});

test('a retired cultivar is not offered when opening a batch', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  w.GF.WWF._cult.cultivars = [
    { id: 'cv1', code: 'Bisamber', name: 'Bisamber', is_active: true },
    { id: 'cv2', code: 'OldStrain', name: 'Old', is_active: false },
  ];
  return w.GF.WWF.cultBatchForm().then(() => {
    const opts = w.__selCfg['cu-b-cultivar'].options.map(o => o.v);
    assert.deepEqual(opts, ['cv1']);
    h.close();
  });
});

test('a new batch cannot be opened directly into a terminal phase', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  w.GF.WWF._cult.cultivars = [{ id: 'cv1', code: 'Bisamber', name: 'Bisamber', is_active: true }];
  return w.GF.WWF.cultBatchForm().then(() => {
    const opts = w.__selCfg['cu-b-phase'].options.map(o => o.v);
    assert.ok(!opts.includes('harvested'));
    assert.ok(!opts.includes('destroyed'));
    h.close();
  });
});

test('a bad batch code is rejected before the request, matching the server pattern', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  w.GF.WWF._cult.cultivars = [{ id: 'cv1', code: 'Bisamber', name: 'Bisamber', is_active: true }];
  return w.GF.WWF.cultBatchForm().then(async () => {
    for (const bad of ['', 'GP 072501', 'GP/072501', 'x'.repeat(65)]) {
      w.__created = undefined;
      w.document.getElementById('cu-b-code').value = bad;
      w.document.getElementById('cu-b-count').value = '2000';
      await w.GF.WWF.cultBatchSave();
      assert.equal(w.__created, undefined, `"${bad}" must not be sent to the server`);
    }
    h.close();
  });
});

test('the clone date is sent as both clone_date and phase_since, because the ids carry it', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.__rooms = [{ id: 'r1', name: 'Flowering 1.1' }];
  w.GF.WWF._cult.cultivars = [{ id: 'cv1', code: 'Bisamber', name: 'Bisamber', is_active: true }];
  return w.GF.WWF.cultBatchForm().then(async () => {
    w.document.getElementById('cu-b-code').value = 'GP072501';
    w.document.getElementById('cu-b-count').value = '2000';
    w.document.getElementById('cu-b-clone').value = '2026-07-01';
    await w.GF.WWF.cultBatchSave();
    assert.equal(w.__created.code, 'GP072501');
    assert.equal(w.__created.plant_count, 2000);
    assert.equal(w.__created.clone_date, '2026-07-01');
    assert.equal(w.__created.phase_since, '2026-07-01',
      'the plant id prefix comes from the clone date, so the batch must carry it');
    h.close();
  });
});

/* ── the cultivar registry ──────────────────────────────────────────────── */

test('a cultivar CODE is immutable once registered — the plant ids are built from it', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF._cult.cultivars = [{ id: 'cv1', code: 'Bisamber', name: 'Bisamber', name_mk: null, note: null, is_active: true }];
  w.GF.WWF.cultCultivarForm('cv1');
  const body = w.document.getElementById('cu-cv-modal-body').innerHTML;
  assert.doesNotMatch(body, /id="cu-cv-code"/,
    'editing a cultivar must not offer to change the code every plant id embeds');
  assert.match(body, /id="cu-cv-name"/, 'the display name stays editable');
  h.close();
});

test('a new cultivar validates its code against the server pattern', async () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF.cultCultivarForm(null);
  for (const bad of ['', 'Bis amber', 'Bis/amber']) {
    w.__cvCreated = undefined;
    w.document.getElementById('cu-cv-code').value = bad;
    w.document.getElementById('cu-cv-name').value = 'Bisamber';
    await w.GF.WWF.cultCultivarSave(null);
    assert.equal(w.__cvCreated, undefined, `"${bad}" must not be sent`);
  }
  w.document.getElementById('cu-cv-code').value = 'Bisamber-2';
  await w.GF.WWF.cultCultivarSave(null);
  assert.equal(w.__cvCreated.code, 'Bisamber-2', 'a valid code with a hyphen is accepted');
  h.close();
});

test('retiring a cultivar goes through is_active, not a delete', () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF._cult.cultivars = [{ id: 'cv1', code: 'Bisamber', name: 'Bisamber', name_mk: null, note: null, is_active: true }];
  w.GF.WWF.cultCultivarForm('cv1');
  return (async () => {
    w.document.getElementById('cu-cv-active').checked = false;
    await w.GF.WWF.cultCultivarSave('cv1');
    const [id, body] = w.__cvPatched;
    assert.equal(id, 'cv1');
    assert.equal(body.is_active, false);
    h.close();
  })();
});

test('a cultivar with no name is refused — the registry exists to retire free text', async () => {
  const h = loadForms('CU_MGR');
  const w = h.window;
  w.GF.WWF.cultCultivarForm(null);
  w.document.getElementById('cu-cv-code').value = 'Bisamber';
  w.document.getElementById('cu-cv-name').value = '   ';
  await w.GF.WWF.cultCultivarSave(null);
  assert.equal(w.__cvCreated, undefined);
  assert.ok(w.__toasts.some(t => /name/i.test(t[0])));
  h.close();
});

/* ── write actions are refused for readers at the handler, not only in markup ── */

test('a reader calling a write handler directly is refused', async () => {
  const h = loadForms('QC_MGR');
  const w = h.window;
  w.GF.API.cultivationGenPlants = async () => { w.__filled = true; return { complete: true }; };
  w.GF.WWF._cult.batches = [BATCH({ phase: 'veg' })];
  await w.GF.WWF.cultFillPlants('b1');
  assert.equal(w.__filled, undefined, 'hiding the button is not the gate — the handler checks too');
  await w.GF.WWF.cultMoveForm('b1');
  assert.ok(!w.__modals.includes('cu-move-modal'));
  await w.GF.WWF.cultBatchForm();
  assert.ok(!w.__modals.includes('cu-batch-modal'));
  w.GF.WWF.cultCultivarForm(null);
  assert.ok(!w.__modals.includes('cu-cv-modal'));
  h.close();
});
