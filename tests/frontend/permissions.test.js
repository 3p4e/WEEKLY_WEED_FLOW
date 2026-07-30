'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/core.js — GF.curRole / GF.perms / GF.ownsTask / GF.can
                    GF.setStatus / GF.cycleStatus / GF.toggleDone

   These predicates gate every write button in the UI. They are NOT the
   security boundary (the backend enforces its own authorisation), but they
   decide what an operator can even attempt, and a wrong answer in either
   direction is a real defect: too permissive and every operator hammers the
   API with requests that 403, too strict and a role silently loses the ability
   to do its job with no error message anywhere.

   The role table is 12 entries wide and hand-maintained (GF.PERMS lists each
   manager role explicitly rather than deriving it), so the failure mode is a
   newly added role being omitted and silently falling back to `operator`. The
   matrix test below is written against Object.keys(GF.PERMS) so a new role is
   covered the moment it is added.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// GF.PEOPLE is empty in data.js — integrate.js fills it from the real roster
// after login. Seeding it here is the same shape that code produces.
function withRoster(extra) {
  const h = loadGF();
  Object.assign(h.GF.PEOPLE, {
    op:     { name: 'Op One',   role: 'operator' },
    op2:    { name: 'Op Two',   role: 'operator' },
    qa:     { name: 'QA Boss',  role: 'qa_mgr' },
    ceo:    { name: 'The CEO',  role: 'ceo' },
    weird:  { name: 'Weird',    role: 'not_a_real_role' },
    noRole: { name: 'No Role' },
  }, extra || {});
  return h;
}

test('GF.curRole falls back to operator for an unknown user and for a roleless person', () => {
  const h = withRoster();
  h.GF.state.user = 'op';      assert.equal(h.GF.curRole(), 'operator');
  h.GF.state.user = 'qa';      assert.equal(h.GF.curRole(), 'qa_mgr');
  // Not in the roster at all — happens on a cold start before loadTeam()
  // resolves, and the localStorage default is the literal string 'marko'.
  h.GF.state.user = 'ghost';   assert.equal(h.GF.curRole(), 'operator');
  h.GF.state.user = 'noRole';  assert.equal(h.GF.curRole(), 'operator');
  h.close();
});

test('GF.perms maps an unrecognised role to the operator row rather than to undefined', () => {
  const h = withRoster();
  h.GF.state.user = 'weird';
  // `GF.PERMS[GF.curRole()] || GF.PERMS.operator` — without the fallback every
  // GF.can() call would throw on `p.create` and the whole UI would white-screen
  // for anyone holding a role the frontend has not been taught yet.
  assert.deepEqual(h.GF.perms(), h.GF.PERMS.operator);
  assert.equal(h.GF.can('create'), true);
  assert.equal(h.GF.can('delete'), false);
  h.close();
});

test('GF.ownsTask is true for the accountable owner and for any listed helper', () => {
  const h = withRoster();
  h.GF.state.user = 'op';
  assert.equal(h.GF.ownsTask({ owner: 'op' }), true);
  assert.equal(h.GF.ownsTask({ owner: 'op2', helpers: ['x', 'op'] }), true);
  assert.equal(h.GF.ownsTask({ owner: 'op2' }), false);
  assert.equal(h.GF.ownsTask({ owner: 'op2', helpers: [] }), false);
  // No helpers key at all is the common shape from the API; must not throw.
  assert.equal(h.GF.ownsTask({ owner: 'op2', helpers: undefined }), false);
  // The `!!t &&` guard: GF.can('edit') is called with the result of GF.task(),
  // which is undefined for a stale id after a re-render.
  assert.equal(h.GF.ownsTask(undefined), false);
  assert.equal(h.GF.ownsTask(null), false);
  h.close();
});

test('operator: can create, can only edit and re-status its OWN tasks, can never delete', () => {
  const h = withRoster();
  h.GF.state.user = 'op';
  const own = { owner: 'op' };
  const helping = { owner: 'op2', helpers: ['op'] };
  const other = { owner: 'op2' };

  assert.equal(h.GF.can('create'), true);
  assert.equal(h.GF.can('team'), false);

  assert.equal(h.GF.can('edit', own), true);
  assert.equal(h.GF.can('edit', helping), true);
  assert.equal(h.GF.can('edit', other), false);

  assert.equal(h.GF.can('status', own), true);
  assert.equal(h.GF.can('status', helping), true);
  assert.equal(h.GF.can('status', other), false);

  // deleteAny is unconditional — an operator cannot delete even its own task.
  // That asymmetry against 'edit' is deliberate (a deleted task loses its
  // audit trail) and is the single most likely thing to be "helpfully" changed.
  assert.equal(h.GF.can('delete', own), false);
  assert.equal(h.GF.can('delete', other), false);
  h.close();
});

