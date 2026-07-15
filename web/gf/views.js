/* views.js — Board, Timeline, Coordination, Dashboard, Team views. Global: GF.views */
window.GF = window.GF || {};

GF.viewHead = (titleKey, subKey, right = '') => `
  <div class="view-head">
    <div><div class="view-title">${GF.t(titleKey)}</div>
      <div class="view-sub">${GF.t(subKey)}</div></div>
    <div class="spacer"></div>${right}
  </div>`;

GF.views = {
  /* ── Board: horizontal day swimlanes ───────────────────────
     One full-width lane per weekday (Mon→Fri); inside each lane the day's
     tasks flow chronologically (by due date, then insertion order) into a
     responsive grid — NOT grouped by completion state. Tasks not pinned to a
     weekday collapse into an "Anytime" lane. A small status chip on each card
     still surfaces progress at a glance without organising the board by it. */
  board() {
    const tasks = GF.scopedTasks(GF.state.selWeek);
    const days = GF.DAYS.slice(0, 5);                       // Mon–Fri
    // Chronological within a lane: earliest due first, undated keep their
    // natural (creation) order via a stable sort.
    const due = t => (t.due ? Date.parse(t.due) : Infinity);
    const chrono = (a, b) => due(a) - due(b);
    const dayColor = { Mon:'var(--green)', Tue:'var(--blue)', Wed:'var(--orange)', Thu:'var(--violet)', Fri:'var(--teal)' };

    const lanes = days.map(day => ({
      label: GF.dayLabel(day),
      color: dayColor[day] || 'var(--primary)',
      today: day === GF.todayDay,
      items: tasks.filter(t => (t.days || []).includes(day)).slice().sort(chrono),
    }));
    const anytime = tasks.filter(t => !(t.days || []).some(d => days.includes(d))).slice().sort(chrono);
    if (anytime.length) lanes.push({ label: AL('Anytime', 'Во секое време'), color: 'var(--ink-3)', today: false, items: anytime });

    const card = t => {
      const d = GF.dep(t.dept);
      return `<div class="kcard" onclick="GF.state.expanded.add('${t.id}');GF.setView('mywork')">
        <div class="kcard-top">
          <span class="kcard-dept" style="color:${d.color}" title="${GF.esc(GF.depName(t.dept))}">${GF.esc(GF.depAbbr(t.dept))}</span>
          <span class="kstatus pill s-${t.status}" title="${GF.esc(GF.statusLabel(t.status))}"><span class="dot" style="background:currentColor;opacity:.75"></span>${GF.statusLabel(t.status)}</span>
        </div>
        <div class="kcard-title" title="${GF.esc(t.title)}">${GF.esc(t.title)}</div>
        <div class="kcard-foot">
          ${GF.avatars([t.owner, ...(t.helpers||[])], 22)}
          <div class="spacer"></div>
          <span class="prtag ${t.pr}">${GF.prLabel(t.pr)}</span>
        </div></div>`;
    };

    const body = lanes.map(l => `
      <div class="kcol${l.items.length ? '' : ' empty'}${l.today ? ' today' : ''}">
        <div class="kcol-head"><span class="dot" style="background:${l.color}"></span>${l.label}
          <span class="kcount">${l.items.length}</span></div>
        <div class="kcol-body">
          ${l.items.map(card).join('') || `<div class="kempty">—</div>`}
        </div></div>`).join('');

    const addBtn = GF.can('create')
      ? `<button class="btn btn-orange btn-sm" onclick="GF.openAdd(${GF.state.selWeek})">${GF.icon('plus','icon','#fff')}${GF.t('new_task_btn')}</button>` : '';
    return GF.viewHead('board','board_sub', addBtn)
      + `<div class="kboard">${body}</div>`;
  },

  /* ── Timeline: day columns across the week ─────────────── */
  timeline() {
    const tasks = GF.scopedTasks(GF.state.selWeek);
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
    const tasks = GF.scopedTasks(GF.state.selWeek);
    const rows = tasks.filter(t => GF.HANDOFF[t.dept]).map(t => {
      const from = GF.dep(t.dept), toId = GF.HANDOFF[t.dept], to = GF.dep(toId);
      const ready = t.status === 'done';
      return `<div class="coord-row ${ready?'ready':''}">
        <div class="coord-task">
          <div class="coord-title">${GF.esc(t.title)}</div>
          <div class="coord-id">${GF.esc(t.id)}</div>
        </div>
        <div class="coord-flow">
          <span class="hbadge" title="${GF.esc(GF.depName(t.dept))}"><span class="chip-dept">${GF.icon(from.icon,'icon',from.color)}</span>${GF.esc(GF.depAbbr(t.dept))}</span>
          ${GF.icon('arrowR','icon','var(--ink-3)')}
          <span class="hbadge" title="${GF.esc(GF.depName(toId))}"><span class="chip-dept">${GF.icon(to.icon,'icon',to.color)}</span>${GF.esc(GF.depAbbr(toId))}</span>
        </div>
        <div class="coord-status">
          ${ready ? `<span class="coord-tag ok">${GF.icon('check','icon','#fff')}${AL('Ready','Подготвено')}</span>`
            : `<span class="coord-tag prog">${GF.icon('clock','icon')}${GF.statusLabel(t.status)}</span>`}
        </div>
      </div>`;
    }).join('');
    return GF.viewHead('coordination','coord_sub')
      + `<div class="coord-list">${rows || `<div class="kempty" style="padding:40px;text-align:center">—</div>`}</div>`;
  },

  /* ── Dashboard: production overview ────────────────────── */
  dash() {
    const all = GF.scopedTasks(GF.state.selWeek);
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
      return `<div class="dash-bar-row"><span class="dbl" style="color:${d.color};font-weight:700">${GF.esc(GF.depName(d.id))}</span>
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
        <div class="dash-card"><div class="dash-card-ttl">${GF.t('completion')} · ${GF.t('total')}</div>
          ${(() => { const ang = Math.round(rate * 1.8); return `
          <div class="mw-gauge" title="${GF.t('completion')}: ${rate}%">
            <div class="mw-gauge__arc" style="background:conic-gradient(from 270deg, var(--green) 0deg ${ang}deg, var(--surface-3) ${ang}deg 180deg, transparent 180deg 360deg)"></div>
            <div class="mw-gauge__needle" style="transform:translateX(-50%) rotate(${ang - 90}deg)"></div>
            <div class="mw-gauge__val">${rate}%</div>
          </div>`; })()}
          ${statRows}</div>
        <div class="dash-card"><div class="dash-card-ttl">${GF.t('departments')}</div>${deptRows||'<div class="kempty">—</div>'}</div>
        <div class="dash-card"><div class="dash-card-ttl">${GF.t('responsible')}</div>${loadRows||'<div class="kempty">—</div>'}</div>
        <div class="dash-card"><div class="dash-card-ttl">${GF.t('blocker')} · ${blockers.length}</div>
          ${blockers.map(t=>`<div class="dash-blk">${GF.icon('flag','icon','var(--red)')}<div><div class="dbk-t">${GF.esc(t.title)}</div><div class="dbk-s">${GF.esc(t.blocker||'')}</div></div></div>`).join('')||'<div class="kempty">None 🎉</div>'}</div>
      </div>`;
  },

  /* ── Executive Overview: exec-only, cross-department, one screen ──────
     Owner / CEO / COO only. Managers keep every task capability; executives
     additionally get this read: north-star KPIs (10-second rule), a department
     matrix they can toggle visibility on, the batch-flow / dependency pipeline
     (where the baton is and where it's stuck), a "needs attention" risk zone,
     and an on-demand AI brief. Everything respects the exec's hidden-department
     choices and the selected week. */
  exec() {
    const todayStr = GF.localDateStr(new Date());
    const allWeek = GF.weekTasks(GF.state.selWeek);              // every department
    const shown = allWeek.filter(t => GF.execDeptShown(t.dept)); // visible only → KPIs
    const isDone = t => t.status === 'done';
    const n = shown.length;
    const by = s => shown.filter(t => t.status === s).length;
    const done = by('done'), rate = n ? Math.round(done / n * 100) : 0;
    const blocked = shown.filter(t => t.status === 'stuck');
    const atRisk = shown.filter(t => t.due && t.due < todayStr && !isDone(t));
    const hours = shown.reduce((a, t) => a + (+t.sessionHours || 0), 0);
    const people = new Set(); shown.forEach(t => { people.add(t.owner); (t.helpers || []).forEach(h => people.add(h)); });
    const activeCount = [...people].filter(id => GF.PEOPLE[id]).length;

    // North-star KPI tiles
    const kpi = (v, l, c, sub) => `<div class="ekpi"><div class="ekpi-v" style="color:${c}">${v}</div>
      <div class="ekpi-l">${l}</div>${sub != null ? `<div class="ekpi-sub">${sub}</div>` : ''}</div>`;
    const kpis = `<div class="exec-kpis">
      ${kpi(rate + '%', AL('Completion', 'Завршеност'), 'var(--green)', done + '/' + n)}
      ${kpi(by('working'), AL('In progress', 'Во тек'), 'var(--orange)', '')}
      ${kpi(by('review'), AL('In review', 'На преглед'), 'var(--blue)', '')}
      ${kpi(blocked.length, AL('Blocked', 'Блокирани'), 'var(--red)', '')}
      ${kpi(atRisk.length, AL('Overdue', 'Задоцнети'), 'var(--amber)', '')}
      ${kpi(Math.round(hours) + 'h', AL('Hours logged', 'Часови'), 'var(--violet)', activeCount + ' ' + AL('active', 'активни'))}
    </div>`;

    // Department matrix with a per-department visibility toggle
    const seg = (c, col) => c ? `<span style="flex:${c};background:${col}"></span>` : '';
    const deptRow = d => {
      const dt = allWeek.filter(t => t.dept === d.id);
      const on = GF.execDeptShown(d.id);
      const dn = dt.length, dd = dt.filter(isDone).length;
      const dw = dt.filter(t => t.status === 'working').length, ds = dt.filter(t => t.status === 'stuck').length;
      const drate = dn ? Math.round(dd / dn * 100) : 0;
      return `<div class="exec-drow ${on ? '' : 'off'}">
        <button class="exec-eye" onclick="GF.toggleExecDept('${d.id}')"
          title="${on ? AL('Hide from overview', 'Сокриј од прегледот') : AL('Show in overview', 'Прикажи во прегледот')}">${GF.icon(on ? 'eye' : 'eyeOff')}</button>
        <span class="exec-dname"><span class="dept-dot" style="background:${d.color}"></span>${GF.esc(GF.depName(d.id))}</span>
        <div class="exec-dbar" title="${dd} ${AL('done', 'завршени')} · ${dw} ${AL('in progress', 'во тек')} · ${ds} ${AL('blocked', 'блокирани')}">
          ${dn ? seg(dd, 'var(--green)') + seg(dw, 'var(--orange)') + seg(ds, 'var(--red)') + seg(dn - dd - dw - ds, 'var(--surface-3)')
               : `<span style="flex:1;background:var(--surface-3)"></span>`}
        </div>
        <span class="exec-dstat">${dn ? drate + '%' : '—'}</span>
        <span class="exec-dcount">${dn}</span>
      </div>`;
    };
    const hiddenN = GF.state.execHidden.size;
    const matrix = `<div class="dash-card exec-card">
      <div class="exec-card-ttl">${GF.icon('layers', 'icon', 'var(--ink-3)')}${AL('Departments', 'Оддели')}
        ${hiddenN ? `<button class="exec-reset" onclick="GF.resetExecDepts()">${AL('Show all', 'Прикажи ги сите')} · ${hiddenN} ${AL('hidden', 'скриени')}</button>` : ''}
      </div>
      ${GF.DEPTS.map(deptRow).join('')}</div>`;

    // Dependency / batch-flow pipeline (ordered from GF.HANDOFF)
    const H = GF.HANDOFF || {};
    const tos = new Set(Object.values(H));
    let cur = Object.keys(H).find(f => !tos.has(f));
    const order = []; const seen = new Set();
    while (cur && !seen.has(cur)) { order.push(cur); seen.add(cur); cur = H[cur]; }
    const node = id => {
      const d = GF.dep(id), dt = shown.filter(t => t.dept === id);
      const ready = dt.filter(isDone).length;
      const wip = dt.filter(t => t.status === 'working' || t.status === 'review').length;
      const stuck = dt.filter(t => t.status === 'stuck').length;
      const cls = stuck ? 'bottleneck' : (ready && !wip && !stuck && dt.length ? 'ready' : '');
      const tag = stuck ? `<span class="pipe-tag stuck">${AL('bottleneck', 'тесно грло')}</span>`
        : (cls === 'ready' ? `<span class="pipe-tag ready">${AL('ready', 'готово')}</span>` : '');
      return `<div class="pipe-node ${cls}" title="${GF.esc(GF.depName(id))} — ${ready} ${AL('ready', 'готови')} · ${wip} ${AL('in progress', 'во тек')}${stuck ? ' · ' + stuck + ' ' + AL('blocked', 'блокирани') : ''}">
        <span class="pipe-dept" style="color:${d.color}">${GF.icon(d.icon, 'icon', d.color)}${GF.esc(GF.depAbbr(id))}</span>
        <div class="pipe-counts"><span class="pc done">${ready}</span><span class="pc wip">${wip}</span>${stuck ? `<span class="pc stuck">${stuck}</span>` : ''}</div>
        ${tag}</div>`;
    };
    const pipeInner = order.length
      ? order.map((id, i) => node(id) + (i < order.length - 1 ? `<span class="pipe-arrow">${GF.icon('arrowR', 'icon', 'var(--ink-3)')}</span>` : '')).join('')
      : `<div class="kempty">—</div>`;
    const pipeline = `<div class="dash-card exec-card">
      <div class="exec-card-ttl">${GF.icon('link', 'icon', 'var(--ink-3)')}${AL('Batch flow & dependencies', 'Тек на серии и зависности')}</div>
      <div class="exec-pipe">${pipeInner}</div>
      <div class="pipe-legend"><span><i class="pl done"></i>${AL('ready to hand off', 'готово за предавање')}</span>
        <span><i class="pl wip"></i>${AL('in progress', 'во тек')}</span><span><i class="pl stuck"></i>${AL('blocked', 'блокирани')}</span></div>
    </div>`;

    // Needs-attention risk zone
    const attn = [...blocked.map(t => ({ t, k: 'stuck' })),
                  ...atRisk.filter(t => t.status !== 'stuck').map(t => ({ t, k: 'overdue' }))].slice(0, 8);
    const attnRows = attn.map(({ t, k }) => {
      const d = GF.dep(t.dept);
      const tag = k === 'stuck' ? `<span class="attn-tag stuck">${AL('Blocked', 'Блокирано')}</span>`
        : `<span class="attn-tag overdue">${AL('Overdue', 'Задоцнето')}</span>`;
      const sub = t.blocker ? GF.esc(t.blocker) : (t.due ? `${AL('Due', 'Рок')} ${GF.esc(t.due)}` : '');
      return `<div class="attn-row" onclick="GF.state.expanded.add('${t.id}');GF.setView('mywork')">
        <span class="dept-dot" style="background:${d.color}"></span>
        <div class="attn-body"><div class="attn-title">${GF.esc(t.title)}</div>${sub ? `<div class="attn-sub">${sub}</div>` : ''}</div>
        ${tag}</div>`;
    }).join('');
    const risk = `<div class="dash-card exec-card">
      <div class="exec-card-ttl">${GF.icon('flag', 'icon', 'var(--red)')}${AL('Needs attention', 'Бара внимание')}
        <span class="exec-chip">${attn.length}</span></div>
      ${attnRows || `<div class="kempty" style="padding:22px 8px;text-align:center">${AL('All clear 🎉', 'Сè е чисто 🎉')}</div>`}</div>`;

    // ── Role-specific strips: every executive reads BOTH operations and
    // direction, so a CEO also sees Operations and a COO also sees Direction.
    const role = GF.curRole();
    const isExec = role === 'owner' || role === 'ceo' || role === 'coo' || role === 'admin';
    const showOps = isExec;
    const showStrategy = isExec;

    let opsStrip = '';
    if (showOps) {
      // On-time %: completed-this-week with a due date, done on/before it —
      // no-deadline completions are excluded (same rule as the backend report).
      const doneDue = shown.filter(t => isDone(t) && t.due);
      const onTime = doneDue.filter(t => !t.completed_date || t.completed_date <= t.due);
      const otPct = doneDue.length ? Math.round(onTime.length / doneDue.length * 100) + '%' : '—';
      const estSum = shown.reduce((a, t) => a + (+t.est || 0), 0);
      const util = estSum ? Math.round(hours / estSum * 100) + '%' : '—';
      const rowsHtml = GF.DEPTS.filter(d => GF.execDeptShown(d.id)).map(d => {
        const dt = allWeek.filter(t => t.dept === d.id);
        const stuckN = dt.filter(t => t.status === 'stuck').length;
        const overN = dt.filter(t => t.due && t.due < todayStr && !isDone(t)).length;
        if (!stuckN && !overN) return '';
        return `<div class="ops-row"><span class="dept-dot" style="background:${d.color}"></span>
          <span class="ops-name">${GF.esc(GF.depName(d.id))}</span>
          ${stuckN ? `<span class="ops-tag stuck">${stuckN} ${AL('blocked', 'блокирани')}</span>` : ''}
          ${overN ? `<span class="ops-tag overdue">${overN} ${AL('overdue', 'задоцнети')}</span>` : ''}</div>`;
      }).join('');
      opsStrip = `<div class="dash-card exec-card exec-strip">
        <div class="exec-card-ttl">${GF.icon('wrench', 'icon', 'var(--ink-3)')}${AL('Operations', 'Операции')}
          <span class="exec-chip">${AL('COO lens', 'COO поглед')}</span></div>
        <div class="strip-kpis">
          <div class="skpi"><span class="v" style="color:var(--green)">${otPct}</span><span class="l">${AL('On-time (with deadlines)', 'Навремено (со рокови)')}</span></div>
          <div class="skpi"><span class="v" style="color:var(--blue)">${util}</span><span class="l">${AL('Hours vs estimate', 'Часови наспроти проценка')}</span></div>
          <div class="skpi"><span class="v" style="color:var(--red)">${blocked.length}</span><span class="l">${AL('Bottlenecks', 'Тесни грла')}</span></div>
        </div>
        ${rowsHtml || `<div class="kempty" style="padding:10px 4px">${AL('No bottlenecks this week 🎉', 'Нема тесни грла оваа недела 🎉')}</div>`}
      </div>`;
    }

    let strategyStrip = '';
    if (showStrategy) {
      // 6-week completion trend from client data — all loaded weeks live in
      // GF.state.tasks, so no extra API round-trip is needed.
      const from = Math.max(0, GF.state.selWeek - 5);
      const pts = [];
      for (let i = from; i <= GF.state.selWeek; i++) {
        const wt = GF.weekTasks(i);
        pts.push({ i, label: 'W' + (GF.calendar.weeks[i] ? GF.calendar.weeks[i].weekNum : i),
                   rate: wt.length ? Math.round(wt.filter(isDone).length / wt.length * 100) : null,
                   total: wt.length });
      }
      const val = pts.filter(x => x.rate !== null);
      const W = 240, H = 52, PAD = 6;
      let spark = '';
      if (val.length >= 2) {
        const xs = (idx) => PAD + idx * ((W - 2 * PAD) / (pts.length - 1));
        const ys = (r) => H - PAD - (r / 100) * (H - 2 * PAD);
        const poly = pts.map((x, idx) => x.rate === null ? null : `${xs(idx).toFixed(1)},${ys(x.rate).toFixed(1)}`)
          .filter(Boolean).join(' ');
        const last = val[val.length - 1];
        const lastIdx = pts.indexOf(last);
        spark = `<svg viewBox="0 0 ${W} ${H}" class="spark" role="img">
          <polyline points="${poly}" fill="none" stroke="var(--green)" stroke-width="2" stroke-linejoin="round"/>
          ${pts.map((x, idx) => x.rate === null ? '' :
            `<circle cx="${xs(idx).toFixed(1)}" cy="${ys(x.rate).toFixed(1)}" r="${idx === lastIdx ? 3.5 : 2}"
              fill="var(--green)"><title>${GF.esc(x.label)}: ${x.rate}% (${x.total} ${AL('tasks', 'задачи')})</title></circle>`).join('')}
        </svg>`;
      }
      const cur = pts[pts.length - 1], prev = pts.length > 1 ? pts[pts.length - 2] : null;
      let delta = '';
      if (cur && prev && cur.rate !== null && prev.rate !== null) {
        const d = cur.rate - prev.rate;
        delta = `<span class="wow ${d >= 0 ? 'up' : 'down'}">${d >= 0 ? '▲' : '▼'} ${Math.abs(d)} ${AL('pp WoW', 'пп сп. мин. нед.')}</span>`;
      }
      const exceptions = attn.slice(0, 5).map(({ t, k }) => {
        const d = GF.dep(t.dept);
        return `<div class="attn-row" onclick="GF.state.expanded.add('${t.id}');GF.setView('mywork')">
          <span class="dept-dot" style="background:${d.color}"></span>
          <div class="attn-body"><div class="attn-title">${GF.esc(t.title)}</div></div>
          <span class="attn-tag ${k === 'stuck' ? 'stuck' : 'overdue'}">${k === 'stuck' ? AL('Blocked', 'Блокирано') : AL('Overdue', 'Задоцнето')}</span></div>`;
      }).join('');
      strategyStrip = `<div class="dash-card exec-card exec-strip">
        <div class="exec-card-ttl">${GF.icon('trend', 'icon', 'var(--ink-3)')}${AL('Direction', 'Насока')}
          <span class="exec-chip">${AL('CEO lens', 'CEO поглед')}</span></div>
        <div class="strip-kpis">
          <div class="skpi"><span class="v" style="color:var(--green)">${cur && cur.rate !== null ? cur.rate + '%' : '—'}</span>
            <span class="l">${AL('Completion this week', 'Завршеност оваа недела')} ${delta}</span></div>
          <div class="spark-wrap">${spark || `<span class="kempty">${AL('Not enough weeks yet', 'Сè уште нема доволно недели')}</span>`}
            <div class="spark-lbl">${AL('6-week completion trend', 'Тренд на завршеност — 6 недели')}</div></div>
        </div>
        ${exceptions ? `<div class="strip-sub">${AL('Exceptions only', 'Само исклучоци')}</div>${exceptions}`
                     : `<div class="kempty" style="padding:10px 4px">${AL('No exceptions 🎉', 'Нема исклучоци 🎉')}</div>`}
      </div>`;
    }

    const strips = (opsStrip || strategyStrip)
      ? `<div class="exec-strips">${opsStrip}${strategyStrip}</div>` : '';

    const briefBtn = `<button class="btn btn-sm" onclick="GF.execBrief()">${GF.icon('sparkle', 'icon')}${AL('AI brief', 'АИ резиме')}</button>`;
    return GF.viewHead('exec_overview', 'exec_sub', briefBtn)
      + kpis
      + `<div id="exec-brief" class="exec-brief" style="display:none"></div>`
      + strips
      + `<div class="exec-grid"><div class="exec-col">${matrix}${pipeline}</div><div class="exec-col">${risk}</div></div>`;
  },

  /* ── Team: people & roles management ───────────────────── */
  team() {
    // Deactivated accounts are kept in GF.PEOPLE (not deleted) so their
    // existing task cards still resolve a name/avatar, but they must not
    // reappear in the active roster list itself.
    const ids = Object.keys(GF.PEOPLE).filter(id => !GF.PEOPLE[id].inactive);
    // The Team nav item renders for everyone (render.sidebar has no per-role
    // filter); the add/edit/remove controls are the real gate — provisioning is
    // admin or a department manager only (executives see the roster read-only).
    // integrate.js defines canProvision; fall back to the perms gate if it
    // hasn't loaded yet.
    const canManage = GF.WWF && GF.WWF.canProvision ? GF.WWF.canProvision() : GF.can('team');
    const cards = ids.map(id => {
      const p = GF.PEOPLE[id];
      const isMe = id === GF.state.user;
      return `<div class="team-card ${isMe?'me':''}">
        <div class="team-top">${GF.avatar(id,46)}
          <div style="flex:1;min-width:0">
            <div class="tc-name">${GF.esc(p.name)}${isMe?` <span class="tc-you">${GF.t('you')}</span>`:''}</div>
            <div class="tc-role">${GF.esc(GF.roleLabel(p.role))}</div>
          </div></div>
        <div class="tc-dept">${p.dept
          ? `<span class="dept-dot" style="background:${GF.dep(p.dept).color}"></span>${GF.esc(GF.depName(p.dept))}`
          : `<span class="dept-dot" style="background:var(--ink-3)"></span>${GF.esc(GF.roleLabel(p.role))}`}</div>
        <div class="tc-actions">
          ${isMe?`<span class="tc-active">${GF.icon('check','icon','var(--green)')}${GF.t('active')}</span>`:''}
          <div class="spacer"></div>
          ${canManage?`<button class="icon-btn btn-sm" title="${GF.t('edit')}" onclick="GF.openUser('${id}')">${GF.icon('settings')}</button>`:''}
          ${canManage && ids.length>1?`<button class="icon-btn btn-sm" title="${GF.t('remove')}" onclick="GF.removeUser('${id}')">${GF.icon('trash')}</button>`:''}
        </div>
      </div>`;
    }).join('');
    const addBtn = canManage
      ? `<button class="btn btn-sm" onclick="GF.WWF.openDeletedUsers()">${GF.icon('box','icon')}${AL('Removed accounts','Отстранети сметки')}</button>`
        + `<button class="btn btn-orange btn-sm" onclick="GF.openUser()">${GF.icon('plus','icon','#fff')}${GF.t('add_user')}</button>`
      : `<span class="role-lock">${GF.icon('shield','icon','var(--ink-3)')}${GF.t('view_only')}</span>`;
    return GF.viewHead('team','team_sub', addBtn)
      + `<div class="team-count">${ids.length} ${GF.t('members')} · ${GF.t('your_role')}: <b>${GF.roleLabel(GF.curRole())}</b></div>`
      + `<div class="team-grid">${cards}</div>`;
  },
};

