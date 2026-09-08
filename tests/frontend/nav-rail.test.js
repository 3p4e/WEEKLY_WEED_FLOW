'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/render.js — GF.pruneNavGroups, the rail's empty-group guard.

   Floor and QMS Studio are ANCHOR groups: render.sidebar emits their label
   and a hidden end-marker, and the views that belong in them insert
   themselves afterwards, because _registerFullPageView (integrate.js)
   monkey-patches render.sidebar and its insertions run after the base body
   has returned. So the label is written before anyone knows whether
   anything will land under it.

   When a module has no such views, the label was left standing over empty
   space. That is how a COO opening the task module met a "FLOOR" heading
   with nothing beneath it, right after being told the floor lives there.

   These tests drive the real helper against the real markup shapes:
   a label with items keeps showing, a label with only its hidden anchor
   is hidden, and the hidden anchor itself is never mistaken for an item.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.API = { user: { role: 'COO' } };
`;

function load() {
  return loadGF({ files: ['data.js', 'core.js', 'render.js'], preScript: PRE });
}

function setNav(h, html) {
  let nav = h.window.document.getElementById('nav');
  if (!nav) {
    nav = h.window.document.createElement('nav');
    nav.id = 'nav';
    h.window.document.body.appendChild(nav);
  }
  nav.innerHTML = html;
  return nav;
}

const GROUP = (label) => `<div class="nav-group">${label}</div>`;
const ITEM = (key) => `<div class="nav-item" data-nav="${key}"><span>${key}</span></div>`;
const ANCHOR = (key) => `<div data-nav="${key}" style="display:none"></div>`;

test('a group label with items under it keeps showing', () => {
  const h = load();
  const nav = setNav(h, GROUP('Operations') + ITEM('mywork') + ITEM('board'));
  h.window.GF.pruneNavGroups();
  assert.equal(nav.querySelector('.nav-group').hidden, false);
  h.close();
});

test('a group label with only its hidden anchor is hidden', () => {
  const h = load();
  // Exactly what the rail emits for Floor when no floor view registered:
  // the label, then the end-marker, then the next group.
  const nav = setNav(h, GROUP('Floor') + ANCHOR('floor-end')
    + GROUP('System') + ITEM('inbox'));
  h.window.GF.pruneNavGroups();
  const groups = nav.querySelectorAll('.nav-group');
  assert.equal(groups[0].hidden, true, 'Floor has nothing under it');
  assert.equal(groups[1].hidden, false, 'System has Inbox');
  h.close();
});

test('items inserted before the anchor keep the label visible', () => {
  const h = load();
  const nav = setNav(h, GROUP('Floor') + ITEM('facility') + ITEM('cultivation')
    + ANCHOR('floor-end') + GROUP('System') + ITEM('inbox'));
  h.window.GF.pruneNavGroups();
  assert.equal(nav.querySelectorAll('.nav-group')[0].hidden, false);
  h.close();
});

test('a trailing group with nothing after it at all is hidden', () => {
  const h = load();
  const nav = setNav(h, GROUP('Operations') + ITEM('mywork') + GROUP('QMS Studio'));
  h.window.GF.pruneNavGroups();
  const groups = nav.querySelectorAll('.nav-group');
  assert.equal(groups[0].hidden, false);
  assert.equal(groups[1].hidden, true);
  h.close();
});

test('the prune un-hides a group that has items again', () => {
  const h = load();
  const nav = setNav(h, GROUP('Floor') + ANCHOR('floor-end'));
  h.window.GF.pruneNavGroups();
  assert.equal(nav.querySelector('.nav-group').hidden, true);
  // A later render inserts the floor views ahead of the anchor.
  nav.insertBefore(
    (() => { const d = h.window.document.createElement('div');
             d.className = 'nav-item'; d.setAttribute('data-nav', 'facility'); return d; })(),
    nav.querySelector('[data-nav="floor-end"]'));
  h.window.GF.pruneNavGroups();
  assert.equal(nav.querySelector('.nav-group').hidden, false);
  h.close();
});

test('an absent rail is not an error', () => {
  const h = load();
  const nav = h.window.document.getElementById('nav');
  if (nav) nav.remove();
  assert.doesNotThrow(() => h.window.GF.pruneNavGroups());
  h.close();
});
