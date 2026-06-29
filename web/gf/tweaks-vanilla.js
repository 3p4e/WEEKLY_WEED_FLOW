/* tweaks-vanilla.js — GrowFlow feel controls (pure vanilla JS, no React).
   Three expressive axes: Character · Palette · Density.
   Persists to localStorage as gf_tweaks_v1. */
(function () {
  /* ── Presets ───────────────────────────────────────────────────────── */
  const CHAR = {
    Clinical: {
      '--r-sm':'4px','--r-md':'6px','--r-lg':'8px','--r-xl':'10px',
      '--sh-1':'0 1px 1px rgba(20,35,60,.10),0 0 0 1px rgba(20,35,60,.06)',
      '--sh-2':'0 2px 6px rgba(20,35,60,.12),0 0 0 1px rgba(20,35,60,.07)',
      '--sh-3':'0 6px 18px rgba(20,35,60,.16)',
    },
    Natural: {
      '--r-sm':'8px','--r-md':'12px','--r-lg':'16px','--r-xl':'22px',
      '--sh-1':'0 1px 2px rgba(20,35,60,.06),0 1px 3px rgba(20,35,60,.05)',
      '--sh-2':'0 4px 14px rgba(20,35,60,.08),0 1px 3px rgba(20,35,60,.05)',
      '--sh-3':'0 14px 40px rgba(20,35,60,.16),0 3px 10px rgba(20,35,60,.07)',
    },
    Bold: {
      '--r-sm':'14px','--r-md':'20px','--r-lg':'28px','--r-xl':'36px',
      '--sh-1':'0 2px 6px rgba(20,35,60,.08),0 1px 4px rgba(20,35,60,.05)',
      '--sh-2':'0 6px 24px rgba(20,35,60,.13),0 2px 6px rgba(20,35,60,.06)',
      '--sh-3':'0 18px 56px rgba(20,35,60,.22),0 5px 16px rgba(20,35,60,.09)',
    },
  };
  const CHAR_EXTRA = {
    Clinical: { borderRadius: '4px',  fontWeightNav: 700, fontWeightTitle: 700 },
    Natural:  { borderRadius: '12px', fontWeightNav: 600, fontWeightTitle: 800 },
    Bold:     { borderRadius: '20px', fontWeightNav: 800, fontWeightTitle: 900 },
  };

  const PALETTES = [
    { label: 'Slate · Citrus',   blue:'#2F6BFF', blue700:'#1E4FD6', blueSoft:'#E7EEFF', orange:'#FF7A1A', orange700:'#E2640A', orangeSoft:'#FFEEDF' },
    { label: 'Forest · Gold',    blue:'#15A86B', blue700:'#0B7A4B', blueSoft:'#DDF4EA', orange:'#F6A609', orange700:'#B45309', orangeSoft:'#FDEFD2' },
    { label: 'Violet · Coral',   blue:'#7A5BE0', blue700:'#5A3FC0', blueSoft:'#ECE6FB', orange:'#FF4D6D', orange700:'#D93050', orangeSoft:'#FFE4EA' },
    { label: 'Midnight · Ember', blue:'#0891B2', blue700:'#0670A0', blueSoft:'#E0F7FB', orange:'#E05C1A', orange700:'#B84410', orangeSoft:'#FFE8D6' },
  ];

  const DENSITY = {
    Compact:  { '--sidebar-w':'214px','--header-h':'52px','fontSize':'13.5px','--density-pad':'10px' },
    Regular:  { '--sidebar-w':'248px','--header-h':'64px','fontSize':'15px',  '--density-pad':'14px' },
    Spacious: { '--sidebar-w':'278px','--header-h':'76px','fontSize':'16px',  '--density-pad':'20px' },
  };

  const DENSITY_DESC = {
    Compact: 'More data, tighter layout.',
    Regular: 'Standard rhythm.',
    Spacious: 'Breathing room, larger targets.',
  };
  const CHAR_DESC = {
    Clinical: 'Sharp corners, strong borders, maximum legibility.',
    Natural:  'Balanced — the designed default.',
    Bold:     'Generous curves, deep shadows, expressive type.',
  };

  /* ── State ── */
  let S = { character: 'Natural', paletteIdx: 0, density: 'Regular' };
  try { Object.assign(S, JSON.parse(localStorage.getItem('gf_tweaks_v1')) || {}); } catch (e) {}

  function save() { try { localStorage.setItem('gf_tweaks_v1', JSON.stringify(S)); } catch (e) {} }

  /* ── Apply ── */
  const root = document.documentElement;
  function applyVars(obj) { Object.entries(obj).forEach(([k, v]) => root.style.setProperty(k, v)); }

  function applyAll() {
    applyVars(CHAR[S.character] || CHAR.Natural);
    const p = PALETTES[S.paletteIdx] || PALETTES[0];
    applyVars({
      '--blue': p.blue, '--blue-700': p.blue700, '--blue-soft': p.blueSoft,
      '--blue-soft-2': p.blueSoft, '--orange': p.orange,
      '--orange-700': p.orange700, '--orange-soft': p.orangeSoft,
    });
    const d = DENSITY[S.density] || DENSITY.Regular;
    applyVars(d);
    root.style.fontSize = d.fontSize;
    // override block for card borders + nav weight
    let el = document.getElementById('__tweaks-css');
    if (!el) { el = document.createElement('style'); el.id = '__tweaks-css'; document.head.appendChild(el); }
    const cx = CHAR_EXTRA[S.character] || CHAR_EXTRA.Natural;
    el.textContent = `
      .kcard,.tlcard,.team-card,.dash-card,.kpi{border-radius:var(--r-md)!important}
      .modal,.sp-card{border-radius:var(--r-lg)!important}
      .nav-item{font-weight:${cx.fontWeightNav}!important}
      .view-title,.kpi-v,.gf-name{font-weight:${cx.fontWeightTitle}!important}
      ${S.character==='Clinical' ? '.btn{border-radius:5px!important}' : ''}
      ${S.character==='Bold' ? '.btn{border-radius:14px!important}' : ''}
    `;
  }

  /* ── Panel HTML ── */
  function buildPanel() {
    const el = document.createElement('div');
    el.id = 'gf-tweaks-panel';
    el.innerHTML = `
      <div id="gftp-header">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" style="width:15px;height:15px;flex-shrink:0"><circle cx="10" cy="10" r="3"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.42 1.42M14.36 14.36l1.42 1.42M4.22 15.78l1.42-1.42M14.36 5.64l1.42-1.42"/></svg>
        <span>Tweaks</span>
        <button id="gftp-close" title="Close">✕</button>
      </div>

      <div class="gftp-sec">Character</div>
      <div class="gftp-desc" id="gftp-char-desc"></div>
      <div class="gftp-radio" id="gftp-char">
        ${['Clinical','Natural','Bold'].map(v => `<button class="gftp-rb" data-char="${v}">${v}</button>`).join('')}
      </div>

      <div class="gftp-sec" style="margin-top:14px">Palette</div>
      <div class="gftp-palettes" id="gftp-pal">
        ${PALETTES.map((p, i) => `
          <button class="gftp-pal-btn" data-pal="${i}" title="${p.label}">
            <span class="gftp-swatch" style="background:${p.blue}"></span>
            <span class="gftp-swatch" style="background:${p.orange}"></span>
            <span class="gftp-pal-lbl">${p.label}</span>
          </button>`).join('')}
      </div>

      <div class="gftp-sec" style="margin-top:14px">Density</div>
      <div class="gftp-desc" id="gftp-dens-desc"></div>
      <div class="gftp-radio" id="gftp-dens">
        ${['Compact','Regular','Spacious'].map(v => `<button class="gftp-rb" data-dens="${v}">${v}</button>`).join('')}
      </div>
    `;
    return el;
  }

  /* ── CSS ── */
  const style = document.createElement('style');
  style.textContent = `
    #gf-tweaks-panel{
      position:fixed;bottom:72px;right:16px;z-index:9999;
      width:238px;background:var(--surface,#fff);
      border:1px solid var(--line,#E2E8F1);border-radius:14px;
      box-shadow:0 12px 40px rgba(16,28,50,.18),0 2px 8px rgba(16,28,50,.1);
      font-family:'Manrope',system-ui,sans-serif;font-size:12.5px;
      padding:0 0 14px;overflow:hidden;
      transform:translateY(10px) scale(.97);opacity:0;pointer-events:none;
      transition:transform .22s cubic-bezier(.22,1,.36,1),opacity .18s;
    }
    #gf-tweaks-panel.open{transform:none;opacity:1;pointer-events:all}
    #gftp-header{display:flex;align-items:center;gap:7px;padding:12px 14px 10px;
      border-bottom:1px solid var(--line,#E2E8F1);font-weight:800;font-size:12.5px;color:var(--ink,#16233B)}
    #gftp-close{margin-left:auto;background:none;border:none;cursor:pointer;color:var(--ink-3,#8A99B0);
      font-size:14px;line-height:1;padding:2px 4px;border-radius:5px}
    #gftp-close:hover{background:var(--surface-2,#F6F8FC);color:var(--ink,#16233B)}
    .gftp-sec{font-size:10px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;
      color:var(--ink-3,#8A99B0);padding:12px 14px 4px}
    .gftp-desc{font-size:11px;color:var(--ink-3,#8A99B0);padding:0 14px 6px;line-height:1.4;min-height:14px}
    .gftp-radio{display:flex;gap:4px;padding:0 14px}
    .gftp-rb{flex:1;border:1px solid var(--line,#E2E8F1);background:var(--surface-2,#F6F8FC);
      color:var(--ink-2,#566884);border-radius:8px;padding:7px 4px;font-size:11.5px;font-weight:700;
      cursor:pointer;font-family:inherit;transition:background .12s,color .12s,border-color .12s}
    .gftp-rb:hover{background:var(--surface,#fff);color:var(--ink,#16233B)}
    .gftp-rb.on{background:var(--blue,#2F6BFF);color:#fff;border-color:var(--blue,#2F6BFF)}
    .gftp-palettes{display:flex;flex-direction:column;gap:5px;padding:0 14px}
    .gftp-pal-btn{display:flex;align-items:center;gap:8px;width:100%;border:1px solid var(--line,#E2E8F1);
      background:var(--surface-2,#F6F8FC);border-radius:9px;padding:7px 10px;cursor:pointer;font-family:inherit;
      transition:background .12s,border-color .12s}
    .gftp-pal-btn:hover{background:var(--surface,#fff)}
    .gftp-pal-btn.on{border-color:var(--blue,#2F6BFF);background:var(--blue-soft,#E7EEFF)}
    .gftp-swatch{width:16px;height:16px;border-radius:5px;flex-shrink:0;box-shadow:0 1px 3px rgba(0,0,0,.15)}
    .gftp-pal-lbl{font-size:11.5px;font-weight:700;color:var(--ink-2,#566884)}
    .gftp-pal-btn.on .gftp-pal-lbl{color:var(--blue-700,#1E4FD6)}

    /* toggle button (floating, bottom-right) */
    #gf-tweaks-toggle{
      position:fixed;bottom:16px;right:16px;z-index:9999;
      width:42px;height:42px;border-radius:12px;
      background:var(--surface,#fff);border:1px solid var(--line,#E2E8F1);
      box-shadow:0 4px 16px rgba(16,28,50,.14);cursor:pointer;
      display:flex;align-items:center;justify-content:center;
      transition:background .15s,box-shadow .15s;
    }
    #gf-tweaks-toggle:hover{background:var(--blue-soft,#E7EEFF);box-shadow:0 6px 22px rgba(47,107,255,.2)}
    #gf-tweaks-toggle svg{stroke:var(--ink-3,#8A99B0)}
    #gf-tweaks-toggle.active svg{stroke:var(--blue,#2F6BFF)}
  `;
  document.head.appendChild(style);

  /* ── Mount panel + toggle ── */
  const panel = buildPanel();
  const toggle = document.createElement('button');
  toggle.id = 'gf-tweaks-toggle';
  toggle.title = 'Tweaks';
  toggle.innerHTML = `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" style="width:18px;height:18px">
    <circle cx="10" cy="10" r="2.5"/>
    <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.42 1.42M14.36 14.36l1.42 1.42M4.22 15.78l1.42-1.42M14.36 5.64l1.42-1.42"/>
  </svg>`;

  function render() {
    // character
    panel.querySelectorAll('[data-char]').forEach(b => b.classList.toggle('on', b.dataset.char === S.character));
    panel.querySelector('#gftp-char-desc').textContent = CHAR_DESC[S.character] || '';
    // palette
    panel.querySelectorAll('[data-pal]').forEach(b => b.classList.toggle('on', +b.dataset.pal === S.paletteIdx));
    // density
    panel.querySelectorAll('[data-dens]').forEach(b => b.classList.toggle('on', b.dataset.dens === S.density));
    panel.querySelector('#gftp-dens-desc').textContent = DENSITY_DESC[S.density] || '';
    // update palette btn swatch colors (they already reflect PALETTES array, static is fine)
  }

  panel.addEventListener('click', e => {
    const char = e.target.closest('[data-char]')?.dataset.char;
    const pal = e.target.closest('[data-pal]')?.dataset.pal;
    const dens = e.target.closest('[data-dens]')?.dataset.dens;
    if (char) { S.character = char; save(); applyAll(); render(); }
    if (pal !== undefined) { S.paletteIdx = +pal; save(); applyAll(); render(); }
    if (dens) { S.density = dens; save(); applyAll(); render(); }
    if (e.target.id === 'gftp-close') { panel.classList.remove('open'); toggle.classList.remove('active'); }
  });

  toggle.addEventListener('click', () => {
    const open = panel.classList.toggle('open');
    toggle.classList.toggle('active', open);
  });

  // Host protocol (Tweaks button in toolbar)
  window.addEventListener('message', e => {
    if (!e.data) return;
    if (e.data.type === '__activate_edit_mode' || e.data.action === '__activate_edit_mode') {
      panel.classList.add('open'); toggle.classList.add('active');
    }
    if (e.data.type === '__deactivate_edit_mode' || e.data.action === '__deactivate_edit_mode') {
      panel.classList.remove('open'); toggle.classList.remove('active');
    }
  });
  // Announce availability
  try { window.parent.postMessage({ type: '__edit_mode_available', keys: ['character','paletteIdx','density'] }, '*'); } catch (e) {}

  document.body.appendChild(panel);
  document.body.appendChild(toggle);

  applyAll();
  render();

  // Now tackle the OOS deep-link: when viewOOS is called, scroll/jump to current phase
  // (see separate OOS enhancement below)
})();
