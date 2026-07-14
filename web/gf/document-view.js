/* document-view.js — weekly Plan/Report DOCUMENT panel: compile → review →
   lock → export PDF. Renders into #report-doc inside the report view.
   The ribbon draws every logged work session over its real local-time extent
   (7 day-rows × 24h), color-keyed by SOP reference code. Load order: after
   report-view.js (extends the same GF.WWF namespace). */
window.GF = window.GF || {}; GF.WWF = GF.WWF || {};

// deptId: '' = org-wide document. Executives/ADMIN/QP pick via the panel's
// department selector; dept-scoped managers never send it (the server forces
// their department regardless — GF.WWF.deptScope() drives the fixed chip UI).
GF.WWF._doc = { data: null, loading: false, error: null, _seq: 0, rangeStart: '', rangeEnd: '', deptId: '' };

GF.WWF._docDeptParam = () => {
  if (GF.WWF.deptScope && GF.WWF.deptScope()) return undefined;  // server forces it
  return GF.WWF._doc.deptId || undefined;
};

GF.WWF.setDocDept = (v) => { GF.WWF._doc.deptId = v || ''; GF.WWF.loadDocument(); };

GF.WWF.loadDocument = async () => {
  const st = GF.WWF._report, ds = GF.WWF._doc;
  const seq = ++ds._seq;   // only the newest load may write state (no last-response-wins races)
  ds.loading = true; ds.error = null; GF.WWF._renderDocPanel();
  try {
    const q = { kind: st.mode };
    if (st.refDate) q.ref_date = st.refDate;
    const dept = GF.WWF._docDeptParam(); if (dept) q.department_id = dept;
    const data = await GF.API.getDocument(q);
    if (seq !== ds._seq) return;            // a newer load/compile/lock superseded this one
    ds.data = data;
    ds.error = null;
  } catch (e) {
    if (seq !== ds._seq) return;
    if (e && e.status === 404) { ds.data = null; ds.error = null; }  // 404 = nothing compiled yet (normal)
    else { ds.error = e.message || String(e); }  // 500/network/403: surface it — do NOT offer to recompile over an existing draft
  }
  ds.loading = false;
  GF.WWF._renderDocPanel();
};

GF.WWF.compileDocument = async () => {
  const st = GF.WWF._report, ds = GF.WWF._doc;
  // Recompiling an existing draft overwrites stored content and discards any
  // saved manual edits — confirm first. The initial compile (no stored row) is
  // safe and never prompts.
  if (ds.data && ds.data.id && ds.data.status === 'draft'
      && !confirm(AL('Recompiling rebuilds this draft and discards your saved manual edits. Continue?',
                     'Повторното составување го обновува овој нацрт и ги отфрла вашите зачувани рачни измени. Продолжи?'))) return;
  ds.loading = true; ds.error = null; GF.WWF._renderDocPanel();
  try {
    const data = await GF.API.compileDocument({ kind: st.mode, ref_date: st.refDate || undefined,
                                                department_id: GF.WWF._docDeptParam() });
    ds._seq++; ds.data = data; ds.error = null;   // authoritative new state; bail any in-flight load
    GF.toast(AL('Document compiled', 'Документот е составен'), 'success');
  } catch (e) {
    GF.toast(AL('Compile failed: ', 'Неуспешно составување: ') + e.message, 'error');
  }
  ds.loading = false;
  GF.WWF._renderDocPanel();
};

// Custom-range preview: draft a report/plan for an arbitrary start→end interval
// WITHOUT persisting it (for looking ahead before the scheduled submission day).
// The scheduled Fri→Thu week stays the only stored/lockable record — this is a
// throwaway draft the user can review + export to PDF.
GF.WWF.previewDocument = async () => {
  const st = GF.WWF._report, ds = GF.WWF._doc;
  const start = (ds.rangeStart || '').trim(), end = (ds.rangeEnd || '').trim();
  if (!start || !end) { GF.toast(AL('Pick a start and end date', 'Изберете почетен и краен датум'), 'error'); return; }
  if (end < start) { GF.toast(AL('End date is before start date', 'Крајниот датум е пред почетниот'), 'error'); return; }
  ds.loading = true; ds.error = null; GF.WWF._renderDocPanel();
  try {
    const data = await GF.API.previewDocument({ kind: st.mode, start, end,
                                                department_id: GF.WWF._docDeptParam() });
    ds._seq++; ds.data = data; ds.error = null;   // authoritative; bail any in-flight load
    GF.toast(AL('Preview generated', 'Прегледот е генериран'), 'success');
  } catch (e) {
    GF.toast(AL('Preview failed: ', 'Неуспешен преглед: ') + e.message, 'error');
  }
  ds.loading = false;
  GF.WWF._renderDocPanel();
};

