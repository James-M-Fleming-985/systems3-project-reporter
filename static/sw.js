// Systems³ Project Reporter — Service Worker
// Cache-first for static assets, network-first for HTML/API

const CACHE_VERSION = 'systems3-v1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;

// Static assets to pre-cache on install
const PRECACHE_URLS = [
  '/static/offline.html',
  '/static/favicon.png',
  '/static/icon-192.png',
  '/static/apple-touch-icon.png',
  '/favicon.ico',
];

// CDN assets to cache on first use
const CDN_HOSTS = [
  'cdn.tailwindcss.com',
  'cdn.jsdelivr.net',
  'cdn.plot.ly',
  'fonts.googleapis.com',
  'fonts.gstatic.com',
];

// Install: pre-cache essential static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== RUNTIME_CACHE)
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch: routing strategy per request type
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (form submissions, API writes)
  if (request.method !== 'GET') return;

  // Strategy 1: Cache-first for own static assets (/static/*)
  if (url.pathname.startsWith('/static/') || url.pathname === '/favicon.ico') {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // Strategy 2: Cache-first for CDN assets (Tailwind, FullCalendar, Plotly, fonts)
  if (CDN_HOSTS.some((host) => url.hostname === host)) {
    event.respondWith(cacheFirst(request, RUNTIME_CACHE));
    return;
  }

  // Strategy 3: Network-first for HTML pages and API calls
  if (request.headers.get('Accept')?.includes('text/html') || url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Default: network with cache fallback
  event.respondWith(networkFirst(request));
});

// Cache-first: serve from cache, fall back to network and cache the response
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // If both cache and network fail, return offline page for navigation
    return caches.match('/static/offline.html');
  }
}

// Network-first: try network, fall back to cache, then offline page
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    // Cache successful HTML responses for offline fallback
    if (response.ok && request.headers.get('Accept')?.includes('text/html')) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Network failed — try cache
    const cached = await caches.match(request);
    if (cached) return cached;

    // Last resort: offline page for navigation requests
    if (request.headers.get('Accept')?.includes('text/html')) {
      return caches.match('/static/offline.html');
    }

    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}
