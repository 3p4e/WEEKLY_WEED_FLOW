/* ══════════════════════════════════════════════════════════════════════
   Weekly Report + Plan — Fri→Thu rolling window with 7-day activity
   time band and AI-generated insights. All data from real timestamps.

   Split out of integrate.js (first decomposition cut). Loads after
   audit-view.js/collab.js — uses the same shared AL() helper and
   GF.WWF._registerFullPageView() defined earlier in the load order.
   ════════════════════════════════════════════════════════════════════ */
GF.WWF._report = { data: null, mode: 'report', refDate: null, loading: false, aiInsights: null, aiLoading: false, pins: null, pinsUser: null };

GF.WWF._sc = (label, value, color) =>
  `<div style="background:var(--surface-2);border:1px solid var(--line);border-radius:11px;padding:14px 16px;text-align:center">
    <div style="font-size:24px;font-weight:800;color:${color}">${value}</div>
    <div style="font-size:12px;color:var(--ink-3);margin-top:2px">${label}</div>
  </div>`;

GF.views.report = function () {
  const st = GF.WWF._report;
  // Already have a fetched report (e.g. the user navigated away and back) —
  // render it straight away instead of flashing the loading skeleton and
  // silently re-fetching every time this view is entered.
  if (st.data) {
    setTimeout(() => { if (GF.WWF.loadDocument) GF.WWF.loadDocument(); }, 0);
    return `<div id="report-view" style="padding:4px 2px 40px">${GF.WWF._reportMarkup()}</div>`;
  }
  if (!st.loading) setTimeout(() => GF.WWF.loadReport(), 0);
  return `<div id="report-view" style="padding:4px 2px 40px">
    <div style="padding:40px;text-align:center;color:var(--ink-3)">${AL('Loading report…', 'Се вчитува извештај…')}</div>
  </div>`;
};

GF.WWF.loadReport = async () => {
  const st = GF.WWF._report;
  // lseq, not `if (st.loading) return`. The early return DROPPED the user's
  // click — switch mode or week while a load is in flight and nothing
  // happened, leaving the toolbar showing one selection and the content
  // another. Superseding instead: the newest request always wins and the
  // stale response is discarded.
  const my = (st.lseq = (st.lseq || 0) + 1);
  st.loading = true;
  st.aiInsights = null;
  st.pins = null; st.pinsUser = null;
  try {
    const q = { mode: st.mode };
    if (st.refDate) q.ref_date = st.refDate;
    const data = await GF.API.weeklyReport(q);
    if (my !== st.lseq) return;                   // superseded by a newer load
    st.data = data;
    // The scheduler archives the AI weekly report / next-week plan to ai_pins
    // (function_key weekly_report / next_week_plan, +_user per person). Best
    // effort — the panel just shows an empty state until the first run lands.
    const orgKey = st.mode === 'plan' ? 'next_week_plan' : 'weekly_report';
    const [org, per] = await Promise.all([
      GF.API.pins({ function_key: orgKey, limit: 1 }).catch(() => []),
      GF.API.pins({ function_key: orgKey + '_user', limit: 10 }).catch(() => []),
    ]);
    if (my !== st.lseq) return;
    st.pins = (org && org[0]) || null;
    st.pinsUser = per || [];
    GF.WWF.renderReport();
    if (st.mode === 'report') GF.WWF._loadAiInsights();
    // Seen: clear the "new AI report" nav badge now that the user is looking at it.
    if (GF.WWF._markReportSeen) GF.WWF._markReportSeen();
  } catch (e) {
    if (my !== st.lseq) return;                   // a newer load owns the view
    const v = GF.$('report-view');
    if (v) v.innerHTML = `<div style="padding:40px;text-align:center;color:#E5484D">${AL('Failed to load report', 'Не може да се вчита извештај')}: ${GF.esc(e.message)}</div>`;
  } finally {
    if (my === st.lseq) st.loading = false;
  }
};

GF.WWF._loadAiInsights = async () => {
  const st = GF.WWF._report;
  if (!st.data) return;
  st.aiLoading = true;
  const my = (st.lseq = (st.lseq || 0) + 1);
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
             'Provide insights on productivity, risks, and recommendations for next week.',
    });
    if (my !== st.lseq) return;
    st.aiInsights = result.available ? result.output : null;
  } catch (e) {
    if (my !== st.lseq) return;
    st.aiInsights = null;
  }
  if (my !== st.lseq) return;
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

