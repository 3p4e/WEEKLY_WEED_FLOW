/* MASS WEED — shared bilingual (EN|МК) + theme (dark/light) controller.
   Include on any surface:  <script src="mw-i18n.js"></script>
   Reads/writes localStorage; applies data-theme + data-lang to <html>.
   Wire controls with data-set-lang="en|mk", data-set-theme="dark|light",
   or data-toggle-theme. Buttons get .is-active reflecting current state. */
(function () {
  var LT = 'mw-theme', LL = 'mw-lang';
  var html = document.documentElement;

  function theme() { return localStorage.getItem(LT) || 'dark'; }
  function lang()  { return localStorage.getItem(LL) || 'en'; }

  function apply() {
    html.setAttribute('data-theme', theme());
    html.setAttribute('data-lang', lang());
  }
  apply(); // run ASAP to avoid flash

  function sync() {
    var th = theme(), lg = lang();
    document.querySelectorAll('[data-set-lang]').forEach(function (b) {
      b.classList.toggle('is-active', b.getAttribute('data-set-lang') === lg);
    });
    document.querySelectorAll('[data-set-theme]').forEach(function (b) {
      b.classList.toggle('is-active', b.getAttribute('data-set-theme') === th);
    });
    document.querySelectorAll('[data-toggle-theme]').forEach(function (b) {
      b.setAttribute('aria-pressed', th === 'light' ? 'true' : 'false');
    });
  }

  document.addEventListener('click', function (e) {
    var el;
    if ((el = e.target.closest('[data-set-theme]'))) {
      localStorage.setItem(LT, el.getAttribute('data-set-theme'));
    } else if ((el = e.target.closest('[data-toggle-theme]'))) {
      localStorage.setItem(LT, theme() === 'dark' ? 'light' : 'dark');
    } else if ((el = e.target.closest('[data-set-lang]'))) {
      localStorage.setItem(LL, el.getAttribute('data-set-lang'));
    } else { return; }
    apply(); sync();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync);
  else sync();
})();
