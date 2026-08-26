/* integrate.js — bridges the GrowFlow UI to the real WEEKLY_WEED_FLOW backend.
   Loaded LAST. Replaces the localStorage/seed data layer with live API data:
   login -> load real departments/weeks/tasks -> render GrowFlow UI -> writes go to the API. */
window.GF = window.GF || {};
GF.WWF = {};

/* ── enum mapping (backend <-> GrowFlow) ───────────────────────────── */
const S_IN  = { ongoing:'working', completed:'done', pending:'pending', stuck:'stuck', review:'review', postponed:'postponed' };
const S_OUT = { working:'ongoing', done:'completed', pending:'pending', stuck:'stuck', review:'review', postponed:'postponed' };
const P_IN  = { normal:'medium', medium:'medium', high:'high', critical:'critical', low:'low' };
const P_OUT = { medium:'normal', high:'high', critical:'critical', low:'low' };
// Colours are the DESIGN SYSTEM's brief hexes, verbatim from the DEPTS config
// in design/mass-weed-mockup/depthome-*.html — five of seven had drifted to
// app-local values, so a department rendered one colour in the mockups and
// another in the product. tests/frontend/mass-weed-dept-colors.test.js pins
// this table (and the --dept-* CSS tokens) to the design source.
const DEPT_STYLE = {
  cultivation:{icon:'leaf',color:'#2BE8A0'}, vegetation:{icon:'leaf',color:'#3FA34D'},
  production:{icon:'box',color:'#2FD9D9'}, qc:{icon:'flask',color:'#9B7BE8'},
  quality_control:{icon:'flask',color:'#9B7BE8'}, quality_assurance:{icon:'shield',color:'#E0743A'},
  logistics:{icon:'box',color:'#22B8D8'}, tooling:{icon:'wrench',color:'#8496B2'},
  security:{icon:'shield',color:'#7C90AE'},
};
// Short, language-neutral department abbreviations (QC, QA, WH…), shown on the
// compact task cards / chips; the full bilingual name shows in lists + dropdowns.
const DEPT_ABBR = {
  qc:'QC', quality_control:'QC', quality_assurance:'QA', production:'PR', cultivation:'CU',
  tooling:'MU', logistics:'WH', security:'SE',
};
// Cross-department handoff pipeline, keyed by the backend's department `code`
// (resolved to real ids once /departments loads — see loadAndRender).
const CODE_HANDOFF = {
  cultivation:'production', production:'qc', qc:'quality_assurance',
  quality_control:'quality_assurance', quality_assurance:'logistics',
};

GF.WWF.meId = 'me';

// GrowFlow role keys <-> backend role enum. GF key = lowercased backend code
// (USER keeps the historical 'operator' key — GF.PERMS/curRole default to it).
const ROLE_OUT = { admin:'ADMIN', owner:'OWNER', ceo:'CEO', coo:'COO', qa_mgr:'QA_MGR', qc_mgr:'QC_MGR',
  pr_mgr:'PR_MGR', wh_mgr:'WH_MGR', se_mgr:'SE_MGR', cu_mgr:'CU_MGR', mu_mgr:'MU_MGR', qp:'QP', operator:'USER' };
const ROLE_IN  = { ADMIN:'admin', OWNER:'owner', CEO:'ceo', COO:'coo', QA_MGR:'qa_mgr', QC_MGR:'qc_mgr',
  PR_MGR:'pr_mgr', WH_MGR:'wh_mgr', SE_MGR:'se_mgr', CU_MGR:'cu_mgr', MU_MGR:'mu_mgr', QP:'qp', USER:'operator' };
// Backend roles that are "elevated" (must mirror app/roles.py ELEVATED_ROLES /
// the DB app.is_elevated()). Everything but USER.
const ELEVATED_ROLES = ['ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR','SE_MGR','CU_MGR','MU_MGR','QP'];
// Roles with no department affiliation — default the dept picker to "None" for these.
const NO_DEPT_ROLES = new Set(['owner', 'ceo', 'coo', 'qp']);
// The 9 department-manager roles (create only USER staff in their own dept).
const MANAGER_ROLES = ['QA_MGR','QC_MGR','PR_MGR','WH_MGR','SE_MGR','CU_MGR','MU_MGR','QP'];
GF.WWF.colorFor = (id) => {
  const c = (GF.AVATAR_COLORS && GF.AVATAR_COLORS.length) ? GF.AVATAR_COLORS
    : ['#2FD9D9','#15A86B','#E0A73E','#7A5BE0','#E5484D','#0EA5A5','#D6336C','#2BE8A0'];
  let h = 0; String(id).split('').forEach(ch => h = (h * 31 + ch.charCodeAt(0)) >>> 0);
  return c[h % c.length];
};

GF.WWF.transform = (t) => ({
  id: t.id, title: t.title, desc: t.description || '',
  dept: t.department_id || (GF.DEPTS[0] && GF.DEPTS[0].id),
  owner: t.user_id || GF.WWF.meId,
  helpers: (t.assignee_ids || []).filter(id => id !== t.user_id),
  status: S_IN[t.status] || 'pending', pr: P_IN[t.priority] || 'medium',
  days: Array.isArray(t.days) ? t.days.map(d => d.slice(0,3)) : [],
  weekId: GF.WWF.weekIndex(t),
  tags: t.tags || [],
  notes: (t.progress_notes || []).map(n => ({ d:(n.day_label||'').slice(0,3), n:n.note||n, by:n.user_id||null })),
  blocker: t.blocker_reason || '', completed_date: t.completed_date, week_start: t.week_start,
  est: t.estimated_hours != null ? Number(t.estimated_hours) : null,
  act: t.actual_hours != null ? Number(t.actual_hours) : null,
  // v2 model
  type: t.task_type || 'other', ref: t.reference_code || '',
  due: t.due_date || null, recurrence: t.recurrence || null,
  outcome: t.outcome || '', archived: !!t.is_archived, parentId: t.parent_id || null,
  attrs: t.attributes || {},
  sessionHours: t.session_hours != null ? Number(t.session_hours) : 0,
  subCount: Number(t.subtask_count || 0), subDone: Number(t.subtask_done_count || 0),
  progressPct: t.progress != null ? Number(t.progress) : 0,
});

GF.WWF.weekIndex = (t) => {
  const W = GF.calendar.weeks;
  if (t.week_id) { const i = W.findIndex(w => w.realId === t.week_id); if (i >= 0) return i; }
  if (t.week_start) { const d = new Date(t.week_start);
    const i = W.findIndex(w => d >= w.start && d <= w.end); if (i >= 0) return i; }
  return GF.calendar.todayId;
};

/* ── Archived visibility ───────────────────────────────────────────
   GET /tasks hides archived rows by default (tasks.py include_archived=false);
   the "Show archived" toggle reloads the list with include_archived=true so
   archiving stops being a one-way trapdoor — archived cards render muted with
   an "Archived" chip and an Unarchive action (worklog.js). */
GF.WWF.taskQuery = () => (GF.state.showArchived ? { include_archived: true } : {});

// Rebuild GF.state.tasks/children from a raw /tasks payload — the single
// shared path for the initial load and the archived-toggle reload.
// Children (subtasks / sub-subtasks) never render as board rows — index
// them by parent for the tree toggle on parent cards (theme → document →
// version). Same transform as any task; sorted oldest-first so a theme's
// documents read chronologically. GF.state.tasks stays parents-only —
// exec/report/board views all assume that.
GF.WWF.applyTasks = (tasks) => {
  GF.state.tasks = tasks.filter(t => !t.parent_id).map(GF.WWF.transform);
  GF.state.children = {};
  tasks.filter(t => t.parent_id).map(GF.WWF.transform).forEach(c => {
    (GF.state.children[c.parentId] = GF.state.children[c.parentId] || []).push(c);
  });
  Object.values(GF.state.children).forEach(list =>
    list.sort((a, b) => String(a.week_start || '9999').localeCompare(String(b.week_start || '9999'))));
};

GF.WWF.toggleArchived = async () => {
  GF.state.showArchived = !GF.state.showArchived;
  // A fast double-toggle fires two overlapping /tasks fetches; without this,
  // whichever call happens to resolve LAST wins and can apply a stale
  // (archived or not) task list against the toggle's now-opposite state.
  const my = (GF.WWF._archivedLseq = (GF.WWF._archivedLseq || 0) + 1);
  try {
    const tasks = (await GF.API.tasks(GF.WWF.taskQuery())) || [];
    if (my !== GF.WWF._archivedLseq) return;
    GF.WWF.applyTasks(tasks);
  } catch (e) {
    if (my !== GF.WWF._archivedLseq) return;
    GF.state.showArchived = !GF.state.showArchived;   // revert; keep the current list
    GF.toast(AL('Tasks: ', 'Задачи: ') + e.message, 'error');
  }
  if (my !== GF.WWF._archivedLseq) return;
  GF.render.all();
};

