/* MASS WEED — shared bilingual (EN|МК) + theme (dark/light) + color-scheme controller.
   Include on any surface:  <script src="mw-i18n.js"></script>
   Applies data-theme + data-lang + data-skin to <html>, persisted in localStorage.
   Wire controls with data-set-lang="en|mk", data-set-theme="dark|light",
   data-toggle-theme, or data-set-skin="alliance|renegade|…".
   The color-scheme dot picker is auto-injected into the first .mw-ctlbar,
   so every page gets it with no per-page markup. ONE identity (the Mass
   Weed HUD), MANY hues. */
(function () {
  var LT = 'mw-theme', LL = 'mw-lang', LS = 'mw-skin';
  var html = document.documentElement;

  var SKINS = [
    ['alliance', '#5ec8f0', 'Alliance', 'Алијанса'],
    ['spectre',  '#3fe0a0', 'Spectre',  'Спектар'],
    ['flux',     '#2fd9d9', 'Flux',     'Флукс'],
    ['paragon',  '#5e7cf0', 'Paragon',  'Парагон'],
    ['omega',    '#c85ef0', 'Omega',    'Омега'],
    ['renegade', '#f0555e', 'Renegade', 'Ренегат'],
    ['citadel',  '#f0c05e', 'Citadel',  'Цитадела']
  ];

  function theme() { return localStorage.getItem(LT) || 'dark'; }
  function lang()  { return localStorage.getItem(LL) || 'en'; }
  function skin()  { return localStorage.getItem(LS) || 'alliance'; }

  function apply() {
    html.setAttribute('data-theme', theme());
    html.setAttribute('data-lang', lang());
    html.setAttribute('data-skin', skin());
  }
  apply(); // run ASAP to avoid flash

  function injectPicker() {
    var bar = document.querySelector('.mw-ctlbar');
    if (!bar || bar.querySelector('.mw-skins')) return;
    var wrap = document.createElement('div');
    wrap.className = 'mw-skins';
    wrap.setAttribute('role', 'group');
    wrap.setAttribute('aria-label', 'Color scheme');
    SKINS.forEach(function (s) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'mw-skins__dot';
      b.setAttribute('data-set-skin', s[0]);
      b.style.background = s[1];
      b.style.setProperty('--sw', s[1]);
      b.title = s[2] + ' · ' + s[3];
      b.setAttribute('aria-label', s[2]);
      wrap.appendChild(b);
    });
    bar.insertBefore(wrap, bar.firstChild);
  }

  function sync() {
    var th = theme(), lg = lang(), sk = skin();
    document.querySelectorAll('[data-set-lang]').forEach(function (b) {
      b.classList.toggle('is-active', b.getAttribute('data-set-lang') === lg);
    });
    document.querySelectorAll('[data-set-theme]').forEach(function (b) {
      b.classList.toggle('is-active', b.getAttribute('data-set-theme') === th);
    });
    document.querySelectorAll('[data-toggle-theme]').forEach(function (b) {
      b.setAttribute('aria-pressed', th === 'light' ? 'true' : 'false');
    });
    document.querySelectorAll('[data-set-skin]').forEach(function (b) {
      b.classList.toggle('is-active', b.getAttribute('data-set-skin') === sk);
    });
  }

  // expose for pages that re-render their control bar
  window.mwSync = function () { injectPicker(); sync(); };

  document.addEventListener('click', function (e) {
    var el;
    if ((el = e.target.closest('[data-set-theme]'))) {
      localStorage.setItem(LT, el.getAttribute('data-set-theme'));
    } else if ((el = e.target.closest('[data-toggle-theme]'))) {
      localStorage.setItem(LT, theme() === 'dark' ? 'light' : 'dark');
    } else if ((el = e.target.closest('[data-set-lang]'))) {
      localStorage.setItem(LL, el.getAttribute('data-set-lang'));
    } else if ((el = e.target.closest('[data-set-skin]'))) {
      localStorage.setItem(LS, el.getAttribute('data-set-skin'));
    } else { return; }
    apply(); sync();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { injectPicker(); sync(); });
  else { injectPicker(); sync(); }
})();
