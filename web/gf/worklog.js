/* ══════════════════════════════════════════════════════════════════════
   Work sessions + v2 task lifecycle affordances — the frontend of the
   overtime engine (POST/GET /tasks/{id}/sessions, DELETE /sessions/{id})
   plus the small follow-up dialogs the status flow triggers (outcome on
   completion, blocker reason when stuck), archive, and edit-task.

   Same monkey-patch pattern as audit-view.js/collab.js (split out of
   integrate.js). Must load AFTER collab.js: uses the shared AL() helper and
   AUDIT_ROLES, bare top-level consts declared in audit-view.js — classic
   <script> tags share one lexical scope in document order.
   ════════════════════════════════════════════════════════════════════ */

/* ── Speech-to-text affordance ──────────────────────────────────────────
   Web Speech API is Chromium/WebKit-only; where it's missing (Firefox, iOS
   WebViews) render an explanatory muted button instead of a dead mic. */
GF.WWF.srSupported = () => !!(window.SpeechRecognition || window.webkitSpeechRecognition);
GF.WWF.micBtn = (inputId) => GF.WWF.srSupported()
  ? `<button class="mini-btn" id="mic-${inputId}" title="${GF.t('dictate')}" onclick="GF.voice.dictate('${inputId}')">${GF.icon('mic')}</button>`
  : `<button class="mini-btn" style="opacity:.4;cursor:not-allowed" title="${AL('Dictation not supported in this browser', 'Диктирањето не е поддржано во овој прелистувач')}"
       onclick="GF.toast('${AL('Dictation not supported in this browser', 'Диктирањето не е поддржано во овој прелистувач')}','info')">${GF.icon('mic')}</button>`;

/* ── Dynamic modal shell (created on demand, reuses .overlay/.modal css) ── */
GF.WWF._ensureModal = (id, maxWidth) => {
  let el = GF.$(id);
  if (!el) { el = document.createElement('div'); el.id = id; el.className = 'overlay'; document.body.appendChild(el); }
  el.innerHTML = `<div class="modal" style="max-width:${maxWidth || '440px'}">
    <div class="modal-head"><h3 id="${id}-title"></h3>
      <button class="btn-ghost" onclick="GF.closeModal('${id}')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
    <div class="modal-body" id="${id}-body"></div>
  </div>`;
  return el;
};

/* ── Work-session modal ───────────────────────────────────────────────── */
GF.WWF._worklog = { taskId: null, sessions: null };

GF.WWF.openWorklog = (taskId) => {
  const t = GF.task(taskId); if (!t) return;
  GF.WWF._worklog = { taskId, sessions: null };
  GF.WWF._ensureModal('worklog-modal', '480px');
  GF.$('worklog-modal-title').textContent = GF.t('log_work') + ' — ' + t.title.slice(0, 40);
  GF.WWF._renderWorklog();
  GF.openModal('worklog-modal');
  GF.API.sessions(taskId)
    .then(s => { GF.WWF._worklog.sessions = s || []; GF.WWF._renderWorklog(); })
    .catch(() => { GF.WWF._worklog.sessions = []; GF.WWF._renderWorklog(); });
};

