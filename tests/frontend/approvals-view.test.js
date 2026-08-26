'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/approvals-view.js — two bugs in loadApprovals / the nav badge.

   Bug 2: loadApprovals had no sequence/generation guard, unlike sibling
   loaders elsewhere (analytics-view.js's st.lseq, document-view.js's
   ds._seq). apvAck() calls it unconditionally on every successful
   accept/decline with no in-flight check, so two overlapping calls (accept
   task A, then quickly task B) could let an out-of-order response overwrite
   newer state with stale data — and this view has no polling to self-correct.

   Bug 3: GF.WWF._apv.data is populated ONLY by loadApprovals(), which
   (before this fix) nothing in the app ever called except from within this
   file's own lazy-load-on-render guard, its retry button, and apvAck. A user
   with pending acknowledgments who hadn't yet opened Approvals never saw the
   nav badge light up. The fix adds a one-shot boot-time prefetch (mirroring
   report-view.js's _checkNewReportPin), guarded on GF.API.token so an
   anonymous page load can't latch st.error and block the real fetch once the
   user logs in.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

// approvals-view.js's IIFE only touches these at load time: registering the
// nav item (_registerFullPageView) and, at the very bottom, the boot-time
// prefetch (a real, but one-shot and near-immediate, setTimeout(...,0) — safe
// to let fire for real, unlike a recurring poll).
function pre({ token = '' } = {}) {
  return `
    window.GF = window.GF || {};
    window.GF.views = window.GF.views || {};
    window.GF.WWF = window.GF.WWF || {};
    window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
    window.GF.state = { view: 'mywork', lang: 'en' };
    window.__renderAllCalls = 0; window.__sidebarCalls = 0;
    window.GF.render = {
      all: function () { window.__renderAllCalls++; },
      sidebar: function () { window.__sidebarCalls++; },
    };
    window.GF.API = { user: { role: 'QC_MGR' }, token: ${JSON.stringify(token)} };
  `;
}

function load(opts) {
  return loadGF({ files: ['data.js', 'core.js', 'approvals-view.js'], preScript: pre(opts) });
}

test('a slower-resolving loadApprovals call does not clobber a faster, more recent one (bug 2)', async () => {
  const h = load();
  const { GF } = h;
  const resolvers = [];
  GF.API.approvalsPending = () => new Promise((resolve) => { resolvers.push(resolve); });
  // documentStatus / qcCoqs are left undefined, so loadApprovals's Promise.all
  // resolves those legs to null immediately (see the `GF.API.x ? ... : null`
  // guards) — only approvalsPending needs hand control for this test.

  const p1 = GF.WWF.loadApprovals();   // seq 1 — accept task A
  const p2 = GF.WWF.loadApprovals();   // seq 2 — accept task B, fired right after
  assert.equal(resolvers.length, 2, 'both calls must be in flight');

  // The LATER call (B) resolves FIRST and is adopted immediately.
  resolvers[1]({ mine: [{ task_id: 'B' }], team: [] });
  await p2;
  assert.equal(GF.WWF._apv.data.mine[0].task_id, 'B', 'B’s own response must be applied');

  // The EARLIER call (A) resolves SECOND, carrying a now-stale snapshot.
  resolvers[0]({ mine: [{ task_id: 'A' }], team: [] });
  await p1;
  assert.equal(GF.WWF._apv.data.mine[0].task_id, 'B',
    'the stale, slower response for A must not clobber B’s already-applied state');
  h.close();
});

test('loadApprovals re-renders the sidebar (not the full panel) when the user is off the Approvals view', async () => {
  const h = load();
  const { GF, window: w } = h;
  GF.API.approvalsPending = async () => ({ mine: [], team: [] });
  GF.state.view = 'mywork';
  await GF.WWF.loadApprovals();
  assert.equal(w.__renderAllCalls, 0, 'the full panel is not rebuilt off-page');
  assert.equal(w.__sidebarCalls, 1, 'the nav badge must still refresh so a prefetch made off-page is visible');
  h.close();
});

test('a boot-time prefetch (persisted session token already present) populates _apv.data before Approvals is ever opened (bug 3)', async () => {
  const h = load({ token: 'tok123' });
  const { GF, window: w } = h;
  let called = 0;
  GF.API.approvalsPending = async () => { called++; return { mine: [{ task_id: 'A', title: 'x' }], team: [] }; };
  assert.equal(GF.WWF._apv.data, null, 'nothing is fetched synchronously — the prefetch is deferred');

  await new Promise((r) => setTimeout(r, 20));   // let the module-scope setTimeout(...,0) fire

  assert.equal(called, 1, 'the boot-time prefetch must call approvalsPending exactly once');
  assert.ok(GF.WWF._apv.data, '_apv.data must be populated');
  assert.equal(GF.WWF._apv.data.mine.length, 1);
  assert.ok(w.__reg && typeof w.__reg.badge === 'function', 'the nav item must have registered a badge callback');
  assert.equal(w.__reg.badge(), true, 'the badge must now report a pending item, before the user ever opened Approvals');
  h.close();
});

test('without a persisted session token, the boot-time prefetch does not fire', async () => {
  const h = load({ token: '' });
  const { GF } = h;
  let called = 0;
  GF.API.approvalsPending = async () => { called++; return { mine: [], team: [] }; };

  await new Promise((r) => setTimeout(r, 20));

  assert.equal(called, 0, 'approvalsPending must not be called before a session token exists');
  assert.equal(GF.WWF._apv.data, null,
    'st.data must stay null — an anonymous 401 here would otherwise latch st.error and block the real fetch after login');
  h.close();
});
