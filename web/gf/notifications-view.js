/* notifications-view.js — per-user Inbox + shared Activity feed.
   Design: docs/RESEARCH-NOTIFICATIONS-2026-07.md (Linear/GitHub/Asana model:
   always-on inbox, reason labels, unread → read → done lifecycle, feed as the
   separate awareness surface). Bilingual by structure: the backend stores
   verb + structured params; the sentence is rendered HERE per GF.state.lang.
   Delivery: 75s polling + refresh on tab focus; the unread count comes from
   the server (single source of truth for the bell badge). */
window.GF = window.GF || {}; GF.WWF = GF.WWF || {};

(function () {
  const AL = (en, mk) => (GF.state.lang === 'mk' ? mk : en);
  GF.WWF._notif = { items: [], feed: [], tab: 'inbox', filter: '', unread: 0, loaded: false,
                    moreItems: false, moreFeed: false,
                    // Team digest (GET /notifications/digest) — lazy: nothing is
                    // fetched until the panel is first opened.
                    digest: null, digestWindow: 'daily', digestOpen: false, digestLoading: false };
  const PAGE = 50;   // backend default limit on /notifications and /activity

  const who = (id) => (GF.PEOPLE && GF.PEOPLE[id] && GF.PEOPLE[id].name) || AL('Someone', 'Некој');

  // verb + params → sentence, per current language. Structured params only.
  const sentence = (n) => {
    const p = n.params || {}, a = who(n.actor_id), t = p.title || '';
    switch (n.verb) {
      case 'assigned':       return AL(`${a} assigned you: ${t}`, `${a} ви додели: ${t}`);
      case 'commented':      return AL(`${a} commented on: ${t}`, `${a} коментираше на: ${t}`)
                                   + (p.preview ? ` — “${p.preview}”` : '');
      case 'ack':            return p.accepted
                                   ? AL(`${a} accepted: ${t}`, `${a} прифати: ${t}`)
                                   : AL(`${a} declined: ${t}`, `${a} одби: ${t}`);
      case 'status_changed': return AL(`${a}: ${t} → ${GF.statusLabel ? GF.statusLabel(({pending:'pending',ongoing:'working',completed:'done'})[p.new] || p.new) : p.new}`,
                                       `${a}: ${t} → ${p.new}`);
      case 'report_locked':  return AL(`${a} locked the weekly ${p.kind} (${p.week_start})`,
                                       `${a} го заклучи неделниот ${p.kind === 'plan' ? 'план' : 'извештај'} (${p.week_start})`);
      case 'created':        return AL(`${a} created: ${t}`, `${a} креираше: ${t}`);
      case 'unassigned':     return AL(`${a} unassigned you from: ${t}`, `${a} ве отстрани од: ${t}`);
      case 'due_soon':       return AL(`Due today: ${t}`, `Рок денес: ${t}`);
      case 'overdue':        return AL(`Overdue (${p.due}): ${t}`, `Задоцнето (${p.due}): ${t}`);
      case 'batch_added':    return AL(`${a} added ${p.plant_count} × ${p.strain} to ${p.room} (${p.phase})`,
                                       `${a} додаде ${p.plant_count} × ${p.strain} во ${p.room} (${p.phase})`);
      case 'batch_moved':    return AL(`${a} moved ${p.plant_count} × ${p.strain}: ${p.old_room} (${p.old_phase}) → ${p.room} (${p.phase})`,
                                       `${a} премести ${p.plant_count} × ${p.strain}: ${p.old_room} (${p.old_phase}) → ${p.room} (${p.phase})`);
      case 'batch_closed':   return AL(`${a} closed the ${p.strain} batch in ${p.room} (${p.plant_count} plants)`,
                                       `${a} ја затвори серијата ${p.strain} во ${p.room} (${p.plant_count} растенија)`);
      default:               return `${a}: ${n.verb} ${t}`;
    }
  };

  const REASONS = {
    assigned: { en: 'Assigned', mk: 'Доделено' }, comment: { en: 'Comment', mk: 'Коментар' },
    status: { en: 'Status', mk: 'Статус' }, report: { en: 'Report', mk: 'Извештај' },
    due: { en: 'Due', mk: 'Рок' }, mentioned: { en: '@', mk: '@' },
    // Canned automation rules (app/automation.py) — a quality role reached
    // this row without necessarily being a task participant, so the reason
    // chip carries the WHY: CAPA/validation work went stuck.
    capa_stuck: { en: 'CAPA stuck', mk: 'CAPA блокирана' },
    validation_stuck: { en: 'Validation stuck', mk: 'Валидација блокирана' },
  };

  // Digest "by action" labels — the events table's verb enum, pluralised as
  // count headings (the per-event sentence above stays the detailed render).
  const VERB_LBL = {
    created: { en: 'Created', mk: 'Креирани' }, assigned: { en: 'Assigned', mk: 'Доделени' },
    unassigned: { en: 'Unassigned', mk: 'Отстранети' }, commented: { en: 'Comments', mk: 'Коментари' },
    status_changed: { en: 'Status changes', mk: 'Промени на статус' },
    report_locked: { en: 'Reports locked', mk: 'Заклучени извештаи' },
    ack: { en: 'Acknowledged', mk: 'Потврдени' }, due_soon: { en: 'Due soon', mk: 'Наскоро рок' },
    overdue: { en: 'Overdue', mk: 'Задоцнети' },
    batch_added: { en: 'Batches added', mk: 'Додадени серии' },
    batch_moved: { en: 'Batches moved', mk: 'Преместени серии' },
    batch_closed: { en: 'Batches closed', mk: 'Затворени серии' },
  };
  const verbLabel = (v) => { const l = VERB_LBL[v]; return l ? AL(l.en, l.mk) : v; };

  const dayLabel = (iso) => {
    const d = iso.slice(0, 10), today = GF.localDateStr ? GF.localDateStr(new Date()) : new Date().toISOString().slice(0, 10);
    if (d === today) return AL('Today', 'Денес');
    const y = new Date(Date.now() - 864e5);
    if (d === (GF.localDateStr ? GF.localDateStr(y) : y.toISOString().slice(0, 10))) return AL('Yesterday', 'Вчера');
    return d;
  };

  const itemRow = (n) => `
    <div class="ntf${n.read ? '' : ' unread'}" onclick="GF.WWF.openNotif('${n.id}','${n.task_id || ''}')">
      <div class="ntf-b">
        <div class="ntf-tt">${GF.esc(sentence(n))}</div>
        <div class="ntf-meta"><span class="ntf-reason">${GF.esc(AL(REASONS[n.reason]?.en || n.reason, REASONS[n.reason]?.mk || n.reason))}</span>
          <span class="ntf-ts">${GF.esc(n.created_at.slice(11, 16))}</span></div>
      </div>
      <button class="mini-btn ntf-done" title="${AL('Done', 'Завршено')}"
        onclick="event.stopPropagation();GF.WWF.notifDone('${n.id}')">${GF.icon('check', 'icon')}</button>
    </div>`;

  // Timeline dot colour by verb class (mockup .mw-feed): completions and
  // locks read "ok", stuck-ish state changes "warn", everything else accent.
  const dotKind = (e) => e.verb === 'report_locked' || e.verb === 'acknowledged' ? 'ok'
    : e.verb === 'overdue' || e.verb === 'due_soon' ? 'warn'
    : e.verb === 'status_changed' ? ((e.params || {}).new === 'completed' ? 'ok' : 'warn') : '';

  const feedRow = (e) => `
    <div class="ntf ntf-feed">
      <div class="ntf-rail"><span class="ntf-fdot ${dotKind(e)}"></span></div>
      <div class="ntf-b"><div class="ntf-tt">${GF.esc(sentence(e))}</div>
        <div class="ntf-meta"><span class="ntf-ts">${GF.esc(e.created_at.slice(11, 16))}</span>
          ${e.department_id && GF.depName ? `<span class="ntf-reason">${GF.esc(GF.depAbbr(e.department_id) || '')}</span>` : ''}</div></div>
    </div>`;

  const grouped = (list, row) => {
    let out = '', last = '';
    list.forEach(n => {
      const d = dayLabel(n.created_at);
      if (d !== last) { out += `<div class="ntf-day">${GF.esc(d)}</div>`; last = d; }
      out += row(n);
    });
    return out || `<div class="ntf-empty">${AL('All clear — nothing here.', 'Сè е чисто — нема ништо.')}</div>`;
  };

  /* ── Team digest panel — "what did my team do", daily/weekly, over the
     same dept-scoped events feed (GET /notifications/digest). Collapsed by
     default; the digest is fetched lazily on first open, never as part of a
     plain notifications render. */
  const digestPanel = () => {
    const st = GF.WWF._notif;
    const dg = st.digest;
    const win = (id, lbl) => `<button class="btn btn-sm ntf-tab ${st.digestWindow === id ? 'btn-primary on' : ''}"
      onclick="event.stopPropagation();GF.WWF.setDigestWindow('${id}')">${lbl}</button>`;
    let body = '';
    if (st.digestOpen) {
      if (st.digestLoading || !dg) {
        body = `<div class="panel-body"><div class="mw-skel" style="height:52px"></div></div>`;
      } else {
        const verbChips = (dg.by_verb || []).map(v =>
          `<span class="chip-opt">${GF.esc(verbLabel(v.verb))} · ${Number(v.count) || 0}</span>`).join('');
        const actorChips = (dg.by_actor || []).map(a =>
          `<span class="chip-opt who">${GF.avatar ? GF.avatar(a.actor_id, 18) : ''}${GF.esc(who(a.actor_id))} · ${Number(a.count) || 0}</span>`).join('');
        const empty = `<span class="ntf-empty">${AL('No activity in this window.', 'Нема активност во овој период.')}</span>`;
        body = `<div class="panel-body">
          <div class="sec-label">${AL('By action', 'По дејство')}</div>
          <div class="chips">${verbChips || empty}</div>
          <div class="sec-label">${AL('By person', 'По лице')}</div>
          <div class="chips chips-who">${actorChips || empty}</div>
          <div class="sec-label">${AL('Recent', 'Неодамнешни')}</div>
          <div class="ntf-list">${grouped((dg.recent || []).slice(0, 12), feedRow)}</div>
        </div>`;
      }
    }
    return `<div class="panel" style="margin-bottom:12px">
      <div class="panel-head" onclick="GF.WWF.toggleDigest()" style="cursor:pointer">
        ${GF.icon('trend', 'icon')}<span class="ttl">${AL('Team digest', 'Тимски преглед')}</span>
        ${st.digestOpen && dg ? `<span class="cnt">${Number(dg.total) || 0}</span>` : ''}
        <div class="spacer"></div>
        ${st.digestOpen ? win('daily', AL('Daily', 'Дневно')) + win('weekly', AL('Weekly', 'Неделно')) : ''}
        ${GF.icon(st.digestOpen ? 'chevU' : 'chevD', 'icon')}
      </div>
      ${body}</div>`;
  };

  GF.views.inbox = () => {
    const st = GF.WWF._notif;
    if (!st.loaded) { GF.WWF.loadInbox(); }
    const tab = (id, lbl) => `<button class="btn btn-sm ntf-tab ${st.tab === id ? 'btn-primary on' : ''}"
      onclick="GF.WWF._notif.tab='${id}';GF.render.all()">${lbl}</button>`;
    const flt = (id, lbl) => `<span class="chip-opt ${st.filter === id ? 'on' : ''}"
      onclick="GF.WWF._notif.filter=GF.WWF._notif.filter==='${id}'?'':'${id}';GF.WWF.loadInbox()">${lbl}</span>`;
    const items = st.filter ? st.items.filter(n => n.reason === st.filter) : st.items;
    return `${GF.viewHead ? GF.viewHead('inbox', 'inbox') : `<h2>${AL('Inbox', 'Сандаче')}</h2>`}
      ${digestPanel()}
      <div class="ntf-bar">
        ${tab('inbox', AL('Inbox', 'Сандаче') + (st.unread ? ` (${st.unread})` : ''))}
        ${tab('feed', AL('Activity', 'Активност'))}
        <div style="flex:1"></div>
        ${st.tab === 'inbox' ? `<button class="btn btn-sm" onclick="GF.WWF.notifReadAll()">${AL('Mark all read', 'Означи сè прочитано')}</button>` : ''}
      </div>
      ${st.tab === 'inbox' ? `<div class="chips" style="margin:0 4px 10px">${
        Object.keys(REASONS).map(r => flt(r, AL(REASONS[r].en, REASONS[r].mk))).join('')}</div>` : ''}
      <div class="ntf-list">${!st.loaded
        ? `<div class="mw-skel" style="height:52px;margin-bottom:8px"></div>
           <div class="mw-skel" style="height:52px;margin-bottom:8px"></div>
           <div class="mw-skel" style="height:52px"></div>`
        : st.tab === 'inbox' ? grouped(items, itemRow) : grouped(st.feed, feedRow)}</div>
      ${(st.tab === 'inbox' ? st.moreItems : st.moreFeed)
        ? `<div class="mw-pager" style="justify-content:center;margin-top:10px">
             <button onclick="GF.WWF.notifOlder('${st.tab === 'inbox' ? 'items' : 'feed'}')">${AL('Load older', 'Вчитај постари')}</button></div>` : ''}`;
  };

  GF.WWF.loadInbox = async () => {
    const st = GF.WWF._notif;
    // Demo mode has no notification data — the demo API router answers these
    // paths with junk that would poison st.items (must stay an ARRAY).
    if (GF.state && GF.state.demo) { st.items = []; st.feed = []; st.loaded = true; return; }
    try {
      const [items, feed, uc] = await Promise.all([
        GF.API.notifications({}), GF.API.activity({}), GF.API.notifUnread()]);
      st.items = Array.isArray(items) ? items : [];
      st.feed = Array.isArray(feed) ? feed : [];
      st.unread = (uc && uc.unread) || 0; st.loaded = true;
      st.moreItems = st.items.length === PAGE; st.moreFeed = st.feed.length === PAGE;
      if (GF.state.view === 'inbox') GF.render.all(); else GF.render.sidebar();
    } catch (e) { /* offline / unauthenticated: badge just stays stale */ }
  };

  // Digest fetch — lazy (first open) + on window switch, never on a plain
  // notifications render. Stale-response guard mirrors openEdit's _editTask
  // check: a slow daily response must not clobber a newer weekly one.
  GF.WWF.toggleDigest = () => {
    const st = GF.WWF._notif;
    st.digestOpen = !st.digestOpen;
    if (st.digestOpen && !st.digest && !st.digestLoading) { GF.WWF.loadDigest(); return; }
    GF.render.all();
  };

  GF.WWF.setDigestWindow = (w) => {
    const st = GF.WWF._notif;
    if (st.digestWindow === w) return;
    st.digestWindow = w; st.digest = null;
    GF.WWF.loadDigest();
  };

  GF.WWF.loadDigest = async () => {
    const st = GF.WWF._notif;
    const w = st.digestWindow;
    const empty = { window: w, by_verb: [], by_actor: [], recent: [], total: 0 };
    // Demo mode has no events data — same guard as loadInbox.
    if (GF.state && GF.state.demo) { st.digest = empty; GF.render.all(); return; }
    st.digestLoading = true;
    GF.render.all();
    try {
      const d = await GF.API.notifDigest(w);
      if (GF.WWF._notif.digestWindow !== w) return;   // window switched while in flight
      st.digest = (d && typeof d === 'object' && Array.isArray(d.recent)) ? d : empty;
    } catch (e) {
      if (GF.WWF._notif.digestWindow !== w) return;
      st.digest = empty;
      GF.toast(AL('Digest failed: ', 'Прегледот не успеа: ') + e.message, 'error');
    } finally {
      if (GF.WWF._notif.digestWindow === w) {
        st.digestLoading = false;
        GF.render.all();
      }
    }
  };

  // Cursor pagination (mockup .mw-pager): append the next page of history
  // using the oldest loaded row as the `before` cursor.
  GF.WWF.notifOlder = async (kind) => {
    const st = GF.WWF._notif;
    const list = kind === 'feed' ? st.feed : st.items;
    if (!list.length) return;
    const before = list[list.length - 1].created_at;
    try {
      const page = kind === 'feed'
        ? await GF.API.activity({ before })
        : await GF.API.notifications({ before });
      const seen = new Set(list.map(x => x.id));
      (page || []).forEach(x => { if (!seen.has(x.id)) list.push(x); });
      if (kind === 'feed') st.moreFeed = (page || []).length === PAGE;
      else st.moreItems = (page || []).length === PAGE;
      GF.render.all();
    } catch (e) { GF.toast(AL('Load failed: ', 'Неуспешно вчитување: ') + e.message, 'error'); }
  };

  GF.WWF.openNotif = async (id, taskId) => {
    try { await GF.API.notifRead(id); } catch (e) {}
    const st = GF.WWF._notif;
    const n = st.items.find(x => x.id === id);
    if (n && !n.read) { n.read = true; st.unread = Math.max(0, st.unread - 1); }
    if (taskId && GF.WWF.xrJump) {
      const t = GF.task && GF.task(taskId);
      GF.WWF.xrJump(taskId, (t && t.week_start) || '');
    } else GF.render.all();
  };

  GF.WWF.notifDone = async (id) => {
    try { await GF.API.notifDone(id); } catch (e) { return; }
    const st = GF.WWF._notif;
    const n = st.items.find(x => x.id === id);
    if (n && !n.read) st.unread = Math.max(0, st.unread - 1);
    st.items = st.items.filter(x => x.id !== id);
    GF.render.all();
  };

  GF.WWF.notifReadAll = async () => {
    try { await GF.API.notifReadAll(); } catch (e) { return; }
    GF.WWF._notif.items.forEach(n => n.read = true);
    GF.WWF._notif.unread = 0;
    GF.render.all();
  };

  // 75s poll + on-focus refresh (research: polling is correct at this scale;
  // server-side unread count is the single source of truth for the badge).
  // Self-guarded: does nothing until a real session exists; never in demo.
  const tick = () => {
    if (GF.API && GF.API.token && !(GF.state && GF.state.demo)) GF.WWF.loadInbox();
  };
  setInterval(tick, 75000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
  window.addEventListener('load', () => setTimeout(tick, 4000));
})();
