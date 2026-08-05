/* ══════════════════════════════════════════════════════════════════════
   Audit Trail — a general (non-QC) GxP capability adopted from the QC lab.
   Read-only, tamper-evident view of the hash-chained audit_log. Visible to
   elevated roles only (everything but USER), which mirrors the DB
   `audit_read` policy / app.is_elevated().

   Split out of integrate.js (first decomposition cut of its monkey-patch
   pattern). Loads right after integrate.js — AUDIT_ROLES declared below
   is a bare top-level const, visible to collab.js/report-view.js only
   because classic <script> tags share one lexical scope in document order.
   AL() itself now lives in core.js (loads first), same reasoning.
   ════════════════════════════════════════════════════════════════════ */
// Reuse integrate.js's ELEVATED_ROLES (same shared <script> scope, loaded
// first) so the elevated set has one definition on the frontend.
const AUDIT_ROLES = ELEVATED_ROLES;
const ACT = {
  INSERT: { c: '#2BE8A0', en: 'Created', mk: 'Создадено' },
  UPDATE: { c: '#2FD9D9', en: 'Updated', mk: 'Изменето' },
  DELETE: { c: '#E5484D', en: 'Deleted', mk: 'Избришано' },
};
const AUDIT_HIDE = ['password_hash'];   // never surface secrets in the trail

GF.WWF.canAudit = () => AUDIT_ROLES.includes((GF.API.user || {}).role);
// /audit/verify is guarded server-side by require_role("ADMIN","QA_MGR","QP") —
// it was just opened to the QA_MGR / QP auditor roles alongside ADMIN. Mirror
// that exact set so ONLY those users get the "Verify chain" action; every other
// elevated role still reads the trail and the integrity strip, just no button.
const AUDIT_VERIFY_ROLES = ['ADMIN', 'QA_MGR', 'QP'];
GF.WWF.canVerifyAudit = () => AUDIT_VERIFY_ROLES.includes((GF.API.user || {}).role);
GF.WWF._audit = { entries: [], before: null, tables: null, verify: null, verifyBusy: false, hasMore: false, gen: 0, loaded: false, query: '' };
GF.WWF._auditFilter = { table_name: '', action: '', source: '' };
// The two databases keep independent hash chains; every row carries which
// one it came from (identity events vs work events).
const AUDIT_SOURCES = {
  users: { c: '#C2410C', en: 'users', mk: 'корисници' },
  tasks: { c: '#2FD9D9', en: 'tasks', mk: 'задачи' },
};

GF.WWF._auditActor = (e) => {
  if (e.user_id && GF.PEOPLE[e.user_id]) return GF.PEOPLE[e.user_id].name;
  if (e.user_email) return e.user_email;
  if (e.user_id) return e.user_id.slice(0, 8) + '…';
  return AL('system', 'систем');
};
GF.WWF._auditTrunc = (v) => {
  let s = (v === null || v === undefined) ? '∅' : (typeof v === 'object' ? JSON.stringify(v) : String(v));
  return s.length > 90 ? s.slice(0, 90) + '…' : s;
};
GF.WWF._auditDiff = (e) => {
  const o = e.old_values || {}, n = e.new_values || {};
  const rows = [];
  if (e.action === 'INSERT') {
    Object.keys(n).forEach(k => { if (!AUDIT_HIDE.includes(k)) rows.push([k, null, n[k]]); });
  } else if (e.action === 'DELETE') {
    Object.keys(o).forEach(k => { if (!AUDIT_HIDE.includes(k)) rows.push([k, o[k], null]); });
  } else {
    const keys = new Set([...Object.keys(o), ...Object.keys(n)]);
    keys.forEach(k => {
      if (AUDIT_HIDE.includes(k)) return;
      if (JSON.stringify(o[k]) !== JSON.stringify(n[k])) rows.push([k, o[k], n[k]]);
    });
  }
  return rows;
};

