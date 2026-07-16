/* qccoa-view.js — QC LIMS: Certificates of analysis + test results (Phase 2, unit 3).

   A certificate of analysis reached through /qc/certificates. A CoA cites a
   specification, optionally links a physical sample, carries a batch id, and
   walks a DRAFT→REVIEWED→APPROVED→RELEASED lifecycle with a PASS/FAIL
   decision. Results are entered while DRAFT; each result's `complies` verdict
   is computed server-side from the numeric value vs the limits — never typed
   by hand (GxP: an unmeasured result stays "unknown"). A failing result on a
   CoA that links a still-testable sample quarantines that sample (the OOS
   hook, done in the backend).

   Review is second-person (the backend rejects a reviewer who is the analyst).
   Approve / release are Qualified-Person decisions (backend-gated; mirrored by
   canQP() here). Read = elevated; write = QC_MGR / QP / execs / ADMIN. Same
   full-page-view + qms-zone pattern; QMS Studio zone, anchored 'qms-end'. */

(function () {
  GF.WWF._qccoa = { coas: null, sel: null, detail: null, specParams: null,
                    specs: null, samples: null, q: '', status: '',
                    loading: false, error: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const _QP = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);
  const canQP = () => _QP.includes((GF.API.user || {}).role);

  const ST = {
    DRAFT: { en: 'Draft', mk: 'Нацрт', c: 'var(--orange)' },
    REVIEWED: { en: 'Reviewed', mk: 'Прегледано', c: 'var(--violet)' },
    APPROVED: { en: 'Approved', mk: 'Одобрено', c: 'var(--teal,var(--blue))' },
    RELEASED: { en: 'Released', mk: 'Ослободено', c: 'var(--green)' },
  };
  // legal forward move + which targets are Qualified-Person-only (mirror backend)
  const NEXT = { DRAFT: 'REVIEWED', REVIEWED: 'APPROVED', APPROVED: 'RELEASED' };
  const QP_TARGETS = { APPROVED: 1, RELEASED: 1 };
  const CERT_TYPES = ['ICOA', 'ECOA', 'COQ', 'WATER', 'OTHER'];

  const stChip = (s) => {
    const m = ST[s] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' };
    return `<span class="chip-opt" style="border-color:${m.c};color:${m.c}">${GF.esc(AL(m.en, m.mk))}</span>`;
  };
  // complies verdict → coloured mark
  const compliesChip = (v) => {
    if (v === true) return `<span class="chip-opt" style="border-color:var(--green);color:var(--green)">✓ ${AL('Pass', 'Задоволува')}</span>`;
    if (v === false) return `<span class="chip-opt" style="border-color:var(--red);color:var(--red)">✗ ${AL('Fail', 'Не задоволува')}</span>`;
    return `<span class="chip-opt" style="border-color:var(--ink-3);color:var(--ink-3)">— ${AL('Unknown', 'Непознато')}</span>`;
  };
  const decChip = (d) => {
    if (d === 'PASS') return `<span class="chip-opt" style="border-color:var(--green);color:var(--green)">PASS</span>`;
    if (d === 'FAIL') return `<span class="chip-opt" style="border-color:var(--red);color:var(--red)">FAIL</span>`;
    return `<span class="ana-note">${AL('undecided', 'неодлучено')}</span>`;
  };

  GF.WWF.loadQcCoas = async () => {
    const st = GF.WWF._qccoa;
    st.loading = true; st.error = null;
    try {
      const q = {}; if (st.status) q.status = st.status;
      st.coas = await GF.API.qcCoas(q);
      // create-form pickers (best-effort; a failure here shouldn't blank the page)
      if (st.specs === null) st.specs = await GF.API.qcSpecs({}).catch(() => []);
      if (st.samples === null) st.samples = await GF.API.qcSamples({}).catch(() => []);
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'qccoa') GF.render.all();
  };

  GF.WWF.qcCoaPick = async (id) => {
    const st = GF.WWF._qccoa;
    if (st.sel === id) { st.sel = null; st.detail = null; st.specParams = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; st.specParams = null; GF.render.all();
    try {
      st.detail = await GF.API.qcCoa(id);
      // pull the linked spec's parameters so results can cite them (server
      // snapshots the limits — the spec is the single source of truth)
      const sid = st.detail.coa.specification_id;
      if (sid) st.specParams = (await GF.API.qcSpec(sid).catch(() => null) || {}).parameters || [];
    } catch (e) { GF.toast(e.message, 'error'); }
    if (GF.state.view === 'qccoa') GF.render.all();
  };
  GF.WWF.qcCoaFilter = (v) => { GF.WWF._qccoa.q = v; GF.render.all(); };
  GF.WWF.qcCoaStatus = (v) => { GF.WWF._qccoa.status = v; GF.WWF.loadQcCoas(); };

  const _reload = async (id) => {
    await GF.WWF.loadQcCoas();
    if (GF.WWF._qccoa.sel === id) {
      GF.WWF._qccoa.detail = await GF.API.qcCoa(id).catch(() => null);
      GF.render.all();
    }
  };

  GF.WWF.qcCoaAdvance = async (id, target) => {
    try { await GF.API.qcPatchCoa(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcCoaDecide = async (id, decision) => {
    try { await GF.API.qcPatchCoa(id, { decision }); GF.toast(AL('Recorded', 'Запишано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };

  // Certificate of Quality — render a released cert to a house-style .docx via
  // the DocEngine (PASS-gated); QP-only (mirrors the backend gate).
  GF.WWF.qcCoaGenerateCoq = async (id) => {
    try {
      await GF.API.qcGenerateCoq(id);
      GF.toast(AL('Certificate of Quality generated', 'Сертификат за квалитет генериран'));
    } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcCoaDlCoq = async (docId, kind) => {
    const url = kind === 'pdf' ? GF.API.studioPdfUrl(docId) : GF.API.studioDocxUrl(docId);
    try {
      const res = await fetch(url, { headers: { Authorization: 'Bearer ' + GF.API.token } });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = docId + (kind === 'pdf' ? '.pdf' : '.docx');
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.qcCoaCreate = async () => {
    const mk = (i) => (document.getElementById(i) || {}).value || '';
    const batch_id = mk('qco-batch').trim(), specification_id = mk('qco-spec');
    if (!batch_id || !specification_id) {
      return GF.toast(AL('Batch and specification are required', 'Потребни се серија и спецификација'), 'error');
    }
    const body = { batch_id, specification_id, cert_type: mk('qco-type') || 'ICOA' };
    const smp = mk('qco-sample'); if (smp) body.sample_id = smp;
    const lab = mk('qco-lab').trim(); if (lab) body.source_lab = lab;
    try {
      const coa = await GF.API.qcCreateCoa(body);
      GF.toast(coa.coa_number + ' ' + AL('created', 'креирано'));
      await GF.WWF.loadQcCoas(); GF.WWF.qcCoaPick(coa.id);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.qcCoaAddResult = async (id) => {
    const mk = (i) => (document.getElementById(i) || {}).value || '';
    const num = (i) => { const v = mk(i).trim(); return v === '' ? null : parseFloat(v); };
    const pid = mk('qcr-param');
    const param = pid ? (GF.WWF._qccoa.specParams || []).find(p => p.id === pid) : null;
    const test_name = (param ? param.test_name_en : mk('qcr-name').trim());
    if (!test_name) return GF.toast(AL('Test name required', 'Потребно е име на тест'), 'error');
    const body = { test_name, result_value: mk('qcr-val').trim() || null,
                   result_numeric: num('qcr-num'), unit: mk('qcr-unit').trim() || null };
    if (param) {
      body.parameter_id = pid;               // server snapshots the param's limits
    } else {
      body.lower_limit = num('qcr-lo'); body.upper_limit = num('qcr-hi');
    }
    try {
      await GF.API.qcAddResult(id, body);
      GF.WWF._qccoa.detail = await GF.API.qcCoa(id);
      GF.render.all();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  const resultRows = (d) => {
    const editable = d.coa.status === 'DRAFT';
    const rows = (d.results || []).map(r => `
      <tr>
        <td>${GF.esc(r.test_name)}</td>
        <td class="mono">${r.result_value != null ? GF.esc(r.result_value) : (r.result_numeric != null ? GF.esc(String(r.result_numeric)) : '—')} ${GF.esc(r.unit || '')}</td>
        <td class="mono">${r.lower_limit != null ? GF.esc(String(r.lower_limit)) : '—'} … ${r.upper_limit != null ? GF.esc(String(r.upper_limit)) : '—'}</td>
        <td>${compliesChip(r.complies)}</td>
      </tr>`).join('');
    const params = GF.WWF._qccoa.specParams || [];
    const paramOpts = params.length
      ? `<option value="">${AL('Free test…', 'Слободен тест…')}</option>` +
        params.map(p => `<option value="${p.id}">${GF.esc(p.test_name_en)}</option>`).join('')
      : '';
    const addRow = (editable && canWrite()) ? `
      <tr class="qcp-add">
        <td>${params.length ? `<select id="qcr-param" style="margin-bottom:4px">${paramOpts}</select>` : ''}<input id="qcr-name" placeholder="${AL('Test name', 'Име на тест')}"></td>
        <td><input id="qcr-val" placeholder="${AL('value / n.d.', 'вредност / н.о.')}" style="width:88px"> <input id="qcr-num" placeholder="${AL('numeric', 'број')}" style="width:70px"> <input id="qcr-unit" placeholder="${AL('unit', 'ед')}" style="width:52px"></td>
        <td><input id="qcr-lo" placeholder="${AL('min', 'мин')}" style="width:56px"> <input id="qcr-hi" placeholder="${AL('max', 'макс')}" style="width:56px"></td>
        <td><button class="btn btn-sm btn-primary" onclick="GF.WWF.qcCoaAddResult('${d.coa.id}')">+</button></td>
      </tr>` : '';
    return `<table class="qcp-table"><thead><tr>
      <th>${AL('Test', 'Тест')}</th><th>${AL('Result', 'Резултат')}</th>
      <th>${AL('Limits', 'Граници')}</th><th>${AL('Complies', 'Задоволува')}</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="4" class="ana-note">${AL('No results yet', 'Сè уште нема резултати')}</td></tr>`}${addRow}</tbody></table>`;
  };

  const detail = (d) => {
    const c = d.coa;
    const nxt = NEXT[c.status];
    const anyFail = (d.results || []).some(r => r.complies === false);
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Certificate', 'Сертификат')}</span><b class="mono">${GF.esc(c.coa_number)}</b>
        <span>${AL('Batch', 'Серија')}</span><b>${GF.esc(c.batch_id)}</b>
        <span>${AL('Type', 'Тип')}</span><b>${GF.esc(c.cert_type)}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(c.status)}</b>
        <span>${AL('Decision', 'Одлука')}</span><b>${decChip(c.decision)}</b>
        ${c.source_lab ? `<span>${AL('Lab', 'Лабораторија')}</span><b>${GF.esc(c.source_lab)}</b>` : ''}
      </div>
      ${anyFail ? `<div class="ana-note" style="color:var(--red-fg,var(--red));margin-top:6px">${AL('⚠ One or more results are out of specification.', '⚠ Еден или повеќе резултати се надвор од спецификација.')}</div>` : ''}
      ${canWrite() ? `<div class="qms-dl" style="margin-top:8px">
        ${nxt && (!QP_TARGETS[nxt] || canQP()) ? `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcCoaAdvance('${c.id}','${nxt}')">${AL('Advance to', 'Напредувај до')} ${GF.esc(AL((ST[nxt]||{}).en || nxt, (ST[nxt]||{}).mk || nxt))}</button>` : ''}
        ${c.status !== 'DRAFT' && c.status !== 'RELEASED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcCoaDecide('${c.id}','PASS')">${AL('Mark PASS', 'Означи PASS')}</button>
          <button class="btn btn-sm" onclick="GF.WWF.qcCoaDecide('${c.id}','FAIL')">${AL('Mark FAIL', 'Означи FAIL')}</button>` : ''}
      </div>` : ''}
      ${c.status === 'RELEASED' && canQP() ? `<div class="qms-dl" style="margin-top:8px">
        <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcCoaGenerateCoq('${c.id}')">${AL('Generate COQ', 'Генерирај COQ')}</button>
        ${c.coq_document_id ? `<button class="btn btn-sm" onclick="GF.WWF.qcCoaDlCoq('${GF.esc(c.coq_document_id)}','docx')">${AL('COQ .docx', 'COQ .docx')}</button>
          <button class="btn btn-sm" onclick="GF.WWF.qcCoaDlCoq('${GF.esc(c.coq_document_id)}','pdf')">${AL('COQ PDF', 'COQ PDF')}</button>` : ''}
      </div>` : ''}
      <div style="margin-top:12px" class="ana-pt">${AL('Test results', 'Тест резултати')}</div>
      ${resultRows(d)}
    </div>`;
  };

  const coaList = () => {
    const st = GF.WWF._qccoa;
    const q = st.q.trim().toLowerCase();
    const rows = (st.coas || []).filter(c => !q
      || (c.coa_number || '').toLowerCase().includes(q)
      || (c.batch_id || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(c => `
      <div class="qms-row ${st.sel === c.id ? 'on' : ''}" onclick="GF.WWF.qcCoaPick('${c.id}')">
        <span class="mono qms-code">${GF.esc(c.coa_number)}</span>
        <span class="qms-title">${GF.esc(c.batch_id)} <span class="ana-note">${GF.esc(c.cert_type)}</span></span>
        ${decChip(c.decision)}${stChip(c.status)}
      </div>
      ${st.sel === c.id ? (st.detail ? detail(st.detail) : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`) : ''}`).join('');
  };

  GF.views.qccoa = () => {
    const st = GF.WWF._qccoa;
    if (!st.coas && !st.loading && !st.error) GF.WWF.loadQcCoas();
    const head = GF.viewHead('qc_coas', 'qc_coas_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — certificates of analysis. Every result is judged against the specification; approve / release is a Qualified-Person decision.',
      'QMS Студио — сертификати за анализа. Секој резултат се оценува според спецификацијата; одобрувањето / ослободувањето е одлука на Квалификуваното лице.')}</div>`;
    if (st.loading || (!st.coas && !st.error)) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcCoas()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const specOpts = (st.specs || []).map(s =>
      `<option value="${s.id}">${GF.esc(s.spec_id)} · ${GF.esc(s.material_code)}</option>`).join('');
    const sampleOpts = (st.samples || []).map(s =>
      `<option value="${s.id}">${GF.esc(s.sample_id)} · ${GF.esc(s.batch_id)}</option>`).join('');
    const create = canWrite() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${AL('New certificate', 'Нов сертификат')}</div>
        <div class="qcs-form">
          <input id="qco-batch" placeholder="${AL('Batch id', 'Серија')}">
          <select id="qco-spec"><option value="">${AL('Specification…', 'Спецификација…')}</option>${specOpts}</select>
          <select id="qco-type">${CERT_TYPES.map(t => `<option value="${t}">${t}</option>`).join('')}</select>
          <select id="qco-sample"><option value="">${AL('Link sample (optional)', 'Поврзи примерок (опц.)')}</option>${sampleOpts}</select>
          <input id="qco-lab" placeholder="${AL('Source lab (optional)', 'Лабораторија (опц.)')}">
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcCoaCreate()">${GF.t('create_task') || 'Create'}</button>
        </div>
      </div>` : '';
    return head + zone + create + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Certificates', 'Сертификати')}</div>
          <input class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcCoaFilter(this.value)">
          <select onchange="GF.WWF.qcCoaStatus(this.value)">
            <option value="">${AL('All statuses', 'Сите статуси')}</option>
            ${Object.keys(ST).map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
        </div>
        <div class="qms-list">${coaList()}</div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qccoa', icon: 'award',
    label: () => AL('QC Certificates', 'КК Сертификати'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
