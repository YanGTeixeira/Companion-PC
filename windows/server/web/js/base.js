"use strict";
// ---------------------------------------------------------------- celular parado: passa as telas / relógio
prefs.dock = store.get("dock", 2);                 // minutos sem tocar
prefs.idleMode = store.get("idleMode", "cycle");   // cycle | clock | off
const IDLE_SLIDE_MS = 15000;
let idleT = Date.now(), idleOn = false, docked = false, dockMoveT = 0, idleI = 0, idleStepT = 0, idleFrom = null;
function idleList() {
  if (prefs.idleMode === "clock") return ["clock"];
  const playing = state.now?.media;
  const list = wideMQ.matches ? ["dash", playing ? "media" : null] : ["dash", state.daily?.weather || state.daily?.events?.length ? "today" : null, "games", playing ? "media" : null];
  return [...list.filter(Boolean), "clock"];
}
function idleStart() {
  if (idleOn || prefs.idleMode === "off" || !$("login").classList.contains("hidden") || !state.stats) return;
  if (document.querySelector(".overlay:not(.hidden)")) return;   // diálogo aberto
  idleOn = true; idleFrom = prefs.tab; idleI = -1; $("kbd").blur(); idleStep();
}
function idleStep() {
  const list = idleList();
  idleI = (idleI + 1) % list.length; idleStepT = Date.now();
  const v = list[idleI];
  docked = v === "clock";
  $("dock").classList.toggle("hidden", !docked);
  $("idle-catch").classList.toggle("hidden", docked);
  if (docked) { renderDock(); const h = new Date().getHours(); if (h >= 21 || h < 4) loadDay(); else $("dk-day").textContent = ""; } else showView(v, true);
}
function idleStop() {
  if (!idleOn) return;
  idleOn = docked = false; idleT = Date.now();
  $("dock").classList.add("hidden"); $("idle-catch").classList.add("hidden");
  showView(idleFrom || "dash", true);
}
function renderDock() {
  const s = state.stats; if (!s) return;
  const [h, m] = s.time.split(":");
  $("dk-h").textContent = h; $("dk-m").textContent = m;
  $("dk-date").textContent = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  $("dk-stats").textContent = [`CPU ${Math.round(s.cpu)}%`, `RAM ${Math.round(s.ram_pct)}%`,
    s.gpu ? `GPU ${Math.round(s.gpu.util)}% ${Math.round(s.gpu.temp)}°C` : ""].filter(Boolean).join("   ");
  const md = state.now?.media, g = state.games?.game;
  $("dk-media").textContent = md && md.status === "playing" ? `> ${md.title}${md.artist ? " / " + md.artist : ""}`
    : g ? `Jogando ${g.name}, ${humanDur(g.elapsed + (performance.now() - state.gamesT) / 1000)}${s.fps?.fps != null ? `, ${s.fps.fps} FPS` : ""}` : "";
  $("dk-extra").textContent = [s.mic?.muted ? "Microfone do PC no mudo" : "", s.timer ? `${s.timer.label} em ${fmtTime(s.timer.left)}` : "",
    focusEnd ? `Foco: ${fmtTime(Math.max(0, (focusEnd - Date.now()) / 1000))}` : ""].filter(Boolean).join("   ");
  renderDockDaily();
  if (Date.now() - dockMoveT > 60000) {   // desloca um pouco a cada minuto para não marcar a tela
    dockMoveT = Date.now();
    $("dk").style.transform = `translate(${(Math.random() * 4 - 2).toFixed(1)}vw, ${(Math.random() * 4 - 2).toFixed(1)}vh)`;
  }
}
["pointerdown", "keydown", "input"].forEach((ev) => addEventListener(ev, () => { idleT = Date.now(); }, true));
$("dock").onclick = $("idle-catch").onclick = idleStop;
$("dock-now").onclick = () => { buzz(8); setTimeout(idleStart, 150); };
$("dock-min").value = String(prefs.dock);
if (!$("dock-min").value) { prefs.dock = 2; $("dock-min").value = "2"; }
$("dock-min").onchange = () => { prefs.dock = +$("dock-min").value; store.set("dock", prefs.dock); idleT = Date.now(); };
$("idle-mode").value = prefs.idleMode;
$("idle-mode").onchange = () => { prefs.idleMode = $("idle-mode").value; store.set("idleMode", prefs.idleMode); idleT = Date.now(); };
setInterval(() => {
  if (idleOn) {
    if (docked) renderDock();
    if (Date.now() - idleStepT > IDLE_SLIDE_MS && idleList().length > 1) idleStep();
  } else if (prefs.idleMode !== "off" && !document.hidden && Date.now() - idleT > prefs.dock * 60000) idleStart();
}, 1000);

