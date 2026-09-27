'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/api.js — small mechanical fixes pinned individually since they
   don't share a theme with api-token-race.test.js (the existing api.js
   test file, scoped to the 401/stale-token race).

   1. notifDigest's parameter used to be named `window`, shadowing the
      global for the whole function body. Harmless today (the body never
      needed the real `window`), but a trap for the next edit that does —
      pin the observable behaviour (query string built from the arg, default
      'daily') survives the rename to `win`.
   2. The legacy qms-api wrapper methods (qmsStats/qmsDocuments/qmsDocument/
      qmsHierarchy/qmsFamilies/qmsRagQuery/qmsDownloadUrl) that api.js's own
      comment says were retired must actually be gone, not just documented
      as gone — guards against them quietly coming back.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// api.js is self-contained (see api-token-race.test.js's own note on this).
function load() {
  return loadGF({ files: ['api.js'] });
}

test('notifDigest builds the digest URL from its argument, defaulting to "daily"', async () => {
  const h = load();
  const w = h.window;
  const calls = [];
  w.fetch = async (url, opts) => { calls.push(url); return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({}) }; };

  await w.GF.API.notifDigest('weekly');
  assert.equal(calls[0], '/notifications/digest?window=weekly');

  await w.GF.API.notifDigest();
  assert.equal(calls[1], '/notifications/digest?window=daily');

  await w.GF.API.notifDigest('');
  assert.equal(calls[2], '/notifications/digest?window=daily',
    'an empty string must fall back to daily, same as before the rename');
  h.close();
});

test('the retired qms-api legacy wrapper methods do not exist on GF.API', () => {
  const h = load();
  const w = h.window;
  for (const name of ['qmsStats', 'qmsDocuments', 'qmsDocument', 'qmsHierarchy',
                       'qmsFamilies', 'qmsRagQuery', 'qmsDownloadUrl']) {
    assert.equal(w.GF.API[name], undefined, `GF.API.${name} should not exist — qms-api was retired`);
  }
  // The successor (QMS Studio / DocEngine) is present in its place.
  assert.equal(typeof w.GF.API.studioDocuments, 'function');
  h.close();
});

/* ── _reqFull keeps the response headers; auditPage reads X-Next-Cursor ──
   The audit trail pages with a server cursor carried in a response HEADER
   (backend/app/api/audit.py). _req returns the body only, so no wrapper
   could read it; _reqFull is the same request with the headers kept
   (review 2026-09-27, R2-BC-02 / A-7).
   ──────────────────────────────────────────────────────────────────────── */

function jsonResponse(w, body, headers) {
  const h = new w.Headers(Object.assign({ 'content-type': 'application/json' }, headers || {}));
  return { ok: true, status: 200, headers: h, json: async () => body, text: async () => JSON.stringify(body) };
}

test('_reqFull returns { data, headers, status } and _req is its body', async () => {
  const h = load();
  const w = h.window;
  w.GF.API.token = 'tok';
  w.fetch = async () => jsonResponse(w, { a: 1 }, { 'X-Next-Cursor': 'abc' });
  const full = await w.GF.API._reqFull('GET', '/x');
  assert.deepEqual(JSON.parse(JSON.stringify(full.data)), { a: 1 });
  assert.equal(full.status, 200);
  assert.equal(full.headers.get('X-Next-Cursor'), 'abc');
  const body = await w.GF.API._req('GET', '/x');
  assert.deepEqual(JSON.parse(JSON.stringify(body)), { a: 1 });
  h.close();
});

test('auditPage sends the query as-is and maps X-Next-Cursor to `next`', async () => {
  const h = load();
  const w = h.window;
  w.GF.API.token = 'tok';
  const urls = [];
  w.fetch = async (url) => { urls.push(url); return jsonResponse(w, [{ id: 1 }], { 'X-Next-Cursor': 'cur-1' }); };
  const page = await w.GF.API.auditPage({ limit: 100, cursor: 'cur-0', source: 'tasks' });
  assert.equal(urls[0], '/audit?limit=100&cursor=cur-0&source=tasks');
  assert.equal(page.next, 'cur-1');
  assert.equal(page.rows.length, 1);

  w.fetch = async () => jsonResponse(w, []);
  const last = await w.GF.API.auditPage({});
  assert.equal(last.next, null, 'no header → null, never the string "null"');
  assert.equal(typeof w.GF.API.audit, 'undefined', 'the body-only audit() wrapper is gone with the `before` paging');
  h.close();
});

