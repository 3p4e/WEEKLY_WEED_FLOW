/* datepicker.js — the app's date field.

   The behaviour under test is not "does a calendar render" but "which day
   does it call today". This app's today belongs to the facility
   (Europe/Skopje); the browser's local day is the READER's day, and the two
   differ for anyone in another zone and for everyone during the nightly
   window where Skopje and UTC sit on different dates. A picker that opens on
   the wrong day offers the wrong day as the obvious click, onto records like
   a harvest date or a manufacture date printed on a certificate. */
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
  const h = loadGF({ files: ['data.js', 'core.js', 'datepicker.js'], preScript: PRE, now: now });
  if (user) h.window.GF.API.user = user;
  return h;
}

test('facilityToday() answers in the facility zone', () => {
  // Harness clock: Thursday 2026-07-30 09:15 +02:00, runner TZ Europe/Skopje.
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  assert.equal(w.GF.facilityToday(), '2026-07-30');
});

test('it follows the FACILITY zone, not the browser — they can be different days', () => {
  // 23:30 in Skopje is already the next day in Kiritimati (UTC+14). The
  // browser says the 30th; the facility zone says the 31st. A reader in
  // another country is exactly this case, and the record belongs to the
  // facility's day, not to theirs.
  const w = load({ facility_tz: 'Pacific/Kiritimati' }, '2026-07-30T23:30:00+02:00').window;
  assert.equal(w.GF.todayISO(), '2026-07-30', 'the browser is on the 30th');
  assert.equal(w.GF.facilityToday(), '2026-07-31', 'the facility is on the 31st');
});

test('it survives the nightly window where Skopje and UTC disagree', () => {
  // 00:30 Skopje = 22:30 UTC the PREVIOUS day. This is the documented hazard
  // that has already broken this project once, and the exact bug that was
  // live in cultivation-view.js: a UTC-rendered "today" stamped yesterday
  // onto every plant id created in these two hours.
  const w = load({ facility_tz: 'Europe/Skopje' }, '2026-07-31T00:30:00+02:00').window;
  assert.equal(w.GF.facilityToday(), '2026-07-31');
  const naiveUTC = new w.Date().toISOString().slice(0, 10);
  assert.equal(naiveUTC, '2026-07-30', 'precondition: UTC really is on the previous day here');
  assert.notEqual(w.GF.facilityToday(), naiveUTC, 'the picker must not use the UTC day');
});

test('falls back to the date the server computed when the zone is unusable', () => {
  const w = load({ facility_tz: 'Not/AZone', facility_today: '2026-03-04' }).window;
  assert.equal(w.GF.facilityToday(), '2026-03-04');
});

test('falls back to the browser day when the server said nothing', () => {
  // The pre-existing behaviour of the whole app — the worst case is what it
  // always did, never an exception.
  const w = load({}).window;
  assert.equal(w.GF.facilityToday(), w.GF.todayISO());
});

test('a served date that is not a date is rejected rather than rendered', () => {
  const w = load({ facility_tz: '', facility_today: 'yesterday-ish' }).window;
  assert.equal(w.GF.facilityToday(), w.GF.todayISO());
});

test('dateField keeps the hidden-input contract every caller reads', () => {
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('hv-c-date', { value: '2026-04-07' });
  const inp = w.document.getElementById('hv-c-date');
  assert.ok(inp, 'the id must still resolve to an input');
  assert.equal(inp.value, '2026-04-07', 'GF.$(id).value must read the ISO date');
  // …and the visible label is the human format, not the ISO string.
  assert.match(w.document.getElementById('hv-c-date-btn').textContent, /07\.04\.2026/);
});

test('an empty field shows its placeholder and holds no value', () => {
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('d1', { placeholder: 'Pick a date' });
  assert.equal(w.document.getElementById('d1').value, '');
  assert.match(w.document.getElementById('d1-btn').textContent, /Pick a date/);
});

