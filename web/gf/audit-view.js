/* ══════════════════════════════════════════════════════════════════════
   Audit Trail — a general (non-QC) GxP capability adopted from the QC lab.
   Read-only, tamper-evident view of the hash-chained audit_log. Visible to
   elevated roles only (ADMIN / DEPT_HEAD / PROJECT_LEAD), which mirrors
   the DB `audit_read` policy.

   Split out of integrate.js (first decomposition cut of its monkey-patch
   pattern). Loads right after integrate.js — AL/AUDIT_ROLES declared below
   are bare top-level consts, visible to collab.js/report-view.js only
   because classic <script> tags share one lexical scope in document order.
   ════════════════════════════════════════════════════════════════════ */
const AL = (en, mk) => (GF.state && GF.state.lang === 'mk') ? mk : en;
const AUDIT_ROLES = ['ADMIN', 'DEPT_HEAD', 'PROJECT_LEAD'];
const ACT = {
  INSERT: { c: '#15A86B', en: 'Created', mk: 'Создадено' },
  UPDATE: { c: '#2F6BFF', en: 'Updated', mk: 'Изменето' },
  DELETE: { c: '#E5484D', en: 'Deleted', mk: 'Избришано' },
};
const AUDIT_HIDE = ['password_hash'];   // never surface secrets in the trail

GF.WWF.canAudit = () => AUDIT_ROLES.includes((GF.API.user || {}).role);
GF.WWF._audit = { entries: [], before: null, tables: null, verify: null, hasMore: false, gen: 0 };
GF.WWF._auditFilter = { table_name: '', action: '', source: '' };
// The two databases keep independent hash chains; every row carries which
// one it came from (identity events vs work events).
const AUDIT_SOURCES = {
  users: { c: '#C2410C', en: 'users', mk: 'корисници' },
  tasks: { c: '#2F6BFF', en: 'tasks', mk: 'задачи' },
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
    if (st.verify === null && (GF.API.user || {}).role === 'ADMIN') {
      try { st.verify = await GF.API.auditVerify(); } catch (e) { st.verify = { error: true }; }
    }
    GF.WWF.renderAudit();
  } catch (e) {
    const v = GF.$('audit-view');
    if (v) v.innerHTML = `<div style="padding:40px;text-align:center;color:#E5484D">${AL('Could not load audit trail', 'Не може да се вчита ревизија')}: ${GF.esc(e.message)}</div>`;
  }
};

GF.WWF.applyAuditFilter = () => {
  GF.WWF._auditFilter.table_name = (GF.$('audit-f-table') || {}).value || '';
  GF.WWF._auditFilter.action = (GF.$('audit-f-action') || {}).value || '';
  GF.WWF._auditFilter.source = (GF.$('audit-f-source') || {}).value || '';
  GF.WWF.loadAudit({ reset: true });
};

