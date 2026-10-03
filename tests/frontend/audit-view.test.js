'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/audit-view.js — loadAudit's pagination.

   The view pages with the SERVER's cursor: GET /audit answers each page
   with an opaque per-chain (created_at, id) keyset in X-Next-Cursor
   (backend/app/api/audit.py), and the following request carries it as
   `cursor`. The view used to send the last row's bare `created_at` as
   `before`, which is lossy when a page boundary falls inside one
   transaction's rows — they all share a created_at (review 2026-09-27,
   BC-08 / R2-BC-02, DECISIONS A-7). GF.API.auditPage returns { rows, next }.

   Rows are still deduped on `source+id` — every row carries `source`
   ("users" | "tasks"), and `id` alone collides across the two chains — so a
   row handed back twice (a retry after a hiccup) is never double-counted.
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
  GF.API.auditPage = async () => ({ rows: [rowA, rowB], next: 'c1' });
  await GF.WWF.loadAudit({ reset: true });
  assert.equal(GF.WWF._audit.entries.length, 2, 'both rows are kept — colliding id but different source');

  // A second fetch that (e.g. a retry after a hiccup) hands back one row
  // already held (same source+id) alongside one genuinely new row.
  const rowC = { id: 9, source: 'tasks', created_at: '2026-07-27T09:00:00.000Z' };
  GF.API.auditPage = async () => ({ rows: [rowA, rowC], next: 'c2' });
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
  GF.API.auditPage = async () => ({ rows: [usersRow, tasksRow], next: 'c1' });
  await GF.WWF.loadAudit({ reset: true });
  assert.equal(GF.WWF._audit.entries.length, 2, 'colliding ids from different chains must both survive');
  h.close();
});

test('the second page carries the cursor the first response returned, and never `before`', async () => {
  const h = load();
  const { GF } = h;
  const calls = [];
  const page1 = { rows: [
    { id: 1, source: 'tasks', created_at: '2026-07-27T12:00:00.000Z' },
    { id: 2, source: 'tasks', created_at: '2026-07-27T12:00:00.000Z' },   // one transaction: same created_at
  ], next: 'eyJ0YXNrcyI6WyIyMDI2LTA3LTI3VDEyOjAwOjAwIiwyXX0' };
  const page2 = { rows: [{ id: 3, source: 'tasks', created_at: '2026-07-27T12:00:00.000Z' }], next: 'second' };
  GF.API.auditPage = async (q) => { calls.push({ ...q }); return calls.length === 1 ? page1 : page2; };

  await GF.WWF.loadAudit({ reset: true });
  assert.equal(calls[0].cursor, undefined, 'the first page asks for the newest rows');
  assert.equal(calls[0].before, undefined, 'the lossy timestamp keyset is not sent');
  assert.equal(GF.WWF._audit.cursor, page1.next);

  await GF.WWF.loadAudit({ reset: false });
  assert.equal(calls[1].cursor, page1.next, 'the second request resumes from the server cursor');
  assert.equal(calls[1].before, undefined);
  assert.equal(GF.WWF._audit.entries.map(e => e.id).join(','), '1,2,3',
    'the third row of the tied group is read — it used to be skipped by created_at < before');
  assert.equal(GF.WWF._audit.cursor, 'second');

  await GF.WWF.loadAudit({ reset: true });
  assert.equal(calls[2].cursor, undefined, 'a reset starts over from the newest rows');
  h.close();
});

test('hasMore is set only for a full page that came with a cursor', async () => {
  const h = load();
  const { GF } = h;
  const full = Array.from({ length: 100 }, (_, i) => ({ id: i + 1, source: 'tasks', created_at: '2026-07-27T12:00:00.000Z' }));
  GF.API.auditPage = async () => ({ rows: full, next: 'more' });
  await GF.WWF.loadAudit({ reset: true });
  assert.equal(GF.WWF._audit.hasMore, true);

  GF.API.auditPage = async () => ({ rows: full.slice(0, 3), next: 'x' });
  await GF.WWF.loadAudit({ reset: true });
  assert.equal(GF.WWF._audit.hasMore, false, 'a short page is the end of the trail');

  GF.API.auditPage = async () => ({ rows: [], next: null });
  await GF.WWF.loadAudit({ reset: true });
  assert.equal(GF.WWF._audit.hasMore, false);
  assert.equal(GF.WWF._audit.cursor, null, 'an empty page carries no cursor and leaves the position alone');
  h.close();
});
