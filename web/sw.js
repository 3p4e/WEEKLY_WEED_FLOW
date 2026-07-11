/* sw.js — WWF service worker. Deliberately SIMPLE:
   - app shell (this static file list) → cache-first, keyed by VERSION so
     bumping the version on deploy invalidates every cached shell file;
   - API paths → network-first (never served stale; falls back to cache only
     if a response happened to be cached, which for API paths it never is);
   - everything else same-origin GET → network, best-effort cache fallback.
   Bump VERSION whenever any shell file changes. */
const VERSION = 'wwf-shell-v3.9.0';

const SHELL = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/gf/app.css', '/gf/skins.css', '/gf/brand.css', '/gf/mobile.css', '/gf/views.css', '/gf/leaf-fx.css', '/gf/entry.css',
  '/gf/boot-guard.js', '/gf/data.js', '/gf/core.js', '/gf/render.js', '/gf/voice.js',
  '/gf/export.js', '/gf/views.js', '/gf/leaf-fx.js', '/gf/assistant.js', '/gf/main.js',
  '/gf/api.js', '/gf/demo.js', '/gf/integrate.js', '/gf/audit-view.js', '/gf/collab.js', '/gf/worklog.js',
  '/gf/report-view.js', '/gf/document-view.js', '/gf/import-view.js', '/gf/intake-view.js', '/gf/tweaks-vanilla.js',
  // 3D-leaf splash/login entry (self-hosted three.js + mesh)
  '/gf/vendor/three.min.js', '/gf/leaf3d.js', '/gf/entry.js', '/assets/pp-leaf-3d.obj',
  '/assets/pp-leaf.png', '/assets/pp-logo.png', '/assets/pp-logo-white.png', '/assets/pp-wordmark.png',
  '/assets/wwf-icon-192.png', '/assets/wwf-icon-512.png',
];

// Paths nginx proxies to the backend — never cache-first, data must be live.
const API_RE = /^\/(auth|departments|weeks|tasks|sessions|capture|intake|ai|audit|reports|health)(\/|$|\?)/;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
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
