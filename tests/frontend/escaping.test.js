'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/core.js — GF.esc, GF.kpiTile   |   web/gf/render.js — GF.avatar

   GF.esc is the app's ONLY output encoder. Every one of the ~60 view files
   builds markup by string concatenation and assigns it to .innerHTML, so
   GF.esc is the whole XSS boundary for task titles, department names, person
   names, notes and reference codes — all operator-supplied. It had no test.

   The two markup helpers below are included because their own source comments
   record that escaping bugs have already happened here ("exactly how the
   escaping bugs in the last round happened"), which makes them the places a
   regression is most likely to recur.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

test('GF.esc encodes all five HTML-significant characters', () => {
  const h = loadGF();
  const esc = h.GF.esc;
  assert.equal(esc('&'), '&amp;');
  assert.equal(esc('<'), '&lt;');
  assert.equal(esc('>'), '&gt;');
  assert.equal(esc('"'), '&quot;');
  assert.equal(esc("'"), '&#39;');
  h.close();
});

test('GF.esc replaces & FIRST, so entities are not double-escaped into working markup', () => {
  const h = loadGF();
  // If & were replaced last, esc('<') would produce '&lt;' and then the
  // ampersand pass would leave it as '&lt;' too — but esc('&lt;') would come
  // out as '&lt;' (a live tag delimiter) instead of the inert '&amp;lt;'.
  assert.equal(h.GF.esc('&lt;script&gt;'), '&amp;lt;script&amp;gt;');
  assert.equal(h.GF.esc('&amp;'), '&amp;amp;');
  h.close();
});

test('GF.esc neutralises the payloads that actually reach innerHTML', () => {
  const h = loadGF();
  const esc = h.GF.esc;
  // Element-content injection.
  assert.equal(esc('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;');
  assert.equal(esc('</span><script>alert(1)</script>'),
    '&lt;/span&gt;&lt;script&gt;alert(1)&lt;/script&gt;');
  // Attribute-value breakout. The views interpolate esc() output into both
  // double-quoted (title="…") and single-quoted (onclick='…') attributes, so
  // BOTH quote characters have to be encoded — encoding only " would leave
  // every single-quoted attribute in the codebase injectable.
  assert.equal(esc('" onmouseover="alert(1)'), '&quot; onmouseover=&quot;alert(1)');
  assert.equal(esc("' onmouseover='alert(1)"), '&#39; onmouseover=&#39;alert(1)');
  h.close();
});

test('GF.esc coerces null and undefined to empty string but keeps a literal 0', () => {
  const h = loadGF();
  const esc = h.GF.esc;
  // The guard is `s == null ? '' : s`, NOT `s || ''`. That distinction is the
  // reason a 0 count renders as "0" and not as a blank cell — and it is the
  // opposite choice from export.js's own esc(), which does use `s || ''`.
  assert.equal(esc(null), '');
  assert.equal(esc(undefined), '');
  assert.equal(esc(0), '0');
  assert.equal(esc(false), 'false');
  assert.equal(esc(''), '');
  h.close();
});

test('GF.esc leaves ordinary text — including Cyrillic — byte-identical', () => {
  const h = loadGF();
  // The UI is bilingual EN/MK; an encoder that mangled non-ASCII would break
  // every Macedonian label in the app.
  for (const s of ['Harvest room 3', 'Контрола на квалитет', 'pH 5.8–6.2', 'SOP-QC-014']) {
    assert.equal(h.GF.esc(s), s);
  }
  h.close();
});

test('GF.kpiTile escapes its label, value and sub-line', () => {
  const h = loadGF();
  // core.js states this helper was made escaping "to close the trap for the
  // next caller that passes a task title or a department name". That is the
  // whole point of the change, so it gets a test.
  const html = h.GF.kpiTile('<b>Done</b>', '<i>7</i>', '"x"');
  assert.equal(html.includes('<b>'), false);
  assert.equal(html.includes('<i>'), false);
  assert.equal(html.includes('&lt;b&gt;Done&lt;/b&gt;'), true);
  assert.equal(html.includes('&lt;i&gt;7&lt;/i&gt;'), true);
  assert.equal(html.includes('&quot;x&quot;'), true);
  h.close();
});

test('GF.kpiTile omits the sub-line element entirely when no sub is given', () => {
  const h = loadGF();
  assert.equal(h.GF.kpiTile('Total', 12).includes('ana-ts'), false);
  assert.equal(h.GF.kpiTile('Total', 12, '3 overdue').includes('ana-ts'), true);
  h.close();
});

test('GF.avatar escapes the person name and initials it interpolates', () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'render.js'] });
  // name lands in a title="…" attribute and init in element content; both come
  // from the team roster, which an admin edits as free text.
  h.GF.PEOPLE.x = { name: '" onload="alert(1)', init: '<b>', bg: '#2BE8A0' };
  const html = h.GF.avatar('x');
  assert.equal(html.includes('onload="alert(1)"'), false);
  assert.equal(html.includes('title="&quot; onload=&quot;alert(1)"'), true);
  assert.equal(html.includes('&lt;b&gt;'), true);
  h.close();
});

test('GF.avatar falls back to a placeholder for an unknown person id', () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'render.js'] });
  // GF.PEOPLE starts empty (integrate.js fills it from the roster after login),
  // so every avatar renders through this branch on a cold start.
  const html = h.GF.avatar('not-a-person');
  assert.equal(html.includes('>?</div>'), true);
  assert.equal(html.includes('title=""'), true);
  h.close();
});

test('GF.esc is reachable as a bare global and AL is shared across script files', () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'render.js'] });
  // core.js declares `const AL` at top level, bare, and documents that every
  // classic <script> loaded afterwards calls it unqualified. That contract is
  // invisible to any test that only pokes at window.GF, and it is the single
  // assumption the whole no-build loading model rests on — if a future edit
  // wrapped a file in an IIFE or added "use strict"-module semantics, ~40 view
  // files would break at runtime and nothing else here would notice.
  assert.equal(h.global('typeof AL'), 'function');
  assert.equal(h.global('AL("english", "македонски")'), 'english');
  h.global('GF.state.lang = "mk"');
  assert.equal(h.global('AL("english", "македонски")'), 'македонски');
  h.close();
});
