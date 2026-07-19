/* facility-view.js — the owner's Facility board (mockup facility.html).
   Live cultivation occupancy: plants per room, strain, phase; phase totals
   (clones / vegetation / flowering) across the site. Read: every role above
   base USER (executives, QP, all department managers). Write (add / move /
   close batches): cultivation manager + executives + ADMIN.

   Environment telemetry from the mockup (temp/RH/CO₂/VPD) is deliberately
   absent — no sensor feed exists; this board shows only what people record.

   Same monkey-patch/view pattern as the other *-view.js files; loads after
   worklog.js (uses AL(), GF.WWF._ensureModal, GF.selectField choosers). */

(function () {
  GF.WWF._fac = { data: null, loading: false, error: null };

  const PHASES = {
    clone:  { en: 'Clones',     mk: 'Клонови',    color: '#2BE8A0' },
    veg:    { en: 'Vegetation', mk: 'Вегетација', color: '#3FA34D' },
    flower: { en: 'Flowering',  mk: 'Цветање',    color: '#E0A73E' },
    mother: { en: 'Mothers',    mk: 'Мајки',      color: '#C89BF0' },
    drying: { en: 'Drying',     mk: 'Сушење',     color: '#8296B4' },
  };
  const KINDS = {
    nursery: { en: 'Nursery', mk: 'Расадник' }, veg: { en: 'Veg', mk: 'Вегетација' },
    flower: { en: 'Grow', mk: 'Одгледување' }, mother: { en: 'Mother', mk: 'Мајки' },
    dry: { en: 'Dry', mk: 'Сушење' }, other: { en: '—', mk: '—' },
  };
  const phLbl = (p) => AL(PHASES[p]?.en || p, PHASES[p]?.mk || p);
  const phCol = (p) => (PHASES[p] || {}).color || 'var(--ink-3)';
  const roomName = (r) => (GF.state.lang === 'mk' && r.name_mk) ? r.name_mk : r.name;
  const canWrite = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'CU_MGR']
    .includes((GF.API.user || {}).role);
  // Room provisioning (POST /facility/rooms, PATCH /facility/rooms/{id}) is
  // ADMIN-only — narrower than canWrite()'s batch-writer set above. Reuses
  // the shared strict-ADMIN helper (integrate.js) rather than duplicating
  // the role check inline.
  const canWriteRooms = () => !!(GF.WWF.isAdmin && GF.WWF.isAdmin());
  const ROOM_CODE_RE = /^[a-z0-9_]{1,64}$/;   // mirrors RoomIn.code server-side pattern
  const daysIn = (iso) => {
    if (!iso) return 0;
    return Math.max(0, Math.round((Date.now() - new Date(iso + 'T00:00:00')) / 864e5));
  };

  GF.WWF.loadFacility = async () => {
    const st = GF.WWF._fac;
    st.loading = true; st.error = null;
    try { st.data = await GF.API.facility(); }
    catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'facility') GF.render.all();
  };

  GF.views.facility = () => {
    const st = GF.WWF._fac;
    if (!st.data && !st.loading && !st.error) GF.WWF.loadFacility();
    const addRoomBtn = canWriteRooms()
      ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.openRoomForm(null)">${GF.icon('plus', 'icon', '#fff')}${AL('Add room', 'Додади соба')}</button>`
      : '';
    const head = GF.viewHead
      ? GF.viewHead('facility_map', 'facility_sub', addRoomBtn)
      : `<h2>${AL('Facility', 'Капацитет')}</h2>`;
    if (st.loading || (!st.data && !st.error)) {
      return head + `<div class="mw-skel" style="height:96px;margin-bottom:10px"></div>
        <div class="mw-skel" style="height:220px"></div>`;
    }
    if (st.error) {
      return head + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadFacility()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const d = st.data, t = d.totals || {};
    // Site-wide totals as a resource strip (icon + glowing count), not a tile
    // grid — the facility board's single "how much is out there right now"
    // readout, distinct from the .dash-kpis tiles other screens use.
    const res = (v, l, c) => `<div class="fac-res"><span class="fac-res-ic" style="color:${c}"></span><span class="fac-res-v" style="color:${c}">${v}</span><span class="fac-res-l">${l}</span></div>`;
    const kpis = `<div class="fac-resbar">
      ${res(t.total || 0, AL('Total plants', 'Вкупно растенија'), 'var(--ink)')}
      ${res(t.clone || 0, phLbl('clone'), phCol('clone'))}
      ${res(t.veg || 0, phLbl('veg'), phCol('veg'))}
      ${res(t.flower || 0, phLbl('flower'), phCol('flower'))}
      ${(t.mother || t.drying) ? res((t.mother || 0) + (t.drying || 0),
          phLbl('mother') + ' / ' + phLbl('drying'), phCol('mother')) : ''}
    </div>`;
    const rooms = (d.rooms || []).map(r => {
      const rows = r.batches.map(b => `
        <div class="fac-strain" title="${GF.esc(b.note || '')}">
          <span class="fs-dot" style="background:${phCol(b.phase)}"></span>
          <span class="fs-nm">${GF.esc(b.strain)}</span>
          <span class="fs-n">${b.plant_count}</span>
          <span class="fs-ph" style="color:${phCol(b.phase)}">${phLbl(b.phase)} · ${daysIn(b.phase_since)}${AL('d', 'д')}</span>
        </div>`).join('');
      return `
      <div class="fac-room" onclick="GF.WWF.openRoom('${r.id}')">
        <div class="fac-room-hd">
          <span class="fr-nm">${GF.esc(roomName(r))}</span>
          <span class="fr-kind">${AL(KINDS[r.kind]?.en || r.kind, KINDS[r.kind]?.mk || r.kind)}</span>
        </div>
        <div class="fr-big"><span class="fr-n">${r.plant_total}</span>
          <span class="fr-u">${AL('plants', 'растенија')}</span></div>
        <div class="fac-strains">${rows || `<div class="fr-empty">${AL('Empty', 'Празно')}</div>`}</div>
      </div>`;
    }).join('');
    return head + kpis + `
      <div class="fac-map">${rooms || `<div class="ntf-empty">${
        canWriteRooms()
          ? AL('No rooms configured yet — use "Add room" above to create the first one.',
               'Сè уште нема соби — користете „Додади соба" погоре за да ја креирате првата.')
          : AL('No rooms configured yet — an administrator sets them up on the facility board.',
               'Сè уште нема соби — администраторот ги поставува на таблата за капацитет.')
        }</div>`}</div>`;
  };

  /* ── Room detail modal: batches + writer controls ── */
  GF.WWF.openRoom = (roomId) => {
    const d = GF.WWF._fac.data; if (!d) return;
    const r = (d.rooms || []).find(x => x.id === roomId); if (!r) return;
    GF.WWF._ensureModal('fac-room-modal', '460px');
    GF.$('fac-room-modal-title').textContent = roomName(r);
    const rows = r.batches.map(b => `
      <div class="sess-row">
        <span class="fs-dot" style="background:${phCol(b.phase)}"></span>
        <span style="font-weight:700">${GF.esc(b.strain)}</span>
        <span style="font-family:var(--mono)">${b.plant_count}</span>
        <span style="flex:1;color:${phCol(b.phase)};font-size:12px">${phLbl(b.phase)} · ${daysIn(b.phase_since)}${AL('d', 'д')}</span>
        ${canWrite() ? `<button class="mini-btn" title="${GF.t('edit')}"
          onclick="GF.WWF.openBatch('${b.id}')">${GF.icon('settings')}</button>` : ''}
      </div>`).join('');
    GF.$('fac-room-modal-body').innerHTML = `
      <div id="fac-room-rows">${rows || `<div class="fr-empty" style="padding:8px 0">${AL('Empty', 'Празно')}</div>`}</div>
      ${canWrite() ? `<button class="btn btn-primary" style="width:100%;justify-content:center;margin-top:12px"
        onclick="GF.WWF.openBatch(null,'${r.id}')">${AL('Add batch', 'Додади серија')}</button>` : ''}
      ${canWriteRooms() ? `<button class="btn" style="width:100%;justify-content:center;margin-top:8px"
        onclick="GF.WWF.openRoomForm('${r.id}')">${GF.icon('settings', 'icon')}${AL('Edit room', 'Уреди соба')}</button>` : ''}`;
    GF.openModal('fac-room-modal');
  };

  /* ── Batch editor: create (batchId null) or edit ── */
  GF.WWF.openBatch = (batchId, roomId) => {
    const d = GF.WWF._fac.data; if (!d) return;
    let b = null;
    if (batchId) {
      for (const r of d.rooms) { b = r.batches.find(x => x.id === batchId); if (b) break; }
      if (!b) return;
      roomId = b.room_id;
    }
    GF.closeModal('fac-room-modal');
    GF.WWF._ensureModal('fac-batch-modal', '420px');
    GF.$('fac-batch-modal-title').textContent = b
      ? AL('Edit batch', 'Уреди серија') : AL('Add batch', 'Додади серија');
    const roomOpts = d.rooms.map(r => ({ v: r.id, label: roomName(r) }));
    const phaseOpts = Object.keys(PHASES).map(p => ({ v: p, label: phLbl(p), color: phCol(p) }));
    GF.$('fac-batch-modal-body').innerHTML = `
      <div class="field"><label>${AL('Strain', 'Сорта')}</label>
        <input id="fb-strain" maxlength="120" value="${GF.esc(b ? b.strain : '')}" placeholder="${AL('e.g. Gorilla Glue', 'пр. Gorilla Glue')}"></div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Plants', 'Растенија')}</label>
          <input id="fb-count" type="number" min="0" step="1" value="${b ? b.plant_count : ''}" placeholder="0"></div>
        <div class="field" style="flex:1.4"><label>${AL('Phase', 'Фаза')}</label>
          ${GF.selectField('fb-phase', { value: b ? b.phase : 'clone', title: AL('Phase', 'Фаза'), options: phaseOpts })}</div>
      </div>
      <div class="field"><label>${AL('Room', 'Соба')}</label>
        ${GF.selectField('fb-room', { value: roomId, title: AL('Room', 'Соба'), options: roomOpts })}</div>
      <div class="field"><label>${AL('Note', 'Белешка')}</label>
        <input id="fb-note" maxlength="500" value="${GF.esc(b && b.note ? b.note : '')}"></div>
      <div class="row" style="gap:10px">
        ${b ? `<button class="btn" style="color:var(--red)" onclick="GF.WWF.closeBatch('${b.id}')">${AL('Close batch', 'Затвори серија')}</button>` : ''}
        <div class="spacer"></div>
        <button class="btn btn-primary" onclick="GF.WWF.saveBatch(${b ? `'${b.id}'` : 'null'})">${GF.t('save')}</button>
      </div>`;
    GF.openModal('fac-batch-modal');
    setTimeout(() => GF.$('fb-strain') && GF.$('fb-strain').focus(), 60);
  };

  GF.WWF.saveBatch = async (batchId) => {
    const strain = ((GF.$('fb-strain') || {}).value || '').trim();
    const count = parseInt((GF.$('fb-count') || {}).value, 10);
    const phase = (GF.$('fb-phase') || {}).value;
    const room = (GF.$('fb-room') || {}).value;
    const note = ((GF.$('fb-note') || {}).value || '').trim() || null;
    if (!strain || !Number.isFinite(count) || count < 0 || !room) {
      GF.toast(AL('Enter strain, plant count and room', 'Внесете сорта, број растенија и соба'), 'error');
      return;
    }
    const body = { room_id: room, strain, plant_count: count, phase, note };
    try {
      if (batchId) await GF.API.facilityPatchBatch(batchId, body);
      else await GF.API.facilityAddBatch(body);
      GF.closeModal('fac-batch-modal');
      GF.toast(GF.t('save') + ' ✓', 'success');
      GF.WWF.loadFacility();
    } catch (e) { GF.toast(AL('Save failed: ', 'Неуспешно зачувување: ') + e.message, 'error'); }
  };

  GF.WWF.closeBatch = async (batchId) => {
    if (!confirm(AL('Close this batch? It leaves the facility board (harvested / culled) but stays in the audit trail.',
                    'Да се затвори серијата? Ја напушта таблата (ожнеана / отстранета), но останува во ревизијата.'))) return;
    try {
      await GF.API.facilityPatchBatch(batchId, { is_active: false });
      GF.closeModal('fac-batch-modal');
      GF.toast('✓', 'success');
      GF.WWF.loadFacility();
    } catch (e) { GF.toast(AL('Failed: ', 'Неуспешно: ') + e.message, 'error'); }
  };

  /* ── Room editor: create (roomId null) or edit — ADMIN only ──
     Mirrors the batch editor above (same modal shell, same save/close-then-
     refresh flow) but gated by canWriteRooms(), not canWrite(), because
     POST/PATCH /facility/rooms are require_role(ADMIN) on the backend while
     batch writes admit the broader CU_MGR/executive set. */
  GF.WWF.openRoomForm = (roomId) => {
    if (!canWriteRooms()) return;
    const d = GF.WWF._fac.data; if (!d) return;
    let r = null;
    if (roomId) { r = (d.rooms || []).find(x => x.id === roomId); if (!r) return; }
    GF.closeModal('fac-room-modal');
    GF.WWF._ensureModal('fac-roomform-modal', '420px');
    GF.$('fac-roomform-modal-title').textContent = r
      ? AL('Edit room', 'Уреди соба') : AL('Add room', 'Додади соба');
    const kindOpts = Object.keys(KINDS).map(k => ({ v: k, label: AL(KINDS[k].en, KINDS[k].mk) }));
    // code is immutable after creation (RoomPatch has no code field) — only
    // shown on the create form.
    GF.$('fac-roomform-modal-body').innerHTML = `
      ${r ? '' : `<div class="field"><label>${AL('Code', 'Код')}</label>
        <input id="fr-code" maxlength="64" placeholder="${AL('e.g. flower_a', 'пр. flower_a')}"></div>`}
      <div class="field"><label>${AL('Name', 'Име')}</label>
        <input id="fr-name" maxlength="120" value="${GF.esc(r ? r.name : '')}" placeholder="${AL('e.g. Flower Room A', 'пр. Соба за цветање А')}"></div>
      <div class="field"><label>${AL('Name (Macedonian)', 'Име (МК)')}</label>
        <input id="fr-name-mk" maxlength="120" value="${GF.esc(r && r.name_mk ? r.name_mk : '')}"></div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1.4"><label>${AL('Kind', 'Тип')}</label>
          ${GF.selectField('fr-kind', { value: r ? r.kind : 'flower', title: AL('Kind', 'Тип'), options: kindOpts })}</div>
        <div class="field" style="flex:1"><label>${AL('Sort', 'Редослед')}</label>
          <input id="fr-sort" type="number" min="0" max="1000" step="1" value="${r ? r.sort : 0}"></div>
      </div>
      <div class="row" style="gap:10px">
        ${r ? `<button class="btn" style="color:var(--red)" onclick="GF.WWF.deactivateRoom('${r.id}')">${AL('Deactivate room', 'Деактивирај соба')}</button>` : ''}
        <div class="spacer"></div>
        <button class="btn btn-primary" onclick="GF.WWF.saveRoom(${r ? `'${r.id}'` : 'null'})">${GF.t('save')}</button>
      </div>`;
    GF.openModal('fac-roomform-modal');
    setTimeout(() => { const f = GF.$('fr-code') || GF.$('fr-name'); if (f) f.focus(); }, 60);
  };

  GF.WWF.saveRoom = async (roomId) => {
    if (!canWriteRooms()) return;
    const name = ((GF.$('fr-name') || {}).value || '').trim();
    const nameMk = ((GF.$('fr-name-mk') || {}).value || '').trim();
    const kind = (GF.$('fr-kind') || {}).value;
    const sortRaw = ((GF.$('fr-sort') || {}).value || '').trim();
    const sort = sortRaw === '' ? 0 : parseInt(sortRaw, 10);
    if (!name) {
      GF.toast(AL('Enter a room name', 'Внесете име на собата'), 'error');
      return;
    }
    if (!Number.isFinite(sort) || sort < 0 || sort > 1000) {
      GF.toast(AL('Sort must be a number between 0 and 1000', 'Редоследот мора да е број меѓу 0 и 1000'), 'error');
      return;
    }
    try {
      if (roomId) {
        // name_mk is the one field the server treats an explicit null as
        // "clear it" rather than "not supplied" — sending '' as null here
        // lets an admin remove a Macedonian name they'd set earlier.
        await GF.API.facilityPatchRoom(roomId, { name, name_mk: nameMk || null, kind, sort });
      } else {
        const code = ((GF.$('fr-code') || {}).value || '').trim().toLowerCase();
        if (!ROOM_CODE_RE.test(code)) {
          GF.toast(AL('Code must be lowercase letters, digits, underscore only (1-64 characters)',
                       'Кодот смее да содржи само мали букви, цифри и долна црта (1-64 знаци)'), 'error');
          return;
        }
        await GF.API.facilityAddRoom({ code, name, name_mk: nameMk || null, kind, sort });
      }
      GF.closeModal('fac-roomform-modal');
      GF.toast(GF.t('save') + ' ✓', 'success');
      GF.WWF.loadFacility();
    } catch (e) { GF.toast(AL('Save failed: ', 'Неуспешно зачувување: ') + e.message, 'error'); }
  };

  GF.WWF.deactivateRoom = async (roomId) => {
    if (!canWriteRooms()) return;
    if (!confirm(AL(
      'Deactivate this room? It disappears from the facility board immediately — move or close any batches inside it first.',
      'Да се деактивира собата? Веднаш исчезнува од таблата за капацитет — прво преместете или затворете ги сериите во неа.'))) return;
    try {
      await GF.API.facilityPatchRoom(roomId, { is_active: false });
      GF.closeModal('fac-roomform-modal');
      GF.toast('✓', 'success');
      GF.WWF.loadFacility();
    } catch (e) { GF.toast(AL('Failed: ', 'Неуспешно: ') + e.message, 'error'); }
  };

  GF.WWF._registerFullPageView({
    key: 'facility', icon: 'leaf',
    label: () => AL('Facility', 'Капацитет'),
    insertBefore: 'mywork',   // Operations group of the rail (mockup nav.js)
    // Same read gate as GET /facility: every role above base USER.
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
