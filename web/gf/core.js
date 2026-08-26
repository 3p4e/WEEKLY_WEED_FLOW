/* core.js — state, storage, calendar, i18n, icons, helpers. Global: GF */
window.GF = window.GF || {};

GF.$ = (id) => document.getElementById(id);
GF.esc = (s) => String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');

// ── Re-entrancy guard for async submit handlers ──
// The Save buttons are plain inline onclick handlers, and the handlers behind
// them await several round trips before they finish (submitAdd: translate,
// then createTask, then one assign call per helper). Nothing stopped a second
// click landing inside that window, which creates a duplicate task — or a
// duplicate user account, complete with its own OTP. Keyed on the button id so
// the in-flight flag can never leak between modals, and the button stays
// disabled for the WHOLE chain, not just the first await.
GF._busy = Object.create(null);
GF.once = async (btnId, fn) => {
  if (GF._busy[btnId]) return;                    // already in flight — drop it
  GF._busy[btnId] = true;
  const btn = GF.$(btnId);
  const label = btn ? btn.innerHTML : '';
  if (btn) btn.disabled = true;
  try {
    return await fn(btn, label);
  } finally {
    delete GF._busy[btnId];
    // Re-read: the handler usually closes the modal, and on some paths the
    // node is replaced by a re-render, so the captured reference can be stale.
    const b = GF.$(btnId);
    if (b) { b.disabled = false; b.innerHTML = label; }
  }
};

