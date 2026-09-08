/* cultivation-view.js — the cultivation department's identity board.

   The Facility board answers "what is in each room right now". This board
   answers the question the owner's scheme actually asks: WHICH cultivar, in
   WHICH coded batch, made up of WHICH individually numbered plants, and where
   has that batch been. It is the UI over app/api/cultivation.py (migration
   0045): the cultivar master, coded batches (GP072501), the per-plant roster
   (<clone-date>_<cultivar>_<seq>), and dated whole-batch phase moves.

   Read: every role above base USER. Write (register a cultivar, move a
   batch): cultivation manager + executives + ADMIN. REGISTER a batch and
   generate its plant ids: those PLUS the QA manager — the owner's model
   (2026-09-05) is that QA, the CEO, the COO and the cultivation manager can
   register a batch; the same set initiates a clone run (propagation-view.js).
   Both sets mirror what the server enforces (_WRITERS / _REGISTRARS in
   app/api/cultivation.py).

   REGISTERING FROM THE PRODUCT SPECIFICATION. The batch form picks its
   cultivar from the ImB Product Specifications — each cultivar arrives with
   its potency ladder (strain name + grades), shown under the chooser — and
   the batch number is pre-filled from the server's suggestion with the
   cultivar code as its fixed head (GF.codeField).

   THE JOURNEY STRIP. When a batch is registered it appears at the top of the
   board as an animated bar: where the batch is on the cultivation →
   production plan, how long it has been there, and what the next step is
   (and whose it is — the harvest cut is where cultivation hands over to
   production). Position comes from the batch's phase, nothing else; the
   plan's phase DURATIONS are not known to the app yet, so the bar shows
   position and elapsed days and makes no promise about dates.

   TWO SERVER RULES THIS VIEW RESPECTS RATHER THAN REIMPLEMENTS:

   1. Phase lives on the BATCH, never on the plant. A flowering room holds
      ~2000 plants and every audited write takes one global advisory lock until
      commit, so a room move is ONE batch update plus ONE phase event. This
      view therefore offers "move batch" and has no per-plant phase control at
      all — the absence is the design, not an omission.
   2. Materialising plant rows is CHUNKED AND RESUMABLE server-side. This view
      calls it in a loop until the server reports complete, because a proxy
      timeout mid-fill is the expected failure and resuming is exactly what the
      endpoint is built for. The loop stops the moment a call creates nothing,
      so a genuinely stuck fill surfaces instead of spinning.

   Terminal phases are the one place this view adds friction of its own: moving
   to harvested/destroyed also settles every still-active plant in the batch
   and cannot be moved again, so it is confirmed in a modal that says so.

   Same monkey-patch/view pattern as the other *-view.js files; loads after
   worklog.js (uses AL(), GF.WWF._ensureModal, GF.selectField). */