// AI-generated content is informational — not a validated GMP/QMS record
// (see docs/SCOPE.md) — so every AI pin surfaces a small disclaimer.
GF.WWF._aiDisclaimer = () =>
  `<div style="margin-top:8px;font-size:11px;color:var(--ink-3);font-style:italic">
    ${AL('AI-generated — informational draft, not an official record.', 'Генерирано од AI — информативна нацрт-верзија, не официјален запис.')}
  </div>`;

GF.WWF._renderPinsPanel = () => {
  const st = GF.WWF._report;
  const title = st.mode === 'plan' ? GF.t('ai_next_week_plan') : GF.t('ai_weekly_report');
  const accent = st.mode === 'plan' ? 'var(--orange)' : 'var(--blue)';
  const soft = st.mode === 'plan' ? 'var(--orange-soft)' : 'var(--blue-soft)';
  const line = st.mode === 'plan' ? 'rgba(224,167,62,.25)' : 'rgba(47,217,217,.25)';
  let inner;
  if (st.pins) {
    const when = GF.WWF._when(st.pins.created_at);
    const perDetails = (st.pinsUser || []).map(p => `
      <details style="margin-top:8px;border-top:1px solid ${line};padding-top:8px">
        <summary style="cursor:pointer;font-size:13px;font-weight:600;color:${accent}">${GF.esc(p.title || '')}</summary>
        <div style="padding:8px 2px;font-size:13px;line-height:1.6;color:var(--ink);white-space:pre-wrap">${GF.esc(p.body || '')}</div>
      </details>`).join('');
    inner = `<div style="padding:14px">
      <div style="font-size:13.5px;line-height:1.65;color:var(--ink);white-space:pre-wrap">${GF.esc(st.pins.body || '')}</div>
      ${perDetails}
      <div style="margin-top:10px;font-size:11px;color:var(--ink-3)">${GF.esc(when)}</div>
      ${GF.WWF._aiDisclaimer()}
    </div>`;
  } else {
    inner = `<div style="padding:16px;color:var(--ink-3);font-size:13px">${GF.t('no_ai_report')}</div>`;
  }
  return `<div style="margin:18px 0;background:${soft};border:1px solid ${line};border-radius:11px;overflow:hidden">
    <div style="padding:12px 14px;border-bottom:1px solid ${line};font-weight:700;font-size:14px;color:${accent}">
      ${GF.icon('trend')} ${title}
    </div>${inner}</div>`;
};

GF.WWF.switchReportMode = (mode) => {
  GF.WWF._report.mode = mode;
  GF.WWF.loadReport();
};

// Pick any week directly (not just ±1 from here): the backend snaps the chosen
// date to its Fri→Thu window, so a report/plan can be compiled or drafted for
// any past or future week ahead of the scheduled submission day.
GF.WWF.jumpReportWeek = (dateStr) => {
  if (!dateStr) return;
  GF.WWF._report.refDate = dateStr;
  GF.WWF.loadReport();
};

// The reference week the backend snaps to. In PLAN mode the returned
// period.start is already shifted +7 (reports.py adds a week for plans), so
// navigating/anchoring from period.start would move TWO weeks per click and the
// date picker would show the wrong week. Undo that +7 to recover the reference.
GF.WWF._refWeekStart = () => {
  const st = GF.WWF._report;
  if (!st.data || !st.data.period || !st.data.period.start) return '';
  if (st.mode !== 'plan') return st.data.period.start;
  const r = new Date(st.data.period.start);
  r.setDate(r.getDate() - 7);
  return GF.localDateStr(r);
};

