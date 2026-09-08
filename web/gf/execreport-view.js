/* execreport-view.js — the owner's cockpit: read-only CONSUMPTION of the
   weekly Plan/Report documents. document-view.js stays the manager AUTHORING
   workbench (compile/edit/approve/lock); this view answers the executive
   questions — who has reported, how did the week go, and "show me 100% of
   the data" via drill-down to every task, note, and logged hour.

   Full-page view (own week/kind picker; the board's week strip is hidden by
   _registerFullPageView). Data: GET /reports/documents/status for the board,
   GET /reports/documents?department_id=… lazily per expanded section.
   Degrades gracefully: an older backend without /status shows a hint instead
   of the board; missing department documents render as ghost sections.
   Loads after document-view.js (uses its _fetchDownload + _ribbonSvg). */
window.GF = window.GF || {}; GF.WWF = GF.WWF || {};
GF.views = GF.views || {};

GF.WWF._xr = { kind: 'report', refDate: '', status: null, docs: {}, open: {},
               loading: false, error: null, seq: 0 };

// Theme-aware tokens, not hardcoded hex — same fix, same reasoning, as
// report-view.js's SC/SC_BG maps (that file's identical class of
// hex-hardcoding). bg/bd both resolve to the status color's `-soft` token so
// the chip repaints correctly in the light theme instead of staying pinned to
// the dark palette's literal rgba values.
const XR_STATUS_STYLE = {
  missing: { bg: 'var(--red-soft)', fg: 'var(--red-fg)', bd: 'var(--red-soft)' },
  draft:   { bg: 'var(--amber-soft)', fg: 'var(--amber-fg)', bd: 'var(--amber-soft)' },
  locked:  { bg: 'var(--primary-soft)', fg: 'var(--primary)', bd: 'var(--primary-soft)' },
};
const xrStatusLbl = (s) => s === 'locked' ? AL('Submitted', 'Поднесен')
  : s === 'draft' ? AL('Draft', 'Нацрт') : AL('Missing', 'Недостасува');

GF.WWF._xrRerender = () => { if (GF.state.view === 'execreport') GF.render.all(); };

GF.WWF.xrLoad = async (force) => {
  const st = GF.WWF._xr;
  // No `if (st.loading) return` here: this function already supersedes via
  // st.seq below, so the early return added nothing except DROPPING the user's
  // click — changing kind or ref_date mid-load did nothing at all, leaving the
  // toolbar and the content disagreeing.
  st.loading = true; st.error = null;
  if (force) { st.status = null; st.docs = {}; }
  GF.WWF._xrRerender();
  const seq = ++st.seq;
  try {
    const q = { kind: st.kind };
    if (st.refDate) q.ref_date = st.refDate;
    const status = await GF.API.documentStatus(q);
    if (seq !== st.seq) return;
    st.status = status;
  } catch (e) {
    if (seq !== st.seq) return;
    // 404/405 = older backend without /status; anything else is a real error.
    st.error = (e && (e.status === 404 || e.status === 405))
      ? AL('The submission board needs the newer backend — deploy it first.',
           'Таблата за поднесувања бара понов backend — прво деплојирајте.')
      : (e.message || String(e));
  }
  st.loading = false;
  GF.WWF._xrRerender();
};

GF.WWF.xrSetKind = (k) => { const st = GF.WWF._xr; if (st.kind === k) return;
  st.kind = k; st.status = null; st.docs = {}; st.open = {}; GF.WWF.xrLoad(); };
GF.WWF.xrSetRef = (v) => { const st = GF.WWF._xr;
  st.refDate = v || ''; st.status = null; st.docs = {}; GF.WWF.xrLoad(); };

// Expand/collapse one section ('' = org-wide) and lazily fetch its document.
GF.WWF.xrToggle = (deptId) => {
  const st = GF.WWF._xr;
  st.open[deptId] = !st.open[deptId];
  if (st.open[deptId] && st.docs[deptId] === undefined) GF.WWF.xrFetchDoc(deptId);
  else GF.WWF._xrRerender();
};

