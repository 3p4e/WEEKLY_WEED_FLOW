/* Bridge — three-mode shell (Agent / Code / Chat). Vanilla JS, no build step. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const fmtTime = (iso) => iso ? new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
  const dur = (a, b) => { if (!a) return ''; const s = Math.max(0, ((b ? new Date(b) : new Date()) - new Date(a)) / 1000); return s < 90 ? `${s.toFixed(0)}s` : `${(s / 60).toFixed(1)}m`; };
  const MODES = ['agent', 'code', 'chat'], GRIDS = ['grid', 'cols', 'focus'];

  const S = { token: null, mode: 'code', status: null, creds: [], tasks: [], sessions: [], agents: [], runs: [], runSel: null, agentSel: null, threads: [], threadId: null, thread: null, pending: [], busy: false,
    panes: [], focus: null, grid: 'grid', dock: { kind: 'none', url: 'http://localhost:3000', threadId: null }, fold: false, folders: [], terms: new Map() };

  // ---------- auth + api
  const url = new URL(location.href);
  if (url.searchParams.get('token')) { localStorage.setItem('bridge_token', url.searchParams.get('token')); url.searchParams.delete('token'); history.replaceState(null, '', url); }
  S.token = localStorage.getItem('bridge_token');
  async function api(method, path, body) {
    const r = await fetch(path, { method, headers: { 'content-type': 'application/json', authorization: `Bearer ${S.token}` }, body: body ? JSON.stringify(body) : undefined });
    if (r.status === 401) { localStorage.removeItem('bridge_token'); askToken(); throw new Error('unauthorized'); }
    const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j;
  }
  const askToken = () => { const d = $('#dlg-token'); if (!d.open) d.showModal(); };
  $('#form-token').addEventListener('submit', (e) => { e.preventDefault(); S.token = new FormData(e.target).get('token').trim(); localStorage.setItem('bridge_token', S.token); $('#dlg-token').close(); boot(); });
  function toast(msg, bad = false) { const d = document.createElement('div'); d.textContent = msg; if (bad) d.className = 'bad'; $('#toast').append(d); setTimeout(() => d.remove(), bad ? 7000 : 3500); }
  const guard = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { if (e.message !== 'unauthorized') toast(e.message, true); } };
  let saveT; const saveLayout = () => { clearTimeout(saveT); saveT = setTimeout(() => api('PUT', '/api/layout', { mode: S.mode, panes: S.panes, focus: S.focus, grid: S.grid, dock: S.dock, fold: S.fold, agentSel: S.agentSel, threadId: S.threadId }).catch(() => {}), 300); };

  // ---------- data
  async function refresh() {
    [S.status, S.tasks, S.sessions, S.creds, S.agents, S.threads] = await Promise.all([api('GET', '/api/status'), api('GET', '/api/tasks'), api('GET', '/api/sessions'), api('GET', '/api/credentials'), api('GET', '/api/agents'), api('GET', '/api/chat/threads')]);
    S.folders = folders();
    renderAll();
  }
  function folders() {
    const set = new Map();
    const add = (p, kind) => { if (!p) return; const f = set.get(p) || { path: p, shells: 0, tasks: 0, agents: 0 }; f[kind]++; set.set(p, f); };
    if (S.status?.projectsRoot) { add(S.status.projectsRoot, 'tasks'); set.get(S.status.projectsRoot).tasks--; }
    for (const s of S.sessions) add(s.worktree?.root || s.cwd, 'shells');
    for (const t of S.tasks) add(t.repoPath, 'tasks');
    for (const a of S.agents) add(a.cwd, 'agents');
    for (const p of JSON.parse(localStorage.getItem('bridge_folders') || '[]')) add(p, 'tasks'), set.get(p).tasks--;
    return [...set.values()].sort((a, b) => (b.shells - a.shells) || a.path.localeCompare(b.path));
  }
  function renderAll() { renderTop(); renderRail(); renderStage(); renderComposer(); }

  // ---------- mode switch
  function setMode(m) {
    if (!MODES.includes(m)) return;
    S.mode = m; document.body.dataset.mode = m;
    $$('.switch button').forEach((b) => b.classList.toggle('active', b.dataset.mode === m));
    $('#stage-code').hidden = m !== 'code'; $('#stage-agent').hidden = m !== 'agent'; $('#stage-chat').hidden = m !== 'chat';
    renderAll(); saveLayout(); if (m === 'code') requestAnimationFrame(fitAll);
  }
  $$('.switch button').forEach((b) => { b.onclick = () => setMode(b.dataset.mode); });

  function renderTop() {
    const st = S.status; if (!st) return;
    const running = S.sessions.filter((x) => x.status === 'running').length;
    const runsLive = S.agents.filter((a) => a.running).length;
    $('#stats').textContent = { agent: `${S.agents.length} agents · ${S.agents.filter((a) => a.enabled && a.cron).length} on a routine · ${runsLive} running now`,
      code: `${running}/${st.maxSessions} shells · ${S.tasks.filter((t) => t.status !== 'done').length} open tasks · ${st.providers.filter((p) => p.installed && p.bin).length} CLIs`,
      chat: `${S.threads.length} threads · ${st.hasServerKey ? 'server key present' : 'no server key'} · ${S.creds.filter((c) => c.envVar === 'ANTHROPIC_API_KEY').length} Anthropic keys in vault` }[S.mode];
    const a = $('#top-actions'); a.innerHTML = '';
    if (S.mode === 'agent') a.append(btn('+ New agent', () => { S.agentSel = null; renderAll(); $('#composer [name=name]')?.focus(); }, 'primary'));
    if (S.mode === 'code') { a.append(btn('+ Shell', guard(async () => { const s = await api('POST', '/api/sessions', { providerId: 'shell', cwd: S.status.projectsRoot }); openPane(s.id); focus(s.id); refresh(); })), btn('+ Agent', () => openFree(null, S.status.projectsRoot), 'primary')); }
    if (S.mode === 'chat') a.append(btn('+ New thread', guard(async () => { const t = await api('POST', '/api/chat/threads', { engine: defaultEngine() }); await refresh(); await openThread(t.id); }), 'primary'));
  }
  const btn = (label, fn, cls = '') => { const b = document.createElement('button'); b.textContent = label; b.className = cls; b.onclick = fn; return b; };
  const defaultEngine = () => (S.status?.hasServerKey || S.creds.some((c) => c.envVar === 'ANTHROPIC_API_KEY')) ? 'api' : 'claude-cli';

  // ---------- rail
  function renderRail() {
    const r = $('#rail'); r.innerHTML = '';
    if (S.mode === 'agent') {
      r.append(el('<h3>Agents</h3>'));
      if (!S.agents.length) r.append(el('<div class="rail-empty">No agents yet. Name one, give it a brief, put it on a routine — the form is at the bottom.</div>'));
      for (const a of S.agents) {
        const it = el(`<button class="item ${a.id === S.agentSel ? 'active' : ''}"><div class="t"><span class="dot ${a.running ? 'run' : a.enabled && a.cron ? 'on' : ''}"></span>${esc(a.name)} <span class="badge">${a.providerId}</span></div><div class="m">${a.cron ? esc(a.cron) + (a.nextRunAt ? ' · next ' + fmtTime(a.nextRunAt) : ' · paused') : 'manual only'}</div><div class="d">${esc(a.brief)}</div></button>`);
        it.onclick = () => selectAgent(a.id); r.append(it);
      }
    }
    if (S.mode === 'code') {
      r.append(el('<h3>Folders</h3>'));
      for (const f of S.folders) {
        const it = el(`<div class="item"><div class="t">${esc(f.path.split('/').pop() || f.path)}</div><div class="m" title="${esc(f.path)}">${esc(f.path)}</div><div class="row" style="margin-top:6px"><span class="hint">${f.shells} shell${f.shells === 1 ? '' : 's'}${f.tasks ? ` · ${f.tasks} task${f.tasks === 1 ? '' : 's'}` : ''}${f.agents ? ` · ${f.agents} agent${f.agents === 1 ? '' : 's'}` : ''}</span><span class="spacer"></span><button class="sm" data-sh>Shell</button><button class="sm" data-ag>Agent</button></div></div>`);
        $('[data-sh]', it).onclick = guard(async () => { const s = await api('POST', '/api/sessions', { providerId: 'shell', cwd: f.path }); openPane(s.id); focus(s.id); refresh(); });
        $('[data-ag]', it).onclick = () => openFree(null, f.path);
        r.append(it);
      }
      const add = el('<form class="row"><input placeholder="Add a folder path…" style="flex:1"><button class="sm">Add</button></form>');
      add.onsubmit = (e) => { e.preventDefault(); const p = $('input', add).value.trim(); if (!p) return; const l = JSON.parse(localStorage.getItem('bridge_folders') || '[]'); if (!l.includes(p)) l.push(p); localStorage.setItem('bridge_folders', JSON.stringify(l)); S.folders = folders(); renderRail(); };
      r.append(add);
      const live = S.sessions.filter((s) => s.status === 'running');
      if (live.length) { r.append(el('<h3 style="margin-top:8px">Live shells</h3>')); for (const s of live) { const c = el(`<button class="item ${S.panes.includes(s.id) ? '' : 'exited'}"><div class="t"><span class="dot on"></span>${esc(s.title)}</div><div class="m">${esc(s.worktree?.branch || s.cwd)}</div></button>`); c.onclick = () => { openPane(s.id); focus(s.id); }; r.append(c); } }
    }
    if (S.mode === 'chat') {
      r.append(el('<h3>Threads</h3>'));
      if (!S.threads.length) r.append(el('<div class="rail-empty">No threads. Start one from the title bar. Threads are sandboxed: the engine has no tools and no view of any repository.</div>'));
      for (const t of S.threads.filter((t) => !t.context)) {
        const it = el(`<button class="item ${t.id === S.threadId ? 'active' : ''}"><div class="t">${esc(t.title)} <span class="badge">${t.engine === 'api' ? 'api' : 'cli'}</span></div><div class="d">${esc(t.last || 'empty')}</div><div class="m">${t.messageCount} messages · ${fmtTime(t.updatedAt)}</div></button>`);
        it.onclick = () => openThread(t.id); r.append(it);
      }
    }
  }

  // ---------- stage
  function renderStage() { if (S.mode === 'agent') renderAgentStage(); if (S.mode === 'code') { renderGrid(); renderDock(); renderFold(); } if (S.mode === 'chat') renderChatStage(); }

  // ===== AGENT =====
  async function selectAgent(id) { S.agentSel = id; S.runSel = null; S.runs = await api('GET', `/api/agents/${id}/runs`).catch(() => []); S.runSel = S.runs[0]?.id || null; renderAll(); saveLayout(); if (S.runSel) loadRun(S.runSel); }
  async function loadRun(id) { S.runSel = id; const r = await api('GET', `/api/runs/${id}`).catch(() => null); const pre = $('#run-output'); if (pre && r) { pre.textContent = r.output || (r.status === 'running' ? '(waiting for output…)' : '(no output)'); pre.scrollTop = pre.scrollHeight; } $$('.runrow').forEach((x) => x.classList.toggle('active', x.dataset.id === id)); renderRunBar(r); }
  function renderRunBar(r) { const bar = $('#run-bar'); if (!bar) return; if (!r) { bar.innerHTML = '<span class="hint">Select a run.</span>'; return; }
    bar.innerHTML = `<span class="st ${r.status}">${r.status}${r.exitCode != null ? ` · exit ${r.exitCode}` : ''}</span><span>${r.trigger}</span><span>${fmtTime(r.startedAt)} · ${dur(r.startedAt, r.finishedAt)}</span><span title="${esc(r.command)}">${esc(r.command).slice(0, 90)}</span><span class="spacer"></span>`;
    if (r.status === 'running') bar.append(btn('Stop', guard(async () => { await api('POST', `/api/runs/${r.id}/cancel`); }), 'sm danger'));
    else bar.append(btn(r.reviewed ? 'Reviewed ✓' : 'Mark reviewed', guard(async () => { await api('PATCH', `/api/runs/${r.id}`, { reviewed: !r.reviewed }); S.runs = await api('GET', `/api/agents/${S.agentSel}/runs`); renderAgentStage(); loadRun(r.id); }), 'sm' + (r.reviewed ? '' : ' primary')));
    if (r.worktree) bar.append(el(`<span class="mono">${esc(r.worktree.branch)}</span>`));
  }
  function renderAgentStage() {
    const st = $('#stage-agent'); st.innerHTML = '';
    const a = S.agents.find((x) => x.id === S.agentSel);
    if (!a) { st.append(el(`<div class="empty" style="flex:1">${S.agents.length ? 'Pick an agent on the left, or create one below.' : 'Agents are teammates on routines.<br>Name one, give it a brief, put it on a schedule. The work runs on its own — you review the result here.'}</div>`)); return; }
    const head = el(`<div class="agent-head"><div style="flex:1"><h2>${esc(a.name)}</h2><div class="meta"><span>${a.providerId} · ${a.authMode}</span><span>${esc(a.cwd)}</span><span>${a.isolation === 'worktree' ? 'own worktree per run' : 'shared checkout'}</span><span>permission: ${a.permission}</span><span>${a.cron ? `routine ${esc(a.cron)} · ${a.enabled ? (a.nextRunAt ? 'next ' + fmtTime(a.nextRunAt) : 'no next run') : 'paused'}` : 'no routine'}</span>${a.cronError ? `<span style="color:var(--bad)">${esc(a.cronError)}</span>` : ''}</div></div></div>`);
    const controls = el('<div class="row"></div>');
    const tog = el(`<label class="toggle"><input type="checkbox" ${a.enabled ? 'checked' : ''} ${a.cron ? '' : 'disabled'}> on routine</label>`);
    $('input', tog).onchange = guard(async (e) => { await api('PATCH', `/api/agents/${a.id}`, { enabled: e.target.checked }); refresh(); });
    controls.append(tog, btn(a.running ? 'Running…' : 'Run now', guard(async () => { await api('POST', `/api/agents/${a.id}/run`); await selectAgent(a.id); }), 'primary'), btn('Delete', guard(async () => { if (!confirm(`Delete agent "${a.name}" and its run history?`)) return; await api('DELETE', `/api/agents/${a.id}`); S.agentSel = null; refresh(); }), 'ghost danger'));
    if (a.running) $$('button', controls)[0].disabled = true;
    head.append(controls); st.append(head);
    const runs = el('<div class="runs"><div class="runlist"></div><div class="runout"><div class="bar" id="run-bar"></div><pre id="run-output"></pre></div></div>');
    const list = $('.runlist', runs);
    if (!S.runs.length) list.append(el('<div class="rail-empty" style="padding:14px">No runs yet. Press Run now, or wait for the routine.</div>'));
    for (const r of S.runs) {
      const row = el(`<div class="runrow ${r.id === S.runSel ? 'active' : ''} ${!r.reviewed && r.status !== 'running' ? 'unreviewed' : ''}" data-id="${r.id}"><span class="dot ${r.status === 'running' ? 'run' : r.status === 'done' ? 'on' : 'off'}"></span><div><div class="when">${fmtTime(r.startedAt)}</div><div class="sub">${r.trigger} · ${dur(r.startedAt, r.finishedAt)}${r.outputBytes ? ` · ${(r.outputBytes / 1024).toFixed(1)} KB` : ''}</div></div><span class="st ${r.status}">${r.status}</span></div>`);
      row.onclick = () => loadRun(r.id); list.append(row);
    }
    st.append(runs);
    if (S.runSel) loadRun(S.runSel); else renderRunBar(null);
  }

  // ===== CODE =====
  function openPane(id) { if (!S.panes.includes(id)) S.panes.push(id); renderGrid(); saveLayout(); }
  function closePane(id) { S.panes = S.panes.filter((x) => x !== id); const t = S.terms.get(id); if (t) { t.ws.close(); t.term.dispose(); S.terms.delete(id); } if (S.focus === id) S.focus = S.panes[0] || null; renderGrid(); saveLayout(); }
  function focus(id) { S.focus = id; $$('.pane').forEach((p) => p.classList.toggle('focused', p.dataset.id === id)); S.terms.get(id)?.term.focus(); renderComposer(); saveLayout(); }
  function renderGrid() {
    const g = $('#grid'); g.className = `grid mode-${S.grid}`;
    $$('#gridmode button').forEach((b) => b.classList.toggle('active', b.dataset.g === S.grid));
    S.panes = S.panes.filter((id) => S.sessions.some((s) => s.id === id) || S.terms.has(id));
    const n = S.panes.length; g.style.setProperty('--cols', n <= 1 ? 1 : n <= 4 ? 2 : n <= 9 ? 3 : 4);
    if (!n) { g.innerHTML = '<div class="empty">No shells open.<br>Pick a folder on the left and open a shell or an agent in it.<br><span class="hint">Alt+N shell · Alt+1/2/3 switch mode · Ctrl/⌘+1…9 focus pane</span></div>'; return; }
    $('.empty', g)?.remove();
    $$('.pane', g).forEach((p) => { if (!S.panes.includes(p.dataset.id)) p.remove(); });
    const focusedPane = document.activeElement?.closest?.('.pane')?.dataset.id;
    const current = $$('.pane', g).map((p) => p.dataset.id);
    const reorder = current.some((id, i) => id !== S.panes[i]);
    for (const id of S.panes) {
      let p = $(`.pane[data-id="${id}"]`, g);
      if (!p) { p = buildPane(id); g.append(p); } else if (reorder) g.append(p);
      const s = S.sessions.find((x) => x.id === id); if (s) updatePaneHeader(p, s);
    }
    if (reorder && focusedPane) S.terms.get(focusedPane)?.term.focus();
    if (!S.focus || !S.panes.includes(S.focus)) S.focus = S.panes[0];
    $$('.pane', g).forEach((p) => p.classList.toggle('focused', p.dataset.id === S.focus));
    requestAnimationFrame(fitAll);
  }
  function buildPane(id) {
    const p = el(`<div class="pane" data-id="${id}"><header><span class="dot"></span><span class="badge"></span><span class="t"></span><span class="branch"></span><button data-max title="Maximize">⤢</button><button data-kill title="Send SIGTERM">■</button><button data-close title="Close pane (process keeps running)">–</button><button data-destroy title="Kill and remove">✕</button></header><div class="term"></div></div>`);
    p.onmousedown = () => focus(id);
    $('[data-max]', p).onclick = () => { p.classList.toggle('maximized'); fitAll(); };
    $('[data-kill]', p).onclick = guard(() => api('POST', `/api/sessions/${id}/kill`, {}));
    $('[data-close]', p).onclick = () => closePane(id);
    $('[data-destroy]', p).onclick = guard(async () => { await api('DELETE', `/api/sessions/${id}`); closePane(id); refresh(); });
    mountTerminal(id, $('.term', p)); return p;
  }
  function updatePaneHeader(p, s) { $('.t', p).textContent = s.title; $('.t', p).title = `${s.command} ${s.argv?.join(' ') || ''}\n${s.cwd}`; $('.badge', p).textContent = s.providerId + (s.authMode !== 'inherit' ? ` · ${s.authMode}` : ''); $('.branch', p).textContent = s.worktree ? s.worktree.branch : s.cwd.split('/').slice(-2).join('/'); $('.dot', p).className = `dot ${s.status === 'running' ? 'on' : 'off'}`; p.classList.toggle('exited', s.status !== 'running'); }
  function mountTerminal(id, host) {
    const term = new Terminal({ cursorBlink: true, fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontSize: 13, theme: { background: '#0b0f14', foreground: '#d7e1ea', cursor: '#27d3c3', selectionBackground: '#27d3c355' }, scrollback: 5000, allowProposedApi: true });
    const fit = new FitAddon.FitAddon(); term.loadAddon(fit); term.loadAddon(new WebLinksAddon.WebLinksAddon()); term.open(host);
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/term/${id}?token=${encodeURIComponent(S.token)}`); ws.binaryType = 'arraybuffer';
    const dec = new TextDecoder();
    ws.onmessage = (ev) => { if (typeof ev.data === 'string') { if (ev.data[0] === '{') { try { const m = JSON.parse(ev.data); if (m.type === 'snapshot') { term.write(m.data); return; } if (m.type === 'exit') return; } catch { /* raw */ } } term.write(ev.data); } else term.write(dec.decode(ev.data)); };
    ws.onopen = () => { try { fit.fit(); } catch {} ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows })); };
    ws.onclose = () => term.write('\r\n\x1b[2m[bridge] disconnected — reload to reattach\x1b[0m\r\n');
    term.onData((d) => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'input', data: d })); });
    term.onResize(({ cols, rows }) => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'resize', cols, rows })); });
    S.terms.set(id, { term, fit, ws });
  }
  function fitAll() { if (S.mode !== 'code') return; for (const [id, t] of S.terms) { const p = $(`.pane[data-id="${id}"]`); if (p && p.offsetParent !== null && p.offsetHeight > 0) { try { t.fit.fit(); } catch {} } } }
  window.addEventListener('resize', fitAll);
  $$('#gridmode button').forEach((b) => { b.onclick = () => { S.grid = b.dataset.g; renderGrid(); saveLayout(); }; });
  $$('#dockmode button').forEach((b) => { b.onclick = () => { S.dock.kind = b.dataset.d; renderDock(); saveLayout(); requestAnimationFrame(fitAll); }; });
  $('#fold-toggle').onclick = () => { S.fold = !S.fold; renderFold(); saveLayout(); requestAnimationFrame(fitAll); };
  function renderFold() { $('#fold').hidden = !S.fold; $('#fold-toggle').classList.toggle('open', S.fold); if (S.fold) { renderBoard(); renderKeys(); renderProviders(); } }

  async function renderDock() {
    const d = $('#dock'); $$('#dockmode button').forEach((b) => b.classList.toggle('active', b.dataset.d === S.dock.kind));
    d.hidden = S.dock.kind === 'none'; if (d.hidden) { d.innerHTML = ''; return; }
    if (S.dock.kind === 'browser') {
      if (!$('iframe', d)) { d.innerHTML = `<div class="dockbar"><form class="row" style="flex:1"><input name="u" value="${esc(S.dock.url)}" placeholder="http://localhost:3000"><button class="sm">Go</button></form><button class="sm" data-reload title="Reload">↻</button></div><iframe sandbox="allow-scripts allow-forms allow-same-origin allow-popups" referrerpolicy="no-referrer"></iframe>`;
        const f = $('iframe', d); f.src = S.dock.url;
        $('form', d).onsubmit = (e) => { e.preventDefault(); S.dock.url = $('[name=u]', d).value.trim(); f.src = S.dock.url; saveLayout(); };
        $('[data-reload]', d).onclick = () => { f.src = S.dock.url; }; }
      return;
    }
    // thread dock: a sandboxed thread tied to the focused pane's folder as context label
    const folder = S.sessions.find((s) => s.id === S.focus)?.cwd || S.status?.projectsRoot || '';
    let t = S.threads.find((x) => x.id === S.dock.threadId);
    if (!t) { t = await api('POST', '/api/chat/threads', { title: `Thread · ${folder.split('/').pop()}`, engine: defaultEngine(), context: folder }).catch(() => null); if (!t) return; S.dock.threadId = t.id; S.threads = await api('GET', '/api/chat/threads'); saveLayout(); }
    const full = await api('GET', `/api/chat/threads/${t.id}`).catch(() => null); if (!full) return;
    d.innerHTML = `<div class="dockbar"><span class="mono" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(full.title)}">${esc(full.title)}</span><span class="badge">${full.engine}</span><button class="sm" data-new>New</button></div><div class="dockbody"><div class="thread" id="dock-thread"></div><div style="padding:8px;border-top:1px solid var(--line)" id="dock-composer"></div></div>`;
    $('[data-new]', d).onclick = () => { S.dock.threadId = null; renderDock(); };
    renderMessages($('#dock-thread', d), full); $('#dock-composer', d).append(chatComposer(full, (thr) => { renderMessages($('#dock-thread', d), thr); }));
  }

  // ---- workspace fold: board / keys / providers
  const STATUS_LABEL = { backlog: 'Backlog', in_progress: 'In progress', review: 'Review', done: 'Done' };
  function renderBoard() {
    const b = $('#board'); b.innerHTML = '';
    for (const st of S.status?.statuses || []) { const col = el(`<div class="col"><h4>${STATUS_LABEL[st]} · ${S.tasks.filter((t) => t.status === st).length}</h4></div>`); for (const t of S.tasks.filter((t) => t.status === st)) col.append(taskCard(t)); b.append(col); }
  }
  function taskCard(t) {
    const agents = t.agents.map((a) => { const s = S.sessions.find((x) => x.id === a.sessionId); return `<span class="chip ${s?.status || 'exited'}" data-open="${a.sessionId}" title="${esc(a.worktree?.branch || 'shared checkout')}">${a.providerId}/${a.role}${s ? '' : ' ✕'}</span>`; }).join('');
    const c = el(`<div class="card"><div class="title">${esc(t.title)}</div><div class="meta">${esc(t.repoPath)}${t.baseRef ? ' @ ' + esc(t.baseRef) : ''}</div>${t.description ? `<div class="hint">${esc(t.description).slice(0, 220)}</div>` : ''}<div class="agents">${agents}</div><div class="row"><select data-status>${Object.entries(STATUS_LABEL).map(([k, v]) => `<option value="${k}" ${k === t.status ? 'selected' : ''}>${v}</option>`).join('')}</select><button data-launch>+ Agent</button><button data-swarm>Swarm</button><button data-del class="ghost danger">✕</button></div></div>`);
    $('[data-status]', c).onchange = guard(async (e) => { await api('PATCH', `/api/tasks/${t.id}`, { status: e.target.value }); refresh(); });
    $('[data-launch]', c).onclick = () => openLaunch(t, false); $('[data-swarm]', c).onclick = () => openLaunch(t, true);
    $('[data-del]', c).onclick = guard(async () => { if (!confirm(`Delete task "${t.title}" and kill its agents? Worktrees are kept.`)) return; await api('DELETE', `/api/tasks/${t.id}`); refresh(); });
    $$('[data-open]', c).forEach((x) => { x.onclick = () => { if (S.sessions.some((s) => s.id === x.dataset.open)) { openPane(x.dataset.open); focus(x.dataset.open); } }; });
    return c;
  }
  function renderProviders() { const box = $('#providers'); box.innerHTML = ''; for (const p of S.status?.providers || []) { const d = el(`<div class="prov"><div><span class="dot ${p.installed ? 'on' : 'off'}"></span> <b>${p.name}</b> <span class="hint">${p.vendor || ''}</span><div class="path">${p.installed ? esc(p.path) : (p.install ? 'not installed — ' + esc(p.install) : '')}</div><div class="hint">${p.keyEnv ? `key: <code>${p.keyEnv}</code>` : ''}${p.subscription ? ` · ${esc(p.subscription)}` : ''}</div></div><button class="sm" ${p.installed ? '' : 'disabled'}>Open</button></div>`); $('button', d).onclick = () => openFree(p.id, S.status.projectsRoot); box.append(d); } }
  function renderKeys() { const box = $('#keys'); box.innerHTML = S.creds.length ? '' : '<p class="hint">No keys stored.</p>'; for (const c of S.creds) { const d = el(`<div class="key"><div><b>${esc(c.name)}</b> <code>${c.envVar}</code><div class="hint">${c.masked} · ${new Date(c.createdAt).toLocaleDateString()}</div></div><button class="ghost danger sm">✕</button></div>`); $('button', d).onclick = guard(async () => { await api('DELETE', `/api/credentials/${c.id}`); refresh(); }); box.append(d); } }
  $('#form-key').addEventListener('submit', guard(async (e) => { e.preventDefault(); await api('POST', '/api/credentials', Object.fromEntries(new FormData(e.target))); e.target.reset(); toast('Key stored (encrypted)'); refresh(); }));
  $('#btn-new-task').onclick = () => $('#dlg-task').showModal();
  $('#form-task').addEventListener('submit', guard(async (e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)); await api('POST', '/api/tasks', { title: f.title, description: f.description, repoPath: f.repoPath || undefined, baseRef: f.baseRef || null }); e.target.reset(); $('#dlg-task').close(); refresh(); }));
  function fillSelects() {
    const provs = (S.status?.providers || []).filter((p) => p.installed);
    for (const id of ['#launch-provider', '#free-provider']) { const sel = $(id); const cur = sel.value; sel.innerHTML = provs.map((p) => `<option value="${p.id}">${p.name}</option>`).join(''); if (provs.some((p) => p.id === cur)) sel.value = cur; }
    for (const id of ['#launch-cred', '#free-cred']) $(id).innerHTML = '<option value="">—</option>' + S.creds.map((c) => `<option value="${c.id}">${esc(c.name)} (${c.envVar})</option>`).join('');
    $('#launch-role').innerHTML = (S.status?.roles || []).map((r) => `<option value="${r}">${r}</option>`).join('');
  }
  function openLaunch(t, swarm) { fillSelects(); const f = $('#form-launch'); f.taskId.value = t.id; f.swarm.value = swarm ? '1' : '0'; $('#launch-title').textContent = (swarm ? 'Swarm on: ' : 'Launch agent on: ') + t.title; $('#launch-role-row').style.display = swarm ? 'none' : ''; $('#launch-hint').textContent = swarm ? 'Launches an architect, an implementer and a reviewer, each in its own worktree, sharing the task notes file.' : 'The agent starts pre-seeded with the task text, its role and the shared notes path.'; $('#dlg-launch').showModal(); }
  $('#form-launch').addEventListener('submit', guard(async (e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)); if (f.authMode === 'key' && !f.credentialId) return toast('Pick a key for key mode', true); const body = { providerId: f.providerId, authMode: f.authMode, credentialId: f.credentialId || null, isolation: f.isolation }; $('#dlg-launch').close();
    if (f.swarm === '1') { const res = await api('POST', `/api/tasks/${f.taskId}/swarm`, body); for (const r of res) openPane(r.session.id); focus(res[0]?.session.id); } else { const res = await api('POST', `/api/tasks/${f.taskId}/launch`, { ...body, role: f.role }); openPane(res.session.id); focus(res.session.id); } refresh(); }));
  function openFree(providerId, cwd) { fillSelects(); const f = $('#form-free'); if (providerId) f.providerId.value = providerId; f.cwd.value = cwd || ''; $('#dlg-free').showModal(); }
  $('#form-free').addEventListener('submit', guard(async (e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)); if (f.authMode === 'key' && !f.credentialId) return toast('Pick a key for key mode', true); $('#dlg-free').close(); const s = await api('POST', '/api/sessions', { providerId: f.providerId, cwd: f.cwd || undefined, authMode: f.authMode, credentialId: f.credentialId || null, prompt: f.prompt || null }); openPane(s.id); focus(s.id); refresh(); }));

  // ===== CHAT =====
  async function openThread(id) { S.threadId = id; S.thread = await api('GET', `/api/chat/threads/${id}`).catch(() => null); S.pending = []; renderAll(); saveLayout(); }
  function renderChatStage() {
    const st = $('#stage-chat'); st.innerHTML = '';
    if (!S.thread) { st.append(el('<div class="empty" style="flex:1">A conversation, not a repo.<br>Threads are not tied to a project. Drop a file, ask a question, keep the thread.<br><span class="hint">Sandboxed: the engine has no tools and no view of any codebase, so it cannot pretend it is inside one.</span></div>')); return; }
    const box = el('<div class="thread"></div>'); renderMessages(box, S.thread); st.append(box);
  }
  function renderMessages(box, t) {
    box.innerHTML = `<div class="sandbox-note">sandboxed · ${t.engine === 'api' ? `Anthropic API · ${esc(t.model)}` : 'Claude CLI in an empty directory, all tools disallowed'} · no repository access</div>`;
    for (const m of t.messages) {
      const files = m.attachments?.length ? `<div class="files">${m.attachments.map((a) => `<span>${esc(a.name)} · ${(a.size / 1024).toFixed(1)} KB</span>`).join('')}</div>` : '';
      const meta = m.role === 'assistant' ? `<div class="meta"><span>${fmtTime(m.ts)}</span>${m.model ? `<span>${esc(m.model)}</span>` : ''}${m.usage ? `<span>${m.usage.input}→${m.usage.output} tok</span>` : ''}${m.cost != null ? `<span>$${m.cost.toFixed(4)}</span>` : ''}</div>` : `<div class="meta"><span>${fmtTime(m.ts)}</span></div>`;
      box.append(el(`<div class="msg ${m.role}">${files}<div class="bubble ${m.error ? 'error' : ''}">${esc(m.error || m.text)}</div>${meta}</div>`));
    }
    if (box.dataset.busy === '1') box.append(el('<div class="thinking">thinking…</div>'));
    box.scrollTop = box.scrollHeight;
  }
  function chatComposer(t, onUpdate) {
    const pending = [];
    const c = el(`<form class="chat-composer"><div><textarea name="text" rows="2" placeholder="Message… (Enter to send, Shift+Enter for a new line, drop files here)"></textarea><div class="pending"></div><div class="chat-opts"><label class="toggle">engine <select name="engine"><option value="api" ${t.engine === 'api' ? 'selected' : ''}>Anthropic API (vault key)</option><option value="claude-cli" ${t.engine === 'claude-cli' ? 'selected' : ''}>Claude CLI (subscription)</option></select></label><label class="toggle">key <select name="credentialId"><option value="">${S.status?.hasServerKey ? 'server key' : '—'}</option>${S.creds.filter((k) => k.envVar === 'ANTHROPIC_API_KEY').map((k) => `<option value="${k.id}" ${k.id === t.credentialId ? 'selected' : ''}>${esc(k.name)}</option>`).join('')}</select></label><label class="toggle">model <input name="model" value="${esc(t.model || '')}" style="width:150px"></label><button type="button" class="sm" data-attach>Attach</button><input type="file" multiple hidden></div></div><button class="primary" style="align-self:end">Send</button></form>`);
    const ta = $('textarea', c), pend = $('.pending', c), file = $('input[type=file]', c);
    const drawPending = () => { pend.innerHTML = ''; pending.forEach((p, i) => { const s = el(`<span title="remove">${esc(p.name)} · ${(p.size / 1024).toFixed(1)} KB ✕</span>`); s.onclick = () => { pending.splice(i, 1); drawPending(); }; pend.append(s); }); };
    const addFiles = (list) => { for (const f of list) { if (f.size > 30e6) { toast(`${f.name} is over 30 MB`, true); continue; } const r = new FileReader(); r.onload = () => { pending.push({ name: f.name, type: f.type || 'text/plain', size: f.size, data: r.result.split(',')[1] }); drawPending(); }; r.readAsDataURL(f); } };
    $('[data-attach]', c).onclick = () => file.click(); file.onchange = () => { addFiles(file.files); file.value = ''; };
    c.ondragover = (e) => { e.preventDefault(); c.classList.add('drag'); }; c.ondragleave = () => c.classList.remove('drag'); c.ondrop = (e) => { e.preventDefault(); c.classList.remove('drag'); addFiles(e.dataTransfer.files); };
    ta.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); c.requestSubmit(); } };
    const settings = () => ({ engine: $('[name=engine]', c).value, credentialId: $('[name=credentialId]', c).value || null, model: $('[name=model]', c).value.trim() || S.status.defaultModel });
    $$('select,input[name=model]', c).forEach((x) => { x.onchange = guard(async () => { const s = settings(); await api('PATCH', `/api/chat/threads/${t.id}`, s); Object.assign(t, s); onUpdate(await api('GET', `/api/chat/threads/${t.id}`)); }); });
    c.onsubmit = guard(async (e) => {
      e.preventDefault(); const text = ta.value; if (!text.trim() && !pending.length) return;
      const s = settings(); if (s.engine !== t.engine || s.credentialId !== t.credentialId || s.model !== t.model) { await api('PATCH', `/api/chat/threads/${t.id}`, s); Object.assign(t, s); }
      const optimistic = { ...t, messages: [...t.messages, { role: 'user', text, ts: new Date().toISOString(), attachments: pending.map((p) => ({ name: p.name, size: p.size })) }] };
      const box = c.closest('#dock')?.querySelector('.thread') || $('#stage-chat .thread'); if (box) { box.dataset.busy = '1'; renderMessages(box, optimistic); }
      ta.value = ''; const atts = pending.splice(0); drawPending(); $('button.primary', c).disabled = true;
      try { const r = await api('POST', `/api/chat/threads/${t.id}/messages`, { text, attachments: atts }); if (box) box.dataset.busy = '0'; Object.assign(t, r.thread); onUpdate(r.thread); S.threads = await api('GET', '/api/chat/threads'); if (S.mode === 'chat') renderRail(); }
      finally { $('button.primary', c).disabled = false; if (box) box.dataset.busy = '0'; ta.focus(); }
    });
    return c;
  }

  // ---------- composer (per mode)
  function renderComposer() {
    const c = $('#composer'); c.innerHTML = '';
    if (S.mode === 'agent') {
      const a = S.agents.find((x) => x.id === S.agentSel);
      const provs = (S.status?.providers || []).filter((p) => p.installed && p.id !== 'shell').concat((S.status?.providers || []).filter((p) => p.id === 'shell'));
      const f = el(`<form class="agent-form">
        <input name="name" placeholder="Agent name (e.g. Nightly test triage)" required value="${esc(a?.name || '')}">
        <select name="providerId">${provs.map((p) => `<option value="${p.id}" ${(a?.providerId || 'claude') === p.id ? 'selected' : ''}>${p.name}</option>`).join('')}</select>
        <select name="authMode"><option value="subscription" ${(a?.authMode || 'subscription') === 'subscription' ? 'selected' : ''}>Subscription login</option><option value="key" ${a?.authMode === 'key' ? 'selected' : ''}>Vault key</option><option value="inherit" ${a?.authMode === 'inherit' ? 'selected' : ''}>Inherit env</option></select>
        <textarea name="brief" class="full" placeholder="Brief — what this teammate does on every run. Written as an instruction to the agent." required>${esc(a?.brief || '')}</textarea>
        <input name="cwd" placeholder="Folder on this host" value="${esc(a?.cwd || S.status?.projectsRoot || '')}">
        <select name="credentialId"><option value="">key: —</option>${S.creds.map((k) => `<option value="${k.id}" ${a?.credentialId === k.id ? 'selected' : ''}>key: ${esc(k.name)}</option>`).join('')}</select>
        <select name="permission"><option value="plan" ${(a?.permission || 'plan') === 'plan' ? 'selected' : ''}>plan: read-only, proposes changes</option><option value="edit" ${a?.permission === 'edit' ? 'selected' : ''}>edit: may change files</option><option value="full" ${a?.permission === 'full' ? 'selected' : ''}>full: may run anything (dangerous)</option></select>
        <div class="row"><select name="preset" style="width:auto"><option value="">routine: none (manual)</option>${Object.entries(S.status?.cronPresets || {}).map(([k, v]) => `<option value="${v}" ${a?.cron === v ? 'selected' : ''}>${k.slice(1)} · ${v}</option>`).join('')}<option value="custom" ${a?.cron && !Object.values(S.status?.cronPresets || {}).includes(a.cron) ? 'selected' : ''}>custom cron…</option></select><input name="cron" placeholder="m h dom mon dow" style="width:170px;font-family:var(--mono)" value="${esc(a?.cron || '')}"><span class="hint" data-preview></span></div>
        <select name="isolation"><option value="shared" ${(a?.isolation || 'shared') === 'shared' ? 'selected' : ''}>shared checkout</option><option value="worktree" ${a?.isolation === 'worktree' ? 'selected' : ''}>fresh worktree per run</option></select>
        <div class="row" style="justify-content:flex-end"><label class="toggle"><input type="checkbox" name="enabled" ${a?.enabled ? 'checked' : ''}> on routine</label><button class="primary">${a ? 'Save agent' : 'Create agent'}</button></div>
      </form>`);
      const cronIn = $('[name=cron]', f), preset = $('[name=preset]', f), prev = $('[data-preview]', f);
      const preview = async () => { const v = cronIn.value.trim(); if (!v) { prev.textContent = ''; return; } const r = await api('POST', '/api/cron/preview', { cron: v }).catch(() => null); prev.textContent = r?.ok ? (r.next ? `next ${fmtTime(r.next)}` : 'never fires') : (r?.error || ''); prev.style.color = r?.ok ? '' : 'var(--bad)'; };
      preset.onchange = () => { if (preset.value !== 'custom') cronIn.value = preset.value; preview(); }; cronIn.oninput = () => { preset.value = 'custom'; preview(); }; preview();
      f.onsubmit = guard(async (e) => { e.preventDefault(); const d = Object.fromEntries(new FormData(f)); const body = { name: d.name, brief: d.brief, providerId: d.providerId, authMode: d.authMode, credentialId: d.credentialId || null, cwd: d.cwd, permission: d.permission, cron: d.cron.trim(), isolation: d.isolation, enabled: Boolean(d.enabled) && Boolean(d.cron.trim()) };
        if (body.authMode === 'key' && !body.credentialId) return toast('Pick a vault key for key mode', true);
        const saved = a ? await api('PATCH', `/api/agents/${a.id}`, body) : await api('POST', '/api/agents', body); await refresh(); await selectAgent(saved.id); toast(a ? 'Agent saved' : 'Agent created'); });
      c.append(f);
    }
    if (S.mode === 'code') {
      const s = S.sessions.find((x) => x.id === S.focus);
      const line = el(`<form class="composer-line"><span class="target">${s ? `→ ${esc(s.title)}` : 'no pane focused'}</span><input name="cmd" placeholder="${s ? 'Type a command or a message for the focused pane and press Enter' : 'Open a shell to send commands'}" ${s ? '' : 'disabled'} autocomplete="off"><button class="sm" ${s ? '' : 'disabled'}>Send</button></form>`);
      line.onsubmit = (e) => { e.preventDefault(); const t = S.terms.get(S.focus); const v = $('input', line).value; if (!t || t.ws.readyState !== 1) return; t.ws.send(JSON.stringify({ type: 'input', data: v + '\r' })); $('input', line).value = ''; };
      c.append(line);
    }
    if (S.mode === 'chat' && S.thread) c.append(chatComposer(S.thread, (thr) => { S.thread = thr; renderChatStage(); }));
  }

  // ---------- keyboard
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && !e.altKey && /^[1-9]$/.test(e.key) && S.mode === 'code') { const id = S.panes[Number(e.key) - 1]; if (id) { e.preventDefault(); focus(id); } return; }
    if (!e.altKey || e.metaKey || e.ctrlKey) return;
    if (e.code === 'Digit1') { e.preventDefault(); setMode('agent'); } if (e.code === 'Digit2') { e.preventDefault(); setMode('code'); } if (e.code === 'Digit3') { e.preventDefault(); setMode('chat'); }
    if (e.code === 'KeyN' && S.mode === 'code') { e.preventDefault(); $$('#top-actions button')[0]?.click(); }
    if (e.code === 'KeyL' && S.mode === 'code') { e.preventDefault(); S.grid = GRIDS[(GRIDS.indexOf(S.grid) + 1) % GRIDS.length]; renderGrid(); saveLayout(); }
  }, true);

  // ---------- live events
  function connectEvents() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/events?token=${encodeURIComponent(S.token)}`);
    ws.onmessage = async (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'hello') { S.sessions = m.sessions; S.tasks = m.tasks; S.agents = m.agents; renderAll(); }
      if (m.type === 'session') { const i = S.sessions.findIndex((s) => s.id === m.session.id); if (i >= 0) S.sessions[i] = m.session; else S.sessions.push(m.session); renderTop(); const p = $(`.pane[data-id="${m.session.id}"]`); if (p) updatePaneHeader(p, m.session); if (S.fold) renderBoard(); }
      if (m.type === 'session_removed') { S.sessions = S.sessions.filter((s) => s.id !== m.id); renderTop(); if (S.fold) renderBoard(); }
      if (m.type === 'agent') { const i = S.agents.findIndex((a) => a.id === m.agent.id); if (i >= 0) S.agents[i] = m.agent; else S.agents.push(m.agent); if (S.mode === 'agent') { renderTop(); renderRail(); if (m.agent.id === S.agentSel) { S.runs = await api('GET', `/api/agents/${S.agentSel}/runs`).catch(() => S.runs); renderAgentStage(); } } }
      if (m.type === 'agent_removed') { S.agents = S.agents.filter((a) => a.id !== m.id); if (S.mode === 'agent') renderAll(); }
      if (m.type === 'run' && m.run.agentId === S.agentSel) { const i = S.runs.findIndex((r) => r.id === m.run.id); if (i >= 0) S.runs[i] = m.run; else { S.runs.unshift(m.run); if (!S.runSel || m.run.status === 'running') S.runSel = m.run.id; } if (S.mode === 'agent') renderAgentStage(); }
      if (m.type === 'run_output' && m.id === S.runSel && S.mode === 'agent') loadRun(m.id);
    };
    ws.onclose = () => setTimeout(connectEvents, 2000);
  }

  // ---------- boot
  const boot = guard(async () => {
    if (!S.token) return askToken();
    const chk = await fetch('/api/auth/check', { headers: { authorization: `Bearer ${S.token}` } });
    if (chk.status !== 200) { localStorage.removeItem('bridge_token'); return askToken(); }
    const layout = await api('GET', '/api/layout');
    S.grid = GRIDS.includes(layout.grid) ? layout.grid : 'grid'; S.dock = { kind: 'none', url: 'http://localhost:3000', threadId: null, ...(layout.dock || {}) }; S.fold = Boolean(layout.fold);
    await refresh();
    S.panes = (layout.panes || []).filter((id) => S.sessions.some((s) => s.id === id)); S.focus = layout.focus;
    if (layout.agentSel && S.agents.some((a) => a.id === layout.agentSel)) await selectAgent(layout.agentSel);
    if (layout.threadId && S.threads.some((t) => t.id === layout.threadId)) { S.threadId = layout.threadId; S.thread = await api('GET', `/api/chat/threads/${layout.threadId}`).catch(() => null); }
    setMode(MODES.includes(layout.mode) ? layout.mode : 'code');
    connectEvents();
  });
  boot();
})();