/* ── build the calendar from the backend's real weeks ──────────────── */
GF.WWF.buildCalendar = (weeks) => {
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const ws = (weeks || []).slice().sort((a,b)=> new Date(a.starts_on) - new Date(b.starts_on));
  const now = new Date(); let todayId = 0;
  // Map into a local first — only replace the calendar once we know we have
  // real weeks. Assigning the (empty) result before the length check would
  // wipe core.js's generated fallback and blank week navigation when /weeks
  // is empty or failed.
  // calendar_weeks.starts_on/ends_on are DATE columns, so the API sends a bare
  // 'YYYY-MM-DD'. `new Date('2026-08-02')` is parsed as UTC midnight, which in a
  // UTC+2 facility is 02:00 LOCAL — so `now <= e` went false from 02:00 onward
  // every Sunday, no week matched, and todayId fell back to 0. Because /weeks is
  // re-sorted ascending above, 0 is the OLDEST week in the table, so the app
  // opened on ancient data every Sunday afternoon. Parse both as explicit LOCAL
  // times and make the end inclusive of its whole day; `end` is also what the
  // `d <= w.end` date->week lookups compare against, so they are fixed with it.
  const dayOnly = (v) => String(v).slice(0, 10);
  const mapped = ws.map((w,i) => {
    const s = new Date(dayOnly(w.starts_on) + 'T00:00:00');
    const e = new Date(dayOnly(w.ends_on) + 'T23:59:59.999');
    if (now >= s && now <= e) todayId = i;
    return { id:i, realId:w.id, start:s, end:e, weekNum:w.iso_week, monthIndex:s.getMonth(), year:s.getFullYear(),
      label:`${MONTHS[s.getMonth()]} ${s.getDate()} – ${MONTHS[e.getMonth()]} ${e.getDate()}`, short:`W${w.iso_week}` };
  });
  if (!mapped.length) return;   // keep core.js's generated fallback weeks
  GF.calendar.weeks = mapped;
  // ensure "today" lands on the last week if all data is in the past
  if (todayId === 0 && now > GF.calendar.weeks[GF.calendar.weeks.length-1].end) todayId = GF.calendar.weeks.length-1;
  GF.calendar.todayId = todayId; GF.state.selWeek = todayId;
};

/* ── login overlay ─────────────────────────────────────────────────── */
// GF.WWF.showLogin / showChangePw are defined by entry.js (loaded after this
// file), which presents the interactive splash instead — this file only owns
// the actual auth calls (doLogin / doChangePw) that presentation reuses.
GF.WWF.doLogin = async () => {
  const u = (GF.$('wwf-u')||{}).value, p = (GF.$('wwf-p')||{}).value;
  const m = GF.$('wwf-login-msg');
  if (m) m.textContent = GF.state.lang === 'mk' ? 'Најавување…' : 'Signing in…';
  try {
    const data = await GF.API.login(u, p);
    if (data.user && data.user.must_change_password) { GF.WWF.showChangePw(p); return; }
    try { sessionStorage.setItem('wwf_show_module_picker', '1'); } catch (e) {}
    GF.$('wwf-login').style.display = 'none'; await GF.WWF.loadAndRender();
  } catch (e) {
    if (!m) return;
    if (e.message === 'unauthorized') {
      m.textContent = GF.state.lang === 'mk' ? 'Погрешно корисничко име или лозинка' : 'Invalid username or password';
    } else if (e.status === 429) {
      m.textContent = GF.state.lang === 'mk' ? 'Премногу обиди — обидете се повторно подоцна' : e.message;
    } else {
      m.textContent = (GF.state.lang === 'mk' ? 'Грешка: ' : 'Error: ') + e.message;
    }
  }
};

/* ── first-login password change (must_change_password) ────────────── */
GF.WWF.doChangePw = async () => {
  const a = (GF.$('wwf-np')||{}).value || '', b = (GF.$('wwf-np2')||{}).value || '';
  const m = GF.$('wwf-login-msg');
  const mk = GF.state.lang === 'mk';
  if (a.length < 8) { if (m) m.textContent = mk ? 'Лозинката мора да има најмалку 8 карактери' : 'Password must be at least 8 characters'; return; }
  if (a !== b) { if (m) m.textContent = mk ? 'Лозинките не се совпаѓаат' : 'Passwords do not match'; return; }
  if (m) m.textContent = mk ? 'Зачувување…' : 'Saving…';
  try {
    await GF.API.changePassword(a, GF.WWF._curPw);
    try { GF.API.user = await GF.API.me(); sessionStorage.setItem('wwf_user', JSON.stringify(GF.API.user)); } catch (e) {}
    try { sessionStorage.setItem('wwf_show_module_picker', '1'); } catch (e2) {}
    GF.$('wwf-login').style.display = 'none'; await GF.WWF.loadAndRender();
  } catch (e) { if (m) m.textContent = (mk ? 'Грешка: ' : 'Error: ') + e.message; }
};

/* ── load real data + render ───────────────────────────────────────── */
GF.WWF.loadTeam = async () => {
  // /auth/directory works for every role (no elevated gate) so avatars,
  // week-strip, and assignee pickers show the real org roster for everyone —
  // /auth/users (full management fields) is only used by the Team admin view.
  let users = null;
  try { users = await GF.API.directory(); } catch (e) { users = [GF.API.user].filter(Boolean); }
  GF.PEOPLE = {};
  (users || []).forEach(p => { if (!p || !p.id) return;
    GF.PEOPLE[p.id] = {
      name: p.full_name || p.username, username: p.username,
      init: ((p.full_name || p.username || 'U').trim().split(/\s+/).slice(0,2).map(x => x[0]).join('').toUpperCase()) || 'U',
      role: ROLE_IN[p.role] || 'operator', roleLabel: p.function_role || p.role || '',
      fn: p.function_role || '',
      // Keep null as null — don't invent a department for cross-org roles
      // (Owner/CEO/COO/QP) that were explicitly assigned "None". A prior
      // version defaulted this to GF.DEPTS[0], silently reassigning every
      // no-department account to whatever the first real department was.
      dept: p.department_id || null, bg: GF.WWF.colorFor(p.id),
      backendRole: p.role, mcp: p.must_change_password, active: p.is_active };
  });
  const me = GF.API.user;
  if (me && me.id && !GF.PEOPLE[me.id]) GF.PEOPLE[me.id] = {
    name: me.full_name || me.username, username: me.username, init: 'ME',
    role: ROLE_IN[me.role] || 'operator', roleLabel: me.function_role || '',
    dept: me.department_id || null, bg: GF.WWF.colorFor(me.id), backendRole: me.role };
};

/* ── Cross-login cache hygiene ──────────────────────────────────────
   Each view IIFE declares its GF.WWF._* state literal once at script load —
   it survives a logout, so a re-login on the same tab would render the
   PREVIOUS account's cached data until every lazy loader happened to refire.
   resetCaches() mutates each known cache back to a neutral empty shape
   (arrays → [] , data fields → null, per-id maps emptied, loading/error →
   idle) while keeping pure UI preferences (tab/kind/filters) as they are.
   Written defensively (typeof checks throughout) so it never throws when a
   view file didn't load. Called at the top of loadAndRender. */
GF.WWF.resetCaches = () => {
  // taskId-keyed map caches: every own key IS another user's data — drop all.
  // _collabSeq goes too, so an in-flight loadCollab from the old session can
  // never land (its captured seq no longer matches anything).
  ['_extras', '_collab', '_collabSeq'].forEach(k => {
    const m = GF.WWF[k];
    if (m && typeof m === 'object' && !Array.isArray(m)) Object.keys(m).forEach(id => { delete m[id]; });
  });
  // Fields that are per-id map caches INSIDE a view state (emptied in place,
  // never nulled — their readers index them directly).
  const MAP_FIELDS = {
    _xr: ['docs', 'open'], _qccus: ['custody'],
    _qcecoa: ['mapParams', 'verify', 'vhist', 'qa', 'chunks', 'chunksOpen', 'exParams'],
  };
  // Data-bearing fields whose "not loaded yet" shape is null (the views'
  // lazy loaders gate on falsy) — null them even when currently a string id.
  // _notif's items/feed are deliberately NOT here: their initial shape is []
  // (readers call .filter on them unconditionally); its `loaded` flag drives
  // the refetch instead.
  const DATA_FIELDS = new Set(['data', 'docs', 'detail', 'sel', 'digest', 'plans', 'specs',
    'samples', 'coas', 'water', 'stab', 'trn', 'rqs', 'sfr', 'rqsAll', 'pick', 'parent',
    'ph', 'editEx', 'specParams']);
  ['_qcs', '_qcsm', '_qccoa', '_qcecoa', '_qccus', '_qcl', '_fac', '_xr', '_apv', '_notif'].forEach(k => {
    const st = GF.WWF[k];
    if (!st || typeof st !== 'object') return;
    const maps = MAP_FIELDS[k] || [];
    Object.keys(st).forEach(f => {
      const v = st[f];
      if (maps.indexOf(f) >= 0) {
        if (v && typeof v === 'object') Object.keys(v).forEach(id => { delete v[id]; });
        else st[f] = {};
        return;
      }
      if (f === 'q') { st[f] = ''; return; }
      if (f === 'status' && typeof v === 'string') { st[f] = ''; return; }
      if (typeof v === 'boolean') { st[f] = false; return; }                 // loading / loaded / open flags
      if (typeof v === 'number') { if (f !== 'seq') st[f] = 0; return; }     // unread etc.; seq guards async races
      if (f === 'error' || /Error$/.test(f)) { st[f] = null; return; }
      if (Array.isArray(v)) { st[f] = DATA_FIELDS.has(f) ? null : []; return; }
      if (v && typeof v === 'object') { st[f] = null; return; }              // detail / data / digest / status(_xr)
      if (typeof v === 'string' && DATA_FIELDS.has(f)) { st[f] = null; return; }  // stale selection ids
      // everything else (tab / kind / refDate / filter / digestWindow, nulls) keeps its value
    });
  });
  // Assistant chat thread (assistant.js re-greets when msgs is empty).
  if (GF.assistant && Array.isArray(GF.assistant.msgs)) GF.assistant.msgs.length = 0;
};

