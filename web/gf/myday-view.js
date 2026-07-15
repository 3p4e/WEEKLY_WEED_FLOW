/* myday-view.js — the personal "today" screen (mockup my-day.html).
   For EVERYONE, operators most of all: today's agenda (tasks scheduled on
   today's weekday or due today), completed-earlier group, pending
   acknowledgments with inline accept/decline, and a small KPI band.

   All agenda data comes from the already-loaded week board (GF.state.tasks
   scoped to me); acknowledgments ride the same /approvals/pending aggregate
   the Approvals view uses (the `mine` list is role-free). */

(function () {
  GF.WWF._myday = { acks: null };

  const meId = () => (GF.API.user || {}).id;
  const myTasks = () => {
    const me = meId();
    return GF.weekTasks(GF.calendar.todayId)
      .filter(t => t.owner === me || (t.helpers || []).includes(me));
  };
  const isToday = (t) =>
    (t.days || []).includes(GF.todayDay) || (t.due && t.due === GF.todayISO());
  const doneToday = (t) => t.status === 'done' &&
    (t.completed_date ? t.completed_date === GF.todayISO() : true);

  const prPill = (t) => (t.pr === 'critical' || t.pr === 'high')
    ? `<span class="prtag ${t.pr}">${GF.prLabel(t.pr)}</span>` : '';

  const row = (t) => {
    const d = GF.dep(t.dept);
    return `
    <div class="md-task${t.status === 'done' ? ' is-done' : ''}">
      <button class="check ${t.status === 'done' ? 'done' : ''}"
        onclick="event.stopPropagation();GF.toggleDone('${t.id}')">${t.status === 'done' ? GF.icon('check', 'icon', '#03130C') : ''}</button>
      <div class="md-b" onclick="GF.WWF.openWorklog&&GF.WWF.openWorklog('${t.id}')">
        <div class="md-t">${GF.esc(t.title)}</div>
        <div class="md-m">
          <span class="dn" style="color:${d.color}">${GF.esc(GF.depAbbr(t.dept))}</span>
          ${t.due ? `<span class="md-due${t.due < GF.todayISO() && t.status !== 'done' ? ' overdue' : ''}">${GF.icon('calendar', 'icon')}${GF.esc(t.due)}</span>` : ''}
          ${prPill(t)}
          ${GF.progress(t) > 0 ? `<span class="tp-val">${GF.progress(t)}%</span>` : ''}
        </div>
      </div>
      <span class="pill s-${t.status}" onclick="event.stopPropagation();GF.pickStatus('${t.id}')">
        <span class="dot" style="background:currentColor;opacity:.7"></span>${GF.statusLabel(t.status)}</span>
    </div>`;
  };

  const loadAcks = async () => {
    try {
      const p = await GF.API.approvalsPending();
      GF.WWF._myday.acks = (p && p.mine) || [];
    } catch (e) { GF.WWF._myday.acks = []; }
    if (GF.state.view === 'myday') GF.render.all();
  };

  GF.views.myday = () => {
    const st = GF.WWF._myday;
    if (st.acks === null) { st.acks = undefined; loadAcks(); }
    const mine = myTasks();
    const today = mine.filter(isToday);
    const open = today.filter(t => t.status !== 'done')
      .sort((a, b) => ['critical', 'high', 'medium', 'low'].indexOf(a.pr) - ['critical', 'high', 'medium', 'low'].indexOf(b.pr));
    const done = mine.filter(t => isToday(t) && doneToday(t));
    const acks = Array.isArray(st.acks) ? st.acks : [];
    const kpi = (v, l, c) => `<div class="kpi"><div class="kpi-v" style="color:${c}">${v}</div><div class="kpi-l">${l}</div></div>`;
    const head = GF.viewHead ? GF.viewHead('my_day', 'my_day_sub') : `<h2>${AL('My Day', 'Мојот ден')}</h2>`;
    const ackBlock = acks.length ? `
      <div class="panel" style="margin-bottom:12px">
        <div class="panel-head"><span class="ttl">${AL('Awaiting your acknowledgment', 'Чека ваша потврда')}</span><span class="cnt">${acks.length}</span></div>
        <div class="panel-body" style="padding:6px 14px 12px">${acks.map(x => `
          <div class="apv-row">
            <span class="fs-dot" style="background:var(--orange)"></span>
            <div class="apv-b"><div class="apv-t">${GF.esc(x.title)}</div>
              <div class="apv-sub">${AL('assigned by', 'доделено од')} ${GF.esc((GF.PEOPLE[x.assigned_by] || {}).name || '—')}</div></div>
            <button class="btn btn-sm btn-primary" onclick="GF.WWF.mdAck('${x.task_id}',true)">✓ ${AL('Accept', 'Прифати')}</button>
            <button class="btn btn-sm" onclick="GF.WWF.mdAck('${x.task_id}',false)">${AL('Decline', 'Одбиј')}</button>
          </div>`).join('')}</div>
      </div>` : '';
    return head + `
      <div class="dash-kpis">
        ${kpi(open.length, AL('Open today', 'Отворени денес'), open.length ? 'var(--orange)' : 'var(--green)')}
        ${kpi(done.length, GF.t('done_count'), 'var(--green)')}
        ${kpi(acks.length, AL('To acknowledge', 'За потврда'), acks.length ? 'var(--amber)' : 'var(--green)')}
        ${kpi(mine.filter(t => t.status === 'stuck').length, GF.t('stuck'), 'var(--red)')}
      </div>
      ${ackBlock}
      <div class="panel">
        <div class="panel-head"><span class="ttl">${AL('Today', 'Денес')} · ${GF.dayLabel(GF.todayDay)}</span><span class="cnt">${open.length}</span></div>
        <div class="panel-body" style="padding:6px 14px 12px">
          ${open.map(row).join('') || `<div class="fr-empty" style="padding:6px 0">${AL('Nothing scheduled for today.', 'Ништо закажано за денес.')}</div>`}
          ${done.length ? `<div class="nav-group" style="padding:12px 0 4px">${AL('Completed earlier', 'Завршено претходно')}</div>${done.map(row).join('')}` : ''}
        </div>
      </div>`;
  };

  GF.WWF.mdAck = async (taskId, accepted) => {
    let reason = null;
    if (!accepted) reason = prompt(AL('Reason for declining (optional):', 'Причина за одбивање (незадолжително):')) || null;
    try {
      await GF.API.ack(taskId, accepted, reason);
      GF.toast(accepted ? '✓' : AL('Declined', 'Одбиено'), 'success');
      GF.WWF._myday.acks = null;
      if (GF.WWF._apv) GF.WWF._apv.data = null;   // Approvals re-fetches
      GF.render.all();
    } catch (e) { GF.toast(AL('Failed: ', 'Неуспешно: ') + e.message, 'error'); }
  };

  GF.WWF._registerFullPageView({
    key: 'myday', icon: 'sun',
    label: () => AL('My Day', 'Мојот ден'),
    insertBefore: 'mywork',   // Operations rail group, beside My Week
    badge: () => Array.isArray(GF.WWF._myday.acks) && GF.WWF._myday.acks.length > 0,
  });
})();
