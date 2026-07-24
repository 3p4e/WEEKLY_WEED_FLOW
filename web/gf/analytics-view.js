/* analytics-view.js — cross-week trends for managers and executives.
   Data: GET /reports/analytics (weekly Fri→Thu buckets; deliberately
   hour-free — counts of tasks and logged sessions, never durations).

   Charts are inline SVG/HTML, CSP-clean, themed via --ch-a/--ch-b chart
   tokens (validated pair per theme — see app.css). Two-series identity is
   carried by the legend + direct hover titles, never color alone.

   Same full-page-view pattern as facility/approvals; guard = every role
   above base USER (mirrors the endpoint's 403). */

(function () {
  GF.WWF._ana = { data: null, loading: false, error: null, weeks: 8 };

  GF.WWF.loadAnalytics = async () => {
    const st = GF.WWF._ana;
    st.loading = true; st.error = null;
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      const data = await GF.API.analytics(st.weeks);
      if (my !== st.lseq) return;
      st.data = data;
    } catch (e) {
      if (my !== st.lseq) return;
      st.error = e.message;
    }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'analytics') GF.render.all();
  };

  GF.WWF.anaRange = (n) => {
    GF.WWF._ana.weeks = n;
    GF.WWF._ana.data = null;
    GF.WWF.loadAnalytics();
    GF.render.all();
  };

  const wkLbl = (iso) => {
    const d = new Date(iso + 'T00:00:00');
    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`;
  };

  // Bar with a 4px-rounded data end and a square baseline (mark spec).
  const barPath = (x, y, w, h, r = 4) => {
    if (h <= r) return `M${x} ${y + h}h${w}v${-h}h${-w}Z`;
    return `M${x} ${y + h}v${-(h - r)}q0 ${-r} ${r} ${-r}h${w - 2 * r}q${r} 0 ${r} ${r}v${h - r}Z`;
  };

  const nice = (m) => { // clean y-axis max
    if (m <= 5) return 5;
    const pow = Math.pow(10, Math.floor(Math.log10(m)));
    for (const k of [1, 2, 5, 10]) if (k * pow >= m) return k * pow;
    return 10 * pow;
  };

  /* Chart A — created vs completed per week (grouped bars, 2 series). */
  const chartFlow = (weeks) => {
    const W = 560, H = 180, padL = 30, padB = 20, padT = 12;
    const n = weeks.length;
    const maxV = nice(Math.max(1, ...weeks.map((w) => Math.max(w.created, w.completed))));
    const slot = (W - padL) / n;
    const bw = Math.min(14, (slot - 8) / 2); // ≤24px, air in the band
    const y = (v) => padT + (H - padB - padT) * (1 - v / maxV);
    const grid = [0, 0.5, 1].map((f) => {
      const gy = y(maxV * f);
      return `<line x1="${padL}" y1="${gy}" x2="${W}" y2="${gy}" class="ana-grid"/>
        <text x="${padL - 5}" y="${gy + 3}" class="ana-tick" text-anchor="end">${Math.round(maxV * f)}</text>`;
    }).join('');
    const bars = weeks.map((w, i) => {
      const x0 = padL + i * slot + (slot - 2 * bw - 2) / 2;
      const lbl = (n <= 8 || i % 2 === (n - 1) % 2)
        ? `<text x="${x0 + bw + 1}" y="${H - 6}" class="ana-tick" text-anchor="middle">${wkLbl(w.week_start)}</text>` : '';
      const cap = i === n - 1 && w.created > 0
        ? `<text x="${x0 + bw / 2}" y="${y(w.created) - 4}" class="ana-cap" text-anchor="middle">${w.created}</text>` : '';
      const cap2 = i === n - 1 && w.completed > 0
        ? `<text x="${x0 + bw + 2 + bw / 2}" y="${y(w.completed) - 4}" class="ana-cap" text-anchor="middle">${w.completed}</text>` : '';
      return `<g><title>${wkLbl(w.week_start)} · ${AL('created', 'креирани')} ${w.created} · ${AL('completed', 'завршени')} ${w.completed}</title>
        <path d="${barPath(x0, y(w.created), bw, (H - padB) - y(w.created))}" fill="var(--ch-a)"/>
        <path d="${barPath(x0 + bw + 2, y(w.completed), bw, (H - padB) - y(w.completed))}" fill="var(--ch-b)"/>
        ${cap}${cap2}${lbl}</g>`;
    }).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${AL('Created vs completed per week', 'Креирани наспроти завршени по недела')}">${grid}${bars}</svg>
      <div class="ana-legend">
        <span><i style="background:var(--ch-a)"></i>${AL('Created', 'Креирани')}</span>
        <span><i style="background:var(--ch-b)"></i>${AL('Completed', 'Завршени')}</span>
      </div>`;
  };

  /* Chart B — on-time completion % per week (single line, fixed 0–100). */
  const chartOnTime = (weeks) => {
    const W = 560, H = 140, padL = 34, padB = 20, padT = 10;
    const n = weeks.length;
    const slot = (W - padL) / n;
    const y = (v) => padT + (H - padB - padT) * (1 - v / 100);
    const pts = weeks.map((w, i) => w.completed > 0
      ? { x: padL + i * slot + slot / 2, y: y(Math.round(100 * w.on_time / w.completed)), v: Math.round(100 * w.on_time / w.completed), w } : null);
    const line = pts.filter(Boolean);
    const grid = [0, 50, 100].map((v) =>
      `<line x1="${padL}" y1="${y(v)}" x2="${W}" y2="${y(v)}" class="ana-grid"/>
       <text x="${padL - 5}" y="${y(v) + 3}" class="ana-tick" text-anchor="end">${v}%</text>`).join('');
    if (!line.length) return `<svg viewBox="0 0 ${W} ${H}">${grid}</svg>
      <div class="ana-note">${AL('No completions in this range yet.', 'Сè уште нема завршувања во овој опсег.')}</div>`;
    const path = line.map((p, i) => `${i ? 'L' : 'M'}${p.x} ${p.y}`).join('');
    const area = `M${line[0].x} ${H - padB}${line.map((p) => `L${p.x} ${p.y}`).join('')}L${line[line.length - 1].x} ${H - padB}Z`;
    const last = line[line.length - 1];
    const dots = line.map((p) =>
      `<circle cx="${p.x}" cy="${p.y}" r="4" fill="var(--ch-b)" stroke="var(--surface)" stroke-width="2">
         <title>${wkLbl(p.w.week_start)} · ${p.v}% (${p.w.on_time}/${p.w.completed})</title></circle>`).join('');
    const labels = weeks.map((w, i) => (n <= 8 || i % 2 === (n - 1) % 2)
      ? `<text x="${padL + i * slot + slot / 2}" y="${H - 6}" class="ana-tick" text-anchor="middle">${wkLbl(w.week_start)}</text>` : '').join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${AL('On-time completion rate', 'Стапка на навремено завршување')}">${grid}
      <path d="${area}" fill="var(--ch-b)" opacity="0.1"/>
      <path d="${path}" fill="none" stroke="var(--ch-b)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      ${dots}<text x="${last.x + 8}" y="${last.y + 3}" class="ana-cap">${last.v}%</text>${labels}</svg>`;
  };

  /* Horizontal HTML bar (dept / type rows). */
  const hbar = (frac) =>
    `<div class="ana-hb"><div class="ana-hb-f" style="width:${Math.max(2, Math.round(100 * frac))}%"></div></div>`;

  const deptName = (d) => (GF.state.lang === 'mk' && d.name_mk) ? d.name_mk : d.name;

  GF.views.analytics = () => {
    const st = GF.WWF._ana;
    if (!st.data && !st.loading && !st.error) GF.WWF.loadAnalytics();
    const head = GF.viewHead
      ? GF.viewHead('analytics', 'analytics_sub')
      : `<h2>${AL('Analytics', 'Аналитика')}</h2>`;
    if (st.loading || (!st.data && !st.error)) {
      return head + `<div class="mw-skel" style="height:80px;margin-bottom:10px"></div>
        <div class="mw-skel" style="height:220px"></div>`;
    }
    if (st.error) {
      return head + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadAnalytics()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const d = st.data;
    const cur = d.weeks[d.weeks.length - 1] || {};
    const doneRange = d.weeks.reduce((s, w) => s + w.completed, 0);
    const onTimeRange = d.weeks.reduce((s, w) => s + w.on_time, 0);
    const pct = doneRange ? Math.round(100 * onTimeRange / doneRange) : null;
    const openNow = d.departments.reduce((s, x) => s + x.open, 0);
    const overdueNow = d.departments.reduce((s, x) => s + x.overdue, 0);

    const tile = GF.kpiTile;

    const kpis = `<div class="ana-tiles">
      ${tile(AL('Open tasks now', 'Отворени задачи сега'), openNow,
             overdueNow ? `<span style="color:var(--red-fg,var(--red))">${overdueNow} ${GF.t('overdue').toLowerCase()}</span>` : '')}
      ${tile(AL('Completed', 'Завршени') + ` · ${d.range.weeks}${AL('w', 'н')}`, doneRange, '')}
      ${tile(AL('On time', 'Навреме'), pct === null ? '—' : pct + '%',
             AL('of completed tasks', 'од завршените задачи'))}
      ${tile(AL('Active people this week', 'Активни лица оваа недела'), cur.active_people || 0,
             `${cur.sessions || 0} ${AL('sessions', 'сесии')}`)}
    </div>`;

    const ranges = [4, 8, 12].map((n) =>
      `<button class="ntf-tab${st.weeks === n ? ' on' : ''}" onclick="GF.WWF.anaRange(${n})">${n} ${AL('weeks', 'недели')}</button>`).join('');

    const maxOpen = Math.max(1, ...d.departments.map((x) => x.open));
    const deptRows = d.departments.map((x) => `
      <div class="ana-row">
        <div class="ana-rl" title="${GF.esc(deptName(x))}">${GF.esc(deptName(x))}</div>
        ${hbar(x.open / maxOpen)}
        <div class="ana-rv">${x.open}</div>
        <div class="ana-rx">
          ${x.stuck ? `<span><i class="fs-dot" style="background:var(--orange)"></i>${x.stuck} ${GF.t('stuck').toLowerCase()}</span>` : ''}
          ${x.overdue ? `<span><i class="fs-dot" style="background:var(--red)"></i>${x.overdue} ${GF.t('overdue').toLowerCase()}</span>` : ''}
        </div>
      </div>`).join('');

    const maxType = Math.max(1, ...d.task_types.map((t) => t.count));
    const typeRows = d.task_types.map((t) => {
      const lbl = (GF.TASK_TYPE_LABELS[t.task_type] || {})[GF.state.lang === 'mk' ? 'mk' : 'en'] || t.task_type;
      return `<div class="ana-row">
        <div class="ana-rl">${GF.esc(lbl)}</div>
        ${hbar(t.count / maxType)}
        <div class="ana-rv">${t.count}</div><div class="ana-rx"></div>
      </div>`;
    }).join('');

    return head + `
      <div class="ana-head">${ranges}</div>
      ${kpis}
      <div class="ana-grid2">
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Task flow per week', 'Проток на задачи по недела')}</div>
          ${chartFlow(d.weeks)}
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('On-time completion', 'Навремено завршување')}</div>
          ${chartOnTime(d.weeks)}
          <div class="ana-note">${AL('Share of completed tasks finished on or before their due date.',
                                     'Удел на завршени задачи завршени на или пред рокот.')}</div>
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Open tasks by department', 'Отворени задачи по оддел')}</div>
          ${deptRows || `<div class="ana-note">${GF.t('no_tasks')}</div>`}
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Open tasks by type', 'Отворени задачи по тип')}</div>
          ${typeRows || `<div class="ana-note">${GF.t('no_tasks')}</div>`}
        </div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'analytics', icon: 'trend',
    label: () => AL('Analytics', 'Аналитика'),
    insertBefore: 'report',   // Management group, beside the weekly report
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
