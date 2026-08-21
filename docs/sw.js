/* Cache-first for map tiles and app shell so the map works with no signal. */
const VERSION = 'forest-v1';
const SHELL = [
  './', './index.html', './leaflet.js', './leaflet.css',
  './manifest.webmanifest', './icon-192.png', './icon-512.png', './icon-180.png'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(VERSION)
      .then(c => Promise.allSettled(SHELL.map(u => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Same-origin tiles and shell: cache first, then network, then cache again.
  if (url.origin === location.origin) {
    e.respondWith(
      caches.match(req, {cacheName: 'forest-tiles'})
        .then(tile => tile || caches.match(req))
        .then(hit => hit || fetch(req).then(res => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(VERSION).then(c => c.put(req, copy));
        }
        return res;
      }).catch(() => hit))
    );
    return;
  }

  // Third-party (the OSM street basemap): network first, fall back to cache.
  e.respondWith(
    fetch(req).then(res => {
      if (res && res.status === 200) {
        const copy = res.clone();
        caches.open(VERSION).then(c => c.put(req, copy));
      }
      return res;
    }).catch(() => caches.match(req))
  );
});
