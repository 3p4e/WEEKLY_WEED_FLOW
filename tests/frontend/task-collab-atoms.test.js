'use strict';

/* ══════════════════════════════════════════════════════════════════════
   The task-collaboration surfaces now speak the design system's atoms:

     • dependencies  → .mw-dep with a met/unmet dot (task-extras.js)
     • acknowledgment → .mw-ack--pending/--accepted/--declined (collab.js)
     • subtask tree  → nested levels carry .mw-subbranch (render.js)

   The dep dot is the one place the restyle ADDS information: green means the
   blocking task is done and no longer blocks, red means it still does. That
   distinction must track other.status and nothing else — it is display, not
   a gate — and it must not invert, because a red dot on a satisfied blocker
   teaches people to ignore the red.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

/* task-extras.js and collab.js are monkey-patch layers over the card render
 * chain. Loading the real chain (views, api, voice…) drags in far more than
 * these assertions exercise, so the shared consts they need are declared the
 * way the page declares them, and only the functions under test are called. */
const PRE = `
  const AUDIT_ROLES = ['ADMIN'];
  window.GF = window.GF || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.render = { card: function () { return ''; }, panels: function () {}, all: function () {} };
  window.GF.PEOPLE = {};
  window.GF.state = window.GF.state || {};
  // chooser.js is not loaded here — stub GF.selectField the way the real one's
  // contract works (a hidden input + trigger), and stash the cfg (options
  // list included) so a test can inspect exactly what candidates renderDeps
  // built without needing the popup machinery itself.
  window.GF.__selectFieldCfgs = {};
  window.GF.selectField = function (id, cfg) {
    window.GF.__selectFieldCfgs[id] = cfg;
    return '<input type="hidden" id="' + id + '" value="' + (cfg.value || '') + '">';
  };
`;

function load(files) {
  return loadGF({ files: ['data.js', 'core.js', ...files], preScript: PRE });
}

test('a dependency renders met only when the blocking task is done', () => {
  const h = load(['collab.js', 'task-extras.js']);
  const t = { id: 'T-1', title: 'Dry room C183' };
  const html = h.GF.WWF.renderDeps(t, {
    blockedBy: [
      { id: 'B-1', title: 'Harvest C183', status: 'done' },
      { id: 'B-2', title: 'Clear PHI hold', status: 'working' },
      { id: 'B-3', title: 'No status at all' },
    ],
    blocks: [],
  });
  const chunk = (title) => {
    const i = html.indexOf(title);
    assert.ok(i > -1, `${title} not rendered`);
    return html.slice(html.lastIndexOf('<span class="mw-dep', i), i);
  };
  assert.match(chunk('Harvest C183'), /mw-dep met/);
  assert.match(chunk('Clear PHI hold'), /mw-dep unmet/,
    'an in-progress blocker showed as met — the dot just lied about a live block');
  assert.match(chunk('No status at all'), /mw-dep unmet/,
    'unknown status must read as still-blocking: the permissive direction is the wrong default');
  assert.match(html, /class="dot"/);
  h.close();
});

test('the "add blocker" candidate list excludes tasks that already depend on this one (avoids an obvious 409 cycle)', () => {
  const h = load(['collab.js', 'task-extras.js']);
  const { GF } = h;
  const t = { id: 'T-1', title: 'Dry room C183' };
  GF.state.tasks = [
    t,
    { id: 'B-1', title: 'Harvest C183' },         // already blocks T-1 (blockedBy)
    { id: 'D-1', title: 'Package C183' },         // already depends on T-1 (blocks) — cycle risk
    { id: 'X-1', title: 'Clean room 9' },         // unrelated, safe candidate
  ];
  const html = GF.WWF.renderDeps(t, {
    blockedBy: [{ id: 'B-1', title: 'Harvest C183', status: 'working' }],
    blocks: [{ id: 'D-1', title: 'Package C183', status: 'working' }],
  });
  assert.ok(html.includes('dep-add-T-1'), 'the add-blocker select field rendered');
  const cfg = GF.__selectFieldCfgs['dep-add-T-1'];
  assert.ok(cfg, 'GF.selectField was called for the add-blocker row');
  const ids = cfg.options.map(o => o.v);
  assert.deepEqual(ids, ['X-1'],
    'candidates must exclude T-1 itself, its existing blocker (B-1), AND anything that already depends on T-1 (D-1) — picking D-1 would create an immediate cycle the backend 409s on');
  h.close();
});

test('the "add blocker" row is omitted entirely once every other task is excluded', () => {
  const h = load(['collab.js', 'task-extras.js']);
  const { GF } = h;
  const t = { id: 'T-1', title: 'Dry room C183' };
  GF.state.tasks = [t, { id: 'D-1', title: 'Package C183' }];
  const html = GF.WWF.renderDeps(t, {
    blockedBy: [],
    blocks: [{ id: 'D-1', title: 'Package C183', status: 'working' }],
  });
  assert.equal(html.includes('dep-add-T-1'), false, 'no add-blocker control when there are no valid candidates left');
  h.close();
});

test('acknowledgment states render as the design ack pills, all three', () => {
  const h = load(['collab.js']);
  h.GF.API = { user: { id: 'U-me' } };
  h.GF.WWF.canManageTask = () => false;
  // renderCollabInner reads its data from the module cache, the way the real
  // load path stores it
  h.GF.WWF._collab['T-1'] = {
    loaded: true,
    comments: [],
    workflow: [],
    assignees: [
      { user_id: 'U-a', name: 'Ana', accepted: true },
      { user_id: 'U-b', name: 'Boro', accepted: false },
      { user_id: 'U-c', name: 'Cvete', accepted: null },
    ],
  };
  const html = h.GF.WWF.renderCollabInner({ id: 'T-1', title: 'x', status: 'working' });
  const of = (name) => {
    const i = html.indexOf(name);
    assert.ok(i > -1, `${name} not rendered`);
    return html.slice(i, i + 220);
  };
  assert.match(of('Ana'), /mw-ack mw-ack--accepted/);
  assert.match(of('Boro'), /mw-ack mw-ack--declined/);
  assert.match(of('Cvete'), /mw-ack mw-ack--pending/);
  // the e2e locates assignees by .dep-chip — the pill replaced the state
  // text, never the chip
  assert.match(html, /class="dep-chip/);
  h.close();
});

test('nested subtask levels carry the design branch, the top level does not', () => {
  const h = load(['render.js']);
  const { GF } = h;
  GF.state.children = {
    'P-1': [{ id: 'C-1', title: 'child', status: 'pending', weekId: 4 }],
    'C-1': [{ id: 'G-1', title: 'grandchild', status: 'pending', weekId: 4 }],
  };
  GF.state.treeOpen = new Set(['C-1']);
  GF.progress = () => 0;
  const html = GF.render.treeRows('P-1', 0);
  assert.match(html, /tree-rows tree-d0"/,
    'depth 0 must NOT carry mw-subbranch: the card body already provides the frame');
  assert.match(html, /tree-rows tree-d1 mw-subbranch"/,
    'nested levels lost the design branch border');
  h.close();
});