(function () {
  GF.WWF._cult = {
    batches: null, cultivars: null, loading: false, error: null,
    showClosed: false,
    plants: null,        // { batchId, code, total, offset, rows }
    filling: null,       // batch id currently being materialised
    tasks: null,          // { batchId, code, rows } — Phase 3 (migration 0054)
    tab: 'batches',       // 'batches' | 'clones' | 'mothers' (the latter two render from propagation-view.js)
    focus: null,          // batch id the journey strip follows: the last registered, else the newest open one
    runs: null,           // clone runs (all), so the strip can say which run a batch was cut in
  };

  // Must stay in step with _PHASES in app/api/cultivation.py and the
  // plant_batches_phase_check in migration 0045.
  const PHASES = [
    { key: 'nursery',   en: 'Nursery',    mk: 'Расадник',   color: '#2FD9D9' },
    { key: 'clone',     en: 'Clones',     mk: 'Клонови',    color: '#2BE8A0' },
    { key: 'veg',       en: 'Vegetation', mk: 'Вегетација', color: '#3FA34D' },
    { key: 'flower',    en: 'Flowering',  mk: 'Цветање',    color: '#E0A73E' },
    { key: 'mother',    en: 'Mothers',    mk: 'Мајки',      color: '#C89BF0' },
    { key: 'drying',    en: 'Drying',     mk: 'Сушење',     color: '#8296B4' },
    { key: 'harvested', en: 'Harvested',  mk: 'Ожнеано',    color: '#5B7A9E' },
    { key: 'destroyed', en: 'Destroyed',  mk: 'Уништено',   color: '#E5484D' },
  ];
  const TERMINAL = ['harvested', 'destroyed'];
  const PH = {}; PHASES.forEach(p => { PH[p.key] = p; });
  const phLbl = (p) => AL(PH[p]?.en || p, PH[p]?.mk || p);
  const phCol = (p) => (PH[p] || {}).color || 'var(--ink-3)';

  const PLANT_STATUS = {
    active:    { en: 'Active',    mk: 'Активно',  color: '#2BE8A0' },
    culled:    { en: 'Culled',    mk: 'Отфрлено', color: '#E0A73E' },
    destroyed: { en: 'Destroyed', mk: 'Уништено', color: '#E5484D' },
    harvested: { en: 'Harvested', mk: 'Ожнеано',  color: '#5B7A9E' },
    moved:     { en: 'Moved',     mk: 'Преместено', color: '#8296B4' },
  };

  const role = () => (GF.API.user || {}).role;
  // Mirrors _WRITERS in app/api/cultivation.py. QA joined the floor writers on
  // 2026-09-05: "QA should be able to move a batch through its phases or edit
  // the cultivar master".
  const canWrite = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'CU_MGR', 'QA_MGR'].includes(role());
  const canRegister = canWrite;
  // Mirrors CultivarIn.code / BatchIn.code server-side, so a bad code is
  // rejected before a round trip rather than as a bare 422.
  const CODE_RE = /^[A-Za-z0-9_-]{1,64}$/;
  // Elapsed days counted on the FACILITY's day, not the browser's: the board
  // compares this with windows the server computed from its own clock, and two
  // clocks disagreeing for an hour or two every night would show a wrong answer
  // rather than an off-by-one nobody notices.
  const daysIn = (iso) => {
    if (!iso) return null;
    return Math.max(0, Math.round(
      (new Date(GF.facilityToday() + 'T00:00:00') - new Date(iso + 'T00:00:00')) / 864e5));
  };
  const dm = (iso) => (iso ? (GF.fmtDateHuman ? GF.fmtDateHuman(iso).slice(0, 5) : iso.slice(5)) : '');
  // FACILITY today, not UTC. This value is printed into every plant id in
  // the batch (see the note under the field), and toISOString() renders the
  // UTC day — so between facility-midnight and UTC-midnight every plant
  // created here was stamped with YESTERDAY.
  const today = () => GF.facilityToday();

  GF.WWF.loadCultivation = async () => {
    const st = GF.WWF._cult;
    st.loading = true; st.error = null;
    try {
      const [b, cv] = await Promise.all([
        GF.API.cultivationBatches(!st.showClosed),
        GF.API.cultivars(),
      ]);
      st.batches = b.batches || [];
      st.cultivars = cv.cultivars || [];
      // Clone runs are a separate module (propagation-view.js); the strip only
      // needs to know which run fed a batch, so a missing API is not an error.
      try { st.runs = GF.API.cloneRuns ? ((await GF.API.cloneRuns(false)).runs || []) : []; }
      catch (_) { st.runs = []; }
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'cultivation') GF.render.all();
  };

  // ── batch card ────────────────────────────────────────────────────────────

  // The headcount line is the one number the owner's scheme is about, and it
  // has THREE distinct values that are routinely confused: the planned count on
  // the batch, how many plant ids actually exist, and how many of those are
  // still alive. Showing one number would hide an incomplete fill.
  const headcount = (b) => {
    const planned = b.plant_count || 0;
    const made = b.plants_materialised || 0;
    const alive = b.plants_active || 0;
    const short = made < planned;
    const parts = [
      `<strong>${planned}</strong> ${AL('planned', 'планирани')}`,
      `<span style="color:${short ? '#E0A73E' : 'var(--ink-3)'}">${made} ${AL('id’d', 'со ID')}</span>`,
    ];
    if (made) parts.push(`<span style="color:#2BE8A0">${alive} ${AL('active', 'активни')}</span>`);
    return parts.join(' · ');
  };

  const batchCard = (b) => {
    const d = daysIn(b.phase_since);
    const terminal = TERMINAL.includes(b.phase);
    const made = b.plants_materialised || 0;
    const planned = b.plant_count || 0;
    const filling = GF.WWF._cult.filling === b.id;
    const actions = [];
    if (canRegister() && !terminal && made < planned) {
      actions.push(`<button class="btn btn-sm" id="cu-fill-${b.id}" ${filling ? 'disabled' : ''}
        onclick="GF.WWF.cultFillPlants('${b.id}')">${GF.icon('layers', 'icon')}${
        filling
          ? AL('Generating…', 'Генерирање…')
          : AL(`Generate ${planned - made} plant ids`, `Генерирај ${planned - made} ID`)}</button>`);
    }
    if (made) {
      actions.push(`<button class="btn btn-sm" onclick="GF.WWF.cultPlantList('${b.id}','${GF.esc(b.code)}')">
        ${GF.icon('file', 'icon')}${AL('Plant roster', 'Список на растенија')}</button>`);
    }
    // Phase 3 (migration 0054): the tasks that reference this batch, whether
    // auto-generated on a phase move or hand-linked via the task form. Shown
    // regardless of plant fill — a task can carry batch_id before any plant
    // id exists.
    actions.push(`<button class="btn btn-sm" onclick="GF.WWF.cultTaskList('${b.id}','${GF.esc(b.code)}')">
      ${GF.icon('menu', 'icon')}${AL('Batch tasks', 'Задачи на батч')}</button>`);
    // The documented record the owner's rule makes the decider of a cut.
    if (canWrite() && b.phase === 'flower') {
      actions.push(`<button class="btn btn-sm" onclick="GF.WWF.trichomeForm('${b.id}','${GF.esc(b.code)}')">
        ${GF.icon('eye', 'icon')}${AL('Trichome check', 'Проверка на трихоми')}</button>`);
    }
    if (canWrite() && !terminal) {
      actions.push(`<button class="btn btn-sm" onclick="GF.WWF.cultMoveForm('${b.id}')">
        ${GF.icon('forward', 'icon')}${AL('Move / advance', 'Премести / фаза')}</button>`);
    }
    // A batch with no cultivar cannot form plant ids at all (the server returns
    // 422). Say that on the card instead of letting the operator find out.
    const noCultivar = !b.cultivar_id
      ? `<div style="color:var(--red);font-size:11px;margin-bottom:6px">${AL(
          'No cultivar on this batch — plant ids cannot be formed until one is set.',
          'Батчот е без сорта — ID на растенија не може да се формираат.')}</div>`
      : '';
    return `<div class="card" style="padding:12px;margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <strong style="flex:1">${GF.esc(b.code || '—')}</strong>
        <span style="color:${phCol(b.phase)};font-size:12px">${GF.esc(phLbl(b.phase))}</span>
      </div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:6px">
        ${GF.esc(b.product_code || b.cultivar_code || b.strain || '—')}${b.cultivar_name ? ' · ' + GF.esc(b.cultivar_name) : ''}
        · ${GF.esc(b.room_name || AL('no room', 'без соба'))}
        ${d != null ? ` · ${d} ${AL('d in phase', 'д. во фаза')}` : ''}
      </div>
      ${noCultivar}
      ${GF.WWF.cultJourney(b, { compact: true })}
      ${GF.WWF.cultExpectLine(b) ? `<div class="cj-x">${GF.WWF.cultExpectLine(b)}</div>` : ''}
      <div style="font-size:12px;margin-bottom:8px">${headcount(b)}</div>
      ${b.note ? `<div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${GF.esc(b.note)}</div>` : ''}
      <div style="display:flex;gap:6px;flex-wrap:wrap">${actions.join('')}</div>
    </div>`;
  };

  // ── view ──────────────────────────────────────────────────────────────────

  GF.views.cultivation = () => {
    const st = GF.WWF._cult;
    if (!st.batches && !st.loading && !st.error) GF.WWF.loadCultivation();
    const right = [
      canWrite() ? `<button class="btn btn-sm" onclick="GF.WWF.cultCultivarList()">${GF.icon('leaf', 'icon')}${AL('Cultivars', 'Сорти')}</button>` : '',
      canRegister() && GF.WWF.cloneRunForm
        ? `<button class="btn btn-sm" onclick="GF.WWF.cloneRunForm()">${GF.icon('layers', 'icon')}${AL('Start clone run', 'Почни клонирање')}</button>` : '',
      canRegister()
        ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.cultBatchForm()">${GF.icon('plus', 'icon', 'currentColor')}${AL('Register batch', 'Регистрирај батч')}</button>` : '',
    ].join('');
    const head = GF.viewHead
      ? GF.viewHead('cultivation', 'cultivation_sub', right)
      : `<div class="view-head"><h2>${AL('Cultivation', 'Одгледување')}</h2>${right}</div>`;
    if (st.loading && !st.batches) return head + `<div class="ntf-empty">${AL('Loading…', 'Вчитување…')}</div>`;
    if (st.error) return head + `<div class="ntf-empty">${GF.esc(st.error)}</div>`;
    const batches = st.batches || [];
    const toggle = `<label style="display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--ink-3);cursor:pointer">
      <input type="checkbox" ${st.showClosed ? 'checked' : ''} onchange="GF.WWF.cultToggleClosed()">
      ${AL('include closed batches', 'вклучи затворени батчови')}</label>`;
    // An empty board still has its tabs: the mother bank and the clone runs
    // are exactly what gets filled BEFORE the first batch exists.
    if (!batches.length && st.tab === 'batches') {
      return head + tabs(batches) + `<div style="margin-bottom:10px">${toggle}</div>` + `<div class="ntf-empty">${AL(
        'No batches yet. A batch is one cultivar in one room — register the cultivar first, then register the batch from its product specification and generate its plant ids.',
        'Нема батчови. Батч е една сорта во една соба — прво регистрирајте сорта, потоа регистрирајте батч од нејзината спецификација и генерирајте ID на растенијата.')}</div>`;
    }
    // Totals by phase, so the board answers "how many plants are flowering"
    // without anyone adding up cards.
    const tally = {};
    let plannedAll = 0, madeAll = 0;
    batches.forEach(b => {
      tally[b.phase] = (tally[b.phase] || 0) + (b.plant_count || 0);
      plannedAll += b.plant_count || 0;
      madeAll += b.plants_materialised || 0;
    });
    const chips = PHASES.filter(p => tally[p.key]).map(p =>
      `<span style="display:inline-flex;gap:5px;align-items:center;margin-right:12px;font-size:12px">
        <span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
        ${GF.esc(AL(p.en, p.mk))} <strong>${tally[p.key]}</strong></span>`).join('');
    const gap = plannedAll > madeAll
      ? `<div style="color:#E0A73E;font-size:11px;margin-top:4px">${AL(
          `${plannedAll - madeAll} planned plants have no id yet`,
          `${plannedAll - madeAll} планирани растенија се уште без ID`)}</div>`
      : '';
    const summary = `<div style="margin-bottom:12px">
      <div style="margin-bottom:6px">${chips}</div>${gap}
      <div style="margin-top:6px">${toggle}</div></div>`;
    // Grouped by phase in the plan's own order, so the board reads as the crop
    // moves rather than as an alphabetical list of codes.
    const groups = PHASES.filter(p => batches.some(b => b.phase === p.key)).map(p => {
      const mine = batches.filter(b => b.phase === p.key);
      return `<div style="margin-bottom:6px">
        <div style="font-size:12px;color:${p.color};margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px">
          ${GF.esc(AL(p.en, p.mk))} <span style="color:var(--ink-3)">(${mine.length})</span></div>
        ${mine.map(batchCard).join('')}</div>`;
    }).join('');
    const body = st.tab === 'batches'
      ? summary + groups
      : (GF.WWF.propagationSection ? GF.WWF.propagationSection(st.tab) : '');
    return head + journeyLanes(batches) + tabs(batches) + body;
  };

  // ── the journey strip ─────────────────────────────────────────────────────
  //
  // The plan as a line: where cultivation's work ends and production's begins
  // is the harvest cut (roles.py, harvest.py). A step's `who` names the
  // department whose step it is; the handoff is drawn at the cut. Position is
  // read from the batch's phase; a step the batch has passed is filled whether
  // or not it stopped there (a batch may go clone → veg without a nursery
  // stop — the plan still shows nursery as behind it). Durations are NOT in
  // this list on purpose: the app has not been told the plan's phase lengths,
  // and a bar that guessed them would be a schedule nobody set.
  const PLAN = [
    { key: 'registered', en: 'Registered',    mk: 'Регистриран',  who: 'cultivation' },
    { key: 'clone',      en: 'Clones',        mk: 'Клонови',      who: 'cultivation' },
    { key: 'nursery',    en: 'Nursery',       mk: 'Расадник',     who: 'cultivation' },
    { key: 'veg',        en: 'Vegetation',    mk: 'Вегетација',   who: 'cultivation' },
    { key: 'flower',     en: 'Flowering',     mk: 'Цветање',      who: 'cultivation' },
    // Harvest, cure and defoliation are one step and one boundary: the end of
    // GACP and the start of GMP (owner, 2026-09-05).
    { key: 'cut', en: 'Harvest · cure · defoliation', mk: 'Жетва · сушење · дефолијација',
      sub: 'GACP → GMP', who: 'cultivation', handoff: true },
    { key: 'drying',     en: 'Drying',        mk: 'Сушење',       who: 'production' },
    { key: 'closed',     en: 'Lot closed',    mk: 'Затворена серија', who: 'production' },
  ];
  const PLAN_POS = { clone: 1, nursery: 2, veg: 3, flower: 4, drying: 6, harvested: 7 };
  const WHO = {
    cultivation: { en: 'cultivation', mk: 'одгледување', color: '#3FA34D' },
    production:  { en: 'production',  mk: 'производство', color: '#E0A73E' },
  };

  // Which clone run fed this batch, if the propagation record says so.
  const runFor = (b) => ((GF.WWF._cult.runs || []).find(r => r.batch_id === b.id) || null);

  GF.WWF.cultJourney = (b, opts = {}) => {
    const compact = !!opts.compact;
    // Mother stock is not on the production path, and a destroyed batch has
    // left it: neither is drawn as "somewhere along the plan".
    if (b.phase === 'destroyed') {
      return compact ? '' : `<div class="cj cj-off">${AL('This batch was destroyed and has left the plan.', 'Овој батч е уништен и не е на планот.')}</div>`;
    }
    if (b.phase === 'mother') {
      return compact ? '' : `<div class="cj cj-off">${AL('Mother stock — kept, not grown out. See the mother bank.', 'Мајки — се чуваат, не се одгледуваат. Видете банка на мајки.')}</div>`;
    }
    const pos = PLAN_POS[b.phase] != null ? PLAN_POS[b.phase] : 0;
    const last = PLAN.length - 1;
    const pct = Math.round((pos / last) * 100);
    const cur = PLAN[pos], next = PLAN[pos + 1] || null;
    const d = daysIn(b.phase_since);
    const dots = PLAN.map((s, i) => {
      const cls = i < pos ? 'cj-done' : i === pos ? 'cj-now' : 'cj-todo';
      const who = WHO[s.who];
      return `<div class="cj-step ${cls}${s.handoff ? ' cj-handoff' : ''}" style="--cj-who:${who.color}" title="${GF.esc(AL(s.en, s.mk))} · ${GF.esc(AL(who.en, who.mk))}">
        <span class="cj-dot"></span>${compact ? '' : `<span class="cj-lbl">${GF.esc(AL(s.en, s.mk))}</span>`}</div>`;
    }).join('');
    const track = `<div class="cj-track${compact ? ' cj-track-sm' : ''}">
      <div class="cj-rail"></div>
      <div class="cj-fill" data-w="${pct}" style="width:0%"></div>
      <div class="cj-steps">${dots}</div></div>`;
    if (compact) return `<div class="cj cj-sm">${track}</div>`;
    const nowWho = WHO[cur.who], nextWho = next ? WHO[next.who] : null;
    const nowLine = `<span class="cj-now-lbl" style="--cj-who:${nowWho.color}">${GF.esc(AL(cur.en, cur.mk))}</span>
      ${b.room_name ? ` · ${GF.esc(b.room_name)}` : ''}${d != null ? ` · ${d} ${AL('d in phase', 'д. во фаза')}` : ''}`;
    const nextLine = next
      ? `${AL('Next', 'Следно')}: <b style="color:${nextWho.color}">${GF.esc(AL(next.en, next.mk))}</b>
         <span style="color:var(--ink-3)">· ${next.handoff
           ? AL('cultivation records the cut, then production takes the lot', 'одгледувањето го запишува сечењето, потоа серијата е на производството')
           : GF.esc(AL(nextWho.en, nextWho.mk))}</span>`
      : `<span style="color:var(--ink-3)">${AL('The lot is closed — nothing follows on this plan.', 'Серијата е затворена — нема следен чекор.')}</span>`;
    const run = runFor(b);
    const runLine = run
      ? `<div class="cj-run">${GF.icon('layers', 'icon')}${AL('Cut in clone run', 'Клонирано во')} ${GF.esc(run.code || (run.cultivar_code + ' · ' + (GF.fmtDateHuman ? GF.fmtDateHuman(run.started_on) : run.started_on)))}
         · ${run.mothers.length} ${AL('mothers', 'мајки')}${run.cuttings_total ? ` · ${run.cuttings_total} ${AL('cuttings', 'резници')}` : ''}${
         run.product_code ? ` · ${GF.esc(run.product_code)}` : ''}</div>`
      : '';
    return `<div class="cj">
      <div class="cj-head">
        <strong>${GF.esc(b.code || '—')}</strong>
        <span style="color:var(--ink-3)">${GF.esc(b.cultivar_code || b.strain || '—')}${b.cultivar_name ? ' · ' + GF.esc(b.cultivar_name) : ''} · ${b.plant_count || 0} ${AL('plants', 'растенија')}</span>
        ${b.product_code ? `<span class="mw-attr">${GF.esc(b.product_code)}</span>` : ''}
        ${b.clone_source ? `<span class="mw-attr">${GF.esc(b.clone_source === 'imported' ? AL('imported clones', 'увезени клонови') : AL('own stock', 'сопствен фонд'))}</span>` : ''}
        <span class="spacer"></span>
        <span class="cj-legend"><i style="background:${WHO.cultivation.color}"></i>${AL('cultivation', 'одгледување')} <i style="background:${WHO.production.color}"></i>${AL('production', 'производство')}</span>
      </div>
      ${track}
      <div class="cj-foot"><div>${AL('Now', 'Сега')}: ${nowLine}</div><div>${nextLine}</div></div>
      ${GF.WWF.cultExpectLine(b) ? `<div class="cj-x">${GF.WWF.cultExpectLine(b)}</div>` : ''}
      ${runLine}
    </div>`;
  };

  // What the plan expects next, in dates the SERVER computed. The board never
  // derives an interval of its own: one copy of the plan, the same discipline
  // the pre-harvest interval keeps.
  const STATE_CLS = { early: 'cj-x-early', in_window: 'cj-x-in', late: 'cj-x-late' };
  GF.WWF.cultExpectLine = (b) => {
    const tc = b.latest_trichome;
    const trich = b.phase === 'flower'
      ? (tc
        ? `<span class="cj-x-t">${AL('trichomes', 'трихоми')}: <b>${GF.esc(tc.verdict)}</b> · ${dm(tc.checked_on)}</span>`
        : `<span class="cj-x-none">${AL('no trichome check recorded', 'нема запис за трихоми')}</span>`)
      : '';
    if (!b.expected_from) return trich;
    const cls = STATE_CLS[b.window_state] || '';
    const what = b.phase === 'flower'
      ? AL('harvest window', 'прозорец за жетва')
      : `→ ${GF.esc(AL((PH[b.expected_next_phase] || {}).en || b.expected_next_phase || '',
                       (PH[b.expected_next_phase] || {}).mk || b.expected_next_phase || ''))} ${AL('expected', 'очекувано')}`;
    return `<span class="${cls}">${what} ${dm(b.expected_from)}–${dm(b.expected_to)}</span>${
      trich ? ' · ' + trich : ''}`;
  };

  // One lane per open batch on a shared axis — "there may be multiple
  // operations at the same time at different stages" (owner, 2026-09-05). The
  // focused lane opens into the full detail below; the rest stay one line each.
  const journeyLanes = (batches) => {
    const st = GF.WWF._cult;
    const open = batches.filter(b => !TERMINAL.includes(b.phase) && b.phase !== 'mother');
    if (!open.length) return '';
    const focused = open.find(x => x.id === st.focus) || open[0];
    const axis = `<div class="cj-axis">${PLAN.map(s =>
      `<span>${GF.esc(AL(s.en, s.mk))}</span>`).join('')}</div>`;
    const lane = (b) => {
      const pos = PLAN_POS[b.phase] != null ? PLAN_POS[b.phase] : 0;
      const pct = Math.round((pos / (PLAN.length - 1)) * 100);
      const dots = PLAN.map((s, i) => {
        const cls = i < pos ? 'cj-done' : i === pos ? 'cj-now' : 'cj-todo';
        return `<div class="cj-step ${cls}${s.handoff ? ' cj-handoff' : ''}" style="--cj-who:${WHO[s.who].color}"><span class="cj-dot"></span></div>`;
      }).join('');
      return `<div class="cj-lane${b.id === focused.id ? ' on' : ''}" onclick="GF.WWF.cultFocus('${b.id}')">
        <div class="cj-lane-id"><strong>${GF.esc(b.code || '—')}</strong>
          <div class="sub">${GF.esc(b.product_code || b.cultivar_code || b.strain || '—')} · ${b.plant_count || 0} ${AL('plants', 'растенија')}${
            b.room_name ? ' · ' + GF.esc(b.room_name) : ''}</div></div>
        <div class="cj-track cj-track-sm"><div class="cj-rail"></div>
          <div class="cj-fill" data-w="${pct}" style="width:0%"></div>
          <div class="cj-steps">${dots}</div></div>
        <div class="cj-lane-x">${GF.WWF.cultExpectLine(b)}</div>
      </div>`;
    };
    // The fills are set to their widths one frame after insertion so they
    // animate from where the previous render left them, not at rest.
    setTimeout(GF.WWF._cultAnimate, 30);
    return `<div class="cj-lanes">${axis}${open.map(lane).join('')}</div>`
      + `<div class="cj-wrap">${GF.WWF.cultJourney(focused)}</div>`;
  };
  GF.WWF._cultAnimate = () => {
    if (typeof document === 'undefined') return;
    document.querySelectorAll('.cj-fill[data-w]').forEach(el => { el.style.width = el.getAttribute('data-w') + '%'; });
  };
  GF.WWF.cultFocus = (id) => { GF.WWF._cult.focus = id; GF.render.all(); };

  const tabs = (batches) => {
    const st = GF.WWF._cult;
    const pr = GF.WWF._prop || {};
    const t = (key, label, n) => `<button class="cj-tab${st.tab === key ? ' on' : ''}" onclick="GF.WWF.cultTab('${key}')">${label}${n != null ? ` <span>${n}</span>` : ''}</button>`;
    return `<div class="cj-tabs">
      ${t('batches', AL('Batches', 'Батчови'), batches.length)}
      ${t('clones', AL('Clone runs', 'Клонирања'), pr.runs ? pr.runs.length : null)}
      ${t('mothers', AL('Mother bank', 'Банка на мајки'), pr.mothers ? pr.mothers.length : null)}
    </div>`;
  };
  GF.WWF.cultTab = (key) => {
    GF.WWF._cult.tab = key;
    if (key !== 'batches' && GF.WWF.loadPropagation && !(GF.WWF._prop || {}).mothers) GF.WWF.loadPropagation();
    GF.render.all();
  };

  GF.WWF.cultToggleClosed = () => {
    const st = GF.WWF._cult;
    st.showClosed = !st.showClosed;
    st.batches = null;
    GF.WWF.loadCultivation();
  };

  // ── materialise plant ids ─────────────────────────────────────────────────

  // The server fills in chunks and reports {created, materialised, complete}.
  // This loops until it says complete, because the whole point of a resumable
  // endpoint is that a cut-off call is resumed rather than restarted. It stops
  // on a call that created nothing — otherwise a batch the server refuses to
  // fill any further would spin forever.
  GF.WWF.cultFillPlants = async (batchId) => {
    if (!canWrite()) return;
    const st = GF.WWF._cult;
    if (st.filling) return;                       // one fill at a time
    st.filling = batchId;
    if (GF.state.view === 'cultivation') GF.render.all();
    let total = 0, rounds = 0;
    try {
      for (;;) {
        const r = await GF.API.cultivationGenPlants(batchId);
        total += r.created || 0;
        rounds += 1;
        if (r.complete) break;
        if (!r.created) {
          GF.toast(AL(
            `Stopped at ${r.materialised}/${r.target} — the server created nothing on the last call`,
            `Прекинато на ${r.materialised}/${r.target} — серверот не создаде ништо`), 'error');
          break;
        }
        if (rounds > 200) {                       // belt and braces on the loop
          GF.toast(AL('Stopped after 200 rounds — check the batch',
                      'Прекинато по 200 круга — проверете го батчот'), 'error');
          break;
        }
      }
      if (total) {
        GF.toast(AL(`${total} plant ids generated`, `${total} ID на растенија генерирани`), 'success');
      }
    } catch (e) {
      // A partial fill is still valid and resumable — say so, so nobody assumes
      // the batch has to be recreated.
      GF.toast(e.message + AL(' — the fill is resumable; press again to continue',
                              ' — полнењето продолжува; притиснете повторно'), 'error');
    }
    st.filling = null;
    await GF.WWF.loadCultivation();
  };

  // ── plant roster ──────────────────────────────────────────────────────────

  const PAGE = 200;

  GF.WWF.cultPlantList = async (batchId, code, offset = 0) => {
    let r;
    try { r = await GF.API.cultivationPlants(batchId, { limit: PAGE, offset }); }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._cult.plants = { batchId, code, total: r.total, offset, rows: r.plants || [] };
    GF.WWF._ensureModal('cu-plants-modal', '560px');
    GF.$('cu-plants-modal-title').textContent =
      AL('Plant roster', 'Список на растенија') + ' — ' + code;
    GF.WWF._cultRenderPlants();
    GF.openModal('cu-plants-modal');
  };

  GF.WWF._cultRenderPlants = () => {
    const p = GF.WWF._cult.plants; if (!p) return;
    const body = GF.$('cu-plants-modal-body'); if (!body) return;
    const from = p.total ? p.offset + 1 : 0;
    const to = Math.min(p.offset + PAGE, p.total);
    const rows = p.rows.map(x => {
      const s = PLANT_STATUS[x.status] || {};
      return `<div style="display:flex;gap:8px;align-items:center;padding:4px 0;border-bottom:1px solid var(--line)">
        <span style="color:var(--ink-3);font-size:11px;min-width:38px">#${x.seq}</span>
        <strong style="flex:1;font-family:var(--mono,monospace);font-size:12px">${GF.esc(x.plant_code)}</strong>
        <span style="color:${s.color || 'var(--ink-3)'};font-size:11px;min-width:70px">${
          GF.esc(AL(s.en || x.status, s.mk || x.status))}</span>
        <span style="color:var(--ink-3);font-size:11px">${GF.esc(x.clone_date || '')}</span>
      </div>`;
    }).join('');
    const nav = [];
    if (p.offset > 0) {
      nav.push(`<button class="btn btn-sm" onclick="GF.WWF.cultPlantList('${p.batchId}','${GF.esc(p.code)}',${Math.max(0, p.offset - PAGE)})">${AL('Previous', 'Претходно')}</button>`);
    }
    if (to < p.total) {
      nav.push(`<button class="btn btn-sm" onclick="GF.WWF.cultPlantList('${p.batchId}','${GF.esc(p.code)}',${p.offset + PAGE})">${AL('Next', 'Следно')}</button>`);
    }
    body.innerHTML = `<div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">
        ${from}–${to} ${AL('of', 'од')} ${p.total}</div>
      ${rows || `<div class="ntf-empty">${AL('No plant ids yet', 'Нема ID на растенија')}</div>`}
      ${nav.length ? `<div class="row" style="gap:8px;margin-top:10px">${nav.join('')}</div>` : ''}`;
  };

  // Phase 3 (migration 0054): the "batch record accumulates from work
  // actually performed" half of the design doc — every task carrying this
  // batch's id, whether auto-generated on a phase move or hand-linked
  // through the ordinary task form. Read-only here; no separate offset
  // paging like the plant roster, since a batch's task set is small (a
  // handful of generated tasks per phase plus whatever was hand-linked).
  const TASK_STATUS = {
    pending:   { en: 'Pending',   mk: 'Чека',      color: 'var(--ink-3)' },
    ongoing:   { en: 'Ongoing',   mk: 'Во тек',    color: '#3FA34D' },
    review:    { en: 'Review',    mk: 'Преглед',   color: '#E0A73E' },
    stuck:     { en: 'Stuck',     mk: 'Заглавено', color: '#E5484D' },
    postponed: { en: 'Postponed', mk: 'Одложено',  color: '#8296B4' },
    completed: { en: 'Completed', mk: 'Завршено',  color: '#2BE8A0' },
  };

  GF.WWF.cultTaskList = async (batchId, code) => {
    let r;
    try { r = await GF.API.cultivationBatchTasks(batchId); }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._cult.tasks = { batchId, code, rows: r.tasks || [] };
    GF.WWF._ensureModal('cu-tasks-modal', '520px');
    GF.$('cu-tasks-modal-title').textContent =
      AL('Batch tasks', 'Задачи на батч') + ' — ' + code;
    GF.WWF._cultRenderTasks();
    GF.openModal('cu-tasks-modal');
  };

  GF.WWF._cultRenderTasks = () => {
    const t = GF.WWF._cult.tasks; if (!t) return;
    const body = GF.$('cu-tasks-modal-body'); if (!body) return;
    const rows = t.rows.map(x => {
      const s = TASK_STATUS[x.status] || {};
      // phase_gen marks an auto-generated task (see _generate_phase_tasks) —
      // shown as a small tag so a grower can tell it apart from one they
      // typed by hand, same distinction the design doc draws.
      const gen = x.phase_gen
        ? `<span style="color:var(--ink-3);font-size:10px;border:1px solid var(--line);border-radius:4px;padding:0 4px">${GF.esc(x.phase_gen)}</span>`
        : '';
      return `<div style="display:flex;gap:8px;align-items:center;padding:4px 0;border-bottom:1px solid var(--line)">
        <span style="flex:1;font-size:12px">${GF.esc(x.title)}</span>
        ${gen}
        <span style="color:${s.color || 'var(--ink-3)'};font-size:11px;min-width:70px;text-align:right">${
          GF.esc(AL(s.en || x.status, s.mk || x.status))}</span>
      </div>`;
    }).join('');
    body.innerHTML = rows || `<div class="ntf-empty">${AL(
      'No tasks linked to this batch yet — one is created automatically on the next veg/flower move, or link one by hand from the task form.',
      'Сè уште нема задачи поврзани со овој батч — се создава автоматски при следното преместување во вег/цвет, или поврзете рачно од формата за задача.')}</div>`;
  };

  // ── cultivar registry ─────────────────────────────────────────────────────

  GF.WWF.cultCultivarList = () => {
    const st = GF.WWF._cult;
    GF.WWF._ensureModal('cu-cvlist-modal', '520px');
    GF.$('cu-cvlist-modal-title').textContent = AL('Cultivars', 'Сорти');
    const rows = (st.cultivars || []).map(cv => {
      const nm = (GF.state.lang === 'mk' && cv.name_mk) ? cv.name_mk : cv.name;
      const act = canWrite()
        ? `<button class="btn btn-sm" onclick="GF.WWF.cultCultivarForm('${cv.id}')">${GF.t('edit')}</button>`
        : '';
      return `<div style="display:flex;gap:8px;align-items:center;padding:5px 0;border-bottom:1px solid var(--line);${cv.is_active ? '' : 'opacity:.5'}">
        <strong style="min-width:110px">${GF.esc(cv.code)}</strong>
        <span style="flex:1">${GF.esc(nm)}</span>
        ${cv.is_active ? '' : `<span style="color:var(--ink-3);font-size:11px">${AL('retired', 'неактивна')}</span>`}
        ${act}
      </div>`;
    }).join('');
    const add = canWrite()
      ? `<div class="row" style="gap:8px;margin-top:10px"><div class="spacer"></div>
         <button class="btn btn-primary" onclick="GF.WWF.cultCultivarForm(null)">${AL('Register cultivar', 'Регистрирај сорта')}</button></div>`
      : '';
    GF.$('cu-cvlist-modal-body').innerHTML =
      (rows || `<div class="ntf-empty">${AL('No cultivars registered yet', 'Нема регистрирани сорти')}</div>`) + add;
    GF.openModal('cu-cvlist-modal');
  };

  GF.WWF.cultCultivarForm = (cultivarId) => {
    if (!canWrite()) return;
    const cv = cultivarId
      ? (GF.WWF._cult.cultivars || []).find(x => x.id === cultivarId)
      : null;
    GF.WWF._ensureModal('cu-cv-modal', '440px');
    GF.$('cu-cv-modal-title').textContent = cv
      ? AL('Edit cultivar', 'Уреди сорта') + ' — ' + cv.code
      : AL('Register cultivar', 'Регистрирај сорта');
    // The CODE is what every plant id is built from, so it is immutable once a
    // cultivar exists — renaming it would silently orphan the ids already
    // printed on the plants. The display name stays editable.
    GF.$('cu-cv-modal-body').innerHTML = `
      ${cv ? '' : `<div class="field"><label>${AL('Code', 'Код')}</label>
        <input id="cu-cv-code" maxlength="64" placeholder="Bisamber">
        <div style="color:var(--ink-3);font-size:11px;margin-top:3px">${AL(
          'Letters, digits, _ and - only. Every plant id in this cultivar is built from this code, so it cannot be changed later.',
          'Само букви, цифри, _ и -. Секој ID на растение се формира од овој код, па не може да се менува подоцна.')}</div></div>`}
      <div class="field"><label>${AL('Name', 'Име')}</label>
        <input id="cu-cv-name" maxlength="120" value="${cv ? GF.esc(cv.name) : ''}"></div>
      <div class="field"><label>${AL('Name (Macedonian)', 'Име (македонски)')}</label>
        <input id="cu-cv-name-mk" maxlength="120" value="${cv && cv.name_mk ? GF.esc(cv.name_mk) : ''}"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="cu-cv-note" maxlength="500" value="${cv && cv.note ? GF.esc(cv.note) : ''}"></div>
      ${cv ? `<label style="display:flex;gap:8px;align-items:center;font-size:12px;margin-bottom:8px;cursor:pointer">
        <input type="checkbox" id="cu-cv-active" ${cv.is_active ? 'checked' : ''}>
        ${AL('Active — offered when opening a new batch', 'Активна — се предлага при нов батч')}</label>` : ''}
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="cu-cv-save"
          onclick="GF.WWF.cultCultivarSave(${cv ? `'${cv.id}'` : 'null'})">${GF.t('save')}</button>
      </div>`;
    GF.openModal('cu-cv-modal');
    setTimeout(() => { const f = GF.$(cv ? 'cu-cv-name' : 'cu-cv-code'); if (f) f.focus(); }, 60);
  };

  GF.WWF.cultCultivarSave = (cultivarId) => GF.once('cu-cv-save', async () => {
    const name = ((GF.$('cu-cv-name') || {}).value || '').trim();
    const nameMk = ((GF.$('cu-cv-name-mk') || {}).value || '').trim() || null;
    const note = ((GF.$('cu-cv-note') || {}).value || '').trim() || null;
    if (!name) { GF.toast(AL('Name is required', 'Името е задолжително'), 'error'); return; }
    try {
      if (cultivarId) {
        const body = { name, name_mk: nameMk, note };
        const chk = GF.$('cu-cv-active');
        if (chk) body.is_active = !!chk.checked;
        await GF.API.cultivarPatch(cultivarId, body);
      } else {
        const code = ((GF.$('cu-cv-code') || {}).value || '').trim();
        if (!CODE_RE.test(code)) {
          GF.toast(AL('Code must be 1–64 characters: letters, digits, _ or -',
                      'Кодот мора да е 1–64 знаци: букви, цифри, _ или -'), 'error');
          return;
        }
        await GF.API.cultivarCreate({ code, name, name_mk: nameMk, note });
      }
      GF.closeModal('cu-cv-modal');
      GF.toast(AL('Cultivar saved', 'Сортата е зачувана'), 'success');
      await GF.WWF.loadCultivation();
      if (GF.$('cu-cvlist-modal')) GF.WWF.cultCultivarList();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── the official product, as the forms show it ───────────────────────────
  // A cultivar arrives from GET /cultivars with the ImB products it is grown
  // to (approved first, drafts flagged). One line for a chooser's sub-text,
  // one panel under it. No product page yet is said plainly, never drawn as a
  // table with no rows.
  const pct = (v) => (v == null ? '—' : Number(v).toFixed(2));
  const pLabel = (p) => `THC ${GF.esc(String(p.grade))}`;
  const approvedProducts = (cv) => ((cv && cv.products) || []).filter(p => p.status === 'APPROVED');

  GF.WWF.cultSpecLine = (cv) => {
    const ps = (cv && cv.products) || [];
    if (!ps.length) return AL('no product specification yet', 'сè уште без спецификација');
    return ps.map(p => `${pLabel(p)}${p.status === 'DRAFT' ? ' (' + AL('DRAFT', 'НАЦРТ') + ')' : ''}`).join(' · ');
  };

  GF.WWF.cultSpecPanel = (cv, productId) => {
    if (!cv) return '';
    const ps = (cv.products || []);
    if (!ps.length) {
      return `<div class="cu-spec cu-spec-none">${GF.icon('file', 'icon')}${AL(
        `${GF.esc(cv.name)} has no product specification registered yet — its potency grades come from the ImB pages, imported under QC → Product catalogue.`,
        `${GF.esc(cv.name)} сè уште нема регистрирана спецификација — потентните степени доаѓаат од ImB страниците, внесени во QC → Каталог на производи.`)}</div>`;
    }
    const rows = ps.map(p => `<tr${p.id === productId ? ' class="on"' : ''}>
      <td>${GF.esc(p.product_code)}</td><td>${pct(p.window_min)} – ${pct(p.window_max)} %</td>
      <td>${pct(p.nominal_pct)} %</td>
      <td><span class="cu-spec-st ${p.status === 'APPROVED' ? 'ok' : 'draft'}">${
        p.status === 'APPROVED' ? AL('APPROVED', 'ОДОБРЕНА') : AL('DRAFT', 'НАЦРТ')}</span></td></tr>`).join('');
    return `<div class="cu-spec">
      <div class="cu-spec-head"><strong>${GF.esc(cv.name)}</strong>
        <span>${AL('ImB Product Specification · QCSP 001 v.03', 'ImB спецификација · QCSP 001 v.03')}</span></div>
      <table class="cu-spec-t"><thead><tr><th>${AL('Product', 'Производ')}</th>
        <th>${AL('Total Δ9-THC window', 'Прозорец вкупен Δ9-THC')}</th>
        <th>${AL('Nominal', 'Номинално')}</th><th></th></tr></thead><tbody>${rows}</tbody></table>
    </div>`;
  };

  GF.WWF.cultBatchForm = async () => {
    if (!canRegister()) return;
    const st = GF.WWF._cult;
    let rooms = [];
    try { rooms = (await GF.API.facility()).rooms || []; }
    catch (e) { GF.toast(e.message, 'error'); return; }
    const cultivars = (st.cultivars || []).filter(c => c.is_active);
    // Both prerequisites are named specifically, because "cannot open a batch"
    // with no reason is the kind of dead end people work around by inventing a
    // free-text strain — which is what the cultivar master exists to retire.
    if (!cultivars.length) {
      GF.toast(AL('Register a cultivar first — a batch is one cultivar in one room',
                  'Прво регистрирајте сорта — батч е една сорта во една соба'), 'error');
      GF.WWF.cultCultivarList();
      return;
    }
    if (!rooms.length) {
      GF.toast(AL('No rooms configured — add rooms on the Facility board first',
                  'Нема соби — прво додајте соби на Капацитет'), 'error');
      return;
    }
    GF.WWF._ensureModal('cu-batch-modal', '500px');
    GF.$('cu-batch-modal-title').textContent = AL('Register batch', 'Регистрирај батч');
    const nonTerminal = PHASES.filter(p => !TERMINAL.includes(p.key));
    // The cultivar is chosen FROM the product specification: each option
    // carries its grades, and picking one fills the batch number (fixed head
    // = the cultivar code) and the specification panel beneath.
    GF.$('cu-batch-modal-body').innerHTML = `
      <div class="field"><label>${AL('Cultivar', 'Сорта')}</label>
        ${GF.selectField('cu-b-cultivar', { value: cultivars[0].id, title: AL('Cultivar', 'Сорта'), searchable: true,
          options: cultivars.map(c => ({ v: c.id, label: c.code + ' — ' + c.name, sub: GF.WWF.cultSpecLine(c) })),
          onPick: () => GF.WWF._cultBatchCultivarSync() })}</div>
      <div class="field"><label>${AL('Target product — the ImB specification it is grown to', 'Целен производ — ImB спецификација')}</label>
        <div id="cu-b-product-wrap"></div>
        <div id="cu-b-spec"></div></div>
      <div class="field"><label>${AL('Clones from', 'Клонови од')}</label>
        ${GF.selectField('cu-b-source', { value: '', title: AL('Clones from', 'Клонови од'), options: [
          { v: '', label: AL('— not stated —', '— не е наведено —') },
          { v: 'own_stock', label: AL('Own stock', 'Сопствен фонд'), sub: AL('cut from the mother bank', 'сечени од банката на мајки') },
          { v: 'imported', label: AL('Imported', 'Увезени'), sub: AL('may stay longer in cloning for quarantine', 'може да останат подолго за карантин') }] })}</div>
      <div class="field"><label>${AL('Batch number', 'Број на батч')}</label>
        <div id="cu-b-code-wrap">${GF.codeField('cu-b-code', { prefix: cultivars[0].code, maxlength: 64, placeholder: 'GP072501' })}</div>
        <div style="color:var(--ink-3);font-size:11px;margin-top:3px">${AL(
          'The cultivar code is the fixed head; the rest is suggested from the batches already registered and can be edited.',
          'Кодот на сортата е фиксен почеток; остатокот е предложен од веќе регистрираните батчови и може да се измени.')}</div></div>
      <div class="field"><label>${AL('Room', 'Соба')}</label>
        ${GF.selectField('cu-b-room', { value: rooms[0].id, title: AL('Room', 'Соба'),
          options: rooms.map(r => ({ v: r.id, label: r.name })) })}</div>
      <div class="field"><label>${AL('Phase', 'Фаза')}</label>
        ${GF.selectField('cu-b-phase', { value: 'clone', title: AL('Phase', 'Фаза'),
          options: nonTerminal.map(p => ({ v: p.key, label: AL(p.en, p.mk) })) })}</div>
      <div class="field"><label>${AL('Plant count', 'Број на растенија')}</label>
        <input id="cu-b-count" type="number" min="0" max="100000" step="1" placeholder="2000"></div>
      <div class="field"><label>${AL('Clone date', 'Датум на клонирање')}</label>
        ${GF.dateField('cu-b-clone', { value: today(), clearable: false })}
        <div style="color:var(--ink-3);font-size:11px;margin-top:3px">${AL(
          'Plant ids are <clone date>_<cultivar>_<number>, so this date is printed on every plant in the batch.',
          'ID на растение е <датум>_<сорта>_<број>, па овој датум е на секое растение во батчот.')}</div></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="cu-b-note" maxlength="500"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'One batch is one cultivar in one room. If a room holds several cultivars, open a batch per cultivar. The batch record is created immediately; the individual plant ids are generated afterwards from the card.',
        'Еден батч е една сорта во една соба. Ако собата има повеќе сорти, отворете батч за секоја. Записот се создава веднаш; ID на растенијата се генерираат потоа од картичката.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="cu-b-save" onclick="GF.WWF.cultBatchSave()">${GF.t('save')}</button>
      </div>`;
    GF.openModal('cu-batch-modal');
    await GF.WWF._cultBatchCultivarSync();
    setTimeout(() => { const f = GF.$('cu-b-count'); if (f) f.focus(); }, 60);
  };

  // On a cultivar pick: show its specification and ask the server for the
  // next batch number. The chooser assigns the hidden input directly and
  // fires no change event, so this is called from its onPick — the only hook
  // that runs (same lesson as _cultMoveSync).
  GF.WWF._cultBatchCultivarSync = async () => {
    const st = GF.WWF._cult;
    const id = (GF.$('cu-b-cultivar') || {}).value;
    const cv = (st.cultivars || []).find(c => c.id === id);
    // Only APPROVED products may be registered against: a draft page's nominal
    // — the 26 in GP26 — can still change.
    const pw = GF.$('cu-b-product-wrap');
    if (pw) {
      const ps = approvedProducts(cv);
      pw.innerHTML = GF.selectField('cu-b-product', {
        value: '', title: AL('Target product', 'Целен производ'),
        options: [{ v: '', label: AL('— no target product —', '— без целен производ —') }].concat(
          ps.map(p => ({ v: p.id, label: `${cv.code} · ${cv.name} — ${pLabel(p)}`,
                         sub: `${pct(p.window_min)}–${pct(p.window_max)} %` }))),
        onPick: () => { const s = GF.$('cu-b-spec');
                        if (s) s.innerHTML = GF.WWF.cultSpecPanel(cv, (GF.$('cu-b-product') || {}).value); } });
    }
    const spec = GF.$('cu-b-spec');
    if (spec) spec.innerHTML = GF.WWF.cultSpecPanel(cv);
    const wrap = GF.$('cu-b-code-wrap');
    if (!wrap || !cv) return;
    let suggested = '';
    try { suggested = GF.API.cultivationBatchCode ? ((await GF.API.cultivationBatchCode(cv.id)).suggested || '') : ''; }
    catch (_) { suggested = ''; }
    // The pick may have changed again while the request was out.
    if (((GF.$('cu-b-cultivar') || {}).value) !== cv.id) return;
    wrap.innerHTML = GF.codeField('cu-b-code', { prefix: cv.code, value: suggested, maxlength: 64, placeholder: 'GP072501' });
  };

  GF.WWF.cultBatchSave = () => GF.once('cu-b-save', async () => {
    const code = ((GF.$('cu-b-code') || {}).value || '').trim();
    if (!CODE_RE.test(code)) {
      GF.toast(AL('Batch code must be 1–64 characters: letters, digits, _ or -',
                  'Кодот мора да е 1–64 знаци: букви, цифри, _ или -'), 'error');
      return;
    }
    const count = parseInt((GF.$('cu-b-count') || {}).value, 10);
    if (!Number.isFinite(count) || count < 0) {
      GF.toast(AL('Enter the plant count', 'Внесете број на растенија'), 'error'); return;
    }
    const clone = ((GF.$('cu-b-clone') || {}).value || '') || null;
    try {
      const created = await GF.API.cultivationBatchCreate({
        code,
        cultivar_id: (GF.$('cu-b-cultivar') || {}).value,
        product_id: ((GF.$('cu-b-product') || {}).value || '') || null,
        clone_source: ((GF.$('cu-b-source') || {}).value || '') || null,
        room_id: (GF.$('cu-b-room') || {}).value,
        phase: (GF.$('cu-b-phase') || {}).value,
        plant_count: count,
        clone_date: clone,
        phase_since: clone,
        note: ((GF.$('cu-b-note') || {}).value || '').trim() || null,
      });
      GF.closeModal('cu-batch-modal');
      GF.toast(AL('Batch registered — generate its plant ids from the card',
                  'Батчот е регистриран — генерирајте ID од картичката'), 'success');
      // The strip at the top now follows the batch just registered.
      GF.WWF._cult.focus = (created || {}).id || null;
      GF.WWF._cult.tab = 'batches';
      await GF.WWF.loadCultivation();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── move / advance a batch ────────────────────────────────────────────────

  GF.WWF.cultMoveForm = async (batchId) => {
    if (!canWrite()) return;
    const b = (GF.WWF._cult.batches || []).find(x => x.id === batchId);
    if (!b) return;
    let rooms = [];
    try { rooms = (await GF.API.facility()).rooms || []; }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._ensureModal('cu-move-modal', '460px');
    GF.$('cu-move-modal-title').textContent =
      AL('Move batch', 'Премести батч') + ' — ' + b.code;
    // The batch's current phase is excluded: "move to where you already are" is
    // not a transition, and recording it would put a meaningless event in the
    // phase history.
    const targets = PHASES.filter(p => p.key !== b.phase);
    const roomOpts = [{ v: '', label: AL('unchanged — ', 'без промена — ') + (b.room_name || '—') }]
      .concat(rooms.map(r => ({ v: r.id, label: r.name })));
    // GF.selectField renders a HIDDEN input and GF.pickSel assigns .value
    // directly — it fires no 'change' event, so a change listener here would
    // never run and the terminal-phase warning would never appear. The chooser's
    // own onPick callback is the only hook that actually fires.
    const phaseCfg = {
      value: targets[0].key, title: AL('To phase', 'Во фаза'),
      options: targets.map(p => ({ v: p.key, label: AL(p.en, p.mk) })),
      onPick: () => GF.WWF._cultMoveSync(b),
    };
    GF.$('cu-move-modal-body').innerHTML = `
      <div style="color:var(--ink-3);font-size:12px;margin-bottom:10px">
        ${GF.esc(b.cultivar_code || b.strain || '—')} · ${b.plant_count} ${AL('plants', 'растенија')} ·
        ${AL('now', 'сега')} <span style="color:${phCol(b.phase)}">${GF.esc(phLbl(b.phase))}</span>
      </div>
      <div class="field"><label>${AL('To phase', 'Во фаза')}</label>
        ${GF.selectField('cu-m-phase', phaseCfg)}</div>
      <div class="field"><label>${AL('To room', 'Во соба')}</label>
        ${GF.selectField('cu-m-room', { value: '', title: AL('To room', 'Во соба'), options: roomOpts })}</div>
      <div class="field"><label>${AL('Date', 'Датум')}</label>
        ${GF.dateField('cu-m-date', { value: today(), clearable: false })}</div>
      <div class="field"><label>${AL('Reason / note', 'Причина / забелешка')}</label>
        <input id="cu-m-reason" maxlength="500"></div>
      <div id="cu-m-warn" style="display:none;color:var(--red);font-size:12px;margin-bottom:8px"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'The whole batch moves as one record — one phase event, not one per plant. Individual plants are not re-numbered by a move.',
        'Целиот батч се движи како еден запис — еден настан за фаза, не по растение. ID на растенијата не се менуваат.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="cu-m-save"
          onclick="GF.WWF.cultMoveSave('${batchId}')">${AL('Record move', 'Запиши')}</button>
      </div>`;
    GF.WWF._cultMoveSync(b);
    GF.openModal('cu-move-modal');
  };

  // Terminal phases are irreversible and settle every active plant, so the
  // warning appears as soon as one is picked — before the button is pressed,
  // not as a 409 afterwards.
  GF.WWF._cultMoveSync = (b) => {
    const sel = GF.$('cu-m-phase'), warn = GF.$('cu-m-warn'), btn = GF.$('cu-m-save');
    const v = (sel || {}).value;
    if (TERMINAL.includes(v)) {
      if (warn) {
        warn.style.display = 'block';
        warn.textContent = AL(
          `This closes the batch: all ${b.plant_count} plants are marked ${v} and the batch cannot be moved again.`,
          `Ова го затвора батчот: сите ${b.plant_count} растенија се означуваат како ${v} и батчот не може повеќе да се движи.`);
      }
      if (btn) btn.className = 'btn btn-orange';
    } else {
      if (warn) warn.style.display = 'none';
      if (btn) btn.className = 'btn btn-primary';
    }
  };

  GF.WWF.cultMoveSave = (batchId) => GF.once('cu-m-save', async () => {
    const toPhase = (GF.$('cu-m-phase') || {}).value;
    const toRoom = ((GF.$('cu-m-room') || {}).value || '') || null;
    const when = ((GF.$('cu-m-date') || {}).value || '') || null;
    const reason = ((GF.$('cu-m-reason') || {}).value || '').trim() || null;
    // A terminal move is the one destructive action on this board. It needs a
    // stated reason: "several tonnes destroyed" with no recorded why is not a
    // record anyone can defend later.
    if (TERMINAL.includes(toPhase) && !reason) {
      GF.toast(AL('Closing a batch needs a reason', 'Затворањето на батч бара причина'), 'error');
      return;
    }
    try {
      const r = await GF.API.cultivationMove(batchId, {
        to_phase: toPhase, to_room_id: toRoom, occurred_on: when, reason });
      GF.closeModal('cu-move-modal');
      GF.toast(TERMINAL.includes(r.phase)
        ? AL(`Batch closed as ${phLbl(r.phase)}`, `Батчот е затворен како ${phLbl(r.phase)}`)
        : AL(`Moved to ${phLbl(r.phase)}`, `Преместено во ${phLbl(r.phase)}`),
        TERMINAL.includes(r.phase) ? 'error' : 'success');
      await GF.WWF.loadCultivation();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── the trichome maturation check ────────────────────────────────────────
  // The owner's rule: the harvest date is decided by progressive tracking of
  // trichome maturation under a stereo or digital microscope, with documented
  // records. This is the record. It gates nothing — the harvest form shows the
  // latest verdict and a cut is never refused for want of one.

  const TC_VERDICTS = [
    { v: 'immature', en: 'Immature', mk: 'Незрели', color: '#8296B4' },
    { v: 'approaching', en: 'Approaching', mk: 'Се приближува', color: '#2FD9D9' },
    { v: 'ready', en: 'Ready', mk: 'Зрели', color: '#2BE8A0' },
    { v: 'overripe', en: 'Overripe', mk: 'Презрели', color: '#E0A73E' },
  ];

  GF.WWF.trichomeForm = (batchId, code) => {
    if (!canWrite()) return;
    GF.WWF._ensureModal('tc-modal', '460px');
    GF.$('tc-modal-title').textContent = AL('Trichome check', 'Проверка на трихоми') + ' — ' + code;
    GF.$('tc-modal-body').innerHTML = `
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Checked on', 'Датум')}</label>
          ${GF.dateField('tc-date', { value: today(), clearable: false })}</div>
        <div class="field" style="flex:1"><label>${AL('Microscope', 'Микроскоп')}</label>
          ${GF.selectField('tc-instrument', { value: 'digital', title: AL('Microscope', 'Микроскоп'),
            options: [{ v: 'stereo', label: AL('Stereo', 'Стерео') },
                      { v: 'digital', label: AL('Digital', 'Дигитален') }] })}</div>
      </div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Magnification', 'Зголемување')}</label>
          <input id="tc-mag" maxlength="40" placeholder="60x"></div>
        <div class="field" style="flex:1"><label>${AL('Sample sites', 'Мерни места')}</label>
          <input id="tc-sites" type="number" min="1" max="1000" step="1"></div>
      </div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Clear %', 'Бистри %')}</label>
          <input id="tc-clear" type="number" min="0" max="100" step="1" oninput="GF.WWF._tcSum()"></div>
        <div class="field" style="flex:1"><label>${AL('Cloudy %', 'Матни %')}</label>
          <input id="tc-cloudy" type="number" min="0" max="100" step="1" oninput="GF.WWF._tcSum()"></div>
        <div class="field" style="flex:1"><label>${AL('Amber %', 'Килибарни %')}</label>
          <input id="tc-amber" type="number" min="0" max="100" step="1" oninput="GF.WWF._tcSum()"></div>
      </div>
      <div id="tc-sum" style="font-size:11px;color:var(--ink-3);margin-bottom:8px"></div>
      <div class="field"><label>${AL('Verdict', 'Оцена')}</label>
        ${GF.selectField('tc-verdict', { value: 'approaching', title: AL('Verdict', 'Оцена'),
          options: TC_VERDICTS.map(x => ({ v: x.v, label: AL(x.en, x.mk), color: x.color })) })}</div>
      <div class="field"><label>${AL('Image reference (optional)', 'Слика (опционално)')}</label>
        <input id="tc-image" maxlength="300"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="tc-note" maxlength="1000"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'The three states are one field of view, so if you give all three they must add up to about 100 %. Leave them blank for a qualitative check — blank means "not counted", not zero.',
        'Трите состојби се едно видно поле, па ако ги внесете сите три мора да збирот е околу 100 %. Оставете празно за квалитативна проверка — празно значи „не е броено“, не нула.')}</div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="tc-save"
          onclick="GF.WWF.trichomeSave('${batchId}')">${GF.t('save')}</button>
      </div>`;
    GF.openModal('tc-modal');
    GF.WWF._tcSum();
  };

  // Shows the running total while the three are typed, so a mistyped split is
  // seen here rather than coming back as a 422.
  GF.WWF._tcSum = () => {
    const el = GF.$('tc-sum');
    if (!el) return;
    const n = (id) => { const v = ((GF.$(id) || {}).value || '').trim(); return v === '' ? null : parseFloat(v); };
    const vals = [n('tc-clear'), n('tc-cloudy'), n('tc-amber')];
    if (vals.some(v => v == null)) { el.textContent = ''; el.style.color = 'var(--ink-3)'; return; }
    const total = vals.reduce((a, b) => a + b, 0);
    const ok = total >= 98 && total <= 102;
    el.textContent = AL(`Total ${total} %`, `Вкупно ${total} %`) + (ok ? '' : ' — ' + AL('must be about 100 %', 'мора да е околу 100 %'));
    el.style.color = ok ? '#2BE8A0' : '#E0A73E';
  };

  GF.WWF.trichomeSave = (batchId) => GF.once('tc-save', async () => {
    const num = (id) => { const v = ((GF.$(id) || {}).value || '').trim(); return v === '' ? null : parseFloat(v); };
    const vals = [num('tc-clear'), num('tc-cloudy'), num('tc-amber')];
    if (vals.every(v => v != null)) {
      const total = vals.reduce((a, b) => a + b, 0);
      if (total < 98 || total > 102) {
        GF.toast(AL('Clear + cloudy + amber must add up to about 100 %',
                    'Бистри + матни + килибарни мора да е околу 100 %'), 'error');
        return;
      }
    }
    try {
      await GF.API.trichomeCheck({
        batch_id: batchId,
        checked_on: ((GF.$('tc-date') || {}).value || '') || null,
        instrument: (GF.$('tc-instrument') || {}).value || 'digital',
        magnification: ((GF.$('tc-mag') || {}).value || '').trim() || null,
        sample_sites: num('tc-sites'),
        pct_clear: vals[0], pct_cloudy: vals[1], pct_amber: vals[2],
        verdict: (GF.$('tc-verdict') || {}).value || 'approaching',
        image_ref: ((GF.$('tc-image') || {}).value || '').trim() || null,
        note: ((GF.$('tc-note') || {}).value || '').trim() || null });
      GF.closeModal('tc-modal');
      GF.toast(AL('Trichome check recorded', 'Проверката е запишана'), 'success');
      await GF.WWF.loadCultivation();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // Same registration + read gate as the Facility and Decontamination boards:
  // every role above base USER may READ; write gating is per-action above.
  GF.WWF._registerFullPageView({
    key: 'cultivation', icon: 'leaf',
    label: () => AL('Cultivation', 'Одгледување'),
    // Anchored on 'mywork' like Facility and Decontamination rather than on
    // 'decon': _registerFullPageView wraps render.sidebar, and this file loads
    // BEFORE decon-view.js, so its wrapper runs first — on the very first render
    // the decon nav item does not exist yet and an anchor on it would silently
    // fall through to append(). Anchoring on a nav key that render.sidebar()
    // itself emits is order-independent.
    insertBefore: 'floor-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
