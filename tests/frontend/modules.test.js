'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/modules.js — GF.MODULES registry, access helpers, keyVisibleNow
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

function loadModules(storageOverrides) {
  return loadGF({
    files: ['data.js', 'core.js', 'chooser.js', 'modules.js'],
    storage: storageOverrides || {},
  });
}

// Helper: cross-realm arrays from jsdom need JSON round-trip for deepStrictEqual.
const toJS = (v) => JSON.parse(JSON.stringify(v));

// ── Registry shape ────────────────────────────────────────────────────

test('GF.MODULES has exactly 6 modules with the expected ids', () => {
  const { GF, close } = loadModules();
  assert.equal(GF.MODULES.length, 6);
  const ids = toJS(GF.MODULES.map(m => m.id));
  assert.deepEqual(ids, ['tasks', 'qc', 'cultivation', 'biosecurity', 'audit', 'analytics']);
  close();
});

test('tasks module: roles=null, correct keys', () => {
  const { GF, close } = loadModules();
  const mod = GF.moduleById('tasks');
  assert.equal(mod.roles, null);
  const expectedKeys = ['depthome','mywork','board','timeline','calendar','myday','team',
    'coord','dash','report','inbox','search','import','intake'];
  assert.deepEqual(toJS(mod.keys), expectedKeys);
  close();
});

test('qc module: correct roles and keys', () => {
  const { GF, close } = loadModules();
  const mod = GF.moduleById('qc');
  assert.deepEqual(toJS(mod.roles), ['QC_MGR','QA_MGR','QP']);
  assert.deepEqual(toJS(mod.keys), ['qccoa','qcregister','qcsample','qclab','qcspec','qcpotency','qcleaves',
    'qccustody','qcecoa','qcoos','qcgenealogy','qmsstudio','qmsregistry','qmsknow']);
  close();
});

test('cultivation module: correct roles and keys', () => {
  const { GF, close } = loadModules();
  const mod = GF.moduleById('cultivation');
  assert.deepEqual(toJS(mod.roles), ['CU_MGR','PR_MGR','WH_MGR','MU_MGR']);
  assert.deepEqual(toJS(mod.keys), ['cultivation','facility','harvest']);
  close();
});

test('biosecurity module: correct roles and keys', () => {
  const { GF, close } = loadModules();
  const mod = GF.moduleById('biosecurity');
  assert.deepEqual(toJS(mod.roles), ['CU_MGR','QA_MGR','SE_MGR']);
  assert.deepEqual(toJS(mod.keys), ['decon','waste']);
  close();
});

test('audit module: correct roles and keys', () => {
  const { GF, close } = loadModules();
  const mod = GF.moduleById('audit');
  assert.deepEqual(toJS(mod.roles), ['QA_MGR','QC_MGR','QP']);
  assert.deepEqual(toJS(mod.keys), ['audit','auditprep','approvals']);
  close();
});

test('analytics module: correct roles (all elevated) and keys', () => {
  const { GF, close } = loadModules();
  const mod = GF.moduleById('analytics');
  assert.deepEqual(toJS(mod.roles), toJS(GF.ELEVATED_MODULE_ROLES));
  assert.deepEqual(toJS(mod.keys), ['analytics','execreport','workload','exec']);
  close();
});

// ── MODULE_OF_KEY covers every declared key ───────────────────────────

test('GF.MODULE_OF_KEY maps every key in every module', () => {
  const { GF, close } = loadModules();
  for (const mod of GF.MODULES) {
    for (const k of mod.keys) {
      assert.equal(GF.MODULE_OF_KEY[k], mod.id, `Key "${k}" not in MODULE_OF_KEY`);
    }
  }
  close();
});

// ── moduleAccessibleFor ───────────────────────────────────────────────

const ACCESS_TABLE = [
  // [role, moduleId, expected]
  ['USER',   'tasks',       true],
  ['USER',   'qc',          false],
  ['USER',   'cultivation', false],
  ['USER',   'biosecurity', false],
  ['USER',   'audit',       false],
  ['USER',   'analytics',   false],

  ['CU_MGR', 'tasks',       true],
  ['CU_MGR', 'cultivation', true],
  ['CU_MGR', 'biosecurity', true],
  ['CU_MGR', 'qc',          false],
  ['CU_MGR', 'audit',       false],
  ['CU_MGR', 'analytics',   true],   // CU_MGR is in ELEVATED_MODULE_ROLES

  ['QA_MGR', 'tasks',       true],
  ['QA_MGR', 'qc',          true],
  ['QA_MGR', 'biosecurity', true],
  ['QA_MGR', 'audit',       true],
  ['QA_MGR', 'analytics',   true],
  ['QA_MGR', 'cultivation', false],

  ['OWNER',  'tasks',       true],
  ['OWNER',  'qc',          true],
  ['OWNER',  'cultivation', true],
  ['OWNER',  'biosecurity', true],
  ['OWNER',  'audit',       true],
  ['OWNER',  'analytics',   true],

  ['ADMIN',  'tasks',       true],
  ['ADMIN',  'qc',          true],
  ['ADMIN',  'analytics',   true],
];

