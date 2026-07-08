/* document-view.js — weekly Plan/Report DOCUMENT panel: compile → review →
   lock → export PDF. Renders into #report-doc inside the report view.
   The ribbon draws every logged work session over its real local-time extent
   (7 day-rows × 24h), color-keyed by SOP reference code. Load order: after
   report-view.js (extends the same GF.WWF namespace). */
window.GF = window.GF || {}; GF.WWF = GF.WWF || {};

GF.WWF._doc = { data: null, loading: false, error: null, _seq: 0 };

GF.WWF.loadDocument = async () => {
  const st = GF.WWF._report, ds = GF.WWF._doc;
  const seq = ++ds._seq;   // only the newest load may write state (no last-response-wins races)
  ds.loading = true; ds.error = null; GF.WWF._renderDocPanel();
  try {
    const q = { kind: st.mode };
    if (st.refDate) q.ref_date = st.refDate;
    const data = await GF.API.getDocument(q);
    if (seq !== ds._seq) return;            // a newer load/compile/lock superseded this one
    ds.data = data; ds.error = null;
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
  ds.loading = true; ds.error = null; GF.WWF._renderDocPanel();
  try {
    const data = await GF.API.compileDocument({ kind: st.mode, ref_date: st.refDate || undefined });
    ds._seq++; ds.data = data; ds.error = null;   // authoritative new state; bail any in-flight load
    GF.toast(AL('Document compiled', 'Документот е составен'), 'success');
  } catch (e) {
    GF.toast(AL('Compile failed: ', 'Неуспешно составување: ') + e.message, 'error');
  }
  ds.loading = false;
  GF.WWF._renderDocPanel();
};

GF.WWF.toggleDocSection = async (idx) => {
  const ds = GF.WWF._doc;
  if (!ds.data || ds.data.status !== 'draft') return;
  const sec = ds.data.content.ai_sections[idx];
  const prev = sec.approved;
  sec.approved = !prev;
  GF.WWF._renderDocPanel();               // optimistic
  try {
    // Section-scoped PATCH: sends {approved} only, not the whole document.
    const data = await GF.API.patchDocumentSection(ds.data.id, sec.key, { approved: sec.approved });
    ds._seq++; ds.data = data;            // adopt the server's canonical copy
  } catch (e) {
    sec.approved = prev;                  // roll back the optimistic flip — the server rejected it
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

GF.WWF.exportDocumentPdf = async () => {
  const ds = GF.WWF._doc;
  if (!ds.data) return;
  try {
    const res = await fetch(GF.API.base + '/reports/documents/' + ds.data.id + '/export.pdf',
      { headers: { Authorization: 'Bearer ' + GF.API.token } });
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
    const name = (m && m[1]) || ('wwf-' + ds.data.kind + '-' + ds.data.week_start
      + (ds.data.status === 'locked' ? '' : '-DRAFT') + '.pdf');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 800);
  } catch (e) { GF.toast(AL('Export failed: ', 'Неуспешен извоз: ') + e.message, 'error'); }
};

/* ── ribbon: 7 day-rows × 24h, sessions as SOP-colored bars ──
   Theme-adaptive live-panel renderer (uses --line/--surface CSS vars so it
   follows light/dark). The PDF has a second, static renderer (_ribbon_svg in
   backend/app/api/documents.py) — deliberately two, for two output targets.
   RECORD-critical geometry MUST match the backend: day-row by date, x =
   start_h*hw, width = max(2, (end_h-start_h)*hw), fill = seg.color. Both draw
   from the same content.ribbon segments, so the record can't drift. */
GF.WWF._ribbonSvg = (segments, weekStart) => {
  if (!segments || !segments.length) return '';
  const W = 860, ROW = 36, LEFT = 70, TOP = 22, H = TOP + 7 * ROW + 14;
  const hw = (W - LEFT - 10) / 24;
  const d0 = new Date(weekStart + 'T00:00:00');
  let s = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto" xmlns="http://www.w3.org/2000/svg">`;
  for (let h = 0; h <= 24; h += 3) {
    const x = LEFT + h * hw;
    s += `<line x1="${x}" y1="${TOP - 4}" x2="${x}" y2="${H - 12}" stroke="var(--line,#E2E8F0)" stroke-width="1"/>`
      + `<text x="${x}" y="${TOP - 8}" font-size="9" fill="var(--ink-3,#8A99B0)" text-anchor="middle">${String(h).padStart(2, '0')}</text>`;
  }
  for (let i = 0; i < 7; i++) {
    const d = new Date(d0); d.setDate(d0.getDate() + i);
    const iso = GF.localDateStr(d);
    const y = TOP + i * ROW;
    const lbl = d.toLocaleDateString(GF.state.lang === 'mk' ? 'mk-MK' : 'en-GB', { weekday: 'short', day: '2-digit', month: '2-digit' });
    s += `<text x="4" y="${y + ROW / 2 + 3}" font-size="10" fill="var(--ink,#16233B)">${GF.esc(lbl)}</text>`
      + `<rect x="${LEFT}" y="${y + 4}" width="${W - LEFT - 10}" height="${ROW - 8}" rx="4" fill="var(--surface-2,#F3F6FA)"/>`;
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
      <td style="text-align:right;color:${(b.night + b.weekend) > 0 ? '#FF7A1A' : 'var(--ink-3)'}">${(b.night + b.weekend + b.overtime).toFixed(1)}h</td>
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

  if (ds.loading) {
    el.innerHTML = `<div style="padding:16px;color:var(--ink-3)">${AL('Working…', 'Се работи…')}</div>`;
    return;
  }
  const d = ds.data;
  let body;
  if (ds.error) {
    // A real failure (500/network/permission) — NOT the empty state. Offer a
    // retry, never a Compile button that could overwrite an existing draft.
    body = `<div style="padding:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <span style="color:#B45309;font-size:13px">${AL('Couldn’t load the document: ', 'Не може да се вчита документот: ')}${GF.esc(ds.error)}</span>
      <button class="btn btn-sm" onclick="GF.WWF.loadDocument()">${AL('Retry', 'Обиди се повторно')}</button>
    </div>`;
  } else if (!d) {
    body = `<div style="padding:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <span style="color:var(--ink-3);font-size:13px">${AL('No document compiled for this week yet.', 'Сè уште нема составен документ за оваа недела.')}</span>
      ${elevated ? `<button class="btn btn-sm btn-primary" onclick="GF.WWF.compileDocument()">${AL('Compile document', 'Состави документ')}</button>` : ''}
    </div>`;
  } else {
    const c = d.content || {};
    const locked = d.status === 'locked';
    const chip = locked
      ? `<span style="background:#E7F7EF;color:#0E6E4A;font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px">${AL('LOCKED — submitted record', 'ЗАКЛУЧЕН — поднесен запис')}${d.locked_at ? ' · ' + d.locked_at.slice(0, 16).replace('T', ' ') : ''}</span>`
      : `<span style="background:#FFF4E5;color:#B45309;font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px">${AL('DRAFT', 'НАЦРТ')}</span>`;
    const sections = (c.ai_sections || []).map((s, i) => {
      if (s.status === 'not_configured') return '';
      const ok = !!s.approved;
      return `<div style="border:1px solid var(--line,#E2E8F0);border-radius:9px;padding:10px 12px;margin:8px 0;background:${ok ? '#F4FBF7' : 'var(--surface,#fff)'}">
        <div style="display:flex;align-items:center;gap:10px">
          <b style="font-size:13px">${GF.esc(s.title)}</b>
          <span style="font-size:10.5px;color:var(--ink-3)">${s.status === 'unavailable' ? AL('agent unavailable', 'агентот е недостапен') : ''}</span>
          <div style="flex:1"></div>
          ${!locked ? `<label style="font-size:12px;display:flex;align-items:center;gap:5px;cursor:pointer">
            <input type="checkbox" ${ok ? 'checked' : ''} onchange="GF.WWF.toggleDocSection(${i})">
            ${AL('Approve for document', 'Одобри за документот')}</label>`
          : (ok ? `<span style="font-size:11px;color:#0E6E4A;font-weight:700">${AL('Approved', 'Одобрено')}</span>` : `<span style="font-size:11px;color:var(--ink-3)">${AL('Not included', 'Не е вклучено')}</span>`)}
        </div>
        ${s.body ? `<div style="font-size:13px;line-height:1.6;margin-top:6px;white-space:pre-wrap;color:var(--ink)">${GF.esc(s.body)}</div>` : ''}
      </div>`;
    }).join('');
    body = `<div style="padding:14px 16px">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px">
        ${chip}
        <span style="font-size:12px;color:var(--ink-3)">${(c.tasks || []).length} ${AL('tasks', 'задачи')} · ${(c.ribbon || []).length} ${AL('logged sessions', 'сесии')}</span>
        <div style="flex:1"></div>
        ${!locked && elevated ? `<button class="btn btn-sm" onclick="GF.WWF.compileDocument()">${AL('Recompile', 'Состави повторно')}</button>` : ''}
        <button class="btn btn-sm" onclick="GF.WWF.exportDocumentPdf()">${AL('Export PDF', 'Извези PDF')}</button>
        ${!locked && elevated ? `<button class="btn btn-sm" style="background:#0E6E4A;color:#fff" onclick="GF.WWF.lockDocument()">${AL('Lock & submit', 'Заклучи и поднеси')}</button>` : ''}
      </div>
      ${c.ribbon && c.ribbon.length ? `
        <div style="font-weight:700;font-size:14px;margin:10px 0 6px">${AL('Week ribbon — logged work by SOP', 'Неделна лента — работа по СОП')}</div>
        ${GF.WWF._ribbonSvg(c.ribbon, c.period && c.period.start)}
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:4px;font-size:11px;color:var(--ink-2)">
          ${(c.metrics && c.metrics.per_sop || []).slice(0, 12).map(b =>
            `<span><span style="display:inline-block;width:9px;height:9px;border-radius:3px;background:${b.color};margin-right:4px;vertical-align:middle"></span>${GF.esc(b.sop)}</span>`).join('')}
        </div>` : ''}
      ${GF.WWF._docMetricsHtml(c.metrics)}
      ${sections ? `<div style="font-weight:700;font-size:14px;margin:14px 0 4px">${AL('AI sections', 'АИ секции')}</div>${sections}` : ''}
    </div>`;
  }
  el.innerHTML = `<div style="margin:18px 0;background:var(--surface,#fff);border:1px solid var(--line,#E2E8F0);border-radius:11px;overflow:hidden">
    <div style="padding:12px 14px;border-bottom:1px solid var(--line,#E2E8F0);font-weight:700;font-size:14px;color:#0E6E4A">
      ${GF.icon('calendar')} ${kindLbl}
    </div>${body}</div>`;
};