GF.views.audit = function () {
  const st = GF.WWF._audit;
  // Already have a fetched page (e.g. the user navigated away and back) —
  // render it straight away instead of wiping it for a fresh loading skeleton.
  if (st.loaded) return `<div id="audit-view" class="audit-wrap" style="padding:4px 2px 40px">${GF.WWF._auditMarkup()}</div>`;
  setTimeout(() => GF.WWF.loadAudit({ reset: true }), 0);
  return `<div id="audit-view" class="audit-wrap" style="padding:4px 2px 40px">
    <div class="audit-loading" style="padding:40px;text-align:center;color:var(--ink-3)">${AL('Loading audit trail…', 'Се вчитува ревизија…')}</div>
  </div>`;
};

GF.WWF.loadAudit = async ({ reset = false } = {}) => {
  const st = GF.WWF._audit;
  if (reset) { st.entries = []; st.before = null; }
  // Bump a generation token so a slower in-flight load can't append its rows
  // on top of a newer reset/filter load (which would duplicate entries).
  const gen = ++st.gen;
  const q = { limit: 100 };
  if (GF.WWF._auditFilter.table_name) q.table_name = GF.WWF._auditFilter.table_name;
  if (GF.WWF._auditFilter.action) q.action = GF.WWF._auditFilter.action;
  if (GF.WWF._auditFilter.source) q.source = GF.WWF._auditFilter.source;
  // Keyset pagination on created_at (NOT id — the two chains have colliding
  // bigint ids): pass the last row's timestamp as `before`.
  if (st.before) q.before = st.before;
  try {
    const page = await GF.API.audit(q);
    if (gen !== st.gen) return;   // a newer load superseded this one
    st.entries = st.entries.concat(page);
    st.before = page.length ? page[page.length - 1].created_at : st.before;
    st.hasMore = page.length === q.limit;
    if (st.tables === null) { try { st.tables = await GF.API.auditTables(); } catch (e) { st.tables = []; } }
    // Chain verification is no longer fetched passively on load — it is now an
    // explicit, on-demand action (GF.WWF.verifyAuditChain, the "Verify chain"
    // button in the integrity strip). st.verify stays null until the user runs it.
    st.loaded = true;
    GF.WWF.renderAudit();
  } catch (e) {
    const v = GF.$('audit-view');
    if (v) v.innerHTML = `<div style="padding:40px;text-align:center;color:#E5484D">${AL('Could not load audit trail', 'Не може да се вчита ревизија')}: ${GF.esc(e.message)}</div>`;
  }
};

// The chain (source) and action facets are now chip toggles that write straight
// to the server-side filter and refetch; the table facet stays a searchable
// popup (it can list many tables), so applyAuditFilter now carries only the
// table value — the chips set their own key directly via setAuditFilter.
GF.WWF.applyAuditFilter = () => {
  GF.WWF._auditFilter.table_name = (GF.$('audit-f-table') || {}).value || '';
  GF.WWF.loadAudit({ reset: true });
};
GF.WWF.setAuditFilter = (key, val) => {
  if (!['table_name', 'action', 'source'].includes(key)) return;
  GF.WWF._auditFilter[key] = val;
  GF.WWF.loadAudit({ reset: true });
};

// Free-text search over the ALREADY-FETCHED rows. The /audit endpoint has no
// text parameter (it filters by table/action/source + created_at keyset only),
// so this is a client-side narrow of the loaded page, exactly like the mockup's
// search box. Re-renders ONLY the list so the input keeps focus between keys.
GF.WWF.filterAudit = () => {
  GF.WWF._audit.query = (GF.$('audit-q') || {}).value || '';
  const host = GF.$('audit-list');
  if (host) host.innerHTML = GF.WWF._auditListHtml();
};

