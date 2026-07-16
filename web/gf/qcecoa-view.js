/* qcecoa-view.js — QC LIMS: eCOA ingestion (Phase 3, unit 2 — "CoA in").

   A supplier / contract-lab Certificate of Analysis (a PDF) is registered
   (/qc/coa-documents), its fields transcribed (pasted here as "Label | value |
   unit" lines, one per test), server-GRADED against the material specification,
   and a reviewed document PROMOTED into a native DRAFT certificate (unit 3) —
   which then flows on to the U1 COQ. Unknown field labels surface in the
   adaptive discovery queue; a human maps a label to a spec parameter once and
   every future CoA with that label auto-maps.

   GxP: the server never invents a value; an unmapped label is queued (never
   guessed); an unmeasured value stays blank / "unknown". Read = elevated;
   write = QC_MGR / QP / execs / ADMIN. QMS Studio zone, anchored 'qms-end'. */

(function () {
  GF.WWF._qcecoa = { docs: null, sel: null, detail: null, ph: null,
                     specs: null, mapParams: {}, verify: {}, qa: {}, q: '', status: '', tab: 'docs',
                     loading: false, error: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);

  const DST = {
    UPLOADED:  { en: 'Uploaded', mk: 'Прикачено', c: 'var(--ink-3)' },
    EXTRACTED: { en: 'Extracted', mk: 'Извлечено', c: 'var(--blue)' },
    REVIEWED:  { en: 'Reviewed', mk: 'Прегледано', c: 'var(--violet)' },
    PROMOTED:  { en: 'Promoted', mk: 'Промовирано', c: 'var(--green)' },
    REJECTED:  { en: 'Rejected', mk: 'Одбиено', c: 'var(--red)' },
  };
  const GRADE = {
    graded:   { en: 'PASS/OOS', c: 'var(--green)' },
    unknown:  { en: 'unmeasured', c: 'var(--orange)' },
    unmapped: { en: 'unmapped', c: 'var(--red)' },
  };
  const chip = (txt, c) => `<span class="chip-opt" style="border-color:${c};color:${c}">${GF.esc(txt)}</span>`;
  const dChip = (s) => { const m = DST[s] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' }; return chip(AL(m.en, m.mk), m.c); };
  const complyChip = (e) => {
    if (e.grade_status === 'unmapped') return chip(AL('unmapped', 'немапирано'), 'var(--red)');
    if (e.complies === true) return chip('PASS', 'var(--green)');
    if (e.complies === false) return chip('OOS', 'var(--red)');
    return chip(AL('unmeasured', 'неизмерено'), 'var(--orange)');
  };

  GF.WWF.loadQcEcoa = async () => {
    const st = GF.WWF._qcecoa;
    st.loading = true; st.error = null;
    try {
      const q = {}; if (st.status) q.status = st.status;
      st.docs = await GF.API.qcCoaDocs(q);
      st.ph = await GF.API.qcPlaceholders({ status: 'OPEN' }).catch(() => []);
      if (!st.specs) st.specs = await GF.API.qcSpecs({}).catch(() => []);
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'qcecoa') GF.render.all();
  };

  GF.WWF.qcEcoaPick = async (id) => {
    const st = GF.WWF._qcecoa;
    if (st.sel === id) { st.sel = null; st.detail = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; GF.render.all();
    try { st.detail = await GF.API.qcCoaDoc(id); } catch (e) { GF.toast(e.message, 'error'); }
    if (GF.state.view === 'qcecoa') GF.render.all();
  };
  GF.WWF.qcEcoaFilter = (v) => { GF.WWF._qcecoa.q = v; GF.render.all(); };
  GF.WWF.qcEcoaStatus = (v) => { GF.WWF._qcecoa.status = v; GF.WWF.loadQcEcoa(); };
  GF.WWF.qcEcoaTab = (t) => { GF.WWF._qcecoa.tab = t; GF.render.all(); };

  const _reload = async (id) => {
    await GF.WWF.loadQcEcoa();
    if (GF.WWF._qcecoa.sel === id) { GF.WWF._qcecoa.detail = await GF.API.qcCoaDoc(id).catch(() => null); GF.render.all(); }
  };

  GF.WWF.qcEcoaCreate = async () => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const batch_id = mk('qec-batch');
    if (!batch_id) return GF.toast(AL('Batch is required', 'Потребна е серија'), 'error');
    const body = { batch_id };
    body.source_institution = mk('qec-src') || null;
    const spec = mk('qec-spec'); if (spec) body.specification_id = spec;
    const mat = mk('qec-mat'); if (mat) body.material_code = mat;
    const rd = mk('qec-rd'); if (rd) body.report_date = rd;
    try {
      const d = await GF.API.qcCreateCoaDoc(body);
      GF.toast(d.doc_number + ' ' + AL('registered', 'регистрирано'));
      await GF.WWF.loadQcEcoa(); GF.WWF.qcEcoaPick(d.id);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  // Parse a textarea of "Label | value | unit" lines into extraction items.
  GF.WWF.qcEcoaSubmitExtractions = async (id) => {
    const raw = ((document.getElementById('qec-extract') || {}).value || '').trim();
    if (!raw) return GF.toast(AL('Paste the CoA fields first', 'Прво залепете ги полињата'), 'error');
    const items = raw.split('\n').map(l => l.trim()).filter(Boolean).map(line => {
      const parts = line.split('|').map(p => p.trim());
      const it = { raw_label: parts[0] };
      if (parts[1]) { it.raw_value = parts[1]; const n = parseFloat(parts[1]); if (!isNaN(n)) it.numeric_value = n; }
      if (parts[2]) it.unit = parts[2];
      return it;
    }).filter(it => it.raw_label);
    if (!items.length) return;
    try {
      const r = await GF.API.qcSubmitExtractions(id, items);
      GF.toast(AL('Graded', 'Оценето') + ': ' + r.count + ' · ' + AL('unmapped', 'немапирани') + ' ' + r.unmapped);
    } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcEcoaAdvance = async (id, target) => {
    try { await GF.API.qcPatchCoaDoc(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcEcoaPromote = async (id) => {
    try {
      const r = await GF.API.qcPromoteCoaDoc(id);
      GF.toast(r.coa_number + ' — ' + r.results_created + ' ' + AL('results', 'резултати')
        + (r.skipped_unmapped ? ' (' + r.skipped_unmapped + ' ' + AL('skipped', 'прескокнати') + ')' : ''));
    } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  // Verify loop: reconcile the promoted certificate against this source doc.
  GF.WWF.qcEcoaVerify = async (docId, coaId) => {
    try {
      const v = await GF.API.qcVerifyCert(coaId);
      GF.WWF._qcecoa.verify[docId] = v;
      GF.toast(v.verdict === 'VERIFIED'
        ? AL('Verified — matches source', 'Потврдено — се совпаѓа со изворот')
        : AL('Discrepancy: ', 'Отстапување: ') + v.mismatches + '/' + v.checked);
    } catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };

  // RAG Q&A over the ingested CoA text (P3-U4).
  GF.WWF.qcEcoaIndexChunks = async (docId) => {
    const raw = ((document.getElementById('qec-chunks-' + docId) || {}).value || '').trim();
    if (!raw) return GF.toast(AL('Paste the CoA text first', 'Прво залепете го текстот'), 'error');
    // split into chunks on blank lines
    const chunks = raw.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean);
    try { const r = await GF.API.qcIndexCoaChunks(docId, chunks); GF.toast(AL('Indexed', 'Индексирано') + ': ' + r.indexed); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };
  GF.WWF.qcEcoaAsk = async (docId) => {
    const question = ((document.getElementById('qec-q-' + docId) || {}).value || '').trim();
    if (!question) return;
    try { GF.WWF._qcecoa.qa[docId] = await GF.API.qcCoaQa({ question, document_id: docId }); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };

  // Placeholder queue — map a discovered label to a spec parameter or ignore it.
  GF.WWF.qcEcoaPickSpec = async (phId, specId) => {
    const st = GF.WWF._qcecoa;
    if (!specId) { st.mapParams[phId] = null; GF.render.all(); return; }
    try { const d = await GF.API.qcSpec(specId); st.mapParams[phId] = d.parameters || []; }
    catch (e) { st.mapParams[phId] = []; }
    GF.render.all();
  };
  GF.WWF.qcEcoaMapPlaceholder = async (phId) => {
    const pid = ((document.getElementById('qec-ph-param-' + phId) || {}).value || '');
    if (!pid) return GF.toast(AL('Pick a parameter', 'Изберете параметар'), 'error');
    try { await GF.API.qcPatchPlaceholder(phId, { status: 'MAPPED', mapped_parameter_id: pid }); GF.toast(AL('Mapped', 'Мапирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcEcoa();
  };
  GF.WWF.qcEcoaIgnorePlaceholder = async (phId) => {
    try { await GF.API.qcPatchPlaceholder(phId, { status: 'IGNORED' }); }
    catch (e) { GF.toast(e.message, 'error'); }
    await GF.WWF.loadQcEcoa();
  };

  const detail = (d) => {
    const doc = d.document;
    const ex = (d.extractions || []).map(e => `
      <tr><td>${GF.esc(e.raw_label)}${e.test_name && e.test_name !== e.raw_label ? ` <span class="ana-note">→ ${GF.esc(e.test_name)}</span>` : ''}</td>
      <td class="mono">${GF.esc(e.raw_value != null ? e.raw_value : (e.numeric_value != null ? e.numeric_value : ''))} ${GF.esc(e.unit || '')}</td>
      <td class="mono">${e.lower_limit != null || e.upper_limit != null ? GF.esc((e.lower_limit != null ? e.lower_limit : '') + '…' + (e.upper_limit != null ? e.upper_limit : '')) : '—'}</td>
      <td>${complyChip(e)}</td></tr>`).join('');
    const canExtract = doc.status !== 'PROMOTED' && doc.status !== 'REJECTED';
    const canPromote = (doc.status === 'EXTRACTED' || doc.status === 'REVIEWED') && !!doc.specification_id;
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Document', 'Документ')}</span><b class="mono">${GF.esc(doc.doc_number)}</b>
        <span>${AL('Batch', 'Серија')}</span><b>${GF.esc(doc.batch_id)}</b>
        <span>${AL('Source lab', 'Изворна лаб.')}</span><b>${GF.esc(doc.source_institution || '—')}</b>
        <span>${AL('Status', 'Статус')}</span><b>${dChip(doc.status)}</b>
        ${doc.material_code ? `<span>${AL('Material', 'Материјал')}</span><b>${GF.esc(doc.material_code)}</b>` : ''}
        ${doc.promoted_coa_id ? `<span>${AL('Certificate', 'Сертификат')}</span><b><a href="#" onclick="GF.setView&&GF.setView('qccoa');return false">${AL('promoted', 'промовиран')}</a></b>` : ''}
      </div>
      <table class="qcp-table" style="margin-top:10px"><thead><tr>
        <th>${AL('Field', 'Поле')}</th><th>${AL('Value', 'Вредност')}</th><th>${AL('Limits', 'Граници')}</th><th>${AL('Grade', 'Оцена')}</th></tr></thead>
        <tbody>${ex || `<tr><td colspan="4" class="ana-note">${AL('No fields transcribed yet', 'Сè уште нема пренесени полиња')}</td></tr>`}</tbody></table>
      ${canWrite() && canExtract ? `
      <div class="ana-panel" style="margin-top:10px;padding:10px">
        <div class="ana-pt" style="margin-bottom:6px">${AL('Transcribe fields (one per line: Label | value | unit)', 'Пренеси полиња (по еден ред: Ознака | вредност | единица)')}</div>
        <textarea id="qec-extract" rows="4" style="width:100%" placeholder="Total THC | 22.0 | %"></textarea>
        <button class="btn btn-sm btn-primary" style="margin-top:6px" onclick="GF.WWF.qcEcoaSubmitExtractions('${doc.id}')">${AL('Grade against spec', 'Оцени според спец.')}</button>
      </div>` : ''}
      ${canWrite() ? `<div class="qms-dl" style="margin-top:8px">
        ${doc.status === 'EXTRACTED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcEcoaAdvance('${doc.id}','REVIEWED')">${AL('Mark reviewed', 'Означи прегледано')}</button>` : ''}
        ${canPromote ? `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaPromote('${doc.id}')">${AL('Promote → certificate', 'Промовирај → сертификат')}</button>` : ''}
        ${(doc.status !== 'PROMOTED' && doc.status !== 'REJECTED') ? `<button class="btn btn-sm" onclick="GF.WWF.qcEcoaAdvance('${doc.id}','REJECTED')">${AL('Reject', 'Одбиј')}</button>` : ''}
      </div>` : ''}
      ${!doc.specification_id ? `<div class="ana-note" style="margin-top:6px">${AL('Attach a specification to grade & promote.', 'Прикачете спецификација за оценување и промоција.')}</div>` : ''}
      ${doc.status === 'PROMOTED' && doc.promoted_coa_id ? (() => {
        const v = GF.WWF._qcecoa.verify[doc.id];
        const vc = v ? (v.verdict === 'VERIFIED' ? 'var(--green)' : 'var(--red)') : null;
        return `<div class="qms-dl" style="margin-top:8px;align-items:center">
          ${canWrite() ? `<button class="btn btn-sm" onclick="GF.WWF.qcEcoaVerify('${doc.id}','${doc.promoted_coa_id}')">${AL('Verify vs source', 'Провери со извор')}</button>` : ''}
          ${v ? chip(AL(v.verdict === 'VERIFIED' ? 'Verified' : 'Discrepancy', v.verdict === 'VERIFIED' ? 'Потврдено' : 'Отстапување') + ' ' + (v.checked - v.mismatches) + '/' + v.checked, vc) : ''}
        </div>` +
        (v && v.mismatches ? `<div class="ana-note" style="margin-top:4px">${v.details.filter(d => !d.match).map(d => GF.esc((d.test_name || '') + ': ' + (d.reason || 'mismatch'))).join(' · ')}</div>` : '');
      })() : ''}
      ${(() => {
        const qa = GF.WWF._qcecoa.qa[doc.id];
        return `<div class="ana-panel" style="margin-top:10px;padding:10px">
          <div class="ana-pt" style="margin-bottom:6px">${AL('Ask the CoA (retrieval Q&A)', 'Прашај го CoA (пребарување)')}</div>
          ${canWrite() ? `<textarea id="qec-chunks-${doc.id}" rows="3" style="width:100%" placeholder="${AL('Paste CoA text — blank line separates passages, then Index', 'Залепете текст од CoA — празен ред дели пасуси, потоа Индексирај')}"></textarea>
          <button class="btn btn-sm" style="margin:6px 0" onclick="GF.WWF.qcEcoaIndexChunks('${doc.id}')">${AL('Index passages', 'Индексирај пасуси')}</button>` : ''}
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <input id="qec-q-${doc.id}" placeholder="${AL('Ask a question…', 'Постави прашање…')}" style="flex:1">
            <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaAsk('${doc.id}')">${AL('Ask', 'Прашај')}</button>
          </div>
          ${qa ? (qa.grounded
            ? `<div style="margin-top:8px">${qa.passages.map(p => `<div class="qms-row" style="flex-direction:column;align-items:flex-start;gap:2px"><span class="ana-note mono">[${GF.esc(p.doc_number)}#${GF.esc(String(p.chunk_index))}] · ${GF.esc(String(p.score))}</span><span>${GF.esc(p.content)}</span></div>`).join('')}</div>`
            : `<div class="ana-note" style="margin-top:8px">${AL('No matching passages — nothing to ground an answer on.', 'Нема совпаѓачки пасуси — нема на што да се заснова одговорот.')}</div>`) : ''}
        </div>`;
      })()}
    </div>`;
  };

  const docList = () => {
    const st = GF.WWF._qcecoa;
    const q = st.q.trim().toLowerCase();
    const rows = (st.docs || []).filter(d => !q
      || (d.doc_number || '').toLowerCase().includes(q)
      || (d.batch_id || '').toLowerCase().includes(q)
      || (d.source_institution || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(d => `
      <div class="qms-row ${st.sel === d.id ? 'on' : ''}" onclick="GF.WWF.qcEcoaPick('${d.id}')">
        <span class="mono qms-code">${GF.esc(d.doc_number)}</span>
        <span class="qms-title">${GF.esc(d.batch_id)} <span class="ana-note">${GF.esc(d.source_institution || '')}</span></span>
        ${dChip(d.status)}
      </div>
      ${st.sel === d.id ? (st.detail ? detail(st.detail) : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`) : ''}`).join('');
  };

  const queueList = () => {
    const st = GF.WWF._qcecoa;
    const rows = (st.ph || []);
    if (!rows.length) return `<div class="ana-note">${AL('No unmapped fields — the queue is clear.', 'Нема немапирани полиња — редот е чист.')}</div>`;
    const specOpts = (st.specs || []).map(s => `<option value="${s.id}">${GF.esc(s.spec_id + ' · ' + (s.material_code || ''))}</option>`).join('');
    return rows.map(p => {
      const params = st.mapParams[p.id];
      const paramSel = params
        ? `<select id="qec-ph-param-${p.id}"><option value="">${AL('parameter…', 'параметар…')}</option>${params.map(pp => `<option value="${pp.id}">${GF.esc(pp.test_name_en || pp.test_name_mk || pp.id)}</option>`).join('')}</select>
           <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaMapPlaceholder('${p.id}')">${AL('Map', 'Мапирај')}</button>`
        : '';
      return `<div class="qms-row" style="flex-wrap:wrap;gap:6px">
        <span class="qms-title">${GF.esc(p.raw_label)} <span class="ana-note">×${GF.esc(String(p.occurrences))}</span></span>
        ${canWrite() ? `<select onchange="GF.WWF.qcEcoaPickSpec('${p.id}', this.value)"><option value="">${AL('spec…', 'спец…')}</option>${specOpts}</select>${paramSel}
        <button class="btn btn-sm" onclick="GF.WWF.qcEcoaIgnorePlaceholder('${p.id}')">${AL('Ignore', 'Игнорирај')}</button>` : ''}
      </div>`;
    }).join('');
  };

  GF.views.qcecoa = () => {
    const st = GF.WWF._qcecoa;
    if (!st.docs && !st.loading && !st.error) GF.WWF.loadQcEcoa();
    const head = GF.viewHead('qc_ecoa', 'qc_ecoa_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — incoming CoA ingestion. Transcribed fields are graded against the material specification; unknown labels are queued for mapping; a reviewed document is promoted into a native certificate. The server never fabricates a value.',
      'QMS Студио — внес на дојдовни CoA. Пренесените полиња се оценуваат според спецификацијата; непознатите ознаки се редат за мапирање; прегледан документ се промовира во сертификат. Серверот никогаш не измислува вредност.')}</div>`;
    if (st.loading || (!st.docs && !st.error)) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQcEcoa()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const tabs = `<div class="qms-dl" style="margin-bottom:10px">
      <button class="btn btn-sm ${st.tab === 'docs' ? 'btn-primary' : ''}" onclick="GF.WWF.qcEcoaTab('docs')">${AL('Documents', 'Документи')}</button>
      <button class="btn btn-sm ${st.tab === 'queue' ? 'btn-primary' : ''}" onclick="GF.WWF.qcEcoaTab('queue')">${AL('Discovery queue', 'Ред за откривање')} (${(st.ph || []).length})</button>
    </div>`;
    if (st.tab === 'queue') {
      return head + zone + tabs + `<div class="panel ana-panel">${queueList()}</div>`;
    }
    const create = canWrite() ? `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div class="ana-pt" style="margin-bottom:8px">${AL('Register an incoming CoA', 'Регистрирај дојдовен CoA')}</div>
        <div class="qcs-form">
          <input id="qec-batch" placeholder="${AL('Batch id', 'Серија')}">
          <input id="qec-src" placeholder="${AL('Source lab', 'Изворна лаб.')}">
          <select id="qec-spec"><option value="">${AL('Specification…', 'Спецификација…')}</option>${(st.specs || []).map(s => `<option value="${s.id}">${GF.esc(s.spec_id + ' · ' + (s.material_code || ''))}</option>`).join('')}</select>
          <input id="qec-mat" placeholder="${AL('Material (optional)', 'Материјал (опц.)')}">
          <input id="qec-rd" type="date" title="${AL('Report date', 'Датум на извештај')}">
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaCreate()">${GF.t('create_task') || 'Create'}</button>
        </div>
      </div>` : '';
    return head + zone + tabs + create + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Documents', 'Документи')}</div>
          <input class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcEcoaFilter(this.value)">
          <select onchange="GF.WWF.qcEcoaStatus(this.value)">
            <option value="">${AL('All statuses', 'Сите статуси')}</option>
            ${Object.keys(DST).map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
        </div>
        <div class="qms-list">${docList()}</div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qcecoa', icon: 'file-input',
    label: () => AL('QC eCOA intake', 'КК eCOA внес'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