GF.WWF._renderWorklog = () => {
  const body = GF.$('worklog-modal-body'); if (!body) return;
  const st = GF.WWF._worklog;
  const today = new Date().toISOString().slice(0, 10);
  const me = (GF.API.user || {}).id;
  const elevated = AUDIT_ROLES.includes((GF.API.user || {}).role);

  let list;
  if (st.sessions === null) {
    list = `<div style="font-size:12px;color:var(--ink-3);padding:6px 0">${AL('Loading…', 'Се вчитува…')}</div>`;
  } else if (!st.sessions.length) {
    list = `<div style="font-size:12px;color:var(--ink-3);padding:6px 0">${AL('No work logged yet.', 'Сè уште нема внесена работа.')}</div>`;
  } else {
    list = st.sessions.map(s => {
      const when = (s.started_at || '').slice(0, 16).replace('T', ' ');
      const who = (GF.PEOPLE[s.user_id] || {}).name || '';
      const del = (s.user_id === me || elevated)
        ? `<button class="mini-btn" style="color:var(--red)" title="${GF.t('delete')}" onclick="GF.WWF.deleteSession('${s.id}')">${GF.icon('trash')}</button>` : '';
      return `<div class="sess-row">
        <span style="font-family:var(--mono);white-space:nowrap">${GF.esc(when)}</span>
        <span style="font-weight:700;white-space:nowrap">${s.hours}h</span>
        <span class="sess-class ${GF.esc(s.classification)}">${GF.esc(s.classification)}</span>
        <span style="flex:1;min-width:0;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${GF.esc(s.note || who)}</span>
        ${del}
      </div>`;
    }).join('');
  }

  body.innerHTML = `
    <div class="row" style="gap:10px">
      <div class="field" style="flex:1.2"><label>${AL('Date', 'Датум')}</label><input id="wl-date" type="date" value="${today}"></div>
      <div class="field" style="flex:1"><label>${AL('Start', 'Почеток')}</label><input id="wl-start" type="time" value="09:00"></div>
    </div>
    <div class="row" style="gap:10px">
      <div class="field" style="flex:1"><label>${AL('End', 'Крај')}</label><input id="wl-end" type="time"></div>
      <div class="field" style="flex:1"><label>${AL('or hours', 'или часови')}</label><input id="wl-hours" type="number" min="0.25" step="0.25" placeholder="2.5"></div>
    </div>
    <div class="field"><label>${AL('Note', 'Белешка')}</label>
      <div class="row" style="gap:8px"><input id="wl-note" placeholder="${AL('What was done…', 'Што беше направено…')}" style="flex:1">
        ${GF.WWF.micBtn('wl-note')}</div></div>
    <button class="btn btn-primary" style="width:100%;justify-content:center" onclick="GF.WWF.submitWorklog()">${GF.t('log_work')}</button>
    <div class="sec-label" style="margin-top:16px">${GF.icon('clock','icon')}${AL('Logged sessions', 'Внесени сесии')}</div>
    <div id="wl-list">${list}</div>`;
};

GF.WWF.submitWorklog = async () => {
  const st = GF.WWF._worklog; if (!st.taskId) return;
  const date = (GF.$('wl-date') || {}).value;
  const start = (GF.$('wl-start') || {}).value;
  const end = (GF.$('wl-end') || {}).value;
  const hoursRaw = parseFloat((GF.$('wl-hours') || {}).value);
  const note = ((GF.$('wl-note') || {}).value || '').trim() || null;
  if (!date || !start) { GF.toast(AL('Enter a date and start time', 'Внесете датум и почетен час'), 'error'); return; }
  if (!end && !(Number.isFinite(hoursRaw) && hoursRaw > 0)) {
    GF.toast(AL('Enter an end time or hours', 'Внесете краен час или часови'), 'error'); return;
  }
  // No offset = facility wall-clock (Europe/Skopje) — backend interprets it so.
  const body = { started_at: `${date}T${start}:00`, note, source: 'manual' };
  if (end) {
    // An end time at or before the start means the shift crossed midnight —
    // roll ended_at to the next day so a 22:00→01:00 session logs instead of
    // 422-ing on "ended_at must be after started_at".
    let endDate = date;
    if (end <= start) {
      const d = new Date(date + 'T00:00:00');
      d.setDate(d.getDate() + 1);
      endDate = d.toISOString().slice(0, 10);
    }
    body.ended_at = `${endDate}T${end}:00`;
  } else body.hours = hoursRaw;
  try {
    const s = await GF.API.addSession(st.taskId, body);
    GF.toast(AL(`Logged ${s.hours}h — ${s.classification}`, `Внесени ${s.hours}ч — ${s.classification}`), 'success');
    st.sessions = (st.sessions || []).concat([s]);
    const t = GF.task(st.taskId);
    if (t) { t.sessionHours = Math.round(((t.sessionHours || 0) + Number(s.hours)) * 100) / 100; GF.render.panels(); }
    GF.WWF._renderWorklog();
  } catch (e) { GF.toast(AL('Log failed: ', 'Неуспешен внес: ') + e.message, 'error'); }
};

