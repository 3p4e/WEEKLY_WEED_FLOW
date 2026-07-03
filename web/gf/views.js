/* views.js — Board, Timeline, Coordination, Dashboard, Team views. Global: GF.views */
window.GF = window.GF || {};

GF.viewHead = (titleKey, subKey, right = '') => `
  <div class="view-head">
    <div><div class="view-title">${GF.t(titleKey)}</div>
      <div class="view-sub">${GF.t(subKey)}</div></div>
    <div class="spacer"></div>${right}
  </div>`;

GF.views = {
  /* ── Board: kanban by status ───────────────────────────── */
  board() {
    const tasks = GF.visibleTasks(GF.state.selWeek);
    const cols = GF.STATUS_ORDER.filter(s => s !== 'postponed');
    const colColor = { pending:'var(--ink-3)', working:'var(--orange)', review:'var(--blue)', stuck:'var(--red)', done:'var(--green)' };
    const body = cols.map(s => {
      const items = tasks.filter(t => t.status === s);
      return `<div class="kcol">
        <div class="kcol-head"><span class="dot" style="background:${colColor[s]}"></span>${GF.statusLabel(s)}
          <span class="kcount">${items.length}</span></div>
        <div class="kcol-body" data-status="${s}" ondragover="GF.dndOver(event)" ondragleave="GF.dndLeave(event)" ondrop="GF.dndDrop(event,'${s}')">
          ${items.map(t => {
            const d = GF.dep(t.dept);
            const drag = GF.can('status', t);
            return `<div class="kcard${drag?' drag':''}" ${drag?`draggable="true" ondragstart="GF.dndStart(event,'${t.id}')" ondragend="GF.dndEnd(event)"`:''} onclick="GF.state.expanded.add('${t.id}');GF.setView('mywork')">
              <div class="kcard-dept" style="color:${d.color}">${GF.depName(t.dept)}</div>
              <div class="kcard-title">${GF.esc(t.title)}</div>
              <div class="kcard-foot">
                ${GF.avatars([t.owner, ...(t.helpers||[])], 22)}
                <div class="spacer"></div>
                <span class="prtag ${t.pr}">${GF.prLabel(t.pr)}</span>
              </div></div>`;
          }).join('') || `<div class="kempty">—</div>`}
        </div></div>`;
    }).join('');
    const addBtn = GF.can('create')
      ? `<button class="btn btn-orange btn-sm" onclick="GF.openAdd(${GF.state.selWeek})">${GF.icon('plus','icon','#fff')}${GF.t('new_task_btn')}</button>` : '';
    return GF.viewHead('board','board_sub', addBtn)
      + `<div class="kboard">${body}</div>`;
  },

  /* ── Timeline: day columns across the week ─────────────── */
  timeline() {
    const tasks = GF.weekTasks(GF.state.selWeek);
    const days = GF.DAYS.slice(0, 5);
    const cols = days.map(day => {
      const items = tasks.filter(t => (t.days||[]).includes(day));
      const isToday = day === GF.todayDay;
      return `<div class="tlcol ${isToday?'today':''}">
        <div class="tlcol-head">${GF.dayLabel(day)}<span class="kcount">${items.length}</span></div>
        <div class="tlcol-body">
          ${items.map(t => { const d = GF.dep(t.dept);
            return `<div class="tlcard s-${t.status}" style="border-left-color:${d.color}"
              onclick="GF.state.expanded.add('${t.id}');GF.setView('mywork')">
              <div class="tlcard-title">${GF.esc(t.title)}</div>
              <div class="tlcard-meta"><span class="pill s-${t.status}" style="pointer-events:none"><span class="dot" style="background:currentColor;opacity:.7"></span>${GF.statusLabel(t.status)}</span>${GF.avatars([t.owner],20)}</div>
            </div>`; }).join('') || `<div class="kempty">—</div>`}
        </div></div>`;
    }).join('');
    return GF.viewHead('timeline','timeline_sub') + `<div class="timeline-grid">${cols}</div>`;
  },

  /* ── Coordination: cross-department handoffs ───────────── */
  coord() {
    const tasks = GF.weekTasks(GF.state.selWeek);
    const rows = tasks.filter(t => GF.HANDOFF[t.dept]).map(t => {
      const from = GF.dep(t.dept), toId = GF.HANDOFF[t.dept], to = GF.dep(toId);
      const ready = t.status === 'done';
      const blockedDeps = (t.deps||[]).map(id=>GF.task(id)).filter(x=>x && x.status!=='done');
      return `<div class="coord-row ${ready?'ready':''}">
        <div class="coord-task">
          <div class="coord-title">${GF.esc(t.title)}</div>
          <div class="coord-id">${GF.esc(t.id)}</div>
        </div>
        <div class="coord-flow">
          <span class="hbadge"><span class="chip-dept">${GF.icon(from.icon,'icon',from.color)}</span>${GF.depName(t.dept)}</span>
          ${GF.icon('arrowR','icon','var(--ink-3)')}
          <span class="hbadge"><span class="chip-dept">${GF.icon(to.icon,'icon',to.color)}</span>${GF.depName(toId)}</span>
        </div>
        <div class="coord-status">
          ${ready ? `<span class="coord-tag ok">${GF.icon('check','icon','#fff')}Ready</span>`
            : blockedDeps.length ? `<span class="coord-tag wait">${GF.icon('clock','icon')}Waiting on ${blockedDeps.length}</span>`
            : `<span class="coord-tag prog">${GF.icon('clock','icon')}${GF.statusLabel(t.status)}</span>`}
          <button class="btn btn-sm" onclick="GF.toast('${GF.t('request_handoff')} → ${GF.depName(toId)}','success')">${GF.t('request_handoff')}</button>
        </div>
      </div>`;
    }).join('');
    return GF.viewHead('coordination','coord_sub')
      + `<div class="coord-list">${rows || `<div class="kempty" style="padding:40px;text-align:center">—</div>`}</div>`;
  },

  /* ── Dashboard: production overview ────────────────────── */
  dash() {
    const all = GF.weekTasks(GF.state.selWeek);
    const n = all.length;
    const by = s => all.filter(t => t.status === s).length;
    const rate = n ? Math.round(by('done')/n*100) : 0;
    const statRows = GF.STATUS_ORDER.map(s => {
      const c = by(s), pct = n ? Math.round(c/n*100) : 0;
      const col = { pending:'var(--ink-3)', working:'var(--orange)', review:'var(--blue)', stuck:'var(--red)', postponed:'var(--amber)', done:'var(--green)' }[s];
      return `<div class="dash-bar-row"><span class="dbl">${GF.statusLabel(s)}</span>
        <div class="track" style="flex:1"><span style="width:${pct}%;background:${col}"></span></div>
        <span class="dbv">${c}</span></div>`;
    }).join('');
    // by department
    const deptCounts = {}; all.forEach(t => deptCounts[t.dept] = (deptCounts[t.dept]||0)+1);
    const deptRows = GF.DEPTS.filter(d => deptCounts[d.id]).sort((a,b)=>deptCounts[b.id]-deptCounts[a.id]).map(d => {
      const c = deptCounts[d.id], pct = Math.round(c/n*100);
      return `<div class="dash-bar-row"><span class="dbl" style="color:${d.color};font-weight:700">${GF.depName(d.id)}</span>
        <div class="track" style="flex:1"><span style="width:${pct}%;background:${d.color}"></span></div>
        <span class="dbv">${c}</span></div>`;
    }).join('');
    // workload by person
    const load = {}; all.forEach(t => { [t.owner,...(t.helpers||[])].forEach(p => load[p]=(load[p]||0)+1); });
    const loadRows = Object.entries(load).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([id,c]) => {
      const p = GF.PEOPLE[id]; if(!p) return '';
      return `<div class="dash-person">${GF.avatar(id,30)}<div style="flex:1;min-width:0">
        <div class="dp-name">${GF.esc(p.name)}</div><div class="dp-role">${GF.esc(GF.roleLabel(p.role))}</div></div>
        <span class="dp-count">${c}</span></div>`;
    }).join('');
    const dayCount = {}; GF.DAYS.forEach(d => dayCount[d]=all.filter(t=>(t.days||[]).includes(d)).length);
    const busiest = Object.entries(dayCount).sort((a,b)=>b[1]-a[1])[0];
    const blockers = all.filter(t=>t.status==='stuck');
    const kpi = (v,l,c) => `<div class="kpi"><div class="kpi-v" style="color:${c}">${v}</div><div class="kpi-l">${l}</div></div>`;
    return GF.viewHead('dashboard','dash_sub') + `
      <div class="dash-kpis">
        ${kpi(rate+'%', GF.t('completion'), 'var(--green)')}
        ${kpi(n, GF.t('total'), 'var(--ink)')}
        ${kpi(by('working'), GF.t('working'), 'var(--orange)')}
        ${kpi(by('stuck'), GF.t('stuck'), 'var(--red)')}
        ${kpi(busiest?GF.dayLabel(busiest[0]):'—', GF.t('busiest'), 'var(--violet)')}
      </div>
      <div class="dash-grid">
        <div class="dash-card"><div class="dash-card-ttl">${GF.t('completion')} · ${GF.t('total')}</div>${statRows}</div>
        <div class="dash-card"><div class="dash-card-ttl">${GF.t('departments')}</div>${deptRows||'<div class="kempty">—</div>'}</div>
        <div class="dash-card"><div class="dash-card-ttl">${GF.t('responsible')}</div>${loadRows||'<div class="kempty">—</div>'}</div>
        <div class="dash-card"><div class="dash-card-ttl">${GF.t('blocker')} · ${blockers.length}</div>
          ${blockers.map(t=>`<div class="dash-blk">${GF.icon('flag','icon','var(--red)')}<div><div class="dbk-t">${GF.esc(t.title)}</div><div class="dbk-s">${GF.esc(t.blocker||'')}</div></div></div>`).join('')||'<div class="kempty">None 🎉</div>'}</div>
      </div>`;
  },

  /* ── Team: people & roles management ───────────────────── */
  team() {
    const ids = Object.keys(GF.PEOPLE);
    const canManage = GF.can('team');
    const cards = ids.map(id => {
      const p = GF.PEOPLE[id];
      const isMe = id === GF.state.user;
      return `<div class="team-card ${isMe?'me':''}">
        <div class="team-top">${GF.avatar(id,46)}
          <div style="flex:1;min-width:0">
            <div class="tc-name">${GF.esc(p.name)}${isMe?` <span class="tc-you">${GF.t('you')}</span>`:''}</div>
            <div class="tc-role">${GF.esc(GF.roleLabel(p.role))}</div>
          </div></div>
        <div class="tc-dept"><span class="dept-dot" style="background:${GF.dep(p.dept).color}"></span>${GF.depName(p.dept)}</div>
        <div class="tc-actions">
          ${isMe?`<span class="tc-active">${GF.icon('check','icon','var(--green)')}${GF.t('active')}</span>`
            :`<button class="btn btn-sm" onclick="GF.setActiveUser('${id}')">${GF.t('set_active')}</button>`}
          <div class="spacer"></div>
          ${canManage?`<button class="icon-btn btn-sm" title="${GF.t('edit')}" onclick="GF.openUser('${id}')">${GF.icon('settings')}</button>`:''}
          ${canManage && ids.length>1?`<button class="icon-btn btn-sm" title="${GF.t('remove')}" onclick="GF.removeUser('${id}')">${GF.icon('trash')}</button>`:''}
        </div>
      </div>`;
    }).join('');
    const addBtn = canManage
      ? `<button class="btn btn-orange btn-sm" onclick="GF.openUser()">${GF.icon('plus','icon','#fff')}${GF.t('add_user')}</button>`
      : `<span class="role-lock">${GF.icon('shield','icon','var(--ink-3)')}${GF.t('view_only')}</span>`;
    return GF.viewHead('team','team_sub', addBtn)
      + `<div class="team-count">${ids.length} ${GF.t('members')} · ${GF.t('your_role')}: <b>${GF.roleLabel(GF.curRole())}</b></div>`
      + `<div class="team-grid">${cards}</div>`;
  },
};

/* ── Board drag-and-drop ── */
GF._dragId = null;
GF.dndStart = (e, id) => {
  GF._dragId = id;
  try { e.dataTransfer.setData('text/plain', id); e.dataTransfer.effectAllowed = 'move'; } catch (x) {}
  e.currentTarget.classList.add('dragging');
};
GF.dndEnd = (e) => {
  e.currentTarget.classList.remove('dragging');
  document.querySelectorAll('.kcol-body.drop-hot').forEach(x => x.classList.remove('drop-hot'));
  GF._dragId = null;
};
GF.dndOver = (e) => { e.preventDefault(); try { e.dataTransfer.dropEffect = 'move'; } catch (x) {} e.currentTarget.classList.add('drop-hot'); };
GF.dndLeave = (e) => { if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.classList.remove('drop-hot'); };
GF.dndDrop = (e, status) => {
  e.preventDefault();
  e.currentTarget.classList.remove('drop-hot');
  let id = ''; try { id = e.dataTransfer.getData('text/plain'); } catch (x) {}
  id = id || GF._dragId; GF._dragId = null;
  if (!id) return;
  if (GF.setStatus(id, status)) { GF.render.all(); GF.toast(GF.statusLabel(status) + ' ✓', 'success'); }
};
