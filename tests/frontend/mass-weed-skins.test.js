'use strict';

/* ══════════════════════════════════════════════════════════════════════
   The Mass Weed hue schemes — "ONE identity, MANY hues" (design mw-i18n.js).

   A hue scheme is data-skin on <html>: it re-hues the two mass-weed themes'
   accent family, backdrop and glow, touches none of the other 33 skins, and
   deliberately never re-hues the semantic stat colors. Three parties must
   agree for it to work, and each pair can drift independently and silently:

     • design/mass-weed-mockup/mw-i18n.js — the authored list (id, hex, names)
     • web/gf/core.js GF.MW_SKINS          — the app's copy of that list
     • web/gf/mass-weed.css                — the [data-skin] token blocks
     • web/index.html boot script          — the pre-paint healing allow-list

   A skin present in the list but missing its CSS block is the token bug all
   over again: the dot renders, the click persists, and the shell repaints in
   nothing. So this file pins each pair to the design source, values included.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF } = require('./helpers/gf-window.js');

const ROOT = path.resolve(__dirname, '..', '..');
const rd = (...p) => fs.readFileSync(path.join(ROOT, ...p), 'utf8');
const DESIGN_I18N = rd('design', 'mass-weed-mockup', 'mw-i18n.js');
const DESIGN_CSS = rd('design', 'mass-weed-mockup', 'mass-weed.css');
const SHIPPED = rd('web', 'gf', 'mass-weed.css').replace(/\/\*[\s\S]*?\*\//g, '');
const INDEX = rd('web', 'index.html');

/** The authored skin list, parsed from the design's own SKINS array:
 *  ['renegade', '#f0555e', 'Renegade', 'Ренегат'], … */
function designSkins() {
  const m = DESIGN_I18N.match(/var SKINS = \[([\s\S]*?)\];/);
  assert.ok(m, 'mw-i18n.js no longer declares var SKINS — this test needs updating, not deleting');
  const out = [...m[1].matchAll(/\['([a-z]+)',\s*'(#[0-9a-f]{6})',\s*'([^']+)',\s*'([^']+)'\]/g)]
    .map(([, id, hex, en, mk]) => ({ id, hex, en, mk }));
  assert.ok(out.length >= 7, `parsed only ${out.length} skins from mw-i18n.js — the parser is broken`);
  return out;
}

