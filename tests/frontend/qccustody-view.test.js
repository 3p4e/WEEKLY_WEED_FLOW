'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qccustody-view.js — chain-of-custody transfer logging.

   Logging a transfer PATCHes onto the chain-of-custody record for a
   sample — the one record type this view exists to protect. Unlike the
   backend guard on custody.py (to_user_id / to_location), the log-transfer
   form here has its own field pair: transfer_type + to_location. Clicking
   "Log transfer" with both blank must not reach the API at all.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
  window.GF.render = { all: function () {} };
  window.GF.viewHead = function () { return '<head></head>'; };
  window.GF.API = { user: { role: 'QC_MGR' } };
`;

function load() {
  return loadGF({ files: ['data.js', 'core.js', 'qccustody-view.js'], preScript: PRE });
}

test('qcCusLogTransfer refuses an all-blank submit — no API call, error toast', async () => {
  const h = load();
  const w = h.window;
  const fields = { 'qcu-xtype': '', 'qcu-xto': '', 'qcu-xreason': '', 'qcu-xcond': '', 'qcu-xok': '' };
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  let apiCalled = false;
  w.GF.API.qcAddCustody = async () => { apiCalled = true; return {}; };
  w.GF.API.qcCustody = async () => [];
  let toastMsg = null, toastType = null;
  w.GF.toast = (msg, type) => { toastMsg = msg; toastType = type; };
  await w.GF.WWF.qcCusLogTransfer('sample1');
  assert.equal(apiCalled, false, 'qcAddCustody must not be called with everything blank');
  assert.ok(toastMsg, 'an error toast is shown');
  assert.equal(toastType, 'error', 'toast is an error toast');
});

test('qcCusLogTransfer refuses when only one of transfer_type / to_location is set', async () => {
  const h = load();
  const w = h.window;
  const fields = { 'qcu-xtype': 'FIELD_TO_LAB', 'qcu-xto': '', 'qcu-xreason': '', 'qcu-xcond': '', 'qcu-xok': '' };
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  let apiCalled = false;
  w.GF.API.qcAddCustody = async () => { apiCalled = true; return {}; };
  w.GF.API.qcCustody = async () => [];
  let toastType = null;
  w.GF.toast = (msg, type) => { toastType = type; };
  await w.GF.WWF.qcCusLogTransfer('sample1');
  assert.equal(apiCalled, false, 'qcAddCustody must not be called with to_location missing');
  assert.equal(toastType, 'error', 'toast is an error toast');
});

test('qcCusLogTransfer sends the transfer once transfer_type + to_location are set', async () => {
  const h = load();
  const w = h.window;
  const fields = { 'qcu-xtype': 'FIELD_TO_LAB', 'qcu-xto': 'Lab A', 'qcu-xreason': '',
                    'qcu-xcond': '', 'qcu-xok': '' };
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  let sent = null;
  w.GF.API.qcAddCustody = async (sampleId, body) => { sent = { sampleId, body }; return {}; };
  w.GF.API.qcCustody = async () => [];
  w.GF.toast = () => {};
  await w.GF.WWF.qcCusLogTransfer('sample1');
  assert.ok(sent, 'qcAddCustody is called once the required fields are present');
  assert.equal(sent.sampleId, 'sample1');
  assert.equal(sent.body.transfer_type, 'FIELD_TO_LAB');
  assert.equal(sent.body.to_location, 'Lab A');
});

/* ══════════════════════════════════════════════════════════════════════
   §6.1.4 priority_justification — required client-side when priority is
   URGENT, in both the create (RQS) form and the edit form. A related
   backend check already exists in custody.py; this is the separate
   frontend-side gap (defense-in-depth UX, not a duplicate).
   ════════════════════════════════════════════════════════════════════ */

function setupRqsCreate(h, fields) {
  const w = h.window;
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  w.__created = null;
  w.GF.API.qcCreateRqs = async (body) => { w.__created = body; return { id: 'r1', rqs_number: 'RQS-0001' }; };
  w.GF.API.qcRqs = async () => [];
  w.GF.API.qcSfr = async () => [];
  w.__toasts = [];
  w.GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  return w;
}

test('qcRqsCreate refuses URGENT priority with a blank justification', async () => {
  const h = load();
  const w = setupRqsCreate(h, {
    'qcu-mat': 'MAT-1', 'qcu-dept': 'Cultivation', 'qcu-priority': 'URGENT',
    'qcu-priority_justification': '',
  });
  await w.GF.WWF.qcRqsCreate();
  assert.equal(w.__created, null, 'qcCreateRqs must not be called');
  assert.equal(w.__toasts.length, 1);
  const [msg, kind] = w.__toasts[0];
  assert.equal(kind, 'error');
  assert.match(msg, /urgency justification is required/i);
});

test('qcRqsCreate allows URGENT priority once a justification is present', async () => {
  const h = load();
  const w = setupRqsCreate(h, {
    'qcu-mat': 'MAT-1', 'qcu-dept': 'Cultivation', 'qcu-priority': 'URGENT',
    'qcu-priority_justification': 'Batch expiring in 48h',
  });
  await w.GF.WWF.qcRqsCreate();
  assert.ok(w.__created, 'qcCreateRqs must be called');
  assert.equal(w.__created.priority, 'URGENT');
  assert.equal(w.__created.priority_justification, 'Batch expiring in 48h');
});

test('qcRqsCreate does not require a justification for ROUTINE priority', async () => {
  const h = load();
  const w = setupRqsCreate(h, {
    'qcu-mat': 'MAT-1', 'qcu-dept': 'Cultivation', 'qcu-priority': 'ROUTINE',
    'qcu-priority_justification': '',
  });
  await w.GF.WWF.qcRqsCreate();
  assert.ok(w.__created, 'qcCreateRqs must be called for a routine request');
});

function setupRqsEdit(h, fields, currentRecord) {
  const w = h.window;
  w.document.getElementById = (id) => (id in fields ? { value: fields[id] } : null);
  w.GF.WWF._qccus = w.GF.WWF._qccus || {};
  w.GF.WWF._qccus.detail = currentRecord;
  w.__saved = null;
  w.GF.API.qcPatchRqs = async (id, body) => { w.__saved = { id, body }; return {}; };
  w.GF.API.qcRqs = async () => [];
  w.GF.API.qcSfr = async () => [];
  w.GF.API.qcRqsOne = async () => currentRecord;
  w.__toasts = [];
  w.GF.toast = (m, k) => { w.__toasts.push([m, k]); };
  return w;
}

test('qcRqsEdit refuses when this edit sets URGENT priority with no justification', async () => {
  const h = load();
  const w = setupRqsEdit(h,
    { 'qcu-e-batch_id': '', 'qcu-e-storage_location': '', 'qcu-e-spec_reference': '',
      'qcu-e-priority': 'URGENT', 'qcu-e-priority_justification': '' },
    { id: 'r1', status: 'OPEN', priority: null, priority_justification: null });
  await w.GF.WWF.qcRqsEdit('r1');
  assert.equal(w.__saved, null, 'qcPatchRqs must not be called');
  assert.equal(w.__toasts.length, 1);
  const [msg, kind] = w.__toasts[0];
  assert.equal(kind, 'error');
  assert.match(msg, /urgency justification is required/i);
});

test('qcRqsEdit refuses when the record is already URGENT with no stored justification, even if this edit only touches an unrelated field', async () => {
  const h = load();
  // The exact loophole this bug covers: priority was already set to URGENT
  // (e.g. on create, before this check existed) with no justification ever
  // recorded, and the user is now just filling in storage_location.
  const w = setupRqsEdit(h,
    { 'qcu-e-storage_location': 'Freezer 2' },
    { id: 'r1', status: 'OPEN', priority: 'URGENT', priority_justification: null });
  await w.GF.WWF.qcRqsEdit('r1');
  assert.equal(w.__saved, null, 'qcPatchRqs must not be called while URGENT has no justification');
  assert.match(w.__toasts[0][0], /urgency justification is required/i);
});

test('qcRqsEdit allows the save once a justification is supplied for URGENT', async () => {
  const h = load();
  const w = setupRqsEdit(h,
    { 'qcu-e-priority': 'URGENT', 'qcu-e-priority_justification': 'QP release deadline' },
    { id: 'r1', status: 'OPEN', priority: null, priority_justification: null });
  await w.GF.WWF.qcRqsEdit('r1');
  assert.ok(w.__saved, 'qcPatchRqs must be called');
  assert.equal(w.__saved.body.priority, 'URGENT');
  assert.equal(w.__saved.body.priority_justification, 'QP release deadline');
});

test('qcRqsEdit allows unrelated edits on an already-justified URGENT record', async () => {
  const h = load();
  const w = setupRqsEdit(h,
    { 'qcu-e-storage_location': 'Freezer 2' },
    { id: 'r1', status: 'OPEN', priority: 'URGENT', priority_justification: 'Already on file' });
  await w.GF.WWF.qcRqsEdit('r1');
  assert.ok(w.__saved, 'qcPatchRqs must be called; the record already carries a justification');
  assert.equal(w.__saved.body.storage_location, 'Freezer 2');
});

/* ══════════════════════════════════════════════════════════════════════
   qcCusPickerOpen — the "Link sample…" picker must not serve a stale
   session-cached sample list; a sample registered earlier this session
   must appear without a full page reload.
   ════════════════════════════════════════════════════════════════════ */

test('qcCusPickerOpen refetches the sample list on every open, not just the first', async () => {
  const h = load();
  const w = h.window;
  const versions = [
    [{ id: 's1', sample_id: 'PP-SMP-0001' }],
    [{ id: 's1', sample_id: 'PP-SMP-0001' }, { id: 's2', sample_id: 'PP-SMP-0002' }],
  ];
  let calls = 0;
  w.GF.API.qcSamples = async () => { const v = versions[Math.min(calls, versions.length - 1)]; calls++; return v; };

  await w.GF.WWF.qcCusPickerOpen('rqs', 'r1');
  assert.equal(calls, 1, 'first open fetches once');
  assert.equal(w.GF.WWF._qccus.samples.length, 1, 'first open sees only the sample registered so far');

  w.GF.WWF.qcCusPickerClose();
  await w.GF.WWF.qcCusPickerOpen('rqs', 'r1');
  assert.equal(calls, 2, 'reopening the picker issues a fresh fetch rather than reusing the cached list');
  assert.equal(w.GF.WWF._qccus.samples.length, 2, 'a sample registered since the first open now appears');
});
