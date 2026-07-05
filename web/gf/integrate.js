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
const DEPT_STYLE = {
  cultivation:{icon:'leaf',color:'#15A86B'}, vegetation:{icon:'leaf',color:'#3FA34D'},
  production:{icon:'box',color:'#2F6BFF'}, qc:{icon:'flask',color:'#7A5BE0'},
  quality_control:{icon:'flask',color:'#7A5BE0'}, quality_assurance:{icon:'shield',color:'#C2410C'},
  logistics:{icon:'box',color:'#0891B2'}, tooling:{icon:'wrench',color:'#5A6B82'},
};
// Cross-department handoff pipeline, keyed by the backend's department `code`
// (resolved to real ids once /departments loads — see loadAndRender).
const CODE_HANDOFF = {
  cultivation:'production', production:'qc', qc:'quality_control',
  quality_control:'quality_assurance', quality_assurance:'logistics',
};

GF.WWF.meId = 'me';

// GrowFlow role keys <-> backend role enum. GF key = lowercased backend code
// (USER keeps the historical 'operator' key — GF.PERMS/curRole default to it).
const ROLE_OUT = { admin:'ADMIN', ceo:'CEO', coo:'COO', qa_mgr:'QA_MGR', qc_mgr:'QC_MGR',
  pr_mgr:'PR_MGR', wh_mgr:'WH_MGR', sc_mgr:'SC_MGR', cu_mgr:'CU_MGR', qp:'QP', operator:'USER' };
const ROLE_IN  = { ADMIN:'admin', CEO:'ceo', COO:'coo', QA_MGR:'qa_mgr', QC_MGR:'qc_mgr',
  PR_MGR:'pr_mgr', WH_MGR:'wh_mgr', SC_MGR:'sc_mgr', CU_MGR:'cu_mgr', QP:'qp', USER:'operator' };
// Backend roles that are "elevated" (must mirror app/roles.py ELEVATED_ROLES /
// the DB app.is_elevated()). Everything but USER.
const ELEVATED_ROLES = ['ADMIN','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR','SC_MGR','CU_MGR','QP'];
// The 7 department-manager roles (create only USER staff in their own dept).
const MANAGER_ROLES = ['QA_MGR','QC_MGR','PR_MGR','WH_MGR','SC_MGR','CU_MGR','QP'];
GF.WWF.colorFor = (id) => {
  const c = (GF.AVATAR_COLORS && GF.AVATAR_COLORS.length) ? GF.AVATAR_COLORS
    : ['#2F6BFF','#15A86B','#FF7A1A','#7A5BE0','#E5484D','#0EA5A5','#D6336C','#C2410C'];
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
  notes: (t.progress_notes || []).map(n => ({ d:(n.day_label||'').slice(0,3), n:n.note||n })),
  blocker: t.blocker_reason || '', completed_date: t.completed_date, week_start: t.week_start,
  est: t.estimated_hours != null ? Number(t.estimated_hours) : null,
  act: t.actual_hours != null ? Number(t.actual_hours) : null,
  // v2 model
  type: t.task_type || 'other', ref: t.reference_code || '',
  due: t.due_date || null, recurrence: t.recurrence || null,
  outcome: t.outcome || '', archived: !!t.is_archived, parentId: t.parent_id || null,
  sessionHours: t.session_hours != null ? Number(t.session_hours) : 0,
  subCount: Number(t.subtask_count || 0), subDone: Number(t.subtask_done_count || 0),
});

