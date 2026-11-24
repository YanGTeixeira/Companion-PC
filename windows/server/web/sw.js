// Service worker: permite instalar como app, receber "Compartilhar" de outros
// apps (fotos, arquivos, links) e abrir o app com o PC desligado ou fora de alcance
// (mostra "desconectado" e tenta de novo). Só roda com HTTPS ou pelo cabo (localhost).
//
// Arquivos do app: sempre da rede primeiro (nunca fica velho com o PC ligado); se o PC
// não responder em NET_WAIT_MS, usa a última cópia guardada.
const APP_CACHE = "app-v1", NET_WAIT_MS = 4000;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k.startsWith("app-") && k !== APP_CACHE) await caches.delete(k);
  await self.clients.claim();
})()));

function appFile(req, url) {
  return req.method === "GET" && url.origin === self.location.origin && !url.pathname.startsWith("/dl/")
    && !req.headers.has("range")   // vídeo da tela ligada vem em pedaços (206): fica com o navegador
    && !url.pathname.startsWith("/share") && !url.searchParams.has("preview");
}

async function networkFirst(req) {
  const cache = await caches.open(APP_CACHE);
  const key = new URL(req.url); key.hash = ""; key.search = "";   // "/?shared=1" e "/" são a mesma página
  const net = fetch(req).then((r) => { if (r.status === 200) cache.put(key.href, r.clone()).catch(() => {}); return r; });
  const timeout = new Promise((res) => setTimeout(res, NET_WAIT_MS));
  const first = await Promise.race([net.catch(() => null), timeout]);
  if (first) return first;
  const saved = await cache.match(key.href);
  if (saved) return saved;
  return net;   // nada guardado: espera a rede mesmo (ou o erro dela)
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (appFile(e.request, url)) { e.respondWith(networkFirst(e.request)); return; }
  if (e.request.method !== "POST" || url.pathname !== "/share") return;
  e.respondWith((async () => {
    const form = await e.request.formData();
    const cache = await caches.open("share");
    await Promise.all((await cache.keys()).map((k) => cache.delete(k)));
    const meta = { title: form.get("title") || "", text: form.get("text") || "", url: form.get("url") || "", files: [] };
    let i = 0;
    for (const f of form.getAll("files")) {
      if (!(f instanceof File)) continue;
      const key = `/share-file/${i++}`;
      await cache.put(key, new Response(f, { headers: { "Content-Type": f.type || "application/octet-stream" } }));
      meta.files.push({ key, name: f.name, size: f.size });
    }
    await cache.put("/share-meta", new Response(JSON.stringify(meta), { headers: { "Content-Type": "application/json" } }));
    return Response.redirect("/?shared=1", 303);
  })());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window" }).then((cs) => (cs[0] ? cs[0].focus() : self.clients.openWindow("/"))));
});