// ── Icons (stroke paths, 20x20 viewBox) ──
GF.ICONS = {
  search:'M17 17l-3.2-3.2M15.5 9.5a6 6 0 11-12 0 6 6 0 0112 0z',
  bell:'M6 8a4 4 0 018 0c0 4 1.5 5 2 6H4c.5-1 2-2 2-6zM8.5 17a1.6 1.6 0 003 0',
  plus:'M10 4v12M4 10h12', mic:'M10 3a2.2 2.2 0 012.2 2.2v4.6a2.2 2.2 0 01-4.4 0V5.2A2.2 2.2 0 0110 3zM5 9.5a5 5 0 0010 0M10 14.5V17M7.5 17h5',
  chevL:'M12 5l-5 5 5 5', chevR:'M8 5l5 5-5 5', chevD:'M5 8l5 5 5-5', chevU:'M5 12l5-5 5 5',
  check:'M4 10.5l4 4 8-9', clock:'M10 5.5V10l3 1.8M10 3a7 7 0 100 14 7 7 0 000-14z',
  user:'M10 10a3 3 0 100-6 3 3 0 000 6zM4.5 17a5.5 5.5 0 0111 0', flag:'M5 3v14M5 3.5h9l-2 3 2 3H5',
  leaf:'M4 16c8 0 12-4 12-12C8 4 4 8 4 16zM4 16c1.5-4 3.5-6 6-7.5', grid:'M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z',
  timeline:'M3 6h9M3 11h13M3 16h6M14 4v4M9 9v4M16 14v4', chat:'M4 5h12v8H9l-3 3v-3H4z',
  link:'M8 12l4-4M7.5 7.5L6 9a3 3 0 004.2 4.2l1.3-1.3M12.5 12.5L14 11a3 3 0 00-4.2-4.2L8.5 8',
  settings:'M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM10 2.5v2M10 15.5v2M3.5 6l1.7 1M14.8 13l1.7 1M3.5 14l1.7-1M14.8 7l1.7-1',
  sun:'M10 13a3 3 0 100-6 3 3 0 000 6zM10 2v2M10 16v2M2 10h2M16 10h2M4.2 4.2l1.4 1.4M14.4 14.4l1.4 1.4M4.2 15.8l1.4-1.4M14.4 5.6l1.4-1.4',
  moon:'M15.5 12.5A6.5 6.5 0 117.5 4.5a5 5 0 108 8z',
  hexagon:'M10 2.5l6.5 3.75v7.5L10 17.5 3.5 13.75v-7.5z',
  palette:'M10 2.5a7.5 7.5 0 000 15c1 0 1.5-.7 1.5-1.5 0-.4-.2-.7-.4-1-.2-.3-.4-.6-.4-1 0-.8.7-1.5 1.5-1.5H14a3.5 3.5 0 003.5-3.5C17.5 5.6 14.1 2.5 10 2.5zM5.5 10.5a1 1 0 110-2 1 1 0 010 2zm3-3.5a1 1 0 110-2 1 1 0 010 2zm4 0a1 1 0 110-2 1 1 0 010 2z',
  drop:'M10 3s5 5.5 5 9a5 5 0 01-10 0c0-3.5 5-9 5-9z', box:'M10 3l6 3v8l-6 3-6-3V6l6-3zM4 6l6 3 6-3M10 9v8',
  shield:'M10 3l6 2v5c0 4-3 6-6 7-3-1-6-3-6-7V5l6-2z',
  wrench:'M12.5 4a3.5 3.5 0 00-4.7 4.2l-4 4a1.5 1.5 0 002.1 2.1l4-4A3.5 3.5 0 0016 7l-2 2-1.5-1.5 2-2A3.5 3.5 0 0012.5 4z',
  flask:'M8 3h4M9 3v5l-4 7a1.5 1.5 0 001.3 2.2h7.4A1.5 1.5 0 0015 15l-4-7V3M6.5 13h7',
  sparkle:'M10 3l1.6 4.4L16 9l-4.4 1.6L10 15l-1.6-4.4L4 9l4.4-1.6L10 3z', arrowR:'M4 10h12M11 5l5 5-5 5',
  trash:'M4 6h12M8 6V4h4v2M6 6l1 11h6l1-11', menu:'M3 6h14M3 10h14M3 14h14',
  trend:'M3 14l4-5 3 3 5-7M14 5h2v2', calendar:'M4 6h12v11H4zM4 6V4m12 2V4M7 3v3m6-3v3M4 9h12',
  at:'M10 10m-3 0a3 3 0 106 0 3 3 0 00-6 0M13 10v1.5a2 2 0 004 0V10a7 7 0 10-3 5.7',
  forward:'M4 5l6 5-6 5V5zM11 5l6 5-6 5V5z', x:'M5 5l10 10M15 5L5 15', play:'M6 4l9 6-9 6V4z',
  info:'M10 9v5M10 6.5h.01M10 3a7 7 0 100 14 7 7 0 000-14z',
  eye:'M2 10s3-5.5 8-5.5S18 10 18 10s-3 5.5-8 5.5S2 10 2 10zM10 12.2a2.2 2.2 0 100-4.4 2.2 2.2 0 000 4.4z',
  eyeOff:'M4 4l12 12M8.3 8.4a2.2 2.2 0 002.9 2.9M6.6 5.8A9 9 0 0110 4.5c5 0 8 5.5 8 5.5a15 15 0 01-2.3 2.8M4.2 7.4A14 14 0 002 10s3 5.5 8 5.5c.9 0 1.7-.1 2.5-.35',
  layers:'M10 3l7 4-7 4-7-4 7-4zM3 11l7 4 7-4M3 14l7 4 7-4',
  award:'M10 12.5a5 5 0 100-10 5 5 0 000 10zM7.7 11.6L6.6 17.5l3.4-1.9 3.4 1.9-1.1-5.9',
  'git-branch':'M5 2.5v10M15 7.5A7.5 7.5 0 017.5 15M15 7.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM5 17.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z',
  'file-input':'M11.5 2.5H7A1.5 1.5 0 005.5 4v4M5.5 14v2.5A1.5 1.5 0 007 18h8a1.5 1.5 0 001.5-1.5V7.5l-5-5M11.5 2.5v5h5M2.5 11H10M7.5 8.5L10 11l-2.5 2.5',
  droplet:'M10 3s5 5.5 5 9a5 5 0 01-10 0c0-3.5 5-9 5-9z',
  'alert-triangle':'M8.6 3.4L2 14.8a1.6 1.6 0 001.4 2.4h13.2a1.6 1.6 0 001.4-2.4L11.4 3.4a1.6 1.6 0 00-2.8 0zM10 7.5V11M10 14h.01',
  users:'M7.5 9.5a3 3 0 100-6 3 3 0 000 6zM2 17a5.5 5.5 0 0111 0M13.2 3.9a3 3 0 010 5.7M14.6 11.8a5.5 5.5 0 013.4 5.2',
  file:'M11.5 2.5H6.5A1.5 1.5 0 005 4v12a1.5 1.5 0 001.5 1.5h7A1.5 1.5 0 0015 16V6l-3.5-3.5zM11.5 2.5V6H15',
  'clipboard-check':'M7 3h6a1 1 0 011 1v1h1a1.5 1.5 0 011.5 1.5v9A1.5 1.5 0 0115 17H5a1.5 1.5 0 01-1.5-1.5v-9A1.5 1.5 0 015 5h1V4a1 1 0 011-1zm0 2h6V4H7v1zM7 11l2 2 4-4.5',
  'bar-chart':'M4 17V11M9 17V6M14 17V3M4 17h11',
};
GF.icon = (n, cls = 'icon', stroke) => `<svg class="${cls}" viewBox="0 0 20 20"${stroke ? ` style="stroke:${stroke}"` : ''}><path d="${GF.ICONS[n] || ''}"/></svg>`;

// ── i18n ──
GF.state = {
  lang: localStorage.getItem('gf_lang') || 'en',
  user: localStorage.getItem('gf_user') || 'marko',
  aiBase: localStorage.getItem('gf_ai_base') || '',
  aiProvider: localStorage.getItem('gf_ai_provider') || 'builtin',
  view: localStorage.getItem('gf_view') || 'mywork',
  selWeek: 0, selDay: 'All', deptFilter: null, tagFilter: null, search: '',
  tasks: [], expanded: new Set(), teleOpen: false,
  // Subtasks/sub-subtasks indexed by parent id (integrate.js builds this from
  // the same /tasks payload) + which parents have their tree expanded.
  children: {}, treeOpen: new Set(),
};

