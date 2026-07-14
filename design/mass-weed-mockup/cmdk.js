/* MASS WEED — global command palette (⌘K / Ctrl+K)
   Drop into any page:  <script src="cmdk.js"></script>
   Injects its own styles + overlay; no dependencies. */
(function () {
  const NAV = [
    ['Dashboard', 'dashboard.html', 'screen'],
    ['Cycle Board', 'board.html', 'screen'],
    ['My Day', 'my-day.html', 'screen'],
    ['Schedule', 'calendar.html', 'screen'],
    ['Crew Workload', 'workload.html', 'screen'],
    ['SOP Library', 'sop.html', 'screen'],
    ['Approvals', 'approvals.html', 'screen'],
    ['Reports', 'reports.html', 'screen'],
    ['Search', 'search.html', 'screen'],
    ['Analytics', 'analytics.html', 'screen'],
    ['Automations', 'automations.html', 'screen'],
    ['Orders', 'orders.html', 'screen'],
    ['Inventory', 'index.html', 'screen'],
    ['Climate', 'environment.html', 'screen'],
    ['Genetics', 'genetics.html', 'screen'],
    ['Nutrients', 'nutrients.html', 'screen'],
    ['Harvest', 'harvest.html', 'screen'],
    ['Cure', 'cure.html', 'screen'],
    ['Packaging', 'packaging.html', 'screen'],
    ['Crew', 'team.html', 'screen'],
    ['Compliance', 'compliance.html', 'screen'],
    ['Vault', 'decrypt.html', 'screen'],
  ];
  const ACTIONS = [
    ['New task', 'task-detail.html?new=1', 'action'],
    ['New order', 'orders.html', 'action'],
    ['New automation rule', 'rule-builder.html', 'action'],
    ['Build a report', 'reports.html', 'action'],
    ['Review approvals', 'approvals.html', 'action'],
    ['Log harvest', 'harvest.html', 'action'],
    ['Scan METRC tag', 'compliance.html', 'action'],
    ['Sign out', 'login.html', 'action'],
  ];
  const RECS = [
    ['Batch F-24 — Cure', 'batch.html?id=F-24', 'batch'],
    ['Batch A-07 — Flower A', 'batch.html?id=A-07', 'batch'],
    ['Order #MW-3182 — Nova Dispensary', 'order-detail.html?id=MW-3182', 'order'],
    ['Order #MW-3179 — Element Retail', 'order-detail.html?id=MW-3179', 'order'],
    ['Wedding Cake IX', 'genetics.html', 'strain'],
    ['Zone 4 Climate', 'environment.html', 'zone'],
  ];
  const ALL = [
    ...ACTIONS.map(x => ({ label: x[0], href: x[1], kind: x[2], group: 'Quick actions' })),
    ...NAV.map(x => ({ label: x[0], href: x[1], kind: x[2], group: 'Go to' })),
    ...RECS.map(x => ({ label: x[0], href: x[1], kind: x[2], group: 'Records' })),
  ];

  const KIND_ICON = {
    screen: 'M4 5h16v14H4zM4 9h16',
    action: 'M12 5v14M5 12h14',
    batch: 'M12 2l8 4v12l-8 4-8-4V6z',
    order: 'M5 7h14l-1 12H6zM9 7V5a3 3 0 0 1 6 0v2',
    strain: 'M12 2c-1 5-5 7-5 11a5 5 0 0 0 10 0c0-4-4-6-5-11z',
    zone: 'M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11z',
  };

  const css = `
  .cmdk-ov{position:fixed;inset:0;z-index:9999;display:none;align-items:flex-start;justify-content:center;
    background:rgba(2,10,22,.72);backdrop-filter:blur(6px);padding-top:12vh;font-family:var(--mw-font,'Saira',sans-serif);}
  .cmdk-ov.open{display:flex;animation:cmdkFade .14s ease;}
  @keyframes cmdkFade{from{opacity:0}to{opacity:1}}
  .cmdk{width:min(620px,92vw);background:linear-gradient(180deg,rgba(9,26,48,.96),rgba(5,16,32,.97));
    clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px);
    box-shadow:0 0 0 1px rgba(94,200,240,.35),0 0 40px rgba(58,159,212,.25),0 24px 60px rgba(0,0,0,.6);
    overflow:hidden;animation:cmdkRise .16s ease;}
  @keyframes cmdkRise{from{transform:translateY(-8px);opacity:.4}to{transform:translateY(0);opacity:1}}
  .cmdk-in{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid rgba(94,200,240,.18);}
  .cmdk-in svg{width:18px;height:18px;color:var(--mw-cyan,#5ec8f0);flex:none;}
  .cmdk-in input{flex:1;background:none;border:none;outline:none;color:var(--mw-ink,#eaf6ff);font-size:16px;
    font-family:inherit;letter-spacing:.02em;}
  .cmdk-in input::placeholder{color:rgba(148,190,220,.5);}
  .cmdk-in kbd{font-size:10px;letter-spacing:.1em;color:var(--mw-text-faint,#6f93b0);
    border:1px solid rgba(94,200,240,.25);border-radius:3px;padding:2px 6px;}
  .cmdk-list{max-height:52vh;overflow-y:auto;padding:8px;}
  .cmdk-grp{font-size:10px;text-transform:uppercase;letter-spacing:.16em;color:var(--mw-text-faint,#6f93b0);
    padding:12px 12px 6px;}
  .cmdk-it{display:flex;align-items:center;gap:12px;padding:10px 12px;cursor:pointer;border-radius:3px;
    color:var(--mw-text,#c4dcec);font-size:14px;}
  .cmdk-it svg{width:16px;height:16px;color:var(--mw-cyan-dim,#3a9fd4);flex:none;}
  .cmdk-it .k{margin-left:auto;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--mw-text-faint,#6f93b0);}
  .cmdk-it.sel{background:linear-gradient(90deg,rgba(58,159,212,.22),rgba(58,159,212,.05));
    box-shadow:inset 2px 0 0 var(--mw-cyan,#5ec8f0);color:var(--mw-ink,#eaf6ff);}
  .cmdk-it.sel svg{color:var(--mw-cyan-bright,#8fdcff);}
  .cmdk-empty{padding:28px;text-align:center;color:var(--mw-text-faint,#6f93b0);font-size:13px;}
  .cmdk-ft{display:flex;gap:16px;padding:10px 18px;border-top:1px solid rgba(94,200,240,.14);
    font-size:10px;letter-spacing:.08em;color:var(--mw-text-faint,#6f93b0);text-transform:uppercase;}
  .cmdk-ft b{color:var(--mw-text-dim,#94beDC);font-weight:600;}`;

  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  const ov = document.createElement('div');
  ov.className = 'cmdk-ov';
  ov.innerHTML = `
    <div class="cmdk" role="dialog" aria-label="Command palette">
      <div class="cmdk-in">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>
        <input type="text" placeholder="Search screens, records, or run a command…" aria-label="Search"/>
        <kbd>ESC</kbd>
      </div>
      <div class="cmdk-list"></div>
      <div class="cmdk-ft"><span><b>↑↓</b> navigate</span><span><b>↵</b> open</span><span><b>⌘K</b> toggle</span></div>
    </div>`;
  document.body.appendChild(ov);

  const input = ov.querySelector('input');
  const list = ov.querySelector('.cmdk-list');
  let sel = 0, flat = [];

  function render(q) {
    q = (q || '').trim().toLowerCase();
    const hits = q ? ALL.filter(i => i.label.toLowerCase().includes(q)) : ALL;
    flat = hits;
    if (!hits.length) { list.innerHTML = `<div class="cmdk-empty">No matches for “${q}”</div>`; return; }
    const groups = {};
    hits.forEach(h => { (groups[h.group] = groups[h.group] || []).push(h); });
    let html = '', idx = 0;
    for (const g of Object.keys(groups)) {
      html += `<div class="cmdk-grp">${g}</div>`;
      for (const it of groups[g]) {
        html += `<div class="cmdk-it${idx === sel ? ' sel' : ''}" data-i="${idx}" data-href="${it.href}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="${KIND_ICON[it.kind] || KIND_ICON.screen}"/></svg>
          <span>${it.label}</span><span class="k">${it.kind}</span></div>`;
        idx++;
      }
    }
    list.innerHTML = html;
    list.querySelectorAll('.cmdk-it').forEach(el => {
      el.addEventListener('mouseenter', () => { sel = +el.dataset.i; paint(); });
      el.addEventListener('click', () => go(+el.dataset.i));
    });
  }
  function paint() {
    list.querySelectorAll('.cmdk-it').forEach(el => el.classList.toggle('sel', +el.dataset.i === sel));
    const cur = list.querySelector('.cmdk-it.sel');
    if (cur) cur.scrollIntoView ? 0 : 0; // avoid scrollIntoView per guidelines
    if (cur) { const r = cur.offsetTop; if (r < list.scrollTop || r > list.scrollTop + list.clientHeight - 40) list.scrollTop = r - 60; }
  }
  function go(i) { const it = flat[i]; if (it) location.href = it.href; }

  function open() { ov.classList.add('open'); input.value = ''; sel = 0; render(''); setTimeout(() => input.focus(), 20); }
  function close() { ov.classList.remove('open'); }
  function toggle() { ov.classList.contains('open') ? close() : open(); }

  input.addEventListener('input', () => { sel = 0; render(input.value); });
  ov.addEventListener('mousedown', e => { if (e.target === ov) close(); });
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); toggle(); return; }
    if (!ov.classList.contains('open')) return;
    if (e.key === 'Escape') { close(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, flat.length - 1); paint(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); paint(); }
    else if (e.key === 'Enter') { e.preventDefault(); go(sel); }
  });

  window.MWCmdK = { open, close, toggle };
})();
