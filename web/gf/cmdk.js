/* cmdk.js — ⌘K / Ctrl+K command palette. Global: GF.cmdk
   Fuzzy-jump to any view, task (incl. tree children), or person. Pure
   client-side: searches what's already in memory (GF.state.tasks/children,
   GF.PEOPLE, the nav views). Idea adopted from the Mass Weed mockups. */
window.GF = window.GF || {};

(function () {
  const AL = (en, mk) => (GF.state.lang === 'mk' ? mk : en);
  let open = false, sel = 0, results = [];

  const VIEWS = () => {
    const v = [
      ['mywork', 'my_week'], ['board', 'board'], ['timeline', 'timeline'],
      ['calendar', 'calendar'], ['coord', 'coordination'], ['dash', 'dashboard'], ['team', 'team'],
    ];
    if (GF.isExec && GF.isExec()) v.unshift(['exec', 'exec_overview']);
    if (GF.hasDeptHome && GF.hasDeptHome()) v.unshift(['depthome', 'dept_home']);
    if (GF.can && GF.can('team')) v.push(['workload', 'workload']);
    return v.map(([id, key]) => ({ kind: 'view', id, label: GF.t(key) }));
  };

  const allTasks = () => {
    const kids = Object.values(GF.state.children || {}).flat();
    return (GF.state.tasks || []).concat(kids);
  };

  // Simple subsequence-friendly scorer: exact substring beats word-prefix
  // beats scattered match; shorter titles win ties.
  const score = (q, s) => {
    s = s.toLowerCase();
    const i = s.indexOf(q);
    if (i === 0) return 100 - s.length * 0.01;
    if (i > 0) return 60 - i * 0.1 - s.length * 0.01;
    let qi = 0;
    for (const ch of s) if (ch === q[qi]) qi++;
    return qi === q.length ? 20 - s.length * 0.01 : -1;
  };

  const search = (q) => {
    q = q.trim().toLowerCase();
    const out = [];
    for (const v of VIEWS()) {
      const sc = q ? score(q, v.label) : 50;
      if (sc >= 0) out.push({ ...v, sc, group: AL('Go to', 'Оди на') });
    }
    if (q) {
      for (const t of allTasks()) {
        const sc = Math.max(score(q, t.title || ''), score(q, t.ref || ''));
        if (sc >= 0) out.push({ kind: 'task', id: t.id, label: t.title, sub: GF.depAbbr(t.dept), sc: sc - 1, group: AL('Tasks', 'Задачи') });
      }
      for (const [pid, p] of Object.entries(GF.PEOPLE || {})) {
        const sc = score(q, p.name || '');
        if (sc >= 0) out.push({ kind: 'person', id: pid, label: p.name, sub: p.roleLabel || '', sc: sc - 2, group: AL('People', 'Луѓе') });
      }
    }
    return out.sort((a, b) => b.sc - a.sc).slice(0, 12);
  };

  const pick = (r) => {
    GF.cmdk.close();
    if (!r) return;
    if (r.kind === 'view') GF.setView(r.id);
    else if (r.kind === 'task') {
      const t = GF.task ? GF.task(r.id) : null;
      if (GF.WWF && GF.WWF.xrJump) GF.WWF.xrJump(r.id, (t && t.week_start) || '');
      else { GF.state.expanded.add(r.id); GF.setView('mywork'); }
    } else if (r.kind === 'person') GF.setView('team');
  };

  const rowHtml = (r, i) => `
    <div class="ck-row ${i === sel ? 'on' : ''}" onmousedown="event.preventDefault();GF.cmdk._pick(${i})">
      <span class="ck-kind">${GF.esc(r.group)}</span>
      <span class="ck-label">${GF.esc(r.label || '')}</span>
      ${r.sub ? `<span class="ck-sub">${GF.esc(r.sub)}</span>` : ''}
    </div>`;

  const render = () => {
    const list = GF.$('ck-list');
    if (list) list.innerHTML = results.map(rowHtml).join('')
      || `<div class="ck-empty">${AL('No matches', 'Нема совпаѓања')}</div>`;
  };

  const ensureDom = () => {
    if (GF.$('cmdk-overlay')) return;
    const el = document.createElement('div');
    el.id = 'cmdk-overlay';
    el.innerHTML = `<div class="ck-box">
        <input id="ck-input" autocomplete="off" spellcheck="false"
               placeholder="${AL('Jump to a view, task or person…', 'Скокни до преглед, задача или личност…')}">
        <div id="ck-list"></div>
        <div class="ck-hint">↑↓ · Enter · Esc</div>
      </div>`;
    el.addEventListener('mousedown', (e) => { if (e.target === el) GF.cmdk.close(); });
    document.body.appendChild(el);
    const st = document.createElement('style');
    st.textContent = `
      #cmdk-overlay{position:fixed;inset:0;z-index:900;display:none;align-items:flex-start;justify-content:center;
        padding-top:12vh;background:var(--overlay);backdrop-filter:blur(6px)}
      #cmdk-overlay.open{display:flex}
      .ck-box{width:560px;max-width:92vw;background:var(--glass-bg);backdrop-filter:var(--glass-blur);
        border:1px solid var(--glass-border);border-radius:var(--r-lg,12px);box-shadow:var(--sh-3);overflow:hidden}
      #ck-input{width:100%;box-sizing:border-box;background:var(--surface-2);border:none;outline:none;
        color:var(--ink);font:inherit;font-size:16px;padding:14px 16px;border-bottom:1px solid var(--line)}
      #ck-list{max-height:46vh;overflow-y:auto;padding:6px}
      .ck-row{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;cursor:pointer}
      .ck-row.on,.ck-row:hover{background:var(--primary-soft)}
      .ck-kind{flex:none;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
        color:var(--ink-3);width:64px}
      .ck-label{flex:1;min-width:0;color:var(--ink);font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .ck-sub{flex:none;font-size:11px;color:var(--ink-3)}
      .ck-empty{padding:18px;text-align:center;color:var(--ink-3);font-size:13px}
      .ck-hint{padding:7px 12px;border-top:1px solid var(--line-2);font-size:10.5px;color:var(--ink-4);text-align:right}`;
    document.head.appendChild(st);
    GF.$('ck-input').addEventListener('input', (e) => { sel = 0; results = search(e.target.value); render(); });
    GF.$('ck-input').addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { sel = Math.min(sel + 1, results.length - 1); render(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); render(); e.preventDefault(); }
      else if (e.key === 'Enter') { pick(results[sel]); }
      else if (e.key === 'Escape') { GF.cmdk.close(); }
    });
  };

  GF.cmdk = {
    open() {
      ensureDom();
      open = true; sel = 0; results = search('');
      GF.$('cmdk-overlay').classList.add('open');
      const inp = GF.$('ck-input'); inp.value = ''; render(); inp.focus();
    },
    close() { open = false; const el = GF.$('cmdk-overlay'); if (el) el.classList.remove('open'); },
    toggle() { open ? this.close() : this.open(); },
    _pick(i) { pick(results[i]); },
  };
})();