GF.WWF.weekIndex = (t) => {
  const W = GF.calendar.weeks;
  if (t.week_id) { const i = W.findIndex(w => w.realId === t.week_id); if (i >= 0) return i; }
  if (t.week_start) { const d = new Date(t.week_start);
    const i = W.findIndex(w => d >= w.start && d <= w.end); if (i >= 0) return i; }
  return GF.calendar.todayId;
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
  const mapped = ws.map((w,i) => {
    const s = new Date(w.starts_on), e = new Date(w.ends_on);
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
GF.WWF.showLogin = (msg) => {
  let el = GF.$('wwf-login');
  if (!el) {
    el = document.createElement('div'); el.id = 'wwf-login';
    el.style.cssText = 'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;'
      + 'background:linear-gradient(135deg,#0e1c14,#16233B);font-family:Manrope,system-ui,sans-serif';
    el.innerHTML = `
      <div style="background:#fff;border-radius:18px;padding:34px 30px;width:340px;box-shadow:0 20px 60px rgba(0,0,0,.4)">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
          <span class="pp-leaf-anim" style="width:42px;height:50px;flex-shrink:0"></span>
          <div><div style="font-size:22px;font-weight:800;color:#16233B">Grow<span style="color:#15A86B">Flow</span></div>
          <div style="font-size:9px;font-weight:800;letter-spacing:.16em;color:#16233B">PURELY<i>PLANT</i></div></div>
        </div>
        <div style="font-size:13px;color:#8A99B0;margin:8px 0 18px">Weekly Weed Flow — sign in</div>
        <input id="wwf-u" placeholder="Username" autocomplete="username"
          style="width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #E3E8F0;border-radius:10px;margin-bottom:10px;font-size:14px">
        <input id="wwf-p" type="password" placeholder="Password" autocomplete="current-password"
          style="width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #E3E8F0;border-radius:10px;margin-bottom:14px;font-size:14px"
          onkeydown="if(event.key==='Enter')GF.WWF.doLogin()">
        <button onclick="GF.WWF.doLogin()" style="width:100%;padding:12px;border:none;border-radius:10px;background:#15A86B;color:#fff;font-weight:700;font-size:14px;cursor:pointer">Sign in</button>
        <div id="wwf-login-msg" style="color:#E5484D;font-size:12px;margin-top:10px;min-height:16px"></div>
      </div>`;
    document.body.appendChild(el);
  }
  el.style.display = 'flex';
  const m = GF.$('wwf-login-msg'); if (m) m.textContent = msg || '';
  setTimeout(() => GF.$('wwf-u') && GF.$('wwf-u').focus(), 60);
};
GF.WWF.doLogin = async () => {
  const u = (GF.$('wwf-u')||{}).value, p = (GF.$('wwf-p')||{}).value;
  const m = GF.$('wwf-login-msg'); if (m) m.textContent = 'Signing in…';
  try {
    const data = await GF.API.login(u, p);
    if (data.user && data.user.must_change_password) { GF.WWF.showChangePw(p); return; }
    GF.$('wwf-login').style.display = 'none'; await GF.WWF.loadAndRender();
  } catch (e) { if (m) m.textContent = e.message === 'unauthorized' ? 'Invalid username or password' : ('Error: ' + e.message); }
};

/* ── first-login password change (must_change_password) ────────────── */
GF.WWF.showChangePw = (currentPw) => {
  GF.WWF._curPw = currentPw || '';
  let el = GF.$('wwf-login'); if (!el) { GF.WWF.showLogin(); el = GF.$('wwf-login'); }
  const IN = 'width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #E3E8F0;border-radius:10px;margin-bottom:10px;font-size:14px';
  el.innerHTML = `
    <div style="background:#fff;border-radius:18px;padding:34px 30px;width:340px;box-shadow:0 20px 60px rgba(0,0,0,.4)">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
        <span class="pp-leaf-anim" style="width:42px;height:50px;flex-shrink:0"></span>
        <div><div style="font-size:22px;font-weight:800;color:#16233B">Grow<span style="color:#15A86B">Flow</span></div></div>
      </div>
      <div style="font-size:15px;font-weight:700;color:#16233B;margin:8px 0 2px">Set a new password</div>
      <div style="font-size:12px;color:#8A99B0;margin-bottom:16px">First login — choose a password (min 8 characters).</div>
      <input id="wwf-np" type="password" placeholder="New password" style="${IN}">
      <input id="wwf-np2" type="password" placeholder="Confirm password" style="${IN}" onkeydown="if(event.key==='Enter')GF.WWF.doChangePw()">
      <button onclick="GF.WWF.doChangePw()" style="width:100%;padding:12px;border:none;border-radius:10px;background:#15A86B;color:#fff;font-weight:700;font-size:14px;cursor:pointer">Set password & continue</button>
      <div id="wwf-login-msg" style="color:#E5484D;font-size:12px;margin-top:10px;min-height:16px"></div>
    </div>`;
  el.style.display = 'flex';
  setTimeout(() => GF.$('wwf-np') && GF.$('wwf-np').focus(), 60);
};
GF.WWF.doChangePw = async () => {
  const a = (GF.$('wwf-np')||{}).value || '', b = (GF.$('wwf-np2')||{}).value || '';
  const m = GF.$('wwf-login-msg');
  if (a.length < 8) { if (m) m.textContent = 'Password must be at least 8 characters'; return; }
  if (a !== b) { if (m) m.textContent = 'Passwords do not match'; return; }
  if (m) m.textContent = 'Saving…';
  try {
    await GF.API.changePassword(a, GF.WWF._curPw);
    try { GF.API.user = await GF.API.me(); sessionStorage.setItem('wwf_user', JSON.stringify(GF.API.user)); } catch (e) {}
    GF.$('wwf-login').style.display = 'none'; await GF.WWF.loadAndRender();
  } catch (e) { if (m) m.textContent = 'Error: ' + e.message; }
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
      dept: p.department_id || (GF.DEPTS[0] || {}).id, bg: GF.WWF.colorFor(p.id),
      backendRole: p.role, mcp: p.must_change_password, active: p.is_active };
  });
  const me = GF.API.user;
  if (me && me.id && !GF.PEOPLE[me.id]) GF.PEOPLE[me.id] = {
    name: me.full_name || me.username, username: me.username, init: 'ME',
    role: ROLE_IN[me.role] || 'operator', roleLabel: me.function_role || '',
    dept: (GF.DEPTS[0] || {}).id, bg: GF.WWF.colorFor(me.id), backendRole: me.role };
};

