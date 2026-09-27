/* qcpotency-view.js — QC LIMS: the product catalogue (QCSP 001).

   The official potency specification is per PRODUCT: one strain at one nominal
   Total Δ9-THC with the window its page prints (owner 2026-09-05; the fitted
   windows of 2026-09-18 replace the flat ±10 % pages). This view is the human
   half of qc_products: list the catalogue by cultivar, import it (the ImB
   pages, or the fitted specifications exported by the Potency Spec Service —
   dry run first, then for real), approve a DRAFT product as a second person
   (the backend refuses the author), supersede, read what a product has tested
   so far, ask which product a measured value belongs to, and open the A4 page.

   The per-cultivar ladders of August 2026 are retired: they stay readable,
   collapsed at the bottom, for certificates issued against them; nothing here
   authors, approves or imports one once a product exists (the backend refuses
   too). Same full-page-view + qms-zone pattern as qcspec-view; QMS Studio zone.

   No data travels inside an inline handler: every control carries
   data-qcp-act / data-id attributes and one delegated listener dispatches. */

(function () {
  GF.WWF._qcpot = { products: null, ladders: null, sel: null, detail: null, detailError: null,
                    ladderSel: null, ladderDetail: null,
                    q: '', status: '', cultivar: '', loading: false, error: null,
                    importing: false, imbPreview: null, fittedPreview: null, fittedText: '',
                    fittedVersion: '', conf: null, confValue: '' };

  // Shared QC/LIMS role gates (core.js GF.QC_HOQC / GF.QC_WRITERS).
  const canApprove = () => GF.QC_HOQC.includes((GF.API.user || {}).role);

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
  const n2 = (v) => (v === null || v === undefined ? '—' : Number(v).toFixed(2));
  const win = (p) => `${n2(p.window_min)} – ${n2(p.window_max)} %`;
  const tol = (p) => (p.nominal_pct != null && p.window_min != null
    ? ` ± ${n2(Number(p.nominal_pct) - Number(p.window_min))} %` : '');
  const btn = (act, id, label, cls = 'btn btn-sm', extra = '') =>
    `<button class="${cls}" data-qcp-act="${act}"${id ? ` data-id="${GF.esc(id)}"` : ''}${extra}>${label}</button>`;

  // ── loading ────────────────────────────────────────────────────────────
  GF.WWF.loadQcPotency = async () => {
    const st = GF.WWF._qcpot;
    st.loading = true; st.error = null;
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      const q = {};
      if (st.status) q.status = st.status;
      const [products, ladders] = await Promise.all([
        GF.API.qcProducts(q),
        GF.API.qcPotencySpecs({}).catch(() => []),
      ]);
      if (my !== st.lseq) return;
      st.products = products; st.ladders = ladders;
    } catch (e) { if (my === st.lseq) st.error = e.message; }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'qcpotency') GF.render.all();
  };

  GF.WWF.qcPotPick = async (id) => {
    const st = GF.WWF._qcpot;
    if (st.sel === id) { st.sel = null; st.detail = null; st.detailError = null; st.conf = null; GF.render.all(); return; }
    st.sel = id; st.detail = null; st.detailError = null; st.conf = null; GF.render.all();
    try { const d = await GF.API.qcProduct(id); if (st.sel === id) st.detail = d; }
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
  GF.WWF.qcPotStatus = async (v) => { GF.WWF._qcpot.status = v; await GF.WWF.loadQcPotency(); GF.refocus('qcp-status'); };
  GF.WWF.qcPotCultivar = (v) => { GF.WWF._qcpot.cultivar = v; GF.render.all(); GF.refocus('qcp-cultivar'); };

  const _reload = async (id) => {
    await GF.WWF.loadQcPotency();
    if (GF.WWF._qcpot.sel === id) {
      GF.WWF._qcpot.detail = await GF.API.qcProduct(id).catch(() => null);
      GF.render.all();
    }
  };

  // ── approve / supersede (HoQC, second person) ──────────────────────────
  GF.WWF.qcPotApprove = async (id) => {
    try {
      const p = await GF.API.qcApproveProduct(id);
      GF.toast(AL(`${p.product_code} approved — it now grades certificates`,
                  `${p.product_code} е одобрен — сега ги оценува сертификатите`));
    } catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };
  GF.WWF.qcPotSupersede = async (id) => {
    try { await GF.API.qcSupersedeProduct(id); GF.toast(AL('Product superseded', 'Производот е заменет')); }
    catch (e) { GF.toast(e.message, 'error'); }
    await _reload(id);
  };

  // ── imports: dry run first, then for real ──────────────────────────────
  GF.WWF.qcPotImport = async (dryRun) => {
    const st = GF.WWF._qcpot;
    st.importing = true; GF.render.all();
    try {
      const r = await GF.API.qcImportProducts({ dry_run: !!dryRun });
      st.imbPreview = r;
      if (!dryRun) {
        GF.toast(AL(`Imported ${r.created.length} product(s), skipped ${r.skipped.length}`,
                    `Внесени ${r.created.length} производи, прескокнати ${r.skipped.length}`));
      }
    } catch (e) { GF.toast(e.message, 'error'); }
    st.importing = false;
    await GF.WWF.loadQcPotency();
  };
  // The Potency Spec Service's own export (GET /api/specs?status=finished),
  // pasted as text; either the {"specs": [...]} envelope or a bare list.
  GF.WWF.qcPotParseFitted = (text) => {
    let parsed;
    try { parsed = JSON.parse(text); } catch (e) { return { error: AL('Not valid JSON', 'Невалиден JSON') }; }
    const specs = Array.isArray(parsed) ? parsed : (parsed && Array.isArray(parsed.specs) ? parsed.specs : null);
    if (!specs || !specs.length) return { error: AL('The export carries no specs', 'Извозот не содржи спецификации') };
    return { specs };
  };
  GF.WWF.qcPotImportFitted = async (dryRun) => {
    const st = GF.WWF._qcpot;
    const g = (i) => (document.getElementById(i) || {}).value || '';
    st.fittedText = g('qcp-fitted-json'); st.fittedVersion = g('qcp-fitted-version').trim();
    const parsed = GF.WWF.qcPotParseFitted(st.fittedText);
    if (parsed.error) return GF.toast(parsed.error, 'error');
    if (!st.fittedVersion) {
      return GF.toast(AL('State the document version the fitted specification was issued under',
                         'Наведете ја верзијата на документот под која е издадена фитуваната спецификација'), 'error');
    }
    st.importing = true; GF.render.all();
    try {
      const r = await GF.API.qcImportFittedProducts({ specs: parsed.specs, doc_version: st.fittedVersion, dry_run: !!dryRun });
      st.fittedPreview = r;
      if (!dryRun) {
        GF.toast(AL(`Imported ${r.created.length} fitted product(s), skipped ${r.skipped.length}`,
                    `Внесени ${r.created.length} фитувани производи, прескокнати ${r.skipped.length}`));
      }
    } catch (e) { GF.toast(e.message, 'error'); }
    st.importing = false;
    await GF.WWF.loadQcPotency();
  };
  // Legacy: the August ladders. Offered only while the org has no product at
  // all — the backend refuses the import once one is APPROVED.
  GF.WWF.qcPotImportLadders = async () => {
    const st = GF.WWF._qcpot;
    st.importing = true; GF.render.all();
    try {
      const r = await GF.API.qcImportPotencySpecs({ family: 'ALL' });
      GF.toast(AL(`Imported ${r.created.length} ladder(s), skipped ${r.skipped.length}`,
                  `Внесени ${r.created.length} скали, прескокнати ${r.skipped.length}`));
    } catch (e) { GF.toast(e.message, 'error'); }
    st.importing = false;
    await GF.WWF.loadQcPotency();
  };

  // ── conformance lookup: which product does a measured value belong to? ──
  GF.WWF.qcPotConform = async () => {
    const st = GF.WWF._qcpot;
    const p = st.detail && st.detail.product;
    if (!p) return;
    const raw = ((document.getElementById('qcp-conf-val') || {}).value || '').trim().replace(',', '.');
    st.confValue = raw;
    const v = Number(raw);
    if (!raw || !isFinite(v) || v < 0 || v > 100) {
      return GF.toast(AL('Enter a Total Δ9-THC between 0 and 100 %', 'Внесете вкупен Δ9-THC меѓу 0 и 100 %'), 'error');
    }
    try {
      st.conf = await GF.API.qcProductConformance({ cultivar_id: p.cultivar_id, total_d9_thc: v, product_id: p.id });
    } catch (e) { st.conf = null; GF.toast(e.message, 'error'); }
    GF.render.all(); GF.refocus('qcp-conf-val');
  };

  // ── the A4 page: a plain link carries no bearer header (FE-09), so fetch
  // with the token and open the document from a blob URL, as the CoQ
  // downloads do (qccoa-view.js qcCoaDlCoq).
  GF.WWF.qcPotOpenDoc = async (url, name) => {
    try {
      const res = await fetch(url, { headers: { Authorization: 'Bearer ' + GF.API.token } });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const blob = await res.blob();
      const href = URL.createObjectURL(new Blob([blob], { type: 'text/html' }));
      const w = window.open(href, '_blank', 'noopener');
      if (!w) {
        const a = document.createElement('a');
        a.href = href; a.download = (name || 'specification') + '.html';
        document.body.appendChild(a); a.click(); a.remove();
      }
      setTimeout(() => URL.revokeObjectURL(href), 60000);
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  // ── legacy ladders, read-only ──────────────────────────────────────────
  GF.WWF.qcPotLadderPick = async (id) => {
    const st = GF.WWF._qcpot;
    if (st.ladderSel === id) { st.ladderSel = null; st.ladderDetail = null; GF.render.all(); return; }
    st.ladderSel = id; st.ladderDetail = null; GF.render.all();
    try { const d = await GF.API.qcPotencySpec(id); if (st.ladderSel === id) st.ladderDetail = d; }
    catch (e) { if (st.ladderSel === id) GF.toast(e.message, 'error'); }
    if (st.ladderSel === id && GF.state.view === 'qcpotency') GF.render.all();
  };

  // ── one delegated listener; data attributes carry the arguments ────────
  GF.WWF.qcPotAct = (el) => {
    const act = el.getAttribute('data-qcp-act'), id = el.getAttribute('data-id');
    switch (act) {
      case 'pick':          return GF.WWF.qcPotPick(id);
      case 'retry':         return GF.WWF.qcPotRetry(id);
      case 'approve':       return GF.WWF.qcPotApprove(id);
      case 'supersede':     return GF.WWF.qcPotSupersede(id);
      case 'doc':           return GF.WWF.qcPotOpenDoc(GF.API.qcProductDocumentUrl(id), el.getAttribute('data-name'));
      case 'ladder-doc':    return GF.WWF.qcPotOpenDoc(GF.API.qcSpecDocumentUrl(id, el.getAttribute('data-tier')), el.getAttribute('data-name'));
      case 'ladder-pick':   return GF.WWF.qcPotLadderPick(id);
      case 'import-dry':    return GF.WWF.qcPotImport(true);
      case 'import':        return GF.WWF.qcPotImport(false);
      case 'fitted-dry':    return GF.WWF.qcPotImportFitted(true);
      case 'fitted':        return GF.WWF.qcPotImportFitted(false);
      case 'ladders-import': return GF.WWF.qcPotImportLadders();
      case 'conform':       return GF.WWF.qcPotConform();
      case 'reload':        return GF.WWF.loadQcPotency();
      default: return undefined;
    }
  };
  document.addEventListener('click', (ev) => {
    const el = ev.target && ev.target.closest && ev.target.closest('[data-qcp-act]');
    if (!el) return;
    ev.preventDefault();
    GF.WWF.qcPotAct(el);
  });
  document.addEventListener('input', (ev) => {
    const el = ev.target;
    if (el && el.id === 'qcp-search') GF.WWF.qcPotFilter(el.value);
  });
  document.addEventListener('change', (ev) => {
    const el = ev.target;
    if (!el) return;
    if (el.id === 'qcp-status') GF.WWF.qcPotStatus(el.value);
    else if (el.id === 'qcp-cultivar') GF.WWF.qcPotCultivar(el.value);
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && ev.target && ev.target.id === 'qcp-conf-val') { ev.preventDefault(); GF.WWF.qcPotConform(); }
  });

  // ── rendering ──────────────────────────────────────────────────────────
  const histBlock = (label, h) => {
    if (!h) return '';
    const vals = (h.values || []).slice(-6).map(v =>
      `<span class="chip-opt mono" title="${GF.esc(v.number || '')}${v.on ? ' · ' + GF.esc(GF.fmtDateTime(v.on)) : ''}" style="border-color:${v.conforms === false ? 'var(--red)' : v.conforms === true ? 'var(--green)' : 'var(--ink-3)'}">${GF.esc(v.lot_code || '—')} · ${n2(v.total_thc)} %</span>`).join(' ');
    return `<div class="qcprod-hist"><span class="ana-note">${label}</span>
      <b>${h.n ? `n=${GF.esc(String(h.n))} · ${AL('avg', 'просек')} ${n2(h.avg)} % · ${n2(h.min)}–${n2(h.max)} %` : AL('nothing measured', 'ништо не е измерено')}</b>
      ${vals ? `<div class="qcprod-vals">${vals}</div>` : ''}</div>`;
  };

  const confBlock = (p, c) => {
    const val = GF.esc(GF.WWF._qcpot.confValue);
    let out = '';
    if (c && c.product) {
      const ok = c.product.conforms;
      const verdict = ok === true
        ? `<span class="chip-opt" style="border-color:var(--green);color:var(--green)">✓ ${AL('conforms to', 'одговара на')} ${GF.esc(c.product.product_code)}</span>`
        : `<span class="chip-opt" style="border-color:var(--red);color:var(--red)">✗ ${AL('outside', 'надвор од')} ${GF.esc(c.product.product_code)}</span>`;
      const regrade = ok === false ? (c.product.regrade_to
        ? `<span class="chip-opt" style="border-color:var(--amber);color:var(--amber)">${AL('falls to', 'паѓа на')} ${GF.esc(c.product.regrade_to)}</span>`
        : `<span class="chip-opt" style="border-color:var(--amber);color:var(--amber)">${AL('fits no grade of this strain', 'не одговара на ниту една класа')}</span>`) : '';
      const matching = (c.matching || []).length
        ? `${AL('satisfies', 'задоволува')}: ${c.matching.map(m => `<span class="mono">${GF.esc(m)}</span>`).join(', ')}`
        : AL('satisfies no product', 'не задоволува ниту еден производ');
      out = `<div class="qcprod-conf-out">${verdict} ${regrade}<div class="ana-note">${matching}${c.nearest ? ` · ${AL('nearest', 'најблизок')}: <span class="mono">${GF.esc(c.nearest)}</span>` : ''}</div></div>`;
    }
    return `<div class="qcprod-conf">
      <span class="ana-note">${AL('Which product does a measured Total Δ9-THC belong to?', 'На кој производ припаѓа измерен вкупен Δ9-THC?')}</span>
      <div class="qcs-form"><input id="qcp-conf-val" inputmode="decimal" placeholder="Total Δ9-THC %" value="${val}" style="max-width:140px">
        ${btn('conform', null, AL('Check', 'Провери'))}</div>${out}</div>`;
  };

  const detail = (d) => {
    const p = d.product;
    const doc = `${GF.esc(p.doc_code)} ${GF.esc(p.doc_version)}`;
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Product', 'Производ')}</span><b class="mono">${GF.esc(p.product_code)}</b>
        <span>${AL('Cultivar', 'Сорта')}</span><b>${GF.esc(p.cultivar_name || '')} <span class="ana-note mono">${GF.esc(p.cultivar_code || '')}</span></b>
        <span>${AL('Nominal', 'Номинал')}</span><b class="mono">${n2(p.nominal_pct)} %${GF.esc(tol(p))}</b>
        <span>${AL('Window', 'Опсег')}</span><b class="mono">${GF.esc(win(p))}</b>
        <span>${AL('Document', 'Документ')}</span><b class="mono">${doc}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(p.status)}</b>
        ${p.effective_date ? `<span>${AL('Effective', 'Важи од')}</span><b class="mono">${GF.esc(p.effective_date)}</b>` : ''}
        ${p.source ? `<span>${AL('Source', 'Извор')}</span><b>${GF.esc(p.source)}</b>` : ''}
        <span>${AL('Updated', 'Ажурирано')}</span><b class="mono">${GF.esc(GF.fmtDateTime(p.updated_at))}</b>
      </div>
      ${p.notes ? `<div class="ana-note" style="margin-top:6px">${GF.esc(p.notes)}</div>` : ''}
      <div class="qms-dl" style="margin-top:8px">
        ${btn('doc', p.id, AL('A4 document', 'A4 документ'), 'btn btn-sm', ` data-name="${GF.esc(p.product_code)}"`)}
        ${canApprove() && p.status === 'DRAFT' ? btn('approve', p.id, AL('Approve', 'Одобри'), 'btn btn-sm btn-primary',
          ` title="${AL('Second person only — the backend refuses the author (segregation of duties). Approving retires the strain\'s ladder and its products of any other document version.', 'Само второ лице — серверот го одбива авторот. Одобрувањето ја повлекува скалата на сортата и нејзините производи од друга верзија.')}"`) : ''}
        ${canApprove() && p.status === 'APPROVED' ? btn('supersede', p.id, AL('Supersede', 'Замени')) : ''}
      </div>
      <div style="margin-top:10px" class="ana-pt">${AL('Tested so far (Total Δ9-THC)', 'Тестирано досега (вкупен Δ9-THC)')}</div>
      ${histBlock(AL('CoQs naming this product', 'CoQ што го именуваат производот'), d.tested)}
      ${histBlock(AL('CoQs naming only the cultivar', 'CoQ што ја именуваат само сортата'), d.cultivar_level)}
      ${histBlock(AL('Certificates of the cultivar\'s batches (by batch code)', 'Сертификати на серии од сортата (по код на серија)'), d.certificate_level)}
      ${confBlock(p, GF.WWF._qcpot.conf)}
    </div>`;
  };

  const productRow = (p, st) => `
      <div class="qms-row ${st.sel === p.id ? 'on' : ''}" data-qcp-act="pick" data-id="${GF.esc(p.id)}">
        <span class="mono qms-code">${GF.esc(p.product_code)}</span>
        <span class="qms-title"><span class="mono">${n2(p.nominal_pct)} %${GF.esc(tol(p))}</span> <span class="ana-note mono">${GF.esc(win(p))}</span>
          <span class="ana-note">· ${GF.esc(p.doc_version)}</span>
          ${p.tested && p.tested.n ? `<span class="ana-note">· ${AL('tested', 'тестирано')} ${GF.esc(String(p.tested.n))} · ${n2(p.tested.avg)} %</span>` : ''}</span>
        ${stChip(p.status)}
      </div>
      ${st.sel === p.id ? (st.detail ? detail(st.detail) : (st.detailError
        ? `<div class="qms-detail" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
             <span style="color:var(--red-fg,var(--red))">${GF.esc(st.detailError)}</span>
             ${btn('retry', p.id, AL('Failed — retry', 'Неуспешно — обиди се повторно'))}</div>`
        : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`)) : ''}`;

  const catalogue = (st) => {
    const q = st.q.trim().toLowerCase();
    const rows = (st.products || []).filter(p => (!st.cultivar || p.cultivar_id === st.cultivar) && (!q
      || (p.cultivar_name || '').toLowerCase().includes(q)
      || (p.cultivar_code || '').toLowerCase().includes(q)
      || (p.product_code || '').toLowerCase().includes(q)
      || (p.doc_version || '').toLowerCase().includes(q)));
    const groups = new Map();
    rows.forEach(p => { const k = p.cultivar_id; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(p); });
    if (!groups.size) {
      return `<div class="ana-note">${(st.products || []).length
        ? AL('No product matches the filter', 'Ниту еден производ не одговара на филтерот')
        : AL('No products yet — import the official catalogue above.', 'Сè уште нема производи — внесете го официјалниот каталог погоре.')}</div>`;
    }
    return [...groups.values()].map(list => {
      const c = list[0];
      const counts = ['APPROVED', 'DRAFT', 'SUPERSEDED'].map(s => {
        const n = list.filter(p => p.status === s).length;
        return n ? `<span class="ana-note">${n} ${GF.esc(AL(ST[s].en, ST[s].mk).toLowerCase())}</span>` : '';
      }).join(' ');
      return `<div class="qcprod-group"><span class="mono qms-code">${GF.esc(c.cultivar_code || '')}</span>
          <span class="qms-title">${GF.esc(c.cultivar_name || '')}</span>${counts}</div>` +
        list.map(p => productRow(p, st)).join('');
    }).join('');
  };

  // The packaged ImB pages' document version, and how versions order (the
  // numbers they carry: v.03 < v.04 < "fitted 2026-09-15") — the same rule
  // the server applies (products._version_key).
  const IMB_VERSION = 'v.03';
  const vkey = (v) => (String(v || '').match(/\d+/g) || []).map(Number);
  const newerThan = (a, b) => {
    const x = vkey(a), y = vkey(b);
    for (let i = 0; i < Math.max(x.length, y.length); i++) {
      const p = x[i] === undefined ? -1 : x[i], q = y[i] === undefined ? -1 : y[i];
      if (p !== q) return p > q;
    }
    return false;
  };
  // Strains holding a product of a later document version than the ImB pages
  // (QR-02, owner 2026-09-18): the v.03 pages are retired for them and the
  // server refuses to import them again.
  const retiredFor = (products) => [...new Set((products || [])
    .filter(p => newerThan(p.doc_version, IMB_VERSION)).map(p => p.cultivar_code || ''))].filter(Boolean).sort();

  const previewBlock = (r, kind) => {
    if (!r) return '';
    const parts = [
      `${r.dry_run ? AL('Dry run', 'Пробно') : AL('Imported', 'Внесено')}: ${r.created.length} ${AL('product(s)', 'производи')}`,
      `${r.skipped.length} ${AL('skipped', 'прескокнати')}`,
      `${r.conflicts.length} ${AL('conflict(s)', 'конфликти')}`,
      `${(r.cultivars_created || []).length} ${AL('new cultivar(s)', 'нови сорти')}`,
    ];
    if (r.cultivars_renamed && r.cultivars_renamed.length) {
      parts.push(`${AL('renamed', 'преименувани')}: ${r.cultivars_renamed.map(x => `${GF.esc(x.code)} ${GF.esc(x.from)} → ${GF.esc(x.to)}`).join(', ')}`);
    }
    const conflicts = (r.conflicts || []).map(c => `<div class="ana-note" style="color:var(--red-fg,var(--red))">${GF.esc(c.strain || c.id || '')} — ${GF.esc(c.code || '')} ${AL('is taken by', 'е зафатен од')} ${GF.esc(c.taken_by || '')}</div>`).join('');
    const refused = (r.refused && r.refused.length)
      ? `<div class="ana-note qcprod-refused" style="color:var(--red-fg,var(--red))">${AL('Retired for', 'Повлечено за')}: ${r.refused.map(GF.esc).join(', ')} — ${AL('a later specification version exists for these strains; the import is refused for them', 'постои понова верзија на спецификацијата за овие сорти; внесот за нив е одбиен')}</div>` : '';
    return `<div class="qcprod-preview" data-kind="${GF.esc(kind)}"><div class="ana-note">${parts.join(' · ')}${r.doc_version ? ` · ${GF.esc(r.doc_code || '')} ${GF.esc(r.doc_version)}` : ''}</div>${conflicts}${refused}
      ${r.dry_run && r.created.length ? `<div class="ana-note">${AL('Nothing was written. Import for real to load these as DRAFT products.', 'Ништо не е запишано. Внесете навистина за да се вчитаат како нацрт производи.')}</div>` : ''}</div>`;
  };

  const importer = (st) => {
    if (!canApprove()) return '';
    const dis = st.importing ? ' disabled' : '';
    const hasProducts = (st.products || []).length > 0;
    const retired = retiredFor(st.products);
    return `<div class="panel ana-panel qcprod-import" style="margin-bottom:12px">
      <div class="ana-pt" style="margin-bottom:6px">${AL('Fitted specifications (Potency Spec Service export)', 'Фитувани спецификации (извоз од Potency Spec Service)')}</div>
      <div class="ana-note" style="margin-bottom:6px">${AL(
        'Owner decision 2026-09-18: the fitted, non-overlapping windows apply everywhere. Paste the service\'s export (GET /api/specs?status=finished) and state the document version it was issued under. Dry run first; everything lands as DRAFT.',
        'Одлука на сопственикот 2026-09-18: фитуваните, непреклопени опсези важат насекаде. Залепете го извозот на сервисот (GET /api/specs?status=finished) и наведете ја верзијата на документот. Прво пробно; сè влегува како нацрт.')}</div>
      <textarea id="qcp-fitted-json" rows="4" placeholder='{"specs": [...]}' spellcheck="false">${GF.esc(st.fittedText)}</textarea>
      <div class="qcs-form" style="margin-top:6px">
        <input id="qcp-fitted-version" placeholder="${AL('Document version (e.g. v.04)', 'Верзија на документ (пр. v.04)')}" value="${GF.esc(st.fittedVersion)}">
        ${btn('fitted-dry', null, AL('Dry run', 'Пробно'), 'btn btn-sm', dis)}
        ${btn('fitted', null, st.importing ? AL('Importing…', 'Внесување…') : AL('Import fitted', 'Внеси фитувани'), 'btn btn-sm btn-primary', dis)}
      </div>
      ${previewBlock(st.fittedPreview, 'fitted')}
      <div class="ana-pt" style="margin:12px 0 6px">${AL('Official ImB pages (QCSP 001 v.03, 42 products)', 'Официјални ImB страници (QCSP 001 v.03, 42 производи)')}</div>
      <div class="ana-note" style="margin-bottom:6px">${AL(
        'The issued v.03 pages as printed (±10 % of nominal — reference since 2026-09-18). Idempotent on code + version; a cultivar still spelt the August way is renamed as the specification prints it.',
        'Издадените v.03 страници како што се отпечатени (±10 % од номиналот — референца од 2026-09-18). Идемпотентно по код + верзија; сорта со августовски правопис се преименува како во спецификацијата.')}</div>
      ${retired.length ? `<div class="ana-note qcprod-retired" style="color:var(--amber);margin-bottom:6px">${AL('Retired for', 'Повлечено за')} ${retired.map(GF.esc).join(', ')}: ${AL('a later specification version is on file, so the v.03 pages cannot be imported again (the server refuses); the dry run shows what it would report.', 'постои понова верзија на спецификацијата, па v.03 страниците не може повторно да се внесат (серверот одбива); пробното покажува што би пријавило.')}</div>` : ''}
      <div class="qcs-form">
        ${btn('import-dry', null, AL('Dry run', 'Пробно'), 'btn btn-sm', dis)}
        ${retired.length ? '' : btn('import', null, st.importing ? AL('Importing…', 'Внесување…') : AL('Import ImB pages', 'Внеси ImB страници'), 'btn btn-sm btn-primary', dis)}
      </div>
      ${previewBlock(st.imbPreview, 'imb')}
      ${hasProducts ? '' : `<details class="qcprod-legacy" style="margin-top:10px"><summary class="ana-note">${AL('Legacy: the August 2026 ladders (retired once a product is approved)', 'Застарено: скалите од август 2026 (повлечени штом се одобри производ)')}</summary>
        <div class="qcs-form" style="margin-top:6px">${btn('ladders-import', null, AL('Import ladders (71 strains, DRAFT)', 'Внеси скали (71 сорти, нацрт)'), 'btn btn-sm', dis)}</div></details>`}
    </div>`;
  };

  const ladderDetail = (d) => {
    const s = d.spec;
    const rows = (d.ranges || []).map(r => `<tr>
      <td>Spec ${GF.esc(ROMAN[r.tier] || r.tier)}</td>
      <td class="mono">${GF.esc(String(r.nominal))}%${r.width_pp != null ? ` ± ${GF.esc(String(r.width_pp))}%` : ''}</td>
      <td class="mono">${GF.esc(String(r.range_min))} – ${GF.esc(String(r.range_max))}%</td>
      <td>${btn('ladder-doc', s.id, AL('A4 document', 'A4 документ'), 'btn btn-sm', ` data-tier="${GF.esc(String(r.tier))}" data-name="${GF.esc((s.cultivar_code || '') + '-' + (ROMAN[r.tier] || r.tier))}"`)}</td>
    </tr>`).join('');
    return `<div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Version', 'Верзија')}</span><b class="mono">${GF.esc(s.version)}${s.variant ? ` <span class="ana-note">${GF.esc(s.variant)}</span>` : ''}</b>
        <span>${AL('Status', 'Статус')}</span><b>${stChip(s.status)}</b>
        <span>${AL('Floor', 'Под')}</span><b class="mono">${GF.esc(String(s.floor_pct))}%</b>
        ${s.effective_date ? `<span>${AL('Effective', 'Важи од')}</span><b class="mono">${GF.esc(s.effective_date)}</b>` : ''}
      </div>
      ${s.notes ? `<div class="ana-note" style="margin-top:6px">${GF.esc(s.notes)}</div>` : ''}
      <table class="qcp-table" style="margin-top:8px"><thead><tr>
        <th>${AL('Grade', 'Класа')}</th><th>${AL('Nominal', 'Номинал')}</th>
        <th>${AL('Range', 'Опсег')}</th><th></th></tr></thead><tbody>${rows}</tbody></table>
      <div class="ana-note" style="margin-top:6px">${AL('Read-only: ladders are retired; certificates issued against one keep printing the grade they were issued with.', 'Само за читање: скалите се повлечени; издадените сертификати ја задржуваат класата со која се издадени.')}</div>
    </div>`;
  };

  const legacyLadders = (st) => {
    const ladders = st.ladders || [];
    if (!ladders.length) return '';
    const rows = ladders.map(s => `
      <div class="qms-row ${st.ladderSel === s.id ? 'on' : ''}" data-qcp-act="ladder-pick" data-id="${GF.esc(s.id)}">
        <span class="mono qms-code">${GF.esc(s.cultivar_code || '')}</span>
        <span class="qms-title">${GF.esc(s.cultivar_name || '')} <span class="ana-note mono">${GF.esc(s.version)}</span></span>
        ${stChip(s.status)}
      </div>
      ${st.ladderSel === s.id ? (st.ladderDetail ? ladderDetail(st.ladderDetail) : `<div class="qms-detail"><div class="mw-skel" style="height:60px"></div></div>`) : ''}`).join('');
    return `<details class="panel ana-panel qcprod-legacy" style="margin-top:12px">
      <summary class="ana-pt" style="cursor:pointer">${AL('Legacy potency ladders (PP-QC-SPEC-001, read-only)', 'Застарени скали на јачина (PP-QC-SPEC-001, само за читање)')} <span class="ana-note">· ${ladders.length}</span></summary>
      <div class="qms-list">${rows}</div></details>`;
  };

  GF.views.qcpotency = () => {
    const st = GF.WWF._qcpot;
    if (!st.products && !st.loading && !st.error) GF.WWF.loadQcPotency();
    const head = `<div class="view-head"><div><div class="view-title">${AL('Product catalogue', 'Каталог на производи')}</div>
      <div class="view-sub">${AL('The official potency specification per product (QCSP 001) — import, approve as a second person, supersede, tested so far, the A4 page', 'Официјална спецификација за јачина по производ (QCSP 001) — внеси, одобри како второ лице, замени, тестирано досега, A4 страница')}</div></div>
      <div class="spacer"></div></div>`;
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — one product is one strain at one nominal Total Δ9-THC with the window its page prints. A CoQ names the product it certifies against; a value outside the window falls to the grade that holds it and opens a formal OOS. Approval is a second-person act.',
      'QMS Студио — еден производ е една сорта на еден номинален вкупен Δ9-THC со опсегот од страницата. CoQ го именува производот; вредност надвор од опсегот паѓа на класата што ја содржи и отвора формален OOS. Одобрувањето е чин на второ лице.')}</div>`;
    if (st.loading && !st.products) {
      return head + zone + `<div class="mw-skel" style="height:60px;margin-bottom:10px"></div><div class="mw-skel" style="height:200px"></div>`;
    }
    if (st.error) {
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        ${btn('reload', null, AL('Retry', 'Обиди се повторно'))}</div>`;
    }
    const cultivars = new Map();
    (st.products || []).forEach(p => cultivars.set(p.cultivar_id, `${p.cultivar_code} · ${p.cultivar_name}`));
    const cvOpts = [...cultivars.entries()].sort((a, b) => a[1].localeCompare(b[1])).map(([id, label]) =>
      `<option value="${GF.esc(id)}" ${st.cultivar === id ? 'selected' : ''}>${GF.esc(label)}</option>`).join('');
    return head + zone + importer(st) + `
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Products by cultivar', 'Производи по сорта')}</div>
          <input id="qcp-search" class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}">
          <select id="qcp-cultivar"><option value="">${AL('All cultivars', 'Сите сорти')}</option>${cvOpts}</select>
          <select id="qcp-status">
            <option value="">${AL('All statuses', 'Сите статуси')}</option>
            ${Object.keys(ST).map(s => `<option value="${s}" ${st.status === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
        </div>
        <div class="qms-list">${catalogue(st)}</div>
      </div>` + legacyLadders(st);
  };

  GF.WWF._registerFullPageView({
    key: 'qcpotency', icon: 'flask',
    label: () => AL('Product catalogue', 'Каталог на производи'),
    insertBefore: 'qms-end',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
