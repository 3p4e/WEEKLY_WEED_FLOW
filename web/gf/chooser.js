/* chooser.js — popup chooser replacing native <select> dropdowns app-wide
   (the Mass Weed mockup's interaction model: every choice opens a popup
   listing the options, instead of a browser dropdown).

   Contract-preserving by design: GF.selectField renders a HIDDEN
   <input id="..."> holding the value plus a visible trigger button — so every
   existing `GF.$('add-dept').value` read (submitAdd, collectDeptAttrs) and
   `.value =` write (openEdit, applyPreset) keeps working unchanged. Writers
   just add a GF.syncSelect(id) call so the button label follows.

   Global: GF.selectField(id, cfg) → markup string
           GF.openChooser(id) / GF.pickSel(id, v) / GF.syncSelect(id)
   cfg: { value, options:[{v,label,color?,sub?}], onPick?(v), searchable?,
          disabled?, placeholder? }                                        */
window.GF = window.GF || {};

(function () {
  const REG = {};            // id → cfg (rebuilt every time the form renders)
  let openId = null;         // which field the overlay is showing
  let hi = -1;               // keyboard-highlighted row index (filtered list)

  const label = (cfg, v) => {
    const o = (cfg.options || []).find(o => String(o.v) === String(v ?? ''));
    return o ? o.label : (cfg.placeholder || '—');
  };

  GF.selectField = (id, cfg) => {
    REG[id] = cfg;
    const v = cfg.value != null ? String(cfg.value) : '';
    return `<input type="hidden" id="${id}" value="${GF.esc(v)}">`
      + `<button type="button" class="sel-btn${cfg.inline ? ' sel-inline' : ''}" id="${id}-btn"${cfg.disabled ? ' disabled' : ''}`
      + ` onclick="GF.openChooser('${id}')" aria-haspopup="listbox">`
      + `<span class="sel-cur">${GF.esc(label(cfg, v))}</span>${GF.icon('chevD', 'icon sel-caret')}</button>`;
  };

  // ── Inline chip group (design task-create-*.html): every option VISIBLE,
  // one tap to pick — the design shows the whole small option set rather than
  // hiding it behind a popup. Same hidden-input contract as selectField, so
  // collectDeptAttrs / applyPreset / openEdit keep reading and writing
  // GF.$(id).value with no idea which control renders it.
  GF.chipField = (id, cfg) => {
    REG[id] = Object.assign({ chips: true }, cfg);
    const v = cfg.value != null ? String(cfg.value) : '';
    const chips = (cfg.options || []).map((o) => `
      <button type="button" class="mw-chip mw-chip--sm${String(o.v) === v ? ' on' : ''}"
        ${o.color ? `style="--cc:${GF.esc(o.color)}"` : ''} data-v="${GF.esc(String(o.v))}"
        onclick="GF.pickChip('${id}', this.dataset.v)"><span class="d"></span>${GF.esc(o.label)}</button>`).join('');
    return `<input type="hidden" id="${id}" value="${GF.esc(v)}">`
      + `<div class="mw-chips" id="${id}-chips" role="radiogroup" aria-label="${GF.esc(cfg.title || '')}">${chips}</div>`;
  };
  GF.pickChip = (id, v) => {
    const cfg = REG[id], inp = GF.$(id);
    if (!cfg || !inp) return;
    // Same-chip tap CLEARS an optional field (the design's None chip pattern
    // without needing an explicit None everywhere).
    inp.value = (inp.value === v && cfg.clearable !== false) ? '' : v;
    GF.syncSelect(id);
    if (cfg.onPick) cfg.onPick(inp.value);
  };

  // Re-read the hidden input (a writer set .value directly) → refresh the
  // control: the popup button's label, or every chip's .on state.
  GF.syncSelect = (id) => {
    const cfg = REG[id], inp = GF.$(id);
    if (!cfg || !inp) return;
    if (cfg.chips) {
      const host = GF.$(id + '-chips');
      if (host) host.querySelectorAll('.mw-chip').forEach((c) =>
        c.classList.toggle('on', c.dataset.v === inp.value));
      return;
    }
    const btn = GF.$(id + '-btn');
    if (!btn) return;
    btn.querySelector('.sel-cur').textContent = label(cfg, inp.value);
  };

  const rows = (cfg, cur, q) => {
    const ql = (q || '').toLowerCase();
    const list = (cfg.options || []).filter(o =>
      !ql || String(o.label).toLowerCase().includes(ql) || String(o.sub || '').toLowerCase().includes(ql));
    if (!list.length) return `<div class="sel-empty">${GF.state.lang === 'mk' ? 'Нема совпаѓања' : 'No matches'}</div>`;
    return list.map((o, i) => `
      <button type="button" class="sel-row${String(o.v) === String(cur) ? ' on' : ''}${i === hi ? ' hover' : ''}"
        data-v="${GF.esc(String(o.v))}" onclick="GF.pickSel('${openId}', this.dataset.v)">
        ${o.color ? `<span class="sel-dot" style="background:${GF.esc(o.color)}"></span>` : ''}
        <span class="sel-lbl">${GF.esc(o.label)}${o.sub ? `<span class="sel-sub">${GF.esc(o.sub)}</span>` : ''}</span>
        ${String(o.v) === String(cur) ? GF.icon('check', 'icon sel-ck') : ''}
      </button>`).join('');
  };

  // Imperative popup — same chooser, no form field. For pickers that act
  // immediately (subtask status pill, quick actions): cfg.value is the
  // current selection, cfg.onPick receives the choice.
  GF.choose = (cfg) => { REG.__choose = cfg; GF.openChooser('__choose'); };

  GF.openChooser = (id) => {
    const cfg = REG[id]; if (!cfg) return;
    openId = id; hi = -1;
    // Anchor the entrance scale on whatever the user actually clicked to get
    // here — the field's .sel-btn button, or (for the imperative GF.choose()
    // path, e.g. GF.pickStatus's status pill) the .pill span. window.event
    // still refers to that live click event here: GF.openChooser only ever
    // runs synchronously inside an inline onclick handler — either directly
    // (the .sel-btn's own onclick) or one call deeper through
    // GF.choose → GF.pickStatus — with no async gap in between, so
    // .currentTarget has not been reset to null yet by the time we read it.
    const ev = window.event;
    const trigger = ev ? (ev.currentTarget || ev.target) : null;
    const triggerRect = trigger ? trigger.getBoundingClientRect() : null;
    let el = GF.$('gf-chooser');
    if (!el) { el = document.createElement('div'); el.id = 'gf-chooser'; el.className = 'overlay'; document.body.appendChild(el); }
    const cur = GF.$(id) ? GF.$(id).value : (cfg.value != null ? String(cfg.value) : '');
    const search = cfg.searchable || (cfg.options || []).length > 8;
    el.innerHTML = `
      <div class="modal sel-modal">
        <div class="modal-head"><h3>${GF.esc(cfg.title || '')}</h3>
          <button class="btn-ghost" onclick="GF.closeModal('gf-chooser')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
        <div class="modal-body sel-body">
          ${search ? `<input id="sel-search" class="sel-search" placeholder="${GF.state.lang === 'mk' ? 'Барај…' : 'Search…'}"
             oninput="GF._selFilter(this.value)" autocomplete="off">` : ''}
          <div class="sel-list" id="sel-list" role="listbox">${rows(cfg, cur, '')}</div>
        </div>
      </div>`;
    GF.openModal('gf-chooser');
    // The popup's own box position/size isn't known until it's laid out, so
    // this has to run AFTER GF.openModal() flips .overlay to display:flex —
    // but still in this same synchronous tick, before the browser paints the
    // animation's first frame. transform-origin is expressed in the
    // element's OWN local coordinate space (0,0 = its own top-left corner),
    // so the trigger's viewport-space center must be converted into an
    // offset from the popup's box, not used as a raw viewport coordinate.
    if (triggerRect) {
      const modalEl = el.querySelector('.sel-modal');
      const modalRect = modalEl.getBoundingClientRect();
      const originX = (triggerRect.left + triggerRect.width / 2) - modalRect.left;
      const originY = (triggerRect.top + triggerRect.height / 2) - modalRect.top;
      modalEl.style.transformOrigin = `${originX}px ${originY}px`;
    }
    const s = GF.$('sel-search'); if (s) s.focus();
  };

  GF._selFilter = (q) => {
    const cfg = REG[openId]; if (!cfg) return;
    hi = -1;
    const cur = GF.$(openId) ? GF.$(openId).value : (cfg.value != null ? String(cfg.value) : '');
    GF.$('sel-list').innerHTML = rows(cfg, cur, q);
  };

  GF.pickSel = (id, v) => {
    const cfg = REG[id];
    if (!cfg) return;
    const inp = GF.$(id);           // absent for imperative GF.choose pickers
    if (inp) { inp.value = v; GF.syncSelect(id); }
    GF.closeModal('gf-chooser'); openId = null;
    if (cfg.onPick) cfg.onPick(v);
  };

  // Keyboard: arrows move the highlight, Enter picks, Escape closes (the
  // global handler in main.js already closes .overlay.open on Escape).
  document.addEventListener('keydown', (e) => {
    const el = GF.$('gf-chooser');
    if (!el || !el.classList.contains('open')) return;
    const list = el.querySelectorAll('.sel-row');
    if (!list.length) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      hi = e.key === 'ArrowDown' ? Math.min(hi + 1, list.length - 1) : Math.max(hi - 1, 0);
      list.forEach((r, i) => r.classList.toggle('hover', i === hi));
      list[hi].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter' && hi >= 0) {
      e.preventDefault(); list[hi].click();
    }
  });
})();
