// Service worker intentionally disabled for reliability during live demo.
// Keep this file to satisfy existing references while providing pass-through behavior.
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {
  // no-op: let browser/network handle all requests directly
});