GF.WWF.renderAudit = () => {
  const v = GF.$('audit-view'); if (!v) return;
  const st = GF.WWF._audit, f = GF.WWF._auditFilter;

  // integrity badges (ADMIN only — /verify is ADMIN-guarded). Both databases
  // chain independently, so each gets its own verified/broken badge.
  let badge = '';
  if (st.verify && !st.verify.error) {
    badge = ['users', 'tasks'].map(src => {
      const v = st.verify[src]; if (!v) return '';
      return v.ok
        ? `<span style="display:inline-flex;align-items:center;gap:6px;background:#E6F7EF;color:#0F7A4D;font-weight:700;font-size:12px;padding:5px 11px;border-radius:999px">
             ${GF.icon('shield', 'icon', '#0F7A4D')} ${GF.esc(AL(AUDIT_SOURCES[src].en, AUDIT_SOURCES[src].mk))} ${AL('verified', 'потврден')} · ${v.total} ${AL('entries', 'записи')}</span>`
        : `<span style="display:inline-flex;align-items:center;gap:6px;background:#FDECEC;color:#C42121;font-weight:700;font-size:12px;padding:5px 11px;border-radius:999px">
             ${GF.icon('flag', 'icon', '#C42121')} ${GF.esc(AL(AUDIT_SOURCES[src].en, AUDIT_SOURCES[src].mk))} ${AL('chain broken at', 'прекин кај')} #${v.first_break_id}</span>`;
    }).join('');
  }

  // filters
  const tableOpts = `<option value="">${AL('All tables', 'Сите табели')}</option>` +
    (st.tables || []).map(t => `<option value="${GF.esc(t.table_name)}" ${f.table_name === t.table_name ? 'selected' : ''}>${GF.esc(t.table_name)} (${t.count})</option>`).join('');
  const actOpts = `<option value="">${AL('All actions', 'Сите дејства')}</option>` +
    Object.keys(ACT).map(a => `<option value="${a}" ${f.action === a ? 'selected' : ''}>${AL(ACT[a].en, ACT[a].mk)}</option>`).join('');
  const srcOpts = `<option value="">${AL('Both chains', 'Двата синџири')}</option>` +
    Object.keys(AUDIT_SOURCES).map(s => `<option value="${s}" ${f.source === s ? 'selected' : ''}>${AL(AUDIT_SOURCES[s].en, AUDIT_SOURCES[s].mk)}</option>`).join('');

  const toolbar = `
    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin:6px 4px 16px">
      <div style="display:flex;align-items:center;gap:10px;min-width:0">
        <h2 style="margin:0;font-size:19px;font-weight:800;color:var(--ink)">${AL('Audit Trail', 'Ревизорска трага')}</h2>
        ${badge}
      </div>
      <div style="flex:1"></div>
      <select id="audit-f-source" onchange="GF.WWF.applyAuditFilter()" class="audit-select" style="padding:8px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;font-size:13px">${srcOpts}</select>
      <select id="audit-f-table" onchange="GF.WWF.applyAuditFilter()" class="audit-select" style="padding:8px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;font-size:13px">${tableOpts}</select>
      <select id="audit-f-action" onchange="GF.WWF.applyAuditFilter()" class="audit-select" style="padding:8px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;font-size:13px">${actOpts}</select>
      <button class="btn btn-sm" onclick="GF.WWF.loadAudit({reset:true})">${GF.icon('clock')}${AL('Refresh', 'Освежи')}</button>
    </div>`;

  let rows;
  if (!st.entries.length) {
    rows = `<div style="padding:40px;text-align:center;color:var(--ink-3)">${AL('No audit entries match.', 'Нема записи.')}</div>`;
  } else {
    rows = st.entries.map(e => {
      const a = ACT[e.action] || { c: '#5A6B82', en: e.action, mk: e.action };
      const src = AUDIT_SOURCES[e.source];
      const srcBadge = src ? `<span class="audit-src" style="background:${src.c}14;color:${src.c};font-weight:800;font-size:10px;letter-spacing:.4px;text-transform:uppercase;padding:3px 7px;border-radius:5px;white-space:nowrap">${GF.esc(AL(src.en, src.mk))}</span>` : '';
      const when = e.created_at ? new Date(e.created_at).toLocaleString() : '';
      const diff = GF.WWF._auditDiff(e);
      const diffHtml = diff.length ? diff.map(([k, ov, nv]) => `
        <div style="display:grid;grid-template-columns:170px 1fr;gap:8px;padding:4px 0;border-top:1px dashed var(--line);font-size:12.5px">
          <div style="font-weight:600;color:var(--ink-2);font-family:ui-monospace,monospace">${GF.esc(k)}</div>
          <div style="min-width:0">
            ${e.action !== 'INSERT' ? `<span style="color:#C42121;text-decoration:${e.action === 'DELETE' ? 'none' : 'line-through'}">${GF.esc(GF.WWF._auditTrunc(ov))}</span>` : ''}
            ${e.action === 'UPDATE' ? '<span style="color:var(--ink-3);margin:0 6px">→</span>' : ''}
            ${e.action !== 'DELETE' ? `<span style="color:#0F7A4D">${GF.esc(GF.WWF._auditTrunc(nv))}</span>` : ''}
          </div>
        </div>`).join('') : `<div style="font-size:12.5px;color:var(--ink-3);padding:4px 0">${AL('No field-level changes recorded.', 'Нема промени на полиња.')}</div>`;
      return `
      <details class="audit-entry" style="background:#fff;border:1px solid var(--line);border-radius:11px;margin-bottom:8px;overflow:hidden">
        <summary style="display:flex;align-items:center;gap:12px;padding:11px 14px;cursor:pointer;list-style:none">
          <span style="font-size:11.5px;color:var(--ink-3);white-space:nowrap;min-width:148px">${GF.esc(when)}</span>
          ${srcBadge}
          <span style="background:${a.c}1A;color:${a.c};font-weight:700;font-size:11px;padding:3px 9px;border-radius:6px;white-space:nowrap">${GF.esc(AL(a.en, a.mk))}</span>
          <span style="font-weight:700;font-size:13px;color:var(--ink);font-family:ui-monospace,monospace">${GF.esc(e.table_name || '—')}</span>
          <span style="font-size:12px;color:var(--ink-3);font-family:ui-monospace,monospace">#${GF.esc(String(e.record_id || '').slice(0, 8))}</span>
          <span style="flex:1"></span>
          <span style="font-size:12.5px;color:var(--ink-2)">${GF.icon('user')}&nbsp;${GF.esc(GF.WWF._auditActor(e))}</span>
        </summary>
        <div style="padding:8px 14px 14px;background:#FAFBFC">
          ${diffHtml}
          <div style="margin-top:9px;font-size:10.5px;color:var(--ink-3);font-family:ui-monospace,monospace;word-break:break-all">
            entry_hash: ${GF.esc((e.entry_hash || '').slice(0, 24))}… · prev: ${GF.esc((e.prev_hash || '∅').slice(0, 16))}…</div>
        </div>
      </details>`;
    }).join('');
  }

  const more = st.hasMore
    ? `<div style="text-align:center;margin-top:10px"><button class="btn" onclick="GF.WWF.loadAudit({reset:false})">${AL('Load more', 'Вчитај повеќе')}</button></div>`
    : '';

  v.innerHTML = toolbar + `<div id="audit-list">${rows}</div>` + more;
};

/* nav item + chrome hiding for the audit view (elevated roles only) */
GF.WWF._registerFullPageView({
  key: 'audit', icon: 'shield', label: () => AL('Audit Trail', 'Ревизија'),
  guard: GF.WWF.canAudit,
});