GF.WWF.xrFetchDoc = async (deptId) => {
  const st = GF.WWF._xr;
  st.docs[deptId] = null;   // null = loading; {missing:true} = not compiled
  GF.WWF._xrRerender();
  try {
    const q = { kind: st.kind };
    if (st.refDate) q.ref_date = st.refDate;
    // Dept-scoped managers never send department_id (the server forces theirs).
    if (deptId && !(GF.WWF.deptScope && GF.WWF.deptScope())) q.department_id = deptId;
    st.docs[deptId] = await GF.API.getDocument(q);
  } catch (e) {
    st.docs[deptId] = (e && e.status === 404) ? { missing: true } : { error: e.message || String(e) };
  }
  GF.WWF._xrRerender();
};

GF.WWF.xrExport = async (docId, fmt, fallback) => {
  try { await GF.WWF._fetchDownload('/reports/documents/' + docId + '/export.' + fmt, fallback); }
  catch (e) { GF.toast(AL('Export failed: ', 'Неуспешен извоз: ') + e.message, 'error'); }
};

// Deep link: land on the board with that week selected and the card expanded.
GF.WWF.xrJump = async (taskId, weekStart) => {
  // A document can reference tasks created after this session loaded the
  // board (someone else's work, or API-side changes) — refresh the cache
  // once when the target is unknown, then navigate.
  if (!GF.task(taskId) && GF.WWF.loadAndRender) {
    try { await GF.WWF.loadAndRender(); } catch (e) {}
  }
  if (weekStart) {
    const d = new Date(weekStart + 'T00:00:00');
    const i = GF.calendar.weeks.findIndex(w => d >= w.start && d <= w.end);
    if (i >= 0) GF.state.selWeek = i;
  }
  GF.state.expanded.add(taskId);
  // A document task may be a tree child — open its parent's tree too.
  const t = GF.task(taskId);
  if (t && t.parentId && GF.state.treeOpen) GF.state.treeOpen.add(t.parentId);
  GF.setView('mywork');
};

/* ── shared status-chip renderer (also used by document-view's strip) ── */
GF.WWF.xrStatusChips = (status, opts) => {
  if (!status) return '';
  const compact = opts && opts.compact;
  const chip = (label, s, deptId, updated) => {
    const c = XR_STATUS_STYLE[s] || XR_STATUS_STYLE.missing;
    const click = compact ? '' : ` onclick="GF.WWF.xrToggle('${GF.esc(deptId)}')" style="cursor:pointer"`;
    return `<span class="xr-chip"${click} title="${GF.esc(label)} — ${xrStatusLbl(s)}${updated ? ' · ' + GF.esc(updated.slice(0, 16).replace('T', ' ')) : ''}">
      <span class="xr-chip-in" style="background:${c.bg};color:${c.fg};border:1px solid ${c.bd}">
        <span class="dot" style="background:currentColor"></span>${GF.esc(label)}</span></span>`;
  };
  const parts = [];
  if (status.org_wide) parts.push(chip(AL('Org-wide', 'Цела орг.'), status.org_wide.status, '', status.org_wide.updated_at));
  (status.departments || []).forEach(d => {
    const dept = (GF.DEPTS || []).find(x => x.id === d.id);
    const label = dept ? GF.depAbbr(dept.id) : d.code;
    parts.push(chip(label, d.status, d.id, d.updated_at));
  });
  return `<div class="xr-chips${compact ? ' xr-chips-compact' : ''}">${parts.join('')}</div>`;
};

/* ── section body renderers (all read-only; everything through GF.esc) ── */

