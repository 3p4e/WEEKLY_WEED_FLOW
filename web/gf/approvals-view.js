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
  GF.WWF._apv = { data: null, docs: null, coqs: null, loading: false, error: null, qTab: 'pending' };

  GF.WWF.loadApprovals = async () => {
    const st = GF.WWF._apv;
    st.loading = true; st.error = null;
    try {
      const [pending, docs, coqs] = await Promise.all([
        GF.API.approvalsPending(),
        GF.API.documentStatus ? GF.API.documentStatus({ kind: 'report' }).catch(() => null) : null,
        // QC review/approve/release folds into the unified queue when the LIMS
        // is populated (QCSOP 012 CoQ: DRAFT→awaiting review, APPROVED→released,
        // VOIDED→sent back). Absent / role-forbidden → null, and those rows just
        // don't render — never fabricated.
        GF.API.qcCoqs ? GF.API.qcCoqs().catch(() => null) : null,
      ]);
      st.data = pending; st.docs = docs; st.coqs = coqs;
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
      <div class="apv-b" onclick="GF.WWF.xrJump&&GF.WWF.xrJump('${GF.esc(x.task_id)}','')">
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

  // ── Unified sign-off queue (mockup approvals.html) ─────────────────────
  // One pending / approved / rejected surface with live counts, folding the
  // task acknowledgments + draft-document locks already loaded here together
  // with QC CoQ review/approve/release items (when the LIMS is populated).
  // ADDITIVE: rows use .mwq-* classes — never .apv-row — so the existing
  // acknowledgment flow (and every e2e selector it owns) is left untouched.
  GF.WWF.apvTab = (tab) => {
    GF.WWF._apv.qTab = tab;
    if (GF.state.view === 'approvals') GF.render.all();
  };

  const QICON = { task: 'check', doc: 'file', coq: 'flask' };
  const qKindLbl = (k) => k === 'coq' ? AL('QC', 'КК') : k === 'doc' ? AL('DOC', 'ДОК') : AL('TASK', 'ЗАД');
  const qItem = (kind, title, sub, when, tone) => ({ kind, title, sub: sub || '', when: when || '', tone: tone || 'info' });

  const buildQueue = (st) => {
    const mine = (st.data && st.data.mine) || [];
    const team = (st.data && st.data.team) || [];
    const drafts = (((st.docs && st.docs.departments) || []).filter(d => d.status === 'draft'));
    const coqs = (st.coqs || []);
    const dname = (d) => GF.state.lang === 'mk' && d.name_mk ? d.name_mk
      : (d.name || AL('Org-wide', 'Целата организација'));
    const coqTitle = (c) => c.coq_number || c.product_name || AL('Certificate of Quality', 'Сертификат за квалитет');
    const pending = [
      ...mine.map(x => qItem('task', x.title,
        `${AL('your acknowledgment · from', 'ваша потврда · од')} ${person(x.assigned_by)}`,
        ago(x.assigned_at), 'warn')),
      ...team.map(x => qItem('task', x.title,
        `${AL('waiting on', 'се чека')} ${person(x.user_id)}`,
        ago(x.assigned_at), 'warn')),
      ...drafts.map(d => qItem('doc', dname(d),
        AL('draft — awaiting lock', 'нацрт — чека заклучување'),
        d.updated_at ? ago(d.updated_at) : '', 'info')),
      ...coqs.filter(c => c.status === 'DRAFT').map(c => qItem('coq', coqTitle(c),
        `${AL('CoQ — awaiting QC review · by', 'CoQ — чека КК преглед · од')} ${person(c.compiled_by)}`,
        c.compiled_at ? ago(c.compiled_at) : '', 'warn')),
    ];
    const approved = coqs.filter(c => c.status === 'APPROVED').map(c => qItem('coq', coqTitle(c),
      `${AL('CoQ reviewed — released · by', 'CoQ прегледан — издаден · од')} ${person(c.reviewed_by)}`,
      c.reviewed_at ? ago(c.reviewed_at) : '', 'good'));
    const rejected = coqs.filter(c => c.status === 'VOIDED').map(c => qItem('coq', coqTitle(c),
      `${AL('CoQ voided', 'CoQ поништен')}${c.void_reason ? ' · ' + c.void_reason : ''} · ${person(c.voided_by)}`,
      c.voided_at ? ago(c.voided_at) : '', 'bad'));
    return { pending, approved, rejected };
  };

  const qRow = (it) => `
    <div class="mwq-row mwq-row--${it.tone}">
      <div class="mwq-ic mwq-ic--${it.tone}">${GF.icon(QICON[it.kind] || 'check')}</div>
      <div class="mwq-body">
        <div class="mwq-t">${GF.esc(it.title)}</div>
        <div class="mwq-sub">${GF.esc(it.sub)}${it.when ? ` · ${GF.esc(it.when)}` : ''}</div>
      </div>
      <span class="mwq-kind">${GF.esc(qKindLbl(it.kind))}</span>
    </div>`;

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
    // Unified queue (additive overlay) — real data only; QC rows only when the
    // LIMS returned CoQs. .mwq-* rows never collide with the .apv-row flow.
    const q = buildQueue(st);
    const qc = { pending: q.pending.length, approved: q.approved.length, rejected: q.rejected.length };
    const qtab = (q[st.qTab] ? st.qTab : 'pending');
    const qrows = q[qtab];
    const coqUnwired = st.coqs == null;
    const qTabBtn = (key, en, mk) =>
      `<button type="button" class="mwq-tab${qtab === key ? ' on' : ''}" onclick="GF.WWF.apvTab('${key}')">${AL(en, mk)}<span class="mwq-c">${qc[key]}</span></button>`;
    return head + `
      <div class="dash-kpis">
        ${kpi(mine.length, AL('Yours to acknowledge', 'Ваши за потврда'), mine.length ? 'var(--orange)' : 'var(--green)')}
        ${kpi(team.length, AL('Team pending', 'Тим во исчекување'), team.length ? 'var(--amber)' : 'var(--green)')}
        ${kpi(drafts.length, AL('Drafts awaiting lock', 'Нацрти за заклучување'), drafts.length ? 'var(--blue)' : 'var(--green)')}
        ${kpi(stuck.length, GF.t('stuck'), stuck.length ? 'var(--red)' : 'var(--green)')}
      </div>
      <div class="mwq panel">
        <div class="mwq-head">
          <span class="mwq-ttl">${AL('Sign-off queue', 'Редица за потпис')}</span>
          <div class="mwq-tabs">
            ${qTabBtn('pending', 'Pending', 'На чекање')}
            ${qTabBtn('approved', 'Approved', 'Одобрени')}
            ${qTabBtn('rejected', 'Rejected', 'Одбиени')}
          </div>
        </div>
        <div class="mwq-list">
          ${qrows.length ? qrows.map(qRow).join('')
            : `<div class="mwq-empty">${qtab === 'pending'
                ? AL('Nothing pending.', 'Нема ништо во исчекување.')
                : AL('Nothing here.', 'Нема ништо тука.')}</div>`}
          ${(qtab !== 'pending' && coqUnwired)
            ? `<div class="mwq-defer">${GF.icon('info')}<span>${AL('Populates from the QC LIMS (CoQ review / approve / release) when available; declined-acknowledgment history is not yet exposed by the backend.', 'Се пополнува од КК LIMS (CoQ преглед / одобрување / издавање) кога е достапно; историјата на одбиени потврди сè уште не е изложена од системот.')}</span></div>`
            : ''}
        </div>
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
        <div class="apv-row" onclick="GF.WWF.xrJump&&GF.WWF.xrJump('${GF.esc(t.id)}','${GF.esc(t.week_start || '')}')">
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
