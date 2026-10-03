'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qmsstudio-view.js — GF.WWF._qstu 'done' step (doneStep()).

   The finished-job panel interpolates the generated document's id straight
   into two inline onclick handlers (Download DOCX / Download PDF). Every
   other occurrence of the same document_id field in this file goes through
   GF.esc (buildStep's doneStep-equivalent, and the registry-row links) —
   this one site did not, so a document id containing a quote could break
   out of the onclick attribute.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
  window.GF.render = { all: function () {} };
  window.GF.viewHead = function () { return '<head></head>'; };
  window.GF.API = { user: { role: 'ADMIN' } };
`;

function load() {
  return loadGF({ files: ['data.js', 'core.js', 'qmsstudio-view.js'], preScript: PRE });
}

// A document id shaped to break out of a single-quoted onclick="..." handler
// if interpolated raw. GF.esc turns the quote into &#39;, which HTML-decodes
// back to a literal `'` inside the attribute value — inert, not a delimiter.
const MALICIOUS_ID = `doc-1' onmouseover='alert(1)`;

test('doneStep() escapes the document id in BOTH download onclick handlers', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qstu.step = 'done';
  w.GF.WWF._qstu.job = { id: 'j1', status: 'done', result: { document_id: MALICIOUS_ID } };
  const html = w.GF.views.qmsstudio();
  assert.ok(!html.includes(`qstuDl('${MALICIOUS_ID}','docx')`),
    'the raw, unescaped id must not appear in the DOCX handler');
  assert.ok(!html.includes(`qstuDl('${MALICIOUS_ID}','pdf')`),
    'the raw, unescaped id must not appear in the PDF handler');
  assert.ok(html.includes(`qstuDl('${w.GF.esc(MALICIOUS_ID)}','docx')`),
    'the DOCX handler must use the GF.esc-escaped id');
  assert.ok(html.includes(`qstuDl('${w.GF.esc(MALICIOUS_ID)}','pdf')`),
    'the PDF handler must use the GF.esc-escaped id');
});

test('doneStep() still renders plain download links for an ordinary document id', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qstu.step = 'done';
  w.GF.WWF._qstu.job = { id: 'j1', status: 'done', result: { document_id: 'doc-42' } };
  const html = w.GF.views.qmsstudio();
  assert.ok(html.includes("qstuDl('doc-42','docx')"));
  assert.ok(html.includes("qstuDl('doc-42','pdf')"));
});


/* ── "Needs your input": the gaps the agents refused to invent ──────────────
   The engine's [NEEDS INPUT: …] contract is only half done when the marker is
   in the .docx — a marker helps whoever is already reading that page. These
   pin the other half: the list reaches the screen, it is escaped like every
   other server value, and "nothing outstanding" is stated rather than left to
   be inferred from an empty panel. */

test('the open questions from the engine are listed with their sections', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qstu.step = 'done';
  w.GF.WWF._qstu.job = { id: 'j1', status: 'done', result: {
    document_id: 'doc-42',
    needs_input: [
      { section: '4.0', item: 'cold room code' },
      { section: '6.0', item: 'incubation temperature' },
    ],
  } };
  const html = w.GF.views.qmsstudio();
  assert.match(html, /Needs your input/);
  assert.ok(html.includes('cold room code'), 'the first question must be shown');
  assert.ok(html.includes('incubation temperature'), 'the second question must be shown');
  assert.ok(html.includes('4.0') && html.includes('6.0'), 'each question names its section');
});

test('a needs-input item is escaped — it is server text, not markup', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qstu.step = 'done';
  w.GF.WWF._qstu.job = { id: 'j1', status: 'done', result: {
    document_id: 'doc-42',
    needs_input: [{ section: '<img src=x onerror=alert(1)>', item: '</div><script>alert(1)</script>' }],
  } };
  const html = w.GF.views.qmsstudio();
  assert.ok(!html.includes('<script>alert(1)</script>'), 'raw markup must not reach the page');
  assert.ok(!html.includes('<img src=x onerror=alert(1)>'), 'raw markup must not reach the page');
  assert.ok(html.includes(w.GF.esc('</div><script>alert(1)</script>')));
});

test('an empty list says so, rather than leaving the reader to infer it', () => {
  const h = load();
  const w = h.window;
  w.GF.WWF._qstu.step = 'done';
  w.GF.WWF._qstu.job = { id: 'j1', status: 'done', result: { document_id: 'doc-42', needs_input: [] } };
  assert.match(w.GF.views.qmsstudio(), /Nothing outstanding/);
});

test('a job built before this feature claims nothing either way', () => {
  // No needs_input key at all: the engine never looked, so neither
  // "outstanding" nor "nothing outstanding" would be an honest thing to print.
  const h = load();
  const w = h.window;
  w.GF.WWF._qstu.step = 'done';
  w.GF.WWF._qstu.job = { id: 'j1', status: 'done', result: { document_id: 'doc-42' } };
  const html = w.GF.views.qmsstudio();
  assert.ok(!/Needs your input/.test(html));
  assert.ok(!/Nothing outstanding/.test(html));
});