// The owner cockpit's headline band (mockup execreport.html .xr-kpis): four
// tiles built entirely from the compiled document's `metrics` (documents.py
// _metrics) — on-time rate, open-overdue count, total logged hours, and mean
// effort ratio. Colour-toned so on-time reads green and overdue reads red at a
// glance. Every field is degrade-safe: a missing metric shows "—"/0, never NaN.
const xrKpis = (c) => {
  const m = (c && c.metrics) || {};
  const ot = m.on_time || {};
  const rate = (ot.rate != null && Number.isFinite(Number(ot.rate))) ? Math.round(ot.rate * 100) + '%' : '—';
  const overdue = m.overdue_open || [];
  const oldest = overdue.reduce((mx, o) => Math.max(mx, o.age_days || 0), 0);
  const hours = (m.per_dept || []).reduce((s, d) => s + (Number(d.hours) || 0), 0);
  const ratios = (m.complexity || []).map(x => x.est_ratio).filter(r => r != null && Number.isFinite(Number(r)));
  const cplx = ratios.length ? ratios.reduce((s, r) => s + Number(r), 0) / ratios.length : null;
  return `<div class="ana-tiles">
    ${GF.kpiTile(AL('On-time', 'Навремено'), rate,
        ot.measured ? `${ot.on_time || 0}/${ot.measured} ${AL('on time', 'навреме')}` : AL('no deadlines', 'без рокови'),
        'good')}
    ${GF.kpiTile(AL('Overdue', 'Задоцнети'), overdue.length,
        overdue.length ? `${AL('oldest', 'најстаро')} ${oldest}${AL('d', 'д')}` : AL('none past due', 'ништо задоцнето'),
        overdue.length ? 'bad' : null)}
    ${GF.kpiTile(AL('Logged hours', 'Логирани часови'), hours ? hours.toFixed(hours < 100 ? 1 : 0) : '0',
        AL('this week', 'оваа недела'))}
    ${GF.kpiTile(AL('Complexity', 'Комплексност'), cplx != null ? cplx.toFixed(1) : '—',
        AL('actual ÷ est', 'реално ÷ план'), cplx != null && cplx > 1.2 ? 'warn' : null)}
  </div>`;
};

const xrNarratives = (c) => {
  const lang = GF.state.lang;
  let out = '';
  (c.template_sections || []).forEach(s => {
    const rows = (s.fields || []).filter(f => f.value).map(f => `
      <div class="xr-frow"><span class="k">${GF.esc(lang === 'mk' ? (f.label_mk || f.label_en) : f.label_en)}</span>
        <span class="v">${GF.esc(f.value)}${f.unit ? ' ' + GF.esc(f.unit) : ''}</span></div>`).join('');
    const nar = s.narrative || {};
    const text = lang === 'mk' ? (nar.mk || nar.en) : (nar.en || nar.mk);
    if (!rows && !text) return;
    out += `<div class="xr-tsec">
      <div class="xr-tsec-head">${GF.esc(lang === 'mk' ? (s.title_mk || s.title_en) : s.title_en)}</div>
      ${rows}${text ? `<div class="xr-nar">${GF.WWF.aiHtml(text)}</div>` : ''}
    </div>`;
  });
  (c.ai_sections || []).forEach(s => {
    if (GF.state.xrHideAI) return;   // "human narrative only" review mode
    if (s.status === 'not_configured' || s.status === 'unavailable') return;
    const text = lang === 'mk' ? (s.body_mk || s.body_en || s.body) : (s.body_en || s.body || s.body_mk);
    if (!text) return;
    out += `<div class="xr-tsec">
      <div class="xr-tsec-head">${GF.esc(s.title)}${s.approved ? '' : ` <span class="xr-badge">${AL('draft', 'нацрт')}</span>`}</div>
      <div class="xr-nar">${GF.WWF.aiHtml(text)}</div>${GF.WWF._aiDisclaimer ? GF.WWF._aiDisclaimer() : ''}
    </div>`;
  });
  return out;
};

const xrTasks = (c) => {
  const who = (uid) => (GF.PEOPLE[uid] || {}).name || '';
  const rows = (c.tasks || []).map(t => {
    const notes = (t.notes || []).map(n => {
      // Executive/owner remarks get the same gold/cyan treatment as the board
      // card (render.js note-owner/note-exec) — the owner reading his own
      // report should spot leadership commentary instantly.
      const p = n.user_id && GF.PEOPLE[n.user_id];
      const br = p && p.backendRole;
      const owner = br === 'OWNER', exec = owner || br === 'CEO' || br === 'COO';
      return `
      <div class="xr-note note ${exec ? 'note-exec' : ''} ${owner ? 'note-owner' : ''}"><b>${GF.esc(n.day || '')}</b> ${GF.esc(n.note || '')}
        ${n.user_id && who(n.user_id) ? `<span class="by">— ${GF.esc(who(n.user_id))}</span>` : ''}</div>`;
    }).join('');
    return `<details class="xr-task"><summary>
        <span class="pill s-${GF.esc((t.status === 'completed' ? 'done' : t.status === 'ongoing' ? 'working' : t.status) || 'pending')}" style="pointer-events:none">${GF.esc(GF.statusLabel((t.status === 'completed' ? 'done' : t.status === 'ongoing' ? 'working' : t.status) || 'pending'))}</span>
        <span class="xr-task-title">${GF.esc(t.title || '')}</span>
        ${t.reference_code ? `<span class="ref-code">${GF.esc(t.reference_code)}</span>` : ''}
      </summary>
      ${t.description ? `<div class="xr-desc">${GF.esc(t.description)}</div>` : ''}
      ${notes || `<div class="xr-note" style="border:none;color:var(--ink-4)">${AL('No progress notes.', 'Нема белешки.')}</div>`}
      <div class="xr-task-actions">
        <button class="btn btn-sm" onclick="GF.WWF.xrJump('${GF.esc(t.id)}','${GF.esc(t.week_start || '')}')">${GF.icon('arrowR', 'icon')}${AL('Open in board', 'Отвори на табла')}</button>
        <button class="btn btn-sm" onclick="GF.WWF.openWorklog&&GF.WWF.openWorklog('${GF.esc(t.id)}')">${GF.icon('clock', 'icon')}${AL('Worklog', 'Работен дневник')}</button>
      </div>
    </details>`;
  }).join('');
  return rows ? `<div class="xr-tasks">${rows}</div>` : '';
};