/* ── section editing ─────────────────────────────────────────────────────
   Every AI narrative (EN + MK) and every template-section field/narrative is
   editable while the document is a DRAFT. Values are read from the DOM at
   save time (data-sec / data-f / data-field attributes) — the panel is an
   innerHTML rebuild, so re-rendering on keystroke would eat input. Approving
   a section SAVES its current inputs in the same PATCH, and unsaved edits in
   OTHER sections are collected and re-applied after the server copy is
   adopted, so nothing typed is ever lost to a re-render. */

GF.WWF._collectDocInputs = () => {
  const root = GF.$('report-doc'); const out = {};
  if (!root) return out;
  root.querySelectorAll('[data-sec]').forEach(el => {
    const key = el.dataset.sec, p = out[key] = out[key] || {};
    if (el.dataset.field) { (p.fields = p.fields || {})[el.dataset.field] = el.value; }
    else if (el.dataset.f) { p[el.dataset.f] = el.value; }
  });
  return out;
};

GF.WWF._applyDocInputs = (content, inputs, skipKey) => {
  const apply = (sec, p) => {
    if (p.body_en !== undefined) { sec.body_en = p.body_en; sec.body = p.body_en; }
    if (p.body_mk !== undefined) sec.body_mk = p.body_mk;
    if (p.narrative_en !== undefined || p.narrative_mk !== undefined) {
      sec.narrative = sec.narrative || { en: '', mk: '' };
      if (p.narrative_en !== undefined) sec.narrative.en = p.narrative_en;
      if (p.narrative_mk !== undefined) sec.narrative.mk = p.narrative_mk;
    }
    if (p.fields) (sec.fields || []).forEach(f => {
      if (p.fields[f.key] !== undefined) f.value = p.fields[f.key];
    });
  };
  Object.entries(inputs).forEach(([key, p]) => {
    if (key === skipKey) return;   // the just-saved section: server copy is canonical
    const sec = (content.ai_sections || []).find(s => s.key === key)
             || (content.template_sections || []).find(s => s.key === key);
    if (sec) apply(sec, p);
  });
};

