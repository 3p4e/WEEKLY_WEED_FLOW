'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/task-detail-view.js — the Mass Weed design's full-screen task
   detail SCREEN (GF.WWF.openTaskDetail).

   These tests load the REAL source into a jsdom window the way index.html
   does and reach the render through the DOM it builds, so a regression in
   the view turns a test red rather than passing against a copy.

   What they pin:
     - THE SCREEN IS THE DESIGN, BOUND TO REAL DATA. The header, meta pills,
       subtasks, and sidebar come from the live task object / GF.state.children,
       not a mock — so the title, status label, and child rows must appear.
     - THE FULL-SCREEN FRAMING. It opens as .overlay.as-screen (the same
       surface the New-task create screen uses), never a floating popup.
     - QC IS THE DEEPER PAGE, GATED ON DEPARTMENT. Only a Quality-Control task
       grows the Lab Testing Lifecycle phase stepper + OOx deviation flag; a
       non-QC task must not, or every department would inherit QC's SOP UI.
     - AN UNKNOWN ID IS A NO-OP, NOT A CRASH.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

function baseTask(over) {
  return Object.assign({
    id: 't1', title: 'Pre-packing protocol — GR-2 harvest lot', desc: 'Execute the 9-step sampling protocol.',
    dept: 'flower', owner: 'u1', helpers: ['u2'], status: 'working', pr: 'high', type: 'lab',
    ref: 'QCSOP 011', due: '2026-07-14', tags: ['prepack', 'gr2'], recurrence: null,
    est: 2.5, notes: [{ d: 'Thu', n: 'Steps 1–2 clear.', by: 'u1' }], progressPct: 45, weekId: 3,
  }, over || {});
}

function boot(task, children) {
  const h = loadGF({ files: ['data.js', 'core.js', 'task-detail-view.js'] });
  const G = h.GF;
  G.state.user = 'u1';
  G.state.lang = 'en';
  G.PEOPLE = {
    u1: { name: 'Kaidan A.', init: 'KA', bg: '#123456', role: 'owner' },
    u2: { name: 'Liara V.', init: 'LV', bg: '#654321', role: 'operator' },
  };
  G.STATUS_COLORS = { pending: '#888', working: '#f0b95e', review: '#5ec8f0', stuck: '#ef4d4d', postponed: '#ecec4a', done: '#2be8a0' };
  G.progress = (t) => (t.status === 'done' ? 100 : (t.progressPct || 0));
  G.state.tasks = [task];
  G.state.children = children || {};
  return h;
}

test('openTaskDetail is registered as a function', () => {
  const h = boot(baseTask());
  assert.equal(typeof h.GF.WWF.openTaskDetail, 'function');
  h.close();
});

test('opens as a full-screen .overlay.as-screen bound to the real task', () => {
  const child = { id: 'c1', title: 'Container selection', status: 'pending', owner: 'u2' };
  const h = boot(baseTask(), { t1: [child] });
  h.GF.WWF.openTaskDetail('t1');
  const doc = h.window.document;
  const modal = doc.getElementById('td-modal');
  assert.ok(modal, '#td-modal overlay was created');
  assert.ok(modal.classList.contains('overlay'), 'is an .overlay');
  assert.ok(modal.classList.contains('as-screen'), 'is full-screen (.as-screen), not a popup');
  assert.ok(modal.classList.contains('open'), 'was opened');
  const wrap = modal.querySelector('.td-wrap');
  assert.ok(wrap, '.td-wrap body rendered');
  assert.match(wrap.querySelector('h1').textContent, /Pre-packing protocol/, 'real title in the header');
  // status label from GF.statusLabel, not a hardcoded string
  assert.ok(wrap.textContent.includes(h.GF.statusLabel('working')), 'status pill reflects the live status');
  // real subtask child row present
  assert.ok(wrap.querySelector('#td-subs').textContent.includes('Container selection'), 'child subtask rendered from GF.state.children');
  h.close();
});

test('a non-QC task does NOT grow the QC lab-lifecycle stepper', () => {
  const h = boot(baseTask({ dept: 'flower' }));
  h.GF.WWF.openTaskDetail('t1');
  const doc = h.window.document;
  assert.equal(doc.querySelector('#td-stepper'), null, 'no phase stepper for a non-QC task');
  assert.equal(doc.querySelector('#td-dev'), null, 'no OOx deviation flag for a non-QC task');
  h.close();
});

test('a QC task grows the Lab Testing Lifecycle stepper (5 phases) + deviation flag', () => {
  const h = boot(baseTask({ dept: 'qc' }));
  h.GF.WWF.openTaskDetail('t1');
  const doc = h.window.document;
  const stepper = doc.querySelector('#td-stepper');
  assert.ok(stepper, 'QC task shows the phase stepper');
  assert.equal(stepper.querySelectorAll('.mw-step').length, 5, 'all five QCSOP-001 phases');
  assert.ok(doc.querySelector('#td-dev'), 'QC task shows the OOx deviation flag');
  // stepper is namespaced (.td-stepper) so it never re-bases the doc-lifecycle .mw-stepper
  assert.equal(doc.querySelectorAll('.td-stepper').length, 1);
  h.close();
});

test('an unknown task id is a no-op, not a crash', () => {
  const h = boot(baseTask());
  assert.doesNotThrow(() => h.GF.WWF.openTaskDetail('does-not-exist'));
  const modal = h.window.document.getElementById('td-modal');
  // either no modal, or one that never got a .td-wrap body
  assert.ok(!modal || !modal.querySelector('.td-wrap'), 'no detail body built for a missing task');
  h.close();
});
