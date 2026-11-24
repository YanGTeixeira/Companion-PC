"use strict";
// ---------------------------------------------------------------- Alertas
prefs.alerts = Object.assign({ steam: true, net: true, download: true, gpu: false, gpuV: 85, cpu: false, cpuV: 90, ram: false, ramV: 90, bat: true, batV: 15 }, store.get("alerts", {}));
const alertOn = {};
const saveAlerts = () => store.set("alerts", prefs.alerts);
["steam", "net", "download", "gpu", "cpu", "ram", "bat"].forEach((k) => {
  const sw = $("al-" + k); sw.classList.toggle("on", !!prefs.alerts[k]);
  sw.onclick = () => { prefs.alerts[k] = !prefs.alerts[k]; saveAlerts(); sw.classList.toggle("on", prefs.alerts[k]); buzz(8); if (prefs.alerts[k]) askNotify(false); };
  const inp = $(`al-${k}-v`);
  if (inp) { inp.value = prefs.alerts[k + "V"]; inp.onchange = () => { const v = +inp.value; if (v > 0) { prefs.alerts[k + "V"] = v; saveAlerts(); } else inp.value = prefs.alerts[k + "V"]; }; }
});
function checkAlerts(s) {
  const chk = (k, val, label, unit) => {
    if (!prefs.alerts[k] || val == null) return;
    const thr = prefs.alerts[k + "V"];
    if (val >= thr && !alertOn[k]) { alertOn[k] = true; notify(`${label} em ${Math.round(val)}${unit}`, `Passou de ${thr}${unit}`, k); }
    else if (val < thr - 5) alertOn[k] = false;   // só avisa de novo depois de baixar 5
  };
  chk("gpu", s.gpu?.temp, "GPU", "°C"); chk("cpu", s.sensors?.cpu_temp, "CPU", "°C"); chk("ram", s.ram_pct, "Memória", "%");
  if (prefs.alerts.bat) for (const b of s.bat || []) {
    if (b.pct == null || b.status === "off") continue;
    const k = "bat:" + b.id, thr = prefs.alerts.batV;
    if (b.pct <= thr && !b.charging && !alertOn[k]) { alertOn[k] = true; notify(`Bateria fraca: ${b.name} ${b.pct}%`, b.approx ? "nível aproximado" : "hora de carregar", "bat"); }
    else if (b.pct > thr + 5 || b.charging) alertOn[k] = false;
  }
}
let netDown = false;
function netAlert(p) {
  if (!p || !prefs.alerts.net) return;
  if (!p.ok && !netDown) { netDown = true; notify("Internet caiu", "O PC está sem conexão com a internet", "net"); }
  else if (p.ok && netDown) { netDown = false; toast(`Internet voltou (${p.ms} ms)`, "ok"); }
}
prefs.pcnotif = store.get("pcnotif", true);
function subNotif() {
  send("notif.sub", { on: prefs.pcnotif }).then((r) => {
    $("pcn-note").textContent = r?.available === false
      ? "Bloqueado no PC: Configurações do Windows > Privacidade > Notificações"
      : "WhatsApp, Discord, e-mail e outros avisos do Windows";
  }).catch(() => {});
}
async function notify(title, body, tag) {
  toast(`${title}${body ? " · " + body : ""}`, "warn");
  if (navigator.vibrate) try { navigator.vibrate([90, 60, 90]); } catch {}
  if (document.hidden && "Notification" in window && Notification.permission === "granted") {
    try {
      const reg = await navigator.serviceWorker?.getRegistration();
      if (reg) reg.showNotification(title, { body, tag, icon: "icon-192.png", badge: "icon-192.png" });
      else new Notification(title, { body, tag });
    } catch {}
  }
}
function askNotify(explicit) {
  if (!("Notification" in window) || !window.isSecureContext) {
    if (explicit) toast(welcome.https ? "Notificações precisam da versão segura (Ajustes › Conexão)" : "Notificações só funcionam com HTTPS (Tailscale) ou pelo cabo", "bad"); return;
  }
  if (Notification.permission === "default") Notification.requestPermission().then(updNotifBtn);
  else if (explicit && Notification.permission === "denied") toast("Bloqueadas — libere nas configurações do Chrome", "bad");
}
function updNotifBtn() {
  const ok = "Notification" in window && window.isSecureContext, p = ok ? Notification.permission : "na";
  $("al-notif").textContent = { granted: "Ativas", denied: "Bloqueadas", na: "Só com HTTPS" }[p] || "Ativar";
}
$("al-notif").onclick = () => askNotify(true);
updNotifBtn();

