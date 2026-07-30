/* depthome-view.js — the department home screen: the landing view for
   department members (operators + their manager). Week-scoped (the week
   strip stays visible — this is a BUILT-IN view, deliberately NOT
   _registerFullPageView), showing the user's own department's week through
   the panels its template defines (GF.DEPT_TEMPLATES in dept-templates.js):
   grouped-by-attribute boards (rooms / batches / equipment / areas), status
   queues, or in/out flow columns — with a generic status layout when the
   department has no template. Nav row + non-dept bounce live in render.js
   (same built-in pattern as the exec view). Loads after worklog.js. */
window.GF = window.GF || {};
GF.views = GF.views || {};

(() => {
  const L = (en, mk) => (GF.state.lang === 'mk' ? mk : en);

  // Compact card — the design system's .mw-tcard (depthome-*.html), carrying
  // the SAME information the old kcard did: nothing the operator could see
  // before may quietly disappear in a restyle. Click still deep-links to the
  // expanded card in My Week (card actions all live there). Department
  // identity is ONE variable: --mw-acc tints the edge, box and chips, exactly
  // the design's domain-tint pattern.
  const card = (t) => {
    const d = GF.dep(t.dept);
    const attrs = GF.attrChipData ? GF.attrChipData(t) : [];
    const meta = [
      `<span class="mw-tcard__dept">${GF.esc(GF.depAbbr(t.dept))}</span>`,
      ...attrs.map(a => `<span class="mw-attr">${GF.esc(a.label)} <b>${GF.esc(a.val)}</b></span>`),
      ...(t.tags || []).slice(0, 3).map(tag => `<span class="mw-htag">#${GF.esc(tag)}</span>`),
      t.sessionHours ? `<span class="mw-sub">${GF.esc(t.sessionHours)}h</span>` : '',
      t.due ? `<span class="mw-due${(t.status !== 'done' && t.due < GF.todayISO()) ? ' mw-due--over' : ''}">${GF.esc(t.due.slice(5))}</span>` : '',
      `<span class="prtag ${t.pr}">${GF.prLabel(t.pr)}</span>`,
    ].filter(Boolean).join('');
    return `<div class="mw-tcard${t.status === 'done' ? ' mw-tcard--done' : ''}" style="--mw-acc:${d.color}" onclick="GF.state.expanded.add('${t.id}');GF.setView('mywork')">
      <span class="mw-tcard__box"></span>
      <div class="mw-tcard__main">
        <div class="mw-tcard__title" title="${GF.esc(t.title)}">${GF.esc(t.title)}</div>
        <div class="mw-tcard__meta">${meta}</div>
      </div>
      <div class="mw-tcard__right">
        <span class="mw-st mw-st--${t.status}">${GF.statusLabel(t.status)}</span>
        ${GF.avatars([t.owner, ...(t.helpers || [])], 20)}
      </div></div>`;
  };

  const grid = (items) => `<div class="dh-grid">${items.map(card).join('') || `<div class="kempty">—</div>`}</div>`;

  // Named queue filters the templates reference by key.
  const week = () => GF.calendar.weeks[GF.state.selWeek];
  const QUEUES = {
    due_week: (t) => t.due && t.status !== 'done' && week() && t.due <= GF.localDateStr(week().end),
    in_review: (t) => t.status === 'review',
    stuck: (t) => t.status === 'stuck',
    handoff_ready: (t) => (t.status === 'done' || t.status === 'review') && !!GF.HANDOFF[t.dept],
    incidents: (t) => (t.attrs || {}).incident_type === 'incident' || t.status === 'stuck',
  };

  const panel = (title, count, body) => `
    <div class="panel dh-panel">
      <div class="panel-head"><span class="ttl">${title}</span><span class="cnt">${count}</span></div>
      <div class="panel-body">${body}</div>
    </div>`;

  const renderPanel = (p, tasks) => {
    const title = GF.esc(GF.tplLabel(p));
    if (p.kind === 'group') {
      const groups = new Map();
      tasks.forEach(t => {
        const k = (t.attrs || {})[p.attr];
        const key = (k != null && k !== '') ? String(k) : null;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(t);
      });
      const named = [...groups.entries()].filter(([k]) => k !== null).sort((a, b) => a[0].localeCompare(b[0]));
      const rest = groups.get(null) || [];
      const body = (named.map(([k, items]) => `
          <div class="dh-group"><div class="dh-group-head"><span class="dh-group-key">${GF.esc(k)}</span><span class="kcount">${items.length}</span></div>${grid(items)}</div>`).join('')
        + (rest.length ? `<div class="dh-group"><div class="dh-group-head"><span class="dh-group-key dh-ungrouped">${L('Ungrouped', 'Негрупирано')}</span><span class="kcount">${rest.length}</span></div>${grid(rest)}</div>` : ''))
        || `<div class="kempty" style="padding:18px;text-align:center">—</div>`;
      return panel(title, tasks.length, body);
    }
    if (p.kind === 'queue') {
      const f = QUEUES[p.key] || (() => false);
      const items = tasks.filter(f);
      return panel(title, items.length, grid(items));
    }
    if (p.kind === 'types') {
      const body = p.types.map(ty => {
        const items = tasks.filter(t => t.type === ty);
        return `<div class="dh-group"><div class="dh-group-head"><span class="dh-group-key">${GF.esc(GF.taskTypeLabel(ty))}</span><span class="kcount">${items.length}</span></div>${grid(items)}</div>`;
      }).join('');
      return panel(title, tasks.length, body);
    }
    if (p.kind === 'inout') {
      const col = (v, lbl) => {
        const items = tasks.filter(t => (t.attrs || {})[p.attr] === v);
        return `<div class="dh-col"><div class="dh-group-head"><span class="dh-group-key">${lbl}</span><span class="kcount">${items.length}</span></div>${grid(items)}</div>`;
      };
      const other = tasks.filter(t => !['in', 'out'].includes((t.attrs || {})[p.attr]));
      return panel(title, tasks.length, `<div class="dh-inout">${col('in', L('Inbound', 'Влез'))}${col('out', L('Outbound', 'Излез'))}</div>`
        + (other.length ? `<div class="dh-group"><div class="dh-group-head"><span class="dh-group-key dh-ungrouped">${L('Other', 'Останато')}</span><span class="kcount">${other.length}</span></div>${grid(other)}</div>` : ''));
    }
    return '';
  };

  // Generic fallback for a department without a template: status queues.
  const GENERIC = [
    { kind: 'queue', key: 'due_week', en: 'Due this week', mk: 'Рок оваа недела' },
    { kind: 'queue', key: 'in_review', en: 'In review', mk: 'На преглед' },
    { kind: 'queue', key: 'stuck', en: 'Stuck / blocked', mk: 'Блокирани' },
  ];

  GF.views.depthome = function () {
    const myDept = GF.myDeptId && GF.myDeptId();
    if (!myDept) return `<div class="kempty" style="padding:40px;text-align:center">—</div>`;
    const d = GF.dep(myDept);
    const tpl = GF.deptTemplate ? GF.deptTemplate(myDept) : null;
    const tasks = GF.weekTasks(GF.state.selWeek).filter(t => t.dept === myDept);

    const presets = (tpl && tpl.presets && GF.can('create')) ? `
      <div class="dh-presets">
        <span class="dh-presets-lbl">${L('Quick add', 'Брзо додавање')}</span>
        ${tpl.presets.map((p, i) =>
          `<span class="chip-opt preset-chip" onclick="GF.openAdd(GF.state.selWeek);GF.applyPreset(${i})">${GF.icon('plus', 'icon')}${GF.esc(GF.tplLabel(p))}</span>`).join('')}
      </div>` : '';

    const done = tasks.filter(t => t.status === 'done').length;
    const head = `
      <div class="view-head dh-head" style="--dh-color:${d.color}">
        <span class="dh-icon">${GF.icon(d.icon, 'icon', d.color)}</span>
        <div><div class="view-title">${GF.esc(GF.depName(myDept))}</div>
          <div class="view-sub">${L('Department home — this week', 'Почетна на одделот — оваа недела')}
            · ${tasks.length} ${L('tasks', 'задачи')} · ${done} ${L('done', 'завршени')}</div></div>
        <div class="spacer"></div>
        ${GF.can('create') ? `<button class="btn btn-orange btn-sm" onclick="GF.openAdd(${GF.state.selWeek})">${GF.icon('plus', 'icon', '#fff')}${GF.t('new_task_btn')}</button>` : ''}
      </div>`;

    const empty = !tasks.length ? `
      <div class="dh-empty">
        <div class="dh-empty-title">${L('Nothing planned for this week yet.', 'Сè уште нема планирано за оваа недела.')}</div>
        <div class="dh-empty-sub">${L('Start from a quick-add above, or create a task.', 'Почнете со брзо додавање погоре, или креирајте задача.')}</div>
      </div>` : '';

    const panels = (tpl && tpl.home ? tpl.home : GENERIC).map(p => renderPanel(p, tasks)).join('');
    // --mw-acc on the container: the design's ONE-variable dept tint. Every
    // panel edge and chip below inherits it; cards also set their own (same
    // value here, but a card rendered outside this view must not depend on
    // an ancestor happening to provide it).
    return head + presets + empty + `<div class="dh-panels" style="--mw-acc:${d.color}">${panels}</div>`;
  };
})();
