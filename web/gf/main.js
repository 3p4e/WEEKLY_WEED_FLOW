/* main.js — boot, CRUD, keyboard shortcuts, add-task, toggle-sub, settings, events */
window.GF = window.GF || {};

// ── CRUD helpers ──
GF.addNote = (taskId) => {
  const t = GF.task(taskId); if (!t) return;
  const el = GF.$('note-' + taskId); if (!el || !el.value.trim()) return;
  t.notes = t.notes || [];
  t.notes.push({ d: GF.todayDay.slice(0, 3), n: el.value.trim() });
  GF.store.save(); GF.render.panels();
};
// GF.deleteTask is defined for real by integrate.js (loaded after this file),
// which gates deletion behind audit-retention rules — no local-only version.

// ── Add task (form modal) ──
// v2 task typology — mirrors the backend TaskType enum (see backend/app/api/tasks.py).
GF.TASK_TYPES = ['capa', 'sop', 'validation', 'document', 'lab', 'meeting', 'admin', 'other'];

GF.openAdd = (weekId, parentId) => {
  // openEdit (worklog.js) already checked GF.can('edit', t) — don't re-deny on
  // 'create', which could wrongly block an allowed edit if the two perms ever diverge.
  if (!GF._fromEdit && !GF.can('create')) return GF.denyToast();
  GF._fromEdit = false;
  GF._addWeek = weekId;
  GF._addParent = parentId || null;   // "Add subtask" presets the parent
  GF._editTask = null;                // openEdit (worklog.js) flips this to PATCH mode
  GF._editHelpers = null;             // openEdit refreshes this from the live assignees list
  const el = GF.$('add-body');
  const deptOpts = GF.DEPTS.map(d => `<option value="${d.id}">${GF.esc(GF.depName(d.id))}</option>`).join('');
  // Deactivated accounts stay in GF.PEOPLE for historical name/avatar lookups
  // but must not be offered as Accountable/Responsible for new work.
  const activePeople = Object.entries(GF.PEOPLE).filter(([, v]) => !v.inactive);
  const respChips = activePeople.map(([k, v]) =>
    `<span class="chip-opt who" data-who="${k}" onclick="this.classList.toggle('on')">${GF.avatar(k,18)}${GF.esc(v.name.split(' ')[0])}</span>`).join('');
  const prOpts = ['critical','high','medium','low'].map(p => `<option value="${p}" ${p==='medium'?'selected':''}>${GF.prLabel(p)}</option>`).join('');
  const dayChips = GF.DAYS.slice(0, 5).map(d => `<span class="chip-opt" data-day="${d}" onclick="this.classList.toggle('on')">${GF.dayLabel(d)}</span>`).join('');
  const typeOpts = GF.TASK_TYPES.map(t => `<option value="${t}" ${t==='other'?'selected':''}>${GF.taskTypeLabel(t)}</option>`).join('');
  const recOpts = ['', 'daily', 'weekly', 'monthly'].map(r =>
    `<option value="${r}">${r ? GF.t('rec_' + r) : GF.t('rec_none')}</option>`).join('');
  el.innerHTML = `
    <div class="field"><label>${GF.t('new_task')}</label>
      <div class="row" style="gap:8px"><input id="add-title" placeholder="${GF.t('new_task')}…" style="flex:1">
        <button class="mini-btn" title="${GF.t('dictate')}" id="mic-add-title" onclick="GF.voice.dictate('add-title')">${GF.icon('mic')}</button></div></div>
    <div class="field"><label>${GF.t('dept_label')}</label><select id="add-dept">${deptOpts}</select></div>
    <div class="field"><label>${GF.t('responsible')} <span class="lbl-hint">${GF.t('responsible_hint')}</span></label><div class="chips chips-who" id="add-resp">${respChips}</div></div>
    <div class="row" style="gap:10px">
      <div class="field" style="flex:1"><label>${GF.t('priority')}</label><select id="add-pr">${prOpts}</select></div>
      <div class="field" style="flex:1"><label>${GF.t('task_type')}</label><select id="add-type">${typeOpts}</select></div>
    </div>
    <div class="row" style="gap:10px">
      <div class="field" style="flex:1"><label>${GF.t('due_date')}</label><input id="add-due" type="date"></div>
      <div class="field" style="flex:1"><label>${GF.t('recurrence')}</label><select id="add-rec">${recOpts}</select></div>
    </div>
    <div class="row" style="gap:10px">
      <div class="field" style="flex:1"><label>${GF.t('reference_code')}</label><input id="add-ref" placeholder="PP-QC-SOP-012" autocapitalize="characters"></div>
      <div class="field" style="flex:1"><label>${GF.t('est_hours')}</label><input id="add-est" type="number" min="0" step="0.5" placeholder="0"></div>
    </div>
    <div class="field"><label>${GF.t('due')}</label><div class="chips" id="add-days">${dayChips}</div></div>`;
  // Default to create-mode labels; worklog.js's openEdit flips these to
  // "Edit task" / "Save" after it sets GF._editTask.
  if (GF.$('add-modal-title')) GF.$('add-modal-title').textContent = GF.t('new_task');
  if (GF.$('add-submit-btn')) GF.$('add-submit-btn').textContent = GF.t('create_task');
  GF.openModal('add-modal');
};
// GF.submitAdd is defined for real by integrate.js (loaded after this file),
// which POSTs/PATCHes through the real API — no local-only version.

// ── User / team management ──
// GF.setActiveUser, GF.removeUser, GF.openUser, and GF.submitUser are all
// defined for real by integrate.js (loaded after this file), which drives
// the actual account API (create/edit/deactivate, reset-password) — real
// auth has no local impersonation or client-only roster, so none of the
// local-only versions this file used to have ever ran.

// ── Keyboard ──
document.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) { if (e.key === 'Escape') e.target.blur(); return; }
  if (e.key === 'Escape') {
    // voice-modal needs its recognizer stopped, not just hidden — route
    // through GF.voice.closeCapture() like the modal's own Cancel/X buttons.
    if (GF.$('voice-modal')?.classList.contains('open')) GF.voice.closeCapture();
    document.querySelectorAll('.overlay.open').forEach(m => m.classList.remove('open'));
  }
  if (e.key === 'ArrowLeft') GF.selectWeek(GF.state.selWeek - 1);
  if (e.key === 'ArrowRight') GF.selectWeek(GF.state.selWeek + 1);
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); GF.$('search-input')?.focus(); }
});

// ── Boot ──
window.addEventListener('DOMContentLoaded', () => {
  GF.store.load();
  GF.render.all();

  GF.$('search-input')?.addEventListener('input', (e) => {
    GF.state.search = e.target.value; GF.render.panels();
  });

  // sidebar toggle (mobile)
  GF.$('hamburger')?.addEventListener('click', () => {
    GF.$('sidebar').classList.toggle('open');
    GF.$('sidebar-overlay').classList.toggle('open');
  });
  GF.$('sidebar-overlay')?.addEventListener('click', () => {
    GF.$('sidebar').classList.remove('open');
    GF.$('sidebar-overlay').classList.remove('open');
  });
});