GF.WWF.loadAndRender = async () => {
  // Never render one account's cached module data under another's session.
  GF.WWF.resetCaches();
  const u = GF.API.user || {};
  GF.WWF.meId = u.id || 'me';
  GF.state.user = GF.WWF.meId;
  // Load each independently so one failure never blanks the UI.
  //
  // 401 is the one exception, and it has to be, because it is not a per-call
  // failure — the session is gone and api.js has ALREADY logged out and put
  // the login overlay back up. Treating it like any other error meant an
  // expired token produced three separate "unauthorized" toasts stacked on top
  // of the login card, and then this function carried on to loadTeam(),
  // buildCalendar() and applyTasks(), rendering an empty app behind the
  // overlay. Bail on the first one instead: there is nothing left to load and
  // nothing left to render.
  let depts = [], weeks = [], tasks = [];
  let expired = false;
  const _authGone = (e) => (e && (e.status === 401 || e.message === 'unauthorized'));
  try { depts = (await GF.API.departments()) || []; }
  catch (e) { if (_authGone(e)) expired = true; else GF.toast(AL('Departments: ', 'Оддели: ') + e.message, 'error'); }
  // A /weeks failure is non-fatal — buildCalendar keeps core.js's generated
  // fallback weeks — but tell the user rather than silently swallowing it.
  if (!expired) {
    try { weeks = (await GF.API.weeks()) || []; }
    catch (e) { if (_authGone(e)) expired = true; else GF.toast(AL('Weeks: ', 'Недели: ') + e.message, 'error'); }
  }
  if (!expired) {
    try { tasks = (await GF.API.tasks(GF.WWF.taskQuery())) || []; }
    catch (e) { if (_authGone(e)) expired = true; else GF.toast(AL('Tasks: ', 'Задачи: ') + e.message, 'error'); }
  }
  if (expired) return;
  if (depts.length) {
    GF.DEPTS = depts.map(d => { const st = DEPT_STYLE[d.code] || {icon:'box',color:'#5A6B82'};
      // `code` rides along so dept-templates.js can resolve the department's
      // field template / presets / home layout from the backend code.
      return { id:d.id, code:d.code, name:d.name, mk:d.name_mk || d.name,
               abbr: DEPT_ABBR[d.code] || (d.code || '').toUpperCase().slice(0, 3),
               icon:st.icon, color:st.color }; });
    // Resolve the code-keyed handoff pipeline to the real backend ids.
    const byCode = {}; depts.forEach(d => { byCode[d.code] = d.id; });
    GF.HANDOFF = {};
    Object.entries(CODE_HANDOFF).forEach(([from, to]) => {
      if (byCode[from] && byCode[to]) GF.HANDOFF[byCode[from]] = byCode[to];
    });
  }
  await GF.WWF.loadTeam();
  // Role-aware landing for a FRESH browser only (no persisted gf_view):
  // TRUE executives (Owner/CEO/COO — not ADMIN, whose exec access is a
  // preview convenience, and whose real account here is a working manager)
  // land on the exec overview; department members (operators and dept
  // managers alike) on their department home. Deliberately not persisted —
  // GF.setView stores the choice once the user actually navigates.
  if (!localStorage.getItem('gf_view')) {
    const role = (GF.API.user || {}).role;
    if (role === 'OWNER' || role === 'CEO' || role === 'COO') GF.state.view = 'exec';
    else if (GF.hasDeptHome && GF.hasDeptHome()) GF.state.view = 'depthome';
  }
  GF.WWF.buildCalendar(weeks);
  GF.WWF.applyTasks(tasks);
  // If current week is empty, navigate to the most recent past week that has tasks
  if (GF.state.tasks.filter(t => t.weekId === GF.state.selWeek).length === 0 && GF.state.tasks.length > 0) {
    const taskWeeks = [...new Set(GF.state.tasks.map(t => t.weekId))]
      .filter(w => Number.isFinite(w) && w < GF.state.selWeek);
    if (taskWeeks.length) GF.state.selWeek = Math.max(...taskWeeks);
  }
  try {
    GF.render.all();
  } catch (e) {
    console.error('[WWF] render error', e);
    GF.toast(AL('Render error: ', 'Грешка при прикажување: ') + (e && e.message || e), 'error');
  }
  // One-shot module picker on fresh login / password change / demo entry.
  try {
    if (sessionStorage.getItem('wwf_show_module_picker') === '1') {
      sessionStorage.removeItem('wwf_show_module_picker');
      if (GF.openModulePicker) GF.openModulePicker({ mandatory: true });
    }
  } catch (e) {}
};

