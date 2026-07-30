/* decon-view.js — HLVd decontamination campaign board.

   The per-room batch record the eradication plan calls for: the 5-step signed
   cycle, the strip-verified bleach log, and the swab results that gate QA
   release. Read: every role above base USER. Cleaning actions (start a cycle,
   sign a step, log a bucket): cultivation manager + executives + ADMIN. Swabs
   and release: QA manager + executives + ADMIN — "nobody else can release a
   room, and no room is released verbally."

   The ORDER and GATE rules live on the server (409 with a `detail`), not here.
   This view disables what it can predict and surfaces the server's message for
   everything else, deliberately — duplicating the rule in JS is how the two
   copies drift, and the server's is the one that governs the record.

   Same monkey-patch/view pattern as the other *-view.js files. */

(function () {
  GF.WWF._decon = { cycles: null, loading: false, error: null, campaign: '' };

  // The plan's §12 sequence, in order. Labels are bilingual per house style.
  const STEPS = [
    { key: 'dry_clean',         en: 'Dry clean',            mk: 'Сухо чистење' },
    { key: 'detergent_wash',    en: 'Detergent wash',       mk: 'Детергентско миење' },
    { key: 'rinse1_whitecloth', en: 'Rinse 1 + white cloth', mk: 'Плакнење 1 + бела крпа' },
    { key: 'bleach',            en: 'Bleach 5,000 ppm',     mk: 'Хлор 5.000 ppm' },
    { key: 'rinse2',            en: 'Rinse 2 (same day)',   mk: 'Плакнење 2 (истиот ден)' },
  ];
  const GATE = 'rinse1_whitecloth';
  const TARGET_PPM = 5000;   // the plan's specification; below this is flagged, not blocked

  const STATUS = {
    in_progress:           { en: 'In progress',    mk: 'Во тек',            color: '#E0A73E' },
    awaiting_verification: { en: 'Awaiting swabs', mk: 'Чека брисеви',      color: '#2FD9D9' },
    released:              { en: 'Released',       mk: 'Ослободена',        color: '#2BE8A0' },
    failed:                { en: 'Failed',         mk: 'Неуспешна',         color: '#E5484D' },
  };

  const stLbl = (s) => AL(STATUS[s]?.en || s, STATUS[s]?.mk || s);
  const stCol = (s) => (STATUS[s] || {}).color || 'var(--ink-3)';
  const role = () => (GF.API.user || {}).role;
  const canClean = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'CU_MGR'].includes(role());
  const canQA    = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'QA_MGR'].includes(role());

  GF.WWF.loadDecon = async () => {
    const st = GF.WWF._decon;
    st.loading = true; st.error = null;
    try {
      const r = await GF.API.deconCycles(st.campaign || undefined);
      st.cycles = r.cycles || [];
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'decon') GF.render.all();
  };

  // Which step may be signed next: the first step whose latest signoff is
  // missing, EXCEPT that a failed white-cloth check sends the crew back to the
  // detergent wash. Mirrors the server's gate so the UI can point at the right
  // button; the server still has the final say.
  const nextStep = (steps) => {
    const gate = steps[GATE];
    if (gate && gate.passed === false) return 'detergent_wash';
    for (const s of STEPS) if (!steps[s.key]) return s.key;
    return null;
  };

  const stepRow = (cyc, s) => {
    const entry = (cyc.steps || {})[s.key];
    const isGate = s.key === GATE;
    let mark = '○', col = 'var(--ink-3)', extra = '';
    if (entry) {
      if (isGate && entry.passed === false) {
        mark = '✕'; col = '#E5484D';
        extra = AL(' — soiled, wash again', ' — валкана, измијте повторно');
      } else {
        mark = '✓'; col = '#2BE8A0';
      }
    }
    const when = entry ? new Date(entry.signed_at).toLocaleString() : '';
    return `<div class="dc-step" style="display:flex;gap:8px;align-items:center;padding:3px 0">
      <span style="color:${col};width:14px;text-align:center">${mark}</span>
      <span style="flex:1">${GF.esc(AL(s.en, s.mk))}${extra}</span>
      <span style="color:var(--ink-3);font-size:11px">${GF.esc(when)}</span>
    </div>`;
  };

  const cycleCard = (cyc) => {
    const next = nextStep(cyc.steps || {});
    const sw = cyc.swabs || {};
    const blocking = (sw.pending || 0) + (sw.positive || 0) + (sw.inconclusive || 0);
    const releasable = cyc.status === 'awaiting_verification' && blocking === 0 && (sw.negative || 0) > 0;
    // Why release is unavailable, in the plan's own terms — so the reason is on
    // screen rather than only in a 409 nobody reads.
    let why = '';
    if (cyc.status === 'in_progress') {
      why = AL('cycle not complete', 'циклусот не е завршен');
    } else if (cyc.status === 'awaiting_verification' && !releasable) {
      why = (sw.negative || 0) === 0 && blocking === 0
        ? AL('no swab on file', 'нема брис во евиденција')
        : AL(`${blocking} swab(s) not negative`, `${blocking} брис(еви) не се негативни`);
    }
    const actions = [];
    if (canClean() && cyc.status === 'in_progress' && next) {
      const label = STEPS.find(s => s.key === next);
      actions.push(`<button class="btn btn-sm" onclick="GF.WWF.deconSignStep('${cyc.id}','${next}')">
        ${GF.icon('check', 'icon')}${GF.esc(AL('Sign: ', 'Потпиши: ') + AL(label.en, label.mk))}</button>`);
    }
    if (canClean()) {
      actions.push(`<button class="btn btn-sm" onclick="GF.WWF.deconBleachForm('${cyc.room_id}','${cyc.id}')">
        ${GF.icon('drop', 'icon')}${AL('Log bucket', 'Внеси кофа')}</button>`);
    }
    if (canQA()) {
      actions.push(`<button class="btn btn-sm" onclick="GF.WWF.deconSwabForm('${cyc.room_id}','${cyc.id}')">
        ${GF.icon('flask', 'icon')}${AL('Add swab', 'Додади брис')}</button>`);
      if (releasable) {
        actions.push(`<button class="btn btn-orange btn-sm" onclick="GF.WWF.deconRelease('${cyc.id}')">
          ${GF.icon('shield', 'icon', '#fff')}${AL('Release room', 'Ослободи соба')}</button>`);
      }
    }
    return `<div class="card" style="padding:12px;margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <strong style="flex:1">${GF.esc(cyc.room_name)}</strong>
        <span style="color:${stCol(cyc.status)};font-size:12px">${GF.esc(stLbl(cyc.status))}</span>
      </div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">
        ${GF.esc(cyc.campaign)} · ${GF.esc(cyc.started_on)}
        ${cyc.released_at ? ' · ' + AL('released ', 'ослободена ') + GF.esc(String(cyc.released_at).slice(0, 10)) : ''}
      </div>
      <div style="margin-bottom:8px">${STEPS.map(s => stepRow(cyc, s)).join('')}</div>
      <div style="font-size:11px;color:var(--ink-3);margin-bottom:8px">
        ${AL('Swabs', 'Брисеви')}:
        <span style="color:#2BE8A0">${sw.negative || 0} ${AL('neg', 'нег')}</span> ·
        <span style="color:#E0A73E">${sw.pending || 0} ${AL('pending', 'во тек')}</span> ·
        <span style="color:#E5484D">${sw.positive || 0} ${AL('pos', 'поз')}</span>
        ${why ? ` — <em>${GF.esc(why)}</em>` : ''}
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">${actions.join('')}</div>
    </div>`;
  };

  GF.views.decon = () => {
    const st = GF.WWF._decon;
    if (!st.cycles && !st.loading && !st.error) GF.WWF.loadDecon();
    const startBtn = canClean()
      ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.deconCycleForm()">${GF.icon('plus', 'icon', '#fff')}${AL('Start room cycle', 'Почни циклус')}</button>`
      : '';
    const head = GF.viewHead
      ? GF.viewHead('decon', 'decon_sub', startBtn)
      : `<div class="view-head"><h2>${AL('Decontamination', 'Деконтаминација')}</h2>${startBtn}</div>`;
    if (st.loading && !st.cycles) return head + `<div class="ntf-empty">${AL('Loading…', 'Вчитување…')}</div>`;
    if (st.error) return head + `<div class="ntf-empty">${GF.esc(st.error)}</div>`;
    const cycles = st.cycles || [];
    if (!cycles.length) {
      return head + `<div class="ntf-empty">${AL(
        'No room cycles yet. Start one per room — every room passes the full 5-step cycle.',
        'Нема циклуси. Почнете по еден за секоја соба — секоја поминува полн циклус од 5 чекори.')}</div>`;
    }
    const released = cycles.filter(c => c.status === 'released').length;
    const summary = `<div style="margin-bottom:10px;color:var(--ink-3);font-size:12px">
      ${released}/${cycles.length} ${AL('rooms released', 'соби ослободени')}</div>`;
    return head + summary + cycles.map(cycleCard).join('');
  };

  // ── actions ───────────────────────────────────────────────────────────────

  GF.WWF.deconSignStep = async (cycleId, step) => {
    // The white-cloth check is the one step with a pass/fail answer — ask, and
    // send passed=false through so a soiled cloth is RECORDED (which reopens the
    // wash) rather than silently skipped.
    let passed;
    if (step === GATE) {
      passed = confirm(AL(
        'White-cloth check PASSED? OK = clean (bleach may proceed). Cancel = soiled (wash again).',
        'Проверката со бела крпа е ПОМИНАТА? OK = чисто (хлорот може). Откажи = валкано (измијте повторно).'));
    }
    try {
      const body = { step };
      if (passed !== undefined) body.passed = passed;
      const r = await GF.API.deconStep(cycleId, body);
      GF.toast(r.cycle_complete
        ? AL('Cycle complete — awaiting swab results', 'Циклусот е завршен — чека брисеви')
        : AL('Step signed', 'Чекорот е потпишан'), 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.deconRelease = async (cycleId) => {
    if (!confirm(AL(
      'Release this room? This is the QA release decision and is recorded against your name.',
      'Да се ослободи собата? Ова е QA одлука и се запишува на ваше име.'))) return;
    const note = prompt(AL('Release note (optional)', 'Забелешка (опционално)')) || null;
    try {
      await GF.API.deconRelease(cycleId, { release_note: note });
      GF.toast(AL('Room released', 'Собата е ослободена'), 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.deconBleachForm = async (roomId, cycleId) => {
    const raw = prompt(AL(
      `Free-chlorine strip reading in ppm (target ${TARGET_PPM}):`,
      `Читање на лентата во ppm (цел ${TARGET_PPM}):`));
    if (raw === null) return;
    const ppm = parseInt(raw, 10);
    if (!Number.isFinite(ppm) || ppm < 0) {
      GF.toast(AL('Enter a number in ppm', 'Внесете број во ppm'), 'error'); return;
    }
    try {
      await GF.API.deconBleachAdd({ room_id: roomId, cycle_id: cycleId, ppm_strip_reading: ppm });
      GF.toast(ppm < TARGET_PPM
        ? AL(`Logged ${ppm} ppm — BELOW the ${TARGET_PPM} ppm specification`,
             `Внесено ${ppm} ppm — ПОД спецификацијата од ${TARGET_PPM} ppm`)
        : AL(`Logged ${ppm} ppm`, `Внесено ${ppm} ppm`),
        ppm < TARGET_PPM ? 'error' : 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.deconSwabForm = async (roomId, cycleId) => {
    const code = prompt(AL('Swab code (e.g. RR-01-001):', 'Код на брис (пр. RR-01-001):'));
    if (!code) return;
    const where = prompt(AL('Location (e.g. tray groove, floor drain):',
                            'Локација (пр. жлеб на тацна, слив):')) || null;
    try {
      await GF.API.deconSwabAdd({ room_id: roomId, cycle_id: cycleId,
                                  swab_code: code.trim(), location_desc: where });
      GF.toast(AL('Swab recorded — result pending', 'Брисот е запишан — чека резултат'), 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.deconCycleForm = async () => {
    // Rooms come from the facility registry — this view never invents a room
    // code (the plan's own room mapping is still an unconfirmed assumption).
    let rooms = [];
    try { rooms = (await GF.API.facility()).rooms || []; }
    catch (e) { GF.toast(e.message, 'error'); return; }
    if (!rooms.length) {
      GF.toast(AL('No rooms configured — add rooms on the Facility board first',
                  'Нема соби — прво додајте соби на Капацитет'), 'error');
      return;
    }
    const listing = rooms.map((r, i) => `${i + 1}. ${r.name}`).join('\n');
    const pick = prompt(AL('Room number:\n', 'Број на соба:\n') + listing);
    if (!pick) return;
    const room = rooms[parseInt(pick, 10) - 1];
    if (!room) { GF.toast(AL('No such room', 'Нема таква соба'), 'error'); return; }
    const campaign = prompt(AL('Campaign id:', 'Кампања:'), GF.WWF._decon.campaign || 'hlvd-2026-07');
    if (!campaign) return;
    try {
      await GF.API.deconCycleCreate({ room_id: room.id, campaign: campaign.trim() });
      GF.toast(AL('Cycle started', 'Циклусот е започнат'), 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  // Same registration + read gate as the Facility board: every role above base
  // USER may READ the record; the write/release gating is per-action above.
  GF.WWF._registerFullPageView({
    key: 'decon', icon: 'shield',
    label: () => AL('Decontamination', 'Деконтаминација'),
    insertBefore: 'mywork',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
