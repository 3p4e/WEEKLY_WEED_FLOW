'use strict';

/* ══════════════════════════════════════════════════════════════════════
   datepicker.js — the keyboard highlights, it does not choose.
   core.js — GF.todayDay is the facility's weekday, read live.

   Review 2026-09-27, FE-08: the arrow keys wrote straight into the hidden
   input. Open an empty expiry or retest date, press ↓ to glance at next
   week, dismiss with ✕ or Esc — and the field held that date, saved with
   the form, while onPick never fired, so the displayed date and the
   submitted state diverged. The file's own contract says highlighted is not
   chosen; only Enter or a click may write.

   FE-07: GF.todayDay was computed once at load from the browser's clock, so
   a tab open across midnight, or a reader in another zone, matched "today"
   tasks against the wrong weekday.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.state = { lang: 'en' };
  window.GF.API = { user: {} };
  window.GF.openModal = function (id) { var e = document.getElementById(id); if (e) e.classList.add('open'); };
  window.GF.closeModal = function (id) { var e = document.getElementById(id); if (e) e.classList.remove('open'); };
`;

function load(user, now) {
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js'], preScript: PRE, now });
  h.window.GF.API.user = user || { facility_tz: 'Europe/Skopje' };
  return h;
}

const key = (w, k) => w.document.dispatchEvent(new w.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));

test('arrow keys move the highlight only — dismissing afterwards leaves the field untouched', () => {
  const h = load();
  const w = h.window;
  const picks = [];
  w.document.body.innerHTML = w.GF.dateField('exp', { onPick: (v) => picks.push(v) });
  w.GF.openDatePicker('exp', null);
  key(w, 'ArrowDown');
  key(w, 'ArrowRight');
  // Harness today is 2026-07-30 → +7 → 08-06 → +1 → 08-07.
  const cursor = w.document.querySelector('.dp-cell.dp-cursor');
  assert.ok(cursor, 'the keyboard position is shown');
  assert.equal(cursor.dataset.v, '2026-08-07');
  assert.equal(w.document.querySelector('.dp-cell.on'), null, 'nothing is CHOSEN yet');
  assert.equal(w.document.getElementById('exp').value, '', 'the input is not written by navigation');
  w.GF.closeModal('gf-datepicker');
  assert.equal(w.document.getElementById('exp').value, '', 'dismissing keeps the field empty');
  assert.match(w.document.getElementById('exp-btn').textContent, /Pick a date/);
  assert.deepEqual(picks, [], 'onPick never fired');
  h.close();
});

test('Enter picks the highlighted day, writing the value and firing onPick once', () => {
  const h = load();
  const w = h.window;
  const picks = [];
  w.document.body.innerHTML = w.GF.dateField('exp', { onPick: (v) => picks.push(v) });
  w.GF.openDatePicker('exp', null);
  key(w, 'ArrowDown');
  key(w, 'Enter');
  assert.equal(w.document.getElementById('exp').value, '2026-08-06');
  assert.deepEqual(picks, ['2026-08-06']);
  assert.equal(w.document.getElementById('gf-datepicker').classList.contains('open'), false, 'the picker closed');
  h.close();
});

test('the highlight starts on the chosen date when there is one, and on today otherwise', () => {
  const h = load();
  const w = h.window;
  w.document.body.innerHTML = w.GF.dateField('d1', { value: '2026-03-10' });
  w.GF.openDatePicker('d1', null);
  assert.equal(w.document.querySelector('.dp-cell.dp-cursor').dataset.v, '2026-03-10');
  key(w, 'ArrowLeft');
  assert.equal(w.document.querySelector('.dp-cell.dp-cursor').dataset.v, '2026-03-09');
  assert.equal(w.document.getElementById('d1').value, '2026-03-10', 'the chosen date is untouched by the move');
  w.GF.closeModal('gf-datepicker');
  w.document.body.innerHTML = w.GF.dateField('d2', {});
  w.GF.openDatePicker('d2', null);
  assert.equal(w.document.querySelector('.dp-cell.dp-cursor').dataset.v, w.GF.facilityToday());
  h.close();
});

test('the highlight cannot leave the min/max span, and Enter respects it too', () => {
  const h = load();
  const w = h.window;
  w.document.body.innerHTML = w.GF.dateField('d1', { value: '2026-05-20', max: '2026-05-20' });
  w.GF.openDatePicker('d1', null);
  key(w, 'ArrowRight');
  assert.equal(w.document.querySelector('.dp-cell.dp-cursor').dataset.v, '2026-05-20', 'stays at the edge');
  key(w, 'Enter');
  assert.equal(w.document.getElementById('d1').value, '2026-05-20');
  h.close();
});

test('a click on a day is still the other explicit way to choose', () => {
  const h = load();
  const w = h.window;
  w.document.body.innerHTML = w.GF.dateField('d1', {});
  w.GF.openDatePicker('d1', null);
  w.document.querySelector('.dp-cell[data-v="2026-07-14"]').click();
  assert.equal(w.document.getElementById('d1').value, '2026-07-14');
  h.close();
});

test('GF.todayDay is the facility\'s weekday, read live, not the browser\'s at load', () => {
  // 23:30 Thursday in Skopje is already Friday in Kiritimati (UTC+14).
  const h = load({ facility_tz: 'Pacific/Kiritimati' }, '2026-07-30T23:30:00+02:00');
  const w = h.window;
  assert.equal(w.GF.todayISO(), '2026-07-30', 'the browser says Thursday');
  assert.equal(w.GF.todayDay, 'Fri', 'the facility says Friday');
  // And it follows the session: switching the facility zone changes the answer.
  w.GF.API.user = { facility_tz: 'Europe/Skopje' };
  assert.equal(w.GF.todayDay, 'Thu');
  h.close();
});
