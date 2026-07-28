/* qcleaves-view.js — QC LIMS: water / stability / transport (Phase 2, unit 6).

   Three self-contained record types reached through /qc: water-quality results
   (PP-QC-SOP-014), the stability programme (QCSOP 018), and external-lab sample
   transports (PP-QC-SOP-012, with the five annex forms). Read = elevated;
   write = QC_MGR / QP / execs / ADMIN. QMS Studio zone, anchored 'qms-end'. */

(function () {
  GF.WWF._qcl = { water: null, stab: null, trn: null, q: '', tab: 'water', loading: false, error: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);
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
  const stabList = () => {
    const st = GF.WWF._qcl, q = st.q.trim().toLowerCase();
    const rows = (st.stab || []).filter(s => !q || (s.material_code || '').toLowerCase().includes(q) || (s.study_id || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return `<table class="qcp-table"><thead><tr><th>ID</th><th>${AL('Type', 'Тип')}</th><th>${AL('Material', 'Материјал')}</th><th>${AL('Batches', 'Серии')}</th><th>${AL('Status', 'Статус')}</th></tr></thead><tbody>${
      rows.map(s => `<tr><td class="mono">${GF.esc(s.study_id)}</td><td>${GF.esc(s.study_type)}</td><td>${GF.esc(s.material_code)}</td>
        <td>${GF.esc((s.batches || []).join(', '))}</td>
        <td>${s.status === 'CLOSED' ? chip(AL('Closed', 'Затворено') + (s.shelf_life ? ' · ' + GF.esc(s.shelf_life) : ''), 'var(--green)') : chip(AL('In progress', 'Во тек'), 'var(--blue)')}
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
    let create = '', list = '';
    if (st.tab === 'stab') {
      create = canWrite() ? `<div class="panel ana-panel" style="margin-bottom:12px"><div class="ana-pt" style="margin-bottom:8px">${AL('New stability study', 'Нова студија за стабилност')}</div><div class="qcs-form">
        <select id="qcl-stype">${STAB_TYPES.map(t => `<option value="${t}">${t}</option>`).join('')}</select>${fld('qcl-smat', AL('Material code', 'Код'))}
        ${fld('qcl-material_name_en', AL('Name (EN)', 'Име (EN)'))}${fld('qcl-material_name_mk', AL('Name (MK)', 'Име (MK)'))}
        ${fld('qcl-sbatches', AL('Batches (comma)', 'Серии (запирки)'))}<input id="qcl-sstarted" type="date">
        <button class="btn btn-sm btn-primary" onclick="GF.WWF.qclCreateStab()">${GF.t('create_task') || 'Create'}</button></div></div>` : '';
      list = stabList();
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
      ${list}</div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qcleaves', icon: 'droplet',
    label: () => AL('QC water/stability', 'КК вода/стабилност'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
