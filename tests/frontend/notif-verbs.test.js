'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/notifications-view.js — every verb the backend emits has a
   sentence, and no sentence prints "undefined" for the params the backend
   actually sends (review 2026-09-27, R2-FE-04 / INV-02 / INV-03 / INV-04).

   The first test is a SOURCE scan: it collects every `verb="…"` literal
   under backend/app (plus the dynamic workflow_* family and the due-scan
   pair) and asserts a `case '<verb>'` exists in the sentence switch — the
   contract the file's own header states. The rest render the real view.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF, GF_DIR } = require('./helpers/gf-window.js');

const BACKEND = path.resolve(GF_DIR, '..', '..', 'backend', 'app');
const VIEW_SRC = fs.readFileSync(path.join(GF_DIR, 'notifications-view.js'), 'utf8');

function pyFiles(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) pyFiles(p, out);
    else if (e.name.endsWith('.py')) out.push(p);
  }
  return out;
}

function emittedVerbs() {
  const verbs = new Set();
  for (const f of pyFiles(BACKEND)) {
    const src = fs.readFileSync(f, 'utf8');
    for (const m of src.matchAll(/verb="([a-z_]+)"/g)) verbs.add(m[1]);
  }
  // Dynamic emitters: tasks.py's f"workflow_{action}" and duescan.py.
  verbs.delete('workflow_');
  ['workflow_submit', 'workflow_approve', 'workflow_reject', 'workflow_block', 'workflow_unblock',
   'due_soon', 'overdue'].forEach(v => verbs.add(v));
  return [...verbs].sort();
}

test('every verb the backend emits has its own case in the sentence switch (no generic fallback in use)', () => {
  const verbs = emittedVerbs();
  assert.ok(verbs.length > 60, `expected the full emitter set, found ${verbs.length}`);
  const missing = verbs.filter(v => !VIEW_SRC.includes(`case '${v}':`));
  assert.deepEqual(missing, [], 'verbs with no sentence: ' + missing.join(', '));
});

test('no case label is shadowed by an earlier one (JavaScript takes the first)', () => {
  const labels = [...VIEW_SRC.matchAll(/case '([a-z_]+)':/g)].map(m => m[1]);
  const dup = labels.filter((v, i) => labels.indexOf(v) !== i);
  assert.deepEqual(dup, [], 'duplicate case labels: ' + dup.join(', '));
});

// ── rendering with the backend's real param shapes ─────────────────────

const PRE = `
  window.setInterval = function () { return 0; };
  window.setTimeout = function () { return 0; };
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.icon = function () { return ''; };
  window.GF.avatar = function () { return ''; };
  window.GF.API = { token: 'tok', user: { id: 'me', role: 'PR_MGR', facility_tz: 'Europe/Skopje' } };
  window.GF.render = { all: function () {}, sidebar: function () {} };
  window.GF.viewHead = function () { return ''; };
`;

function render(items, { lang, tab } = {}) {
  const h = loadGF({ files: ['data.js', 'core.js', 'notifications-view.js'], preScript: PRE,
                     storage: lang ? { gf_lang: lang } : {} });
  const w = h.window;
  w.GF.state.user = 'me';
  w.GF.PEOPLE = { ana: { name: 'Ana' } };
  const st = w.GF.WWF._notif;
  st.loaded = true; st.user = 'me';
  const rows = items.map((n, i) => ({ id: 'n' + i, reason: 'status', read: true, actor_id: 'ana',
                                      created_at: '2026-07-30T07:00:00Z', ...n }));
  if (tab === 'feed') { st.tab = 'feed'; st.feed = rows; st.items = []; }
  else st.items = rows;
  const html = w.GF.views.inbox();
  h.close();
  return html;
}

// The coordinator's contract for cultivation.py: what the backend emits now.
const ADDED_NEW  = { code: 'GP072501', strain: 'Gorilla Punch', room: 'Flowering 1.1', plant_count: 2000, phase: 'clone' };
const MOVED_NEW  = { code: 'GP072501', strain: 'Gorilla Punch', room: 'Flowering 1.2', plant_count: 2000, phase: 'veg',
                     old_room: 'Flowering 1.1', old_phase: 'clone' };
// What the backend emitted before the contract (events already stored).
const ADDED_OLD  = { code: 'GP072501', cultivar: 'GP', plant_count: 2000, phase: 'clone', product_code: 'GP_THC26' };
const MOVED_OLD  = { code: 'GP072501', old_phase: 'clone', phase: 'veg', room_change: false, generated_tasks: 4 };

