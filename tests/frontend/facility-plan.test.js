'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/facility-view.js — the as-built floor plan board.

   The owner asked for a visual reference for every room against the real
   layout. The register (backend/app/data/facility_layout.json, migration
   0068) gives each room a normalised anchor on the ground-floor sheet, and
   this board places one pin per room over an image of that same sheet.

   What is pinned here is what makes the picture trustworthy:

     - THE PIN IS THE ANCHOR. A pin's left/top are the register's plan_x /
       plan_y in percent, unscaled and unrounded beyond three decimals. The
       image was cropped to exactly the bounds those anchors were normalised
       against, so any arithmetic in the view would be the thing that breaks
       the alignment.
     - ZOOM SCALES THE STAGE, NOT THE PINS. Percent positioning means the
       pins follow the image at every zoom for free; a zoom that touched the
       pin coordinates would drift them.
     - THE DRAWING IS NOT EDITABLE. The classify form offers the regime, the
       grade, the department and the operational-room link — and never the
       code, name, area, perimeter or anchor, which are what the sheet says.
     - THE GRADE IS NOT INVENTED. A room with no grade says so rather than
       showing a guess: no cleanliness grade appears anywhere on the drawing.
     - CLASSIFYING IS GATED to the roles the server accepts in
       facility_layout.py's _CLASSIFIERS.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
  window.GF.WWF._ensureModal = function () {};
  window.GF.render = { all: function () {} };
  window.GF.viewHead = function (a, b, extra) { return '<head>' + (extra || '') + '</head>'; };
  window.GF.openModal = function () {};
  window.GF.closeModal = function () {};
  window.GF.API = { user: { role: 'QA_MGR' }, facility: function () { return Promise.resolve(null); } };
