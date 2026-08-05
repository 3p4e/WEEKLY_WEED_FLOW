/* calendar-view.js — month-grid calendar over task due dates. Global: GF.views.calendar
   Client-side only: buckets GF.state.tasks (+ tree children) by due_date into
   a Monday-first month grid. Click a task chip to open it on the board.
   Idea adopted from the Mass Weed mockups. */
window.GF = window.GF || {};

(function () {
  GF.state.calOffset = 0;   // months relative to the current month

  GF.calNav = (d) => { GF.state.calOffset += d; GF.render.all(); };
  GF.calToday = () => { GF.state.calOffset = 0; GF.render.all(); };

  // Days with more than 3 due tasks only show the first 3 by default (the
  // grid cell has no room for more) — the "+N" pill was previously inert,
  // silently hiding the rest with no way to reach them. It now toggles this
  // day into its cell showing every task.
  GF.state.calExpandedDays = GF.state.calExpandedDays || new Set();
  GF.calToggleDay = (iso) => {
    const s = GF.state.calExpandedDays;
    if (s.has(iso)) s.delete(iso); else s.add(iso);
    GF.render.all();
  };

  const MONTHS = {
    en: ['January','February','March','April','May','June','July','August','September','October','November','December'],
    mk: ['Јануари','Февруари','Март','Април','Мај','Јуни','Јули','Август','Септември','Октомври','Ноември','Декември'],
  };
  // Short month names for the Upcoming strip's date line (bilingual).
  const MONTHS_ABBR = {
    en: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
    mk: ['Јан','Феб','Мар','Апр','Мај','Јун','Јул','Авг','Сеп','Окт','Ное','Дек'],
  };

  GF.views.calendar = () => {
    const now = new Date();
    const base = new Date(now.getFullYear(), now.getMonth() + GF.state.calOffset, 1);
    const y = base.getFullYear(), m = base.getMonth();
    const first = new Date(y, m, 1);
    const startDow = (first.getDay() + 6) % 7;                  // Monday-first
    const daysIn = new Date(y, m + 1, 0).getDate();
    const todayISO = GF.todayISO();   // facility-local; UTC toISOString() drifts a day for +offset

    // Bucket every task (top-level + tree children) by due date.
    const kids = Object.values(GF.state.children || {}).flat();
    const byDay = {};
    (GF.state.tasks || []).concat(kids).forEach(t => {
      const d = t.due;
      if (d) (byDay[d.slice(0, 10)] = byDay[d.slice(0, 10)] || []).push(t);
    });

    const dow = GF.state.lang === 'mk'
      ? ['Пон','Вто','Сре','Чет','Пет','Саб','Нед'] : ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    let cells = '';
    for (let i = 0; i < startDow; i++) cells += '<div class="cal-cell cal-pad"></div>';
    for (let d = 1; d <= daysIn; d++) {
      const iso = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const ts = byDay[iso] || [];
      const expanded = GF.state.calExpandedDays.has(iso);
      const shown = expanded ? ts : ts.slice(0, 3);
      const chips = shown.map(t => {
        const dep = GF.dep(t.dept) || {};
        return `<div class="cal-chip ${t.status === 'done' ? 'done' : ''}" title="${GF.esc(t.title)}"
          style="border-left-color:${dep.color || 'var(--primary)'}"
          onclick="GF.WWF&&GF.WWF.xrJump&&GF.WWF.xrJump('${GF.esc(t.id)}','${GF.esc(t.week_start || '')}')">${GF.esc(t.title)}</div>`;
      }).join('');
      const more = ts.length > 3
        ? `<div class="cal-more" role="button" tabindex="0" onclick="GF.calToggleDay('${iso}')"
             onkeydown="if(event.key==='Enter')GF.calToggleDay('${iso}')">${expanded ? AL('less', 'помалку') : `+${ts.length - 3}`}</div>`
        : '';
      cells += `<div class="cal-cell ${iso === todayISO ? 'cal-today' : ''}">
        <div class="cal-num">${d}</div>${chips}${more}</div>`;
    }

    // ── Legend: departments present in the month on screen ──────────────
    // The grid chips are tinted by department (border-left-color = dep.color);
    // the legend decodes exactly those colours. Only departments that appear
    // in the displayed month are listed, ordered by GF.DEPTS' canonical order,
    // so it stays small and matches what is on screen. Derived purely from the
    // task data already bucketed above — no new fetch.
    const monthPrefix = `${y}-${String(m + 1).padStart(2, '0')}`;
    const deptRank = GF.DEPTS.map(dp => dp.id);
    const monthDepts = [...new Set(
      Object.keys(byDay).filter(k => k.startsWith(monthPrefix))
        .flatMap(k => byDay[k].map(t => t.dept))
    )].filter(Boolean).sort((a, b) => deptRank.indexOf(a) - deptRank.indexOf(b));
    const legend = monthDepts.length ? `<div class="cal-legend" role="list"
        aria-label="${AL('Departments shown this month', 'Прикажани оддели за месецот')}">
        ${monthDepts.map(id => { const dp = GF.dep(id) || {};
          return `<span class="cal-lg" role="listitem"><i class="cal-lg-dot"
            style="background:${dp.color || 'var(--primary)'}"></i>${GF.esc(GF.depName(id))}</span>`;
        }).join('')}</div>` : '';

    // ── Upcoming strip: next few not-done task due-dates ────────────────
    // From the same task data (top-level + tree children), independent of which
    // month is being viewed: the next 6 due-on-or-after-today tasks, soonest
    // first. Date-only ISO strings (YYYY-MM-DD) sort lexicographically. Each
    // card deep-links to the task via the same xrJump the grid chips use.
    const abbr = MONTHS_ABBR[GF.state.lang] || MONTHS_ABBR.en;
    const upDate = (iso) => {
      const [uy, um, ud] = iso.split('-').map(Number);
      const wd = dow[(new Date(uy, um - 1, ud).getDay() + 6) % 7];
      return `${wd}, ${abbr[um - 1]} ${ud}`;
    };
    const upcoming = (GF.state.tasks || []).concat(kids)
      .filter(t => t.due && t.status !== 'done' && t.due.slice(0, 10) >= todayISO)
      .sort((a, b) => (a.due.slice(0, 10) < b.due.slice(0, 10) ? -1
                     : a.due.slice(0, 10) > b.due.slice(0, 10) ? 1 : 0))
      .slice(0, 6);
    const upCards = upcoming.map(t => {
      const dp = GF.dep(t.dept) || {};
      const color = dp.color || 'var(--primary)';
      return `<div class="cal-upcard" role="button" tabindex="0"
        style="border-left-color:${color}" title="${GF.esc(t.title)}"
        onclick="GF.WWF&&GF.WWF.xrJump&&GF.WWF.xrJump('${GF.esc(t.id)}','${GF.esc(t.week_start || '')}')"
        onkeydown="if((event.key==='Enter'||event.key===' ')&&GF.WWF&&GF.WWF.xrJump){event.preventDefault();GF.WWF.xrJump('${GF.esc(t.id)}','${GF.esc(t.week_start || '')}')}">
        <span class="cal-up-dot" style="background:${color}"></span>
        <span class="cal-up-body">
          <span class="cal-up-title">${GF.esc(t.title)}</span>
          <span class="cal-up-date">${upDate(t.due.slice(0, 10))}</span>
        </span></div>`;
    }).join('');
    const upStrip = `<div class="cal-up-wrap">
        <div class="cal-up-label">${AL('Upcoming', 'Претстојни')}</div>
        <div class="cal-upstrip">${upCards ||
          `<div class="cal-up-empty">${AL('Nothing upcoming', 'Нема претстојни задачи')}</div>`}</div>
      </div>`;

    return `${GF.viewHead('calendar', 'calendar')}
      <div class="cal-bar">
        <button class="btn btn-sm" onclick="GF.calNav(-1)">${GF.icon('chevL', 'icon')}</button>
        <div class="cal-title">${MONTHS[GF.state.lang][m] || MONTHS.en[m]} ${y}</div>
        <button class="btn btn-sm" onclick="GF.calNav(1)">${GF.icon('chevR', 'icon')}</button>
        <button class="btn btn-sm" onclick="GF.calToday()">${AL('Today', 'Денес')}</button>
        ${legend}
      </div>
      ${upStrip}
      <div class="cal-grid">
        ${dow.map(d => `<div class="cal-dow">${d}</div>`).join('')}
        ${cells}
      </div>`;
  };
})();
