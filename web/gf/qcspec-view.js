/* qcspec-view.js — QC LIMS: Specifications registry (Phase 2, unit 1).

   Controlled acceptance-criteria master data reached through the authed
   backend (/qc/specifications). A spec has a material code, a version, an
   8-stage lifecycle (INITIATED→…→ACTIVE→UNDER_CHANGE, + SUPERSEDED/WITHDRAWN),
   an optional THC grade + release window, and a set of test parameters (per-
   analyte acceptance limits). Read = any elevated role; write (create /
   advance / author parameters) = QC_MGR / QP / execs / ADMIN, gated by the
   backend and mirrored by canWrite() here.

   GMP: limits are never invented — a blank limit stays blank. Same full-page-
   view + qms-zone banner pattern as qmsregistry; belongs to the QMS Studio
   zone (docs/SCOPE.md), anchored insertBefore 'qms-end'. */

(function () {
  GF.WWF._qcs = { specs: null, sel: null, detail: null, detailError: null, q: '', status: '',
                  loading: false, error: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);

  // status → colour, mirroring qmsregistry's stChip vocabulary
  const ST = {
    INITIATED: { en: 'Initiated', mk: 'Иницирано', c: 'var(--ink-3)' },
    DRAFT: { en: 'Draft', mk: 'Нацрт', c: 'var(--orange)' },
    QC_REVIEW: { en: 'QC review', mk: 'КК преглед', c: 'var(--blue)' },
    QA_APPROVED: { en: 'QA approved', mk: 'ОК одобрено', c: 'var(--violet)' },
    NUMBERED: { en: 'Numbered', mk: 'Нумерирано', c: 'var(--violet)' },
    TRAINED: { en: 'Trained', mk: 'Обучено', c: 'var(--teal,var(--blue))' },
    ACTIVE: { en: 'Active', mk: 'Активно', c: 'var(--green)' },
    UNDER_CHANGE: { en: 'Under change', mk: 'Во измена', c: 'var(--amber)' },
    SUPERSEDED: { en: 'Superseded', mk: 'Заменето', c: 'var(--ink-3)' },
    WITHDRAWN: { en: 'Withdrawn', mk: 'Повлечено', c: 'var(--red)' },
  };
  // legal moves, mirroring backend qc.py _SPEC_TRANSITIONS — the UI never
  // offers a transition the server would 409. NEXT is the forward chain;
  // BACK is the one allowed kick-back (QC review findings return the spec to
  // authoring); WITHDRAWN is reachable from every non-terminal state EXCEPT
  // ACTIVE (an active spec is superseded by a new version, never withdrawn).
  const NEXT = { INITIATED: 'DRAFT', DRAFT: 'QC_REVIEW', QC_REVIEW: 'QA_APPROVED',
                 QA_APPROVED: 'NUMBERED', NUMBERED: 'TRAINED', TRAINED: 'ACTIVE',
                 ACTIVE: 'UNDER_CHANGE', UNDER_CHANGE: 'ACTIVE' };
  const BACK = { QC_REVIEW: 'DRAFT' };
  const stChip = (s) => {
    const m = ST[s] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' };
    return `<span class="chip-opt" style="border-color:${m.c};color:${m.c}">${GF.esc(AL(m.en, m.mk))}</span>`;
  };

  GF.WWF.loadQcSpecs = async () => {
    const st = GF.WWF._qcs;
    st.loading = true; st.error = null;
    try {
      const q = {};
      if (st.status) q.status = st.status;
      st.specs = await GF.API.qcSpecs(q);
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'qcspec') GF.render.all();
  };

  GF.WWF.qcSpecPick = async (id) => {
    const st = GF.WWF._qcs;
    if (st.sel === id) { st.sel = null; st.detail = null; st.detailError = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; st.detailError = null; GF.render.all();
    try { st.detail = await GF.API.qcSpec(id); }
    catch (e) { st.detailError = e.message; GF.toast(e.message, 'error'); }
    if (GF.state.view === 'qcspec') GF.render.all();
  };
  // Retry after a failed detail fetch: clearing sel first lets pick() take the
  // select path again, so one click re-fetches the same row.
  GF.WWF.qcSpecRetry = (id) => {
    const st = GF.WWF._qcs;
    st.sel = null; st.detail = null; st.detailError = null;
    GF.WWF.qcSpecPick(id);
  };
  GF.WWF.qcSpecFilter = (v) => { GF.WWF._qcs.q = v; GF.render.all(); GF.refocus('qcs-search'); };
  GF.WWF.qcSpecStatus = async (v) => { GF.WWF._qcs.status = v; await GF.WWF.loadQcSpecs(); GF.refocus('qcs-status'); };

  GF.WWF.qcSpecAdvance = async (id, target) => {
    try { await GF.API.qcPatchSpec(id, { status: target }); GF.toast(AL('Advanced', 'Напреднато')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcSpecs();
    if (GF.WWF._qcs.sel === id) { GF.WWF._qcs.detail = await GF.API.qcSpec(id).catch(() => null); GF.render.all(); }
  };

  GF.WWF.qcSpecCreate = async () => {
    const mk = (id) => (document.getElementById(id) || {}).value || '';
    const material_code = mk('qcs-mat').trim();
    const material_name_en = mk('qcs-en').trim();
    if (!material_code || !material_name_en) {
      return GF.toast(AL('Material code and English name are required', 'Потребни се код и англиско име'), 'error');
    }
    const body = { material_code, material_name_en,
                   material_name_mk: mk('qcs-mkn').trim() || null,
                   version: parseInt(mk('qcs-ver'), 10) || 1 };
    const g = mk('qcs-grade'); if (g) body.thc_grade = g;
    try {
      const spec = await GF.API.qcCreateSpec(body);
      GF.toast(spec.spec_id + ' ' + AL('created', 'креирано'));
      await GF.WWF.loadQcSpecs();
      GF.WWF.qcSpecPick(spec.id);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.qcSpecAddParam = async (id) => {
    const mk = (i) => (document.getElementById(i) || {}).value || '';
    const test_name_en = mk('qcp-en').trim();
    if (!test_name_en) return GF.toast(AL('Test name required', 'Потребно е име на тест'), 'error');
    const num = (i) => { const v = mk(i).trim(); return v === '' ? null : parseFloat(v); };
    const body = { test_name_en, test_name_mk: mk('qcp-mk').trim() || null,
                   test_method: mk('qcp-method').trim() || null, unit: mk('qcp-unit').trim() || null,
                   lower_limit: num('qcp-lo'), upper_limit: num('qcp-hi'),
                   pharmacopoeia_ref: mk('qcp-ref').trim() || null };
    // Ph. Eur. 3028 derived total: computed from two measured components
    // (a = neutral form, b = acid form) — the engine derives a + 0.877·b at
    // COQ time; a computed parameter is never transcribed.
    const ck = mk('qcp-computed');
    if (ck) {
      body.computed_kind = ck;
      body.component_a_id = mk('qcp-comp-a') || null;
      body.component_b_id = mk('qcp-comp-b') || null;
    }
    try {
      await GF.API.qcAddSpecParam(id, body);
      GF.WWF._qcs.detail = await GF.API.qcSpec(id);
      GF.render.all();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.qcSpecDelParam = async (id, pid) => {
    try { await GF.API.qcDeleteSpecParam(id, pid); GF.WWF._qcs.detail = await GF.API.qcSpec(id); GF.render.all(); }
    catch (e) { GF.toast(e.message, 'error'); }
  };

  const paramRows = (d) => {
    const editable = ['INITIATED', 'DRAFT', 'QC_REVIEW'].includes(d.spec.status);
    const computedNote = (p) => !p.computed_kind ? '' :
      `<div class="ana-note">Σ ${p.computed_kind === 'total_thc'
        ? AL('Total THC — computed (Ph. Eur. 3028)', 'Вкупен ТХЦ — пресметано (Ph. Eur. 3028)')
        : AL('Total CBD — computed (Ph. Eur. 3028)', 'Вкупен ЦБД — пресметано (Ph. Eur. 3028)')}</div>`;
    const rows = (d.parameters || []).map(p => `
      <tr>
        <td>${GF.esc(p.test_name_en)}${p.test_name_mk ? `<div class="ana-note">${GF.esc(p.test_name_mk)}</div>` : ''}${computedNote(p)}</td>
        <td>${GF.esc(p.test_method || '—')}</td>
        <td class="mono">${p.lower_limit != null ? GF.esc(String(p.lower_limit)) : '—'} … ${p.upper_limit != null ? GF.esc(String(p.upper_limit)) : '—'} ${GF.esc(p.unit || '')}</td>
        <td>${GF.esc(p.pharmacopoeia_ref || '—')}</td>
        ${editable && canWrite() ? `<td><button class="btn btn-sm" onclick="GF.WWF.qcSpecDelParam('${d.spec.id}','${p.id}')">✕</button></td>` : '<td></td>'}
      </tr>`).join('');
    // component pickers for a computed total — only measured params qualify
    const comps = (d.parameters || []).filter(p => !p.computed_kind);
    const compOpts = (lbl) => `<option value="">${lbl}</option>` +
      comps.map(p => `<option value="${p.id}">${GF.esc(p.test_name_en)}</option>`).join('');
    const addRow = (editable && canWrite()) ? `
      <tr class="qcp-add">
        <td><input id="qcp-en" placeholder="${AL('Test (EN)', 'Тест (АНГ)')}"><input id="qcp-mk" placeholder="${AL('Test (MK)', 'Тест (МК)')}">
          <select id="qcp-computed" style="margin-top:4px">
            <option value="">${AL('Measured', 'Мерено')}</option>
            <option value="total_thc">${AL('Computed: total THC', 'Пресметано: вкупен ТХЦ')}</option>
            <option value="total_cbd">${AL('Computed: total CBD', 'Пресметано: вкупен ЦБД')}</option>
          </select>
          ${comps.length ? `<select id="qcp-comp-a">${compOpts(AL('Component a (neutral)…', 'Компонента а (неутрална)…'))}</select>
          <select id="qcp-comp-b">${compOpts(AL('Component b (acid)…', 'Компонента б (киселинска)…'))}</select>` : ''}</td>
        <td><input id="qcp-method" placeholder="${AL('Method', 'Метод')}"></td>
        <td><input id="qcp-lo" placeholder="${AL('min', 'мин')}" style="width:60px"> <input id="qcp-hi" placeholder="${AL('max', 'макс')}" style="width:60px"> <input id="qcp-unit" placeholder="${AL('unit', 'ед')}" style="width:56px"></td>
        <td><input id="qcp-ref" placeholder="Ph.Eur."></td>
        <td><button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSpecAddParam('${d.spec.id}')">+</button></td>
      </tr>` : '';
    return `<table class="qcp-table"><thead><tr>
      <th>${AL('Parameter', 'Параметар')}</th><th>${AL('Method', 'Метод')}</th>
      <th>${AL('Limits', 'Граници')}</th><th>${AL('Ref', 'Реф')}</th><th></th></tr></thead>
      <tbody>${rows || `<tr><td colspan="5" class="ana-note">${AL('No parameters yet', 'Сè уште нема параметри')}</td></tr>`}${addRow}</tbody></table>`;
  };

  const detail = (d) => {
    const s = d.spec;
    const nxt = NEXT[s.status];
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Code', 'Код')}</span><b class="mono">${GF.esc(s.spec_id)}</b>
        <span>${AL('Material', 'Материјал')}</span><b>${GF.esc(s.material_code)} · v${GF.esc(String(s.version))}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(s.status)}</b>
        <span>${AL('THC grade', 'ТХЦ одделение')}</span><b>${GF.esc(s.thc_grade || '—')}</b>
      </div>
      ${nxt && canWrite() ? `<div class="qms-dl"><button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSpecAdvance('${s.id}','${nxt}')">${AL('Advance to', 'Напредувај до')} ${GF.esc(nxt)}</button>
        ${BACK[s.status] ? `<button class="btn btn-sm" onclick="GF.WWF.qcSpecAdvance('${s.id}','${BACK[s.status]}')">${AL('Return to draft', 'Врати во нацрт')}</button>` : ''}
        ${!['ACTIVE', 'WITHDRAWN', 'SUPERSEDED'].includes(s.status) ? `<button class="btn btn-sm" onclick="GF.WWF.qcSpecAdvance('${s.id}','WITHDRAWN')">${AL('Withdraw', 'Повлечи')}</button>` : ''}</div>` : ''}
      <div style="margin-top:12px" class="ana-pt">${AL('Test parameters', 'Тест параметри')}</div>
      ${paramRows(d)}
    </div>`;
  };

  const specList = () => {
    const st = GF.WWF._qcs;
    const q = st.q.trim().toLowerCase();
    const rows = (st.specs || []).filter(s => !q
      || (s.spec_id || '').toLowerCase().includes(q)
      || (s.material_code || '').toLowerCase().includes(q)
      || (s.material_name_en || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(s => `
      <div class="qms-row ${st.sel === s.id ? 'on' : ''}" onclick="GF.WWF.qcSpecPick('${s.id}')">
        <span class="mono qms-code">${GF.esc(s.spec_id)}</span>
        <span class="qms-title">${GF.esc(s.material_name_en)} <span class="ana-note">${GF.esc(s.material_code)} v${GF.esc(String(s.version))}</span></span>
        ${stChip(s.status)}
      </div>
      ${st.sel === s.id ? (st.detail ? detail(st.detail) : (st.detailError
        ? `<div class="qms-detail" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
             <span style="color:var(--red-fg,var(--red))">${GF.esc(st.detailError)}</span>
             <button class="btn btn-sm" onclick="GF.WWF.qcSpecRetry('${s.id}')">${AL('Failed — retry', 'Неуспешно — обиди се повторно')}</button></div>`
        : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`)) : ''}`).join('');
  };

  GF.views.qcspec = () => {
    const st = GF.WWF._qcs;
    if (!st.specs && !st.loading && !st.error) GF.WWF.loadQcSpecs();
    const head = GF.viewHead('qc_specs', 'qc_specs_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — controlled QC specifications. Results are judged against the ACTIVE version.',
      'QMS Студио — контролирани КК спецификации. Резултатите се оценуваат според АКТИВНАТА верзија.')}</div>`;
    if (st.loading || (!st.specs && !st.error)) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcSpecs()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const create = canWrite() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${AL('New specification', 'Нова спецификација')}</div>
        <div class="qcs-form">
          <input id="qcs-mat" placeholder="${AL('Material code', 'Код на материјал')}">
          <input id="qcs-en" placeholder="${AL('Name (EN)', 'Име (АНГ)')}">
          <input id="qcs-mkn" placeholder="${AL('Name (MK)', 'Име (МК)')}">
          <input id="qcs-ver" type="number" min="1" value="1" style="width:64px" title="${AL('Version', 'Верзија')}">
          <select id="qcs-grade"><option value="">${AL('THC grade…', 'ТХЦ одд…')}</option>
            <option>GRADE_I</option><option>GRADE_II</option><option>GRADE_III</option><option>GRADE_IV</option><option>GRADE_V</option></select>
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSpecCreate()">${GF.t('create_task') || 'Create'}</button>
        </div>
      </div>` : '';
    return head + zone + create + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Specifications', 'Спецификации')}</div>
          <input id="qcs-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcSpecFilter(this.value)">
          <select id="qcs-status" onchange="GF.WWF.qcSpecStatus(this.value)" value="${st.status}">
            <option value="">${AL('All statuses', 'Сите статуси')}</option>
            ${Object.keys(ST).map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
        </div>
        <div class="qms-list">${specList()}</div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qcspec', icon: 'flask',
    label: () => AL('QC Specifications', 'КК Спецификации'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
