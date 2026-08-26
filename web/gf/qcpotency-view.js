/* qcpotency-view.js — QC LIMS: per-cultivar potency ladders (QCSP 001).

   The stored, APPROVED grade ladders of PP-QC-SPEC-001 / QCSP 001: one ladder
   version per cultivar, tiers I..N with 2-decimal ranges and nominals; a
   batch's Total Δ9-THC resolves to a Spec tier against the cultivar's APPROVED
   ladder (the CoQ freezes that version at compile). This view is the human
   half of the model: review imported/authored DRAFT ladders, approve them
   (second person — the backend refuses the author), supersede, and open the
   per-grade A4 Product Specification document.

   The 71-strain owner catalogue ships with the backend; "Import catalogue"
   loads a family (BASE_SPCs / NEWs / RENs / ALL) as DRAFT rows, idempotently.
   Same full-page-view + qms-zone pattern as qcspec-view; QMS Studio zone. */

(function () {
  GF.WWF._qcpot = { specs: null, sel: null, detail: null, detailError: null, q: '', status: '',
                    loading: false, error: null, importing: false };

  const _HOQC = ['ADMIN', 'QC_MGR', 'QP'];
  const canApprove = () => _HOQC.includes((GF.API.user || {}).role);
  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);

  const ST = {
    DRAFT: { en: 'Draft', mk: 'Нацрт', c: 'var(--orange)' },
    APPROVED: { en: 'Approved', mk: 'Одобрено', c: 'var(--green)' },
    SUPERSEDED: { en: 'Superseded', mk: 'Заменето', c: 'var(--ink-3)' },
  };
  const stChip = (s) => {
    const m = ST[s] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' };
    return `<span class="chip-opt" style="border-color:${m.c};color:${m.c}">${GF.esc(AL(m.en, m.mk))}</span>`;
  };
  const ROMAN = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI' };

  GF.WWF.loadQcPotency = async () => {
    const st = GF.WWF._qcpot;
    st.loading = true; st.error = null;
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      const q = {};
      if (st.status) q.status = st.status;
      const specs = await GF.API.qcPotencySpecs(q);
      if (my !== st.lseq) return;
      st.specs = specs;
    } catch (e) { if (my === st.lseq) st.error = e.message; }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'qcpotency') GF.render.all();
  };

  GF.WWF.qcPotPick = async (id) => {
    const st = GF.WWF._qcpot;
    if (st.sel === id) { st.sel = null; st.detail = null; st.detailError = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; st.detailError = null; GF.render.all();
    try { const d = await GF.API.qcPotencySpec(id); if (st.sel === id) st.detail = d; }
    catch (e) { if (st.sel === id) { st.detailError = e.message; GF.toast(e.message, 'error'); } }
    if (st.sel === id && GF.state.view === 'qcpotency') GF.render.all();
  };
  // Retry after a failed detail fetch: clearing sel first lets pick() take the
  // select path again, so one click re-fetches the same row.
  GF.WWF.qcPotRetry = (id) => {
    const st = GF.WWF._qcpot;
    st.sel = null; st.detail = null; st.detailError = null;
    GF.WWF.qcPotPick(id);
  };
  GF.WWF.qcPotFilter = (v) => { GF.WWF._qcpot.q = v; GF.render.all(); GF.refocus('qcp-search'); };
  GF.WWF.qcPotStatus = (v) => { GF.WWF._qcpot.status = v; GF.WWF.loadQcPotency(); };

  const _reload = async (id) => {
    await GF.WWF.loadQcPotency();
    if (GF.WWF._qcpot.sel === id) {
      GF.WWF._qcpot.detail = await GF.API.qcPotencySpec(id).catch(() => null);
      GF.render.all();
    }
  };

  GF.WWF.qcPotApprove = async (id) => {
    try {
      await GF.API.qcApprovePotencySpec(id);
      GF.toast(AL('Ladder approved — it now grades certificates', 'Скалата е одобрена — сега ги оценува сертификатите'));
    } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcPotSupersede = async (id) => {
    try { await GF.API.qcSupersedePotencySpec(id); GF.toast(AL('Ladder superseded', 'Скалата е заменета')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcPotImport = async () => {
    const fam = (document.getElementById('qcp-family') || {}).value || 'ALL';
    const st = GF.WWF._qcpot;
    st.importing = true; GF.render.all();
    try {
      const r = await GF.API.qcImportPotencySpecs({ family: fam });
      GF.toast(AL(`Imported ${r.created.length} ladder(s), skipped ${r.skipped.length}`,
                  `Внесени ${r.created.length} скали, прескокнати ${r.skipped.length}`));
    } catch (e) { GF.toast(e.message, 'error'); }
    st.importing = false;
    await GF.WWF.loadQcPotency();
  };

  const detail = (d) => {
    const s = d.spec;
    const rows = (d.ranges || []).map(r => `<tr${s.status === 'APPROVED' ? '' : ' class="ana-note"'}>
      <td>Spec ${GF.esc(ROMAN[r.tier] || r.tier)}</td>
      <td class="mono">${GF.esc(String(r.nominal))}%${r.width_pp != null ? ` ± ${GF.esc(String(r.width_pp))}%` : ''}</td>
      <td class="mono">${GF.esc(String(r.range_min))} – ${GF.esc(String(r.range_max))}%</td>
      <td><a class="btn btn-sm" target="_blank" rel="noopener" href="${GF.API.qcSpecDocumentUrl(s.id, r.tier)}">${AL('A4 document', 'A4 документ')}</a></td>
    </tr>`).join('');
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Cultivar', 'Сорта')}</span><b>${GF.esc(s.cultivar_name || '')} <span class="ana-note mono">${GF.esc(s.cultivar_code || '')}</span></b>
        <span>${AL('Version', 'Верзија')}</span><b class="mono">${GF.esc(s.version)}${s.variant ? ` <span class="ana-note">${GF.esc(s.variant)}</span>` : ''}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(s.status)}</b>
        <span>${AL('Floor', 'Под')}</span><b class="mono">${GF.esc(String(s.floor_pct))}%</b>
        <span>${AL('Data support', 'Податоци')}</span><b>${s.data_supported ? AL('data-supported (≥3 batches)', 'поддржано со податоци (≥3 серии)') : AL('provisional', 'привремено')}</b>
        ${s.effective_date ? `<span>${AL('Effective', 'Важи од')}</span><b class="mono">${GF.esc(s.effective_date)}</b>` : ''}
      </div>
      ${s.notes ? `<div class="ana-note" style="margin-top:6px">${GF.esc(s.notes)}</div>` : ''}
      <div style="margin-top:10px" class="ana-pt">${AL('Grade ladder (Total Δ9-THC)', 'Скала на класи (вкупен Δ9-THC)')}</div>
      <table class="qcp-table"><thead><tr>
        <th>${AL('Grade', 'Класа')}</th><th>${AL('Nominal', 'Номинал')}</th>
        <th>${AL('Range', 'Опсег')}</th><th></th></tr></thead><tbody>${rows}</tbody></table>
      ${canApprove() ? `<div class="qms-dl" style="margin-top:8px">
        ${s.status === 'DRAFT' ? `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcPotApprove('${s.id}')" title="${AL('Second person only — the backend refuses the author (segregation of duties)', 'Само второ лице — серверот го одбива авторот')}">${AL('Approve', 'Одобри')}</button>` : ''}
        ${s.status === 'APPROVED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcPotSupersede('${s.id}')">${AL('Supersede', 'Замени')}</button>` : ''}
      </div>` : ''}
    </div>`;
  };

  GF.views.qcpotency = () => {
    const st = GF.WWF._qcpot;
    if (!st.specs && !st.loading && !st.error) GF.WWF.loadQcPotency();
    const head = GF.viewHead('qc_potency', 'qc_potency_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — per-cultivar potency grade ladders (QCSP 001). A batch\'s Total Δ9-THC resolves to its Spec tier against the cultivar\'s APPROVED ladder; approval is a second-person act.',
      'QMS Студио — скали на класи по сорта (QCSP 001). Вкупниот Δ9-THC на серијата се оценува според ОДОБРЕНАТА скала на сортата; одобрувањето е чин на второ лице.')}</div>`;
    if (st.loading && !st.specs) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcPotency()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const q = st.q.trim().toLowerCase();
    const rows = (st.specs || []).filter(s => !q
      || (s.cultivar_name || '').toLowerCase().includes(q)
      || (s.cultivar_code || '').toLowerCase().includes(q)
      || (s.version || '').toLowerCase().includes(q));
    const list = rows.length ? rows.map(s => `
      <div class="qms-row ${st.sel === s.id ? 'on' : ''}" onclick="GF.WWF.qcPotPick('${s.id}')">
        <span class="mono qms-code">${GF.esc(s.cultivar_code || '')}</span>
        <span class="qms-title">${GF.esc(s.cultivar_name || '')} <span class="ana-note mono">${GF.esc(s.version)}</span>
          ${s.data_supported ? '' : `<span class="ana-note">· ${AL('provisional', 'привремено')}</span>`}</span>
        ${stChip(s.status)}
      </div>
      ${st.sel === s.id ? (st.detail ? detail(st.detail) : (st.detailError
        ? `<div class="qms-detail" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
             <span style="color:var(--red-fg,var(--red))">${GF.esc(st.detailError)}</span>
             <button class="btn btn-sm" onclick="GF.WWF.qcPotRetry('${s.id}')">${AL('Failed — retry', 'Неуспешно — обиди се повторно')}</button></div>`
        : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`)) : ''}`).join('')
      : `<div class="ana-note">${AL('No potency ladders yet — import the owner catalogue below.', 'Сè уште нема скали — внесете го каталогот подолу.')}</div>`;
    const importer = canApprove() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${AL('Import the owner catalogue (71 strains, DRAFT)', 'Внеси каталог (71 сорти, нацрт)')}</div>
        <div class="qcs-form">
          <select id="qcp-family">
            <option value="ALL">ALL</option><option value="BASE_SPCs">BASE_SPCs (CULI-001)</option>
            <option value="NEWs">NEWs</option><option value="RENs">RENs</option>
          </select>
          <button class="btn btn-sm btn-primary" ${st.importing ? 'disabled' : ''} onclick="GF.WWF.qcPotImport()">${st.importing ? AL('Importing…', 'Внесување…') : AL('Import catalogue', 'Внеси каталог')}</button>
        </div>
        <div class="ana-note" style="margin-top:6px">${AL('Idempotent: an existing cultivar+version is skipped. Everything lands as DRAFT — approval stays a human, second-person act.', 'Идемпотентно: постоечка сорта+верзија се прескокнува. Сè влегува како нацрт — одобрувањето останува чин на второ лице.')}</div>
      </div>` : '';
    return head + zone + importer + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Potency ladders', 'Скали на јачина')}</div>
          <input id="qcp-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcPotFilter(this.value)">
          <select onchange="GF.WWF.qcPotStatus(this.value)">
            <option value="">${AL('All statuses', 'Сите статуси')}</option>
            ${Object.keys(ST).map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
        </div>
        <div class="qms-list">${list}</div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qcpotency', icon: 'flask',
    label: () => AL('Potency ladders', 'Скали на јачина'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
