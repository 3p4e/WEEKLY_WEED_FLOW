/* core.js — state, storage, calendar, i18n, icons, helpers. Global: GF */
window.GF = window.GF || {};

GF.$ = (id) => document.getElementById(id);
GF.esc = (s) => String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
GF.uid = () => 'T-' + Math.random().toString(36).slice(2, 7).toUpperCase();

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
GF.dep = (id) => GF.DEPTS.find(d => d.id === id) || GF.DEPTS[0];
GF.depName = (id) => { const d = GF.dep(id); return GF.state.lang === 'mk' ? d.mk : d.name; };
// Compact, language-neutral abbreviation (QC, QA, WH…) for cards/chips; falls
// back to the full name if a department has none.
GF.depAbbr = (id) => { const d = GF.dep(id); return (d && d.abbr) || (d ? d.name : ''); };
GF.statusLabel = (s) => GF.STATUS[s] ? GF.STATUS[s][GF.state.lang] : s;
GF.prLabel = (p) => GF.PRIORITY[p] ? GF.PRIORITY[p][GF.state.lang] : p;
GF.dayLabel = (d) => { const i = GF.DAYS.indexOf(d); return GF.state.lang === 'mk' && i >= 0 ? GF.DAYS_MK[i] : d; };
GF.taskTypeLabel = (t) => { const l = GF.TASK_TYPE_LABELS && GF.TASK_TYPE_LABELS[t]; return l ? (l[GF.state.lang] || l.en) : t; };

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
    const e = new Date(s); e.setDate(s.getDate() + 6);
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
  },
  save() { try { localStorage.setItem('gf_tasks_v1', JSON.stringify(GF.state.tasks)); } catch {} },
};

GF.task = (id) => GF.state.tasks.find(t => t.id === id);

