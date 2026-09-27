'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/qccustody-view.js — the chain of custody continues past one hop.

   custody.py anchors every transfer after the first on the previous
   entry's destination: the new entry must state the from_location it is
   collected from, and — when the previous entry named a recipient — that
   person as from_user_id. The form sent neither, so the SECOND transfer for
   any sample was refused with 409 and no field-to-lab chain could be
   recorded past its first step (review 2026-09-27, FE-02).

   The form now pre-fills both from the last chain entry (read-only), offers
   a recipient picker (to_user_id), and sends them. These tests drive the
   real view and the real submit handler.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.render = { all: function () {} };
  window.GF.viewHead = function () { return '<head></head>'; };
  window.GF.API = { user: { role: 'QC_MGR', id: 'u1' } };
`;

const SFR = { id: 's1', sfr_number: 'SFR-0001', sampling_location: 'Field 3', destination_facility: 'Lab',
              status: 'IN_FIELD', sample_id: 'smp1', barrel_numbers: [] };

// Render the SFR tab with one record selected so the chain panel for its
// sample is on screen, exactly as a user would reach it.
function render(h, chain) {
  const w = h.window;
  w.GF.PEOPLE = { u1: { name: 'Ana' }, u2: { name: 'Boro' }, u3: { name: 'Old', inactive: true } };
  const st = w.GF.WWF._qccus;
  st.tab = 'sfr'; st.sfr = [SFR]; st.sel = 's1'; st.detail = SFR;
  st.custody = { smp1: chain };
  w.document.body.innerHTML = w.GF.views.qccustody();
  return w;
}

const ENTRY1 = { id: 'c1', sample_id: 'smp1', transfer_type: 'FIELD_TO_LAB', from_user_id: 'u1', to_user_id: 'u2',
                 from_location: null, to_location: 'Lab A bench 2', transferred_at: '2026-07-30T06:00:00+00:00' };

test('with a previous entry, the origin is pre-filled read-only from its destination', () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'qccustody-view.js'], preScript: PRE });
  const w = render(h, [ENTRY1]);
  const from = w.document.getElementById('qcu-xfrom');
  assert.ok(from, 'the origin field is rendered');
  assert.equal(from.value, 'Lab A bench 2', 'origin = the last entry\'s to_location');
  assert.equal(from.hasAttribute('readonly'), true, 'the origin is not editable — the chain must be continuous');
  assert.equal(w.document.getElementById('qcu-xfromuser').value, 'u2', 'the custodian = the last entry\'s recipient');
  assert.match(w.document.body.innerHTML, /Boro/, 'the custodian is shown by name');
  // The chain table shows both ends of each hop.
  assert.match(w.document.body.innerHTML, /<th>From<\/th><th>To<\/th>/);
  h.close();
});

test('the recipient picker lists active people only', () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'qccustody-view.js'], preScript: PRE });
  const w = render(h, []);
  const opts = [...w.document.querySelectorAll('#qcu-xtouser option')].map(o => o.value);
  assert.deepEqual(opts, ['', 'u1', 'u2'], 'an inactive account cannot receive custody');
  assert.equal(w.document.getElementById('qcu-xfrom'), null, 'a first transfer has no origin to inherit');
  h.close();
});

test('the second transfer sends the previous destination as its origin, and the recipient', async () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'qccustody-view.js'], preScript: PRE });
  const w = render(h, [ENTRY1]);
  w.document.getElementById('qcu-xtype').value = 'LAB_INTERNAL';
  w.document.getElementById('qcu-xto').value = 'Freezer 1';
  w.document.getElementById('qcu-xtouser').value = 'u1';
  w.document.getElementById('qcu-xreason').value = 'storage';
  let sent = null;
  w.GF.API.qcAddCustody = async (sampleId, body) => { sent = { sampleId, body }; return {}; };
  w.GF.API.qcCustody = async () => [ENTRY1];
  w.GF.toast = () => {};
  await w.GF.WWF.qcCusLogTransfer('smp1');
  assert.ok(sent, 'the transfer is sent');
  assert.equal(sent.sampleId, 'smp1');
  assert.equal(sent.body.transfer_type, 'LAB_INTERNAL');
  assert.equal(sent.body.to_location, 'Freezer 1');
  assert.equal(sent.body.to_user_id, 'u1');
  assert.equal(sent.body.from_location, 'Lab A bench 2', 'continuity: collected from where it was left');
  assert.equal(sent.body.from_user_id, 'u2', 'continuity: collected from whoever last held it');
  assert.equal(sent.body.transfer_reason, 'storage');
  h.close();
});

test('a transfer to a named person with no location is a valid destination', async () => {
  const h = loadGF({ files: ['data.js', 'core.js', 'qccustody-view.js'], preScript: PRE });
  const w = render(h, []);
  w.document.getElementById('qcu-xtype').value = 'FIELD_TO_LAB';
  w.document.getElementById('qcu-xtouser').value = 'u2';
  let sent = null;
  w.GF.API.qcAddCustody = async (sampleId, body) => { sent = body; return {}; };
  w.GF.API.qcCustody = async () => [];
  const toasts = [];
  w.GF.toast = (m, k) => toasts.push([m, k]);
  await w.GF.WWF.qcCusLogTransfer('smp1');
  assert.ok(sent, 'a recipient alone satisfies the server\'s destination minimum');
  assert.equal(sent.to_user_id, 'u2');
  assert.equal(sent.to_location, null);
  assert.equal(sent.from_location, undefined, 'a first hop states no origin');
  assert.equal(toasts.some(t => t[1] === 'error'), false);
  h.close();
});