for (const lang of ['en', 'mk']) {
  test(`batch_added / batch_moved never print "undefined" in ${lang}, for either param shape`, () => {
    const html = render([
      { verb: 'batch_added', params: ADDED_NEW }, { verb: 'batch_moved', params: MOVED_NEW },
      { verb: 'batch_added', params: ADDED_OLD }, { verb: 'batch_moved', params: MOVED_OLD },
      { verb: 'batch_added', params: {} }, { verb: 'batch_moved', params: {} },
    ], { lang });
    assert.doesNotMatch(html, /undefined/);
    assert.doesNotMatch(html, /\bnull\b/);
    assert.match(html, /GP072501 — 2000 × Gorilla Punch/);
    assert.match(html, /Flowering 1\.1 \(clone\) → Flowering 1\.2 \(veg\)/);
    assert.match(html, /GP072501 — 2000 × GP/, 'the old shape falls back to `cultivar`');
    assert.match(html, /: clone → veg/, 'a phase-only move prints the phases alone');
  });
}

test('a room change (the phase clock kept, CS-06) reads as a room change, not as "flower → flower"', () => {
  const html = render([{ verb: 'batch_moved', params: { code: 'GP072501', strain: 'Gorilla Punch', plant_count: 2000,
    phase: 'flower', old_phase: 'flower', room: 'Flowering 1.2', old_room: 'Flowering 1.1', room_change: true } }]);
  assert.match(html, /changed room for GP072501 — 2000 × Gorilla Punch: Flowering 1\.1 → Flowering 1\.2 \(flower\)/);
  assert.doesNotMatch(html, /flower\) → /);
  const mk = render([{ verb: 'batch_moved', params: { code: 'GP072501', strain: 'GP', room: 'B', old_room: 'A', room_change: true } }], { lang: 'mk' });
  assert.match(mk, /друга просторија/);
});

test('the contract keys win over the fallbacks when both are present', () => {
  const html = render([{ verb: 'batch_added', params: { ...ADDED_NEW, cultivar: 'GP', room_name: 'other' } }]);
  assert.match(html, /Gorilla Punch/);
  assert.match(html, /in Flowering 1\.1/);
  assert.doesNotMatch(html, /× GP\b/);
});

test('product_approved shows the cultivar and the document version (the shadowed richer case)', () => {
  const html = render([{ verb: 'product_approved', params: { product_code: 'GP_THC26:CBD1', cultivar: 'GP', doc_version: 'v.03' } }]);
  assert.match(html, /approved product GP_THC26:CBD1 \(GP, v\.03\)/);
  assert.match(render([{ verb: 'product_created', params: { product_code: 'GP_THC26', cultivar: 'GP' } }]), /authored product GP_THC26 \(GP\)/);
});

// The five verbs that used to fall to the generic line, with the exact
// params their emitters send (signatures.py, commercial.py, potency_import.py,
// facility_layout.py).
const FIVE = [
  ['coq_signed', { meaning: 'approved' }, /signed a certificate of quality \(approved\)/],
  ['commercial_identity_upserted', { batch_code: 'GP072501', neu_name: 'Gorilla Punch THC 26' }, /commercial identity of GP072501: Gorilla Punch THC 26/],
  ['portfolio_master_imported', { imported: 12 }, /portfolio master: 12 commercial identities/],
  ['potency_catalogue_imported', { version: '1.4', family: 'THC', created: 5, skipped: 1, conflicts: 0 }, /THC potency ladders v1\.4: 5 created, 1 skipped, 0 conflicts/],
  ['facility_layout_imported', { created: 12, updated: 3, source: 'Layout Full.pdf' }, /facility layout from Layout Full\.pdf: 12 rooms created, 3 updated/],
];
for (const [verb, params, re] of FIVE) {
  test(`${verb} renders a real sentence in both languages, never the generic "actor · words" line`, () => {
    const en = render([{ verb, params }]);
    assert.match(en, re);
    assert.doesNotMatch(en, /undefined/);
    assert.doesNotMatch(en, new RegExp('Ana · ' + verb.replace(/_/g, ' ')), 'must not fall to the generic line');
    const mk = render([{ verb, params }], { lang: 'mk' });
    assert.doesNotMatch(mk, /undefined/);
    assert.notEqual(mk, en, 'the Macedonian sentence differs from the English one');
  });
}

test('an acknowledgement gets the green feed dot (the verb is `ack`, not `acknowledged`)', () => {
  const html = render([{ verb: 'ack', params: { title: 'Cut GP', accepted: true } }], { tab: 'feed' });
  assert.match(html, /ntf-fdot ok/);
});