GF.WWF.shiftReportWeek = (delta) => {
  const st = GF.WWF._report;
  if (delta === 0) { st.refDate = null; }
  else {
    // Anchor on the REFERENCE week (refDate if set, else derived from the data
    // with the plan shift undone) — never on the raw, possibly-shifted
    // period.start.
    const base = st.refDate || GF.WWF._refWeekStart();
    const ref = base ? new Date(base) : new Date();
    ref.setDate(ref.getDate() + delta * 7);
    // localDateStr (local getters) not toISOString (UTC): a positive-offset
    // facility would otherwise shift the ref date back a day and select the
    // wrong Fri→Thu window in _fri_thu().
    st.refDate = GF.localDateStr(ref);
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
      <div style="display:flex;flex-direction:column;gap:1px;background:var(--surface-3);border-radius:4px;padding:2px;overflow:hidden">`;

    for (let h = 0; h < 24; h++) {
      const count = day.hours[h];
      let color;
      if (isWe) color = '#E5484D';
      else if (h >= 8 && h < 17) color = '#2BE8A0';
      else color = '#E0A73E';
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
    <span><span style="display:inline-block;width:10px;height:10px;background:#2BE8A0;border-radius:2px;margin-right:4px;vertical-align:middle"></span>${AL('Regular (8–17)', 'Редовно (8–17)')}</span>
    <span><span style="display:inline-block;width:10px;height:10px;background:#E0A73E;border-radius:2px;margin-right:4px;vertical-align:middle"></span>${AL('Overtime', 'Прекувремено')}</span>
    <span><span style="display:inline-block;width:10px;height:10px;background:#E5484D;border-radius:2px;margin-right:4px;vertical-align:middle"></span>${AL('Weekend', 'Викенд')}</span>
  </div></div>`;
  return html;
};

// Pure markup builder — no DOM access — so GF.views.report can render an
// already-fetched report directly (H12) without going through renderReport's
// getElementById + innerHTML side effect.
GF.WWF._reportMarkup = () => {
  const d = GF.WWF._report.data; if (!d) return '';
  const isR = d.mode === 'report';
  const s = d.summary;

  const toolbar = `
    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:6px 4px 18px">
      <h2 style="margin:0;font-size:19px;font-weight:800;color:var(--ink)">
        ${isR ? AL('Weekly Report', 'Неделен извештај') : AL('Weekly Plan', 'Неделен план')}
      </h2>
      <div style="flex:1"></div>
      <div style="display:flex;gap:4px">
        <button class="btn btn-sm" onclick="GF.WWF.switchReportMode('report')" style="${isR ? 'background:var(--blue);color:#03130C' : ''}">${AL('Report', 'Извештај')}</button>
        <button class="btn btn-sm" onclick="GF.WWF.switchReportMode('plan')" style="${!isR ? 'background:var(--blue);color:#03130C' : ''}">${AL('Plan', 'План')}</button>
      </div>
      <div style="display:flex;gap:4px;align-items:center">
        <button class="btn btn-sm" onclick="GF.WWF.shiftReportWeek(-1)" title="${AL('Previous week', 'Претходна недела')}">◀</button>
        <button class="btn btn-sm" onclick="GF.WWF.shiftReportWeek(0)" title="${AL('Current week', 'Тековна недела')}">${AL('Today', 'Денес')}</button>
        <button class="btn btn-sm" onclick="GF.WWF.shiftReportWeek(1)" title="${AL('Next week', 'Следна недела')}">▶</button>
        <input type="date" value="${GF.WWF._refWeekStart()}" title="${AL('Jump to any week', 'Скокни на било која недела')}"
          onchange="GF.WWF.jumpReportWeek(this.value)"
          style="font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:7px;background:var(--surface);color:var(--ink)">
      </div>
      <button class="btn btn-sm" onclick="GF.export.open('${isR ? 'report' : 'plan'}')"
        title="${AL('Export raw task data as CSV / JSON', 'Извези сурови податоци како CSV / JSON')}">
        ${GF.icon('forward','icon')}${AL('Export CSV / JSON', 'Извези CSV / JSON')}</button>
    </div>`;

  const period = `<div style="font-size:14px;font-weight:600;color:var(--ink-2);margin:0 4px 16px">${GF.icon('calendar')} ${GF.esc(d.period.label)}</div>`;

  const cards = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:18px">
      ${GF.WWF._sc(AL('Total', 'Вкупно'), s.total, 'var(--blue)')}
      ${GF.WWF._sc(AL('Completed', 'Завршени'), s.completed, 'var(--primary)')}
      ${GF.WWF._sc(AL('In Progress', 'Во тек'), s.in_progress, 'var(--orange)')}
      ${GF.WWF._sc(AL('Stuck', 'Блокирани'), s.stuck, '#E5484D')}
      ${GF.WWF._sc(AL('Pending', 'Чекаат'), s.pending, '#5A6B82')}
      ${s.review ? GF.WWF._sc(AL('In Review', 'На преглед'), s.review, '#7A5BE0') : ''}
      ${s.postponed ? GF.WWF._sc(AL('Postponed', 'Одложени'), s.postponed, '#F6A609') : ''}
    </div>`;

  const band = isR ? GF.WWF._renderTimeBand(d.time_band) : '';

  // Hour sums were removed app-wide (owner decision) — no hours-by-person
  // table anymore; the activity band above still shows WHEN work happened.
  const hoursByPerson = '';

  // ── Overdue (due_date passed, not completed) ──
  let overdueList = '';
  if (isR && d.overdue && d.overdue.length) {
    // Local-midnight anchored on both sides (not `new Date()` vs a UTC-parsed
    // due_date): a positive-offset facility would otherwise see its "now" sit
    // ahead of the UTC-midnight due date by the timezone offset, adding an
    // extra day to every count (same idiom as GF.WWF.shiftReportWeek above).
    const today = new Date(GF.todayISO() + 'T00:00:00');
    overdueList = `<div style="margin:18px 0" id="report-overdue">
      <div style="font-weight:700;font-size:14px;color:#E5484D;margin-bottom:8px">${GF.icon('flag', 'icon', '#E5484D')} ${AL('Overdue', 'Задоцнети')} (${d.overdue.length})</div>
      ${d.overdue.map(t => {
        const daysLate = Math.max(1, Math.round((today - new Date(t.due_date + 'T00:00:00')) / 86400000));
        return `<div style="display:flex;align-items:center;gap:10px;padding:9px 12px;background:var(--surface-2);border:1px solid var(--red-soft);border-left:4px solid #E5484D;border-radius:9px;margin-bottom:5px">
          <span style="flex:1;font-size:13px;font-weight:600;color:var(--ink)">${GF.esc(t.title)}</span>
          <span style="font-size:11.5px;color:var(--ink-3);font-family:var(--mono);white-space:nowrap">${GF.esc(t.due_date)}</span>
          <span style="font-size:11px;font-weight:800;color:#E5484D;white-space:nowrap">${daysLate} ${AL(daysLate === 1 ? 'day late' : 'days late', daysLate === 1 ? 'ден доцни' : 'дена доцни')}</span>
        </div>`;
      }).join('')}
    </div>`;
  }

  // ── Task-type breakdown (one line of chips) ──
  let typeLine = '';
  if (d.task_types && Object.keys(d.task_types).length) {
    typeLine = `<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:14px 0" id="report-types">
      <span style="font-weight:700;font-size:13px;color:var(--ink)">${GF.t('task_type')}:</span>
      ${Object.entries(d.task_types).sort((a, b) => b[1] - a[1]).map(([tt, n]) =>
        `<span style="font-size:11.5px;font-weight:700;background:var(--violet-soft);color:var(--violet);padding:3px 10px;border-radius:999px">${GF.esc(GF.taskTypeLabel(tt))} · ${n}</span>`).join('')}
    </div>`;
  }


  let depts = '';
  if (d.departments.length) {
    depts = `<div style="margin:18px 0">
      <div style="font-weight:700;font-size:14px;color:var(--ink);margin-bottom:8px">${AL('Departments', 'Оддели')}</div>
      ${d.departments.map(dp => {
        const pct = dp.total ? Math.round(dp.completed / dp.total * 100) : 0;
        return `<div style="display:flex;align-items:center;gap:10px;padding:7px 10px;background:var(--surface-2);border:1px solid var(--line);border-radius:9px;margin-bottom:6px">
          <span style="font-weight:600;font-size:13px;flex:1">${GF.esc(dp.name)}</span>
          <span style="font-size:12px;color:var(--ink-3)">${dp.completed}/${dp.total} ${AL('done', 'завршени')}</span>
          <div style="width:80px;height:6px;background:var(--surface-3);border-radius:3px;overflow:hidden">
            <div style="width:${pct}%;height:100%;background:var(--primary);border-radius:3px"></div>
          </div>
        </div>`;
      }).join('')}
    </div>`;
  }

  const SC = { completed: '#2BE8A0', done: '#2BE8A0', ongoing: '#E0A73E', in_progress: '#E0A73E',
               stuck: '#E5484D', pending: '#5A6B82', review: '#7A5BE0', postponed: '#F6A609' };
  let taskList;
  if (d.tasks.length) {
    taskList = `<div style="margin:18px 0">
      <div style="font-weight:700;font-size:14px;color:var(--ink);margin-bottom:8px">${AL('Tasks', 'Задачи')} (${d.tasks.length})</div>
      ${d.tasks.map(t => {
        const col = SC[t.status] || '#5A6B82';
        return `<div style="display:flex;align-items:center;gap:10px;padding:9px 12px;background:var(--surface-2);border:1px solid var(--line);border-radius:9px;margin-bottom:5px">
          <span style="width:8px;height:8px;border-radius:50%;background:${col};flex-shrink:0"></span>
          <span style="flex:1;font-size:13px;font-weight:500;color:var(--ink)">${GF.esc(t.title)}</span>
          <span style="font-size:11px;color:var(--ink-3);white-space:nowrap">${GF.esc(t.department || '')}</span>
          <span style="font-size:11px;font-weight:700;color:${col};padding:2px 8px;background:${col}1A;border-radius:6px">${GF.esc(GF.statusLabel ? GF.statusLabel(t.status) : t.status)}</span>
        </div>`;
      }).join('')}
    </div>`;
  } else {
    taskList = `<div style="padding:20px;text-align:center;color:var(--ink-3)">${AL('No tasks in this period.', 'Нема задачи за овој период.')}</div>`;
  }

  const ai = isR ? `
    <div style="margin:18px 0;background:var(--blue-soft);border:1px solid rgba(47,217,217,.25);border-radius:11px;overflow:hidden">
      <div style="padding:12px 14px;border-bottom:1px solid rgba(47,217,217,.25);font-weight:700;font-size:14px;color:var(--blue)">
        ${GF.icon('sparkle')} ${AL('AI Insights', 'AI Увиди')}
      </div>
      <div id="report-ai">${GF.WWF._renderAiBox()}</div>
    </div>` : '';

  const pinsPanel = GF.WWF._renderPinsPanel();
  // Document panel (document-view.js) renders into #report-doc after load.
  const docPanel = '<div id="report-doc"></div>';
  return toolbar + period + cards + docPanel + typeLine + band + hoursByPerson + overdueList + pinsPanel + depts + taskList + ai;
};

GF.WWF.renderReport = () => {
  const v = GF.$('report-view'); if (!v) return;
  if (!GF.WWF._report.data) return;
  v.innerHTML = GF.WWF._reportMarkup();
  if (GF.WWF.loadDocument) GF.WWF.loadDocument();
};

/* nav item for the report/plan view, above Audit Trail */
GF.WWF._registerFullPageView({
  key: 'report', icon: 'trend', label: () => AL('Report', 'Извештај'),
  // Management group of the rail (mockup nav.js) — audit/intake/import stay System.
  insertBefore: 'coord', badge: () => GF.WWF._hasNewReportPin,
});

/* ── Minimal in-app "new AI report" indicator (no email/push/SMTP) ──────
   Compares the latest weekly_report pin's created_at against a localStorage
   marker. First-ever load just seeds the marker so a fresh browser never
   shows a false-positive badge for pre-existing history. */
GF.WWF._checkNewReportPin = async () => {
  const SEEN_KEY = 'wwf_last_seen_pin_ts';
  try {
    const [latest] = await GF.API.pins({ function_key: 'weekly_report', limit: 1 });
    if (!latest) return;
    const seen = localStorage.getItem(SEEN_KEY);
    if (seen === null) { localStorage.setItem(SEEN_KEY, latest.created_at); return; }
    GF.WWF._hasNewReportPin = new Date(latest.created_at) > new Date(seen);
    GF.render.sidebar();
  } catch (e) { /* best effort — never blocks the rest of the UI */ }
};

GF.WWF._markReportSeen = () => {
  localStorage.setItem('wwf_last_seen_pin_ts', new Date().toISOString());
  GF.WWF._hasNewReportPin = false;
};

setTimeout(() => GF.WWF._checkNewReportPin(), 0);