GF.WWF.deleteSession = async (sessionId) => {
  const st = GF.WWF._worklog;
  if (!confirm(AL('Delete this work session?', 'Да се избрише оваа сесија?'))) return;
  try {
    await GF.API.deleteSession(sessionId);
    const gone = (st.sessions || []).find(s => s.id === sessionId);
    st.sessions = (st.sessions || []).filter(s => s.id !== sessionId);
    const t = GF.task(st.taskId);
    if (t && gone) { t.sessionHours = Math.max(0, Math.round(((t.sessionHours || 0) - Number(gone.hours)) * 100) / 100); GF.render.panels(); }
    GF.WWF._renderWorklog();
    GF.toast(GF.t('delete') + ' ✓', 'success');
  } catch (e) { GF.toast(AL('Delete failed: ', 'Неуспешно бришење: ') + e.message, 'error'); }
};

/* ── Outcome prompt (on completion) — optional, non-blocking ───────────── */
GF.WWF.promptOutcome = (taskId) => {
  const t = GF.task(taskId); if (!t) return;
  GF.WWF._ensureModal('outcome-modal', '400px');
  GF.$('outcome-modal-title').textContent = GF.t('outcome');
  GF.$('outcome-modal-body').innerHTML = `
    <div style="font-size:13px;color:var(--ink-2);margin-bottom:12px">${AL('Task completed — add an optional outcome note?', 'Задачата е завршена — додадете белешка за резултатот?')}</div>
    <div class="field"><div class="row" style="gap:8px">
      <input id="outcome-note" placeholder="${AL('e.g. Deviation closed, report filed', 'пр. Отстапувањето е затворено')}" style="flex:1"
        onkeydown="if(event.key==='Enter')GF.WWF.saveOutcome('${t.id}')">
      ${GF.WWF.micBtn('outcome-note')}</div></div>
    <div class="row" style="gap:10px">
      <button class="btn" style="flex:1;justify-content:center" onclick="GF.closeModal('outcome-modal')">${AL('Skip', 'Прескокни')}</button>
      <button class="btn btn-primary" style="flex:1;justify-content:center" onclick="GF.WWF.saveOutcome('${t.id}')">${GF.t('save')}</button>
    </div>`;
  GF.openModal('outcome-modal');
  setTimeout(() => GF.$('outcome-note') && GF.$('outcome-note').focus(), 60);
};

GF.WWF.saveOutcome = async (taskId) => {
  const v = ((GF.$('outcome-note') || {}).value || '').trim();
  GF.closeModal('outcome-modal');
  if (!v) return;
  try {
    await GF.API.updateTask(taskId, { outcome: v });
    const t = GF.task(taskId); if (t) t.outcome = v;
    GF.toast(GF.t('outcome') + ' ✓', 'success');
  } catch (e) { GF.toast(AL('Save failed: ', 'Неуспешно зачувување: ') + e.message, 'error'); }
};

/* ── Blocker prompt (on stuck) ─────────────────────────────────────────── */
GF.WWF.promptBlocker = (taskId) => {
  const t = GF.task(taskId); if (!t) return;
  GF.WWF._ensureModal('blocker-modal', '400px');
  GF.$('blocker-modal-title').textContent = GF.t('blocker');
  GF.$('blocker-modal-body').innerHTML = `
    <div style="font-size:13px;color:var(--ink-2);margin-bottom:12px">${AL('What is blocking this task?', 'Што ја блокира оваа задача?')}</div>
    <div class="field"><div class="row" style="gap:8px">
      <input id="blocker-note" value="${GF.esc(t.blocker || '')}" placeholder="${AL('e.g. Waiting on QC release', 'пр. Чекаме ослободување од КК')}" style="flex:1"
        onkeydown="if(event.key==='Enter')GF.WWF.saveBlocker('${t.id}')">
      ${GF.WWF.micBtn('blocker-note')}</div></div>
    <div class="row" style="gap:10px">
      <button class="btn" style="flex:1;justify-content:center" onclick="GF.closeModal('blocker-modal')">${AL('Skip', 'Прескокни')}</button>
      <button class="btn btn-primary" style="flex:1;justify-content:center" onclick="GF.WWF.saveBlocker('${t.id}')">${GF.t('save')}</button>
    </div>`;
  GF.openModal('blocker-modal');
  setTimeout(() => GF.$('blocker-note') && GF.$('blocker-note').focus(), 60);
};

