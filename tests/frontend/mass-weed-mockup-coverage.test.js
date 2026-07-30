'use strict';

/* ══════════════════════════════════════════════════════════════════════
   Every .mw-* class a mockup puts in its markup must be styled somewhere.

   THE FAILURE MODE, and why it needs a test rather than an eyeball:
   an undefined CSS class does not error. The browser does not warn, nothing
   is logged, the element still renders — as a bare unstyled <div>. This is
   the same silent class of breakage that let web/gf/mass-weed.css ship with
   ZERO --mw-* tokens (see mass-weed-tokens.test.js): the app looked wrong,
   and "looks wrong" is not something CI notices.

   It bit for real on 2026-07-30. Three new QC mockups landed written against
   .mw-chip, while the design system defines .mw-chip2 — a one-character
   naming mismatch that no amount of reading catches and no test then existed
   to catch either.

   WHAT COUNTS AS "STYLED": a rule in design/mass-weed-mockup/mass-weed.css,
   or a rule in the mockup's own <style> block. Both are real; a page-scoped
   atom is a legitimate choice, an atom styled in NEITHER place is not.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const DIR = path.resolve(__dirname, '..', '..', 'design', 'mass-weed-mockup');

/** Comments NAME the atoms they document, so a presence check against raw
 *  text passes on the prose after the real rule is gone. Always strip. */
const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '');

const selectorsIn = (css) =>
  new Set([...stripComments(css).matchAll(/\.(mw-[A-Za-z0-9_-]+)/g)].map((m) => m[1]));

/** Class names as they appear in markup. Several mockups build the attribute
 *  in JS — `class="mw-tcard'+(done?' mw-tcard--done':'')+'"` — so the value is
 *  scanned for class-shaped tokens rather than split on whitespace, which
 *  would yield `mw-tcard'+(done?'` and match nothing. */
function classesUsedIn(html) {
  const used = new Set();
  for (const [, attr] of html.matchAll(/class="([^"]*)"/g)) {
    for (const m of attr.matchAll(/mw-[a-z0-9_-]+/g)) used.add(m[0]);
  }
  return used;
}

/** `'mw-st--'+card.status` leaves the literal prefix `mw-st--` behind. That is
 *  a fragment of a name, not a name: the real class is computed at runtime and
 *  cannot be checked statically. Drop trailing-separator fragments — and ONLY
 *  those, so a genuinely undefined atom never hides behind this filter. */
const isRuntimeFragment = (cls) => /(--|__)$/.test(cls);

/** Atoms used in markup that nothing styles, as of 2026-07-30.
 *
 *  This is a record of a real gap, not a licence. Each entry means some part
 *  of that mockup renders unstyled today. They are listed so the gap is
 *  visible in the repo and cannot GROW silently — a new undefined atom fails
 *  this test immediately.
 *
 *  • mw-chip / mw-chip--sm / mw-chips — the newest QC pages were written
 *    against `.mw-chip`; the design system defines `.mw-chip2`. One of the two
 *    names is wrong and only the design's author can say which.
 *  • mw-ack(+--accepted/--pending), mw-dep, mw-reveal(+--info/--warn),
 *    mw-subnode, mw-subbranch, mw-subghost, mw-step__t, mw-hero-ic — atoms the
 *    2026-07-30 task-detail / task-create designs depend on that are not in
 *    the mass-weed.css revision committed here. Most likely the design CSS is
 *    a revision behind what those pages were authored against.
 *  • mw-catalog-row / mw-cat-name — pre-existing, same shape, older files.
 *
 *  Deleting an entry once its atom is styled is REQUIRED: the "no stale
 *  entries" test below fails on any that has been fixed, so this list cannot
 *  quietly outlive the problem it documents. */
const KNOWN_UNSTYLED = new Set([
  'mw-ack', 'mw-ack--accepted', 'mw-ack--pending',
  'mw-cat-name', 'mw-catalog-row',
  'mw-chip', 'mw-chip--sm', 'mw-chips',
  'mw-dep', 'mw-hero-ic',
  'mw-reveal', 'mw-reveal--info', 'mw-reveal--warn',
  'mw-step__t', 'mw-subbranch', 'mw-subghost', 'mw-subnode',
]);

