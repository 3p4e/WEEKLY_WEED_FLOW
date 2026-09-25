/* irrigation-view.js — Irrigation & feeding: the fertigation record, per room
   per day.

   What solution went onto a room, its volume, and the feed and runoff EC/pH
   read around it (irrigation_events, migration 0052). Until 2026-09-05 this
   lived as a "Feeding" tab inside the harvest view and was written by the
   cultivation manager — because there was no irrigation role to own it and
   nowhere else to put it. Irrigation is a department of its own at the
   facility (the fertigation plant and its distribution to every room), so
   the record is now its own view, written by its own manager (IR_MGR) and
   read by everyone above base staff.

   Backend: app/api/irrigation.py — writers ADMIN / executives / IR_MGR. The
   routes still hang off /cultivation because a feed is a record ABOUT a
   cultivation room; who writes it changed, what it is did not.

   Same contract as every floor view: read = elevated roles, the write
   affordance appears only for a recorder, and the backend gate is
   authoritative — this file only mirrors it. */

(function () {
  GF.WWF._irr = { feeds: null, loading: false, error: null };

  const role = () => (GF.API.user || {}).role;
  // Mirrors _RECORDERS in app/api/irrigation.py.
  const canRecord = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'IR_MGR'].includes(role());

  GF.WWF.loadIrrigation = async () => {
    const st = GF.WWF._irr;
    st.loading = true; st.error = null;
    try { st.feeds = (await GF.API.irrigation()).feeds || []; }
    catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'irrigation') GF.render.all();
  };

  // A reading that was not taken is shown as nothing — never as 0, which is a
  // real, in-range value. Same rule the record itself keeps (blank = not
  // measured).
  const rdg = (label, v, unit) => v == null ? '' :
    `<span class="mw-attr" style="--mw-acc:#2FD9D9">${label} <b>${GF.esc(String(v))}${unit || ''}</b></span>`;
  const feedRow = (f) => `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:7px 0;border-bottom:1px solid var(--line)">
      <span style="min-width:150px;font-size:13px">${GF.esc(f.room_name || '—')}${
        f.batch_code ? ` · <span style="color:var(--ink-3)">${GF.esc(f.batch_code)}</span>` : ''}</span>
      <span style="font-size:11px;color:var(--ink-3);min-width:88px">${GF.esc(f.applied_on || '')}</span>
      ${f.method ? `<span class="mw-attr">${GF.esc(f.method)}</span>` : ''}
      ${rdg(AL('Vol', 'Кол.'), f.water_volume_l, ' L')}
      ${rdg('EC', f.feed_ec, '')}${rdg('pH', f.feed_ph, '')}
      ${rdg(AL('runoff EC', 'истек EC'), f.runoff_ec, '')}${rdg(AL('runoff pH', 'истек pH'), f.runoff_ph, '')}
      <span style="flex:1;min-width:80px;font-size:11px;color:var(--ink-3);text-align:right">${GF.esc(f.nutrients || '')}</span>
    </div>`;

  // Must stay in step with irrigation_events_method_check (migration 0052)
  // and _METHODS in app/api/irrigation.py.
  const FEED_METHODS = [
    { v: '', en: '— method —', mk: '— метод —' },
    { v: 'drip', en: 'Drip', mk: 'Капково' }, { v: 'hand', en: 'Hand', mk: 'Рачно' },
    { v: 'flood', en: 'Flood / ebb', mk: 'Поплавно' }, { v: 'boom', en: 'Boom', mk: 'Прскалка' },
    { v: 'other', en: 'Other', mk: 'Друго' },
  ];

  GF.WWF.feedForm = async () => {
    if (!canRecord()) return;
    let rooms = [], batches = [];
    try {
      rooms = (await GF.API.facility()).rooms || [];
      batches = (await GF.API.cultivationBatches(true)).batches || [];
    } catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._ensureModal('ir-feed-modal', '460px');
    GF.$('ir-feed-modal-title').textContent = AL('Log feed', 'Запиши хранење');
    const roomOpts = rooms.map(r => ({ v: r.id, label: r.name }));
    const batchOpts = [{ v: '', label: AL('— whole room, not one batch —', '— цела соба, не еден батч —') }]
      .concat(batches.map(b => ({ v: b.id, label: `${b.code} · ${b.cultivar_code || '—'}`, sub: b.room_name || '' })));
    GF.$('ir-feed-modal-body').innerHTML = `
      <div class="field"><label>${AL('Room', 'Соба')}</label>
        ${GF.selectField('ir-f-room', { value: roomOpts[0] ? roomOpts[0].v : '', title: AL('Room', 'Соба'), options: roomOpts })}</div>
      <div class="field"><label>${AL('Batch (if only one)', 'Батч (ако е само еден)')}</label>
        ${GF.selectField('ir-f-batch', { value: '', title: AL('Batch', 'Батч'), options: batchOpts, searchable: true })}</div>
      <div class="field"><label>${AL('Method', 'Метод')}</label>
        ${GF.selectField('ir-f-method', { value: '', title: AL('Method', 'Метод'), options: FEED_METHODS.map(t => ({ v: t.v, label: AL(t.en, t.mk) })) })}</div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Water volume (L)', 'Вода (L)')}</label>
          <input id="ir-f-vol" type="number" min="0" step="0.1"></div>
      </div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Feed EC', 'EC храна')}</label><input id="ir-f-fec" type="number" min="0" step="0.01"></div>
        <div class="field" style="flex:1"><label>${AL('Feed pH', 'pH храна')}</label><input id="ir-f-fph" type="number" min="0" max="14" step="0.1"></div>
      </div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Runoff EC', 'EC истек')}</label><input id="ir-f-rec" type="number" min="0" step="0.01"></div>
        <div class="field" style="flex:1"><label>${AL('Runoff pH', 'pH истек')}</label><input id="ir-f-rph" type="number" min="0" max="14" step="0.1"></div>
      </div>
      <div class="field"><label>${AL('Nutrients / recipe', 'Хранливи / рецепт')}</label>
        <input id="ir-f-nut" maxlength="1000" placeholder="${AL('Base A+B 2ml/L, CalMag 1ml/L', 'База A+B 2ml/L, CalMag 1ml/L')}"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="ir-f-note" maxlength="1000"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'A feed is recorded for a room; name a batch only when a room holds more than one cultivar. Leave a reading blank if it was not measured — blank means "not measured", not zero.',
        'Хранењето се евидентира за соба; наведете батч само ако собата има повеќе од една сорта. Оставете мерење празно ако не е мерено — празно значи „не е мерено“, не нула.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="ir-f-save" onclick="GF.WWF.feedSave()">${GF.t('save')}</button>
      </div>`;
    GF.openModal('ir-feed-modal');
    setTimeout(() => { const f = GF.$('ir-f-vol'); if (f) f.focus(); }, 60);
  };

  GF.WWF.feedSave = () => GF.once('ir-f-save', async () => {
    const room = ((GF.$('ir-f-room') || {}).value || '') || null;
    if (!room) { GF.toast(AL('Pick the room', 'Изберете соба'), 'error'); return; }
    // parseFloat, not parseInt: EC and pH are decimals. Blank → null ("not
    // measured"), never 0, matching the record's own semantics.
    const num = (id) => {
      const raw = ((GF.$(id) || {}).value || '').trim();
      return raw === '' ? null : parseFloat(raw);
    };
    try {
      await GF.API.irrigationLog({
        room_id: room,
        batch_id: ((GF.$('ir-f-batch') || {}).value || '') || null,
        method: ((GF.$('ir-f-method') || {}).value || '') || null,
        water_volume_l: num('ir-f-vol'),
        feed_ec: num('ir-f-fec'), feed_ph: num('ir-f-fph'),
        runoff_ec: num('ir-f-rec'), runoff_ph: num('ir-f-rph'),
        nutrients: ((GF.$('ir-f-nut') || {}).value || '').trim() || null,
        note: ((GF.$('ir-f-note') || {}).value || '').trim() || null });
      GF.closeModal('ir-feed-modal');
      GF.toast(AL('Feed logged', 'Хранењето е запишано'), 'success');
      await GF.WWF.loadIrrigation();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  GF.views.irrigation = () => {
    const st = GF.WWF._irr;
    if (!st.feeds && !st.loading && !st.error) GF.WWF.loadIrrigation();
    const newBtn = canRecord()
      ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.feedForm()">${GF.icon('plus', 'icon', 'currentColor')}${AL('Log feed', 'Запиши хранење')}</button>`
      : '';
    const head = GF.viewHead
      ? GF.viewHead('irrigation', 'irrigation_sub', newBtn)
      : `<div class="view-head"><h2>${AL('Irrigation', 'Наводнување')}</h2>${newBtn}</div>`;
    if (st.loading && !st.feeds) return head + `<div class="ntf-empty">${AL('Loading…', 'Вчитување…')}</div>`;
    if (st.error) return head + `<div class="ntf-empty">${GF.esc(st.error)}</div>`;
    const rows = st.feeds || [];
    if (!rows.length) {
      return head + `<div class="ntf-empty">${AL(
        'No feeds logged. Irrigation and feeding are recorded per room per day — what solution went on, its volume, and the feed and runoff readings taken around it.',
        'Нема запишани хранења. Наводнувањето и хранењето се евидентираат по соба по ден — кој раствор е даден, количината и мерењата на храна и истек.')}</div>`;
    }
    return head + `<div class="panel" style="padding:4px 14px">${rows.map(feedRow).join('')}</div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'irrigation', icon: 'drop',
    label: () => AL('Irrigation', 'Наводнување'),
    insertBefore: 'floor-end',   // Floor group, beside Facility
    // Same read gate as GET /cultivation/irrigation: every role above base USER.
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
