/* qccustody-view.js — QC LIMS: custody cluster (Phase 2, unit 5).

   Field-to-lab traceability (ALCOA++). Three linked records reached through
   /qc: a Sampling Request (RQS, PP-QC-SOP-017 — a department asks QC to sample
   a material/batch; a 24-hour QC registration window is tracked), a Sample
   Field Record (SFR — the field operation: barrels, destination, transport
   times), and the chain of custody (every handoff of a sample). Read = elevated;
   write = QC_MGR / QP / execs / ADMIN. QMS Studio zone, anchored 'qms-end'. */

(function () {
  GF.WWF._qccus = { rqs: null, sfr: null, sel: null, detail: null, detailError: null, custody: {},
                    samples: null, pick: null, rqsAll: null,
                    q: '', status: '', tab: 'rqs', loading: false, error: null };

  const _WRITERS = ['ADMIN', 'OWNER', 'CEO', 'COO', 'QC_MGR', 'QP'];
  const canWrite = () => _WRITERS.includes((GF.API.user || {}).role);

  const RQS_ST = {
    OPEN:        { en: 'Open', mk: 'Отворено', c: 'var(--orange)' },
    REGISTERED:  { en: 'Registered', mk: 'Регистрирано', c: 'var(--blue)' },
    IN_PROGRESS: { en: 'In progress', mk: 'Во тек', c: 'var(--violet)' },
    COMPLETED:   { en: 'Completed', mk: 'Завршено', c: 'var(--green)' },
    CANCELLED:   { en: 'Cancelled', mk: 'Откажано', c: 'var(--ink-3)' },
  };
  const RQS_NEXT = { OPEN: 'REGISTERED', REGISTERED: 'IN_PROGRESS', IN_PROGRESS: 'COMPLETED' };
  const SFR_ST = {
    CREATED:   { en: 'Created', mk: 'Создадено', c: 'var(--ink-3)' },
    IN_FIELD:  { en: 'In field', mk: 'На терен', c: 'var(--blue)' },
    COMPLETED: { en: 'Completed', mk: 'Завршено', c: 'var(--green)' },
    CANCELLED: { en: 'Cancelled', mk: 'Откажано', c: 'var(--ink-3)' },
  };
  const SFR_NEXT = { CREATED: 'IN_FIELD', IN_FIELD: 'COMPLETED' };
  const XFER = ['FIELD_TO_LAB', 'LAB_INTERNAL', 'LAB_TO_DISPOSAL', 'STABILITY_TRANSFER'];
  // QCSOP 011 §6.1.4 vocabularies (mirror the backend enums)
  const RQS_TESTS = ['POTENCY', 'LOD', 'FM', 'MICRO', 'HEAVY_METALS', 'PESTICIDES', 'MYCOTOXINS', 'OTHER'];
  const RQS_MATERIAL_ST = ['QUARANTINE', 'IN_PROCESS', 'OTHER'];
  // The §6.1.4 fields that must be present before an RQS can be REGISTERED
  // (the completeness gate the backend enforces at §6.1.6).
  const RQS_MANDATORY = ['batch_id', 'num_samples', 'required_tests', 'storage_location', 'material_status', 'spec_reference'];
  const rqsIncomplete = (r) => RQS_MANDATORY.filter(m =>
    m === 'required_tests' ? !(r.required_tests && r.required_tests.length)
      : (r[m] === null || r[m] === undefined || r[m] === ''));

  const chip = (t, c) => `<span class="chip-opt" style="border-color:${c};color:${c}">${GF.esc(t)}</span>`;
  const stChip = (m, s) => { const x = m[s] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' }; return chip(AL(x.en, x.mk), x.c); };
  const dt = (s) => s ? GF.esc(String(s).slice(0, 16).replace('T', ' ')) : '—';

  GF.WWF.loadQcCustody = async () => {
    const st = GF.WWF._qccus;
    st.loading = true; st.error = null;
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      if (st.tab === 'sfr') {
        const sfr = await GF.API.qcSfr(st.status ? { status: st.status } : {});
        if (my !== st.lseq) return;
        st.sfr = sfr;
        // Open RQS feed the optional "from sampling request" picker on the
        // create form; a failure keeps the previous list (field stays optional).
        if (canWrite()) st.rqsAll = await GF.API.qcRqs({}).catch(() => st.rqsAll);
      } else {
        const rqs = await GF.API.qcRqs(st.status ? { status: st.status } : {});
        if (my !== st.lseq) return;
        st.rqs = rqs;
      }
    } catch (e) { if (my === st.lseq) st.error = e.message; }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'qccustody') GF.render.all();
  };
  GF.WWF.qcCusTab = (t) => { const st = GF.WWF._qccus; st.tab = t; st.sel = null; st.detail = null; st.detailError = null; st.status = ''; st.pick = null; GF.WWF.loadQcCustody(); };
  GF.WWF.qcCusFilter = (v) => { GF.WWF._qccus.q = v; GF.render.all(); GF.refocus('qcu-search'); };
  GF.WWF.qcCusStatus = async (v) => { GF.WWF._qccus.status = v; await GF.WWF.loadQcCustody(); GF.refocus('qcu-status'); };

  GF.WWF.qcCusPick = async (id) => {
    const st = GF.WWF._qccus;
    if (st.sel === id) { st.sel = null; st.detail = null; st.detailError = null; st.pick = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; st.detailError = null; st.pick = null; GF.render.all();
    try {
      const d = st.tab === 'sfr' ? await GF.API.qcSfrOne(id) : await GF.API.qcRqsOne(id);
      if (st.sel !== id) return;                  // another row was picked meanwhile
      st.detail = d;
      if (st.tab === 'sfr' && d.sample_id)
        st.custody[d.sample_id] = await GF.API.qcCustody(d.sample_id).catch(() => []);
    } catch (e) { if (st.sel === id) { st.detailError = e.message; GF.toast(e.message, 'error'); } }
    if (st.sel === id && GF.state.view === 'qccustody') GF.render.all();
  };
  // Retry after a failed detail fetch: clearing sel first lets pick() take the
  // select path again, so one click re-fetches the same row.
  GF.WWF.qcCusRetry = (id) => {
    const st = GF.WWF._qccus;
    st.sel = null; st.detail = null; st.detailError = null;
    GF.WWF.qcCusPick(id);
  };

  GF.WWF.qcRqsAdvance = async (id, target) => {
    const body = { status: target };
    if (target === 'CANCELLED') {
      // Escape/dismiss aborts the cancellation; an empty reason stays optional.
      const reason = prompt(AL('Cancellation reason (optional):', 'Причина за откажување (незадолжително):'));
      if (reason === null) return;
      if (reason.trim()) body.cancellation_reason = reason.trim();
    }
    try { await GF.API.qcPatchRqs(id, body); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.WWF._qccus.sel = null; GF.WWF._qccus.detail = null; await GF.WWF.loadQcCustody();
  };
  GF.WWF.qcSfrAdvance = async (id, target) => {
    try { await GF.API.qcPatchSfr(id, { status: target }); GF.toast(AL('Updated', 'Ажурирано')); }
    catch (e) { GF.toast(e.message, 'error'); }
    GF.WWF._qccus.sel = null; GF.WWF._qccus.detail = null; await GF.WWF.loadQcCustody();
  };
  // §6.2.3 / §6.3.2 — record the sampling equipment and the ambient/received
  // conditions on the field record.
  GF.WWF.qcSfrReceipt = async (id) => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const body = {};
    ['sampling_equipment', 'ambient_conditions', 'received_condition'].forEach(k => { const v = mk('qcu-r-' + k); if (v) body[k] = v; });
    if (!Object.keys(body).length) return GF.toast(AL('Nothing to save', 'Ништо за зачувување'));
    try { await GF.API.qcPatchSfr(id, body); GF.toast(AL('Saved', 'Зачувано')); }
    catch (e) { return GF.toast(e.message, 'error'); }
    const st = GF.WWF._qccus; st.sel = null; st.detail = null;
    await GF.WWF.loadQcCustody(); GF.WWF.qcCusPick(id);
  };
  GF.WWF.qcRqsCreate = async () => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const material_code = mk('qcu-mat'), originating_department = mk('qcu-dept');
    if (!material_code || !originating_department) return GF.toast(AL('Material and department are required', 'Потребни се материјал и оддел'), 'error');
    const body = { material_code, originating_department };
    ['material_name_en', 'material_name_mk', 'batch_id', 'assigned_sp_type',
     'priority_justification', 'storage_location', 'spec_reference'].forEach(k => { const v = mk('qcu-' + k); if (v) body[k] = v; });
    const ns = mk('qcu-num_samples'); if (ns) body.num_samples = parseInt(ns, 10);
    const pri = mk('qcu-priority'); if (pri) body.priority = pri;
    const mst = mk('qcu-material_status'); if (mst) body.material_status = mst;
    const relEl = document.getElementById('qcu-release_related'); if (relEl && relEl.checked) body.release_related = true;
    const tsel = document.getElementById('qcu-required_tests');
    if (tsel) { const t = Array.from(tsel.selectedOptions).map(o => o.value); if (t.length) body.required_tests = t; }
    try { const r = await GF.API.qcCreateRqs(body); GF.toast(r.rqs_number + ' ' + AL('opened', 'отворено')); await GF.WWF.loadQcCustody(); GF.WWF.qcCusPick(r.id); }
    catch (e) { GF.toast(e.message, 'error'); }
  };
  // Fill in the §6.1.4 mandatory fields on an OPEN draft before registration.
  GF.WWF.qcRqsEdit = async (id) => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const body = {};
    ['batch_id', 'storage_location', 'spec_reference'].forEach(k => { const v = mk('qcu-e-' + k); if (v) body[k] = v; });
    const ns = mk('qcu-e-num_samples'); if (ns) body.num_samples = parseInt(ns, 10);
    const mst = mk('qcu-e-material_status'); if (mst) body.material_status = mst;
    const pri = mk('qcu-e-priority'); if (pri) body.priority = pri;
    const pj = mk('qcu-e-priority_justification'); if (pj) body.priority_justification = pj;
    const tsel = document.getElementById('qcu-e-required_tests');
    if (tsel) { const t = Array.from(tsel.selectedOptions).map(o => o.value); if (t.length) body.required_tests = t; }
    if (!Object.keys(body).length) return GF.toast(AL('Nothing to save', 'Ништо за зачувување'));
    try { await GF.API.qcPatchRqs(id, body); GF.toast(AL('Saved', 'Зачувано')); }
    catch (e) { return GF.toast(e.message, 'error'); }
    const st = GF.WWF._qccus; st.sel = null; st.detail = null;
    await GF.WWF.loadQcCustody(); GF.WWF.qcCusPick(id);
  };
  GF.WWF.qcSfrCreate = async () => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const sampling_location = mk('qcu-loc'), destination_facility = mk('qcu-dest');
    const rqs = mk('qcu-rqs');
    if (!sampling_location || !destination_facility) return GF.toast(AL('Location and destination are required', 'Потребни се локација и дестинација'), 'error');
    // §6.1.1 — no sampling without a registered RQS: the link is required.
    if (!rqs) return GF.toast(AL('A registered sampling request is required (QCSOP 011 §6.1.1)', 'Потребно е регистрирано барање за мостри (QCSOP 011 §6.1.1)'), 'error');
    const body = { sampling_location, destination_facility, rqs_id: rqs };
    const coords = mk('qcu-coords'); if (coords) body.sampling_coordinates = coords;
    const nc = mk('qcu-nc'); if (nc) body.num_containers = parseInt(nc, 10) || null;
    const barrels = mk('qcu-barrels'); if (barrels) body.barrel_numbers = barrels.split(',').map(s => s.trim()).filter(Boolean);
    const equip = mk('qcu-equip'); if (equip) body.sampling_equipment = equip;
    try { const r = await GF.API.qcCreateSfr(body); GF.toast(r.sfr_number + ' ' + AL('created', 'создадено')); await GF.WWF.loadQcCustody(); GF.WWF.qcCusPick(r.id); }
    catch (e) { GF.toast(e.message, 'error'); }
  };
  GF.WWF.qcCusLogTransfer = async (sampleId) => {
    const mk = (i) => ((document.getElementById(i) || {}).value || '').trim();
    const body = { transfer_type: mk('qcu-xtype') || null, to_location: mk('qcu-xto') || null, transfer_reason: mk('qcu-xreason') || null };
    // §6.3.1 — the condition confirmed at the handoff.
    const cond = mk('qcu-xcond'); if (cond) body.sample_condition = cond;
    const okv = mk('qcu-xok'); if (okv) body.condition_ok = okv === 'yes';
    try { await GF.API.qcAddCustody(sampleId, body); GF.toast(AL('Transfer logged', 'Трансферот е запишан')); GF.WWF._qccus.custody[sampleId] = await GF.API.qcCustody(sampleId).catch(() => []); GF.render.all(); }
    catch (e) { GF.toast(e.message, 'error'); }
  };

  // ── Sample linking (shared by SFR + RQS details) ──
  // Linking a sample to an SFR is what unlocks the chain-of-custody panel;
  // on an RQS it records which registered sample the request produced.
  GF.WWF.qcCusPickerOpen = async (kind, id) => {
    const st = GF.WWF._qccus;
    st.pick = { kind, id };
    if (!st.samples) {
      GF.render.all();
      try { st.samples = await GF.API.qcSamples({}); }
      catch (e) { st.samples = null; st.pick = null; GF.toast(e.message, 'error'); }
    }
    if (GF.state.view === 'qccustody') GF.render.all();
  };
  GF.WWF.qcCusPickerClose = () => { GF.WWF._qccus.pick = null; GF.render.all(); };
  GF.WWF.qcCusLinkSample = async (kind, id) => {
    const sid = ((document.getElementById('qcu-linksample') || {}).value || '').trim();
    if (!sid) return GF.toast(AL('Pick a sample first', 'Прво изберете примерок'), 'error');
    try {
      if (kind === 'sfr') await GF.API.qcPatchSfr(id, { sample_id: sid });
      else await GF.API.qcPatchRqs(id, { sample_id: sid });
      GF.toast(AL('Sample linked', 'Примерокот е поврзан'));
    } catch (e) { return GF.toast(e.message, 'error'); }
    const st = GF.WWF._qccus;
    st.pick = null; st.sel = null; st.detail = null;
    await GF.WWF.loadQcCustody(); GF.WWF.qcCusPick(id);
  };
  GF.WWF.qcRqsAssign = async (id) => {
    const uid = ((document.getElementById('qcu-assignee') || {}).value || '').trim();
    if (!uid) return GF.toast(AL('Pick a person first', 'Прво изберете лице'), 'error');
    try { await GF.API.qcPatchRqs(id, { assigned_to_id: uid }); GF.toast(AL('Assigned', 'Доделено')); }
    catch (e) { return GF.toast(e.message, 'error'); }
    const st = GF.WWF._qccus;
    st.sel = null; st.detail = null;
    await GF.WWF.loadQcCustody(); GF.WWF.qcCusPick(id);
  };

  const fld = (id, ph) => `<input id="${id}" placeholder="${GF.esc(ph)}">`;

  // Human sample code if the samples list is cached, else a short UUID — never
  // an invented code.
  const sampleRef = (uuid) => {
    const s = (GF.WWF._qccus.samples || []).find(x => x.id === uuid);
    return GF.esc(s ? s.sample_id : (String(uuid).slice(0, 8) + '…'));
  };

  // Shared sample picker: collapsed → button; open → select of registered
  // samples + link/cancel. kind is 'sfr' | 'rqs' (which PATCH to send).
  const samplePicker = (kind, id) => {
    const st = GF.WWF._qccus;
    if (!st.pick || st.pick.kind !== kind || st.pick.id !== id)
      return `<button class="btn btn-sm" onclick="GF.WWF.qcCusPickerOpen('${kind}','${id}')">${AL('Link sample…', 'Поврзи примерок…')}</button>`;
    if (!st.samples) return `<span class="ana-note">${AL('Loading samples…', 'Се вчитуваат примероци…')}</span>`;
    if (!st.samples.length) return `<span class="ana-note">${AL('No samples registered yet', 'Сè уште нема примероци')}</span>
      <button class="btn btn-sm" onclick="GF.WWF.qcCusPickerClose()">${AL('Close', 'Затвори')}</button>`;
    return `<select id="qcu-linksample"><option value="">${AL('sample…', 'примерок…')}</option>${st.samples.map(s =>
        `<option value="${s.id}">${GF.esc(s.sample_id + ' — ' + (s.material_code || '') + (s.batch_id ? ' · ' + s.batch_id : ''))}</option>`).join('')}</select>
      <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcCusLinkSample('${kind}','${id}')">${AL('Link', 'Поврзи')}</button>
      <button class="btn btn-sm" onclick="GF.WWF.qcCusPickerClose()">${AL('Close', 'Затвори')}</button>`;
  };

  const PRI_LBL = { ROUTINE: { en: 'Routine', mk: 'Рутинско', c: 'var(--ink-3)' }, URGENT: { en: 'Urgent', mk: 'Итно', c: 'var(--red)' } };
  const rqsDetail = (r) => {
    const nxt = RQS_NEXT[r.status];
    const open = r.status !== 'COMPLETED' && r.status !== 'CANCELLED';
    const people = Object.keys(GF.PEOPLE || {}).filter(pid => !(GF.PEOPLE[pid] || {}).inactive);
    // §6.1.6 completeness gate — what still blocks registration (only relevant while OPEN).
    const missing = r.status === 'OPEN' ? rqsIncomplete(r) : [];
    const registerBlocked = nxt === 'REGISTERED' && missing.length;
    return `<div class="qms-detail"><div class="qms-dgrid">
      <span>${AL('RQS №', 'RQS №')}</span><b class="mono">${GF.esc(r.rqs_number)}</b>
      ${r.qc_control_number ? `<span>${AL('QC control №', 'КК контролен №')}</span><b class="mono">${GF.esc(r.qc_control_number)}</b>` : ''}
      <span>${AL('Material', 'Материјал')}</span><b>${GF.esc(r.material_code)}</b>
      <span>${AL('Department', 'Оддел')}</span><b>${GF.esc(r.originating_department)}</b>
      <span>${AL('Status', 'Статус')}</span><b>${stChip(RQS_ST, r.status)} ${r.priority === 'URGENT' ? stChip(PRI_LBL, r.priority) : ''}</b>
      ${r.batch_id ? `<span>${AL('Batch', 'Серија')}</span><b>${GF.esc(r.batch_id)}</b>` : ''}
      ${r.num_samples != null ? `<span>${AL('№ samples', 'Бр. мостри')}</span><b>${r.num_samples}</b>` : ''}
      ${(r.required_tests && r.required_tests.length) ? `<span>${AL('Required tests', 'Потребни тестови')}</span><b>${GF.esc(r.required_tests.join(', '))}</b>` : ''}
      ${r.material_status ? `<span>${AL('Material status', 'Статус на материјал')}</span><b>${GF.esc(r.material_status)}</b>` : ''}
      ${r.storage_location ? `<span>${AL('Storage', 'Складирање')}</span><b>${GF.esc(r.storage_location)}</b>` : ''}
      ${r.spec_reference ? `<span>${AL('Spec ref.', 'Спец. реф.')}</span><b>${GF.esc(r.spec_reference)}</b>` : ''}
      ${r.priority_justification ? `<span>${AL('Urgency reason', 'Причина за итност')}</span><b>${GF.esc(r.priority_justification)}</b>` : ''}
      ${r.release_related ? `<span>${AL('Release-related', 'Поврзано со ослободување')}</span><b>${chip(AL('yes — QP registers', 'да — QP регистрира'), 'var(--violet)')}</b>` : ''}
      <span>${AL('Reg. deadline', 'Рок за рег.')}</span><b class="mono">${dt(r.registration_deadline)}</b>
      ${r.registered_at ? `<span>${AL('Registered', 'Регистрирано')}</span><b class="mono">${dt(r.registered_at)} ${r.registration_window_met === false ? chip(AL('late', 'доцна'), 'var(--red)') : (r.registration_window_met ? chip(AL('on time', 'навреме'), 'var(--green)') : '')}</b>` : ''}
      ${r.assigned_to_id ? `<span>${AL('Assigned to', 'Доделено на')}</span><b>${GF.esc(((GF.PEOPLE || {})[r.assigned_to_id] || {}).name || r.assigned_to_id)}</b>` : ''}
      ${r.sample_id ? `<span>${AL('Sample', 'Примерок')}</span><b class="mono">${sampleRef(r.sample_id)}</b>` : ''}
      ${r.cancellation_reason ? `<span>${AL('Cancel reason', 'Причина за откажување')}</span><b>${GF.esc(r.cancellation_reason)}</b>` : ''}
    </div>${registerBlocked ? `<div class="ana-note" style="margin-top:8px;color:var(--orange)">${AL('Cannot register — QCSOP 011 §6.1.6 requires:', 'Не може да се регистрира — QCSOP 011 §6.1.6 бара:')} ${GF.esc(missing.join(', '))}</div>` : ''}${canWrite() && nxt ? `<div class="qms-dl" style="margin-top:8px">
      <button class="btn btn-sm btn-primary" ${registerBlocked ? 'disabled title="' + GF.esc(AL('Complete the §6.1.4 fields first', 'Прво пополнете ги полињата §6.1.4')) + '"' : ''} onclick="GF.WWF.qcRqsAdvance('${r.id}','${nxt}')">${AL('Advance to', 'Напредувај до')} ${GF.esc(AL((RQS_ST[nxt]||{}).en, (RQS_ST[nxt]||{}).mk))}</button>
      ${r.status !== 'COMPLETED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcRqsAdvance('${r.id}','CANCELLED')">${AL('Cancel', 'Откажи')}</button>` : ''}
    </div>` : ''}${canWrite() && open ? `<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;align-items:center">
      ${r.sample_id ? '' : samplePicker('rqs', r.id)}
      <select id="qcu-assignee"><option value="">${AL('assignee…', 'одговорен…')}</option>${people.map(pid =>
        `<option value="${pid}" ${r.assigned_to_id === pid ? 'selected' : ''}>${GF.esc(((GF.PEOPLE || {})[pid] || {}).name || pid)}</option>`).join('')}</select>
      <button class="btn btn-sm" onclick="GF.WWF.qcRqsAssign('${r.id}')">${AL('Assign', 'Додели')}</button>
    </div>` : ''}${canWrite() && r.status === 'OPEN' ? `<div class="ana-note" style="margin-top:6px">${AL('Complete the §6.1.4 fields:', 'Пополнете ги полињата §6.1.4:')}
      <div class="qcs-form" style="margin-top:4px">
        <input id="qcu-e-batch_id" placeholder="${AL('Batch', 'Серија')}" value="${GF.esc(r.batch_id || '')}">
        <input id="qcu-e-num_samples" type="number" min="0" placeholder="${AL('№ samples', 'Бр. мостри')}" value="${r.num_samples != null ? r.num_samples : ''}">
        <input id="qcu-e-storage_location" placeholder="${AL('Storage location', 'Локација за складирање')}" value="${GF.esc(r.storage_location || '')}">
        <input id="qcu-e-spec_reference" placeholder="${AL('Specification reference', 'Референца на спец.')}" value="${GF.esc(r.spec_reference || '')}">
        <select id="qcu-e-material_status"><option value="">${AL('material status…', 'статус на материјал…')}</option>${RQS_MATERIAL_ST.map(s => `<option value="${s}" ${r.material_status === s ? 'selected' : ''}>${s}</option>`).join('')}</select>
        <select id="qcu-e-priority"><option value="">${AL('priority…', 'приоритет…')}</option>${RQS_PRIORITIES_KV()}</select>
        <input id="qcu-e-priority_justification" placeholder="${AL('Urgency justification (if URGENT)', 'Оправдување за итност (ако е ИТНО)')}" value="${GF.esc(r.priority_justification || '')}">
        <select id="qcu-e-required_tests" multiple size="4" title="${AL('Ctrl/Cmd-click to pick multiple', 'Ctrl/Cmd-клик за повеќе')}">${RQS_TESTS.map(t => `<option value="${t}" ${(r.required_tests || []).includes(t) ? 'selected' : ''}>${t}</option>`).join('')}</select>
        <button class="btn btn-sm" onclick="GF.WWF.qcRqsEdit('${r.id}')">${AL('Save §6.1.4 fields', 'Зачувај §6.1.4 полиња')}</button>
      </div></div>` : ''}</div>`;
  };
  const RQS_PRIORITIES_KV = () => `<option value="ROUTINE">${AL('Routine', 'Рутинско')}</option><option value="URGENT">${AL('Urgent', 'Итно')}</option>`;

  const condChip = (ok) => ok === true ? chip(AL('intact', 'исправно'), 'var(--green)')
    : (ok === false ? chip(AL('compromised', 'нарушено'), 'var(--red)') : '');
  const custodyPanel = (sampleId) => {
    const rows = (GF.WWF._qccus.custody[sampleId] || []);
    const list = rows.map(x => `<tr><td class="mono">${dt(x.transferred_at)}</td><td>${GF.esc(x.transfer_type || '—')}</td><td>${GF.esc(x.to_location || '')}</td><td>${GF.esc(x.transfer_reason || '')}</td><td>${GF.esc(x.sample_condition || '')} ${condChip(x.condition_ok)}</td></tr>`).join('');
    return `<div style="margin-top:12px" class="ana-pt">${AL('Chain of custody', 'Ланец на чување')}</div>
      <table class="qcp-table"><thead><tr><th>${AL('When', 'Кога')}</th><th>${AL('Type', 'Тип')}</th><th>${AL('To', 'До')}</th><th>${AL('Reason', 'Причина')}</th><th>${AL('Condition', 'Состојба')}</th></tr></thead>
      <tbody>${list || `<tr><td colspan="5" class="ana-note">${AL('No custody transfers', 'Нема трансфери')}</td></tr>`}</tbody></table>
      ${canWrite() ? `<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;align-items:center">
        <select id="qcu-xtype"><option value="">${AL('type…', 'тип…')}</option>${XFER.map(t => `<option value="${t}">${t}</option>`).join('')}</select>
        <input id="qcu-xto" placeholder="${AL('to location', 'до локација')}"><input id="qcu-xreason" placeholder="${AL('reason', 'причина')}" style="flex:1">
        <input id="qcu-xcond" placeholder="${AL('condition at handoff', 'состојба при предавање')}">
        <select id="qcu-xok"><option value="">${AL('intact?', 'исправно?')}</option><option value="yes">${AL('intact', 'исправно')}</option><option value="no">${AL('compromised', 'нарушено')}</option></select>
        <button class="btn btn-sm" onclick="GF.WWF.qcCusLogTransfer('${sampleId}')">+ ${AL('Log transfer', 'Запиши трансфер')}</button>
      </div>` : ''}`;
  };

  const sfrDetail = (r) => {
    const nxt = SFR_NEXT[r.status];
    return `<div class="qms-detail"><div class="qms-dgrid">
      <span>${AL('SFR №', 'SFR №')}</span><b class="mono">${GF.esc(r.sfr_number)}</b>
      <span>${AL('Location', 'Локација')}</span><b>${GF.esc(r.sampling_location)}</b>
      <span>${AL('Destination', 'Дестинација')}</span><b>${GF.esc(r.destination_facility)}</b>
      <span>${AL('Status', 'Статус')}</span><b>${stChip(SFR_ST, r.status)}</b>
      ${(r.barrel_numbers && r.barrel_numbers.length) ? `<span>${AL('Barrels', 'Буриња')}</span><b>${GF.esc(r.barrel_numbers.join(', '))}</b>` : ''}
      ${r.num_containers != null ? `<span>${AL('Containers', 'Контејнери')}</span><b>${r.num_containers}</b>` : ''}
      ${r.sampling_equipment ? `<span>${AL('Equipment', 'Опрема')}</span><b>${GF.esc(r.sampling_equipment)}</b>` : ''}
      ${r.ambient_conditions ? `<span>${AL('Ambient cond.', 'Амбиентални усл.')}</span><b>${GF.esc(r.ambient_conditions)}</b>` : ''}
      ${r.received_condition ? `<span>${AL('Received cond.', 'Состојба при прием')}</span><b>${GF.esc(r.received_condition)}</b>` : ''}
      ${r.sample_id ? `<span>${AL('Sample', 'Примерок')}</span><b class="mono">${sampleRef(r.sample_id)}</b>` : ''}
    </div>${canWrite() && nxt ? `<div class="qms-dl" style="margin-top:8px">
      <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcSfrAdvance('${r.id}','${nxt}')">${AL('Advance to', 'Напредувај до')} ${GF.esc(AL((SFR_ST[nxt]||{}).en, (SFR_ST[nxt]||{}).mk))}</button>
      ${r.status !== 'COMPLETED' ? `<button class="btn btn-sm" onclick="GF.WWF.qcSfrAdvance('${r.id}','CANCELLED')">${AL('Cancel', 'Откажи')}</button>` : ''}
    </div>` : ''}${canWrite() && r.status !== 'CANCELLED' ? `<div class="ana-note" style="margin-top:6px">${AL('Equipment & receipt conditions (§6.2.3 / §6.3.2):', 'Опрема и услови при прием (§6.2.3 / §6.3.2):')}
      <div class="qcs-form" style="margin-top:4px">
        <input id="qcu-r-sampling_equipment" placeholder="${AL('Sampling equipment', 'Опрема за земање мостри')}" value="${GF.esc(r.sampling_equipment || '')}">
        <input id="qcu-r-ambient_conditions" placeholder="${AL('Ambient conditions', 'Амбиентални услови')}" value="${GF.esc(r.ambient_conditions || '')}">
        <input id="qcu-r-received_condition" placeholder="${AL('Condition at receipt', 'Состојба при прием')}" value="${GF.esc(r.received_condition || '')}">
        <button class="btn btn-sm" onclick="GF.WWF.qcSfrReceipt('${r.id}')">${AL('Save receipt', 'Зачувај прием')}</button>
      </div></div>` : ''}
    ${r.sample_id ? custodyPanel(r.sample_id) : `<div class="ana-note" style="margin-top:8px">${AL('Link a sample to record its chain of custody.', 'Поврзете примерок за да се води ланецот на чување.')}</div>
      ${canWrite() && r.status !== 'CANCELLED' ? `<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;align-items:center">${samplePicker('sfr', r.id)}</div>` : ''}`}</div>`;
  };

  // Failed detail fetch → error + one-click retry instead of a permanent skeleton.
  const failRow = (id) => `<div class="qms-detail" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <span style="color:var(--red-fg,var(--red))">${GF.esc(GF.WWF._qccus.detailError)}</span>
    <button class="btn btn-sm" onclick="GF.WWF.qcCusRetry('${id}')">${AL('Failed — retry', 'Неуспешно — обиди се повторно')}</button></div>`;

  const listRows = () => {
    const st = GF.WWF._qccus;
    const q = st.q.trim().toLowerCase();
    if (st.tab === 'sfr') {
      const rows = (st.sfr || []).filter(r => !q || (r.sfr_number || '').toLowerCase().includes(q) || (r.sampling_location || '').toLowerCase().includes(q));
      if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
      return rows.map(r => `<div class="qms-row ${st.sel === r.id ? 'on' : ''}" onclick="GF.WWF.qcCusPick('${r.id}')">
        <span class="mono qms-code">${GF.esc(r.sfr_number)}</span>
        <span class="qms-title">${GF.esc(r.sampling_location)} <span class="ana-note">→ ${GF.esc(r.destination_facility)}</span></span>
        ${stChip(SFR_ST, r.status)}</div>
        ${st.sel === r.id ? (st.detail ? sfrDetail(st.detail) : (st.detailError ? failRow(r.id)
          : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`)) : ''}`).join('');
    }
    const rows = (st.rqs || []).filter(r => !q || (r.rqs_number || '').toLowerCase().includes(q) || (r.material_code || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(r => `<div class="qms-row ${st.sel === r.id ? 'on' : ''}" onclick="GF.WWF.qcCusPick('${r.id}')">
      <span class="mono qms-code">${GF.esc(r.rqs_number)}</span>
      <span class="qms-title">${GF.esc(r.material_code)} <span class="ana-note">${GF.esc(r.originating_department)}</span></span>
      ${stChip(RQS_ST, r.status)}</div>
      ${st.sel === r.id ? (st.detail ? rqsDetail(st.detail) : (st.detailError ? failRow(r.id)
        : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`)) : ''}`).join('');
  };

  GF.views.qccustody = () => {
    const st = GF.WWF._qccus;
    if (!st.rqs && !st.sfr && !st.loading && !st.error) GF.WWF.loadQcCustody();
    const head = GF.viewHead('qc_custody', 'qc_custody_sub');
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — custody cluster: sampling requests (24-hour QC registration window), field sample records (barrels, destination, transport), and the ALCOA++ chain of custody per sample.',
      'QMS Студио — кластер за чување: барања за земање мостри (24-часовен прозорец за регистрација), теренски записи за мостри (буриња, дестинација, транспорт) и ALCOA++ ланец на чување по примерок.')}</div>`;
    const tabs = `<div class="qms-dl" style="margin-bottom:10px">
      <button class="btn btn-sm ${st.tab === 'rqs' ? 'btn-primary' : ''}" onclick="GF.WWF.qcCusTab('rqs')">${AL('Sampling requests', 'Барања за мостри')}</button>
      <button class="btn btn-sm ${st.tab === 'sfr' ? 'btn-primary' : ''}" onclick="GF.WWF.qcCusTab('sfr')">${AL('Field records', 'Теренски записи')}</button>
    </div>`;
    if (st.loading || (!st.rqs && !st.sfr && !st.error)) return head + zone + tabs + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    if (st.error) return head + zone + tabs + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap"><span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span><button class="btn btn-sm" onclick="GF.WWF.loadQcCustody()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    // §6.1.1 — a field record may only be raised against a REGISTERED (or
    // already in-progress) RQS. OPEN drafts and cancelled/completed ones are
    // excluded from the required picker.
    const rqsReg = (st.rqsAll || []).filter(x => x.status === 'REGISTERED' || x.status === 'IN_PROGRESS');
    const create = canWrite() ? (st.tab === 'sfr' ? `
      <div class="panel ana-panel" style="margin-bottom:12px"><div class="ana-pt" style="margin-bottom:8px">${AL('New field record', 'Нов теренски запис')}</div>
        ${rqsReg.length ? '' : `<div class="ana-note" style="margin-bottom:8px;color:var(--orange)">${AL('No registered sampling request available — register an RQS first (QCSOP 011 §6.1.1).', 'Нема регистрирано барање за мостри — прво регистрирајте RQS (QCSOP 011 §6.1.1).')}</div>`}
        <div class="qcs-form">
          <select id="qcu-rqs"><option value="">${AL('Registered sampling request (required)', 'Регистрирано барање за мостри (задолжително)')}</option>${rqsReg.map(x =>
            `<option value="${x.id}">${GF.esc(x.rqs_number + ' — ' + x.material_code + (x.qc_control_number ? ' · ' + x.qc_control_number : ''))}</option>`).join('')}</select>
          ${fld('qcu-loc', AL('Sampling location', 'Локација'))}${fld('qcu-dest', AL('Destination facility', 'Дестинација'))}
          ${fld('qcu-coords', AL('GPS (lat,long)', 'ГПС'))}${fld('qcu-barrels', AL('Barrels (comma-sep)', 'Буриња (запирки)'))}
          <input id="qcu-nc" type="number" min="0" placeholder="${AL('№ containers', 'Бр. контејнери')}">
          ${fld('qcu-equip', AL('Sampling equipment', 'Опрема за земање мостри'))}
          <button class="btn btn-sm btn-primary" ${rqsReg.length ? '' : 'disabled'} onclick="GF.WWF.qcSfrCreate()">${GF.t('create_task') || 'Create'}</button>
        </div></div>` : `
      <div class="panel ana-panel" style="margin-bottom:12px"><div class="ana-pt" style="margin-bottom:8px">${AL('New sampling request', 'Ново барање за мостри')}</div>
        <div class="qcs-form">
          ${fld('qcu-mat', AL('Material code', 'Код на материјал'))}${fld('qcu-dept', AL('Originating department', 'Оддел'))}
          ${fld('qcu-material_name_en', AL('Material (EN)', 'Материјал (EN)'))}${fld('qcu-material_name_mk', AL('Material (MK)', 'Материјал (MK)'))}
          ${fld('qcu-batch_id', AL('Batch', 'Серија'))}<input id="qcu-num_samples" type="number" min="0" placeholder="${AL('№ of samples', 'Бр. на мостри')}">
          ${fld('qcu-storage_location', AL('Storage location', 'Локација за складирање'))}${fld('qcu-spec_reference', AL('Specification reference', 'Референца на спец.'))}
          <select id="qcu-material_status"><option value="">${AL('material status…', 'статус на материјал…')}</option>${RQS_MATERIAL_ST.map(s => `<option value="${s}">${s}</option>`).join('')}</select>
          <select id="qcu-priority"><option value="">${AL('priority (routine)', 'приоритет (рутинско)')}</option>${RQS_PRIORITIES_KV()}</select>
          ${fld('qcu-priority_justification', AL('Urgency justification', 'Оправдување за итност'))}${fld('qcu-assigned_sp_type', AL('SP type (SP_01..)', 'СП тип'))}
          <select id="qcu-required_tests" multiple size="4" title="${AL('Ctrl/Cmd-click to pick multiple tests', 'Ctrl/Cmd-клик за повеќе тестови')}">${RQS_TESTS.map(t => `<option value="${t}">${t}</option>`).join('')}</select>
          <label class="ana-note" style="display:flex;align-items:center;gap:6px"><input id="qcu-release_related" type="checkbox">${AL('Release-related (QP registers)', 'Поврзано со ослободување (QP регистрира)')}</label>
          <button class="btn btn-sm btn-primary" onclick="GF.WWF.qcRqsCreate()">${GF.t('create_task') || 'Create'}</button>
        </div></div>`) : '';
    const statuses = st.tab === 'sfr' ? Object.keys(SFR_ST) : Object.keys(RQS_ST);
    return head + zone + tabs + create + `<div class="panel ana-panel">
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
        <div class="ana-pt" style="margin:0">${st.tab === 'sfr' ? AL('Field records', 'Теренски записи') : AL('Sampling requests', 'Барања за мостри')}</div>
        <input id="qcu-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}" oninput="GF.WWF.qcCusFilter(this.value)">
        <select id="qcu-status" onchange="GF.WWF.qcCusStatus(this.value)"><option value="">${AL('All statuses', 'Сите статуси')}</option>${statuses.map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}</select>
      </div>
      <div class="qms-list">${listRows()}</div></div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qccustody', icon: 'git-branch',
    label: () => AL('QC custody', 'КК чување'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
