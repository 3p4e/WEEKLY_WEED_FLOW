'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/voice.js — GF.voice.dictate() must track WHICH field is recording,
   not just THAT some field is recording.

   Before the fix, a single module-global `_rec` meant "something is
   recording", with no record of what. Clicking mic B while mic A was
   recording stopped A's recognizer but reset B's UI (a no-op — B was never
   on), leaving A's button stuck showing "recording" forever and swallowing
   the click on B; the user had to click B a second time to actually start
   it. Reproducible in the add-task modal, which has two dictation triggers.

   jsdom implements neither SpeechRecognition nor webkitSpeechRecognition, so
   — same as any other browser-API boundary this suite stubs (GF.export's
   _download for Blob/createObjectURL) — a minimal fake recognizer stands in
   for the real one. Everything that decides which field's UI updates and
   which recognizer starts next is the real dictate() source.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

class FakeRecognizer {
  constructor() {
    this.onresult = null; this.onerror = null; this.onend = null;
    this.started = false; this.stopped = false;
  }
  start() { this.started = true; }
  stop() { this.started = false; this.stopped = true; }   // real API fires 'onend' asynchronously — tests trigger it explicitly where relevant
}

function load() {
  const h = loadGF({
    files: ['data.js', 'core.js', 'voice.js'],
    bodyHtml: '<input id="fieldA"><button id="mic-fieldA"></button>' +
              '<input id="fieldB"><button id="mic-fieldB"></button>',
  });
  h.window.SpeechRecognition = FakeRecognizer;
  return h;
}

function micIsRecording(w, inputId) {
  return w.document.getElementById('mic-' + inputId).classList.contains('rec');
}

test('starting dictation on field B while field A is recording stops A\'s UI and starts B in the same click', () => {
  const h = load();
  const w = h.window;

  w.GF.voice.dictate('fieldA');
  assert.equal(w.GF.voice._recFor, 'fieldA');
  assert.equal(micIsRecording(w, 'fieldA'), true);
  const recA = w.GF.voice._rec;

  // Click mic B — field A is still recording.
  w.GF.voice.dictate('fieldB');

  assert.equal(recA.stopped, true, 'A\'s recognizer must actually be stopped');
  assert.equal(micIsRecording(w, 'fieldA'), false,
    'A\'s mic button must not be left stuck showing "recording" — the OLD bug set B\'s UI to false instead of A\'s, a no-op that left A stuck on');
  assert.equal(micIsRecording(w, 'fieldB'), true,
    'clicking B must start B in this SAME click, not require a second click');
  assert.equal(w.GF.voice._recFor, 'fieldB');
  assert.notEqual(w.GF.voice._rec, recA, 'a fresh recognizer must be recording for B, not the (stopped) one for A');
  h.close();
});

test('clicking the SAME recording field\'s mic again just stops it (no restart)', () => {
  const h = load();
  const w = h.window;

  w.GF.voice.dictate('fieldA');
  const recA = w.GF.voice._rec;
  w.GF.voice.dictate('fieldA');   // same field, second click

  assert.equal(recA.stopped, true);
  assert.equal(w.GF.voice._rec, null);
  assert.equal(w.GF.voice._recFor, null);
  assert.equal(micIsRecording(w, 'fieldA'), false);
  h.close();
});

test('a late-firing onend from a superseded recognizer does not clobber the new one\'s state', () => {
  // The existing "only clear _rec if it still points at THIS recognizer"
  // guard on rec.onend must keep working now that _recFor is also tracked:
  // A's belated onend must not blank out B's _rec/_recFor or flip B's UI off.
  const h = load();
  const w = h.window;

  w.GF.voice.dictate('fieldA');
  const recA = w.GF.voice._rec;
  w.GF.voice.dictate('fieldB');
  const recB = w.GF.voice._rec;

  // Simulate the real API's asynchronous 'end' event arriving late for A,
  // AFTER B has already started.
  recA.onend();

  assert.equal(w.GF.voice._rec, recB, 'B\'s in-progress recognizer must survive A\'s late onend');
  assert.equal(w.GF.voice._recFor, 'fieldB');
  assert.equal(micIsRecording(w, 'fieldB'), true, 'B must still show as recording');
  h.close();
});

test('dictate() writes transcript text into the field it was actually invoked for', () => {
  const h = load();
  const w = h.window;
  w.GF.voice.dictate('fieldA');
  const recA = w.GF.voice._rec;
  recA.onresult({ resultIndex: 0, results: [{ 0: { transcript: 'hello' }, isFinal: true, length: 1 }] });
  assert.equal(w.document.getElementById('fieldA').value, 'hello');
  h.close();
});