/** --mw-* pairs in the first block matching `selector`{…} of a css text. */
function tokensIn(css, selector) {
  const m = css.match(new RegExp(selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\{([\\s\\S]*?)\\}'));
  if (!m) return null;
  return new Map([...m[1].matchAll(/(--mw-[a-z0-9-]+)\s*:\s*([^;]+);/g)]
    .map(([, k, v]) => [k, v.replace(/\s+/g, ' ').trim()]));
}

test('GF.MW_SKINS matches the design list — ids, hexes and both names', () => {
  const h = loadGF({ files: ['data.js', 'core.js'] });
  // Array.from in THIS realm, not h.GF.MW_SKINS.map: .map returns an array of
  // the receiver's (jsdom) realm, and deepStrictEqual compares prototypes, so
  // identical values would still fail as "different" across realms.
  const app = Array.from(h.GF.MW_SKINS, ({ id, hex, en, mk }) => ({ id, hex, en, mk }));
  assert.deepEqual(app, designSkins(),
    'web/gf/core.js GF.MW_SKINS has drifted from design/mass-weed-mockup/mw-i18n.js');
  h.close();
});

test('every non-default skin has its accent AND dark-backdrop CSS blocks, with design values', () => {
  for (const { id } of designSkins()) {
    if (id === 'alliance') continue;   // the default is the absence of the attribute
    const dAcc = tokensIn(DESIGN_CSS, `[data-skin="${id}"]`);
    const dDark = tokensIn(DESIGN_CSS, `[data-theme="dark"][data-skin="${id}"]`);
    assert.ok(dAcc && dDark, `the design CSS itself lacks blocks for "${id}" — update this test's source expectations`);
    const sAcc = tokensIn(SHIPPED, `:root[data-theme^="mass-weed"][data-skin="${id}"]`);
    const sDark = tokensIn(SHIPPED, `:root[data-theme="mass-weed"][data-skin="${id}"]`);
    assert.ok(sAcc, `web/gf/mass-weed.css has no accent block for data-skin="${id}" — the dot picks a hue that paints nothing`);
    assert.ok(sDark, `web/gf/mass-weed.css has no dark backdrop block for data-skin="${id}"`);
    for (const [k, v] of dAcc) {
      assert.equal(sAcc.get(k), v, `${id}: shipped accent token ${k} drifted from the design`);
    }
    for (const [k, v] of dDark) {
      assert.equal(sDark.get(k), v, `${id}: shipped backdrop token ${k} drifted from the design`);
    }
    // The app-token derivation — the part the DESIGN does not need but the app
    // cannot work without: with --mw-* re-hued and --primary/--bg still cyan,
    // atoms and chrome disagree, the exact halfway state the port prevents.
    const block = SHIPPED.match(new RegExp(
      `:root\\[data-theme="mass-weed"\\]\\[data-skin="${id}"\\]\\{([\\s\\S]*?)\\}`))[1];
    for (const t of ['--bg:', '--surface:', '--primary:', '--accent-rgb:', '--mw-bg-g1:']) {
      assert.ok(block.includes(t), `${id}: dark block does not re-derive ${t.slice(0, -1)} for the app chrome`);
    }
    const light = SHIPPED.match(new RegExp(
      `:root\\[data-theme="mass-weed-light"\\]\\[data-skin="${id}"\\]\\{([\\s\\S]*?)\\}`));
    assert.ok(light && light[1].includes('--primary:'),
      `${id}: no light-theme accent derivation — Cool Mist would stay cyan under this hue`);
  }
});

test('the accent-rgb triplet in each dark block IS the skin hex, not a stale copy', () => {
  const hex2rgb = (hx) => [1, 3, 5].map((i) => parseInt(hx.slice(i, i + 2), 16)).join(',');
  for (const { id, hex } of designSkins()) {
    if (id === 'alliance') continue;
    const block = SHIPPED.match(new RegExp(
      `:root\\[data-theme="mass-weed"\\]\\[data-skin="${id}"\\]\\{([\\s\\S]*?)\\}`))[1];
    const m = block.match(/--accent-rgb:\s*([\d,]+)/);
    assert.ok(m, `${id}: no --accent-rgb`);
    assert.equal(m[1].replace(/\s/g, ''), hex2rgb(hex),
      `${id}: --accent-rgb does not match the ${hex} accent — rgba(var(--accent-rgb)) glows the wrong colour`);
  }
});

test('the boot script heals and applies gf_mw_skin with the same id list', () => {
  const m = INDEX.match(/var HUES=\[([^\]]+)\]/);
  assert.ok(m, "index.html's boot script no longer carries the HUES allow-list");
  const boot = m[1].match(/'([a-z]+)'/g).map((s) => s.slice(1, -1));
  assert.deepEqual(boot, designSkins().map((k) => k.id),
    'the boot allow-list drifted from the design list: a saved skin the app offers would be healed away at boot (or a retired one kept)');
  assert.match(INDEX, /gf_mw_skin/, 'boot script does not read the persisted hue at all');
});

test('setMWSkin applies the attribute, persists, and treats the default as absence', () => {
  const h = loadGF({ files: ['data.js', 'core.js'] });
  const root = h.window.document.documentElement;
  h.GF.setMWSkin('renegade');
  assert.equal(root.dataset.skin, 'renegade');
  assert.equal(h.window.localStorage.getItem('gf_mw_skin'), 'renegade');
  assert.equal(h.GF.curMWSkin(), 'renegade');
  h.GF.setMWSkin('alliance');
  assert.equal(root.dataset.skin, undefined,
    'alliance must REMOVE the attribute: the default cyan comes from the base blocks, never from a [data-skin] match');
  assert.equal(h.window.localStorage.getItem('gf_mw_skin'), 'alliance');
  h.close();
});

test('an unknown skin id snaps to the default instead of styling nothing', () => {
  const h = loadGF({ files: ['data.js', 'core.js'] });
  h.GF.setMWSkin('geth');   // not a hue and never will be
  assert.equal(h.window.document.documentElement.dataset.skin, undefined);
  assert.equal(h.GF.curMWSkin(), 'alliance');
  h.close();
});

test('the theme picker offers the hue row on mass-weed and not on carbon skins', () => {
  const h = loadGF({ files: ['data.js', 'core.js'] });
  const doc = h.window.document;
  doc.documentElement.dataset.theme = 'mass-weed';
  h.GF.openThemePicker();
  assert.equal(doc.querySelectorAll('.mw-skins__dot').length, h.GF.MW_SKINS.length,
    'one dot per hue while a mass-weed theme is active');
  doc.documentElement.dataset.theme = 'nord';
  h.GF.openThemePicker();
  assert.equal(doc.querySelectorAll('.mw-skins__dot').length, 0,
    'the hue axis re-tints nothing outside mass-weed, so offering it there teaches the user the panel is decorative');
  h.close();
});