// Render an AI narrative body: escape-first, then a fixed markdown-lite
// whitelist (## headings, **bold**, [task:xxxxxxxx] citations — the agents
// emit these even when asked for plain prose). Citations that match a loaded
// task become deep links into the board (via the same xrJump the executive
// report uses); unknown ids stay inert chips. The backend's _md_lite is the
// export-side twin of this — keep them in step.
GF.WWF.aiHtml = (text) => {
  let t = GF.esc(String(text || ''));
  t = t.replace(/^#{1,4}\s+(.+)$/gm, '<b style="display:block;font-size:13.5px;margin:7px 0 2px">$1</b>');
  // An odd count of "**" means an unclosed bold marker would otherwise pair
  // with the NEXT legitimate opening marker, bolding everything in between —
  // leave the markers literal rather than scramble the sentence.
  if ((t.match(/\*\*/g) || []).length % 2 === 0) {
    t = t.replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>');
  }
  // Built once per call, not per citation match, and matched on the FULL
  // cited ref (not pre-truncated) so this resolves identically to the
  // backend's _md_lite for the same narrative + task list.
  const pool = ((GF.state && GF.state.tasks) ? GF.state.tasks : [])
    .concat((GF.state && GF.state.childrenByParent) ? Object.values(GF.state.childrenByParent).flat() : [])
    .map(x => String(x.id || '').toLowerCase())
    .filter(Boolean)
    .sort();
  t = t.replace(/\[task:([0-9a-fA-F-]{4,36})\]/g, (_, ref) => {
    const refLc = ref.toLowerCase();
    const short = refLc.slice(0, 8);
    const full = pool.find(id => id.startsWith(refLc));
    const chip = 'background:rgba(43,232,160,.10);border:1px solid rgba(43,232,160,.25);border-radius:7px;'
               + 'padding:0 5px;font-size:11px;font-family:ui-monospace,monospace;color:#2BE8A0';
    // L4 (defense-in-depth): `full` is resolved from GF.state task ids (always
    // UUIDs) and every interpolation already goes through GF.esc, but the id
    // lands inside an inline onclick JS-string — so require a clean UUID shape
    // before emitting the clickable link. Anything else degrades to the inert
    // chip below rather than risk a malformed handler.
    const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
    if (full && uuidRe.test(full) && GF.WWF.xrJump) {
      const hit = GF.task ? GF.task(full) : null;
      const weekStart = hit ? (hit.week_start || hit.weekStart || '') : '';
      return `<a href="#" style="${chip};cursor:pointer;text-decoration:none" `
           + `onclick="GF.WWF.xrJump('${GF.esc(full)}','${GF.esc(weekStart)}');return false">задача/task ${GF.esc(short)}</a>`;
    }
    return `<span style="${chip}">задача/task ${GF.esc(short)}</span>`;
  });
  return t;
};

// Bulk-approve: flip every not-yet-approved section (AI + template) in one
// pass, reusing the per-section endpoint sequentially — before locking, the
// reviewer otherwise ticks up to 10 checkboxes one by one. (approvals.html
// mockup adoption, scoped to the one approval flow the app actually has.)
GF.WWF.approveAllSections = async () => {
  const ds = GF.WWF._doc;
  const c = ds.data && ds.data.content;
  if (!c || ds.data.status !== 'draft') return;
  const keys = [
    ...(c.ai_sections || []).filter(s => !s.approved && (s.body_en || s.body || s.body_mk)).map(s => s.key),
    ...(c.template_sections || []).filter(s => !s.approved).map(s => s.key),
  ];
  if (!keys.length) { GF.toast(AL('Everything is already approved', 'Сè е веќе одобрено'), 'info'); return; }
  let ok = 0;
  for (const key of keys) {
    try { await GF.WWF.saveDocSection(key, true); ok++; }
    catch (e) { GF.toast(AL('Failed on ', 'Неуспешно на ') + key + ': ' + e.message, 'error'); break; }
  }
  if (ok) GF.toast(AL(`Approved ${ok} section(s)`, `Одобрени ${ok} секции`), 'success');
};

// Save one section's inputs; optionally flip `approved` in the same PATCH.
GF.WWF.saveDocSection = async (key, approved) => {
  const ds = GF.WWF._doc;
  if (!ds.data || ds.data.status !== 'draft') return;
  const inputs = GF.WWF._collectDocInputs();
  const patch = Object.assign({}, inputs[key] || {});
  if (approved !== undefined) patch.approved = approved;
  try {
    const data = await GF.API.patchDocumentSection(ds.data.id, key, patch);
    ds._seq++; ds.data = data;                       // adopt the server's canonical copy
    GF.WWF._applyDocInputs(ds.data.content || {}, inputs, key);  // keep other sections' unsaved edits
    if (approved === undefined) GF.toast(AL('Section saved', 'Секцијата е зачувана'), 'success');
  } catch (e) {
    GF.toast(AL('Not saved: ', 'Не се зачува: ') + e.message, 'error');
  }
  GF.WWF._renderDocPanel();
};

GF.WWF.lockDocument = async () => {
  const ds = GF.WWF._doc;
  if (!ds.data) return;
  if (!confirm(AL(
    'Lock this document as the submitted record for the week? It becomes immutable.',
    'Да се заклучи документот како поднесен запис за неделата? Станува непроменлив.'))) return;
  try {
    const data = await GF.API.lockDocument(ds.data.id);
    ds._seq++; ds.data = data;
    GF.toast(AL('Document locked', 'Документот е заклучен'), 'success');
  } catch (e) { GF.toast(AL('Lock failed: ', 'Неуспешно заклучување: ') + e.message, 'error'); }
  GF.WWF._renderDocPanel();
};

/* ── shared authenticated file download (PDF / standalone HTML) ──
   One owner of the raw-fetch → blob → <a download> flow, the 401 → re-login
   routing, the Content-Disposition filename adoption, and the demo-mode
   guard. Also used by execreport-view.js. */
GF.WWF._fetchDownload = async (path, fallbackName, init) => {
  if (GF.DEMO && GF.DEMO.active && GF.DEMO.active()) {
    GF.toast(AL('File export is not available in demo mode — on the live system this downloads the document.',
                'Извозот на датотеки не е достапен во демо режим — во живата апликација се презема документот.'), 'info');
    return;
  }
  const res = await fetch(GF.API.base + path, Object.assign(
    { headers: { Authorization: 'Bearer ' + GF.API.token } }, init || {}));
  if (res.status === 401) {
    // Route an expired token back to the login overlay, same as GF.API._req —
    // a raw fetch here would otherwise strand the user behind a toast.
    GF.API.logout();
    if (GF.WWF.showLogin) GF.WWF.showLogin();
    throw new Error(AL('Session expired', 'Сесијата истече'));
  }
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const blob = await res.blob();
  // Take the filename from the server's Content-Disposition (single owner of
  // the naming + DRAFT-suffix policy); fall back only if the header is absent.
  const cd = res.headers.get('content-disposition') || '';
  const m = /filename="?([^"]+)"?/.exec(cd);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = (m && m[1]) || fallbackName;
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 800);
};

GF.WWF.exportDocumentPdf = async () => {
  const ds = GF.WWF._doc;
  if (!ds.data) return;
  // A custom-range preview has no stored row (id === null) — POST the reviewed
  // content back to the range-export endpoint; a saved week doc exports by id.
  const isPreview = ds.data.status === 'preview' || !ds.data.id;
  const fallback = 'wwf-' + ds.data.kind + '-' + ds.data.week_start
    + (ds.data.status === 'locked' ? '' : '-DRAFT') + '.pdf';
  try {
    if (isPreview) {
      await GF.WWF._fetchDownload('/reports/documents/export-range.pdf', fallback,
        { method: 'POST', headers: { Authorization: 'Bearer ' + GF.API.token, 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: ds.data.kind, content: ds.data.content }) });
    } else {
      await GF.WWF._fetchDownload('/reports/documents/' + ds.data.id + '/export.pdf', fallback);
    }
  } catch (e) { GF.toast(AL('Export failed: ', 'Неуспешен извоз: ') + e.message, 'error'); }
};

