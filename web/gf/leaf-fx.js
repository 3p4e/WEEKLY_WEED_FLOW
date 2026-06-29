/* leaf-fx.js v2 — 8-mode interactive leaf + GrowFlow wordmark FX + auto-idle */
window.GF = window.GF || {};

GF.leafFX = {
  modes: ['calm','drift','pulse','shake','spin','bounce','storm','rave'],
  labels: {
    calm:   {en:'Calm',    mk:'Мирно'},
    drift:  {en:'Drift',   mk:'Лебди'},
    pulse:  {en:'Pulse',   mk:'Пулс'},
    shake:  {en:'Shake!',  mk:'Тресење!'},
    spin:   {en:'Spin',    mk:'Вртење'},
    bounce: {en:'Bounce',  mk:'Поскок'},
    storm:  {en:'Storm!',  mk:'Бура!'},
    rave:   {en:'Party!',  mk:'Журка!'},
  },

  init() {
    document.querySelectorAll('.leaf-stage').forEach(st => this.bind(st));
    this.initMark();
    // Auto-idle for sidebar + header leaves (start after page warm-up)
    setTimeout(() => {
      const sidebar = document.getElementById('brand-leaf');
      if (sidebar) this.startAutoIdle(sidebar, {restMin:4500, restMax:11000, holdMin:900, holdMax:2000});
      const header  = document.getElementById('header-leaf');
      if (header)  this.startAutoIdle(header,  {restMin:7000, restMax:16000, holdMin:700, holdMax:1500});
    }, 3500);
  },

  bind(stage) {
    if (stage._fx) return; stage._fx = true;
    const d3 = stage.querySelector('.leaf-3d');
    if (!d3) return;
    let hover = false, rx = 0, ry = 0, raf = null;
    const apply = () => {
      raf = null;
      // Enhanced: ±42° tilt, 36 px translateZ, 1.14 scale
      d3.style.transform =
        `rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)` +
        ` translateZ(${hover ? 36 : 0}px) scale(${hover ? 1.14 : 1})`;
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(apply); };

    stage.addEventListener('pointerenter', () => { hover = true;  schedule(); });
    stage.addEventListener('pointerleave', () => { hover = false; rx = 0; ry = 0; schedule(); });
    stage.addEventListener('pointermove', e => {
      const r  = stage.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width  - 0.5;
      const py = (e.clientY - r.top)  / r.height - 0.5;
      ry = px * 42; rx = -py * 42;   // ±42° (was ±28°)
      schedule();
    });
    stage.addEventListener('click',   () => this.cycle(stage));
    stage.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.cycle(stage); }
    });
    stage.setAttribute('tabindex', '0');
    stage.setAttribute('role', 'button');
    stage.setAttribute('aria-label', 'GrowFlow leaf — click to change animation');
    stage.dataset.mode = stage.dataset.mode || 'calm';
  },

  cycle(stage) {
    const i    = this.modes.indexOf(stage.dataset.mode || 'calm');
    const next = this.modes[(i + 1) % this.modes.length];
    stage.dataset.mode = next;
    this.burst(stage, next);
    this.tag(stage, next);
  },

  burst(stage, mode) {
    if (window.matchMedia && matchMedia('(prefers-reduced-motion:reduce)').matches) return;
    const rip = document.createElement('span');
    rip.className = 'leaf-ripple';
    stage.appendChild(rip);
    setTimeout(() => rip.remove(), 700);

    const n = mode === 'rave' ? 26 : (mode === 'storm' || mode === 'shake') ? 18 : 14;
    for (let k = 0; k < n; k++) {
      const s   = document.createElement('span');
      s.className = 'leaf-spark';
      const ang = (Math.PI * 2 * k / n) + Math.random() * 0.65;
      const dist = 30 + Math.random() * 44;
      s.style.setProperty('--dx', (Math.cos(ang) * dist).toFixed(1) + 'px');
      s.style.setProperty('--dy', (Math.sin(ang) * dist).toFixed(1) + 'px');
      const sz = 5 + Math.random() * 6;
      s.style.width = s.style.height = sz.toFixed(1) + 'px';
      if (mode === 'rave') {
        const h = Math.floor(Math.random() * 360);
        s.style.background = `radial-gradient(circle,hsl(${h},92%,74%),hsl(${h},92%,52%))`;
      } else if (mode === 'storm') {
        s.style.background = 'radial-gradient(circle,#b3e0ff,#2F6BFF)';
      } else if (mode === 'pulse') {
        s.style.background = 'radial-gradient(circle,#d4f7bc,#5BBA47)';
      } else if (mode === 'shake') {
        s.style.background = 'radial-gradient(circle,#ffe9b3,#FF9A1A)';
      }
      stage.appendChild(s);
      setTimeout(() => s.remove(), 790);
    }
  },

  tag(stage, mode) {
    let el = stage.querySelector('.leaf-mode-tag');
    if (!el) {
      el = document.createElement('span');
      el.className = 'leaf-mode-tag';
      stage.appendChild(el);
    }
    const lang = (window.GF  && GF.state  && GF.state.lang) ||
                 (window.QC  && QC.lang)  || 'en';
    el.textContent = (this.labels[mode] || {})[lang] || this.labels[mode].en;
    el.classList.remove('show'); void el.offsetWidth; el.classList.add('show');
  },

  /* ── Auto-idle: period of rest → sudden sharp action → rest → repeat ── */
  startAutoIdle(stage, opts) {
    if (stage._autoIdle) return;
    stage._autoIdle = true;
    opts = opts || {};
    const active   = ['pulse','shake','spin','bounce','storm','drift'];
    const restMin  = opts.restMin  || 2000;
    const restMax  = opts.restMax  || 5000;
    const holdMin  = opts.holdMin  || 900;
    const holdMax  = opts.holdMax  || 2000;
    let   lastMode = '';

    const tick = () => {
      if (!document.contains(stage)) return;
      const rest = restMin + Math.random() * (restMax - restMin);
      setTimeout(() => {
        if (!document.contains(stage)) return;
        // pick a mode different from last one
        const pool = active.filter(m => m !== lastMode);
        const mode = pool[Math.floor(Math.random() * pool.length)];
        lastMode = mode;
        stage.dataset.mode = mode;
        this.burst(stage, mode);
        const hold = holdMin + Math.random() * (holdMax - holdMin);

        setTimeout(() => {
          if (!document.contains(stage)) return;
          // 30% chance: chain a second rapid hit before resting
          if (Math.random() < 0.3) {
            const pool2 = active.filter(m => m !== mode);
            const mode2 = pool2[Math.floor(Math.random() * pool2.length)];
            stage.dataset.mode = mode2;
            this.burst(stage, mode2);
            setTimeout(() => {
              if (document.contains(stage)) { stage.dataset.mode = 'calm'; tick(); }
            }, 700 + Math.random() * 400);
          } else {
            stage.dataset.mode = 'calm';
            tick();
          }
        }, hold);
      }, rest);
    };
    tick();
  },

  /* ── GrowFlow wordmark: wrap letters, start wave + periodic sprout ── */
  /* GrowFlow wordmark: periodic bloom on the static .gf-grow-word spans.
     "Grow" span + "Flow" <b> are already in the HTML — no DOM surgery. */
  initMark() {
    const bloom = () => {
      document.querySelectorAll('.gf-grow-word').forEach(w => {
        w.classList.remove('blooming'); void w.offsetWidth; w.classList.add('blooming');
      });
      setTimeout(bloom, 8000 + Math.random() * 8000);
    };
    setTimeout(bloom, 2000 + Math.random() * 3000);
  },
};

// Boot
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => GF.leafFX.init());
} else {
  GF.leafFX.init();
}

// Boot
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => GF.leafFX.init());
} else {
  GF.leafFX.init();
}