/* On-demand AI executive brief for the Executive Overview. Concise by design;
   full editable AI reports live in the Document Engine. Defensive: handles
   AI-unavailable and errors without breaking the view. */
GF.execBrief = async () => {
  const el = GF.$('exec-brief'); if (!el) return;
  el.style.display = 'block';
  el.innerHTML = `<div class="exec-brief-load">${GF.icon('sparkle', 'icon')}${AL('Generating executive brief…', 'Генерирам извршно резиме…')}</div>`;
  try {
    const r = await GF.API.ai('weekly_summary', { week: GF.state.selWeek });
    if (r && r.available === false) {
      el.innerHTML = `<div class="exec-brief-off">${AL('AI is not configured for this workspace.', 'АИ не е конфигуриран за овој простор.')}</div>`;
      return;
    }
    const text = (r && (r.output || r.summary || r.text)) || AL('No summary available.', 'Нема достапно резиме.');
    el.innerHTML = `<div class="exec-brief-head">${GF.icon('sparkle', 'icon')}<b>${AL('AI executive brief', 'АИ извршно резиме')}</b>
        <button class="exec-brief-x" title="${AL('Dismiss', 'Затвори')}" onclick="GF.$('exec-brief').style.display='none'">${GF.icon('x')}</button></div>
      <div class="exec-brief-txt">${GF.esc(text)}</div>`;
  } catch (e) {
    el.innerHTML = `<div class="exec-brief-off">${AL('Could not generate the brief', 'Не можев да генерирам резиме')}: ${GF.esc(e && e.message || '')}</div>`;
  }
};
