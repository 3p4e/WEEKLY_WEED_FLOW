'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/integrate.js — the department head (PATCH /departments/{id}).

   DECISIONS A-3: the head is the manager a handoff to the department is
   addressed to, and ADMIN may set any elevated user. The route had no
   screen and GF.DEPTS never carried head_user_id, so handoffRights'
   department-head branch was unreachable (review 2026-09-27, INV-06 /
   R2-FE-14). integrate.js ends with a bare install() and is not loadable
   whole, so the two functions are sliced out of it and run as written.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF, GF_DIR } = require('./helpers/gf-window.js');

const SRC = fs.readFileSync(path.join(GF_DIR, 'integrate.js'), 'utf8');
const start = SRC.indexOf('GF.WWF.openDeptHeadForm = ');
const end = SRC.indexOf('// openUser(id)', start);
assert.ok(start > 0 && end > start, 'openDeptHeadForm / saveDeptHead not found in integrate.js');
const HEAD_SRC = SRC.slice(start, end);

test('GF.DEPTS carries head_user_id from GET /departments (the branch handoffRights reads)', () => {
  const map = SRC.slice(SRC.indexOf('GF.DEPTS = depts.map('), SRC.indexOf('GF.HANDOFF = {};'));
  assert.match(map, /head_user_id:\s*d\.head_user_id/);
});

function load(role) {
  const h = loadGF({ files: ['data.js', 'core.js', 'chooser.js', 'modules.js'] });
  const { GF, window: w } = h;
  GF.WWF = GF.WWF || {};
  GF.API = { user: { role } };
  GF.WWF.isAdmin = () => role === 'ADMIN';
  GF.WWF.loadAndRender = async () => { w.__reloaded = (w.__reloaded || 0) + 1; };
  GF.DEPTS = [{ id: 'd1', name: 'Production', mk: 'Производство', color: '#123', head_user_id: 'h1' }];
  GF.PEOPLE = {
    h1: { name: 'Head One', role: 'pr_mgr', backendRole: 'PR_MGR', active: true },
    op: { name: 'Operator', role: 'operator', backendRole: 'USER', active: true },
    ex: { name: 'Ex Manager', role: 'qa_mgr', backendRole: 'QA_MGR', active: false },
    qa: { name: 'Quality', role: 'qa_mgr', backendRole: 'QA_MGR', active: true },
  };
  w.__modals = []; w.__closed = []; w.__toasts = [];
  GF.WWF._ensureModal = (id) => {
    if (w.document.getElementById(id)) return;
    const wrap = w.document.createElement('div');
    wrap.id = id;
    wrap.innerHTML = `<div id="${id}-title"></div><div id="${id}-body"></div>`;
    w.document.body.appendChild(wrap);
  };
  h.load(HEAD_SRC, '<integrate.js:openDeptHeadForm>');
  // The real GF.selectField renders only the current label (the options live
  // in chooser.js's registry); record the cfg so the offered set is readable.
  w.__selCfg = {};
  GF.selectField = (id, cfg) => { w.__selCfg[id] = cfg; return `<input type="hidden" id="${id}" value="${cfg.value || ''}">`; };
  GF.openModal = (id) => { w.__modals.push(id); };
  GF.closeModal = (id) => { w.__closed.push(id); };
  GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  GF.once = async (id, fn) => fn();
  return h;
}

test('the head chooser offers only active users holding an elevated role, with the current head selected', () => {
  const h = load('ADMIN');
  const { GF, window: w } = h;
  GF.WWF.openDeptHeadForm('d1');
  assert.deepEqual(w.__modals, ['dept-head-modal']);
  const labels = w.__selCfg['dept-head-user'].options.map(o => o.label).join('|');
  assert.match(labels, /Head One/);
  assert.match(labels, /Quality/);
  assert.doesNotMatch(labels, /Operator/, 'a department is run by a manager, not an operator (tasks.py _validate_department_head)');
  assert.doesNotMatch(labels, /Ex Manager/, 'an inactive account is not offered');
  assert.equal(w.document.getElementById('dept-head-user').value, 'h1');
  h.close();
});

test('saving PATCHes head_user_id, and clearing sends an explicit null', async () => {
  const h = load('ADMIN');
  const { GF, window: w } = h;
  const calls = [];
  GF.API.departmentPatch = async (id, body) => { calls.push([id, JSON.parse(JSON.stringify(body))]); return {}; };
  GF.WWF.openDeptHeadForm('d1');
  w.document.getElementById('dept-head-user').value = 'qa';
  await GF.WWF.saveDeptHead('d1');
  w.document.getElementById('dept-head-user').value = '';
  await GF.WWF.saveDeptHead('d1');
  assert.deepEqual(calls, [['d1', { head_user_id: 'qa' }], ['d1', { head_user_id: null }]]);
  assert.deepEqual(w.__closed, ['dept-head-modal', 'dept-head-modal']);
  assert.equal(w.__reloaded, 2, 'the departments are reloaded so GF.DEPTS carries the new head');
  h.close();
});

test('a non-admin can neither open the form nor save through it', async () => {
  const h = load('QA_MGR');
  const { GF, window: w } = h;
  let patched = 0;
  GF.API.departmentPatch = async () => { patched++; return {}; };
  GF.WWF.openDeptHeadForm('d1');
  assert.deepEqual(w.__modals, []);
  await GF.WWF.saveDeptHead('d1');
  assert.equal(patched, 0);
  h.close();
});
