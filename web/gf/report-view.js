/* ══════════════════════════════════════════════════════════════════════
   Weekly Report + Plan — Fri→Thu rolling window with 7-day activity
   time band and AI-generated insights. All data from real timestamps.

   Split out of integrate.js (first decomposition cut). Loads after
   audit-view.js/collab.js — uses the same shared AL() helper and
   GF.WWF._registerFullPageView() defined earlier in the load order.
   ════════════════════════════════════════════════════════════════════ */
GF.WWF._report = { data: null, mode: 'report', refDate: null, loading: false, aiInsights: null, aiLoading: false, pins: null, pinsUser: null };

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
  st.pins = null; st.pinsUser = null;
  try {
    const q = { mode: st.mode };
    if (st.refDate) q.ref_date = st.refDate;
    st.data = await GF.API.weeklyReport(q);
    // The scheduler archives the AI weekly report / next-week plan to ai_pins
    // (function_key weekly_report / next_week_plan, +_user per person). Best
    // effort — the panel just shows an empty state until the first run lands.
    const orgKey = st.mode === 'plan' ? 'next_week_plan' : 'weekly_report';
    const [org, per] = await Promise.all([
      GF.API.pins({ function_key: orgKey, limit: 1 }).catch(() => []),
      GF.API.pins({ function_key: orgKey + '_user', limit: 10 }).catch(() => []),
    ]);
    st.pins = (org && org[0]) || null;
    st.pinsUser = per || [];
    GF.WWF.renderReport();
    if (st.mode === 'report') GF.WWF._loadAiInsights();
    // Seen: clear the "new AI report" nav badge now that the user is looking at it.
    if (GF.WWF._markReportSeen) GF.WWF._markReportSeen();
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

// AI-generated content is informational — not a validated GMP/QMS record
// (see docs/SCOPE.md) — so every AI pin surfaces a small disclaimer.
GF.WWF._aiDisclaimer = () =>
  `<div style="margin-top:8px;font-size:11px;color:var(--ink-3);font-style:italic">
    ${AL('AI-generated — informational draft, not an official record.', 'Генерирано од AI — информативна нацрт-верзија, не официјален запис.')}
  </div>`;

GF.WWF._renderPinsPanel = () => {
  const st = GF.WWF._report;
  const title = st.mode === 'plan' ? GF.t('ai_next_week_plan') : GF.t('ai_weekly_report');
  const accent = st.mode === 'plan' ? '#FF7A1A' : '#2F6BFF';
  const soft = st.mode === 'plan' ? '#FFF4EC' : '#F8F9FF';
  const line = st.mode === 'plan' ? '#FFE0C7' : '#D6E0FF';
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
      ${s.review ? GF.WWF._sc(AL('In Review', 'На преглед'), s.review, '#7A5BE0') : ''}
      ${s.postponed ? GF.WWF._sc(AL('Postponed', 'Одложени'), s.postponed, '#F6A609') : ''}
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
               stuck: '#E5484D', pending: '#5A6B82', review: '#7A5BE0', postponed: '#F6A609' };
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

  const pinsPanel = GF.WWF._renderPinsPanel();
  v.innerHTML = toolbar + period + cards + band + pinsPanel + depts + taskList + ai;
};

/* nav item for the report/plan view, above Audit Trail */
GF.WWF._registerFullPageView({
  key: 'report', icon: 'trend', label: () => AL('Report', 'Извештај'),
  insertBefore: 'audit', badge: () => GF.WWF._hasNewReportPin,
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
