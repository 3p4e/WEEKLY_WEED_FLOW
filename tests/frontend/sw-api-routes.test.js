'use strict';

/* ══════════════════════════════════════════════════════════════════════
   sw.js API_RE must cover everything nginx proxies to the backend.

   THE BUG THIS EXISTS TO PREVENT, found 2026-07-30 with `decon` already live in
   production: sw.js routes requests two ways — API paths network-first, and
   EVERYTHING ELSE cache-first. A backend prefix missing from API_RE therefore
   does not 404 and does not error. It falls through to the static branch, gets
   stored in the versioned cache on first fetch, and is replayed from cache on
   every later request until the next VERSION bump. A decontamination board that
   silently shows yesterday's swab results is worse than one that fails.

   Both files are plain text with a single source of truth each, so this compares
   them directly rather than mocking a service worker. It is a drift detector, not
   a behavioural test: any prefix nginx forwards must be in API_RE. The reverse is
   allowed — API_RE may legitimately name a prefix nginx handles in its own
   location block (`intake` has a longer read timeout and so is matched first).
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const WEB = path.resolve(__dirname, '..', '..', 'web');
const sw = fs.readFileSync(path.join(WEB, 'sw.js'), 'utf8');
const nginx = fs.readFileSync(path.join(WEB, 'nginx.conf'), 'utf8');

/** Every alternation group in an nginx `location ~ ^/(a|b|c)(/|$)` proxy block,
 *  plus single-prefix blocks like `location ~ ^/intake(/|$)`. Only blocks that
 *  actually proxy_pass count — `location /` and the static-asset block do not. */
function nginxProxiedPrefixes(conf) {
  const out = new Set();
  // Split on `location` so each chunk carries its own body, then keep the ones
  // that proxy. A regex over the whole file would pair a pattern with another
  // block's proxy_pass.
  for (const chunk of conf.split(/\blocation\b/).slice(1)) {
    if (!/proxy_pass/.test(chunk)) continue;
    const m = chunk.match(/~\s*\^\\?\/\(?([A-Za-z0-9_|-]+)\)?\(/);
    if (!m) continue;
    for (const p of m[1].split('|')) if (p) out.add(p);
  }
  return out;
}

function swApiPrefixes(src) {
  const m = src.match(/const API_RE = \/\^\\\/\(([^)]+)\)/);
  assert.ok(m, 'could not find API_RE in sw.js — this test needs updating, not deleting');
  return new Set(m[1].split('|').filter(Boolean));
}

test('every backend prefix nginx proxies is network-first in the service worker', () => {
  const proxied = nginxProxiedPrefixes(nginx);
  const api = swApiPrefixes(sw);
  // Sanity: if the nginx parse silently returned nothing, the assertion below
  // would pass vacuously and the drift detector would be permanently green.
  assert.ok(proxied.size >= 15,
    `parsed only ${proxied.size} proxied prefixes from nginx.conf — the parser is broken, ` +
    'so this test would pass no matter what sw.js contains');
  const missing = [...proxied].filter(p => !api.has(p)).sort();
  assert.deepEqual(missing, [],
    'these backend prefixes are NOT in sw.js API_RE, so their API responses will be ' +
    'cached cache-first and served stale until the next VERSION bump: ' + missing.join(', '));
});

