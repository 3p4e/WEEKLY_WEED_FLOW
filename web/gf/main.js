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
GF.deleteTask = (taskId) => {
  const t = GF.task(taskId);
  if (!GF.can('delete', t)) return GF.denyToast();
  GF.state.tasks = GF.state.tasks.filter(t => t.id !== taskId);
  GF.state.expanded.delete(taskId);
  GF.store.save(); GF.render.panels(); GF.render.telemetry();
  GF.toast(GF.t('delete') + ' ✓', 'success');
};

// ── Add task (form modal) ──
GF.openAdd = (weekId) => {
  if (!GF.can('create')) return GF.denyToast();
  GF._addWeek = weekId;
  const el = GF.$('add-body');
  const deptOpts = GF.DEPTS.map(d => `<option value="${d.id}">${GF.depName(d.id)}</option>`).join('');
  const ownerOpts = Object.entries(GF.PEOPLE).map(([k, v]) => `<option value="${k}" ${k===GF.state.user?'selected':''}>${GF.esc(v.name)}</option>`).join('');
  const respChips = Object.entries(GF.PEOPLE).map(([k, v]) =>
    `<span class="chip-opt who" data-who="${k}" onclick="this.classList.toggle('on')">${GF.avatar(k,18)}${GF.esc(v.name.split(' ')[0])}</span>`).join('');
  const prOpts = ['critical','high','medium','low'].map(p => `<option value="${p}" ${p==='medium'?'selected':''}>${GF.prLabel(p)}</option>`).join('');
  const dayChips = GF.DAYS.slice(0, 5).map(d => `<span class="chip-opt" data-day="${d}" onclick="this.classList.toggle('on')">${GF.dayLabel(d)}</span>`).join('');
  el.innerHTML = `
    <div class="field"><label>${GF.t('new_task')}</label>
      <div class="row" style="gap:8px"><input id="add-title" placeholder="${GF.t('new_task')}…" style="flex:1">
        <button class="mini-btn" title="${GF.t('dictate')}" id="mic-add-title" onclick="GF.voice.dictate('add-title')">${GF.icon('mic')}</button></div></div>
    <div class="field"><label>${GF.t('dept_label')}</label><select id="add-dept">${deptOpts}</select></div>
    <div class="field"><label>${GF.t('accountable')} <span class="lbl-hint">${GF.t('accountable_hint')}</span></label><select id="add-owner">${ownerOpts}</select></div>
    <div class="field"><label>${GF.t('responsible')} <span class="lbl-hint">${GF.t('responsible_hint')}</span></label><div class="chips chips-who" id="add-resp">${respChips}</div></div>
    <div class="field"><label>${GF.t('priority')}</label><select id="add-pr">${prOpts}</select></div>
    <div class="field"><label>${GF.t('est_hours')}</label><input id="add-est" type="number" min="0" step="0.5" placeholder="0"></div>
    <div class="field"><label>${GF.t('due')}</label><div class="chips" id="add-days">${dayChips}</div></div>`;
  GF.openModal('add-modal');
};
GF.submitAdd = () => {
  const title = (GF.$('add-title')?.value || '').trim();
  if (!title) { GF.toast('Enter a title', 'error'); return; }
  const days = [...GF.$('add-days').querySelectorAll('.on')].map(el => el.dataset.day);
  const owner = GF.$('add-owner').value;
  const helpers = [...GF.$('add-resp').querySelectorAll('.on')].map(el => el.dataset.who).filter(w => w !== owner);
  const task = {
    id: GF.uid(), title, dept: GF.$('add-dept').value, owner, helpers,
    status: 'pending', pr: GF.$('add-pr').value, days: days.length ? days : [GF.todayDay],
    weekId: GF._addWeek, tags: [], desc: '', notes: [], deps: [], blocker: '',
  };
  GF.state.tasks.push(task); GF.store.save();
  GF.closeModal('add-modal'); GF.render.all();
  GF.toast(GF.t('create_task') + ' ✓', 'success');
};

// ── User / team management ──
GF.setActiveUser = (id) => {
  if (!GF.PEOPLE[id]) return;
  GF.state.user = id; try { localStorage.setItem('gf_user', id); } catch (e) {}
  if (window.APP && APP._updateAvatar) APP._updateAvatar();
  GF.render.all();
  GF.toast(GF.PEOPLE[id].name + ' ✓', 'success');
};
GF.removeUser = (id) => {
  if (!GF.can('team')) return GF.denyToast();
  if (!GF.PEOPLE[id]) return;
  if (Object.keys(GF.PEOPLE).length <= 1) { GF.toast('Cannot remove the last member', 'error'); return; }
  GF.people.remove(id);
  GF.render.all();
  GF.toast(GF.t('remove') + ' ✓', 'success');
};
GF.openUser = (id) => {
  if (!GF.can('team')) return GF.denyToast();
  GF._editUser = id || null;
  const p = id ? GF.PEOPLE[id] : { name: '', role: 'operator', dept: 'veg', bg: GF.AVATAR_COLORS[0] };
  const deptOpts = GF.DEPTS.map(d => `<option value="${d.id}" ${d.id===p.dept?'selected':''}>${GF.depName(d.id)}</option>`).join('');
  const roleOpts = Object.keys(GF.ROLES).map(r => `<option value="${r}" ${r===p.role?'selected':''}>${GF.roleLabel(r)}</option>`).join('');
  const swatches = GF.AVATAR_COLORS.map(c => `<span class="swatch ${c===p.bg?'on':''}" data-color="${c}" style="background:${c}" onclick="this.parentNode.querySelectorAll('.swatch').forEach(s=>s.classList.remove('on'));this.classList.add('on')"></span>`).join('');
  GF.$('user-title').textContent = id ? GF.t('edit_user') : GF.t('add_user');
  GF.$('user-body').innerHTML = `
    <div class="field"><label>${GF.t('full_name')}</label><input id="u-name" value="${GF.esc(p.name)}" placeholder="e.g. Ana Nikolova"></div>
    <div class="field"><label>${GF.t('role')}</label><select id="u-role">${roleOpts}</select></div>
    <div class="field"><label>${GF.t('dept_label')}</label><select id="u-dept">${deptOpts}</select></div>
    <div class="field"><label>${GF.t('avatar_color')}</label><div class="swatches" id="u-colors">${swatches}</div></div>`;
  GF.openModal('user-modal');
};
GF.submitUser = () => {
  const name = (GF.$('u-name')?.value || '').trim();
  if (!name) { GF.toast('Enter a name', 'error'); return; }
  const role = GF.$('u-role').value, dept = GF.$('u-dept').value;
  const bg = GF.$('u-colors').querySelector('.swatch.on')?.dataset.color || GF.AVATAR_COLORS[0];
  const person = { name, role, roleLabel: GF.ROLES[role] ? GF.ROLES[role].en : role, dept, bg, init: GF.people.initials(name) };
  GF.people.upsert(GF._editUser, person);
  GF.closeModal('user-modal'); GF.render.all();
  GF.toast((GF._editUser ? GF.t('save') : GF.t('add_user')) + ' ✓', 'success');
};

// ── Keyboard ──
document.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) { if (e.key === 'Escape') e.target.blur(); return; }
  if (e.key === 'Escape') document.querySelectorAll('.overlay.open').forEach(m => m.classList.remove('open'));
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
