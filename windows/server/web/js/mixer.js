"use strict";
// ---------------------------------------------------------------- Mixer e saída de áudio
let mixData = null, mixBusy = false, mixDrag = null, mixT = 0;
async function pollMixer() {
  if (mixBusy || !ws || ws.readyState !== 1 || !welcome.features?.mixer || document.hidden) return;
  mixBusy = true; mixT = Date.now();
  try { mixData = await send("mixer.get"); renderMixer(); } catch {} finally { mixBusy = false; }
}
setInterval(() => { if ((vis("media") || vis("mix")) && Date.now() - mixT > (vis("mix") ? 450 : 4000)) pollMixer(); }, 250);
function renderMixer() {
  const d = mixData; if (!d) return;
  const cur = d.outputs.find((o) => o.default);
  $("out-name").textContent = cur ? cur.name : "–";
  if (!vis("mix")) return;
  $("outs").innerHTML = d.outputs.map((o) => `<button class="outrow${o.default ? " on" : ""}" data-id="${esc(o.id)}"><i></i><span>${esc(o.name)}</span></button>`).join("")
    || '<div class="empty">Nenhuma saída ativa</div>';
  $("mx-master").textContent = d.master ? (d.master.muted ? "PC: mudo" : `PC: ${d.master.level}%`) : "";
  const list = $("mx-list"), seen = new Set();
  list.querySelector(".empty")?.remove();
  for (const a of d.apps) {
    seen.add(a.key);
    let row = [...list.children].find((r) => r.dataset.key === a.key);
    if (!row) {
      row = document.createElement("div"); row.className = "mxrow"; row.dataset.key = a.key;
      row.innerHTML = '<span class="mxic"></span><div class="mxmid"><div class="mxname"></div><input type="range" min="0" max="100"><div class="peak"><i></i></div></div><span class="mxval"></span><button class="mxmute"></button>';
      list.appendChild(row); bindMixRow(row);
    }
    row.querySelector(".mxic").textContent = a.key === "_system" ? "#" : a.name.slice(0, 1).toUpperCase();
    row.querySelector(".mxname").textContent = a.name;
    if (mixDrag !== a.key) { row.querySelector("input").value = a.level; row.querySelector(".mxval").textContent = a.level + "%"; }
    row.querySelector(".mxmute").textContent = a.muted ? "MUDO" : "SOM";
    row.classList.toggle("muted", a.muted);
    row.querySelector(".peak i").style.setProperty("--pk", Math.min(100, Math.sqrt(a.peak) * 100) + "%");
  }
  [...list.children].forEach((r) => { if (r.dataset.key && !seen.has(r.dataset.key)) r.remove(); });
  if (!d.apps.length) list.innerHTML = '<div class="empty">Nenhum app tocando som agora</div>';
}
function bindMixRow(row) {
  const key = row.dataset.key, inp = row.querySelector("input"); let t = 0;
  inp.addEventListener("input", () => {
    mixDrag = key; row.querySelector(".mxval").textContent = inp.value + "%";
    const now = performance.now(); if (now - t > 70) { t = now; send("mixer.set", { key, level: +inp.value }, false).catch(() => {}); }
  });
  inp.addEventListener("change", () => { send("mixer.set", { key, level: +inp.value }, false).catch(() => {}); setTimeout(() => { if (mixDrag === key) mixDrag = null; }, 900); });
  row.querySelector(".mxmute").onclick = () => { buzz(8); send("mixer.set", { key, muted: "toggle" }).then((d) => { if (d) { mixData = d; renderMixer(); } }).catch((e) => toast(e.message, "bad")); };
}
$("outs").onclick = (e) => {
  const b = e.target.closest(".outrow"); if (!b || b.classList.contains("on")) return;
  buzz(); act("audio.set_output", { id: b.dataset.id }).then((name) => { if (name) toast("Saída: " + name, "ok"); mixT = 0; pollMixer(); });
};
$("out-chip").onclick = () => { buzz(); act("audio.cycle").then((name) => { if (name) toast("Saída: " + name, "ok"); mixT = 0; pollMixer(); }); };
