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

  const $ = (id) => (window.GF && GF.$ ? GF.$(id) : document.getElementById(id));

  function loginCardHTML() {
    return `
      <div class="gf-card-title">Weekly Weed Flow</div>
      <div class="gf-card-sub">Sign in to continue</div>
      <input id="wwf-u" class="gf-in" placeholder="Username" autocomplete="username" autocapitalize="none" spellcheck="false">
      <input id="wwf-p" class="gf-in" type="password" placeholder="Password" autocomplete="current-password"
             onkeydown="if(event.key==='Enter')GF.WWF.doLogin()">
      <button class="gf-btn" onclick="GF.WWF.doLogin()">Sign in</button>
      <div id="wwf-login-msg" class="gf-msg"></div>`;
  }

  function changePwCardHTML() {
    return `
      <div class="gf-card-title">Set a new password</div>
      <div class="gf-card-sub">First login — choose a password (min 8 characters).</div>
      <input id="wwf-np" class="gf-in" type="password" placeholder="New password" autocomplete="new-password">
      <input id="wwf-np2" class="gf-in" type="password" placeholder="Confirm password" autocomplete="new-password"
             onkeydown="if(event.key==='Enter')GF.WWF.doChangePw()">
      <button class="gf-btn" onclick="GF.WWF.doChangePw()">Set password &amp; continue</button>
      <div id="wwf-login-msg" class="gf-msg"></div>`;
  }

  function buildEntry(el, cardHTML) {
    el.className = 'gf-entry-root';
    el.innerHTML = `
      <div class="gf-entry" id="gf-entry">
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

  function reveal() {
    if (opened) return;
    opened = true;
    const entry = $('gf-entry'); if (entry) entry.classList.add('entered');
    setTimeout(() => {
      const lw = $('gf-lw'); if (lw) lw.classList.add('show');
      const u = $('wwf-u') || $('wwf-np'); if (u) setTimeout(() => { try { u.focus(); } catch (e) {} }, 260);
    }, 540);
  }

  function backToLeaf() {
    opened = false;
    const entry = $('gf-entry'); if (entry) entry.classList.remove('entered');
    const lw = $('gf-lw'); if (lw) lw.classList.remove('show');
  }

  // Reveal the card immediately (no leaf-tap gate) — used post-auth for the
  // forced password-change screen and to surface an error message on re-login.
  function revealNow() {
    opened = true;
    const entry = $('gf-entry'); if (entry) entry.classList.add('entered');
    const lw = $('gf-lw'); if (lw) lw.classList.add('show');
  }

  function ensureRoot() {
    let el = $('wwf-login');
    if (!el) { el = document.createElement('div'); el.id = 'wwf-login'; document.body.appendChild(el); }
    return el;
  }

  // ── Overrides ──────────────────────────────────────────────────────
  GF.WWF.showLogin = (msg) => {
    const el = ensureRoot();
    el.style.display = 'block';
    buildEntry(el, loginCardHTML());   // rebuild fresh so re-login starts at the splash
    opened = false;
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
    if (!el || !$('gf-entry-card')) { el = ensureRoot(); el.style.display = 'block'; buildEntry(el, changePwCardHTML()); mountLeaf(); }
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
      return _origLoadAndRender.apply(this, arguments);
    };
  }
})();
