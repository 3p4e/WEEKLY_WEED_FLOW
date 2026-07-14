/* calendar-view.js — month-grid calendar over task due dates. Global: GF.views.calendar
   Client-side only: buckets GF.state.tasks (+ tree children) by due_date into
   a Monday-first month grid. Click a task chip to open it on the board.
   Idea adopted from the Mass Weed mockups. */
window.GF = window.GF || {};

(function () {
  const AL = (en, mk) => (GF.state.lang === 'mk' ? mk : en);
  GF.state.calOffset = 0;   // months relative to the current month

  GF.calNav = (d) => { GF.state.calOffset += d; GF.render.all(); };
  GF.calToday = () => { GF.state.calOffset = 0; GF.render.all(); };

  const MONTHS = {
    en: ['January','February','March','April','May','June','July','August','September','October','November','December'],
    mk: ['Јануари','Февруари','Март','Април','Мај','Јуни','Јули','Август','Септември','Октомври','Ноември','Декември'],
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
      const chips = ts.slice(0, 3).map(t => {
        const dep = GF.dep(t.dept) || {};
        return `<div class="cal-chip ${t.status === 'done' ? 'done' : ''}" title="${GF.esc(t.title)}"
          style="border-left-color:${dep.color || 'var(--primary)'}"
          onclick="GF.WWF&&GF.WWF.xrJump&&GF.WWF.xrJump('${GF.esc(t.id)}','${GF.esc(t.week_start || '')}')">${GF.esc(t.title)}</div>`;
      }).join('');
      const more = ts.length > 3 ? `<div class="cal-more">+${ts.length - 3}</div>` : '';
      cells += `<div class="cal-cell ${iso === todayISO ? 'cal-today' : ''}">
        <div class="cal-num">${d}</div>${chips}${more}</div>`;
    }

    return `${GF.viewHead('calendar', 'calendar')}
      <div class="cal-bar">
        <button class="btn btn-sm" onclick="GF.calNav(-1)">${GF.icon('chevL', 'icon')}</button>
        <div class="cal-title">${MONTHS[GF.state.lang][m] || MONTHS.en[m]} ${y}</div>
        <button class="btn btn-sm" onclick="GF.calNav(1)">${GF.icon('chevR', 'icon')}</button>
        <button class="btn btn-sm" onclick="GF.calToday()">${AL('Today', 'Денес')}</button>
      </div>
      <div class="cal-grid">
        ${dow.map(d => `<div class="cal-dow">${d}</div>`).join('')}
        ${cells}
      </div>`;
  };
})();
