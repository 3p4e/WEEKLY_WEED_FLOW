'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/api.js — every request carries a deadline.

   Before this, _req() called bare fetch(): a backend that accepted the
   connection and then never answered left the await pending forever. The
   caller's spinner never cleared and its `finally` never ran, so the only
   thing standing between the user and a permanently stuck screen was
   GF.once()'s per-button guard — which prevents a SECOND click; it does
   nothing for the first one that hung.

   Two properties matter and both are pinned here: a request that outlives its
   deadline REJECTS (rather than hanging), and the AI/long-build routes get a
   deadline longer than the backend's own upstream timeout — aborting before
   the server gives up would replace a real error message with silence.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

function load() {
  return loadGF({ files: ['api.js'] });
}

test('a request that never answers rejects on its deadline instead of hanging', async () => {
  const h = load();
  const w = h.window;
  w.GF.API.token = 'tok';

  // A backend that accepts the request and then goes silent: this fetch only
  // ever settles by way of the abort signal.
  w.fetch = (url, opts) => new Promise((_resolve, reject) => {
    opts.signal.addEventListener('abort', () => {
      const e = new Error('aborted');
      e.name = 'AbortError';
      reject(e);
    });
  });

  const err = await w.GF.API._req('GET', '/tasks', null, 20).then(
    () => { throw new Error('the request resolved — it must reject on its deadline'); },
    (e) => e,
  );
  assert.equal(err.timeout, true);
  assert.equal(err.status, 0, 'no HTTP status: nothing came back');
  assert.match(err.message, /did not respond in time/i);
});

test('a network failure is reported as unreachable, NOT as a timeout', async () => {
  const h = load();
  const w = h.window;
  w.fetch = () => Promise.reject(new TypeError('Failed to fetch'));

  const err = await w.GF.API._req('GET', '/tasks').then(
    () => { throw new Error('must reject'); },
    (e) => e,
  );
  // The two need different things from the user — retry now vs check the
  // connection — so they must not collapse into one opaque message.
  assert.equal(err.timeout, false);
  assert.equal(err.status, 0);
  assert.match(err.message, /could not reach the server/i);
});

test('the long-running agent routes get the deadline nginx gives them, and no other route does', () => {
  const h = load();
  const api = h.window.GF.API;

  // These four are exactly the paths web/nginx.conf reads for 180s (the
  // DocEngine agent block + /intake). The client must outlast the proxy so the
  // proxy's 504 is what the user sees.
  for (const path of [
    '/qms/studio/workflows/abc-123/chat',
    '/qms/studio/workflows/abc-123/revise',
    '/qms/studio/build',
    '/qms/rag-query',
    '/intake/bilingual',
  ]) {
    assert.equal(api._timeoutFor(path), api._SLOW_TIMEOUT_MS, path + ' must get the slow-route deadline');
  }

  // Everything else — including /ai, which nginx reads for 60s and whose own
  // backend timeout is 15s — takes the ordinary deadline.
  for (const path of ['/tasks', '/auth/me', '/ai/summarise',
                      '/qms/studio/workflows/abc-123', '/qms/studio/documents']) {
    assert.equal(api._timeoutFor(path), api._TIMEOUT_MS, path + ' must get the ordinary deadline');
  }
});

test('every client deadline sits PAST the nginx read timeout it pairs with', () => {
  // The ordering is the invariant, not the numbers: whichever hop gives up
  // first writes the error the user sees, and nginx's 504 carries a reason
  // while a client abort cannot. Read the real nginx.conf so the two files
  // cannot drift apart silently.
  const fs = require('node:fs');
  const path = require('node:path');
  const conf = fs.readFileSync(
    path.join(__dirname, '..', '..', 'web', 'nginx.conf'), 'utf8');
  const timeouts = [...conf.matchAll(/proxy_read_timeout\s+(\d+)s/g)].map((m) => Number(m[1]));
  assert.ok(timeouts.length >= 3, 'expected the API proxy blocks to declare read timeouts');

  const h = load();
  const api = h.window.GF.API;
  assert.ok(api._TIMEOUT_MS > Math.min(...timeouts) * 1000,
    'the ordinary deadline must outlast the general 60s proxy block');
  assert.ok(api._SLOW_TIMEOUT_MS > Math.max(...timeouts) * 1000,
    'the slow deadline must outlast the 180s agent-route proxy block');
});

test('a successful response clears its timer — no stray abort after the fact', async () => {
  const h = load();
  const w = h.window;
  let aborted = false;

  w.fetch = (url, opts) => {
    opts.signal.addEventListener('abort', () => { aborted = true; });
    return Promise.resolve({
      status: 200, ok: true,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ ok: true }),
    });
  };

  const out = await w.GF.API._req('GET', '/tasks', null, 15);
  assert.deepEqual(out, { ok: true });
  await new Promise((r) => setTimeout(r, 40));   // past the deadline it would have had
  assert.equal(aborted, false, 'the timer must be cleared once the response lands');
});
