'use strict';

/* ══════════════════════════════════════════════════════════════════════
   The app's --mw-* token layer must not drift from the design system.

   THE BUG THIS EXISTS TO PREVENT, found 2026-07-30 with the owner asking why
   the deployed app "is deliberately not the one I created in the design":

   There are TWO mass-weed.css files.
     • design/mass-weed-mockup/mass-weed.css — the AUTHORED design system.
       Defines ~48 --mw-* tokens (--mw-void, --mw-cyan, --mw-panel, --mw-ink…)
       and the .mw-* component atoms every mockup is written against.
     • web/gf/mass-weed.css — the SHIPPED skin. It used to define ZERO --mw-*
       tokens, mapping Mass Effect colours onto the app's generic token names
       (--bg/--ink/--primary) instead.

   The consequence was silent and total: any screen authored against the
   design system rendered UNSTYLED in the real app, because every
   var(--mw-…) resolved to nothing. Nothing failed, nothing logged — the page
   just looked wrong, and "looked wrong" is not something CI notices.

   So the shipped skin now carries the design system's token block verbatim,
   and this test pins the two together. It compares VALUES, not just presence:
   a token that exists in both but drifts to a different hex is exactly as
   broken as a missing one, and harder to spot by eye.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..');
const DESIGN = fs.readFileSync(
  path.join(ROOT, 'design', 'mass-weed-mockup', 'mass-weed.css'), 'utf8');
const SHIPPED = fs.readFileSync(path.join(ROOT, 'web', 'gf', 'mass-weed.css'), 'utf8');

/** The file's own comments NAME the atoms they document (".mw-htag (#hash
 *  outline chip)"), so a presence check against the raw text passes on the
 *  prose even after the real rule is gone. Every structural assertion below
 *  runs against comment-stripped CSS instead. */
const SHIPPED_CODE = SHIPPED.replace(/\/\*[\s\S]*?\*\//g, '');

/** Pull the `--mw-*: value;` pairs out of one CSS block. */
function tokensIn(css, blockRe, label) {
  const m = css.match(blockRe);
  assert.ok(m, `could not locate the ${label} block — this test needs updating, not deleting`);
  const out = new Map();
  for (const [, k, v] of m[1].matchAll(/(--mw-[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    out.set(k, v);
  }
  return out;
}

/** CSS treats `0.76` and `.76` as the same number; so must this comparison,
 *  or the test fails on formatting and gets muted for crying wolf. */
function norm(v) {
  return v.replace(/\s+/g, '').toLowerCase().replace(/(?<![\d.])0\./g, '.');
}

function compare(designBlock, shippedBlock, label) {
  const d = tokensIn(DESIGN, designBlock, `design ${label}`);
  const s = tokensIn(SHIPPED, shippedBlock, `shipped ${label}`);

  // Vacuity guard: if either parse silently returned nothing, every assertion
  // below would pass while checking literally nothing.
  assert.ok(d.size >= 20,
    `parsed only ${d.size} tokens from the design ${label} block — the parser is broken`);

  const missing = [...d.keys()].filter(k => !s.has(k)).sort();
  assert.deepEqual(missing, [],
    `these --mw-* tokens exist in the design system but NOT in web/gf/mass-weed.css, so any ` +
    `mockup using them renders unstyled in the real app: ${missing.join(', ')}`);

  const drifted = [...d.keys()]
    .filter(k => s.has(k) && norm(d.get(k)) !== norm(s.get(k)))
    .map(k => `${k} (design: ${d.get(k).trim()} | shipped: ${s.get(k).trim()})`);
  assert.deepEqual(drifted, [],
    `these --mw-* tokens have DRIFTED from the design system: ${drifted.join('; ')}`);

  return d.size;
}

test('the dark theme carries every design-system --mw-* token, unchanged', () => {
  const n = compare(/:root \{([\s\S]*?)\n\}/,
                    /:root\[data-theme="mass-weed"\] \{([\s\S]*?)\n\}/, 'dark');
  assert.ok(n >= 40, `expected the design system to define 40+ dark tokens, found ${n}`);
});

test('the light theme carries every design-system --mw-* override, unchanged', () => {
  // The design deliberately overrides only a SUBSET for daylight; everything
  // else inherits from the dark block. Overriding more in the shipped file
  // than the design does would fork the two without this catching it.
  compare(/\[data-theme="light"\]\{([\s\S]*?)\n\}/,
          /:root\[data-theme="mass-weed-light"\] \{([\s\S]*?)\n\}/, 'light');
});

test('the component atoms the newest designs depend on are all present', () => {
  // Stage 2 of the port. The design notes on depthome-qc.html name these as
  // "added to mass-weed.css as shared atoms" — they are what the QC screens
  // are built out of. A missing atom does not error; the element just renders
  // as an unstyled div, which is the same invisible failure the tokens had.
  const REQUIRED = [
    '.mw-panel', '.mw-well', '.mw-label', '.mw-field', '.mw-input',
    '.mw-tcard', '.mw-tcard__box', '.mw-tcard__main', '.mw-tcard__title',
    '.mw-tcard__meta', '.mw-tcard__dept', '.mw-tcard__id', '.mw-tcard__right',
    '.mw-attr', '.mw-htag', '.mw-due', '.mw-sub',
    '.mw-st--done', '.mw-st--working', '.mw-st--review',
    '.mw-st--stuck', '.mw-st--postponed',
  ];
  // Boundary-matched, NOT a bare substring check: `.includes('.mw-htag')`
  // also matches `.mw-htagXX`, so renaming an atom would slip straight past.
  // A selector must be followed by something that actually ends it.
  const missing = REQUIRED.filter(sel =>
    !new RegExp(sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![a-z0-9_-])', 'i').test(SHIPPED_CODE));
  assert.deepEqual(missing, [],
    `these design-system atoms are missing from web/gf/mass-weed.css, so markup using ` +
    `them renders unstyled: ${missing.join(', ')}`);
});

test('no --mw-* token is referenced without being defined or given a fallback', () => {
  // A var(--mw-x) that resolves to nothing is exactly the bug this whole port
  // fixes, so it must not be reintroduced by a future atom import. A var()
  // WITH a fallback is fine — the design sets --mw-acc inline per department,
  // by design, and every use of it carries a default.
  const defined = new Set([...SHIPPED_CODE.matchAll(/(--mw-[a-z0-9-]+)\s*:/g)].map(m => m[1]));
  const bare = new Set([...SHIPPED_CODE.matchAll(/var\((--mw-[a-z0-9-]+)\s*\)/g)].map(m => m[1]));
  assert.ok(bare.size >= 10, `parsed only ${bare.size} bare var() uses — the parser is broken`);
  const dangling = [...bare].filter(t => !defined.has(t)).sort();
  assert.deepEqual(dangling, [],
    `referenced with no definition and no fallback: ${dangling.join(', ')}`);
});

test('mass-weed.css has balanced braces', () => {
  // A truncated paste of a token block is the likeliest way this file breaks,
  // and an unbalanced brace silently swallows every rule after it.
  const open = (SHIPPED.match(/\{/g) || []).length;
  const close = (SHIPPED.match(/\}/g) || []).length;
  assert.equal(open, close, `web/gf/mass-weed.css has ${open} '{' and ${close} '}'`);
});