/* ── persistence overrides (writes -> API) ─────────────────────────── */
GF.WWF.install = () => {
  GF.store.load = () => {
    if (!GF.API.token) { GF.WWF.showLogin(); return; }
    // A token can be persisted (login succeeded) from a session that never
    // finished the forced first-login password change — go straight back to
    // that screen instead of letting loadAndRender() 403 on every call.
    if (GF.API.user && GF.API.user.must_change_password) { GF.WWF.showChangePw(); return; }
    GF.WWF.loadAndRender().catch(()=>GF.WWF.showLogin());
  };
  GF.store.save = () => {};   // explicit API calls below own persistence

  const origCycle = GF.cycleStatus, origSet = GF.setStatus, origToggle = GF.toggleDone;
  // Revert the optimistic status change if the save fails (permission lost,
  // task deleted/reassigned, network error) so the UI never shows an unsaved
  // status as if it were persisted.
  const pushStatus = async (id, prevStatus) => { const t = GF.task(id); if (!t) return;
    try {
      const resp = await GF.API.updateTask(id, { status: S_OUT[t.status] || 'pending' });
      if (resp && resp.completed_date !== undefined) t.completed_date = resp.completed_date;
      // Completion forward-fills progress=100 server-side — mirror it so the
      // local bar doesn't lag until the next full reload.
      if (resp && resp.progress !== undefined) t.progressPct = Number(resp.progress);
      // Completing a recurring task auto-creates its next instance server-side.
      if (t.status === 'done' && resp && resp.next_instance) {
        GF.state.tasks.push(GF.WWF.transform(resp.next_instance));
        GF.render.all();
        GF.toast(GF.state.lang === 'mk' ? 'Следната повторлива задача е креирана ✓' : 'Next recurring task created ✓', 'success');
      }
      // Non-blocking follow-up prompts (defined in worklog.js, loaded later):
      // outcome note on completion, blocker reason when stuck.
      if (t.status === 'done' && GF.WWF.promptOutcome) GF.WWF.promptOutcome(id);
      else if (t.status === 'stuck' && GF.WWF.promptBlocker) GF.WWF.promptBlocker(id);
    }
    catch(e){ if (prevStatus !== undefined) { t.status = prevStatus; GF.render.panels(); } GF.toast(e.message || 'Save failed','error'); } };
  // Re-entrancy guard, same GF.once() pattern as submitAdd/submitUser below —
  // but keyed on the TASK id rather than a button id, since these three fire
  // from per-task inline controls (a checkbox, a status-cycle click, a picker
  // pick), not one shared modal button. A fast double-click computed its PATCH
  // body from the mutating LOCAL status, so two overlapping in-flight
  // requests could race and let network timing — not the user's actual last
  // click — decide what got persisted. Sharing one key ('status-'+id) across
  // all three functions guards any combination of them on the SAME task,
  // while a different task id is never blocked (GF.once's busy flag is keyed
  // per id, and GF.$('status-'+id) resolves to no real DOM node, so the
  // disable/re-enable it also does is a harmless no-op here).
  // GF.once's synchronous prefix — the busy check, then this callback's own
  // code up to its first genuine await (pushStatus's fetch) — still runs
  // before GF.once(...) returns, so callers reading GF.setStatus's return
  // value synchronously (render.js's status picker, worklog.js) keep working:
  // a dropped (already-busy) call yields `false`, exactly like a rejected one.
  GF.cycleStatus = (id) => { GF.once('status-' + id, async () => {
    const t = GF.task(id); const prev = t && t.status; origCycle(id); await pushStatus(id, prev);
  }); };
  GF.toggleDone = (id) => { GF.once('status-' + id, async () => {
    const t = GF.task(id); const prev = t && t.status; origToggle(id); await pushStatus(id, prev);
  }); };
  GF.setStatus = (id, s) => {
    let ok = false;
    GF.once('status-' + id, async () => {
      const t = GF.task(id); const prev = t && t.status;
      ok = origSet(id, s);
      if (ok) await pushStatus(id, prev);
    });
    return ok;
  };

  GF.deleteTask = (id) => GF.toast(GF.state.lang==='mk'?'Бришењето е оневозможено (ревизија)':'Delete disabled (audit retention)','info');

  const origAddNote = GF.addNote;
  GF.addNote = (taskId) => { const el = GF.$('note-'+taskId); const v = el && el.value.trim();
    origAddNote(taskId);
    if (v) GF.API.addProgress(taskId, { day_label: GF.todayDay, note: v }).catch(()=>{}); };

  // GF.once spans the ENTIRE chain below — translate, then createTask, then
  // the per-helper assign loop. The old inline guard only covered the
  // translate step and re-enabled the button while the create was still to
  // come, so a second click duplicated the task (H6).
  GF.submitAdd = () => GF.once('add-submit-btn', async () => {
    const title = (GF.$('add-title')?.value||'').trim();
    if (!title) { GF.toast(AL('Enter a title','Внесете наслов'),'error'); return; }
    const days = [...GF.$('add-days').querySelectorAll('.on')].map(el => el.dataset.day);
    const deptId = GF.$('add-dept').value;
    const wk = GF.calendar.weeks[GF._addWeek] || GF.calendar.weeks[GF.calendar.todayId];
    // v2 fields (due date, typology, recurrence)
    const dueDate = GF.$('add-due')?.value || null;
    const refCode = (GF.$('add-ref')?.value || '').trim() || null;
    const recFreq = GF.$('add-rec')?.value || '';
    // "Every N" interval + optional end date (backend _check_recurrence:
    // interval must be an int in 1..1000, until an ISO date). Clamp
    // client-side so a stray value degrades gracefully instead of 422-ing
    // the whole save; `until` is omitted entirely when empty.
    const recN = parseInt(GF.$('add-rec-n')?.value, 10);
    const recInterval = Number.isFinite(recN) ? Math.max(1, Math.min(1000, recN)) : 1;
    const recUntil = GF.$('add-rec-until')?.value || null;
    const recurrence = recFreq
      ? Object.assign({ freq: recFreq, interval: recInterval }, recUntil ? { until: recUntil } : {})
      : null;
    // Comma-separated free tags; bounded client-side to the backend's 422
    // limits (≤32 tags, ≤64 chars each) so a long paste degrades gracefully.
    const tags = (GF.$('add-tags')?.value || '').split(',')
      .map(s => s.trim()).filter(Boolean).slice(0, 32).map(s => s.slice(0, 64));

    // Bilingual on Save: every task the app creates/edits is stored bilingual
    // "Македонски | English" regardless of the language it was typed in. A brief
    // spinner runs on the Save button while the AI translates; it falls back to
    // the typed text if the AI is unavailable, so the save is never blocked.
    // GF.once owns `disabled` (and restores the label) for the whole chain —
    // only the transient label changes here, so the button cannot come back
    // alive between the translate and the create.
    const btn = GF.$('add-submit-btn');
    const btnLabel = btn ? btn.textContent : '';
    if (btn) btn.innerHTML = `<span class="spinner"></span> ${AL('Translating…','Преведување…')}`;
    // The typed description (the design's create page has a real Description
    // field) rides through the same bilingual pass as the title; if the AI is
    // unavailable the typed text ships as-is.
    const typedDesc = (GF.$('add-desc')?.value || '').trim();
    let biTitle = title, biDesc = typedDesc;
    try { const bi = await GF.ai.bilingual(title, typedDesc); biTitle = bi.title; biDesc = bi.description || typedDesc; }
    finally { if (btn) btn.textContent = btnLabel; }

    // Edit mode (openEdit in worklog.js sets GF._editTask) → PATCH instead of POST.
    if (GF._editTask) {
      const id = GF._editTask, t = GF.task(id);
      try {
        const patched = await GF.API.updateTask(id, {
          title: biTitle, description: biDesc, priority: P_OUT[GF.$('add-pr').value]||'normal',
          // Send the department text alongside the id (as the create path
          // does) — reports.py groups the department breakdown by the text
          // column, so updating only department_id leaves the two out of sync.
          department_id: deptId, department: (GF.dep(deptId)||{}).name || null,
          days: days.length?days:[GF.todayDay],
          due_date: dueDate,
          task_type: GF.$('add-type')?.value || 'other', reference_code: refCode,
          recurrence, tags,
          // Whole-object replace; collect starts from the task's existing
          // attributes so keys outside the current dept template survive.
          attributes: GF.collectDeptAttrs ? GF.collectDeptAttrs(deptId, (t && t.attrs) || {}) : undefined,
        });
        // Persist Responsible changes: diff the selected chips against the
        // task's current helpers and add/remove via the collab endpoints.
        // Exclude the task OWNER (not the editing session's user — those
        // differ whenever a non-owner Responsible helper is the one editing)
        // since the owner is implicit and never an explicit assignee.
        const desired = [...GF.$('add-resp').querySelectorAll('.on')]
          .map(el => el.dataset.who).filter(w => w !== (t && t.owner));
        // GF._editHelpers (populated by worklog.js's openEdit from the real
        // assignees endpoint) is the ground truth; t.helpers is only a
        // fallback for the rare case that fetch hadn't resolved yet.
        const current = GF._editHelpers || (t && t.helpers) || [];
        // The backend's assign/unassign endpoints require the task owner or
        // an elevated role (collab.py's _can_manage_task) — mirror that gate
        // here (GF.WWF.canManageTask matches it exactly) so a non-owner
        // helper doesn't get a confusing per-person 403 for every attempted
        // change; instead, tell them up front that the change won't stick.
        const respChanged = desired.some(w => !current.includes(w)) || current.some(w => !desired.includes(w));
        // Local state must mirror what was actually PERSISTED: when the
        // helper-editor path is refused (info toast below), the card keeps
        // showing the saved set — never the desired-but-rejected one.
        let persistedHelpers = current;
        if (respChanged && t && GF.WWF.canManageTask(t)) {
          for (const who of desired) if (!current.includes(who)) {
            try { await GF.API.assign(id, who); }
            catch (e) { GF.toast(AL('Could not assign ', 'Не може да се додели ') + ((GF.PEOPLE[who]||{}).name||who) + ': ' + e.message, 'error'); }
          }
          for (const who of current) if (!desired.includes(who)) {
            try { await GF.API.unassign(id, who); }
            catch (e) { GF.toast(AL('Could not unassign ', 'Не може да се отстрани доделувањето за ') + ((GF.PEOPLE[who]||{}).name||who) + ': ' + e.message, 'error'); }
          }
          persistedHelpers = desired;
        } else if (respChanged) {
          GF.toast(AL("Only the task owner or a manager can change who's responsible.",
                      'Само сопственикот на задачата или менаџер може да ја смени одговорноста.'), 'info');
        }
        if (t) { const keep = { weekId: t.weekId, notes: t.notes, helpers: persistedHelpers, subCount: t.subCount, subDone: t.subDone, sessionHours: t.sessionHours };
          Object.assign(t, GF.WWF.transform(patched), keep); }
        // Only reset the shared edit-session globals / close the modal if
        // they still refer to THIS save — if the user has since opened a
        // different edit session (openEdit reassigns these synchronously),
        // clobbering them here would discard that other session's state and
        // force-close its modal out from under the user.
        if (GF._editTask === id) { GF._editTask = null; GF._editHelpers = null; GF.closeModal('add-modal'); }
        GF.render.all(); GF.toast(GF.t('save')+' ✓','success');
      } catch(e) { GF.toast(AL('Save failed: ','Неуспешно зачувување: ')+e.message,'error'); }
      return;
    }

    // Accountable (add-owner) has no backend counterpart — POST /tasks always
    // owns the task as the creator (TaskIn has no owner field) — so only
    // Responsible (helpers) is actually assignable; wire it the same way
    // GF.voice.createFromVoice does for its single ownerMatch.
    const helperIds = GF._addParent ? [] :
      [...GF.$('add-resp').querySelectorAll('.on')].map(el => el.dataset.who).filter(w => w !== GF.WWF.meId);

    try {
      const created = await GF.API.createTask({
        title: biTitle, description: biDesc, status:'pending', priority: P_OUT[GF.$('add-pr').value]||'normal',
        department_id: deptId, department:(GF.dep(deptId)||{}).name, week_id: wk && wk.realId,
        week_start: wk ? GF.localDateStr(wk.start) : null, days: days.length?days:[GF.todayDay],
        due_date: dueDate, task_type: GF.$('add-type')?.value || 'other',
        reference_code: refCode, recurrence, tags, parent_id: GF._addParent || null,
        attributes: GF.collectDeptAttrs ? GF.collectDeptAttrs(deptId) : undefined,
      });
      if (GF._addParent) {
        // Subtasks never render as top-level cards — bump the parent's counter instead.
        const parent = GF.task(GF._addParent);
        if (parent) parent.subCount = (parent.subCount || 0) + 1;
        GF._addParent = null;
      } else {
        GF.state.tasks.push(GF.WWF.transform(created));
      }
      GF.closeModal('add-modal'); GF.render.all(); GF.toast(GF.t('create_task')+' ✓','success');
      for (const who of helperIds) {
        try { await GF.API.assign(created.id, who); } catch (e) {
          GF.toast(AL('Could not assign ', 'Не може да се додели ') + ((GF.PEOPLE[who]||{}).name||who) + ': ' + e.message, 'error'); }
      }
      if (helperIds.length) { await GF.WWF.loadCollab(created.id); GF.render.panels(); }
    } catch(e) { GF.toast(AL('Create failed: ','Неуспешно креирање: ')+e.message,'error'); }
  });

  // AI features -> real backend Letta functions (/ai/{function_key}, body: {input}).
  // Every call degrades to "AI agent unavailable" when no binding is configured —
  // see backend/app/api/ai.py — instead of throwing.
  GF.ai = GF.ai || {};
  GF.ai.summary = async (kind) => {
    GF.$('ai-out').innerHTML = `<div class="ai-loading"><span class="spinner"></span>${GF.t('generate')}…</div>`;
    if (GF.$('ai-modal-title')) GF.$('ai-modal-title').textContent = AL('AI Summary', 'AI резиме');
    if (GF.$('ai-close-btn')) GF.$('ai-close-btn').textContent = GF.t('close');
    GF.openModal('ai-modal');
    try {
      const wk = GF.calendar.weeks[GF.state.selWeek + (kind==='plan'?1:0)] || GF.calendar.weeks[GF.state.selWeek];
      const tasks = GF.weekTasks(wk ? wk.id : GF.state.selWeek);
      const body = tasks.map(t => `- [${t.status}] ${t.title} (${GF.depName(t.dept)}, ${t.pr})`).join('\n') || '(no tasks)';
      const prompt = (kind === 'plan'
        ? 'Analyse next week\'s plan: priorities, risks, workload. Bullet points.\n\n'
        : 'Summarise this week\'s status: completed, in-progress, blockers. Bullet points.\n\n') + body;
      const r = await GF.API.ai('weekly_summary', { input: prompt, context: { week_id: wk && wk.realId, kind } });
      const text = (r && r.available) ? r.output : (AL('AI agent unavailable', 'АИ агентот е недостапен') + (r && r.reason ? ' (' + r.reason + ')' : ''));
      GF.$('ai-out').innerHTML = `<div class="ai-out">${GF.esc(text)}</div>`;
    } catch(e) { GF.$('ai-out').innerHTML = `<div class="ai-out">${AL('AI error', 'АИ грешка')}: ${GF.esc(e.message)}</div>`; }
  };

  GF.ai.paraphraseInput = async (inputId) => {
    const el = GF.$(inputId); if (!el || !el.value.trim()) return;
    const orig = el.value.trim();
    GF.toast(GF.t('paraphrase') + '…', 'info');
    try {
      const r = await GF.API.ai('draft_description', { input:
        `Rewrite this task note as one clear professional sentence for a GMP cannabis facility. Keep batch/room IDs.\n\n${orig}` });
      if (r && r.available && r.output) el.value = r.output.trim();
      else GF.toast(AL('AI unavailable', 'АИ е недостапен'), 'info');
    } catch (e) { GF.toast(AL('AI error: ', 'АИ грешка: ') + e.message, 'error'); }
  };

  GF.ai.paraphraseTask = async (taskId) => {
    const t = GF.task(taskId); if (!t || !t.desc) { GF.toast(AL('Nothing to rewrite', 'Нема што да се преформулира'), 'info'); return; }
    GF.toast(GF.t('paraphrase') + '…', 'info');
    try {
      const r = await GF.API.ai('draft_description', { input: `Rewrite concisely for GMP cannabis: ${t.desc}` });
      if (!(r && r.available && r.output)) { GF.toast(AL('AI unavailable', 'АИ е недостапен'), 'info'); return; }
      const rewritten = r.output.trim();
      // Only mutate local state once the backend save succeeds — otherwise a
      // failed PATCH leaves the card showing text that was never persisted.
      await GF.API.updateTask(taskId, { description: rewritten });
      t.desc = rewritten;
      GF.render.panels(); GF.toast(AL('Rewritten ✓', 'Преформулирано ✓'), 'success');
    } catch (e) { GF.toast(AL('AI error: ', 'АИ грешка: ') + e.message, 'error'); }
  };

  // Translate a task into the bilingual "Македонски | English" format the
  // platform stores everything in. Short-circuits when the title is already
  // bilingual, and falls back to the raw text if the AI is unavailable — the
  // caller (GF.submitAdd) must never be blocked from saving.
  GF.ai.bilingual = async (title, description) => {
    const desc = description || '';
    if ((title || '').includes(' | ')) return { title, description: desc };  // already МК | EN
    try {
      const r = await GF.API.bilingual({ title, description: desc || null });
      if (r && r.available && r.title) return { title: r.title, description: (r.description != null ? r.description : desc) };
    } catch (e) {}
    return { title, description: desc };
  };

  GF.ai.parseVoice = async (transcript) => {
    const depts = GF.DEPTS.map(d => GF.state.lang === 'mk' ? d.mk : d.name);
    const people = Object.entries(GF.PEOPLE).map(([, p]) => p.name);
    try {
      const r = await GF.API.ai('voice_capture', { input:
        `Parse this spoken task into JSON {title,department,priority,assignee,due,days}. ` +
        `The platform is bilingual: title MUST contain both languages as ` +
        `"<Македонски наслов> | <English title>" — translate whichever half is missing. ` +
        `Valid depts: ${depts.join(', ')}. Valid people: ${people.join(', ')}. ` +
        `priority: critical|high|medium|low. Return ONLY JSON.\n\n"${transcript}"` });
      if (r && r.available && r.output) {
        const m = r.output.match(/\{[\s\S]*\}/);
        if (m) return JSON.parse(m[0]);
      }
    } catch (e) {}
    return { title: transcript };
  };

  if (GF.assistant) {
    // assistant.js's own send()/_maybeEnrich() gate on provider() === 'none'
    // (checking window.claude / GF.state.aiBase) before ever calling complete() —
    // neither is set now that complete() always targets the real backend, so
    // without this override the chat/enrichment paths never fire at all.
    GF.assistant.provider = () => 'backend';
    GF.assistant.statusInfo = () => ({
      dot: 'var(--green)', on: true,
      label: GF.state.lang === 'mk' ? 'Поврзан' : 'Connected',
    });
    GF.assistant.complete = async (prompt) => {
      const r = await GF.API.ai('corpus_qa', { input: prompt });
      if (r && r.available) return r.output || '';
      throw new Error('no-ai');
    };
  }

  // Voice-captured tasks must persist through the same API path as GF.submitAdd.
  GF.voice.createFromVoice = async () => {
    const p = GF.voice._parsed || {};
    // Guard on a non-empty department/assignee before matching — String.includes('')
    // is always true, so without this guard an undetected field would "match"
    // whatever entry happens to be first in GF.DEPTS/GF.PEOPLE.
    const deptQuery = (p.department || '').trim().toLowerCase();
    const deptMatch = deptQuery ? GF.DEPTS.find(d => d.name.toLowerCase().includes(deptQuery)
      || d.mk.toLowerCase().includes(deptQuery)) : null;
    const assigneeQuery = (p.assignee || '').trim().toLowerCase();
    const ownerMatch = assigneeQuery
      ? Object.entries(GF.PEOPLE).find(([, v]) => v.name.toLowerCase().includes(assigneeQuery)) : null;
    const days = Array.isArray(p.days) && p.days.length ? p.days : [GF.todayDay];
    const wk = GF.calendar.weeks[GF.voice._weekId] || GF.calendar.weeks[GF.calendar.todayId];
    try {
      const created = await GF.API.createTask({
        title: p.title || GF.voice._transcript, description: '', status: 'pending',
        priority: P_OUT[p.priority] || 'normal',
        department_id: deptMatch ? deptMatch.id : null, department: deptMatch ? deptMatch.name : null,
        week_id: wk && wk.realId, week_start: wk ? GF.localDateStr(wk.start) : null, days,
      });
      GF.state.tasks.push(GF.WWF.transform(created));
      GF.closeModal('voice-modal'); GF.render.all(); GF.toast(GF.t('create_task') + ' ✓', 'success');
      if (ownerMatch && ownerMatch[0] !== GF.WWF.meId) {
        try {
          await GF.API.assign(created.id, ownerMatch[0]);
          await GF.WWF.loadCollab(created.id);
        } catch (e) { GF.toast(AL('Could not assign ', 'Не може да се додели ') + ownerMatch[1].name + ': ' + e.message, 'error'); }
      }
    } catch (e) { GF.toast(AL('Create failed: ', 'Неуспешно креирање: ') + e.message, 'error'); }
  };

  // Settings modal — replaces the old logout-only gear. Tabs: Preferences,
  // Security (change my own password), AI agent bindings (admin), Account.
  GF._setTab = 'prefs';
  GF.openSettings = (tab) => { GF._setTab = (typeof tab === 'string') ? tab : 'prefs'; GF.WWF.renderSettings(); GF.openModal('settings-modal'); };
  GF.WWF.setTab = (t) => { GF._setTab = t; GF.WWF.renderSettings(); };
  GF.WWF.setLangKeep = (l) => { GF.setLang(l); GF.WWF.renderSettings(); };
  GF.WWF.settingsLogout = () => { if (confirm(AL('Log out of Weekly Weed Flow?', 'Одјава од Weekly Weed Flow?'))) { GF.API.logout(); location.reload(); } };

  GF.WWF.renderSettings = () => {
    const body = GF.$('set-body'); if (!body) return;
    const admin = !!(GF.WWF.isAdmin && GF.WWF.isAdmin());
    if (GF._setTab === 'ai' && !admin) GF._setTab = 'prefs';
    if (GF.$('set-title')) GF.$('set-title').textContent = AL('Settings', 'Поставки');
    const tabs = [['prefs', AL('Preferences', 'Поставки')], ['display', AL('Display', 'Приказ')], ['security', AL('Security', 'Безбедност')]];
    if (admin) tabs.push(['ai', AL('AI agents', 'AI агенти')]);
    tabs.push(['account', AL('Account', 'Сметка')]);
    const bar = tabs.map(([k, l]) => `<button class="set-tab ${GF._setTab === k ? 'on' : ''}" onclick="GF.WWF.setTab('${k}')">${l}</button>`).join('');
    let pane = '';
    if (GF._setTab === 'prefs') {
      const lg = GF.state.lang;
      pane = `<div class="set-pane"><div class="set-row">
          <div><div class="set-lab">${AL('Language', 'Јазик')}</div>
            <div class="set-hint">${AL('Interface language for menus and reports.', 'Јазик на интерфејсот за менијата и извештаите.')}</div></div>
          <div class="seg">
            <button class="seg-b ${lg === 'en' ? 'on' : ''}" onclick="GF.WWF.setLangKeep('en')">English</button>
            <button class="seg-b ${lg === 'mk' ? 'on' : ''}" onclick="GF.WWF.setLangKeep('mk')">Македонски</button>
          </div></div></div>`;
    } else if (GF._setTab === 'display') {
      // Density / character / accent — the engine has lived in
      // tweaks-vanilla.js all along (design-mode only); GF.tweaks makes it a
      // real user preference. Theme itself stays on the header palette button.
      const tw = GF.tweaks ? GF.tweaks.get() : null;
      const segBtn = (key, field, cur, desc) =>
        `<button class="seg-b ${cur === key ? 'on' : ''}" title="${GF.esc(desc || '')}"
           onclick='GF.tweaks.set({"${field}":"${key}"});GF.WWF.renderSettings()'>${GF.esc(key)}</button>`;
      pane = !tw ? `<div class="set-pane set-hint">${AL('Display engine unavailable.', 'Модулот за приказ е недостапен.')}</div>`
        : `<div class="set-pane">
        <div class="set-row"><div><div class="set-lab">${AL('Density', 'Густина')}</div>
            <div class="set-hint">${AL('How much fits on screen.', 'Колку содржина се собира на екранот.')}</div></div>
          <div class="seg">${GF.tweaks.DENSITY_KEYS.map(k => segBtn(k, 'density', tw.density, GF.tweaks.DENSITY_DESC[k])).join('')}</div></div>
        <div class="set-row"><div><div class="set-lab">${AL('Character', 'Карактер')}</div>
            <div class="set-hint">${AL('Corner radius, shadows and type weight.', 'Заобленост, сенки и дебелина на фонтот.')}</div></div>
          <div class="seg">${GF.tweaks.CHAR_KEYS.map(k => segBtn(k, 'character', tw.character, GF.tweaks.CHAR_DESC[k])).join('')}</div></div>
        <div class="set-row"><div><div class="set-lab">${AL('Accent pair', 'Акцентни бои')}</div>
            <div class="set-hint">${AL('Secondary blue/orange accents. "Theme default" follows the active skin.', 'Секундарни акценти. Стандардно ги следи активниот изглед.')}</div></div>
          <div class="seg">${GF.tweaks.PALETTES.map((p, i) =>
            `<button class="seg-b ${tw.paletteIdx === i ? 'on' : ''}" onclick="GF.tweaks.set({paletteIdx:${i}});GF.WWF.renderSettings()">
               <span style="display:inline-block;width:9px;height:9px;border-radius:5px;background:${p.blue}"></span>
               <span style="display:inline-block;width:9px;height:9px;border-radius:5px;background:${p.orange};margin-right:5px"></span>
               ${i === 0 ? AL('Theme default', 'Стандардно') : GF.esc(p.label)}</button>`).join('')}</div></div>
        </div>`;
    } else if (GF._setTab === 'security') {
      pane = `<div class="set-pane">
        <div class="field"><label>${AL('Current password', 'Тековна лозинка')}</label><input id="set-cur" type="password" autocomplete="current-password"></div>
        <div class="field"><label>${AL('New password', 'Нова лозинка')}</label><input id="set-new" type="password" autocomplete="new-password"></div>
        <div class="field"><label>${AL('Confirm new password', 'Потврди нова лозинка')}</label><input id="set-conf" type="password" autocomplete="new-password"></div>
        <div id="set-pw-msg" class="set-msg"></div>
        <button class="btn btn-primary" onclick="GF.WWF.changeMyPassword()">${AL('Change password', 'Смени лозинка')}</button></div>`;
    } else if (GF._setTab === 'ai') {
      pane = `<div class="set-pane"><div class="set-hint" style="margin-bottom:10px">${AL('Point each AI function at a Letta agent. Changes save immediately.', 'Поврзете ја секоја AI функција со Letta агент. Промените се зачувуваат веднаш.')}</div>
        <div id="set-ai"><div class="ai-loading"><span class="spinner"></span>${GF.t('generate')}…</div></div></div>`;
      setTimeout(GF.WWF.renderAiTab, 0);
    } else {
      const u = GF.API.user || {};
      pane = `<div class="set-pane">
        <div class="set-kv"><span>${AL('Name', 'Име')}</span><b>${GF.esc(u.full_name || u.username || '—')}</b></div>
        <div class="set-kv"><span>${AL('Username', 'Корисник')}</span><b>${GF.esc(u.username || '—')}</b></div>
        <div class="set-kv"><span>${AL('Role', 'Улога')}</span><b>${GF.esc(GF.roleLabel(u.role ? (ROLE_IN[u.role] || 'operator') : GF.curRole()))}</b></div>
        <div class="set-kv"><span>${AL('Department', 'Оддел')}</span><b>${GF.esc(u.department_id ? GF.depName(u.department_id) : '—')}</b></div>
        <button class="btn btn-danger" style="margin-top:16px" onclick="GF.WWF.settingsLogout()">${AL('Log out', 'Одјава')}</button></div>`;
    }
    body.innerHTML = `<div class="set-tabs">${bar}</div>${pane}`;
  };

  GF.WWF.changeMyPassword = async () => {
    const cur = (GF.$('set-cur') || {}).value || '', nw = (GF.$('set-new') || {}).value || '', cf = (GF.$('set-conf') || {}).value || '';
    const msg = GF.$('set-pw-msg');
    const show = (t, ok) => { if (msg) { msg.textContent = t; msg.style.color = ok ? 'var(--primary-fg)' : 'var(--red)'; } };
    if (!nw) return show(AL('Enter a new password.', 'Внесете нова лозинка.'));
    if (nw !== cf) return show(AL('New passwords do not match.', 'Лозинките не се совпаѓаат.'));
    try {
      await GF.API.changePassword(nw, cur || null);
      ['set-cur', 'set-new', 'set-conf'].forEach(id => { const el = GF.$(id); if (el) el.value = ''; });
      show(AL('Password changed ✓', 'Лозинката е сменета ✓'), true);
      GF.toast(AL('Password changed ✓', 'Лозинката е сменета ✓'), 'success');
    } catch (e) { show(AL('Failed: ', 'Неуспешно: ') + (e.message || e)); }
  };

  GF.WWF.renderAiTab = async () => {
    const box = GF.$('set-ai'); if (!box) return;
    try {
      const [fns, ag, binds] = await Promise.all([GF.API.aiFunctions(), GF.API.aiAgents(), GF.API.aiBindings()]);
      const agents = (ag && ag.agents) || [];
      const bindByFn = {}; (binds || []).forEach(b => { bindByFn[b.function_key] = b; });
      const catalog = (fns && fns.catalog) || {};
      const agentOptions = [{ v: '', label: AL('— none —', '— ништо —') }]
        .concat(agents.map(a => ({ v: a.id, label: a.name || a.id })));
      const rows = Object.keys(catalog).map(fn => {
        const b = bindByFn[fn] || {};
        return `<div class="ai-bind">
          <div class="ai-bind-h"><b>${GF.esc(fn)}</b>
            <label class="ai-bind-on"><input type="checkbox" ${b.is_active ? 'checked' : ''} onchange="GF.WWF.saveBinding('${fn}')"> ${AL('Active', 'Активно')}</label></div>
          <div class="set-hint">${GF.esc(catalog[fn])}</div>
          ${GF.selectField('ai-sel-' + fn, { value: b.letta_agent_id || '', title: fn, searchable: true,
            options: agentOptions, onPick: () => GF.WWF.saveBinding(fn) })}</div>`;
      }).join('');
      box.innerHTML = agents.length ? rows : `<div class="set-msg">${AL('No Letta agents found.', 'Нема пронајдени Letta агенти.')}</div>`;
    } catch (e) {
      box.innerHTML = `<div class="set-msg" style="color:var(--red)">${AL('Could not load AI settings: ', 'Не може да се вчитаат AI поставки: ')}${GF.esc(e.message || String(e))}</div>`;
    }
  };

  GF.WWF.saveBinding = async (fn) => {
    const sel = GF.$('ai-sel-' + fn); if (!sel) return;
    const agentId = sel.value;
    const cb = sel.closest('.ai-bind').querySelector('input[type=checkbox]');
    const on = cb ? cb.checked : true;
    try {
      if (!agentId) { await GF.API.deleteAiBinding(fn); GF.toast(fn + ': ' + AL('cleared', 'исчистено'), 'info'); }
      else { await GF.API.setAiBinding(fn, { letta_agent_id: agentId, is_active: on }); GF.toast(fn + ' ✓', 'success'); }
    } catch (e) { GF.toast(AL('Save failed: ', 'Неуспешно: ') + (e.message || e), 'error'); }
  };

  // Roll over incomplete tasks to next week. Persists via the real API —
  // the original local-only version mutated state and called the now-no-op
  // GF.store.save(), so tasks appeared to move but reverted on next reload.
  // Bounded to weeks that already exist in GF.calendar.weeks (there is no
  // API to create a calendar_weeks row) rather than faking a week forward.
  GF.rollover = async () => {
    const weekIdx = GF.state.selWeek;
    const nextWeek = GF.calendar.weeks[weekIdx + 1];
    if (!nextWeek) {
      GF.toast(GF.state.lang === 'mk'
        ? 'Следната недела сè уште не е креирана'
        : 'Next week has not been created yet', 'error');
      return;
    }
    const incomplete = GF.weekTasks(weekIdx).filter(t => t.status !== 'done');
    if (!incomplete.length) { GF.toast(AL('All tasks are done — nothing to roll over', 'Сите задачи се завршени — нема што да се пренесе'), 'info'); return; }
    const weekStart = GF.localDateStr(nextWeek.start);
    const results = await Promise.allSettled(incomplete.map(t =>
      GF.API.updateTask(t.id, { week_id: nextWeek.realId, week_start: weekStart })));
    let moved = 0;
    incomplete.forEach((t, i) => { if (results[i].status === 'fulfilled') { t.weekId = nextWeek.id; moved++; } });
    GF.render.all();
    const failed = incomplete.length - moved;
    if (!moved) GF.toast(AL('Roll over failed', 'Пренесувањето не успеа'), 'error');
    else if (failed) GF.toast(AL(`${moved} task(s) rolled over, ${failed} failed`, `${moved} задача(и) пренесени, ${failed} неуспешни`), 'info');
    else GF.toast(AL(`${moved} task(s) rolled to next week`, `${moved} задача(и) пренесени во следната недела`), 'success');
  };
};

