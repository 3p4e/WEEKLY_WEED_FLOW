'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/render.js — Workload and the Executive overview live in the rail
   of the module that owns them (review 2026-09-27, FE-12).

   modules.js files both keys under `analytics`, but the rail emitted them
   in the task module's Management group. Clicking one switched the module,
   the rail re-rendered with only the analytics items — which did not
   include them — and the only way back was the module picker; and the
   Analytics module had no entry for either. These tests render the real
   rail under each module.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.WWF.deptScope = function () { return null; };
  window.GF.hasDeptHome = function () { return false; };
  window.GF.API = { user: { role: 'COO' } };
`;
const SHELL = '<nav id="nav"></nav><div id="side-label"></div><div id="dept-list"></div><div id="user-card"></div>';

// `role` is the PEOPLE-table role core.js's permission matrix reads
// (GF.curRole): 'coo' is an executive, 'qa_mgr' a department manager,
// 'operator' base staff.
async function rail(role, moduleId) {
  const h = loadGF({ files: ['data.js', 'core.js', 'chooser.js', 'modules.js', 'render.js'],
                     preScript: PRE, bodyHtml: SHELL });
  const w = h.window;
  w.GF.state.user = 'me';
  w.GF.PEOPLE = { me: { name: 'Me', role, roleLabel: '' } };
  w.GF.DEPTS = [];
  w.GF.state.module = moduleId;
  w.GF.render.sidebar();
  const keys = [...w.document.querySelectorAll('#nav .nav-item')].map(e => e.dataset.nav);
  const groups = [...w.document.querySelectorAll('#nav .nav-group')].map(e => e.textContent);
  // sidebar() queues pruneNavGroups as a microtask; let it run against a
  // live window before closing it.
  await new Promise(r => setImmediate(r));
  h.close();
  return { keys, groups };
}

test('the task rail no longer carries Workload or the Executive overview', async () => {
  const { keys } = await rail('coo', 'tasks');
  assert.ok(keys.includes('mywork') && keys.includes('coord') && keys.includes('team'), 'the task items are there');
  assert.ok(!keys.includes('workload'), 'Workload is an analytics-module view');
  assert.ok(!keys.includes('exec'), 'so is the Executive overview');
});

test('the analytics rail lists them under an Analytics group, for a role that may use them', async () => {
  const { keys, groups } = await rail('coo', 'analytics');
  assert.ok(groups.includes('Analytics'), 'the module has its own group label');
  assert.deepEqual(keys.filter(k => k === 'exec' || k === 'workload'), ['exec', 'workload']);
  assert.ok(!keys.includes('mywork'), 'task-module items stay out of the analytics rail');
});

test('the gates travel with the items: a manager gets Workload but not the Executive overview', async () => {
  const { keys } = await rail('qa_mgr', 'analytics');
  assert.ok(keys.includes('workload'), 'workload balancing is a coordination tool for managers');
  assert.ok(!keys.includes('exec'), 'the exec overview is for executives');
});