/* ── Wrapper inventory (review 2026-09-27, INV-05 / INV-06 / FE-22) ──────
   The wrappers with no caller are gone; the routes the other views wire this
   round have theirs; qcProductLadderCreate stays for the catalogue screen.
   ──────────────────────────────────────────────────────────────────────── */

test('the dead QC / cultivation wrappers are gone and the requested ones exist', () => {
  const h = load();
  const api = h.window.GF.API;
  for (const name of ['qcCreatePotencySpec', 'qcApprovePotencySpec', 'qcSupersedePotencySpec',
                      'qcPotencyDisposition', 'qcProductCreate', 'qcProductPatch', 'qcProductPotency',
                      'qcCommercialIdentities', 'qcImportCommercial', 'campaignPatch', 'audit']) {
    assert.equal(api[name], undefined, `GF.API.${name} has no caller and should not exist`);
  }
  for (const name of ['trichomeCheckPatch', 'qcCoqSign', 'qcCoqSignatures', 'departmentPatch',
                      'qcProductLadderCreate', 'trichomeChecks', 'qcSignatures', 'auditPage', 'cultivationBatchCode']) {
    assert.equal(typeof api[name], 'function', `GF.API.${name} is expected`);
  }
  h.close();
});

test('the new wrappers hit the routes they are named for, with the body unchanged', async () => {
  const h = load();
  const w = h.window;
  w.GF.API.token = 'tok';
  const calls = [];
  w.fetch = async (url, opts) => { calls.push([opts.method, url, opts.body]); return jsonResponse(w, {}); };
  await w.GF.API.trichomeCheckPatch('tc1', { verdict: 'mostly_cloudy', reason: 'typo' });
  await w.GF.API.qcCoqSign('q1', { meaning: 'approved', password: 'x' });
  await w.GF.API.qcCoqSignatures('q1');
  await w.GF.API.departmentPatch('d1', { head_user_id: 'u9' });
  await w.GF.API.departmentPatch('d1', { head_user_id: null });
  await w.GF.API.cultivationBatchCode('cv1', { clone_date: '2026-07-25' });
  await w.GF.API.cultivationBatchCode('cv1');
  assert.deepEqual(calls, [
    ['PATCH', '/cultivation/trichome-checks/tc1', JSON.stringify({ verdict: 'mostly_cloudy', reason: 'typo' })],
    ['POST', '/qc/coq/q1/sign', JSON.stringify({ meaning: 'approved', password: 'x' })],
    ['GET', '/qc/coq/q1/signatures', undefined],
    ['PATCH', '/departments/d1', JSON.stringify({ head_user_id: 'u9' })],
    ['PATCH', '/departments/d1', JSON.stringify({ head_user_id: null })],
    ['GET', '/cultivation/batch-code?cultivar_id=cv1&clone_date=2026-07-25', undefined],
    ['GET', '/cultivation/batch-code?cultivar_id=cv1', undefined],
  ]);
  h.close();
});

test('the custody wrapper sends the body the view gives it, unchanged (R2-FE-05: the server rule wins)', async () => {
  const h = load();
  const w = h.window;
  w.GF.API.token = 'tok';
  let sent = null;
  w.fetch = async (url, opts) => { sent = [url, opts.body]; return jsonResponse(w, {}); };
  const body = { from_location: 'Sampling bench', from_user_id: 'S', to_user_id: 'L', note: 'hop 2' };
  await w.GF.API.qcAddCustody('s1', body);
  assert.deepEqual(sent, ['/qc/samples/s1/custody', JSON.stringify(body)]);
  h.close();
});
