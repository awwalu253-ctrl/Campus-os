/* Campus OS — Phase 1 service worker
   Rules:
   - Precache the app shell + offline page.
   - Static assets: stale-while-revalidate.
   - HTML: network-first, fall back to cache, fall back to /offline.
   - API GETs: network-first, short cache. Never cache auth or mutations.
   - Never cache per-user endpoints such as notifications.
   - Never fabricate live data. */

const VERSION = 'campus-os-v16';
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

// API GETs that are safe to cache: campus-scoped data that is the same
// for every user on a given campus within a short window.
//
// IMPORTANT: any future per-user API endpoint MUST be added to
// isUncacheableApiGet below. Caching per-user responses leaks data
// between sessions on a shared device.
function isCacheableApiGet(url) {
  if (!url.pathname.startsWith('/api/')) return false;
  if (url.pathname.startsWith('/api/auth')) return false;
  if (isUncacheableApiGet(url)) return false;
  return true;
}

// API GETs that must never be cached. Network-only, no cache fallback.
// If the network is down, the request fails and the client handles it.
function isUncacheableApiGet(url) {
  // Notifications are per-user and private.
  if (url.pathname.startsWith('/api/v1/notifications')) return true;
  return false;
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

  // Uncacheable API GETs — network-only, no fallback. Covers per-user
  // endpoints such as notifications.
  if (isUncacheableApiGet(url)) {
    event.respondWith(fetch(req));
    return;
  }

  // Cacheable API GETs — network-first with cache fallback.
  if (isCacheableApiGet(url)) {
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

// ═══════════════════════════════════════════════════════
// Web Push
// ═══════════════════════════════════════════════════════

self.addEventListener('push', (event) => {
  // Payload is JSON: {title, body, url, tag}
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (err) {
      data = { title: 'Campus OS', body: event.data.text() || '' };
    }
  }

  const title = data.title || 'Campus OS';
  const options = {
    body: data.body || '',
    tag: data.tag || undefined,
    data: { url: data.url || '/' },
    badge: '/static/icons/pwa-192.png',
    icon: '/static/icons/pwa-192.png',
    requireInteraction: false,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const targetUrl = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // If a Campus OS window is already open, focus it and navigate.
      for (const client of clientList) {
        if (client.url.startsWith(self.location.origin) && 'focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      // Otherwise open a new one.
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })
  );
});