// ---------------------------------------------------------------- Ajustes do celular
let wakeLock = null;
// Sem HTTPS (Wi-Fi) o Android não dá wakeLock: um vídeo mudo e minúsculo em loop mantém a tela acesa
const keepVid = Object.assign(document.createElement("video"), { muted: true, loop: true, playsInline: true });
keepVid.setAttribute("muted", ""); keepVid.setAttribute("playsinline", ""); keepVid.setAttribute("aria-hidden", "true");
keepVid.innerHTML = '<source src="keepawake.webm" type="video/webm"><source src="keepawake.mp4" type="video/mp4">';
keepVid.style.cssText = "position:fixed;left:0;bottom:0;width:2px;height:2px;opacity:.01;pointer-events:none;z-index:-1";
document.body.appendChild(keepVid);
async function applyWake() {
  // jogando, a tela fica acesa mesmo com "manter tela ligada" desligado (os timers precisam da tela)
  const want = prefs.wake || !!state.games?.game;
  const native = "wakeLock" in navigator && window.isSecureContext;
  if (!native) { if (want && document.visibilityState === "visible") keepVid.play().catch(() => {}); else keepVid.pause(); return; }
  try {
    if (want && document.visibilityState === "visible" && !wakeLock) {
      wakeLock = await navigator.wakeLock.request("screen");
      wakeLock.addEventListener("release", () => (wakeLock = null));
    } else if (!want && wakeLock) { await wakeLock.release(); wakeLock = null; }
  } catch { /* sem HTTPS/localhost o Android não deixa */ }
}
function bindSwitch(id, key, onChange) {
  const sw = $(id); sw.classList.toggle("on", !!prefs[key]);
  sw.onclick = () => { prefs[key] = !prefs[key]; store.set(key, prefs[key]); sw.classList.toggle("on", prefs[key]); onChange && onChange(); };
}
bindSwitch("sw-wake", "wake", applyWake);
bindSwitch("sw-vib", "vib");
$("sw-full").onclick = () => {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  else document.documentElement.requestFullscreen({ navigationUI: "hide" }).catch(() => toast("Tela cheia indisponível", "bad"));
};
document.addEventListener("fullscreenchange", () => $("sw-full").classList.toggle("on", !!document.fullscreenElement));
// Travar deitado: o Android só deixa travar a rotação em tela cheia (ou no app instalado)
prefs.land = store.get("land", false);
async function applyLand() {
  $("sw-land").classList.toggle("on", prefs.land);
  if (!screen.orientation?.lock) return;
  try {
    if (prefs.land) {
      if (!document.fullscreenElement && !matchMedia("(display-mode: fullscreen)").matches)
        await document.documentElement.requestFullscreen({ navigationUI: "hide" });
      await screen.orientation.lock("landscape");
    } else screen.orientation.unlock();
  } catch { if (prefs.land) toast("Não deu para travar a rotação aqui", "bad"); }
}
$("sw-land").onclick = () => { prefs.land = !prefs.land; store.set("land", prefs.land); applyLand(); };
$("sw-land").classList.toggle("on", prefs.land);
// tela cheia exige um toque: reaplica no primeiro toque depois de abrir o app
document.addEventListener("pointerdown", () => { if (prefs.land && !document.fullscreenElement) applyLand(); }, { once: true });
$("sens").value = prefs.sens; $("sens-val").textContent = prefs.sens + "×";
$("sens").oninput = () => { prefs.sens = +$("sens").value; store.set("sens", prefs.sens); $("sens-val").textContent = prefs.sens.toFixed(1) + "×"; };
document.addEventListener("pointerdown", () => applyWake(), { once: true });   // o vídeo só toca depois de um toque

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") { applyWake(); if (!ws) { retry = 0; connect(); } else if (vis("screen")) screenLoop(); }
});

