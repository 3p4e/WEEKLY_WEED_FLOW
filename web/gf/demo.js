/* demo.js — LIVE DEMO MODE: a real session against the real backend.
   Entered from the login screen ("Try the demo"). POST /demo/start wipes and
   re-seeds a dedicated demo organization server-side (org_id RLS isolates it
   from every real tenant exactly like real tenants are isolated from each
   other) and returns a short-lived token for the sample cast's ADMIN — so the
   demo always shows the app's REAL, current feature set: every view, every
   module, fully interactive. Changes are real rows in the demo org and are
   wiped on exit and again on the next start.

   Same rules as the previous (in-memory) demo instalment:
     · one narrative — Arrakis / Spice Production ("the spice must flow");
     · a RANDOM skin is applied on every start (the visitor's own theme is
       remembered and restored on exit);
     · nothing is saved; never connected to the production database (the /demo
       endpoints only exist where DEMO_ENABLED is set — the test stack).

   The old client-side mock router this file used to contain is retired — no
   request interception; GF.API talks to the backend normally. */
window.GF = window.GF || {};

GF.DEMO = (function () {
  const KEY = 'wwf_demo';                       // sessionStorage — this tab is a demo
  const PREV_THEME_KEY = 'wwf_demo_prev_theme'; // localStorage — visitor's own skin
  const CAST = 'dune';                          // one narrative: Arrakis / Spice Production
  const CAST_LABEL = { en: 'Arrakis · Spice Production', mk: 'Аракис · Производство на зачин' };
  const active = () => { try { return sessionStorage.getItem(KEY) === '1'; } catch (e) { return false; } };

  async function enter() {
    const btn = document.querySelector('.gf-demo-float');
    if (btn) { btn.disabled = true; btn.style.opacity = '.6'; }
    let data;
    try {
      const r = await fetch('/demo/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cast: CAST }),
      });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || ('HTTP ' + r.status));
      data = await r.json();
    } catch (e) {
      if (btn) { btn.disabled = false; btn.style.opacity = ''; }
      const mk = (GF.state && GF.state.lang) === 'mk';
      const msg = mk ? 'Демото не е достапно во моментов: ' : 'The demo is unavailable right now: ';
      if (GF.toast) GF.toast(msg + e.message, 'error'); else alert(msg + e.message);
      return;
    }
    try {
      // Random skin per start (always different from the one on screen);
      // the visitor's own theme is remembered once and restored on exit.
      if (GF.THEMES && GF.THEMES.length) {
        const cur = localStorage.getItem('gf_theme') || 'mass-weed';
        if (localStorage.getItem(PREV_THEME_KEY) === null) localStorage.setItem(PREV_THEME_KEY, cur);
        const pool = GF.THEMES.filter(t => t.id !== cur);
        const pick = pool[Math.floor(Math.random() * pool.length)] || GF.THEMES[0];
        localStorage.setItem('gf_theme', pick.id);   // the <head> boot script applies it after reload
      }
      sessionStorage.setItem(KEY, '1');
      sessionStorage.setItem('wwf_token', data.access_token);
      sessionStorage.setItem('wwf_user', JSON.stringify(data.user));
      sessionStorage.setItem('wwf_show_module_picker', '1');
    } catch (e) {}
    location.reload();
  }

  function exit() {
    // Best-effort server wipe — the next visitor's start re-seeds regardless.
    try {
      const tok = sessionStorage.getItem('wwf_token');
      if (tok) fetch('/demo/exit', { method: 'POST', headers: { Authorization: 'Bearer ' + tok }, keepalive: true }).catch(() => {});
    } catch (e) {}
    try {
      sessionStorage.removeItem(KEY); sessionStorage.removeItem('wwf_token'); sessionStorage.removeItem('wwf_user');
      restoreTheme();
    } catch (e) {}
    location.reload();
  }

  function restoreTheme() {
    let prev = localStorage.getItem(PREV_THEME_KEY);
    if (prev === null) return;
    // Exclusive Mass Weed: a pre-retirement id saved as "previous" heals the
    // same way the boot script heals gf_theme, or the demo exit would paint a
    // retired shell until the next reload.
    if (GF.healTheme) prev = GF.healTheme(prev);
    localStorage.setItem('gf_theme', prev);
    localStorage.removeItem(PREV_THEME_KEY);
    const root = document.documentElement;
    root.dataset.theme = prev;
    root.removeAttribute('data-skin-carbon');
  }

  function banner() {
    if (document.getElementById('gf-demo-banner')) return;
    const b = document.createElement('div');
    b.id = 'gf-demo-banner';
    const mk = (GF.state && GF.state.lang) === 'mk';
    const label = CAST_LABEL;
    b.innerHTML = `<span class="gfdb-dot"></span><b>${mk ? 'ДЕМО' : 'DEMO'} · ${mk ? label.mk : label.en}</b>
      <span>${mk ? 'примерни податоци · изгледот се менува при секој старт · промените не се зачувуваат · не е поврзано со продукциската база'
                 : 'sample data · skin rotates every start · changes are not saved · not connected to the production database'}</span>
      <button onclick="GF.DEMO.exit()">${mk ? 'Излези од демо' : 'Exit demo'}</button>`;
    document.body.appendChild(b);
    document.body.classList.add('demo-on');
  }

  function install() {
    if (active()) {
      let tok = null;
      try { tok = sessionStorage.getItem('wwf_token'); } catch (e) {}
      if (!tok) {
        // The demo token expired / was cleared by a 401 — the tab is no longer
        // a demo session. Drop the flag and give the visitor their theme back.
        try { sessionStorage.removeItem(KEY); } catch (e) {}
        try { restoreTheme(); } catch (e) {}
        return;
      }
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', banner);
      else banner();
    } else {
      // A demo tab that was closed (not exited) leaves the random skin behind —
      // heal it on the next non-demo load.
      try { restoreTheme(); } catch (e) {}
    }
  }
  install();

  return { active, enter, exit };
})();