GF.WWF.install();

/* ── Board view: "Show archived" toggle in the filter area ──────────
   views.js's board() predates the archive feature; wrap it (same
   monkey-patch pattern as _registerFullPageView) to slot the toggle chip
   between the view head and the lanes. */
if (GF.views && GF.views.board) {
  const _origBoard = GF.views.board.bind(GF.views);
  GF.views.board = () => {
    const chip = `<div class="chips" style="margin:0 4px 10px"><span class="chip-opt ${GF.state.showArchived ? 'on' : ''}"
      onclick="GF.WWF.toggleArchived()">${GF.icon('box', 'icon')}${GF.t('show_archived')}</span></div>`;
    const html = _origBoard();
    const anchor = '<div class="kboard">';
    return html.includes(anchor) ? html.replace(anchor, chip + anchor) : chip + html;
  };
}

/* ── Team / account provisioning (real backend, OTP shown to admin) ── */
// Who may create/deactivate accounts: an admin (incl. qcm.blani, an ADMIN
// titled "QC Manager") or a department manager. Executives are elevated (they
// see the roster + audit) but are NOT account creators — mirrors the backend
// create_user guard (require_role(ADMIN, *MANAGER_ROLES)). ADMIN itself is
// never assignable through the app.
GF.WWF.canProvision = () => {
  const r = (GF.API.user || {}).role;
  return r === 'ADMIN' || MANAGER_ROLES.includes(r);
};

