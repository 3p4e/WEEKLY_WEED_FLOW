/* qmsregistry-view.js — QMS Studio: SOP Registry browser (unification
   Phase 1, docs/UNIFICATION-ANALYSIS-2026-07.md).

   Read-only window onto the QMS Creator's document registry, reached through
   the authed platform proxy (/qms/* — the qms-api key never touches the
   browser). Registry data: stats tiles, family/hierarchy tree, searchable
   document list, detail panel with DOCX/PDF downloads.

   Governance (docs/SCOPE.md): this is the QMS *Studio* zone — the documents
   shown here are the authoritative QMS records; the ops zone references them
   only by code. The zone banner below says exactly that.

   When qms-api is not deployed (local dev, e2e, or prod before the owner's
   Phase-1 promotion) the proxy answers 503 "QMS service unavailable" and
   this view shows a labeled unavailable state — that state is itself pinned
   by the e2e spec. Same full-page-view pattern as facility/approvals. */

(function () {
  GF.WWF._qmsr = { stats: null, docs: null, hier: null, sel: null,
                   q: '', loading: false, error: null };

  GF.WWF.loadQmsRegistry = async () => {
    const st = GF.WWF._qmsr;
    st.loading = true; st.error = null;
    try {
      const [stats, docs, hier] = await Promise.all([
        GF.API.qmsStats(), GF.API.qmsDocuments(), GF.API.qmsHierarchy().catch(() => null),
      ]);
      st.stats = stats; st.docs = docs; st.hier = hier;
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'qmsregistry') GF.render.all();
  };

  GF.WWF.qmsPick = (code) => {
    GF.WWF._qmsr.sel = code === GF.WWF._qmsr.sel ? null : code;
    GF.render.all();
  };
  GF.WWF.qmsFilter = (v) => { GF.WWF._qmsr.q = v; GF.render.all(); };

  const STATUS = {
    approved:  { en: 'Approved',  mk: 'Одобрен',   c: 'var(--green)' },
    draft:     { en: 'Draft',     mk: 'Нацрт',     c: 'var(--orange)' },
    in_review: { en: 'In review', mk: 'На преглед', c: 'var(--blue)' },
    planned:   { en: 'Planned',   mk: 'Планиран',  c: 'var(--violet)' },
    completed: { en: 'Completed', mk: 'Завршен',   c: 'var(--green)' },
    archived:  { en: 'Archived',  mk: 'Архивиран', c: 'var(--ink-3)' },
  };
  const stChip = (s) => {
    const m = STATUS[(s || '').toLowerCase()] || { en: s || '—', mk: s || '—', c: 'var(--ink-3)' };
    return `<span class="chip-opt" style="border-color:${m.c};color:${m.c}">${GF.esc(AL(m.en, m.mk))}</span>`;
  };

  const docList = (docs) => {
    const st = GF.WWF._qmsr;
    const q = st.q.trim().toLowerCase();
    const rows = (docs || []).filter(d => !q
      || (d.code || '').toLowerCase().includes(q)
      || (d.title || '').toLowerCase().includes(q));
    if (!rows.length) return `<div class="ana-note">${GF.t('no_tasks')}</div>`;
    return rows.map(d => `
      <div class="qms-row ${st.sel === d.code ? 'on' : ''}" onclick="GF.WWF.qmsPick('${GF.esc(d.code || '')}')">
        <span class="mono qms-code">${GF.esc(d.code || '—')}</span>
        <span class="qms-title">${GF.esc(d.title || '')}</span>
        ${stChip(d.status)}
      </div>
      ${st.sel === d.code ? detail(d) : ''}`).join('');
  };

  const detail = (d) => `
    <div class="qms-detail">
      <div class="qms-dgrid">
        <span>${AL('Department', 'Оддел')}</span><b>${GF.esc(d.department || '—')}</b>
        <span>${AL('Version', 'Верзија')}</span><b>${GF.esc(String(d.version || '—'))}</b>
        <span>${AL('Updated', 'Ажурирано')}</span><b>${GF.esc((d.last_modified || '').slice(0, 10) || '—')}</b>
      </div>
      <div class="qms-dl">
        ${d.docx_path ? `<button class="btn btn-sm" onclick="GF.WWF.qmsDownload('${GF.esc(d.docx_path)}')">${AL('Download DOCX', 'Преземи DOCX')}</button>` : ''}
        ${d.pdf_path ? `<button class="btn btn-sm" onclick="GF.WWF.qmsDownload('${GF.esc(d.pdf_path)}')">${AL('Download PDF', 'Преземи PDF')}</button>` : ''}
        ${!d.docx_path && !d.pdf_path ? `<span class="ana-note">${AL('No generated file yet', 'Сè уште нема генериран документ')}</span>` : ''}
      </div>
    </div>`;

  GF.WWF.qmsDownload = async (path) => {
    // authenticated fetch → blob download (same pattern as the PDF exports)
    try {
      const url = GF.API.qmsDownloadUrl(path);
      const r = await fetch(url, { headers: { Authorization: 'Bearer ' + GF.API.token } });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.status);
      const blob = await r.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = path.split('/').pop();
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { GF.toast(AL('Download failed: ', 'Неуспешно преземање: ') + e.message, 'error'); }
  };

  GF.views.qmsregistry = () => {
    const st = GF.WWF._qmsr;
    if (!st.docs && !st.loading && !st.error) GF.WWF.loadQmsRegistry();
    const head = GF.viewHead
      ? GF.viewHead('sop_registry', 'sop_registry_sub')
      : `<h2>${AL('SOP Registry', 'Регистар на СОП')}</h2>`;
    const zone = `<div class="qms-zone">${AL(
      'QMS Studio — authoritative QMS documents. Operational tasks reference these records by code.',
      'QMS Студио — авторитативни QMS документи. Оперативните задачи ги референцираат овие записи по код.')}</div>`;
    if (st.loading || (!st.docs && !st.error)) {
      return head + zone + `<div class="mw-skel" style="height:80px;margin-bottom:10px"></div>
        <div class="mw-skel" style="height:220px"></div>`;
    }
    if (st.error) {
      // The legacy SOP registry (qms-api) has been retired — its proxy answers a
      // 503 "unavailable". Show that as an honest retired state, not a retryable
      // error. Controlled-document authoring lives in Document Studio now.
      if (/unavailable|503/i.test(st.error)) {
        return head + zone + `<div class="panel" style="padding:16px">
          <div class="ana-pt" style="margin:0 0 6px">${AL('SOP Registry retired', 'Регистарот на СОП е повлечен')}</div>
          <div class="ana-note">${AL(
            'The legacy SOP registry has been retired. Create and manage controlled documents in Document Studio.',
            'Наследениот регистар на СОП е повлечен. Креирајте и управувајте со контролирани документи во Студиото за документи.')}</div></div>`;
      }
      return head + zone + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadQmsRegistry()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const s = st.stats || {};
    const sc = s.status_counts || {};
    const tile = (label, value) => `<div class="ana-tile">
      <div class="ana-tl">${label}</div><div class="ana-tv">${value}</div></div>`;
    return head + zone + `
      <div class="ana-tiles">
        ${tile(AL('Total SOPs', 'Вкупно СОП'), s.total_documents ?? (st.docs || []).length)}
        ${tile(AL('Approved', 'Одобрени'), sc.approved ?? 0)}
        ${tile(AL('Drafts', 'Нацрти'), sc.draft ?? 0)}
        ${tile(AL('Departments', 'Оддели'), s.departments ?? '—')}
      </div>
      <div class="panel ana-panel">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
          <div class="ana-pt" style="margin:0">${AL('Documents', 'Документи')}</div>
          <input class="qms-search" placeholder="${GF.t('search')}" value="${GF.esc(st.q)}"
            oninput="GF.WWF.qmsFilter(this.value)">
        </div>
        <div class="qms-list">${docList(st.docs)}</div>
      </div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'qmsregistry', icon: 'shield',
    label: () => AL('SOP Registry', 'Регистар на СОП'),
    insertBefore: 'qms-end',   // QMS Studio group (render.js sidebar)
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