const DESIGN_CSS = selectorsIn(fs.readFileSync(path.join(DIR, 'mass-weed.css'), 'utf8'));
const MOCKUPS = fs.readdirSync(DIR).filter((f) => f.endsWith('.html')).sort();

/** every mockup, paired with the atoms it uses that nothing styles */
function unstyledByFile() {
  const out = new Map();
  for (const name of MOCKUPS) {
    const html = fs.readFileSync(path.join(DIR, name), 'utf8');
    const inline = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join('\n');
    const defined = new Set([...DESIGN_CSS, ...selectorsIn(inline)]);
    const missing = [...classesUsedIn(html)]
      .filter((c) => !defined.has(c) && !isRuntimeFragment(c))
      .sort();
    if (missing.length) out.set(name, missing);
  }
  return out;
}

test('the mockup set is actually being read', () => {
  // Without this, a bad DIR or a changed extension turns every assertion
  // below into a check of the empty set, which passes for the wrong reason.
  assert.ok(MOCKUPS.length >= 30,
    `found only ${MOCKUPS.length} mockups in ${DIR} — the glob is broken, not the designs`);
  assert.ok(DESIGN_CSS.size >= 100,
    `parsed only ${DESIGN_CSS.size} .mw-* selectors from mass-weed.css — the parser is broken`);
});

test('no mockup uses a .mw-* class that nothing styles', () => {
  const offenders = [];
  for (const [file, missing] of unstyledByFile()) {
    const fresh = missing.filter((c) => !KNOWN_UNSTYLED.has(c));
    if (fresh.length) offenders.push(`${file}: ${fresh.join(', ')}`);
  }
  assert.deepEqual(offenders, [],
    'these classes appear in mockup markup but are styled neither in ' +
    'design/mass-weed-mockup/mass-weed.css nor in the page\'s own <style>, so those ' +
    'elements render as bare unstyled divs — nothing errors and nothing logs:\n  ' +
    offenders.join('\n  '));
});

test('KNOWN_UNSTYLED carries no stale entries', () => {
  // An allow-list that outlives its problem is worse than no allow-list: it
  // keeps asserting a gap that is closed, and the next real gap gets waved
  // through by whoever assumes the list is already out of date.
  const stillMissing = new Set([...unstyledByFile().values()].flat());
  const stale = [...KNOWN_UNSTYLED].filter((c) => !stillMissing.has(c)).sort();
  assert.deepEqual(stale, [],
    `these are styled now (or no longer used) — delete them from KNOWN_UNSTYLED: ${stale.join(', ')}`);
});

test('every mockup that uses the design system also links it', () => {
  // A mockup that uses .mw-* classes but forgets the <link> renders entirely
  // unstyled — obvious on screen, easy to ship when a file is added by
  // copy-paste, and invisible to every other test here.
  //
  // The condition is "uses the system", not "is a mockup". report-standalone.html
  // links nothing ON PURPOSE — it is the offline artifact the owner opens on a
  // train with no network, so its design notes require zero network requests and
  // one inline <style>. It uses no .mw-* class either, so it depends on nothing
  // this file checks. Keying the exemption to actual usage rather than to that
  // filename means the next deliberately self-contained page needs no edit here,
  // while a page that starts using .mw-* classes is caught the moment it does.
  const orphans = MOCKUPS.filter((name) => {
    const html = fs.readFileSync(path.join(DIR, name), 'utf8');
    if (classesUsedIn(html).size === 0) return false;
    return !/<link[^>]+href="mass-weed\.css"/.test(html);
  });
  assert.deepEqual(orphans, [],
    `these mockups use .mw-* classes but never link mass-weed.css, so they render ` +
    `entirely unstyled: ${orphans.join(', ')}`);
});
