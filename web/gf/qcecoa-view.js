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
  GF.WWF._qcecoa = { docs: null, sel: null, detail: null, detailError: null, ph: null,
                     specs: null, mapParams: {}, verify: {}, vhist: {}, qa: {},
                     chunks: {}, chunksOpen: {}, exParams: {}, editEx: null,
                     checklist: {},                 // QCT 018 review checklist per doc id
                     q: '', status: '', tab: 'docs',
                     loading: false, error: null };
  const _HOQC = ['ADMIN', 'QC_MGR', 'QP'];
  const canHoqc = () => _HOQC.includes((GF.API.user || {}).role);

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
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      const q = {}; if (st.status) q.status = st.status;
      const docs = await GF.API.qcCoaDocs(q);
      if (my !== st.lseq) return;
      st.docs = docs;
      st.ph = await GF.API.qcPlaceholders({ status: 'OPEN' }).catch(() => []);
      if (!st.specs) st.specs = await GF.API.qcSpecs({}).catch(() => []);
    } catch (e) { if (my === st.lseq) st.error = e.message; }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'qcecoa') GF.render.all();
  };

  GF.WWF.qcEcoaPick = async (id) => {
    const st = GF.WWF._qcecoa;
    if (st.sel === id) { st.sel = null; st.detail = null; st.detailError = null; st.editEx = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; st.detailError = null; st.editEx = null; GF.render.all();
    try {
      const [d, ch] = await Promise.all([
        GF.API.qcCoaDoc(id),
        GF.API.qcCoaChunks(id).catch(() => st.chunks[id] || [])]);
      if (st.sel === id) { st.detail = d; st.chunks[id] = ch; }
    } catch (e) { if (st.sel === id) { st.detailError = e.message; GF.toast(e.message, 'error'); } }
    if (st.sel === id && GF.state.view === 'qcecoa') GF.render.all();
  };
  // Retry after a failed detail fetch: clearing sel first lets pick() take the
  // select path again, so one click re-fetches the same row.
  GF.WWF.qcEcoaRetry = (id) => {
    const st = GF.WWF._qcecoa;
    st.sel = null; st.detail = null; st.detailError = null;
    GF.WWF.qcEcoaPick(id);
  };
  GF.WWF.qcEcoaFilter = (v) => { GF.WWF._qcecoa.q = v; GF.render.all(); GF.refocus('qec-search'); };
  GF.WWF.qcEcoaStatus = async (v) => { GF.WWF._qcecoa.status = v; await GF.WWF.loadQcEcoa(); GF.refocus('qec-status'); };
  GF.WWF.qcEcoaTab = (t) => { GF.WWF._qcecoa.tab = t; GF.render.all(); };

  const _reload = async (id) => {
    await GF.WWF.loadQcEcoa();
    if (GF.WWF._qcecoa.sel === id) { GF.WWF._qcecoa.detail = await GF.API.qcCoaDoc(id).catch(() => null); GF.render.all(); }
  };

  // A content edit resets an already-signed §6.3.2 checklist server-side (B2).
  // The panel caches the checklist per doc and only fetches when it is
  // undefined, so drop the cache — otherwise it keeps rendering the ACCEPTED
  // signature the server has just cleared.
  const _checklistInvalidated = (id, resp) => {
    if (!resp || !resp.checklist_reset) return;
    delete GF.WWF._qcecoa.checklist[id];
    GF.toast(AL('Review checklist reset to pending — the correction must be re-signed',
                'Листата за преглед е вратена на чекање — корекцијата мора повторно да се потпише'));
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

  // Parse a textarea of "Label | value | unit | lab verdict" lines into extraction items.
  GF.WWF.qcEcoaSubmitExtractions = async (id) => {
    const raw = ((document.getElementById('qec-extract') || {}).value || '').trim();
    if (!raw) return GF.toast(AL('Paste the CoA fields first', 'Прво залепете ги полињата'), 'error');
    const items = raw.split('\n').map(l => l.trim()).filter(Boolean).map(line => {
      const parts = line.split('|').map(p => p.trim());
      const it = { raw_label: parts[0] };
      if (parts[1]) { it.raw_value = parts[1]; const n = parseFloat(parts[1]); if (!isNaN(n)) it.numeric_value = n; }
      if (parts[2]) it.unit = parts[2];
      if (parts[3]) it.lab_verdict = parts[3];   // lab's stated verdict — reference only
      return it;
    }).filter(it => it.raw_label);
    if (!items.length) return;
    try {
      const r = await GF.API.qcSubmitExtractions(id, items);
      GF.toast(AL('Graded', 'Оценето') + ': ' + r.count + ' · ' + AL('unmapped', 'немапирани') + ' ' + r.unmapped);
      _checklistInvalidated(id, r);
    } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcEcoaAdvance = async (id, target) => {
    try { await GF.API.qcPatchCoaDoc(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  // Attach a specification to a doc registered without one — unblocks grade & promote.
  GF.WWF.qcEcoaAttachSpec = async (id) => {
    const specId = ((document.getElementById('qec-attach-spec-' + id) || {}).value || '');
    if (!specId) return GF.toast(AL('Pick a specification', 'Изберете спецификација'), 'error');
    try {
      await GF.API.qcPatchCoaDoc(id, { specification_id: specId });
      GF.toast(AL('Specification attached', 'Спецификацијата е прикачена'));
    } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  // Reviewer fix of one transcribed row (value / unit / parameter mapping).
  GF.WWF.qcEcoaEditEx = async (eid) => {
    const st = GF.WWF._qcecoa;
    if (st.editEx === eid) { st.editEx = null; GF.render.all(); return; }
    st.editEx = eid;
    const doc = (st.detail || {}).document;
    const specId = doc && doc.specification_id;
    if (specId && !st.exParams[specId]) {
      try { const s = await GF.API.qcSpec(specId); st.exParams[specId] = s.parameters || []; }
      catch (e) { st.exParams[specId] = []; }
    }
    GF.render.all();
  };
  GF.WWF.qcEcoaSaveEx = async (docId, eid) => {
    const gv = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const val = gv('qec-ex-val-' + eid);
    const unit = gv('qec-ex-unit-' + eid);
    const pid = gv('qec-ex-param-' + eid);
    const body = {};
    if (val === '') body.numeric_value = null;   // deliberately cleared → stays unmeasured
    else {
      const n = parseFloat(val);
      if (isNaN(n)) return GF.toast(AL('Value must be numeric', 'Вредноста мора да е бројчена'), 'error');
      body.numeric_value = n;
    }
    body.unit = unit || null;
    if (pid) body.parameter_id = pid;            // re-map → server re-grades
    try {
      const r = await GF.API.qcPatchExtraction(docId, eid, body);
      GF.WWF._qcecoa.editEx = null;
      GF.toast(AL('Updated', 'Ажурирано'));
      _checklistInvalidated(docId, r);
    } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(docId);
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
    const st = GF.WWF._qcecoa;
    try {
      const v = await GF.API.qcVerifyCert(coaId);
      st.verify[docId] = v;
      if (st.vhist[docId]) {   // history panel open — refresh it with the new run
        st.vhist[docId] = await GF.API.qcVerifications(coaId).catch(() => st.vhist[docId]);
      }
      GF.toast(v.verdict === 'VERIFIED'
        ? AL('Verified — matches source', 'Потврдено — се совпаѓа со изворот')
        : AL('Discrepancy: ', 'Отстапување: ') + v.mismatches + '/' + v.checked);
    } catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };
  // Audit trail: list the recorded verification runs for the promoted certificate.
  GF.WWF.qcEcoaVerifyHistory = async (docId, coaId) => {
    const st = GF.WWF._qcecoa;
    if (st.vhist[docId]) { delete st.vhist[docId]; GF.render.all(); return; }
    try { st.vhist[docId] = await GF.API.qcVerifications(coaId); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };

  // RAG Q&A over the ingested CoA text (P3-U4).
  GF.WWF.qcEcoaIndexChunks = async (docId) => {
    const raw = ((document.getElementById('qec-chunks-' + docId) || {}).value || '').trim();
    if (!raw) return GF.toast(AL('Paste the CoA text first', 'Прво залепете го текстот'), 'error');
    // split into chunks on blank lines
    const chunks = raw.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean);
    const st = GF.WWF._qcecoa;
    try {
      const r = await GF.API.qcIndexCoaChunks(docId, chunks);
      GF.toast(AL('Indexed', 'Индексирано') + ': ' + r.indexed);
      st.chunks[docId] = await GF.API.qcCoaChunks(docId).catch(() => st.chunks[docId] || []);
    } catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };
  // ── External CoA Review Checklist (QCT 018) — §6.3.2 ──
  GF.WWF.qcEcoaChecklistLoad = async (docId) => {
    const st = GF.WWF._qcecoa;
    try { st.checklist[docId] = await GF.API.qcChecklist(docId) || {}; }
    catch (e) { st.checklist[docId] = {}; }
    GF.render.all();
  };
  GF.WWF.qcEcoaChecklistSave = async (docId) => {
    const cb = (id) => !!(document.getElementById(id) || {}).checked;
    const body = {
      sample_id_match: cb('qec-cl-sid-' + docId),
      method_per_tqa: cb('qec-cl-mth-' + docId),
      units_per_spec: cb('qec-cl-uni-' + docId),
      conformance_by_pp: cb('qec-cl-cbp-' + docId),
      discrepancies: ((document.getElementById('qec-cl-dsc-' + docId) || {}).value || '').trim() || null,
    };
    try { GF.WWF._qcecoa.checklist[docId] = await GF.API.qcSaveChecklist(docId, body); GF.toast(AL('Checklist saved', 'Листата е зачувана')); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };
  GF.WWF.qcEcoaChecklistDecide = async (docId, outcome) => {
    if (outcome === 'REJECTED' && !confirm(AL('Reject this eCoA? It should then be voided and replaced by the contract lab.',
                                              'Одбиј го овој eCoA? Треба да се поништи и замени од договорната лабораторија.'))) return;
    try { GF.WWF._qcecoa.checklist[docId] = await GF.API.qcDecideChecklist(docId, { outcome }); GF.toast(AL('Recorded', 'Запишано')); }
    catch (e) { return GF.toast(e.message, 'error'); }
    GF.render.all();
  };
  GF.WWF.qcEcoaToggleChunks = async (docId) => {
    const st = GF.WWF._qcecoa;
    st.chunksOpen[docId] = !st.chunksOpen[docId];
    if (st.chunksOpen[docId] && st.chunks[docId] == null) {
      try { st.chunks[docId] = await GF.API.qcCoaChunks(docId); }
      catch (e) { st.chunks[docId] = []; }
    }
    GF.render.all();
  };
  GF.WWF.qcEcoaAsk = async (docId) => {
    const question = ((document.getElementById('qec-q-' + docId) || {}).value || '').trim();
    if (!question) return;
    try { GF.WWF._qcecoa.qa[docId] = await GF.API.qcCoaQa({ question, document_id: docId }); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.render.all();
  };
  // Source-document custody (item 12): store the original PDF with a SHA-256.
  GF.WWF.qcEcoaUploadOriginal = async (docId, inputEl) => {
    const file = inputEl && inputEl.files && inputEl.files[0];
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) { inputEl.value = ''; return GF.toast(AL('File exceeds 20 MB', 'Датотеката надминува 20 MB'), 'error'); }
    try {
      const b64 = await new Promise((res, rej) => {
        const fr = new FileReader();
        fr.onload = () => res(String(fr.result).split(',', 2)[1] || '');
        fr.onerror = () => rej(new Error('read failed'));
        fr.readAsDataURL(file);
      });
      await GF.API.qcUploadOriginal(docId, { filename: file.name, content_type: file.type || null, content_b64: b64 });
      GF.toast(AL('Original stored', 'Оригиналот е зачуван'));
      if (GF.WWF._qcecoa.sel === docId) GF.WWF._qcecoa.detail = await GF.API.qcCoaDoc(docId).catch(() => null);
      GF.render.all();
    } catch (e) { GF.toast(e.status === 413 ? AL('File too large', 'Датотеката е преголема') : e.message, 'error'); }
    finally { if (inputEl) inputEl.value = ''; }
  };
  GF.WWF.qcEcoaDlOriginal = async (fileId, filename) => {
    try {
      const res = await fetch(GF.API.qcOriginalDlUrl(fileId), { headers: { Authorization: 'Bearer ' + GF.API.token } });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      if (res.headers.get('X-Integrity') === 'MISMATCH') GF.toast(AL('⚠ Integrity check failed — stored bytes changed', '⚠ Проверката на интегритет не успеа'), 'error');
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = filename || 'original';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } catch (e) { GF.toast(e.message, 'error'); }
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

  // §6.3.2 External CoA Review Checklist (QCT 018) panel. Lazily loads once per
  // doc; the HoQC signs ACCEPTED/REJECTED which locks it.
  const checklistPanel = (doc) => {
    const st = GF.WWF._qcecoa;
    const cl = st.checklist[doc.id];
    if (cl === undefined) { GF.WWF.qcEcoaChecklistLoad(doc.id); return `<div class="ana-note" style="margin-top:8px">${AL('Loading review checklist…', 'Се вчитува листата…')}</div>`; }
    const decided = cl && cl.outcome && cl.outcome !== 'PENDING';
    const chk = (id, k, label) =>
      `<label style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="${id}" ${cl && cl[k] ? 'checked' : ''} ${decided ? 'disabled' : ''}>${label}</label>`;
    return `<div class="ana-panel" style="margin-top:10px;padding:10px">
      <div class="ana-pt" style="margin-bottom:6px">${AL('External CoA review checklist (QCT 018 · §6.3.2)', 'Листа за преглед на надворешен CoA (QCT 018 · §6.3.2)')}
        ${decided ? `<span class="chip-opt" style="border-color:${cl.outcome === 'ACCEPTED' ? 'var(--green)' : 'var(--red)'};color:${cl.outcome === 'ACCEPTED' ? 'var(--green)' : 'var(--red)'}">${GF.esc(cl.outcome)}</span>` : ''}</div>
      <div style="display:flex;flex-direction:column;gap:4px">
        ${chk('qec-cl-sid-' + doc.id, 'sample_id_match', AL('Sample ID matches the PP submission record', 'ИД на примерок се совпаѓа со записот на ПП'))}
        ${chk('qec-cl-mth-' + doc.id, 'method_per_tqa', AL('Each parameter uses the method agreed in the TQA', 'Секој параметар го користи договорениот метод (TQA)'))}
        ${chk('qec-cl-uni-' + doc.id, 'units_per_spec', AL('Results expressed in the PP specification units', 'Резултатите се во единиците од спец. на ПП'))}
        ${chk('qec-cl-cbp-' + doc.id, 'conformance_by_pp', AL('Conformance determined by Purely Plant (not taken from the eCoA)', 'Усогласеноста ја утврди Пјурели Плант (не од eCoA)'))}
        <input id="qec-cl-dsc-${doc.id}" placeholder="${AL('Discrepancies / flags (resolve before accepting)', 'Несовпаѓања / знаменца (реши пред прифаќање)')}" value="${GF.esc((cl && cl.discrepancies) || '')}" ${decided ? 'disabled' : ''}>
      </div>
      ${!decided ? `<div class="qms-dl" style="margin-top:8px">
        ${canWrite() ? `<button class="btn btn-sm" onclick="GF.WWF.qcEcoaChecklistSave('${doc.id}')">${AL('Save checklist', 'Зачувај листа')}</button>` : ''}
        ${canHoqc() ? `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaChecklistDecide('${doc.id}','ACCEPTED')">${AL('Accept (sign)', 'Прифати (потпиши)')}</button>
          <button class="btn btn-sm" onclick="GF.WWF.qcEcoaChecklistDecide('${doc.id}','REJECTED')">${AL('Reject', 'Одбиј')}</button>` : ''}
      </div>` : `<div class="ana-note" style="margin-top:6px">${AL('Signed & locked', 'Потпишано и заклучено')}${cl.reviewed_at ? ' · ' + GF.esc(String(cl.reviewed_at).slice(0, 10)) : ''}</div>`}
    </div>`;
  };

  const detail = (d) => {
    const st = GF.WWF._qcecoa;
    const doc = d.document;
    const exParams = doc.specification_id ? (st.exParams[doc.specification_id] || []) : [];
    const ex = (d.extractions || []).map(e => {
      const row = `
      <tr><td>${GF.esc(e.raw_label)}${e.test_name && e.test_name !== e.raw_label ? ` <span class="ana-note">→ ${GF.esc(e.test_name)}</span>` : ''}</td>
      <td class="mono">${GF.esc(e.numeric_value != null ? e.numeric_value : (e.raw_value != null ? e.raw_value : ''))} ${GF.esc(e.unit || '')}</td>
      <td class="mono">${e.lower_limit != null || e.upper_limit != null ? GF.esc((e.lower_limit != null ? e.lower_limit : '') + '…' + (e.upper_limit != null ? e.upper_limit : '')) : '—'}</td>
      <td>${complyChip(e)}${e.lab_verdict ? ` <span class="ana-note"${e.lab_verdict_mismatch ? ' style="color:var(--red);font-weight:600"' : ''}>${AL('lab', 'лаб')}: ${GF.esc(e.lab_verdict)}${e.lab_verdict_mismatch ? ' ⚠ ' + AL('disagrees', 'несогласување') : ''}</span>` : ''}${canWrite() ? ` <button class="btn btn-sm" onclick="GF.WWF.qcEcoaEditEx('${e.id}')">${st.editEx === e.id ? AL('Cancel', 'Откажи') : AL('Edit', 'Уреди')}</button>` : ''}</td></tr>`;
      if (!canWrite() || st.editEx !== e.id) return row;
      return row + `
      <tr><td colspan="4"><div class="qms-dl" style="align-items:center;flex-wrap:wrap">
        <input id="qec-ex-val-${e.id}" value="${GF.esc(e.numeric_value != null ? e.numeric_value : '')}" placeholder="${AL('Value', 'Вредност')}" style="width:100px">
        <input id="qec-ex-unit-${e.id}" value="${GF.esc(e.unit || '')}" placeholder="${AL('Unit', 'Единица')}" style="width:80px">
        <select id="qec-ex-param-${e.id}">
          <option value="">${AL('Keep parameter', 'Задржи параметар')}</option>
          ${exParams.map(pp => `<option value="${pp.id}">${GF.esc(pp.test_name_en || pp.test_name_mk || pp.id)}</option>`).join('')}
        </select>
        <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaSaveEx('${doc.id}','${e.id}')">${AL('Save', 'Зачувај')}</button>
      </div></td></tr>`;
    }).join('');
    const canExtract = doc.status !== 'PROMOTED' && doc.status !== 'REJECTED';
    const canPromote = (doc.status === 'EXTRACTED' || doc.status === 'REVIEWED') && !!doc.specification_id;
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Document', 'Документ')}</span><b class="mono">${GF.esc(doc.doc_number)}</b>
        <span>${AL('Batch', 'Серија')}</span><b>${GF.esc(doc.batch_id)}</b>
        <span>${AL('Source lab', 'Изворна лаб.')}</span><b>${GF.esc(doc.source_institution || '—')}</b>
        <span>${AL('Status', 'Статус')}</span><b>${dChip(doc.status)}</b>
        ${doc.material_code ? `<span>${AL('Material', 'Материјал')}</span><b>${GF.esc(doc.material_code)}</b>` : ''}
        ${doc.review_deadline ? `<span>${AL('Review by', 'Прегледај до')}</span><b class="mono">${GF.esc(doc.review_deadline)}${
            doc.review_overdue ? ` <span class="chip-opt" style="border-color:var(--red);color:var(--red)">${AL('overdue', 'задоцнето')}</span>`
            : doc.review_window_met === true ? ` <span class="chip-opt" style="border-color:var(--green);color:var(--green)">${AL('in window', 'во рок')}</span>`
            : doc.review_window_met === false ? ` <span class="chip-opt" style="border-color:var(--amber);color:var(--amber)">${AL('late', 'доцна')}</span>` : ''}</b>` : ''}
        ${doc.promoted_coa_id ? `<span>${AL('Certificate', 'Сертификат')}</span><b><a href="#" onclick="GF.setView&&GF.setView('qccoa');return false">${AL('promoted', 'промовиран')}</a></b>` : ''}
      </div>
      <table class="qcp-table" style="margin-top:10px"><thead><tr>
        <th>${AL('Field', 'Поле')}</th><th>${AL('Value', 'Вредност')}</th><th>${AL('Limits', 'Граници')}</th><th>${AL('Grade', 'Оцена')}</th></tr></thead>
        <tbody>${ex || `<tr><td colspan="4" class="ana-note">${AL('No fields transcribed yet', 'Сè уште нема пренесени полиња')}</td></tr>`}</tbody></table>
      ${canWrite() && canExtract ? `
      <div class="ana-panel" style="margin-top:10px;padding:10px">
        <div class="ana-pt" style="margin-bottom:6px">${AL('Transcribe fields (one per line: Label | value | unit | lab verdict)', 'Пренеси полиња (по еден ред: Ознака | вредност | единица | лаб. заклучок)')}</div>
        <textarea id="qec-extract" rows="4" style="width:100%" placeholder="Total THC | 22.0 | % | Pass"></textarea>
        <button class="btn btn-sm btn-primary" style="margin-top:6px" onclick="GF.WWF.qcEcoaSubmitExtractions('${doc.id}')">${AL('Grade against spec', 'Оцени според спец.')}</button>
      </div>` : ''}
      ${canWrite() ? `<div class="qms-dl" style="margin-top:8px">
        ${doc.status === 'EXTRACTED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcEcoaAdvance('${doc.id}','REVIEWED')">${AL('Mark reviewed', 'Означи прегледано')}</button>` : ''}
        ${canPromote ? `<button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaPromote('${doc.id}')">${AL('Promote → certificate', 'Промовирај → сертификат')}</button>` : ''}
        ${(doc.status !== 'PROMOTED' && doc.status !== 'REJECTED') ? `<button class="btn btn-sm" onclick="GF.WWF.qcEcoaAdvance('${doc.id}','REJECTED')">${AL('Reject', 'Одбиј')}</button>` : ''}
      </div>` : ''}
      ${doc.status !== 'REJECTED' ? checklistPanel(doc) : ''}
      ${!doc.specification_id ? `<div class="ana-note" style="margin-top:6px">${AL('Attach a specification to grade & promote.', 'Прикачете спецификација за оценување и промоција.')}</div>
      ${canWrite() ? `<div class="qms-dl" style="margin-top:6px;align-items:center">
        <select id="qec-attach-spec-${doc.id}"><option value="">${AL('Specification…', 'Спецификација…')}</option>${(st.specs || []).map(s => `<option value="${s.id}">${GF.esc(s.spec_id + ' · ' + (s.material_code || ''))}</option>`).join('')}</select>
        <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaAttachSpec('${doc.id}')">${AL('Attach', 'Прикачи')}</button>
      </div>` : ''}` : ''}
      ${doc.status === 'PROMOTED' && doc.promoted_coa_id ? (() => {
        const v = st.verify[doc.id];
        const vc = v ? (v.verdict === 'VERIFIED' ? 'var(--green)' : 'var(--red)') : null;
        const h = st.vhist[doc.id];
        return `<div class="qms-dl" style="margin-top:8px;align-items:center">
          ${canWrite() ? `<button class="btn btn-sm" onclick="GF.WWF.qcEcoaVerify('${doc.id}','${doc.promoted_coa_id}')">${AL('Verify vs source', 'Провери со извор')}</button>` : ''}
          <button class="btn btn-sm" onclick="GF.WWF.qcEcoaVerifyHistory('${doc.id}','${doc.promoted_coa_id}')">${h ? AL('Hide history', 'Скриј историја') : AL('History', 'Историја')}</button>
          ${v ? chip(AL(v.verdict === 'VERIFIED' ? 'Verified' : 'Discrepancy', v.verdict === 'VERIFIED' ? 'Потврдено' : 'Отстапување') + ' ' + (v.checked - v.mismatches) + '/' + v.checked, vc) : ''}
        </div>` +
        (v && v.mismatches ? `<div class="ana-note" style="margin-top:4px">${v.details.filter(d => !d.match).map(d => GF.esc((d.test_name || '') + ': ' + (d.reason || 'mismatch'))).join(' · ')}</div>` : '') +
        (h ? (h.length ? `<div style="margin-top:6px">${h.map(r => {
          const ok = r.verdict === 'VERIFIED';
          return `<div class="qms-row" style="gap:8px">
            ${chip(AL(ok ? 'Verified' : 'Discrepancy', ok ? 'Потврдено' : 'Отстапување'), ok ? 'var(--green)' : 'var(--red)')}
            <span class="ana-note mono">${GF.esc((r.verified_at || '').replace('T', ' ').slice(0, 16))}</span>
            <span class="ana-note">${GF.esc(String(r.mismatches)) + '/' + GF.esc(String(r.checked))} ${AL('mismatches', 'отстапувања')}</span>
          </div>`;
        }).join('')}</div>`
        : `<div class="ana-note" style="margin-top:4px">${AL('No verification runs recorded yet.', 'Сè уште нема запишани проверки.')}</div>`) : '');
      })() : ''}
      ${(() => {
        const qa = st.qa[doc.id];
        const ch = st.chunks[doc.id];
        const chOpen = !!st.chunksOpen[doc.id];
        return `<div class="ana-panel" style="margin-top:10px;padding:10px">
          <div class="ana-pt" style="margin-bottom:6px">${AL('Ask the CoA (retrieval Q&A)', 'Прашај го CoA (пребарување)')}</div>
          ${canWrite() ? `<textarea id="qec-chunks-${doc.id}" rows="3" style="width:100%" placeholder="${AL('Paste CoA text — blank line separates passages, then Index', 'Залепете текст од CoA — празен ред дели пасуси, потоа Индексирај')}"></textarea>
          <button class="btn btn-sm" style="margin:6px 0" onclick="GF.WWF.qcEcoaIndexChunks('${doc.id}')">${AL('Index passages', 'Индексирај пасуси')}</button>` : ''}
          <div style="margin:6px 0">
            <button class="btn btn-sm" onclick="GF.WWF.qcEcoaToggleChunks('${doc.id}')">${AL('Indexed passages', 'Индексирани пасуси')}${ch ? ' (' + ch.length + ')' : ''} ${chOpen ? AL('— hide', '— скриј') : AL('— show', '— прикажи')}</button>
            ${chOpen ? (ch && ch.length
              ? `<div style="margin-top:6px">${ch.map(c => `<div class="qms-row" style="gap:6px"><span class="ana-note mono">#${GF.esc(String(c.chunk_index))}</span><span class="ana-note">${GF.esc((c.content || '').slice(0, 120))}${(c.content || '').length > 120 ? '…' : ''}</span></div>`).join('')}</div>`
              : `<div class="ana-note" style="margin-top:6px">${AL('No passages indexed yet.', 'Сè уште нема индексирани пасуси.')}</div>`) : ''}
          </div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <input id="qec-q-${doc.id}" placeholder="${AL('Ask a question…', 'Постави прашање…')}" style="flex:1">
            <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcEcoaAsk('${doc.id}')">${AL('Ask', 'Прашај')}</button>
          </div>
          ${qa ? (qa.grounded
            ? `<div style="margin-top:8px">${qa.passages.map(p => `<div class="qms-row" style="flex-direction:column;align-items:flex-start;gap:2px"><span class="ana-note mono">[${GF.esc(p.doc_number)}#${GF.esc(String(p.chunk_index))}] · ${GF.esc(String(p.score))}</span><span>${GF.esc(p.content)}</span></div>`).join('')}</div>`
            : `<div class="ana-note" style="margin-top:8px">${AL('No matching passages — nothing to ground an answer on.', 'Нема совпаѓачки пасуси — нема на што да се заснова одговорот.')}</div>`) : ''}
        </div>`;
      })()}
      ${(() => {
        const files = d.originals || [];
        const rows = files.map(f => `<div class="qms-row" style="gap:8px;align-items:center">
          <span class="qms-title">${GF.esc(f.filename)} <span class="ana-note">${GF.esc(String(Math.round((f.size_bytes || 0) / 1024)))} KB</span></span>
          <span class="ana-note mono" title="SHA-256">${GF.esc((f.sha256 || '').slice(0, 12))}…</span>
          <button class="btn btn-sm" onclick="GF.WWF.qcEcoaDlOriginal('${f.id}','${GF.esc((f.filename || 'original').replace(/'/g, ''))}')">${AL('Download', 'Преземи')}</button>
        </div>`).join('');
        return `<div class="ana-panel" style="margin-top:10px;padding:10px">
          <div class="ana-pt" style="margin-bottom:6px">${AL('Original documents (SHA-256 custody)', 'Оригинални документи (SHA-256 старателство)')}</div>
          ${rows || `<div class="ana-note">${AL('No original stored — attach the source PDF for the record.', 'Нема зачуван оригинал — прикачете го изворниот PDF за евиденција.')}</div>`}
          ${canWrite() ? `<div style="margin-top:6px"><input type="file" id="qec-orig-${doc.id}" onchange="GF.WWF.qcEcoaUploadOriginal('${doc.id}', this)"></div>` : ''}
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
        ${d.review_overdue ? `<span class="chip-opt" style="border-color:var(--red);color:var(--red)">${AL('review overdue', 'преглед задоцнет')}</span>` : ''}
        ${dChip(d.status)}
      </div>
      ${st.sel === d.id ? (st.detail ? detail(st.detail) : (st.detailError
        ? `<div class="qms-detail" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
             <span style="color:var(--red-fg,var(--red))">${GF.esc(st.detailError)}</span>
             <button class="btn btn-sm" onclick="GF.WWF.qcEcoaRetry('${d.id}')">${AL('Failed — retry', 'Неуспешно — обиди се повторно')}</button></div>`
        : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`)) : ''}`).join('');
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
          <input id="qec-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcEcoaFilter(this.value)">
          <select id="qec-status" onchange="GF.WWF.qcEcoaStatus(this.value)">
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
