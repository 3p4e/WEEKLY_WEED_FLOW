'use strict';

/* ══════════════════════════════════════════════════════════════════════
   Cross-department handoffs reach the department they are sent to —
   review 2026-09-27, FE-06 / BC-04 / FE-18.

   collab.py resolve_handoff decides who may accept, reject or cancel:
     target side = the receiving department's head, or an elevated role
                   whose department is the target or one of its ancestors;
     org-wide    = an elevated role with no department scope;
     accept      = target side, or org-wide and not the proposer;
     reject      = target side or org-wide;
     cancel      = any of those, or the proposer.
   The card used "task owner or any elevated role", so a USER owner, the
   source manager and the proposing executive saw buttons that 403'd, and
   the receiving manager — the one the proposal is addressed to — had no
   button and no list. These tests pin the client rule case by case, the
   card, the inbox sentence and routing, and the Approvals list.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const toJS = (v) => JSON.parse(JSON.stringify(v));

// The departments tree: Cultivation with Cloning under it, and Production.
const DEPTS = [
  { id: 'cu', code: 'cultivation', name: 'Cultivation', mk: 'Одгледување', parent_id: null },
  { id: 'cl', code: 'cloning', name: 'Cloning', mk: 'Клонирање', parent_id: 'cu' },
  { id: 'pr', code: 'production', name: 'Production', mk: 'Производство', parent_id: null },
];

// integrate.js owns deptScope / deptFamily and cannot be loaded here (it
// runs install() at load). Declared the way integrate.js defines them.
const PRE = `
  const AUDIT_ROLES = ['ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR','SE_MGR','CU_MGR','IR_MGR','MU_MGR','QP'];
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.render = { card: function () { return ''; }, panels: function () {}, all: function () {}, sidebar: function () {} };
  window.GF.viewHead = function () { return ''; };
  window.GF.PEOPLE = { pm: { name: 'Petar' }, cm: { name: 'Cveta' }, ex: { name: 'Olga' }, us: { name: 'Uros' } };
  window.GF.DEPTS = ${JSON.stringify(DEPTS)};
  window.GF.scopedTasks = function () { return []; };
  const DEPT_SCOPED = new Set(['QA_MGR','QC_MGR','PR_MGR','WH_MGR','SE_MGR','CU_MGR','IR_MGR','MU_MGR']);
  window.GF.WWF.deptScope = function () { var u = GF.API.user || {}; return (DEPT_SCOPED.has(u.role) && u.department_id) ? u.department_id : null; };
  window.GF.WWF.deptFamily = function (root) {
    if (!root) return []; var out = [String(root)];
    for (var i = 0; i < out.length; i++) GF.DEPTS.forEach(function (d) { if (d.parent_id && String(d.parent_id) === out[i] && out.indexOf(String(d.id)) < 0) out.push(String(d.id)); });
    return out;
  };
  window.GF.API = { user: { id: 'pm', role: 'PR_MGR', department_id: 'pr' } };
`;

const FILES = ['data.js', 'core.js', 'chooser.js', 'modules.js', 'collab.js', 'task-extras.js'];
const PEOPLE = { pm: { name: 'Petar' }, cm: { name: 'Cveta' }, ex: { name: 'Olga' }, us: { name: 'Uros' } };

// data.js seeds its own GF.DEPTS / GF.PEOPLE at load, so the fixtures are
// assigned AFTER the sources ran, the way integrate.js replaces them.
function load(user, extraFiles) {
  const h = loadGF({ files: [...FILES, ...(extraFiles || [])], preScript: PRE });
  h.window.GF.DEPTS = toJS(DEPTS);
  h.window.GF.PEOPLE = toJS(PEOPLE);
  if (user) h.window.GF.API.user = user;
  return h;
}

// A handoff of a Cultivation task to Production, proposed by the executive.
const H = { id: 'h1', task_id: 't1', from_dept_id: 'cu', to_dept_id: 'pr', requested_by: 'ex', status: 'proposed', note: 'dry room ready' };

const CASES = [
  // [label, user, expected {accept, reject, cancel}]
  ['the receiving department\'s manager', { id: 'pm', role: 'PR_MGR', department_id: 'pr' }, { accept: true, reject: true, cancel: true }],
  ['the source department\'s manager', { id: 'cm', role: 'CU_MGR', department_id: 'cu' }, { accept: false, reject: false, cancel: false }],
  ['a USER who owns the task', { id: 'us', role: 'USER', department_id: 'cu' }, { accept: false, reject: false, cancel: false }],
  ['the org-wide executive who proposed it', { id: 'ex', role: 'OWNER', department_id: null }, { accept: false, reject: true, cancel: true }],
  ['another org-wide executive', { id: 'ex2', role: 'CEO', department_id: null }, { accept: true, reject: true, cancel: true }],
  ['the QP (manager rank, org-wide)', { id: 'qp', role: 'QP', department_id: 'qa' }, { accept: true, reject: true, cancel: true }],
  ['ADMIN', { id: 'ad', role: 'ADMIN', department_id: null }, { accept: true, reject: true, cancel: true }],
  ['an unrelated department\'s manager', { id: 'wm', role: 'WH_MGR', department_id: 'wh' }, { accept: false, reject: false, cancel: false }],
];

test('handoffRights mirrors the server predicate case by case', () => {
  for (const [label, user, want] of CASES) {
    const h = load(user);
    const r = h.GF.WWF.handoffRights(H);
    assert.deepEqual({ accept: r.accept, reject: r.reject, cancel: r.cancel }, want, label);
    h.close();
  }
});

test('a USER who proposed a handoff may withdraw it and nothing else', () => {
  const h = load({ id: 'us', role: 'USER', department_id: 'cu' });
  const r = h.GF.WWF.handoffRights({ ...H, requested_by: 'us' });
  assert.deepEqual({ accept: r.accept, reject: r.reject, cancel: r.cancel }, { accept: false, reject: false, cancel: true });
  h.close();
});

test('the parent department\'s manager receives a handoff addressed to a sub-department', () => {
  // Cloning sits under Cultivation and its manager runs it (dept_family).
  const h = load({ id: 'cm', role: 'CU_MGR', department_id: 'cu' });
  const r = h.GF.WWF.handoffRights({ ...H, from_dept_id: 'pr', to_dept_id: 'cl' });
  assert.equal(r.accept, true);
  assert.equal(r.targetSide, true);
  h.close();
});

test('a department head named on the department is target-side whatever their role', () => {
  const h = load({ id: 'head', role: 'USER', department_id: null });
  h.GF.DEPTS = DEPTS.map(d => d.id === 'pr' ? { ...d, head_user_id: 'head' } : d);
  assert.equal(h.GF.WWF.handoffRights(H).accept, true, 'departments.head_user_id, once the payload carries it');
  h.close();
});

test('the card offers exactly the buttons the server will honour', () => {
  const t = { id: 't1', title: 'Dry room C183', dept: 'cu', owner: 'us' };
  const x = { links: [], blockedBy: [], blocks: [], handoffs: [H], loaded: true };
  // Receiving manager: accept, reject, cancel.
  let h = load({ id: 'pm', role: 'PR_MGR', department_id: 'pr' });
  let html = h.GF.WWF.renderHandoffs(t, x);
  assert.match(html, /resolveHandoff\('h1','accepted'\)/);
  assert.match(html, /resolveHandoff\('h1','rejected'\)/);
  assert.match(html, /resolveHandoff\('h1','cancelled'\)/);
  h.close();
  // The USER who owns the task: no buttons at all (they used to see ✓ ✕ → 403).
  h = load({ id: 'us', role: 'USER', department_id: 'cu' });
  html = h.GF.WWF.renderHandoffs(t, x);
  assert.doesNotMatch(html, /resolveHandoff\(/, 'no button that the server would refuse');
  assert.match(html, /proposed/, 'the proposal itself is still shown');
  h.close();
  // The proposing executive: withdraw or reject, never accept their own.
  h = load({ id: 'ex', role: 'OWNER', department_id: null });
  html = h.GF.WWF.renderHandoffs(t, x);
  assert.doesNotMatch(html, /'accepted'/);
  assert.match(html, /'rejected'/);
  assert.match(html, /'cancelled'/);
  h.close();
});

/* ── Inbox: sentences and routing ─────────────────────────────────────── */
const PRE_NOTIF = `
  window.setInterval = function () { return 0; };
  window.setTimeout = function () { return 0; };
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.PEOPLE = { ex: { name: 'Olga' } };
  window.GF.icon = function () { return ''; };
  window.GF.avatar = function () { return ''; };
  // 'pm' is the receiving department's manager (PR_MGR) — openNotif routes a
  // handoff ping to Approvals only for a role that can open it (R2-FE-01).
  window.GF.API = { token: 'tok', user: { id: 'pm', role: 'PR_MGR', facility_tz: 'Europe/Skopje' } };
  window.GF.render = { all: function () {}, sidebar: function () {} };
  window.GF.viewHead = function () { return ''; };
`;

