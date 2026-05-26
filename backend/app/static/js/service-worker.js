const CACHE_NAME = 'swingmaster-cache-v4';
const ASSETS_TO_CACHE = [
  '/',
  '/manifest.json',
  '/static/offline.html',
  '/static/js/app.js',
  '/static/js/auth.js',
  '/static/js/dashboard.js',
  '/static/js/screener.js',
  '/static/js/watchlist.js',
  '/static/js/journal.js',
  '/static/js/profile.js',
  '/static/js/modals.js',
  '/static/js/lightweight-charts.js'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('Opened cache');
      return cache.addAll(ASSETS_TO_CACHE);
    }).catch((err) => console.error('Cache addAll error:', err))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match('/static/offline.html').then((res) => {
          return res || caches.match('/');
        });
      })
    );
  } else {
    event.respondWith(
      caches.match(event.request).then((response) => {
        return response || fetch(event.request);
      })
    );
  }
});
