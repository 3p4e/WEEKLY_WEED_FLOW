/* facility-view.js — the owner's Facility board (mockup facility.html).
   Live cultivation occupancy: plants per room, strain, phase; phase totals
   (clones / vegetation / flowering) across the site. Read: every role above
   base USER (executives, QP, all department managers). READ-ONLY over
   batches — creating, moving, and closing a batch lives on the Cultivation
   board (GF.WWF.cultBatchForm there), which is also the only place that can
   set a batch's cultivar/code (required for plant ids and the genealogy chain).
   This file used to have its own batch editor writing PATCH/POST
   /facility/batches — a second, independent write path over the exact same
   row Cultivation owns, with no cultivar/code, no headcount validation, and
   a narrower phase list that could crash this board outright the moment a
   batch was in a phase (nursery) this file's own display map didn't know
   about. Removed; see backend/app/api/facility.py's module docstring.

   Environment telemetry from the mockup (temp/RH/CO₂/VPD) is deliberately
   absent — no sensor feed exists; this board shows only what people record.

   Same monkey-patch/view pattern as the other *-view.js files; loads after
   worklog.js (uses AL(), GF.WWF._ensureModal, GF.selectField choosers). */

(function () {
  GF.WWF._fac = { data: null, loading: false, error: null };

  const PHASES = {
    nursery: { en: 'Nursery',   mk: 'Расадник',   color: '#7FD9C4' },
    clone:  { en: 'Clones',     mk: 'Клонови',    color: '#2BE8A0' },
    veg:    { en: 'Vegetation', mk: 'Вегетација', color: '#3FA34D' },
    flower: { en: 'Flowering',  mk: 'Цветање',    color: '#E0A73E' },
    mother: { en: 'Mothers',    mk: 'Мајки',      color: '#C89BF0' },
    drying: { en: 'Drying',     mk: 'Сушење',     color: '#8296B4' },
  };
  const KINDS = {
    clone: { en: 'Clone', mk: 'Клонирање' },
    nursery: { en: 'Nursery', mk: 'Расадник' }, veg: { en: 'Veg', mk: 'Вегетација' },
    flower: { en: 'Grow', mk: 'Одгледување' }, mother: { en: 'Mother', mk: 'Мајки' },
    dry: { en: 'Dry', mk: 'Сушење' }, other: { en: '—', mk: '—' },
  };
  const phLbl = (p) => AL(PHASES[p]?.en || p, PHASES[p]?.mk || p);
  const phCol = (p) => (PHASES[p] || {}).color || 'var(--ink-3)';
  const roomName = (r) => (GF.state.lang === 'mk' && r.name_mk) ? r.name_mk : r.name;
  // Rooms are opened and edited by whoever RUNS them — mirrors _ROOM_WRITERS
  // and _KINDS_BY_ROLE in app/api/facility.py. ADMIN and the executives: any
  // room. A department manager: only the kinds their department operates,
  // within their own department (or a sub-department of it). Rooms used to be
  // ADMIN-only, and a batch requires a room — so the cultivation manager
  // could create a batch and had nowhere to put it.
  const role = () => (GF.API.user || {}).role;
  const ROOM_WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'CU_MGR', 'PR_MGR'];
  const KINDS_BY_ROLE = { CU_MGR: ['clone', 'nursery', 'veg', 'flower', 'mother'], PR_MGR: ['dry'] };
  const isExec = () => ['ADMIN', 'OWNER', 'CEO', 'COO'].includes(role());
  const myKinds = () => isExec() ? null : (KINDS_BY_ROLE[role()] || []);   // null = any
  const myFamily = () => GF.WWF.deptFamily ? GF.WWF.deptFamily((GF.API.user || {}).department_id) : [];
  const canWriteRooms = () => ROOM_WRITERS.includes(role()) && (isExec() || !!(GF.API.user || {}).department_id);
  // This room, as it is: mine to edit? (The server decides; this only hides
  // a button that would 403.) A legacy room with no department is editable by
  // the manager whose kind it is — see facility.py's _assert_room_authority.
  const canEditRoom = (r) => canWriteRooms() && (isExec() ||
    (myKinds().includes(r.kind) && (!r.department_id || myFamily().includes(String(r.department_id)))));
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
      ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.openRoomForm(null)">${GF.icon('plus', 'icon', 'currentColor')}${AL('Add room', 'Додади соба')}</button>`
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
          : AL('No rooms configured yet — a department manager or an administrator sets them up on the facility board.',
               'Сè уште нема соби — менаџер на оддел или администраторот ги поставува на таблата за капацитет.')
        }</div>`}</div>`;
  };

  /* ── Room detail modal: batches (read-only) + writer controls ── */
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
      </div>`).join('');
    GF.$('fac-room-modal-body').innerHTML = `
      <div id="fac-room-rows">${rows || `<div class="fr-empty" style="padding:8px 0">${AL('Empty', 'Празно')}</div>`}</div>
      <div style="font-size:12px;color:var(--ink-3);margin-top:12px">
        ${AL('Add, move, or close batches from the Cultivation board.', 'Додавајте, преместувајте или затворајте серии од таблата за Култивација.')}</div>
      ${canEditRoom(r) ? `<button class="btn" style="width:100%;justify-content:center;margin-top:8px"
        onclick="GF.WWF.openRoomForm('${r.id}')">${GF.icon('settings', 'icon')}${AL('Edit room', 'Уреди соба')}</button>` : ''}`;
    GF.openModal('fac-room-modal');
  };

  /* ── Room editor: create (roomId null) or edit ──
     Gated by canWriteRooms(); the kinds on offer are the caller's own
     (a cultivation manager is not shown 'dry'), and the department is theirs
     unless they are ADMIN / an executive, who choose it — or leave it unset. */
  GF.WWF.openRoomForm = (roomId) => {
    if (!canWriteRooms()) return;
    const d = GF.WWF._fac.data; if (!d) return;
    let r = null;
    if (roomId) { r = (d.rooms || []).find(x => x.id === roomId); if (!r) return; }
    GF.closeModal('fac-room-modal');
    GF.WWF._ensureModal('fac-roomform-modal', '420px');
    GF.$('fac-roomform-modal-title').textContent = r
      ? AL('Edit room', 'Уреди соба') : AL('Add room', 'Додади соба');
    const kinds = myKinds();
    const kindOpts = Object.keys(KINDS).filter(k => !kinds || kinds.includes(k))
      .map(k => ({ v: k, label: AL(KINDS[k].en, KINDS[k].mk) }));
    const defKind = r ? r.kind : (kinds ? kinds[0] : 'flower');
    // ADMIN / executives pick the department that runs the room (or none);
    // a manager's room is their department's, said rather than chosen.
    const deptRow = isExec()
      ? `<div class="field"><label>${AL('Department', 'Оддел')}</label>
          ${GF.selectField('fr-dept', { value: r && r.department_id ? r.department_id : '',
            title: AL('Department', 'Оддел'), searchable: true,
            options: [{ v: '', label: AL('— none —', '— нема —') }].concat(
              (GF.DEPTS || []).map(d => ({ v: d.id, label: GF.depName ? GF.depName(d.id) : d.name, color: d.color }))) })}</div>`
      : `<div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
          'The room belongs to your department.', 'Собата припаѓа на вашиот оддел.')}</div>`;
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
          ${GF.selectField('fr-kind', { value: defKind, title: AL('Kind', 'Тип'), options: kindOpts })}</div>
        <div class="field" style="flex:1"><label>${AL('Sort', 'Редослед')}</label>
          <input id="fr-sort" type="number" min="0" max="1000" step="1" value="${r ? r.sort : 0}"></div>
      </div>
      ${deptRow}
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
    // Only ADMIN / executives have the chooser; a manager sends no department
    // and the server assigns their own (create) or leaves it as it is (edit).
    const deptEl = GF.$('fr-dept');
    const dept = deptEl ? ((deptEl.value || '') || null) : undefined;
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
        const patch = { name, name_mk: nameMk || null, kind, sort };
        if (dept !== undefined) patch.department_id = dept;   // null = unassign (ADMIN/exec only)
        await GF.API.facilityPatchRoom(roomId, patch);
      } else {
        const code = ((GF.$('fr-code') || {}).value || '').trim().toLowerCase();
        if (!ROOM_CODE_RE.test(code)) {
          GF.toast(AL('Code must be lowercase letters, digits, underscore only (1-64 characters)',
                       'Кодот смее да содржи само мали букви, цифри и долна црта (1-64 знаци)'), 'error');
          return;
        }
        const body = { code, name, name_mk: nameMk || null, kind, sort };
        if (dept) body.department_id = dept;
        await GF.API.facilityAddRoom(body);
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
    insertBefore: 'floor-end',   // Floor group of the rail
    // Same read gate as GET /facility: every role above base USER.
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