// Standalone interactive HTML snapshot — stored documents only (a preview has
// no row to export; the offline artifact is for the submitted/draft record).
GF.WWF.exportDocumentHtml = async () => {
  const ds = GF.WWF._doc;
  if (!ds.data) return;
  if (ds.data.status === 'preview' || !ds.data.id) {
    GF.toast(AL('HTML export works on the stored week document — compile it first.',
                'HTML извозот работи на зачуваниот неделен документ — прво составете го.'), 'info');
    return;
  }
  try {
    await GF.WWF._fetchDownload('/reports/documents/' + ds.data.id + '/export.html',
      'wwf-' + ds.data.kind + '-' + ds.data.week_start + '.html');
  } catch (e) {
    if (/HTTP 40(4|5)/.test(e.message || '')) {
      GF.toast(AL('HTML export needs the newer backend — deploy it first.',
                  'HTML извозот бара понов backend — прво деплојирајте.'), 'info');
    } else { GF.toast(AL('Export failed: ', 'Неуспешен извоз: ') + e.message, 'error'); }
  }
};

/* ── ribbon: 7 day-rows × 24h, sessions as SOP-colored bars ──
   Theme-adaptive live-panel renderer (uses --line/--surface CSS vars so it
   follows light/dark). The PDF has a second, static renderer (_ribbon_svg in
   backend/app/api/documents.py) — deliberately two, for two output targets.
   RECORD-critical geometry MUST match the backend: day-row by date, x =
   start_h*hw, width = max(2, (end_h-start_h)*hw), fill = seg.color. Both draw
   from the same content.ribbon segments, so the record can't drift. */
GF.WWF._ribbonSvg = (segments, weekStart, days) => {
  if (!segments || !segments.length) return '';
  const n = Math.max(1, Math.min(days || 7, 92));   // one row per day (7 for a week)
  const W = 860, ROW = 36, LEFT = 70, TOP = 22, H = TOP + n * ROW + 14;
  const hw = (W - LEFT - 10) / 24;
  const d0 = new Date(weekStart + 'T00:00:00');
  let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto" xmlns="http://www.w3.org/2000/svg">`;
  for (let h = 0; h <= 24; h += 3) {
    const x = LEFT + h * hw;
    s += `<line x1="${x}" y1="${TOP - 4}" x2="${x}" y2="${H - 12}" stroke="var(--line,rgba(43,232,160,.12))" stroke-width="1"/>`
      + `<text x="${x}" y="${TOP - 8}" font-size="9" fill="var(--ink-3,#5F8575)" text-anchor="middle">${String(h).padStart(2, '0')}</text>`;
  }
  for (let i = 0; i < n; i++) {
    const d = new Date(d0); d.setDate(d0.getDate() + i);
    const iso = GF.localDateStr(d);
    const y = TOP + i * ROW;
    const lbl = d.toLocaleDateString(GF.state.lang === 'mk' ? 'mk-MK' : 'en-GB', { weekday: 'short', day: '2-digit', month: '2-digit' });
    s += `<text x="4" y="${y + ROW / 2 + 3}" font-size="10" fill="var(--ink,#DDF3E9)">${GF.esc(lbl)}</text>`
      + `<rect x="${LEFT}" y="${y + 4}" width="${W - LEFT - 10}" height="${ROW - 8}" rx="4" fill="var(--surface-2,#102219)"/>`;
    segments.forEach(seg => {
      if (seg.date !== iso) return;
      const x = LEFT + seg.start_h * hw, w = Math.max(2, (seg.end_h - seg.start_h) * hw);
      s += `<rect x="${x.toFixed(1)}" y="${y + 6}" width="${w.toFixed(1)}" height="${ROW - 12}" rx="3" fill="${seg.color}" fill-opacity="0.92">`
        + `<title>${GF.esc(seg.title)} · ${GF.esc(seg.sop)} · ${seg.hours}h (${seg.start.slice(11, 16)}–${seg.end.slice(11, 16)})</title></rect>`;
    });
  }
  s += '</svg>';
  return s;
};