/** Every prefix api.js actually requests. */
function clientCalledPrefixes() {
  const apiJs = fs.readFileSync(path.join(WEB, 'gf', 'api.js'), 'utf8');
  const called = new Set();
  for (const m of apiJs.matchAll(/_req\(\s*'(?:GET|POST|PATCH|PUT|DELETE)',\s*'\/([a-z0-9_-]+)/g)) {
    called.add(m[1]);
  }
  assert.ok(called.size >= 15,
    `parsed only ${called.size} called prefixes from api.js — the parser is broken, ` +
    'so the assertions below would pass no matter what');
  return called;
}

test('the API prefixes the app actually calls are all network-first', () => {
  // A second, independent angle: read the paths api.js requests rather than the
  // proxy config, so a prefix that exists in the client but was never added to
  // nginx is caught too.
  const api = swApiPrefixes(sw);
  const missing = [...clientCalledPrefixes()].filter(p => !api.has(p)).sort();
  assert.deepEqual(missing, [],
    'api.js calls these prefixes but sw.js would serve them cache-first: ' + missing.join(', '));
});

test('every prefix the client calls is actually proxied to the backend by nginx', () => {
  // THE BUG THIS FOUND, live in production on 2026-07-30: `handoffs` was absent
  // from the nginx allowlist while GF.API.resolveHandoff posted to
  // /handoffs/{id}/resolve. Unproxied paths fall through to the SPA location,
  // where the static handler answers a POST with 405 — verified against the
  // running frontend, which returned 405 there and 401 for the neighbouring
  // /tasks/{id}/handoffs. Resolving a cross-department handoff had therefore
  // never reached the backend, and nothing failed loudly enough to notice.
  const proxied = nginxProxiedPrefixes(nginx);
  assert.ok(proxied.size >= 15, `parsed only ${proxied.size} proxied prefixes — parser broken`);
  const unreachable = [...clientCalledPrefixes()].filter(p => !proxied.has(p)).sort();
  assert.deepEqual(unreachable, [],
    'api.js calls these prefixes but nginx does not proxy them, so in production they hit ' +
    'the SPA fallback (405 on a POST, index.html on a GET): ' + unreachable.join(', '));
});

test('every gf script index.html loads is in the service-worker precache list', () => {
  // The precache list is written by hand, and a new view file left out of it is
  // invisible until someone opens the app offline.
  const html = fs.readFileSync(path.join(WEB, 'index.html'), 'utf8');
  const tags = [...html.matchAll(/<script src="(gf\/[^"]+)"/g)].map(m => m[1]);
  assert.ok(tags.length >= 40, `parsed only ${tags.length} script tags — the parser is broken`);
  const missing = tags.filter(t => !sw.includes("'/" + t + "'"));
  assert.deepEqual(missing, [], 'not in the sw.js precache list: ' + missing.join(', '));
  // And each one must actually exist on disk.
  const absent = tags.filter(t => !fs.existsSync(path.join(WEB, t)));
  assert.deepEqual(absent, [], 'index.html loads files that do not exist: ' + absent.join(', '));
});

test('every path in the precache list exists, or the service worker never installs', () => {
  // The reverse direction, and the more severe one: SHELL is passed to
  // cache.addAll(), which REJECTS if any single request fails. One stale path —
  // a renamed view, a deleted asset — therefore fails the whole install inside
  // e.waitUntil(), so the app silently loses offline support and every shell
  // file keeps going to the network. Nothing on screen says so.
  const m = sw.match(/const SHELL = \[([\s\S]*?)\n\];/);
  assert.ok(m, 'could not find the SHELL array in sw.js');
  const paths = [...m[1].matchAll(/'([^']+)'/g)].map(x => x[1]);
  assert.ok(paths.length >= 50, `parsed only ${paths.length} SHELL entries — the parser is broken`);
  // '/' and '/index.html' are the same document; everything else maps to a file.
  const absent = paths
    .filter(p => p !== '/')
    .filter(p => !fs.existsSync(path.join(WEB, p.replace(/^\//, ''))));
  assert.deepEqual(absent, [],
    'precached but missing from web/ — cache.addAll() will reject and the service ' +
    'worker will never install: ' + absent.join(', '));
});

test('the e2e nginx proxies every prefix production nginx does', () => {
  // THE BUG THIS FOUND, 2026-07-31 during a comprehensive test pass: the
  // Playwright proxy (web/e2e/nginx.local.conf) had drifted five prefixes
  // behind production's web/nginx.conf — cultivation, decon, waste, handoffs
  // and intake were all absent. An e2e spec driving one of those boards would
  // hit the SPA fallback (200 index.html on a GET, 405 on a POST) instead of
  // the backend, so it would fail confusingly or pass against the wrong
  // response. The existing tests above only compare production nginx.conf to
  // sw.js and api.js, so nothing watched the e2e proxy at all; the suite
  // stayed green only because no current spec happened to touch those five.
  //
  // The e2e proxy must be a SUPERSET of production's proxied prefixes: it may
  // add locals (it does not today), but it must never drop one, or the e2e
  // environment stops being a faithful stand-in for production exactly where a
  // spec would rely on it.
  const local = fs.readFileSync(path.join(WEB, 'e2e', 'nginx.local.conf'), 'utf8');
  const prod = nginxProxiedPrefixes(nginx);
  const e2e = nginxProxiedPrefixes(local);
  assert.ok(prod.size >= 15, `parsed only ${prod.size} prod prefixes — parser broken`);
  assert.ok(e2e.size >= 15, `parsed only ${e2e.size} e2e prefixes — parser broken`);
  const missing = [...prod].filter(p => !e2e.has(p)).sort();
  assert.deepEqual(missing, [],
    'web/e2e/nginx.local.conf does NOT proxy these prefixes that production proxies, so an ' +
    'e2e spec exercising them silently hits the SPA fallback: ' + missing.join(', '));
});
