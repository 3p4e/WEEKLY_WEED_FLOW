'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/core.js — GF.weekTasks / GF.visibleTasks / GF.scopedTasks
                    GF.execTasks / GF.execDeptShown
   web/gf/render.js — GF.progress

   These four selectors decide what every view shows. They differ from each
   other by ONE filter each, which is precisely why they are worth pinning:
   core.js documents that the views used to reach for the wrong one
   ("they previously used unfiltered weekTasks and ignored it"), and the only
   thing preventing that from recurring is that somebody remembers which
   selector applies the day filter and which does not.

   GF.progress is here because its precedence rule is genuinely surprising: an
   explicitly recorded 0% completion falls back to the status heuristic.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const FILES = ['data.js', 'core.js', 'render.js'];

// A small week of tasks in the shape integrate.js produces from /tasks.
const TASKS = [
  { id: 'T-A', title: 'Swab room 3',      weekId: 4, dept: 'qc',    status: 'pending', days: ['Mon', 'Tue'], tags: ['swab'] },
  { id: 'T-B', title: 'Trim batch P160012', weekId: 4, dept: 'prod',  status: 'working', days: ['Tue'],        tags: ['urgent', 'swab'] },
  { id: 'T-C', title: 'Calibrate pH meter', weekId: 4, dept: 'qc',    status: 'done',    days: [],             tags: [] },
  { id: 'T-D', title: 'Next week job',    weekId: 5, dept: 'qc',    status: 'pending', days: ['Mon'],        tags: [] },
  { id: 'T-SUB', title: 'a subtask',      weekId: 4, dept: 'qc',    status: 'pending', days: ['Mon'],        tags: [], parentId: 'T-A' },
];

function withTasks() {
  const h = loadGF({ files: FILES });
  h.GF.state.tasks = TASKS.map(t => Object.assign({}, t));
  return h;
}

const ids = (list) => Array.from(list, t => t.id);

test('GF.weekTasks returns only that week, and EXCLUDES subtask rows', () => {
  const h = withTasks();
  // `!t.parentId` is what keeps a subtask from also appearing as a top-level
  // card. Every selector below is built on this one, so a change here leaks
  // duplicate rows into all of them at once.
  assert.deepEqual(ids(h.GF.weekTasks(4)), ['T-A', 'T-B', 'T-C']);
  assert.deepEqual(ids(h.GF.weekTasks(5)), ['T-D']);
  assert.deepEqual(ids(h.GF.weekTasks(99)), []);
  h.close();
});

test('GF.visibleTasks applies the day filter; GF.scopedTasks deliberately does not', () => {
  const h = withTasks();
  h.GF.state.selDay = 'Tue';
  // This is the ONLY difference between the two, and it is the reason both
  // exist: Timeline/Coordination/Dashboard present their own day dimension and
  // must see the whole week.
  assert.deepEqual(ids(h.GF.visibleTasks(4)), ['T-A', 'T-B']);
  assert.deepEqual(ids(h.GF.scopedTasks(4)), ['T-A', 'T-B', 'T-C']);

  h.GF.state.selDay = 'All';
  assert.deepEqual(ids(h.GF.visibleTasks(4)), ['T-A', 'T-B', 'T-C']);
  h.close();
});

test('a task with no assigned days is hidden by any specific day, shown under All', () => {
  const h = withTasks();
  // T-C has days: []. Under a day filter it vanishes from My Week entirely —
  // the practical reason the day pills default to 'All'.
  h.GF.state.selDay = 'Mon';
  assert.deepEqual(ids(h.GF.visibleTasks(4)), ['T-A']);
  h.GF.state.selDay = 'Wed';
  assert.deepEqual(ids(h.GF.visibleTasks(4)), []);
  h.close();
});

test('both selectors apply the department and tag filters', () => {
  const h = withTasks();
  h.GF.state.deptFilter = 'qc';
  assert.deepEqual(ids(h.GF.scopedTasks(4)), ['T-A', 'T-C']);
  h.GF.state.deptFilter = null;

  h.GF.state.tagFilter = 'swab';
  assert.deepEqual(ids(h.GF.scopedTasks(4)), ['T-A', 'T-B']);
  h.GF.state.tagFilter = 'nope';
  assert.deepEqual(ids(h.GF.scopedTasks(4)), []);
  h.close();
});

test('search matches the title OR the id, case-insensitively, with the query trimmed', () => {
  const h = withTasks();
  const q = (s) => { h.GF.state.search = s; return ids(h.GF.scopedTasks(4)); };
  assert.deepEqual(q('swab'), ['T-A']);
  assert.deepEqual(q('SWAB'), ['T-A']);
  assert.deepEqual(q('  swab  '), ['T-A'], 'the query is trimmed before matching');
  // Matching the id is what makes pasting a task reference into the search box
  // work; the haystack is `${title} ${id}` lowercased.
  assert.deepEqual(q('t-b'), ['T-B']);
  assert.deepEqual(q('p160012'), ['T-B']);
  // Whitespace-only is treated as no filter at all, not as a literal space.
  assert.deepEqual(q('   '), ['T-A', 'T-B', 'T-C']);
  h.close();
});

test('the dept, tag and search filters compose (AND, not OR)', () => {
  const h = withTasks();
  Object.assign(h.GF.state, { deptFilter: 'qc', tagFilter: 'swab', search: 'room' });
  assert.deepEqual(ids(h.GF.scopedTasks(4)), ['T-A']);
  h.GF.state.search = 'batch';   // matches T-B, which fails the dept filter
  assert.deepEqual(ids(h.GF.scopedTasks(4)), []);
  h.close();
});

