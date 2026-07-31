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

// Recurrence detail row ("every N" interval + optional end date) — only
// meaningful once a frequency is picked, so it stays hidden for "Does not
// repeat". Called by the add-rec chooser's onPick and by worklog.js's
// openEdit when prefilling an existing recurrence.
GF.syncRecFields = (freq) => {
  const row = GF.$('add-rec-extra'); if (!row) return;
  row.style.display = freq ? '' : 'none';
};

GF.openAdd = (weekId, parentId) => {
  // openEdit (worklog.js) already checked GF.can('edit', t) — don't re-deny on
  // 'create', which could wrongly block an allowed edit if the two perms ever diverge.
  if (!GF._fromEdit && !GF.can('create')) return GF.denyToast();
  const fromEdit = !!GF._fromEdit;    // captured before the reset below
  GF._fromEdit = false;
  GF._addWeek = weekId;
  GF._addParent = parentId || null;   // "Add subtask" presets the parent
  GF._editTask = null;                // openEdit (worklog.js) flips this to PATCH mode
  GF._editHelpers = null;             // openEdit refreshes this from the live assignees list
  const el = GF.$('add-body');
  // Department scoping (mirrors the backend guard in tasks.py): a dept-scoped
  // manager creates TOP-LEVEL tasks in their own department only, so the
  // picker locks to it. For a SUBTASK the full picker stays open — picking
  // another department delegates that piece of work and makes the parent a
  // multi-departmental task, fully visible to both departments. Edit mode
  // keeps the full list too: the task may legitimately live in another
  // department (delegated subtask / assigned helper) and openEdit must be
  // able to set the select to it; the server rejects illegal moves.
  const scopeDept = GF.WWF && GF.WWF.deptScope ? GF.WWF.deptScope() : null;
  const lockDept = scopeDept && !parentId && !fromEdit;
  const deptList = lockDept ? GF.DEPTS.filter(d => d.id === scopeDept) : GF.DEPTS;
  const deptOptions = deptList.map(d => ({ v: d.id, label: GF.depName(d.id), color: d.color }));
  const deptHint = parentId && scopeDept
    ? `<span class="lbl-hint">${GF.state.lang === 'mk'
        ? 'изберете друг оддел за да ја делегирате под-задачата'
        : 'pick another department to delegate this subtask'}</span>` : '';
  // Deactivated accounts stay in GF.PEOPLE for historical name/avatar lookups
  // but must not be offered as Accountable/Responsible for new work.
  const activePeople = Object.entries(GF.PEOPLE).filter(([, v]) => !v.inactive);
  const respChips = activePeople.map(([k, v]) =>
    `<span class="chip-opt who" data-who="${k}" onclick="this.classList.toggle('on')">${GF.avatar(k,18)}${GF.esc(v.name.split(' ')[0])}</span>`).join('');
  const prOptions = ['critical','high','medium','low'].map(p => ({ v: p, label: GF.prLabel(p) }));
  const dayChips = GF.DAYS.slice(0, 5).map(d => `<span class="chip-opt" data-day="${d}" onclick="this.classList.toggle('on')">${GF.dayLabel(d)}</span>`).join('');
  const typeOptions = GF.TASK_TYPES.map(t => ({ v: t, label: GF.taskTypeLabel(t) }));
  const recOptions = ['', 'daily', 'weekly', 'monthly'].map(r => ({ v: r, label: r ? GF.t('rec_' + r) : GF.t('rec_none') }));
  const defaultDept = deptList[0] ? deptList[0].id : '';
  // Sectioned create sheet — the design's task-create-*.html layout (labelled
  // .af-sec groups, chip pickers, a dept-tinted header) rather than a flat
  // stack of fields. Every field id is unchanged, so submitAdd / collectDeptAttrs
  // / openEdit's prefill and the e2e all keep working; only the presentation
  // changed. The AL() helper isn't loaded in main.js's scope, so bilingual
  // section labels use GF.state.lang inline, the same pattern as the tags row.
  const L = (en, mk) => (GF.state.lang === 'mk' ? mk : en);
  const secT = (en, mk, side) => `<p class="af-sec__t">${L(en, mk)}${side ? `<span class="af-sec__side">${side}</span>` : ''}</p>`;
  el.innerHTML = `
    <div class="af-sec">
      ${secT('Task title', 'Наслов на задача')}
      <div class="row" style="gap:8px"><input id="add-title" class="mw-input" placeholder="${GF.t('new_task')}…" style="flex:1">
        <button class="mini-btn" title="${GF.t('dictate')}" id="mic-add-title" onclick="GF.voice.dictate('add-title')">${GF.icon('mic')}</button></div>
    </div>
    <div class="af-sec">
      ${secT(GF.t('dept_label'), GF.t('dept_label'), deptHint || '')}
      ${GF.selectField('add-dept', {
        value: defaultDept, options: deptOptions, disabled: lockDept, title: GF.t('dept_label'),
        onPick: (v) => { if (GF.refreshDeptFields) GF.refreshDeptFields(v, null, !fromEdit && !parentId); if (GF._addAccent) GF._addAccent(v); },
      })}
      <div class="af-field" id="add-preset-row" style="display:none"></div>
    </div>
    <div class="af-sec" id="add-dept-fields-sec">
      <div id="add-dept-fields"></div>
    </div>
    <div class="af-cols">
      <div class="af-sec">${secT('Type', 'Тип')}${GF.chipField('add-type', {
        value: 'other', clearable: false, title: GF.t('task_type'), options: typeOptions })}</div>
      <div class="af-sec">${secT('Priority tier', 'Ниво на приоритет')}${GF.chipField('add-pr', {
        value: 'medium', clearable: false, title: GF.t('priority'),
        options: prOptions.map(o => ({ ...o, color: ({ critical: 'var(--red)', high: 'var(--orange)', medium: 'var(--blue)', low: 'var(--ink-3)' })[o.v] })),
        onPick: () => GF.renderAddPreview && GF.renderAddPreview() })}</div>
    </div>
    <div class="af-cols">
      <div class="af-sec">${secT('Due date', 'Рок')}<input id="add-due" class="mw-input" type="date"></div>
      <div class="af-sec">${secT('Recurrence', 'Повторување')}${GF.selectField('add-rec', {
        value: '', options: recOptions, title: GF.t('recurrence'), onPick: (v) => GF.syncRecFields(v) })}</div>
    </div>
    <div class="af-cols" id="add-rec-extra" style="display:none">
      <div class="af-sec">${secT('Repeat every', 'Повторувај на секои')}<input id="add-rec-n" class="mw-input" type="number" min="1" max="1000" step="1" value="1"></div>
      <div class="af-sec">${secT('Until', 'До')}<input id="add-rec-until" class="mw-input" type="date"></div>
    </div>
    <div class="af-sec">
      ${secT('Assignees', 'Задолжени', GF.t('responsible_hint'))}
      <div class="chips chips-who" id="add-resp">${respChips}</div>
    </div>
    <div class="af-cols">
      <div class="af-sec">${secT('Tags', 'Ознаки', L('comma-separated', 'одделени со запирка'))}
        <input id="add-tags" class="mw-input" placeholder="hlvd, tranche-1" oninput="GF.renderAddPreview&&GF.renderAddPreview()"></div>
      <div class="af-sec">${secT('SOP reference', 'СОП референца', L('code + link', 'код + линк'))}
        <input id="add-ref" class="mw-input" placeholder="PP-QC-SOP-012" autocapitalize="characters"></div>
    </div>
    <div class="af-sec">${secT('Days', 'Денови')}<div class="chips" id="add-days">${dayChips}</div></div>
    <div class="af-prev" id="add-preview"></div>`;
  // Department template fields (+ quick-add presets in create mode) for the
  // currently selected department; re-rendered by the dept chooser's onPick,
  // and re-rendered with prefill by worklog.js's openEdit in edit mode.
  if (GF.refreshDeptFields) GF.refreshDeptFields(GF.$('add-dept').value, null, !fromEdit && !parentId);
  if (GF._addAccent) GF._addAccent(GF.$('add-dept').value);
  const titleEl = GF.$('add-title');
  if (titleEl) titleEl.addEventListener('input', () => GF.renderAddPreview && GF.renderAddPreview());
  // Default to create-mode labels; worklog.js's openEdit flips these to
  // "Edit task" / "Save" after it sets GF._editTask.
  if (GF.$('add-modal-title')) GF.$('add-modal-title').textContent = GF.t('new_task');
  if (GF.$('add-submit-btn')) GF.$('add-submit-btn').textContent = GF.t('create_task');
  if (GF.$('add-cancel-btn')) GF.$('add-cancel-btn').textContent = GF.t('cancel');
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
  const modalOpen = document.querySelector('.overlay.open');
  if (!modalOpen && e.key === 'ArrowLeft') GF.selectWeek(GF.state.selWeek - 1);
  if (!modalOpen && e.key === 'ArrowRight') GF.selectWeek(GF.state.selWeek + 1);
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); GF.cmdk ? GF.cmdk.toggle() : GF.$('search-input')?.focus(); }
});

// ── Boot ──
window.addEventListener('DOMContentLoaded', () => {
  // GF.store.load() renders itself (see core.js / integrate.js's override) —
  // a second render.all() here used to fire unconditionally right after,
  // flashing an empty shell before the real (async) data arrived.
  GF.store.load();

  GF.$('search-input')?.addEventListener('input', (e) => {
    GF.state.search = e.target.value;
    // The search box filters the My-Week task panels only. render.panels()
    // rebuilds the My-Week panel unconditionally, so calling it while another
    // full-page view is active used to OVERWRITE that view with the My-Week
    // list (nav still highlighting the old view). Re-render whatever view is
    // actually active instead — My Week filters, other views just re-render.
    if (GF.state.view === 'mywork') GF.render.panels();
    else GF.setView(GF.state.view);
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
