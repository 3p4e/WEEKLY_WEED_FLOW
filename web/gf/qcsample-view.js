/* qcsample-view.js — QC LIMS: Samples registry + lifecycle (Phase 2, unit 2).

   Physical samples reached through /qc/samples. A sample has a PP-SMP id, a
   batch, a material, and a lifecycle (COLLECTED → IN_TRANSIT → RECEIVED →
   IN_TEST → TESTED → REVIEWED → APPROVED → RELEASED, + terminal REJECTED and
   the OOS branch QUARANTINE). Release/reject are a Qualified-Person decision
   (Annex 16 — QP or ADMIN ONLY, backend-enforced; executives are business
   leadership, not a GMP quality role). Self-referential genealogy
   (sub-samples / retests) shows in the detail.

   Read = elevated; write/advance = QC_MGR / QP / execs / ADMIN. Same
   full-page-view + qms-zone pattern as qcspec; QMS Studio zone, anchored
   insertBefore 'qms-end'. */

(function () {
  GF.WWF._qcsm = { samples: null, sel: null, detail: null, q: '', status: '', tab: 'samples',
                   loading: false, error: null, parent: null,
                   plans: null, plansLoading: false, plansError: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const _QP = ['ADMIN', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);
  const canQP = () => _QP.includes((GF.API.user || {}).role);

  const ST = {
    COLLECTED: { en: 'Collected', mk: 'Земено', c: 'var(--ink-3)' },
    IN_TRANSIT: { en: 'In transit', mk: 'Во транспорт', c: 'var(--orange)' },
    RECEIVED: { en: 'Received', mk: 'Примено', c: 'var(--blue)' },
    IN_TEST: { en: 'In test', mk: 'На тестирање', c: 'var(--blue)' },
    TESTED: { en: 'Tested', mk: 'Тестирано', c: 'var(--violet)' },
    REVIEWED: { en: 'Reviewed', mk: 'Прегледано', c: 'var(--violet)' },
    APPROVED: { en: 'Approved', mk: 'Одобрено', c: 'var(--teal,var(--blue))' },
    RELEASED: { en: 'Released', mk: 'Ослободено', c: 'var(--green)' },
    REJECTED: { en: 'Rejected', mk: 'Одбиено', c: 'var(--red)' },
    QUARANTINE: { en: 'Quarantine', mk: 'Карантин', c: 'var(--amber)' },
  };
  // EXACT mirror of backend qc.py _SAMPLE_TRANSITIONS — the single source of
  // legal moves; the UI never offers a target the server would 409. Note
  // IN_TEST cannot go straight to REJECTED (it exits via TESTED/QUARANTINE),
  // and COLLECTED may be quarantined directly. REJECTED renders as the
  // distinct Reject affordance, not an advance button.
  const LEGAL = {
    COLLECTED: ['IN_TRANSIT', 'RECEIVED', 'QUARANTINE', 'REJECTED'],
    IN_TRANSIT: ['RECEIVED', 'REJECTED'],
    RECEIVED: ['IN_TEST', 'REJECTED'],
    IN_TEST: ['TESTED', 'QUARANTINE'],
    TESTED: ['REVIEWED', 'QUARANTINE', 'REJECTED'],
    REVIEWED: ['APPROVED', 'REJECTED'],
    APPROVED: ['RELEASED', 'REJECTED'],
    QUARANTINE: ['IN_TEST', 'REJECTED'],
    RELEASED: [], REJECTED: [],
  };
  // release / reject are Qualified-Person decisions (qc.py _QP_TRANSITION_TARGETS)
  const QP_TARGETS = { RELEASED: 1, REJECTED: 1 };
  const stChip = (s) => {
    const m = ST[s] || { en: s, mk: s, c: 'var(--ink-3)' };
    return `<span class="chip-opt" style="border-color:${m.c};color:${m.c}">${GF.esc(AL(m.en, m.mk))}</span>`;
  };

  // sampling-plan frequency vocabulary (mirrors backend's _FREQUENCIES)
  const FREQ = {
    EVERY_BATCH: { en: 'Every batch', mk: 'Секоја серија', c: 'var(--blue)' },
    PERIODIC: { en: 'Periodic', mk: 'Периодично', c: 'var(--violet)' },
    RANDOM: { en: 'Random', mk: 'Случајно', c: 'var(--orange)' },
  };
  const chip = (txt, c) => `<span class="chip-opt" style="border-color:${c};color:${c}">${GF.esc(txt)}</span>`;
  const freqChip = (f) => { const m = FREQ[f] || { en: f || '—', mk: f || '—', c: 'var(--ink-3)' }; return chip(AL(m.en, m.mk), m.c); };
  // resolve a sample's linked sampling_plan_id (uuid) to its human PP-SPL code
  const planLabel = (id) => { const p = (GF.WWF._qcsm.plans || []).find(p => p.id === id); return p ? p.plan_id : id; };

  GF.WWF.loadQcSamples = async () => {
    const st = GF.WWF._qcsm;
    st.loading = true; st.error = null;
    try {
      const q = {}; if (st.status) q.status = st.status;
      st.samples = await GF.API.qcSamples(q);
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'qcsample') GF.render.all();
  };

  GF.WWF.loadQcPlans = async () => {
    const st = GF.WWF._qcsm;
    st.plansLoading = true; st.plansError = null;
    try { st.plans = await GF.API.qcSamplingPlans({}); }
    catch (e) { st.plansError = e.message; }
    st.plansLoading = false;
    if (GF.state.view === 'qcsample') GF.render.all();
  };

  GF.WWF.qcSamplePick = async (id) => {
    const st = GF.WWF._qcsm;
    if (st.sel === id) { st.sel = null; st.detail = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; GF.render.all();
    try { st.detail = await GF.API.qcSample(id); } catch (e) { GF.toast(e.message, 'error'); }
    if (GF.state.view === 'qcsample') GF.render.all();
  };
  GF.WWF.qcSampleFilter = (v) => { GF.WWF._qcsm.q = v; GF.render.all(); };
  GF.WWF.qcSampleStatus = (v) => { GF.WWF._qcsm.status = v; GF.WWF.loadQcSamples(); };
  GF.WWF.qcSampleTab = (t) => { GF.WWF._qcsm.tab = t; GF.render.all(); };

  GF.WWF.qcSampleMove = async (id, target) => {
    try { await GF.API.qcPatchSample(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcSamples();
    if (GF.WWF._qcsm.sel === id) { GF.WWF._qcsm.detail = await GF.API.qcSample(id).catch(() => null); GF.render.all(); }
  };

  GF.WWF.qcSampleCreate = async () => {
    const st = GF.WWF._qcsm;
    const mk = (i) => (document.getElementById(i) || {}).value || '';
    const batch_id = mk('qsm-batch').trim(), material_code = mk('qsm-mat').trim();
    if (!batch_id || !material_code) return GF.toast(AL('Batch and material are required', 'Потребни се серија и материјал'), 'error');
    const body = { batch_id, material_code, sample_type: mk('qsm-type').trim() || null,
                   location: mk('qsm-loc').trim() || null,
                   retention_sample: !!(document.getElementById('qsm-ret') || {}).checked };
    const plan = mk('qsm-plan'); if (plan) body.sampling_plan_id = plan;
    const qty = mk('qsm-qty').trim(); if (qty !== '' && !isNaN(parseFloat(qty))) body.quantity = parseFloat(qty);
    const unit = mk('qsm-unit').trim(); if (unit) body.quantity_unit = unit;
    const notes = mk('qsm-notes').trim(); if (notes) body.notes = notes;
    if (st.parent) body.parent_id = st.parent.id;  // aliquot / sub-sample link
    try {
      const s = await GF.API.qcCreateSample(body);
      GF.toast(s.sample_id + ' ' + AL('created', 'креирано'));
      st.parent = null;
      await GF.WWF.loadQcSamples(); GF.WWF.qcSamplePick(s.id);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  // "Add sub-sample" on a sample's detail — pre-links the create form to that
  // parent (the form shows the parent code and sends parent_id on create).
  GF.WWF.qcSampleSubOf = (id) => {
    const st = GF.WWF._qcsm;
    const s = (st.detail && st.detail.sample && st.detail.sample.id === id)
      ? st.detail.sample : (st.samples || []).find(x => x.id === id);
    if (!s) return;
    st.parent = { id: s.id, sample_id: s.sample_id, batch_id: s.batch_id, material_code: s.material_code };
    st.tab = 'samples';
    GF.render.all();
  };
  GF.WWF.qcSampleClearParent = () => { GF.WWF._qcsm.parent = null; GF.render.all(); };

  GF.WWF.qcPlanCreate = async () => {
    const mk = (i) => (document.getElementById(i) || {}).value || '';
    const material_code = mk('qsp-mat').trim();
    if (!material_code) return GF.toast(AL('Material code is required', 'Потребен е код на материјал'), 'error');
    const body = { material_code, sampling_frequency: mk('qsp-freq') || 'EVERY_BATCH' };
    const formula = mk('qsp-formula').trim(); if (formula) body.sample_size_formula = formula;
    const min = mk('qsp-min').trim(); if (min !== '') body.min_sample_size = parseInt(min, 10);
    const max = mk('qsp-max').trim(); if (max !== '') body.max_sample_size = parseInt(max, 10);
    try {
      const p = await GF.API.qcCreateSamplingPlan(body);
      GF.toast(p.plan_id + ' ' + AL('created', 'креирано'));
      await GF.WWF.loadQcPlans();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  const detail = (d) => {
    const s = d.sample;
    // only backend-legal targets (LEGAL mirrors qc.py); QP-only targets are
    // hidden from non-QP writers — the backend would 403/409 anything else.
    const legal = LEGAL[s.status] || [];
    const moves = legal.filter(t => t !== 'REJECTED' && (!QP_TARGETS[t] || canQP()));
    const canReject = legal.includes('REJECTED') && canQP();
    const parent = s.parent_id ? (GF.WWF._qcsm.samples || []).find(x => x.id === s.parent_id) : null;
    const kids = (d.children || []).map(k => `<div class="qms-row"><span class="mono qms-code">${GF.esc(k.sample_id)}</span><span class="qms-title">${GF.esc(k.batch_id)}</span>${stChip(k.status)}</div>`).join('');
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Sample', 'Примерок')}</span><b class="mono">${GF.esc(s.sample_id)}</b>
        <span>${AL('Batch', 'Серија')}</span><b>${GF.esc(s.batch_id)}</b>
        <span>${AL('Material', 'Материјал')}</span><b>${GF.esc(s.material_code)}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(s.status)}</b>
        <span>${AL('Location', 'Локација')}</span><b>${GF.esc(s.location || '—')}</b>
        ${s.parent_id ? `<span>${AL('Sub-sample of', 'Под-примерок од')}</span><b class="mono">${GF.esc(parent ? parent.sample_id : s.parent_id)}</b>` : ''}
        ${s.quantity != null ? `<span>${AL('Quantity', 'Количина')}</span><b>${GF.esc(String(s.quantity))} ${GF.esc(s.quantity_unit || '')}</b>` : ''}
        ${s.sampling_plan_id ? `<span>${AL('Sampling plan', 'План за земање мостри')}</span><b class="mono">${GF.esc(planLabel(s.sampling_plan_id))}</b>` : ''}
        ${s.retention_sample ? `<span>${AL('Retention', 'Резерва')}</span><b>✓</b>` : ''}
        ${s.notes ? `<span>${AL('Notes', 'Белешки')}</span><b>${GF.esc(s.notes)}</b>` : ''}
      </div>
      ${canWrite() ? `<div class="qms-dl">
        ${moves.map(t => `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSampleMove('${s.id}','${t}')">${GF.esc(AL((ST[t]||{}).en || t, (ST[t]||{}).mk || t))}</button>`).join('')}
        ${canReject ? `<button class="btn btn-sm" onclick="GF.WWF.qcSampleMove('${s.id}','REJECTED')">${AL('Reject', 'Одбиј')}</button>` : ''}
        <button class="btn btn-sm" onclick="GF.WWF.qcSampleSubOf('${s.id}')">${AL('Add sub-sample', 'Додади под-примерок')}</button>
      </div>` : ''}
      ${kids ? `<div style="margin-top:10px" class="ana-pt">${AL('Sub-samples', 'Под-примероци')}</div>${kids}` : ''}
    </div>`;
  };

  const sampleList = () => {
    const st = GF.WWF._qcsm;
    const q = st.q.trim().toLowerCase();
    const rows = (st.samples || []).filter(s => !q
      || (s.sample_id || '').toLowerCase().includes(q)
      || (s.batch_id || '').toLowerCase().includes(q)
      || (s.material_code || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(s => `
      <div class="qms-row ${st.sel === s.id ? 'on' : ''}" onclick="GF.WWF.qcSamplePick('${s.id}')">
        <span class="mono qms-code">${GF.esc(s.sample_id)}</span>
        <span class="qms-title">${GF.esc(s.batch_id)} <span class="ana-note">${GF.esc(s.material_code)}</span></span>
        ${stChip(s.status)}
      </div>
      ${st.sel === s.id ? (st.detail ? detail(st.detail) : `<div class="qms-detail"><div class="mw-skel" style="height:50px"></div></div>`) : ''}`).join('');
  };

  const planList = () => {
    const st = GF.WWF._qcsm;
    if (st.plansLoading && !st.plans) return `<div class="mw-skel" style="height:80px"></div>`;
    if (st.plansError) return `<div class="ana-note" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <span style="color:var(--red-fg,var(--red))">${GF.esc(st.plansError)}</span>
      <button class="btn btn-sm" onclick="GF.WWF.loadQcPlans()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    const rows = st.plans || [];
    if (!rows.length) return `<div class="ana-note">${AL('No sampling plans yet', 'Сè уште нема планови за земање мостри')}</div>`;
    return `<table class="qcp-table"><thead><tr>
      <th>${AL('Plan', 'План')}</th><th>${AL('Material', 'Материјал')}</th>
      <th>${AL('Frequency', 'Фреквенција')}</th><th>${AL('Formula', 'Формула')}</th>
      <th>${AL('Size', 'Големина')}</th></tr></thead>
      <tbody>${rows.map(p => `<tr>
        <td class="mono">${GF.esc(p.plan_id)}</td>
        <td>${GF.esc(p.material_code)}</td>
        <td>${freqChip(p.sampling_frequency)}</td>
        <td>${GF.esc(p.sample_size_formula || '—')}</td>
        <td class="mono">${p.min_sample_size != null ? GF.esc(String(p.min_sample_size)) : '—'} … ${p.max_sample_size != null ? GF.esc(String(p.max_sample_size)) : '—'}</td>
      </tr>`).join('')}</tbody></table>`;
  };

  GF.views.qcsample = () => {
    const st = GF.WWF._qcsm;
    if (!st.samples && !st.loading && !st.error) GF.WWF.loadQcSamples();
    if (!st.plans && !st.plansLoading && !st.plansError) GF.WWF.loadQcPlans();
    const head = GF.viewHead('qc_samples', 'qc_samples_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — physical QC samples and their sampling plans. Release / reject is a Qualified-Person decision.',
      'QMS Студио — физички КК примероци и нивните планови за земање мостри. Ослободување / одбивање е одлука на Квалификуваното лице.')}</div>`;
    if (st.loading || (!st.samples && !st.error)) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcSamples()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const tabs = `<div class="qms-dl" style="margin-bottom:10px">
      <button class="btn btn-sm ${st.tab === 'samples' ? 'btn-primary' : ''}" onclick="GF.WWF.qcSampleTab('samples')">${AL('Samples', 'Примероци')}</button>
      <button class="btn btn-sm ${st.tab === 'plans' ? 'btn-primary' : ''}" onclick="GF.WWF.qcSampleTab('plans')">${AL('Sampling plans', 'Планови за земање мостри')} (${(st.plans || []).length})</button>
    </div>`;
    if (st.tab === 'plans') {
      const createPlan = canWrite() ? `
        <div class="panel ana-panel" style="margin-bottom:12px">
          <div class="ana-pt" style="margin-bottom:8px">${AL('New sampling plan', 'Нов план за земање мостри')}</div>
          <div class="qcs-form">
            <input id="qsp-mat" placeholder="${AL('Material code', 'Код на материјал')}">
            ${GF.selectField('qsp-freq', { value: 'EVERY_BATCH', title: AL('Frequency', 'Фреквенција'),
              options: Object.keys(FREQ).map(f => ({ v: f, label: AL(FREQ[f].en, FREQ[f].mk) })) })}
            <input id="qsp-formula" placeholder="${AL('Sample size formula (optional)', 'Формула за големина (опц.)')}">
            <input id="qsp-min" type="number" min="0" max="100000" placeholder="${AL('Min size', 'Мин.')}" style="width:80px">
            <input id="qsp-max" type="number" min="0" max="100000" placeholder="${AL('Max size', 'Макс.')}" style="width:80px">
            <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcPlanCreate()">${GF.t('create_task') || 'Create'}</button>
          </div>
        </div>` : '';
      return head + zone + tabs + createPlan + `
        <div class="panel ana-panel">
          <div class="ana-pt" style="margin-bottom:8px">${AL('Active sampling plans', 'Активни планови за земање мостри')}</div>
          ${planList()}
        </div>`;
    }
    const planOptions = [{ v: '', label: AL('No plan', 'Без план') }]
      .concat((st.plans || []).map(p => ({ v: p.id, label: p.plan_id, sub: p.material_code })));
    const create = canWrite() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${st.parent ? AL('Collect sub-sample', 'Земи под-примерок') : AL('Collect sample', 'Земи примерок')}</div>
        ${st.parent ? `<div class="ana-note" style="margin-bottom:8px">${AL('Aliquot / sub-sample of', 'Аликвот / под-примерок од')}
          <b class="mono">${GF.esc(st.parent.sample_id)}</b>
          <button class="btn btn-sm" onclick="GF.WWF.qcSampleClearParent()">✕</button></div>` : ''}
        <div class="qcs-form">
          <input id="qsm-batch" placeholder="${AL('Batch id', 'Серија')}" value="${GF.esc(st.parent ? st.parent.batch_id || '' : '')}">
          <input id="qsm-mat" placeholder="${AL('Material code', 'Код на материјал')}" value="${GF.esc(st.parent ? st.parent.material_code || '' : '')}">
          <input id="qsm-type" placeholder="${AL('Type', 'Тип')}">
          <input id="qsm-loc" placeholder="${AL('Location', 'Локација')}">
          <input id="qsm-qty" type="number" min="0" step="any" placeholder="${AL('Qty', 'Кол.')}" style="width:72px">
          <input id="qsm-unit" placeholder="${AL('unit', 'ед')}" style="width:56px">
          ${GF.selectField('qsm-plan', { value: '', title: AL('Sampling plan', 'План за земање мостри'),
            searchable: true, placeholder: AL('No plan', 'Без план'), options: planOptions })}
          <input id="qsm-notes" placeholder="${AL('Notes (optional)', 'Белешки (опц.)')}">
          <label style="display:flex;align-items:center;gap:6px"><input id="qsm-ret" type="checkbox">${AL('Retention sample', 'Резервен примерок')}</label>
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSampleCreate()">${GF.t('create_task') || 'Create'}</button>
        </div>
      </div>` : '';
    return head + zone + tabs + create + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Samples', 'Примероци')}</div>
          <input class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcSampleFilter(this.value)">
          <select onchange="GF.WWF.qcSampleStatus(this.value)">
            <option value="">${AL('All statuses', 'Сите статуси')}</option>
            ${Object.keys(ST).map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
        </div>
        <div class="qms-list">${sampleList()}</div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qcsample', icon: 'box',
    label: () => AL('QC Samples', 'КК Примероци'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
