/* integrate.js — bridges the GrowFlow UI to the real WEEKLY_WEED_FLOW backend.
   Loaded LAST. Replaces the localStorage/seed data layer with live API data:
   login -> load real departments/weeks/tasks -> render GrowFlow UI -> writes go to the API. */
window.GF = window.GF || {};
GF.WWF = {};

/* ── enum mapping (backend <-> GrowFlow) ───────────────────────────── */
const S_IN  = { ongoing:'working', completed:'done', pending:'pending', stuck:'stuck', review:'review', postponed:'postponed' };
const S_OUT = { working:'ongoing', done:'completed', pending:'pending', stuck:'stuck', review:'review', postponed:'postponed' };
const P_IN  = { normal:'medium', high:'high', critical:'critical', low:'low' };
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
  owner: t.user_id || GF.WWF.meId, helpers: [],
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
      t.desc = r.output.trim();
      await GF.API.updateTask(taskId, { description: t.desc });
      GF.render.panels(); GF.toast('Rewritten ✓', 'success');
    } catch (e) { GF.toast('AI error', 'error'); }
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

  if (GF.assistant) GF.assistant.complete = async (prompt) => {
    const r = await GF.API.ai('corpus_qa', { input: prompt }); return (r && r.available && r.output) || ''; };

  // Voice-captured tasks must persist through the same API path as GF.submitAdd.
  GF.voice.createFromVoice = async () => {
    const p = GF.voice._parsed || {};
    const deptMatch = GF.DEPTS.find(d => d.name.toLowerCase().includes((p.department || '').toLowerCase())
      || d.mk.toLowerCase().includes((p.department || '').toLowerCase()));
    const ownerMatch = Object.entries(GF.PEOPLE).find(([, v]) => v.name.toLowerCase().includes((p.assignee || '').toLowerCase()));
    const days = Array.isArray(p.days) && p.days.length ? p.days : [GF.todayDay];
    const wk = GF.calendar.weeks[GF.voice._weekId] || GF.calendar.weeks[GF.calendar.todayId];
    try {
      const created = await GF.API.createTask({
        title: p.title || GF.voice._transcript, description: '', status: 'pending',
        priority: P_OUT[p.priority] || 'normal',
        department_id: deptMatch ? deptMatch.id : null, department: deptMatch ? deptMatch.name : null,
        week_id: wk && wk.realId, week_start: wk ? wk.start.toISOString().slice(0,10) : null, days,
      });
      GF.state.tasks.push(GF.WWF.transform(created));
      if (ownerMatch && ownerMatch[0] !== GF.WWF.meId) GF.API.assign(created.id, ownerMatch[0]).catch(()=>{});
      GF.closeModal('voice-modal'); GF.render.all(); GF.toast(GF.t('create_task') + ' ✓', 'success');
    } catch (e) { GF.toast('Create failed: ' + e.message, 'error'); }
  };

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
GF.WWF._audit = { entries: [], before: null, tables: null, verify: null, hasMore: false, gen: 0 };
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
  // Bump a generation token so a slower in-flight load can't append its rows
  // on top of a newer reset/filter load (which would duplicate entries).
  const gen = ++st.gen;
  const q = { limit: 100 };
  if (GF.WWF._auditFilter.table_name) q.table_name = GF.WWF._auditFilter.table_name;
  if (GF.WWF._auditFilter.action) q.action = GF.WWF._auditFilter.action;
  if (st.before) q.before_id = st.before;
  try {
    const page = await GF.API.audit(q);
    if (gen !== st.gen) return;   // a newer load superseded this one
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
          <span style="background:${a.c}1A;color:${a.c};font-weight:700;font-size:11px;padding:3px 9px;border-radius:6px;white-space:nowrap">${GF.esc(AL(a.en, a.mk))}</span>
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

/* ══════════════════════════════════════════════════════════════════════
   Task collaboration — comments + assignment/acknowledgment, injected into the
   expanded task card. Comments are visible to anyone who can see the task;
   assigning a teammate makes the task appear in their week and lets them
   accept/decline. Backed by /tasks/{id}/comments|assignees|ack.
   ════════════════════════════════════════════════════════════════════ */
GF.WWF._collab = {};   // taskId -> { comments, assignees, loaded }

GF.WWF.canManageTask = (t) =>
  AUDIT_ROLES.includes((GF.API.user || {}).role) || (t && t.owner === GF.WWF.meId);

GF.WWF._when = (iso) => { try { return new Date(iso).toLocaleString(); } catch (e) { return ''; } };

GF.WWF.collabSection = (t) => {
  const c = GF.WWF._collab[t.id];
  if (!c || !c.loaded) setTimeout(() => GF.WWF.loadCollab(t.id), 0);
  return `<div class="collab-sec" id="collab-${t.id}">${GF.WWF.renderCollabInner(t)}</div>`;
};

GF.WWF.renderCollabInner = (t) => {
  const c = GF.WWF._collab[t.id];
  if (!c || !c.loaded) return `<div style="font-size:12px;color:var(--ink-3);padding:6px 0">${AL('Loading…', 'Се вчитува…')}</div>`;
  const me = (GF.API.user || {}).id;
  const manage = GF.WWF.canManageTask(t);

  // Comments thread
  const comments = c.comments.length ? c.comments.map(m => `
    <div class="note" style="align-items:flex-start">
      <span class="nd" style="min-width:0;flex:0 0 auto">${GF.esc(m.author || '—')}</span>
      <span style="flex:1">${GF.esc(m.content)}</span>
      <span style="font-size:10px;color:var(--ink-3);white-space:nowrap">${GF.esc(GF.WWF._when(m.created_at))}</span>
    </div>`).join('') : `<div style="font-size:12px;color:var(--ink-3)">${AL('No comments yet.', 'Сè уште нема коментари.')}</div>`;

  // Assignee chips (+ accept/decline for me, remove for managers)
  const chips = c.assignees.map(a => {
    const state = a.accepted === true ? `<span style="color:var(--green)">✓ ${AL('accepted', 'прифатено')}</span>`
      : a.accepted === false ? `<span style="color:#E5484D">✋ ${AL('declined', 'одбиено')}</span>`
      : `<span style="color:var(--ink-3)">${AL('pending', 'во тек')}</span>`;
    const mineActions = (a.user_id === me && a.accepted == null) ? `
      <button class="mini-btn" style="color:var(--green)" title="${AL('Accept', 'Прифати')}" onclick="GF.WWF.doAck('${t.id}',true)">✓</button>
      <button class="mini-btn" style="color:#E5484D" title="${AL('Decline', 'Одбиј')}" onclick="GF.WWF.doAck('${t.id}',false)">✕</button>` : '';
    const rm = manage ? `<button class="mini-btn" style="color:var(--ink-3)" title="${AL('Remove', 'Отстрани')}" onclick="GF.WWF.removeAssignee('${t.id}','${a.user_id}')">×</button>` : '';
    return `<span class="dep-chip" style="gap:6px">${GF.icon('user','icon')}${GF.esc(a.name)} ${state}${mineActions}${rm}</span>`;
  }).join('');

  // Assign control (managers only): teammates not already assigned
  let assignRow = '';
  if (manage) {
    const have = new Set(c.assignees.map(a => a.user_id));
    const opts = Object.keys(GF.PEOPLE || {}).filter(id => !have.has(id))
      .map(id => `<option value="${id}">${GF.esc(GF.PEOPLE[id].name)}</option>`).join('');
    assignRow = opts ? `
      <div class="note-input" style="margin-top:6px">
        <select id="assign-${t.id}" style="flex:1;padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px">${opts}</select>
        <button class="mini-btn" style="color:var(--blue)" title="${AL('Assign', 'Додели')}" onclick="GF.WWF.doAssign('${t.id}')">${GF.icon('plus')}</button>
      </div>` : '';
  }

  return `
    <div class="sec-label">${GF.icon('at','icon')}${AL('Assignees', 'Доделени')}</div>
    <div class="deps">${chips || `<span style="font-size:12px;color:var(--ink-3)">${AL('Nobody assigned.', 'Никој не е доделен.')}</span>`}</div>
    ${assignRow}
    <div class="sec-label">${GF.icon('chat','icon')}${AL('Comments', 'Коментари')}</div>
    <div class="notes">${comments}</div>
    <div class="note-input">
      <input id="cmt-${t.id}" placeholder="${AL('Add a comment…', 'Додади коментар…')}" onkeydown="if(event.key==='Enter')GF.WWF.postComment('${t.id}')">
      <button class="mini-btn" style="color:var(--blue)" onclick="GF.WWF.postComment('${t.id}')">${GF.icon('plus')}</button>
    </div>`;
};

GF.WWF.loadCollab = async (taskId) => {
  try {
    const [comments, assignees] = await Promise.all([
      GF.API.comments(taskId).catch(() => []),
      GF.API.assignees(taskId).catch(() => []),
    ]);
    GF.WWF._collab[taskId] = { comments: comments || [], assignees: assignees || [], loaded: true };
  } catch (e) {
    GF.WWF._collab[taskId] = { comments: [], assignees: [], loaded: true };
  }
  const t = GF.task(taskId);
  const el = GF.$('collab-' + taskId);
  if (el && t) el.innerHTML = GF.WWF.renderCollabInner(t);
};

GF.WWF.postComment = async (taskId) => {
  const inp = GF.$('cmt-' + taskId); const text = inp && inp.value.trim();
  if (!text) return;
  inp.value = '';
  try { await GF.API.addComment(taskId, text); await GF.WWF.loadCollab(taskId); }
  catch (e) { GF.toast('Comment failed: ' + e.message, 'error'); }
};

GF.WWF.doAssign = async (taskId) => {
  const sel = GF.$('assign-' + taskId); const uid = sel && sel.value;
  if (!uid) return;
  try { await GF.API.assign(taskId, uid); await GF.WWF.loadCollab(taskId); GF.toast(AL('Assigned ✓', 'Доделено ✓'), 'success'); }
  catch (e) { GF.toast('Assign failed: ' + e.message, 'error'); }
};

GF.WWF.removeAssignee = async (taskId, userId) => {
  try { await GF.API.unassign(taskId, userId); await GF.WWF.loadCollab(taskId); }
  catch (e) { GF.toast('Remove failed: ' + e.message, 'error'); }
};

GF.WWF.doAck = async (taskId, accepted) => {
  let reason = null;
  if (!accepted) { reason = prompt(AL('Reason for declining (optional):', 'Причина за одбивање (опционално):')) || ''; }
  try { await GF.API.ack(taskId, accepted, reason); await GF.WWF.loadCollab(taskId);
    GF.toast(accepted ? AL('Accepted ✓', 'Прифатено ✓') : AL('Declined', 'Одбиено'), accepted ? 'success' : 'info'); }
  catch (e) { GF.toast('Failed: ' + e.message, 'error'); }
};

// Inject the collab section into every expanded card, just above its actions.
(function () {
  const _card = GF.render.card.bind(GF.render);
  GF.render.card = function (t) {
    const html = _card(t);
    if (!GF.state.expanded || !GF.state.expanded.has(t.id)) return html;
    const anchor = '<div class="card-actions">';
    // Function replacement → returned text is inserted literally (a string
    // replacement would interpret $&/$'/$1 patterns inside comment content).
    return html.indexOf(anchor) >= 0
      ? html.replace(anchor, () => GF.WWF.collabSection(t) + anchor)
      : html;
  };
})();

/* ══════════════════════════════════════════════════════════════════════
   Weekly Report + Plan — Fri→Thu rolling window with 7-day activity
   time band and AI-generated insights. All data from real timestamps.
   ════════════════════════════════════════════════════════════════════ */
GF.WWF._report = { data: null, mode: 'report', refDate: null, loading: false, aiInsights: null, aiLoading: false };

GF.WWF._sc = (label, value, color) =>
  `<div style="background:#fff;border:1px solid var(--line);border-radius:11px;padding:14px 16px;text-align:center">
    <div style="font-size:24px;font-weight:800;color:${color}">${value}</div>
    <div style="font-size:12px;color:var(--ink-3);margin-top:2px">${label}</div>
  </div>`;

GF.views.report = function () {
  setTimeout(() => GF.WWF.loadReport(), 0);
  return `<div id="report-view" style="padding:4px 2px 40px">
    <div style="padding:40px;text-align:center;color:var(--ink-3)">${AL('Loading report…', 'Се вчитува извештај…')}</div>
  </div>`;
};

GF.WWF.loadReport = async () => {
  const st = GF.WWF._report;
  if (st.loading) return;
  st.loading = true;
  st.aiInsights = null;
  try {
    const q = { mode: st.mode };
    if (st.refDate) q.ref_date = st.refDate;
    st.data = await GF.API.weeklyReport(q);
    GF.WWF.renderReport();
    if (st.mode === 'report') GF.WWF._loadAiInsights();
  } catch (e) {
    const v = GF.$('report-view');
    if (v) v.innerHTML = `<div style="padding:40px;text-align:center;color:#E5484D">${AL('Failed to load report', 'Не може да се вчита извештај')}: ${GF.esc(e.message)}</div>`;
  } finally {
    st.loading = false;
  }
};

GF.WWF._loadAiInsights = async () => {
  const st = GF.WWF._report;
  if (!st.data) return;
  st.aiLoading = true;
  const el = GF.$('report-ai');
  if (el) el.innerHTML = `<div style="padding:16px;text-align:center;color:var(--ink-3)">${GF.icon('sparkle')} ${AL('Generating AI insights…', 'Генерирање AI увиди…')}</div>`;
  try {
    const p = st.data.period;
    const s = st.data.summary;
    const result = await GF.API.ai('weekly_summary', {
      input: 'Generate a concise weekly summary for ' + p.label + '. ' +
             'Total tasks: ' + s.total + ', completed: ' + s.completed +
             ', in progress: ' + s.in_progress + ', stuck: ' + s.stuck +
             ', pending: ' + s.pending + '. ' +
             'Estimated hours: ' + s.estimated_hours + ', actual: ' + s.actual_hours + '. ' +
             'Provide insights on productivity, risks, and recommendations for next week.',
    });
    st.aiInsights = result.available ? result.output : null;
  } catch (e) {
    st.aiInsights = null;
  }
  st.aiLoading = false;
  const aiEl = GF.$('report-ai');
  if (aiEl) aiEl.innerHTML = GF.WWF._renderAiBox();
};

GF.WWF._renderAiBox = () => {
  const st = GF.WWF._report;
  if (st.aiLoading) return `<div style="padding:16px;text-align:center;color:var(--ink-3)">${GF.icon('sparkle')} ${AL('Generating AI insights…', 'Генерирање AI увиди…')}</div>`;
  if (!st.aiInsights) return `<div style="padding:16px;color:var(--ink-3);font-size:13px">${AL('AI insights unavailable.', 'AI увидите не се достапни.')}</div>`;
  return `<div style="padding:14px;font-size:13.5px;line-height:1.65;color:var(--ink);white-space:pre-wrap">${GF.esc(st.aiInsights)}</div>`;
};

GF.WWF.switchReportMode = (mode) => {
  GF.WWF._report.mode = mode;
  GF.WWF.loadReport();
};

GF.WWF.shiftReportWeek = (delta) => {
  const st = GF.WWF._report;
  if (delta === 0) { st.refDate = null; }
  else {
    const ref = st.data ? new Date(st.data.period.start) : new Date();
    ref.setDate(ref.getDate() + delta * 7);
    st.refDate = ref.toISOString().slice(0, 10);
  }
  GF.WWF.loadReport();
};

GF.WWF._renderTimeBand = (band) => {
  if (!band || !band.length) return '';
  const maxCount = Math.max(1, ...band.flatMap(d => d.hours));

  let html = '<div style="margin:18px 0">';
  html += `<div style="font-weight:700;font-size:14px;color:var(--ink);margin-bottom:10px">${AL('Activity Time Band', 'Временска лента на активност')}</div>`;
  html += '<div style="display:flex;gap:3px;overflow-x:auto;padding:4px 0">';

  band.forEach(day => {
    const isWe = day.dow === 5 || day.dow === 6;
    const lbl = day.day_name + '<br><span style="font-size:10px">' + day.date.slice(5) + '</span>';
    const total = day.hours.reduce((a, b) => a + b, 0);

    html += `<div style="flex:1;min-width:58px;text-align:center">
      <div style="font-size:11px;font-weight:600;color:${isWe ? '#E5484D' : 'var(--ink-2)'};margin-bottom:6px;line-height:1.3">${lbl}</div>
      <div style="display:flex;flex-direction:column;gap:1px;background:#f4f4f5;border-radius:4px;padding:2px;overflow:hidden">`;

    for (let h = 0; h < 24; h++) {
      const count = day.hours[h];
      let color;
      if (isWe) color = '#E5484D';
      else if (h >= 8 && h < 17) color = '#15A86B';
      else color = '#FF7A1A';
      const opacity = count > 0 ? Math.min(0.3 + (count / maxCount) * 0.7, 1) : 0.05;
      const tip = day.day_name + ' ' + String(h).padStart(2, '0') + ':00 — ' + count + ' event' + (count !== 1 ? 's' : '');
      html += `<div title="${GF.esc(tip)}" style="height:3px;background:${color};opacity:${opacity.toFixed(2)};border-radius:1px"></div>`;
    }

    html += `</div>
      <div style="font-size:10px;color:var(--ink-3);margin-top:4px">${total}</div>
    </div>`;
  });

  html += '</div>';
  html += `<div style="display:flex;gap:16px;margin-top:8px;font-size:11px;color:var(--ink-3)">
    <span><span style="display:inline-block;width:10px;height:10px;background:#15A86B;border-radius:2px;margin-right:4px;vertical-align:middle"></span>${AL('Regular (8–17)', 'Редовно (8–17)')}</span>
    <span><span style="display:inline-block;width:10px;height:10px;background:#FF7A1A;border-radius:2px;margin-right:4px;vertical-align:middle"></span>${AL('Overtime', 'Прекувремено')}</span>
    <span><span style="display:inline-block;width:10px;height:10px;background:#E5484D;border-radius:2px;margin-right:4px;vertical-align:middle"></span>${AL('Weekend', 'Викенд')}</span>
  </div></div>`;
  return html;
};

GF.WWF.renderReport = () => {
  const v = GF.$('report-view'); if (!v) return;
  const d = GF.WWF._report.data; if (!d) return;
  const isR = d.mode === 'report';
  const s = d.summary;

  const toolbar = `
    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:6px 4px 18px">
      <h2 style="margin:0;font-size:19px;font-weight:800;color:var(--ink)">
        ${isR ? AL('Weekly Report', 'Неделен извештај') : AL('Weekly Plan', 'Неделен план')}
      </h2>
      <div style="flex:1"></div>
      <div style="display:flex;gap:4px">
        <button class="btn btn-sm" onclick="GF.WWF.switchReportMode('report')" style="${isR ? 'background:var(--blue);color:#fff' : ''}">${AL('Report', 'Извештај')}</button>
        <button class="btn btn-sm" onclick="GF.WWF.switchReportMode('plan')" style="${!isR ? 'background:var(--blue);color:#fff' : ''}">${AL('Plan', 'План')}</button>
      </div>
      <div style="display:flex;gap:4px">
        <button class="btn btn-sm" onclick="GF.WWF.shiftReportWeek(-1)" title="${AL('Previous week', 'Претходна недела')}">◀</button>
        <button class="btn btn-sm" onclick="GF.WWF.shiftReportWeek(0)" title="${AL('Current week', 'Тековна недела')}">${AL('Today', 'Денес')}</button>
        <button class="btn btn-sm" onclick="GF.WWF.shiftReportWeek(1)" title="${AL('Next week', 'Следна недела')}">▶</button>
      </div>
    </div>`;

  const period = `<div style="font-size:14px;font-weight:600;color:var(--ink-2);margin:0 4px 16px">${GF.icon('calendar')} ${GF.esc(d.period.label)}</div>`;

  const cards = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:18px">
      ${GF.WWF._sc(AL('Total', 'Вкупно'), s.total, '#2F6BFF')}
      ${GF.WWF._sc(AL('Completed', 'Завршени'), s.completed, '#15A86B')}
      ${GF.WWF._sc(AL('In Progress', 'Во тек'), s.in_progress, '#FF7A1A')}
      ${GF.WWF._sc(AL('Stuck', 'Блокирани'), s.stuck, '#E5484D')}
      ${GF.WWF._sc(AL('Pending', 'Чекаат'), s.pending, '#5A6B82')}
      ${(s.estimated_hours || s.actual_hours) ? GF.WWF._sc(AL('Hours', 'Часови'), s.actual_hours + '/' + s.estimated_hours, '#7A5BE0') : ''}
    </div>`;

  const band = isR ? GF.WWF._renderTimeBand(d.time_band) : '';

  let depts = '';
  if (d.departments.length) {
    depts = `<div style="margin:18px 0">
      <div style="font-weight:700;font-size:14px;color:var(--ink);margin-bottom:8px">${AL('Departments', 'Оддели')}</div>
      ${d.departments.map(dp => {
        const pct = dp.total ? Math.round(dp.completed / dp.total * 100) : 0;
        return `<div style="display:flex;align-items:center;gap:10px;padding:7px 10px;background:#fff;border:1px solid var(--line);border-radius:9px;margin-bottom:6px">
          <span style="font-weight:600;font-size:13px;flex:1">${GF.esc(dp.name)}</span>
          <span style="font-size:12px;color:var(--ink-3)">${dp.completed}/${dp.total} ${AL('done', 'завршени')}</span>
          <div style="width:80px;height:6px;background:#eee;border-radius:3px;overflow:hidden">
            <div style="width:${pct}%;height:100%;background:#15A86B;border-radius:3px"></div>
          </div>
        </div>`;
      }).join('')}
    </div>`;
  }

  const SC = { completed: '#15A86B', done: '#15A86B', ongoing: '#FF7A1A', in_progress: '#FF7A1A',
               stuck: '#E5484D', pending: '#5A6B82', review: '#7A5BE0' };
  let taskList;
  if (d.tasks.length) {
    taskList = `<div style="margin:18px 0">
      <div style="font-weight:700;font-size:14px;color:var(--ink);margin-bottom:8px">${AL('Tasks', 'Задачи')} (${d.tasks.length})</div>
      ${d.tasks.map(t => {
        const col = SC[t.status] || '#5A6B82';
        return `<div style="display:flex;align-items:center;gap:10px;padding:9px 12px;background:#fff;border:1px solid var(--line);border-radius:9px;margin-bottom:5px">
          <span style="width:8px;height:8px;border-radius:50%;background:${col};flex-shrink:0"></span>
          <span style="flex:1;font-size:13px;font-weight:500;color:var(--ink)">${GF.esc(t.title)}</span>
          <span style="font-size:11px;color:var(--ink-3);white-space:nowrap">${GF.esc(t.department || '')}</span>
          <span style="font-size:11px;font-weight:700;color:${col};padding:2px 8px;background:${col}1A;border-radius:6px">${GF.esc(t.status)}</span>
        </div>`;
      }).join('')}
    </div>`;
  } else {
    taskList = `<div style="padding:20px;text-align:center;color:var(--ink-3)">${AL('No tasks in this period.', 'Нема задачи за овој период.')}</div>`;
  }

  const ai = isR ? `
    <div style="margin:18px 0;background:#F8F9FF;border:1px solid #D6E0FF;border-radius:11px;overflow:hidden">
      <div style="padding:12px 14px;border-bottom:1px solid #D6E0FF;font-weight:700;font-size:14px;color:#2F6BFF">
        ${GF.icon('sparkle')} ${AL('AI Insights', 'AI Увиди')}
      </div>
      <div id="report-ai">${GF.WWF._renderAiBox()}</div>
    </div>` : '';

  v.innerHTML = toolbar + period + cards + band + depts + taskList + ai;
};

/* nav item for the report/plan view */
(function () {
  const _sb3 = GF.render.sidebar.bind(GF.render);
  GF.render.sidebar = function () {
    _sb3();
    const nav = GF.$('nav'); if (!nav) return;
    let item = nav.querySelector('[data-nav="report"]');
    if (!item) {
      item = document.createElement('div');
      item.setAttribute('data-nav', 'report');
      item.onclick = () => GF.setView('report');
      item.innerHTML = GF.icon('trend') + `<span>${AL('Report', 'Извештај')}</span>`;
      const auditItem = nav.querySelector('[data-nav="audit"]');
      if (auditItem) nav.insertBefore(item, auditItem);
      else nav.appendChild(item);
    }
    item.className = 'nav-item' + (GF.state.view === 'report' ? ' active' : '');
  };

  const _all3 = GF.render.all.bind(GF.render);
  GF.render.all = function () {
    _all3();
    if (GF.state.view === 'report') {
      ['week-strip', 'day-pills', 'telemetry'].forEach(id => { const el = GF.$(id); if (el) el.style.display = 'none'; });
    }
  };
})();
