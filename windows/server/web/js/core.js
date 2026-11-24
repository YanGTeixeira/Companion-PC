"use strict";
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- ajustes
const store = {
  get(k, d) { try { const v = localStorage.getItem("pcc." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("pcc." + k, JSON.stringify(v)); } catch {} },
};
// token via QR/link: http://pc:8770/#t=TOKEN  (o # não vai pela rede)
(() => {
  const m = location.hash.match(/[#&]t=([^&]+)/);
  if (m) store.set("token", decodeURIComponent(m[1]));
  const tab = location.hash.match(/[#&]tab=(\w+)/);   // link direto para uma aba: #tab=mouse
  if (tab) store.set("tab", tab[1]);
  if (m || tab) history.replaceState(null, "", location.pathname + location.search);
})();
// prévia dentro do editor do PC (/editor): sem som, sem vibrar, e o editor escolhe a aba
const PREVIEW = new URLSearchParams(location.search).has("preview");
const PREVIEW_LIVE = new Set(), LIVE_REAL = {};
addEventListener("message", (e) => {
  if (e.origin !== location.origin || !e.data || e.data.pcc !== "view") return;
  // Jogando e Reunião só existem ao vivo; na prévia aparecem quando o editor pede
  for (const v of ["play", "meet"]) if (v !== e.data.view && PREVIEW_LIVE.has(v)) { PREVIEW_LIVE.delete(v); if (!LIVE_REAL[v]) setLive(v, "", false, false); }
  if (["play", "meet"].includes(e.data.view) && !VIEWS.includes(e.data.view)) { PREVIEW_LIVE.add(e.data.view); setLive(e.data.view, e.data.view === "play" ? "Jogando" : "Reunião", true, false); }
  if (VIEWS.includes(e.data.view)) showView(e.data.view, true);
  if (e.data.layout) applyLayout(e.data.layout, true);
});
const prefs = { snd: store.get("snd", true), wake: store.get("wake", true), vib: store.get("vib", true), sens: store.get("sens", 1.8), tab: store.get("tab", "dash") };

// ---------------------------------------------------------------- formatação
const fmtBytes = (n, rate) => {
  n = +n || 0; const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i < 2 ? n.toFixed(0) : n.toFixed(1)) + " " + u[i] + (rate ? "/s" : "");
};
const fmtTime = (s) => { s = Math.max(0, Math.floor(s || 0)); const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${x}` : `${m}:${x}`; };
const humanDur = (s) => { s = Math.max(0, Math.floor(s || 0)); if (s < 60) return s + "s"; const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m} min`; };
const humanAgo = (s) => { s = Math.max(0, s || 0); if (s < 120) return "agora"; if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`; const d = Math.floor(s / 86400); return d === 1 ? "ontem" : `há ${d} dias`; };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const setBar = (id, pct) => { const b = $(id); pct = Math.max(0, Math.min(100, +pct || 0));
  b.firstElementChild.style.width = pct + "%"; b.classList.toggle("warn", pct >= 75 && pct < 90); b.classList.toggle("bad", pct >= 90); };

function buzz(ms = 12) { if (PREVIEW) return; snd(ms <= 8 ? "tab" : "tap"); if (prefs.vib && navigator.vibrate) try { navigator.vibrate(ms); } catch {} }
// sons de terminal: bipes de onda quadrada gerados na hora (sem arquivos)
let actx = null;
const SOUNDS = { alarm: [[880, 0.08], [1320, 0.08], [880, 0.08], [1320, 0.14]], tap: [[1900, 0.022]], tab: [[1300, 0.025], [1900, 0.025]], ok: [[1400, 0.045], [2100, 0.06]],
  err: [[320, 0.11], [220, 0.14]], on: [[800, 0.045], [1200, 0.045], [1800, 0.07]], off: [[1200, 0.06], [600, 0.1]], note: [[1700, 0.05], [1700, 0.05]] };
function snd(kind) {
  if (!prefs.snd) return;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    if (actx.state === "suspended") actx.resume();
    let t = actx.currentTime + 0.005;
    for (const [f, d] of SOUNDS[kind] || []) {
      const o = actx.createOscillator(), g = actx.createGain();
      o.type = "square"; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.035, t + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
      o.connect(g).connect(actx.destination); o.start(t); o.stop(t + d + 0.02); t += d + 0.018;
    }
  } catch {}
}
let toastT;
function toast(msg, kind = "") {
  if (kind === "ok" || kind === "bad") snd(kind === "ok" ? "ok" : "err");
  const t = $("toast"); t.textContent = msg; t.className = "toast " + kind;
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.add("hidden"), 2200);
}

// ---------------------------------------------------------------- conexão
let ws = null, welcome = {}, nextId = 1, retry = 0, retryT = null, wasOnline = false;
const pending = new Map();
let pageBuild = 0;
const state = { stats: null, now: null, games: null, art: {}, gameart: {}, nowT: 0, gamesT: 0 };

function wsUrl() { return (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"; }

function connect() {
  clearTimeout(retryT);
  const token = store.get("token", "");
  if (!token) { showLogin(); return; }
  setDot("wait", "Conectando…");
  const sock = ws = new WebSocket(wsUrl());
  sock.onopen = () => sock.send(JSON.stringify({ t: "hello", token, client: "android", ...(PREVIEW ? { role: "preview" } : {}),
    screen: `${innerWidth}x${innerHeight} dpr${devicePixelRatio} ${matchMedia("(orientation: landscape)").matches ? "deitado" : "em pé"} cq=${CSS.supports("container-type: size")} ${(navigator.userAgent.match(/Chrome\/[\d.]+/) || [navigator.userAgent.slice(0, 40)])[0]}` }));
  sock.onmessage = (ev) => { if (sock === ws) onMsg(JSON.parse(ev.data)); };
  sock.onclose = (ev) => {
    if (sock !== ws) return;
    ws = null;
    for (const [, p] of pending) p.reject(new Error("desconectado")); pending.clear();
    if (ev.code === 4001) { store.set("token", ""); setDot("", "Token inválido"); showLogin("Token inválido. Confira o config.json do PC."); return; }
    setDot("", "Desconectado");
    if (wasOnline) { wasOnline = false; snd("off"); }
    retry = Math.min(retry + 1, 6);
    retryT = setTimeout(connect, [500, 1000, 2000, 3000, 5000, 5000, 8000][retry]);
  };
  sock.onerror = () => {};
}

function send(a, p = {}, reply = true, timeout = 8000) {
  if (!ws || ws.readyState !== 1) { if (reply) toast("Sem conexão com o PC", "bad"); return Promise.reject(new Error("offline")); }
  const msg = { t: "req", a, p };
  if (!reply) { ws.send(JSON.stringify(msg)); return Promise.resolve(); }
  msg.id = nextId++;
  ws.send(JSON.stringify(msg));
  return new Promise((resolve, reject) => {
    pending.set(msg.id, { resolve, reject });
    setTimeout(() => { if (pending.delete(msg.id)) reject(new Error("sem resposta")); }, timeout);
  });
}
function act(a, p, label) {
  buzz();
  return send(a, p).then((d) => { if (label) toast(label, "ok"); return d; }).catch((e) => { if (e.message !== "offline") toast(e.message, "bad"); });
}

function onMsg(m) {
  switch (m.t) {
    case "welcome":
      // página nova no PC: recarrega (o app reconecta sozinho e nunca baixaria o HTML de novo)
      if (m.web && pageBuild && m.web !== pageBuild) { location.reload(); return; }
      pageBuild = pageBuild || m.web;
      welcome = m; retry = 0;
      if (m.layout) applyLayout(m.layout, true);
      $("host").textContent = m.host; $("os").textContent = m.os;
      setDot("ok", "");
      renderPower(); loadDeck(); pollMixer();
      if (vis("screen")) screenLoop();
      bootLine(`${m.host} conectado.`); bootDone();
      if (typeof dotaShown === "function") dotaShown();
      snd("on"); wasOnline = true;
      if (m.features?.notif) subNotif();
      libT = 0; if (vis("games")) loadGamesExtra();
      uT = 0; if (vis("usage")) setTimeout(loadUsage);
      vozHelpT = 0; vozDevs = false; if (vis("voz")) loadVoiceHelp();
      CONN = `${m.host} · servidor ${m.version} · ${location.host}`; showConn();
      $("b-secure").classList.toggle("hidden", !m.https || window.isSecureContext);
      break;
    case "res": {
      const p = pending.get(m.id); if (!p) return; pending.delete(m.id);
      m.ok ? p.resolve(m.d) : p.reject(new Error(m.e || "falhou"));
      break;
    }
    case "stats": state.stats = m.d; renderStats(); break;
    case "now": state.now = m.d; state.nowT = performance.now(); renderNow(); break;
    case "art": state.art = { [m.id]: "data:image/jpeg;base64," + m.jpg }; renderNow(); break;
    case "meet": onMeet(m.d); break;
    case "layout": applyLayout(m.d, true); break;
    case "deck": if (m.d && !deckEdit) { deckData = m.d; renderDeck(); } break;
    case "gsi": state.gsi = m.d; state.gsiT = Date.now(); renderGsi(); break;
    case "daily": state.daily = m.d; renderToday(); break;
    case "steam": onSteam(m.d); break;
    case "match_end": onMatchEnd(m.d); break;
    case "match_report": onMatchReport(m.d); break;
    case "dota_plan": onDotaPlan(m.d, m.reset); break;
    case "meet_soon": onMeetSoon(m.d); break;
    case "focus": onFocus(m.d); break;
    case "games": state.games = m.d; state.gamesT = performance.now(); renderGames(); onGameState(); break;
    case "gameart": state.gameart = { [m.id]: "data:image/jpeg;base64," + m.jpg }; renderGames(); renderPlay(); break;
    case "event":
      if (m.kind === "notif") { snd("note"); notify(`${m.app}: ${m.title}`, m.body, "pcn-" + m.app); break; }
      if (m.kind === "voice") { voiceEvent(m); break; }
      if (m.kind === "steam_done" && prefs.alerts.steam) notify("Steam: pronto para jogar", m.name, "steam-dl");
      if (m.kind === "download" && prefs.alerts.download) notify("Download concluído", m.name + (m.size ? ` · ${fmtBytes(m.size)}` : ""), "dl");
      break;
  }
}

function setDot(cls, text) {
  $("dot").className = $("dot2").className = "dot " + cls;
  $("via").textContent = text || (["localhost", "127.0.0.1"].includes(location.hostname) ? "cabo USB" : "Wi-Fi");
  $("banner").classList.toggle("hidden", cls === "ok" || !welcome.host);
  $("banner").textContent = "Sem conexão com o PC — tentando de novo…";
}

function showLogin(msg) {
  bootDone(true);
  $("login").classList.remove("hidden");
  if (msg) $("login").querySelector("p").textContent = msg;
  $("token").value = "";
  setTimeout(() => $("token").focus(), 50);
}
$("login-form").onsubmit = (e) => {
  e.preventDefault();
  const t = $("token").value.trim(); if (!t) return;
  store.set("token", t); $("login").classList.add("hidden"); connect();
};
// HTTP pela rede local -> o mesmo app no endereço HTTPS do PC (Tailscale), levando o token
$("b-secure").onclick = () => {
  if (!welcome.https) return;
  location.href = welcome.https + "#t=" + encodeURIComponent(store.get("token", ""));
};
$("b-logout").onclick = () => { store.set("token", ""); if (ws) { const s = ws; ws = null; s.close(); } showLogin(); };

