/* Bridge workspace UI — vanilla JS, no build step. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const state = { token: null, status: null, tasks: [], sessions: [], creds: [], panes: [], focus: null, mode: 'grid', terms: new Map() };

  // ---------- auth
  const url = new URL(location.href);
  if (url.searchParams.get('token')) { localStorage.setItem('bridge_token', url.searchParams.get('token')); url.searchParams.delete('token'); history.replaceState(null, '', url); }
  state.token = localStorage.getItem('bridge_token');

  async function api(method, path, body) {
    const r = await fetch(path, { method, headers: { 'content-type': 'application/json', authorization: `Bearer ${state.token}` }, body: body ? JSON.stringify(body) : undefined });
    if (r.status === 401) { localStorage.removeItem('bridge_token'); askToken(); throw new Error('unauthorized'); }
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.statusText);
    return j;
  }
  function askToken() {
    const d = $('#dlg-token'); if (!d.open) d.showModal();
  }
  $('#form-token').addEventListener('submit', (e) => { e.preventDefault(); state.token = new FormData(e.target).get('token').trim(); localStorage.setItem('bridge_token', state.token); $('#dlg-token').close(); boot(); });

  function toast(msg, bad = false) { const d = document.createElement('div'); d.textContent = msg; if (bad) d.className = 'bad'; $('#toast').append(d); setTimeout(() => d.remove(), bad ? 7000 : 3500); }
  const guard = (fn) => async (...a) => { try { return await fn(...a); } catch (e) { if (e.message !== 'unauthorized') toast(e.message, true); } };

  // ---------- data
  async function refresh() {
    [state.status, state.tasks, state.sessions, state.creds] = await Promise.all([api('GET', '/api/status'), api('GET', '/api/tasks'), api('GET', '/api/sessions'), api('GET', '/api/credentials')]);
    renderAll();
  }
  function renderAll() { renderStats(); renderBoard(); renderProviders(); renderKeys(); renderGrid(); fillSelects(); }

  function renderStats() {
    const s = state.status; if (!s) return;
    const running = state.sessions.filter((x) => x.status === 'running').length;
    $('#stats').textContent = `${running}/${s.maxSessions} agents running · ${state.tasks.filter((t) => t.status !== 'done').length} open tasks · ${s.providers.filter((p) => p.installed && p.bin).length} CLIs installed · ${s.projectsRoot}`;
  }

  // ---------- board
  const STATUS_LABEL = { backlog: 'Backlog', in_progress: 'In progress', review: 'Review', done: 'Done' };
  function renderBoard() {
    const b = $('#board'); b.innerHTML = '';
    for (const st of state.status?.statuses || []) {
      const col = document.createElement('div'); col.className = 'col';
      const items = state.tasks.filter((t) => t.status === st);
      col.innerHTML = `<h4>${STATUS_LABEL[st]} · ${items.length}</h4>`;
      for (const t of items) col.append(taskCard(t));
      b.append(col);
    }
  }
  function taskCard(t) {
    const c = document.createElement('div'); c.className = 'card';
    const agents = t.agents.map((a) => { const s = state.sessions.find((x) => x.id === a.sessionId); return `<span class="chip ${s?.status || 'exited'}" data-open="${a.sessionId}" title="${a.worktree?.branch || 'shared checkout'}">${a.providerId}/${a.role}${s ? '' : ' ✕'}</span>`; }).join('');
    c.innerHTML = `<div class="title">${esc(t.title)}</div>
      <div class="meta">${esc(t.repoPath)}${t.baseRef ? ' @ ' + esc(t.baseRef) : ''}</div>
      ${t.description ? `<div class="hint">${esc(t.description).slice(0, 220)}</div>` : ''}
      <div class="agents">${agents}</div>
      <div class="row">
        <select data-status>${Object.entries(STATUS_LABEL).map(([k, v]) => `<option value="${k}" ${k === t.status ? 'selected' : ''}>${v}</option>`).join('')}</select>
        <button data-launch>+ Agent</button><button data-swarm>Swarm</button><button data-del class="ghost danger">✕</button>
      </div>`;
    $('[data-status]', c).onchange = guard(async (e) => { await api('PATCH', `/api/tasks/${t.id}`, { status: e.target.value }); refresh(); });
    $('[data-launch]', c).onclick = () => openLaunch(t, false);
    $('[data-swarm]', c).onclick = () => openLaunch(t, true);
    $('[data-del]', c).onclick = guard(async () => { if (!confirm(`Delete task "${t.title}" and kill its agents? Worktrees are kept.`)) return; await api('DELETE', `/api/tasks/${t.id}`); refresh(); });
    $$('[data-open]', c).forEach((el) => { el.onclick = () => { const id = el.dataset.open; if (state.sessions.some((s) => s.id === id)) { openPane(id); focus(id); } }; });
    return c;
  }
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));

  // ---------- providers / keys
  function renderProviders() {
    const box = $('#providers'); box.innerHTML = '';
    for (const p of state.status?.providers || []) {
      const d = document.createElement('div'); d.className = 'prov';
      d.innerHTML = `<div><span class="dot ${p.installed ? 'on' : 'off'}"></span><span class="name">${p.name}</span> <span class="hint">${p.vendor || ''}</span>
        <div class="path">${p.installed ? esc(p.path) : (p.install ? 'not installed — ' + esc(p.install) : '')}</div>
        <div class="hint">${p.keyEnv ? `key: <code>${p.keyEnv}</code>` : ''}${p.subscription ? ` · subscription: ${esc(p.subscription)}` : ''}</div></div>
        <button ${p.installed ? '' : 'disabled'} data-quick>Open</button>`;
      $('[data-quick]', d).onclick = () => openFree(p.id);
      box.append(d);
    }
  }
  function renderKeys() {
    const box = $('#keys'); box.innerHTML = state.creds.length ? '' : '<p class="hint">No keys stored.</p>';
    for (const c of state.creds) {
      const d = document.createElement('div'); d.className = 'key';
      d.innerHTML = `<div><b>${esc(c.name)}</b> <code>${c.envVar}</code><div class="hint">${c.masked} · ${new Date(c.createdAt).toLocaleDateString()}</div></div><button class="ghost danger" data-rm>✕</button>`;
      $('[data-rm]', d).onclick = guard(async () => { await api('DELETE', `/api/credentials/${c.id}`); refresh(); });
      box.append(d);
    }
  }
  $('#form-key').addEventListener('submit', guard(async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target));
    await api('POST', '/api/credentials', f); e.target.reset(); toast('Key stored (encrypted)'); refresh();
  }));

  function fillSelects() {
    const provs = (state.status?.providers || []).filter((p) => p.installed);
    for (const id of ['#launch-provider', '#free-provider']) {
      const sel = $(id); const cur = sel.value;
      sel.innerHTML = provs.map((p) => `<option value="${p.id}">${p.name}</option>`).join('');
      if (provs.some((p) => p.id === cur)) sel.value = cur;
    }
    for (const id of ['#launch-cred', '#free-cred']) {
      $(id).innerHTML = '<option value="">—</option>' + state.creds.map((c) => `<option value="${c.id}">${esc(c.name)} (${c.envVar})</option>`).join('');
    }
    $('#launch-role').innerHTML = (state.status?.roles || []).map((r) => `<option value="${r}">${r}</option>`).join('');
  }

  // ---------- launch dialogs
  function openLaunch(t, swarm) {
    const f = $('#form-launch'); f.taskId.value = t.id; f.swarm.value = swarm ? '1' : '0';
    $('#launch-title').textContent = swarm ? `Swarm on: ${t.title}` : `Launch agent on: ${t.title}`;
    $('#launch-role-row').style.display = swarm ? 'none' : '';
    $('#launch-hint').textContent = swarm ? 'Launches an architect, an implementer and a reviewer of the chosen agent, each in its own worktree, sharing the task notes file.' : 'The agent starts pre-seeded with the task text, its role and the shared notes path.';
    $('#dlg-launch').showModal();
  }
  $('#form-launch').addEventListener('submit', guard(async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target));
    if (f.authMode === 'key' && !f.credentialId) return toast('Pick a key for key mode', true);
    const body = { providerId: f.providerId, authMode: f.authMode, credentialId: f.credentialId || null, isolation: f.isolation };
    let res;
    if (f.swarm === '1') { res = await api('POST', `/api/tasks/${f.taskId}/swarm`, body); $('#dlg-launch').close(); for (const r of res) openPane(r.session.id); focus(res[0]?.session.id); }
    else { res = await api('POST', `/api/tasks/${f.taskId}/launch`, { ...body, role: f.role }); $('#dlg-launch').close(); openPane(res.session.id); focus(res.session.id); }
    refresh();
  }));
  function openFree(providerId) { const f = $('#form-free'); if (providerId) f.providerId.value = providerId; $('#dlg-free').showModal(); }
  $('#form-free').addEventListener('submit', guard(async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target));
    if (f.authMode === 'key' && !f.credentialId) return toast('Pick a key for key mode', true);
    const s = await api('POST', '/api/sessions', { providerId: f.providerId, cwd: f.cwd || undefined, authMode: f.authMode, credentialId: f.credentialId || null, prompt: f.prompt || null });
    $('#dlg-free').close(); openPane(s.id); focus(s.id); refresh();
  }));
  $('#form-task').addEventListener('submit', guard(async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target));
    await api('POST', '/api/tasks', { title: f.title, description: f.description, repoPath: f.repoPath || undefined, baseRef: f.baseRef || null });
    e.target.reset(); $('#dlg-task').close(); refresh();
  }));
  $('#btn-new-task').onclick = () => $('#dlg-task').showModal();
  $('#btn-new-shell').onclick = guard(async () => { const s = await api('POST', '/api/sessions', { providerId: 'shell' }); openPane(s.id); focus(s.id); refresh(); });
  $('#btn-new-agent').onclick = () => openFree();
  $('#btn-drawer').onclick = () => { $('#drawer').hidden = !$('#drawer').hidden; fitAll(); };
  $$('#drawer .tabs button').forEach((b) => { b.onclick = () => { $$('#drawer .tabs button').forEach((x) => x.classList.toggle('active', x === b)); $$('.tab').forEach((t) => t.classList.toggle('active', t.id === `tab-${b.dataset.tab}`)); }; });
  const MODES = ['grid', 'cols', 'focus'];
  $('#btn-layout').onclick = () => { state.mode = MODES[(MODES.indexOf(state.mode) + 1) % MODES.length]; renderGrid(); saveLayout(); };

  // ---------- panes / terminals
  function openPane(id) { if (!state.panes.includes(id)) state.panes.push(id); renderGrid(); saveLayout(); }
  function closePane(id) { state.panes = state.panes.filter((x) => x !== id); const t = state.terms.get(id); if (t) { t.ws.close(); t.term.dispose(); state.terms.delete(id); } if (state.focus === id) state.focus = state.panes[0] || null; renderGrid(); saveLayout(); }
  function focus(id) { state.focus = id; $$('.pane').forEach((p) => p.classList.toggle('focused', p.dataset.id === id)); state.terms.get(id)?.term.focus(); saveLayout(); }
  let saveT; function saveLayout() { clearTimeout(saveT); saveT = setTimeout(() => api('PUT', '/api/layout', { panes: state.panes, focus: state.focus, mode: state.mode }).catch(() => {}), 300); }

  function renderGrid() {
    const g = $('#grid');
    g.className = `grid mode-${state.mode}`;
    $('#btn-layout').textContent = { grid: 'Grid', cols: 'Columns', focus: 'Focus' }[state.mode];
    state.panes = state.panes.filter((id) => state.sessions.some((s) => s.id === id) || state.terms.has(id));
    const n = state.panes.length;
    g.style.setProperty('--cols', n <= 1 ? 1 : n <= 4 ? 2 : n <= 9 ? 3 : 4);
    if (!n) { g.innerHTML = '<div class="empty">No panes open.<br>Create a task and launch agents on it, or open a shell.<br><span class="hint">Alt+N new shell · Alt+T tasks &amp; keys · Alt+L layout · Ctrl/⌘+1…9 focus pane</span></div>'; return; }
    $('.empty', g)?.remove();
    // remove panes no longer wanted
    $$('.pane', g).forEach((p) => { if (!state.panes.includes(p.dataset.id)) p.remove(); });
    // Re-append only when the DOM order differs: moving a node blurs the
    // terminal inside it, which would swallow the user's keystrokes.
    const focusedPane = document.activeElement?.closest?.('.pane')?.dataset.id;
    const current = $$('.pane', g).map((p) => p.dataset.id);
    const reorder = current.some((id, i) => id !== state.panes[i]);
    for (const id of state.panes) {
      let p = $(`.pane[data-id="${id}"]`, g);
      if (!p) { p = buildPane(id); g.append(p); }
      else if (reorder) g.append(p);
      const s = state.sessions.find((x) => x.id === id);
      if (s) updatePaneHeader(p, s);
    }
    if (reorder && focusedPane) state.terms.get(focusedPane)?.term.focus();
    if (!state.focus || !state.panes.includes(state.focus)) state.focus = state.panes[0];
    $$('.pane', g).forEach((p) => p.classList.toggle('focused', p.dataset.id === state.focus));
    requestAnimationFrame(fitAll);
  }
  function buildPane(id) {
    const p = document.createElement('div'); p.className = 'pane'; p.dataset.id = id;
    p.innerHTML = `<header><span class="dot"></span><span class="badge"></span><span class="t"></span><span class="branch"></span>
      <button data-max title="Maximize">⤢</button><button data-kill title="Send SIGTERM">■</button><button data-close title="Close pane (agent keeps running)">–</button><button data-destroy title="Kill and remove session">✕</button></header><div class="term"></div>`;
    p.onmousedown = () => focus(id);
    $('[data-max]', p).onclick = () => { p.classList.toggle('maximized'); fitAll(); };
    $('[data-kill]', p).onclick = guard(() => api('POST', `/api/sessions/${id}/kill`, {}));
    $('[data-close]', p).onclick = () => closePane(id);
    $('[data-destroy]', p).onclick = guard(async () => { await api('DELETE', `/api/sessions/${id}`); closePane(id); refresh(); });
    mountTerminal(id, $('.term', p));
    return p;
  }
  function updatePaneHeader(p, s) {
    $('.t', p).textContent = s.title; $('.t', p).title = `${s.command} ${s.argv?.join(' ') || ''}\n${s.cwd}`;
    $('.badge', p).textContent = s.providerId + (s.authMode !== 'inherit' ? ` · ${s.authMode}` : '');
    $('.branch', p).textContent = s.worktree ? s.worktree.branch : s.cwd.split('/').slice(-2).join('/');
    $('.dot', p).className = `dot ${s.status === 'running' ? 'on' : 'off'}`;
    p.classList.toggle('exited', s.status !== 'running');
  }
  function mountTerminal(id, el) {
    const term = new Terminal({ cursorBlink: true, fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontSize: 13, theme: { background: '#0b0f14', foreground: '#d7e1ea', cursor: '#27d3c3', selectionBackground: '#27d3c355' }, scrollback: 5000, allowProposedApi: true });
    const fit = new FitAddon.FitAddon(); term.loadAddon(fit); term.loadAddon(new WebLinksAddon.WebLinksAddon());
    term.open(el);
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/term/${id}?token=${encodeURIComponent(state.token)}`);
    ws.binaryType = 'arraybuffer';
    const dec = new TextDecoder();
    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        if (ev.data[0] === '{') { try { const m = JSON.parse(ev.data); if (m.type === 'snapshot') { term.write(m.data); return; } if (m.type === 'exit') return; } catch { /* raw */ } }
        term.write(ev.data);
      } else term.write(dec.decode(ev.data));
    };
    ws.onopen = () => { fit.fit(); ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows })); };
    ws.onclose = () => term.write('\r\n\x1b[2m[bridge] disconnected — reload to reattach\x1b[0m\r\n');
    term.onData((d) => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'input', data: d })); });
    term.onResize(({ cols, rows }) => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'resize', cols, rows })); });
    state.terms.set(id, { term, fit, ws });
  }
  function fitAll() { for (const [id, t] of state.terms) { const p = $(`.pane[data-id="${id}"]`); if (p && p.offsetParent !== null && p.offsetHeight > 0) { try { t.fit.fit(); } catch { /* hidden */ } } } }
  window.addEventListener('resize', fitAll);

  // ---------- keyboard
  // Capture phase: xterm cancels keydown on its textarea, so a bubbling
  // listener would never see chords typed while a terminal has focus.
  window.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && /^[1-9]$/.test(e.key)) { const id = state.panes[Number(e.key) - 1]; if (id) { e.preventDefault(); focus(id); } return; }
    // Alt-chords only: bare letters must always reach the terminal.
    if (!e.altKey || e.metaKey || e.ctrlKey) return;
    if (e.code === 'KeyN') { e.preventDefault(); $('#btn-new-shell').click(); }
    if (e.code === 'KeyT') { e.preventDefault(); $('#btn-drawer').click(); }
    if (e.code === 'KeyL') { e.preventDefault(); $('#btn-layout').click(); }
  }, true);

  // ---------- live events
  function connectEvents() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/events?token=${encodeURIComponent(state.token)}`);
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'hello') { state.sessions = m.sessions; state.tasks = m.tasks; renderAll(); }
      if (m.type === 'session') { const i = state.sessions.findIndex((s) => s.id === m.session.id); if (i >= 0) state.sessions[i] = m.session; else state.sessions.push(m.session); renderStats(); renderBoard(); const p = $(`.pane[data-id="${m.session.id}"]`); if (p) updatePaneHeader(p, m.session); }
      if (m.type === 'session_removed') { state.sessions = state.sessions.filter((s) => s.id !== m.id); renderStats(); renderBoard(); }
    };
    ws.onclose = () => setTimeout(connectEvents, 2000);
  }

  // ---------- boot
  const boot = guard(async () => {
    if (!state.token) return askToken();
    const chk = await fetch('/api/auth/check', { headers: { authorization: `Bearer ${state.token}` } });
    if (chk.status !== 200) { localStorage.removeItem('bridge_token'); return askToken(); }
    const layout = await api('GET', '/api/layout');
    state.mode = MODES.includes(layout.mode) ? layout.mode : 'grid';
    await refresh();
    state.panes = (layout.panes || []).filter((id) => state.sessions.some((s) => s.id === id));
    state.focus = layout.focus;
    renderGrid();
    connectEvents();
    if (!state.sessions.length && !$('#drawer').hidden === false) { $('#drawer').hidden = false; }
  });
  boot();
})();
