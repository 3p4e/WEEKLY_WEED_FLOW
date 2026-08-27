'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/depthome-view.js — the department home's task cards are now the
   design system's .mw-tcard (depthome-*.html, all seven departments).

   Two things must hold or the restyle is a regression wearing a new skin:

   1. INFORMATION PARITY. The old kcard showed dept, status, title, owner
      avatars, attribute chips and priority. A restyle that quietly drops one
      of those is not a restyle — an operator triaging a room board loses a
      signal nobody decided to remove. Every element is asserted by content,
      not by trusting the class names.

   2. PORTABILITY. The .mw-* atoms consume --mw-* tokens bare, and only the
      two mass-weed themes define them. The moment an app view emits .mw-*
      markup, all 33 other skins would render it with var() resolving to
      NOTHING — invisible text, the token bug in reverse. Section 7 of
      web/gf/mass-weed.css aliases each consumed token for non-mass-weed
      skins; the invariant test below walks the atom sections and fails the
      moment any atom consumes a bare token the alias block does not cover,
      so the guarantee cannot rot as atoms are added.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF } = require('./helpers/gf-window.js');

const FILES = ['data.js', 'core.js', 'dept-templates.js', 'depthome-view.js'];

const PRE = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.render = { all: function () {}, panels: function () {} };
  window.GF.HANDOFF = {};