test('opening an EMPTY field lands on the facility today and highlights it — without choosing it', () => {
  // The distinction the owner asked for: today is where the calendar opens,
  // not a value silently written into a record nobody touched. An expiry date
  // defaulted to today is a real, wrong claim.
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('d1', {});
  w.GF.openDatePicker('d1', null);
  const today = w.GF.facilityToday();
  const cell = w.document.querySelector('.dp-cell.dp-today');
  assert.ok(cell, 'today must be marked in the grid');
  assert.equal(cell.dataset.v, today);
  assert.equal(w.document.getElementById('d1').value, '', 'opening must not write a value');
});

test('opening a FILLED field lands on the chosen date and marks it selected', () => {
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('d1', { value: '2026-01-15' });
  w.GF.openDatePicker('d1', null);
  const on = w.document.querySelector('.dp-cell.on');
  assert.equal(on.dataset.v, '2026-01-15');
});

test('picking a day writes the ISO value and updates the label', () => {
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('d1', {});
  w.GF.openDatePicker('d1', null);
  w.GF.pickDate('d1', '2026-06-09');
  assert.equal(w.document.getElementById('d1').value, '2026-06-09');
  assert.match(w.document.getElementById('d1-btn').textContent, /09\.06\.2026/);
});

test('onPick fires with the chosen date, and with empty on clear', () => {
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  const seen = [];
  w.document.body.innerHTML = w.GF.dateField('d1', { onPick: (v) => seen.push(v) });
  w.GF.openDatePicker('d1', null);
  w.GF.pickDate('d1', '2026-06-09');
  w.GF.openDatePicker('d1', null);
  w.GF.pickDate('d1', '');
  assert.deepEqual(seen, ['2026-06-09', '']);
  assert.equal(w.document.getElementById('d1').value, '');
});

test('min/max disable the days outside the allowed span', () => {
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('d1', { value: '2026-05-10', min: '2026-05-05', max: '2026-05-20' });
  w.GF.openDatePicker('d1', null);
  const cell = v => w.document.querySelector(`.dp-cell[data-v="${v}"]`);
  assert.ok(cell('2026-05-04').disabled, 'a day before min must not be pickable');
  assert.ok(!cell('2026-05-10').disabled);
  assert.ok(cell('2026-05-21').disabled, 'a day after max must not be pickable');
});

test('an impossible date is not rolled over into a real one', () => {
  // new Date(2026,1,31) silently becomes 3 March. A rolled-over date in a GxP
  // record is the same class of wrong fact as a fabricated one, so the field
  // shows nothing rather than a date the user never picked.
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  assert.equal(w.GF.fmtDateHuman('2026-02-31'), '');
  assert.equal(w.GF.fmtDateHuman('not-a-date'), '');
  assert.equal(w.GF.fmtDateHuman(''), '');
});

test('syncDate refreshes the label after a direct .value write', () => {
  // Writers that set GF.$(id).value directly (the pattern chooser.js also
  // supports) must be able to make the control catch up.
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('d1', {});
  w.document.getElementById('d1').value = '2026-12-01';
  w.GF.syncDate('d1');
  assert.match(w.document.getElementById('d1-btn').textContent, /01\.12\.2026/);
});

test('the Today button offers the facility day', () => {
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('d1', {});
  w.GF.openDatePicker('d1', null);
  const foot = w.document.querySelector('.dp-foot').textContent;
  assert.match(foot, new RegExp(w.GF.fmtDateHuman(w.GF.facilityToday()).replace(/\./g, '\\.')));
});

test('the grid is Monday-first, matching the facility week', () => {
  const w = load({ facility_tz: 'Europe/Skopje' }).window;
  w.document.body.innerHTML = w.GF.dateField('d1', { value: '2026-04-15' });
  w.GF.openDatePicker('d1', null);
  const dows = [...w.document.querySelectorAll('.dp-dow')].map(e => e.textContent);
  assert.equal(dows[0], 'Mon');
  assert.equal(dows[6], 'Sun');
  // 1 April 2026 is a Wednesday → two leading pad cells.
  assert.equal(w.document.querySelectorAll('.dp-pad').length, 2);
});
