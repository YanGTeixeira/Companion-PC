"use strict";
// ---------------------------------------------------------------- Enviar / receber
function sendText(paste) {
  const text = $("snd-text").value;
  if (!text) return toast("Escreva ou cole algo primeiro", "bad");
  act("clip.set", { text, paste }, paste ? "Colado no PC" : "Copiado no PC (Ctrl+V lá)");
}
$("snd-copy").onclick = () => sendText(false);
$("snd-paste").onclick = () => sendText(true);
$("snd-folder").onclick = () => act("file.open_folder", {}, "Abrindo a pasta no PC");
$("snd-files").onchange = (e) => { uploadFiles([...e.target.files]); e.target.value = ""; };
const CHUNK = 512 * 1024;
let upQueue = Promise.resolve();
function uploadFiles(files) {
  for (const f of files) { const row = addUpRow(f); upQueue = upQueue.then(() => uploadOne(f, row)); }
}
function addUpRow(f) {
  const row = document.createElement("div"); row.className = "uprow";
  row.innerHTML = `<div class="row"><span>${esc(f.name)}</span><span class="st">na fila · ${fmtBytes(f.size)}</span></div><div class="bar"><i></i></div>`;
  $("up-list").prepend(row); return row;
}
function b64(buf) {
  const u = new Uint8Array(buf); let x = "";
  for (let i = 0; i < u.length; i += 0x8000) x += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
  return btoa(x);
}
async function uploadOne(f, row) {
  const st = row.querySelector(".st"), bar = row.querySelector(".bar i"); let id = null;
  try {
    ({ id } = await send("file.begin", { name: f.name, size: f.size }));
    const t0 = performance.now();
    for (let off = 0; off < f.size; off += CHUNK) {
      await send("file.chunk", { id, data: b64(await f.slice(off, off + CHUNK).arrayBuffer()) });
      const done = Math.min(f.size, off + CHUNK), sec = Math.max((performance.now() - t0) / 1000, 0.001);
      bar.style.width = (done / f.size) * 100 + "%";
      st.textContent = `${Math.round((done / f.size) * 100)}% · ${fmtBytes(done / sec, true)}`;
    }
    const r = await send("file.end", { id });
    st.textContent = "OK " + r.name; row.classList.add("done"); bar.style.width = "100%"; buzz(25);
  } catch (e) {
    st.textContent = "falhou: " + e.message; row.classList.add("fail");
    if (id) send("file.cancel", { id }, false).catch(() => {});
  }
}
async function copyLocal(text) {
  try { await navigator.clipboard.writeText(text); }
  catch { const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
  toast("Copiado no celular", "ok"); buzz();
}
$("rcv-get").onclick = async () => {
  buzz(); const out = $("rcv-out"); out.innerHTML = '<div class="empty">Buscando…</div>';
  try {
    const r = await send("clip.get");
    if (r.kind === "text") {
      const url = /^https?:\/\/\S+$/.test(r.text.trim()) ? r.text.trim() : null;
      out.innerHTML = `<pre class="cliptext"></pre><div class="brow"><button class="btn primary" id="rcv-copy">Copiar no celular</button>${url ? '<a class="btn" id="rcv-open" target="_blank" rel="noopener">Abrir link</a>' : ""}</div>`;
      out.querySelector("pre").textContent = r.text;
      $("rcv-copy").onclick = () => copyLocal(r.text);
      if (url) $("rcv-open").href = url;
    } else if (r.kind === "image") {
      out.innerHTML = `<img class="clipimg" src="data:image/jpeg;base64,${r.preview}" alt="Imagem copiada no PC"><div class="sub" style="margin-top:6px">${r.w}×${r.h} px</div>
        <div class="brow"><a class="btn primary" href="${r.url}" download="${esc(r.name)}">Salvar no celular</a></div>`;
    } else if (r.kind === "files") {
      out.innerHTML = '<div style="margin-top:10px"></div>' + r.files.map((f) => `<div class="row"><span>${f.dir ? "[pasta] " : ""}${esc(f.name)}</span><span>${f.url
        ? `<a class="lnk" href="${f.url}" download="${esc(f.name)}">baixar · ${fmtBytes(f.size)}</a>` : f.dir ? "pasta (não dá)" : "grande demais"}</span></div>`).join("");
    } else out.innerHTML = '<div class="empty">Nada copiado no PC.</div>';
  } catch (e) { out.innerHTML = `<div class="empty">Erro: ${esc(e.message)}</div>`; }
};
// Compartilhar de outro app (PWA instalado): o service worker guarda e redireciona para /?shared=1
async function handleShared() {
  const q = new URLSearchParams(location.search);
  if (!q.has("shared")) return;
  history.replaceState(null, "", "/");
  try {
    const cache = await caches.open("share"), metaR = await cache.match("/share-meta");
    if (!metaR) return;
    const meta = await metaR.json(), files = [];
    for (const f of meta.files) { const r = await cache.match(f.key); if (r) files.push(new File([await r.blob()], f.name, { type: r.headers.get("Content-Type") || "" })); }
    await Promise.all((await cache.keys()).map((k) => cache.delete(k)));
    showView("send");
    const text = [meta.title, meta.text, meta.url].filter(Boolean).join("\n");
    if (text) $("snd-text").value = text;
    if (files.length) { toast(`Enviando ${files.length} arquivo(s) ao PC…`, "ok"); waitConnected().then(() => uploadFiles(files)); }
  } catch { toast("Não consegui receber o compartilhamento", "bad"); }
}
const waitConnected = () => new Promise((res) => { const chk = () => (welcome.host && ws && ws.readyState === 1 ? res() : setTimeout(chk, 300)); chk(); });

