/* integrate.js — bridges the GrowFlow UI to the real WEEKLY_WEED_FLOW backend.
   Loaded LAST. Replaces the localStorage/seed data layer with live API data:
   login -> load real departments/weeks/tasks -> render GrowFlow UI -> writes go to the API. */
window.GF = window.GF || {};
GF.WWF = {};

/* ── enum mapping (backend <-> GrowFlow) ───────────────────────────── */
const S_IN  = { ongoing:'working', completed:'done', pending:'pending', stuck:'stuck', review:'review', postponed:'postponed' };
const S_OUT = { working:'ongoing', done:'completed', pending:'pending', stuck:'stuck', review:'ongoing', postponed:'pending' };
const P_IN  = { normal:'medium', high:'high', critical:'critical', low:'low' };
const P_OUT = { medium:'normal', high:'high', critical:'critical', low:'low' };
const DEPT_STYLE = {
  cultivation:{icon:'leaf',color:'#15A86B'}, vegetation:{icon:'leaf',color:'#3FA34D'},
  production:{icon:'box',color:'#2F6BFF'}, qc:{icon:'flask',color:'#7A5BE0'},
  quality_control:{icon:'flask',color:'#7A5BE0'}, quality_assurance:{icon:'shield',color:'#C2410C'},
  logistics:{icon:'box',color:'#0891B2'}, tooling:{icon:'wrench',color:'#5A6B82'},
};

GF.WWF.meId = 'me';

// GrowFlow role keys <-> backend role enum
const ROLE_OUT = { admin:'ADMIN', hod:'DEPT_HEAD', qa:'QA_AUDITOR', qp:'PROJECT_LEAD', operator:'USER', viewer:'TEAM_LEADER' };
const ROLE_IN  = { ADMIN:'admin', DEPT_HEAD:'hod', QA_AUDITOR:'qa', PROJECT_LEAD:'qp', USER:'operator', TEAM_LEADER:'viewer' };
GF.WWF.colorFor = (id) => {
  const c = (GF.AVATAR_COLORS && GF.AVATAR_COLORS.length) ? GF.AVATAR_COLORS
    : ['#2F6BFF','#15A86B','#FF7A1A','#7A5BE0','#E5484D','#0EA5A5','#D6336C','#C2410C'];
  let h = 0; String(id).split('').forEach(ch => h = (h * 31 + ch.charCodeAt(0)) >>> 0);
  return c[h % c.length];
};

