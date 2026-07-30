'use strict';

/* ══════════════════════════════════════════════════════════════════════
   Department identity must be ONE colour per department, everywhere.

   The design system's source of truth is the DEPTS config block the
   depthome-*.html pages share (c / col / ab per department). The app carried
   its own copies — DEPT_STYLE in integrate.js and the --dept-* tokens in
   web/gf/mass-weed.css — and five of seven had silently drifted, so QC was
   #9B7BE8 in every mockup and #7A5BE0 in the product. Nothing failed;
   the department just wore two colours depending on where you looked, which
   is exactly the "deliberately not the one I created in the design" class
   of bug the owner has already had to report by eye once.

   These tests pin every app copy to the design block, by value. The design
   file is parsed, not paraphrased: update the design and the test tells you
   which copies now lag.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..');
const rd = (...p) => fs.readFileSync(path.join(ROOT, ...p), 'utf8');

/** The DEPTS config from the design pages: { code: {col, ab} }. */
function designDepts() {
  const t = rd('design', 'mass-weed-mockup', 'depthome-qc.html');
  const m = t.match(/DEPTS = \[([\s\S]*?)\];/);
  assert.ok(m, 'depthome-qc.html no longer carries the DEPTS config — update this test, not delete it');
  const out = {};
  for (const [, code, col, ab] of m[1].matchAll(
    /c:'([a-z_]+)'[^}]*?col:'(#[0-9A-Fa-f]{6})'[^}]*?ab:'([A-Z]+)'/g)) {
    out[code] = { col: col.toUpperCase(), ab };
  }
  assert.ok(Object.keys(out).length === 7, `parsed ${Object.keys(out).length} departments — the parser is broken`);
  return out;
}

test('integrate.js DEPT_STYLE carries the design colour for every department', () => {
  const src = rd('web', 'gf', 'integrate.js');
  const m = src.match(/const DEPT_STYLE = \{([\s\S]*?)\};/);
  assert.ok(m, 'DEPT_STYLE moved — update this test');
  const app = {};
  for (const [, code, color] of m[1].matchAll(/([a-z_]+):\{icon:'[a-z]+',color:'(#[0-9A-Fa-f]{6})'\}/g)) {
    app[code] = color.toUpperCase();
  }
  const drifted = [];
  for (const [code, d] of Object.entries(designDepts())) {
    if (app[code] && app[code] !== d.col) drifted.push(`${code}: app ${app[code]} vs design ${d.col}`);
    if (!app[code]) drifted.push(`${code}: missing from DEPT_STYLE`);
  }
  assert.deepEqual(drifted, [],
    'DEPT_STYLE drifted from the design DEPTS config — the department wears two colours: ' + drifted.join('; '));
});

test('quality_control aliases to the same colour as qc', () => {
  // The backend has used both codes historically; if the alias drifts the
  // same department flips colour depending on which code a row carries.
  const src = rd('web', 'gf', 'integrate.js');
  const qc = src.match(/(?<![a-z_])qc:\{icon:'flask',color:'(#[0-9A-Fa-f]{6})'\}/);
  const qcc = src.match(/quality_control:\{icon:'flask',color:'(#[0-9A-Fa-f]{6})'\}/);
  assert.ok(qc && qcc, 'qc / quality_control entries moved');
  assert.equal(qcc[1].toUpperCase(), qc[1].toUpperCase());
});

test('the --dept-* tokens match the design in BOTH mass-weed theme blocks', () => {
  const css = rd('web', 'gf', 'mass-weed.css');
  const design = designDepts();
  const blocks = [...css.matchAll(/--dept-([a-z_]+):\s*(#[0-9A-Fa-f]{6})/g)];
  assert.ok(blocks.length >= 14, `found only ${blocks.length} --dept-* declarations (expected 7 per theme block)`);
  const drifted = [];
  for (const [, code, hex] of blocks) {
    if (design[code] && hex.toUpperCase() !== design[code].col) {
      drifted.push(`--dept-${code}: ${hex} vs design ${design[code].col}`);
    }
  }
  assert.deepEqual(drifted, [], 'CSS dept tokens drifted from the design: ' + drifted.join('; '));
});

test('the abbreviations match the design too', () => {
  const src = rd('web', 'gf', 'integrate.js');
  const m = src.match(/const DEPT_ABBR = \{([\s\S]*?)\};/);
  assert.ok(m, 'DEPT_ABBR moved — update this test');
  const app = {};
  for (const [, code, ab] of m[1].matchAll(/([a-z_]+):'([A-Z]+)'/g)) app[code] = ab;
  for (const [code, d] of Object.entries(designDepts())) {
    assert.equal(app[code], d.ab, `${code}: abbreviation drifted from the design`);
  }
});
