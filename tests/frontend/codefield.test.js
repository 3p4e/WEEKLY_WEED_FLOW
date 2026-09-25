/* codefield.js — an input whose constant leading part is already there.

   The behaviour that matters is not "does a prefix appear" but "can the user
   end up with a code that has lost or mangled its head". A QCSOP_012 that
   became 012, or QCSOP-012 where the house writes QCSOP_012, is a code that
   looks plausible, sorts differently and matches nothing. */
const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.state = { lang: 'en' };
`;

const load = () => loadGF({ files: ['data.js', 'core.js', 'codefield.js'], preScript: PRE });

function field(w, cfg) {
  w.document.body.innerHTML = w.GF.codeField('c1', cfg);
  return w.document.getElementById('c1');
}

test('an empty field starts with the constant head already typed', () => {
  const w = load().window;
  assert.equal(field(w, { prefix: 'QCSOP_' }).value, 'QCSOP_');
});

test('the whole code — head included — is what callers read back', () => {
  const w = load().window;
  const el = field(w, { prefix: 'QCSOP_' });
  el.value = 'QCSOP_012';
  assert.equal(w.document.getElementById('c1').value, 'QCSOP_012');
});

test('an existing code is shown as recorded, not rewritten to the convention', () => {
  // This control completes a code being entered; it does not retro-fit one
  // already stored under an older spelling.
  const w = load().window;
  assert.equal(field(w, { prefix: 'QCSOP_', value: 'QCSOP-999' }).value, 'QCSOP-999');
});

test('clicking anywhere in the head moves the caret past it', () => {
  // "the pointer will continue on that spot onward" — the user taps the field
  // and types the number, without landing inside the fixed part.
  const w = load().window;
  const el = field(w, { prefix: 'QCSOP_' });
  el.setSelectionRange(2, 2);
  w.GF._codeCaret('c1');
  assert.equal(el.selectionStart, 6);
  assert.equal(el.selectionEnd, 6);
});

test('a caret the user placed in their OWN typing is left alone', () => {
  const w = load().window;
  const el = field(w, { prefix: 'QCSOP_' });
  el.value = 'QCSOP_012';
  el.setSelectionRange(8, 8);      // between the 1 and the 2
  w.GF._codeCaret('c1');
  assert.equal(el.selectionStart, 8, 'the caret must not jump out of the tail');
});

test('a selection is not collapsed under the user', () => {
  // Select-all then retype is a legitimate way to correct a code.
  const w = load().window;
  const el = field(w, { prefix: 'QCSOP_' });
  el.value = 'QCSOP_012';
  el.setSelectionRange(0, 9);
  w.GF._codeCaret('c1');
  assert.equal(el.selectionStart, 0);
  assert.equal(el.selectionEnd, 9);
});

test('backspacing into the head puts it back and keeps the tail', () => {
  const w = load().window;
  const el = field(w, { prefix: 'QCSOP_' });
  el.value = 'QCSOP012';           // the underscore was deleted
  w.GF._codeGuard('c1');
  assert.equal(el.value, 'QCSOP_012');
  assert.equal(el.selectionStart, 9, 'caret ends after what they had typed');
});

test('erasing the head entirely restores it without losing the number', () => {
  const w = load().window;
  const el = field(w, { prefix: 'QCSOP_' });
  el.value = '012';                // held backspace
  w.GF._codeGuard('c1');
  assert.equal(el.value, 'QCSOP_012');
});

test('a partially-eaten head is repaired, not doubled', () => {
  const w = load().window;
  const el = field(w, { prefix: 'QCSOP_' });
  el.value = 'SOP_012';            // 'QC' deleted from the front
  w.GF._codeGuard('c1');
  assert.equal(el.value, 'QCSOP_012');
});

test('a correct value is left completely untouched', () => {
  const w = load().window;
  const el = field(w, { prefix: 'QCSOP_' });
  el.value = 'QCSOP_012';
  w.GF._codeGuard('c1');
  assert.equal(el.value, 'QCSOP_012');
});

test('the tail is NOT shape-enforced — a real code the mask did not predict still goes in', () => {
  // The corpus carries annexes (QASOP_031_A10) and forms this app has never
  // seen. Rejecting one would be worse than accepting it.
  const w = load().window;
  const el = field(w, { prefix: 'QASOP_' });
  el.value = 'QASOP_031_A10';
  w.GF._codeGuard('c1');
  assert.equal(el.value, 'QASOP_031_A10');
});

test('with no prefix it behaves as an ordinary input', () => {
  // A field whose convention nobody has established must not acquire a
  // guessed one — it just takes what is typed.
  const w = load().window;
  const el = field(w, { prefix: '' });
  assert.equal(el.value, '');
  el.value = 'anything at all';
  w.GF._codeGuard('c1');
  w.GF._codeCaret('c1');
  assert.equal(el.value, 'anything at all');
});

test('the value and placeholder are escaped, like every other server value', () => {
  const w = load().window;
  const html = w.GF.codeField('c1', { prefix: '', value: '"><img src=x onerror=alert(1)>' });
  assert.ok(!html.includes('<img src=x'), 'raw markup must not reach the page');
});
