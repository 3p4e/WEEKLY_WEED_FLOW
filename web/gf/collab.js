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
    const people = Object.keys(GF.PEOPLE || {}).filter(id => !have.has(id) && !GF.PEOPLE[id].inactive);
    assignRow = people.length ? `
      <div class="note-input" style="margin-top:6px">
        <span style="flex:1;min-width:0">${GF.selectField('assign-' + t.id, {
          value: people[0], title: AL('Assign', 'Додели'), searchable: true,
          options: people.map(id => ({ v: id, label: GF.PEOPLE[id].name, sub: GF.roleLabel ? GF.roleLabel(GF.PEOPLE[id].role) : undefined })) })}</span>
        <button class="mini-btn" style="color:var(--blue)" title="${AL('Assign', 'Додели')}" onclick="GF.WWF.doAssign('${t.id}')">${GF.icon('plus')}</button>
      </div>` : '';
  }

  return `
    ${GF.WWF.workflowSection(t, c)}
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

GF.WWF._collabSeq = GF.WWF._collabSeq || {};

GF.WWF.loadCollab = async (taskId) => {
  // Every action on this task's card (comment, assign, ack, ...) triggers
  // its own independent loadCollab(taskId) call; without a sequence guard,
  // an older call's response can resolve after (and overwrite) a newer
  // one's, making a just-added comment/assignee vanish from the render.
  const seq = (GF.WWF._collabSeq[taskId] = (GF.WWF._collabSeq[taskId] || 0) + 1);
  let result;
  try {
    const [comments, assignees, wf] = await Promise.all([
      GF.API.comments(taskId).catch(() => []),
      GF.API.assignees(taskId).catch(() => []),
      GF.API.taskWorkflow(taskId).catch(() => null),
    ]);
    result = { comments: comments || [], assignees: assignees || [], wf, loaded: true };
  } catch (e) {
    result = { comments: [], assignees: [], wf: null, loaded: true };
  }
  if (GF.WWF._collabSeq[taskId] !== seq) return;  // a newer call already resolved
  GF.WWF._collab[taskId] = result;
  const t = GF.task(taskId);
  const el = GF.$('collab-' + taskId);
  if (el && t) el.innerHTML = GF.WWF.renderCollabInner(t);
};

GF.WWF.postComment = async (taskId) => {
  const inp = GF.$('cmt-' + taskId); const text = inp && inp.value.trim();
  if (!text) return;
  inp.value = '';
  try { await GF.API.addComment(taskId, text); await GF.WWF.loadCollab(taskId); }
  catch (e) { GF.toast(AL('Comment failed: ', 'Коментарот не успеа: ') + e.message, 'error'); }
};

/* ── Workflow sign-off (SUMA v2): submit → approve/reject + QP quality block.
   The lifecycle only moves through POST /tasks/{id}/workflow; the strip shows
   the state, the actions the current role may take, and the event history
   (the sign-off record — actor, role, remark, time). ─────────────────────── */
GF.WWF._wfMeta = {
  draft:      { en: 'Draft',       mk: 'Нацрт',        c: 'var(--ink-3)' },
  submitted:  { en: 'Submitted',   mk: 'Поднесено',    c: 'var(--blue)' },
  approved:   { en: 'Approved',    mk: 'Одобрено',     c: 'var(--green)' },
  rejected:   { en: 'Rejected',    mk: 'Одбиено',      c: '#E5484D' },
  qp_blocked: { en: 'QP blocked',  mk: 'QP блокирано', c: 'var(--amber,#f0a020)' },
};

GF.WWF.workflowSection = (t, c) => {
  const wf = c && c.wf;
  if (!wf) return '';
  const st = wf.workflow_state || 'draft';
  const m = GF.WWF._wfMeta[st] || { en: st, mk: st, c: 'var(--ink-3)' };
  const role = (GF.API.user || {}).role;
  const elevated = !!role && role !== 'USER';
  const qp = role === 'QP' || role === 'ADMIN';
  const btn = (act, label, color) =>
    `<button class="mini-btn" style="color:${color}" onclick="GF.WWF.wfAct('${t.id}','${act}')">${label}</button>`;
  const actions = [];
  if (st !== 'submitted' && st !== 'qp_blocked') actions.push(btn('submit', AL('Submit', 'Поднеси'), 'var(--blue)'));
  if (elevated && st === 'submitted') {
    actions.push(btn('approve', AL('Approve', 'Одобри'), 'var(--green)'));
    actions.push(btn('reject', AL('Reject', 'Одбиј'), '#E5484D'));
  }
  if (qp && st !== 'qp_blocked') actions.push(btn('block', AL('QP block', 'QP блок'), 'var(--amber,#f0a020)'));
  if (qp && st === 'qp_blocked') actions.push(btn('unblock', AL('Lift block', 'Тргни блок'), 'var(--green)'));
  const events = (wf.events || []).length ? wf.events.map(e => `
    <div class="note" style="align-items:flex-start">
      <span class="nd" style="min-width:0;flex:0 0 auto">${GF.esc(e.action)}</span>
      <span style="flex:1">${GF.esc(e.actor_role || '')}${e.remark ? ' — ' + GF.esc(e.remark) : ''}</span>
      <span style="font-size:10px;color:var(--ink-3);white-space:nowrap">${GF.esc(GF.WWF._when(e.created_at))}</span>
    </div>`).join('') : `<div style="font-size:12px;color:var(--ink-3)">${AL('No sign-off events yet.', 'Сè уште нема настани.')}</div>`;
  return `
    <div class="sec-label">${GF.icon('check', 'icon')}${AL('Sign-off', 'Одобрување')}
      <span class="dep-chip" style="margin-left:6px;color:${m.c};border-color:${m.c}">${GF.esc(AL(m.en, m.mk))}</span>
    </div>
    <div class="note-input" style="flex-wrap:wrap;gap:6px">
      <input id="wf-remark-${t.id}" placeholder="${AL('Remark (required to reject/block)…', 'Забелешка (задолжителна за одбивање/блок)…')}" style="flex:1;min-width:140px">
      ${actions.join('')}
    </div>
    <div class="notes">${events}</div>`;
};

GF.WWF.wfAct = async (taskId, action) => {
  const inp = GF.$('wf-remark-' + taskId);
  const remark = (inp && inp.value.trim()) || null;
  if ((action === 'reject' || action === 'block') && !remark) {
    return GF.toast(AL('A remark is required to reject or block', 'Потребна е забелешка за одбивање или блок'), 'error');
  }
  try {
    await GF.API.taskWorkflowAct(taskId, { action, ...(remark ? { remark } : {}) });
    GF.toast(AL('Sign-off recorded', 'Одобрувањето е запишано'));
    await GF.WWF.loadCollab(taskId);
  } catch (e) { GF.toast(e.message, 'error'); }
};

GF.WWF.doAssign = async (taskId) => {
  const sel = GF.$('assign-' + taskId); const uid = sel && sel.value;
  if (!uid) return;
  try { await GF.API.assign(taskId, uid); await GF.WWF.loadCollab(taskId); GF.toast(AL('Assigned ✓', 'Доделено ✓'), 'success'); }
  catch (e) { GF.toast(AL('Assign failed: ', 'Доделувањето не успеа: ') + e.message, 'error'); }
};

GF.WWF.removeAssignee = async (taskId, userId) => {
  try { await GF.API.unassign(taskId, userId); await GF.WWF.loadCollab(taskId); }
  catch (e) { GF.toast(AL('Remove failed: ', 'Отстранувањето не успеа: ') + e.message, 'error'); }
};

GF.WWF.doAck = async (taskId, accepted) => {
  let reason = null;
  if (!accepted) { reason = prompt(AL('Reason for declining (optional):', 'Причина за одбивање (опционално):')) || ''; }
  try { await GF.API.ack(taskId, accepted, reason); await GF.WWF.loadCollab(taskId);
    GF.toast(accepted ? AL('Accepted ✓', 'Прифатено ✓') : AL('Declined', 'Одбиено'), accepted ? 'success' : 'info'); }
  catch (e) { GF.toast(AL('Failed: ', 'Неуспешно: ') + e.message, 'error'); }
};

// Inject the collab section into every expanded card, above actions.
(function () {
  const _card = GF.render.card.bind(GF.render);
  GF.render.card = function (t) {
    const html = _card(t);
    if (!GF.state.expanded || !GF.state.expanded.has(t.id)) return html;
    const anchor = '<div class="card-actions">';
    // Function replacement → returned text is inserted literally (a string
    // replacement would interpret $&/$'/$1 patterns inside comment content).
    return html.indexOf(anchor) >= 0
      ? html.replace(anchor, () => GF.WWF.collabSection(t) + anchor)
      : html;
  };
})();