test('missing tags/days arrays are treated as empty, not as a crash', () => {
  const h = loadGF({ files: FILES });
  // The API omits both keys on tasks that have none.
  h.GF.state.tasks = [{ id: 'T-X', title: 'bare', weekId: 4, dept: 'qc', status: 'pending' }];
  h.GF.state.selDay = 'Mon';
  assert.deepEqual(ids(h.GF.visibleTasks(4)), []);
  h.GF.state.selDay = 'All';
  h.GF.state.tagFilter = 'anything';
  assert.deepEqual(ids(h.GF.visibleTasks(4)), []);
  h.GF.state.tagFilter = null;
  assert.deepEqual(ids(h.GF.visibleTasks(4)), ['T-X']);
  h.close();
});

test('GF.execTasks ignores the sidebar filters and honours only the hidden-department set', () => {
  const h = withTasks();
  // Documented intent: the executive overview is a full-week read. If it ever
  // started respecting selDay/search the "one screen" cross-department numbers
  // would quietly become a filtered subset while still being read as totals.
  Object.assign(h.GF.state, { selDay: 'Mon', search: 'swab', deptFilter: 'prod', tagFilter: 'urgent' });
  assert.deepEqual(ids(h.GF.execTasks(4)), ['T-A', 'T-B', 'T-C']);

  h.GF.state.execHidden.add('qc');
  assert.deepEqual(ids(h.GF.execTasks(4)), ['T-B']);
  assert.equal(h.GF.execDeptShown('qc'), false);
  assert.equal(h.GF.execDeptShown('prod'), true);
  h.close();
});

test('GF.toggleExecDept flips a department and persists the set to localStorage', () => {
  const h = withTasks();
  h.GF.render = { all: () => {} };   // toggleExecDept repaints; only the hook is replaced
  h.GF.toggleExecDept('qc');
  assert.equal(h.GF.execDeptShown('qc'), false);
  assert.deepEqual(JSON.parse(h.window.localStorage.getItem('gf_exec_hidden')), ['qc']);
  h.GF.toggleExecDept('qc');
  assert.equal(h.GF.execDeptShown('qc'), true);
  assert.deepEqual(JSON.parse(h.window.localStorage.getItem('gf_exec_hidden')), []);

  h.GF.toggleExecDept('qc');
  h.GF.toggleExecDept('prod');
  h.GF.resetExecDepts();
  assert.equal(h.GF.state.execHidden.size, 0);
  assert.deepEqual(JSON.parse(h.window.localStorage.getItem('gf_exec_hidden')), []);
  h.close();
});

test('a corrupt gf_exec_hidden value degrades to "nothing hidden" instead of throwing at load', () => {
  // The value is user-writable localStorage read inside core.js's load-time
  // IIFE. If that throws, core.js never finishes and the app is a blank page —
  // which is what the try/catch and the Array.isArray check are for.
  for (const bad of ['not json', '{"a":1}', '"str"', '42', 'null', '']) {
    const h = loadGF({ files: FILES, storage: { gf_exec_hidden: bad } });
    assert.equal(h.GF.state.execHidden.size, 0, `gf_exec_hidden=${JSON.stringify(bad)}`);
    assert.equal(h.GF.execDeptShown('qc'), true);
    h.close();
  }
  // A well-formed value IS honoured, so the test above is not passing simply
  // because the value is always ignored.
  const ok = loadGF({ files: FILES, storage: { gf_exec_hidden: '["qc","prod"]' } });
  assert.equal(ok.GF.execDeptShown('qc'), false);
  assert.equal(ok.GF.execDeptShown('prod'), false);
  assert.equal(ok.GF.execDeptShown('veg'), true);
  ok.close();
});

/* ── GF.progress (render.js) ──────────────────────────────────────────── */

test('GF.progress: done is always 100, whatever the recorded percentage says', () => {
  const h = loadGF({ files: FILES });
  assert.equal(h.GF.progress({ status: 'done' }), 100);
  assert.equal(h.GF.progress({ status: 'done', progressPct: 40 }), 100);
  h.close();
});

test('GF.progress: an explicit percentage wins over the status heuristic', () => {
  const h = loadGF({ files: FILES });
  assert.equal(h.GF.progress({ status: 'pending', progressPct: 35 }), 35);
  assert.equal(h.GF.progress({ status: 'working', progressPct: 90 }), 90);
  h.close();
});

test('GF.progress: a recorded 0% falls BACK to the status heuristic', () => {
  const h = loadGF({ files: FILES });
  // The guard is `progressPct > 0`, so a worklog entry that deliberately scores
  // a task at 0% is indistinguishable from never having been scored, and the
  // card shows 50% for a 'working' task. Surprising enough to pin explicitly.
  assert.equal(h.GF.progress({ status: 'working', progressPct: 0 }), 50);
  h.close();
});

test('GF.progress: non-numeric or absent percentages fall back, and an unknown status is 0', () => {
  const h = loadGF({ files: FILES });
  const heuristic = { done: 100, working: 50, review: 75, stuck: 25, postponed: 10, pending: 0 };
  for (const [status, pct] of Object.entries(heuristic)) {
    assert.equal(h.GF.progress({ status }), pct, `${status} heuristic`);
  }
  for (const bad of [null, undefined, NaN, Infinity, '80']) {
    assert.equal(h.GF.progress({ status: 'review', progressPct: bad }), 75,
      `progressPct=${String(bad)} must not be trusted`);
  }
  // `?? 0` — a status outside the six known ones (a raw backend enum value
  // leaking through, e.g. 'ongoing') reads as 0%, not undefined/NaN.
  assert.equal(h.GF.progress({ status: 'ongoing' }), 0);
  assert.equal(h.GF.progress({ status: undefined }), 0);
  h.close();
});