// Frontend mirror of the backend dept_scope (app/deps.py): department managers
// (not QP — org-wide batch certification) are scoped to their own department.
// This drives UI affordances only (sidebar, locked dept picker) — the API
// enforces the actual visibility on GET /tasks and /reports/weekly.
const DEPT_SCOPED_ROLES = new Set(['QA_MGR', 'QC_MGR', 'PR_MGR', 'WH_MGR', 'SE_MGR', 'CU_MGR', 'MU_MGR']);
GF.WWF.deptScope = () => {
  const u = GF.API.user || {};
  return (DEPT_SCOPED_ROLES.has(u.role) && u.department_id) ? u.department_id : null;
};

// Strict ADMIN check — mirrors the AI-bindings endpoints' require_role(ADMIN)
// (backend/app/api/ai.py). Deliberately narrower than canProvision (which also
// admits department managers): reusing canProvision here previously showed the
// Settings "AI agents" tab to managers who then got a raw 403 from every call.
GF.WWF.isAdmin = () => (GF.API.user || {}).role === 'ADMIN';

/* ── Department provisioning (POST /departments, ADMIN-only) ──
   The backend route existed only for the provisioning script — org
   departments could never be created from the app. Idempotent server-side:
   re-POSTing an existing code returns the existing row. */
GF.WWF.openDeptForm = () => {
  if (!GF.WWF.isAdmin()) return;
  GF.WWF._ensureModal('dept-form-modal', '420px');
  GF.$('dept-form-modal-title').textContent = AL('Add department', 'Додади оддел');
  GF.$('dept-form-modal-body').innerHTML = `
    <div class="field"><label>${AL('Code', 'Код')}</label>
      <input id="dept-code" maxlength="64" placeholder="${AL('e.g. logistics', 'пр. logistics')}"></div>
    <div class="field"><label>${AL('Name', 'Име')}</label>
      <input id="dept-name" maxlength="120"></div>
    <div class="field"><label>${AL('Name (Macedonian)', 'Име (МК)')}</label>
      <input id="dept-name-mk" maxlength="120"></div>
    <div class="row" style="gap:10px"><div class="spacer"></div>
      <button class="btn btn-primary" onclick="GF.WWF.saveDept()">${GF.t('save')}</button></div>`;
  GF.openModal('dept-form-modal');
  setTimeout(() => { const f = GF.$('dept-code'); if (f) f.focus(); }, 60);
};