GF.WWF.transform = (t) => ({
  id: t.id, title: t.title, desc: t.description || '',
  dept: t.department_id || (GF.DEPTS[0] && GF.DEPTS[0].id),
  owner: GF.WWF.meId, helpers: [],
  status: S_IN[t.status] || 'pending', pr: P_IN[t.priority] || 'medium',
  days: Array.isArray(t.days) ? t.days.map(d => d.slice(0,3)) : [],
  weekId: GF.WWF.weekIndex(t), room: '', batch: '',
  tags: t.tags || [], deps: [],
  notes: (t.progress_notes || []).map(n => ({ d:(n.day_label||'').slice(0,3), n:n.note||n })),
  subs: [], blocker: '', completed_date: t.completed_date, week_start: t.week_start,
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
  GF.calendar.weeks = ws.map((w,i) => {
    const s = new Date(w.starts_on), e = new Date(w.ends_on);
    if (now >= s && now <= e) todayId = i;
    return { id:i, realId:w.id, start:s, end:e, weekNum:w.iso_week, monthIndex:s.getMonth(), year:s.getFullYear(),
      label:`${MONTHS[s.getMonth()]} ${s.getDate()} – ${MONTHS[e.getMonth()]} ${e.getDate()}`, short:`W${w.iso_week}` };
  });
  if (!GF.calendar.weeks.length) { // fallback: keep core.js generated weeks
    return;
  }
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
  let users = null;
  try { users = await GF.API.listUsers(); } catch (e) { users = [GF.API.user].filter(Boolean); }
  GF.PEOPLE = {};
  (users || []).forEach(p => { if (!p || !p.id) return;
    GF.PEOPLE[p.id] = {
      name: p.full_name || p.username, username: p.username,
      init: ((p.full_name || p.username || 'U').trim().split(/\s+/).slice(0,2).map(x => x[0]).join('').toUpperCase()) || 'U',
      role: ROLE_IN[p.role] || 'operator', roleLabel: p.function_role || p.role || '',
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
  try { depts = (await GF.API.departments()) || []; } catch (e) { GF.toast('Departments: ' + e.message, 'error'); }
  try { weeks = (await GF.API.weeks()) || []; } catch (e) {}
  try { tasks = (await GF.API.tasks()) || []; } catch (e) { GF.toast('Tasks: ' + e.message, 'error'); }
  if (depts.length) GF.DEPTS = depts.map(d => { const st = DEPT_STYLE[d.code] || {icon:'box',color:'#5A6B82'};
    return { id:d.id, name:d.name, mk:d.name_mk || d.name, icon:st.icon, color:st.color }; });
  await GF.WWF.loadTeam();
  GF.WWF.buildCalendar(weeks);
  GF.state.tasks = tasks.filter(t => !t.parent_id).map(GF.WWF.transform);
  try { GF.render.all(); } catch (e) { console.error('render error', e); }
};

/* ── persistence overrides (writes -> API) ─────────────────────────── */
GF.WWF.install = () => {
  GF.store.load = () => { if (GF.API.token) GF.WWF.loadAndRender().catch(()=>GF.WWF.showLogin()); else GF.WWF.showLogin(); };
  GF.store.save = () => {};   // explicit API calls below own persistence

  const origCycle = GF.cycleStatus, origSet = GF.setStatus, origToggle = GF.toggleDone;
  const pushStatus = async (id) => { const t = GF.task(id); if (!t) return;
    try { await GF.API.updateTask(id, { status: S_OUT[t.status] || 'pending' }); } catch(e){ GF.toast('Save failed','error'); } };
  GF.cycleStatus = (id) => { origCycle(id); pushStatus(id); };
  GF.toggleDone  = (id) => { origToggle(id); pushStatus(id); };
  GF.setStatus   = (id, s) => { const ok = origSet(id, s); if (ok) pushStatus(id); return ok; };

  GF.deleteTask = (id) => GF.toast(GF.state.lang==='mk'?'Бришењето е оневозможено (ревизија)':'Delete disabled (audit retention)','info');

  const origAddNote = GF.addNote;
  GF.addNote = (taskId) => { const el = GF.$('note-'+taskId); const v = el && el.value.trim();
    origAddNote(taskId);
    if (v) GF.API.addProgress(taskId, { day_label: GF.todayDay, note: v }).catch(()=>{}); };

  GF.submitAdd = async () => {
    const title = (GF.$('add-title')?.value||'').trim();
    if (!title) { GF.toast('Enter a title','error'); return; }
    const days = [...GF.$('add-days').querySelectorAll('.on')].map(el => el.dataset.day);
    const deptId = GF.$('add-dept').value;
    const wk = GF.calendar.weeks[GF._addWeek] || GF.calendar.weeks[GF.calendar.todayId];
    try {
      const created = await GF.API.createTask({
        title, description:'', status:'pending', priority: P_OUT[GF.$('add-pr').value]||'normal',
        department_id: deptId, department:(GF.dep(deptId)||{}).name, week_id: wk && wk.realId,
        week_start: wk ? wk.start.toISOString().slice(0,10) : null, days: days.length?days:[GF.todayDay],
      });
      GF.state.tasks.push(GF.WWF.transform(created));
      GF.closeModal('add-modal'); GF.render.all(); GF.toast(GF.t('create_task')+' ✓','success');
    } catch(e) { GF.toast('Create failed: '+e.message,'error'); }
  };

  // AI weekly summary / plan -> backend Letta function
  GF.ai = GF.ai || {};
  GF.ai.summary = async (kind) => {
    GF.$('ai-out').innerHTML = `<div class="ai-loading"><span class="spinner"></span>${GF.t('generate')}…</div>`;
    GF.openModal('ai-modal');
    try {
      const wk = GF.calendar.weeks[GF.state.selWeek + (kind==='plan'?1:0)] || GF.calendar.weeks[GF.state.selWeek];
      const r = await GF.API.ai('weekly_summary', { week_id: wk && wk.realId, kind });
      const text = (r && (r.text || r.reply || r.message)) || (r.available===false ? 'AI agent unavailable ('+(r.reason||'')+')' : JSON.stringify(r));
      GF.$('ai-out').innerHTML = `<div class="ai-out">${GF.esc(text)}</div>`;
    } catch(e) { GF.$('ai-out').innerHTML = `<div class="ai-out">AI error: ${GF.esc(e.message)}</div>`; }
  };
  if (GF.assistant) GF.assistant.complete = async (prompt) => {
    const r = await GF.API.ai('corpus_qa', { message: prompt }); return (r && (r.text||r.reply)) || ''; };

  // logout from the user card / settings
  GF.openSettings = () => { if (confirm('Log out of Weekly Weed Flow?')) { GF.API.logout(); location.reload(); } };
};

GF.WWF.install();

/* ── Team / account provisioning (real backend, OTP shown to admin) ── */
GF.openUser = (id) => {
  if (!GF.can('team')) return GF.denyToast();
  GF._editUser = null;  // create only (no in-place edit endpoint)
  const deptOpts = GF.DEPTS.map(d => `<option value="${d.id}">${GF.depName(d.id)}</option>`).join('');
  const roleOpts = Object.keys(GF.ROLES).filter(r => ROLE_OUT[r]).map(r =>
    `<option value="${r}" ${r==='operator'?'selected':''}>${GF.roleLabel(r)}</option>`).join('');
  GF.$('user-title').textContent = GF.t('add_user');
  GF.$('user-body').innerHTML = `
    <div class="field"><label>${GF.t('full_name')}</label><input id="u-name" placeholder="e.g. Ana Nikolova"></div>
    <div class="field"><label>Username</label><input id="u-username" placeholder="e.g. ana" autocapitalize="off" autocomplete="off"></div>
    <div class="field"><label>${GF.t('role')}</label><select id="u-role">${roleOpts}</select></div>
    <div class="field"><label>${GF.t('dept_label')}</label><select id="u-dept">${deptOpts}</select></div>
    <div class="field"><label>Title (optional)</label><input id="u-fn" placeholder="e.g. Head of QC"></div>
    <div style="font-size:12px;color:var(--ink-3);margin-top:6px;line-height:1.5">
      A <b>one-time password</b> is generated and shown to you on save. Give the username + one-time
      password to the person — they set their own password on first login.</div>`;
  GF.openModal('user-modal');
};

GF.submitUser = async () => {
  const name = (GF.$('u-name')?.value || '').trim();
  const username = (GF.$('u-username')?.value || '').trim().toLowerCase();
  if (!name) { GF.toast('Enter a full name', 'error'); return; }
  if (!username) { GF.toast('Enter a username', 'error'); return; }
  const role = ROLE_OUT[GF.$('u-role').value] || 'USER';
  const department_id = GF.$('u-dept').value;
  const function_role = (GF.$('u-fn')?.value || '').trim() || null;
  GF.toast('Creating account…', 'info');
  try {
    const res = await GF.API.createUser({ username, full_name: name, role, department_id, function_role });
    GF.closeModal('user-modal');
    GF.WWF.showOtp(res.user || { username, full_name: name }, res.otp);
    await GF.WWF.loadAndRender();
  } catch (e) { GF.toast('Create failed: ' + (e.message || e), 'error'); }
};

GF.removeUser = async (id) => {
  if (!GF.can('team')) return GF.denyToast();
  if (id === GF.state.user) { GF.toast('You cannot remove your own account', 'error'); return; }
  const p = GF.PEOPLE[id] || {};
  if (!confirm('Deactivate the account for ' + (p.name || id) + '?')) return;
  try { await GF.API.deleteUser(id); delete GF.PEOPLE[id]; GF.render.all(); GF.toast('Account removed ✓', 'success'); }
  catch (e) { GF.toast('Remove failed: ' + e.message, 'error'); }
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

/* ══════════════════════════════════════════════════════════════════════
   Audit Trail — a general (non-QC) GxP capability adopted from the QC lab.
   Read-only, tamper-evident view of the hash-chained audit_log. Visible to
   elevated roles only (ADMIN / DEPT_HEAD / PROJECT_LEAD / QA_AUDITOR), which
   mirrors the DB `audit_read` policy.
   ════════════════════════════════════════════════════════════════════ */
const AL = (en, mk) => (GF.state && GF.state.lang === 'mk') ? mk : en;
const AUDIT_ROLES = ['ADMIN', 'DEPT_HEAD', 'PROJECT_LEAD', 'QA_AUDITOR'];
const ACT = {
  INSERT: { c: '#15A86B', en: 'Created', mk: 'Создадено' },
  UPDATE: { c: '#2F6BFF', en: 'Updated', mk: 'Изменето' },
  DELETE: { c: '#E5484D', en: 'Deleted', mk: 'Избришано' },
};
const AUDIT_HIDE = ['password_hash'];   // never surface secrets in the trail

GF.WWF.canAudit = () => AUDIT_ROLES.includes((GF.API.user || {}).role);
GF.WWF._audit = { entries: [], before: null, tables: null, verify: null, hasMore: false };
GF.WWF._auditFilter = { table_name: '', action: '' };

GF.WWF._auditActor = (e) => {
  if (e.user_id && GF.PEOPLE[e.user_id]) return GF.PEOPLE[e.user_id].name;
  if (e.user_email) return e.user_email;
  if (e.user_id) return e.user_id.slice(0, 8) + '…';
  return AL('system', 'систем');
};
GF.WWF._auditTrunc = (v) => {
  let s = (v === null || v === undefined) ? '∅' : (typeof v === 'object' ? JSON.stringify(v) : String(v));
  return s.length > 90 ? s.slice(0, 90) + '…' : s;
};
GF.WWF._auditDiff = (e) => {
  const o = e.old_values || {}, n = e.new_values || {};
  const rows = [];
  if (e.action === 'INSERT') {
    Object.keys(n).forEach(k => { if (!AUDIT_HIDE.includes(k)) rows.push([k, null, n[k]]); });
  } else if (e.action === 'DELETE') {
    Object.keys(o).forEach(k => { if (!AUDIT_HIDE.includes(k)) rows.push([k, o[k], null]); });
  } else {
    const keys = new Set([...Object.keys(o), ...Object.keys(n)]);
    keys.forEach(k => {
      if (AUDIT_HIDE.includes(k)) return;
      if (JSON.stringify(o[k]) !== JSON.stringify(n[k])) rows.push([k, o[k], n[k]]);
    });
  }
  return rows;
};

GF.views.audit = function () {
  setTimeout(() => GF.WWF.loadAudit({ reset: true }), 0);
  return `<div id="audit-view" class="audit-wrap" style="padding:4px 2px 40px">
    <div class="audit-loading" style="padding:40px;text-align:center;color:var(--ink-3)">${AL('Loading audit trail…', 'Се вчитува ревизија…')}</div>
  </div>`;
};

GF.WWF.loadAudit = async ({ reset = false } = {}) => {
  const st = GF.WWF._audit;
  if (reset) { st.entries = []; st.before = null; }
  const q = { limit: 100 };
  if (GF.WWF._auditFilter.table_name) q.table_name = GF.WWF._auditFilter.table_name;
  if (GF.WWF._auditFilter.action) q.action = GF.WWF._auditFilter.action;
  if (st.before) q.before_id = st.before;
  try {
    const page = await GF.API.audit(q);
    st.entries = st.entries.concat(page);
    st.before = page.length ? page[page.length - 1].id : st.before;
    st.hasMore = page.length === q.limit;
    if (st.tables === null) { try { st.tables = await GF.API.auditTables(); } catch (e) { st.tables = []; } }
    if (st.verify === null && (GF.API.user || {}).role === 'ADMIN') {
      try { st.verify = await GF.API.auditVerify(); } catch (e) { st.verify = { error: true }; }
    }
    GF.WWF.renderAudit();
  } catch (e) {
    const v = GF.$('audit-view');
    if (v) v.innerHTML = `<div style="padding:40px;text-align:center;color:#E5484D">${AL('Could not load audit trail', 'Не може да се вчита ревизија')}: ${GF.esc(e.message)}</div>`;
  }
};

GF.WWF.applyAuditFilter = () => {
  GF.WWF._auditFilter.table_name = (GF.$('audit-f-table') || {}).value || '';
  GF.WWF._auditFilter.action = (GF.$('audit-f-action') || {}).value || '';
  GF.WWF.loadAudit({ reset: true });
};

GF.WWF.renderAudit = () => {
  const v = GF.$('audit-view'); if (!v) return;
  const st = GF.WWF._audit, f = GF.WWF._auditFilter;

  // integrity badge (ADMIN only — /verify is ADMIN-guarded)
  let badge = '';
  if (st.verify && !st.verify.error) {
    badge = st.verify.ok
      ? `<span style="display:inline-flex;align-items:center;gap:6px;background:#E6F7EF;color:#0F7A4D;font-weight:700;font-size:12px;padding:5px 11px;border-radius:999px">
           ${GF.icon('shield', 'icon', '#0F7A4D')} ${AL('Chain verified', 'Синџирот е потврден')} · ${st.verify.total} ${AL('entries', 'записи')}</span>`
      : `<span style="display:inline-flex;align-items:center;gap:6px;background:#FDECEC;color:#C42121;font-weight:700;font-size:12px;padding:5px 11px;border-radius:999px">
           ${GF.icon('flag', 'icon', '#C42121')} ${AL('Chain broken at', 'Прекин кај')} #${st.verify.first_break_id}</span>`;
  }

  // filters
  const tableOpts = `<option value="">${AL('All tables', 'Сите табели')}</option>` +
    (st.tables || []).map(t => `<option value="${GF.esc(t.table_name)}" ${f.table_name === t.table_name ? 'selected' : ''}>${GF.esc(t.table_name)} (${t.count})</option>`).join('');
  const actOpts = `<option value="">${AL('All actions', 'Сите дејства')}</option>` +
    Object.keys(ACT).map(a => `<option value="${a}" ${f.action === a ? 'selected' : ''}>${AL(ACT[a].en, ACT[a].mk)}</option>`).join('');

  const toolbar = `
    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:6px 4px 16px">
      <div style="display:flex;align-items:center;gap:10px;min-width:0">
        <h2 style="margin:0;font-size:19px;font-weight:800;color:var(--ink)">${AL('Audit Trail', 'Ревизорска трага')}</h2>
        ${badge}
      </div>
      <div style="flex:1"></div>
      <select id="audit-f-table" onchange="GF.WWF.applyAuditFilter()" class="audit-select" style="padding:8px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;font-size:13px">${tableOpts}</select>
      <select id="audit-f-action" onchange="GF.WWF.applyAuditFilter()" class="audit-select" style="padding:8px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;font-size:13px">${actOpts}</select>
      <button class="btn btn-sm" onclick="GF.WWF.loadAudit({reset:true})">${GF.icon('clock')}${AL('Refresh', 'Освежи')}</button>
    </div>`;

  let rows;
  if (!st.entries.length) {
    rows = `<div style="padding:40px;text-align:center;color:var(--ink-3)">${AL('No audit entries match.', 'Нема записи.')}</div>`;
  } else {
    rows = st.entries.map(e => {
      const a = ACT[e.action] || { c: '#5A6B82', en: e.action, mk: e.action };
      const when = e.created_at ? new Date(e.created_at).toLocaleString() : '';
      const diff = GF.WWF._auditDiff(e);
      const diffHtml = diff.length ? diff.map(([k, ov, nv]) => `
        <div style="display:grid;grid-template-columns:170px 1fr;gap:8px;padding:4px 0;border-top:1px dashed var(--line);font-size:12.5px">
          <div style="font-weight:600;color:var(--ink-2);font-family:ui-monospace,monospace">${GF.esc(k)}</div>
          <div style="min-width:0">
            ${e.action !== 'INSERT' ? `<span style="color:#C42121;text-decoration:${e.action === 'DELETE' ? 'none' : 'line-through'}">${GF.esc(GF.WWF._auditTrunc(ov))}</span>` : ''}
            ${e.action === 'UPDATE' ? '<span style="color:var(--ink-3);margin:0 6px">→</span>' : ''}
            ${e.action !== 'DELETE' ? `<span style="color:#0F7A4D">${GF.esc(GF.WWF._auditTrunc(nv))}</span>` : ''}
          </div>
        </div>`).join('') : `<div style="font-size:12.5px;color:var(--ink-3);padding:4px 0">${AL('No field-level changes recorded.', 'Нема промени на полиња.')}</div>`;
      return `
      <details class="audit-entry" style="background:#fff;border:1px solid var(--line);border-radius:11px;margin-bottom:8px;overflow:hidden">
        <summary style="display:flex;align-items:center;gap:12px;padding:11px 14px;cursor:pointer;list-style:none">
          <span style="font-size:11.5px;color:var(--ink-3);white-space:nowrap;min-width:148px">${GF.esc(when)}</span>
          <span style="background:${a.c}1A;color:${a.c};font-weight:700;font-size:11px;padding:3px 9px;border-radius:6px;white-space:nowrap">${AL(a.en, a.mk)}</span>
          <span style="font-weight:700;font-size:13px;color:var(--ink);font-family:ui-monospace,monospace">${GF.esc(e.table_name || '—')}</span>
          <span style="font-size:12px;color:var(--ink-3);font-family:ui-monospace,monospace">#${GF.esc(String(e.record_id || '').slice(0, 8))}</span>
          <span style="flex:1"></span>
          <span style="font-size:12.5px;color:var(--ink-2)">${GF.icon('user')}&nbsp;${GF.esc(GF.WWF._auditActor(e))}</span>
        </summary>
        <div style="padding:8px 14px 14px;background:#FAFBFC">
          ${diffHtml}
          <div style="margin-top:9px;font-size:10.5px;color:var(--ink-3);font-family:ui-monospace,monospace;word-break:break-all">
            entry_hash: ${GF.esc((e.entry_hash || '').slice(0, 24))}… · prev: ${GF.esc((e.prev_hash || '∅').slice(0, 16))}…</div>
        </div>
      </details>`;
    }).join('');
  }

  const more = st.hasMore
    ? `<div style="text-align:center;margin-top:10px"><button class="btn" onclick="GF.WWF.loadAudit({reset:false})">${AL('Load more', 'Вчитај повеќе')}</button></div>`
    : '';

  v.innerHTML = toolbar + `<div id="audit-list">${rows}</div>` + more;
};

/* nav item + chrome hiding for the audit view (elevated roles only) */
(function () {
  const _sidebar = GF.render.sidebar.bind(GF.render);
  GF.render.sidebar = function () {
    _sidebar();
    if (!GF.WWF.canAudit()) return;
    const nav = GF.$('nav'); if (!nav) return;
    let item = nav.querySelector('[data-nav="audit"]');
    if (!item) {
      item = document.createElement('div');
      item.setAttribute('data-nav', 'audit');
      item.onclick = () => GF.setView('audit');
      item.innerHTML = GF.icon('shield') + `<span>${AL('Audit Trail', 'Ревизија')}</span>`;
      nav.appendChild(item);
    }
    item.className = 'nav-item' + (GF.state.view === 'audit' ? ' active' : '');
  };

  const _all = GF.render.all.bind(GF.render);
  GF.render.all = function () {
    // Non-elevated user somehow on the audit view → bounce to My Week.
    if (GF.state.view === 'audit' && !GF.WWF.canAudit()) GF.state.view = 'mywork';
    _all();
    if (GF.state.view === 'audit') {
      ['week-strip', 'day-pills', 'telemetry'].forEach(id => { const el = GF.$(id); if (el) el.style.display = 'none'; });
    }
  };
})();
