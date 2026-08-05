/* search-view.js — full-page grouped search (mockup search.html). Global: GF.views.search
   A page-level companion to the ⌘K palette (cmdk.js): same in-memory, real-data
   sources, grouped by kind, but reachable from the rail (useful on touch, where
   there is no keyboard shortcut). Searches ONLY what is already in memory —
   views, tasks (incl. tree children), people, and, when the Facility board has
   been loaded this session, rooms and their batches. Documents are NOT a source
   here: there is no always-loaded document index to search (deferred). No
   network; navigation reuses the same handlers the palette uses. */
window.GF = window.GF || {}; GF.WWF = GF.WWF || {};
GF.views = GF.views || {};

(function () {
  GF.WWF._search = GF.WWF._search || { q: '' };

  // Same subsequence-friendly scorer as cmdk.js (exact-prefix > substring >
  // scattered; shorter strings win ties). Kept local so this view is
  // self-contained rather than reaching into cmdk's closure.
  const score = (q, s) => {
    s = (s || '').toLowerCase();
    const i = s.indexOf(q);
    if (i === 0) return 100 - s.length * 0.01;
    if (i > 0) return 60 - i * 0.1 - s.length * 0.01;
    let qi = 0;
    for (const ch of s) if (ch === q[qi]) qi++;
    return qi === q.length ? 20 - s.length * 0.01 : -1;
  };

  const allTasks = () => {
    const kids = Object.values(GF.state.children || {}).flat();
    return (GF.state.tasks || []).concat(kids);
  };

  // Navigation destinations, mirroring cmdk's VIEWS() but tolerant of missing
  // capability helpers (every guard is optional-chained).
  const VIEWS = () => {
    const v = [
      ['mywork', 'my_week'], ['board', 'board'], ['timeline', 'timeline'],
      ['calendar', 'calendar'], ['coord', 'coordination'], ['dash', 'dashboard'], ['team', 'team'],
    ];
    if (GF.isExec && GF.isExec()) v.unshift(['exec', 'exec_overview']);
    if (GF.hasDeptHome && GF.hasDeptHome()) v.unshift(['depthome', 'dept_home']);
    if (GF.can && GF.can('team')) v.push(['workload', 'workload']);
    return v.map(([id, key]) => ({ kind: 'view', id, label: (GF.t ? GF.t(key) : key) }));
  };

  // Rooms + batches, ONLY if the facility board has already loaded them this
  // session (GF.WWF._fac.data). No fetch — an un-visited Facility board simply
  // contributes no room/batch results, and the empty-state explains why.
  const facilityRooms = () => ((GF.WWF._fac && GF.WWF._fac.data && GF.WWF._fac.data.rooms) || []);

  GF.WWF._searchMatches = () => {
    const q = (GF.WWF._search.q || '').trim().toLowerCase();
    const out = [];
    for (const v of VIEWS()) {
      const sc = q ? score(q, v.label) : 40;
      if (sc >= 0) out.push({ ...v, sc, group: AL('Go to', 'Оди на') });
    }
    if (q) {
      for (const t of allTasks()) {
        const sc = Math.max(score(q, t.title || ''), score(q, t.ref || ''), score(q, t.reference_code || ''));
        if (sc >= 0) out.push({ kind: 'task', id: t.id, week: t.week_start || '', label: t.title, sub: GF.depAbbr ? GF.depAbbr(t.dept) : '', sc: sc - 1, group: AL('Tasks', 'Задачи') });
      }
      for (const [pid, p] of Object.entries(GF.PEOPLE || {})) {
        const sc = score(q, p.name || '');
        if (sc >= 0) out.push({ kind: 'person', id: pid, label: p.name, sub: p.roleLabel || '', sc: sc - 2, group: AL('People', 'Луѓе') });
      }
      for (const r of facilityRooms()) {
        const rn = (GF.state.lang === 'mk' && r.name_mk) ? r.name_mk : r.name;
        const rsc = score(q, rn || '');
        if (rsc >= 0) out.push({ kind: 'room', id: r.id, label: rn, sub: (r.plant_total || 0) + ' ' + AL('plants', 'растенија'), sc: rsc - 2, group: AL('Rooms', 'Соби') });
        for (const b of (r.batches || [])) {
          const bsc = score(q, b.strain || '');
          if (bsc >= 0) out.push({ kind: 'room', id: r.id, label: b.strain, sub: rn + ' · ' + (b.plant_count || 0), sc: bsc - 3, group: AL('Batches', 'Серии') });
        }
      }
    }
    return out.sort((a, b) => b.sc - a.sc);
  };

  GF.WWF.searchGo = (kind, id, week) => {
    if (kind === 'view') { GF.setView(id); return; }
    if (kind === 'task') {
      if (GF.WWF.xrJump) GF.WWF.xrJump(id, week || '');
      else { (GF.state.expanded = GF.state.expanded || new Set()).add(id); GF.setView('mywork'); }
      return;
    }
    if (kind === 'person') { GF.setView('team'); return; }
    if (kind === 'room') {
      GF.setView('facility');
      if (GF.WWF.openRoom) setTimeout(() => GF.WWF.openRoom(id), 60);
      return;
    }
  };

  // Re-render ONLY the results list on each keystroke so the input keeps focus
  // (same idiom as audit-view's filterAudit / the rest of the app).
  GF.WWF.searchInput = (v) => {
    GF.WWF._search.q = v;
    const host = GF.$('search-results');
    if (host) host.innerHTML = GF.WWF._searchResultsHtml();
  };

  const KIND_ICON = { view: 'arrowR', task: 'check', person: 'user', room: 'leaf' };

  GF.WWF._searchResultsHtml = () => {
    const q = (GF.WWF._search.q || '').trim();
    const matches = GF.WWF._searchMatches();
    if (!matches.length) {
      return `<div class="sr-empty">${q
        ? AL('No matches in what is loaded. Open the relevant board first, then search again.',
             'Нема совпаѓања во вчитаното. Прво отворете ја соодветната табла, па пребарувајте повторно.')
        : AL('Type to search views, tasks, people' + (facilityRooms().length ? ', rooms and batches' : ''),
             'Пишувајте за да пребарувате прегледи, задачи, луѓе' + (facilityRooms().length ? ', соби и серии' : ''))}</div>`;
    }
    // Group in first-seen order (matches are already score-sorted).
    const groups = [];
    const byGroup = {};
    for (const m of matches) {
      if (!byGroup[m.group]) { byGroup[m.group] = []; groups.push(m.group); }
      if (byGroup[m.group].length < 12) byGroup[m.group].push(m);   // cap per group
    }
    return groups.map(g => {
      const rows = byGroup[g].map(m => `
        <button class="sr-row" onclick="GF.WWF.searchGo('${GF.esc(m.kind)}','${GF.esc(m.id)}','${GF.esc(m.week || '')}')">
          <span class="sr-ic">${GF.icon(KIND_ICON[m.kind] || 'arrowR', 'icon')}</span>
          <span class="sr-label">${GF.esc(m.label || '')}</span>
          ${m.sub ? `<span class="sr-sub">${GF.esc(m.sub)}</span>` : ''}</button>`).join('');
      return `<div class="sr-group"><div class="sr-group-h">${GF.esc(g)}<span class="sr-count">${byGroup[g].length}</span></div>${rows}</div>`;
    }).join('');
  };

  GF.views.search = () => {
    // Built manually rather than via GF.viewHead: there is no 'search'/'search_sub'
    // title i18n pair (the 'search' key is the board filter's placeholder), so
    // viewHead would render the wrong label.
    const head = `<div class="view-head">
      <div><div class="view-title">${AL('Search', 'Пребарување')}</div>
        <div class="view-sub">${AL('Everything loaded this session', 'Сè вчитано оваа сесија')}</div></div>
      <div class="spacer"></div>
    </div>`;
    const hint = facilityRooms().length
      ? AL('Searching views, tasks, people, rooms and batches — everything loaded this session.',
           'Пребарување низ прегледи, задачи, луѓе, соби и серии — сè вчитано оваа сесија.')
      : AL('Searching views, tasks and people. Open the Facility board to include rooms and batches. Tip: ⌘K does this from anywhere.',
           'Пребарување низ прегледи, задачи и луѓе. Отворете ја таблата за капацитет за соби и серии. Совет: ⌘K го прави ова од каде било.');
    return head + `
      <div class="sr-box">
        <span class="sr-box-ic">${GF.icon('search', 'icon')}</span>
        <input id="search-page-input" class="sr-input" autocomplete="off" spellcheck="false"
          value="${GF.esc(GF.WWF._search.q || '')}"
          oninput="GF.WWF.searchInput(this.value)"
          placeholder="${AL('Search everything…', 'Пребарувај сè…')}">
      </div>
      <div class="sr-hint">${hint}</div>
      <div id="search-results" class="sr-results">${GF.WWF._searchResultsHtml()}</div>`;
  };

  GF.WWF._registerFullPageView({
    key: 'search', icon: 'search',
    label: () => AL('Search', 'Пребарување'),
    insertBefore: 'mywork',   // top of the rail — a global utility
    guard: () => !!(GF.API.user || {}).role,
  });
})();
