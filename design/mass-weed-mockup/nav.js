/* MASS WEED — persistent left-rail navigation (shared component)
   Drop into any app page:  <script src="nav.js"></script>
   Renders a grouped, collapsible rail; hides the legacy .mw-nav; sets active
   state from the current filename. Collapse state persists in localStorage. */
(function () {
  // ---- domain accent colors ----
  var ACC = {
    ops:  '#5ec8f0',   // Operations — cyan (all roles)
    mgr:  '#f0b95e',   // Manager    — gold (managers only)
    sys:  '#7fa3bd'    // System     — dim (all roles)
  };

  // ---- icon set (unified 24-grid, 1.6 stroke — P7) ----
  var I = {
    dash:   '<path d="M4 13h6V4H4zM14 20h6V4h-6zM4 20h6v-5H4z"/>',
    day:    '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
    board:  '<rect x="3" y="4" width="5" height="16" rx="1"/><rect x="10" y="4" width="5" height="11" rx="1"/><rect x="17" y="4" width="4" height="16" rx="1"/>',
    workload:'<path d="M3 20V10M9 20V4M15 20v-6M21 20V8"/>',
    calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/>',
    climate:'<path d="M12 3c-1 5-5 7-5 11a5 5 0 0 0 10 0c0-4-4-6-5-11z"/>',
    genetics:'<path d="M7 3c0 6 10 6 10 12M17 3c0 6-10 6-10 12M7 3v18M17 3v18"/><path d="M8 7h8M8 17h8"/>',
    nutrients:'<path d="M6 3h12l-2 4v6a4 4 0 0 1-8 0V7z"/><path d="M9 13h6"/>',
    harvest:'<path d="M4 20c6-2 8-8 8-14M12 6c0 6 2 12 8 14M12 6c-3 0-5 2-5 4M12 6c3 0 5 2 5 4"/>',
    cure:   '<path d="M8 3h8M9 3v4l-4 9a4 4 0 0 0 4 5h6a4 4 0 0 0 4-5l-4-9V3"/><path d="M6 14h12"/>',
    batch:  '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 9h16M9 9v11"/>',
    inventory:'<path d="M3 7l9-4 9 4-9 4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>',
    packaging:'<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M4 10h16M10 4v6"/>',
    orders: '<path d="M6 6h15l-2 9H8z"/><path d="M6 6L5 3H2"/><circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/>',
    analytics:'<path d="M4 4v16h16"/><path d="M8 15l3-4 3 3 4-6"/>',
    compliance:'<path d="M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z"/><path d="M9 12l2 2 4-4"/>',
    approvals:'<path d="M9 11l3 3L20 6"/><path d="M20 12v7a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h9"/>',
    reports:'<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 13h6M9 17h6M9 9h2"/>',
    sop:    '<path d="M5 4h10l4 4v12H5z"/><path d="M9 9h6M9 13h6M9 17h4"/><path d="M15 4v4h4"/>',
    vault:  '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="12" cy="12" r="4"/><path d="M12 8v1M12 15v1M8 12h1M15 12h1"/>',
    crew:   '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 6a3 3 0 0 1 0 6M21 20a6 6 0 0 0-4-5.6"/>',
    automations:'<path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/><circle cx="12" cy="12" r="3"/>',
    notifications:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 0 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H1a2 2 0 0 1 0-4h.1A1.6 1.6 0 0 0 4.6 7a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 9 2.6h.1A1.6 1.6 0 0 0 11 1a2 2 0 0 1 4 0v.1A1.6 1.6 0 0 0 17 4.6a1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7h.2a2 2 0 0 1 0 4h-.1A1.6 1.6 0 0 0 19.4 15z"/>',
    signout:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>',
    collapse:'<path d="M15 6l-6 6 6 6"/>',
    home:   '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/>',
    qms:    '<path d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z"/><path d="M9 12l2 2 4-4"/>',
    tree:   '<path d="M5 4v16"/><path d="M5 8h7M5 14h10M5 20h13"/><circle cx="5" cy="4" r="1.4"/>',
    exec:   '<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4"/><path d="M9 13l2 2 4-4"/>',
    role:   '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    facility:'<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M3 10h9M12 3v18M12 14h9M17 14v7"/>'
  };

  // ---- nav structure ----
  // This is a TASK-TRACKER. Departments are a LENS over one shared task system
  // (see Dept Home), not sections with bespoke tooling. Domain-specific pages
  // (Cultivation climate/genetics/nutrients/harvest/cure/batches, Distribution
  // inventory/packaging/orders, deep Compliance sop/vault/compliance) are QMS/
  // LIMS territory — their .html files are kept in the project for future reuse
  // but are intentionally OFF the rail. Reachable directly by URL / Search.
  //
  // Two roles: Operations + System show for everyone; the Manager group (cross-
  // cutting visibility: workload, approvals, reports, analytics) shows only for
  // managers. Toggle role from the rail footer (persisted in localStorage).
  var NAV = [
    { g:'Operations', k:'ops', items:[
      { h:'dashboard.html', t:'Dashboard',  i:'dash' },
      { h:'my-day.html',    t:'My Day',     i:'day' },
      { h:'depthome.html',  t:'Dept Home',  i:'home' },
      { h:'facility.html',  t:'Facility',   i:'facility' },
      { h:'board.html',     t:'Cycle Board',i:'board' },
      { h:'board-tree.html',t:'Theme Board',i:'tree' },
      { h:'calendar.html',  t:'Calendar',   i:'calendar' }
    ]},
    { g:'Manager', k:'mgr', role:'manager', items:[
      { h:'workload.html',   t:'Workload',   i:'workload' },
      { h:'approvals.html',  t:'Approvals',  i:'approvals' },
      { h:'reports.html',    t:'Reports',    i:'reports' },
      { h:'execreport.html', t:'Exec Report',i:'exec' },
      { h:'analytics.html',  t:'Analytics',  i:'analytics' }
    ]},
    { g:'QMS', k:'qms', items:[
      { h:'qms-home.html',      t:'Command Deck', i:'qms' },
      { h:'modules.html',       t:'Modules',      i:'tree' },
      { h:'qc-lab.html',        t:'QC Lab',       i:'facility' },
      { h:'qc-registers.html',  t:'Registers',    i:'tree' },
      { h:'doc-control.html',   t:'Documents',    i:'reports' },
      { h:'supplier-qual.html', t:'Suppliers',    i:'crew' }
    ]},
    { g:'System', k:'sys', items:[
      { h:'team.html',          t:'Crew',        i:'crew' },
      { h:'automations.html',   t:'Automations', i:'automations' },
      { h:'notifications.html', t:'Alerts',      i:'notifications' },
      { h:'search.html',        t:'Search',      i:'search' },
      { h:'settings.html',      t:'Settings',    i:'settings' }
    ]}
  ];

  // detail pages highlight their parent
  var ALIAS = {
    'task-detail.html':'board.html',
    'order-detail.html':'orders.html',
    'rule-builder.html':'automations.html',
    'af-modal.html':'board.html',
    'report-standalone.html':'execreport.html'
  };

  function currentPage() {
    var p = (location.pathname.split('/').pop() || 'dashboard.html').toLowerCase();
    if (!p || p === '') p = 'dashboard.html';
    return ALIAS[p] || p;
  }

  var LS = 'mw-rail-collapsed';
  var LS_ROLE = 'mw-role';
  function currentRole() { return localStorage.getItem(LS_ROLE) === 'operator' ? 'operator' : 'manager'; }
  function rebuildRail() { var r = document.querySelector('.mw-rail'); if (r) r.remove(); build(); }
  function build() {
    if (document.querySelector('.mw-rail')) return;
    var root = document.querySelector('.mw-root') || document.body;
    document.body.classList.add('mw-has-rail');
    if (localStorage.getItem(LS) === '1') document.body.classList.add('mw-rail-collapsed');

    var cur = currentPage();
    var role = currentRole();
    // domain accent for this screen (drives --mw-screen-acc tint)
    var screenAcc = null, screenKey = null;
    NAV.forEach(function (grp) {
      grp.items.forEach(function (it) { if (it.h.toLowerCase() === cur) { screenAcc = ACC[grp.k]; screenKey = grp.k; } });
    });
    if (screenAcc) {
      document.body.style.setProperty('--mw-screen-acc', screenAcc);
      document.body.classList.add('mw-dom-' + screenKey);
    }

    var rail = document.createElement('aside');
    rail.className = 'mw-rail';

    var html = '';
    html += '<div class="mw-rail__brand"><span class="mw-rail__mark"></span><span class="mw-rail__name">Mass Weed</span></div>';
    html += '<div class="mw-rail__scroll">';
    NAV.forEach(function (grp) {
      if (grp.role === 'manager' && role !== 'manager') return;
      var acc = ACC[grp.k];
      html += '<div class="mw-rail__group" style="--mw-grp:' + acc + '">' + grp.g + '</div>';
      grp.items.forEach(function (it) {
        var active = (it.h.toLowerCase() === cur) ? ' is-active' : '';
        html += '<a href="' + it.h + '" class="mw-rail__item' + active + '" style="--mw-acc:' + acc + '">' +
                  '<svg viewBox="0 0 24 24">' + (I[it.i] || '') + '</svg>' +
                  '<span class="lbl">' + it.t + '</span>' +
                  '<span class="tip">' + it.t + '</span>' +
                '</a>';
      });
    });
    html += '</div>';
    // footer
    html += '<div class="mw-rail__foot">';
    html += '<button class="mw-rail__ctl mw-rail__roletgl" type="button"><svg viewBox="0 0 24 24">' + I.role + '</svg><span class="lbl">' + (role === 'manager' ? 'Manager' : 'Operator') + ' view</span><span class="kbd">' + (role === 'manager' ? 'MGR' : 'OP') + '</span></button>';
    html += '<button class="mw-rail__ctl" data-cmdk type="button"><svg viewBox="0 0 24 24">' + I.search + '</svg><span class="lbl">Command</span><span class="kbd">⌘K</span></button>';
    html += '<a href="login.html" class="mw-rail__ctl"><svg viewBox="0 0 24 24">' + I.signout + '</svg><span class="lbl">Sign Out</span></a>';
    html += '<button class="mw-rail__ctl mw-rail__toggle" type="button"><svg viewBox="0 0 24 24">' + I.collapse + '</svg><span class="lbl">Collapse</span></button>';
    html += '</div>';

    rail.innerHTML = html;
    root.insertBefore(rail, root.firstChild);

    // toggle collapse
    rail.querySelector('.mw-rail__toggle').addEventListener('click', function () {
      var c = document.body.classList.toggle('mw-rail-collapsed');
      localStorage.setItem(LS, c ? '1' : '0');
    });
    // command palette hook (cmdk.js listens for ⌘K; trigger via synthetic key)
    var cmd = rail.querySelector('[data-cmdk]');
    if (cmd) cmd.addEventListener('click', function () {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
    });

    // role toggle — manager ⇄ operator, persisted; rebuilds the rail
    var rt = rail.querySelector('.mw-rail__roletgl');
    if (rt) rt.addEventListener('click', function () {
      localStorage.setItem(LS_ROLE, currentRole() === 'manager' ? 'operator' : 'manager');
      rebuildRail();
    });

    // bring the active item into view within the rail's own scroll region
    var scroll = rail.querySelector('.mw-rail__scroll');
    var act = rail.querySelector('.mw-rail__item.is-active');
    if (scroll && act) {
      var need = act.offsetTop - scroll.clientHeight / 2 + act.offsetHeight / 2;
      if (need > 0) scroll.scrollTop = need;
    }
  }

  // P4: unified entrance animation — sweep every stat-fill up from 0 on load.
  // Runs after build() so page inline scripts have already set target widths.
  function animateStatFills() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var fills = document.querySelectorAll('.mw-stat__fill');
    if (!fills.length) return;
    var targets = [];
    fills.forEach(function (el, i) {
      var w = el.style.width;
      if (!w) return;
      targets.push([el, w]);
      el.style.transitionDelay = (i * 45) + 'ms';
      el.style.width = '0%';
    });
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        targets.forEach(function (t) { t[0].style.width = t[1]; });
      });
    });
  }

  function boot() { build(); animateStatFills(); }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