// ── Roles (used by Team / user management) ──
// Keys are GF tokens (lowercased backend role codes; see ROLE_IN/ROLE_OUT in
// integrate.js). ADMIN is a system role and is never offered in a role picker.
GF.ROLES = {
  admin:   { en: 'Administrator',          mk: 'Администратор' },
  owner:   { en: 'Owner',                  mk: 'Сопственик' },
  ceo:     { en: 'CEO',                    mk: 'Извршен директор' },
  coo:     { en: 'COO',                    mk: 'Оперативен директор' },
  qa_mgr:  { en: 'QA Manager',             mk: 'Менаџер за КО' },
  qc_mgr:  { en: 'QC Manager',             mk: 'Менаџер за КК' },
  pr_mgr:  { en: 'Production Manager',     mk: 'Менаџер за производство' },
  wh_mgr:  { en: 'Warehouse Manager',      mk: 'Менаџер за магацин' },
  se_mgr:  { en: 'Security Manager',       mk: 'Менаџер за обезбедување' },
  cu_mgr:  { en: 'Cultivation Manager',    mk: 'Менаџер за одгледување' },
  mu_mgr:  { en: 'Maintenance Manager',    mk: 'Менаџер за одржување' },
  qp:      { en: 'Qualified Person',       mk: 'Квалификувано лице' },
  operator:{ en: 'Operator',               mk: 'Оператор' },
};
GF.roleLabel = (r) => (GF.ROLES[r] ? GF.ROLES[r][GF.state.lang] || GF.ROLES[r].en : r);
GF.AVATAR_COLORS = ['#2FD9D9','#2BE8A0','#E0A73E','#7A5BE0','#E5484D','#0EA5A5','#D6336C','#C2410C','#8FB6A6','#0891B2'];

// ── QC/LIMS role gates (uppercase backend role codes) ──
// Shared write / Qualified-Person / Head-of-QC role arrays for the QC/LIMS
// screens (samples, custody, spec, potency, lab, register, genealogy, coa,
// ecoa, oos, leaves) — previously copy-pasted verbatim (as local `_WRITERS` /
// `_QP` / `_HOQC` consts) across ten separate view files. Single source now;
// each view's canWrite()/canQP()/canApprove()-style helper reads these.
GF.QC_WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
GF.QC_QP = ['ADMIN', 'QP'];
GF.QC_HOQC = ['ADMIN', 'QC_MGR', 'QP'];

// ── Permissions per role ──
//   own = only on tasks the user is Accountable/Responsible for
// Executives + all managers get the full row (like the old admin/hod);
// operator (USER) is own-tasks-only. Unknown roles fall back to operator.
const _FULL = { create: true, editAny: true, deleteAny: true, status: 'any', team: true };
GF.PERMS = {
  admin: _FULL, owner: _FULL, ceo: _FULL, coo: _FULL,
  qa_mgr: _FULL, qc_mgr: _FULL, pr_mgr: _FULL, wh_mgr: _FULL, se_mgr: _FULL, cu_mgr: _FULL, mu_mgr: _FULL, qp: _FULL,
  operator: { create: true, editAny: false, deleteAny: false, status: 'own', team: false },
};
GF.curRole = () => (GF.PEOPLE[GF.state.user] || {}).role || 'operator';
GF.perms = () => GF.PERMS[GF.curRole()] || GF.PERMS.operator;
GF.ownsTask = (t) => !!t && (t.owner === GF.state.user || (t.helpers || []).includes(GF.state.user));
GF.can = (action, t) => {
  const p = GF.perms();
  switch (action) {
    case 'create': return !!p.create;
    case 'team':   return !!p.team;
    case 'edit':   return p.editAny || GF.ownsTask(t);
    case 'delete': return !!p.deleteAny;
    case 'status':
      if (p.status === 'any') return true;
      if (p.status === 'own') return GF.ownsTask(t);
      return false;
    default: return false;
  }
};
GF.denyToast = () => GF.toast(GF.state.lang === 'mk'
  ? 'Немате дозвола за ова (улога: ' + GF.roleLabel(GF.curRole()) + ')'
  : 'Not permitted for your role (' + GF.roleLabel(GF.curRole()) + ')', 'error');

