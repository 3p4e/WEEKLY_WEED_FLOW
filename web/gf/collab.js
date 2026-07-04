/* ══════════════════════════════════════════════════════════════════════
   Task collaboration — comments + assignment/acknowledgment, injected into the
   expanded task card. Comments are visible to anyone who can see the task;
   assigning a teammate makes the task appear in their week and lets them
   accept/decline. Backed by /tasks/{id}/comments|assignees|ack.

   Split out of integrate.js (first decomposition cut). Must load AFTER
   audit-view.js: canManageTask below reads AUDIT_ROLES, a bare top-level
   const declared there — classic <script> tags share one lexical scope in
   document order, so that dependency only resolves in that load order.
   ════════════════════════════════════════════════════════════════════ */
GF.WWF._collab = {};   // taskId -> { comments, assignees, loaded }

GF.WWF.canManageTask = (t) =>
  AUDIT_ROLES.includes((GF.API.user || {}).role) || (t && t.owner === GF.WWF.meId);

GF.WWF._when = (iso) => { try { return new Date(iso).toLocaleString(); } catch (e) { return ''; } };

GF.WWF.collabSection = (t) => {
  const c = GF.WWF._collab[t.id];
  if (!c || !c.loaded) setTimeout(() => GF.WWF.loadCollab(t.id), 0);
  return `<div class="collab-sec" id="collab-${t.id}">${GF.WWF.renderCollabInner(t)}</div>`;
};

GF.WWF.renderCollabInner = (t) => {
  const c = GF.WWF._collab[t.id];
  if (!c || !c.loaded) return `<div style="font-size:12px;color:var(--ink-3);padding:6px 0">${AL('Loading…', 'Се вчитува…')}</div>`;
  const me = (GF.API.user || {}).id;
  const manage = GF.WWF.canManageTask(t);

  // Comments thread
  const comments = c.comments.length ? c.comments.map(m => `
    <div class="note" style="align-items:flex-start">
      <span class="nd" style="min-width:0;flex:0 0 auto">${GF.esc(m.author || '—')}</span>
      <span style="flex:1">${GF.esc(m.content)}</span>
      <span style="font-size:10px;color:var(--ink-3);white-space:nowrap">${GF.esc(GF.WWF._when(m.created_at))}</span>
    </div>`).join('') : `<div style="font-size:12px;color:var(--ink-3)">${AL('No comments yet.', 'Сè уште нема коментари.')}</div>`;

  // Assignee chips (+ accept/decline for me, remove for managers)
  const chips = c.assignees.map(a => {
    const state = a.accepted === true ? `<span style="color:var(--green)">✓ ${AL('accepted', 'прифатено')}</span>`
      : a.accepted === false ? `<span style="color:#E5484D">✋ ${AL('declined', 'одбиено')}</span>`
      : `<span style="color:var(--ink-3)">${AL('pending', 'во тек')}</span>`;
    const mineActions = (a.user_id === me && a.accepted == null) ? `
      <button class="mini-btn" style="color:var(--green)" title="${AL('Accept', 'Прифати')}" onclick="GF.WWF.doAck('${t.id}',true)">✓</button>
      <button class="mini-btn" style="color:#E5484D" title="${AL('Decline', 'Одбиј')}" onclick="GF.WWF.doAck('${t.id}',false)">✕</button>` : '';
    const rm = manage ? `<button class="mini-btn" style="color:var(--ink-3)" title="${AL('Remove', 'Отстрани')}" onclick="GF.WWF.removeAssignee('${t.id}','${a.user_id}')">×</button>` : '';
    return `<span class="dep-chip" style="gap:6px">${GF.icon('user','icon')}${GF.esc(a.name)} ${state}${mineActions}${rm}</span>`;
  }).join('');

  // Assign control (managers only): teammates not already assigned
  let assignRow = '';
  if (manage) {
    const have = new Set(c.assignees.map(a => a.user_id));
    const opts = Object.keys(GF.PEOPLE || {}).filter(id => !have.has(id))
      .map(id => `<option value="${id}">${GF.esc(GF.PEOPLE[id].name)}</option>`).join('');
    assignRow = opts ? `
      <div class="note-input" style="margin-top:6px">
        <select id="assign-${t.id}" style="flex:1;padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px">${opts}</select>
        <button class="mini-btn" style="color:var(--blue)" title="${AL('Assign', 'Додели')}" onclick="GF.WWF.doAssign('${t.id}')">${GF.icon('plus')}</button>
      </div>` : '';
  }

  return `
    <div class="sec-label">${GF.icon('at','icon')}${AL('Assignees', 'Доделени')}</div>
    <div class="deps">${chips || `<span style="font-size:12px;color:var(--ink-3)">${AL('Nobody assigned.', 'Никој не е доделен.')}</span>`}</div>
    ${assignRow}
    <div class="sec-label">${GF.icon('chat','icon')}${AL('Comments', 'Коментари')}</div>
    <div class="notes">${comments}</div>
    <div class="note-input">
      <input id="cmt-${t.id}" placeholder="${AL('Add a comment…', 'Додади коментар…')}" onkeydown="if(event.key==='Enter')GF.WWF.postComment('${t.id}')">
      <button class="mini-btn" style="color:var(--blue)" onclick="GF.WWF.postComment('${t.id}')">${GF.icon('plus')}</button>
    </div>`;
};

