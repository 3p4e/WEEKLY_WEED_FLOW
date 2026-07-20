/* qcregister-view.js — QC LIMS: certificate register (QCLB 020 §6.13).

   A read layer over the certificates: the §6.13 canned queries (by year /
   quarter / type / lab; pending; OOS-linked; end-of-retention) with each row
   carrying its OOS + supersession cross-references and retention window, plus
   a numbering-gap data-integrity report. Read = any elevated role. Same
   full-page-view + qms-zone pattern; QMS Studio zone, anchored 'qms-end'. */

(function () {
  GF.WWF._qcreg = { rows: null, gaps: null, labs: null,
                    f: { year: '', quarter: '', cert_type: '', laboratory_id: '',
                         pending: false, oos_linked: false, retention: '' },
                    loading: false, error: null };

  const CERT_TYPES = ['ICOA', 'ECOA', 'COQ', 'WATER', 'OTHER'];

  const stColor = (s) => ({
    DRAFT: 'var(--orange)', REVIEWED: 'var(--violet)', APPROVED: 'var(--teal,var(--blue))',
    RELEASED: 'var(--green)', SUPERSEDED: 'var(--ink-3)',
  }[s] || 'var(--ink-3)');
  const stChip = (s) => `<span class="chip-opt" style="border-color:${stColor(s)};color:${stColor(s)}">${GF.esc(s || '—')}</span>`;

  GF.WWF.loadQcRegister = async () => {
    const st = GF.WWF._qcreg;
    st.loading = true; st.error = null;
    try {
      const f = st.f;
      const q = {};
      if (f.year) q.year = f.year;
      if (f.quarter) q.quarter = f.quarter;
      if (f.cert_type) q.cert_type = f.cert_type;
      if (f.laboratory_id) q.laboratory_id = f.laboratory_id;
      if (f.pending) q.pending = 'true';
      if (f.oos_linked) q.oos_linked = 'true';
      if (f.retention) q.retention = f.retention;
      st.rows = await GF.API.qcRegister(q);
      if (st.labs === null) st.labs = await GF.API.qcLabs({}).catch(() => []);
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'qcregister') GF.render.all();
  };

  GF.WWF.qcRegSet = async (key, val) => {
    GF.WWF._qcreg.f[key] = val;
    await GF.WWF.loadQcRegister();
    GF.refocus('qcreg-' + key);
  };
  GF.WWF.qcRegToggle = async (key) => {
    GF.WWF._qcreg.f[key] = !GF.WWF._qcreg.f[key];
    await GF.WWF.loadQcRegister();
  };

  GF.WWF.qcRegGaps = async () => {
    const st = GF.WWF._qcreg;
    const year = st.f.year || new Date().getFullYear();
    try { st.gaps = await GF.API.qcRegisterGaps(year); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };

  const regTable = () => {
    const st = GF.WWF._qcreg;
    const rows = st.rows || [];
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    const tr = rows.map(r => `
      <tr>
        <td class="mono">${GF.esc(r.coa_number)}</td>
        <td>${GF.esc(r.batch_id)}</td>
        <td>${GF.esc(r.cert_type)}</td>
        <td>${stChip(r.status)}</td>
        <td>${GF.esc(r.laboratory || '—')}</td>
        <td class="mono">${r.retention_expiry ? GF.esc(r.retention_expiry) : '—'}</td>
        <td>${GF.esc(r.archive_ref || '—')}</td>
        <td>${r.open_oos ? `<span class="chip-opt" style="border-color:var(--red);color:var(--red)">${r.open_oos} OOS</span>` : '—'}</td>
        <td>${r.superseded_by ? `<span class="ana-note">→ ${GF.esc(r.superseded_by)}</span>` : (r.supersedes_id ? `<span class="ana-note">${AL('revision', 'ревизија')}</span>` : '—')}</td>
      </tr>`).join('');
    return `<div style="overflow-x:auto"><table class="qcp-table"><thead><tr>
      <th>${AL('Number', 'Број')}</th><th>${AL('Batch', 'Серија')}</th><th>${AL('Type', 'Тип')}</th>
      <th>${AL('Status', 'Статус')}</th><th>${AL('Laboratory', 'Лабораторија')}</th>
      <th>${AL('Retention', 'Чување')}</th><th>${AL('Archive', 'Архива')}</th>
      <th>OOS</th><th>${AL('Supersession', 'Замена')}</th></tr></thead>
      <tbody>${tr}</tbody></table></div>`;
  };

  const gapsPanel = () => {
    const g = GF.WWF._qcreg.gaps;
    if (!g) return '';
    return `<div class="panel ana-panel" style="margin-top:12px">
      <div class="ana-pt" style="margin-bottom:6px">${AL('Numbering gaps', 'Празнини во нумерација')} · ${g.year}</div>
      <div class="ana-note" style="margin-bottom:6px">${AL('Issued', 'Издадени')}: ${g.issued}${g.min != null ? ` · ${AL('range', 'опсег')} ${g.min}–${g.max}` : ''}</div>
      ${(g.gaps || []).length
        ? `<div style="display:flex;gap:6px;flex-wrap:wrap">${g.gaps.map(x => `<span class="chip-opt" style="border-color:var(--amber);color:var(--amber)">${GF.esc(x)}</span>`).join('')}</div>`
        : `<div class="ana-note" style="color:var(--green)">${AL('No gaps in the issued range.', 'Нема празнини во издадениот опсег.')}</div>`}
      <div class="ana-note" style="margin-top:8px;font-style:italic">${GF.esc(g.note || '')}</div>
    </div>`;
  };

  GF.views.qcregister = () => {
    const st = GF.WWF._qcreg;
    if (!st.rows && !st.loading && !st.error) GF.WWF.loadQcRegister();
    const head = GF.viewHead('qc_register', 'qc_register_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — the certificate register (QCLB 020 §6.13): canned queries + numbering-gap integrity check.',
      'QMS Студио — регистар на сертификати (QCLB 020 §6.13): предефинирани прашања + проверка на празнини во нумерацијата.')}</div>`;
    if (st.loading && !st.rows) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcRegister()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const f = st.f;
    const labOpts = (st.labs || []).map(l => `<option value="${l.id}" ${f.laboratory_id === l.id ? 'selected' : ''}>${GF.esc(l.name)}</option>`).join('');
    const filters = `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <input id="qcreg-year" placeholder="${AL('Year', 'Година')}" style="width:80px" value="${GF.esc(f.year)}" onchange="GF.WWF.qcRegSet('year', this.value)">
          <select id="qcreg-quarter" onchange="GF.WWF.qcRegSet('quarter', this.value)">
            <option value="">${AL('All quarters', 'Сите квартали')}</option>
            ${[1, 2, 3, 4].map(q => `<option value="${q}" ${String(f.quarter) === String(q) ? 'selected' : ''}>Q${q}</option>`).join('')}
          </select>
          <select id="qcreg-cert_type" onchange="GF.WWF.qcRegSet('cert_type', this.value)">
            <option value="">${AL('All types', 'Сите типови')}</option>
            ${CERT_TYPES.map(t => `<option value="${t}" ${f.cert_type === t ? 'selected' : ''}>${t}</option>`).join('')}
          </select>
          <select id="qcreg-laboratory_id" onchange="GF.WWF.qcRegSet('laboratory_id', this.value)">
            <option value="">${AL('All labs', 'Сите лаборатории')}</option>${labOpts}
          </select>
          <select id="qcreg-retention" onchange="GF.WWF.qcRegSet('retention', this.value)">
            <option value="">${AL('Any retention', 'Секое чување')}</option>
            <option value="expiring" ${f.retention === 'expiring' ? 'selected' : ''}>${AL('Expiring ≤90d', 'Истекува ≤90д')}</option>
            <option value="expired" ${f.retention === 'expired' ? 'selected' : ''}>${AL('Expired', 'Истечено')}</option>
          </select>
          <label class="chip-opt" style="cursor:pointer"><input type="checkbox" ${f.pending ? 'checked' : ''} onchange="GF.WWF.qcRegToggle('pending')"> ${AL('Pending', 'Во тек')}</label>
          <label class="chip-opt" style="cursor:pointer"><input type="checkbox" ${f.oos_linked ? 'checked' : ''} onchange="GF.WWF.qcRegToggle('oos_linked')"> ${AL('OOS-linked', 'Со OOS')}</label>
          <button class="btn btn-sm" onclick="GF.WWF.qcRegGaps()">${AL('Numbering gaps', 'Празнини')}</button>
        </div>
      </div>`;
    return head + zone + filters + `<div class="panel ana-panel">${regTable()}</div>` + gapsPanel();
  };

  GF.WWF._registerFullPageView({
    key: 'qcregister', icon: 'list',
    label: () => AL('QC Register', 'КК Регистар'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
