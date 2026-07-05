/* render.js — all DOM rendering. Global: GF.render */
window.GF = window.GF || {};

GF.avatar = (id, size = 28, ring) => {
  const p = GF.PEOPLE[id] || { init: '?', bg: '#8A99B0', name: '' };
  return `<div class="avatar" title="${GF.esc(p.name)}" style="width:${size}px;height:${size}px;background:${p.bg};
    font-size:${size * 0.38}px${ring ? `;box-shadow:0 0 0 2px #fff,0 0 0 4px ${p.bg}40` : ''}">${GF.esc(p.init)}</div>`;
};
GF.avatars = (ids, size = 26) => `<div class="avatars">${ids.map(i => GF.avatar(i, size)).join('')}</div>`;
GF.progress = (t) => ({ done: 100, working: 50, review: 75, stuck: 25, postponed: 10, pending: 0 }[t.status] ?? 0);
GF.HANDOFF = { clone:'veg', veg:'flower', flower:'prod', prod:'qc', qc:'qa', qa:'whout', irr:'prod', whin:'prod', maint:'irr' };

GF.render = {
  all() {
    this.sidebar(); this.header();
    const v = GF.state.view;
    const show = (id, on) => { const el = GF.$(id); if (el) el.style.display = on ? '' : 'none'; };
    const weekViews = v === 'mywork' || v === 'board' || v === 'timeline';
    show('week-strip', v !== 'team');
    show('day-pills', v === 'mywork' || v === 'board');
    show('telemetry', v === 'mywork');
    if (v !== 'team') { this.weekStrip(); }
    if (v === 'mywork' || v === 'board') this.dayPills();
    if (v === 'mywork') this.telemetry();

    if (v === 'mywork') { this.panels(); }
    else if (GF.views && GF.views[v]) { GF.$('panels').innerHTML = GF.views[v](); }
    else { this.panels(); }
  },

  header() {
    const u = GF.PEOPLE[GF.state.user];
    GF.$('lang-en').classList.toggle('on', GF.state.lang === 'en');
    GF.$('lang-mk').classList.toggle('on', GF.state.lang === 'mk');
    GF.$('search-input').placeholder = GF.t('search');
    GF.$('voice-btn-label').textContent = GF.t('voice_task');
    const nl = GF.$('newtask-label'); if (nl) nl.textContent = GF.t('new_task_btn');
    // Gate the header New-task button on the real create permission. (Was
    // guarded by a never-defined `window.APP`, so it never ran — inert dead code.)
    const nb = GF.$('newtask-btn'); if (nb) nb.style.display = GF.can('create') ? '' : 'none';
    GF.$('header-avatar').outerHTML = `<div id="header-avatar">${GF.avatar(GF.state.user, 38, true)}</div>`;
  },

  sidebar() {
    const nav = [
      ['mywork', 'my_week', 'check'], ['board', 'board', 'grid'], ['timeline', 'timeline', 'timeline'],
      ['coord', 'coordination', 'at', 3], ['dash', 'dashboard', 'trend'], ['team', 'team', 'user'],
    ];
    GF.$('nav').innerHTML = nav.map(([id, key, ic, badge]) => `
      <div class="nav-item ${id === GF.state.view ? 'active' : ''}" onclick="GF.setView('${id}')">
        ${GF.icon(ic)}<span>${GF.t(key)}</span>${badge ? `<span class="nav-badge">${badge}</span>` : ''}
      </div>`).join('');

    GF.$('side-label').textContent = GF.t('departments');
    const counts = {};
    GF.weekTasks(GF.state.selWeek).forEach(t => { counts[t.dept] = (counts[t.dept] || 0) + 1; });
    GF.$('dept-list').innerHTML = GF.DEPTS.map(d => `
      <div class="dept-row ${GF.state.deptFilter === d.id ? 'active' : ''}" onclick="GF.filterDept('${d.id}')">
        <span class="dept-dot" style="background:${d.color}"></span>${GF.esc(GF.depName(d.id))}
        ${counts[d.id] ? `<span class="dept-count">${counts[d.id]}</span>` : ''}
      </div>`).join('');

    const u = GF.PEOPLE[GF.state.user] || { name: '—', roleLabel: '' };
    GF.$('user-card').innerHTML = `${GF.avatar(GF.state.user, 34)}
      <div style="min-width:0"><div class="nm">${GF.esc(u.name)}</div><div class="rl">${GF.esc(u.roleLabel)}</div></div>`;
  },

  weekStrip() {
    const w = GF.calendar.weeks[GF.state.selWeek];
    const isNow = GF.state.selWeek === GF.calendar.todayId;
    const active = [...new Set(GF.weekTasks(GF.state.selWeek).flatMap(t => [t.owner, ...(t.helpers || [])]))]
      .filter(id => GF.PEOPLE[id]).slice(0, 5);
    GF.$('week-strip').innerHTML = `
      <div class="weeknav">
        <button class="icon-btn btn-sm" style="width:34px;height:34px" onclick="GF.selectWeek(${GF.state.selWeek - 1})">${GF.icon('chevL')}</button>
        <button class="icon-btn btn-sm" style="width:34px;height:34px" onclick="GF.selectWeek(${GF.state.selWeek + 1})">${GF.icon('chevR')}</button>
      </div>
      <div><div class="week-title">${GF.t('this_week') !== 'This Week' && isNow ? GF.t('this_week') : 'Week ' + w.weekNum}</div></div>
      <div class="week-dates">${w.label}, ${w.year}</div>
      ${isNow ? `<span class="badge-now">${GF.t('this_week_badge')}</span>` : ''}
      <div class="spacer"></div>
      ${GF.avatars(active, 30)}`;
  },

  dayPills() {
    const wt = GF.weekTasks(GF.state.selWeek);
    const counts = { All: wt.length };
    GF.DAYS.forEach(d => counts[d] = wt.filter(t => (t.days || []).includes(d)).length);
    const days = ['All', ...GF.DAYS.slice(0, 5)];
    GF.$('day-pills').innerHTML = days.map(d => `
      <button class="day-pill ${GF.state.selDay === d ? 'active' : ''}" onclick="GF.selectDay('${d}')">
        ${d === 'All' ? GF.t('all') : GF.dayLabel(d)}<span class="count">${counts[d] || 0}</span>
      </button>`).join('');
  },

  telemetry() {
    const all = GF.weekTasks(GF.state.selWeek);
    const n = all.length;
    const by = (s) => all.filter(t => t.status === s).length;
    const done = by('done'), rate = n ? Math.round(done / n * 100) : 0;
    const dayCount = {}; GF.DAYS.forEach(d => dayCount[d] = all.filter(t => (t.days || []).includes(d)).length);
    const busiest = Object.entries(dayCount).sort((a, b) => b[1] - a[1])[0];
    const stat = (v, l, c) => `<div class="tele-stat"><span class="v" style="color:${c}">${v}</span><span class="l">${l}</span></div>`;
    GF.$('telemetry').className = 'telemetry' + (GF.state.teleOpen ? ' open' : '');
    GF.$('telemetry').innerHTML = `
      <div class="tele-bar" onclick="GF.state.teleOpen=!GF.state.teleOpen;GF.render.telemetry()">
        ${stat(rate + '%', GF.t('completion'), 'var(--green)')}
        ${stat(n, GF.t('total'), 'var(--ink)')}
        ${stat(by('working'), GF.t('working'), 'var(--orange)')}
        ${stat(by('stuck'), GF.t('stuck'), 'var(--red)')}
        ${stat(by('postponed'), GF.t('postponed'), 'var(--amber)')}
        ${GF.icon('chevD', 'icon tele-chev')}
      </div>
      <div class="tele-detail">
        <div class="track" style="height:9px"><span style="width:${rate}%;background:var(--green)"></span></div>
        <div class="tele-grid">
          <div class="tele-card"><div class="v" style="color:var(--green)">${done}</div><div class="l">${GF.statusLabel('done')}</div></div>
          <div class="tele-card"><div class="v" style="color:var(--orange)">${by('working')}</div><div class="l">${GF.statusLabel('working')}</div></div>
          <div class="tele-card"><div class="v" style="color:var(--blue)">${by('review')}</div><div class="l">${GF.statusLabel('review')}</div></div>
          <div class="tele-card"><div class="v" style="color:var(--red)">${by('stuck')}</div><div class="l">${GF.statusLabel('stuck')}</div></div>
          <div class="tele-card"><div class="v" style="color:var(--violet)">${busiest ? GF.dayLabel(busiest[0]) : '—'}</div><div class="l">${GF.t('busiest')}</div></div>
        </div>
      </div>`;
  },

  panels() {
    const cur = GF.visibleTasks(GF.state.selWeek);
    const nextId = GF.state.selWeek + 1;
    const nxt = GF.weekTasks(nextId);
    // Tags filter: every tag on this week's tasks, filtered client-side.
    const allTags = [...new Set(GF.weekTasks(GF.state.selWeek).flatMap(t => t.tags || []))].sort();
    const tagFilter = (allTags.length || GF.state.tagFilter) ? `
      <select id="tag-filter" class="tag-filter" onchange="GF.setTagFilter(this.value)">
        <option value="">${GF.t('all_tags')}</option>
        ${allTags.map(tg => `<option value="${GF.esc(tg)}" ${GF.state.tagFilter === tg ? 'selected' : ''}>#${GF.esc(tg)}</option>`).join('')}
      </select>` : '';
    GF.$('panels').innerHTML = `
      <div class="panel">
        <div class="panel-head">
          <span class="ttl">${GF.state.selWeek === GF.calendar.todayId ? GF.t('this_week') : 'Week ' + GF.calendar.weeks[GF.state.selWeek].weekNum}</span>
          <span class="cnt">${cur.length}</span>
          <div class="spacer"></div>
          ${tagFilter}
          <button class="btn btn-sm" onclick="GF.export.open('report')">${GF.icon('forward','icon')}${GF.t('report')}</button>
          <button class="btn btn-sm" onclick="GF.ai.summary('report')">${GF.icon('sparkle','icon','var(--orange)')}${GF.t('ai_summary')}</button>
          <button class="btn btn-sm" onclick="GF.rollover()">${GF.icon('forward','icon')}${GF.t('rollover')}</button>
        </div>
        <div class="panel-body">
          ${cur.length ? cur.map(t => this.card(t)).join('') : `<div class="add-row" style="justify-content:center;cursor:default">${GF.t('no_tasks')}</div>`}
        </div>
        ${GF.can('create') ? `<div class="add-row" onclick="GF.openAdd(${GF.state.selWeek})">${GF.icon('plus')}<span>${GF.t('add_task')}</span>
          <div class="spacer"></div><span title="${GF.t('voice_task')}" style="cursor:pointer;display:inline-flex" onclick="event.stopPropagation();GF.voice.openCapture(${GF.state.selWeek})">${GF.icon('mic','icon','var(--orange)')}</span></div>` : ''}
      </div>
      <div class="panel collapsed" id="next-panel">
        <div class="panel-head" onclick="GF.$('next-panel').classList.toggle('collapsed')" style="cursor:pointer">
          ${GF.icon('chevD','icon collapse-chev')}
          <span class="ttl">${GF.t('next_week')}</span><span class="cnt">${nxt.length}</span>
          <div class="spacer"></div>
          <button class="btn btn-sm" onclick="event.stopPropagation();GF.ai.summary('plan')">${GF.icon('sparkle','icon','var(--orange)')}${GF.t('ai_brief')}</button>
        </div>
        <div class="panel-body">${nxt.map(t => this.card(t)).join('') || `<div class="add-row" style="justify-content:center;cursor:default">${GF.t('no_tasks')}</div>`}</div>
        ${GF.can('create') ? `<div class="add-row" onclick="GF.openAdd(${nextId})">${GF.icon('plus')}<span>${GF.t('add_task')}</span></div>` : ''}
      </div>`;
  },

  card(t) {
    const d = GF.dep(t.dept);
    const exp = GF.state.expanded.has(t.id);
    const prog = GF.progress(t);
    const daytags = (t.days || []).map(x => `<span class="daytag">${GF.dayLabel(x)}</span>`).join('');
    const meta = [t.id].filter(Boolean);
    // v2 badges: due date (danger when overdue + not done), type chip,
    // reference code, subtask progress, logged session hours, tags.
    const overdue = t.due && t.status !== 'done' && t.due < GF.todayISO();
    const dueBadge = t.due ? `<span class="due-badge ${overdue ? 'overdue' : ''}" title="${GF.t('due_date')}">
      ${GF.icon('calendar', 'icon')}${GF.esc(t.due)}${overdue ? ' · ' + GF.t('overdue') : ''}</span>` : '';
    const typeChip = (t.type && t.type !== 'other') ? `<span class="type-chip t-${GF.esc(t.type)}">${GF.esc(GF.taskTypeLabel(t.type))}</span>` : '';
    const refCode = t.ref ? `<span class="ref-code">${GF.esc(t.ref)}</span>` : '';
    const subProg = t.subCount > 0 ? `<span class="sub-prog" title="${GF.t('subtasks')}">${GF.icon('check', 'icon')}${t.subDone || 0}/${t.subCount}</span>` : '';
    const sessHours = t.sessionHours > 0 ? `<span class="sess-hours" title="${GF.t('log_work')}">${GF.icon('clock', 'icon')}${t.sessionHours}h</span>` : '';
    const tagChips = (t.tags || []).map(tg => `<span class="tag-chip">#${GF.esc(tg)}</span>`).join('');
    const head = `
      <div class="card-head" onclick="GF.toggleExpand('${t.id}')">
        <button class="check ${t.status === 'done' ? 'done' : ''}" onclick="event.stopPropagation();GF.toggleDone('${t.id}')">
          ${t.status === 'done' ? GF.icon('check', 'icon', '#fff') : ''}</button>
        <div style="flex:1;min-width:0">
          <div class="card-title">${GF.esc(t.title)}</div>
          <div class="card-meta"><span class="dn" style="color:${d.color}">${GF.esc(GF.depName(t.dept))}</span>
            ${meta.map(m => `<span>·</span><span>${GF.esc(m)}</span>`).join('')}
            ${refCode}${typeChip}${dueBadge}${subProg}${sessHours}${tagChips}</div>
        </div>
        <div class="daytags">${daytags}</div>
        ${GF.avatars([t.owner, ...(t.helpers || [])], 26)}
        <span class="pill s-${t.status}" onclick="event.stopPropagation();GF.cycleStatus('${t.id}')"><span class="dot" style="background:currentColor;opacity:.7"></span>${GF.statusLabel(t.status)}</span>
        <span class="prtag ${t.pr}">${GF.prLabel(t.pr)}</span>
        ${GF.icon('chevD', 'icon chev-card')}
      </div>`;
    if (!exp) return `<div class="card s-${t.status}">${head}</div>`;

    const noteId = 'note-' + t.id;
    const notes = (t.notes || []).map(n => `<div class="note"><span class="nd">${GF.dayLabel(n.d)}</span><span>${GF.esc(n.n)}</span></div>`).join('');
    const toDept = GF.HANDOFF[t.dept];
    const handoff = toDept ? `
      <div class="sec-label">${GF.icon('arrowR','icon')}${GF.t('handoff')}</div>
      <div class="handoff">
        <span class="hbadge"><span class="chip-dept">${GF.icon(d.icon,'icon',d.color)}</span>${GF.esc(GF.depName(t.dept))}</span>
        ${GF.icon('arrowR','icon','var(--ink-3)')}
        <span class="hbadge"><span class="chip-dept">${GF.icon(GF.dep(toDept).icon,'icon',GF.dep(toDept).color)}</span>${GF.esc(GF.depName(toDept))}</span>
      </div>` : '';

    const body = `
      <div class="card-body">
        ${t.status === 'stuck' && t.blocker ? `<div class="blocker">${GF.icon('flag')}<div><div class="bt">${GF.t('blocker')}: ${GF.esc(t.blocker)}</div></div></div>` : ''}
        ${t.desc ? `<div class="card-desc">${GF.esc(t.desc)}</div>` : ''}
        <div class="sec-label">${GF.icon('chat','icon')}${GF.t('notes')}</div>
        <div class="notes">${notes || ''}</div>
        <div class="note-input">
          <input id="${noteId}" placeholder="${GF.t('add_note')}" onkeydown="if(event.key==='Enter')GF.addNote('${t.id}')">
          <button class="mini-btn" id="mic-${noteId}" title="${GF.t('dictate')}" onclick="GF.voice.dictate('${noteId}')">${GF.icon('mic')}</button>
          <button class="mini-btn ai" title="${GF.t('paraphrase')}" onclick="GF.ai.paraphraseInput('${noteId}')">${GF.icon('sparkle')}</button>
          <button class="mini-btn" style="color:var(--blue)" onclick="GF.addNote('${t.id}')">${GF.icon('plus')}</button>
        </div>
        ${handoff}
        <div class="card-actions">
          <button class="btn btn-sm" onclick="GF.WWF&&GF.WWF.openWorklog&&GF.WWF.openWorklog('${t.id}')">${GF.icon('clock','icon','var(--blue)')}${GF.t('log_work')}</button>
          <button class="btn btn-sm" onclick="GF.openAdd(${JSON.stringify(t.weekId)},'${t.id}')">${GF.icon('plus','icon')}${GF.t('add_subtask')}</button>
          <button class="btn btn-sm" onclick="GF.WWF&&GF.WWF.openEdit&&GF.WWF.openEdit('${t.id}')">${GF.icon('settings','icon')}${GF.t('edit')}</button>
          <button class="btn btn-sm" onclick="GF.ai.paraphraseTask('${t.id}')">${GF.icon('sparkle','icon','var(--orange)')}${GF.t('paraphrase')}</button>
          <div class="track" style="max-width:160px;margin:0 6px"><span style="width:${prog}%;background:${d.color}"></span></div>
          <span class="mono" style="font-size:12px;color:var(--ink-2);font-weight:600">${prog}%</span>
          <div class="spacer"></div>
          <button class="btn btn-sm" onclick="GF.WWF&&GF.WWF.archiveTask&&GF.WWF.archiveTask('${t.id}')">${GF.icon('box','icon')}${GF.t('archive')}</button>
        </div>
      </div>`;
    return `<div class="card s-${t.status} expanded">${head}${body}</div>`;
  },
};