const xrSection = (label, deptId, statusEntry) => {
  const st = GF.WWF._xr;
  const open = !!st.open[deptId];
  const s = statusEntry ? statusEntry.status : 'missing';
  const c0 = XR_STATUS_STYLE[s] || XR_STATUS_STYLE.missing;
  const head = `<div class="xr-sec-head" onclick="GF.WWF.xrToggle('${GF.esc(deptId)}')">
    ${GF.icon(open ? 'chevD' : 'chevR', 'icon')}
    <b>${GF.esc(label)}</b>
    <span class="xr-chip-in" style="background:${c0.bg};color:${c0.fg};border:1px solid ${c0.bd}">${xrStatusLbl(s)}</span>
    ${statusEntry && statusEntry.updated_at ? `<span class="sub">${GF.esc(statusEntry.updated_at.slice(0, 16).replace('T', ' '))}</span>` : ''}
    <div class="spacer"></div>
  </div>`;
  let body = '';
  if (open) {
    const doc = st.docs[deptId];
    // Self-heal on cache-miss: xrSetKind/xrSetRef wipe st.docs on a kind/week
    // change but leave already-open sections open (xrSetRef especially — the
    // user is still looking at this department, just a different week), so
    // without this an open section stuck at `undefined` never re-fetches and
    // shows "Loading…" forever. Mirrors the org-wide KPI band's own
    // self-healing fetch above (GF.views.execreport), now for every section.
    if (doc === undefined) GF.WWF.xrFetchDoc(deptId);
    if (doc === null || doc === undefined) {
      body = `<div class="xr-sec-body sub" style="display:flex;align-items:center;gap:10px">
        <span class="mw-spinner mw-spinner--sm"></span>${AL('Loading…', 'Се вчитува…')}</div>`;
    } else if (doc.missing) {
      body = `<div class="xr-sec-body sub">${AL('Not submitted — no document compiled for this week.', 'Не е поднесено — нема составен документ за оваа недела.')}</div>`;
    } else if (doc.error) {
      body = `<div class="xr-sec-body" style="color:var(--red-fg)">${GF.esc(doc.error)}</div>`;
    } else {
      const c = doc.content || {};
      const exports = `<div class="xr-exports">
        <button class="btn btn-sm" onclick="GF.WWF.xrExport('${GF.esc(doc.id)}','pdf','wwf-${GF.esc(doc.kind)}-${GF.esc(doc.week_start)}.pdf')">${AL('PDF', 'PDF')}</button>
        <button class="btn btn-sm" onclick="GF.WWF.xrExport('${GF.esc(doc.id)}','html','wwf-${GF.esc(doc.kind)}-${GF.esc(doc.week_start)}.html')">${AL('Interactive HTML', 'Интерактивен HTML')}</button>
        <button class="btn btn-sm ${GF.state.xrHideAI ? 'btn-primary' : ''}" onclick="GF.state.xrHideAI=!GF.state.xrHideAI;GF.render.all()"
          title="${AL('Hide AI-drafted passages — human narrative only', 'Скриј ги AI пасусите — само човечки наратив')}">
          ${GF.icon(GF.state.xrHideAI ? 'eyeOff' : 'sparkle', 'icon')}${GF.state.xrHideAI ? AL('AI hidden', 'AI скриено') : AL('AI shown', 'AI прикажано')}</button>
      </div>`;
      body = `<div class="xr-sec-body">
        ${exports}
        ${xrNarratives(c)}
        ${c.ribbon && c.ribbon.length && GF.WWF._ribbonSvg
          ? `<div class="xr-tsec-head" style="margin-top:10px">${AL('Logged work', 'Одработено')}</div>`
            + GF.WWF._ribbonSvg(c.ribbon, c.period && c.period.start, c.period && c.period.days) : ''}
        ${xrTasks(c)}
      </div>`;
    }
  }
  return `<div class="xr-sec${open ? ' open' : ''}">${head}${body}</div>`;
};