GF.WWF.saveDept = async () => {
  if (!GF.WWF.isAdmin()) return;
  const code = ((GF.$('dept-code') || {}).value || '').trim().toLowerCase();
  const name = ((GF.$('dept-name') || {}).value || '').trim();
  const nameMk = ((GF.$('dept-name-mk') || {}).value || '').trim();
  if (!/^[a-z0-9_]{1,64}$/.test(code)) {   // mirrors DepartmentIn.code server-side
    GF.toast(AL('Code must be lowercase letters, digits, underscore only (1-64 characters)',
                'Кодот смее да содржи само мали букви, цифри и долна црта (1-64 знаци)'), 'error');
    return;
  }
  if (!name) { GF.toast(AL('Enter a department name', 'Внесете име на одделот'), 'error'); return; }
  try {
    await GF.API.createDepartment({ code, name, name_mk: nameMk || null });
    GF.closeModal('dept-form-modal');
    GF.toast(GF.t('save') + ' ✓', 'success');
    await GF.WWF.loadAndRender();
  } catch (e) { GF.toast(AL('Failed: ', 'Неуспешно: ') + e.message, 'error'); }
};

// openUser(id) → edit an existing person (name/role/dept/title + reset password);
// openUser() with no id → create a new account. The Team-card gear icon passes id.
GF.openUser = (id) => {
  if (!GF.WWF.canProvision()) return GF.denyToast();
  const me = GF.API.user || {};
  const iAmAdmin = me.role === 'ADMIN';
  const editing = !!(id && GF.PEOPLE[id]);
  GF._editUser = editing ? id : null;
  const p = editing ? GF.PEOPLE[id] : null;
  // Admin offers every role EXCEPT admin (ADMIN is DB-seeded only, never
  // picked). A manager may only touch Operator staff, locked to their own
  // department. The backend _can_manage enforces both regardless.
  const roleKeys = iAmAdmin ? Object.keys(GF.ROLES).filter(r => r !== 'admin') : ['operator'];
  const curRole = editing ? (p.role || 'operator') : 'operator';
  const roleOptions = roleKeys.map(r => ({ v: r, label: GF.roleLabel(r) }));
  const curDept = editing ? p.dept : me.department_id;
  // Explicit "None" so cross-org roles (Owner / CEO / COO / QP) can be assigned
  // no department right from the picker, instead of the row silently vanishing.
  const deptOptions = [{ v: '', label: AL('None — no department', '— Без оддел —') }]
    .concat(GF.DEPTS.map(d => ({ v: String(d.id), label: GF.depName(d.id), color: d.color })));
  GF.$('user-title').textContent = editing ? GF.t('edit_user') : GF.t('add_user');
  GF.$('user-cancel-btn').textContent = GF.t('cancel');
  GF.$('user-save-btn').textContent = GF.t('save');
  const usernameRow = editing
    ? `<div class="field"><label>Username</label><div style="font:700 15px ui-monospace,monospace;color:var(--ink-2)">${GF.esc(p.username || '')}</div></div>`
    : `<div class="field"><label>Username</label><input id="u-username" placeholder="e.g. ana" autocapitalize="off" autocomplete="off"></div>`;
  const footNote = editing
    ? `<button class="btn btn-danger" style="width:100%;justify-content:center;margin-top:8px" onclick="GF.WWF.resetUserPw('${id}')">${GF.icon('shield','icon')}${AL('Reset password', 'Ресетирај лозинка')}</button>`
    : `<div style="font-size:12px;color:var(--ink-3);margin-top:6px;line-height:1.5">${AL(
        'A <b>one-time password</b> is generated and shown to you on save. Give the username + one-time password to the person — they set their own on first login.',
        'На зачувување се генерира <b>еднократна лозинка</b> и ви се прикажува. Дајте им ги корисничкото име и лозинката на лицето — тие поставуваат своја при првото најавување.')}</div>`;
  GF.$('user-body').innerHTML = `
    <div class="field"><label>${GF.t('full_name')}</label><input id="u-name" value="${editing ? GF.esc(p.name || '') : ''}" placeholder="e.g. Ana Nikolova"></div>
    ${usernameRow}
    <div class="field"><label>${GF.t('role')}</label>${GF.selectField('u-role', {
      value: curRole, disabled: !iAmAdmin, title: GF.t('role'), options: roleOptions,
      onPick: (v) => GF._userRoleChange(v) })}</div>
    <div class="field" id="u-dept-row"><label>${GF.t('dept_label')}</label>${GF.selectField('u-dept', {
      value: curDept ? String(curDept) : '', disabled: !iAmAdmin, title: GF.t('dept_label'), options: deptOptions })}</div>
    <div id="u-nodept-note" style="display:none;font-size:12px;color:var(--ink-3);padding:2px 0 8px">${AL('Cross-org role — no department assignment', 'Меѓусекторска улога — без оддел')}</div>
    <div class="field"><label>${AL('Title (optional)', 'Титула (изборно)')}</label><input id="u-fn" value="${editing ? GF.esc(p.fn || '') : ''}" placeholder="e.g. Head of QC"></div>
    ${footNote}`;
  GF._userRoleChange(curRole);
  GF.openModal('user-modal');
};

GF._userRoleChange = (roleKey) => {
  const note = GF.$('u-nodept-note'), sel = GF.$('u-dept');
  const cross = NO_DEPT_ROLES.has(roleKey);
  // Keep the department picker visible for every role now that "None" is a real
  // option; for cross-org roles just default it to None and show the hint.
  if (note) note.style.display = cross ? '' : 'none';
  if (cross && sel) { sel.value = ''; if (GF.syncSelect) GF.syncSelect('u-dept'); }
};

GF.WWF.resetUserPw = async (id) => {
  const p = GF.PEOPLE[id] || {};
  if (!confirm(AL('Reset the password for ' + (p.name || id) + '? A new one-time password will be shown.',
                  'Ресетирај ја лозинката за ' + (p.name || id) + '? Ќе се прикаже нова еднократна лозинка.'))) return;
  try {
    const res = await GF.API.resetPassword(id);
    GF.closeModal('user-modal');
    GF.WWF.showOtp(res.user || { username: p.username, full_name: p.name }, res.otp);
  } catch (e) { GF.toast(AL('Reset failed: ', 'Неуспешно ресетирање: ') + (e.message || e), 'error'); }
};