GF.WWF.loadCollab = async (taskId) => {
  try {
    const [comments, assignees] = await Promise.all([
      GF.API.comments(taskId).catch(() => []),
      GF.API.assignees(taskId).catch(() => []),
    ]);
    GF.WWF._collab[taskId] = { comments: comments || [], assignees: assignees || [], loaded: true };
  } catch (e) {
    GF.WWF._collab[taskId] = { comments: [], assignees: [], loaded: true };
  }
  const t = GF.task(taskId);
  const el = GF.$('collab-' + taskId);
  if (el && t) el.innerHTML = GF.WWF.renderCollabInner(t);
};

GF.WWF.postComment = async (taskId) => {
  const inp = GF.$('cmt-' + taskId); const text = inp && inp.value.trim();
  if (!text) return;
  inp.value = '';
  try { await GF.API.addComment(taskId, text); await GF.WWF.loadCollab(taskId); }
  catch (e) { GF.toast('Comment failed: ' + e.message, 'error'); }
};

GF.WWF.doAssign = async (taskId) => {
  const sel = GF.$('assign-' + taskId); const uid = sel && sel.value;
  if (!uid) return;
  try { await GF.API.assign(taskId, uid); await GF.WWF.loadCollab(taskId); GF.toast(AL('Assigned ✓', 'Доделено ✓'), 'success'); }
  catch (e) { GF.toast('Assign failed: ' + e.message, 'error'); }
};

GF.WWF.removeAssignee = async (taskId, userId) => {
  try { await GF.API.unassign(taskId, userId); await GF.WWF.loadCollab(taskId); }
  catch (e) { GF.toast('Remove failed: ' + e.message, 'error'); }
};

GF.WWF.doAck = async (taskId, accepted) => {
  let reason = null;
  if (!accepted) { reason = prompt(AL('Reason for declining (optional):', 'Причина за одбивање (опционално):')) || ''; }
  try { await GF.API.ack(taskId, accepted, reason); await GF.WWF.loadCollab(taskId);
    GF.toast(accepted ? AL('Accepted ✓', 'Прифатено ✓') : AL('Declined', 'Одбиено'), accepted ? 'success' : 'info'); }
  catch (e) { GF.toast('Failed: ' + e.message, 'error'); }
};

// Effort capture: hours-spent input on the expanded card (persists to the
// real backend). estimated_hours is set at creation; actual_hours here.
GF.WWF.hoursSection = (t) => {
  const est = (t.est != null) ? t.est : '—';
  const act = (t.act != null) ? t.act : '';
  return `
    <div class="sec-label">${GF.icon('clock','icon')}${AL('Hours', 'Часови')}</div>
    <div class="note-input">
      <input id="hrs-${t.id}" type="number" min="0" step="0.5" value="${act}"
             placeholder="${AL('Hours spent', 'Потрошени часови')}"
             onchange="GF.WWF.saveHours('${t.id}')"
             style="flex:1;padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px">
      <span style="font-size:12px;color:var(--ink-3);white-space:nowrap">/ ${AL('est', 'проц.')} ${est}</span>
    </div>`;
};

GF.WWF.saveHours = async (taskId) => {
  const el = GF.$('hrs-' + taskId); const t = GF.task(taskId);
  if (!el || !t) return;
  const raw = el.value.trim();
  const v = raw === '' ? null : parseFloat(raw);
  if (v !== null && (!Number.isFinite(v) || v < 0)) { GF.toast(AL('Enter a valid number', 'Внесете важечки број'), 'error'); return; }
  const prev = t.act;
  try {
    // Persist first — only mutate local state once the backend confirms.
    await GF.API.updateTask(taskId, { actual_hours: v });
    t.act = v; GF.render.panels(); GF.toast(AL('Hours saved ✓', 'Часовите се зачувани ✓'), 'success');
  } catch (e) {
    t.act = prev; GF.render.panels(); GF.toast('Save failed: ' + e.message, 'error');
  }
};

// Inject the hours + collab sections into every expanded card, above actions.
(function () {
  const _card = GF.render.card.bind(GF.render);
  GF.render.card = function (t) {
    const html = _card(t);
    if (!GF.state.expanded || !GF.state.expanded.has(t.id)) return html;
    const anchor = '<div class="card-actions">';
    // Function replacement → returned text is inserted literally (a string
    // replacement would interpret $&/$'/$1 patterns inside comment content).
    return html.indexOf(anchor) >= 0
      ? html.replace(anchor, () => GF.WWF.hoursSection(t) + GF.WWF.collabSection(t) + anchor)
      : html;
  };
})();