// Explicit, on-demand chain verification — replaces the old passive ADMIN-only
// auto-badge. Guarded to the same roles the server admits (ADMIN/QA_MGR/QP) and
// re-renders only the integrity strip, so a search-in-progress list is untouched.
GF.WWF.verifyAuditChain = async () => {
  if (!GF.WWF.canVerifyAudit()) { GF.denyToast(); return; }
  const st = GF.WWF._audit;
  if (st.verifyBusy) return;
  st.verifyBusy = true;
  GF.WWF._renderVerifybar();
  try {
    st.verify = await GF.API.auditVerify();
    const broken = !st.verify.ok;
    GF.toast(broken
      ? AL('Chain integrity check FAILED — breaks found', 'Проверката на интегритет НЕ Е успешна — пронајдени прекини')
      : AL('Chain verified — no breaks found', 'Синџирот е потврден — без прекини'),
      broken ? 'error' : 'success');
  } catch (e) {
    st.verify = { error: true, message: e.message };
    GF.toast(AL('Could not verify chain', 'Не може да се потврди синџирот') + ': ' + e.message, 'error');
  } finally {
    st.verifyBusy = false;
    GF.WWF._renderVerifybar();
  }
};
// Swap just the integrity strip in place (id-stable) so the verdict updates
// without rebuilding the list and dropping search focus / scroll position.
GF.WWF._renderVerifybar = () => {
  const el = GF.$('audit-verifybar');
  if (el) el.outerHTML = GF.WWF._verifybarHtml();
};

// ── Integrity strip (the mockup's "verify bar"): chain glyph + SHA-256 meta,
// an on-demand verdict per chain, and the "Verify chain" action button. Built
// as its own fragment (id-stable) so GF.WWF._renderVerifybar can swap it alone.
GF.WWF._verifybarHtml = () => {
  const st = GF.WWF._audit;
  const loaded = st.entries.length;
  const meta = `SHA-256 · ${loaded}${st.hasMore ? '+' : ''} ${AL('entries loaded', 'вчитани записи')}`;

  let verdicts;
  if (st.verifyBusy) {
    verdicts = `<span class="audit-verdict idle">${AL('Verifying…', 'Се проверува…')}</span>`;
  } else if (st.verify && st.verify.error) {
    verdicts = `<span class="audit-verdict bad">${GF.icon('flag', 'icon')}${AL('Verification failed', 'Неуспешна проверка')}</span>`;
  } else if (st.verify) {
    // Both databases chain independently, so each reports its own verdict.
    verdicts = ['users', 'tasks'].map(src => {
      const v = st.verify[src], s = AUDIT_SOURCES[src];
      if (!v || !s) return '';
      const label = GF.esc(AL(s.en, s.mk));
      return v.ok
        ? `<span class="audit-verdict ok">${GF.icon('check', 'icon')}${label} ${AL('verified', 'потврден')} · ${GF.esc(v.total)}</span>`
        : `<span class="audit-verdict bad">${GF.icon('flag', 'icon')}${label} ${AL('break at', 'прекин кај')} #${GF.esc(v.first_break_id)}</span>`;
    }).join('');
  } else {
    verdicts = `<span class="audit-verdict idle">${AL('Not verified', 'Непотврдено')}</span>`;
  }

  const btn = GF.WWF.canVerifyAudit()
    ? `<button class="btn btn-sm" ${st.verifyBusy ? 'disabled' : ''} onclick="GF.WWF.verifyAuditChain()">${GF.icon('shield')}${st.verifyBusy ? AL('Verifying…', 'Се проверува…') : AL('Verify chain', 'Провери синџир')}</button>`
    : '';

  return `<div class="audit-verifybar" id="audit-verifybar">
      <span class="audit-vb-ic">${GF.icon('link', 'icon')}</span>
      <div class="audit-vb-body">
        <div class="audit-vb-title">${AL('Chain integrity', 'Интегритет на синџирот')}</div>
        <div class="audit-vb-meta">${GF.esc(meta)}</div>
      </div>
      <div class="audit-vb-verdicts">${verdicts}</div>
      ${btn}
    </div>`;
};

// Lower-cased search haystack for one entry — entity (table + record id),
// actor, action, source and every diffed field key/value, so the search box
// matches the same things the mockup's does.
GF.WWF._auditHaystack = (e) => {
  const parts = [e.table_name, e.record_id, e.action, e.source, GF.WWF._auditActor(e), e.user_email];
  const a = ACT[e.action]; if (a) parts.push(a.en, a.mk);
  const s = AUDIT_SOURCES[e.source]; if (s) parts.push(s.en, s.mk);
  GF.WWF._auditDiff(e).forEach(([k, ov, nv]) => parts.push(k, GF.WWF._auditTrunc(ov), GF.WWF._auditTrunc(nv)));
  return parts.filter(Boolean).join(' ').toLowerCase();
};
GF.WWF._auditVisible = () => {
  const st = GF.WWF._audit, q = (st.query || '').trim().toLowerCase();
  if (!q) return st.entries;
  return st.entries.filter(e => GF.WWF._auditHaystack(e).includes(q));
};

