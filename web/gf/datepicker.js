/* datepicker.js — the app's date field, replacing bare <input type="date">.

   Why not the native control: it opens on the BROWSER's today, and this app's
   today belongs to the facility (Europe/Skopje — see GF.facilityToday). For
   anyone working the nightly window where Skopje and UTC differ, or reading
   from another zone, the native picker highlights the wrong day and offers it
   as the obvious click. On a GxP record — a harvest date, a sampling date, a
   manufacture date printed onto a certificate — that is a wrong fact, entered
   by a control that looked like it was helping.

   So: a month grid that opens on the facility's today, highlights it, and
   lets the user move day / month / year explicitly.

   Contract copied from chooser.js deliberately, for the same reason it has
   one: a HIDDEN <input id="..."> holds the ISO value, so every existing
   `GF.$('hv-c-date').value` read and `.value =` write keeps working with no
   idea which control renders it. A visible button shows the formatted date.

   Global: GF.dateField(id, cfg) → markup string
           GF.openDatePicker(id, ev) / GF.pickDate(id, iso) / GF.syncDate(id)
   cfg: { value, placeholder?, min?, max?, onPick?(iso), clearable? }

   IMPORTANT — highlighted is not the same as chosen. An empty field opens ON
   today without WRITING today: silently defaulting an expiry or a retest date
   to today would put a real, wrong claim into a record the user never
   touched. Fields that genuinely want today prefilled (a clone date, a
   worklog day) pass it as cfg.value at their call site, as they already did. */
window.GF = window.GF || {};

