// Private messages and authenticated HTML must never enter Cache Storage.
const CACHE_NAME="fresh-ai-chat-static-v0.3.2";
self.addEventListener("install",event=>{self.skipWaiting();});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("fresh-ai-chat-")).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener("fetch",event=>{ /* network-only: no response caching */ });
