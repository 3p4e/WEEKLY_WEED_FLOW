'use strict';

/* ══════════════════════════════════════════════════════════════════════
   gf-window.js — load the REAL web/gf/*.js sources into a jsdom window.

   web/index.html is a no-build app: ~54 classic <script src> tags, no
   imports/exports, everything hanging off a shared `window.GF` global. There
   is nothing to `require()`. So this harness reproduces the actual loading
   model instead of working around it: it appends a real <script> element per
   source file to a jsdom document and lets jsdom execute it, in the same order
   index.html does.

   Why <script> elements and not `window.eval(src)`: core.js declares two
   BARE top-level consts (`AL` and `_FULL`) and relies on classic scripts
   sharing one global lexical scope, so later files can call `AL(...)`
   unqualified — a contract core.js documents explicitly. Indirect eval gives
   each call its own declarative environment, so `const AL` would vanish and
   every file loaded after core.js would break in the harness but not in the
   browser. Script elements share the realm's global lexical scope exactly the
   way the browser does, so what the tests exercise is the shipped loading
   model, not an approximation of it.
   ════════════════════════════════════════════════════════════════════ */

// The facility timezone. The backend hard-codes it (settings.snapshot_tz =
// "Europe/Skopje") and drives every week window and work-session boundary
// from it. It is pinned here because several helpers under test are only
// CORRECT because they read local date components rather than UTC ones
// (GF.localDateStr carries a long comment about exactly that). Under TZ=UTC
// local and UTC agree, so a regression back to toISOString() would go green.
// Assigning process.env.TZ re-reads the zone on node >= 16; the assertions
// below fail loudly if the runner's tzdata cannot resolve the zone, rather
// than letting the date tests pass vacuously.
process.env.TZ = 'Europe/Skopje';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');

assert.equal(new Date(2026, 6, 1).getTimezoneOffset(), -120,
  'TZ=Europe/Skopje did not take effect (expected UTC+2 in July). The runner cannot ' +
  'resolve that zone, so the local-vs-UTC date tests would pass vacuously — install tzdata.');
assert.equal(new Date(2026, 0, 1).getTimezoneOffset(), -60,
  'TZ=Europe/Skopje did not take effect (expected UTC+1 in January).');

const GF_DIR = path.resolve(__dirname, '..', '..', '..', 'web', 'gf');

// Frozen "now" for every window this harness builds: Thursday 2026-07-30
// 09:15 local (UTC+2). Chosen because core.js runs its calendar generator at
// LOAD time off `new Date()`, so without a fixed clock the week table — and
// therefore GF.calendar.todayId and GF.state.selWeek — changes every week and
// the tests could only assert vacuous things about it.
const FROZEN_LOCAL_ISO = '2026-07-30T09:15:00+02:00';

// Injected as a source file, ahead of the real ones, so the replacement Date
// lives in the jsdom realm (a Node-realm subclass would hand the sources
// cross-realm instances). Only the zero-argument form and Date.now() are
// pinned; every other form still behaves normally, because the code under
// test also constructs dates from explicit components and from strings.
const FREEZE_CLOCK_SRC = (iso) => `
(() => {
  const Real = Date;
  const FIXED = Real.parse(${JSON.stringify(iso)});
  class FrozenDate extends Real {
    constructor(...args) { if (args.length === 0) super(FIXED); else super(...args); }
    static now() { return FIXED; }
  }
  window.Date = FrozenDate;
})();`;

// The shell index.html provides. Deliberately minimal: no #toasts container,
// which makes GF.toast (and therefore GF.denyToast) a no-op early return
// instead of scheduling its 3-second dismissal timer — the suite stays free of
// real timers without stubbing anything.
const BASE_HTML = '<!doctype html><html><head></head><body></body></html>';

