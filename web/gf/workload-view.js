/* workload-view.js — crew capacity for the selected week. Global: GF.views.workload
   Per-person load bars (priority-weighted points, or estimated hours where
   set) over the week's tasks, with drag-and-drop: drag a task chip onto a
   person to add them as a helper (the owner is immutable by design — POST
   /tasks always owns as creator — so drag ADDS an assignee via the existing
   /tasks/{id}/assignees endpoint rather than transferring ownership).
   Managers/execs only (nav-gated by GF.can('team')). From the Mass Weed mockups. */
window.GF = window.GF || {};

(function () {
  const AL = (en, mk) => (GF.state.lang === 'mk' ? mk : en);
  const W = { critical: 3, high: 2, medium: 1.5, low: 1 };
  const CAP = 12;   // soft weekly capacity in points — display heuristic only

  const load = (t) => (Number.isFinite(t.est) && t.est > 0 ? t.est / 2 : (W[t.pr] || 1.5));

  GF.wlDragStart = (ev, id) => { ev.dataTransfer.setData('text/task-id', id); ev.dataTransfer.effectAllowed = 'copy'; };
  GF.wlDragOver = (ev) => { ev.preventDefault(); ev.currentTarget.classList.add('wl-over'); };
  GF.wlDragLeave = (ev) => { ev.currentTarget.classList.remove('wl-over'); };
  GF.wlDrop = async (ev, personId) => {
    ev.preventDefault(); ev.currentTarget.classList.remove('wl-over');
    const taskId = ev.dataTransfer.getData('text/task-id');
    if (!taskId || !personId) return;
    const t = GF.task(taskId);
    if (t && (t.owner === personId || (t.helpers || []).includes(personId))) {
      GF.toast(AL('Already on this task', 'Веќе е на задачата'), 'info'); return;
    }
    try {
      await GF.API.assign(taskId, personId, 'assignee');
      if (t && !(t.helpers || []).includes(personId)) (t.helpers = t.helpers || []).push(personId);
      GF.toast(AL('Added as helper', 'Додаден како помошник'), 'success');
      GF.render.all();
    } catch (e) { GF.toast(AL('Could not assign: ', 'Неуспешно доделување: ') + e.message, 'error'); }
  };

  GF.views.workload = () => {
    const tasks = GF.scopedTasks(GF.state.selWeek).filter(t => t.status !== 'done');
    const per = {};   // personId -> {pts, tasks[]}
    tasks.forEach(t => {
      const people = [t.owner].concat(t.helpers || []).filter(Boolean);
      people.forEach(p => { (per[p] = per[p] || { pts: 0, tasks: [] }); per[p].pts += load(t) / people.length; per[p].tasks.push(t); });
    });
    // every known person renders, even with zero load — they're drop targets
    Object.keys(GF.PEOPLE).forEach(p => { per[p] = per[p] || { pts: 0, tasks: [] }; });

    const rows = Object.entries(per)
      .sort((a, b) => b[1].pts - a[1].pts)
      .map(([pid, d]) => {
        const p = GF.PEOPLE[pid] || { name: pid, roleLabel: '' };
        const pct = Math.min(100, Math.round((d.pts / CAP) * 100));
        const tier = pct >= 90 ? 'hot' : pct >= 60 ? 'warm' : 'ok';
        const chips = d.tasks.slice(0, 8).map(t => `
          <span class="wl-chip" draggable="true" ondragstart="GF.wlDragStart(event,'${GF.esc(t.id)}')"
            title="${GF.esc(t.title)}" onclick="GF.WWF&&GF.WWF.xrJump&&GF.WWF.xrJump('${GF.esc(t.id)}','${GF.esc(t.week_start || '')}')">
            ${GF.esc(t.title.length > 34 ? t.title.slice(0, 33) + '…' : t.title)}</span>`).join('');
        return `<div class="wl-row" ondragover="GF.wlDragOver(event)" ondragleave="GF.wlDragLeave(event)"
                     ondrop="GF.wlDrop(event,'${GF.esc(pid)}')">
          <div class="wl-who">${GF.avatar(pid, 32)}
            <div class="wl-name"><b>${GF.esc(p.name)}</b><span>${GF.esc(p.roleLabel || '')}</span></div></div>
          <div class="wl-bar"><div class="wl-fill wl-${tier}" style="width:${pct}%"></div>
            <span class="wl-pts">${d.pts.toFixed(1)} ${AL('pts', 'поени')}</span></div>
          <div class="wl-chips">${chips || `<span class="wl-none">${AL('No load this week', 'Нема оптовареност')}</span>`}</div>
        </div>`;
      }).join('');

    return `${GF.viewHead('workload', 'workload')}
      <div class="wl-hint">${AL('Drag a task onto a person to add them as a helper. Weights: critical 3 · high 2 · medium 1.5 · low 1 (estimated hours override).',
                                'Повлечете задача врз личност за да ја додадете како помошник. Тежини: критично 3 · високо 2 · средно 1.5 · ниско 1 (проценетите часови имаат предност).')}</div>
      <div class="wl-list">${rows}</div>`;
  };
})();