// ── Executive scope ──
// Managers already have full task perms; executives (Owner/CEO/COO) get the
// SAME task capabilities PLUS an exec-only Executive Overview with cross-
// department metrics, department-visibility toggles, and dependency/batch-flow
// observation — things lower roles never see. Admin is included so it can
// preview the executive experience.
GF.EXEC_ROLES = new Set(['owner', 'ceo', 'coo', 'admin']);
GF.isExec = () => GF.EXEC_ROLES.has(GF.curRole());
// Departments an executive has hidden from their overview (persisted per browser).
GF.state.execHidden = (() => {
  try { const s = JSON.parse(localStorage.getItem('gf_exec_hidden') || '[]'); return new Set(Array.isArray(s) ? s : []); }
  catch (e) { return new Set(); }
})();
GF.execDeptShown = (id) => !GF.state.execHidden.has(id);
GF.toggleExecDept = (id) => {
  const s = GF.state.execHidden; s.has(id) ? s.delete(id) : s.add(id);
  try { localStorage.setItem('gf_exec_hidden', JSON.stringify([...s])); } catch (e) {}
  if (GF.render && GF.render.all) GF.render.all();
};
GF.resetExecDepts = () => {
  GF.state.execHidden.clear();
  try { localStorage.setItem('gf_exec_hidden', '[]'); } catch (e) {}
  if (GF.render && GF.render.all) GF.render.all();
};
// Whole-week tasks minus hidden departments — the executive overview is a
// full-week read and deliberately ignores the sidebar day/tag/search filters.
GF.execTasks = (weekId) => GF.weekTasks(weekId).filter(t => !GF.state.execHidden.has(t.dept));
GF.t = (k) => (GF.I18N[GF.state.lang] && GF.I18N[GF.state.lang][k]) || GF.I18N.en[k] || k;
// The ad-hoc bilingual picker every view uses for strings that aren't worth a
// GF.I18N key. A bare top-level const (not GF.AL) so every classic <script>
// tag loaded after this one can call it unqualified, same as the rest of this
// file's globals — canonical home for what used to be 8 separate copies
// scattered across view files (all subtly different: some skipped the
// `GF.state &&` guard and would throw before state exists, others returned
// `undefined` instead of the English fallback).
const AL = (en, mk) => (GF.state && GF.state.lang === 'mk') ? mk : en;
GF.dep = (id) => GF.DEPTS.find(d => d.id === id) || GF.DEPTS[0];
GF.depName = (id) => { const d = GF.dep(id); return GF.state.lang === 'mk' ? d.mk : d.name; };
// Compact, language-neutral abbreviation (QC, QA, WH…) for cards/chips; falls
// back to the full name if a department has none.
GF.depAbbr = (id) => { const d = GF.dep(id); return (d && d.abbr) || (d ? d.name : ''); };
GF.statusLabel = (s) => GF.STATUS[s] ? GF.STATUS[s][GF.state.lang] : s;
GF.prLabel = (p) => GF.PRIORITY[p] ? GF.PRIORITY[p][GF.state.lang] : p;
GF.dayLabel = (d) => { const i = GF.DAYS.indexOf(d); return GF.state.lang === 'mk' && i >= 0 ? GF.DAYS_MK[i] : d; };
GF.taskTypeLabel = (t) => { const l = GF.TASK_TYPE_LABELS && GF.TASK_TYPE_LABELS[t]; return l ? (l[GF.state.lang] || l.en) : t; };

// Shared KPI-tile markup (label above value, optional sub-line) — the .ana-*
// classes analytics/auditprep/execreport all use for their summary strips.
// A wrapping container of either `ana-tiles` (grid) or `xr-kpis` (flex) is
// the caller's choice. report-view.js's own centered, per-status-colored
// stat card (_sc()) is a genuinely different design (color-coded by status,
// not a plain label+value) and stays separate rather than being forced into
// this shape.
// Escapes like every sibling markup helper in this file. Callers pass only
// static labels and numbers today, so this changes no current output — it
// closes the trap for the next caller that passes a task title or a department
// name, which is exactly how the escaping bugs in the last round happened.
// Optional `tone` tints the value good/bad/warn (green/red/amber) — the exec
// cockpit's KPI band uses it to flag on-time vs overdue at a glance. It's a
// fixed keyword from calling code (never user data), but whitelisted anyway so
// it can never inject a class, matching this helper's escaping discipline.
// Optional `subTone` does the same for the sub-line: callers that need a
// colored badge there (e.g. "3 overdue") pass plain text in `sub` plus a
// `subTone` keyword — the color is applied HERE, inside the function that
// already escapes `sub`, instead of a call site building a raw `<span
// style=...>` string that GF.esc would then neuter into visible tag text.
GF.kpiTile = (label, value, sub, tone, subTone) => {
  const t = (tone === 'good' || tone === 'bad' || tone === 'warn') ? ' ana-tv--' + tone : '';
  const st = (subTone === 'good' || subTone === 'bad' || subTone === 'warn') ? ' ana-ts--' + subTone : '';
  return `<div class="ana-tile">
  <div class="ana-tl">${GF.esc(label)}</div><div class="ana-tv${t}">${GF.esc(value)}</div>
  ${sub ? `<div class="ana-ts${st}">${GF.esc(sub)}</div>` : ''}</div>`;
};