function inbox(items, lang) {
  const h = loadGF({ files: ['data.js', 'core.js', 'notifications-view.js'], preScript: PRE_NOTIF,
                     storage: lang ? { gf_lang: lang } : {} });
  const w = h.window;
  w.GF.state.user = 'pm';
  w.GF.PEOPLE = { ex: { name: 'Olga' } };   // data.js seeded its own at load
  const st = w.GF.WWF._notif;
  st.loaded = true; st.user = 'pm';
  st.items = items.map((n, i) => ({ id: 'n' + i, reason: 'status', read: true, created_at: '2026-07-30T07:00:00Z', ...n }));
  return { h, w, html: w.GF.views.inbox() };
}

test('a handoff proposal and its resolution read as sentences, in both languages', () => {
  const items = [
    { verb: 'handoff', actor_id: 'ex', task_id: 't1', params: { title: 'Dry room C183', to_dept: 'Production' } },
    { verb: 'handoff_resolved', actor_id: 'ex', task_id: 't1', params: { title: 'Dry room C183', status: 'accepted' } },
  ];
  let r = inbox(items);
  assert.match(r.html, /Olga proposed a handoff to Production: Dry room C183/);
  assert.match(r.html, /Olga accepted the handoff: Dry room C183/);
  r.h.close();
  r = inbox(items, 'mk');
  assert.match(r.html, /Olga предложи префрлање до Production: Dry room C183/);
  assert.match(r.html, /Olga го прифати префрлањето: Dry room C183/);
  r.h.close();
});

