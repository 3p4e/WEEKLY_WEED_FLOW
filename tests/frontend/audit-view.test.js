'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/audit-view.js — loadAudit's keyset pagination cursor (bug 1).

   loadAudit paginates on created_at ALONE (the two merged hash chains have
   colliding bigint ids, so id can't be the cursor). If several rows ever
   share an identical created_at and that group straddles a 100-row page
   boundary, the backend's own per-chain query could already have dropped the
   overflow before the frontend ever sees it — closing that fully needs a
   compound (created_at, id) keyset on the SERVER, which needs confirmation
   of which timestamp function the audit trigger uses (out of scope here).

   What IS added on the frontend, defensively: every row also carries `id`
   and `source` ("users" | "tasks" — see backend/app/api/audit.py's _ser()),
   and `source+id` is a reliable per-row key WITHIN a fetched page even though
   `id` alone collides across chains. loadAudit now dedupes newly-fetched rows
   against already-held ones by that key, so a row can never be double-counted
   if it is ever handed back across two fetches.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// audit-view.js is a bare top-level script (not an IIFE) that reads
// ELEVATED_ROLES at load time (`const AUDIT_ROLES = ELEVATED_ROLES`) and
// calls GF.WWF._registerFullPageView() at the very end — the same minimal
// contract document-view.test.js declares for the same reason.
const PRE = `
  const ELEVATED_ROLES = ['ADMIN', 'QA_MGR', 'QP'];
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.API = { user: { role: 'ADMIN' } };
`;

function load() {
  const h = loadGF({ files: ['data.js', 'core.js', 'audit-view.js'], preScript: PRE });
  // These tests target loadAudit's pagination/dedup bookkeeping only — skip
  // the full markup rebuild (_auditMarkup pulls in GF.selectField, GF.icon,
  // etc. that a full render would need) and the /audit/tables side call.
  h.GF.WWF.renderAudit = () => {};
  h.GF.WWF._audit.tables = [];
  return h;
}

test('loadAudit dedupes rows by source+id across fetches, so a row handed back twice is never double-counted', async () => {
  const h = load();
  const { GF } = h;
  const rowA = { id: 5, source: 'tasks', created_at: '2026-07-27T10:00:00.000Z' };
  const rowB = { id: 5, source: 'users', created_at: '2026-07-27T10:00:00.000Z' };   // colliding id, other chain
  GF.API.audit = async () => [rowA, rowB];
  await GF.WWF.loadAudit({ reset: true });
  assert.equal(GF.WWF._audit.entries.length, 2, 'both rows are kept — colliding id but different source');

  // A second fetch that (e.g. a retry after a hiccup) hands back one row
  // already held (same source+id) alongside one genuinely new row.
  const rowC = { id: 9, source: 'tasks', created_at: '2026-07-27T09:00:00.000Z' };
  GF.API.audit = async () => [rowA, rowC];
  await GF.WWF.loadAudit({ reset: false });
  assert.equal(GF.WWF._audit.entries.length, 3,
    'the repeated row (same source+id as rowA) must not be counted twice');
  // .join() sidesteps a cross-realm array-identity false negative from
  // assert.deepEqual (GF.WWF._audit.entries is a jsdom-realm array; a plain
  // [5,5,9] literal here is a Node-realm one) by comparing plain primitives.
  assert.equal(GF.WWF._audit.entries.map(e => e.id).join(','), '5,5,9');
  h.close();
});

test('a colliding id across the two chains is NOT treated as a duplicate on the very first page', async () => {
  const h = load();
  const { GF } = h;
  // Same id, different chain, arriving together on ONE page — this must not
  // be conflated into a single row (id alone is documented to collide).
  const usersRow = { id: 42, source: 'users', created_at: '2026-07-27T11:00:00.000Z' };
  const tasksRow = { id: 42, source: 'tasks', created_at: '2026-07-27T11:00:00.000Z' };
  GF.API.audit = async () => [usersRow, tasksRow];
  await GF.WWF.loadAudit({ reset: true });
  assert.equal(GF.WWF._audit.entries.length, 2, 'colliding ids from different chains must both survive');
  h.close();
});

test('the pagination cursor still advances to the last row’s created_at (unchanged base behavior)', async () => {
  const h = load();
  const { GF } = h;
  const page = [
    { id: 1, source: 'tasks', created_at: '2026-07-27T12:00:00.000Z' },
    { id: 2, source: 'tasks', created_at: '2026-07-27T11:00:00.000Z' },
  ];
  GF.API.audit = async () => page;
  await GF.WWF.loadAudit({ reset: true });
  assert.equal(GF.WWF._audit.before, '2026-07-27T11:00:00.000Z');
  h.close();
});
