/* qccustody-view.js — QC LIMS: custody cluster (Phase 2, unit 5).

   Field-to-lab traceability (ALCOA++). Three linked records reached through
   /qc: a Sampling Request (RQS, PP-QC-SOP-017 — a department asks QC to sample
   a material/batch; a 24-hour QC registration window is tracked), a Sample
   Field Record (SFR — the field operation: barrels, destination, transport
   times), and the chain of custody (every handoff of a sample). Read = elevated;
   write = QC_MGR / QP / execs / ADMIN. QMS Studio zone, anchored 'qms-end'. */

(function () {
  GF.WWF._qccus = { rqs: null, sfr: null, sel: null, detail: null, custody: {},
                    q: '', status: '', tab: 'rqs', loading: false, error: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);

  const RQS_ST = {
    OPEN:        { en: 'Open', mk: 'Отворено', c: 'var(--orange)' },
    REGISTERED:  { en: 'Registered', mk: 'Регистрирано', c: 'var(--blue)' },
    IN_PROGRESS: { en: 'In progress', mk: 'Во тек', c: 'var(--violet)' },
    COMPLETED:   { en: 'Completed', mk: 'Завршено', c: 'var(--green)' },
    CANCELLED:   { en: 'Cancelled', mk: 'Откажано', c: 'var(--ink-3)' },
  };
  const RQS_NEXT = { OPEN: 'REGISTERED', REGISTERED: 'IN_PROGRESS', IN_PROGRESS: 'COMPLETED' };
  const SFR_ST = {
    CREATED:   { en: 'Created', mk: 'Создадено', c: 'var(--ink-3)' },
    IN_FIELD:  { en: 'In field', mk: 'На терен', c: 'var(--blue)' },
    COMPLETED: { en: 'Completed', mk: 'Завршено', c: 'var(--green)' },
    CANCELLED: { en: 'Cancelled', mk: 'Откажано', c: 'var(--ink-3)' },
  };
  const SFR_NEXT = { CREATED: 'IN_FIELD', IN_FIELD: 'COMPLETED' };
  const XFER = ['FIELD_TO_LAB', 'LAB_INTERNAL', 'LAB_TO_DISPOSAL', 'STABILITY_TRANSFER'];

  const chip = (t, c) => `<span class="chip-opt" style="border-color:${c};color:${c}">${GF.esc(t)}</span>`;
  const stChip = (m, s) => { const x = m[s] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' }; return chip(AL(x.en, x.mk), x.c); };
  const dt = (s) => s ? GF.esc(String(s).slice(0, 16).replace('T', ' ')) : '—';

  GF.WWF.loadQcCustody = async () => {
    const st = GF.WWF._qccus;
    st.loading = true; st.error = null;
    try {
      if (st.tab === 'sfr') st.sfr = await GF.API.qcSfr(st.status ? { status: st.status } : {});
      else st.rqs = await GF.API.qcRqs(st.status ? { status: st.status } : {});
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'qccustody') GF.render.all();
  };
  GF.WWF.qcCusTab = (t) => { const st = GF.WWF._qccus; st.tab = t; st.sel = null; st.detail = null; st.status = ''; GF.WWF.loadQcCustody(); };
  GF.WWF.qcCusFilter = (v) => { GF.WWF._qccus.q = v; GF.render.all(); };
  GF.WWF.qcCusStatus = (v) => { GF.WWF._qccus.status = v; GF.WWF.loadQcCustody(); };

  GF.WWF.qcCusPick = async (id) => {
    const st = GF.WWF._qccus;
    if (st.sel === id) { st.sel = null; st.detail = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; GF.render.all();
    try {
      st.detail = st.tab === 'sfr' ? await GF.API.qcSfrOne(id) : await GF.API.qcRqsOne(id);
      if (st.tab === 'sfr' && st.detail.sample_id)
        st.custody[st.detail.sample_id] = await GF.API.qcCustody(st.detail.sample_id).catch(() => []);
    } catch (e) { GF.toast(e.message, 'error'); }
    if (GF.state.view === 'qccustody') GF.render.all();
  };

  GF.WWF.qcRqsAdvance = async (id, target) => {
    try { await GF.API.qcPatchRqs(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.WWF._qccus.sel = null; GF.WWF._qccus.detail = null; await GF.WWF.loadQcCustody();
  };
  GF.WWF.qcSfrAdvance = async (id, target) => {
    try { await GF.API.qcPatchSfr(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.WWF._qccus.sel = null; GF.WWF._qccus.detail = null; await GF.WWF.loadQcCustody();
  };
  GF.WWF.qcRqsCreate = async () => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const material_code = mk('qcu-mat'), originating_department = mk('qcu-dept');
    if (!material_code || !originating_department) return GF.toast(AL('Material and department are required', 'Потребни се материјал и оддел'), 'error');
    const body = { material_code, originating_department };
    ['material_name_en', 'material_name_mk', 'batch_id', 'assigned_sp_type'].forEach(k => { const v = mk('qcu-' + k); if (v) body[k] = v; });
    try { const r = await GF.API.qcCreateRqs(body); GF.toast(r.rqs_number + ' ' + AL('opened', 'отворено')); await GF.WWF.loadQcCustody(); GF.WWF.qcCusPick(r.id); }
    catch (e) { GF.toast(e.message, 'error'); }
  };
  GF.WWF.qcSfrCreate = async () => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const sampling_location = mk('qcu-loc'), destination_facility = mk('qcu-dest');
    if (!sampling_location || !destination_facility) return GF.toast(AL('Location and destination are required', 'Потребни се локација и дестинација'), 'error');
    const body = { sampling_location, destination_facility };
    const coords = mk('qcu-coords'); if (coords) body.sampling_coordinates = coords;
    const nc = mk('qcu-nc'); if (nc) body.num_containers = parseInt(nc, 10) || null;
    const barrels = mk('qcu-barrels'); if (barrels) body.barrel_numbers = barrels.split(',').map(s => s.trim()).filter(Boolean);
    try { const r = await GF.API.qcCreateSfr(body); GF.toast(r.sfr_number + ' ' + AL('created', 'создадено')); await GF.WWF.loadQcCustody(); GF.WWF.qcCusPick(r.id); }
    catch (e) { GF.toast(e.message, 'error'); }
  };
  GF.WWF.qcCusLogTransfer = async (sampleId) => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const body = { transfer_type: mk('qcu-xtype') || null, to_location: mk('qcu-xto') || null, transfer_reason: mk('qcu-xreason') || null };
    try { await GF.API.qcAddCustody(sampleId, body); GF.toast(AL('Transfer logged', 'Трансферот е запишан')); GF.WWF._qccus.custody[sampleId] = await GF.API.qcCustody(sampleId).catch(() => []); GF.render.all(); }
    catch (e) { GF.toast(e.message, 'error'); }
  };

  const fld = (id, ph) => `<input id="${id}" placeholder="${GF.esc(ph)}">`;

  const rqsDetail = (r) => {
    const nxt = RQS_NEXT[r.status];
    return `<div class="qms-detail"><div class="qms-dgrid">
      <span>${AL('RQS', 'RQS')}</span><b class="mono">${GF.esc(r.rqs_number)}</b>
      <span>${AL('Material', 'Материјал')}</span><b>${GF.esc(r.material_code)}</b>
      <span>${AL('Department', 'Оддел')}</span><b>${GF.esc(r.originating_department)}</b>
      <span>${AL('Status', 'Статус')}</span><b>${stChip(RQS_ST, r.status)}</b>
      ${r.batch_id ? `<span>${AL('Batch', 'Серија')}</span><b>${GF.esc(r.batch_id)}</b>` : ''}
      <span>${AL('Reg. deadline', 'Рок за рег.')}</span><b class="mono">${dt(r.registration_deadline)}</b>
      ${r.registered_at ? `<span>${AL('Registered', 'Регистрирано')}</span><b class="mono">${dt(r.registered_at)} ${r.registration_window_met === false ? chip(AL('late', 'доцна'), 'var(--red)') : (r.registration_window_met ? chip(AL('on time', 'навреме'), 'var(--green)') : '')}</b>` : ''}
    </div>${canWrite() && nxt ? `<div class="qms-dl" style="margin-top:8px">
      <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcRqsAdvance('${r.id}','${nxt}')">${AL('Advance to', 'Напредувај до')} ${GF.esc(AL((RQS_ST[nxt]||{}).en, (RQS_ST[nxt]||{}).mk))}</button>
      ${r.status !== 'COMPLETED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcRqsAdvance('${r.id}','CANCELLED')">${AL('Cancel', 'Откажи')}</button>` : ''}
    </div>` : ''}</div>`;
  };

  const custodyPanel = (sampleId) => {
    const rows = (GF.WWF._qccus.custody[sampleId] || []);
    const list = rows.map(x => `<tr><td class="mono">${dt(x.transferred_at)}</td><td>${GF.esc(x.transfer_type || '—')}</td><td>${GF.esc(x.to_location || '')}</td><td>${GF.esc(x.transfer_reason || '')}</td></tr>`).join('');
    return `<div style="margin-top:12px" class="ana-pt">${AL('Chain of custody', 'Ланец на чување')}</div>
      <table class="qcp-table"><thead><tr><th>${AL('When', 'Кога')}</th><th>${AL('Type', 'Тип')}</th><th>${AL('To', 'До')}</th><th>${AL('Reason', 'Причина')}</th></tr></thead>
      <tbody>${list || `<tr><td colspan="4" class="ana-note">${AL('No custody transfers', 'Нема трансфери')}</td></tr>`}</tbody></table>
      ${canWrite() ? `<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;align-items:center">
        <select id="qcu-xtype"><option value="">${AL('type…', 'тип…')}</option>${XFER.map(t => `<option value="${t}">${t}</option>`).join('')}</select>
        <input id="qcu-xto" placeholder="${AL('to location', 'до локација')}"><input id="qcu-xreason" placeholder="${AL('reason', 'причина')}" style="flex:1">
        <button class="btn btn-sm" onclick="GF.WWF.qcCusLogTransfer('${sampleId}')">+ ${AL('Log transfer', 'Запиши трансфер')}</button>
      </div>` : ''}`;
  };

  const sfrDetail = (r) => {
    const nxt = SFR_NEXT[r.status];
    return `<div class="qms-detail"><div class="qms-dgrid">
      <span>${AL('SFR', 'SFR')}</span><b class="mono">${GF.esc(r.sfr_number)}</b>
      <span>${AL('Location', 'Локација')}</span><b>${GF.esc(r.sampling_location)}</b>
      <span>${AL('Destination', 'Дестинација')}</span><b>${GF.esc(r.destination_facility)}</b>
      <span>${AL('Status', 'Статус')}</span><b>${stChip(SFR_ST, r.status)}</b>
      ${(r.barrel_numbers && r.barrel_numbers.length) ? `<span>${AL('Barrels', 'Буриња')}</span><b>${GF.esc(r.barrel_numbers.join(', '))}</b>` : ''}
      ${r.num_containers != null ? `<span>${AL('Containers', 'Контејнери')}</span><b>${r.num_containers}</b>` : ''}
    </div>${canWrite() && nxt ? `<div class="qms-dl" style="margin-top:8px">
      <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSfrAdvance('${r.id}','${nxt}')">${AL('Advance to', 'Напредувај до')} ${GF.esc(AL((SFR_ST[nxt]||{}).en, (SFR_ST[nxt]||{}).mk))}</button>
      ${r.status !== 'COMPLETED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcSfrAdvance('${r.id}','CANCELLED')">${AL('Cancel', 'Откажи')}</button>` : ''}
    </div>` : ''}
    ${r.sample_id ? custodyPanel(r.sample_id) : `<div class="ana-note" style="margin-top:8px">${AL('Link a sample to record its chain of custody.', 'Поврзете примерок за да се води ланецот на чување.')}</div>`}</div>`;
  };

  const listRows = () => {
    const st = GF.WWF._qccus;
    const q = st.q.trim().toLowerCase();
    if (st.tab === 'sfr') {
      const rows = (st.sfr || []).filter(r => !q || (r.sfr_number || '').toLowerCase().includes(q) || (r.sampling_location || '').toLowerCase().includes(q));
      if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
      return rows.map(r => `<div class="qms-row ${st.sel === r.id ? 'on' : ''}" onclick="GF.WWF.qcCusPick('${r.id}')">
        <span class="mono qms-code">${GF.esc(r.sfr_number)}</span>
        <span class="qms-title">${GF.esc(r.sampling_location)} <span class="ana-note">→ ${GF.esc(r.destination_facility)}</span></span>
        ${stChip(SFR_ST, r.status)}</div>
        ${st.sel === r.id ? (st.detail ? sfrDetail(st.detail) : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`) : ''}`).join('');
    }
    const rows = (st.rqs || []).filter(r => !q || (r.rqs_number || '').toLowerCase().includes(q) || (r.material_code || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(r => `<div class="qms-row ${st.sel === r.id ? 'on' : ''}" onclick="GF.WWF.qcCusPick('${r.id}')">
      <span class="mono qms-code">${GF.esc(r.rqs_number)}</span>
      <span class="qms-title">${GF.esc(r.material_code)} <span class="ana-note">${GF.esc(r.originating_department)}</span></span>
      ${stChip(RQS_ST, r.status)}</div>
      ${st.sel === r.id ? (st.detail ? rqsDetail(st.detail) : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`) : ''}`).join('');
  };

  GF.views.qccustody = () => {
    const st = GF.WWF._qccus;
    if (!st.rqs && !st.sfr && !st.loading && !st.error) GF.WWF.loadQcCustody();
    const head = GF.viewHead('qc_custody', 'qc_custody_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — custody cluster: sampling requests (24-hour QC registration window), field sample records (barrels, destination, transport), and the ALCOA++ chain of custody per sample.',
      'QMS Студио — кластер за чување: барања за земање мостри (24-часовен прозорец за регистрација), теренски записи за мостри (буриња, дестинација, транспорт) и ALCOA++ ланец на чување по примерок.')}</div>`;
    const tabs = `<div class="qms-dl" style="margin-bottom:10px">
      <button class="btn btn-sm ${st.tab === 'rqs' ? 'btn-primary' : ''}" onclick="GF.WWF.qcCusTab('rqs')">${AL('Sampling requests', 'Барања за мостри')}</button>
      <button class="btn btn-sm ${st.tab === 'sfr' ? 'btn-primary' : ''}" onclick="GF.WWF.qcCusTab('sfr')">${AL('Field records', 'Теренски записи')}</button>
    </div>`;
    if (st.loading || (!st.rqs && !st.sfr && !st.error)) return head + zone + tabs + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    if (st.error) return head + zone + tabs + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap"><span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span><button class="btn btn-sm" onclick="GF.WWF.loadQcCustody()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    const create = canWrite() ? (st.tab === 'sfr' ? `
      <div class="panel ana-panel" style="margin-bottom:12px"><div class="ana-pt" style="margin-bottom:8px">${AL('New field record', 'Нов теренски запис')}</div>
        <div class="qcs-form">
          ${fld('qcu-loc', AL('Sampling location', 'Локација'))}${fld('qcu-dest', AL('Destination facility', 'Дестинација'))}
          ${fld('qcu-coords', AL('GPS (lat,long)', 'ГПС'))}${fld('qcu-barrels', AL('Barrels (comma-sep)', 'Буриња (запирки)'))}
          <input id="qcu-nc" type="number" min="0" placeholder="${AL('# containers', '# контејнери')}">
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSfrCreate()">${GF.t('create_task') || 'Create'}</button>
        </div></div>` : `
      <div class="panel ana-panel" style="margin-bottom:12px"><div class="ana-pt" style="margin-bottom:8px">${AL('New sampling request', 'Ново барање за мостри')}</div>
        <div class="qcs-form">
          ${fld('qcu-mat', AL('Material code', 'Код на материјал'))}${fld('qcu-dept', AL('Originating department', 'Оддел'))}
          ${fld('qcu-material_name_en', AL('Material (EN)', 'Материјал (EN)'))}${fld('qcu-material_name_mk', AL('Material (MK)', 'Материјал (MK)'))}
          ${fld('qcu-batch_id', AL('Batch (optional)', 'Серија (опц.)'))}${fld('qcu-assigned_sp_type', AL('SP type (SP_01..)', 'СП тип'))}
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcRqsCreate()">${GF.t('create_task') || 'Create'}</button>
        </div></div>`) : '';
    const statuses = st.tab === 'sfr' ? Object.keys(SFR_ST) : Object.keys(RQS_ST);
    return head + zone + tabs + create + `<div class="panel ana-panel">
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
        <div class="ana-pt" style="margin:0">${st.tab === 'sfr' ? AL('Field records', 'Теренски записи') : AL('Sampling requests', 'Барања за мостри')}</div>
        <input class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcCusFilter(this.value)">
        <select onchange="GF.WWF.qcCusStatus(this.value)"><option value="">${AL('All statuses', 'Сите статуси')}</option>${statuses.map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}</select>
      </div>
      <div class="qms-list">${listRows()}</div></div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qccustody', icon: 'git-branch',
    label: () => AL('QC custody', 'КК чување'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
