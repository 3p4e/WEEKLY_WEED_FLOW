/* render.js — all DOM rendering. Global: GF.render */
window.GF = window.GF || {};

GF.avatar = (id, size = 28, ring) => {
  const p = GF.PEOPLE[id] || { init: '?', bg: '#5F8575', name: '' };
  return `<div class="avatar" title="${GF.esc(p.name)}" style="width:${size}px;height:${size}px;background:${p.bg};
    font-size:${size * 0.38}px${ring ? `;box-shadow:0 0 0 2px #060F0B,0 0 0 4px ${p.bg}40` : ''}">${GF.esc(p.init)}</div>`;
};
GF.avatars = (ids, size = 26) => `<div class="avatars">${ids.map(i => GF.avatar(i, size)).join('')}</div>`;
// Explicit completion (tasks.progress, set from the worklog panel) wins over
// the old status heuristic; the heuristic remains the fallback for tasks
// nobody has scored yet (and for demo-mode tasks that have no progressPct).
GF.progress = (t) => {
  if (t.status === 'done') return 100;
  if (Number.isFinite(t.progressPct) && t.progressPct > 0) return t.progressPct;
  return { done: 100, working: 50, review: 75, stuck: 25, postponed: 10, pending: 0 }[t.status] ?? 0;
};
GF.HANDOFF = { clone:'veg', veg:'flower', flower:'prod', prod:'qc', qc:'qa', qa:'whout', irr:'prod', whin:'prod', maint:'irr' };

// The Mass Weed status pill opens an explicit picker (mockup interaction)
// instead of blind-cycling through the six states. Falls back to the cycle
// when chooser.js hasn't loaded (never happens in the shipped shell).
GF.STATUS_COLORS = { pending:'var(--ink-3)', working:'var(--orange)', review:'var(--blue)',
                     stuck:'var(--red)', postponed:'var(--amber)', done:'var(--green)' };
GF.pickStatus = (id) => {
  const t = GF.task(id); if (!t) return;
  if (!GF.can('status', t)) return GF.denyToast();
  if (!GF.choose) return GF.cycleStatus(id);
  GF.choose({
    title: GF.t('change_status'), value: t.status,
    options: GF.STATUS_ORDER.map(s => ({ v: s, label: GF.statusLabel(s), color: GF.STATUS_COLORS[s] })),
    onPick: (v) => { if (v !== t.status && GF.setStatus(id, v)) { GF.render.panels(); GF.render.telemetry(); } },
  });
};

