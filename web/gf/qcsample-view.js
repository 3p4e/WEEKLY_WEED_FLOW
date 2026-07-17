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
  GF.WWF._qcsm = { samples: null, sel: null, detail: null, q: '', status: '',
                   loading: false, error: null };

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
  // legal forward moves the UI offers (mirror of the backend map's happy path)
  const NEXT = {
    COLLECTED: ['IN_TRANSIT', 'RECEIVED'], IN_TRANSIT: ['RECEIVED'], RECEIVED: ['IN_TEST'],
    IN_TEST: ['TESTED', 'QUARANTINE'], TESTED: ['REVIEWED', 'QUARANTINE'], REVIEWED: ['APPROVED'],
    APPROVED: ['RELEASED'], QUARANTINE: ['IN_TEST'],
  };
  const QP_TARGETS = { RELEASED: 1, REJECTED: 1 };
  const stChip = (s) => {
    const m = ST[s] || { en: s, mk: s, c: 'var(--ink-3)' };
    return `<span class="chip-opt" style="border-color:${m.c};color:${m.c}">${GF.esc(AL(m.en, m.mk))}</span>`;
  };

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

  GF.WWF.qcSamplePick = async (id) => {
    const st = GF.WWF._qcsm;
    if (st.sel === id) { st.sel = null; st.detail = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; GF.render.all();
    try { st.detail = await GF.API.qcSample(id); } catch (e) { GF.toast(e.message, 'error'); }
    if (GF.state.view === 'qcsample') GF.render.all();
  };
  GF.WWF.qcSampleFilter = (v) => { GF.WWF._qcsm.q = v; GF.render.all(); };
  GF.WWF.qcSampleStatus = (v) => { GF.WWF._qcsm.status = v; GF.WWF.loadQcSamples(); };

  GF.WWF.qcSampleMove = async (id, target) => {
    try { await GF.API.qcPatchSample(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcSamples();
    if (GF.WWF._qcsm.sel === id) { GF.WWF._qcsm.detail = await GF.API.qcSample(id).catch(() => null); GF.render.all(); }
  };

  GF.WWF.qcSampleCreate = async () => {
    const mk = (i) => (document.getElementById(i) || {}).value || '';
    const batch_id = mk('qsm-batch').trim(), material_code = mk('qsm-mat').trim();
    if (!batch_id || !material_code) return GF.toast(AL('Batch and material are required', 'Потребни се серија и материјал'), 'error');
    const body = { batch_id, material_code, sample_type: mk('qsm-type').trim() || null,
                   location: mk('qsm-loc').trim() || null };
    try {
      const s = await GF.API.qcCreateSample(body);
      GF.toast(s.sample_id + ' ' + AL('created', 'креирано'));
      await GF.WWF.loadQcSamples(); GF.WWF.qcSamplePick(s.id);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  const detail = (d) => {
    const s = d.sample;
    const moves = (NEXT[s.status] || []).filter(t => !QP_TARGETS[t] || canQP());
    const canReject = !['RELEASED', 'REJECTED'].includes(s.status) && canQP();
    const kids = (d.children || []).map(k => `<div class="qms-row"><span class="mono qms-code">${GF.esc(k.sample_id)}</span><span class="qms-title">${GF.esc(k.batch_id)}</span>${stChip(k.status)}</div>`).join('');
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Sample', 'Примерок')}</span><b class="mono">${GF.esc(s.sample_id)}</b>
        <span>${AL('Batch', 'Серија')}</span><b>${GF.esc(s.batch_id)}</b>
        <span>${AL('Material', 'Материјал')}</span><b>${GF.esc(s.material_code)}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(s.status)}</b>
        <span>${AL('Location', 'Локација')}</span><b>${GF.esc(s.location || '—')}</b>
        ${s.retention_sample ? `<span>${AL('Retention', 'Резерва')}</span><b>✓</b>` : ''}
      </div>
      ${canWrite() && (moves.length || canReject) ? `<div class="qms-dl">
        ${moves.map(t => `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSampleMove('${s.id}','${t}')">${GF.esc(AL((ST[t]||{}).en || t, (ST[t]||{}).mk || t))}</button>`).join('')}
        ${canReject ? `<button class="btn btn-sm" onclick="GF.WWF.qcSampleMove('${s.id}','REJECTED')">${AL('Reject', 'Одбиј')}</button>` : ''}
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

  GF.views.qcsample = () => {
    const st = GF.WWF._qcsm;
    if (!st.samples && !st.loading && !st.error) GF.WWF.loadQcSamples();
    const head = GF.viewHead('qc_samples', 'qc_samples_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — physical QC samples. Release / reject is a Qualified-Person decision.',
      'QMS Студио — физички КК примероци. Ослободување / одбивање е одлука на Квалификуваното лице.')}</div>`;
    if (st.loading || (!st.samples && !st.error)) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcSamples()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const create = canWrite() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${AL('Collect sample', 'Земи примерок')}</div>
        <div class="qcs-form">
          <input id="qsm-batch" placeholder="${AL('Batch id', 'Серија')}">
          <input id="qsm-mat" placeholder="${AL('Material code', 'Код на материјал')}">
          <input id="qsm-type" placeholder="${AL('Type', 'Тип')}">
          <input id="qsm-loc" placeholder="${AL('Location', 'Локација')}">
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSampleCreate()">${GF.t('create_task') || 'Create'}</button>
        </div>
      </div>` : '';
    return head + zone + create + `
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
