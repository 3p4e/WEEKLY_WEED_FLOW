'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/integrate.js — GF.cycleStatus / GF.toggleDone / GF.setStatus must
   guard against overlapping in-flight PATCHes on the SAME task, the same way
   submitAdd/submitUser already guard their Save buttons with GF.once().

   Each of the three calls a synchronous local mutation, then fires an async
   pushStatus() PATCH computed from the (already-mutated) local status. Before
   the fix, a fast double-click fired two overlapping PATCHes; whichever
   response resolved LAST decided the persisted state, regardless of the
   user's actual last click. The fix scopes GF.once('status-'+id, ...) per
   task id, so a second call on the SAME task while the first is still in
   flight is dropped (GF.once's own semantics — see core.js), while a
   different task's status control is never blocked.

   This file loads the real chassis (data/core/render/voice/api/integrate, in
   index.html order) so GF.WWF.install() actually runs and installs the real
   overrides under test — the README's "integrate.js is not covered" note is
   about the view layer's live-HTTP glue, not this reusable status-mutation
   guard, which is pure logic once GF.API.updateTask is stubbed.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const flush = async (n = 12) => { for (let i = 0; i < n; i++) await Promise.resolve(); };

function load() {
  const h = loadGF({
    files: ['data.js', 'core.js', 'render.js', 'voice.js', 'api.js', 'integrate.js'],
  });
  const w = h.window;
  // Rendering/animation are irrelevant to the guard under test, and pull in
  // DOM ids (#panels, requestAnimationFrame) this harness's bare shell does
  // not provide — stub them, the same way harvest-view.test.js's PRE_HARVEST
  // stubs GF.render.all rather than building the real page around it.
  w.GF.render.panels = () => {};
  w.GF.render.telemetry = () => {};
  w.GF.render.all = () => {};
  w.GF.flashCompleted = () => {};
  // Full permissions so GF.can('status', t) never itself blocks a call —
  // the guard under test is the re-entrancy lock, not the permission gate.
  w.GF.state.user = 'me';
  w.GF.PEOPLE = { me: { role: 'admin' } };
  return h;
}

function addTask(w, over = {}) {
  const t = { id: 't1', status: 'pending', owner: 'me', helpers: [], ...over };
  w.GF.state.tasks.push(t);
  return t;
}

// A controllable GF.API.updateTask: every call is recorded and left pending
// until its resolver is invoked, so the test drives the exact interleaving.
function stubUpdateTask(w) {
  const calls = [];
  const resolvers = [];
  w.GF.API.updateTask = (id, body) => new Promise((resolve) => {
    calls.push({ id, body });
    resolvers.push(resolve);
  });
  return { calls, resolvers };
}

// setStatus is deliberately NOT in this loop: unlike toggleDone/cycleStatus
// (which always flip/advance the status), origSet's own no-op guard
// (`if (t.status === status) return false;`) refuses a call that targets the
// status the task is ALREADY at — a real behaviour of core.js, unrelated to
// the once-guard under test here. Its equivalent scenarios are covered below
// with explicitly varied target statuses so that check never masks the guard.
for (const [name, fire] of [
  ['toggleDone', (GF, id) => GF.toggleDone(id)],
  ['cycleStatus', (GF, id) => GF.cycleStatus(id)],
]) {
  test(`${name}: a fast double-click on the SAME task only PATCHes once while the first is in flight`, async () => {
    const h = load();
    const w = h.window;
    addTask(w);
    const { calls } = stubUpdateTask(w);

    fire(w.GF, 't1');
    fire(w.GF, 't1');
    await flush();

    assert.equal(calls.length, 1,
      'the second click, while the first PATCH is still in flight, must be dropped — not fired as a second overlapping request');
    h.close();
  });

  test(`${name}: once the in-flight PATCH resolves, the guard clears and a further click goes through`, async () => {
    const h = load();
    const w = h.window;
    addTask(w);
    const { calls, resolvers } = stubUpdateTask(w);

    fire(w.GF, 't1');
    await flush();
    assert.equal(calls.length, 1);

    resolvers[0]({});
    await flush();

    fire(w.GF, 't1');
    await flush();
    assert.equal(calls.length, 2,
      'GF.once only drops a call while an earlier one for the SAME task is in flight — it must not latch permanently');
    h.close();
  });

  test(`${name}: a busy task never blocks a DIFFERENT task's status control`, async () => {
    const h = load();
    const w = h.window;
    addTask(w, { id: 't1' });
    addTask(w, { id: 't2' });
    const { calls } = stubUpdateTask(w);

    fire(w.GF, 't1');       // leaves t1's guard busy (updateTask never resolved)
    fire(w.GF, 't2');
    await flush();

    assert.equal(calls.length, 2,
      'cycling/toggling status on task A must not block a simultaneous click on task B');
    assert.deepEqual(calls.map(c => c.id).sort(), ['t1', 't2']);
    h.close();
  });
}

/* ── setStatus: same three scenarios, with explicitly distinct target
   statuses per call so origSet's own "already at this status" no-op check
   never gets confused with the once-guard being tested here. ── */

test('setStatus: a fast double-click on the SAME task only PATCHes once while the first is in flight', async () => {
  const h = load();
  const w = h.window;
  addTask(w, { status: 'pending' });
  const { calls } = stubUpdateTask(w);

  w.GF.setStatus('t1', 'working');
  w.GF.setStatus('t1', 'stuck');   // a genuinely different target — must still be dropped as busy
  await flush();

  assert.equal(calls.length, 1,
    'the second click, while the first PATCH is still in flight, must be dropped — not fired as a second overlapping request');
  h.close();
});

test('setStatus: once the in-flight PATCH resolves, the guard clears and a further click goes through', async () => {
  const h = load();
  const w = h.window;
  addTask(w, { status: 'pending' });
  const { calls, resolvers } = stubUpdateTask(w);

  w.GF.setStatus('t1', 'working');
  await flush();
  assert.equal(calls.length, 1);

  resolvers[0]({});
  await flush();

  w.GF.setStatus('t1', 'done');   // different target than the first call landed on
  await flush();
  assert.equal(calls.length, 2,
    'GF.once only drops a call while an earlier one for the SAME task is in flight — it must not latch permanently');
  h.close();
});

test('setStatus: a busy task never blocks a DIFFERENT task\'s status control', async () => {
  const h = load();
  const w = h.window;
  addTask(w, { id: 't1', status: 'pending' });
  addTask(w, { id: 't2', status: 'pending' });
  const { calls } = stubUpdateTask(w);

  w.GF.setStatus('t1', 'working');   // leaves t1's guard busy (updateTask never resolved)
  w.GF.setStatus('t2', 'working');
  await flush();

  assert.equal(calls.length, 2,
    'setting status on task A must not block a simultaneous status change on task B');
  assert.deepEqual(calls.map(c => c.id).sort(), ['t1', 't2']);
  h.close();
});

test('setStatus keeps its synchronous true/false return for callers (render.js\'s status picker, worklog.js)', async () => {
  // render.js: `if (v !== t.status && GF.setStatus(id, v)) { GF.render.panels(); ... }`
  // worklog.js: `if (GF.setStatus && GF.setStatus(taskId, 'done')) { ... }`
  // Both branch on GF.setStatus's return value SYNCHRONOUSLY, so the fix must
  // preserve a real boolean return — not a Promise — despite now routing
  // through the async GF.once() guard.
  const h = load();
  const w = h.window;
  addTask(w, { status: 'pending' });
  stubUpdateTask(w);

  const first = w.GF.setStatus('t1', 'working');
  assert.equal(first, true, 'the first, unguarded call must report success synchronously');
  assert.equal(typeof first, 'boolean', 'must be a real boolean, not a pending Promise');

  const second = w.GF.setStatus('t1', 'done');
  assert.equal(second, false,
    'a call dropped because the same task is already mid-PATCH must synchronously report false, exactly like a rejected/no-op setStatus');
  h.close();
});

test('a mid-flight PATCH failure reverts the local status, and the guard still clears', async () => {
  const h = load();
  const w = h.window;
  const t = addTask(w, { status: 'pending' });
  let rejectFirst;
  w.GF.API.updateTask = () => new Promise((_resolve, reject) => { rejectFirst = reject; });

  w.GF.toggleDone('t1');
  await flush();
  assert.equal(t.status, 'done', 'the optimistic local mutation applies immediately');

  rejectFirst(new Error('network down'));
  await flush();
  assert.equal(t.status, 'pending', 'a failed save must revert the optimistic status change');

  // The guard must have cleared despite the rejection, so a subsequent click
  // is not permanently locked out by one failed request.
  const { calls } = stubUpdateTask(w);
  w.GF.toggleDone('t1');
  await flush();
  assert.equal(calls.length, 1, 'the guard must release even when pushStatus rejects');
  h.close();
});
