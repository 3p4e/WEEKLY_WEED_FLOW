/* sw.js — WWF service worker. Deliberately SIMPLE:
   - app shell (this static file list) → cache-first, keyed by VERSION so
     bumping the version on deploy invalidates every cached shell file;
   - API paths → network-first (never served stale; falls back to cache only
     if a response happened to be cached, which for API paths it never is);
   - everything else same-origin GET → network, best-effort cache fallback.
   Bump VERSION whenever any shell file changes. */
const VERSION = 'wwf-shell-v3.99.0';

const SHELL = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/gf/app.css', '/gf/skins.css', '/gf/brand.css', '/gf/mobile.css', '/gf/views.css', '/gf/leaf-fx.css', '/gf/entry.css', '/gf/mass-weed.css',
  '/gf/boot-guard.js', '/gf/data.js', '/gf/core.js', '/gf/render.js', '/gf/voice.js',
  '/gf/export.js', '/gf/views.js', '/gf/cmdk.js', '/gf/calendar-view.js', '/gf/workload-view.js', '/gf/leaf-fx.js', '/gf/assistant.js', '/gf/main.js',
  '/gf/api.js', '/gf/demo.js', '/gf/integrate.js', '/gf/audit-view.js', '/gf/collab.js', '/gf/task-extras.js', '/gf/worklog.js', '/gf/task-detail-view.js',
  '/gf/report-view.js', '/gf/document-view.js', '/gf/execreport-view.js', '/gf/import-view.js', '/gf/intake-view.js', '/gf/search-view.js',
  '/gf/modules.js', '/gf/dept-templates.js', '/gf/depthome-view.js', '/gf/notifications-view.js', '/gf/facility-view.js', '/gf/cultivation-view.js', '/gf/propagation-view.js', '/gf/harvest-view.js', '/gf/irrigation-view.js', '/gf/decon-view.js', '/gf/waste-view.js', '/gf/approvals-view.js', '/gf/myday-view.js', '/gf/analytics-view.js', '/gf/auditprep-view.js', '/gf/qmsregistry-view.js', '/gf/qmsknow-view.js', '/gf/qmsstudio-view.js', '/gf/qcspec-view.js', '/gf/qcpotency-view.js', '/gf/qclab-view.js', '/gf/qcregister-view.js', '/gf/qcgenealogy-view.js', '/gf/qcsample-view.js', '/gf/qccoa-view.js', '/gf/qcoos-view.js', '/gf/qcecoa-view.js', '/gf/qccustody-view.js', '/gf/qcleaves-view.js', '/gf/chooser.js', '/gf/datepicker.js', '/gf/codefield.js', '/gf/tweaks-vanilla.js',
  // 3D-leaf splash/login entry (self-hosted three.js + mesh)
  '/gf/vendor/three.min.js', '/gf/leaf3d.js', '/gf/entry.js', '/assets/pp-leaf-3d.obj',
  '/assets/pp-leaf.png', '/assets/pp-logo.png', '/assets/pp-logo-white.png', '/assets/pp-wordmark.png',
  '/assets/wwf-icon-192.png', '/assets/wwf-icon-512.png',
];

// Paths nginx proxies to the backend — never cache-first, data must be live.
//
// This list MUST cover every prefix in nginx.conf's proxy location blocks. A
// missing prefix does NOT 404 — it falls through to the cache-first branch
// below, so API responses get stored under VERSION and replayed stale until the
// next deploy. `decon` was missing here while live in production for exactly
// that reason, so tests/frontend/sw-api-routes.test.js now compares the two
// lists and fails on any drift.
const API_RE = /^\/(auth|departments|weeks|tasks|sessions|capture|intake|ai|audit|reports|notifications|activity|handoffs|facility|cultivation|decon|waste|approvals|qms|qc|demo|health)(\/|$|\?)/;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      // A prior wwf-shell-v* cache key means this activate is REPLACING an
      // older worker (a real deploy) — claim clients so the new shell takes
      // over instantly (index.html's controllerchange listener then reloads
      // the one open tab, deliberately, per its own comment). On the very
      // first-ever install there is no prior key: there is nothing to
      // "update" from, so skip claim() — otherwise a brand-new visitor's tab
      // reloads itself once for no reason the instant it finishes loading.
      const isUpdate = keys.some((k) => k !== VERSION);
      return Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))
        .then(() => { if (isUpdate) return self.clients.claim(); });
    })
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (API_RE.test(url.pathname)) {
    // network-first: live data or nothing (API responses are never pre-cached)
    e.respondWith(fetch(req).catch(() => caches.match(req)));
    return;
  }

  // app shell + other static files: cache-first, fill the cache on miss
  e.respondWith(
    caches.match(req, { ignoreSearch: url.pathname === '/' }).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(req, copy));
      }
      return res;
    }))
  );
});
