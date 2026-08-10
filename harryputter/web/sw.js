/* HarryPutter PWA — bump CACHE when shell assets change. */
const CACHE = "harryputter-shell-v34";
const SHELL = ["./manifest.webmanifest", "./pwa-192.png", "./pwa-512.png", "./apple-touch-icon.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const path = url.pathname;
  if (!path.includes("/web/")) return;

  if (path.endsWith("/sw.js")) {
    event.respondWith(fetch(request));
    return;
  }

  // Never cache index.html — auth/session logic must stay fresh.
  if (request.mode === "navigate" || path.endsWith(".html")) {
    event.respondWith(
      fetch(request).catch(() => caches.match("./index.html"))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request).then((response) => {
        if (response.ok) {
          caches.open(CACHE).then((cache) => cache.put(request, response.clone()));
        }
        return response;
      });
      return cached || network;
    })
  );
});