GF.WWF.loadAndRender = async () => {
  const u = GF.API.user || {};
  GF.WWF.meId = u.id || 'me';
  GF.state.user = GF.WWF.meId;
  // Load each independently so one failure never blanks the UI.
  let depts = [], weeks = [], tasks = [];
  try { depts = (await GF.API.departments()) || []; } catch (e) { GF.toast(AL('Departments: ', 'Оддели: ') + e.message, 'error'); }
  // A /weeks failure is non-fatal — buildCalendar keeps core.js's generated
  // fallback weeks — but tell the user rather than silently swallowing it.
  try { weeks = (await GF.API.weeks()) || []; } catch (e) { GF.toast(AL('Weeks: ', 'Недели: ') + e.message, 'error'); }
  try { tasks = (await GF.API.tasks()) || []; } catch (e) { GF.toast(AL('Tasks: ', 'Задачи: ') + e.message, 'error'); }
  if (depts.length) {
    GF.DEPTS = depts.map(d => { const st = DEPT_STYLE[d.code] || {icon:'box',color:'#5A6B82'};
      return { id:d.id, name:d.name, mk:d.name_mk || d.name, icon:st.icon, color:st.color }; });
    // Resolve the code-keyed handoff pipeline to the real backend ids.
    const byCode = {}; depts.forEach(d => { byCode[d.code] = d.id; });
    GF.HANDOFF = {};
    Object.entries(CODE_HANDOFF).forEach(([from, to]) => {
      if (byCode[from] && byCode[to]) GF.HANDOFF[byCode[from]] = byCode[to];
    });
  }
  await GF.WWF.loadTeam();
  GF.WWF.buildCalendar(weeks);
  GF.state.tasks = tasks.filter(t => !t.parent_id).map(GF.WWF.transform);
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
    GF.toast('Render error: ' + (e && e.message || e), 'error');
  }
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
  GF.cycleStatus = (id) => { const t = GF.task(id); const prev = t && t.status; origCycle(id); pushStatus(id, prev); };
  GF.toggleDone  = (id) => { const t = GF.task(id); const prev = t && t.status; origToggle(id); pushStatus(id, prev); };
  GF.setStatus   = (id, s) => { const t = GF.task(id); const prev = t && t.status;
    const ok = origSet(id, s); if (ok) pushStatus(id, prev); return ok; };

  GF.deleteTask = (id) => GF.toast(GF.state.lang==='mk'?'Бришењето е оневозможено (ревизија)':'Delete disabled (audit retention)','info');

  const origAddNote = GF.addNote;
  GF.addNote = (taskId) => { const el = GF.$('note-'+taskId); const v = el && el.value.trim();
    origAddNote(taskId);
    if (v) GF.API.addProgress(taskId, { day_label: GF.todayDay, note: v }).catch(()=>{}); };

  GF.submitAdd = async () => {
    const title = (GF.$('add-title')?.value||'').trim();
    if (!title) { GF.toast(AL('Enter a title','Внесете наслов'),'error'); return; }
    const days = [...GF.$('add-days').querySelectorAll('.on')].map(el => el.dataset.day);
    const deptId = GF.$('add-dept').value;
    const wk = GF.calendar.weeks[GF._addWeek] || GF.calendar.weeks[GF.calendar.todayId];
    const estRaw = parseFloat(GF.$('add-est')?.value);
    // >= 0, not > 0: a deliberate zero-hour estimate is a value, not "no estimate".
    const estHours = Number.isFinite(estRaw) && estRaw >= 0 ? estRaw : null;
    // v2 fields (due date, typology, recurrence)
    const dueDate = GF.$('add-due')?.value || null;
    const refCode = (GF.$('add-ref')?.value || '').trim() || null;
    const recFreq = GF.$('add-rec')?.value || '';
    const recurrence = recFreq ? { freq: recFreq, interval: 1 } : null;

    // Edit mode (openEdit in worklog.js sets GF._editTask) → PATCH instead of POST.
    if (GF._editTask) {
      const id = GF._editTask, t = GF.task(id);
      try {
        const patched = await GF.API.updateTask(id, {
          title, priority: P_OUT[GF.$('add-pr').value]||'normal',
          // Send the department text alongside the id (as the create path
          // does) — reports.py groups the department breakdown by the text
          // column, so updating only department_id leaves the two out of sync.
          department_id: deptId, department: (GF.dep(deptId)||{}).name || null,
          days: days.length?days:[GF.todayDay],
          estimated_hours: estHours, due_date: dueDate,
          task_type: GF.$('add-type')?.value || 'other', reference_code: refCode,
          recurrence,
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
        if (respChanged && t && GF.WWF.canManageTask(t)) {
          for (const who of desired) if (!current.includes(who)) {
            try { await GF.API.assign(id, who); }
            catch (e) { GF.toast('Could not assign ' + ((GF.PEOPLE[who]||{}).name||who) + ': ' + e.message, 'error'); }
          }
          for (const who of current) if (!desired.includes(who)) {
            try { await GF.API.unassign(id, who); }
            catch (e) { GF.toast('Could not unassign ' + ((GF.PEOPLE[who]||{}).name||who) + ': ' + e.message, 'error'); }
          }
        } else if (respChanged) {
          GF.toast(AL("Only the task owner or a manager can change who's responsible.",
                      'Само сопственикот на задачата или менаџер може да ја смени одговорноста.'), 'info');
        }
        if (t) { const keep = { weekId: t.weekId, notes: t.notes, helpers: desired, subCount: t.subCount, subDone: t.subDone, sessionHours: t.sessionHours };
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
        title, description:'', status:'pending', priority: P_OUT[GF.$('add-pr').value]||'normal',
        department_id: deptId, department:(GF.dep(deptId)||{}).name, week_id: wk && wk.realId,
        week_start: wk ? GF.localDateStr(wk.start) : null, days: days.length?days:[GF.todayDay],
        estimated_hours: estHours,
        due_date: dueDate, task_type: GF.$('add-type')?.value || 'other',
        reference_code: refCode, recurrence, parent_id: GF._addParent || null,
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
          GF.toast('Could not assign ' + ((GF.PEOPLE[who]||{}).name||who) + ': ' + e.message, 'error'); }
      }
      if (helperIds.length) { await GF.WWF.loadCollab(created.id); GF.render.panels(); }
    } catch(e) { GF.toast(AL('Create failed: ','Неуспешно креирање: ')+e.message,'error'); }
  };

  // AI features -> real backend Letta functions (/ai/{function_key}, body: {input}).
  // Every call degrades to "AI agent unavailable" when no binding is configured —
  // see backend/app/api/ai.py — instead of throwing.
  GF.ai = GF.ai || {};
  GF.ai.summary = async (kind) => {
    GF.$('ai-out').innerHTML = `<div class="ai-loading"><span class="spinner"></span>${GF.t('generate')}…</div>`;
    GF.openModal('ai-modal');
    try {
      const wk = GF.calendar.weeks[GF.state.selWeek + (kind==='plan'?1:0)] || GF.calendar.weeks[GF.state.selWeek];
      const tasks = GF.weekTasks(wk ? wk.id : GF.state.selWeek);
      const body = tasks.map(t => `- [${t.status}] ${t.title} (${GF.depName(t.dept)}, ${t.pr})`).join('\n') || '(no tasks)';
      const prompt = (kind === 'plan'
        ? 'Analyse next week\'s plan: priorities, risks, workload. Bullet points.\n\n'
        : 'Summarise this week\'s status: completed, in-progress, blockers. Bullet points.\n\n') + body;
      const r = await GF.API.ai('weekly_summary', { input: prompt, context: { week_id: wk && wk.realId, kind } });
      const text = (r && r.available) ? r.output : ('AI agent unavailable' + (r && r.reason ? ' (' + r.reason + ')' : ''));
      GF.$('ai-out').innerHTML = `<div class="ai-out">${GF.esc(text)}</div>`;
    } catch(e) { GF.$('ai-out').innerHTML = `<div class="ai-out">AI error: ${GF.esc(e.message)}</div>`; }
  };

  GF.ai.paraphraseInput = async (inputId) => {
    const el = GF.$(inputId); if (!el || !el.value.trim()) return;
    const orig = el.value.trim();
    GF.toast(GF.t('paraphrase') + '…', 'info');
    try {
      const r = await GF.API.ai('draft_description', { input:
        `Rewrite this task note as one clear professional sentence for a GMP cannabis facility. Keep batch/room IDs.\n\n${orig}` });
      if (r && r.available && r.output) el.value = r.output.trim();
      else GF.toast('AI unavailable', 'info');
    } catch (e) { GF.toast('AI error: ' + e.message, 'error'); }
  };

  GF.ai.paraphraseTask = async (taskId) => {
    const t = GF.task(taskId); if (!t || !t.desc) { GF.toast('Nothing to rewrite', 'info'); return; }
    GF.toast(GF.t('paraphrase') + '…', 'info');
    try {
      const r = await GF.API.ai('draft_description', { input: `Rewrite concisely for GMP cannabis: ${t.desc}` });
      if (!(r && r.available && r.output)) { GF.toast('AI unavailable', 'info'); return; }
      const rewritten = r.output.trim();
      // Only mutate local state once the backend save succeeds — otherwise a
      // failed PATCH leaves the card showing text that was never persisted.
      await GF.API.updateTask(taskId, { description: rewritten });
      t.desc = rewritten;
      GF.render.panels(); GF.toast('Rewritten ✓', 'success');
    } catch (e) { GF.toast('AI error: ' + e.message, 'error'); }
  };

  GF.ai.parseVoice = async (transcript) => {
    const depts = GF.DEPTS.map(d => GF.state.lang === 'mk' ? d.mk : d.name);
    const people = Object.entries(GF.PEOPLE).map(([, p]) => p.name);
    try {
      const r = await GF.API.ai('voice_capture', { input:
        `Parse this spoken task into JSON {title,department,priority,assignee,due,days}. ` +
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
        } catch (e) { GF.toast('Could not assign ' + ownerMatch[1].name + ': ' + e.message, 'error'); }
      }
    } catch (e) { GF.toast('Create failed: ' + e.message, 'error'); }
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
    const tabs = [['prefs', AL('Preferences', 'Поставки')], ['security', AL('Security', 'Безбедност')]];
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
    const show = (t, ok) => { if (msg) { msg.textContent = t; msg.style.color = ok ? 'var(--green-fg)' : 'var(--red)'; } };
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
      const opts = (sel) => ['<option value="">' + AL('— none —', '— ништо —') + '</option>']
        .concat(agents.map(a => `<option value="${GF.esc(a.id)}" ${a.id === sel ? 'selected' : ''}>${GF.esc(a.name || a.id)}</option>`)).join('');
      const rows = Object.keys(catalog).map(fn => {
        const b = bindByFn[fn] || {};
        return `<div class="ai-bind">
          <div class="ai-bind-h"><b>${GF.esc(fn)}</b>
            <label class="ai-bind-on"><input type="checkbox" ${b.is_active ? 'checked' : ''} onchange="GF.WWF.saveBinding('${fn}')"> ${AL('Active', 'Активно')}</label></div>
          <div class="set-hint">${GF.esc(catalog[fn])}</div>
          <select id="ai-sel-${fn}" onchange="GF.WWF.saveBinding('${fn}')">${opts(b.letta_agent_id)}</select></div>`;
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

// Strict ADMIN check — mirrors the AI-bindings endpoints' require_role(ADMIN)
// (backend/app/api/ai.py). Deliberately narrower than canProvision (which also
// admits department managers): reusing canProvision here previously showed the
// Settings "AI agents" tab to managers who then got a raw 403 from every call.
GF.WWF.isAdmin = () => (GF.API.user || {}).role === 'ADMIN';

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
  const roleOpts = roleKeys.map(r =>
    `<option value="${r}" ${r===curRole?'selected':''}>${GF.esc(GF.roleLabel(r))}</option>`).join('');
  const curDept = editing ? p.dept : me.department_id;
  const deptOpts = GF.DEPTS.map(d =>
    `<option value="${d.id}" ${String(d.id)===String(curDept)?'selected':''}>${GF.esc(GF.depName(d.id))}</option>`).join('');
  const deptLocked = iAmAdmin ? '' : 'disabled';
  GF.$('user-title').textContent = editing ? GF.t('edit_user') : GF.t('add_user');
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
    <div class="field"><label>${GF.t('role')}</label><select id="u-role" ${iAmAdmin?'':'disabled'}>${roleOpts}</select></div>
    <div class="field"><label>${GF.t('dept_label')}</label><select id="u-dept" ${deptLocked}>${deptOpts}</select></div>
    <div class="field"><label>${AL('Title (optional)', 'Титула (изборно)')}</label><input id="u-fn" value="${editing ? GF.esc(p.fn || '') : ''}" placeholder="e.g. Head of QC"></div>
    ${footNote}`;
  GF.openModal('user-modal');
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

GF.submitUser = async () => {
  const name = (GF.$('u-name')?.value || '').trim();
  if (!name) { GF.toast(AL('Enter a full name', 'Внесете име и презиме'), 'error'); return; }
  const role = ROLE_OUT[GF.$('u-role').value] || 'USER';
  const department_id = GF.$('u-dept').value;
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
};

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

// Real auth: no local impersonation — switching accounts means logging in as them.
GF.setActiveUser = () => GF.toast(GF.state.lang === 'mk'
  ? 'За друга сметка, одјавете се и најавете се како тој корисник.'
  : 'To use another account, log out and sign in as that user.', 'info');

GF.WWF.showOtp = (user, otp) => {
  let el = GF.$('wwf-otp');
  if (!el) { el = document.createElement('div'); el.id = 'wwf-otp'; el.className = 'overlay'; document.body.appendChild(el); }
  el.innerHTML = `
    <div class="modal" style="max-width:420px">
      <div class="modal-head"><h3>Account created</h3>
        <button class="btn-ghost" onclick="GF.closeModal('wwf-otp')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
      <div class="modal-body">
        <div style="font-size:13px;color:var(--ink-2);margin-bottom:14px">Share these with <b>${GF.esc(user.full_name || user.username)}</b>. They set their own password on first login; this one-time password works once.</div>
        <div class="field"><label>Username</label>
          <div style="font:700 18px ui-monospace,monospace;color:var(--ink)">${GF.esc(user.username)}</div></div>
        <div class="field" style="margin-top:12px"><label>One-time password</label>
          <div style="font:800 24px ui-monospace,monospace;letter-spacing:2px;color:var(--green)">${GF.esc(otp || '—')}</div></div>
      </div>
      <div class="modal-foot"><button class="btn btn-primary" onclick="GF.closeModal('wwf-otp')">Done</button></div>
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
  const _sidebar = GF.render.sidebar.bind(GF.render);
  GF.render.sidebar = function () {
    _sidebar();
    if (guard && !guard()) return;
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
    if (guard && GF.state.view === key && !guard()) GF.state.view = 'mywork';
    _all();
    if (GF.state.view === key) {
      ['week-strip', 'day-pills', 'telemetry'].forEach(id => { const el = GF.$(id); if (el) el.style.display = 'none'; });
    }
  };
};

