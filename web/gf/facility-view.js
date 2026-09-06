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
  GF.WWF._fac = { data: null, loading: false, error: null, tab: 'rooms' };
  // The as-built register (tasks 0068 + api/facility_layout.py): the building
  // as the architect drew it, loaded lazily the first time the plan is opened.
  GF.WWF._plan = { data: null, loading: false, error: null, mode: 'plan',
                   zone: '', q: '', zoom: 1, sel: null, room: null };

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
    // Two boards over the same building: what is growing in it right now
    // (rooms) and what it IS (the as-built plan, tasks 0068).
    const tab = (key, label) => `<button class="cj-tab${st.tab === key ? ' on' : ''}"
      onclick="GF.WWF.facTab('${key}')">${label}</button>`;
    const tabs = `<div class="cj-tabs">
      ${tab('rooms', AL('Rooms', 'Соби'))}
      ${tab('plan', AL('Floor plan', 'Основа'))}
    </div>`;
    if (st.tab === 'plan') return head + tabs + GF.WWF.facPlan();
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
    return head + tabs + kpis + `
      <div class="fac-map">${rooms || `<div class="ntf-empty">${
        canWriteRooms()
          ? AL('No rooms configured yet — use "Add room" above to create the first one.',
               'Сè уште нема соби — користете „Додади соба" погоре за да ја креирате првата.')
          : AL('No rooms configured yet — a department manager or an administrator sets them up on the facility board.',
               'Сè уште нема соби — менаџер на оддел или администраторот ги поставува на таблата за капацитет.')
        }</div>`}</div>`;
  };

  /* ── The as-built floor plan ──────────────────────────────────────────
     The register carries, per room, a normalised anchor (plan_x, plan_y) on
     the ground-floor sheet, so a marker is placed at exactly the point the
     architect stamped the room code. The image below the markers is that
     sheet — assets/facility-ground-floor.png, rendered from the PDF over the
     same bounds the anchors were normalised against, so the two agree by
     construction rather than by eye. */

  const ZONES = {
    cultivation:  { en: 'Cultivation',  mk: 'Одгледување',   color: '#2EA043' },
    post_harvest: { en: 'Post-harvest', mk: 'По берба',      color: '#D27814' },
    production:   { en: 'Production',   mk: 'Производство',  color: '#A03CC8' },
    quality:      { en: 'Quality',      mk: 'Квалитет',      color: '#008CBE' },
    warehouse:    { en: 'Warehouse',    mk: 'Магацин',       color: '#C8A000' },
    airlock:      { en: 'Air lock',     mk: 'Тампон зона',   color: '#E63C3C' },
    circulation:  { en: 'Circulation',  mk: 'Ходници',       color: '#7A7A85' },
    personnel:    { en: 'Personnel',    mk: 'Персонал',      color: '#3C5AC8' },
    technical:    { en: 'Technical',    mk: 'Техника',       color: '#5A5A5A' },
    utility:      { en: 'Utility',      mk: 'Помошни',       color: '#8C8C5A' },
    waste:        { en: 'Waste',        mk: 'Отпад',         color: '#78462A' },
    egress:       { en: 'Fire exit',    mk: 'ППЗ излез',     color: '#E61E1E' },
  };
  const REGIMES = { GACP: { en: 'GACP', mk: 'ГАЦП' }, GMP: { en: 'GMP', mk: 'ГМП' },
                    SUPPORT: { en: 'Support', mk: 'Придружни' } };
  const zLbl = (z) => z && ZONES[z] ? AL(ZONES[z].en, ZONES[z].mk) : AL('Unclassified', 'Некласифицирано');
  const zCol = (z) => (ZONES[z] || {}).color || 'var(--ink-3)';
  const planName = (r) => (GF.state.lang === 'mk' && r.name_mk) ? r.name_mk : (r.name_en || r.code);
  // Grade and regime are QA's call, not the drawing's — the same roles the
  // server lets through in facility_layout.py's _CLASSIFIERS.
  const canClassify = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'QA_MGR'].includes(role());

  GF.WWF.facTab = (key) => {
    GF.WWF._fac.tab = key;
    if (key === 'plan') {
      const p = GF.WWF._plan;
      if (!p.data && !p.loading && !p.error) GF.WWF.loadPlan();
    }
    GF.render.all();
  };

  GF.WWF.loadPlan = async () => {
    const p = GF.WWF._plan;
    p.loading = true; p.error = null;
    try { p.data = await GF.API.facilityLayout(); }
    catch (e) { p.error = e.message; }
    p.loading = false;
    if (GF.state.view === 'facility') GF.render.all();
  };

  GF.WWF.planZone = (z) => { GF.WWF._plan.zone = GF.WWF._plan.zone === z ? '' : z; GF.render.all(); };
  GF.WWF.planZoom = (d) => {
    const p = GF.WWF._plan;
    p.zoom = Math.min(6, Math.max(1, Math.round((p.zoom + d) * 10) / 10));
    GF.render.all();
  };
  GF.WWF.planSearch = (v) => {
    GF.WWF._plan.q = v;
    // Re-render only the shapes and the roster, so the field keeps focus.
    const stage = GF.$('fp-stage'); if (stage) stage.innerHTML = GF.WWF._planMarkers();
    const svg = GF.$('fp-svg'); if (svg) svg.innerHTML = GF.WWF._planShapes();
    const list = GF.$('fp-list'); if (list) list.innerHTML = GF.WWF._planRoster();
  };

  const planRooms = () => {
    const p = GF.WWF._plan;
    const q = (p.q || '').trim().toLowerCase();
    return (p.data && p.data.rooms ? p.data.rooms : []).filter(r => {
      if (p.zone && r.zone !== p.zone) return false;
      if (!q) return true;
      return (r.code || '').toLowerCase().includes(q)
          || (r.name_en || '').toLowerCase().includes(q)
          || (r.name_mk || '').toLowerCase().includes(q);
    });
  };

  GF.WWF._planMarkers = () => planRooms().filter(r => r.plan_x != null).map(r => `
    <button class="fp-pin${GF.WWF._plan.sel === r.id ? ' on' : ''}"
      style="left:${(r.plan_x * 100).toFixed(3)}%;top:${(r.plan_y * 100).toFixed(3)}%;--pin:${zCol(r.zone)}"
      title="${GF.esc(r.code + ' · ' + planName(r))}"
      onclick="event.stopPropagation();GF.WWF.openPlanRoom('${r.id}')">
      <span class="fp-pin-dot"></span><span class="fp-pin-lbl">${GF.esc(r.code)}</span>
    </button>`).join('');

  GF.WWF._planRoster = () => {
    const rows = planRooms();
    if (!rows.length) return `<div class="fr-empty" style="padding:10px 0">${AL('No room matches.', 'Нема соба што одговара.')}</div>`;
    return rows.map(r => `
      <div class="fp-row" onclick="GF.WWF.openPlanRoom('${r.id}')">
        <span class="fp-row-dot" style="background:${zCol(r.zone)}"></span>
        <span class="fp-row-code">${GF.esc(r.code)}</span>
        <span class="fp-row-nm">${GF.esc(planName(r))}</span>
        <span class="fp-row-a">${r.area_m2 != null ? r.area_m2.toFixed(2) + ' m²' : '—'}</span>
        <span class="fp-row-rg">${r.regime ? AL(REGIMES[r.regime].en, REGIMES[r.regime].mk) : ''}</span>
      </div>`).join('');
  };


  /* ── The plan the app draws itself ────────────────────────────────────
     Every room carries a rectangle in the same normalised frame as its pin
     (tasks 0069): the SIZE solved exactly from the area and perimeter the
     drawing stamps, the POSITION and orientation fitted to the drawing's own
     wall ink, and `box_conf` recording how well the fitted edges landed on it.

     Drawn as SVG rather than as a picture of the sheet, which buys the three
     things a scan cannot give: it takes the app's theme, it stays sharp at any
     zoom on any screen, and a room can be coloured by what it IS. Rooms whose
     fit scored low are drawn dashed — the app says "about here" rather than
     implying a survey nobody did. */

  const PLAN_VB_W = 1000;
  const PLAN_VB_H = 443;          // 2710 x 1200 pt, the frame the boxes normalise to
  const LOW_CONF = 0.15;

  /* The register's frame is the sheet's frame, and the sheet has margin the
     building does not fill — a quarter of it is empty site. The DATA stays in
     that one frame so a room's rectangle and its pin are the same coordinates;
     only the camera moves. */
  const planViewBox = (rooms) => {
    const b = rooms.filter(r => r.box_x != null);
    if (!b.length) return `0 0 ${PLAN_VB_W} ${PLAN_VB_H}`;
    const x0 = Math.min(...b.map(r => r.box_x)) * PLAN_VB_W;
    const y0 = Math.min(...b.map(r => r.box_y)) * PLAN_VB_H;
    const x1 = Math.max(...b.map(r => r.box_x + r.box_w)) * PLAN_VB_W;
    const y1 = Math.max(...b.map(r => r.box_y + r.box_h)) * PLAN_VB_H;
    const m = 6;
    return `${(x0 - m).toFixed(1)} ${(y0 - m).toFixed(1)} `
         + `${(x1 - x0 + 2 * m).toFixed(1)} ${(y1 - y0 + 2 * m).toFixed(1)}`;
  };

  GF.WWF.planMode = (m) => { GF.WWF._plan.mode = m; GF.render.all(); };

  // Which rooms the current filters single out. Unlike the drawing's pins the
  // plan never removes a room — a floor plan with holes in it is not a floor
  // plan — so a filtered-out room is dimmed and made unclickable instead.
  const planMatch = (r) => {
    const p = GF.WWF._plan;
    const q = (p.q || '').trim().toLowerCase();
    if (p.zone && r.zone !== p.zone) return false;
    if (!q) return true;
    return (r.code || '').toLowerCase().includes(q)
        || (r.name_en || '').toLowerCase().includes(q)
        || (r.name_mk || '').toLowerCase().includes(q);
  };

  GF.WWF._planShapes = () => {
    const p = GF.WWF._plan;
    const rooms = (p.data && p.data.rooms ? p.data.rooms : []).filter(r => r.box_x != null);
    const anyFilter = !!(p.zone || (p.q || '').trim());
    // Biggest first, so a small room inside a hall stays clickable above it.
    return rooms.slice().sort((a, b) => (b.box_w * b.box_h) - (a.box_w * a.box_h))
      .map(r => {
        const on = planMatch(r);
        const x = (r.box_x * PLAN_VB_W).toFixed(2);
        const y = (r.box_y * PLAN_VB_H).toFixed(2);
        const w = (r.box_w * PLAN_VB_W).toFixed(2);
        const h = (r.box_h * PLAN_VB_H).toFixed(2);
        const cls = 'fp-r'
          + (p.sel === r.id ? ' on' : '')
          + (anyFilter && !on ? ' off' : '')
          + ((r.box_conf != null && r.box_conf < LOW_CONF) ? ' loose' : '');
        const label = (r.box_w * PLAN_VB_W > 26 && r.box_h * PLAN_VB_H > 11)
          ? `<text class="fp-rt" x="${(+x + 2.5).toFixed(2)}" y="${(+y + 8).toFixed(2)}">${GF.esc(r.code)}</text>`
          : '';
        return `<g class="${cls}" style="--pin:${zCol(r.zone)}"
            onclick="GF.WWF.openPlanRoom('${r.id}')">
            <title>${GF.esc(r.code + ' · ' + planName(r)
              + (r.area_m2 != null ? ' · ' + r.area_m2.toFixed(2) + ' m²' : ''))}</title>
            <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="0.8"></rect>${label}</g>`;
      }).join('');
  };

  GF.WWF.facPlan = () => {
    const p = GF.WWF._plan;
    if (p.loading || (!p.data && !p.error)) {
      return `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div>
              <div class="mw-skel" style="height:340px"></div>`;
    }
    if (p.error) {
      return `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(p.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadPlan()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    if (!(p.data.rooms || []).length) {
      return `<div class="panel" style="padding:18px;text-align:center">
        <div style="color:var(--ink-2);margin-bottom:10px">${AL(
          'The ground-floor plan has not been loaded into this organisation yet.',
          'Основата на приземјето сè уште не е внесена во оваа организација.')}</div>
        ${isExec() ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.importPlan()">${
          AL('Load the ground-floor plan', 'Внеси ја основата')}</button>` : ''}</div>`;
    }
    const totals = p.data.totals || {};
    const chip = (z) => {
      const t = totals[z]; if (!t) return '';
      return `<button class="fp-chip${p.zone === z ? ' on' : ''}" onclick="GF.WWF.planZone('${z}')"
        style="--pin:${zCol(z)}"><span></span>${zLbl(z)}
        <b>${t.rooms}</b> · ${Math.round(t.area_m2)} m²</button>`;
    };
    const legend = `<div class="fp-legend">${Object.keys(ZONES).map(chip).join('')}</div>`;
    const mode = (k, label) => `<button class="fp-mode${p.mode === k ? ' on' : ''}"
      onclick="GF.WWF.planMode('${k}')">${label}</button>`;
    const bar = `<div class="fp-bar">
      <div class="fp-modes">
        ${mode('plan', AL('Plan', 'Основа'))}
        ${mode('drawing', AL('Drawing', 'Цртеж'))}
      </div>
      <input id="fp-q" class="fp-q" placeholder="${AL('Find a room — code or name', 'Најди соба — код или име')}"
             value="${GF.esc(p.q)}" oninput="GF.WWF.planSearch(this.value)">
      <div class="fp-zoom">
        <button class="btn btn-sm" onclick="GF.WWF.planZoom(-0.5)">−</button>
        <span>${Math.round(p.zoom * 100)}%</span>
        <button class="btn btn-sm" onclick="GF.WWF.planZoom(0.5)">+</button>
      </div>
    </div>`;
    // Two representations of one building, over the same register and the same
    // room card: the plan the app draws, and the architect's own sheet.
    const stage = p.mode === 'drawing'
      ? `<div class="fp-stage-outer" style="width:${p.zoom * 100}%">
          <img class="fp-img" src="assets/facility-ground-floor.png" alt="${
            AL('Ground-floor plan', 'Основа на приземје')}">
          <div class="fp-stage${p.zoom < 1.5 ? ' fp-quiet' : ''}" id="fp-stage">${GF.WWF._planMarkers()}</div>
        </div>`
      : `<div class="fp-stage-outer" style="width:${p.zoom * 100}%">
          <svg class="fp-svg" id="fp-svg" viewBox="${planViewBox(p.data.rooms || [])}"
               preserveAspectRatio="xMidYMid meet" role="img"
               aria-label="${AL('Ground-floor plan', 'Основа на приземје')}">
            ${GF.WWF._planShapes()}
          </svg>
        </div>`;
    const src = p.mode === 'drawing'
      ? AL('Ground floor — Medical Cannabis Facility, Petrovec. Conceptual layout, 03/2021.',
           'Приземје — Медицинска канабис фабрика, Петровец. Концептуална основа, 03/2021.')
      : AL('Drawn from the register: each room sized from its stamped area and perimeter, '
           + 'placed against the architect\'s ground-floor sheet. A dashed room is approximately placed.',
           'Нацртано од регистарот: секоја соба е димензионирана од запишаната површина и периметар, '
           + 'поставена според основата на архитектот. Испрекинатите соби се приближно поставени.');
    return bar + legend + `
      <div class="fp-wrap${p.mode === 'plan' ? ' fp-wrap-plan' : ''}">${stage}</div>
      <div class="fp-src">${src}</div>
      <div class="fp-list" id="fp-list">${GF.WWF._planRoster()}</div>`;
  };

  GF.WWF.importPlan = async () => {
    if (!isExec()) return;
    try {
      const res = await GF.API.facilityLayoutImport({ dry_run: false });
      GF.toast(`${res.created.length} + ${res.updated.length} ✓`, 'success');
      GF.WWF._plan.data = null;
      GF.WWF.loadPlan();
    } catch (e) { GF.toast(AL('Failed: ', 'Неуспешно: ') + e.message, 'error'); }
  };

  GF.WWF.openPlanRoom = async (id) => {
    GF.WWF._plan.sel = id;
    GF.WWF._ensureModal('fac-plan-modal', '460px');
    const list = (GF.WWF._plan.data || {}).rooms || [];
    const r = list.find(x => x.id === id); if (!r) return;
    GF.$('fac-plan-modal-title').textContent = r.code + ' · ' + planName(r);
    GF.$('fac-plan-modal-body').innerHTML = GF.WWF._planCard(r, null);
    GF.openModal('fac-plan-modal');
    // The detail call adds what is growing in the room right now.
    try {
      const full = await GF.API.facilityLayoutRoom(id);
      GF.WWF._plan.room = full;
      const body = GF.$('fac-plan-modal-body');
      if (body) body.innerHTML = GF.WWF._planCard(full, full.batches || []);
    } catch (e) { /* the card without batches is still the truth of the drawing */ }
  };

  GF.WWF._planCard = (r, batches) => {
    const kv = (l, v) => v == null || v === '' ? ''
      : `<div class="fp-kv"><span>${l}</span><b>${GF.esc(String(v))}</b></div>`;
    const other = GF.state.lang === 'mk' ? r.name_en : r.name_mk;
    const grade = r.grade
      ? GF.esc(r.grade)
      : `<span style="color:var(--ink-3)">${AL('not classified', 'некласифицирано')}</span>`;
    const bl = batches == null
      ? `<div class="fr-empty" style="padding:6px 0">${AL('Loading…', 'Се вчитува…')}</div>`
      : (batches.length
        ? batches.map(b => `<div class="sess-row">
            <span class="fs-dot" style="background:${phCol(b.phase)}"></span>
            <span style="font-weight:700">${GF.esc(b.code)}</span>
            <span style="font-family:var(--mono)">${b.plant_count}</span>
            <span style="flex:1;color:${phCol(b.phase)};font-size:12px">${GF.esc(b.cultivar_name || b.cultivar_code || '')} · ${phLbl(b.phase)}</span>
          </div>`).join('')
        : `<div class="fr-empty" style="padding:6px 0">${r.room_id
            ? AL('Nothing growing here right now.', 'Моментално нема ништо во раст тука.')
            : AL('Not linked to a room the app schedules.', 'Не е поврзана со соба што апликацијата планира.')}</div>`);
    return `
      <div class="fp-badges">
        <span class="fp-badge" style="--pin:${zCol(r.zone)}">${zLbl(r.zone)}</span>
        ${r.regime ? `<span class="fp-badge fp-badge-q">${AL(REGIMES[r.regime].en, REGIMES[r.regime].mk)}</span>` : ''}
      </div>
      ${other ? `<div style="color:var(--ink-2);font-size:12px;margin-bottom:8px">${GF.esc(other)}</div>` : ''}
      ${kv(AL('Area', 'Површина'), r.area_m2 != null ? r.area_m2.toFixed(2) + ' m²' : null)}
      ${kv(AL('Cultivation area', 'Површина за одгледување'), r.net_area_m2 != null ? r.net_area_m2.toFixed(2) + ' m²' : null)}
      ${kv(AL('Perimeter', 'Периметар'), r.perimeter_m != null ? r.perimeter_m.toFixed(2) + ' m' : null)}
      <div class="fp-kv"><span>${AL('Cleanliness grade', 'Класа на чистота')}</span><b>${grade}</b></div>
      ${kv(AL('Department', 'Оддел'), r.department_name)}
      ${kv(AL('Room', 'Соба'), r.room_name)}
      ${r.notes ? `<div style="font-size:12px;color:var(--ink-2);margin-top:8px">${GF.esc(r.notes)}</div>` : ''}
      <div class="fp-sub">${AL('In this room', 'Во оваа соба')}</div>
      ${bl}
      ${canClassify() ? `<button class="btn" style="width:100%;justify-content:center;margin-top:10px"
        onclick="GF.WWF.openPlanClassify('${r.id}')">${GF.icon('settings', 'icon')}${
        AL('Classify this room', 'Класифицирај ја собата')}</button>` : ''}`;
  };

  /* ── Classification: the grade, the regime and the link to an operational
     room. Never the code, name, area or anchor — those are what the drawing
     says, and the app must not quietly disagree with the sheet. */
  GF.WWF.openPlanClassify = (id) => {
    if (!canClassify()) return;
    const r = ((GF.WWF._plan.data || {}).rooms || []).find(x => x.id === id); if (!r) return;
    GF.closeModal('fac-plan-modal');
    GF.WWF._ensureModal('fac-plancls-modal', '420px');
    GF.$('fac-plancls-modal-title').textContent = AL('Classify ', 'Класифицирај ') + r.code;
    const rooms = ((GF.WWF._fac.data || {}).rooms || []);
    GF.$('fac-plancls-modal-body').innerHTML = `
      <div class="field"><label>${AL('Regime', 'Режим')}</label>
        ${GF.selectField('pc-regime', { value: r.regime || '', title: AL('Regime', 'Режим'),
          options: [{ v: '', label: AL('— unset —', '— незададено —') }].concat(
            Object.keys(REGIMES).map(k => ({ v: k, label: AL(REGIMES[k].en, REGIMES[k].mk) }))) })}</div>
      <div class="field"><label>${AL('Cleanliness grade', 'Класа на чистота')}</label>
        <input id="pc-grade" maxlength="40" value="${GF.esc(r.grade || '')}"
               placeholder="${AL('e.g. D — as the validation master plan states it', 'пр. D — како што стои во планот за валидација')}"></div>
      <div class="field"><label>${AL('Department', 'Оддел')}</label>
        ${GF.selectField('pc-dept', { value: r.department_id || '', title: AL('Department', 'Оддел'), searchable: true,
          options: [{ v: '', label: AL('— none —', '— нема —') }].concat(
            (GF.DEPTS || []).map(d => ({ v: d.id, label: GF.depName ? GF.depName(d.id) : d.name, color: d.color }))) })}</div>
      <div class="field"><label>${AL('Room the app schedules', 'Соба што апликацијата планира')}</label>
        ${GF.selectField('pc-room', { value: r.room_id || '', title: AL('Room', 'Соба'), searchable: true,
          options: [{ v: '', label: AL('— none —', '— нема —') }].concat(
            rooms.map(x => ({ v: x.id, label: roomName(x) }))) })}</div>
      <div class="field"><label>${AL('Note', 'Белешка')}</label>
        <textarea id="pc-note" rows="2" maxlength="2000">${GF.esc(r.notes || '')}</textarea></div>
      <button class="btn btn-primary" style="width:100%;justify-content:center"
        onclick="GF.WWF.savePlanClassify('${r.id}')">${GF.t('save')}</button>`;
    GF.openModal('fac-plancls-modal');
  };

  GF.WWF.savePlanClassify = async (id) => {
    const val = (k) => { const el = GF.$(k); return el ? el.value : ''; };
    const body = { regime: val('pc-regime') || null, grade: val('pc-grade').trim() || null,
                   department_id: val('pc-dept') || null, room_id: val('pc-room') || null,
                   notes: val('pc-note').trim() || null };
    try {
      await GF.API.facilityLayoutPatch(id, body);
      GF.closeModal('fac-plancls-modal');
      GF.toast(GF.t('save') + ' ✓', 'success');
      GF.WWF.loadPlan();
    } catch (e) { GF.toast(AL('Save failed: ', 'Неуспешно зачувување: ') + e.message, 'error'); }
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
