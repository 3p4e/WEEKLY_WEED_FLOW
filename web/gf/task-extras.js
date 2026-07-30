/* ══════════════════════════════════════════════════════════════════════
   Task extras — Links, Dependencies (blocked-by/blocks), and cross-department
   Handoffs, injected into the expanded task card. Same pattern as collab.js's
   Comments/Assignees section: all three backends (task_links, task_dependencies,
   handoffs) have existed since the v2 task model / TMS T1 work with full
   api.js wrappers already wired — none of them had any UI to reach them
   until now.

   Must load AFTER collab.js: it wraps GF.render.card again, chaining onto
   collab.js's own wrap (classic <script> tags share one lexical scope in
   document order, same constraint documented there).
   ════════════════════════════════════════════════════════════════════ */
GF.WWF._extras = {};   // taskId -> { links, blockedBy, blocks, handoffs, loaded }

GF.WWF.extrasSection = (t) => {
  const x = GF.WWF._extras[t.id];
  if (!x || !x.loaded) setTimeout(() => GF.WWF.loadExtras(t.id), 0);
  return `<div class="extras-sec" id="extras-${t.id}">${GF.WWF.renderExtrasInner(t)}</div>`;
};

GF.WWF.renderExtrasInner = (t) => {
  const x = GF.WWF._extras[t.id];
  if (!x || !x.loaded) return `<div style="font-size:12px;color:var(--ink-3);padding:6px 0">${AL('Loading…', 'Се вчитува…')}</div>`;
  return GF.WWF.renderLinks(t, x) + GF.WWF.renderDeps(t, x) + GF.WWF.renderHandoffs(t, x);
};

GF.WWF._extrasSeq = GF.WWF._extrasSeq || {};

GF.WWF.loadExtras = async (taskId) => {
  // Same staleness guard as loadCollab: an older in-flight call must never
  // overwrite a newer one's result.
  const seq = (GF.WWF._extrasSeq[taskId] = (GF.WWF._extrasSeq[taskId] || 0) + 1);
  let result;
  try {
    const [full, handoffs] = await Promise.all([
      GF.API.getTask(taskId).catch(() => null),
      GF.API.handoffs(taskId).catch(() => []),
    ]);
    result = {
      links: (full && full.links) || [],
      blockedBy: (full && full.blocked_by) || [],
      blocks: (full && full.blocks) || [],
      handoffs: handoffs || [],
      loaded: true,
    };
  } catch (e) {
    result = { links: [], blockedBy: [], blocks: [], handoffs: [], loaded: true };
  }
  if (GF.WWF._extrasSeq[taskId] !== seq) return;  // a newer call already resolved
  GF.WWF._extras[taskId] = result;
  const t = GF.task(taskId);
  const el = GF.$('extras-' + taskId);
  if (el && t) el.innerHTML = GF.WWF.renderExtrasInner(t);
};

/* ── Links (task_links: url + label + kind) ──────────────────────────── */
const LINK_KIND_ICON = { drive: 'file', sop: 'shield', doc: 'file', other: 'link' };

GF.WWF.renderLinks = (t, x) => {
  const rows = x.links.length ? x.links.map(l => `
    <div class="note" style="align-items:center">
      ${GF.icon(LINK_KIND_ICON[l.kind] || 'link', 'icon')}
      <a href="${GF.esc(l.url)}" target="_blank" rel="noopener noreferrer"
         style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${GF.esc(l.label || l.url)}</a>
      <button class="mini-btn" style="color:var(--ink-3)" title="${AL('Remove', 'Отстрани')}" onclick="GF.WWF.removeLink('${t.id}','${l.id}')">×</button>
    </div>`).join('') : `<div style="font-size:12px;color:var(--ink-3)">${AL('No links yet.', 'Сè уште нема линкови.')}</div>`;
  return `
    <div class="sec-label">${GF.icon('link', 'icon')}${AL('Links', 'Линкови')}</div>
    <div class="notes">${rows}</div>
    <div class="note-input" style="flex-wrap:wrap">
      <input id="lnk-url-${t.id}" placeholder="${AL('https://…', 'https://…')}" style="flex:2;min-width:120px">
      <input id="lnk-label-${t.id}" placeholder="${AL('Label (optional)', 'Ознака (опционално)')}" style="flex:1;min-width:100px">
      <span style="flex:0 0 auto">${GF.selectField('lnk-kind-' + t.id, {
        value: 'other', title: AL('Kind', 'Вид'),
        options: [
          { v: 'drive', label: AL('Drive', 'Драјв') },
          { v: 'sop', label: 'SOP' },
          { v: 'doc', label: AL('Document', 'Документ') },
          { v: 'other', label: AL('Other', 'Друго') },
        ] })}</span>
      <button class="mini-btn" style="color:var(--blue)" title="${AL('Add link', 'Додади линк')}" onclick="GF.WWF.addLink('${t.id}')">${GF.icon('plus')}</button>
    </div>`;
};

