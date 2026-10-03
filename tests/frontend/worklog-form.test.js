'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/worklog.js — the Log Work modal must not throw away what the user
   has typed.

   THE BUG, found 2026-07-30 when the e2e suite failed three times in a row on
   `worklog-report.spec.js`:

   `_renderWorklog()` rebuilds the entire modal body with `innerHTML = …`,
   which destroys and recreates #wl-date / #wl-start / #wl-end / #wl-hours /
   #wl-note with their template DEFAULTS. Four callers were doing that while
   the user was mid-entry:

     • openWorklog() renders once immediately (list = "Loading…"), then again
       when GET /tasks/{id}/sessions resolves. On a developer machine that
       second render lands before a human can type. Under CI load it lands
       in the middle of the form, and the entry silently reverts to
       today / 09:00 / no hours — so the submit posted a Thursday session
       where the test had asked for a Saturday, or failed validation and
       posted nothing at all.
     • setProgress() and progressMarkDone() re-render after a quick-set
       click. Not a race at all, and reproducible by hand: type a date and
       hours, click 75%, watch both vanish.
     • deleteSession() re-renders after removing a row.

   The failure is silent in the worst way — no error, no toast, the form just
   quietly holds different values than the ones that were typed, and the user
   finds out by reading back a work record that says the wrong day.

   The fix preserves the fields by DEFAULT and makes the single caller that
   genuinely wants them cleared (submitWorklog, after the session is saved)
   ask for it explicitly. These tests pin that direction: a new caller must be
   safe without knowing this history, and clearing must stay opt-in.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const FILES = ['data.js', 'core.js', 'datepicker.js', 'worklog.js'];

/* worklog.js sits at the end of a chain of bare top-level consts that classic
 * <script> tags share (AUDIT_ROLES in audit-view.js, itself ELEVATED_ROLES from
 * integrate.js), and loading that whole chain drags in views.js, voice.js and
 * api.js for globals this file never touches. AUDIT_ROLES is used in exactly
 * one place here — whether a session row offers a delete button to someone who
 * did not log it — which none of these assertions exercise. So it is declared
 * as a `const` in a pre-script, the same way the real page declares it, and
 * deliberately NOT kept in sync with the production list: if a future test does
 * start depending on the elevation rule, it must load the real source rather
 * than trust this. */
const PRE = `
  const AUDIT_ROLES = ['ADMIN'];
  window.GF = window.GF || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.PEOPLE = {};
  window.GF.render = { panels: function () {}, telemetry: function () {} };
  window.GF.setStatus = function () { return true; };
`;

const TASK = {
  id: 'T-W', title: 'Swab room C180', weekId: 4, dept: 'qc',
  status: 'pending', days: ['Thu'], progressPct: 0,
};

function open() {
  const h = loadGF({ files: FILES, preScript: PRE });
  const { GF } = h;
  GF.state.tasks = [Object.assign({}, TASK)];
  GF.API = Object.assign(GF.API || {}, {
    user: { id: 'U-1', role: 'ADMIN' },
    // Deliberately never settles: this is the exact window the bug lived in —
    // the modal is open and interactive while the session list is still in
    // flight. Resolving it is done per-test, by hand, at the chosen moment.
    sessions: () => new Promise(() => {}),
  });
  GF.WWF.openWorklog('T-W');
  return h;
}

/** Type into the form the way a user (or Playwright) does. */
function fill(h, values) {
  for (const [id, v] of Object.entries(values)) {
    const el = h.window.document.getElementById(id);
    assert.ok(el, `#${id} is not in the modal — the form markup changed`);
    el.value = v;
  }
}

const read = (h, id) => (h.window.document.getElementById(id) || {}).value;

test('the entry fields exist as soon as the modal opens, before sessions load', () => {
  // If they did not, the race below could not happen — and neither could the
  // user's. This is the precondition the rest of the file depends on.
  const h = open();
  assert.equal(read(h, 'wl-date'), h.GF.todayISO());
  assert.equal(read(h, 'wl-start'), '09:00');
  h.close();
});

