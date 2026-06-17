/* CLIT Controller IDE service worker — static app-shell caching ONLY.

   Live state must always come from the backend, so this never caches:
   - /api/*            (chat, tasks, queue, approvals, provider state, logs)
   - /api/events*      (SSE stream + polling fallback)
   - text/event-stream responses
   - WebSocket / PTY traffic (not interceptable by fetch anyway)
   It caches only the built app shell + hashed static assets so the window opens
   fast and offline; everything dynamic is network-only. */

const CACHE = "clitc-shell-v5";
const SHELL = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icons/bean.svg",
  "/icons/bean-192.png",
  "/icons/bean-512.png",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((path) => c.add(path))))
      .catch(() => undefined),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function isStaticAsset(url) {
  return (
    url.pathname.startsWith("/assets/") ||
    url.pathname.startsWith("/icons/") ||
    /\.(?:js|css|png|svg|woff2?|webmanifest|ico)$/.test(url.pathname)
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // never cache mutations

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // third-party: passthrough

  // Live backend data is always network-only — never served from cache.
  if (url.pathname === "/api" || url.pathname.startsWith("/api/") || url.pathname.includes("/events/stream")) return;
  if ((req.headers.get("accept") || "").includes("text/event-stream")) return;

  // App-shell navigations: network-first, fall back to the cached shell offline.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("/index.html").then((r) => r || caches.match("/"))),
    );
    return;
  }

  // Hashed static assets: cache-first, refresh in the background.
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const network = fetch(req)
          .then((res) => {
            if (res && res.status === 200) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(req, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || network;
      }),
    );
  }
  // Everything else: default network handling.
});
