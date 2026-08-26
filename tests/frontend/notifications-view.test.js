'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/notifications-view.js — two bugs in the inbox item row / openNotif.

   Bug 5: n.id and n.task_id were interpolated into onclick="..." attributes
   with NO escaping at all (not even GF.esc), unlike every other dynamic
   value in this file (sentence output, reason labels, timestamps). Since a
   notification's id ultimately traces back to a database row a backend bug
   or migration hiccup could make non-UUID, and task_id is attacker-adjacent
   in the same way, an unescaped quote could break out of the onclick
   attribute and inject markup/script.

   Bug 6: openNotif swallowed a failed GF.API.notifRead(id) call
   (`catch (e) {}`) and STILL applied the optimistic local update (n.read =
   true, decrementing the unread count) — unlike its two siblings
   notifDone/notifReadAll, which correctly `return` (aborting the local
   mutation) on a caught error. A network blip or expired session would
   silently mark a notification read / decrement the badge client-side even
   though the server never recorded it.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// notifications-view.js is a self-contained IIFE; the globals below are
// exactly what its render/action paths touch. GF.render.all is stubbed to a
// counter (openNotif's success path calls it when there is no task to jump
// to) rather than left undefined, since GF.render itself is render.js's
// object and is not loaded here.
//
// The file also registers a real 75s setInterval poll plus a window-'load'
// -triggered one-shot setTimeout(...,4000) at module scope (its own
// self-correcting mechanism — see the bug-3 note in approvals-view.js about
// this view lacking an equivalent). Neither is exercised by anything below,
// and a real pending timer on the jsdom window's realm keeps node:test's
// process from going idle between/after tests, so both are stubbed inert
// here — scoped to this test file only, not the shared harness.
const PRE = `
  window.setInterval = function () { return 0; };
  window.setTimeout = function () { return 0; };
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.PEOPLE = {};
  window.GF.icon = function () { return ''; };
  window.GF.avatar = function () { return ''; };
  window.GF.state = { user: 'me', lang: 'en' };
  window.GF.API = { token: 'tok', user: { id: 'me' } };
  window.__renderAllCalls = 0;
  window.GF.render = { all: function () { window.__renderAllCalls++; }, sidebar: function () {} };
`;

function load() {
  return loadGF({ files: ['data.js', 'core.js', 'notifications-view.js'], preScript: PRE });
}

test('the inbox row escapes n.id and n.task_id in both onclick sites (bug 5)', () => {
  const h = load();
  const { GF, window: w } = h;
  const st = GF.WWF._notif;
  // Already "loaded" for the current user so GF.views.inbox() renders
  // straight from st.items instead of firing off a real loadInbox().
  st.loaded = true; st.user = GF.state.user;
  st.items = [{
    id: `n1' onmouseover='alert(1)`,
    task_id: `t1" onclick="evil()`,
    read: false, reason: 'assigned', verb: 'assigned', actor_id: 'u1',
    params: { title: 'Task X' }, created_at: '2026-07-27T10:00:00',
  }];
  const html = GF.views.inbox();

  // Neither payload must ever appear as LIVE, unescaped markup.
  assert.equal(html.includes(`onmouseover='alert(1)`), false,
    'the single-quote breakout in n.id must not survive into the onclick attribute');
  assert.equal(html.includes(`onclick="evil()"`), false,
    'the double-quote breakout in n.task_id must not survive into the onclick attribute');

  // Both quote characters must come through GF.esc()-encoded.
  assert.ok(html.includes(GF.esc(st.items[0].id)),
    'openNotif(...) must carry the GF.esc()-encoded id');
  assert.ok(html.includes(GF.esc(st.items[0].task_id)),
    'openNotif(...) must carry the GF.esc()-encoded task_id');
  // notifDone(id) is the row's second onclick site using the same n.id.
  assert.ok(html.includes(`GF.WWF.notifDone('${GF.esc(st.items[0].id)}')`),
    'notifDone(...) must also carry the GF.esc()-encoded id');
  h.close();
});

test('a plain UUID-shaped id/task_id render byte-identical through GF.esc (no visual regression from the bug-5 fix)', () => {
  const h = load();
  const { GF } = h;
  const st = GF.WWF._notif;
  st.loaded = true; st.user = GF.state.user;
  st.items = [{
    id: '11111111-1111-1111-1111-111111111111',
    task_id: '22222222-2222-2222-2222-222222222222',
    read: false, reason: 'assigned', verb: 'assigned', actor_id: 'u1',
    params: { title: 'Task X' }, created_at: '2026-07-27T10:00:00',
  }];
  const html = GF.views.inbox();
  assert.ok(html.includes(
    `onclick="GF.WWF.openNotif('11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222')"`));
  assert.ok(html.includes(`GF.WWF.notifDone('11111111-1111-1111-1111-111111111111')`));
  h.close();
});

test('openNotif aborts the optimistic read/unread mutation when the API call fails (bug 6)', async () => {
  const h = load();
  const { GF, window: w } = h;
  const st = GF.WWF._notif;
  const n = { id: 'n1', task_id: '', read: false };
  st.items = [n];
  st.unread = 3;
  GF.API.notifRead = async () => { throw new Error('network blip'); };
  let xrJumpCalled = false;
  GF.WWF.xrJump = () => { xrJumpCalled = true; };

  await GF.WWF.openNotif('n1', '');

  assert.equal(n.read, false, 'a failed notifRead must NOT mark the notification read locally');
  assert.equal(st.unread, 3, 'a failed notifRead must NOT decrement the unread badge count');
  assert.equal(st._justRead['n1'], undefined,
    'the optimistic-guard window must not be armed for a write that never landed');
  assert.equal(xrJumpCalled, false, 'no navigation should follow a failed mark-as-read either');
  assert.equal(w.__renderAllCalls, 0, 'no re-render should follow a failed mark-as-read either');
  h.close();
});

test('openNotif still applies the optimistic mutation on success (behavior unchanged by the bug-6 fix)', async () => {
  const h = load();
  const { GF, window: w } = h;
  const st = GF.WWF._notif;
  const n = { id: 'n2', task_id: '', read: false };
  st.items = [n];
  st.unread = 2;
  let readCalledWith = null;
  GF.API.notifRead = async (id) => { readCalledWith = id; };

  await GF.WWF.openNotif('n2', '');

  assert.equal(readCalledWith, 'n2');
  assert.equal(n.read, true, 'a successful notifRead still marks the notification read locally');
  assert.equal(st.unread, 1, 'a successful notifRead still decrements the unread badge count');
  // Compare against the FROZEN clock's own notion of "now", evaluated inside
  // the jsdom window's realm — the outer Node process runs on the real,
  // unfrozen clock, which is not comparable to a value openNotif computed
  // from the window's overridden Date.
  assert.ok(st._justRead['n2'] > h.global('Date.now()'),
    'the optimistic-guard window is armed on a real success');
  assert.equal(w.__renderAllCalls, 1, 'the no-task-to-jump-to branch still re-renders on success');
  h.close();
});