test('the session list arriving does not wipe a half-typed entry', () => {
  const h = open();
  fill(h, { 'wl-date': '2026-07-25', 'wl-start': '10:00', 'wl-hours': '2.5', 'wl-note': 'weekend swab' });

  // The GET resolves mid-form. This is the exact sequence that failed in CI.
  h.GF.WWF._worklog.sessions = [];
  h.GF.WWF._renderWorklog();

  assert.equal(read(h, 'wl-date'), '2026-07-25',
    'the date the user typed was replaced by today — a Saturday session would log as a weekday');
  assert.equal(read(h, 'wl-start'), '10:00');
  assert.equal(read(h, 'wl-hours'), '2.5',
    'hours were cleared, so the submit fails validation and logs nothing at all');
  assert.equal(read(h, 'wl-note'), 'weekend swab');
  h.close();
});

test('a rendered session list really did replace the loading state', () => {
  // Guards the test above from passing vacuously: if _renderWorklog had
  // silently no-opped, the fields would survive for the wrong reason.
  const h = open();
  assert.match(h.window.document.getElementById('wl-list').innerHTML, /Loading|Се вчитува/);
  h.GF.WWF._worklog.sessions = [];
  h.GF.WWF._renderWorklog();
  assert.doesNotMatch(h.window.document.getElementById('wl-list').innerHTML, /Loading|Се вчитува/);
  h.close();
});

test('setting completion % does not wipe a half-typed entry', () => {
  // Same destruction, no race required — a plain click reproduces it.
  const h = open();
  fill(h, { 'wl-date': '2026-07-25', 'wl-hours': '2.5' });
  h.GF.WWF.progressMarkDone('T-W');
  assert.equal(read(h, 'wl-date'), '2026-07-25');
  assert.equal(read(h, 'wl-hours'), '2.5');
  h.close();
});

test('clearing the form stays opt-in, and still works when asked for', () => {
  // The counterpart: after a session is actually saved, leaving the old values
  // in place would invite logging the same work twice. submitWorklog is the
  // only caller allowed to ask for this.
  const h = open();
  fill(h, { 'wl-date': '2026-07-25', 'wl-start': '10:00', 'wl-hours': '2.5', 'wl-note': 'weekend swab' });
  h.GF.WWF._renderWorklog({ resetForm: true });
  assert.equal(read(h, 'wl-date'), h.GF.todayISO());
  assert.equal(read(h, 'wl-start'), '09:00');
  assert.equal(read(h, 'wl-hours'), '');
  assert.equal(read(h, 'wl-note'), '');
  h.close();
});

test('submitWorklog is the caller that clears, and it clears only on success', async () => {
  // Pins the direction of the default: were submitWorklog to stop passing
  // resetForm, a saved session would leave its own values sitting in the form.
  const h = open();
  const posted = [];
  h.GF.API.addSession = async (taskId, body) => {
    posted.push([taskId, body]);
    return { id: 'S-1', hours: 2.5, classification: 'weekend', started_at: body.started_at, user_id: 'U-1' };
  };
  h.GF.WWF._worklog.sessions = [];
  h.GF.WWF._renderWorklog();
  fill(h, { 'wl-date': '2026-07-25', 'wl-start': '10:00', 'wl-hours': '2.5' });

  await h.GF.WWF.submitWorklog();

  assert.deepEqual(posted.map(([, b]) => b.started_at), ['2026-07-25T10:00:00'],
    'the values that reached the API are not the ones that were typed');
  assert.equal(read(h, 'wl-date'), h.GF.todayISO(), 'the form was not cleared after a successful log');
  h.close();
});

test('a failed submit leaves the entry intact to retry', () => {
  // Clearing on failure would make the user retype everything to find out
  // whether the second attempt fares any better.
  const h = open();
  h.GF.API.addSession = async () => { throw new Error('boom'); };
  h.GF.WWF._worklog.sessions = [];
  h.GF.WWF._renderWorklog();
  fill(h, { 'wl-date': '2026-07-25', 'wl-start': '10:00', 'wl-hours': '2.5' });

  return h.GF.WWF.submitWorklog().then(() => {
    assert.equal(read(h, 'wl-date'), '2026-07-25');
    assert.equal(read(h, 'wl-hours'), '2.5');
    h.close();
  });
});
