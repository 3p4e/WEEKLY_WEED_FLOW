/* approvals-view.js — everything waiting on a decision (mockup approvals.html,
   mapped to what actually exists in WWF; the mockup's COA/PO/order approvals
   are LIMS territory and stay out until those models exist).

   Sections:
     · Awaiting YOUR acknowledgment — accept / decline inline (everyone with
       the view; operators get the same rows on My Day).
     · Awaiting the team's acknowledgment — follow-up list (dept-scoped for
       department managers, org-wide for executives).
     · Weekly documents still in draft (awaiting lock) — from /status.
     · Stuck tasks in your scope — from the loaded week board.

   Manager rail group; guard = every role above base USER. */

(function () {
  GF.WWF._apv = { data: null, docs: null, loading: false, error: null };

  GF.WWF.loadApprovals = async () => {
    const st = GF.WWF._apv;
    st.loading = true; st.error = null;
    try {
      const [pending, docs] = await Promise.all([
        GF.API.approvalsPending(),
        GF.API.documentStatus ? GF.API.documentStatus({ kind: 'report' }).catch(() => null) : null,
      ]);
      st.data = pending; st.docs = docs;
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'approvals') GF.render.all();
  };

  const person = (id) => (GF.PEOPLE[id] && GF.PEOPLE[id].name) || AL('Someone', 'Некој');
  const ago = (iso) => {
    const h = Math.round((Date.now() - new Date(iso)) / 36e5);
    if (h < 1) return AL('just now', 'штотуку');
    if (h < 24) return h + AL('h ago', 'ч.');
    return Math.round(h / 24) + AL('d ago', 'д.');
  };

  const ackRow = (x, mine) => `
    <div class="apv-row">
      <span class="fs-dot" style="background:var(--${{critical:'red',high:'orange'}[x.priority] || 'blue'})"></span>
      <div class="apv-b" onclick="GF.WWF.xrJump&&GF.WWF.xrJump('${x.task_id}','')">
        <div class="apv-t">${GF.esc(x.title)}</div>
        <div class="apv-sub">${mine
          ? `${AL('assigned by', 'доделено од')} ${GF.esc(person(x.assigned_by))}`
          : `${AL('waiting on', 'се чека')} <b>${GF.esc(person(x.user_id))}</b>`} · ${ago(x.assigned_at)}
          ${x.due_date ? ` · ${GF.t('due')} ${GF.esc(x.due_date)}` : ''}</div>
      </div>
      ${mine ? `
        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();GF.WWF.apvAck('${x.task_id}',true)">✓ ${AL('Accept', 'Прифати')}</button>
        <button class="btn btn-sm" onclick="event.stopPropagation();GF.WWF.apvAck('${x.task_id}',false)">${AL('Decline', 'Одбиј')}</button>` : ''}
    </div>`;

  GF.WWF.apvAck = async (taskId, accepted) => {
    let reason = null;
    if (!accepted) {
      reason = prompt(AL('Reason for declining (optional):', 'Причина за одбивање (незадолжително):')) || null;
    }
    try {
      await GF.API.ack(taskId, accepted, reason);
      GF.toast(accepted ? '✓' : AL('Declined', 'Одбиено'), 'success');
      GF.WWF.loadApprovals();
      if (GF.WWF._myday) GF.WWF._myday.acks = null;   // My Day re-fetches
    } catch (e) { GF.toast(AL('Failed: ', 'Неуспешно: ') + e.message, 'error'); }
  };

  const sec = (label, count, body) => `
    <div class="panel" style="margin-bottom:12px">
      <div class="panel-head"><span class="ttl">${label}</span><span class="cnt">${count}</span></div>
      <div class="panel-body" style="padding:6px 14px 12px">${body}</div>
    </div>`;
  const empty = () => `<div class="fr-empty" style="padding:6px 0">${AL('Nothing pending.', 'Нема ништо во исчекување.')}</div>`;

  GF.views.approvals = () => {
    const st = GF.WWF._apv;
    if (!st.data && !st.loading && !st.error) GF.WWF.loadApprovals();
    const head = GF.viewHead ? GF.viewHead('approvals', 'approvals_sub') : `<h2>${AL('Approvals', 'Одобрувања')}</h2>`;
    if (st.loading || (!st.data && !st.error)) {
      return head + `<div class="mw-skel" style="height:64px;margin-bottom:8px"></div>
        <div class="mw-skel" style="height:64px"></div>`;
    }
    if (st.error) {
      return head + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadApprovals()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const mine = (st.data.mine || []);
    const team = (st.data.team || []);
    // draft documents awaiting lock (org row: department_id absent)
    const drafts = ((st.docs && st.docs.departments) || []).filter(d => d.status === 'draft');
    const stuck = GF.scopedTasks ? GF.scopedTasks(GF.state.selWeek).filter(t => t.status === 'stuck') : [];
    const kpi = (v, l, c) => `<div class="kpi"><div class="kpi-v" style="color:${c}">${v}</div><div class="kpi-l">${l}</div></div>`;
    return head + `
      <div class="dash-kpis">
        ${kpi(mine.length, AL('Yours to acknowledge', 'Ваши за потврда'), mine.length ? 'var(--orange)' : 'var(--green)')}
        ${kpi(team.length, AL('Team pending', 'Тим во исчекување'), team.length ? 'var(--amber)' : 'var(--green)')}
        ${kpi(drafts.length, AL('Drafts awaiting lock', 'Нацрти за заклучување'), drafts.length ? 'var(--blue)' : 'var(--green)')}
        ${kpi(stuck.length, GF.t('stuck'), stuck.length ? 'var(--red)' : 'var(--green)')}
      </div>
      ${sec(AL('Awaiting your acknowledgment', 'Чека ваша потврда'), mine.length,
            mine.map(x => ackRow(x, true)).join('') || empty())}
      ${sec(AL('Awaiting the team', 'Чека потврда од тимот'), team.length,
            team.map(x => ackRow(x, false)).join('') || empty())}
      ${sec(AL('Weekly documents in draft', 'Неделни документи во нацрт'), drafts.length,
            drafts.map(d => `
        <div class="apv-row" onclick="GF.setView('report')">
          <span class="fs-dot" style="background:var(--amber)"></span>
          <div class="apv-b"><div class="apv-t">${GF.esc(GF.state.lang === 'mk' && d.name_mk ? d.name_mk : (d.name || AL('Org-wide', 'Целата организација')))}</div>
            <div class="apv-sub">${AL('draft — awaiting lock', 'нацрт — чека заклучување')}${d.updated_at ? ' · ' + GF.esc(d.updated_at.slice(0, 16).replace('T', ' ')) : ''}</div></div>
        </div>`).join('') || empty())}
      ${sec(GF.t('stuck'), stuck.length, stuck.map(t => `
        <div class="apv-row" onclick="GF.WWF.xrJump&&GF.WWF.xrJump('${t.id}','${GF.esc(t.week_start || '')}')">
          <span class="fs-dot" style="background:var(--red)"></span>
          <div class="apv-b"><div class="apv-t">${GF.esc(t.title)}</div>
            <div class="apv-sub">${GF.esc(t.blocker || '')}</div></div>
        </div>`).join('') || empty())}`;
  };

  GF.WWF._registerFullPageView({
    key: 'approvals', icon: 'check',
    label: () => AL('Approvals', 'Одобрувања'),
    insertBefore: 'coord',   // Manager rail group (mockup nav.js)
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
    badge: () => { const d = GF.WWF._apv.data; return !!(d && (d.mine || []).length); },
  });
})();