// ── Calendar ──
GF.calendar = { weeks: [], todayId: 0 };
(function genWeeks() {
  const now = new Date();
  const dow = (now.getDay() + 6) % 7;                 // 0 = Monday
  const monday = new Date(now); monday.setDate(now.getDate() - dow); monday.setHours(0,0,0,0);
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const start = new Date(monday); start.setDate(monday.getDate() - 4 * 7);  // 4 weeks back
  for (let i = 0; i < 14; i++) {
    const s = new Date(start); s.setDate(start.getDate() + i * 7);
    // End of the SEVENTH day, not its midnight. `s` inherits 00:00:00.000 from
    // the anchor Monday, so a plain +6 days put `e` at Sunday 00:00:00.000 and
    // the `now <= e` test below went false for all but the first millisecond of
    // Sunday — no week matched, todayId kept its initial 0, and the app opened
    // four weeks in the past every Sunday. `end` is also what the date->week
    // lookups elsewhere compare with `d <= w.end`, so they shared the bug.
    const e = new Date(s); e.setDate(s.getDate() + 6); e.setHours(23,59,59,999);
    const num = Math.ceil(((s - new Date(s.getFullYear(),0,1)) / 86400000 + 1) / 7);
    GF.calendar.weeks.push({
      id: i, start: s, end: e, weekNum: num, monthIndex: s.getMonth(), year: s.getFullYear(),
      label: `${MONTHS[s.getMonth()]} ${s.getDate()} – ${MONTHS[e.getMonth()]} ${e.getDate()}`,
      short: `W${num}`,
    });
    if (now >= s && now <= e) GF.calendar.todayId = i;
  }
  GF.state.selWeek = GF.calendar.todayId;
})();
GF.todayDay = GF.DAYS[(new Date().getDay() + 6) % 7];
// Format a Date using its LOCAL (browser/facility) calendar day — unlike
// `d.toISOString()`, which always converts to UTC first: for any positive
// UTC offset (e.g. Europe/Skopje), converting a local midnight back through
// toISOString() lands on the PREVIOUS UTC day, silently shifting date-only
// values by one day. Due-date strings are plain (no offset) local days, so
// any "what day is this Date" conversion must go through local getters.
GF.localDateStr = (d) => {
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
GF.todayISO = () => GF.localDateStr(new Date());

// ── Storage ──
// integrate.js (loaded last) overrides both methods before this is ever
// called in normal operation — it always drives tasks from the real API.
// This localStorage path only matters if integrate.js itself fails to load.
GF.store = {
  load() {
    try { GF.people.load(); } catch (e) {}
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem('gf_tasks_v1')); } catch {}
    if (saved && Array.isArray(saved)) GF.state.tasks = saved;
    // integrate.js's override (the normal path) renders itself once real data
    // arrives — this fallback is the only case where load() must also paint
    // the UI, since nothing else will.
    if (GF.render && GF.render.all) GF.render.all();
  },
  save() { try { localStorage.setItem('gf_tasks_v1', JSON.stringify(GF.state.tasks)); } catch {} },
};

GF.task = (id) => GF.state.tasks.find(t => t.id === id)
  // Child rows (theme → document → version tree) resolve too, so worklog/edit
  // opened from a tree row find their task like any board card's would.
  || Object.values(GF.state.children || {}).flat().find(t => t.id === id);

// ── People (team) persistence + CRUD ──
GF.people = {
  load() {
    try {
      const saved = JSON.parse(localStorage.getItem('gf_people_v1'));
      if (saved && typeof saved === 'object') Object.assign(GF.PEOPLE, saved);
    } catch (e) {}
  },
  save() { try { localStorage.setItem('gf_people_v1', JSON.stringify(GF.PEOPLE)); } catch (e) {} },
  initials(name) {
    return String(name || '?').trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?';
  },
};

// ── Status cycle ──
GF.cycleStatus = (id) => {
  const t = GF.task(id); if (!t) return;
  if (!GF.can('status', t)) return GF.denyToast();
  const i = GF.STATUS_ORDER.indexOf(t.status);
  t.status = GF.STATUS_ORDER[(i + 1) % GF.STATUS_ORDER.length];
  GF.store.save(); GF.render.panels(); GF.render.telemetry();
};
GF.setStatus = (id, status) => {
  const t = GF.task(id); if (!t || !GF.STATUS[status]) return false;
  if (!GF.can('status', t)) { GF.denyToast(); return false; }
  if (t.status === status) return false;
  t.status = status;
  GF.store.save();
  return true;
};
GF.toggleDone = (id) => {
  const t = GF.task(id); if (!t) return;
  if (!GF.can('status', t)) return GF.denyToast();
  const becameDone = t.status !== 'done';
  t.status = t.status === 'done' ? 'working' : 'done';
  GF.store.save(); GF.render.panels(); GF.render.telemetry();
  if (becameDone && GF.flashCompleted) GF.flashCompleted(id);
};