/**
 * Build a jsdom window and execute the named web/gf sources in it.
 *
 * @param {object}   [opts]
 * @param {string[]} [opts.files]    web/gf file names, in index.html order.
 * @param {string}   [opts.bodyHtml] markup to place in <body> before loading.
 * @param {object}   [opts.storage]  localStorage keys seeded BEFORE the sources
 *                                   load — core.js reads gf_lang / gf_user /
 *                                   gf_view / gf_exec_hidden at load time, so
 *                                   they cannot be set afterwards.
 * @param {string}   [opts.now]      override the frozen clock (local ISO).
 * @param {string}   [opts.preScript] JS evaluated after the clock and before
 *                                    the source files, to declare globals that
 *                                    a file touches at load time.
 * @returns {{window: object, GF: object, load: Function, close: Function}}
 */
function loadGF(opts = {}) {
  const files = opts.files || ['data.js', 'core.js'];

  // jsdom reports an exception thrown by an executing <script> as a
  // "jsdomError" on the virtual console and otherwise swallows it. Collect
  // them and assert after each file, so a source file that fails to load at
  // all is a RED test rather than a window with a half-built GF on it.
  const jsdomErrors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (err) => jsdomErrors.push(err));
  virtualConsole.sendTo(console, { omitJSDOMErrors: true });

  const dom = new JSDOM(BASE_HTML, {
    // A real http(s) origin, not about:blank: localStorage throws on an opaque
    // origin, and core.js reads it at load time for lang/user/view/theme.
    url: 'https://wwf.test/',
    runScripts: 'dangerously',
    virtualConsole,
  });
  const window = dom.window;

  const load = (src, label) => {
    const el = window.document.createElement('script');
    el.textContent = src;
    window.document.head.appendChild(el);
    if (jsdomErrors.length) {
      const e = jsdomErrors[0];
      throw new Error(`${label} threw while loading: ${(e && (e.detail || e)).stack || e}`);
    }
  };

  load(FREEZE_CLOCK_SRC(opts.now || FROZEN_LOCAL_ISO), '<frozen clock>');
  // Some sources are not loadable in isolation: integrate.js ends with a bare
  // `GF.WWF.install()`, so merely loading the file executes code that reaches
  // for globals other files own (GF.voice, ...). That is a property of the
  // no-build multi-script pattern, not of the test — there is no import graph to
  // resolve, so the only options are to load the whole app or to declare the
  // few globals a file touches on the way up. preScript does the latter, and
  // keeping it explicit per test documents exactly what each file depends on.
  if (opts.preScript) load(opts.preScript, '<preScript>');
  if (opts.bodyHtml) window.document.body.innerHTML = opts.bodyHtml;
  for (const [k, v] of Object.entries(opts.storage || {})) {
    window.localStorage.setItem(k, v);
  }

  for (const name of files) {
    load(fs.readFileSync(path.join(GF_DIR, name), 'utf8'), `web/gf/${name}`);
  }

  return {
    window,
    GF: window.GF,
    // Evaluate an expression in the sources' own global scope — the only way
    // to observe the bare top-level globals (core.js's `AL`) that the classic
    // <script> loading model shares between files.
    global: (expr) => window.eval(expr),
    load: (src, label = '<inline>') => load(src, label),
    close: () => window.close(),
  };
}

/**
 * Replace GF.export._download with a recorder and return the recorded calls.
 *
 * Only the browser-download boundary is stubbed, and it has to be: jsdom
 * implements Blob but NOT URL.createObjectURL, so _download cannot run at all
 * here. Everything that shapes the file — GF.export._csv / ._json, and the
 * escaping inside them — is the real source.
 */
function captureDownloads(GF) {
  const calls = [];
  GF.export._download = (content, name, mime) => { calls.push({ content, name, mime }); };
  return calls;
}

/** Split a CSV line the way a spreadsheet would: on commas outside quotes. */
function csvFields(line) {
  const out = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { inQuotes = !inQuotes; cur += ch; continue; }
    if (ch === ',' && !inQuotes) { out.push(cur); cur = ''; continue; }
    cur += ch;
  }
  out.push(cur);
  return out;
}

module.exports = { loadGF, captureDownloads, csvFields, GF_DIR, FROZEN_LOCAL_ISO };
