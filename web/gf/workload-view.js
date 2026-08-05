/* workload-view.js — crew capacity for the selected week. Global: GF.views.workload
   Per-person load bars (priority-weighted points
   set) over the week's tasks, with drag-and-drop: drag a task chip onto a
   person to add them as a helper (the owner is immutable by design — POST
   /tasks always owns as creator — so drag ADDS an assignee via the existing
   /tasks/{id}/assignees endpoint rather than transferring ownership).
   Managers/execs only (nav-gated by GF.can('team')). From the Mass Weed mockups. */
window.GF = window.GF || {};

(function () {
  const W = { critical: 3, high: 2, medium: 1.5, low: 1 };
  const CAP = 12;   // soft weekly capacity in points — display heuristic only

  const load = (t) => (W[t.pr] || 1.5);

  // A person with more than 8 tasks this week only showed the first 8, with
  // no indicator at all that more existed — the rest were silently dropped.
  // A "+N" pill now toggles that person's row to show every chip.
  GF.state.wlExpandedPeople = GF.state.wlExpandedPeople || new Set();
  GF.wlToggle = (personId) => {
    const s = GF.state.wlExpandedPeople;
    if (s.has(personId)) s.delete(personId); else s.add(personId);
    GF.render.all();
  };

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

    // KPI band (Mass Weed mockup workload.html): crew-wide load at a glance.
    // rawPct is UNCAPPED here (a person can be >100% of the soft capacity),
    // unlike the per-row bar which clamps for display.
    const people = Object.values(per);
    const rawPct = (d) => (d.pts / CAP) * 100;
    const kOpen = tasks.length;
    const kOver = people.filter(d => rawPct(d) > 100).length;
    const kFree = people.filter(d => rawPct(d) < 70).length;
    const kAvg = people.length ? Math.round(people.reduce((s, d) => s + rawPct(d), 0) / people.length) : 0;
    const band = `<div class="ana-tiles wl-kpis">
      ${GF.kpiTile(AL('Open Tasks', 'Отворени задачи'), kOpen, AL('across crew', 'во екипата'))}
      ${GF.kpiTile(AL('Overloaded', 'Преоптоварени'), kOver, AL('over capacity', 'над капацитет'))}
      ${GF.kpiTile(AL('Available', 'Достапни'), kFree, AL('under 70%', 'под 70%'))}
      ${GF.kpiTile(AL('Avg Load', 'Просечна оптовареност'), kAvg + '%', AL('of capacity', 'од капацитет'))}</div>`;

    const rows = Object.entries(per)
      .sort((a, b) => b[1].pts - a[1].pts)
      .map(([pid, d]) => {
        const p = GF.PEOPLE[pid] || { name: pid, roleLabel: '' };
        const pct = Math.min(100, Math.round((d.pts / CAP) * 100));
        const tier = pct >= 90 ? 'hot' : pct >= 60 ? 'warm' : 'ok';
        const expanded = GF.state.wlExpandedPeople.has(pid);
        const shownTasks = expanded ? d.tasks : d.tasks.slice(0, 8);
        const chips = shownTasks.map(t => `
          <span class="wl-chip" draggable="true" ondragstart="GF.wlDragStart(event,'${GF.esc(t.id)}')"
            title="${GF.esc(t.title)} · ${GF.esc(GF.prLabel(t.pr))}" onclick="GF.WWF&&GF.WWF.xrJump&&GF.WWF.xrJump('${GF.esc(t.id)}','${GF.esc(t.week_start || '')}')">
            <i class="wl-dot ${GF.esc(t.pr || 'medium')}"></i>${GF.esc(t.title.length > 32 ? t.title.slice(0, 31) + '…' : t.title)}</span>`).join('')
          + (d.tasks.length > 8 ? `<span class="wl-chip" style="cursor:pointer;color:var(--ink-3)"
              onclick="GF.wlToggle('${GF.esc(pid)}')">${expanded ? AL('less', 'помалку') : `+${d.tasks.length - 8}`}</span>` : '');
        return `<div class="wl-row" ondragover="GF.wlDragOver(event)" ondragleave="GF.wlDragLeave(event)"
                     ondrop="GF.wlDrop(event,'${GF.esc(pid)}')">
          <div class="wl-who">${GF.avatar(pid, 32)}
            <div class="wl-name"><b>${GF.esc(p.name)}</b><span>${GF.esc(p.roleLabel || '')}</span></div></div>
          <div class="wl-bar"><div class="wl-fill wl-${tier}" style="transform:scaleX(${pct / 100})"></div>
            <span class="wl-pts">${d.pts.toFixed(1)} ${AL('pts', 'поени')}</span></div>
          <div class="wl-chips">${chips || `<span class="wl-none">${AL('No load this week', 'Нема оптовареност')}</span>`}</div>
        </div>`;
      }).join('');

    return `${GF.viewHead('workload', 'workload')}
      ${band}
      <div class="wl-hint">${AL('Drag a task onto a person to add them as a helper. Weights: critical 3 · high 2 · medium 1.5 · low 1.',
                                'Повлечете задача врз личност за да ја додадете како помошник. Тежини: критично 3 · високо 2 · средно 1.5 · ниско 1 (проценетите часови имаат предност).')}</div>
      <div class="wl-list">${rows}</div>`;
  };
})();
