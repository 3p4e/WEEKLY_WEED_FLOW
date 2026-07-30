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
  GF.WWF._decon = { cycles: null, loading: false, error: null, campaign: '',
                    corridors: null };

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
      // Both in one round trip: the corridor cadence is part of the same
      // campaign picture, and a second render pass would make the panel flash in
      // after the cycles.
      const [r, cor] = await Promise.all([
        GF.API.deconCycles(st.campaign || undefined),
        GF.API.deconCorridors(st.campaign || undefined),
      ]);
      st.cycles = r.cycles || [];
      st.corridors = cor;
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
      // Without this the pending count on the card is a dead number — there
      // would be no way to enter the result that clears it.
      if ((sw.pending || 0) + (sw.negative || 0) + (sw.positive || 0) + (sw.inconclusive || 0) > 0) {
        actions.push(`<button class="btn btn-sm" onclick="GF.WWF.deconSwabList('${cyc.room_id}','${cyc.id}')">
          ${GF.icon('file', 'icon')}${AL('Swab results', 'Резултати')}</button>`);
      }
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

  // ── corridor cleaning cadence (§25, migration 0049) ─────────────────────
  //
  // The server derives `overdue` and the interval; this panel renders them and
  // does NOT recompute the 4 hours, because two copies of an interval is how the
  // board and the record come to disagree about what "overdue" means.
  //
  // It sits at the TOP of the board during a campaign, above the room cycles.
  // The cadence is the thing that lapses silently — a room cycle is a visible
  // piece of work someone is doing, an unswept corridor is the absence of one.

  const TRIGGERS = [
    { v: 'four_hourly',    en: 'Four-hourly round', mk: 'Четиричасовен циклус' },
    { v: 'shift_change',   en: 'Shift changeover',  mk: 'Промена на смена' },
    { v: 'waste_movement', en: 'After a waste movement', mk: 'По движење на отпад' },
    { v: 'other',          en: 'Other',             mk: 'Друго' },
  ];
  const trigLbl = (v) => { const o = TRIGGERS.find(t => t.v === v); return o ? AL(o.en, o.mk) : v; };
  const roomName = (r) => (GF.state.lang === 'mk' && r.name_mk) ? r.name_mk : r.name;

  // "241 minutes" is not how anyone thinks about a 4-hourly round.
  const sinceLbl = (mins) => {
    if (mins == null) return AL('never', 'никогаш');
    if (mins < 60) return `${mins} ${AL('min ago', 'мин.')}`;
    const h = Math.floor(mins / 60), m = mins % 60;
    return `${h}h${m ? ' ' + m + 'm' : ''} ${AL('ago', 'претходно')}`;
  };

  const corridorPanel = () => {
    const cor = GF.WWF._decon.corridors;
    if (!cor || !(cor.corridors || []).length) return '';
    const rows = cor.corridors.map(c => {
      const col = c.overdue ? '#E5484D' : '#2BE8A0';
      const btn = canClean()
        ? `<button class="btn btn-sm" onclick="GF.WWF.deconCorridorForm('${c.room_id}')">
            ${AL('Record clean', 'Запиши чистење')}</button>`
        : '';
      return `<div style="display:flex;gap:8px;align-items:center;padding:4px 0${c.overdue ? ';background:rgba(229,72,77,.06)' : ''}">
        <span style="width:8px;height:8px;border-radius:50%;background:${col};flex:none"></span>
        <strong style="flex:1;font-size:12px">${GF.esc(roomName(c))}</strong>
        <span style="color:${col};font-size:11px;min-width:110px;text-align:right">${
          GF.esc(sinceLbl(c.minutes_since))}</span>
        <span style="color:var(--ink-3);font-size:11px;min-width:60px;text-align:right">${
          c.cleanings} ${AL('logged', 'запис.')}</span>
        ${btn}
      </div>`;
    }).join('');
    const late = cor.corridors.filter(c => c.overdue).length;
    // ONE derivation of the interval, used by both the subtitle and the summary.
    // A hardcoded "4-hourly" caption above a computed "past the 2-hour interval"
    // line is the same two-copies-of-a-rule problem in miniature, and the caption
    // is the half a reader would believe.
    const hrs = Math.round((cor.interval_minutes || 240) / 60);
    const head = late
      ? `<div style="color:#E5484D;font-size:12px;margin-bottom:6px">${AL(
          `${late} of ${cor.corridors.length} corridors are past the ${hrs}-hour interval.`,
          `${late} од ${cor.corridors.length} коридори го надминаа интервалот од ${hrs} часа.`)}</div>`
      : `<div style="color:#2BE8A0;font-size:12px;margin-bottom:6px">${AL(
          `All ${cor.corridors.length} corridors are inside the ${hrs}-hour interval.`,
          `Сите ${cor.corridors.length} коридори се во интервалот од ${hrs} часа.`)}</div>`;
    // The cross-module breach: something left the site and no corridor has been
    // cleaned since. Listed by manifest, because "after every waste movement"
    // names the movement, and a count alone would not say which.
    const moves = (cor.movements_without_cleaning || []);
    const movesBlock = moves.length
      ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--line)">
          <div style="color:#E5484D;font-size:12px;margin-bottom:4px">${AL(
            `${moves.length} waste movement(s) left the site with no corridor cleaning recorded after them:`,
            `${moves.length} движење(а) на отпад без запишано чистење на коридор потоа:`)}</div>
          ${moves.map(m => `<div style="font-size:11px;color:var(--ink-3)">
            ${GF.esc(m.manifest_code)} · ${GF.esc(String(m.disposed_at).slice(0, 16).replace('T', ' '))}
          </div>`).join('')}
        </div>`
      : '';
    return `<div class="card" style="padding:12px;margin-bottom:12px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <strong style="flex:1">${AL('Corridor cleaning cadence', 'Циклус на чистење на коридори')}</strong>
        <span style="color:var(--ink-3);font-size:11px">${AL(
          `after every waste movement · ${hrs}-hourly · shift changeover`,
          `по секое движење на отпад · на ${hrs} часа · промена на смена`)}</span>
      </div>
      ${head}${rows}${movesBlock}
    </div>`;
  };

  GF.WWF.deconCorridorForm = async (roomId) => {
    if (!canClean()) return;
    // Manifests are offered so an "after a waste movement" clean can cite the
    // movement it followed — the server refuses that trigger without one, and
    // making the operator go and find a code by hand is how the rule gets
    // recorded as 'other' instead.
    let manifests = [];
    try { manifests = (await GF.API.wasteManifests({ status: 'disposed' })).manifests || []; }
    catch (e) { manifests = []; }   // the register is optional context, not a blocker
    GF.WWF._ensureModal('dc-cor-modal', '440px');
    GF.$('dc-cor-modal-title').textContent = AL('Record corridor cleaning', 'Запиши чистење на коридор');
    const manOpts = [{ v: '', label: AL('— none —', '— ништо —') }]
      .concat(manifests.map(m => ({ v: m.id, label: m.manifest_code,
                                    sub: String(m.disposed_at || '').slice(0, 16).replace('T', ' ') })));
    GF.$('dc-cor-modal-body').innerHTML = `
      <div class="field"><label>${AL('What prompted this clean', 'Што го предизвика чистењето')}</label>
        ${GF.selectField('dc-cor-trigger', { value: 'four_hourly',
          title: AL('Trigger', 'Причина'),
          options: TRIGGERS.map(t => ({ v: t.v, label: AL(t.en, t.mk) })),
          onPick: (v) => GF.WWF._deconCorridorSync(v) })}</div>
      <div class="field" id="dc-cor-man-field"><label>${AL('Waste movement', 'Движење на отпад')}</label>
        ${GF.selectField('dc-cor-manifest', { value: '', title: AL('Waste movement', 'Движење на отпад'),
          options: manOpts, searchable: true })}
        <div id="dc-cor-man-hint" style="color:var(--ink-3);font-size:11px;margin-top:3px"></div></div>
      <div class="field"><label>${AL('Free-chlorine strip reading (ppm, optional)', 'Читање на лентата (ppm, опционално)')}</label>
        <input id="dc-cor-ppm" type="number" min="0" max="200000" step="50" placeholder="${TARGET_PPM}"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="dc-cor-note" maxlength="500"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'The time is stamped by the server, not entered here — a cleaning that can be backdated satisfies the cadence on paper only.',
        'Времето го внесува серверот, не се внесува тука — запис што може да се смени наназад ја задоволува обврската само на хартија.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="dc-cor-save"
          onclick="GF.WWF.deconCorridorSave('${roomId}')">${GF.t('save')}</button>
      </div>`;
    GF.WWF._deconCorridorSync('four_hourly');
    GF.openModal('dc-cor-modal');
  };

  // GF.selectField renders a HIDDEN input and GF.pickSel assigns .value directly,
  // firing no change event, so onPick is the only hook that runs.
  GF.WWF._deconCorridorSync = (trigger) => {
    const hint = GF.$('dc-cor-man-hint');
    if (!hint) return;
    hint.textContent = trigger === 'waste_movement'
      ? AL('Required: "after every waste movement" needs the movement it followed.',
           'Задолжително: „по секое движење на отпад" бара кое движење.')
      : AL('Optional for this trigger.', 'Опционално за оваа причина.');
    hint.style.color = trigger === 'waste_movement' ? 'var(--red)' : 'var(--ink-3)';
  };

  GF.WWF.deconCorridorSave = (roomId) => GF.once('dc-cor-save', async () => {
    const trigger = (GF.$('dc-cor-trigger') || {}).value;
    const manifestId = ((GF.$('dc-cor-manifest') || {}).value || '') || null;
    // Checked here as well as server-side so the operator is told what is
    // missing while the form is still open and the answer is still to hand.
    if (trigger === 'waste_movement' && !manifestId) {
      GF.toast(AL('Pick the waste movement this clean followed',
                  'Изберете кое движење на отпад е чистено потоа'), 'error');
      return;
    }
    const ppmRaw = ((GF.$('dc-cor-ppm') || {}).value || '').trim();
    try {
      await GF.API.deconCorridorClean({
        room_id: roomId, trigger, manifest_id: manifestId,
        campaign: GF.WWF._decon.campaign || 'hlvd-2026-07',
        ppm_strip_reading: ppmRaw === '' ? null : parseInt(ppmRaw, 10),
        note: ((GF.$('dc-cor-note') || {}).value || '').trim() || null });
      GF.closeModal('dc-cor-modal');
      GF.toast(AL('Corridor cleaning recorded — ' + trigLbl(trigger),
                  'Запишано чистење — ' + trigLbl(trigger)), 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

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
    // The corridor panel renders even with no room cycles: the cadence runs
    // throughout the campaign, including before the first room cycle is started
    // and after the last one is released.
    const corridors = corridorPanel();
    if (!cycles.length) {
      return head + corridors + `<div class="ntf-empty">${AL(
        'No room cycles yet. Start one per room — every room passes the full 5-step cycle.',
        'Нема циклуси. Почнете по еден за секоја соба — секоја поминува полн циклус од 5 чекори.')}</div>`;
    }
    const released = cycles.filter(c => c.status === 'released').length;
    const summary = `<div style="margin-bottom:10px;color:var(--ink-3);font-size:12px">
      ${released}/${cycles.length} ${AL('rooms released', 'соби ослободени')}</div>`;
    return head + corridors + summary + cycles.map(cycleCard).join('');
  };

  // ── actions ───────────────────────────────────────────────────────────────

  GF.WWF.deconSignStep = async (cycleId, step) => {
    // The white-cloth check is the one step with a pass/fail ANSWER, and it gets
    // its own modal with two explicit buttons rather than a confirm(). With
    // confirm(), "Cancel" would record a FAILED check — so anyone dismissing the
    // dialog, or expecting Cancel to mean "abort, I mis-tapped", would write a
    // failure into a GxP record. There is no safe default here, so the operator
    // must choose, and dismissing writes nothing.
    if (step === GATE) { GF.WWF.deconWhiteClothForm(cycleId); return; }
    await GF.WWF.deconSubmitStep(cycleId, step);
  };

  GF.WWF.deconSubmitStep = async (cycleId, step, passed) => {
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

  GF.WWF.deconWhiteClothForm = (cycleId) => {
    if (!canClean()) return;
    GF.WWF._ensureModal('dc-wc-modal', '440px');
    GF.$('dc-wc-modal-title').textContent = AL('White-cloth check', 'Проверка со бела крпа');
    GF.$('dc-wc-modal-body').innerHTML = `
      <div style="margin-bottom:10px">${AL(
        'A second person wipes the rinsed surface with a white cloth. This is the gate on the detergent wash — bleach on a surface that is not physically clean is quenched within seconds and the surface is NOT disinfected.',
        'Второ лице ја брише исплакнатата површина со бела крпа. Ова е контролна точка за миењето — хлор на површина што не е физички чиста се неутралізира за секунди и површината НЕ е дезинфицирана.')}</div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="dc-wc-note" maxlength="500"></div>
      <div class="row" style="gap:10px">
        <button class="btn" style="color:var(--red)" id="dc-wc-fail"
          onclick="GF.WWF.deconWhiteClothSave('${cycleId}', false)">
          ${AL('Soiled — wash again', 'Валкана — измијте повторно')}</button>
        <div class="spacer"></div>
        <button class="btn btn-primary" id="dc-wc-pass"
          onclick="GF.WWF.deconWhiteClothSave('${cycleId}', true)">
          ${AL('Clean — passed', 'Чиста — поминато')}</button>
      </div>`;
    GF.openModal('dc-wc-modal');
  };

  GF.WWF.deconWhiteClothSave = (cycleId, passed) =>
    GF.once(passed ? 'dc-wc-pass' : 'dc-wc-fail', async () => {
      const note = ((GF.$('dc-wc-note') || {}).value || '').trim() || null;
      try {
        const body = { step: GATE, passed };
        if (note) body.note = note;
        const r = await GF.API.deconStep(cycleId, body);
        GF.closeModal('dc-wc-modal');
        GF.toast(passed
          ? (r.cycle_complete
              ? AL('Cycle complete — awaiting swab results', 'Циклусот е завршен — чека брисеви')
              : AL('White-cloth check passed — bleach may proceed', 'Проверката е помината — хлорот може'))
          : AL('Recorded as soiled — wash again before bleach', 'Запишано како валкано — измијте пред хлор'),
          passed ? 'success' : 'error');
        await GF.WWF.loadDecon();
      } catch (e) { GF.toast(e.message, 'error'); }
    });

  // The QA release decision, "in writing". Its own modal rather than a
  // confirm()+prompt() pair: it is the formal record that the room is clean, it
  // is attributed to the signer, and it must state what it was signed against.
  GF.WWF.deconRelease = (cycleId) => {
    if (!canQA()) return;
    GF.WWF._ensureModal('dc-rel-modal', '460px');
    GF.$('dc-rel-modal-title').textContent = AL('QA room release', 'QA ослободување на соба');
    GF.$('dc-rel-modal-body').innerHTML = `
      <div style="margin-bottom:10px">${AL(
        'You are releasing this room against its completed batch record: every cycle step signed, and every swab returned negative. This decision is recorded against your name and cannot be undone.',
        'Ја ослободувате собата врз основа на комплетна евиденција: сите чекори потпишани и сите брисеви негативни. Одлуката се запишува на ваше име и не може да се врати.')}</div>
      <div class="field"><label>${AL('Release note', 'Забелешка за ослободување')}</label>
        <input id="dc-rel-note" maxlength="1000"
          placeholder="${AL('e.g. swabs RR-01-001..005 negative, HVAC confirmed, room sealed', 'пр. брисеви RR-01-001..005 негативни, HVAC потврден, собата затворена')}"></div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-orange" id="dc-rel-save"
          onclick="GF.WWF.deconReleaseSave('${cycleId}')">
          ${AL('Release room', 'Ослободи соба')}</button>
      </div>`;
    GF.openModal('dc-rel-modal');
    setTimeout(() => { const f = GF.$('dc-rel-note'); if (f) f.focus(); }, 60);
  };

  GF.WWF.deconReleaseSave = (cycleId) => GF.once('dc-rel-save', async () => {
    try {
      await GF.API.deconRelease(cycleId, {
        release_note: ((GF.$('dc-rel-note') || {}).value || '').trim() || null });
      GF.closeModal('dc-rel-modal');
      GF.toast(AL('Room released', 'Собата е ослободена'), 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── forms ─────────────────────────────────────────────────────────────────
  // Real modals, not prompt(): this record is filled in many times a shift by a
  // gloved operator on a tablet, where a native prompt is a single unlabelled
  // line with no validation, no bilingual label and no way to correct a typo
  // before submitting. Same _ensureModal/.field/selectField idiom as
  // facility-view.js, and every submit goes through GF.once so a double tap
  // cannot write the record twice.

  GF.WWF.deconBleachForm = (roomId, cycleId) => {
    if (!canClean()) return;
    GF.WWF._ensureModal('dc-bleach-modal', '420px');
    GF.$('dc-bleach-modal-title').textContent = AL('Log bleach bucket', 'Внеси кофа со хлор');
    GF.$('dc-bleach-modal-body').innerHTML = `
      <div class="field"><label>${AL('Free-chlorine strip reading (ppm)', 'Читање на лентата (ppm)')}</label>
        <input id="dc-ppm" type="number" min="0" max="200000" step="50" placeholder="${TARGET_PPM}"></div>
      <div id="dc-ppm-warn" style="display:none;color:var(--red);font-size:12px;margin:-4px 0 8px"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="dc-bleach-note" maxlength="500"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">
        ${AL(`Specification: ${TARGET_PPM} ppm (1 part bleach : 9 parts cold water), minimum 2 minutes wet. Fresh mix every shift and again after 4 hours.`,
             `Спецификација: ${TARGET_PPM} ppm (1 дел хлор : 9 дела студена вода), минимум 2 минути влажно. Свежа смеса на секоја смена и повторно по 4 часа.`)}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="dc-bleach-save"
          onclick="GF.WWF.deconBleachSave('${roomId}','${cycleId}')">${GF.t('save')}</button>
      </div>`;
    // Live below-spec warning — the plan's #1 risk is a crew defaulting to
    // housekeeping strength (~400 ppm), so say so BEFORE the record is written.
    const inp = GF.$('dc-ppm'), warn = GF.$('dc-ppm-warn');
    if (inp && warn) {
      inp.oninput = () => {
        const v = parseInt(inp.value, 10);
        if (Number.isFinite(v) && v > 0 && v < TARGET_PPM) {
          warn.style.display = 'block';
          warn.textContent = AL(
            `${v} ppm is BELOW the ${TARGET_PPM} ppm specification — this bucket will not clear the viroid.`,
            `${v} ppm е ПОД спецификацијата од ${TARGET_PPM} ppm — оваа кофа нема да го уништи вироидот.`);
        } else { warn.style.display = 'none'; }
      };
    }
    GF.openModal('dc-bleach-modal');
    setTimeout(() => { const f = GF.$('dc-ppm'); if (f) f.focus(); }, 60);
  };

  GF.WWF.deconBleachSave = (roomId, cycleId) => GF.once('dc-bleach-save', async () => {
    const ppm = parseInt((GF.$('dc-ppm') || {}).value, 10);
    if (!Number.isFinite(ppm) || ppm < 0) {
      GF.toast(AL('Enter the strip reading in ppm', 'Внесете читање во ppm'), 'error'); return;
    }
    try {
      await GF.API.deconBleachAdd({
        room_id: roomId, cycle_id: cycleId || null, ppm_strip_reading: ppm,
        note: ((GF.$('dc-bleach-note') || {}).value || '').trim() || null });
      GF.closeModal('dc-bleach-modal');
      GF.toast(ppm < TARGET_PPM
        ? AL(`Logged ${ppm} ppm — BELOW specification`, `Внесено ${ppm} ppm — ПОД спецификација`)
        : AL(`Logged ${ppm} ppm`, `Внесено ${ppm} ppm`), ppm < TARGET_PPM ? 'error' : 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  GF.WWF.deconSwabForm = (roomId, cycleId) => {
    if (!canQA()) return;
    GF.WWF._ensureModal('dc-swab-modal', '440px');
    GF.$('dc-swab-modal-title').textContent = AL('Add RT-qPCR swab', 'Додади RT-qPCR брис');
    GF.$('dc-swab-modal-body').innerHTML = `
      <div class="field"><label>${AL('Swab code', 'Код на брис')}</label>
        <input id="dc-swab-code" maxlength="64" placeholder="RR-01-001"></div>
      <div class="field"><label>${AL('Location swabbed', 'Локација')}</label>
        <input id="dc-swab-loc" maxlength="300"
          placeholder="${AL('e.g. tray groove, floor drain rim, emitter', 'пр. жлеб на тацна, слив, капалка')}"></div>
      <div class="field"><label>${AL('Laboratory (optional)', 'Лабораторија (опционално)')}</label>
        <input id="dc-swab-lab" maxlength="120"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">
        ${AL('Swab where contamination survives, not the middle of a clean wall: floor-wall coving, drain rims, under bench edges, door handles, light housings, line ends and emitters.',
             'Земајте брис каде преживува контаминација, не од средина на чист ѕид: споеви под-ѕид, рабови на сливови, долни рабови на маси, рачки, светилки, краеви на линии и капалки.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="dc-swab-save"
          onclick="GF.WWF.deconSwabSave('${roomId}','${cycleId}')">${GF.t('save')}</button>
      </div>`;
    GF.openModal('dc-swab-modal');
    setTimeout(() => { const f = GF.$('dc-swab-code'); if (f) f.focus(); }, 60);
  };

  GF.WWF.deconSwabSave = (roomId, cycleId) => GF.once('dc-swab-save', async () => {
    const code = ((GF.$('dc-swab-code') || {}).value || '').trim();
    if (!code) { GF.toast(AL('Swab code is required', 'Кодот е задолжителен'), 'error'); return; }
    try {
      await GF.API.deconSwabAdd({
        room_id: roomId, cycle_id: cycleId || null, swab_code: code,
        location_desc: ((GF.$('dc-swab-loc') || {}).value || '').trim() || null,
        lab_name: ((GF.$('dc-swab-lab') || {}).value || '').trim() || null });
      GF.closeModal('dc-swab-modal');
      GF.toast(AL('Swab recorded — result pending', 'Брисот е запишан — чека резултат'), 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // Recording a RESULT is its own form: the Ct value and the action taken on a
  // positive are part of the record the plan requires, and a positive must
  // never be a bare status flip with no stated action.
  GF.WWF.deconSwabList = async (roomId, cycleId) => {
    if (!canQA()) return;
    let swabs = [];
    try { swabs = (await GF.API.deconSwabs({ room_id: roomId })).swabs || []; }
    catch (e) { GF.toast(e.message, 'error'); return; }
    const mine = swabs.filter(x => !cycleId || x.cycle_id === cycleId);
    GF.WWF._ensureModal('dc-swablist-modal', '520px');
    GF.$('dc-swablist-modal-title').textContent = AL('Swab results', 'Резултати од брисеви');
    const COL = { negative: '#2BE8A0', positive: '#E5484D', pending: '#E0A73E', inconclusive: '#E0A73E' };
    const rows = mine.map(x => {
      const act = x.result === 'pending'
        ? `<button class="btn btn-sm" onclick="GF.WWF.deconSwabResultForm('${x.id}','${GF.esc(x.swab_code)}')">${AL('Enter result', 'Внеси резултат')}</button>`
        : `<span style="color:var(--ink-3);font-size:11px">${x.ct_value != null ? 'Ct ' + x.ct_value : ''}</span>`;
      return `<div style="display:flex;gap:8px;align-items:center;padding:5px 0;border-bottom:1px solid var(--line)">
        <strong style="min-width:110px">${GF.esc(x.swab_code)}</strong>
        <span style="flex:1;color:var(--ink-3);font-size:11px">${GF.esc(x.location_desc || '—')}</span>
        <span style="color:${COL[x.result] || 'var(--ink-3)'};font-size:12px;min-width:80px">${GF.esc(x.result)}</span>
        ${act}
      </div>`;
    }).join('');
    GF.$('dc-swablist-modal-body').innerHTML = rows
      || `<div class="ntf-empty">${AL('No swabs for this cycle yet', 'Нема брисеви за овој циклус')}</div>`;
    GF.openModal('dc-swablist-modal');
  };

  GF.WWF.deconSwabResultForm = (swabId, code) => {
    if (!canQA()) return;
    GF.WWF._ensureModal('dc-res-modal', '420px');
    GF.$('dc-res-modal-title').textContent = AL('Swab result', 'Резултат од брис') + ' — ' + code;
    GF.$('dc-res-modal-body').innerHTML = `
      <div class="field"><label>${AL('Result', 'Резултат')}</label>
        ${GF.selectField('dc-res-val', { value: 'negative', title: AL('Result', 'Резултат'), options: [
          { v: 'negative',     label: AL('Negative', 'Негативен') },
          { v: 'positive',     label: AL('Positive', 'Позитивен') },
          { v: 'inconclusive', label: AL('Inconclusive', 'Неодреден') }] })}</div>
      <div class="field"><label>${AL('Ct value (optional)', 'Ct вредност (опционално)')}</label>
        <input id="dc-res-ct" type="number" min="0" max="100" step="0.1"></div>
      <div class="field"><label>${AL('Action taken', 'Преземена мерка')}</label>
        <input id="dc-res-action" maxlength="500"
          placeholder="${AL('required on a positive — re-clean and re-test', 'задолжително при позитивен — повторно чистење и тест')}"></div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="dc-res-save"
          onclick="GF.WWF.deconSwabResultSave('${swabId}')">${GF.t('save')}</button>
      </div>`;
    GF.openModal('dc-res-modal');
  };

  GF.WWF.deconSwabResultSave = (swabId) => GF.once('dc-res-save', async () => {
    const result = (GF.$('dc-res-val') || {}).value;
    const action = ((GF.$('dc-res-action') || {}).value || '').trim();
    // A positive with no stated action is an incomplete record — the plan's
    // action-on-positive is "immediate re-clean and re-test", and it must be
    // written down by the person recording the result.
    if (result === 'positive' && !action) {
      GF.toast(AL('A positive result needs the action taken', 'Позитивен резултат бара преземена мерка'), 'error');
      return;
    }
    const ctRaw = (GF.$('dc-res-ct') || {}).value;
    const ct = ctRaw === '' || ctRaw == null ? null : parseFloat(ctRaw);
    try {
      await GF.API.deconSwabResult(swabId, { result, ct_value: ct, action_taken: action || null });
      GF.closeModal('dc-res-modal');
      GF.closeModal('dc-swablist-modal');
      GF.toast(AL('Result recorded', 'Резултатот е запишан'), result === 'positive' ? 'error' : 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  GF.WWF.deconCycleForm = async () => {
    if (!canClean()) return;
    // Rooms come from the facility registry — this view never invents a room
    // code. The registry is the one place the code/Room-N reconciliation lives
    // (see the room-register note in docs/DEPLOY.md); a code typed here would
    // bypass it.
    let rooms = [];
    try { rooms = (await GF.API.facility()).rooms || []; }
    catch (e) { GF.toast(e.message, 'error'); return; }
    if (!rooms.length) {
      GF.toast(AL('No rooms configured — add rooms on the Facility board first',
                  'Нема соби — прво додајте соби на Капацитет'), 'error');
      return;
    }
    GF.WWF._ensureModal('dc-cycle-modal', '420px');
    GF.$('dc-cycle-modal-title').textContent = AL('Start room cycle', 'Почни циклус за соба');
    const roomOpts = rooms.map(r => ({ v: r.id, label: r.name }));
    GF.$('dc-cycle-modal-body').innerHTML = `
      <div class="field"><label>${AL('Room', 'Соба')}</label>
        ${GF.selectField('dc-cyc-room', { value: rooms[0].id, title: AL('Room', 'Соба'), options: roomOpts })}</div>
      <div class="field"><label>${AL('Campaign', 'Кампања')}</label>
        <input id="dc-cyc-campaign" maxlength="120" value="${GF.esc(GF.WWF._decon.campaign || 'hlvd-2026-07')}"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="dc-cyc-note" maxlength="500"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">
        ${AL('Every room passes the full 5-step cycle. Rough cleaning alone is not a handover — the room is not released until every step is signed and its swabs are negative.',
             'Секоја соба поминува полн циклус од 5 чекори. Грубото чистење не е предавање — собата не се ослободува додека сите чекори не се потпишани и брисевите негативни.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="dc-cyc-save" onclick="GF.WWF.deconCycleSave()">${GF.t('save')}</button>
      </div>`;
    GF.openModal('dc-cycle-modal');
  };

  GF.WWF.deconCycleSave = () => GF.once('dc-cyc-save', async () => {
    const roomId = (GF.$('dc-cyc-room') || {}).value;
    const campaign = ((GF.$('dc-cyc-campaign') || {}).value || '').trim();
    if (!roomId || !campaign) {
      GF.toast(AL('Room and campaign are required', 'Соба и кампања се задолжителни'), 'error'); return;
    }
    try {
      await GF.API.deconCycleCreate({ room_id: roomId, campaign,
        note: ((GF.$('dc-cyc-note') || {}).value || '').trim() || null });
      GF.closeModal('dc-cycle-modal');
      GF.WWF._decon.campaign = '';
      GF.toast(AL('Cycle started', 'Циклусот е започнат'), 'success');
      await GF.WWF.loadDecon();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // Same registration + read gate as the Facility board: every role above base
  // USER may READ the record; the write/release gating is per-action above.
  GF.WWF._registerFullPageView({
    key: 'decon', icon: 'shield',
    label: () => AL('Decontamination', 'Деконтаминација'),
    insertBefore: 'mywork',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