// Had no guard at all (H7): a second click on Save created a SECOND account,
// with its own username collision or its own OTP, and only the last showOtp
// was ever displayed. Covers the edit branch too.
GF.submitUser = () => GF.once('user-save-btn', async () => {
  const name = (GF.$('u-name')?.value || '').trim();
  if (!name) { GF.toast(AL('Enter a full name', 'Внесете име и презиме'), 'error'); return; }
  const roleKey = GF.$('u-role').value;
  const role = ROLE_OUT[roleKey] || 'USER';
  // "None" (empty value) → no department; allowed for any role now.
  const department_id = GF.$('u-dept')?.value || null;
  const function_role = (GF.$('u-fn')?.value || '').trim() || null;
  // Edit mode (openUser was given an id) → PATCH the existing account.
  if (GF._editUser) {
    try {
      await GF.API.updateUser(GF._editUser, { full_name: name, role, department_id, function_role });
      GF._editUser = null;
      GF.closeModal('user-modal');
      await GF.WWF.loadAndRender();
      GF.toast(AL('Saved ✓', 'Зачувано ✓'), 'success');
    } catch (e) { GF.toast(AL('Save failed: ', 'Неуспешно зачувување: ') + (e.message || e), 'error'); }
    return;
  }
  const username = (GF.$('u-username')?.value || '').trim().toLowerCase();
  if (!username) { GF.toast(AL('Enter a username', 'Внесете корисничко име'), 'error'); return; }
  GF.toast(AL('Creating account…', 'Се креира сметка…'), 'info');
  try {
    const res = await GF.API.createUser({ username, full_name: name, role, department_id, function_role });
    GF.closeModal('user-modal');
    GF.WWF.showOtp(res.user || { username, full_name: name }, res.otp);
    await GF.WWF.loadAndRender();
  } catch (e) { GF.toast(AL('Create failed: ', 'Неуспешно креирање: ') + (e.message || e), 'error'); }
});

GF.removeUser = async (id) => {
  if (!GF.WWF.canProvision()) return GF.denyToast();
  if (id === GF.state.user) { GF.toast(AL('You cannot remove your own account', 'Не можете да ја отстраните сопствената сметка'), 'error'); return; }
  const p = GF.PEOPLE[id] || {};
  if (!confirm(AL('Deactivate the account for ', 'Деактивирај ја сметката за ') + (p.name || id) + '?')) return;
  try {
    await GF.API.deleteUser(id);
    // Deactivate is a soft-delete — keep the entry (flagged inactive) so
    // avatars/names on that person's existing tasks still resolve instead
    // of falling back to a blank '?' until the next full roster reload.
    if (GF.PEOPLE[id]) GF.PEOPLE[id].inactive = true;
    GF.render.all(); GF.toast(AL('Account removed ✓', 'Сметката е отстранета ✓'), 'success');
  } catch (e) { GF.toast(AL('Remove failed: ', 'Неуспешно отстранување: ') + e.message, 'error'); }
};

// Removing an account only soft-deletes it (is_deleted=true) — the row (and
// its audit history) stays, and its username is freed for reuse. This modal
// is how an admin/manager finds those soft-deleted rows again: to confirm a
// username really is free before retrying, or to purge one for good.
GF.WWF.openDeletedUsers = async () => {
  if (!GF.WWF.canProvision()) return GF.denyToast();
  let el = GF.$('wwf-deleted');
  if (!el) { el = document.createElement('div'); el.id = 'wwf-deleted'; el.className = 'overlay'; document.body.appendChild(el); }
  el.innerHTML = `
    <div class="modal" style="max-width:520px">
      <div class="modal-head"><h3>${AL('Removed accounts', 'Отстранети сметки')}</h3>
        <button class="btn-ghost" onclick="GF.closeModal('wwf-deleted')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
      <div class="modal-body" id="wwf-deleted-body">${AL('Loading…', 'Вчитување…')}</div>
    </div>`;
  GF.openModal('wwf-deleted');
  try {
    GF.WWF._renderDeletedUsers(await GF.API.listDeletedUsers());
  } catch (e) {
    const b = GF.$('wwf-deleted-body');
    if (b) b.innerHTML = `<div style="color:var(--red-fg);font-size:13px">${GF.esc(e.message)}</div>`;
  }
};

GF.WWF._renderDeletedUsers = (rows) => {
  const body = GF.$('wwf-deleted-body');
  if (!body) return;
  if (!rows.length) {
    body.innerHTML = `<div style="color:var(--ink-3);font-size:13px">${AL('No removed accounts.', 'Нема отстранети сметки.')}</div>`;
    return;
  }
  body.innerHTML = rows.map(r => `
    <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px dashed var(--line)">
      <div style="flex:1;min-width:0">
        <div style="font-weight:700;font-size:13.5px;color:var(--ink)">${GF.esc(r.full_name)}</div>
        <div style="font-size:12px;color:var(--ink-3);font-family:var(--mono)">${GF.esc(r.username)} · ${GF.esc(GF.roleLabel(ROLE_IN[r.role] || 'operator'))}</div>
      </div>
      <button class="btn btn-sm" style="color:var(--red-fg)" onclick="GF.WWF.purgeDeletedUser('${r.id}',${GF.esc(JSON.stringify(r.username))})">${GF.icon('trash', 'icon')}${AL('Delete permanently', 'Трајно бриши')}</button>
    </div>`).join('');
};

GF.WWF.purgeDeletedUser = async (id, username) => {
  const msg = AL(
    `Permanently delete this account? This cannot be undone — username "${username}" is already free to reuse, so this is only needed to clean up the roster.`,
    `Трајно бришење на оваа сметка? Ова не може да се врати — корисничкото име „${username}“ е веќе слободно за повторна употреба, ова е само за чистење на списокот.`);
  if (!confirm(msg)) return;
  try {
    await GF.API.purgeUser(id);
    GF.toast(AL('Account permanently deleted ✓', 'Сметката е трајно избришана ✓'), 'success');
    GF.WWF._renderDeletedUsers(await GF.API.listDeletedUsers());
  } catch (e) { GF.toast(AL('Delete failed: ', 'Неуспешно бришење: ') + e.message, 'error'); }
};

// Real auth: no local impersonation — switching accounts means logging in as them.
GF.setActiveUser = () => GF.toast(GF.state.lang === 'mk'
  ? 'За друга сметка, одјавете се и најавете се како тој корисник.'
  : 'To use another account, log out and sign in as that user.', 'info');

GF.WWF.showOtp = (user, otp) => {
  let el = GF.$('wwf-otp');
  if (!el) { el = document.createElement('div'); el.id = 'wwf-otp'; el.className = 'overlay'; document.body.appendChild(el); }
  const nm = GF.esc(user.full_name || user.username);
  el.innerHTML = `
    <div class="modal" style="max-width:420px">
      <div class="modal-head"><h3>${AL('Account created', 'Сметката е креирана')}</h3>
        <button class="btn-ghost" onclick="GF.closeModal('wwf-otp')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
      <div class="modal-body">
        <div style="font-size:13px;color:var(--ink-2);margin-bottom:14px">${AL(
          'Share these with <b>' + nm + '</b>. They set their own password on first login; this one-time password works once.',
          'Споделете ги овие со <b>' + nm + '</b>. Лицето поставува своја лозинка при првото најавување; оваа еднократна лозинка важи само еднаш.')}</div>
        <div class="field"><label>Username</label>
          <div style="font:700 18px ui-monospace,monospace;color:var(--ink)">${GF.esc(user.username)}</div></div>
        <div class="field" style="margin-top:12px"><label>${AL('One-time password', 'Еднократна лозинка')}</label>
          <div style="font:800 24px ui-monospace,monospace;letter-spacing:2px;color:var(--green)">${GF.esc(otp || '—')}</div></div>
      </div>
      <div class="modal-foot"><button class="btn btn-primary" onclick="GF.closeModal('wwf-otp')">${AL('Done', 'Готово')}</button></div>
    </div>`;
  GF.openModal('wwf-otp');
};

/* ── Shared full-page-view nav registration ─────────────────────────────
   Used by audit-view.js and report-view.js (loaded next) to add a nav item
   + hide the week/day/telemetry chrome while that view is active, without
   each view copy-pasting its own sidebar/render.all override. `guard`, if
   given, both hides the item from render.sidebar() and bounces away from
   the view in render.all() if the current user fails it; `insertBefore`
   places the item ahead of an existing nav key; `badge` (optional
   () => boolean) toggles a small dot on the item, e.g. "new report ready". */
GF.WWF._registerFullPageView = ({ key, icon, label, guard, insertBefore, badge }) => {
  const moduleGuard = () => GF.keyVisibleNow ? GF.keyVisibleNow(key) : true;
  const effectiveGuard = guard ? () => moduleGuard() && guard() : moduleGuard;

  const _sidebar = GF.render.sidebar.bind(GF.render);
  GF.render.sidebar = function () {
    _sidebar();
    if (!effectiveGuard()) return;
    const nav = GF.$('nav'); if (!nav) return;
    let item = nav.querySelector(`[data-nav="${key}"]`);
    if (!item) {
      item = document.createElement('div');
      item.setAttribute('data-nav', key);
      item.onclick = () => GF.setView(key);
      item.innerHTML = GF.icon(icon) + `<span>${label()}</span>` + (badge ? '<span class="nav-badge-dot" style="display:none"></span>' : '');
      const before = insertBefore ? nav.querySelector(`[data-nav="${insertBefore}"]`) : null;
      if (before) nav.insertBefore(item, before); else nav.appendChild(item);
    }
    item.className = 'nav-item' + (GF.state.view === key ? ' active' : '');
    if (badge) { const dot = item.querySelector('.nav-badge-dot'); if (dot) dot.style.display = badge() ? 'inline-block' : 'none'; }
  };

  const _all = GF.render.all.bind(GF.render);
  GF.render.all = function () {
    if (GF.state.view === key && !effectiveGuard()) GF.state.view = 'mywork';
    _all();
    if (GF.state.view === key) {
      ['week-strip', 'day-pills', 'telemetry'].forEach(id => { const el = GF.$(id); if (el) el.style.display = 'none'; });
    }
  };
};

