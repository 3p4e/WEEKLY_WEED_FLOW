'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/document-view.js — out-of-order write responses on the document
   panel must not clobber newer state.

   loadDocument has always captured a sequence number BEFORE its request and
   checked it AFTER, before applying the response, so a stale load can never
   overwrite a newer one. The four WRITE paths — compileDocument,
   previewDocument, saveDocSection, lockDocument — only bumped the sequence
   AFTER a successful response. That stops them from being overwritten by
   something OLDER, but never checks whether THEY were superseded by
   something that started after them and resolved first.

   Concretely: a reviewer saves section A, then quickly saves section B
   before A's response returns. If A's response arrives after B's,
   saveDocSection's unconditional `ds.data = data` used to overwrite B's
   just-adopted, correctly-saved server state with A's older copy.

   A second, related bug: the approve checkbox's onchange calls
   saveDocSection directly, bypassing _collectDocInputs — so _applyDocInputs
   (which reapplies unsaved edits from OTHER sections after a re-render)
   never carried the approved flag. A pending approval could visibly (though
   never durably — the PATCH itself still lands) revert to unchecked if
   another section's save resolved and re-rendered the panel first.

   Both are reproduced here with hand-controlled promise resolution — the
   same out-of-order-arrival pattern harvest-view.test.js uses for
   harvestClearanceCheck's own sequence guard.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const FILES = ['data.js', 'core.js', 'document-view.js'];

// document-view.js sits after integrate.js in index.html and reads its bare
// top-level ELEVATED_ROLES to decide whether Compile/Save/Lock controls
// render. Declared here the same way worklog-form.test.js declares
// AUDIT_ROLES, rather than loading the whole app for one constant.
// GF.selectField (views.js) is stubbed for the same reason — it backs the
// department picker shown to elevated roles, which these tests never assert
// on.
const PRE = `
  const ELEVATED_ROLES = ['ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR','SE_MGR','CU_MGR','MU_MGR','QP'];
  window.GF = window.GF || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.selectField = function () { return ''; };
`;

function baseDoc() {
  return {
    id: 'doc1',
    status: 'draft',
    kind: 'report',
    week_start: '2026-07-27',
    content: {
      ai_sections: [
        { key: 'A', title: 'Section A', body_en: 'a-orig', body_mk: '', approved: false },
        { key: 'B', title: 'Section B', body_en: 'b-orig', body_mk: '', approved: false },
      ],
      template_sections: [],
      tasks: [],
      ribbon: [],
    },
  };
}

function open() {
  const h = loadGF({ files: FILES, preScript: PRE, bodyHtml: '<div id="report-doc"></div>' });
  const { GF } = h;
  GF.WWF._report = { mode: 'report', refDate: '' };
  GF.API = Object.assign(GF.API || {}, { user: { id: 'U-1', role: 'ADMIN' } });
  return h;
}

test('a slower-resolving section save does not clobber a faster one’s already-applied state', async () => {
  const h = open();
  const { GF } = h;
  GF.WWF._doc.data = baseDoc();
  GF.WWF._renderDocPanel();

  const pending = {};
  GF.API.patchDocumentSection = (_docId, key) => new Promise((resolve) => { pending[key] = resolve; });

  // A is clicked first (lower seq)...
  const pA = GF.WWF.saveDocSection('A');
  await Promise.resolve();
  assert.ok(pending.A, 'A’s save must be in flight');

  // ...then B is clicked before A’s response returns (higher seq — B is the
  // more recent action).
  const pB = GF.WWF.saveDocSection('B');
  await Promise.resolve();
  assert.ok(pending.B, 'B’s save must be in flight');

  // B — the LATER click — resolves FIRST and is adopted immediately.
  const docAfterB = baseDoc();
  docAfterB.content.ai_sections[1].body_en = 'B-SAVED';
  pending.B(docAfterB);
  await pB;
  assert.equal(GF.WWF._doc.data.content.ai_sections[1].body_en, 'B-SAVED',
    'B’s own response must be applied');

  // A — the EARLIER click — resolves SECOND, carrying a server snapshot from
  // before B's save landed. Without the sequence guard this unconditionally
  // overwrote ds.data, reverting B.
  const docAfterA = baseDoc();
  docAfterA.content.ai_sections[0].body_en = 'A-SAVED';
  docAfterA.content.ai_sections[1].body_en = 'b-orig';   // stale: predates B's save
  pending.A(docAfterA);
  await pA;

  assert.equal(GF.WWF._doc.data.content.ai_sections[1].body_en, 'B-SAVED',
    'the stale, slower A response must not clobber B’s already-applied state');
  h.close();
});

test('an approved checkbox survives a re-render triggered by a concurrent section save', async () => {
  const h = open();
  const { GF, window: w } = h;
  GF.WWF._doc.data = baseDoc();
  GF.WWF._renderDocPanel();

  const cbB = w.document.querySelector('input[data-sec="B"][data-f="approved"]');
  assert.ok(cbB, 'the approve checkbox must carry data-sec/data-f so it is collected like any other field');
  assert.equal(cbB.checked, false);

  const pending = {};
  GF.API.patchDocumentSection = (_docId, key) => new Promise((resolve) => { pending[key] = resolve; });

  // The reviewer checks B's approve box. The browser flips .checked before
  // firing onchange, which calls saveDocSection directly — reproduce that
  // ordering by hand.
  cbB.checked = true;
  const pB = GF.WWF.saveDocSection('B', true);
  await Promise.resolve();
  assert.ok(pending.B, 'B’s approval PATCH must be in flight');

  // While B's approval is still in flight, the reviewer separately saves A's
  // text. saveDocSection('A') snapshots the CURRENT DOM via
  // _collectDocInputs before its own request goes out — including B's
  // now-checked box.
  const pA = GF.WWF.saveDocSection('A');
  await Promise.resolve();
  assert.ok(pending.A, 'A’s save must be in flight');

  // A resolves first, with a server snapshot that does NOT yet know about
  // B's still-in-flight approval.
  const docAfterA = baseDoc();
  docAfterA.content.ai_sections[0].body_en = 'A-SAVED';
  docAfterA.content.ai_sections[1].approved = false;   // server hasn't processed B's PATCH yet
  pending.A(docAfterA);
  await pA;

  // The re-render A's save triggers must still show B as approved — the
  // pending, not-yet-confirmed approval must survive it, the same way an
  // unsaved text edit in another section would.
  const content = GF.WWF._doc.data.content;
  assert.equal(content.ai_sections.find(s => s.key === 'B').approved, true,
    'B’s in-flight approval must survive a re-render triggered by A’s save');
  const cbB2 = w.document.querySelector('input[data-sec="B"][data-f="approved"]');
  assert.ok(cbB2, 'the panel must have re-rendered');
  assert.equal(cbB2.checked, true, 'the rendered checkbox must still show checked, not reverted');

  h.close();
});