`;

function load({ tasks, dept = 'cultivation' } = {}) {
  const h = loadGF({ files: FILES, preScript: PRE });
  const { GF } = h;
  GF.myDeptId = () => dept;
  GF.can = () => true;
  GF.avatars = (ids) => `<span class="avz" data-n="${(ids || []).filter(Boolean).length}"></span>`;
  // In production GF.DEPTS comes from the API, each row carrying the template
  // `code`; the static data.js roster is the legacy grow-stage list and has
  // neither a 'cultivation' row nor codes, which silently downgrades every
  // department to the GENERIC layout. Register the department the way the API
  // sync would, so the REAL cultivation template (group-by-room) renders —
  // the layout the design pages show.
  GF.DEPTS.push({ id: dept, name: 'Cultivation', mk: 'Одгледување', icon: 'leaf', color: '#12a06a', code: dept });
  GF.state.tasks = tasks || [];
  // depthome renders the SELECTED week; pin selWeek to the frozen clock's week
  GF.state.selWeek = GF.calendar.todayId;
  return h;
}

// A task in the shape integrate.js produces, on the frozen clock's week.
function task(over = {}) {
  return Object.assign({
    id: 'T-1', title: 'Flush room C180', dept: 'cultivation', status: 'working',
    weekId: (over.weekId !== undefined ? over.weekId : undefined), pr: 'high',
    owner: 'U-1', helpers: ['U-2'], tags: ['flush'], sessionHours: 3.5,
    due: '2026-07-31', days: ['Thu'], attrs: { room: 'C180', strain: 'Kalorist' },
  }, over);
}

function render(h) {
  return h.GF.views.depthome();
}

test('the card is an .mw-tcard carrying the department accent', () => {
  const h = load({ tasks: [task({ weekId: undefined })] });
  // weekTasks keys on weekId — give the task the selected week's id.
  h.GF.state.tasks[0].weekId = h.GF.state.selWeek;
  const html = render(h);
  assert.match(html, /class="mw-tcard[" ]/);
  const dColor = h.GF.dep('cultivation').color;
  assert.ok(html.includes(`--mw-acc:${dColor}`),
    'the card does not carry the department color as --mw-acc — the design tint pattern is broken');
  assert.match(html, /dh-panels" style="--mw-acc:/,
    'the panels container must set --mw-acc too: panel edges and chips inherit it');
  h.close();
});

test('information parity with the old kcard: nothing an operator saw is gone', () => {
  const h = load({ tasks: [task()] });
  h.GF.state.tasks[0].weekId = h.GF.state.selWeek;
  const html = render(h);
  assert.match(html, /Flush room C180/, 'title');
  assert.match(html, /mw-tcard__dept/, 'department abbreviation');
  assert.match(html, /mw-st mw-st--working/, 'status pill uses the design class for this status');
  assert.match(html, /class="avz" data-n="2"/, 'owner + helper avatars');
  assert.match(html, /mw-attr/, 'attribute chips');
  assert.match(html, /C180/, 'attribute value survives');
  assert.match(html, /mw-htag/, 'hash tags');
  assert.match(html, /#flush/, 'tag content');
  assert.match(html, /prtag high/, 'priority chip');
  assert.match(html, /3\.5<\/span>|3\.5h/, 'logged hours');
  h.close();
});

test('overdue shows as mw-due--over; done and future do not', () => {
  const h = load({
    tasks: [
      task({ id: 'T-o', title: 'over', due: '2026-07-29', status: 'working' }),   // frozen today is 07-30
      task({ id: 'T-d', title: 'done-over', due: '2026-07-29', status: 'done' }),
      task({ id: 'T-f', title: 'future', due: '2026-08-04', status: 'working' }),
    ],
  });
  h.GF.state.tasks.forEach(t => { t.weekId = h.GF.state.selWeek; });
  const html = render(h);
  // Split on the card ELEMENT only — a bare 'class="mw-tcard' split also fires
  // on mw-tcard__title/__meta and hands back fragments of one card.
  const cards = html.split(/(?=<div class="mw-tcard[" ])/).filter(c => c.startsWith('<div class="mw-tcard'));
  const of = (title) => {
    const c = cards.find(x => x.includes(`>${title}<`));
    assert.ok(c, `no card rendered with title "${title}"`);
    return c;
  };
  assert.match(of('over'), /mw-due--over/);
  assert.doesNotMatch(of('done-over'), /mw-due--over/,
    'a finished task is not "overdue" — flagging it teaches operators to ignore the red');
  assert.doesNotMatch(of('future'), /mw-due--over/);
  h.close();
});

test('every status the app has renders SOME pill, including ones the design lacks', () => {
  // The design ships pills for done/working/review/stuck/postponed. The app
  // also has "pending". The base .mw-st class must still style it — a status
  // with no visual is indistinguishable from a bug.
  const h = load({ tasks: [task({ status: 'pending' })] });
  h.GF.state.tasks[0].weekId = h.GF.state.selWeek;
  assert.match(render(h), /mw-st mw-st--pending/);
  const css = fs.readFileSync(path.resolve(__dirname, '..', '..', 'web', 'gf', 'mass-weed.css'), 'utf8');
  assert.match(css, /\.mw-st\{/, 'the base .mw-st rule must exist for statuses without a modifier');
  h.close();
});

test('attrChips and attrChipData agree — one source of truth for chips', () => {
  const h = load({ tasks: [] });
  const t = task();
  const data = h.GF.attrChipData(t);
  assert.ok(data.length >= 1, 'chip data is empty for a task with attrs');
  const html = h.GF.attrChips(t);
  for (const e of data) {
    assert.ok(html.includes(h.GF.esc(e.val)), `attrChips lost the ${e.label} value`);
  }
  h.close();
});

test('INVARIANT: every --mw-* token an atom consumes bare is aliased for non-mass-weed skins', () => {
  // Section markers live in comments, so locate the slices FIRST, then strip
  // comments inside each slice before scanning — stripping first would erase
  // the anchors themselves.
  const raw = fs.readFileSync(path.resolve(__dirname, '..', '..', 'web', 'gf', 'mass-weed.css'), 'utf8');
  const atomsStart = raw.indexOf('4 · COMPONENT FILL');
  const aliasStart = raw.indexOf(':root:not([data-theme^="mass-weed"])');
  assert.ok(atomsStart > 0 && aliasStart > atomsStart, 'section markers moved — update this test, not delete it');
  const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '');
  const atoms = strip(raw.slice(atomsStart, aliasStart));
  const aliasBlock = strip(raw.slice(aliasStart));
  const consumed = new Set([...atoms.matchAll(/var\((--mw-[a-z0-9-]+)\)/g)].map(m => m[1]));
  assert.ok(consumed.size >= 20, `parsed only ${consumed.size} consumed tokens — the parser is broken`);
  const unaliased = [...consumed].filter(t => !new RegExp(t + '\\s*:').test(aliasBlock)).sort();
  assert.deepEqual(unaliased, [],
    `these tokens are consumed bare by atoms but NOT aliased for the 33 non-mass-weed skins, ` +
    `so any app view emitting that atom renders invisibly there: ${unaliased.join(', ')}`);
});
