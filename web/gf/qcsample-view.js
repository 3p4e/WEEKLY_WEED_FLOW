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
  GF.WWF._qcsm = { samples: null, sel: null, detail: null, detailError: null,
                   q: '', status: '', tab: 'samples',
                   loading: false, error: null, parent: null,
                   // Controlled-draft store for the create form: inputs render
                   // from here so a mid-typing re-render never clobbers them.
                   draft: null,
                   plans: null, plansLoading: false, plansError: null };

  // GxP genealogy guard: st.parent set by "Add sub-sample" must not survive
  // leaving the view — a later unrelated "Collect sample" would silently
  // attach parent_id. Entering the view from any other view starts with no
  // parent link and a fresh draft.
  const _setView = GF.setView;
  GF.setView = (v) => {
    if (v === 'qcsample' && GF.state.view !== 'qcsample') {
      GF.WWF._qcsm.parent = null;
      GF.WWF._qcsm.draft = null;
    }
    return _setView(v);
  };

  // Shared QC/LIMS role gates (core.js GF.QC_WRITERS / GF.QC_QP) — see that
  // file's comment; was a local copy-pasted array here.
  const canWrite = () => GF.QC_WRITERS.includes((GF.API.user || {}).role);
  const canQP = () => GF.QC_QP.includes((GF.API.user || {}).role);

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

  // QCSOP 011 §6.2.1 sample-type taxonomy (mirrors backend's _SAMPLE_KINDS)
  const KIND = {
    PC:   { en: 'Primary control', mk: 'Примарна контрола' },
    MB:   { en: 'Microbiology', mk: 'Микробиологија' },
    EXT:  { en: 'External lab', mk: 'Надворешна лаб.' },
    RET:  { en: 'Retention', mk: 'Резерва' },
    STAB: { en: 'Stability', mk: 'Стабилност' },
    RT:   { en: 'Retest', mk: 'Ретест' },
    CC:   { en: 'Counter-check', mk: 'Контра-проверка' },
  };
  const kindLabel = (k) => { const m = KIND[k]; return m ? AL(m.en, m.mk) : k; };

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
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      const q = {}; if (st.status) q.status = st.status;
      const samples = await GF.API.qcSamples(q);
      if (my !== st.lseq) return;
      st.samples = samples;
    } catch (e) { if (my === st.lseq) st.error = e.message; }
    if (my !== st.lseq) return;
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
    if (st.sel === id) { st.sel = null; st.detail = null; st.detailError = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; st.detailError = null; GF.render.all();
    try { const d = await GF.API.qcSample(id); if (st.sel === id) st.detail = d; }
    catch (e) { if (st.sel === id) { st.detailError = e.message; GF.toast(e.message, 'error'); } }
    if (st.sel === id && GF.state.view === 'qcsample') GF.render.all();
  };
  // Retry after a failed detail fetch: clearing sel first lets pick() take the
  // select path again, so one click re-fetches the same row.
  GF.WWF.qcSampleRetry = (id) => {
    const st = GF.WWF._qcsm;
    st.sel = null; st.detail = null; st.detailError = null;
    GF.WWF.qcSamplePick(id);
  };
  GF.WWF.qcSampleFilter = (v) => { GF.WWF._qcsm.q = v; GF.render.all(); GF.refocus('qsm-search'); };
  GF.WWF.qcSampleStatus = async (v) => { GF.WWF._qcsm.status = v; await GF.WWF.loadQcSamples(); GF.refocus('qsm-status'); };
  // Tab switches always drop a pending sub-sample parent link (GxP: it must
  // never silently ride along into a later, unrelated collection).
  GF.WWF.qcSampleTab = (t) => { const st = GF.WWF._qcsm; st.tab = t; st.parent = null; GF.render.all(); };

  // Create-form controlled inputs: every keystroke lands in st.draft, so the
  // values survive any re-render (filter keystrokes, tab bounces).
  GF.WWF.qcSampleDraft = (k, v) => {
    const st = GF.WWF._qcsm;
    st.draft = st.draft || {};
    st.draft[k] = v;
  };
  // Loud parent-link integrity check: editing batch/material away from the
  // parent's prefill detaches the sub-sample link explicitly (never silently).
  GF.WWF.qcSampleParentCheck = (el) => {
    const st = GF.WWF._qcsm;
    if (!st.parent || !el || !el.id) return;
    const want = el.id === 'qsm-batch' ? (st.parent.batch_id || '') : (st.parent.material_code || '');
    if (el.value === want) return;
    st.parent = null;
    GF.toast(AL('Sub-sample link cleared — batch/material no longer match the parent sample',
                'Врската за под-примерок е тргната — серијата/материјалот веќе не се совпаѓаат со примерокот-родител'), 'info');
    GF.render.all();
    GF.refocus(el.id);
  };

  GF.WWF.qcSampleMove = async (id, target) => {
    try { await GF.API.qcPatchSample(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcSamples();
    if (GF.WWF._qcsm.sel === id) { GF.WWF._qcsm.detail = await GF.API.qcSample(id).catch(() => null); GF.render.all(); }
  };

  // §6.7 — flag / clear a non-conforming sample (a distinct signal from the
  // lifecycle status; carries a reason).
  GF.WWF.qcSampleFlagNC = async (id) => {
    const reason = prompt(AL('Non-conformance reason:', 'Причина за неусогласеност:'));
    if (reason === null) return;
    if (!reason.trim()) return GF.toast(AL('A reason is required', 'Потребна е причина'), 'error');
    try { await GF.API.qcPatchSample(id, { non_conforming: true, non_conforming_reason: reason.trim() }); GF.toast(AL('Flagged non-conforming', 'Означено како неусогласено')); }
    catch (e) { return GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcSamples();
    if (GF.WWF._qcsm.sel === id) { GF.WWF._qcsm.detail = await GF.API.qcSample(id).catch(() => null); GF.render.all(); }
  };
  GF.WWF.qcSampleClearNC = async (id) => {
    try { await GF.API.qcPatchSample(id, { non_conforming: false, non_conforming_reason: null }); GF.toast(AL('Cleared', 'Исчистено')); }
    catch (e) { return GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcSamples();
    if (GF.WWF._qcsm.sel === id) { GF.WWF._qcsm.detail = await GF.API.qcSample(id).catch(() => null); GF.render.all(); }
  };

  GF.WWF.qcSampleCreate = async () => {
    const st = GF.WWF._qcsm;
    const dr = st.draft || {};
    // Draft first (it survives re-renders); the live input is the fallback.
    const mk = (i, k) => (dr[k] != null ? String(dr[k]) : ((document.getElementById(i) || {}).value || ''));
    const batch_id = mk('qsm-batch', 'batch').trim(), material_code = mk('qsm-mat', 'mat').trim();
    if (!batch_id || !material_code) return GF.toast(AL('Batch and material are required', 'Потребни се серија и материјал'), 'error');
    const body = { batch_id, material_code, sample_type: mk('qsm-type', 'type').trim() || null,
                   location: mk('qsm-loc', 'loc').trim() || null,
                   retention_sample: dr.ret != null ? !!dr.ret : !!(document.getElementById('qsm-ret') || {}).checked };
    const plan = mk('qsm-plan', 'plan'); if (plan) body.sampling_plan_id = plan;
    const qty = mk('qsm-qty', 'qty').trim(); if (qty !== '' && !isNaN(parseFloat(qty))) body.quantity = parseFloat(qty);
    const unit = mk('qsm-unit', 'unit').trim(); if (unit) body.quantity_unit = unit;
    const kind = mk('qsm-kind', 'kind').trim(); if (kind) body.sample_kind = kind;
    const rex = mk('qsm-retexp', 'retexp').trim(); if (rex) body.retention_expiry = rex;
    const notes = mk('qsm-notes', 'notes').trim(); if (notes) body.notes = notes;
    if (st.parent) body.parent_id = st.parent.id;  // aliquot / sub-sample link
    try {
      const s = await GF.API.qcCreateSample(body);
      GF.toast(s.sample_id + ' ' + AL('created', 'креирано'));
      st.parent = null; st.draft = null;
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
    // Seed the controlled draft with ONLY the parent's prefill — a RESET, not a
    // merge. An abandoned "Collect sample" draft (type/loc/qty/unit/kind/notes/
    // retention…) must never carry over into this sub-sample form; it always
    // starts clean, with just the genealogy-consistent batch/material.
    st.draft = { batch: s.batch_id || '', mat: s.material_code || '' };
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
    // A transposed range (min > max) is nonsensical once this plan drives real
    // sample-size decisions — refuse it here, before it ever reaches the API.
    if (body.min_sample_size != null && body.max_sample_size != null && body.min_sample_size > body.max_sample_size) {
      return GF.toast(AL('Min sample size cannot exceed max sample size', 'Минималната големина не смее да биде поголема од максималната'), 'error');
    }
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
        <span>${AL('Status', 'Статус')}</span><b>${stChip(s.status)}${s.non_conforming ? ' ' + chip(AL('non-conforming', 'неусогласено'), 'var(--red)') : ''}</b>
        <span>${AL('Location', 'Локација')}</span><b>${GF.esc(s.location || '—')}</b>
        ${s.sample_kind ? `<span>${AL('Sample type', 'Тип на мостра')}</span><b>${GF.esc(s.sample_kind)} · ${GF.esc(kindLabel(s.sample_kind))}</b>` : ''}
        ${s.parent_id ? `<span>${AL('Sub-sample of', 'Под-примерок од')}</span><b class="mono">${GF.esc(parent ? parent.sample_id : s.parent_id)}</b>` : ''}
        ${s.quantity != null ? `<span>${AL('Quantity', 'Количина')}</span><b>${GF.esc(String(s.quantity))} ${GF.esc(s.quantity_unit || '')}</b>` : ''}
        ${s.sampling_plan_id ? `<span>${AL('Sampling plan', 'План за земање мостри')}</span><b class="mono">${GF.esc(planLabel(s.sampling_plan_id))}</b>` : ''}
        ${s.retention_sample ? `<span>${AL('Retention', 'Резерва')}</span><b>✓</b>` : ''}
        ${s.retention_expiry ? `<span>${AL('Retention expiry', 'Истек на резерва')}</span><b class="mono">${GF.esc(s.retention_expiry)}</b>` : ''}
        ${s.non_conforming && s.non_conforming_reason ? `<span>${AL('NC reason', 'Причина за НЦ')}</span><b>${GF.esc(s.non_conforming_reason)}</b>` : ''}
        ${s.notes ? `<span>${AL('Notes', 'Белешки')}</span><b>${GF.esc(s.notes)}</b>` : ''}
      </div>
      ${canWrite() ? `<div class="qms-dl">
        ${moves.map(t => `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSampleMove('${s.id}','${t}')">${GF.esc(AL((ST[t]||{}).en || t, (ST[t]||{}).mk || t))}</button>`).join('')}
        ${canReject ? `<button class="btn btn-sm" onclick="GF.WWF.qcSampleMove('${s.id}','REJECTED')">${AL('Reject', 'Одбиј')}</button>` : ''}
        <button class="btn btn-sm" onclick="GF.WWF.qcSampleSubOf('${s.id}')">${AL('Add sub-sample', 'Додади под-примерок')}</button>
        ${s.non_conforming ? `<button class="btn btn-sm" onclick="GF.WWF.qcSampleClearNC('${s.id}')">${AL('Clear NC', 'Тргни НЦ')}</button>`
          : `<button class="btn btn-sm" onclick="GF.WWF.qcSampleFlagNC('${s.id}')">${AL('Flag non-conforming', 'Означи неусогласено')}</button>`}
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
      ${st.sel === s.id ? (st.detail ? detail(st.detail) : (st.detailError
        ? `<div class="qms-detail" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
             <span style="color:var(--red-fg,var(--red))">${GF.esc(st.detailError)}</span>
             <button class="btn btn-sm" onclick="GF.WWF.qcSampleRetry('${s.id}')">${AL('Failed — retry', 'Неуспешно — обиди се повторно')}</button></div>`
        : `<div class="qms-detail"><div class="mw-skel" style="height:50px"></div></div>`)) : ''}`).join('');
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
    // Controlled values: draft first (survives re-renders), parent prefill as
    // the fallback for the two genealogy fields.
    const dr = st.draft || {};
    const dv = (k, fb) => GF.esc(dr[k] != null ? dr[k] : (fb || ''));
    const create = canWrite() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${st.parent ? AL('Collect sub-sample', 'Земи под-примерок') : AL('Collect sample', 'Земи примерок')}</div>
        ${st.parent ? `<div class="ana-note" style="margin-bottom:8px">${AL('Aliquot / sub-sample of', 'Аликвот / под-примерок од')}
          <b class="mono">${GF.esc(st.parent.sample_id)}</b>
          <button class="btn btn-sm" onclick="GF.WWF.qcSampleClearParent()">✕</button></div>` : ''}
        <div class="qcs-form">
          <input id="qsm-batch" placeholder="${AL('Batch id', 'Серија')}" value="${dv('batch', st.parent && st.parent.batch_id)}"
            oninput="GF.WWF.qcSampleDraft('batch', this.value);GF.WWF.qcSampleParentCheck(this)">
          <input id="qsm-mat" placeholder="${AL('Material code', 'Код на материјал')}" value="${dv('mat', st.parent && st.parent.material_code)}"
            oninput="GF.WWF.qcSampleDraft('mat', this.value);GF.WWF.qcSampleParentCheck(this)">
          <input id="qsm-type" placeholder="${AL('Type', 'Тип')}" value="${dv('type')}" oninput="GF.WWF.qcSampleDraft('type', this.value)">
          <input id="qsm-loc" placeholder="${AL('Location', 'Локација')}" value="${dv('loc')}" oninput="GF.WWF.qcSampleDraft('loc', this.value)">
          <input id="qsm-qty" type="number" min="0" step="any" placeholder="${AL('Qty', 'Кол.')}" style="width:72px" value="${dv('qty')}" oninput="GF.WWF.qcSampleDraft('qty', this.value)">
          <input id="qsm-unit" placeholder="${AL('unit', 'ед')}" style="width:56px" value="${dv('unit')}" oninput="GF.WWF.qcSampleDraft('unit', this.value)">
          <select id="qsm-kind" onchange="GF.WWF.qcSampleDraft('kind', this.value)"><option value="">${AL('sample type…', 'тип на мостра…')}</option>${Object.keys(KIND).map(k => `<option value="${k}" ${dr.kind === k ? 'selected' : ''}>${k} · ${GF.esc(kindLabel(k))}</option>`).join('')}</select>
          ${GF.dateField('qsm-retexp', { value: dv('retexp'),
            placeholder: AL('Retention expiry', 'Истек на резерва'),
            onPick: (v) => GF.WWF.qcSampleDraft('retexp', v) })}
          ${GF.selectField('qsm-plan', { value: '', title: AL('Sampling plan', 'План за земање мостри'),
            searchable: true, placeholder: AL('No plan', 'Без план'), options: planOptions })}
          <input id="qsm-notes" placeholder="${AL('Notes (optional)', 'Белешки (опц.)')}" value="${dv('notes')}" oninput="GF.WWF.qcSampleDraft('notes', this.value)">
          <label style="display:flex;align-items:center;gap:6px"><input id="qsm-ret" type="checkbox" ${dr.ret ? 'checked' : ''} onchange="GF.WWF.qcSampleDraft('ret', this.checked)">${AL('Retention sample', 'Резервен примерок')}</label>
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSampleCreate()">${GF.t('create_task') || 'Create'}</button>
        </div>
      </div>` : '';
    return head + zone + tabs + create + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Samples', 'Примероци')}</div>
          <input id="qsm-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcSampleFilter(this.value)">
          <select id="qsm-status" onchange="GF.WWF.qcSampleStatus(this.value)">
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