GF.WWF.addLink = async (taskId) => {
  const urlInp = GF.$('lnk-url-' + taskId), labelInp = GF.$('lnk-label-' + taskId), kindInp = GF.$('lnk-kind-' + taskId);
  const url = urlInp ? urlInp.value.trim() : '';
  if (!url) return;
  if (!/^https?:\/\//i.test(url)) { GF.toast(AL('URL must start with http(s)://', 'URL мора да почнува со http(s)://'), 'error'); return; }
  const label = labelInp ? labelInp.value.trim() : '';
  const kind = kindInp ? kindInp.value : 'other';
  urlInp.value = ''; if (labelInp) labelInp.value = '';
  try {
    await GF.API.addLink(taskId, { url, label: label || null, kind });
    await GF.WWF.loadExtras(taskId);
  } catch (e) { GF.toast(AL('Add link failed: ', 'Неуспешно додавање линк: ') + e.message, 'error'); }
};

GF.WWF.removeLink = async (taskId, linkId) => {
  try { await GF.API.deleteLink(taskId, linkId); await GF.WWF.loadExtras(taskId); }
  catch (e) { GF.toast(AL('Remove failed: ', 'Неуспешно отстранување: ') + e.message, 'error'); }
};

/* ── Dependencies (task_dependencies: task_id is blocked_by depends_on) ── */
GF.WWF.renderDeps = (t, x) => {
  // Design .mw-dep: the dot is green once the OTHER task is done (the blocker
  // no longer blocks) and red while it still does — state the old chip never
  // showed. The dot only ever reflects other.status; it is display, not gate.
  const chip = (other, onRemove) => `
    <span class="mw-dep ${other.status === 'done' ? 'met' : 'unmet'}"><span class="dot"></span>${GF.esc(other.title)}
      <button class="mini-btn" style="color:var(--ink-3)" title="${AL('Remove', 'Отстрани')}" onclick="${onRemove}">×</button>
    </span>`;
  const blockedBy = x.blockedBy.length
    ? x.blockedBy.map(o => chip(o, `GF.WWF.removeDependency('${t.id}','${o.id}')`)).join('')
    : `<span style="font-size:12px;color:var(--ink-3)">${AL('Nothing.', 'Ништо.')}</span>`;
  const blocks = x.blocks.length
    // A "blocks" edge lives on the OTHER task's row (that task depends on
    // this one) — remove it there: task_id=other, depends_on=this task.
    ? x.blocks.map(o => chip(o, `GF.WWF.removeDependency('${o.id}','${t.id}')`)).join('')
    : `<span style="font-size:12px;color:var(--ink-3)">${AL('Nothing.', 'Ништо.')}</span>`;
  const already = new Set([t.id, ...x.blockedBy.map(o => o.id)]);
  const candidates = (GF.state.tasks || []).filter(o => !already.has(o.id));
  const addRow = candidates.length ? `
    <div class="note-input">
      <span style="flex:1;min-width:0">${GF.selectField('dep-add-' + t.id, {
        value: candidates[0].id, title: AL('Task', 'Задача'), searchable: true,
        options: candidates.map(o => ({ v: o.id, label: o.title })) })}</span>
      <button class="mini-btn" style="color:var(--blue)" title="${AL('Add blocker', 'Додади блокатор')}" onclick="GF.WWF.addDependency('${t.id}')">${GF.icon('plus')}</button>
    </div>` : '';
  return `
    <div class="sec-label">${GF.icon('link', 'icon')}${AL('Blocked by', 'Блокирано од')}</div>
    <div class="deps">${blockedBy}</div>
    ${addRow}
    <div class="sec-label">${GF.icon('link', 'icon')}${AL('Blocks', 'Блокира')}</div>
    <div class="deps">${blocks}</div>`;
};

GF.WWF.addDependency = async (taskId) => {
  const sel = GF.$('dep-add-' + taskId); const dep = sel && sel.value;
  if (!dep) return;
  try { await GF.API.addDependency(taskId, dep); await GF.WWF.loadExtras(taskId); }
  catch (e) { GF.toast(AL('Add dependency failed: ', 'Неуспешно додавање зависност: ') + e.message, 'error'); }
};

GF.WWF.removeDependency = async (taskId, depId) => {
  try { await GF.API.deleteDependency(taskId, depId); await GF.WWF.loadExtras(taskId); }
  catch (e) { GF.toast(AL('Remove failed: ', 'Неуспешно отстранување: ') + e.message, 'error'); }
};

/* ── Cross-department handoffs ───────────────────────────────────────── */
GF.WWF._deptName = (id) => {
  const d = (GF.DEPTS || []).find(d => d.id === id);
  return d ? (GF.state.lang === 'mk' ? d.mk : d.name) : (id || '—');
};

GF.WWF.renderHandoffs = (t, x) => {
  const me = (GF.API.user || {}).id;
  const canResolve = GF.WWF.canManageTask(t);
  const rows = x.handoffs.length ? x.handoffs.map(h => {
    const st = {
      proposed: AL('proposed', 'предложено'), accepted: AL('accepted', 'прифатено'),
      rejected: AL('rejected', 'одбиено'), cancelled: AL('cancelled', 'откажано'),
    }[h.status] || h.status;
    const canCancel = canResolve || String(h.requested_by) === String(me);
    let actions = '';
    if (h.status === 'proposed') {
      if (canResolve) actions += `
        <button class="mini-btn" style="color:var(--green)" title="${AL('Accept', 'Прифати')}" onclick="GF.WWF.resolveHandoff('${h.id}','accepted')">✓</button>
        <button class="mini-btn" style="color:#E5484D" title="${AL('Reject', 'Одбиј')}" onclick="GF.WWF.resolveHandoff('${h.id}','rejected')">✕</button>`;
      if (canCancel) actions += `
        <button class="mini-btn" style="color:var(--ink-3)" title="${AL('Cancel', 'Откажи')}" onclick="GF.WWF.resolveHandoff('${h.id}','cancelled')">⊘</button>`;
    }
    return `
      <div class="note" style="align-items:flex-start">
        <span style="flex:1">${GF.WWF._deptName(h.from_dept_id)} → ${GF.WWF._deptName(h.to_dept_id)}
          ${h.note ? `<span style="color:var(--ink-3)"> — ${GF.esc(h.note)}</span>` : ''}</span>
        <span style="font-size:11px;color:var(--ink-3);white-space:nowrap">${st}</span>
        ${actions}
      </div>`;
  }).join('') : `<div style="font-size:12px;color:var(--ink-3)">${AL('No handoffs proposed.', 'Нема предложено префрлање.')}</div>`;
  const otherDepts = (GF.DEPTS || []).filter(d => d.id !== t.dept);
  const proposeRow = otherDepts.length ? `
    <div class="note-input" style="flex-wrap:wrap">
      <span style="flex:1;min-width:0">${GF.selectField('ho-dept-' + t.id, {
        value: otherDepts[0].id, title: AL('Department', 'Оддел'),
        options: otherDepts.map(d => ({ v: d.id, label: GF.state.lang === 'mk' ? d.mk : d.name })) })}</span>
      <input id="ho-note-${t.id}" placeholder="${AL('Note (optional)', 'Белешка (опционално)')}" style="flex:1;min-width:100px">
      <button class="mini-btn" style="color:var(--blue)" title="${AL('Propose handoff', 'Предложи префрлање')}" onclick="GF.WWF.proposeHandoff('${t.id}')">${GF.icon('plus')}</button>
    </div>` : '';
  return `
    <div class="sec-label">${GF.icon('users', 'icon')}${AL('Handoffs', 'Префрлања')}</div>
    <div class="notes">${rows}</div>
    ${proposeRow}`;
};

GF.WWF.proposeHandoff = async (taskId) => {
  const deptSel = GF.$('ho-dept-' + taskId), noteInp = GF.$('ho-note-' + taskId);
  const toDeptId = deptSel && deptSel.value;
  if (!toDeptId) return;
  const note = noteInp ? noteInp.value.trim() : '';
  if (noteInp) noteInp.value = '';
  try {
    await GF.API.proposeHandoff(taskId, toDeptId, note || null);
    await GF.WWF.loadExtras(taskId);
    GF.toast(AL('Handoff proposed ✓', 'Префрлањето е предложено ✓'), 'success');
  } catch (e) { GF.toast(AL('Propose handoff failed: ', 'Неуспешно предлагање: ') + e.message, 'error'); }
};

GF.WWF.resolveHandoff = async (handoffId, status) => {
  try {
    await GF.API.resolveHandoff(handoffId, status);
    if (status === 'accepted') {
      // Accepting moves the task server-side (department_id changes) —
      // find which task this handoff belonged to (from whichever extras
      // cache still holds it) and mirror that locally so the board
      // regroups it immediately instead of waiting for a full reload.
      for (const [taskId, x] of Object.entries(GF.WWF._extras)) {
        const h = (x.handoffs || []).find(h => h.id === handoffId);
        if (h) { const t = GF.task(taskId); if (t) t.dept = h.to_dept_id; break; }
      }
    }
    Object.keys(GF.WWF._extras).forEach(id => GF.WWF.loadExtras(id));
    GF.render.all();
    GF.toast(AL('Handoff updated ✓', 'Префрлањето е ажурирано ✓'), 'success');
  } catch (e) { GF.toast(AL('Resolve failed: ', 'Неуспешно решавање: ') + e.message, 'error'); }
};

// Inject after collab's section, still above card-actions.
(function () {
  const _card = GF.render.card.bind(GF.render);
  GF.render.card = function (t) {
    const html = _card(t);
    if (!GF.state.expanded || !GF.state.expanded.has(t.id)) return html;
    const anchor = '<div class="card-actions">';
    // Function replacement → returned text is inserted literally (a string
    // replacement would interpret $&/$'/$1 patterns inside link/note content).
    return html.indexOf(anchor) >= 0
      ? html.replace(anchor, () => GF.WWF.extrasSection(t) + anchor)
      : html;
  };
})();
