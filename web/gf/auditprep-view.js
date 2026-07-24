/* auditprep-view.js — GMP audit-preparation readiness.
   Data: GET /reports/audit-prep (per-programme completion over tasks tagged
   MK-GMP / EU-GMP / SOP-writing, a due-date milestone timeline, and planning
   telemetry: status distribution, busiest scheduled day, outcome traceability).

   Assimilated from the SUMA/ISO17verSUMA executive dashboard's "GMP & SOP
   Preparation Tracker" + "Audit Preparation Timeline". This is a PLANNING aid
   over the existing tasks.tags facet — NOT a controlled record (the QMS /
   DocEngine zone owns audit deliverables; see docs/SCOPE.md's two-zone note).

   Same full-page-view pattern + guard as analytics/approvals (every role above
   base USER). Reuses the ana-* CSS tokens — no new stylesheet. */

(function () {
  GF.WWF._ap = { data: null, loading: false, error: null };

  GF.WWF.loadAuditPrep = async () => {
    const st = GF.WWF._ap;
    st.loading = true; st.error = null;
    try { st.data = await GF.API.auditPrep(); }
    catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'auditprep') GF.render.all();
  };

  // Localised weekday label for the "busiest day" tile.
  const DOW = { Mon: ['Mon', 'Пон'], Tue: ['Tue', 'Вто'], Wed: ['Wed', 'Сре'],
                Thu: ['Thu', 'Чет'], Fri: ['Fri', 'Пет'], Sat: ['Sat', 'Саб'], Sun: ['Sun', 'Нед'] };
  const dow = (d) => (DOW[d] ? AL(DOW[d][0], DOW[d][1]) : d);

  const fmtDate = (iso) => {
    const d = new Date(iso + 'T00:00:00');
    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`;
  };

  // Horizontal progress bar (reuses the analytics ana-hb classes).
  const bar = (frac, cls) =>
    `<div class="ana-hb"><div class="ana-hb-f${cls ? ' ' + cls : ''}" style="width:${Math.max(2, Math.round(100 * frac))}%"></div></div>`;

  const statusColor = { completed: 'var(--green,#3aa76d)', ongoing: 'var(--ch-b)',
                        review: 'var(--ch-a)', stuck: 'var(--orange)',
                        postponed: 'var(--muted)', pending: 'var(--muted)' };

  GF.views.auditprep = () => {
    const st = GF.WWF._ap;
    if (!st.data && !st.loading && !st.error) GF.WWF.loadAuditPrep();
    const head = GF.viewHead
      ? GF.viewHead('auditprep', 'auditprep_sub')
      : `<h2>${AL('Audit readiness', 'Подготвеност за ревизија')}</h2>`;

    if (st.loading || (!st.data && !st.error)) {
      return head + `<div class="mw-skel" style="height:80px;margin-bottom:10px"></div>
        <div class="mw-skel" style="height:220px"></div>`;
    }
    if (st.error) {
      return head + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadAuditPrep()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }

    const d = st.data;
    const totalAll = d.programs.reduce((s, p) => s + p.total, 0);
    const doneAll = d.programs.reduce((s, p) => s + p.completed, 0);
    const overdueAll = d.programs.reduce((s, p) => s + p.overdue, 0);
    const readiness = totalAll ? Math.round(100 * doneAll / totalAll) : null;
    const tr = d.traceability || { completed: 0, with_outcome: 0, without_outcome: 0, rate: 0 };

    const tile = (label, value, sub) => `<div class="ana-tile">
      <div class="ana-tl">${label}</div><div class="ana-tv">${value}</div>
      ${sub ? `<div class="ana-ts">${sub}</div>` : ''}</div>`;

    const kpis = `<div class="ana-tiles">
      ${tile(AL('Overall readiness', 'Вкупна подготвеност'), readiness === null ? '—' : readiness + '%',
             `${doneAll}/${totalAll} ${AL('tasks done', 'задачи завршени')}`)}
      ${tile(AL('Audit-prep tasks', 'Задачи за подготовка'), totalAll,
             overdueAll ? `<span style="color:var(--red-fg,var(--red))">${overdueAll} ${GF.t('overdue').toLowerCase()}</span>` : '')}
      ${tile(AL('Busiest day', 'Најоптоварен ден'), d.busiest_day ? dow(d.busiest_day.day) : '—',
             d.busiest_day ? `${d.busiest_day.count} ${AL('scheduled', 'закажани')}` : '')}
      ${tile(AL('Outcome traceability', 'Следливост на исход'), tr.completed ? Math.round(100 * tr.rate) + '%' : '—',
             tr.without_outcome ? `<span style="color:var(--orange)">${tr.without_outcome} ${AL('missing outcome', 'без исход')}</span>`
                                : AL('all completed logged', 'сите завршени запишани'))}
    </div>`;

    // Per-programme readiness rows.
    const progRows = d.programs.map((p) => {
      const frac = p.total ? p.completed / p.total : 0;
      const pct = Math.round(100 * frac);
      const chips = [
        p.ongoing ? `<span><i class="fs-dot" style="background:var(--ch-b)"></i>${p.ongoing} ${AL('ongoing', 'во тек')}</span>` : '',
        p.stuck ? `<span><i class="fs-dot" style="background:var(--orange)"></i>${p.stuck} ${GF.t('stuck').toLowerCase()}</span>` : '',
        p.pending ? `<span><i class="fs-dot" style="background:var(--muted)"></i>${p.pending} ${AL('pending', 'на чекање')}</span>` : '',
        p.overdue ? `<span><i class="fs-dot" style="background:var(--red)"></i>${p.overdue} ${GF.t('overdue').toLowerCase()}</span>` : '',
      ].filter(Boolean).join('');
      return `<div class="ana-row" style="align-items:flex-start">
        <div class="ana-rl" title="${GF.esc(p.program)}" style="font-weight:600">${GF.esc(p.program)}</div>
        <div style="flex:1;min-width:120px">
          ${bar(frac)}
          <div class="ana-rx" style="margin-top:4px">${chips || `<span class="ana-note">${AL('no tasks tagged', 'нема означени задачи')}</span>`}</div>
        </div>
        <div class="ana-rv" title="${p.completed}/${p.total}">${p.total ? pct + '%' : '—'}</div>
      </div>`;
    }).join('');

    // Milestone timeline (due-dated audit-prep tasks, soonest first).
    const tlRows = d.timeline.length ? d.timeline.slice(0, 40).map((t) => {
      const progChips = (t.programs || []).map((pr) =>
        `<span class="tag-chip">${GF.esc(pr)}</span>`).join(' ');
      const sc = statusColor[t.status] || 'var(--muted)';
      return `<div class="ana-row" style="cursor:pointer" onclick="GF.setView('board')" title="${AL('Open the board', 'Отвори ја таблата')}">
        <div class="ana-rl" style="min-width:92px;${t.overdue ? 'color:var(--red-fg,var(--red))' : ''}">${fmtDate(t.due_date)}</div>
        <div style="flex:1;min-width:120px">
          <div title="${GF.esc(t.title)}">${GF.esc(t.title)}</div>
          <div class="ana-rx" style="margin-top:2px">${progChips}
            <span><i class="fs-dot" style="background:${sc}"></i>${GF.esc(GF.t(t.status) || t.status)}</span>
            ${t.overdue ? `<span style="color:var(--red-fg,var(--red))">${GF.t('overdue')}</span>` : ''}
          </div>
        </div>
      </div>`;
    }).join('') : `<div class="ana-note">${AL('No dated audit-prep milestones yet. Add a due date to a tagged task to see it here.', 'Сè уште нема датумирани пресвртници. Додај рок на означена задача за да се појави тука.')}</div>`;

    return head + `
      ${kpis}
      <div class="ana-grid2">
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Readiness by programme', 'Подготвеност по програма')}</div>
          ${progRows}
          <div class="ana-note" style="margin-top:8px">${AL(
            'Programmes are tracked as task tags (MK-GMP, EU-GMP, SOP-writing). A planning aid — the QMS holds the controlled audit record.',
            'Програмите се следат како ознаки на задачи (MK-GMP, EU-GMP, SOP-writing). Помош при планирање — QMS го чува контролираниот запис.')}</div>
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Milestone timeline', 'Временска рамка на пресвртници')}</div>
          ${tlRows}
        </div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'auditprep', icon: 'shield',
    label: () => AL('Audit readiness', 'Подготвеност за ревизија'),
    insertBefore: 'analytics',   // Management group, beside analytics
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
