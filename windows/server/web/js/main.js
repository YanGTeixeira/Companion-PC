"use strict";
// ---------------------------------------------------------------- loop de tela
setInterval(() => {
  if (vis("media")) tickProgress();
  if (vis("games") && state.games?.game) renderGames();
}, 1000);

// tamanho da tela em Ajustes > Conexão (ajuda a acertar o layout de cada aparelho)
let CONN = "";
function showConn() { $("conn-info").textContent = [CONN, `tela ${innerWidth}×${innerHeight}`].filter(Boolean).join(" · "); }
addEventListener("resize", showConn); showConn();
if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("sw.js").catch(() => {});
// visual: cor do terminal e efeito de tubo
prefs.theme = store.get("theme", "green"); prefs.crt = store.get("crt", true); prefs.skin = store.get("skin", "fallout");
// temas: cada um tem variantes (cores) e alguns têm o efeito de tubo
// THEMES (temas e variantes) fica em catalogo.js: o mesmo para o app, o Personalizar e a página Jogador
function themeOk() {
  const t = THEMES.find((x) => x.id === prefs.skin) || THEMES[0];
  prefs.skin = t.id;
  if (!t.variants.some(([v]) => v === prefs.theme)) prefs.theme = t.variants[0][0];
  return t;
}
function renderThemePicker() {
  // temas inteiros novos (1.19) têm todas as variantes com cadeado: o tema todo aparece travado até liberar uma
  $("themes").innerHTML = THEMES.map((t) => {
    const free = t.variants.filter(([v]) => !themeLocked(t.id, v)), all = !free.length;
    return `<div class="thm${t.id === prefs.skin ? " on" : ""}${all ? " lockall" : ""}" data-skin="${t.id}" data-theme="${(free[0] || t.variants[0])[0]}">
    <button class="thb" data-pick="${t.id}"><span class="thn">${all ? "🔒 " : ""}${t.name}</span><small>${t.desc}</small></button>
    ${t.variants.length > 1 ? `<div class="thv">${t.variants.map(([v, l, c]) => { const lk = themeLocked(t.id, v); return `<button data-pick="${t.id}" data-var="${v}" class="${t.id === prefs.skin && v === prefs.theme ? "on" : ""}${lk ? " lock" : ""}" style="background:${c}" aria-label="${l}${lk ? " (bloqueado)" : ""}" title="${l}${lk ? " · libera em Jogador › Recompensas" : ""}">${lk ? "🔒" : ""}</button>`; }).join("")}</div>` : ""}</div>`;
  }).join("");
}
function pickTheme(skin, variant) {
  const t0 = THEMES.find((t) => t.id === skin);
  if (!variant && t0) variant = (t0.variants.find(([v]) => !themeLocked(skin, v)) || t0.variants[0])[0];
  if (variant && themeLocked(skin, variant)) {
    const r = state.conq.rewards.find((x) => x.id === `${skin}:${variant}`);
    return toast(`Esse tema libera no ${reqText(r)}`, "bad");
  }
  prefs.skin = skin; prefs.theme = variant || (THEMES.find((t) => t.id === skin)?.variants[0][0]);
  store.set("skin", prefs.skin); store.set("theme", prefs.theme); applyTheme();
  // o tema vale para todos os aparelhos: grava no PC
  if (ws && ws.readyState === 1) send("layout.set", { layout: { ...LAYOUT, skin: prefs.skin, theme: prefs.theme, crt: prefs.crt } }).catch(() => {});
}
// troca automática (Personalizar > Tema): o jogo aberto vence o horário; os dois vencem a escolha manual
const toMin = (hm) => { const [h, m] = String(hm || "0:0").split(":").map(Number); return (h || 0) * 60 + (m || 0); };
function autoPick() {
  const a = LAYOUT?.auto || {};
  if (a.game?.on) {
    const g = state.games?.game?.name || "", k = /dota/i.test(g) ? "dota2" : /counter-strike/i.test(g) ? "cs2" : null;
    if (k && a.game[k]) return a.game[k];
  }
  if (a.time?.on && a.time.night) {
    const d = new Date(), m = d.getHours() * 60 + d.getMinutes(), f = toMin(a.time.from || "19:00"), t = toMin(a.time.to || "07:00");
    const night = f > t ? m >= f || m < t : m >= f && m < t;
    return night ? a.time.night : a.time.day || null;
  }
  return null;
}
let themeEff = "";
function applyTheme() {
  themeOk();
  let skin = prefs.skin, theme = prefs.theme;
  const ap = autoPick();
  if (ap) {
    const [s2, v2] = ap.split(":"), t2 = THEMES.find((x) => x.id === s2);
    if (t2) { skin = s2; theme = t2.variants.some(([v]) => v === v2) ? v2 : t2.variants[0][0]; }
  }
  const t = THEMES.find((x) => x.id === skin);
  themeEff = skin + ":" + theme;
  document.documentElement.dataset.skin = skin;
  document.documentElement.dataset.theme = theme;
  document.body.classList.toggle("crt", prefs.crt && !!t.crt);
  $("sw-crt").closest(".set").classList.toggle("hidden", !t.crt);
  renderThemePicker();
  document.querySelector('meta[name="theme-color"]').content = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
  if (vis("dash")) drawSparks();
  if (typeof applyAccent === "function") applyAccent();
}
function autoTheme() {
  const ap = autoPick(), want = ap || prefs.skin + ":" + prefs.theme;
  if (want !== themeEff) applyTheme();
}
setInterval(autoTheme, 30000);
$("themes").onclick = (e) => { const b = e.target.closest("[data-pick]"); if (!b) return; buzz(8); pickTheme(b.dataset.pick, b.dataset.var); };
bindSwitch("sw-crt", "crt", () => { applyTheme(); if (ws && ws.readyState === 1) send("layout.set", { layout: { ...LAYOUT, skin: prefs.skin, theme: prefs.theme, crt: prefs.crt } }).catch(() => {}); });
bindSwitch("sw-deckauto", "deckAuto", () => { lastApp = null; });
bindSwitch("sw-snd", "snd", () => snd("ok"));
// animações dos temas, fundos, efeitos e cores (também param com "reduzir movimento" e bateria fraca)
prefs.anim = store.get("anim", true); ANIM.pref = prefs.anim; animSync();
bindSwitch("sw-anim", "anim", () => { ANIM.pref = prefs.anim; animSync(); });
bindSwitch("sw-pcnotif", "pcnotif", () => { if (ws && welcome.features?.notif) subNotif(); });
applyTheme();
showView(prefs.tab == "apps" ? "deck" : prefs.tab);
handleShared();
renderPower();
applyWake();
connect();
