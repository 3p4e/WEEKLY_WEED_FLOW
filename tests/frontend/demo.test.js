'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/demo.js — GF.DEMO.exit()

   exit() already reset the demo session (sessionStorage) and the visitor's
   theme (restoreTheme()), but left the other UI-preference localStorage
   keys — view, module, language — untouched. On a shared/kiosk browser a
   demo visitor's language change (or view/module) silently carried over
   into whoever used the app next. Fixed by clearing gf_view/gf_module/
   gf_lang alongside the existing theme restore, the same "drop stale gf_*
   keys" idea boot-guard.js already applies on a schema bump.

   demo.js is self-contained enough to load standalone (its module-load-time
   install() call only touches sessionStorage/localStorage, both guarded by
   try/catch) — same reasoning as api-token-race.test.js's api.js-only load.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

function setup() {
  return loadGF({ files: ['demo.js'] });
}

test('exit() clears the view/module/language preference keys, not just the demo session + theme', () => {
  const h = setup();
  const w = h.window;
  // A demo session in progress, plus UI prefs the demo visitor picked (or
  // that were already sitting there from whoever used this kiosk before them).
  w.sessionStorage.setItem('wwf_demo', '1');
  w.sessionStorage.setItem('wwf_token', 'demo-token');
  w.sessionStorage.setItem('wwf_user', '{"id":"u1"}');
  w.localStorage.setItem('gf_view', 'board');
  w.localStorage.setItem('gf_module', 'qc');
  w.localStorage.setItem('gf_lang', 'mk');

  h.GF.DEMO.exit();

  assert.equal(w.sessionStorage.getItem('wwf_demo'), null);
  assert.equal(w.sessionStorage.getItem('wwf_token'), null);
  assert.equal(w.sessionStorage.getItem('wwf_user'), null);
  assert.equal(w.localStorage.getItem('gf_view'), null,
    'gf_view must be cleared so the next visitor gets the app default, not the demo visitor\'s last view');
  assert.equal(w.localStorage.getItem('gf_module'), null,
    'gf_module must be cleared so the next visitor is not dropped into the demo visitor\'s last module');
  assert.equal(w.localStorage.getItem('gf_lang'), null,
    'gf_lang must be cleared — this is the exact bug: a demo visitor\'s language change ' +
    'must not persist into the next real user\'s session on a shared/kiosk browser');
  h.close();
});

test('exit() still restores the visitor\'s own pre-demo theme (regression guard on existing behaviour)', () => {
  const h = setup();
  const w = h.window;
  w.localStorage.setItem('gf_theme', 'mass-weed');                  // the random skin the demo picked
  w.localStorage.setItem('wwf_demo_prev_theme', 'mass-weed-light'); // captured on enter()
  w.sessionStorage.setItem('wwf_demo', '1');
  w.sessionStorage.setItem('wwf_token', 'demo-token');

  h.GF.DEMO.exit();

  assert.equal(w.localStorage.getItem('gf_theme'), 'mass-weed-light');
  assert.equal(w.localStorage.getItem('wwf_demo_prev_theme'), null);
  h.close();
});

test('exit() is safe to call with no demo session in progress at all', () => {
  const h = setup();
  assert.doesNotThrow(() => h.GF.DEMO.exit());
  h.close();
});
