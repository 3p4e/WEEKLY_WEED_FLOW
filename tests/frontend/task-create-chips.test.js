'use strict';

/* ══════════════════════════════════════════════════════════════════════
   The New-task surface is the design's create page: inline chip groups
   (task-create-*.html) instead of values hidden behind popups.

   The owner requested this redesign explicitly, screenshots in hand. The
   design's rule is that a SMALL option set is fully visible — type, priority,
   lifecycle phase, OOx flag are one tap, with the chosen chip lit. What must
   NOT change is the contract underneath: every writer in the app
   (collectDeptAttrs, applyPreset, worklog.js's openEdit prefill) reads and
   writes GF.$(id).value on a hidden input and then calls GF.syncSelect(id).
   If chips forget that contract, presets silently stop pre-selecting and
   edit stops prefilling — visible controls, invisible values.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const FILES = ['data.js', 'core.js', 'chooser.js', 'dept-templates.js'];

const PRE = `
  window.GF = window.GF || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.render = { all: function () {}, panels: function () {} };
`;

function load() {
  const h = loadGF({ files: FILES, preScript: PRE });
  // Give the qc department its template code the way the API sync would.
  // data.js's legacy roster ALREADY has a code-less 'qc' row and deptCode()
  // takes the FIRST id match, so pushing a second row would leave the
  // code-less one winning and every template lookup silently null.
  const qc = h.GF.DEPTS.find((d) => d.id === 'qc');
  if (qc) qc.code = 'qc';
  else h.GF.DEPTS.push({ id: 'qc', name: 'Quality Control', mk: 'КК', icon: 'flask', color: '#9B7BE8', code: 'qc' });
  return h;
}

function mount(h, html) {
  const host = h.window.document.createElement('div');
  host.innerHTML = html;
  h.window.document.body.appendChild(host);
  return host;
}

test('chipField renders every option visible, with the current one lit', () => {
  const h = load();
  const host = mount(h, h.GF.chipField('f1', {
    value: 'b', title: 'T',
    options: [{ v: 'a', label: 'A' }, { v: 'b', label: 'B' }, { v: 'c', label: 'C' }],
  }));
  assert.equal(host.querySelectorAll('.mw-chip').length, 3, 'an option got hidden');
  assert.equal(host.querySelector('.mw-chip.on').dataset.v, 'b');
  assert.equal(host.querySelector('input[type="hidden"]#f1').value, 'b',
    'the hidden-input contract is gone — every existing writer breaks');
  h.close();
});

test('picking a chip moves the value, the light, and fires onPick', () => {
  const h = load();
  const picked = [];
  const host = mount(h, h.GF.chipField('f2', {
    value: 'a', clearable: false, onPick: (v) => picked.push(v),
    options: [{ v: 'a', label: 'A' }, { v: 'b', label: 'B' }],
  }));
  h.GF.pickChip('f2', 'b');
  assert.equal(h.window.document.getElementById('f2').value, 'b');
  assert.equal(host.querySelector('.mw-chip.on').dataset.v, 'b', 'the light did not move');
  assert.deepEqual(picked, ['b']);
  h.close();
});

test('a clearable field clears on a same-chip tap; clearable:false refuses', () => {
  // Optional attrs (OOx flag) clear by re-tapping — the design's "None"
  // without a None chip everywhere. Required fields (priority) must never
  // reach an empty value through the UI.
  const h = load();
  mount(h, h.GF.chipField('opt', { value: 'oos', options: [{ v: 'oos', label: 'OOS' }] }));
  h.GF.pickChip('opt', 'oos');
  assert.equal(h.window.document.getElementById('opt').value, '', 'optional field did not clear');
  mount(h, h.GF.chipField('req', { value: 'medium', clearable: false, options: [{ v: 'medium', label: 'M' }] }));
  h.GF.pickChip('req', 'medium');
  assert.equal(h.window.document.getElementById('req').value, 'medium', 'a required field emptied itself');
  h.close();
});

test('syncSelect refreshes chip state after a direct value write (the preset/edit path)', () => {
  // applyPreset and openEdit set GF.$(id).value = v directly, then call
  // GF.syncSelect(id) — exactly this sequence. If chips ignore it, presets
  // stop pre-selecting and edit stops prefilling with no error anywhere.
  const h = load();
  const host = mount(h, h.GF.chipField('f3', {
    value: '', options: [{ v: 'lab', label: 'Lab' }, { v: 'final', label: 'Final' }],
  }));
  h.window.document.getElementById('f3').value = 'final';
  h.GF.syncSelect('f3');
  assert.equal(host.querySelector('.mw-chip.on').dataset.v, 'final');
  h.close();
});

test('QC template renders lifecycle phase and OOx as inline chips, popup only for large sets', () => {
  const h = load();
  const html = h.GF.renderDeptFields('qc', {});
  for (const key of ['lifecycle_phase', 'oox_flag']) {
    assert.ok(html.includes(`id="attr-f-${key}-chips"`), `${key} is not an inline chip group`);
    assert.ok(html.includes(`id="attr-f-${key}"`), `${key} lost its hidden input`);
  }
  // 5 phases + 4 OOx flags, every option visible
  assert.match(html, /1 · RQS[\s\S]*5 · Closure/);
  assert.match(html, /OOS[\s\S]*OOC/);
  // inspection_type has 5 options -> also chips; a hypothetical larger set
  // keeps the searchable popup — prove the branch exists both ways
  assert.ok(html.includes('id="attr-f-inspection_type-chips"'));
  const big = h.GF.renderDeptFields.toString();
  assert.match(big, /opts\.length <= 6/, 'the small-set threshold moved — update this test with intent');
  h.close();
});

test('the OOx codes match the design task pages, and phase order is the QCSOP ladder', () => {
  const h = load();
  const tpl = h.GF.DEPT_TEMPLATES.qc;
  const phase = tpl.fields.find((f) => f.key === 'lifecycle_phase');
  const oox = tpl.fields.find((f) => f.key === 'oox_flag');
  assert.deepEqual(Array.from(phase.opts, (o) => o.v), ['rqs', 'sfr', 'str', 'ari', 'closure'],
    'the lifecycle ladder is ordered — RQS to Closure, same as the design stepper');
  assert.deepEqual(Array.from(oox.opts, (o) => o.v), ['oos', 'oot', 'ooe', 'ooc'],
    'the deviation codes come from QCSOP 019 via the design pages');
  h.close();
});
