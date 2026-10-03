'use strict';

/* ══════════════════════════════════════════════════════════════════════
   Approvals is reachable by every manager role (review 2026-09-27, R2-FE-01).

   `approvals` was a key of the `audit` module (roles QA_MGR / QC_MGR / QP),
   so PR_MGR — the receiver of the owner's own cultivation → production
   handoff — and CU/WH/IR/SE/MU_MGR could never open "Handoffs to your
   department": no rail item in any module, and the handoff notification's
   setView('approvals') was bounced to My Week by render.all(). The key now
   lives in the task module (roles: null); the view's own guard
   (role !== 'USER') keeps it off the operator rail, and openNotif sends an
   operator to the task instead of a view that bounces.

   These tests drive the REAL module registry, the REAL rail renderer, the
   REAL _registerFullPageView (sliced out of integrate.js, whose tail is not
   loadable in isolation) and the real approvals-view.js registration.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF, GF_DIR } = require('./helpers/gf-window.js');

const MANAGERS = ['PR_MGR', 'CU_MGR', 'WH_MGR', 'IR_MGR', 'SE_MGR', 'MU_MGR', 'QA_MGR', 'QC_MGR', 'QP'];

// The real registration helper, verbatim from integrate.js.
const integrateSrc = fs.readFileSync(path.join(GF_DIR, 'integrate.js'), 'utf8');
const regStart = integrateSrc.indexOf('GF.WWF._registerFullPageView = (');
const regEnd = integrateSrc.indexOf('\n};', regStart) + 3;
assert.ok(regStart > 0 && regEnd > regStart, '_registerFullPageView not found in integrate.js');
const REGISTER_SRC = integrateSrc.slice(regStart, regEnd);

const PRE = (role) => `
  window.setTimeout = function () { return 0; };
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF.deptScope = function () { return null; };
  window.GF.hasDeptHome = function () { return false; };
  window.GF.API = { user: { role: ${JSON.stringify(role)} }, token: '' };
`;
const SHELL = '<nav id="nav"></nav><div id="side-label"></div><div id="dept-list"></div><div id="user-card"></div>';

async function railFor(role, moduleId = 'tasks') {
  const h = loadGF({ files: ['data.js', 'core.js', 'chooser.js', 'modules.js', 'render.js'],
                     preScript: PRE(role), bodyHtml: SHELL });
  h.load(REGISTER_SRC, '<integrate.js:_registerFullPageView>');
  h.load(fs.readFileSync(path.join(GF_DIR, 'approvals-view.js'), 'utf8'), 'web/gf/approvals-view.js');
  const w = h.window;
  w.GF.state.user = 'me';
  w.GF.PEOPLE = { me: { name: 'Me', role: 'operator', roleLabel: '' } };
  w.GF.DEPTS = [];
  w.GF.state.module = moduleId;
  w.GF.render.sidebar();
  const keys = [...w.document.querySelectorAll('#nav .nav-item')].map(e => e.dataset.nav);
  await new Promise(r => setImmediate(r));
  h.close();
  return keys;
}

test('approvals is a task-module key, not an audit-module one', () => {
  const { GF, close } = loadGF({ files: ['data.js', 'core.js', 'chooser.js', 'modules.js'] });
  assert.equal(GF.moduleForKey('approvals'), 'tasks');
  assert.ok(!GF.moduleById('audit').keys.includes('approvals'));
  close();
});

for (const role of MANAGERS) {
  test(`keyVisibleNow('approvals') holds for ${role} in the task module`, () => {
    const { GF, close } = loadGF({ files: ['data.js', 'core.js', 'chooser.js', 'modules.js'] });
    GF.API = { user: { role } };
    GF.state.module = 'tasks';
    assert.equal(GF.keyVisibleNow('approvals'), true);
    close();
  });
}

for (const role of MANAGERS) {
  test(`the real task rail carries an Approvals item for ${role}`, async () => {
    const keys = await railFor(role);
    assert.ok(keys.includes('approvals'), `no [data-nav="approvals"] for ${role}: ${keys.join(',')}`);
    // It sits in the Management group, ahead of Coordination (insertBefore: 'coord').
    assert.equal(keys.indexOf('approvals'), keys.indexOf('coord') - 1);
  });
}

test('the operator rail does not carry Approvals (the view guard, not the module, excludes USER)', async () => {
  const keys = await railFor('USER');
  assert.ok(!keys.includes('approvals'));
});

test('a stale approvals view is NOT bounced for a department manager (render.all keeps it)', async () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'chooser.js', 'modules.js', 'render.js'],
                     preScript: PRE('PR_MGR'), bodyHtml: SHELL });
  h.load(REGISTER_SRC, '<integrate.js:_registerFullPageView>');
  h.load(fs.readFileSync(path.join(GF_DIR, 'approvals-view.js'), 'utf8'), 'web/gf/approvals-view.js');
  const { GF, window: w } = h;
  w.GF.state.user = 'me';
  w.GF.PEOPLE = { me: { name: 'Me', role: 'operator', roleLabel: '' } };
  w.GF.DEPTS = [];
  GF.state.module = 'tasks';
  GF.state.view = 'approvals';
  // render.all() renders the view through GF.views.approvals; the shell here
  // has no #panels, so stub the pieces after the guard check.
  GF.render.header = () => {};
  GF.render.weekStrip = () => {};
  GF.views.approvals = () => '';
  GF.$ = (id) => w.document.getElementById(id) || { style: {}, innerHTML: '' };
  GF.render.all();
  assert.equal(GF.state.view, 'approvals');
  await new Promise(r => setImmediate(r));   // let sidebar()'s prune microtask run on a live window
  h.close();
});

// ── openNotif routing ────────────────────────────────────────────────

const NOTIF_PRE = (role) => `
  window.setInterval = function () { return 0; };
  window.setTimeout = function () { return 0; };
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.PEOPLE = {};
  window.GF.icon = function () { return ''; };
  window.GF.avatar = function () { return ''; };
  window.GF.state = { user: 'me', lang: 'en', module: 'tasks' };
  window.GF.API = { token: 'tok', user: { id: 'me', role: ${JSON.stringify(role)} },
                    notifRead: async function () { return {}; } };
  window.__setView = []; window.__jump = [];
  window.GF.setView = function (v) { window.__setView.push(v); };
  window.GF.WWF.xrJump = function (id) { window.__jump.push(id); };
  window.GF.render = { all: function () {}, sidebar: function () {} };
`;

async function openHandoff(role) {
  const h = loadGF({ files: ['data.js', 'core.js', 'chooser.js', 'modules.js', 'notifications-view.js'],
                     preScript: NOTIF_PRE(role) });
  const { GF, window: w } = h;
  GF.state.module = 'tasks';
  // core.js defines the real GF.setView after the preScript ran; record the
  // call instead of navigating (render.js is not loaded here).
  GF.setView = (v) => { w.__setView.push(v); };
  const st = GF.WWF._notif;
  st.items = [{ id: 'n1', task_id: 't1', read: false, reason: 'assigned', verb: 'handoff',
                actor_id: 'u1', params: { title: 'Cut GP', to_dept: 'Production' }, created_at: '2026-07-27T10:00:00' }];
  await GF.WWF.openNotif('n1', 't1');
  const out = { setView: [...w.__setView], jump: [...w.__jump] };
  h.close();
  return out;
}

test('a handoff notification opens Approvals for the receiving manager', async () => {
  const r = await openHandoff('PR_MGR');
  assert.deepEqual(r.setView, ['approvals']);
  assert.deepEqual(r.jump, []);
});

test('a handoff notification jumps an operator to the task instead of a view that bounces', async () => {
  const r = await openHandoff('USER');
  assert.deepEqual(r.setView, []);
  assert.deepEqual(r.jump, ['t1']);
});