GF.views.execreport = function () {
  const st = GF.WWF._xr;
  if (!st.status && !st.loading && !st.error) { GF.WWF.xrLoad(); }

  const kindBtn = (k, lbl) => `<button class="btn btn-sm${st.kind === k ? ' btn-primary' : ''}"
    onclick="GF.WWF.xrSetKind('${k}')">${lbl}</button>`;
  const head = `
    <div class="view-head">
      <div><div class="view-title">${AL('Executive Report', 'Извештај за раководство')}</div>
        <div class="view-sub">${AL('Weekly documents — submissions, drill-down, export', 'Неделни документи — поднесувања, детали, извоз')}
          ${st.status ? ' · ' + GF.esc(st.status.week_start) : ''}</div></div>
      <div class="spacer"></div>
      ${kindBtn('report', GF.t('report'))}${kindBtn('plan', GF.t('plan'))}
      <span class="xr-datefield" title="${AL('Pick any date — its week is shown', 'Изберете датум — се прикажува неговата недела')}"
        >${GF.dateField('xr-ref', { value: st.refDate, clearable: false,
           onPick: (v) => { if (v) GF.WWF.xrSetRef(v); } })}</span>
      <button class="btn btn-sm" onclick="GF.WWF.xrLoad(true)">${GF.icon('forward', 'icon')}${AL('Refresh', 'Освежи')}</button>
    </div>`;

  if (st.loading && !st.status) return head + `<div class="kempty" style="padding:36px;text-align:center">${AL('Loading…', 'Се вчитува…')}</div>`;
  if (st.error) return head + `<div class="dh-empty"><div class="dh-empty-title">${GF.esc(st.error)}</div>
    <div class="dh-empty-sub"><button class="btn btn-sm" onclick="GF.WWF.xrLoad(true)">${AL('Retry', 'Обиди се повторно')}</button></div></div>`;
  if (!st.status) return head;

  // KPI band from the org-wide document once it's loaded (auto-fetch when the
  // org-wide record exists; a dept manager has no org-wide access — skipped).
  let kpis = '';
  if (st.status.org_wide && st.status.org_wide.status !== 'missing') {
    const orgDoc = st.docs[''];
    if (orgDoc === undefined) GF.WWF.xrFetchDoc('');
    else if (orgDoc && !orgDoc.missing && !orgDoc.error && st.kind === 'report') kpis = xrKpis(orgDoc.content);
  }

  const sections = [];
  if (st.status.org_wide) sections.push(xrSection(AL('Org-wide document', 'Документ за целата организација'), '', st.status.org_wide));
  (st.status.departments || []).forEach(d => {
    const dept = (GF.DEPTS || []).find(x => x.id === d.id);
    sections.push(xrSection(dept ? GF.depName(dept.id) : d.name, d.id, d));
  });

  return head
    + GF.WWF.xrStatusChips(st.status)
    + kpis
    + `<div class="xr-secs">${sections.join('')}</div>`;
};

GF.WWF._registerFullPageView({
  key: 'execreport',
  icon: 'eye',
  insertBefore: 'report',   // Management group of the rail (mockup nav.js)
  label: () => AL('Executive Report', 'Извештај'),
  // Same gate as the backend's require_role(*ELEVATED_ROLES) on /status and
  // the document endpoints — a base USER would only collect 403s here.
  guard: () => ELEVATED_ROLES.includes((GF.API.user || {}).role),
});