test('every role in GF.PERMS marked editAny gets the full write row', () => {
  const h = withRoster();
  // Written against the table itself: a role added to GF.PERMS with a
  // hand-typed row that forgets a flag fails here instead of shipping.
  const roles = Object.keys(h.GF.PERMS);
  assert.equal(roles.length >= 12, true, 'the role table shrank unexpectedly');

  for (const role of roles) {
    h.GF.PEOPLE.subject = { name: 'Subject', role };
    h.GF.state.user = 'subject';
    const p = h.GF.PERMS[role];
    const other = { owner: 'op' };

    assert.equal(h.GF.can('create'), !!p.create, `${role}: create`);
    assert.equal(h.GF.can('team'), !!p.team, `${role}: team`);
    assert.equal(h.GF.can('delete', other), !!p.deleteAny, `${role}: delete`);
    assert.equal(h.GF.can('edit', other), !!p.editAny, `${role}: edit someone else's task`);
    // Own tasks are editable regardless of editAny.
    assert.equal(h.GF.can('edit', { owner: 'subject' }), true, `${role}: edit own task`);
    assert.equal(h.GF.can('status', other), p.status === 'any', `${role}: status on someone else's task`);
    assert.equal(h.GF.can('status', { owner: 'subject' }), true, `${role}: status on own task`);
  }
  h.close();
});

test('GF.can returns false for an unrecognised action instead of throwing or defaulting to allow', () => {
  const h = withRoster();
  h.GF.state.user = 'ceo';   // the most privileged role available
  assert.equal(h.GF.can('publish', { owner: 'ceo' }), false);
  assert.equal(h.GF.can(undefined, { owner: 'ceo' }), false);
  assert.equal(h.GF.can(''), false);
  h.close();
});

test('GF.isExec is exactly owner/ceo/coo/admin — managers are NOT executives', () => {
  const h = withRoster();
  // Managers already hold every task permission, so the only thing this set
  // controls is access to the cross-department Executive Overview. Widening it
  // by accident would expose other departments' metrics to a department lead.
  const expectExec = ['owner', 'ceo', 'coo', 'admin'];
  for (const role of Object.keys(h.GF.PERMS)) {
    h.GF.PEOPLE.subject = { name: 'S', role };
    h.GF.state.user = 'subject';
    assert.equal(h.GF.isExec(), expectExec.includes(role), `${role}: isExec`);
  }
  // qp holds _FULL task perms but is deliberately not an executive.
  assert.deepEqual(h.GF.PERMS.qp, h.GF.PERMS.ceo);
  h.GF.PEOPLE.subject = { name: 'S', role: 'qp' };
  h.GF.state.user = 'subject';
  assert.equal(h.GF.isExec(), false);
  h.close();
});

/* ── The gate as applied: GF.setStatus ──────────────────────────────── */

function withTasks() {
  const h = withRoster();
  h.GF.state.tasks = [
    { id: 'T-OWN', title: 'mine', owner: 'op', weekId: 4, status: 'pending' },
    { id: 'T-OTHER', title: 'theirs', owner: 'op2', weekId: 4, status: 'pending' },
  ];
  return h;
}

test('GF.setStatus applies a permitted change, reports true, and persists it', () => {
  const h = withTasks();
  h.GF.state.user = 'op';
  assert.equal(h.GF.setStatus('T-OWN', 'working'), true);
  assert.equal(h.GF.task('T-OWN').status, 'working');
  // GF.store.save() is the localStorage fallback path; integrate.js overrides
  // the API side but not this write, so it still runs on every status change.
  const saved = JSON.parse(h.window.localStorage.getItem('gf_tasks_v1'));
  assert.equal(saved.find(t => t.id === 'T-OWN').status, 'working');
  h.close();
});