// ── Filters / nav ──
GF.weekTasks = (weekId) => GF.state.tasks.filter(t => t.weekId === weekId && !t.parentId);
GF.visibleTasks = (weekId) => {
  const { selDay, deptFilter, tagFilter, search, user } = GF.state;
  const q = search.trim().toLowerCase();
  return GF.weekTasks(weekId).filter(t => {
    if (selDay !== 'All' && !(t.days || []).includes(selDay)) return false;
    if (deptFilter && t.dept !== deptFilter) return false;
    if (tagFilter && !(t.tags || []).includes(tagFilter)) return false;
    if (q && !(`${t.title} ${t.id}`.toLowerCase().includes(q))) return false;
    return true;
  });
};
// Like visibleTasks but WITHOUT the day filter — for views that present their
// own day dimension (Timeline) or aggregate the whole week (Coordination,
// Dashboard). Still applies dept/tag/search so the sidebar filter is honored
// there too (they previously used unfiltered weekTasks and ignored it).
GF.scopedTasks = (weekId) => {
  const { deptFilter, tagFilter, search } = GF.state;
  const q = search.trim().toLowerCase();
  return GF.weekTasks(weekId).filter(t => {
    if (deptFilter && t.dept !== deptFilter) return false;
    if (tagFilter && !(t.tags || []).includes(tagFilter)) return false;
    if (q && !(`${t.title} ${t.id}`.toLowerCase().includes(q))) return false;
    return true;
  });
};
GF.setTagFilter = (tag) => { GF.state.tagFilter = tag || null; GF.render.panels(); };

GF.setLang = (l) => { GF.state.lang = l; localStorage.setItem('gf_lang', l); GF.render.all(); };

// ── Themes / skins (data-driven, extensible) ──
// <html data-theme> is the single source of truth (an inline <head> script in
// index.html sets it from localStorage before any CSS paints — no flash).
// The 3 CORE skins live in app.css; the 30 CARBON skins in skins.css, which
// also carry a data-skin-carbon marker (set by setTheme + the boot script) so
// their shared derived-token block applies. Adding a skin = one CSS block +
// one row here; the 3D leaf auto-derives its colour from the active tokens.
// Core (non-Carbon) skins: their full derived-token sets live in app.css /
// mass-weed.css, so they never carry the data-skin-carbon marker.
GF.THEME_CORE = { 'mass-weed': 1, 'mass-weed-light': 1 };
GF.THEMES = [
  // EXCLUSIVE MASS WEED (owner directive 2026-07-31): the app has ONE visual
  // identity — the Mass Weed HUD — as a dark and a daylight variant, re-huable
  // via GF.MW_SKINS ("ONE identity, MANY hues", the design's own model). The
  // pre-Mass-Weed dark/light/suma AND the 30 carbon skins are RETIRED: any
  // saved id heals to the identity of the same brightness (GF.healTheme; the
  // index.html boot script mirrors it before first paint).
  { id: 'mass-weed',       name: 'Mass Weed',             group: 'dark' },
  { id: 'mass-weed-light', name: 'Mass Weed · Cool Mist', group: 'light' },
];
// Retired-theme healing: light-family ids keep their brightness on Cool Mist;
// every other retired/unknown id lands on the dark HUD.
GF.LEGACY_LIGHT = ['light', 'amber-glow-light', 'aurora-light', 'azure-silence-light',
  'blush-slate-light', 'console-horizon-light', 'jade-matrix-light', 'jade-mint-light',
  'kawaii', 'miami-neon-light', 'playlist-mint-light', 'retro-98', 'steel-mist-light',
  'winter-blush-light'];
GF.healTheme = (id) => (GF.themeById(id) ? id
  : GF.LEGACY_LIGHT.indexOf(id) >= 0 ? 'mass-weed-light' : 'mass-weed');