// Just the rows (+ optional "showing N of M" count) for the #audit-list host,
// so a keystroke in the search box re-renders this alone and keeps input focus.
GF.WWF._auditListHtml = () => {
  const st = GF.WWF._audit;
  const q = (st.query || '').trim();
  const list = GF.WWF._auditVisible();
  if (!list.length) {
    const msg = st.entries.length
      ? AL('No entries match your search.', 'Нема записи што одговараат на пребарувањето.')
      : AL('No audit entries match.', 'Нема записи.');
    return `<div style="padding:40px;text-align:center;color:var(--ink-3)">${msg}</div>`;
  }
  const count = q
    ? `<div class="audit-count">${GF.esc(AL('Showing', 'Прикажани'))} ${list.length} / ${st.entries.length}${st.hasMore ? '+' : ''}</div>`
    : '';
  const rows = list.map(e => {
    const a = ACT[e.action] || { c: '#5A6B82', en: e.action, mk: e.action };
    const src = AUDIT_SOURCES[e.source];
    const srcBadge = src ? `<span class="audit-src" style="background:${src.c}14;color:${src.c};font-weight:800;font-size:10px;letter-spacing:.4px;text-transform:uppercase;padding:3px 7px;border-radius:5px;white-space:nowrap">${GF.esc(AL(src.en, src.mk))}</span>` : '';
    const when = e.created_at ? new Date(e.created_at).toLocaleString() : '';
    const diff = GF.WWF._auditDiff(e);
    const diffHtml = diff.length ? diff.map(([k, ov, nv]) => `
      <div style="display:grid;grid-template-columns:170px 1fr;gap:8px;padding:4px 0;border-top:1px dashed var(--line);font-size:12.5px">
        <div style="font-weight:600;color:var(--ink-2);font-family:ui-monospace,monospace">${GF.esc(k)}</div>
        <div style="min-width:0">
          ${e.action !== 'INSERT' ? `<span style="color:#FF4D5E;text-decoration:${e.action === 'DELETE' ? 'none' : 'line-through'}">${GF.esc(GF.WWF._auditTrunc(ov))}</span>` : ''}
          ${e.action === 'UPDATE' ? '<span style="color:var(--ink-3);margin:0 6px">→</span>' : ''}
          ${e.action !== 'DELETE' ? `<span style="color:#2BE8A0">${GF.esc(GF.WWF._auditTrunc(nv))}</span>` : ''}
        </div>
      </div>`).join('') : `<div style="font-size:12.5px;color:var(--ink-3);padding:4px 0">${AL('No field-level changes recorded.', 'Нема промени на полиња.')}</div>`;
    return `
    <details class="audit-entry" style="background:var(--surface-2);border:1px solid var(--line);border-radius:11px;margin-bottom:8px;overflow:hidden">
      <summary style="display:flex;align-items:center;gap:12px;padding:11px 14px;cursor:pointer;list-style:none">
        <span style="font-size:11.5px;color:var(--ink-3);white-space:nowrap;min-width:148px">${GF.esc(when)}</span>
        ${srcBadge}
        <span style="background:${a.c}1A;color:${a.c};font-weight:700;font-size:11px;padding:3px 9px;border-radius:6px;white-space:nowrap">${GF.esc(AL(a.en, a.mk))}</span>
        <span style="font-weight:700;font-size:13px;color:var(--ink);font-family:ui-monospace,monospace">${GF.esc(e.table_name || '—')}</span>
        <span style="font-size:12px;color:var(--ink-3);font-family:ui-monospace,monospace">#${GF.esc(String(e.record_id || '').slice(0, 8))}</span>
        <span style="flex:1"></span>
        <span style="font-size:12.5px;color:var(--ink-2)">${GF.icon('user')}&nbsp;${GF.esc(GF.WWF._auditActor(e))}</span>
      </summary>
      <div style="padding:8px 14px 14px;background:var(--surface-3)">
        ${diffHtml}
        <div style="margin-top:9px;font-size:10.5px;color:var(--ink-3);font-family:ui-monospace,monospace;word-break:break-all">
          entry_hash: ${GF.esc((e.entry_hash || '').slice(0, 24))}… · prev: ${GF.esc((e.prev_hash || '∅').slice(0, 16))}…</div>
      </div>
    </details>`;
  }).join('');
  return count + rows;
};

