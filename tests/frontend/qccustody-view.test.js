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
