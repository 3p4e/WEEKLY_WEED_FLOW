/* qcoos-view.js — QC LIMS: OOS investigations + CAPA (Phase 2, unit 4).

   An out-of-specification (OOS/OOT/OOE/OOC) investigation reached through
   /qc/oos. A failing result (unit 3) is the trigger; the record walks the GxP
   two-phase flow — Phase I laboratory investigation → Phase II full/root-cause
   investigation → QP disposition → close. Closing the OOS and setting a batch
   disposition (RELEASE/REJECT/REPROCESS/RETAIN) are Qualified-Person decisions
   (Annex 16 — QP or ADMIN ONLY, backend-gated; mirrored by canQP() here;
   executives are business leadership, not a GMP quality role). The register
   is append-only.

   CAPA is not a separate record: it is derived at read time from the OOS rows
   (/qc/capa), so the CAPA register panel here is a live view of OOS state.
   Read = elevated; write = QC_MGR / QP / execs / ADMIN. QMS Studio zone,
   anchored 'qms-end'. */

(function () {
  GF.WWF._qcoos = { rows: null, sel: null, detail: null, capa: null,
                    q: '', status: '', tab: 'oos', loading: false, error: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const _QP = ['ADMIN', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);
  const canQP = () => _QP.includes((GF.API.user || {}).role);

  const ST = {
    OPEN:     { en: 'Open', mk: 'Отворено', c: 'var(--orange)' },
    PHASE_I:  { en: 'Phase I', mk: 'Фаза I', c: 'var(--blue)' },
    PHASE_II: { en: 'Phase II', mk: 'Фаза II', c: 'var(--violet)' },
    CLOSED:   { en: 'Closed', mk: 'Затворено', c: 'var(--green)' },
  };
  const NEXT = { OPEN: 'PHASE_I', PHASE_I: 'PHASE_II', PHASE_II: 'CLOSED' };
  const QP_TARGETS = { CLOSED: 1 };
  const TYPES = ['OOS', 'OOT', 'OOE', 'OOC'];
  const RISK = { HIGH: 'var(--red)', MEDIUM: 'var(--orange)', LOW: 'var(--ink-3)' };
  const DISP = { RELEASE: 'var(--green)', REJECT: 'var(--red)', REPROCESS: 'var(--violet)', RETAIN: 'var(--ink-3)' };
  const CAPA_C = { OPEN: 'var(--orange)', IN_PROGRESS: 'var(--blue)', EFFECTIVE: 'var(--violet)', CLOSED: 'var(--green)' };

  const chip = (txt, c) => `<span class="chip-opt" style="border-color:${c};color:${c}">${GF.esc(txt)}</span>`;
  const stChip = (s) => { const m = ST[s] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' }; return chip(AL(m.en, m.mk), m.c); };

  GF.WWF.loadQcOos = async () => {
    const st = GF.WWF._qcoos;
    st.loading = true; st.error = null;
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      const q = {}; if (st.status) q.status = st.status;
      const rows = await GF.API.qcOos(q);
      if (my !== st.lseq) return;
      st.rows = rows;
      st.capa = await GF.API.qcCapa({}).catch(() => []);
    } catch (e) { if (my === st.lseq) st.error = e.message; }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'qcoos') GF.render.all();
  };

  GF.WWF.qcOosPick = async (id) => {
    const st = GF.WWF._qcoos;
    if (st.sel === id) { st.sel = null; st.detail = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; GF.render.all();
    try { const d = await GF.API.qcOosOne(id); if (st.sel === id) st.detail = d; }
    catch (e) { if (st.sel === id) GF.toast(e.message, 'error'); }
    if (st.sel === id && GF.state.view === 'qcoos') GF.render.all();
  };
  GF.WWF.qcOosFilter = (v) => { GF.WWF._qcoos.q = v; GF.render.all(); GF.refocus('qoo-search'); };
  GF.WWF.qcOosStatus = async (v) => { GF.WWF._qcoos.status = v; await GF.WWF.loadQcOos(); GF.refocus('qoo-status'); };
  GF.WWF.qcOosTab = (t) => { GF.WWF._qcoos.tab = t; GF.render.all(); };

  const _reload = async (id) => {
    await GF.WWF.loadQcOos();
    if (GF.WWF._qcoos.sel === id) { GF.WWF._qcoos.detail = await GF.API.qcOosOne(id).catch(() => null); GF.render.all(); }
  };

  GF.WWF.qcOosAdvance = async (id, target) => {
    try { await GF.API.qcPatchOos(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcOosDisposition = async (id) => {
    const disp = (document.getElementById('qoo-disp') || {}).value || '';
    const reason = ((document.getElementById('qoo-disp-reason') || {}).value || '').trim();
    if (!disp) return GF.toast(AL('Pick a disposition', 'Изберете диспозиција'), 'error');
    try { await GF.API.qcPatchOos(id, { disposition: disp, disposition_reason: reason || null }); GF.toast(AL('Recorded', 'Запишано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcOosSavePhase = async (id) => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const body = {};
    ['lab_investigation_result', 'root_cause_category', 'root_cause_description',
     'impact_assessment', 'capa_reference', 'effectiveness_check_result'].forEach(k => {
      const v = mk('qoo-' + k); if (v) body[k] = v;
    });
    const eff = mk('qoo-effectiveness_check_date'); if (eff) body.effectiveness_check_date = eff;
    if (!Object.keys(body).length) return;
    try { await GF.API.qcPatchOos(id, body); GF.toast(AL('Saved', 'Зачувано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcOosAddEvent = async (id) => {
    const action = ((document.getElementById('qoo-ev-action') || {}).value || '').trim();
    const details = ((document.getElementById('qoo-ev-details') || {}).value || '').trim();
    if (!action) return GF.toast(AL('Action required', 'Потребна е акција'), 'error');
    try { await GF.API.qcAddOosRegister(id, { action, details: details || null }); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcOosNotify = async (id) => {
    const part = (document.getElementById('qoo-nt-part') || {}).value || 'A';
    const message = ((document.getElementById('qoo-nt-msg') || {}).value || '').trim();
    try { await GF.API.qcAddOosNotify(id, { part, message: message || null, recipients: [] }); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcOosAck = async (id, nid) => {
    try { await GF.API.qcAckOosNotify(id, nid); } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcOosCreate = async () => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const batch_id = mk('qoo-batch');
    if (!batch_id) return GF.toast(AL('Batch is required', 'Потребна е серија'), 'error');
    const body = { batch_id, oos_type: mk('qoo-type') || 'OOS' };
    ['test_name', 'material_code'].forEach(k => { const v = mk('qoo-' + k); if (v) body[k] = v; });
    const risk = mk('qoo-risk'); if (risk) body.risk_level = risk;
    const dd = mk('qoo-detection'); if (dd) body.detection_date = dd;
    const dl = mk('qoo-deadline'); if (dl) body.timeline_deadline = dl;
    try {
      const oos = await GF.API.qcCreateOos(body);
      GF.toast(oos.oos_number + ' ' + AL('opened', 'отворено'));
      await GF.WWF.loadQcOos(); GF.WWF.qcOosPick(oos.id);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  const fld = (id, ph, val) => `<input id="${id}" placeholder="${GF.esc(ph)}" value="${GF.esc(val || '')}" style="width:100%">`;
  const area = (id, ph, val) => `<textarea id="${id}" placeholder="${GF.esc(ph)}" rows="2" style="width:100%">${GF.esc(val || '')}</textarea>`;

  const detail = (d) => {
    const o = d.oos;
    const nxt = NEXT[o.status];
    const canClose = o.status !== 'CLOSED';
    const reg = (d.register || []).map(e => `
      <tr><td class="mono">${GF.esc((e.created_at || '').slice(0, 16).replace('T', ' '))}</td>
      <td>${GF.esc(e.action)}</td><td>${GF.esc(e.details || '')}</td></tr>`).join('');
    const notifs = (d.notifications || []).map(n => `
      <div class="qms-row">
        <span class="mono">${AL('Part', 'Дел')} ${GF.esc(n.part)}</span>
        <span class="qms-title">${GF.esc(n.message || '')}</span>
        ${n.acknowledged ? chip(AL('acknowledged', 'потврдено'), 'var(--green)')
          : (canWrite() ? `<button class="btn btn-sm" onclick="GF.WWF.qcOosAck('${o.id}','${n.id}')">${AL('Ack', 'Потврди')}</button>` : chip(AL('pending', 'на чекање'), 'var(--orange)'))}
      </div>`).join('');
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('OOS', 'OOS')}</span><b class="mono">${GF.esc(o.oos_number)}</b>
        <span>${AL('Batch', 'Серија')}</span><b>${GF.esc(o.batch_id)}</b>
        <span>${AL('Type', 'Тип')}</span><b>${GF.esc(o.oos_type)}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(o.status)}</b>
        ${o.test_name ? `<span>${AL('Test', 'Тест')}</span><b>${GF.esc(o.test_name)}</b>` : ''}
        ${o.risk_level ? `<span>${AL('Risk', 'Ризик')}</span><b>${chip(o.risk_level, RISK[o.risk_level] || 'var(--ink-3)')}</b>` : ''}
        ${o.disposition ? `<span>${AL('Disposition', 'Диспозиција')}</span><b>${chip(o.disposition, DISP[o.disposition] || 'var(--ink-3)')}</b>` : ''}
      </div>
      ${canWrite() ? `<div class="qms-dl" style="margin-top:8px">
        ${nxt && (!QP_TARGETS[nxt] || canQP()) ? `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcOosAdvance('${o.id}','${nxt}')">${AL('Advance to', 'Напредувај до')} ${GF.esc(AL((ST[nxt]||{}).en||nxt, (ST[nxt]||{}).mk||nxt))}</button>` : ''}
        ${canClose && canQP() && nxt !== 'CLOSED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcOosAdvance('${o.id}','CLOSED')">${AL('Close (QP)', 'Затвори (КЛ)')}</button>` : ''}
      </div>` : ''}
      ${canWrite() && o.status !== 'CLOSED' ? `
      <div class="ana-panel" style="margin-top:10px;padding:10px">
        <div class="ana-pt" style="margin-bottom:6px">${AL('Investigation', 'Истрага')}</div>
        <div style="display:grid;gap:6px">
          ${area('qoo-lab_investigation_result', AL('Phase I — lab investigation result', 'Фаза I — резултат од лаб. истрага'), o.lab_investigation_result)}
          ${fld('qoo-root_cause_category', AL('Root-cause category', 'Категорија на корен-причина'), o.root_cause_category)}
          ${area('qoo-root_cause_description', AL('Root-cause description', 'Опис на корен-причина'), o.root_cause_description)}
          ${area('qoo-impact_assessment', AL('Impact assessment', 'Проценка на влијание'), o.impact_assessment)}
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            ${fld('qoo-capa_reference', AL('CAPA ref', 'CAPA реф.'), o.capa_reference)}
            <input id="qoo-effectiveness_check_date" type="date" value="${GF.esc(o.effectiveness_check_date || '')}">
            ${fld('qoo-effectiveness_check_result', AL('Effectiveness result', 'Резултат од ефективност'), o.effectiveness_check_result)}
          </div>
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcOosSavePhase('${o.id}')">${AL('Save investigation', 'Зачувај истрага')}</button>
        </div>
        ${canQP() ? `<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;align-items:center">
          <select id="qoo-disp"><option value="">${AL('Disposition…', 'Диспозиција…')}</option>${Object.keys(DISP).map(x => `<option value="${x}">${x}</option>`).join('')}</select>
          <input id="qoo-disp-reason" placeholder="${AL('reason', 'причина')}" style="flex:1">
          <button class="btn btn-sm" onclick="GF.WWF.qcOosDisposition('${o.id}')">${AL('Set disposition (QP)', 'Постави диспозиција (КЛ)')}</button>
        </div>` : ''}
      </div>` : ''}
      <div style="margin-top:12px" class="ana-pt">${AL('Register (append-only)', 'Регистар (само додавање)')}</div>
      <table class="qcp-table"><thead><tr><th>${AL('When', 'Кога')}</th><th>${AL('Action', 'Акција')}</th><th>${AL('Details', 'Детали')}</th></tr></thead>
        <tbody>${reg || `<tr><td colspan="3" class="ana-note">${AL('No events', 'Нема настани')}</td></tr>`}</tbody></table>
      ${canWrite() && o.status !== 'CLOSED' ? `<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">
        <input id="qoo-ev-action" placeholder="${AL('action', 'акција')}" style="width:150px">
        <input id="qoo-ev-details" placeholder="${AL('details', 'детали')}" style="flex:1">
        <button class="btn btn-sm" onclick="GF.WWF.qcOosAddEvent('${o.id}')">+ ${AL('Event', 'Настан')}</button>
      </div>` : ''}
      <div style="margin-top:12px" class="ana-pt">${AL('Notifications', 'Известувања')}</div>
      ${notifs || `<div class="ana-note">${AL('No notifications', 'Нема известувања')}</div>`}
      ${canWrite() && o.status !== 'CLOSED' ? `<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;align-items:center">
        <select id="qoo-nt-part">${['A', 'B', 'C', 'D'].map(p => `<option value="${p}">${AL('Part', 'Дел')} ${p}</option>`).join('')}</select>
        <input id="qoo-nt-msg" placeholder="${AL('message', 'порака')}" style="flex:1">
        <button class="btn btn-sm" onclick="GF.WWF.qcOosNotify('${o.id}')">+ ${AL('Notify', 'Извести')}</button>
      </div>` : ''}
    </div>`;
  };

  const oosList = () => {
    const st = GF.WWF._qcoos;
    const q = st.q.trim().toLowerCase();
    const rows = (st.rows || []).filter(o => !q
      || (o.oos_number || '').toLowerCase().includes(q)
      || (o.batch_id || '').toLowerCase().includes(q)
      || (o.test_name || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(o => `
      <div class="qms-row ${st.sel === o.id ? 'on' : ''}" onclick="GF.WWF.qcOosPick('${o.id}')">
        <span class="mono qms-code">${GF.esc(o.oos_number)}</span>
        <span class="qms-title">${GF.esc(o.batch_id)} <span class="ana-note">${GF.esc(o.oos_type)}${o.test_name ? ' · ' + GF.esc(o.test_name) : ''}</span></span>
        ${o.risk_level ? chip(o.risk_level, RISK[o.risk_level] || 'var(--ink-3)') : ''}${stChip(o.status)}
      </div>
      ${st.sel === o.id ? (st.detail ? detail(st.detail) : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`) : ''}`).join('');
  };

  const capaList = () => {
    const st = GF.WWF._qcoos;
    const rows = (st.capa || []);
    if (!rows.length) return `<div class="ana-note">${AL('No CAPA entries', 'Нема CAPA записи')}</div>`;
    return `<table class="qcp-table"><thead><tr>
      <th>${AL('CAPA', 'CAPA')}</th><th>${AL('OOS', 'OOS')}</th><th>${AL('Title', 'Наслов')}</th>
      <th>${AL('Due', 'Рок')}</th><th>${AL('Status', 'Статус')}</th></tr></thead><tbody>${
      rows.map(c => `<tr>
        <td class="mono">${GF.esc(c.id)}</td>
        <td class="mono"><a href="#" onclick="GF.WWF.qcOosTab('oos');GF.WWF.qcOosPick('${c.oos_id}');return false">${GF.esc(c.oos_number)}</a></td>
        <td>${GF.esc((c.title || '').slice(0, 60))}</td>
        <td class="mono">${GF.esc(c.due || '—')}</td>
        <td>${chip(c.status, CAPA_C[c.status] || 'var(--ink-3)')}</td></tr>`).join('')
      }</tbody></table>`;
  };

  GF.views.qcoos = () => {
    const st = GF.WWF._qcoos;
    if (!st.rows && !st.loading && !st.error) GF.WWF.loadQcOos();
    const head = GF.viewHead('qc_oos', 'qc_oos_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — out-of-specification investigations. Closing an OOS and setting a batch disposition are Qualified-Person decisions; the register is append-only. CAPA is derived from OOS state.',
      'QMS Студио — истраги надвор од спецификација. Затворањето на OOS и поставувањето диспозиција се одлуки на Квалификуваното лице; регистарот е само за додавање. CAPA се изведува од состојбата на OOS.')}</div>`;
    if (st.loading || (!st.rows && !st.error)) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcOos()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const tabs = `<div class="qms-dl" style="margin-bottom:10px">
      <button class="btn btn-sm ${st.tab === 'oos' ? 'btn-primary' : ''}" onclick="GF.WWF.qcOosTab('oos')">${AL('OOS investigations', 'OOS истраги')}</button>
      <button class="btn btn-sm ${st.tab === 'capa' ? 'btn-primary' : ''}" onclick="GF.WWF.qcOosTab('capa')">${AL('CAPA register', 'CAPA регистар')} (${(st.capa || []).length})</button>
    </div>`;
    if (st.tab === 'capa') {
      return head + zone + tabs + `<div class="panel ana-panel">${capaList()}</div>`;
    }
    const create = canWrite() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${AL('Open an OOS', 'Отвори OOS')}</div>
        <div class="qcs-form">
          <input id="qoo-batch" placeholder="${AL('Batch id', 'Серија')}">
          <select id="qoo-type">${TYPES.map(t => `<option value="${t}">${t}</option>`).join('')}</select>
          <input id="qoo-test_name" placeholder="${AL('Test name', 'Име на тест')}">
          <input id="qoo-material_code" placeholder="${AL('Material (optional)', 'Материјал (опц.)')}">
          <select id="qoo-risk"><option value="">${AL('Risk…', 'Ризик…')}</option>${Object.keys(RISK).map(r => `<option value="${r}">${r}</option>`).join('')}</select>
          <input id="qoo-detection" type="date" title="${AL('Detection date', 'Датум на откривање')}">
          <input id="qoo-deadline" type="date" title="${AL('Timeline deadline', 'Краен рок')}">
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcOosCreate()">${GF.t('create_task') || 'Create'}</button>
        </div>
      </div>` : '';
    return head + zone + tabs + create + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Investigations', 'Истраги')}</div>
          <input id="qoo-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcOosFilter(this.value)">
          <select id="qoo-status" onchange="GF.WWF.qcOosStatus(this.value)">
            <option value="">${AL('All statuses', 'Сите статуси')}</option>
            ${Object.keys(ST).map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
        </div>
        <div class="qms-list">${oosList()}</div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qcoos', icon: 'alert-triangle',
    label: () => AL('QC OOS & CAPA', 'КК OOS и CAPA'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
