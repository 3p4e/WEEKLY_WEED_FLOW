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
  try { await GF.API.login(u, p); GF.$('wwf-login').style.display = 'none'; await GF.WWF.loadAndRender(); }
  catch (e) { if (m) m.textContent = e.message === 'unauthorized' ? 'Invalid username or password' : ('Error: ' + e.message); }
};

/* ── load real data + render ───────────────────────────────────────── */
GF.WWF.loadAndRender = async () => {
  const [depts, weeks, tasks] = await Promise.all([GF.API.departments(), GF.API.weeks(), GF.API.tasks()]);
  GF.DEPTS = depts.map(d => { const st = DEPT_STYLE[d.code] || {icon:'box',color:'#5A6B82'};
    return { id:d.id, name:d.name, mk:d.name_mk || d.name, icon:st.icon, color:st.color }; });
  const u = GF.API.user || {};
  GF.WWF.meId = u.id || 'me';
  GF.PEOPLE = {}; GF.PEOPLE[GF.WWF.meId] = {
    name:u.full_name || u.username || 'User', init:(u.full_name||u.username||'U').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase(),
    role: u.role==='ADMIN'?'admin':'hod', roleLabel:u.function_role || u.role || '', dept:(GF.DEPTS[0]||{}).id, bg:'#15A86B' };
  GF.state.user = GF.WWF.meId;
  GF.WWF.buildCalendar(weeks);
  GF.state.tasks = tasks.filter(t => !t.parent_id).map(GF.WWF.transform);
  GF.render.all();
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
