"use strict";
// ---------------------------------------------------------------- Reunião (Meet no Edge, pela extensão)
let meetSeen = null;   // reunião para a qual o app já mudou de aba sozinho
function onMeet(d) {
  state.meet = d;
  const live = !!(d && (d.inCall || d.lobby));
  setLive("meet", "Reunião", live);
  if (live && d.inCall && meetSeen !== d.code) {
    meetSeen = d.code;
    if (prefs.tab !== "meet") { showView("meet", true); toast("Reunião: atalhos abertos", "ok"); }
  }
  if (!live) meetSeen = null;
  renderMeet();
}
function renderMeet() {
  const d = state.meet, live = !!(d && (d.inCall || d.lobby));
  ["meet-chip", "meet-chip2"].forEach((id) => { $(id).classList.toggle("hidden", !live || vis("meet")); $(id).classList.toggle("muted", !!d && d.mic === false); });
  if (!live) return;
  $("mt-app").textContent = (d.app || "Meet").toUpperCase();
  $("mt-title").textContent = d.title || d.code || "Reunião";
  $("mt-ppl").textContent = d.people ? `${d.people} pessoa${d.people > 1 ? "s" : ""}` : "";
  $("mt-hint").textContent = d.lobby ? "Na sala de espera" : d.sharing ? "Você está compartilhando a tela" : "";
  const set = (k, on, lblOn, lblOff, can) => {
    const b = document.querySelector(`#mt-btns [data-m="${k}"]`); if (!b) return;
    b.disabled = can === false;
    b.classList.toggle("on", on === true); b.classList.toggle("off", on === false && (k === "mic" || k === "cam"));
    if (lblOn) b.querySelector(".dl").textContent = on ? lblOn : lblOff;
  };
  set("mic", d.mic, "Microfone ligado", "Mudo · toque para falar", d.can?.mic);
  set("cam", d.cam, "Câmera ligada", "Câmera desligada", d.can?.cam);
  set("hand", d.hand, "Abaixar a mão", "Levantar a mão", d.can?.hand);
  set("share", d.sharing, "Parar de compartilhar", "Compartilhar tela", d.can?.share);
  set("captions", null, null, null, d.can?.captions);
  document.querySelectorAll("#mt-btns [data-m]").forEach((b) => {
    const k = b.dataset.m, inCallOnly = ["share", "hand", "captions", "chat", "leave"].includes(k);
    b.classList.toggle("hidden", k === "join" ? !d.lobby : d.lobby && inCallOnly);
  });
  tickMeet();
}
const humanClock = (s) => { s = Math.floor(s); const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = s % 60; return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(x).padStart(2, "0"); };
function tickMeet() {
  if (!vis("meet")) return;
  const d = state.meet;
  $("mt-time").textContent = d?.since ? humanClock(Math.max(0, Date.now() / 1000 - d.since)) : "";
}
setInterval(tickMeet, 1000);
function meetCmd(cmd, arg) {
  return send("meet.cmd", arg == null ? { cmd } : { cmd, arg }).then((r) => { if (typeof r === "string") toast(r, "ok"); }).catch((e) => toast(e.message, "bad"));
}
$("mt-btns").addEventListener("click", (e) => {
  const b = e.target.closest("[data-m]"); if (!b || b.dataset.m === "leave") return;
  buzz(); meetCmd(b.dataset.m);
});
// sair: segurar 0,8 s (evita sair da chamada sem querer)
(() => {
  const b = document.querySelector('#mt-btns [data-m="leave"]'); let t = null;
  const start = (e) => { e.preventDefault(); b.classList.add("hold"); buzz(8); t = setTimeout(() => { b.classList.remove("hold"); buzz(40); meetCmd("leave"); }, 800); };
  const stop = () => { clearTimeout(t); b.classList.remove("hold"); };
  b.addEventListener("pointerdown", start); ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => b.addEventListener(ev, stop));
})();
["meet-chip", "meet-chip2"].forEach((id) => ($(id).onclick = () => { buzz(8); showView("meet"); }));