(function () {
  const REG = {};            // id → cfg (rebuilt every time the form renders)
  let openId = null;
  let viewY = 0, viewM = 0;  // the month the grid is currently showing

  const MK_MONTHS = ['јануари', 'февруари', 'март', 'април', 'мај', 'јуни',
                     'јули', 'август', 'септември', 'октомври', 'ноември', 'декември'];
  const EN_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November', 'December'];
  // Monday-first, matching calendar-view.js and the facility's own week.
  const MK_DOW = ['пон', 'вто', 'сре', 'чет', 'пет', 'саб', 'нед'];
  const EN_DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  const mk = () => GF.state && GF.state.lang === 'mk';
  const monthName = (m) => (mk() ? MK_MONTHS : EN_MONTHS)[m];

  const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
  const parse = (iso) => {
    const m = ISO.exec(String(iso || ''));
    if (!m) return null;
    const y = +m[1], mo = +m[2] - 1, d = +m[3];
    const dt = new Date(y, mo, d);
    // Rejects 2026-02-31 and friends: Date rolls them over silently, and a
    // rolled-over date in a record is the same class of wrong fact as a
    // fabricated one.
    return (dt.getFullYear() === y && dt.getMonth() === mo && dt.getDate() === d)
      ? { y: y, m: mo, d: d } : null;
  };
  const iso = (y, m, d) => {
    const p = n => String(n).padStart(2, '0');
    return `${y}-${p(m + 1)}-${p(d)}`;
  };

  // Display format: DD.MM.YYYY — the convention already used for dates the
  // facility reads (auditprep-view.js), and unambiguous in both languages.
  GF.fmtDateHuman = (v) => {
    const p = parse(v);
    if (!p) return '';
    const z = n => String(n).padStart(2, '0');
    return `${z(p.d)}.${z(p.m + 1)}.${p.y}`;
  };

  GF.dateField = (id, cfg) => {
    cfg = cfg || {};
    REG[id] = cfg;
    const v = cfg.value != null ? String(cfg.value) : '';
    const shown = GF.fmtDateHuman(v);
    const ph = cfg.placeholder || (mk() ? 'Избери датум' : 'Pick a date');
    return `<input type="hidden" id="${id}" value="${GF.esc(v)}">`
      + `<button type="button" class="sel-btn dp-btn" id="${id}-btn"${cfg.disabled ? ' disabled' : ''}`
      + ` onclick="GF.openDatePicker('${id}', event)" aria-haspopup="dialog">`
      + `<span class="sel-cur${shown ? '' : ' dp-empty'}">${GF.esc(shown || ph)}</span>`
      + `${GF.icon ? GF.icon('calendar', 'icon sel-caret') : ''}</button>`;
  };

  // Re-read the hidden input (a writer set .value directly) → refresh the label.
  GF.syncDate = (id) => {
    const cfg = REG[id], inp = GF.$(id), btn = GF.$(id + '-btn');
    if (!cfg || !inp || !btn) return;
    const shown = GF.fmtDateHuman(inp.value);
    const cur = btn.querySelector('.sel-cur');
    cur.textContent = shown || cfg.placeholder || (mk() ? 'Избери датум' : 'Pick a date');
    cur.classList.toggle('dp-empty', !shown);
  };

  const inRange = (cfg, v) =>
    (!cfg.min || v >= cfg.min) && (!cfg.max || v <= cfg.max);

  const grid = (cfg, cur) => {
    const today = GF.facilityToday();
    const first = new Date(viewY, viewM, 1);
    // Monday-first padding, same derivation as calendar-view.js.
    const pad = (first.getDay() + 6) % 7;
    const days = new Date(viewY, viewM + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < pad; i++) cells.push('<span class="dp-cell dp-pad"></span>');
    for (let d = 1; d <= days; d++) {
      const v = iso(viewY, viewM, d);
      const on = v === cur, isToday = v === today, ok = inRange(cfg, v);
      cells.push(
        `<button type="button" class="dp-cell${on ? ' on' : ''}${isToday ? ' dp-today' : ''}"`
        + `${ok ? '' : ' disabled'} data-v="${v}"`
        + ` aria-current="${isToday ? 'date' : 'false'}"`
        + ` onclick="GF.pickDate('${openId}', this.dataset.v)">${d}</button>`);
    }
    const dow = (mk() ? MK_DOW : EN_DOW)
      .map(n => `<span class="dp-dow">${n}</span>`).join('');
    return `<div class="dp-dows">${dow}</div><div class="dp-grid">${cells.join('')}</div>`;
  };

  const body = (id) => {
    const cfg = REG[id];
    const inp = GF.$(id);
    const cur = inp ? inp.value : (cfg.value != null ? String(cfg.value) : '');
    const today = GF.facilityToday();
    const t = parse(today);
    // Year range: wide enough for an expiry or a retest date, anchored on the
    // facility's year rather than the browser's.
    const y0 = (t ? t.y : viewY) - 6, y1 = (t ? t.y : viewY) + 8;
    const years = [];
    for (let y = y0; y <= y1; y++) {
      years.push(`<option value="${y}"${y === viewY ? ' selected' : ''}>${y}</option>`);
    }
    const months = (mk() ? MK_MONTHS : EN_MONTHS).map((n, i) =>
      `<option value="${i}"${i === viewM ? ' selected' : ''}>${GF.esc(n)}</option>`).join('');
    return `
      <div class="dp-head">
        <button type="button" class="btn-ghost dp-nav" aria-label="${mk() ? 'Претходен месец' : 'Previous month'}"
          onclick="GF._dpMove(-1)">‹</button>
        <select class="dp-sel" aria-label="${mk() ? 'Месец' : 'Month'}" onchange="GF._dpSet('m', this.value)">${months}</select>
        <select class="dp-sel" aria-label="${mk() ? 'Година' : 'Year'}" onchange="GF._dpSet('y', this.value)">${years.join('')}</select>
        <button type="button" class="btn-ghost dp-nav" aria-label="${mk() ? 'Следен месец' : 'Next month'}"
          onclick="GF._dpMove(1)">›</button>
      </div>
      ${grid(cfg, cur)}
      <div class="dp-foot">
        <button type="button" class="btn btn-sm" onclick="GF.pickDate('${id}', '${today}')">
          ${mk() ? 'Денес' : 'Today'} · ${GF.esc(GF.fmtDateHuman(today))}</button>
        ${cfg.clearable === false ? '' : `<button type="button" class="btn btn-sm" onclick="GF.pickDate('${id}', '')">
          ${mk() ? 'Исчисти' : 'Clear'}</button>`}
      </div>`;
  };

  const repaint = () => {
    const el = GF.$('gf-datepicker');
    if (!el || !openId) return;
    const host = el.querySelector('.dp-body');
    if (host) host.innerHTML = body(openId);
  };

  GF._dpMove = (delta) => {
    viewM += delta;
    if (viewM < 0) { viewM = 11; viewY -= 1; }
    else if (viewM > 11) { viewM = 0; viewY += 1; }
    repaint();
  };
  GF._dpSet = (which, v) => {
    if (which === 'm') viewM = +v; else viewY = +v;
    repaint();
  };

  GF.openDatePicker = (id, ev) => {
    const cfg = REG[id];
    if (!cfg || (GF.$(id + '-btn') || {}).disabled) return;
    openId = id;
    const inp = GF.$(id);
    const cur = inp ? inp.value : (cfg.value != null ? String(cfg.value) : '');
    // Open on the chosen date if there is one, otherwise on the FACILITY's
    // today — the whole point of this control.
    const at = parse(cur) || parse(GF.facilityToday()) || parse(GF.todayISO());
    viewY = at.y; viewM = at.m;

    const trigger = ev ? (ev.currentTarget || ev.target) : null;
    const triggerRect = trigger ? trigger.getBoundingClientRect() : null;
    let el = GF.$('gf-datepicker');
    if (!el) {
      el = document.createElement('div');
      el.id = 'gf-datepicker'; el.className = 'overlay';
    }
    // Always (re)append: this picker is opened FROM inside other overlays
    // (the task modal, the worklog modal), which are themselves created on
    // first use and appended to <body>. Two .overlay siblings share one
    // z-index, so DOM order decides which paints on top — and a modal first
    // opened AFTER this element existed would land later in <body> and sit
    // over the calendar, swallowing every click on it (seen live in e2e:
    // "#worklog-modal subtree intercepts pointer events"). appendChild on an
    // existing node MOVES it to the end, so the picker is always last, and
    // app.css gives it a stacking layer above modals besides.
    document.body.appendChild(el);
    el.innerHTML = `
      <div class="modal sel-modal dp-modal" role="dialog" aria-modal="true"
        aria-label="${mk() ? 'Избери датум' : 'Pick a date'}">
        <div class="modal-head"><h3>${GF.esc(cfg.title || (mk() ? 'Избери датум' : 'Pick a date'))}</h3>
          <button class="btn-ghost" onclick="GF.closeModal('gf-datepicker')">
            <svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
        <div class="modal-body dp-body">${body(id)}</div>
      </div>`;
    GF.openModal('gf-datepicker');
    // Same entrance-origin trick as chooser.js — see its comment for why this
    // must run after openModal but inside the same synchronous tick.
    if (triggerRect) {
      const m = el.querySelector('.dp-modal');
      const r = m.getBoundingClientRect();
      m.style.transformOrigin =
        `${(triggerRect.left + triggerRect.width / 2) - r.left}px `
        + `${(triggerRect.top + triggerRect.height / 2) - r.top}px`;
    }
  };

  GF.pickDate = (id, v) => {
    const cfg = REG[id];
    if (!cfg) return;
    const inp = GF.$(id);
    if (inp) { inp.value = v || ''; GF.syncDate(id); }
    GF.closeModal('gf-datepicker'); openId = null;
    if (cfg.onPick) cfg.onPick(v || '');
  };

  // Keyboard: arrows walk days, PageUp/Down change month, Enter picks the
  // focused day. The grid's buttons are real buttons, so Tab already works —
  // this adds the calendar-shaped movement on top.
  document.addEventListener('keydown', (e) => {
    const el = GF.$('gf-datepicker');
    if (!el || !el.classList.contains('open') || !openId) return;
    const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
    if (step) {
      e.preventDefault();
      const cur = (GF.$(openId) || {}).value;
      const at = parse(cur) || parse(GF.facilityToday());
      const d = new Date(at.y, at.m, at.d + step);
      const v = iso(d.getFullYear(), d.getMonth(), d.getDate());
      if (!inRange(REG[openId], v)) return;
      const inp = GF.$(openId);
      if (inp) { inp.value = v; GF.syncDate(openId); }
      viewY = d.getFullYear(); viewM = d.getMonth();
      repaint();
    } else if (e.key === 'PageUp' || e.key === 'PageDown') {
      e.preventDefault(); GF._dpMove(e.key === 'PageUp' ? -1 : 1);
    } else if (e.key === 'Enter') {
      const cur = (GF.$(openId) || {}).value;
      if (parse(cur)) { e.preventDefault(); GF.pickDate(openId, cur); }
    }
  });
})();
