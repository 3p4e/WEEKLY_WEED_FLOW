'use strict';

/* ══════════════════════════════════════════════════════════════════════
   shell-hash.js — the fingerprint of the service worker's precached shell.

   web/sw.js caches the app shell cache-first, keyed by VERSION, so a shell
   file that changes without a VERSION bump is served stale until the next
   bump (review 2026-09-27, FE-13 / R2-FE-17). Nothing enforced the bump.

   This module hashes every file in sw.js's SHELL list as it is on disk and
   compares it with tests/frontend/fixtures/shell-hash.json, which records
   { version, hash } as of the last bump. shell-and-gates.test.js fails when
   the hash differs from the fixture's while VERSION is unchanged — "the
   shell changed, bump VERSION" — and when the fixture is stale after a
   bump — "regenerate the fixture". Regenerate with:

       node tests/frontend/helpers/shell-hash.js --write

   which refuses to record a changed shell under an unchanged VERSION.
   ════════════════════════════════════════════════════════════════════ */

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const WEB = path.resolve(__dirname, '..', '..', '..', 'web');
const FIXTURE = path.resolve(__dirname, '..', 'fixtures', 'shell-hash.json');

function readSw() {
  return fs.readFileSync(path.join(WEB, 'sw.js'), 'utf8');
}

function shellVersion(sw = readSw()) {
  const m = /const VERSION = '([^']+)'/.exec(sw);
  if (!m) throw new Error('web/sw.js: no `const VERSION = ...`');
  return m[1];
}

// The precache list as sw.js declares it — every quoted path inside the
// SHELL array literal. '/' is index.html served at the root; it is hashed
// once, as index.html.
function shellPaths(sw = readSw()) {
  const start = sw.indexOf('const SHELL = [');
  const end = sw.indexOf('];', start);
  if (start < 0 || end < 0) throw new Error('web/sw.js: no SHELL list');
  const block = sw.slice(start, end);
  const paths = [...block.matchAll(/'(\/[^']*)'/g)].map(m => m[1]);
  return [...new Set(paths.map(p => (p === '/' ? '/index.html' : p)))].sort();
}

// sha256 over "<path>\n<sha256 of the file>\n" for every precached file, so a
// change in any one of them — or in the list itself — changes the digest.
// A listed file missing on disk is part of the fingerprint too, as MISSING.
function shellHash() {
  const sw = readSw();
  const h = crypto.createHash('sha256');
  const missing = [];
  for (const p of shellPaths(sw)) {
    const file = path.join(WEB, p);
    let digest = 'MISSING';
    if (fs.existsSync(file) && fs.statSync(file).isFile()) {
      digest = crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
    } else {
      missing.push(p);
    }
    h.update(p + '\n' + digest + '\n');
  }
  return { version: shellVersion(sw), hash: h.digest('hex'), missing };
}

function readFixture() {
  if (!fs.existsSync(FIXTURE)) return null;
  return JSON.parse(fs.readFileSync(FIXTURE, 'utf8'));
}

function writeFixture({ force = false } = {}) {
  const now = shellHash();
  const prev = readFixture();
  if (prev && prev.hash !== now.hash && prev.version === now.version && !force) {
    throw new Error(`the shell changed but web/sw.js VERSION is still ${now.version} — bump it first`);
  }
  fs.mkdirSync(path.dirname(FIXTURE), { recursive: true });
  fs.writeFileSync(FIXTURE, JSON.stringify({ version: now.version, hash: now.hash }, null, 2) + '\n');
  return now;
}

module.exports = { WEB, FIXTURE, shellVersion, shellPaths, shellHash, readFixture, writeFixture };

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.includes('--write')) {
    const r = writeFixture({ force: args.includes('--force') });
    console.log(`wrote ${path.relative(process.cwd(), FIXTURE)}: ${r.version} ${r.hash.slice(0, 12)}…`);
  } else {
    const now = shellHash(), prev = readFixture();
    console.log(JSON.stringify({ now, fixture: prev }, null, 2));
    process.exitCode = prev && prev.hash === now.hash && prev.version === now.version ? 0 : 1;
  }
}