GF.themeById = (id) => GF.THEMES.find(t => t.id === id);
GF.curTheme = () => GF.healTheme(document.documentElement.dataset.theme);
GF.syncThemeBtn = () => {
  const btn = GF.$('theme-btn');
  if (btn) {
    btn.innerHTML = GF.icon('palette');
    const cur = GF.themeById(GF.curTheme());
    btn.title = (GF.state.lang === 'mk' ? 'Тема: ' : 'Theme: ') + (cur ? cur.name : 'Dark') +
      (GF.state.lang === 'mk' ? ' — кликни за избор' : ' — click to choose');
  }
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#060F0B';
};
GF.setTheme = (name, opts) => {
  name = GF.healTheme(name);   // exclusive Mass Weed: retired/unknown ids heal to the identity
  const root = document.documentElement;
  root.dataset.theme = name;
  // Both surviving themes are core (define their own derived tokens); the
  // carbon marker is never set now that the carbon skins are retired.
  root.removeAttribute('data-skin-carbon');
  // noPersist: apply the skin to the DOM WITHOUT recording it as the user's
  // saved preference — the splash/login screen showcases a random skin each
  // load but must never overwrite the real skin the user picked in the app.
  if (!(opts && opts.noPersist)) { try { localStorage.setItem('gf_theme', name); } catch (e) {} }
  GF.syncThemeBtn();
  // Re-tint the 3D leaf logos to the new skin's tokens, in place.
  if (GF.leafFX && GF.leafFX.retintAll) GF.leafFX.retintAll(name);
  if (!(opts && opts.silent) && GF.toast) {
    const t = GF.themeById(name);
    GF.toast((GF.state.lang === 'mk' ? 'Тема: ' : 'Theme: ') + (t ? t.name : name), 'info');
  }
};
// Read every theme's (--primary,--bg) swatch by briefly probing data-theme on
// <html> and restoring it — all synchronous, so no intermediate paint/flash.
GF._themeSwatches = () => {
  const root = document.documentElement;
  const prevTheme = root.dataset.theme, prevCarbon = root.hasAttribute('data-skin-carbon');
  const cs = getComputedStyle(root), out = {};
  GF.THEMES.forEach(t => {
    root.dataset.theme = t.id;
    if (GF.THEME_CORE[t.id]) root.removeAttribute('data-skin-carbon'); else root.setAttribute('data-skin-carbon', '');
    out[t.id] = { primary: cs.getPropertyValue('--primary').trim() || '#2BE8A0', bg: cs.getPropertyValue('--bg').trim() || '#0E1F17' };
  });
  root.dataset.theme = prevTheme;
  if (prevCarbon) root.setAttribute('data-skin-carbon', ''); else root.removeAttribute('data-skin-carbon');
  return out;
};
// Grouped theme PICKER (33 skins don't cycle). One swatch chip per theme.
GF.openThemePicker = () => {
  let el = GF.$('gf-theme-modal');
  if (!el) { el = document.createElement('div'); el.id = 'gf-theme-modal'; el.className = 'overlay'; document.body.appendChild(el); }
  const sw = GF._themeSwatches();
  const cur = GF.curTheme();
  const chip = (t) => `
    <button class="theme-chip ${t.id === cur ? 'on' : ''}" onclick="GF.pickTheme('${t.id}')" title="${GF.esc(t.name)}">
      <span class="theme-sw" style="background:${sw[t.id].bg}"><span style="background:${sw[t.id].primary}"></span></span>
      <span class="theme-nm">${GF.esc(t.name)}</span>
      ${t.id === cur ? GF.icon('check', 'icon theme-ck') : ''}
    </button>`;
  const grid = (group) => `<div class="theme-grid">${GF.THEMES.filter(t => t.group === group).map(chip).join('')}</div>`;
  // Hue dots — shown only while a mass-weed theme is active, because the hue
  // axis re-tints nothing else and a control that visibly does nothing teaches
  // the user the whole panel might be decorative.
  const curSkin = GF.curMWSkin();
  const hueRow = String(cur).startsWith('mass-weed') ? `
        <div class="theme-group-lbl" style="margin-top:14px">${GF.state.lang === 'mk' ? 'Нијанса (Mass Weed)' : 'Hue (Mass Weed)'}</div>
        <div class="mw-skins" role="radiogroup" style="padding:6px 2px">${GF.MW_SKINS.map(k => `
          <button class="mw-skins__dot ${k.id === curSkin ? 'is-active' : ''}" role="radio" aria-checked="${k.id === curSkin}"
            style="--sw:${k.hex}" title="${GF.esc(GF.state.lang === 'mk' ? k.mk : k.en)}"
            onclick="GF.pickMWSkin('${k.id}')"></button>`).join('')}</div>` : '';
  el.innerHTML = `
    <div class="modal" style="max-width:560px">
      <div class="modal-head"><h3>${GF.state.lang === 'mk' ? 'Тема / изглед' : 'Theme / skin'}</h3>
        <button class="btn-ghost" onclick="GF.closeModal('gf-theme-modal')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
      <div class="modal-body">
        <div class="theme-group-lbl">${GF.state.lang === 'mk' ? 'Темни' : 'Dark'}</div>${grid('dark')}
        <div class="theme-group-lbl" style="margin-top:14px">${GF.state.lang === 'mk' ? 'Светли' : 'Light'}</div>${grid('light')}${hueRow}
      </div>
    </div>`;
  GF.openModal('gf-theme-modal');
};
GF.pickTheme = (id) => { GF.setTheme(id); GF.openThemePicker(); };   // re-render to move the check