`;

function load(role) {
  const h = loadGF({
    files: ['data.js', 'core.js', 'chooser.js', 'datepicker.js', 'codefield.js', 'facility-view.js'],
    preScript: PRE,
  });
  if (role) h.window.GF.API.user = { role };
  return h;
}

const ROOM = (over = {}) => ({
  id: 'l1', code: 'C180', name_en: 'FLOWERING PREMISE 1.1',
  name_mk: 'ПРОСТОРИЈА ЗА ЦВЕТАЊЕ 1.1', wing: 'cultivation', zone: 'cultivation',
  regime: 'GACP', grade: null, area_m2: 501.38, net_area_m2: 416.0, perimeter_m: 111.35,
  plan_x: 0.30125, plan_y: 0.41875,
  box_x: 0.28, box_y: 0.1, box_w: 0.06, box_h: 0.55, box_conf: 0.4,
  department_id: null, department_name: null,
  room_id: null, room_code: null, room_name: null, notes: null, ...over,
});

function renderPlan(h, rooms, totals, mode) {
  h.window.GF.WWF._fac.tab = 'plan';
  h.window.GF.WWF._fac.data = { rooms: [], totals: {} };
  h.window.GF.WWF._plan.data = {
    rooms, totals: totals || { cultivation: { rooms: rooms.length, area_m2: 501.38 } },
    vocab: {},
  };
  if (mode) h.window.GF.WWF._plan.mode = mode;
  h.window.GF.state.view = 'facility';
  return h.window.GF.views.facility();
}

/* ── the picture ────────────────────────────────────────────────────────── */

test('drawing mode: a pin sits at the register anchor, in percent, over the ground-floor sheet', () => {
  const h = load();
  const html = renderPlan(h, [ROOM()], null, 'drawing');
  assert.match(html, /src="assets\/facility-ground-floor\.png"/);
  assert.match(html, /left:30\.125%/);
  assert.match(html, /top:41\.875%/);
  assert.match(html, /class="fp-pin"/);
  h.close();
});

test('drawing mode: zoom scales the stage and leaves every pin coordinate alone', () => {
  const h = load();
  const before = renderPlan(h, [ROOM()], null, 'drawing');
  assert.match(before, /class="fp-stage-outer" style="width:100%"/);
  h.window.GF.WWF.planZoom(1);
  const after = renderPlan(h, [ROOM()], null, 'drawing');
  assert.match(after, /class="fp-stage-outer" style="width:200%"/);
  assert.match(after, /left:30\.125%/);
  assert.match(after, /top:41\.875%/);
  h.close();
});

/* ── plan mode: the SVG the app draws itself ─────────────────────────────── */

test('plan mode is the default, and draws an SVG rectangle sized from the room box', () => {
  const h = load();
  const html = renderPlan(h, [ROOM()]);
  assert.equal(h.window.GF.WWF._plan.mode, 'plan');
  assert.match(html, /<svg class="fp-svg"/);
  assert.match(html, /class="fp-r[^"]*"[^>]*style="--pin:/);
  // 1000 x 443 is the frame the register's box_* columns normalise to.
  assert.match(html, /x="280\.00" y="44\.30" width="60\.00" height="243\.65"/);
  h.close();
});

test('a room the register cannot size (no box) is skipped by the plan but stays in the roster', () => {
  const h = load();
  const html = renderPlan(h, [ROOM({ id: 'l2', code: 'C88', box_x: null, box_y: null, box_w: null, box_h: null, box_conf: null })]);
  assert.equal((html.match(/class="fp-r[" ]/g) || []).length, 0);
  assert.match(html, /fp-row-code">C88/);
  h.close();
});

test('a loose fit (low box_conf) is drawn dashed, a confident one is not', () => {
  const h = load();
  const loose = renderPlan(h, [ROOM({ box_conf: 0.05 })]);
  assert.match(loose, /class="fp-r loose"/);
  const solid = renderPlan(h, [ROOM({ box_conf: 0.4 })]);
  assert.doesNotMatch(solid, /class="fp-r[^"]*loose/);
  h.close();
});

test('the plan viewBox frames the building, not the whole sheet margin', () => {
  const h = load();
  // Two rooms nowhere near the sheet edges: the frame must hug them, not the
  // full 1000 x 443 register frame the boxes are normalised against.
  const html = renderPlan(h, [
    ROOM({ box_x: 0.30, box_y: 0.10, box_w: 0.06, box_h: 0.55 }),
    ROOM({ id: 'l2', code: 'F104', box_x: 0.83, box_y: 0.20, box_w: 0.06, box_h: 0.20, zone: 'post_harvest' }),
  ]);
  const m = html.match(/viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"/);
  assert.ok(m, 'expected a viewBox attribute');
  const [, vx, vy, vw, vh] = m.map(Number);
  assert.ok(vw < 900, `viewBox width ${vw} should be tighter than the full 1000-wide register frame`);
  assert.ok(vx > 0, 'the frame should not start at the sheet origin when rooms start well inside it');
});

test('filtering by zone dims the non-matching rooms instead of removing them', () => {
  const h = load();
  const html = renderPlan(h, [ROOM(), ROOM({ id: 'l2', code: 'F104', name_en: 'DRYING ROOM 1A',
    zone: 'post_harvest', box_x: 0.83, box_y: 0.2, box_w: 0.06, box_h: 0.2 })]);
  h.window.GF.WWF._plan.zone = 'post_harvest';
  const shapes = h.window.GF.WWF._planShapes();
  const groups = shapes.split('</g>').filter(g => g.includes('<g '));
  const c180 = groups.find(g => g.includes(">C180<"));
  const f104 = groups.find(g => g.includes(">F104<"));
  assert.match(c180, /class="fp-r off"/, 'the filtered-out room is dimmed');
  assert.doesNotMatch(f104, /off/, 'the matching room is not dimmed');
  h.close();
});

test('switching to drawing mode and back preserves the selected room', () => {
  const h = load();
  renderPlan(h, [ROOM()]);
  h.window.GF.WWF._plan.sel = 'l1';
  h.window.GF.WWF.planMode('drawing');
  assert.equal(h.window.GF.WWF._plan.mode, 'drawing');
  assert.equal(h.window.GF.WWF._plan.sel, 'l1');
  h.close();
});

test('a room with no anchor is listed but never pinned', () => {
  const h = load();
  const html = renderPlan(h, [ROOM({ id: 'l2', code: 'T49', plan_x: null, plan_y: null })]);
  assert.equal((html.match(/class="fp-pin/g) || []).length, 0);
  assert.match(html, /fp-row-code">T49/);
  h.close();
});

test('the search narrows both the pins and the roster', () => {
  const h = load();
  renderPlan(h, [ROOM(), ROOM({ id: 'l2', code: 'F104', name_en: 'DRYING ROOM 1A', zone: 'post_harvest' })]);
  h.window.GF.WWF._plan.q = 'dry';
  const markers = h.window.GF.WWF._planMarkers();
  const roster = h.window.GF.WWF._planRoster();
  assert.ok(!markers.includes('C180') && markers.includes('F104'));
  assert.ok(!roster.includes('C180') && roster.includes('F104'));
  h.close();
});

test('a zone chip filters to that zone and toggles back off', () => {
  const h = load();
  renderPlan(h, [ROOM(), ROOM({ id: 'l2', code: 'F104', zone: 'post_harvest' })],
             { cultivation: { rooms: 1, area_m2: 501.38 }, post_harvest: { rooms: 1, area_m2: 98.27 } });
  h.window.GF.WWF._plan.zone = 'post_harvest';
  assert.ok(!h.window.GF.WWF._planMarkers().includes('C180'));
  h.window.GF.WWF.planZone('post_harvest');
  assert.equal(h.window.GF.WWF._plan.zone, '');
  h.close();
});

/* ── what the card says ─────────────────────────────────────────────────── */

test('the room card prints the stamped area, the cultivation area and the perimeter', () => {
  const h = load();
  renderPlan(h, [ROOM()]);
  const card = h.window.GF.WWF._planCard(ROOM(), []);
  assert.match(card, /501\.38 m²/);
  assert.match(card, /416\.00 m²/);
  assert.match(card, /111\.35 m/);
  h.close();
});

test('a room with no cleanliness grade says so instead of showing one', () => {
  const h = load();
  renderPlan(h, [ROOM()]);
  const card = h.window.GF.WWF._planCard(ROOM(), []);
  assert.match(card, /not classified/);
  const graded = h.window.GF.WWF._planCard(ROOM({ grade: 'D' }), []);
  assert.ok(!/not classified/.test(graded) && /<b>D<\/b>/.test(graded));
  h.close();
});

test('an unlinked room says it is not one the app schedules', () => {
  const h = load();
  renderPlan(h, [ROOM()]);
  const card = h.window.GF.WWF._planCard(ROOM(), []);
  assert.match(card, /Not linked to a room the app schedules/);
  const linked = h.window.GF.WWF._planCard(ROOM({ room_id: 'r1', room_name: 'Flowering 1.1' }), []);
  assert.match(linked, /Nothing growing here right now/);
  h.close();
});

/* ── who may classify, and what may be classified ───────────────────────── */

test('QA is offered the classify button and an operator is not', () => {
  const qa = load('QA_MGR');
  renderPlan(qa, [ROOM()]);
  assert.match(qa.window.GF.WWF._planCard(ROOM(), []), /Classify this room/);
  qa.close();

  const cu = load('CU_MGR');
  renderPlan(cu, [ROOM()]);
  assert.ok(!/Classify this room/.test(cu.window.GF.WWF._planCard(ROOM(), [])));
  cu.close();
});

test('the classify form never offers the code, name, area, perimeter or anchor', () => {
  const h = load('QA_MGR');
  // core.js installs the real modal helpers over the stubs; the form itself is
  // what this test reads, not the open/close plumbing.
  h.window.GF.closeModal = () => {};
  h.window.GF.openModal = () => {};
  renderPlan(h, [ROOM()]);
  const body = h.window.document.createElement('div');
  body.id = 'fac-plancls-modal-body';
  const title = h.window.document.createElement('div');
  title.id = 'fac-plancls-modal-title';
  h.window.document.body.append(title, body);
  h.window.GF.WWF.openPlanClassify('l1');
  const html = body.innerHTML;
  assert.match(html, /pc-regime/);
  assert.match(html, /pc-grade/);
  assert.match(html, /pc-dept/);
  assert.match(html, /pc-room/);
  for (const forbidden of ['pc-code', 'pc-name', 'pc-area', 'pc-perimeter', 'pc-plan']) {
    assert.ok(!html.includes(forbidden), forbidden + ' must not be editable');
  }
  h.close();
});

/* ── the empty register ─────────────────────────────────────────────────── */

test('an empty register offers the load button to an executive only', () => {
  const exec = load('COO');
  const html = renderPlan(exec, [], {});
  assert.match(html, /Load the ground-floor plan/);
  exec.close();

  const qa = load('QA_MGR');
  const q = renderPlan(qa, [], {});
  assert.match(q, /has not been loaded into this organisation yet/);
  assert.ok(!/Load the ground-floor plan/.test(q));
  qa.close();
});

test('the board opens on the rooms tab and the plan is a second tab', () => {
  const h = load();
  h.window.GF.WWF._fac.data = { rooms: [], totals: {} };
  h.window.GF.state.view = 'facility';
  assert.equal(h.window.GF.WWF._fac.tab, 'rooms');
  const html = h.window.GF.views.facility();
  assert.match(html, /Floor plan/);
  assert.match(html, /class="cj-tab on"[^>]*>\s*Rooms/);
  h.close();
});