GF.WWF.saveBlocker = async (taskId) => {
  const v = ((GF.$('blocker-note') || {}).value || '').trim();
  GF.closeModal('blocker-modal');
  if (!v) return;
  try {
    await GF.API.updateTask(taskId, { blocker_reason: v });
    const t = GF.task(taskId); if (t) { t.blocker = v; GF.render.panels(); }
    GF.toast(GF.t('blocker') + ' ✓', 'success');
  } catch (e) { GF.toast(AL('Save failed: ', 'Неуспешно зачувување: ') + e.message, 'error'); }
};

/* ── Archive (PATCH is_archived — backend list excludes archived by default) ── */
GF.WWF.archiveTask = async (taskId) => {
  const t = GF.task(taskId); if (!t) return;
  if (!confirm(AL('Archive "' + t.title + '"? It disappears from the week views but stays in reports and the audit trail.',
                  'Архивирај „' + t.title + '"? Ќе исчезне од неделните прегледи, но останува во извештаите.'))) return;
  try {
    await GF.API.updateTask(taskId, { is_archived: true });
    GF.state.tasks = GF.state.tasks.filter(x => x.id !== taskId);
    GF.state.expanded.delete(taskId);
    GF.render.all();
    GF.toast(GF.t('archive') + ' ✓', 'success');
  } catch (e) { GF.toast(AL('Archive failed: ', 'Неуспешно архивирање: ') + e.message, 'error'); }
};

/* ── Edit task — reuses the add modal, submitAdd PATCHes when _editTask set ── */
GF.WWF.openEdit = (taskId) => {
  const t = GF.task(taskId); if (!t) return;
  if (!GF.can('edit', t)) return GF.denyToast();
  GF._fromEdit = true;             // openAdd re-checks 'create' otherwise
  GF.openAdd(t.weekId);            // builds the form (resets _editTask/_addParent)
  GF._editTask = taskId;
  GF.$('add-title').value = t.title;
  GF.$('add-dept').value = t.dept;
  GF.$('add-pr').value = t.pr;
  if (GF.$('add-type')) GF.$('add-type').value = t.type || 'other';
  if (GF.$('add-due')) GF.$('add-due').value = t.due || '';
  if (GF.$('add-ref')) GF.$('add-ref').value = t.ref || '';
  if (GF.$('add-rec')) GF.$('add-rec').value = (t.recurrence && t.recurrence.freq) || '';
  if (GF.$('add-est')) GF.$('add-est').value = t.est != null ? t.est : '';
  [...GF.$('add-days').querySelectorAll('.chip-opt')].forEach(el => {
    el.classList.toggle('on', (t.days || []).includes(el.dataset.day));
  });
  // Pre-select the Responsible chips from the task's current helpers so the
  // edit form shows who's already assigned; submitAdd diffs against this to
  // add/remove assignees on save.
  if (GF.$('add-resp')) {
    [...GF.$('add-resp').querySelectorAll('.chip-opt')].forEach(el => {
      el.classList.toggle('on', (t.helpers || []).includes(el.dataset.who));
    });
  }
  // openAdd defaulted the modal to create-mode labels — flip to edit.
  if (GF.$('add-modal-title')) GF.$('add-modal-title').textContent = GF.t('edit_task');
  if (GF.$('add-submit-btn')) GF.$('add-submit-btn').textContent = GF.t('save');
};
