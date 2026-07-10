/* tweaks-vanilla.js — GrowFlow feel controls (pure vanilla JS, no React).
   Three expressive axes: Character · Palette · Density.
   Persists to localStorage as gf_tweaks_v1. */
(function () {
  // The live design-tweaks EDITOR is a design-time tool, not a shipped user
  // feature — its floating panel/toggle only mount when explicitly opted in
  // (localStorage gf_design='1' or ?design=1) so normal users never see it.
  // Applying a PREVIOUSLY saved gf_tweaks_v1 customization is a separate
  // concern that must always run (see the unconditional applyAll() call
  // below) — gating that too would silently stop honoring a customization
  // someone saved before this opt-in was added.
  var _designMode = false;
  try { _designMode = localStorage.getItem('gf_design') === '1' || /[?&]design=1(&|$)/.test(location.search); } catch (e) {}

  /* ── Presets ───────────────────────────────────────────────────────── */
  const CHAR = {
    Clinical: {
      '--r-sm':'4px','--r-md':'6px','--r-lg':'8px','--r-xl':'10px',
      '--sh-1':'0 1px 1px rgba(0,0,0,.25),0 0 0 1px rgba(43,232,160,.08)',
      '--sh-2':'0 2px 6px rgba(0,0,0,.30),0 0 0 1px rgba(43,232,160,.10)',
      '--sh-3':'0 6px 18px rgba(0,0,0,.40)',
    },
    Natural: {
      '--r-sm':'8px','--r-md':'12px','--r-lg':'16px','--r-xl':'22px',
      '--sh-1':'0 1px 2px rgba(0,0,0,.20),0 1px 3px rgba(0,0,0,.15)',
      '--sh-2':'0 4px 14px rgba(0,0,0,.28),0 1px 3px rgba(0,0,0,.15)',
      '--sh-3':'0 14px 40px rgba(0,0,0,.40),0 3px 10px rgba(0,0,0,.20)',
    },
    Bold: {
      '--r-sm':'14px','--r-md':'20px','--r-lg':'28px','--r-xl':'36px',
      '--sh-1':'0 2px 6px rgba(0,0,0,.22),0 1px 4px rgba(0,0,0,.15)',
      '--sh-2':'0 6px 24px rgba(0,0,0,.32),0 2px 6px rgba(0,0,0,.18)',
      '--sh-3':'0 18px 56px rgba(0,0,0,.50),0 5px 16px rgba(0,0,0,.22)',
    },
  };
  const CHAR_EXTRA = {
    Clinical: { borderRadius: '4px',  fontWeightNav: 700, fontWeightTitle: 700 },
    Natural:  { borderRadius: '12px', fontWeightNav: 600, fontWeightTitle: 800 },
    Bold:     { borderRadius: '20px', fontWeightNav: 800, fontWeightTitle: 900 },
  };

  // PALETTES[0] is the branded default — must match app.css dark-theme tokens.
  // Updating this here keeps applyAll() from overwriting the refactored CSS vars
  // with stale light-mode values for every user whose paletteIdx is 0 (the default).
  const PALETTES = [
    { label: 'Plasma · Bronze',   blue:'#2FD9D9', blue700:'#1FB3B3', blueSoft:'rgba(47,217,217,.15)', orange:'#E0A73E', orange700:'#C0862A', orangeSoft:'rgba(224,167,62,.15)' },
    { label: 'Forest · Gold',    blue:'#15A86B', blue700:'#0B7A4B', blueSoft:'rgba(21,168,107,.15)', orange:'#F6A609', orange700:'#B45309', orangeSoft:'rgba(246,166,9,.15)' },
    { label: 'Violet · Coral',   blue:'#7A5BE0', blue700:'#5A3FC0', blueSoft:'rgba(122,91,224,.15)', orange:'#FF4D6D', orange700:'#D93050', orangeSoft:'rgba(255,77,109,.15)' },
    { label: 'Midnight · Ember', blue:'#0891B2', blue700:'#0670A0', blueSoft:'rgba(8,145,178,.15)', orange:'#E05C1A', orange700:'#B84410', orangeSoft:'rgba(224,92,26,.15)' },
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
    // The accent-palette axis writes --blue/--orange as INLINE styles on <html>,
    // which beat any :root[data-theme="…"] rule. Only do that when the user has
    // EXPLICITLY chosen a non-default palette (design mode). paletteIdx 0 means
    // "use the active theme's own accents", so leave them alone — otherwise
    // these inline vars clobber the light/suma skins' cyan/gold with the dark
    // theme's teal/bronze. Also clear any previously-pinned inline values so
    // switching back to palette 0 releases the theme's tokens.
    if (S.paletteIdx !== 0) {
      const p = PALETTES[S.paletteIdx] || PALETTES[0];
      applyVars({
        '--blue': p.blue, '--blue-700': p.blue700, '--blue-soft': p.blueSoft,
        '--blue-soft-2': p.blueSoft, '--orange': p.orange,
        '--orange-700': p.orange700, '--orange-soft': p.orangeSoft,
      });
    } else {
      ['--blue', '--blue-700', '--blue-soft', '--blue-soft-2', '--orange', '--orange-700', '--orange-soft']
        .forEach(k => root.style.removeProperty(k));
    }
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
  applyAll();   // reapply any previously saved customization for every visitor
  if (!_designMode) return;   // everything below builds/mounts the editor UI

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
      width:238px;background:var(--surface,#0B1913);
      border:1px solid var(--line,rgba(43,232,160,.12));border-radius:14px;
      box-shadow:0 12px 40px rgba(0,0,0,.45),0 2px 8px rgba(0,0,0,.30);
      font-family:'Saira',system-ui,sans-serif;font-size:12.5px;
      padding:0 0 14px;overflow:hidden;
      transform:translateY(10px) scale(.97);opacity:0;pointer-events:none;
      transition:transform .22s cubic-bezier(.22,1,.36,1),opacity .18s;
    }
    #gf-tweaks-panel.open{transform:none;opacity:1;pointer-events:all}
    #gftp-header{display:flex;align-items:center;gap:7px;padding:12px 14px 10px;
      border-bottom:1px solid var(--line,rgba(43,232,160,.12));font-weight:800;font-size:12.5px;color:var(--ink,#DDF3E9)}
    #gftp-close{margin-left:auto;background:none;border:none;cursor:pointer;color:var(--ink-3,#5F8575);
      font-size:14px;line-height:1;padding:2px 4px;border-radius:5px}
    #gftp-close:hover{background:var(--surface-2,#102219);color:var(--ink,#DDF3E9)}
    .gftp-sec{font-size:10px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;
      color:var(--ink-3,#5F8575);padding:12px 14px 4px}
    .gftp-desc{font-size:11px;color:var(--ink-3,#5F8575);padding:0 14px 6px;line-height:1.4;min-height:14px}
    .gftp-radio{display:flex;gap:4px;padding:0 14px}
    .gftp-rb{flex:1;border:1px solid var(--line,rgba(43,232,160,.12));background:var(--surface-2,#102219);
      color:var(--ink-2,#8FB6A6);border-radius:8px;padding:7px 4px;font-size:11.5px;font-weight:700;
      cursor:pointer;font-family:inherit;transition:background .12s,color .12s,border-color .12s}
    .gftp-rb:hover{background:var(--surface,#0B1913);color:var(--ink,#DDF3E9)}
    .gftp-rb.on{background:var(--blue,#2FD9D9);color:#03130C;border-color:var(--blue,#2FD9D9)}
    .gftp-palettes{display:flex;flex-direction:column;gap:5px;padding:0 14px}
    .gftp-pal-btn{display:flex;align-items:center;gap:8px;width:100%;border:1px solid var(--line,rgba(43,232,160,.12));
      background:var(--surface-2,#102219);border-radius:9px;padding:7px 10px;cursor:pointer;font-family:inherit;
      transition:background .12s,border-color .12s}
    .gftp-pal-btn:hover{background:var(--surface,#0B1913)}
    .gftp-pal-btn.on{border-color:var(--blue,#2FD9D9);background:var(--blue-soft,rgba(47,217,217,.15))}
    .gftp-swatch{width:16px;height:16px;border-radius:5px;flex-shrink:0;box-shadow:0 1px 3px rgba(0,0,0,.35)}
    .gftp-pal-lbl{font-size:11.5px;font-weight:700;color:var(--ink-2,#8FB6A6)}
    .gftp-pal-btn.on .gftp-pal-lbl{color:var(--blue-700,#1FB3B3)}

    /* toggle button (floating, bottom-right) */
    #gf-tweaks-toggle{
      position:fixed;bottom:16px;right:16px;z-index:9999;
      width:42px;height:42px;border-radius:12px;
      background:var(--surface,#0B1913);border:1px solid var(--line,rgba(43,232,160,.12));
      box-shadow:0 4px 16px rgba(0,0,0,.35);cursor:pointer;
      display:flex;align-items:center;justify-content:center;
      transition:background .15s,box-shadow .15s;
    }
    #gf-tweaks-toggle:hover{background:var(--blue-soft,rgba(47,217,217,.15));box-shadow:0 6px 22px rgba(47,217,217,.2)}
    #gf-tweaks-toggle svg{stroke:var(--ink-3,#5F8575)}
    #gf-tweaks-toggle.active svg{stroke:var(--blue,#2FD9D9)}
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

  render();   // sync the panel's active-option highlighting to the state applyAll() already applied
})();
