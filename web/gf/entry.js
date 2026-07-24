/* entry.js — 3D-leaf splash + sign-in. Overrides GF.WWF.showLogin /
   showChangePw (defined in integrate.js, which is loaded first) to present the
   interactive three.js leaf (leaf3d.js) as a full-screen splash: the leaf is the
   hero, "tap the leaf to enter" reveals the glass sign-in card sliding in beneath
   the shrunk/lifted leaf. This replaces ONLY the presentation — it reuses the
   real auth (GF.WWF.doLogin / doChangePw / loadAndRender) untouched, and reuses
   the same field ids (#wwf-u / #wwf-p / #wwf-login-msg / #wwf-np / #wwf-np2). */
window.GF = window.GF || {};
GF.WWF = GF.WWF || {};

(function () {
  // Leaf a touch smaller on phones so the whole splash fits above the card.
  const leafSize = () => Math.max(200, Math.min(280, Math.round((window.innerWidth || 360) * 0.72)));

  let leaf = null;      // live leaf3d instance (destroyed on login / re-show)
  let opened = false;   // reveal guard — true once the card is shown
  let entrySkin = 'dark'; // the random skin showcased on the current splash

  const $ = (id) => (window.GF && GF.$ ? GF.$(id) : document.getElementById(id));

  // The splash/login screen showcases a RANDOM skin each time it's shown — the
  // leaf, glows and accents take that skin's palette. Restricted to the dark
  // skin group so the splash's dark stage always reads well (a light skin would
  // wash out the glowing leaf). Applied to the DOM only — never persisted, so a
  // real user's saved skin is untouched and is re-applied the moment they log in
  // (see the loadAndRender override below).
  function pickEntrySkin() {
    try {
      if (!(GF.THEMES && GF.setTheme)) return 'mass-weed';
      const pool = GF.THEMES.filter(t => t.group === 'dark');
      const pick = (pool.length ? pool : GF.THEMES)[Math.floor(Math.random() * (pool.length || GF.THEMES.length))];
      entrySkin = (pick && pick.id) || 'dark';
      GF.setTheme(entrySkin, { silent: true, noPersist: true });
    } catch (e) { entrySkin = 'dark'; }
    return entrySkin;
  }

  function loginCardHTML() {
    return `
      <div class="gf-card-title">Weekly Weed Flow</div>
      <div class="gf-card-sub">${AL('Sign in to continue', 'Најавете се за да продолжите')}</div>
      <input id="wwf-u" class="gf-in" placeholder="${AL('Username', 'Корисничко име')}" autocomplete="username" autocapitalize="none" spellcheck="false">
      <input id="wwf-p" class="gf-in" type="password" placeholder="${AL('Password', 'Лозинка')}" autocomplete="current-password"
             onkeydown="if(event.key==='Enter')GF.WWF.doLogin()">
      <button class="gf-btn" onclick="GF.WWF.doLogin()">${AL('Sign in', 'Најави се')}</button>
      <div id="wwf-login-msg" class="gf-msg"></div>`;
  }

  function changePwCardHTML() {
    return `
      <div class="gf-card-title">${AL('Set a new password', 'Постави нова лозинка')}</div>
      <div class="gf-card-sub">${AL('First login — choose a password (min 8 characters).',
                                     'Прва пријава — изберете лозинка (мин. 8 карактери).')}</div>
      <input id="wwf-np" class="gf-in" type="password" placeholder="${AL('New password', 'Нова лозинка')}" autocomplete="new-password">
      <input id="wwf-np2" class="gf-in" type="password" placeholder="${AL('Confirm password', 'Потврди лозинка')}" autocomplete="new-password"
             onkeydown="if(event.key==='Enter')GF.WWF.doChangePw()">
      <button class="gf-btn" onclick="GF.WWF.doChangePw()">${AL('Set password &amp; continue', 'Постави лозинка и продолжи')}</button>
      <div id="wwf-login-msg" class="gf-msg"></div>`;
  }

  // The demo button is gated on the backend: it only appears where the server
  // reports demo_enabled (test stacks), and stays hidden in production until a
  // time-matched demo is switched on there. Rendered hidden, then revealed once
  // /health confirms — inline display:none beats the stylesheet without any
  // !important, so there is never a flash of the button on prod.
  let _demoOk = null;   // null = not probed yet; true/false once /health answers
  function revealDemoIfEnabled(el) {
    const show = () => { const b = el.querySelector('.gf-demo-float'); if (b && _demoOk) b.style.display = ''; };
    if (_demoOk !== null) return show();
    fetch('/health', { cache: 'no-store' })
      .then((r) => r.json())
      .then((j) => { _demoOk = !!j.demo_enabled; })
      .catch(() => { _demoOk = false; })
      .then(show);
  }

  function buildEntry(el, cardHTML, withDemo) {
    el.className = 'gf-entry-root';
    // The demo entry lives OUTSIDE the sign-in card — a fixed pill pinned to the
    // top-right corner, never affected by the card/leaf layout (which is what
    // buried it before). Hidden until the backend confirms demo is enabled.
    const demoBtn = withDemo ? `
        <button class="gf-demo-float" style="display:none" onclick="GF.DEMO.enter()"
                title="Sample data — separate from the real system · Примерни податоци"
                aria-label="Try the demo">🌿 <span>Try the demo · Демо</span></button>` : '';
    el.innerHTML = `
      <div class="gf-entry" id="gf-entry">
        ${demoBtn}
        <div class="gf-atmos"></div>
        <div class="gf-stage" id="gf-leaf-stage" role="button" tabindex="0" aria-label="GrowFlow leaf — tap to enter"></div>
        <div class="gf-shadow" id="gf-leaf-shadow"></div>
        <div class="gf-lockup" id="gf-lockup">
          <div class="gf-name">Grow<span class="gf-flow">Flow</span></div>
          <div class="gf-wordmark" aria-label="Purely Plant"></div>
          <div class="gf-tagline">The Future of Cannabis</div>
          <div class="gf-enter"><b>Tap the leaf</b> to enter</div>
        </div>
        <div class="gf-lw" id="gf-lw">
          <div class="gf-card" id="gf-entry-card">${cardHTML}</div>
        </div>
        <div class="gf-back" id="gf-back" role="button" tabindex="0">&lsaquo; back to leaf</div>
      </div>`;
    const back = $('gf-back');
    if (back) { back.onclick = backToLeaf; back.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); backToLeaf(); } }; }
    const stage = $('gf-leaf-stage');
    if (stage) stage.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); reveal(); } });
    if (withDemo) revealDemoIfEnabled(el);
  }

  function mountLeaf() {
    const stage = $('gf-leaf-stage');
    if (!stage) return;
    if (leaf && leaf.destroy) { try { leaf.destroy(); } catch (e) {} leaf = null; }
    stage.className = 'gf-stage';
    stage.innerHTML = '';
    const inst = GF.leaf3d && GF.leaf3d.mount(stage, {
      size: leafSize(),
      shadowEl: $('gf-leaf-shadow'),
      objUrl: 'assets/pp-leaf-3d.obj',
      // The splash showcases a random DARK skin (pickEntrySkin) — the hero leaf
      // takes that skin's palette. Confined to dark skins so it always glows
      // right against the dark stage.
      theme: entrySkin,
      onEnter: reveal,
      onError: cssFallbackLeaf,
    });
    if (inst) leaf = inst; else cssFallbackLeaf();
  }

  // WebGL/three.js unavailable → reuse the app's existing animated CSS leaf so
  // the splash still works everywhere (and a click still reveals the card).
  function cssFallbackLeaf() {
    const stage = $('gf-leaf-stage');
    if (!stage) return;
    stage.classList.add('gf-stage--css');
    stage.innerHTML = '<span class="leaf-stage" data-mode="calm" style="width:160px;height:186px"><span class="leaf-3d"><span class="leaf-float"><span class="pp-leaf-anim pp-leaf-anim--xl"></span></span></span></span>';
    stage.addEventListener('click', reveal);
    if (GF.leafFX && GF.leafFX.bind) { const s = stage.querySelector('.leaf-stage'); if (s) GF.leafFX.bind(s); }
  }

  // After the card slides in, guarantee the WHOLE card — including the "Try the
  // demo" button at its foot — is inside the viewport. The reveal shrinks the
  // 3D leaf via a CSS transform (.gf-entry.entered .gf-stage), but in some
  // browsers (notably Firefox) the WebGL canvas does not give back its layout
  // box the same way, so the leaf+card group can be taller than the viewport
  // and push the demo button below the fold. `.gf-entry` is the overflow-y:auto
  // scroll container, so nudging its scrollTop brings the clipped card fully
  // into view — a browser-agnostic safety net independent of the leaf shrink.
  function ensureCardInView() {
    const entry = $('gf-entry');
    const card = $('gf-entry-card');
    if (!entry || !card) return;
    try {
      let overshoot = card.getBoundingClientRect().bottom - window.innerHeight + 14; // 14px breathing room
      if (overshoot <= 0) { entry.classList.remove('gf-overflow'); return; }
      // The group is taller than the viewport. Centering (default) leaves the
      // top overflow unreachable and caps scrollTop, so the card's foot stays
      // clipped. Top-align first (all overflow moves below), then scroll the
      // whole card — including the demo button — into view.
      entry.classList.add('gf-overflow');
      // Recompute after reflow so we scroll by the right amount.
      overshoot = card.getBoundingClientRect().bottom - window.innerHeight + 14;
      if (overshoot > 0) entry.scrollTop += overshoot;
    } catch (e) {}
  }

  function reveal() {
    if (opened) return;
    opened = true;
    const entry = $('gf-entry'); if (entry) entry.classList.add('entered');
    setTimeout(() => {
      const lw = $('gf-lw'); if (lw) lw.classList.add('show');
      const u = $('wwf-u') || $('wwf-np'); if (u) setTimeout(() => { try { u.focus(); } catch (e) {} }, 260);
      // Card animates in over ~.55s; run the guard after it settles.
      setTimeout(ensureCardInView, 620);
    }, 540);
  }

  function backToLeaf() {
    opened = false;
    const entry = $('gf-entry'); if (entry) { entry.classList.remove('entered'); entry.classList.remove('gf-overflow'); entry.scrollTop = 0; }
    const lw = $('gf-lw'); if (lw) lw.classList.remove('show');
  }

  // Reveal the card immediately (no leaf-tap gate) — used post-auth for the
  // forced password-change screen and to surface an error message on re-login.
  function revealNow() {
    opened = true;
    const entry = $('gf-entry'); if (entry) entry.classList.add('entered');
    const lw = $('gf-lw'); if (lw) lw.classList.add('show');
    setTimeout(ensureCardInView, 60);
  }

  // Re-assert the guard on resize/orientation change while the card is open —
  // e.g. rotating a phone or opening the keyboard changes the fold.
  window.addEventListener('resize', () => { if (opened) ensureCardInView(); });

  function ensureRoot() {
    let el = $('wwf-login');
    if (!el) { el = document.createElement('div'); el.id = 'wwf-login'; document.body.appendChild(el); }
    return el;
  }

  // ── Overrides ──────────────────────────────────────────────────────
  GF.WWF.showLogin = (msg) => {
    const el = ensureRoot();
    el.style.display = 'block';
    buildEntry(el, loginCardHTML(), true);   // rebuild fresh so re-login starts at the splash; floating demo button
    opened = false;
    pickEntrySkin();                   // a fresh random skin every time the splash appears
    mountLeaf();
    const m = $('wwf-login-msg'); if (m) m.textContent = msg || '';
    // If we're here because of an error (bad token / session expiry), skip the
    // splash gate and show the card + message straight away.
    if (msg) revealNow();
    else setTimeout(() => { const u = $('wwf-u'); /* focus happens after reveal */ }, 0);
  };

  GF.WWF.showChangePw = (currentPw) => {
    GF.WWF._curPw = currentPw || '';
    let el = $('wwf-login');
    if (!el || !$('gf-entry-card')) { el = ensureRoot(); el.style.display = 'block'; buildEntry(el, changePwCardHTML()); pickEntrySkin(); mountLeaf(); }
    else { const card = $('gf-entry-card'); if (card) card.innerHTML = changePwCardHTML(); }
    revealNow();
    setTimeout(() => { const n = $('wwf-np'); if (n) try { n.focus(); } catch (e) {} }, 80);
  };

  // Free the WebGL leaf once we leave the entry screen for the app. Both success
  // paths (normal login and forced password change) funnel through loadAndRender.
  if (typeof GF.WWF.loadAndRender === 'function') {
    const _origLoadAndRender = GF.WWF.loadAndRender;
    GF.WWF.loadAndRender = function () {
      if (leaf && leaf.destroy) { try { leaf.destroy(); } catch (e) {} leaf = null; }
      // Entering the app: drop the splash's showcase skin and apply the user's
      // OWN saved skin (gf_theme). For the demo, gf_theme already holds the
      // demo's per-start random skin, so this restores that instead — either
      // way the logged-in app reflects the remembered choice, not the splash's
      // random one.
      try {
        const saved = localStorage.getItem('gf_theme') || 'mass-weed';
        // A valid saved skin is re-applied without touching storage. An invalid
        // one (retired/corrupt/legacy id the pre-paint boot applied verbatim,
        // matching no CSS) is HEALED: setTheme falls back to mass-weed and — by
        // dropping noPersist — rewrites gf_theme, so the unstyled-flash can't
        // recur on every load.
        const valid = GF.themeById && GF.themeById(saved);
        if (GF.setTheme && (!valid || document.documentElement.dataset.theme !== saved)) {
          GF.setTheme(saved, { silent: true, noPersist: !!valid });
        }
      } catch (e) {}
      return _origLoadAndRender.apply(this, arguments);
    };
  }
})();