// ── Mass Weed hue schemes (design mw-i18n.js: "ONE identity, MANY hues") ──
// A SECOND, orthogonal axis to the theme: data-skin on <html> re-hues the two
// mass-weed themes (accent family, backdrop, glow — never the semantic
// green/amber/red) and does nothing to the other 33 skins, so it survives
// theme switches instead of being reset by them. 'alliance' is the original
// cyan and means NO attribute — the default must not depend on a CSS block
// matching, or a typo in the attribute would unstyle the whole shell.
// Ids, hexes and both names come from the design file verbatim;
// tests/frontend/mass-weed-skins.test.js pins them against it.
GF.MW_SKINS = [
  { id: 'alliance', hex: '#5ec8f0', en: 'Alliance', mk: 'Алијанса' },
  { id: 'spectre',  hex: '#3fe0a0', en: 'Spectre',  mk: 'Спектар' },
  { id: 'flux',     hex: '#2fd9d9', en: 'Flux',     mk: 'Флукс' },
  { id: 'paragon',  hex: '#5e7cf0', en: 'Paragon',  mk: 'Парагон' },
  { id: 'omega',    hex: '#c85ef0', en: 'Omega',    mk: 'Омега' },
  { id: 'renegade', hex: '#f0555e', en: 'Renegade', mk: 'Ренегат' },
  { id: 'citadel',  hex: '#f0c05e', en: 'Citadel',  mk: 'Цитадела' },
];
GF.curMWSkin = () => {
  const s = document.documentElement.dataset.skin;
  return GF.MW_SKINS.some(k => k.id === s) ? s : 'alliance';
};
GF.setMWSkin = (id) => {
  const skin = GF.MW_SKINS.find(k => k.id === id) || GF.MW_SKINS[0];
  const root = document.documentElement;
  if (skin.id === 'alliance') delete root.dataset.skin;
  else root.dataset.skin = skin.id;
  try { localStorage.setItem('gf_mw_skin', skin.id); } catch (e) {}
  GF.syncThemeBtn();   // meta theme-color follows --bg, which the hue re-tints
  // The 3D leaf reads the ACTIVE computed tokens, so re-tinting with the
  // current theme id picks up the new hue.
  if (GF.leafFX && GF.leafFX.retintAll) GF.leafFX.retintAll(GF.curTheme());
};
GF.pickMWSkin = (id) => { GF.setMWSkin(id); GF.openThemePicker(); };  // re-render to move the ring
// Back-compat: the header button previously "toggled"; now it opens the picker.
GF.toggleTheme = () => GF.openThemePicker();
GF.setView = (v) => {
  // Cross-module deep links (exec-report "Open in board", the calendar /
  // approvals / ⌘K / search jumps, and document task links — all route through
  // GF.WWF.xrJump → setView('mywork')) target a view that may live in a
  // different module than the active one. Carry the user into that view's
  // module when their role can access it, instead of letting render.all()'s
  // module bounce reset the navigation to the current module's default.
  // modules.js loads after this file, so the helpers are optional-chained; a
  // target module the role CANNOT access is left alone (render.all() then
  // bounces it, preserving the access gate).
  if (GF.moduleForKey && GF.moduleAccessibleFor && GF.state) {
    const mod = GF.moduleForKey(v);
    const role = (GF.API && GF.API.user && GF.API.user.role) || 'USER';
    if (mod && mod !== (GF.state.module || 'tasks') && GF.moduleAccessibleFor(mod, role)) {
      GF.state.module = mod;
      try { localStorage.setItem('gf_module', mod); } catch (e) {}
    }
  }
  GF.state.view = v;
  try { localStorage.setItem('gf_view', v); } catch (e) {}
  if (GF.render && GF.render.all) GF.render.all();
};
GF.setUser = (u) => { GF.state.user = u; localStorage.setItem('gf_user', u); GF.render.all(); };
GF.selectWeek = (id) => { GF.state.selWeek = Math.max(0, Math.min(GF.calendar.weeks.length - 1, id)); GF.render.all(); };
GF.selectDay = (d) => { GF.state.selDay = d; GF.render.panels(); GF.render.dayPills(); };
GF.filterDept = (id) => { GF.state.deptFilter = GF.state.deptFilter === id ? null : id; GF.render.all(); };
GF.toggleExpand = (id) => { const s = GF.state.expanded; s.has(id) ? s.delete(id) : s.add(id); GF.render.panels(); };
GF.toggleTree = (id) => { const s = GF.state.treeOpen; s.has(id) ? s.delete(id) : s.add(id); GF.render.panels(); };
GF.goToday = () => { GF.state.selWeek = GF.calendar.todayId; GF.state.selDay = 'All'; GF.render.all(); };

// Restore focus (caret at end) to an element rebuilt by a full re-render —
// GF.render.all() replaces #panels' innerHTML, destroying the focused search
// box mid-typing. List views call this right after render with the input's
// stable id. Null-safe: missing ids and non-text controls (selects) are fine.
GF.refocus = (id) => {
  const el = GF.$(id);
  if (!el || typeof el.focus !== 'function') return;
  el.focus();
  if (typeof el.setSelectionRange === 'function' && typeof el.value === 'string') {
    try { el.setSelectionRange(el.value.length, el.value.length); } catch (e) {}
  }
};

// ── Modals + toast ──
// Focus management (a11y): remember what had focus when a modal opens and restore
// it on close, so keyboard focus is never orphaned on the now-hidden dialog.
GF.openModal = (id) => {
  GF._modalReturnFocus = document.activeElement;
  GF.$(id).classList.add('open');
};
GF.closeModal = (id) => {
  GF.$(id).classList.remove('open');
  const back = GF._modalReturnFocus;
  GF._modalReturnFocus = null;
  if (back && typeof back.focus === 'function' && document.contains(back)) {
    try { back.focus(); } catch (e) {}
  }
};
GF.toast = (msg, type = 'info') => {
  const c = GF.$('toasts'); if (!c) return;
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  const ic = type === 'success' ? 'check' : type === 'error' ? 'info' : 'info';
  el.innerHTML = GF.icon(ic) + '<span>' + GF.esc(msg) + '</span>';
  c.appendChild(el);
  setTimeout(() => { el.style.transition = 'opacity .3s,transform .3s'; el.style.opacity = '0'; el.style.transform = 'translateX(30px)'; setTimeout(() => el.remove(), 300); }, 3000);
};