// ── People (team) persistence + CRUD ──
GF.people = {
  load() {
    try {
      const saved = JSON.parse(localStorage.getItem('gf_people_v1'));
      if (saved && typeof saved === 'object') Object.assign(GF.PEOPLE, saved);
    } catch (e) {}
  },
  save() { try { localStorage.setItem('gf_people_v1', JSON.stringify(GF.PEOPLE)); } catch (e) {} },
  upsert(id, person) {
    if (!id) id = 'u_' + Math.random().toString(36).slice(2, 8);
    GF.PEOPLE[id] = { ...(GF.PEOPLE[id] || {}), ...person };
    this.save();
    return id;
  },
  remove(id) {
    if (!GF.PEOPLE[id]) return;
    // reassign their tasks back to current user so nothing is orphaned
    GF.state.tasks.forEach(t => {
      if (t.owner === id) t.owner = GF.state.user === id ? 'marko' : GF.state.user;
      t.helpers = (t.helpers || []).filter(h => h !== id);
    });
    if (GF.state.user === id) GF.state.user = 'marko';
    delete GF.PEOPLE[id];
    GF.store.save(); this.save();
  },
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
  t.status = t.status === 'done' ? 'working' : 'done';
  GF.store.save(); GF.render.panels(); GF.render.telemetry();
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
GF.THEME_CORE = { dark: 1, light: 1, suma: 1 };   // the 3 non-Carbon skins
GF.THEMES = [
  // Core
  { id: 'dark',  name: 'Plasma (default)', group: 'dark' },
  { id: 'suma',  name: 'SUMA · Protoss',   group: 'dark' },
  { id: 'light', name: 'Cool Mist',        group: 'light' },
  // Carbon — dark
  { id: 'blurple-chat',      name: 'Blurple Chat',      group: 'dark' },
  { id: 'blush-slate-dark',  name: 'Blush Slate',       group: 'dark' },
  { id: 'code-forge',        name: 'Code Forge',        group: 'dark' },
  { id: 'digital-rain',      name: 'Digital Rain',      group: 'dark' },
  { id: 'ebony-amber',       name: 'Ebony Amber',       group: 'dark' },
  { id: 'forest',            name: 'Forest',            group: 'dark' },
  { id: 'heart-of-darkness', name: 'Heart of Darkness', group: 'dark' },
  { id: 'indigo-turquoise',  name: 'Indigo Turquoise',  group: 'dark' },
  { id: 'lambda-core',       name: 'Lambda Core',       group: 'dark' },
  { id: 'mocha-paws',        name: 'Mocha (Catppuccin)',group: 'dark' },
  { id: 'nightfang',         name: 'Nightfang (Dracula)',group: 'dark' },
  { id: 'nord',              name: 'Nord',              group: 'dark' },
  { id: 'nordic',            name: 'Nordic',            group: 'dark' },
  { id: 'solo-night',        name: 'Solo Night',        group: 'dark' },
  { id: 'tropical-midnight', name: 'Tropical Midnight', group: 'dark' },
  { id: 'vapor-classic',     name: 'Vapor Classic',     group: 'dark' },
  { id: 'vapor-deck',        name: 'Vapor Deck',        group: 'dark' },
  // Carbon — light
  { id: 'amber-glow-light',     name: 'Amber Glow',      group: 'light' },
  { id: 'aurora-light',         name: 'Aurora',          group: 'light' },
  { id: 'azure-silence-light',  name: 'Azure Silence',   group: 'light' },
  { id: 'blush-slate-light',    name: 'Blush Slate',     group: 'light' },
  { id: 'console-horizon-light',name: 'Console Horizon', group: 'light' },
  { id: 'jade-matrix-light',    name: 'Jade Matrix',     group: 'light' },
  { id: 'jade-mint-light',      name: 'Jade Mint',       group: 'light' },
  { id: 'kawaii',               name: 'Kawaii',          group: 'light' },
  { id: 'miami-neon-light',     name: 'Miami Neon',      group: 'light' },
  { id: 'playlist-mint-light',  name: 'Playlist Mint',   group: 'light' },
  { id: 'retro-98',             name: 'Retro 98',        group: 'light' },
  { id: 'steel-mist-light',     name: 'Steel Mist',      group: 'light' },
  { id: 'winter-blush-light',   name: 'Winter Blush',    group: 'light' },
];
GF.themeById = (id) => GF.THEMES.find(t => t.id === id);
GF.curTheme = () => {
  const t = document.documentElement.dataset.theme;
  return GF.themeById(t) ? t : 'dark';
};
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
  if (!GF.themeById(name)) name = 'dark';
  const root = document.documentElement;
  root.dataset.theme = name;
  // Carbon skins need the marker so skins.css's derived-token block applies;
  // the 3 core skins must NOT have it (they define their own derived tokens).
  if (GF.THEME_CORE[name]) root.removeAttribute('data-skin-carbon');
  else root.setAttribute('data-skin-carbon', '');
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
  el.innerHTML = `
    <div class="modal" style="max-width:560px">
      <div class="modal-head"><h3>${GF.state.lang === 'mk' ? 'Тема / изглед' : 'Theme / skin'}</h3>
        <button class="btn-ghost" onclick="GF.closeModal('gf-theme-modal')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
      <div class="modal-body">
        <div class="theme-group-lbl">${GF.state.lang === 'mk' ? 'Темни' : 'Dark'}</div>${grid('dark')}
        <div class="theme-group-lbl" style="margin-top:14px">${GF.state.lang === 'mk' ? 'Светли' : 'Light'}</div>${grid('light')}
      </div>
    </div>`;
  GF.openModal('gf-theme-modal');
};
GF.pickTheme = (id) => { GF.setTheme(id); GF.openThemePicker(); };   // re-render to move the check
// Back-compat: the header button previously "toggled"; now it opens the picker.
GF.toggleTheme = () => GF.openThemePicker();
GF.setView = (v) => {
  GF.state.view = v;
  try { localStorage.setItem('gf_view', v); } catch (e) {}
  if (GF.render && GF.render.all) GF.render.all();
};
GF.setUser = (u) => { GF.state.user = u; localStorage.setItem('gf_user', u); GF.render.all(); };
GF.selectWeek = (id) => { GF.state.selWeek = Math.max(0, Math.min(GF.calendar.weeks.length - 1, id)); GF.render.all(); };
GF.selectDay = (d) => { GF.state.selDay = d; GF.render.panels(); GF.render.dayPills(); };
GF.filterDept = (id) => { GF.state.deptFilter = GF.state.deptFilter === id ? null : id; GF.render.all(); };
GF.toggleExpand = (id) => { const s = GF.state.expanded; s.has(id) ? s.delete(id) : s.add(id); GF.render.panels(); };
GF.goToday = () => { GF.state.selWeek = GF.calendar.todayId; GF.state.selDay = 'All'; GF.render.all(); };

// ── Modals + toast ──
GF.openModal = (id) => GF.$(id).classList.add('open');
GF.closeModal = (id) => GF.$(id).classList.remove('open');
GF.toast = (msg, type = 'info') => {
  const c = GF.$('toasts'); if (!c) return;
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  const ic = type === 'success' ? 'check' : type === 'error' ? 'info' : 'info';
  el.innerHTML = GF.icon(ic) + '<span>' + GF.esc(msg) + '</span>';
  c.appendChild(el);
  setTimeout(() => { el.style.transition = 'opacity .3s,transform .3s'; el.style.opacity = '0'; el.style.transform = 'translateX(30px)'; setTimeout(() => el.remove(), 300); }, 3000);
};