GF.WWF._docMetricsHtml = (m) => {
  if (!m || !m.per_sop || !m.per_sop.length) return '';
  const rows = m.per_sop.map(b => {
    const delta = b.prev4_avg_hours ? Math.round(((b.hours - b.prev4_avg_hours) / b.prev4_avg_hours) * 100) : null;
    const trend = delta === null ? '—' : (delta >= 0 ? '+' : '') + delta + '%';
    return `<tr>
      <td><span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${b.color};margin-right:6px;vertical-align:middle"></span>${GF.esc(b.sop)}</td>
      <td style="text-align:right;font-weight:700">${b.hours}h</td>
      <td style="text-align:right;color:var(--ink-3)">${b.prev4_avg_hours}h</td>
      <td style="text-align:right;color:${delta > 25 ? '#E5484D' : 'var(--ink-2)'}">${trend}</td>
      <td style="text-align:right">${b.tasks}</td>
      <td style="text-align:right;color:${(b.night + b.weekend) > 0 ? '#E0A73E' : 'var(--ink-3)'}">${(b.night + b.weekend + b.overtime).toFixed(1)}h</td>
    </tr>`;
  }).join('');
  const ot = m.on_time || {};
  return `<div style="margin:14px 0">
    <div style="font-weight:700;font-size:14px;margin-bottom:8px">${AL('Metrics by SOP', 'Метрики по СОП')}</div>
    <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12.5px">
      <tr style="color:var(--ink-3);font-size:11px;text-transform:uppercase;letter-spacing:.04em">
        <th style="text-align:left;padding:4px 6px">${AL('SOP / area', 'СОП / област')}</th>
        <th style="text-align:right;padding:4px 6px">${AL('Hours', 'Часови')}</th>
        <th style="text-align:right;padding:4px 6px">${AL('4-wk avg', '4-нед. просек')}</th>
        <th style="text-align:right;padding:4px 6px">Δ</th>
        <th style="text-align:right;padding:4px 6px">${AL('Tasks', 'Задачи')}</th>
        <th style="text-align:right;padding:4px 6px">${AL('Off-hours', 'Вон работно')}</th>
      </tr>${rows}</table></div>
    ${ot.completed ? `<div style="font-size:12px;color:var(--ink-2);margin-top:6px">${AL('On-time completion', 'Навремено завршени')}: <b>${ot.on_time}/${ot.measured != null ? ot.measured : ot.completed}</b> ${AL('with deadlines', 'со рокови')}${ot.rate != null ? ' (' + Math.round(ot.rate * 100) + '%)' : ''} · ${ot.completed} ${AL('completed', 'завршени')}</div>` : ''}
  </div>`;
};

