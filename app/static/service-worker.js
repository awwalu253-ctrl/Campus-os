/* Campus OS — Phase 1 service worker
   Rules:
   - Precache the app shell + offline page.
   - Static assets: stale-while-revalidate.
   - HTML: network-first, fall back to cache, fall back to /offline.
   - API GETs: network-first, short cache. Never cache auth or mutations.
   - Never fabricate live data. */

const VERSION = 'campus-os-v12';
const STATIC_CACHE = `${VERSION}-static`;
const PAGES_CACHE = `${VERSION}-pages`;
const OFFLINE_URL = '/offline';

const PRECACHE = [
  '/',
  '/offline',
  '/static/css/tokens.css',
  '/static/css/base.css',
  '/static/css/components.css',
  '/static/css/layout.css',
  '/static/js/app.js',
  '/static/js/pwa/install.js',
  '/static/js/pwa/splash.js',
  '/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

function isApiGet(url) {
  return url.pathname.startsWith('/api/') && !url.pathname.startsWith('/api/auth');
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // never cache mutations
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // HTML
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(PAGES_CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then((r) => r || caches.match(OFFLINE_URL)))
    );
    return;
  }

  // API GETs
  if (isApiGet(url)) {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(PAGES_CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req))
    );
    return;
  }

  // Static assets
  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(STATIC_CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => cached);
      return cached || fetchPromise;
    })
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});