for (const [role, moduleId, expected] of ACCESS_TABLE) {
  test(`moduleAccessibleFor: ${role} / ${moduleId} → ${expected}`, () => {
    const { GF, close } = loadModules();
    assert.equal(GF.moduleAccessibleFor(moduleId, role), expected);
    close();
  });
}

// ── accessibleModules ─────────────────────────────────────────────────

test('accessibleModules(USER) returns only tasks', () => {
  const { GF, close } = loadModules();
  const ids = toJS(GF.accessibleModules('USER').map(m => m.id));
  assert.deepEqual(ids, ['tasks']);
  close();
});

test('accessibleModules(OWNER) returns all 6', () => {
  const { GF, close } = loadModules();
  const ids = toJS(GF.accessibleModules('OWNER').map(m => m.id));
  assert.equal(ids.length, 6);
  close();
});

// ── keyVisibleNow ─────────────────────────────────────────────────────

test('keyVisibleNow: a tasks-module key is visible when module=tasks', () => {
  const { GF, close } = loadModules();
  GF.API = { user: { role: 'USER' } };
  GF.state.module = 'tasks';
  assert.equal(GF.keyVisibleNow('mywork'), true);
  assert.equal(GF.keyVisibleNow('board'), true);
  close();
});

test('keyVisibleNow: a qc key is NOT visible when module=tasks', () => {
  const { GF, close } = loadModules();
  GF.API = { user: { role: 'QC_MGR' } };
  GF.state.module = 'tasks';
  assert.equal(GF.keyVisibleNow('qccoa'), false);
  close();
});

test('keyVisibleNow: a qc key IS visible when role=QC_MGR and module=qc', () => {
  const { GF, close } = loadModules();
  GF.API = { user: { role: 'QC_MGR' } };
  GF.state.module = 'qc';
  assert.equal(GF.keyVisibleNow('qccoa'), true);
  close();
});

test('keyVisibleNow: a qc key is NOT visible when USER even with module=qc', () => {
  const { GF, close } = loadModules();
  GF.API = { user: { role: 'USER' } };
  GF.state.module = 'qc';
  assert.equal(GF.keyVisibleNow('qccoa'), false);
  close();
});

test('keyVisibleNow: unclassified key fails CLOSED (hidden, not visible everywhere)', () => {
  const { GF, close } = loadModules();
  GF.API = { user: { role: 'USER' } };
  GF.state.module = 'tasks';
  assert.equal(GF.keyVisibleNow('completely-unknown-key'), false);
  close();
});

test('keyVisibleNow: unclassified key stays hidden even for a full-access role', () => {
  const { GF, close } = loadModules();
  // Fail-closed must not be bypassable by an elevated role — a key missing
  // from the registry is a gap to fix, not a door any role can walk through.
  GF.API = { user: { role: 'ADMIN' } };
  GF.state.module = 'analytics';
  assert.equal(GF.keyVisibleNow('completely-unknown-key'), false);
  close();
});

// ── setView carries cross-module deep links into the target module ─────
// (xrJump → setView('mywork'), exec-report "Open in board", calendar/⌘K jumps)

test('setView switches to the target view\'s module when the role can access it', () => {
  const { GF, close } = loadModules();
  GF.API = { user: { role: 'QC_MGR' } };
  GF.state.module = 'tasks';
  GF.setView('qccoa');            // a qc-module view, reached via a deep link
  assert.equal(GF.state.module, 'qc');
  assert.equal(GF.state.view, 'qccoa');
  close();
});

test('setView does NOT switch module for a view the role cannot access', () => {
  const { GF, close } = loadModules();
  GF.API = { user: { role: 'USER' } };
  GF.state.module = 'tasks';
  GF.setView('qccoa');            // USER has no qc access — gate preserved
  assert.equal(GF.state.module, 'tasks');   // render.all() then bounces the view
  close();
});

test('setView leaves the module unchanged for a same-module view', () => {
  const { GF, close } = loadModules();
  GF.API = { user: { role: 'USER' } };
  GF.state.module = 'tasks';
  GF.setView('board');
  assert.equal(GF.state.module, 'tasks');
  assert.equal(GF.state.view, 'board');
  close();
});

// ── VIEW_LABEL_KEY completeness ───────────────────────────────────────

test('GF.VIEW_LABEL_KEY covers every key in every module', () => {
  const { GF, close } = loadModules();
  for (const mod of GF.MODULES) {
    for (const k of mod.keys) {
      assert.ok(GF.VIEW_LABEL_KEY[k] !== undefined, `VIEW_LABEL_KEY missing key: "${k}"`);
    }
  }
  close();
});

// ── Persistence ───────────────────────────────────────────────────────

test('state.module is null when localStorage is empty', () => {
  const { GF, close } = loadModules();
  assert.equal(GF.state.module, null);
  close();
});

test('state.module is restored from localStorage', () => {
  const { GF, close } = loadModules({ gf_module: 'qc' });
  assert.equal(GF.state.module, 'qc');
  close();
});