test('every other emitted verb renders as words with its object, never a raw token', () => {
  const r = inbox([
    { verb: 'decon_swab_positive', actor_id: 'ex', params: { room: 'Flowering 1.1', swab_code: 'RR-01-003' } },
    { verb: 'oos_opened', actor_id: 'ex', params: { oos_number: 'OOS-2026-0003', batch_id: 'GP072501' } },
    // A verb this build does not know: generic actor · words: object.
    { verb: 'something_new_here', actor_id: 'ex', object_type: 'qc_sample', params: {} },
  ]);
  assert.match(r.html, /Positive swab RR-01-003 in Flowering 1\.1/);
  assert.match(r.html, /Olga opened OOS-2026-0003 on batch GP072501/);
  assert.match(r.html, /Olga · something new here: sample/);
  assert.doesNotMatch(r.html, /something_new_here/, 'the machine token never reaches the screen');
  r.h.close();
});

test('opening a handoff notification goes to Approvals, not to a board where the task is not', async () => {
  const r = inbox([{ verb: 'handoff', actor_id: 'ex', task_id: 't1', params: { title: 'Dry room C183', to_dept: 'Production' } }]);
  const w = r.w;
  w.GF.API.notifRead = async () => ({});
  const views = [];
  w.GF.setView = (v) => views.push(v);
  let jumped = false;
  w.GF.WWF.xrJump = () => { jumped = true; };
  await w.GF.WWF.openNotif('n0', 't1');
  assert.deepEqual(views, ['approvals']);
  assert.equal(jumped, false);
  r.h.close();
});

/* ── Approvals: the list the receiving manager acts from ─────────────── */
test('Approvals lists the handoffs addressed to my department with Accept / Reject, and counts them in the badge', async () => {
  const h = load({ id: 'pm', role: 'PR_MGR', department_id: 'pr' }, ['approvals-view.js']);
  const w = h.window;
  w.GF.API.approvalsPending = async () => ({ mine: [], team: [] });
  let notifQuery = null;
  w.GF.API.notifications = async (q) => { notifQuery = q; return [
    { id: 'n1', verb: 'handoff', task_id: 't1', params: { title: 'Dry room C183', to_dept: 'Production' }, created_at: '2026-07-30T07:00:00Z' },
    { id: 'n2', verb: 'handoff', task_id: 't2', params: { title: 'Not for me', to_dept: 'Cultivation' }, created_at: '2026-07-30T07:00:00Z' },
  ]; };
  w.GF.API.handoffs = async (taskId) => taskId === 't1'
    ? [{ ...H, created_at: '2026-07-30T06:00:00Z' }, { ...H, id: 'h0', status: 'rejected' }]
    : [{ ...H, id: 'h2', task_id: 't2', from_dept_id: 'pr', to_dept_id: 'cu', status: 'proposed' }];
  w.GF.t = (k) => k;
  w.GF.state.view = 'approvals';
  await w.GF.WWF.loadApprovals();
  const st = w.GF.WWF._apv;
  assert.equal(notifQuery && notifQuery.limit, 200, 'the inbox is read at its maximum page, not the default 50 (R2-FE-09)');
  assert.deepEqual(toJS(st.handoffs.map(x => x.id)), ['h1'], 'only proposed handoffs I may decide on');
  const html = w.GF.views.approvals();
  assert.match(html, /Handoffs to your department/);
  assert.match(html, /Dry room C183/);
  assert.match(html, /Cultivation → Production/);
  assert.match(html, /dry room ready/);
  assert.match(html, /apvHandoff\('h1','accepted'\)/);
  assert.match(html, /apvHandoff\('h1','rejected'\)/);
  assert.doesNotMatch(html, /Not for me/);
  h.close();
});

test('accepting from Approvals resolves through the server and reloads the list', async () => {
  const h = load({ id: 'pm', role: 'PR_MGR', department_id: 'pr' }, ['approvals-view.js']);
  const w = h.window;
  w.GF.API.approvalsPending = async () => ({ mine: [], team: [] });
  w.GF.API.notifications = async () => [];
  const calls = [];
  w.GF.API.resolveHandoff = async (id, status) => { calls.push([id, status]); return { ok: true }; };
  w.GF.toast = () => {};
  let loads = 0;
  const realLoad = w.GF.WWF.loadApprovals;
  w.GF.WWF.loadApprovals = async () => { loads++; return realLoad(); };
  await w.GF.WWF.apvHandoff('h1', 'accepted');
  assert.deepEqual(toJS(calls), [['h1', 'accepted']]);
  assert.equal(loads, 1);
  h.close();
});
