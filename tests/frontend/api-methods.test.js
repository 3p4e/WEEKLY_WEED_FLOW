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