GF.render = {
  all() {
    this.sidebar(); this.header();
    // The exec view is executive-only; if a stale gf_view lands a non-exec here
    // (e.g. a shared browser), fall back to My Week. Same bounce for the
    // department home when the user has no department (execs, QP, ADMIN).
    if (GF.state.view === 'exec' && !(GF.isExec && GF.isExec())) GF.state.view = 'mywork';
    if (GF.state.view === 'depthome' && !(GF.hasDeptHome && GF.hasDeptHome())) GF.state.view = 'mywork';
    const v = GF.state.view;
    const show = (id, on) => { const el = GF.$(id); if (el) el.style.display = on ? '' : 'none'; };
    const weekViews = v === 'mywork' || v === 'board' || v === 'timeline';
    show('week-strip', v !== 'team' && v !== 'calendar');   // calendar is month-scoped
    show('day-pills', v === 'mywork' || v === 'board');
    show('telemetry', v === 'mywork');
    if (v !== 'team' && v !== 'calendar') { this.weekStrip(); }
    if (v === 'mywork' || v === 'board') this.dayPills();
    if (v === 'mywork') this.telemetry();

    if (v === 'mywork') { this.panels(); }
    else if (GF.views && GF.views[v]) { GF.$('panels').innerHTML = GF.views[v](); }
    else { this.panels(); }
  },

  header() {
    const u = GF.PEOPLE[GF.state.user];
    GF.syncThemeBtn();
    GF.$('lang-en').classList.toggle('on', GF.state.lang === 'en');
    GF.$('lang-mk').classList.toggle('on', GF.state.lang === 'mk');
    GF.$('search-input').placeholder = GF.t('search');
    GF.$('voice-btn-label').textContent = GF.t('voice_task');
    const nl = GF.$('newtask-label'); if (nl) nl.textContent = GF.t('new_task_btn');
    // Gate the header New-task button on the real create permission. (Was
    // guarded by a never-defined `window.APP`, so it never ran — inert dead code.)
    const nb = GF.$('newtask-btn'); if (nb) nb.style.display = GF.can('create') ? '' : 'none';
    // The header avatar is YOU (the logged-in user) — make it open Settings on
    // the Account tab, like the gear beside it and the sidebar user-card. It
    // looked like a button but had no handler, so tapping it did nothing.
    const meName = (GF.PEOPLE[GF.state.user] || {}).name || '';
    GF.$('header-avatar').outerHTML = `<div id="header-avatar" onclick="GF.openSettings('account')"`
      + ` style="cursor:pointer" title="${GF.esc(meName)} — ${AL('Account & settings', 'Сметка и поставки')}">`
      + `${GF.avatar(GF.state.user, 38, true)}</div>`;
  },

  sidebar() {
    // Grouped rail per the owner's mockup (nav.js: Operations / Manager /
    // System). Items keep their existing visibility rules — groups only
    // organize, never hide. data-nav anchors let the full-page views
    // (_registerFullPageView) insert themselves into the right group.
    // Coordination badge = pending cross-department handoffs (handoff tasks
    // not yet ready) in the selected week. 0 → no badge renders.
    const coordPending = GF.scopedTasks(GF.state.selWeek)
      .filter(t => GF.HANDOFF[t.dept] && t.status !== 'done').length;
    const unreadN = (GF.WWF && GF.WWF._notif && GF.WWF._notif.unread) || 0;
    const ops = [];
    if (GF.hasDeptHome && GF.hasDeptHome()) ops.push(['depthome', 'dept_home', 'home']);
    ops.push(['mywork', 'my_week', 'check'], ['board', 'board', 'grid'],
             ['timeline', 'timeline', 'timeline'], ['calendar', 'calendar', 'calendar']);
    const mgr = [];
    if (GF.isExec && GF.isExec()) mgr.push(['exec', 'exec_overview', 'layers']);
    mgr.push(['coord', 'coordination', 'at', coordPending], ['dash', 'dashboard', 'trend'], ['team', 'team', 'user']);
    // Workload balancing is a coordination tool — managers/execs only.
    if (GF.can('team')) mgr.push(['workload', 'workload', 'clock']);
    const sys = [['inbox', 'inbox', 'bell', unreadN]];
    const item = ([id, key, ic, badge]) => `
      <div class="nav-item ${id === GF.state.view ? 'active' : ''}" data-nav="${id}" onclick="GF.setView('${id}')">
        ${GF.icon(ic)}<span>${GF.t(key)}</span>${badge ? `<span class="nav-badge">${badge}</span>` : ''}
      </div>`;
    const group = (lbl, items) => items.length
      ? `<div class="nav-group">${lbl}</div>` + items.map(item).join('') : '';
    // QMS Studio zone (unification Phase 1 — docs/UNIFICATION-ANALYSIS-2026-07.md):
    // an empty labeled group whose hidden end-marker anchors the QMS views
    // registered via _registerFullPageView({insertBefore:'qms-end'}). Only
    // rendered for roles above base USER — same gate as the views themselves —
    // so operators never see an empty group label.
    const role = (GF.API && GF.API.user || {}).role;
    const qmsGroup = role && role !== 'USER'
      ? `<div class="nav-group">${AL('QMS Studio', 'QMS Студио')}</div>
         <div data-nav="qms-end" style="display:none"></div>` : '';
    GF.$('nav').innerHTML =
      group(AL('Operations', 'Операции'), ops)
      + group(AL('Management', 'Менаџмент'), mgr)
      + qmsGroup
      + group(AL('System', 'Систем'), sys);

    GF.$('side-label').textContent = GF.t('departments');
    const counts = {};
    GF.weekTasks(GF.state.selWeek).forEach(t => { counts[t.dept] = (counts[t.dept] || 0) + 1; });
    // A dept-scoped manager's sidebar shows only departments they can actually
    // have tasks in this week: their own, plus any department that appears via
    // a multi-departmental family (delegated subtask both sides see in full).
    const scope = GF.WWF && GF.WWF.deptScope ? GF.WWF.deptScope() : null;
    const sideDepts = scope ? GF.DEPTS.filter(d => d.id === scope || counts[d.id]) : GF.DEPTS;
    GF.$('dept-list').innerHTML = sideDepts.map(d => `
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
      ${active.length ? `<div class="week-active" onclick="GF.setView('team')"`
        + ` title="${AL('People active this week — open Team', 'Активни оваа недела — отвори Тим')}">`
        + `<span class="week-active-lbl">${AL('Active this week', 'Активни оваа недела')}</span>`
        + `${GF.avatars(active, 28)}</div>` : ''}`;
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
    const tagFilter = (allTags.length || GF.state.tagFilter) ? GF.selectField('tag-filter', {
      value: GF.state.tagFilter || '', inline: true, title: GF.t('all_tags'),
      options: [{ v: '', label: GF.t('all_tags') }].concat(allTags.map(tg => ({ v: tg, label: '#' + tg }))),
      onPick: (v) => GF.setTagFilter(v),
    }) : '';
    GF.$('panels').innerHTML = `
      <div class="panel">
        <div class="panel-head">
          <span class="ttl">${GF.state.selWeek === GF.calendar.todayId ? GF.t('this_week') : 'Week ' + GF.calendar.weeks[GF.state.selWeek].weekNum}</span>
          <span class="cnt">${cur.length}</span>
          <div class="spacer"></div>
          ${tagFilter}
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
    // The subtask counter is the tree toggle: themes expand into their
    // documents (and documents into versions) as indented rows below the card.
    const treeOpen = GF.state.treeOpen && GF.state.treeOpen.has(t.id);
    // Parent progress ring (mockup .mw-ring, mini): fraction of sub-tasks
    // completed, tinted by the department colour.
    const subPct = t.subCount > 0 ? Math.round((t.subDone || 0) / t.subCount * 100) : 0;
    const subProg = t.subCount > 0 ? `<span class="sub-prog tree-toggle${treeOpen ? ' open' : ''}" title="${GF.t('subtasks')}"
      onclick="event.stopPropagation();GF.toggleTree('${t.id}')">${GF.icon(treeOpen ? 'chevD' : 'chevR', 'icon')}
      <span class="ring-mini" style="--p:${subPct};--col:${d.color}"></span>${t.subDone || 0}/${t.subCount}</span>` : '';
    // All sub-tasks done but the parent isn't: SUGGEST completion, never
    // enforce it (the parent may have work of its own left).
    const subHint = (t.subCount > 0 && t.subDone === t.subCount && t.status !== 'done' && GF.can('status', t))
      ? `<button class="subdone-hint" title="${GF.t('subtasks')}: ${t.subDone}/${t.subCount}"
           onclick="event.stopPropagation();GF.toggleDone('${t.id}')">✓ ${GF.t('mark_done')}?</button>` : '';
    const tagChips = (t.tags || []).map(tg => `<span class="tag-chip">#${GF.esc(tg)}</span>`).join('');
    const attrChips = GF.attrChips ? GF.attrChips(t) : '';
    const head = `
      <div class="card-head" onclick="GF.toggleExpand('${t.id}')">
        <button class="check ${t.status === 'done' ? 'done' : ''}" onclick="event.stopPropagation();GF.toggleDone('${t.id}')">
          ${t.status === 'done' ? GF.icon('check', 'icon', '#03130C') : ''}</button>
        <div class="card-main">
          <div class="card-title">${GF.esc(t.title)}</div>
          <div class="card-meta"><span class="dn" style="color:${d.color}" title="${GF.esc(GF.depName(t.dept))}">${GF.esc(GF.depAbbr(t.dept))}</span>
            ${meta.map(m => `<span>·</span><span>${GF.esc(m)}</span>`).join('')}
            ${refCode}${typeChip}${dueBadge}${subProg}${subHint}${attrChips}${tagChips}</div>
        </div>
        <div class="card-side">
          <div class="daytags">${daytags}</div>
          ${GF.avatars([t.owner, ...(t.helpers || [])], 26)}
          <span class="pill s-${t.status}" title="${GF.t('change_status')}" onclick="event.stopPropagation();GF.pickStatus('${t.id}')"><span class="dot" style="background:currentColor;opacity:.7"></span>${GF.statusLabel(t.status)}</span>
          <span class="prtag ${t.pr}">${GF.prLabel(t.pr)}</span>
        </div>
        ${GF.icon('chevD', 'icon chev-card')}
      </div>`;
    const tree = treeOpen ? this.treeRows(t.id, 1) : '';
    if (!exp) return `<div class="card s-${t.status}">${head}${tree}</div>`;

    const noteId = 'note-' + t.id;
    // Executive input stands out: notes written by the OWNER get the strongest
    // (gold) treatment, CEO/COO a lighter one — so directives from above are
    // never lost in the scroll of ordinary progress notes.
    const notes = (t.notes || []).map(n => {
      const p = n.by && GF.PEOPLE[n.by];
      const br = p && p.backendRole;
      const owner = br === 'OWNER';
      const exec = owner || br === 'CEO' || br === 'COO';
      const chip = exec ? `<span class="note-role-chip ${owner ? 'owner' : ''}" title="${GF.esc(p.name)}">${GF.esc(GF.roleLabel(p.role))}</span>` : '';
      return `<div class="note ${exec ? 'note-exec' : ''} ${owner ? 'note-owner' : ''}">
        <span class="nd">${GF.dayLabel(n.d)}</span><span style="flex:1">${GF.esc(n.n)}</span>${chip}</div>`;
    }).join('');
    const toDept = GF.HANDOFF[t.dept];
    const handoff = toDept ? `
      <div class="sec-label">${GF.icon('arrowR','icon')}${GF.t('handoff')}</div>
      <div class="handoff">
        <span class="hbadge" title="${GF.esc(GF.depName(t.dept))}"><span class="chip-dept">${GF.icon(d.icon,'icon',d.color)}</span>${GF.esc(GF.depAbbr(t.dept))}</span>
        ${GF.icon('arrowR','icon','var(--ink-3)')}
        <span class="hbadge" title="${GF.esc(GF.depName(toDept))}"><span class="chip-dept">${GF.icon(GF.dep(toDept).icon,'icon',GF.dep(toDept).color)}</span>${GF.esc(GF.depAbbr(toDept))}</span>
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
    return `<div class="card s-${t.status} expanded">${head}${body}${tree}</div>`;
  },

  /* ── Tree rows: a parent's children as indented compact rows (theme →
     document → version; two levels below the card). Children deliberately
     are NOT week-filtered — a theme card sits in its initiation week while
     its documents span months, so the tree always shows ALL of them, each
     with its own date range. Row click opens the worklog (sessions/notes);
     the pencil opens the normal edit modal. */
  treeRows(parentId, depth) {
    const kids = (GF.state.children && GF.state.children[parentId]) || [];
    if (!kids.length || depth > 8) return '';   // depth 8 = cycle sanity, not a UI cap
    const rows = kids.map(c => {
      const grand = ((GF.state.children && GF.state.children[c.id]) || []).length;
      const open = GF.state.treeOpen.has(c.id);
      const range = [c.week_start, c.due].filter(Boolean).join(' → ');
      const toggle = grand
        ? `<span class="tree-toggle${open ? ' open' : ''}" onclick="event.stopPropagation();GF.toggleTree('${c.id}')">${GF.icon(open ? 'chevD' : 'chevR', 'icon')}<span class="tree-count">${grand}</span></span>`
        : `<span class="tree-dot s-${c.status}"></span>`;
      return `
      <div class="tree-row s-${c.status}" onclick="event.stopPropagation();GF.WWF&&GF.WWF.openWorklog&&GF.WWF.openWorklog('${c.id}')">
        <button class="check ${c.status === 'done' ? 'done' : ''}" title="${GF.t('mark_done') || 'Done'}"
          onclick="event.stopPropagation();GF.toggleDone('${c.id}')">${c.status === 'done' ? GF.icon('check', 'icon', '#03130C') : ''}</button>
        ${toggle}
        <span class="tree-title" title="${GF.esc(c.title)}">${GF.esc(c.title)}</span>
        ${range ? `<span class="tree-range">${GF.esc(range)}</span>` : ''}
        ${(() => { const p = GF.progress(c); return p > 0 ? `<span class="tree-prog" title="${GF.t('completion')}: ${p}%">
          <span class="tp-track"><span class="tp-fill ${p >= 75 ? 'hi' : p >= 34 ? 'mid' : 'lo'}" style="width:${p}%"></span></span>
          <span class="tp-val">${p}%</span></span>` : ''; })()}
        <span class="pill s-${c.status}" title="${GF.t('change_status') || 'Change status'}"
          onclick="event.stopPropagation();GF.pickStatus('${c.id}')"><span class="dot" style="background:currentColor;opacity:.7"></span>${GF.statusLabel(c.status)}</span>
        <button class="mini-btn tree-edit" title="${GF.t('edit')}" onclick="event.stopPropagation();GF.WWF&&GF.WWF.openEdit&&GF.WWF.openEdit('${c.id}')">${GF.icon('settings')}</button>
      </div>${open ? this.treeRows(c.id, depth + 1) : ''}`;
    }).join('');
    return `<div class="tree-rows tree-d${depth}">${rows}</div>`;
  },
};