test('GF.setStatus refuses a change the role may not make and does NOT mutate the task', () => {
  const h = withTasks();
  h.GF.state.user = 'op';
  // The deny path calls GF.denyToast(); with no #toasts container in the DOM
  // GF.toast returns early, so nothing is scheduled and nothing is asserted
  // about the toast here — only that the refusal is total.
  assert.equal(h.GF.setStatus('T-OTHER', 'done'), false);
  assert.equal(h.GF.task('T-OTHER').status, 'pending');
  h.close();
});

test('GF.setStatus rejects a status outside GF.STATUS and an unknown task id', () => {
  const h = withTasks();
  h.GF.state.user = 'qa';   // full permissions, so only the value check can fail
  assert.equal(h.GF.setStatus('T-OWN', 'completed'), false, "'completed' is the BACKEND enum, not a GF status");
  assert.equal(h.GF.setStatus('T-OWN', ''), false);
  assert.equal(h.GF.setStatus('no-such-task', 'done'), false);
  assert.equal(h.GF.task('T-OWN').status, 'pending');
  h.close();
});

test('GF.setStatus returns false for a no-op change — callers use that to skip a re-render', () => {
  const h = withTasks();
  h.GF.state.user = 'qa';
  // false therefore means BOTH "refused" and "already there". render.js's
  // pickStatus relies on the second meaning; anything treating false as an
  // error would surface a spurious failure every time a user re-picks the
  // status a task already has.
  assert.equal(h.GF.setStatus('T-OWN', 'pending'), false);
  assert.equal(h.GF.setStatus('T-OWN', 'done'), true);
  assert.equal(h.GF.setStatus('T-OWN', 'done'), false);
  h.close();
});

test('GF.cycleStatus walks GF.STATUS_ORDER and wraps from done back to pending', () => {
  const h = withTasks();
  h.GF.state.user = 'qa';
  // cycleStatus repaints on every step, so the two render hooks it calls are
  // replaced with counters. Nothing about the cycle logic is stubbed — the
  // order and the wraparound come from the real GF.STATUS_ORDER.
  let painted = 0;
  h.GF.render = { panels: () => { painted++; }, telemetry: () => { painted++; } };

  const seen = [h.GF.task('T-OWN').status];
  for (let i = 0; i < h.GF.STATUS_ORDER.length; i++) {
    h.GF.cycleStatus('T-OWN');
    seen.push(h.GF.task('T-OWN').status);
  }
  assert.deepEqual(seen, ['pending', 'working', 'review', 'stuck', 'postponed', 'done', 'pending']);
  assert.equal(painted, h.GF.STATUS_ORDER.length * 2);
  h.close();
});

test('GF.cycleStatus on a task the role may not touch neither mutates nor repaints', () => {
  const h = withTasks();
  h.GF.state.user = 'op';
  let painted = 0;
  h.GF.render = { panels: () => { painted++; }, telemetry: () => { painted++; } };
  h.GF.cycleStatus('T-OTHER');
  assert.equal(h.GF.task('T-OTHER').status, 'pending');
  assert.equal(painted, 0, 'the deny path must return before the render calls');
  h.close();
});

test('GF.toggleDone flips to done and back to working, never to the original status', () => {
  const h = withTasks();
  h.GF.state.user = 'qa';
  h.GF.render = { panels: () => {}, telemetry: () => {} };
  // 'pending' -> 'done' -> 'working'. The un-done side is hard-coded to
  // 'working', so a checkbox untick does NOT restore 'pending' or 'stuck'.
  // Pinned because it looks like a toggle and is not one.
  h.GF.toggleDone('T-OWN');
  assert.equal(h.GF.task('T-OWN').status, 'done');
  h.GF.toggleDone('T-OWN');
  assert.equal(h.GF.task('T-OWN').status, 'working');
  h.close();
});

test('GF.task resolves subtask rows out of GF.state.children as well as the flat list', () => {
  const h = withTasks();
  // The tree rows (theme -> document -> version) live under GF.state.children
  // keyed by parent id, never in GF.state.tasks; every status/edit handler
  // opened from a tree row goes through GF.task() to find its target.
  h.GF.state.children = { 'T-OWN': [{ id: 'T-CHILD', title: 'child', owner: 'op', parentId: 'T-OWN' }] };
  assert.equal(h.GF.task('T-CHILD').title, 'child');
  assert.equal(h.GF.task('T-MISSING'), undefined);
  // A missing children map must not throw — it is `{}` until integrate.js
  // builds it from the /tasks payload.
  h.GF.state.children = undefined;
  assert.equal(h.GF.task('T-CHILD'), undefined);
  h.close();
});