GF.WWF._renderDocPanel = () => {
  const el = GF.$('report-doc'); if (!el) return;
  const ds = GF.WWF._doc, st = GF.WWF._report;
  // Reuse integrate.js's shared ELEVATED_ROLES (same classic-script scope) so a
  // new non-elevated role can't slip past a hand-rolled `!== 'USER'` check and
  // show Compile/Lock buttons that then 403 on the backend's require_role gate.
  const elevated = ELEVATED_ROLES.includes((GF.API.user || {}).role);
  const kindLbl = st.mode === 'plan' ? AL('Plan document', 'Документ План') : AL('Report document', 'Документ Извештај');

  // Custom-range control (elevated only): draft a report/plan for ANY interval
  // ahead of the scheduled submission day. Produces a non-persisted preview the
  // user can review + export; the scheduled Fri→Thu week stays the only stored,
  // lockable record. Values live in GF.WWF._doc so they survive re-render.
  const inStyle = 'font:inherit;padding:5px 8px;border:1px solid var(--line,rgba(43,232,160,.12));border-radius:7px;background:var(--surface,#0B1913);color:var(--ink,#DDF3E9)';
  const rangeControls = elevated ? `
    <div style="padding:10px 14px;border-bottom:1px solid var(--line,#E2E8F0);display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12.5px">
      <span style="color:var(--ink-3);font-weight:600">${AL('Custom range', 'Прилагоден опсег')}</span>
      <input type="date" value="${GF.esc(ds.rangeStart || '')}" onchange="GF.WWF._doc.rangeStart=this.value" style="${inStyle}">
      <span style="color:var(--ink-3)">→</span>
      <input type="date" value="${GF.esc(ds.rangeEnd || '')}" onchange="GF.WWF._doc.rangeEnd=this.value" style="${inStyle}">
      <button class="btn btn-sm btn-primary" onclick="GF.WWF.previewDocument()">${AL('Generate preview', 'Генерирај преглед')}</button>
      <span style="color:var(--ink-3);font-size:11px">${AL('unsaved draft for any interval', 'незачуван нацрт за секој интервал')}</span>
    </div>` : '';

  let body;
  if (ds.loading) {
    body = `<div style="padding:16px;color:var(--ink-3)">${AL('Working…', 'Се работи…')}</div>`;
  } else if (ds.error) {
    // A real failure (500/network/permission) — NOT the empty state. Offer a
    // retry, never a Compile button that could overwrite an existing draft.
    body = `<div style="padding:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <span style="color:#B45309;font-size:13px">${AL('Couldn’t load the document: ', 'Не може да се вчита документот: ')}${GF.esc(ds.error)}</span>
      <button class="btn btn-sm" onclick="GF.WWF.loadDocument()">${AL('Retry', 'Обиди се повторно')}</button>
    </div>`;
  } else if (!ds.data) {
    body = `<div style="padding:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <span style="color:var(--ink-3);font-size:13px">${AL('No document compiled for this week yet.', 'Сè уште нема составен документ за оваа недела.')}</span>
      ${elevated ? `<button class="btn btn-sm btn-primary" onclick="GF.WWF.compileDocument()">${AL('Compile document', 'Состави документ')}</button>` : ''}
    </div>`;
  } else {
    const d = ds.data;
    const c = d.content || {};
    const isPreview = d.status === 'preview';   // non-persisted custom-range draft
    const locked = d.status === 'locked';
    const chip = isPreview
      ? `<span style="background:rgba(47,217,217,.12);color:#2FD9D9;font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px;border:1px solid rgba(47,217,217,.25)">${AL('PREVIEW — not saved', 'ПРЕГЛЕД — незачуван')}${c.period && c.period.label ? ' · ' + GF.esc(c.period.label) : ''}</span>`
      : locked
      ? `<span style="background:rgba(43,232,160,.12);color:#2BE8A0;font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px;border:1px solid rgba(43,232,160,.25)">${AL('LOCKED — submitted record', 'ЗАКЛУЧЕН — поднесен запис')}${d.locked_at ? ' · ' + d.locked_at.slice(0, 16).replace('T', ' ') : ''}</span>`
      : `<span style="background:rgba(224,167,62,.12);color:#E0A73E;font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px;border:1px solid rgba(224,167,62,.25)">${AL('DRAFT', 'НАЦРТ')}</span>`;
    // A section is editable only on a stored draft (preview has no row to
    // PATCH; locked is immutable). Read rule: body_en falls back to legacy
    // `body` so pre-v2 drafts/locked docs render.
    const editable = !isPreview && !locked;
    const ta = (key, f, val, ph) => `<textarea data-sec="${GF.esc(key)}" data-f="${f}" placeholder="${ph}"
        style="width:100%;box-sizing:border-box;min-height:64px;margin-top:5px;font:inherit;font-size:12.5px;line-height:1.55;
        padding:7px 9px;border:1px solid var(--line,rgba(43,232,160,.12));border-radius:8px;
        background:var(--surface-2,#102219);color:var(--ink,#DDF3E9);resize:vertical">${GF.esc(val || '')}</textarea>`;
    const langLbl = (t) => `<div style="font-size:9.5px;font-weight:800;letter-spacing:.5px;color:var(--ink-3);margin-top:7px">${t}</div>`;
    const approveCtl = (key, ok, label) => editable
      ? `<label style="font-size:12px;display:flex;align-items:center;gap:5px;cursor:pointer">
          <input type="checkbox" ${ok ? 'checked' : ''} onchange="GF.WWF.saveDocSection('${GF.esc(key)}', this.checked)">
          ${label || AL('Approve for document', 'Одобри за документот')}</label>`
      : (isPreview ? ''
        : (ok ? `<span style="font-size:11px;color:#2BE8A0;font-weight:700">${AL('Approved', 'Одобрено')}</span>`
              : `<span style="font-size:11px;color:var(--ink-3)">${AL('Not included', 'Не е вклучено')}</span>`));
    const saveBtn = (key) => editable
      ? `<button class="btn btn-sm" onclick="GF.WWF.saveDocSection('${GF.esc(key)}')">${AL('Save section', 'Зачувај секција')}</button>` : '';

    const sections = (c.ai_sections || []).map((s) => {
      // not_configured = no AI agent bound. In a draft it's a normal editable
      // section the user fills in by hand; when locked/preview with no content
      // written there is nothing to show, so keep it hidden.
      if (s.status === 'not_configured' && !editable && !(s.body_en || s.body || s.body_mk)) return '';
      const ok = !!s.approved;
      const bodyEn = s.body_en || s.body || '', bodyMk = s.body_mk || '';
      const bodyHtml = editable
        ? langLbl('EN') + ta(s.key, 'body_en', bodyEn, AL('English narrative…', 'Наратив на англиски…'))
          + langLbl('МК') + ta(s.key, 'body_mk', bodyMk, AL('Macedonian narrative…', 'Наратив на македонски…'))
        : (bodyEn ? `${langLbl('EN')}<div style="font-size:13px;line-height:1.6;white-space:pre-wrap;color:var(--ink)">${GF.WWF.aiHtml(bodyEn)}</div>` : '')
          + (bodyMk ? `${langLbl('МК')}<div style="font-size:13px;line-height:1.6;white-space:pre-wrap;color:var(--ink)">${GF.WWF.aiHtml(bodyMk)}</div>` : '');
      return `<div style="border:1px solid var(--line,rgba(43,232,160,.12));border-radius:9px;padding:10px 12px;margin:8px 0;background:${ok ? 'rgba(43,232,160,.06)' : 'var(--surface,#0B1913)'}">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <b style="font-size:13px">${GF.esc(s.title)}</b>
          <span style="font-size:10.5px;color:var(--ink-3)">${s.status === 'unavailable' ? AL('agent unavailable — write it by hand', 'агентот е недостапен — напишете рачно') : (s.status === 'not_configured' ? AL('No AI agent bound — write this section manually', 'Нема поврзан AI агент — пополнете рачно') : '')}</span>
          <div style="flex:1"></div>
          ${saveBtn(s.key)}
          ${approveCtl(s.key, ok)}
        </div>
        ${bodyHtml}
      </div>`;
    }).join('');

    // Per-department GMP template sections (content v2): metric grid + bilingual
    // narrative, all editable in draft. v1 documents have none → block hidden.
    const inSt = 'font:inherit;font-size:12.5px;padding:5px 8px;border:1px solid var(--line,rgba(43,232,160,.12));border-radius:7px;background:var(--surface-2,#102219);color:var(--ink,#DDF3E9);width:100%;box-sizing:border-box';
    const tsections = (c.template_sections || []).map((s) => {
      const ok = !!s.approved;
      const nar = s.narrative || {};
      const rows = (s.fields || []).map(f => `
        <div style="display:flex;align-items:center;gap:10px;padding:3px 0">
          <span style="flex:0 0 46%;min-width:0;font-size:12px;color:var(--ink-2)">${GF.esc(AL(f.label_en, f.label_mk))}</span>
          ${editable
            ? `<input data-sec="${GF.esc(s.key)}" data-field="${GF.esc(f.key)}" value="${GF.esc(f.value || '')}" style="${inSt};flex:1">`
            : `<span style="flex:1;font-size:12.5px;color:var(--ink)">${GF.esc(f.value || '—')}</span>`}
          ${f.unit ? `<span style="flex-shrink:0;font-size:11px;color:var(--ink-3)">${GF.esc(f.unit)}</span>` : ''}
        </div>`).join('');
      const narHtml = editable
        ? langLbl('EN') + ta(s.key, 'narrative_en', nar.en, AL('Narrative (English)…', 'Наратив (англиски)…'))
          + langLbl('МК') + ta(s.key, 'narrative_mk', nar.mk, AL('Narrative (Macedonian)…', 'Наратив (македонски)…'))
        : (nar.en ? `${langLbl('EN')}<div style="font-size:12.5px;line-height:1.55;white-space:pre-wrap;color:var(--ink)">${GF.WWF.aiHtml(nar.en)}</div>` : '')
          + (nar.mk ? `${langLbl('МК')}<div style="font-size:12.5px;line-height:1.55;white-space:pre-wrap;color:var(--ink)">${GF.WWF.aiHtml(nar.mk)}</div>` : '');
      return `<div style="border:1px solid var(--line,rgba(43,232,160,.12));border-radius:9px;padding:10px 12px;margin:8px 0;background:${ok ? 'rgba(43,232,160,.06)' : 'var(--surface,#0B1913)'}">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px">
          <b style="font-size:13px">${GF.esc(s.title_en || '')}</b>
          <span style="font-size:11px;color:var(--ink-3)">${GF.esc(s.title_mk || '')}</span>
          <div style="flex:1"></div>
          ${saveBtn(s.key)}
          ${approveCtl(s.key, ok, AL('Approve narrative', 'Одобри наратив'))}
        </div>
        ${rows}
        ${narHtml}
      </div>`;
    }).join('');
    const ribbonLbl = isPreview ? AL('Activity ribbon — logged work by SOP', 'Лента на активност — работа по СОП')
                                : AL('Week ribbon — logged work by SOP', 'Неделна лента — работа по СОП');
    body = `<div style="padding:14px 16px">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px">
        ${chip}
        <span style="font-size:12px;color:var(--ink-3)">${(c.tasks || []).length} ${AL('tasks', 'задачи')} · ${(c.ribbon || []).length} ${AL('logged sessions', 'сесии')}</span>
        <div style="flex:1"></div>
        ${isPreview && elevated ? `<button class="btn btn-sm" onclick="GF.WWF.previewDocument()">${AL('Regenerate', 'Регенерирај')}</button>` : ''}
        ${!isPreview && !locked && elevated ? `<button class="btn btn-sm" onclick="GF.WWF.compileDocument()">${AL('Recompile', 'Состави повторно')}</button>` : ''}
        ${!isPreview && !locked && elevated ? `<button class="btn btn-sm" onclick="GF.WWF.approveAllSections()">${AL('Approve all sections', 'Одобри ги сите секции')}</button>` : ''}
        <button class="btn btn-sm" onclick="GF.WWF.exportDocumentPdf()">${AL('Export PDF', 'Извези PDF')}</button>
        ${!isPreview ? `<button class="btn btn-sm" onclick="GF.WWF.exportDocumentHtml()">${AL('Export HTML', 'Извези HTML')}</button>` : ''}
        ${!isPreview && !locked && elevated ? `<button class="btn btn-sm" style="background:var(--primary);color:#03130C;font-weight:700" onclick="GF.WWF.lockDocument()">${AL('Lock & submit', 'Заклучи и поднеси')}</button>` : ''}
      </div>
      ${c.ribbon && c.ribbon.length ? `
        <div style="font-weight:700;font-size:14px;margin:10px 0 6px">${ribbonLbl}</div>
        ${GF.WWF._ribbonSvg(c.ribbon, c.period && c.period.start, c.period && c.period.days)}
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:4px;font-size:11px;color:var(--ink-2)">
          ${(c.metrics && c.metrics.per_sop || []).slice(0, 12).map(b =>
            `<span><span style="display:inline-block;width:9px;height:9px;border-radius:3px;background:${b.color};margin-right:4px;vertical-align:middle"></span>${GF.esc(b.sop)}</span>`).join('')}
        </div>` : ''}
      ${GF.WWF._docMetricsHtml(c.metrics)}
      ${tsections ? `<div style="font-weight:700;font-size:14px;margin:14px 0 4px">${AL('Department status', 'Статус по оддели')}
        <span style="font-size:11px;color:var(--ink-3);font-weight:400;margin-left:6px">${AL('metric grids are manual entry — edit, save, approve', 'метриките се рачен внес — уредете, зачувајте, одобрете')}</span></div>${tsections}` : ''}
      ${sections ? `<div style="font-weight:700;font-size:14px;margin:14px 0 4px">${AL('AI sections', 'АИ секции')}
        ${editable ? `<span style="font-size:11px;color:var(--ink-3);font-weight:400;margin-left:6px">${AL('every text is editable before submission', 'секој текст е уредлив пред поднесување')}</span>` : ''}</div>${sections}` : ''}
    </div>`;
  }
  // Document scope control: executives/ADMIN/QP pick org-wide or a specific
  // department (each is its own stored document per week); a dept-scoped
  // manager sees a fixed chip — the server forces their department anyway.
  const scoped = GF.WWF.deptScope ? GF.WWF.deptScope() : null;
  let deptCtl = '';
  if (scoped) {
    const d = (GF.DEPTS || []).find(x => x.id === scoped);
    deptCtl = `<span style="font-size:11px;font-weight:700;color:var(--ink-2);background:var(--surface-2,#102219);
      border:1px solid var(--line,rgba(43,232,160,.12));border-radius:99px;padding:3px 10px">
      ${d ? `<span class="dept-dot" style="background:${d.color};margin-right:5px"></span>${GF.esc(GF.depName(d.id))}` : AL('Your department', 'Вашиот оддел')}</span>`;
  } else if (elevated) {
    const opts = [`<option value="">${AL('Org-wide', 'Цела организација')}</option>`]
      .concat((GF.DEPTS || []).map(d =>
        `<option value="${d.id}" ${ds.deptId === d.id ? 'selected' : ''}>${GF.esc(GF.depName(d.id))}</option>`)).join('');
    deptCtl = `<select onchange="GF.WWF.setDocDept(this.value)" title="${AL('Document scope', 'Опсег на документот')}"
      style="font:inherit;font-size:12px;padding:4px 8px;border:1px solid var(--line,rgba(43,232,160,.12));
      border-radius:7px;background:var(--surface-2,#102219);color:var(--ink,#DDF3E9)">${opts}</select>`;
  }
  // Per-department submission strip on the ORG-WIDE panel: executives see at
  // a glance which departments haven't submitted before locking the org-wide
  // record. Loaded lazily from GET /status (execreport-view.js shares the
  // renderer); hidden for scoped managers and while a department is selected.
  let statusStrip = '';
  if (!scoped && elevated && !ds.deptId && GF.WWF.xrStatusChips) {
    statusStrip = GF.WWF.xrStatusChips(ds.status, { compact: true });
    GF.WWF._loadDocStatus && GF.WWF._loadDocStatus();
  }
  el.innerHTML = `<div style="margin:18px 0;background:var(--surface,#0B1913);border:1px solid var(--line,rgba(43,232,160,.12));border-radius:11px;overflow:hidden">
    <div style="padding:12px 14px;border-bottom:1px solid var(--line,rgba(43,232,160,.12));font-weight:700;font-size:14px;color:var(--primary,#2BE8A0);display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      ${GF.icon('calendar')} ${kindLbl}<div style="flex:1"></div>${deptCtl}
    </div>${statusStrip}${rangeControls}${body}</div>`;
};

// Fetch the per-department submission roll-up for the panel's current week /
// kind — cached per (kind, refDate) so the render → load → render cycle
// settles after one round trip. An older backend without /status (or demo
// mode) simply hides the strip.
GF.WWF._loadDocStatus = async () => {
  const st = GF.WWF._report, ds = GF.WWF._doc;
  const key = st.mode + '|' + (st.refDate || '');
  if (ds._statusKey === key) return;
  ds._statusKey = key;
  try {
    const q = { kind: st.mode };
    if (st.refDate) q.ref_date = st.refDate;
    ds.status = await GF.API.documentStatus(q);
  } catch (e) { ds.status = null; }
  GF.WWF._renderDocPanel();
};
