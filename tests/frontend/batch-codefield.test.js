'use strict';

/* ══════════════════════════════════════════════════════════════════════
   codefield.js — GF.batchCodeField: the QC batch-id fields get the constant
   head the owner asked for (2026-09-05: "pre-fill the constant part, caret
   after it"), review 2026-09-27 INS-12.

   The facility's batch number is <cultivar code><MMYY><nn> (GP072501), so
   the constant head is the strain's code — the same rule the cultivation
   batch form already applies. A strain chooser sits in front of the code
   field: pick the strain, its code is there, type the tail. No strain =
   an ordinary input; an existing value keeps its spelling.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF, GF_DIR } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.state = { lang: 'en' };
`;
const load = () => loadGF({ files: ['data.js', 'core.js', 'codefield.js'], preScript: PRE });

const CVS = [
  { code: 'GP', name: 'Gorilla Punch' },
  { code: 'GPX', name: 'Gorilla Punch X' },
  { code: 'CJ', name: 'Cap Junky', is_active: false },
];

function field(w, cfg) {
  w.document.body.innerHTML = w.GF.batchCodeField('b', Object.assign({ cultivars: CVS }, cfg || {}));
  return { inp: w.document.getElementById('b'), sel: w.document.getElementById('b-cv') };
}
const pick = (w, sel, code) => { sel.value = code; sel.dispatchEvent(new w.Event('change', { bubbles: true })); };

test('the chooser offers the active strains and an empty field starts without a head', () => {
  const w = load().window;
  const { inp, sel } = field(w, {});
  assert.deepEqual([...sel.options].map(o => o.value), ['', 'GP', 'GPX'], 'an inactive strain is not offered');
  assert.equal(inp.value, '', 'no strain chosen = an ordinary input');
});

test('picking the strain puts its code in as the head, caret after it, and the tail is typed', () => {
  const w = load().window;
  const { inp, sel } = field(w, {});
  w.GF._batchCvPick.call(null, 'b'); // no-op while nothing is chosen
  pick(w, sel, 'GP');
  assert.equal(inp.value, 'GP');
  assert.equal(inp.selectionStart, 2, 'the caret continues after the head');
  inp.value = 'GP072501';
  inp.dispatchEvent(new w.Event('input', { bubbles: true }));
  assert.equal(inp.value, 'GP072501');
  // The head cannot be eaten by editing (codeField's guard).
  inp.value = 'P072501';
  inp.dispatchEvent(new w.Event('input', { bubbles: true }));
  assert.equal(inp.value, 'GP072501');
});

test('changing the strain swaps the head and keeps the tail', () => {
  const w = load().window;
  const { inp, sel } = field(w, {});
  pick(w, sel, 'GP');
  inp.value = 'GP072501';
  pick(w, sel, 'GPX');
  assert.equal(inp.value, 'GPX072501');
  pick(w, sel, '');
  assert.equal(inp.value, '072501', 'no strain: the head goes, the typed tail stays');
});

test('an existing value keeps its spelling and preselects its strain by the longest matching head', () => {
  const w = load().window;
  const { inp, sel } = field(w, { value: 'GPX072501' });
  assert.equal(inp.value, 'GPX072501');
  assert.equal(sel.value, 'GPX', 'GPX, not GP, is the head of GPX072501');
  const other = field(w, { value: 'AB-legacy' });
  assert.equal(other.inp.value, 'AB-legacy', 'a code that predates the convention is shown as recorded');
  assert.equal(other.sel.value, '');
});

test('a strain change re-fires the view\'s own oninput so its draft sees the new value', () => {
  const w = load().window;
  const { sel } = field(w, { oninput: 'window.__seen = this.value' });
  pick(w, sel, 'GP');
  assert.equal(w.__seen, 'GP');
});

test('the cultivar list is fetched once per session and every waiting form is told', async () => {
  const w = load().window;
  let calls = 0;
  let resolve;
  w.GF.API = { cultivars: () => { calls++; return new Promise(r => { resolve = r; }); } };
  const seen = [];
  // Arrays come back from the jsdom realm, so they are compared by length.
  assert.equal(w.GF.batchCodeCultivars((cvs) => seen.push(['a', cvs.length])).length, 0, 'nothing known yet');
  assert.equal(w.GF.batchCodeCultivars((cvs) => seen.push(['b', cvs.length])).length, 0, 'a second form waits on the same request');
  assert.equal(calls, 1);
  resolve({ cultivars: CVS });
  await new Promise(r => setImmediate(r));
  assert.deepEqual(seen, [['a', 3], ['b', 3]]);
  assert.equal(w.GF.batchCodeCultivars().length, 3, 'served from the cache now');
  assert.equal(calls, 1);
  w.GF.batchCodeCultivars.reset();
  assert.equal(w.GF.batchCodeCultivars().length, 0, 'a new login starts over');
  assert.equal(calls, 2);
});

test('the three QC batch-id fields the owner named use the control', () => {
  for (const [file, id] of [['qcsample-view.js', 'qsm-batch'], ['qcecoa-view.js', 'qec-batch'], ['qcoos-view.js', 'qoo-batch']]) {
    const src = fs.readFileSync(path.join(GF_DIR, file), 'utf8');
    assert.match(src, new RegExp(`GF\\.batchCodeField\\('${id}'`), `${file}: ${id} is a batch code field`);
    assert.doesNotMatch(src, new RegExp(`<input id="${id}"`), `${file}: ${id} is no longer plain text`);
  }
});
