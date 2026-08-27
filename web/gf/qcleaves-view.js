/* qcleaves-view.js — QC LIMS: water / stability / transport (Phase 2, unit 6).

   Three self-contained record types reached through /qc: water-quality results
   (PP-QC-SOP-014), the stability programme (QCSOP 018), and external-lab sample
   transports (PP-QC-SOP-012, with the five annex forms). Read = elevated;
   write = QC_MGR / QP / execs / ADMIN. QMS Studio zone, anchored 'qms-end'. */

(function () {
  GF.WWF._qcl = { water: null, stab: null, trn: null, q: '', tab: 'water', loading: false, error: null };

  // Shared QC/LIMS role gate (core.js GF.QC_WRITERS) — see that file's
  // comment; was a local copy-pasted array here.
  const canWrite = () => GF.QC_WRITERS.includes((GF.API.user || {}).role);
  const chip = (t, c) => `<span class="chip-opt" style="border-color:${c};color:${c}">${GF.esc(t)}</span>`;
  const GRADES = ['TW', 'BW', 'TR', 'RO'];
  const STAB_TYPES = ['LT', 'ACC', 'INT'];
  const TRN_ST = { draft: 'var(--ink-3)', in_transit: 'var(--blue)', received: 'var(--green)' };
  const TRN_NEXT = { draft: 'in_transit', in_transit: 'received' };

  GF.WWF.loadQcLeaves = async () => {
    const st = GF.WWF._qcl;
    // lseq, like every sibling QC view. qclTab() re-loads on each tab switch,
    // so a fast click through stab -> trn -> water leaves three loads racing
    // and the slowest used to paint its tab's data under whichever tab is
    // actually showing.
    const my = (st.lseq = (st.lseq || 0) + 1);
    st.loading = true; st.error = null;
    try {
      const tab = st.tab;
      const data = tab === 'stab' ? await GF.API.qcStability({})
        : tab === 'trn' ? await GF.API.qcTransports({})
        : await GF.API.qcWater({});
      if (my !== st.lseq) return;                 // superseded by a newer load
      if (tab === 'stab') st.stab = data;
      else if (tab === 'trn') st.trn = data;
      else st.water = data;
    } catch (e) { if (my === st.lseq) st.error = e.message; }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'qcleaves') GF.render.all();
  };
  GF.WWF.qclTab = (t) => { GF.WWF._qcl.tab = t; GF.WWF.loadQcLeaves(); };
  GF.WWF.qclFilter = (v) => { GF.WWF._qcl.q = v; GF.render.all(); GF.refocus('qcl-search'); };

  const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();

  GF.WWF.qclCreateWater = async () => {
    const location = mk('qcl-loc'), grade = mk('qcl-grade');
    if (!location) return GF.toast(AL('Location required', 'Потребна е локација'), 'error');
    const passed = mk('qcl-passed') !== 'fail';
    const ooe = mk('qcl-ooe');
    if (!passed && !ooe) return GF.toast(AL('OOE reason required for a failing result', 'Потребна е причина за OOE'), 'error');
    // `grade || 'RO'` is defensive only: #qcl-grade (GRADES, below) has no
    // blank option, so the select always yields a non-empty value and this
    // fallback cannot fire through the UI. Left in place as a safety net.
    const body = { location, grade: grade || 'RO', passed };
    if (!passed) body.ooe = ooe;
    const rd = mk('qcl-wdate'); if (rd) body.result_date = rd;
    const pj = mk('qcl-params'); if (pj) { try { body.parameters = JSON.parse(pj); } catch (e) { return GF.toast(AL('Parameters must be JSON', 'Параметрите мора да се JSON'), 'error'); } }
    try { const r = await GF.API.qcCreateWater(body); GF.toast(r.water_test_id); await GF.WWF.loadQcLeaves(); }
    catch (e) { GF.toast(e.message, 'error'); }
  };
  GF.WWF.qclToggleWater = async (id, passed) => {
    const patch = { passed: !passed };
    // Flipping PASS -> OOE: a failing water result demands a recorded reason,
    // same as the create-form gate above — never a bare unexplained fail.
    if (passed) {
      const ooe = prompt(AL('OOE reason (required):', 'Причина за OOE (задолжително):'));
      if (!ooe) return;
      patch.ooe = ooe;
    }
    try { await GF.API.qcPatchWater(id, patch); } catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcLeaves();
  };
  GF.WWF.qclCreateStab = async () => {
    const study_type = mk('qcl-stype') || 'LT', material_code = mk('qcl-smat');
    if (!material_code) return GF.toast(AL('Material required', 'Потребен е материјал'), 'error');
    const body = { study_type, material_code };
    ['material_name_en', 'material_name_mk'].forEach(k => { const v = mk('qcl-' + k); if (v) body[k] = v; });
    const b = mk('qcl-sbatches'); if (b) body.batches = b.split(',').map(s => s.trim()).filter(Boolean);
    const sd = mk('qcl-sstarted'); if (sd) body.started = sd;
    try { const r = await GF.API.qcCreateStability(body); GF.toast(r.study_id); await GF.WWF.loadQcLeaves(); }
    catch (e) { GF.toast(e.message, 'error'); }
  };
  GF.WWF.qclCloseStab = async (id) => {
    const shelf = prompt(AL('Assigned shelf life (e.g. 24 months):', 'Доделен рок на траење:')); if (shelf === null) return;
    try { await GF.API.qcPatchStability(id, { status: 'CLOSED', shelf_life: shelf || null }); GF.toast(AL('Closed', 'Затворено')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcLeaves();
  };
  // ── Stability pull-schedule DRAWER (design parity with leaves.html) ───────
  // Read-only side panel; distinct from qclCloseStab above (that CLOSES a
  // study — a write). Open finds the already-loaded study by id and paints the
  // derived timeline; nothing here fetches or fabricates.
  GF.WWF.qclSchedOpen = (id) => {
    const s = (GF.WWF._qcl.stab || []).find(x => x.id === id);
    const dr = document.getElementById('qcl-drawer'), sc = document.getElementById('qcl-scrim');
    if (!s || !dr || !sc) return;                 // demo/empty-safe: no study, no drawer
    dr.innerHTML = stabDrawer(s);
    dr.style.display = 'block'; sc.style.display = 'block';
    dr.classList.add('on'); sc.classList.add('on');
  };
  GF.WWF.qclSchedClose = () => {
    const dr = document.getElementById('qcl-drawer'), sc = document.getElementById('qcl-scrim');
    if (dr) { dr.classList.remove('on'); dr.style.display = 'none'; dr.innerHTML = ''; }
    if (sc) { sc.classList.remove('on'); sc.style.display = 'none'; }
  };
  GF.WWF.qclCreateTrn = async () => {
    const sample_id = mk('qcl-tsample');
    if (!sample_id) return GF.toast(AL('Sample required', 'Потребен е примерок'), 'error');
    const body = { sample_id };
    ['batch_id', 'external_lab'].forEach(k => { const v = mk('qcl-t' + k.split('_')[0]); if (v) body[k] = v; });
    const t = mk('qcl-ttests'); if (t) body.tests = t.split(',').map(s => s.trim()).filter(Boolean);
    try { const r = await GF.API.qcCreateTransport(body); GF.toast(r.transport_id); await GF.WWF.loadQcLeaves(); }
    catch (e) { GF.toast(e.message, 'error'); }
  };
  GF.WWF.qclAdvanceTrn = async (id, target) => {
    try { await GF.API.qcPatchTransport(id, { status: target }); } catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcLeaves();
  };
  GF.WWF.qclToggleForm = async (id, form, on) => {
    try { await GF.API.qcPatchTransport(id, { ['form_' + form]: !on }); } catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcLeaves();
  };

  const fld = (id, ph) => `<input id="${id}" placeholder="${GF.esc(ph)}">`;

  const waterList = () => {
    const st = GF.WWF._qcl, q = st.q.trim().toLowerCase();
    const rows = (st.water || []).filter(w => !q || (w.location || '').toLowerCase().includes(q) || (w.water_test_id || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return `<table class="qcp-table"><thead><tr><th>ID</th><th>${AL('Location', 'Локација')}</th><th>${AL('Grade', 'Класа')}</th><th>${AL('Date', 'Датум')}</th><th>${AL('Parameters', 'Параметри')}</th><th>${AL('Result', 'Резултат')}</th></tr></thead><tbody>${
      rows.map(w => {
        const P = w.parameters || {};
        const pstr = Object.keys(P).map(k => GF.esc(k + ': ' + P[k])).join(' · ');
        return `<tr><td class="mono">${GF.esc(w.water_test_id)}</td><td>${GF.esc(w.location)}</td><td>${GF.esc(w.grade)}</td>
        <td class="mono">${GF.esc(w.result_date || '—')}</td>
        <td class="ana-note">${pstr || '—'}</td>
        <td>${w.passed ? chip('PASS', 'var(--green)') : chip('OOE' + (w.ooe ? ' · ' + GF.esc(w.ooe) : ''), 'var(--red)')}
        ${canWrite() ? `<button class="btn btn-sm" onclick="GF.WWF.qclToggleWater('${w.id}',${w.passed})">${AL('flip', 'смени')}</button>` : ''}</td></tr>`;
      }).join('')
    }</tbody></table>`;
  };
  // ── Stability timeline: REAL fields only ────────────────────────────────
  // The qc_stability_studies row (see backend/app/api/qc/leaves.py _stab_out)
  // carries NO per-pull record — no per-timepoint dates, status or analytical
  // results. So the timeline is derived from exactly three real fields:
  //   • schedule  — free-text pull timepoints (e.g. "0, 3, 6, 12, 24 mo")
  //   • started   — the baseline (t0) anchor date
  //   • status    — IN_PROGRESS / CLOSED
  // A timepoint's DATE is started + N months (N parsed from the schedule
  // token); its dot is CLOSED→done, else scheduled-date-past→due, else pending.
  // Per-timepoint pull RESULTS (THC / water / TYMC in the mockup) have no
  // backing field and are DEFERRED, flagged in the drawer — never invented.
  const _addMonths = (iso, n) => {
    if (!iso) return null;
    const d = new Date(iso + 'T00:00:00');
    if (isNaN(d.getTime())) return null;
    d.setMonth(d.getMonth() + n);
    return d;
  };
  const _fmtDMY = (d) => (d instanceof Date && !isNaN(d.getTime()))
    ? [d.getDate(), d.getMonth() + 1].map(n => String(n).padStart(2, '0')).join('.') + '.' + d.getFullYear()
    : null;
  // Numbers in a stability schedule are conventionally MONTHS (0/3/6/12/24).
  // If a token carries a non-month unit we decline to place it on a date
  // rather than guess wrong — the label still shows, the date stays blank.
  const _tpMonths = (tok) => {
    if (/\b(wk|wks|week|weeks|d|day|days|yr|yrs|year|years)\b/i.test(tok)) return null;
    const m = String(tok).match(/\d+(?:\.\d+)?/);
    return m ? Number(m[0]) : null;
  };
  const _parseSchedule = (sched) => {
    if (!sched) return [];
    const flat = [];
    String(sched).split(/[,;/|]+/).map(t => t.trim()).filter(Boolean).forEach(seg => {
      // "0 3 6 12 24" (purely numeric, space-separated) → one point each
      if (/^[\d\s.]+$/.test(seg) && /\s/.test(seg)) seg.split(/\s+/).filter(Boolean).forEach(p => flat.push(p));
      else flat.push(seg);
    });
    return flat.map(tok => ({ label: tok, months: _tpMonths(tok) }));
  };
  const _stabTypeLbl = (t) => ({ LT: ['long-term', 'долгорочна'], ACC: ['accelerated', 'акцелерирана'], INT: ['intermediate', 'среднорочна'] }[t] || ['', '']);

  const stabDrawer = (s) => {
    const closed = s.status === 'CLOSED';
    const today = new Date(); today.setHours(0, 0, 0, 0);
    let tps = _parseSchedule(s.schedule);
    // No explicit schedule but a real start date → the baseline (t0) pull is
    // itself a real timepoint; show that rather than an empty timeline.
    if (!tps.length && s.started) tps = [{ label: AL('t0 · start', 't0 · почеток'), months: 0 }];
    const rows = tps.map(tp => {
      const dt = (tp.months != null && s.started) ? _addMonths(s.started, tp.months) : null;
      const ds = _fmtDMY(dt);
      let cls, en, mk;
      if (closed) { cls = 'done'; en = 'complete'; mk = 'завршено'; }
      else if (dt && dt.getTime() <= today.getTime()) { cls = 'due'; en = 'due'; mk = 'рок'; }
      else { cls = 'pend'; en = 'scheduled'; mk = 'закажано'; }
      const r = ds
        ? `<span class="mwl-tp-r mono">${GF.esc(ds)}</span>`
        : `<span class="mwl-tp-r mwl-blank mono">${AL('date not scheduled', 'датумот не е закажан')}</span>`;
      return `<div class="mwl-tp ${cls}"><span class="mwl-tp-dot"></span><span class="mwl-tp-m">${GF.esc(tp.label)}</span>${r}<span class="mwl-tp-s ${cls}">${AL(en, mk)}</span></div>`;
    }).join('');
    const tl = _stabTypeLbl(s.study_type);
    const matName = (GF.state.lang === 'mk' ? s.material_name_mk : s.material_name_en) || s.material_name_en || s.material_name_mk || '';
    const statusChip = closed
      ? chip(AL('Closed', 'Затворено') + (s.shelf_life ? ' · ' + s.shelf_life : ''), 'var(--green)')
      : chip(AL('In progress', 'Во тек'), 'var(--blue)');
    const meta = (k, v) => v ? `<div class="mwl-meta-k">${GF.esc(k)}</div><div class="mwl-meta-v">${v}</div>` : '';
    return `<div class="mwl-dr-hd">
      <button class="mwl-dr-cls" onclick="GF.WWF.qclSchedClose()" title="${AL('Close', 'Затвори')}">${GF.icon('x')}</button>
      <div class="mwl-dr-code mono">${GF.esc(s.study_id)}</div>
      <div class="mwl-dr-title"><span class="mwl-gd">${GF.esc(s.study_type)}</span> ${GF.esc(AL(tl[0], tl[1]))}</div>
    </div>
    <div class="mwl-dr-bd">
      <div class="mwl-dr-sec">${AL('Study', 'Студија')}</div>
      <div class="mwl-meta">
        ${meta(AL('Material', 'Материјал'), GF.esc(s.material_code || '—') + (matName ? ' · ' + GF.esc(matName) : ''))}
        ${meta(AL('Batches', 'Серии'), GF.esc((s.batches || []).join(', ')) || '—')}
        ${meta(AL('Started', 'Започната'), GF.esc(s.started || '—'))}
        ${meta(AL('Status', 'Статус'), statusChip)}
        ${meta(AL('Protocol', 'Протокол'), s.protocol ? GF.esc(s.protocol) : '')}
        ${meta(AL('Report', 'Извештај'), s.report ? GF.esc(s.report) : '')}
        ${meta(AL('Shelf-life', 'Рок на траење'), s.shelf_life ? GF.esc(s.shelf_life) : '')}
      </div>
      <div class="mwl-dr-sec">${AL('Timepoint pull schedule', 'Распоред на точки за земање')}</div>
      ${rows || `<div class="ana-note">${AL('No pull schedule or start date recorded.', 'Нема запишан распоред или датум на почеток.')}</div>`}
      <div class="ana-note mwl-defer">${AL('Dots show each timepoint’s schedule position (study start date + status). Per-timepoint pull results are not captured in the stability record yet.', 'Точките ја покажуваат позицијата по распоред за секоја точка (датум на почеток + статус). Резултатите по точка сè уште не се евидентираат.')}</div>
      ${s.notes ? `<div class="mwl-dr-sec">${AL('Notes', 'Белешки')}</div><div class="ana-note">${GF.esc(s.notes)}</div>` : ''}
    </div>`;
  };

  const stabList = () => {
    const st = GF.WWF._qcl, q = st.q.trim().toLowerCase();
    const rows = (st.stab || []).filter(s => !q || (s.material_code || '').toLowerCase().includes(q) || (s.study_id || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return `<table class="qcp-table"><thead><tr><th>ID</th><th>${AL('Type', 'Тип')}</th><th>${AL('Material', 'Материјал')}</th><th>${AL('Batches', 'Серии')}</th><th>${AL('Status', 'Статус')}</th></tr></thead><tbody>${
      rows.map(s => `<tr><td class="mono">${GF.esc(s.study_id)}</td><td>${GF.esc(s.study_type)}</td><td>${GF.esc(s.material_code)}</td>
        <td>${GF.esc((s.batches || []).join(', '))}</td>
        <td>${s.status === 'CLOSED' ? chip(AL('Closed', 'Затворено') + (s.shelf_life ? ' · ' + GF.esc(s.shelf_life) : ''), 'var(--green)') : chip(AL('In progress', 'Во тек'), 'var(--blue)')}
        <button class="btn btn-sm mwl-sched-btn" onclick="GF.WWF.qclSchedOpen('${s.id}')" title="${AL('Pull schedule', 'Распоред на точки')}">${GF.icon('timeline')} ${AL('Schedule', 'Распоред')}</button>
        ${canWrite() && s.status !== 'CLOSED' ? `<button class="btn btn-sm" onclick="GF.WWF.qclCloseStab('${s.id}')">${AL('Close', 'Затвори')}</button>` : ''}</td></tr>`).join('')
    }</tbody></table>`;
  };
  const trnList = () => {
    const st = GF.WWF._qcl, q = st.q.trim().toLowerCase();
    const rows = (st.trn || []).filter(t => !q || (t.sample_id || '').toLowerCase().includes(q) || (t.transport_id || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    const FORMS = ['sar', 'moia', 'tmcoc', 'coo', 'fin'];
    return rows.map(t => {
      const F = t.forms || {};
      return `<div class="qms-row" style="flex-wrap:wrap;gap:6px">
      <span class="mono qms-code">${GF.esc(t.transport_id)}</span>
      <span class="qms-title">${GF.esc(t.sample_id)} <span class="ana-note">→ ${GF.esc(t.external_lab || '?')}${(t.tests && t.tests.length) ? ' · ' + GF.esc(t.tests.join(', ')) : ''}</span></span>
      ${chip(t.status, TRN_ST[t.status] || 'var(--ink-3)')}
      <span style="display:flex;gap:3px">${FORMS.map(f => `<span class="chip-opt" style="cursor:${canWrite() ? 'pointer' : 'default'};border-color:${F[f] ? 'var(--green)' : 'var(--ink-4)'};color:${F[f] ? 'var(--green)' : 'var(--ink-3)'}" ${canWrite() ? `onclick="GF.WWF.qclToggleForm('${t.id}','${f}',${!!F[f]})"` : ''}>${f.toUpperCase()}</span>`).join('')}</span>
      ${canWrite() && TRN_NEXT[t.status] ? `<button class="btn btn-sm" onclick="GF.WWF.qclAdvanceTrn('${t.id}','${TRN_NEXT[t.status]}')">→ ${GF.esc(TRN_NEXT[t.status])}</button>` : ''}
    </div>`;
    }).join('');
  };

  GF.views.qcleaves = () => {
    const st = GF.WWF._qcl;
    if (!st.water && !st.stab && !st.trn && !st.loading && !st.error) GF.WWF.loadQcLeaves();
    const head = GF.viewHead('qc_leaves', 'qc_leaves_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — water quality (PP-QC-SOP-014), the stability programme (QCSOP 018), and external-lab sample transport with its annex forms (PP-QC-SOP-012).',
      'QMS Студио — квалитет на вода (PP-QC-SOP-014), програма за стабилност (QCSOP 018) и транспорт на мостри до надворешна лабораторија со анекс-форми (PP-QC-SOP-012).')}</div>`;
    const tabs = `<div class="qms-dl" style="margin-bottom:10px">
      ${[['water', AL('Water', 'Вода')], ['stab', AL('Stability', 'Стабилност')], ['trn', AL('Transport', 'Транспорт')]].map(([k, l]) =>
        `<button class="btn btn-sm ${st.tab === k ? 'btn-primary' : ''}" onclick="GF.WWF.qclTab('${k}')">${l}</button>`).join('')}
    </div>`;
    if (st.loading) return head + zone + tabs + `<div class="mw-skel" style="height:200px"></div>`;
    if (st.error) return head + zone + tabs + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap"><span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span><button class="btn btn-sm" onclick="GF.WWF.loadQcLeaves()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    let create = '', list = '', extra = '';
    if (st.tab === 'stab') {
      create = canWrite() ? `<div class="panel ana-panel" style="margin-bottom:12px"><div class="ana-pt" style="margin-bottom:8px">${AL('New stability study', 'Нова студија за стабилност')}</div><div class="qcs-form">
        <select id="qcl-stype">${STAB_TYPES.map(t => `<option value="${t}">${t}</option>`).join('')}</select>${fld('qcl-smat', AL('Material code', 'Код'))}
        ${fld('qcl-material_name_en', AL('Name (EN)', 'Име (EN)'))}${fld('qcl-material_name_mk', AL('Name (MK)', 'Име (MK)'))}
        ${fld('qcl-sbatches', AL('Batches (comma)', 'Серии (запирки)'))}<input id="qcl-sstarted" type="date">
        <button class="btn btn-sm btn-primary" onclick="GF.WWF.qclCreateStab()">${GF.t('create_task') || 'Create'}</button></div></div>` : '';
      list = stabList();
      // Pull-schedule drawer scaffold — empty + hidden until a row is opened,
      // so the control-wiring scan sees only the already-resolvable close
      // handler and no per-study inline handlers on first render.
      extra = `<div id="qcl-scrim" class="mwl-scrim" style="display:none" onclick="GF.WWF.qclSchedClose()"></div><aside id="qcl-drawer" class="mwl-drawer" style="display:none"></aside>`;
    } else if (st.tab === 'trn') {
      create = canWrite() ? `<div class="panel ana-panel" style="margin-bottom:12px"><div class="ana-pt" style="margin-bottom:8px">${AL('New transport', 'Нов транспорт')}</div><div class="qcs-form">
        ${fld('qcl-tsample', AL('Sample id', 'Примерок'))}${fld('qcl-tbatch', AL('Batch', 'Серија'))}${fld('qcl-texternal', AL('External lab', 'Надв. лаб.'))}${fld('qcl-ttests', AL('Tests (comma)', 'Тестови (запирки)'))}
        <button class="btn btn-sm btn-primary" onclick="GF.WWF.qclCreateTrn()">${GF.t('create_task') || 'Create'}</button></div></div>` : '';
      list = `<div class="qms-list">${trnList()}</div>`;
    } else {
      create = canWrite() ? `<div class="panel ana-panel" style="margin-bottom:12px"><div class="ana-pt" style="margin-bottom:8px">${AL('New water result', 'Нов резултат за вода')}</div><div class="qcs-form">
        ${fld('qcl-loc', AL('Location (SL code)', 'Локација (SL)'))}<select id="qcl-grade">${GRADES.map(g => `<option value="${g}">${g}</option>`).join('')}</select>
        <input id="qcl-wdate" type="date">${fld('qcl-params', AL('Parameters (JSON)', 'Параметри (JSON)'))}
        <select id="qcl-passed" title="${AL('Result', 'Резултат')}"><option value="pass">PASS</option><option value="fail">OOE</option></select>
        ${fld('qcl-ooe', AL('OOE reason (if failing)', 'Причина за OOE (ако не поминал)'))}
        <button class="btn btn-sm btn-primary" onclick="GF.WWF.qclCreateWater()">${GF.t('create_task') || 'Create'}</button></div></div>` : '';
      list = waterList();
    }
    return head + zone + tabs + create + `<div class="panel ana-panel">
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
        <div class="ana-pt" style="margin:0">${AL('Records', 'Записи')}</div>
        <input id="qcl-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qclFilter(this.value)"></div>
      ${list}</div>` + extra;
  };

  GF.WWF._registerFullPageView({
    key: 'qcleaves', icon: 'droplet',
    label: () => AL('QC water/stability', 'КК вода/стабилност'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });

  // Esc closes the pull-schedule drawer — registered once, and a no-op on any
  // other view (the drawer element only exists on the stability tab).
  if (!GF.WWF._qclSchedKey) {
    GF.WWF._qclSchedKey = true;
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      const dr = document.getElementById('qcl-drawer');
      if (dr && dr.style.display !== 'none') GF.WWF.qclSchedClose();
    });
  }
})();
