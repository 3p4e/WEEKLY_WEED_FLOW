'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/chooser.js — GF.openChooser / GF.choose / GF.selectField
   the popup dropdown's animation-origin logic

   GF.openChooser used to anchor the popup's entrance animation on
   `window.event` — the deprecated global that only happens to hold the
   right click event because of how every caller was invoked (synchronously,
   no async gap). Fixed by threading the real event object through as a
   parameter: GF.selectField's own trigger button now passes `event`
   explicitly in its onclick, GF.choose(cfg, ev) forwards it, and
   GF.openChooser(id, ev) uses ONLY what it is handed — no read of the
   global inside GF.openChooser itself. GF.choose() falls back to
   window.event when its caller doesn't pass one (its only current caller,
   render.js's GF.pickStatus, is outside this pass's file scope, so that one
   compatibility shim is deliberate and documented in chooser.js).

   Geometry: jsdom has no layout engine, so every element's real
   getBoundingClientRect() is a flat 0/0/0/0 rect. Tests that need to tell
   two elements apart stub that method directly on the element — the
   documented, supported way to fake layout in this harness (see the file's
   own quick check before writing this).
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

function setup() {
  return loadGF({ files: ['data.js', 'core.js', 'chooser.js'], bodyHtml: '<div id="toasts"></div>' });
}

test('GF.selectField\'s trigger button passes the real click event explicitly', () => {
  const h = setup();
  const markup = h.GF.selectField('f1', { value: 'a', options: [{ v: 'a', label: 'A' }, { v: 'b', label: 'B' } ] });
  assert.match(markup, /onclick="GF\.openChooser\('f1', event\)"/,
    'the button must thread the real click event into GF.openChooser, not rely on it reading window.event');
  h.close();
});

test('GF.openChooser anchors on the THREADED event, never on window.event', () => {
  const h = setup();
  const doc = h.window.document;
  doc.body.insertAdjacentHTML('beforeend',
    h.GF.selectField('f1', { value: 'a', options: [{ v: 'a', label: 'A' }] }));
  const btn = doc.getElementById('f1-btn');
  btn.getBoundingClientRect = () => ({ left: 100, top: 50, width: 20, height: 20 });

  // A decoy on window.event pointing at a DIFFERENT element with a wildly
  // different rect. If GF.openChooser ever fell back to window.event instead
  // of trusting its `ev` parameter, the popup would anchor on THIS instead.
  const decoy = doc.createElement('button');
  doc.body.appendChild(decoy);
  decoy.getBoundingClientRect = () => ({ left: 900, top: 900, width: 20, height: 20 });
  h.window.event = { currentTarget: decoy, target: decoy };

  h.GF.openChooser('f1', { currentTarget: btn, target: btn });

  const modal = doc.getElementById('gf-chooser').querySelector('.sel-modal');
  assert.ok(modal, 'the popup must have opened');
  // origin = (btn rect center) − (modal rect top-left); the modal's own rect
  // is jsdom's flat 0/0/0/0, so the origin is exactly the button's center.
  assert.equal(modal.style.transformOrigin, '110px 60px',
    'must be positioned from the passed-in event, not from window.event\'s decoy target');
  h.close();
});

test('GF.openChooser with no event at all still opens (no throw), just with no transform-origin', () => {
  const h = setup();
  const doc = h.window.document;
  doc.body.insertAdjacentHTML('beforeend',
    h.GF.selectField('f1', { value: 'a', options: [{ v: 'a', label: 'A' }] }));
  h.window.event = undefined;
  assert.doesNotThrow(() => h.GF.openChooser('f1'));
  const modal = doc.getElementById('gf-chooser').querySelector('.sel-modal');
  assert.equal(modal.style.transformOrigin, '');
  h.close();
});

test('GF.choose(cfg, ev) forwards the threaded event to GF.openChooser, same as GF.selectField\'s path', () => {
  const h = setup();
  const doc = h.window.document;
  const trigger = doc.createElement('span');
  doc.body.appendChild(trigger);
  trigger.getBoundingClientRect = () => ({ left: 40, top: 10, width: 10, height: 10 });
  h.window.event = null;   // prove the imperative path does not need the global either

  let picked = null;
  h.GF.choose({ title: 'Pick', value: 'x', options: [{ v: 'x', label: 'X' }],
                onPick: (v) => { picked = v; } }, { currentTarget: trigger, target: trigger });

  const modal = doc.getElementById('gf-chooser').querySelector('.sel-modal');
  assert.equal(modal.style.transformOrigin, '45px 15px');
  h.close();
  void picked; // exercised only to prove onPick still wired through cfg
});

test('GF.choose(cfg) with no ev argument falls back to window.event (documented compatibility shim)', () => {
  const h = setup();
  const doc = h.window.document;
  const trigger = doc.createElement('span');
  doc.body.appendChild(trigger);
  trigger.getBoundingClientRect = () => ({ left: 200, top: 300, width: 10, height: 10 });
  h.window.event = { currentTarget: trigger, target: trigger };

  h.GF.choose({ title: 'Pick', value: 'x', options: [{ v: 'x', label: 'X' }] });

  const modal = doc.getElementById('gf-chooser').querySelector('.sel-modal');
  assert.equal(modal.style.transformOrigin, '205px 305px',
    'the one remaining caller that omits ev (render.js\'s GF.pickStatus) must keep working unchanged');
  h.close();
});