// Pure markup builder — no DOM access — so GF.views.audit can render an
// already-fetched page directly (H12) without going through renderAudit's
// getElementById + innerHTML side effect.
GF.WWF._auditMarkup = () => {
  const st = GF.WWF._audit, f = GF.WWF._auditFilter;

  const header = `<div style="display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:6px 4px 12px">
      <h2 style="margin:0;font-size:19px;font-weight:800;color:var(--ink)">${AL('Audit Trail', 'Ревизорска трага')}</h2>
      <span style="flex:1"></span>
      <button class="btn btn-sm" onclick="GF.WWF.loadAudit({reset:true})">${GF.icon('clock')}${AL('Refresh', 'Освежи')}</button>
    </div>`;

  // Chain + action facets become chip toggles (small, fully-visible option sets
  // — the mockup's filter treatment); the table facet stays a searchable popup
  // because it can list many tables. All three still drive the SERVER filter.
  const chainChips = [{ v: '', en: 'Both chains', mk: 'Двата синџири' }]
    .concat(Object.keys(AUDIT_SOURCES).map(s => ({ v: s, en: AUDIT_SOURCES[s].en, mk: AUDIT_SOURCES[s].mk })));
  const actChips = [{ v: '', en: 'All', mk: 'Сите' }]
    .concat(Object.keys(ACT).map(k => ({ v: k, en: ACT[k].en, mk: ACT[k].mk })));
  const chip = (key, cur, o) => `<button type="button" class="audit-fchip${String(o.v) === String(cur) ? ' on' : ''}" onclick="GF.WWF.setAuditFilter('${key}','${o.v}')">${GF.esc(AL(o.en, o.mk))}</button>`;

  const tableOptions = [{ v: '', label: AL('All tables', 'Сите табели') }]
    .concat((st.tables || []).map(t => ({ v: t.table_name, label: `${t.table_name} (${t.count})` })));

  const filters = `<div class="audit-filters">
      <div class="audit-fseg" role="group" aria-label="${GF.esc(AL('Chain', 'Синџир'))}">${chainChips.map(o => chip('source', f.source, o)).join('')}</div>
      <div class="audit-fseg" role="group" aria-label="${GF.esc(AL('Action', 'Дејство'))}">${actChips.map(o => chip('action', f.action, o)).join('')}</div>
      <div class="audit-tablesel">${GF.selectField('audit-f-table', { value: f.table_name || '', inline: true, searchable: true, title: AL('Table', 'Табела'), options: tableOptions, onPick: () => GF.WWF.applyAuditFilter() })}</div>
      <label class="audit-search">${GF.icon('search', 'icon')}<input id="audit-q" type="text" value="${GF.esc(st.query || '')}" oninput="GF.WWF.filterAudit()" placeholder="${GF.esc(AL('Search entity, actor, field…', 'Барај ентитет, корисник, поле…'))}" autocomplete="off"></label>
    </div>`;

  const more = st.hasMore
    ? `<div class="mw-pager" style="justify-content:center;margin-top:10px"><button onclick="GF.WWF.loadAudit({reset:false})">${AL('Load more', 'Вчитај повеќе')}</button></div>`
    : '';

  return header + GF.WWF._verifybarHtml() + filters
    + `<div id="audit-list">${GF.WWF._auditListHtml()}</div>` + more;
};

GF.WWF.renderAudit = () => {
  const v = GF.$('audit-view'); if (!v) return;
  v.innerHTML = GF.WWF._auditMarkup();
};

/* nav item + chrome hiding for the audit view (elevated roles only) */
GF.WWF._registerFullPageView({
  key: 'audit', icon: 'shield', label: () => AL('Audit Trail', 'Ревизија'),
  guard: GF.WWF.canAudit,
});
