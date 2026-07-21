/* qclab-view.js — QC LIMS: accredited laboratories registry (URS Chapter 7).

   The structured replacement for the free-text source_institution/source_lab
   provenance strings. A laboratory carries its accreditation body/number, its
   ISO 17025 accredited scope (the method/test tokens it is accredited to run —
   a certificate result on a method outside this list is flagged on the COQ),
   the quality-agreement reference, and the lab's decimal separator (the
   decimal-comma defence: a German lab writes 1,5 for 1.5). Reference master
   data, so the lifecycle is the simple ACTIVE/INACTIVE pair.

   Read = any elevated role; write = QC_MGR / QP / execs / ADMIN, gated by the
   backend and mirrored by canWrite(). Same full-page-view + qms-zone pattern as
   qcspec; QMS Studio zone, anchored insertBefore 'qms-end'. */

(function () {
  GF.WWF._qclab = { labs: null, sel: null, detail: null, detailError: null,
                    q: '', status: '', loading: false, error: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);

  const ST = {
    ACTIVE: { en: 'Active', mk: 'Активна', c: 'var(--green)' },
    INACTIVE: { en: 'Inactive', mk: 'Неактивна', c: 'var(--ink-3)' },
  };
  const stChip = (s) => {
    const m = ST[s] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' };
    return `<span class="chip-opt" style="border-color:${m.c};color:${m.c}">${GF.esc(AL(m.en, m.mk))}</span>`;
  };

  GF.WWF.loadQcLabs = async () => {
    const st = GF.WWF._qclab;
    st.loading = true; st.error = null;
    try {
      const q = {}; if (st.status) q.status = st.status;
      st.labs = await GF.API.qcLabs(q);
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'qclab') GF.render.all();
  };

  GF.WWF.qcLabPick = async (id) => {
    const st = GF.WWF._qclab;
    if (st.sel === id) { st.sel = null; st.detail = null; st.detailError = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; st.detailError = null; GF.render.all();
    try { st.detail = await GF.API.qcLab(id); }
    catch (e) { st.detailError = e.message; GF.toast(e.message, 'error'); }
    if (GF.state.view === 'qclab') GF.render.all();
  };
  GF.WWF.qcLabFilter = (v) => { GF.WWF._qclab.q = v; GF.render.all(); GF.refocus('qcl-search'); };
  GF.WWF.qcLabStatus = async (v) => { GF.WWF._qclab.status = v; await GF.WWF.loadQcLabs(); GF.refocus('qcl-status'); };

  const _reload = async (id) => {
    await GF.WWF.loadQcLabs();
    if (GF.WWF._qclab.sel === id) { GF.WWF._qclab.detail = await GF.API.qcLab(id).catch(() => null); GF.render.all(); }
  };

  GF.WWF.qcLabCreate = async () => {
    const mk = (i) => (document.getElementById(i) || {}).value || '';
    const name = mk('qcl-name').trim();
    if (!name) return GF.toast(AL('Laboratory name required', 'Потребно е име на лабораторија'), 'error');
    const scope = mk('qcl-scope').split(',').map(s => s.trim()).filter(Boolean);
    const body = {
      name, accreditation_body: mk('qcl-body').trim() || null,
      accreditation_number: mk('qcl-num').trim() || null,
      iso17025_scope: scope, quality_agreement_ref: mk('qcl-qa').trim() || null,
      locale: mk('qcl-locale').trim() || null, decimal_separator: mk('qcl-dec') || '.',
      country: mk('qcl-country').trim() || null,
    };
    try {
      const lab = await GF.API.qcCreateLab(body);
      GF.toast(lab.lab_code + ' ' + AL('created', 'креирана'));
      await GF.WWF.loadQcLabs();
      GF.WWF.qcLabPick(lab.id);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.qcLabToggle = async (id, status) => {
    try { await GF.API.qcPatchLab(id, { status }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };

  const detail = (d) => {
    const scope = (d.iso17025_scope || []);
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Code', 'Код')}</span><b class="mono">${GF.esc(d.lab_code)}</b>
        <span>${AL('Name', 'Име')}</span><b>${GF.esc(d.name)}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(d.status)}</b>
        ${d.accreditation_body || d.accreditation_number ? `<span>${AL('Accreditation', 'Акредитација')}</span><b>${GF.esc([d.accreditation_body, d.accreditation_number].filter(Boolean).join(' · '))}</b>` : ''}
        ${d.quality_agreement_ref ? `<span>${AL('Quality agreement', 'Договор за квалитет')}</span><b>${GF.esc(d.quality_agreement_ref)}</b>` : ''}
        ${d.locale ? `<span>${AL('Locale', 'Локал')}</span><b>${GF.esc(d.locale)}</b>` : ''}
        <span>${AL('Decimal', 'Децимала')}</span><b class="mono">${GF.esc(d.decimal_separator)}</b>
        ${d.country ? `<span>${AL('Country', 'Земја')}</span><b>${GF.esc(d.country)}</b>` : ''}
      </div>
      <div style="margin-top:10px" class="ana-pt">${AL('ISO 17025 scope', 'ISO 17025 опсег')}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px">${
        scope.length ? scope.map(s => `<span class="chip-opt">${GF.esc(s)}</span>`).join('')
                     : `<span class="ana-note">${AL('No accredited scope declared — results are not scope-flagged.', 'Не е декларран акредитиран опсег — резултатите не се означуваат.')}</span>`}</div>
      ${canWrite() ? `<div class="qms-dl" style="margin-top:10px">
        ${d.status === 'ACTIVE'
          ? `<button class="btn btn-sm" onclick="GF.WWF.qcLabToggle('${d.id}','INACTIVE')">${AL('Deactivate', 'Деактивирај')}</button>`
          : `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcLabToggle('${d.id}','ACTIVE')">${AL('Activate', 'Активирај')}</button>`}
      </div>` : ''}
    </div>`;
  };

  const labList = () => {
    const st = GF.WWF._qclab;
    const q = st.q.trim().toLowerCase();
    const rows = (st.labs || []).filter(l => !q
      || (l.name || '').toLowerCase().includes(q)
      || (l.lab_code || '').toLowerCase().includes(q)
      || (l.accreditation_body || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(l => `
      <div class="qms-row ${st.sel === l.id ? 'on' : ''}" onclick="GF.WWF.qcLabPick('${l.id}')">
        <span class="mono qms-code">${GF.esc(l.lab_code)}</span>
        <span class="qms-title">${GF.esc(l.name)} ${l.accreditation_body ? `<span class="ana-note">${GF.esc(l.accreditation_body)}</span>` : ''}</span>
        ${stChip(l.status)}
      </div>
      ${st.sel === l.id ? (st.detail ? detail(st.detail) : (st.detailError
        ? `<div class="qms-detail" style="color:var(--red-fg,var(--red))">${GF.esc(st.detailError)}</div>`
        : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`)) : ''}`).join('');
  };

  GF.views.qclab = () => {
    const st = GF.WWF._qclab;
    if (!st.labs && !st.loading && !st.error) GF.WWF.loadQcLabs();
    const head = GF.viewHead('qc_labs', 'qc_labs_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — accredited laboratories. A result run on a method outside a lab\'s ISO 17025 scope is flagged on the certificate.',
      'QMS Студио — акредитирани лаборатории. Резултат на метод надвор од ISO 17025 опсегот на лабораторијата се означува на сертификатот.')}</div>`;
    if (st.loading || (!st.labs && !st.error)) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcLabs()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const create = canWrite() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${AL('New laboratory', 'Нова лабораторија')}</div>
        <div class="qcs-form">
          <input id="qcl-name" placeholder="${AL('Laboratory name', 'Име на лабораторија')}">
          <input id="qcl-body" placeholder="${AL('Accreditation body', 'Акредитационо тело')}">
          <input id="qcl-num" placeholder="${AL('Accreditation №', 'Акредитација №')}">
          <input id="qcl-scope" placeholder="${AL('ISO 17025 scope (comma-sep methods)', 'ISO 17025 опсег (методи, запирка)')}" style="min-width:220px">
          <input id="qcl-qa" placeholder="${AL('Quality agreement ref', 'Реф. договор за квалитет')}">
          <input id="qcl-locale" placeholder="${AL('Locale (e.g. de-DE)', 'Локал (пр. de-DE)')}" style="width:110px">
          <select id="qcl-dec" title="${AL('Decimal separator', 'Децимален раздвојувач')}"><option value=".">1.5</option><option value=",">1,5</option></select>
          <input id="qcl-country" placeholder="${AL('Country', 'Земја')}" style="width:110px">
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcLabCreate()">${GF.t('create_task') || 'Create'}</button>
        </div>
      </div>` : '';
    return head + zone + create + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Laboratories', 'Лаборатории')}</div>
          <input id="qcl-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcLabFilter(this.value)">
          <select id="qcl-status" onchange="GF.WWF.qcLabStatus(this.value)">
            <option value="">${AL('All statuses', 'Сите статуси')}</option>
            ${Object.keys(ST).map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
        </div>
        <div class="qms-list">${labList()}</div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qclab', icon: 'flask',
    label: () => AL('QC Laboratories', 'КК Лаборатории'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
