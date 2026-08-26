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
