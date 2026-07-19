/* qmsknow-view.js — QMS Studio: Knowledge Search (RETIRED).

   Semantic search across the QMS Creator's two Letta archives, via the old
   qms-api proxy (POST /qms/rag-query). qms-api was retired platform-wide
   (docs/PLATFORM-ROADMAP-2026-07.md) — its API key is blank on every stack,
   so that endpoint 503s permanently, not intermittently. Regulatory lookups
   now live in Document Studio's regulatory-check step (qmsstudio-view.js,
   DocEngine-backed).

   Previously a search fired the doomed network call every time (a guaranteed
   503 + console error after a real wait) before showing this same message —
   pure noise for a known outcome. Skip the request; go straight to the
   retired state. The search bar stays (its own e2e step still fills and
   submits it) so the interaction reads as "this used to work, here's where
   it went" rather than the input silently vanishing. Text is pinned by
   web/e2e/tests/qms-studio.spec.js. */

(function () {
  GF.WWF._qmsk = { q: '', db: 'both', results: null, searching: false, error: null };

  GF.WWF.qmsSearch = () => {
    const st = GF.WWF._qmsk;
    const q = (GF.$('qmsk-q') ? GF.$('qmsk-q').value : st.q).trim();
    if (!q) return;
    st.q = q; st.error = 'retired (503)'; st.results = null; st.searching = false;
    GF.render.all();
  };

  GF.WWF.qmsDb = (db) => {
    GF.WWF._qmsk.db = db;
    GF.render.all();
  };

  const badge = (label, color) =>
    `<span class="chip-opt" style="border-color:${color};color:${color}">${label}</span>`;

  const resultCard = (r, src) => `
    <div class="qms-hit">
      <div class="qms-hit-h">
        ${badge(src === 'db1'
          ? AL('Regulatory', 'Регулатива')
          : AL('Facility', 'Капацитет'), src === 'db1' ? 'var(--blue)' : 'var(--green)')}
        ${r.source ? `<span class="mono qms-code">${GF.esc(String(r.source).slice(0, 60))}</span>` : ''}
        ${r.score != null ? `<span class="ana-note" style="margin:0">${Math.round(100 * r.score)}%</span>` : ''}
      </div>
      <div class="qms-hit-b">${GF.esc(String(r.text || r.content || r.passage || '').slice(0, 600))}</div>
    </div>`;

  const results = (data) => {
    const d1 = data.db1_results || [], d2 = data.db2_results || [];
    const all = [...d1.map(r => [r, 'db1']), ...d2.map(r => [r, 'db2'])];
    if (!all.length) return `<div class="ana-note">${AL('No passages matched.', 'Нема совпаѓања.')}</div>`;
    return all.map(([r, s]) => resultCard(r, s)).join('');
  };

  GF.views.qmsknow = () => {
    const st = GF.WWF._qmsk;
    const head = GF.viewHead
      ? GF.viewHead('knowledge', 'knowledge_sub')
      : `<h2>${AL('Knowledge Search', 'Пребарување знаење')}</h2>`;
    const dbChip = (id, lbl) => `<span class="chip-opt ${st.db === id ? 'on' : ''}"
      onclick="GF.WWF.qmsDb('${id}')">${lbl}</span>`;
    const bar = `
      <div class="panel ana-panel" style="margin-bottom:12px">
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
          <input id="qmsk-q" class="qms-search" style="flex:1;min-width:220px"
            placeholder="${AL('Ask the QMS knowledge base…', 'Прашај ја базата на знаење…')}"
            value="${GF.esc(st.q)}" onkeydown="if(event.key==='Enter')GF.WWF.qmsSearch()">
          <button class="btn btn-primary btn-sm" onclick="GF.WWF.qmsSearch()">${GF.t('search').replace('…', '')}</button>
        </div>
        <div class="chips" style="margin-top:10px">
          ${dbChip('both', AL('Both databases', 'Двете бази'))}
          ${dbChip('db1', AL('Regulatory (EU-GMP)', 'Регулатива (EU-GMP)'))}
          ${dbChip('db2', AL('Facility documents', 'Документи на капацитетот'))}
        </div>
      </div>`;
    let body = '';
    if (st.searching) {
      body = `<div class="mw-skel" style="height:64px;margin-bottom:8px"></div>
              <div class="mw-skel" style="height:64px"></div>`;
    } else if (st.error && /unavailable|503/i.test(st.error)) {
      // Legacy knowledge search (qms-api rag-query) retired — honest state.
      body = `<div class="panel" style="padding:16px">
        <div class="ana-pt" style="margin:0 0 6px">${AL('Knowledge search retired', 'Пребарувањето на знаење е повлечено')}</div>
        <div class="ana-note">${AL(
          'The legacy QMS knowledge search has been retired. Use Document Studio for document authoring and regulatory checks.',
          'Наследеното пребарување на QMS знаење е повлечено. Користете го Студиото за документи за креирање и регулаторни проверки.')}</div></div>`;
    } else if (st.error) {
      body = `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.qmsSearch()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    } else if (st.results) {
      body = `<div class="panel ana-panel"><div class="qms-list">${results(st.results)}</div></div>`;
    } else {
      body = `<div class="ana-note">${AL(
        'Search the regulatory corpus and the facility document base. Results are informational excerpts — the authoritative record is always the source document.',
        'Пребарајте го регулаторниот корпус и документите на капацитетот. Резултатите се информативни извадоци — авторитативен е секогаш изворниот документ.')}</div>`;
    }
    return head + bar + body;
  };

  GF.WWF._registerFullPageView({
    key: 'qmsknow', icon: 'search',
    label: () => AL('Knowledge', 'Знаење'),
    insertBefore: 'qms-end',   // QMS Studio group (render.js sidebar)
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
