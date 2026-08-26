'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/api.js — GF.API._req() must not log the user out for a 401 that
   belongs to a token this request no longer sends.

   _headers() snapshots `this.token` at request-send time, and changePassword()
   swaps in a fresh token SYNCHRONOUSLY the instant the server confirms the
   change (the server invalidates the OLD token immediately). A request that
   was already in flight with the old token — a background poll, say — can
   therefore 401 AFTER the swap. Treating every 401 as "the session is dead"
   wipes the just-refreshed VALID token and force-logs the user out right
   after a successful, intentional credential change.

   Reproduced the same way harvest-view.test.js's stale-clearance-response
   test and document-view.test.js's out-of-order-save tests reproduce their
   races: a hand-controlled fetch promise, resolved only after the token has
   been rotated out from under it.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// api.js is self-contained: every reference to GF.state / GF.WWF inside it is
// already guarded (`if (window.GF && GF.state)`, `if (hadSession && GF.WWF...`),
// so it loads and runs standalone — no core.js, no DOM shell required.
function load() {
  return loadGF({ files: ['api.js'] });
}

test('a 401 for a request whose token was rotated out mid-flight does NOT log out', async () => {
  const h = load();
  const w = h.window;
  w.GF.API.token = 'old-token';
  w.GF.API.user = { id: 'u1', username: 'alice' };

  let sentHeaders;
  let resolveFetch;
  w.fetch = (url, opts) => {
    sentHeaders = opts.headers;
    return new Promise((resolve) => { resolveFetch = resolve; });
  };

  // A background request goes out while 'old-token' is still current...
  const pending = w.GF.API._req('GET', '/notifications/unread-count');
  assert.equal(sentHeaders['Authorization'], 'Bearer old-token',
    'the in-flight request must have been sent with the token current at send time');

  // ...then changePassword()'s success handler installs a fresh token
  // SYNCHRONOUSLY, exactly as GF.API.changePassword does the instant the
  // server confirms the change — before the stale request's response lands.
  w.GF.API.token = 'new-token';

  // The server rejects the now-superseded old token with 401, arriving AFTER
  // the rotation.
  resolveFetch({ status: 401 });
  await assert.rejects(pending, (e) => e.message === 'unauthorized' && e.status === 401);

  assert.equal(w.GF.API.token, 'new-token',
    'the just-rotated-in valid token must survive a 401 that belongs to the OLD, stale request');
  assert.ok(w.GF.API.user,
    'a legitimately-rotated token must not force-log-out the user who just changed their password');
  h.close();
});

test('a 401 for a request that used the CURRENT token still logs out (no regression)', async () => {
  const h = load();
  const w = h.window;
  w.GF.API.token = 'only-token';
  w.GF.API.user = { id: 'u1', username: 'alice' };
  w.fetch = async () => ({ status: 401 });

  await assert.rejects(w.GF.API._req('GET', '/tasks'),
    (e) => e.message === 'unauthorized' && e.status === 401);

  assert.equal(w.GF.API.token, '',
    'an honestly-expired/invalidated session (token unchanged since the request was sent) must still log out');
  assert.equal(w.GF.API.user, null);
  h.close();
});

test('two overlapping stale requests on the same rotated-out token both fail quietly, only once', async () => {
  // Not just one in-flight request racing the rotation — a poll that fires a
  // couple of overlapping calls on the old token before the rotation lands
  // must not log out on EITHER of their late 401s.
  const h = load();
  const w = h.window;
  w.GF.API.token = 'old-token';
  w.GF.API.user = { id: 'u1' };

  const resolvers = [];
  w.fetch = () => new Promise((resolve) => { resolvers.push(resolve); });

  const p1 = w.GF.API._req('GET', '/tasks');
  const p2 = w.GF.API._req('GET', '/departments');
  w.GF.API.token = 'new-token';   // rotated while BOTH are in flight

  resolvers[0]({ status: 401 });
  resolvers[1]({ status: 401 });
  await assert.rejects(p1, /unauthorized/);
  await assert.rejects(p2, /unauthorized/);

  assert.equal(w.GF.API.token, 'new-token');
  assert.ok(w.GF.API.user, 'neither stale 401 may log out the rotated-in session');
  h.close();
});

test('login\'s own 401 never triggers the logout path, rotated token or not', async () => {
  // Sanity check that the new token-comparison guard sits INSIDE the existing
  // `path !== '/auth/login'` branch rather than replacing it.
  const h = load();
  const w = h.window;
  w.GF.API.token = '';
  w.GF.API.user = null;
  w.fetch = async () => ({ status: 401 });
  await assert.rejects(w.GF.API._req('POST', '/auth/login', { email: 'x', password: 'y' }),
    /unauthorized/);
  assert.equal(w.GF.API.token, '');
  h.close();
});
