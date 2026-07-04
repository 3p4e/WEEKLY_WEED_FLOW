/* ══════════════════════════════════════════════════════════════════════
   Capture Import — the manual half of the capture pipeline. Paste the
   fenced JSON a Master Capture Prompt session produced (claude.ai, Cowork,
   Claude Code, the Drive sweep) and it lands in WWF via POST
   /capture/import: idempotent, deduped by external_ref, statuses only move
   forward. The automatic half is the claude.ai/Cowork connector, which
   calls the same endpoint (see docs/TASK-CAPTURE-PROMPT.md, DELIVERY).

   Loads after report-view.js — same AL() helper +
   GF.WWF._registerFullPageView() pattern as the other full-page views.
   ════════════════════════════════════════════════════════════════════ */
GF.views.import = function () {
  return `<div id="import-view" style="padding:4px 2px 40px;max-width:860px">
    <h2 style="margin:6px 4px 6px;font-size:19px;font-weight:800;color:var(--ink)">${AL('Import capture', 'Увоз на задачи')}</h2>
    <div style="font-size:13px;color:var(--ink-2);margin:0 4px 14px">
      ${AL('Paste the JSON block a capture session produced (the whole {"session_meta": …, "tasks": […]} object, with or without the ```json fence). Importing the same capture twice is safe — tasks merge by external_ref.',
           'Залепете го JSON блокот од capture сесија. Двоен увоз е безбеден — задачите се спојуваат по external_ref.')}
    </div>
    <textarea id="import-json" spellcheck="false" placeholder='{"session_meta": {…}, "tasks": […]}'
      style="width:100%;min-height:260px;font:12px ui-monospace,monospace;background:#fff;border:1px solid var(--line);border-radius:11px;padding:12px;color:var(--ink);resize:vertical"></textarea>
    <div style="display:flex;gap:8px;align-items:center;margin-top:10px">
      <button class="btn btn-primary" onclick="GF.WWF.runImport()">${AL('Import', 'Увези')}</button>
      <span id="import-busy" style="display:none;color:var(--ink-3);font-size:13px">${AL('Importing…', 'Се увезува…')}</span>
    </div>
    <div id="import-result" style="margin-top:16px"></div>
  </div>`;
};

GF.WWF.runImport = async () => {
  const ta = GF.$('import-json'), out = GF.$('import-result'), busy = GF.$('import-busy');
  if (!ta || !out) return;
  let text = (ta.value || '').trim();
  // Tolerate a pasted fenced block — strip ```json … ``` wrappers.
  text = text.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (e) {
    out.innerHTML = `<div style="color:#E5484D;font-size:13px">${AL('Not valid JSON', 'Невалиден JSON')}: ${GF.esc(e.message)}</div>`;
    return;
  }
  if (!payload || !Array.isArray(payload.tasks)) {
    out.innerHTML = `<div style="color:#E5484D;font-size:13px">${AL('Expected an object with a "tasks" array', 'Очекуван е објект со "tasks" низа')}</div>`;
    return;
  }
  busy.style.display = 'inline';
  try {
    const r = await GF.API._req('POST', '/capture/import', payload);
    const skipped = (r.skipped || []).map(s =>
      `<li><code>${GF.esc(s.external_ref || '—')}</code> — ${GF.esc(s.reason)}</li>`).join('');
    out.innerHTML = `
      <div style="background:#fff;border:1px solid var(--line);border-radius:11px;padding:14px 16px;font-size:13px;color:var(--ink)">
        <b>${AL('Imported', 'Увезено')}:</b>
        ${r.created} ${AL('created', 'нови')}, ${r.updated} ${AL('updated', 'ажурирани')},
        ${r.sessions_added} ${AL('work sessions added', 'работни сесии додадени')}.
        ${skipped ? `<div style="margin-top:8px;color:#E5484D"><b>${AL('Skipped', 'Прескокнати')} (${r.skipped.length}):</b><ul style="margin:6px 0 0 18px">${skipped}</ul></div>` : ''}
      </div>`;
    if (r.created || r.updated) {
      GF.toast && GF.toast(AL('Capture imported', 'Увозот заврши'));
      // Refresh task state so the imported work shows up without a reload.
      if (GF.WWF.loadAndRender) GF.WWF.loadAndRender();
    }
  } catch (e) {
    out.innerHTML = `<div style="color:#E5484D;font-size:13px">${AL('Import failed', 'Увозот не успеа')}: ${GF.esc(e.message)}</div>`;
  } finally {
    busy.style.display = 'none';
  }
};

/* nav item below Report; visible to every signed-in user (the backend
   enforces owner-scoping — non-admins can only import their own work). */
GF.WWF._registerFullPageView({
  key: 'import', icon: 'box', label: () => AL('Import', 'Увоз'),
  insertBefore: 'audit',
});
